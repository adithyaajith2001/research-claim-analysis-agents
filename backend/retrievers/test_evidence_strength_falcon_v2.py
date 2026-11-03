import json
from types import SimpleNamespace

from evidence_strength_agent import (
    normalize_table_evidence,
    parse_scoring_response,
)


# ============================================================
# TEST 1: FALCON HEADER/ROW NORMALIZATION
# ============================================================

raw_evidence = """Header:
Model | MMLU (0-shot) | MMLU-Pro (0-shot) | Mobile-MMLU (0-shot) | Mobile-MMLU-Pro (0-shot)

Row:
Falcon3-3B-Instruct 55.8 22.3 42.6 37.2"""


normalized = normalize_table_evidence(
    raw_evidence
)

print("\n" + "=" * 70)
print("TEST 1: NORMALIZED FALCON EVIDENCE")
print("=" * 70)
print(normalized)

assert "Header:" in normalized
assert "Row:" in normalized
assert "MMLU (0-shot)" in normalized
assert "Falcon3-3B-Instruct" in normalized
assert "55.8" in normalized

print("\nNORMALIZATION TEST: PASS")


# ============================================================
# TEST 2: GEMINI RESPONSE PARSER
# ============================================================

gemini_response = """```json
{
  "evidence_strength_score": 5.75,
  "reasoning": "The paper provides a GitHub link for code and data to support reproducibility, but mentions no robustness checks or multiple runs for the score, and introduces a new mobile-adapted benchmark variant without detailing contamination controls."
}
```"""


score, reasoning = parse_scoring_response(
    gemini_response
)

print("\n" + "=" * 70)
print("TEST 2: SCORING RESPONSE PARSER")
print("=" * 70)
print("Score:", score)
print("Reasoning:", reasoning)

assert score == 5.75
assert "GitHub link" in reasoning

print("\nRESPONSE PARSER TEST: PASS")


# ============================================================
# TEST 3: EMBEDDED JSON
# ============================================================

embedded_response = """
Here is the scoring result:

{
  "evidence_strength_score": 6.25,
  "reasoning": "The evidence is clearly linked to the reported benchmark result."
}

End of response.
"""

score2, reasoning2 = parse_scoring_response(
    embedded_response
)

print("\n" + "=" * 70)
print("TEST 3: EMBEDDED JSON PARSER")
print("=" * 70)
print("Score:", score2)
print("Reasoning:", reasoning2)

assert score2 == 6.25
assert "clearly linked" in reasoning2

print("\nEMBEDDED JSON TEST: PASS")


# ============================================================
# FINAL RESULT
# ============================================================

print("\n" + "=" * 70)
print("ALL EVIDENCE STRENGTH REGRESSION TESTS PASSED")
print("=" * 70)