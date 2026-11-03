"""
contradiction_agent.py

WHAT: identifies comparable cross-paper claim pairs and classifies them as
"Agrees" or "Contradicts" using deterministic value-gap rules.

COMPARABILITY RULES
-------------------
Two claims are compared only when they share all of the following:
    1. benchmark_name
    2. value_type
    3. model identity
    4. evaluation setting (for example 0-shot / 5-shot)
    5. metric identity when it can be established
    6. measurement scope when it can be established

WHY model identity is required
------------------------------
Different models are expected to have different benchmark scores. A score of
56.8 from one model and 71.7 from another is not, by itself, a contradiction.
The earlier implementation grouped only by benchmark + value_type, which
created hundreds of meaningless cross-model comparisons once full-text claim
extraction started producing richer tables.

WHY evaluation setting is required
-----------------------------------
A model can report different results under different evaluation protocols,
such as 0-shot versus 5-shot. Those are different measurements and should not
be treated as contradictory merely because the numbers differ.

WHY value normalization is required
-----------------------------------
Some papers report accuracy as a proportion (0.845) while others report the
same kind of accuracy as a percentage (84.5). For comparison purposes only,
absolute_accuracy values in (0, 1] are converted to percentage scale. The
original reported_value is never modified in the database.

SOURCE TRACEABILITY
-------------------
When Evidence rows are available, their citation_text is used to recover
shot-setting and metric information. Claims with unknown settings may only
be compared with claims whose settings are also unknown.

IDEMPOTENT
----------
Reruns do not create duplicate Contradiction rows because
 db_schema.contradiction_exists() is used by insert_contradiction().
"""

import itertools
import re
from typing import Dict, List, Optional, Tuple, Any

from db_schema import get_session, Claim, insert_contradiction

try:
    from db_schema import Evidence
except ImportError:  # defensive compatibility with older schemas
    Evidence = None

from config import (
    CONTRADICTION_AGREE_MAX_DIFF,
    CONTRADICTION_HIGH_SEVERITY_DIFF,
)


# ============================================================
# MODEL DETECTION
# ============================================================

# Common LLM family tokens. These are only used to identify a model subject;
# they do not change the benchmark or claim value itself.
_MODEL_HINTS = (
    "gpt",
    "claude",
    "gemini",
    "llama",
    "llama2",
    "llama3",
    "qwen",
    "phi",
    "mistral",
    "mixtral",
    "gemma",
    "granite",
    "falcon",
    "nemotron",
    "deepseek",
    "yi",
    "command-r",
    "commandr",
    "roberta",
    "bert",
    "t5",
    "flan",
    "opt",
    "bloom",
    "vicuna",
    "alpaca",
    "zephyr",
    "olmo",
    "internlm",
    "internvl",
    "mpt",
    "jamba",
    "starcoder",
    "codellama",
)

_MODEL_VERBS = (
    "achieves",
    "achieved",
    "reports",
    "reported",
    "obtains",
    "obtained",
    "scores",
    "scored",
    "gets",
    "got",
    "has",
    "shows",
    "showed",
    "records",
    "recorded",
    "attains",
    "attained",
    "reaches",
    "reached",
    "obtains an accuracy of",
)

_GENERIC_SUBJECTS = {
    "the model",
    "model",
    "the system",
    "system",
    "the method",
    "method",
    "the approach",
    "approach",
}


def _normalize_model_name(model_name: str) -> str:
    """Normalize model naming differences for comparison only."""
    if not model_name:
        return ""

    value = str(model_name).strip().lower()
    value = re.sub(r"\bthe\s+", "", value)
    value = re.sub(r"\bmodel\b", "", value)
    value = re.sub(r"[^a-z0-9]+", "", value)
    return value


def _extract_model_name(claim_text: str) -> Optional[str]:
    """
    Extract the model subject from common claim formulations.

    Examples:
        GPT-4o achieves an average accuracy of 0.845 on MMLU.
        Qwen2.5-3B-Instruct achieves 65.4 on MMLU.
    """
    if not claim_text:
        return None

    text = " ".join(str(claim_text).split()).strip()

    escaped_verbs = sorted(
        (re.escape(v) for v in _MODEL_VERBS),
        key=len,
        reverse=True,
    )
    verb_pattern = "|".join(escaped_verbs)

    match = re.match(
        rf"^\s*(?P<subject>.+?)\s+(?:{verb_pattern})\b",
        text,
        flags=re.IGNORECASE,
    )

    if not match:
        return None

    subject = match.group("subject").strip(" .,:;-\t")
    subject = re.sub(r"^the\s+", "", subject, flags=re.IGNORECASE)

    if not subject:
        return None

    if subject.lower() in _GENERIC_SUBJECTS:
        return None

    normalized = _normalize_model_name(subject)
    if not normalized:
        return None

    # Require a recognizable model-family token or a model-like identifier
    # containing a digit. This blocks accidental subjects such as
    # "Science Fundamentals" from entering contradiction groups.
    lowered = normalized.lower()
    has_model_hint = any(
        hint.replace("-", "") in lowered
        for hint in _MODEL_HINTS
    )
    has_digit = any(ch.isdigit() for ch in lowered)

    if not has_model_hint and not has_digit:
        return None

    return normalized


# ============================================================
# EVALUATION SETTING / METRIC
# ============================================================


def _normalize_shot_setting(text: str) -> Optional[str]:
    """Return a canonical shot-count setting such as '0-shot' or '5-shot'."""
    if not text:
        return None

    lowered = " ".join(str(text).lower().split())

    if re.search(r"\bzero[- ]shot\b", lowered):
        return "0-shot"

    if re.search(r"\bone[- ]shot\b", lowered):
        return "1-shot"

    if re.search(r"\btwo[- ]shot\b", lowered):
        return "2-shot"

    if re.search(r"\bfew[- ]shot\b", lowered):
        return "few-shot"

    match = re.search(r"\b(\d+)\s*[- ]\s*shot\b", lowered)
    if match:
        return f"{int(match.group(1))}-shot"

    match = re.search(r"\b(\d+)shot\b", lowered)
    if match:
        return f"{int(match.group(1))}-shot"

    return None


def _extract_metric(text: str, value_type: str) -> Optional[str]:
    """
    Identify the metric represented by the claim/evidence.

    When the claim's value_type is absolute_accuracy, accuracy is the default
    metric only when no more specific metric is visible.
    """
    if not text:
        return "accuracy" if value_type == "absolute_accuracy" else None

    lowered = " ".join(str(text).lower().split())

    metric_patterns = (
        ("exact_match", ("exact match", "exact-match")),
        ("f1", ("f1", "f1-score", "f1 score")),
        ("bleu", ("bleu",)),
        ("rouge", ("rouge",)),
        ("precision", ("precision",)),
        ("recall", ("recall",)),
        ("auc", ("auc", "area under the curve")),
        ("average_score", ("average score", "avg. score", "avg score")),
        ("accuracy", ("accuracy", "correct answers")),
    )

    for canonical, terms in metric_patterns:
        if any(term in lowered for term in terms):
            return canonical

    if value_type == "absolute_accuracy":
        return "accuracy"

    return None



def _extract_measurement_scope(
    claim,
    evidence_text: str = "",
) -> Optional[str]:
    """
    Identify the population/aggregation scope of a benchmark measurement.

    Examples:
        "average accuracy ... on MMLU" -> "average"
        "... on MMLU (Humanities)" -> "humanities"
        "... on High School Government And Politics on MMLU"
            -> "high school government and politics"

    This prevents a whole-benchmark average from being compared with a
    subject/category score from another paper.
    """
    claim_text = " ".join(
        str(getattr(claim, "claim_text", "") or "").split()
    ).strip()
    evidence = " ".join(str(evidence_text or "").split()).strip()
    combined = f"{claim_text}\n{evidence}".strip()

    lowered = combined.lower()

    # Explicit aggregate wording in the claim is the strongest signal.
    if re.search(r"\baverage\s+(?:accuracy|score|performance)\b", lowered):
        return "average"

    # Common MMLU category scopes.  Match specific subjects/categories
    # before broad aggregate labels so that:
    #   "High School Government And Politics"
    # is not incorrectly reduced to:
    #   "social science"
    # merely because the broad category also appears nearby.
    scope_terms = (
        "high school government and politics",
        "high school government & politics",
        "professional accounting",
        "humanities",
        "social sciences",
        "social science",
        "stem",
        "other",
    )

    for term in scope_terms:
        if re.search(rf"\b{re.escape(term)}\b", lowered):
            return term.replace("&", "and")

    # If the claim explicitly says "on <subject> on MMLU", use the subject.
    match = re.search(
        r"\bon\s+(.+?)\s+on\s+(?:the\s+)?mmlu\b",
        claim_text,
        flags=re.IGNORECASE,
    )
    if match:
        scope = match.group(1).strip(" .,:;()-")
        if scope:
            return " ".join(scope.lower().split())

    # Parenthesized scope in the claim, e.g. "MMLU (Humanities)".
    match = re.search(
        r"\bmmlu\s*\(([^)]+)\)",
        claim_text,
        flags=re.IGNORECASE,
    )
    if match:
        scope = match.group(1).strip()
        # Do not treat shot-setting as measurement scope.
        if not re.search(r"\b\d+\s*[- ]?\s*shot\b", scope, re.IGNORECASE):
            if scope.lower() not in {"0-shot", "1-shot", "2-shot", "few-shot"}:
                return " ".join(scope.lower().split())

    return None


def _extract_evaluation_signature(
    claim,
    evidence_text: str = "",
) -> Tuple[Optional[str], Optional[str]]:
    """
    Return (evaluation_setting, metric).

    Claim text is combined with Evidence.citation_text so table headers such
    as 'MMLU (0-shot)' are visible when the claim text itself only says
    'achieves 56.8 on MMLU'.
    """
    claim_text = str(getattr(claim, "claim_text", "") or "")
    value_type = str(getattr(claim, "value_type", "") or "")

    combined = f"{claim_text}\n{evidence_text}".strip()

    shot_setting = _normalize_shot_setting(combined)
    metric = _extract_metric(combined, value_type)

    return shot_setting, metric


# ============================================================
# VALUE NORMALIZATION
# ============================================================


def _normalized_comparison_value(
    value: Any,
    value_type: str,
) -> Optional[float]:
    """
    Normalize only the comparison representation.

    For absolute_accuracy:
        0.845 -> 84.5
        84.5  -> 84.5

    Other value types are left untouched because a decimal improvement may
    legitimately have a domain-specific interpretation that should not be
    guessed.
    """
    if value is None:
        return None

    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return None

    if value_type == "absolute_accuracy" and 0 < abs(numeric) <= 1:
        numeric *= 100.0

    return numeric


# ============================================================
# DIAGNOSTIC HELPERS
# ============================================================


def _claim_context(
    claim,
    evidence_text: str = "",
) -> Dict[str, Any]:
    """Build deterministic comparison metadata for one Claim row."""
    model_key = _extract_model_name(
        str(getattr(claim, "claim_text", "") or "")
    )

    setting, metric = _extract_evaluation_signature(
        claim,
        evidence_text=evidence_text,
    )
    measurement_scope = _extract_measurement_scope(
        claim,
        evidence_text=evidence_text,
    )

    return {
        "claim": claim,
        "evidence_text": evidence_text or "",
        "model_key": model_key,
        "evaluation_setting": setting,
        "metric": metric,
        "measurement_scope": measurement_scope,
    }


def _display_model(model_key: Optional[str]) -> str:
    return model_key if model_key else "UNKNOWN_MODEL"


def _display_setting(setting: Optional[str]) -> str:
    return setting if setting else "UNKNOWN_SETTING"


def _display_metric(metric: Optional[str]) -> str:
    return metric if metric else "UNKNOWN_METRIC"


# ============================================================
# CONTRADICTION CLASSIFICATION
# ============================================================


def _classify(diff: float) -> tuple:
    """
    Turn a numeric gap into (relation_type, severity).

    Thresholds remain owned by config.py, preserving the project's
    existing deterministic scoring design.
    """
    if diff <= CONTRADICTION_AGREE_MAX_DIFF:
        return "Agrees", "Low"

    severity = (
        "High"
        if diff > CONTRADICTION_HIGH_SEVERITY_DIFF
        else "Medium"
    )

    return "Contradicts", severity


# ============================================================
# PAIRWISE COMPARISON
# ============================================================


def find_contradictions_in_group(
    claims_for_one_group: list,
) -> list:
    """
    Compare claims that already belong to the same benchmark/value_type/
    model/evaluation-setting/metric group.

    The function is defensive and re-checks the comparability conditions so
    callers cannot accidentally bypass the rules.
    """
    results = []

    for item_a, item_b in itertools.combinations(
        claims_for_one_group,
        2,
    ):
        # Support both enriched context dictionaries and direct Claim objects.
        context_a = (
            item_a
            if isinstance(item_a, dict) and "claim" in item_a
            else _claim_context(item_a)
        )
        context_b = (
            item_b
            if isinstance(item_b, dict) and "claim" in item_b
            else _claim_context(item_b)
        )

        a = context_a["claim"]
        b = context_b["claim"]

        # Same-paper restatements are not cross-paper contradictions.
        if a.paper_id == b.paper_id:
            continue

        # Defensive model check.
        if not context_a["model_key"] or not context_b["model_key"]:
            continue

        if context_a["model_key"] != context_b["model_key"]:
            continue

        # Only compare claims with matching evaluation settings.
        # None matches None, but None does not match a known setting.
        if (
            context_a["evaluation_setting"]
            != context_b["evaluation_setting"]
        ):
            continue

        # Defensive metric check.
        if context_a["metric"] and context_b["metric"]:
            if context_a["metric"] != context_b["metric"]:
                continue

        # Defensive measurement-scope check.
        # If both scopes are known, they must refer to the same population or
        # aggregation (e.g. average vs Humanities). Unknown scope is allowed
        # only when the other side is also unknown.
        scope_a = context_a.get("measurement_scope")
        scope_b = context_b.get("measurement_scope")
        if scope_a != scope_b:
            continue

        if a.reported_value is None or b.reported_value is None:
            continue

        value_a = _normalized_comparison_value(
            a.reported_value,
            a.value_type,
        )
        value_b = _normalized_comparison_value(
            b.reported_value,
            b.value_type,
        )

        if value_a is None or value_b is None:
            continue

        diff = round(abs(value_a - value_b), 2)
        relation_type, severity = _classify(diff)

        results.append({
            "claim_a_id": a.id,
            "claim_b_id": b.id,
            "claim_a_text": a.claim_text,
            "claim_b_text": b.claim_text,
            "benchmark_name": a.benchmark_name,
            "value_type": a.value_type,
            "model_name": context_a["model_key"],
            "evaluation_setting": context_a["evaluation_setting"],
            "metric": context_a["metric"],
            "measurement_scope": context_a.get("measurement_scope"),
            "reported_value_a": a.reported_value,
            "reported_value_b": b.reported_value,
            "comparison_value_a": round(value_a, 4),
            "comparison_value_b": round(value_b, 4),
            "relation_type": relation_type,
            "severity": severity,
            "value_diff": diff,
        })

    return results


# ============================================================
# LOAD EVIDENCE TEXTS
# ============================================================


def _load_evidence_texts(
    session,
    claim_ids: List[int],
) -> Dict[int, str]:
    """Load citation/source text for shot-setting and metric detection."""
    if Evidence is None or not claim_ids:
        return {}

    evidence_map: Dict[int, List[str]] = {}

    rows = (
        session.query(Evidence)
        .filter(Evidence.claim_id.in_(claim_ids))
        .all()
    )

    for row in rows:
        claim_id = getattr(row, "claim_id", None)
        citation_text = getattr(row, "citation_text", "")

        if claim_id is None or not citation_text:
            continue

        evidence_map.setdefault(
            claim_id,
            [],
        ).append(
            str(citation_text)
        )

    return {
        claim_id: "\n".join(texts)
        for claim_id, texts in evidence_map.items()
    }


# ============================================================
# DETECT ALL CONTRADICTIONS
# ============================================================


def detect_all_contradictions(session=None) -> list:
    """
    Load all eligible claims and compare only truly compatible measurements.

    Required comparison key:
        (benchmark_name, value_type, model, evaluation_setting, metric,
         measurement_scope)

    Claims missing a model identity are excluded. Claims with unknown
    evaluation settings may be compared only with claims that also have
    unknown settings, subject to the other comparability checks.
    """
    close_session = False

    if session is None:
        session = get_session()
        close_session = True

    claims = (
        session.query(Claim)
        .filter(Claim.benchmark_name.isnot(None))
        .filter(Claim.reported_value.isnot(None))
        .filter(Claim.value_type.isnot(None))
        .all()
    )

    if not claims:
        print("[info] no typed benchmark claims available for contradiction analysis")
        if close_session:
            session.close()
        return []

    evidence_texts = _load_evidence_texts(
        session,
        [claim.id for claim in claims],
    )

    # Keep the historical diagnostic for untyped rows.
    skipped_untyped = (
        session.query(Claim)
        .filter(Claim.benchmark_name.isnot(None))
        .filter(Claim.reported_value.isnot(None))
        .filter(Claim.value_type.is_(None))
        .count()
    )

    if skipped_untyped:
        print(
            f"[info] skipping {skipped_untyped} claim(s) with a reported_value "
            f"but no value_type - excluded from comparison"
        )

    contexts = []

    skipped_missing_model = 0
    skipped_missing_setting = 0

    for claim in claims:
        context = _claim_context(
            claim,
            evidence_text=evidence_texts.get(claim.id, ""),
        )

        print("\n" + "=" * 70)
        print("[CONTRADICTION DEBUG]")
        print("Claim ID:", claim.id)
        print("Claim:", claim.claim_text)
        print("Benchmark:", claim.benchmark_name)
        print("Reported value:", claim.reported_value)
        print("Value type:", claim.value_type)
        print("Evidence:")
        print(evidence_texts.get(claim.id, "<NO EVIDENCE>"))
        print("Detected model:", context["model_key"])
        print("Detected setting:", context["evaluation_setting"])
        print("Detected metric:", context["metric"])
        print("Detected scope:", context.get("measurement_scope"))
        print("=" * 70)

        if not context["model_key"]:
            skipped_missing_model += 1
            continue

        if not context["evaluation_setting"]:
            skipped_missing_setting += 1

        # Retain unknown-setting claims. They can only pair with claims
        # that have the same (also unknown) evaluation setting.
        contexts.append(context)

    print(
        f"[info] eligible comparison claims: {len(contexts)} / {len(claims)}"
    )

    if skipped_missing_model:
        print(
            f"[info] excluded {skipped_missing_model} claim(s): "
            "model identity could not be established"
        )

    if skipped_missing_setting:
        print(
            f"[info] {skipped_missing_setting} claim(s) have unknown "
            "evaluation settings; they will only be compared with "
            "claims whose settings are also unknown"
        )

    by_group: Dict[
        Tuple[str, str, str, str, str, str],
        List[Dict[str, Any]],
    ] = {}

    for context in contexts:
        claim = context["claim"]

        key = (
            str(claim.benchmark_name).strip().lower(),
            str(claim.value_type).strip().lower(),
            context["model_key"],
            context["evaluation_setting"],
            context["metric"] or "",
            context.get("measurement_scope") or "",
        )

        by_group.setdefault(
            key,
            [],
        ).append(context)

    all_results = []

    for (
        benchmark_name,
        value_type,
        model_key,
        evaluation_setting,
        metric,
        measurement_scope,
    ), group in by_group.items():
        pairs = find_contradictions_in_group(group)

        # Helpful diagnostic: show when a group contains multiple claims but
        # no cross-paper pair was produced. This is especially useful when
        # duplicate measurements exist in the same paper.
        if len(group) >= 2 and not pairs:
            paper_ids = sorted(
                {
                    getattr(ctx["claim"], "paper_id", None)
                    for ctx in group
                }
            )
            print(
                f"[info] no cross-paper pair in group; "
                f"paper_ids={paper_ids}"
            )

        if len(group) >= 2:
            print(
                f"[info] {benchmark_name} ({value_type}) | "
                f"model={_display_model(model_key)} | "
                f"setting={_display_setting(evaluation_setting)} | "
                f"metric={_display_metric(metric)} | "
                f"scope={measurement_scope or 'UNKNOWN_SCOPE'}: "
                f"compared {len(group)} claim(s), found {len(pairs)} pair(s)"
            )

        all_results.extend(pairs)

    print(
        f"[info] contradiction analysis groups: {len(by_group)}"
    )
    print(
        f"[info] comparable cross-paper pairs: {len(all_results)}"
    )

    if close_session:
        session.close()

    return all_results


# ============================================================
# STORE RESULTS
# ============================================================


def store_contradictions(
    session,
    contradiction_dicts: list,
) -> list:
    """Write contradiction results using the existing idempotent DB helper."""
    stored_rows = []
    skipped = 0

    for cd in contradiction_dicts:
        row = insert_contradiction(
            session,
            claim_a_id=cd["claim_a_id"],
            claim_b_id=cd["claim_b_id"],
            relation_type=cd["relation_type"],
            severity=cd["severity"],
        )

        if row is None:
            skipped += 1
            continue

        stored_rows.append(row)

    if skipped:
        print(
            f"[info] skipped {skipped} pair(s) already in the contradictions table"
        )

    return stored_rows


# ============================================================
# FULL RUNNER
# ============================================================


def run_contradiction_detection() -> dict:
    """
    Detect comparable cross-paper pairs across the whole database and store
    the new rows.
    """
    session = get_session()

    try:
        found = detect_all_contradictions(session)
        stored = store_contradictions(
            session,
            found,
        )
    finally:
        session.close()

    return {
        "pairs_compared": len(found),
        "contradictions_stored": len(stored),
        "results": found,
    }


# ============================================================
# DIRECT TEST
# ============================================================


if __name__ == "__main__":
    from pprint import pprint

    summary = run_contradiction_detection()

    print(
        f"\nDone. {summary['contradictions_stored']} new contradiction "
        f"row(s) stored out of {summary['pairs_compared']} comparable pair(s).\n"
    )

    pprint(summary["results"])
