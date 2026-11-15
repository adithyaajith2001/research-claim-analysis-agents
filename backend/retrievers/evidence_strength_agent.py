"""
evidence_strength_agent.py - robust parser / normalized-evidence revision

Drop-in interface:
    score_claim(
        claim_row,
        evidence_text,
        paper_context,
        client,
        citation_count=None
    ) -> (score_0_to_10, reasoning)

Fixes:
1. Canonicalizes Header:/Row: evidence before it is inserted into the scoring prompt.
2. Accepts pipe-delimited and lightly malformed Header:/Row table artifacts.
3. Parses Gemini scoring responses defensively:
   - plain JSON
   - ```json ... ``` fences
   - JSON embedded in surrounding text
   - common score-key variants
4. Validates score range 0..10 and reasoning before accepting the response.
5. Keeps the existing Evidence Strength responsibility: a 0-10 reliability
   assessment driven by reproducibility, experimental design, and benchmark
   standardisation signals. No new scoring weights are introduced here.
"""

import json
import math
import re
from typing import Any, Dict, Optional, Tuple

from config import MODEL_NAME, MAX_OUTPUT_TOKENS_SCORING, MOCK_MODE
from llm_utils import call_with_retry


DEFAULT_FALLBACK_SCORE = 7.5


# ============================================================
# EVIDENCE NORMALIZATION
# ============================================================

def normalize_table_evidence(evidence: Any) -> str:
    """
    Normalize the evidence representation without changing its meaning.

    Accepted forms include:
        Header:
        Model | MMLU (0-shot) | MMLU-Pro (0-shot) | ...

        Row:
        Falcon3-3B-Instruct | 55.8 | 22.3 | 42.6 | 37.2

    The function also tolerates common whitespace artifacts produced by PDF
    extraction, such as:
        ModelMMLU
        (0-shot)MMLU-Pro

    It never invents values. It only reorganizes already-present labels.
    """
    text = str(evidence or "").replace("\r\n", "\n").replace("\r", "\n").strip()
    if not text:
        return ""

    # Normalize Markdown/code fences around an evidence block.
    text = re.sub(r"```(?:text|markdown)?\s*", "", text, flags=re.IGNORECASE)
    text = text.replace("```", "").strip()

    # Canonicalize section labels.
    text = re.sub(r"(?im)^\s*header\s*:\s*", "Header:\n", text)
    text = re.sub(r"(?im)^\s*row\s*:\s*", "Row:\n", text)

    if not re.search(r"(?im)^\s*Header:\s*$", text):
        # Not a Header:/Row: artifact. Preserve ordinary evidence verbatim.
        return text

    if not re.search(r"(?im)^\s*Row:\s*$", text):
        # A Header-only artifact is still useful evidence; do not fabricate a row.
        return text

    header_match = re.search(
        r"(?is)Header:\s*(.*?)\n\s*Row:\s*(.*)",
        text,
    )
    if not header_match:
        return text

    header_block = header_match.group(1).strip()
    row_block = header_match.group(2).strip()

    # Stop at a second section label if one exists.
    row_block = re.split(
        r"\n\s*(?:Notes?|Source|Caption|Context)\s*:",
        row_block,
        maxsplit=1,
        flags=re.IGNORECASE,
    )[0].strip()

    # Repair OCR/PDF artifacts such as "ModelMMLU" and
    # "(0-shot)MMLU-Pro" while keeping the original benchmark tokens.
    header_block = re.sub(
        r"\bModel(?=MMLU(?:-Pro)?\b)",
        "Model | ",
        header_block,
        flags=re.IGNORECASE,
    )

    header_block = re.sub(
        r"\((\d+)\s*-\s*shot\)(?=[A-Za-z])",
        r"(\1-shot) | ",
        header_block,
        flags=re.IGNORECASE,
    )

    # If a header is whitespace-separated rather than pipe-separated, rebuild
    # the four benchmark columns when all four are present. This is deliberately
    # conservative: no split is performed when the mapping is ambiguous.
    benchmarks = re.findall(
        r"\b(MMLU(?:-Pro)?|Mobile-MMLU(?:-Pro)?)\b",
        header_block,
        flags=re.IGNORECASE,
    )

    if "|" not in header_block and benchmarks:
        # Extract shot labels in encounter order.
        shots = re.findall(
            r"\(\s*(\d+)\s*-\s*shot\s*\)",
            header_block,
            flags=re.IGNORECASE,
        )
        if len(shots) == len(benchmarks):
            columns = ["Model"]
            for benchmark, shot in zip(benchmarks, shots):
                columns.append(f"{benchmark} ({shot}-shot)")
            header_block = " | ".join(columns)

    # Normalize a whitespace row only when it has the same number of numeric
    # cells as the header's benchmark columns. Model identity is kept intact.
    if "|" not in row_block and benchmarks:
        numeric_cells = re.findall(
            r"(?<!\w)(?:\d+(?:\.\d+)?)(?!\w)",
            row_block,
        )
        if len(numeric_cells) >= len(benchmarks):
            # Match the model prefix up to the first numeric cell.
            first_num = re.search(
                r"(?<!\w)\d+(?:\.\d+)?(?!\w)",
                row_block,
            )
            if first_num:
                model = row_block[:first_num.start()].strip()
                values = numeric_cells[:len(benchmarks)]
                if model:
                    row_block = " | ".join([model] + values)

    return (
        "Header:\n"
        + header_block.strip()
        + "\n\nRow:\n"
        + row_block.strip()
    )


# ============================================================
# SCORING RESPONSE PARSER
# ============================================================

def _strip_code_fences(text: str) -> str:
    text = str(text or "").strip()
    text = re.sub(r"^\s*```(?:json|JSON)?\s*", "", text)
    text = re.sub(r"\s*```\s*$", "", text)
    return text.strip()


def _extract_balanced_json_object(text: str) -> Optional[str]:
    """
    Find the first balanced {...} object, respecting JSON strings.
    """
    s = str(text or "")
    start = s.find("{")
    if start < 0:
        return None

    depth = 0
    in_string = False
    escaped = False

    for i in range(start, len(s)):
        ch = s[i]

        if in_string:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                in_string = False
            continue

        if ch == '"':
            in_string = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return s[start:i + 1]

    return None


def parse_scoring_response(raw_text: Any) -> Tuple[float, str]:
    """
    Parse a Gemini evidence-strength response robustly.

    Accepted score keys:
        evidence_strength_score
        evidence_score
        score

    Accepted reasoning keys:
        reasoning
        rationale
        explanation
    """
    text = str(raw_text or "").strip()
    if not text:
        raise ValueError("empty scoring response")

    candidates = []
    cleaned = _strip_code_fences(text)
    candidates.append(cleaned)

    embedded = _extract_balanced_json_object(cleaned)
    if embedded and embedded not in candidates:
        candidates.append(embedded)

    parsed: Optional[Any] = None

    for candidate in candidates:
        try:
            parsed = json.loads(candidate)
            break
        except (json.JSONDecodeError, TypeError):
            continue

    # Some providers occasionally wrap the object in a one-element array.
    if parsed is not None and isinstance(parsed, list) and parsed:
        parsed = parsed[0]

    if isinstance(parsed, dict):
        score_value = None
        for key in (
            "evidence_strength_score",
            "evidence_score",
            "score",
        ):
            if key in parsed:
                score_value = parsed[key]
                break

        reasoning = ""
        for key in (
            "reasoning",
            "rationale",
            "explanation",
        ):
            value = parsed.get(key)
            if value is not None:
                reasoning = str(value).strip()
                if reasoning:
                    break

        if score_value is not None:
            try:
                score = float(score_value)
            except (TypeError, ValueError):
                score = None

            if score is not None and math.isfinite(score) and 0.0 <= score <= 10.0:
                return round(score, 2), reasoning

    # Last-resort extraction for otherwise useful model text. This is intentionally
    # narrow so prose numbers such as a benchmark accuracy cannot become the score.
    score_match = re.search(
        r'"?(?:evidence[_\s-]*strength[_\s-]*score|evidence[_\s-]*score|score)"?\s*'
        r"[:=]\s*([0-9]+(?:\.[0-9]+)?)",
        cleaned,
        flags=re.IGNORECASE,
    )

    if score_match:
        score = float(score_match.group(1))
        if 0.0 <= score <= 10.0 and math.isfinite(score):
            reasoning_match = re.search(
                r'"?(?:reasoning|rationale|explanation)"?\s*[:=]\s*"?(.*?)(?:"\s*[,}]|\s*$)',
                cleaned,
                flags=re.IGNORECASE | re.DOTALL,
            )
            reasoning = (
                reasoning_match.group(1).strip()
                if reasoning_match
                else ""
            )
            return round(score, 2), reasoning

    raise ValueError("could not parse a valid 0-10 evidence-strength score")


# ============================================================
# PROMPT
# ============================================================

SCORING_PROMPT = """You are the Evidence Strength Agent in a scientific claim
auditing pipeline.

Assess the reliability strength of the supplied claim/evidence on a 0-10 scale.

Judge only evidence strength, not whether the claim is true in the abstract.
Judge ONLY what the supplied evidence and paper context actually show. Do not
lower the score because something is simply not shown in the supplied text.

Start from this anchor and adjust:

- Start at 6: a result taken from the paper's own results table or text, with
  the model, benchmark and number clearly tied together.
- Add 1 if the metric and evaluation setting are stated (for example "5-shot
  accuracy", "pass@1").
- Add 1 if the paper states that code, weights or evaluation details are
  released, or reports repeated runs, variance or error bars.
- Add 1 if the benchmark is a standard, well-defined one with a clear version
  or subset.
- Subtract 2 if the metric or setting is unclear or the number could belong
  to a different benchmark variant or subset.
- Subtract 2 if the number is only a sub-component or a derived figure, not
  the benchmark's headline score.
- Subtract 2 if the evidence is a prose mention with no table or setting.

Keep the result between 0 and 10. A clearly reported single result on a
standard benchmark normally lands between 6 and 8.

Return ONLY one JSON object:
{{
  "evidence_strength_score": <number 0-10>,
  "reasoning": "<one or two concise sentences>"
}}

CLAIM:
{claim}

BENCHMARK:
{benchmark}

REPORTED VALUE:
{reported_value}

VALUE TYPE:
{value_type}

EVALUATION SETTING:
{evaluation_setting}

EVIDENCE:
<EVIDENCE>
{evidence}
</EVIDENCE>

PAPER CONTEXT:
<CONTEXT>
{paper_context}
</CONTEXT>

CITATION COUNT:
{citation_count}
"""


# ============================================================
# MOCK / TEST SUPPORT
# ============================================================

def parse_mock_scoring_response(raw_response: str) -> Tuple[float, str]:
    """Public test hook for regression tests."""
    return parse_scoring_response(raw_response)


# ============================================================
# PUBLIC API
# ============================================================

def score_claim(
    claim_row,
    evidence_text: str,
    paper_context: str,
    client,
    citation_count=None,
):
    """
    Score one claim and return (score, reasoning).

    The 7.5 fallback is retained only for an actual scoring/parsing failure,
    preserving the existing pipeline contract.
    """
    normalized_evidence = normalize_table_evidence(evidence_text)

    claim_text = getattr(claim_row, "claim_text", "") or ""
    benchmark = getattr(claim_row, "benchmark_name", "") or ""
    reported_value = getattr(claim_row, "reported_value", "") or ""
    value_type = getattr(claim_row, "value_type", "") or ""
    evaluation_setting = getattr(claim_row, "evaluation_setting", "") or ""

    prompt = SCORING_PROMPT.format(
        claim=claim_text,
        benchmark=benchmark,
        reported_value=reported_value,
        value_type=value_type,
        evaluation_setting=evaluation_setting,
        evidence=normalized_evidence,
        paper_context=str(paper_context or "")[:12000],
        citation_count=(
            citation_count
            if citation_count is not None
            else "unknown"
        ),
    )

    try:
        if MOCK_MODE or client is None:
            # Keep a deterministic mock path for local integration tests.
            raw_response = json.dumps(
                {
                    "evidence_strength_score": 5.75,
                    "reasoning": (
                        "The evidence is a single benchmark result with a "
                        "clear model/value mapping, but it does not establish "
                        "multiple runs or broader robustness checks."
                    ),
                }
            )
        else:
            response = call_with_retry(
                client,
                MODEL_NAME,
                prompt,
                {"max_output_tokens": MAX_OUTPUT_TOKENS_SCORING, "temperature": 0.0},
            )
            raw_response = getattr(response, "text", "") or ""

        score, reasoning = parse_scoring_response(raw_response)

        return score, reasoning

    except Exception as error:
        print(
            f"[warn] scoring failed to parse for claim: "
            f"{claim_text[:80]}..."
        )
        print(f"[warn] scoring parser detail: {error}")
        return DEFAULT_FALLBACK_SCORE, ""
