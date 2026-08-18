"""
test_pipeline.py

WHAT: runs the FULL chain end-to-end on realistic test papers, so you can
prove today (to yourself and your guide) that extraction -> DB -> scoring
works together, not just as isolated files.

WHY a "retrieval stub" instead of Adithya's real agent: she hasn't sent hers
yet. The stub below returns the exact same shape her function will return
(list of dicts with id/title/authors/year/abstract) - see the comment marked
SWAP POINT. When she sends her code, you delete the stub function body and
call hers instead; nothing downstream changes.

WHEN to run this: right now, to verify your part works; again after Adithya's
retrieval agent is wired in, to verify the integration didn't break anything.
"""

import os
from dotenv import load_dotenv
load_dotenv()
from config import MOCK_MODE

api_key = os.environ.get("GEMINI_API_KEY")
client = None

if MOCK_MODE:
    print("[info] MOCK_MODE is on - running pipeline on deterministic fake responses, no Gemini calls will be made")
else:
    if not api_key:
        raise ValueError("GEMINI_API_KEY not found - check your .env file exists and load_dotenv() ran")
    print(f"[debug] Loaded API key ending in: ...{api_key[-4:]}")
    from google import genai
    client = genai.Client(api_key=api_key)

from db_schema import get_session, upsert_paper, insert_claim_with_evidence, update_claim_score
from claim_extraction_agent import extract_claims_from_text
from evidence_strength_agent import score_claim
from db_schema import Claim


def get_papers_from_retrieval(query: str, max_results: int = 10):
    """SWAP POINT (now wired): calls Adithya's UnifiedPaperRetriever via
    retrieval_adapter.get_pipeline_ready_papers(), which normalizes her
    output (different id keys per source, authors-as-list, no full_text,
    JATS-tagged/missing CrossRef abstracts) into the dict shape this
    pipeline requires. See retrieval_adapter.py's docstring for exactly
    what gets dropped and why.

    Requires: arxiv_retriever.py, semantic_scholar_retriever.py,
    crossref_retriever.py, unified_retriever.py, and retrieval_adapter.py
    all present alongside this file, plus network access to arXiv /
    Semantic Scholar / CrossRef (not available in this sandbox - see
    README)."""
    from retrieval_adapter import get_pipeline_ready_papers
    return get_pipeline_ready_papers(query, max_results=max_results)


def get_test_papers_stub():
    """FALLBACK: deterministic local papers, used when USE_LIVE_RETRIEVAL is
    False (no network / no retriever files yet) so you can still exercise
    the extraction -> DB -> scoring chain offline."""
    return [
        {
            "id": "2401.00001",
            "title": "Scaling Instruction Tuning for Reasoning Benchmarks",
            "authors": "A. Author, B. Coauthor",
            "year": 2024,
            "source": "arXiv",
            "abstract": (
                "Abstract: We evaluate our new instruction-tuned model across "
                "standard benchmarks. Our model achieves 86.4% on MMLU, "
                "substantially outperforming prior open-weight baselines. On "
                "GSM8K, the model solves 91.2% of problems correctly. We release "
                "our code and evaluation scripts publicly.\n\n"
                "Results: We further confirm our model achieves 86.4% on MMLU in "
                "the detailed results table, consistent with the abstract. On "
                "HumanEval, the model scores 67.0% pass@1 averaged over 5 seeds."
            ),
        },
        {
            "id": "2402.00002",
            "title": "A Contrasting Evaluation of Instruction-Tuned Models",
            "authors": "C. Researcher",
            "year": 2024,
            "source": "arXiv",
            "abstract": (
                "Abstract: We independently re-evaluate several public models. "
                "We find the model from prior work achieves only 79.5% on MMLU "
                "under our stricter evaluation protocol, notably lower than "
                "originally reported. On GSM8K we measure 91.0% accuracy, "
                "consistent with prior claims."
            ),
        },
    ]


# Flip this to True once Adithya's retriever files + network access are both
# available. Kept as an explicit switch (not an auto-fallback try/except)
# so a broken live call fails loudly instead of silently testing against
# stub data and giving you false confidence.
USE_LIVE_RETRIEVAL = True
LIVE_QUERY = "GSM8K math reasoning language model accuracy improvement"

def run_pipeline():
    session = get_session()
    papers = (
        get_papers_from_retrieval(LIVE_QUERY, max_results=1)
        if USE_LIVE_RETRIEVAL
        else get_test_papers_stub()
    )

    all_inserted_claim_ids = []

    for paper in papers:
        print(f"\n=== Processing paper {paper['id']}: {paper['title']} ===")
        upsert_paper(session, paper)

        claims = extract_claims_from_text(paper["id"], paper["abstract"], client=client)
        print(f"Extracted {len(claims)} validated, deduped claim(s)")

        for c in claims:
            claim_row = insert_claim_with_evidence(session, c)
            evidence_text = claim_row.evidence[0].citation_text
            score, reasoning = score_claim(
                claim_row, evidence_text, paper_context=paper["title"], client=client,
            )
            update_claim_score(session, claim_row.id, score)
            all_inserted_claim_ids.append(claim_row.id)
            print(f"  [{score}/10] {claim_row.claim_text}  -- {reasoning}")

    print(f"\nPipeline complete. {len(all_inserted_claim_ids)} claims scored and stored.")
    return session, all_inserted_claim_ids


if __name__ == "__main__":
    run_pipeline()