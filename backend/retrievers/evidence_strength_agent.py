"""
evidence_strength_agent.py

WHAT: computes a 0-10 evidence-strength/confidence score for a single claim.

WHY THE WEIGHTS ARE DIFFERENT FROM YOUR OLD CODE (this is the whole point of
narrowing to one domain): your old score_manual() weighted sample_size,
dataset_quality, reproducibility, citation_count, venue_score, and
experimental_design roughly evenly - a generic recipe meant to work "okay"
for any paper. But what actually makes a BENCHMARK claim trustworthy is
different from what makes, say, a cybersecurity vulnerability claim
trustworthy (there it'd be more about real-world exploit validation and
disclosure process, not "benchmark standardization").

For THIS domain, the strongest signals are:
  1. benchmark_is_standard (NEW, high weight) - is this one of our
     VALIDATED_BENCHMARKS (a known, standardized, widely-used benchmark) or
     a benchmark the authors invented themselves? A claim on a standard,
     public benchmark is far easier to independently verify than a claim on
     a private eval set only the authors have access to.
  2. reproducibility - did they release code/checkpoints/eval scripts?
  3. experimental_design - single run vs multiple seeds, fixed prompt vs
     prompt-robustness checked, etc.
  4. citation_count / venue - kept, but LOWER weight here, because a paper
     can be brand new (0 citations, preprint-only) and still make a
     perfectly checkable benchmark claim - novelty shouldn't be punished
     heavily in this domain the way it might be in, say, medicine.

HOW: hybrid scoring, same pattern as before -
  - benchmark_is_standard is RULE-BASED (looked up from config, not judged by
    an LLM - this is a fact, not an opinion, so don't waste an LLM call on it)
  - dataset_quality / reproducibility / experimental_design are LLM-JUDGED
    from the claim + evidence + paper context
  - final score = renormalized weighted average, skipping any factor with
    no data (so missing info doesn't unfairly tank the score)

WHEN this runs: once per claim, right after claim_extraction_agent.py
produces it, before it's written to the dashboard / DB.
"""

import json
from llm_utils import call_with_retry
from config import (
    MODEL_NAME, MAX_OUTPUT_TOKENS_SCORING, VALIDATED_BENCHMARKS, MOCK_MODE,
)

SCORING_PROMPT = """You are a skeptical peer reviewer scoring ONE benchmark
performance claim from an LLM/NLP evaluation paper.

CLAIM: {claim_text}
SUPPORTING SENTENCE: {evidence_text}
PAPER CONTEXT: {paper_context}

Rate each factor 0-10 based ONLY on what's stated or reasonably inferable.
Use null if it truly cannot be judged from the given text.

- "reproducibility": did the paper mention released code, checkpoints, or
  public eval scripts for this benchmark result?
- "experimental_design": is there evidence of multiple runs/seeds, or is it a
  single number with no robustness check mentioned?
- "dataset_quality": for the benchmark used, is there any indicated concern
  about contamination, versioning, or non-standard subsetting?

Return ONLY this JSON object, no markdown, no preamble:
{{
  "reproducibility": <0-10 or null>,
  "experimental_design": <0-10 or null>,
  "dataset_quality": <0-10 or null>,
  "reasoning": "<one sentence justification>"
}}
"""

# Domain-specific weights. NOTE: these sum to 1.0 and are DIFFERENT from a
# generic paper-scoring recipe - see module docstring for why.
WEIGHTS = {
    "benchmark_is_standard": 0.30,  # rule-based, highest weight in this domain
    "reproducibility": 0.25,
    "experimental_design": 0.20,
    "dataset_quality": 0.15,
    "citation_count_score": 0.10,   # de-emphasized vs. generic scoring
}


def _benchmark_is_standard_score(benchmark_name: str) -> float:
    """WHAT: rule-based check, not LLM-judged.
    WHY rule-based: whether a benchmark is on our validated/standardized
    list is a FACT we already have in config.py, not a judgment call -
    asking an LLM to guess this would be slower, costlier, and less
    reliable than just checking a list we already curated."""
    return 10.0 if benchmark_name in VALIDATED_BENCHMARKS else 3.0


def _normalize_citation_count(c):
    if c is None:
        return None
    return min(10.0, c / 10)


def score_manual(benchmark_is_standard=None, reproducibility=None,
                  experimental_design=None, dataset_quality=None,
                  citation_count=None) -> float:
    """WHAT: weighted average across whichever factors have data.
    WHY renormalize: if e.g. citation_count is unknown (brand-new preprint),
    we shouldn't silently score it as 0 - we drop it and redistribute its
    weight across the factors we DO have, so missing metadata doesn't
    unfairly punish a claim."""
    weighted_inputs = {
        "benchmark_is_standard": (benchmark_is_standard, WEIGHTS["benchmark_is_standard"]),
        "reproducibility": (reproducibility, WEIGHTS["reproducibility"]),
        "experimental_design": (experimental_design, WEIGHTS["experimental_design"]),
        "dataset_quality": (dataset_quality, WEIGHTS["dataset_quality"]),
        "citation_count_score": (_normalize_citation_count(citation_count), WEIGHTS["citation_count_score"]),
    }
    available = [(v, w) for v, w in weighted_inputs.values() if v is not None]
    if not available:
        return 0.0
    total_weight = sum(w for _, w in available)
    weighted_sum = sum(v * w for v, w in available)
    return round(weighted_sum / total_weight, 2)


def _mock_llm_judgment(claim_text: str, evidence_text: str) -> dict:
    """WHEN used: only in MOCK_MODE (no Gemini key). Deterministic stand-in
    so scoring logic/math can be tested for free before wiring in the real
    API key."""
    has_repro_hint = any(w in evidence_text.lower() for w in ["code", "released", "public", "checkpoint"])
    return {
        "reproducibility": 7.0 if has_repro_hint else 4.0,
        "experimental_design": 6.0,
        "dataset_quality": 7.0,
        "reasoning": "[MOCK] heuristic placeholder judgment, replace with real API call",
    }


def score_claim(claim_row, evidence_text: str, paper_context: str, client=None,
                 citation_count=None) -> tuple:
    """WHAT: full pipeline for one claim - rule-based benchmark check +
    LLM-judged qualitative factors -> final weighted score.

    WHEN to call: once per claim, immediately after extraction, passing in
    the Claim ORM row (needs .claim_text and .benchmark_name), its linked
    evidence text, and enough paper context (e.g. title + abstract) for the
    LLM to judge reproducibility/design signals.

    Returns: (final_score: float, reasoning: str)
    """
    if MOCK_MODE or client is None:
        judged = _mock_llm_judgment(claim_row.claim_text, evidence_text)
    else:
        response = call_with_retry(
            client,
            MODEL_NAME,
            SCORING_PROMPT.format(
                claim_text=claim_row.claim_text,
                evidence_text=evidence_text,
                paper_context=paper_context,
            ),
            {"max_output_tokens": MAX_OUTPUT_TOKENS_SCORING},
        )
        raw = response.text.strip().replace("```json", "").replace("```", "").strip()
        try:
            judged = json.loads(raw)
        except json.JSONDecodeError:
            print(f"[warn] scoring failed to parse for claim: {claim_row.claim_text[:60]}...")
            judged = {"reproducibility": None, "experimental_design": None, "dataset_quality": None, "reasoning": ""}

    final_score = score_manual(
        benchmark_is_standard=_benchmark_is_standard_score(claim_row.benchmark_name),
        reproducibility=judged.get("reproducibility"),
        experimental_design=judged.get("experimental_design"),
        dataset_quality=judged.get("dataset_quality"),
        citation_count=citation_count,
    )
    return final_score, judged.get("reasoning", "")
