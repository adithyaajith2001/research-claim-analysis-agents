"""
claim_extraction_agent.py

WHAT: extracts scientific claims from a paper's text and links each to its
supporting sentence(s), SCOPED to the LLM-benchmark domain.

WHY "careful" matters here specifically (per your guide's feedback):
A generic "extract every claim" prompt is a trap. It will pull in claims like
"our approach is more efficient" (vague, unscorable, incomparable across
papers) right alongside "Model X scores 86.4% on MMLU" (concrete, scorable,
comparable). If both kinds land in your DB with equal weight:
  - Evidence Strength Agent has nothing numeric to grade the vague ones on.
  - Contradiction Agent can't compare a vague claim from Paper A to anything
    in Paper B - there's no shared yardstick.
So THIS agent is deliberately narrow: it asks for benchmark-style claims,
tags each with (benchmark_name, reported_value) when the claim contains one,
and REJECTS claims that don't fit the domain schema rather than guessing.

WHAT "careful" means concretely, implemented below:
  1. Domain-constrained prompt (only VALIDATED_BENCHMARKS from config.py).
  2. Schema validation - a parsed claim missing required fields is DROPPED,
     not silently kept with nulls (a claim with no source_sentence is
     unverifiable and shouldn't reach the DB at all).
  3. Deduplication - papers often restate the same finding in the abstract
     AND the conclusion. Without dedup, that one real finding gets counted
     (and scored) as if it were two independent claims - inflating both
     your claim count and, later, any aggregate confidence metric.
  4. Retry with backoff on malformed JSON (your original code just skipped
     and moved on - silently losing data instead of trying again).

HOW: same chunk() -> call model -> parse JSON pattern as before, but every
step above is new.

WHEN this runs: once per retrieved paper, right after the retrieval agent
hands off paper text/abstract, before evidence_strength_agent.py scores
anything.

NOTE: 503-retry logic lives in llm_utils.call_with_retry, shared with
evidence_strength_agent.py - do not add a local duplicate here again.
"""

import json
import time
import re
from llm_utils import call_with_retry
from config import (
    MODEL_NAME, MAX_OUTPUT_TOKENS_EXTRACTION, SECONDS_BETWEEN_CALLS,
    MAX_RETRIES, VALIDATED_BENCHMARKS, MOCK_MODE,
)

# ---------------------------------------------------------------------------
# Prompt - DOMAIN CONSTRAINED
# WHY the benchmark list is injected into the prompt itself: this is the
# actual mechanism that keeps extraction "on domain". The model is told
# exactly which benchmarks count, so a paper that mentions an unrelated
# medical trial statistic (if it slips into a chunk as boilerplate) won't
# get pulled in as a "claim".
# ---------------------------------------------------------------------------
EXTRACTION_PROMPT = """You are a careful scientific claim extraction agent
working ONLY in the domain of LLM/NLP benchmark evaluation research.

Extract ONLY claims that report a model's performance on one of these
benchmarks: {benchmarks}

For each such claim, return an object with these exact fields:
- "claim": one-sentence paraphrase of the claim
- "source_sentence": the EXACT sentence(s) from the text supporting it (do not paraphrase this field)
- "section": section this came from (e.g. "Results", "Abstract"), or "Unknown"
- "claim_type": one of ["performance_claim", "finding", "conclusion"]
- "benchmark_name": which benchmark from the list above this claim is about
- "reported_value": the numeric score reported, as a plain number (e.g. 86.4). Use null if no number is stated.
- "value_type": what KIND of number reported_value is. One of:
  - "absolute_accuracy": a standalone score/accuracy on the benchmark (e.g. "achieves 86.4% on MMLU")
  - "absolute_improvement": a percentage-point gain over a baseline (e.g. "a 1.3% absolute improvement")
  - "relative_improvement": a relative/proportional gain over a baseline (e.g. "+28.4% relative accuracy improvement")
  Use null only if reported_value is also null.

STRICT RULES:
- If a sentence does not name one of the listed benchmarks, DO NOT extract it.
- If you cannot find the exact benchmark name in the text, do not guess - skip it.
- Ignore boilerplate (acknowledgments, funding, generic background/motivation).
- CRITICAL: absolute_accuracy, absolute_improvement, and relative_improvement are NOT
  interchangeable numbers. A claim like "improves accuracy from 22.0% to 60.7%" reports
  an absolute_accuracy value (60.7, the final score), NOT the 38.7-point gain, unless the
  sentence itself frames the number as the improvement/delta rather than the resulting score.
- Return ONLY a JSON array of these objects. No preamble, no markdown fences.

TEXT:
{chunk}
"""


def chunk_text(text, max_chars=6000):
    """Naive paragraph-based chunker (unchanged from original - this part was fine)."""
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    chunks, current = [], ""
    for p in paragraphs:
        if len(current) + len(p) > max_chars:
            chunks.append(current)
            current = p
        else:
            current += "\n\n" + p
    if current:
        chunks.append(current)
    return chunks


def _validate_claim(c: dict) -> bool:
    """WHAT: rejects a parsed claim if it's missing anything the rest of the
    pipeline depends on.
    WHY: a claim with no source_sentence can never be verified; a claim with
    a benchmark_name not in our validated list means the model ignored
    instructions and we should not trust it downstream."""
    required = ["claim", "source_sentence", "claim_type"]
    if not all(c.get(k) for k in required):
        return False
    if c.get("benchmark_name") and c["benchmark_name"] not in VALIDATED_BENCHMARKS:
        return False
    # WHY: a reported_value with no value_type is exactly the ambiguity that
    # let contradiction_agent.py compare absolute accuracy against
    # improvement deltas as if they were the same quantity - reject rather
    # than let an untyped number reach the DB.
    if c.get("reported_value") is not None and not c.get("value_type"):
        return False
    if c.get("value_type") not in (None, "absolute_accuracy", "absolute_improvement", "relative_improvement"):
        return False
    return True


def _normalize_for_dedup(claim_text: str) -> str:
    """WHAT: lowercases + strips punctuation/whitespace so near-identical
    restatements of the same claim collapse to the same key.
    WHY: papers restate their headline result in the abstract, intro, AND
    conclusion almost verbatim - without this, one real finding becomes 2-3
    'claims' in your DB, double-counting it in every downstream metric."""
    t = claim_text.lower().strip()
    t = re.sub(r"[^\w\s%.]", "", t)
    t = re.sub(r"\s+", " ", t)
    return t


def _dedupe_claims(claims: list) -> list:
    """Keeps the first occurrence of each (benchmark_name, value_type,
    reported_value, normalized claim text) combination.
    WHY value_type is in the key: an absolute_accuracy of 60.7 and a
    relative_improvement of 60.7 are different facts that happen to share a
    number - they must not collapse into one deduped claim."""
    seen = set()
    deduped = []
    for c in claims:
        key = (
            c.get("benchmark_name"),
            c.get("value_type"),
            c.get("reported_value"),
            _normalize_for_dedup(c["claim"]),
        )
        if key in seen:
            continue
        seen.add(key)
        deduped.append(c)
    return deduped


def _mock_llm_response(chunk: str) -> str:
    """WHEN this is used: only when config.MOCK_MODE is True (no Gemini API
    key available). Lets you test chunking/validation/dedup/DB-write logic
    for free, without burning API quota, before wiring in the real key.
    This is a deliberately dumb regex-based stand-in, NOT a real extractor -
    replace by setting GEMINI_API_KEY and it's bypassed entirely."""
    results = []
    for bench in VALIDATED_BENCHMARKS:
        # matches BOTH "MMLU ... 86.4%" and "86.4% on MMLU" orderings, since
        # real papers use both phrasings interchangeably.
        patterns = [
            rf"{bench}[^.]{{0,80}}?(\d{{1,3}}\.?\d?)\s*%",
            rf"(\d{{1,3}}\.?\d?)\s*%[^.]{{0,80}}?{bench}",
        ]
        for pattern in patterns:
            for m in re.finditer(pattern, chunk, flags=re.IGNORECASE):
                sentence_start = chunk.rfind(".", 0, m.start()) + 1
                sentence_end = chunk.find(".", m.end())
                sentence_end = sentence_end if sentence_end != -1 else len(chunk)
                sentence = chunk[sentence_start:sentence_end].strip()
                results.append({
                    "claim": f"Model reports {m.group(1)}% on {bench}",
                    "source_sentence": sentence,
                    "section": "Unknown",
                    "claim_type": "performance_claim",
                    "benchmark_name": bench,
                    "reported_value": float(m.group(1)),
                    # mock only ever synthesizes "X% on BENCH" style sentences,
                    # which are always a standalone score, never a delta.
                    "value_type": "absolute_accuracy",
                })
    return json.dumps(results)


def extract_claims_from_text(paper_id: str, text: str, client=None) -> list:
    """WHAT: runs extraction over one paper's text, chunk by chunk, with
    retry-on-malformed-JSON, schema validation, and dedup.

    WHEN to call: once per paper, after retrieval, before scoring.

    HOW: if config.MOCK_MODE is True, `client` is ignored and a deterministic
    mock response is used instead - so you can test this file right now
    without any API key. Once you have GEMINI_API_KEY set and pass a real
    `client` (google.genai.Client instance), it calls the real model, with
    503 retries handled by llm_utils.call_with_retry.
    """
    #print(f"[debug] paper {paper_id} input text (first 400 chars): {text[:400]}")
    all_claims = []
    for i, chunk in enumerate(chunk_text(text)):
        parsed = None
        for attempt in range(MAX_RETRIES):
            if MOCK_MODE or client is None:
                raw = _mock_llm_response(chunk)
            else:
                response = call_with_retry(
                    client,
                    MODEL_NAME,
                    EXTRACTION_PROMPT.format(
                        benchmarks=", ".join(VALIDATED_BENCHMARKS), chunk=chunk
                    ),
                    {"max_output_tokens": MAX_OUTPUT_TOKENS_EXTRACTION},
                )
                raw = response.text.strip().replace("```json", "").replace("```", "").strip()
                print(f"[debug] paper {paper_id} chunk {i} raw response: {raw[:500]}")
            try:
                parsed = json.loads(raw)
                break
            except json.JSONDecodeError:
                print(f"[warn] paper {paper_id} chunk {i} attempt {attempt+1}: bad JSON, retrying")
                if not MOCK_MODE:
                    time.sleep(5)

        if parsed is None:
            print(f"[error] paper {paper_id} chunk {i}: failed after {MAX_RETRIES} attempts, skipping chunk")
            continue

        valid_claims = [c for c in parsed if _validate_claim(c)]
        dropped = len(parsed) - len(valid_claims)
        if dropped:
            print(f"[info] paper {paper_id} chunk {i}: dropped {dropped} claim(s) failing schema/domain validation")

        for c in valid_claims:
            c["paper_id"] = paper_id
            c["chunk_index"] = i
        all_claims.extend(valid_claims)

        if not MOCK_MODE:
            time.sleep(SECONDS_BETWEEN_CALLS)

    before = len(all_claims)
    all_claims = _dedupe_claims(all_claims)
    if before != len(all_claims):
        print(f"[info] paper {paper_id}: deduped {before} -> {len(all_claims)} claims")

    return all_claims