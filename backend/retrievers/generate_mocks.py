# """
# generate_mocks.py

# WHAT: dumps the pipeline's output into the three mock files your team's
# work-division doc assigns to YOU:
#   - mocks/sample_claims.json
#   - mocks/sample_evidence.json
#   - mocks/sample_contradictions.json
# (sample_papers.json included too, since Adithya's retrieval agent isn't
# wired in yet and Sheethal may want paper metadata for her evidence-cards UI.)

# WHY mocks matter (per your own doc's "MOCK DATA STRATEGY - NO BLOCKING"
# section): Sheethal needs realistic contradiction/evidence shapes to build
# her D3.js visualization and evidence cards WITHOUT waiting for the full
# pipeline to be wired together with real API keys. You generating these today
# unblocks her today too.

# NOTE on sample_contradictions.json: contradiction DETECTION is Adithya's
# agent, not yours. This file is a HAND-CONSTRUCTED mock (using the real
# MMLU/GSM8K claims your pipeline just produced) so:
#   1. You have something realistic to build/test YOUR contradiction
#      visualization component against right now.
#   2. When Adithya's real Contradiction Agent is ready, you swap this mock
#      file's contents for her real output - same schema, no code changes
#      needed in the visualization.

# WHEN to run: any time after test_pipeline.py, to refresh the mocks.
# """

# import json
# from db_schema import get_session, Paper, Claim, Evidence

# session = get_session()

# papers = session.query(Paper).all()
# claims = session.query(Claim).all()

# sample_papers = [
#     {"id": p.id, "title": p.title, "authors": p.authors, "year": p.year, "source": p.source}
#     for p in papers
# ]

# sample_claims = [
#     {
#         "id": c.id, "paper_id": c.paper_id, "claim_text": c.claim_text,
#         "claim_type": c.claim_type, "benchmark_name": c.benchmark_name,
#         "reported_value": c.reported_value, "evidence_strength_score": c.evidence_strength_score,
#     }
#     for c in claims
# ]

# sample_evidence = [
#     {"id": e.id, "claim_id": e.claim_id, "citation_text": e.citation_text,
#      "reliability_score": e.reliability_score}
#     for c in claims for e in c.evidence
# ]

# # Hand-built contradiction mock (see docstring) - built from the REAL claims
# # your pipeline extracted above: the two MMLU claims (86.4% vs 79.5%) for
# # what the two papers imply is a comparable model are flagged Contradicts;
# # the two GSM8K claims (91.2% vs 91.0%) are close enough to flag Agrees.
# mmlu_claims = [c for c in claims if c.benchmark_name == "MMLU"]
# gsm8k_claims = [c for c in claims if c.benchmark_name == "GSM8K"]

# sample_contradictions = []
# if len(mmlu_claims) >= 2:
#     a, b = mmlu_claims[0], mmlu_claims[1]
#     diff = abs(a.reported_value - b.reported_value)
#     sample_contradictions.append({
#         "id": 1, "claim_a_id": a.id, "claim_b_id": b.id,
#         "claim_a_text": a.claim_text, "claim_b_text": b.claim_text,
#         "benchmark_name": "MMLU",
#         "relation_type": "Contradicts" if diff > 3 else "Agrees",
#         "severity": "High" if diff > 5 else "Medium",
#         "value_diff": round(diff, 1),
#     })
# if len(gsm8k_claims) >= 2:
#     a, b = gsm8k_claims[0], gsm8k_claims[1]
#     diff = abs(a.reported_value - b.reported_value)
#     sample_contradictions.append({
#         "id": 2, "claim_a_id": a.id, "claim_b_id": b.id,
#         "claim_a_text": a.claim_text, "claim_b_text": b.claim_text,
#         "benchmark_name": "GSM8K",
#         "relation_type": "Contradicts" if diff > 3 else "Agrees",
#         "severity": "Low",
#         "value_diff": round(diff, 1),
#     })

# with open("mocks/sample_papers.json", "w") as f:
#     json.dump(sample_papers, f, indent=2)
# with open("mocks/sample_claims.json", "w") as f:
#     json.dump(sample_claims, f, indent=2)
# with open("mocks/sample_evidence.json", "w") as f:
#     json.dump(sample_evidence, f, indent=2)
# with open("mocks/sample_contradictions.json", "w") as f:
#     json.dump(sample_contradictions, f, indent=2)

# print(f"Wrote {len(sample_papers)} papers, {len(sample_claims)} claims, "
#       f"{len(sample_evidence)} evidence rows, {len(sample_contradictions)} contradiction pairs to mocks/")

"""
generate_mocks.py

WHAT: dumps the pipeline's output into the mock files your team's work-division
doc assigns to YOU:
  - mocks/sample_papers.json
  - mocks/sample_claims.json
  - mocks/sample_evidence.json
  - mocks/sample_contradictions.json

WHY mocks matter (per your own doc's "MOCK DATA STRATEGY - NO BLOCKING"
section): Sheethal needs realistic contradiction/evidence shapes to build her
D3.js visualization and evidence cards WITHOUT waiting for the full pipeline.

HOW contradictions are produced (CHANGED): this file no longer hand-picks
claim pairs. It calls contradiction_agent.detect_all_contradictions(), the same
function production uses, so the mock file always matches real agent output.
Same-paper restatements are skipped by the agent itself, and cross-paper
conflicts are found automatically.

WHERE files are written (CHANGED): output goes to backend/mocks/ relative to
THIS file, not the current working directory, so running the script from any
folder writes to the same place.

WHEN to run: any time after test_pipeline.py, to refresh the mocks.
"""

import json
import os

from db_schema import get_session, Paper, Claim, Evidence
from contradiction_agent import detect_all_contradictions

MOCK_DIR = os.path.normpath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "mocks")
)
os.makedirs(MOCK_DIR, exist_ok=True)


def _mock_path(filename: str) -> str:
    return os.path.join(MOCK_DIR, filename)


session = get_session()
try:
    papers = session.query(Paper).all()
    claims = session.query(Claim).all()

    sample_papers = [
        {
            "id": p.id,
            "title": p.title,
            "authors": p.authors,
            "year": p.year,
            "source": p.source,
        }
        for p in papers
    ]

    sample_claims = [
        {
            "id": c.id,
            "paper_id": c.paper_id,
            "claim_text": c.claim_text,
            "claim_type": c.claim_type,
            "benchmark_name": c.benchmark_name,
            "reported_value": c.reported_value,
            "value_type": c.value_type,
            "evaluation_setting": c.evaluation_setting,
            "metric": c.metric,
            "evidence_strength_score": c.evidence_strength_score,
        }
        for c in claims
    ]

    sample_evidence = [
        {
            "id": e.id,
            "claim_id": e.claim_id,
            "citation_text": e.citation_text,
            "reliability_score": e.reliability_score,
        }
        for c in claims
        for e in c.evidence
    ]

    # Same function production uses. Does NOT write to the contradictions
    # table; this is only for the mock file.
    contradiction_rows = detect_all_contradictions(session)

    sample_contradictions = [
        {
            "id": i,
            "claim_a_id": cd["claim_a_id"],
            "claim_b_id": cd["claim_b_id"],
            "claim_a_text": cd["claim_a_text"],
            "claim_b_text": cd["claim_b_text"],
            "benchmark_name": cd["benchmark_name"],
            "value_type": cd["value_type"],
            "evaluation_setting": cd["evaluation_setting"],
            "metric": cd["metric"],
            "relation_type": cd["relation_type"],
            "severity": cd["severity"],
            "value_diff": cd["value_diff"],
        }
        for i, cd in enumerate(contradiction_rows, start=1)
    ]
finally:
    session.close()

with open(_mock_path("sample_papers.json"), "w", encoding="utf-8") as f:
    json.dump(sample_papers, f, indent=2)
with open(_mock_path("sample_claims.json"), "w", encoding="utf-8") as f:
    json.dump(sample_claims, f, indent=2)
with open(_mock_path("sample_evidence.json"), "w", encoding="utf-8") as f:
    json.dump(sample_evidence, f, indent=2)
with open(_mock_path("sample_contradictions.json"), "w", encoding="utf-8") as f:
    json.dump(sample_contradictions, f, indent=2)

print(f"Wrote {len(sample_papers)} papers, {len(sample_claims)} claims, "
      f"{len(sample_evidence)} evidence rows, {len(sample_contradictions)} "
      f"contradiction pairs to {MOCK_DIR}")