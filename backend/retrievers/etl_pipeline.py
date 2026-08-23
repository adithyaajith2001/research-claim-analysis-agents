"""
etl_pipeline.py

WHAT:
Coordinates the complete processing pipeline for one research paper.

Pipeline

Paper
    ↓
Store Paper
    ↓
Claim Extraction
    ↓
Store Claims + Evidence
    ↓
Evidence Strength Scoring
    ↓
Update Confidence Score
    ↓
Return Processing Summary

Author: Malavika Krishna
"""

from claim_extraction_agent import extract_claims_from_text
from evidence_strength_agent import score_claim
from db_schema import (
    get_session,
    upsert_paper,
    insert_claim_with_evidence,
    update_claim_score,
    Paper,
    Claim,
    Evidence,
)


def process_paper(paper: dict, client=None):
    """
    Process one paper end-to-end.

    Parameters
    ----------
    paper : dict

    Expected Keys

    {
        "id": "...",
        "title": "...",
        "authors": "...",
        "year": 2025,
        "source": "arXiv",
        "source_url": "...",
        "citation_count": 123,
        "abstract": "...",
        "full_text": "..."
    }

    Returns
    -------
    dict
        Processing summary
    """

    session = get_session()

    print("=" * 60)
    print(f"Processing Paper : {paper['title']}")
    print("=" * 60)

    # --------------------------------------------------
    # STEP 1
    # Store paper
    # --------------------------------------------------

    upsert_paper(session, paper)

    # --------------------------------------------------
    # STEP 2
    # Extract claims
    # --------------------------------------------------

    claims = extract_claims_from_text(
        paper_id=paper["id"],
        text=paper["full_text"],
        client=client,
    )

    print(f"Claims Extracted : {len(claims)}")

    processed_claims = []

    # --------------------------------------------------
    # STEP 3
    # Store each claim
    # --------------------------------------------------

    for claim in claims:

        claim_row = insert_claim_with_evidence(
            session,
            claim,
        )

        # --------------------------------------------------
        # Fetch evidence row
        # --------------------------------------------------

        evidence_row = session.query(Evidence).filter(
            Evidence.claim_id == claim_row.id
        ).first()

        evidence_text = ""

        if evidence_row:
            evidence_text = evidence_row.citation_text

        # --------------------------------------------------
        # STEP 4
        # Score evidence
        # --------------------------------------------------

        score, reasoning = score_claim(
            claim_row=claim_row,
            evidence_text=evidence_text,
            paper_context=paper.get("abstract", ""),
            client=client,
            citation_count=paper.get("citation_count"),
        )

        # --------------------------------------------------
        # STEP 5
        # Save score
        # --------------------------------------------------

        update_claim_score(
            session=session,
            claim_id=claim_row.id,
            evidence_strength_score=score,
        )

        processed_claims.append({
            "claim_id": claim_row.id,
            "claim": claim_row.claim_text,
            "benchmark": claim_row.benchmark_name,
            "reported_value": claim_row.reported_value,
            "evidence_strength_score": score,
            "reasoning": reasoning,
        })

    session.close()

    return {

        "paper_id": paper["id"],

        "title": paper["title"],

        "claims_found": len(processed_claims),

        "claims": processed_claims,

    }


# ---------------------------------------------------------------------
# Test
# ---------------------------------------------------------------------

if __name__ == "__main__":

    sample_paper = {
        "id": "paper001",
        "title": "GPT-4 Technical Report",
        "authors": "OpenAI",
        "year": 2024,
        "source": "arXiv",
        "citation_count": 150,
        "abstract": "We evaluate GPT-4 on MMLU.",
        "full_text": """
        GPT-4 achieves 86.4% accuracy on MMLU.
        Code and evaluation scripts are publicly released.
        """,}

    result = process_paper(sample_paper, client=None)
    from pprint import pprint
    pprint(result)