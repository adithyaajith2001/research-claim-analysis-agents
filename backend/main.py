import truststore
truststore.inject_into_ssl()
import os
import sys
import traceback

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field


# ============================================================
# PROJECT PATH SETUP
# ============================================================

BACKEND_DIR = os.path.dirname(
    os.path.abspath(__file__)
)

RETRIEVERS_DIR = os.path.join(
    BACKEND_DIR,
    "retrievers"
)

# test_pipeline.py and the supporting backend modules
# are inside the retrievers folder.
if RETRIEVERS_DIR not in sys.path:
    sys.path.insert(
        0,
        RETRIEVERS_DIR
    )


# ============================================================
# IMPORT COMPLETE PIPELINE
# ============================================================

from test_pipeline import run_pipeline


# ============================================================
# FASTAPI APP
# ============================================================

app = FastAPI(
    title="ResearchClaimAI API",
    description=(
        "Multi-agent research claim analysis backend"
    ),
    version="1.0.0",
)


# ============================================================
# CORS
# ============================================================

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================
# REQUEST MODEL
# ============================================================

class AnalysisRequest(BaseModel):

    query: str = Field(
        ...,
        min_length=1,
        description=(
            "Research topic or benchmark to analyze"
        ),
    )

    max_results: int = Field(
        default=8,
        ge=1,
        le=20,
        description=(
            "Maximum number of papers to retrieve"
        ),
    )


# ============================================================
# ROOT
# ============================================================

@app.get("/")
def root():

    return {
        "status": "success",
        "message": "ResearchClaimAI backend is running",
    }


# ============================================================
# HEALTH CHECK
# ============================================================

@app.get("/api/health")
def health():

    return {
        "status": "healthy",
        "message": "FastAPI backend is running",
    }


# ============================================================
# HELPER:
# NORMALIZE PIPELINE RETURN VALUE
# ============================================================

def normalize_pipeline_result(
    pipeline_output
):
    """
    Accept both possible return formats:

    New:
        run_pipeline() -> final_result

    Older:
        run_pipeline() -> (session, final_result)

    Returns:
        final_result dictionary
    """

    if isinstance(
        pipeline_output,
        tuple
    ):

        if len(pipeline_output) >= 2:
            result = pipeline_output[1]

        else:
            result = {}

    elif isinstance(
        pipeline_output,
        dict
    ):

        result = pipeline_output

    else:

        result = {}

    return result


# ============================================================
# HELPER:
# BUILD PAPER EVIDENCE GROUPS
# ============================================================


def build_evidence_groups(claims):
    """
    Build paper-level evidence groups for the React dashboard.

    Each paper appears once per category. Individual claims and
    evidence records are preserved within the paper-level record.

    similarity_score: TF-IDF similarity, 0.0 to 1.0
    verification_score: structured verification, 0.0 to 10.0
    structured_match_score: normalized structured score, 0.0 to 1.0
    """

    categories = ("supporting", "contradicting", "neutral")

    groups = {category: [] for category in categories}
    indexes = {category: {} for category in categories}
    metrics = {}

    def normalize_text(value):
        return " ".join(str(value or "").casefold().split())

    def as_number(value):
        try:
            number = float(value)
            return number if number == number else None
        except (TypeError, ValueError):
            return None

    def get_paper_key(paper_id, paper_title, claim_text):
        normalized_title = normalize_text(paper_title)

        if normalized_title:
            return ("title", normalized_title)

        if paper_id:
            return ("id", str(paper_id))

        return ("claim", normalize_text(claim_text))

    def add_evidence(category, paper_id, paper_title, claim_text, item):
        if not isinstance(item, dict):
            return

        paper_id = str(paper_id or "")
        paper_title = str(
            paper_title or "Unknown research paper"
        ).strip()
        claim_text = str(claim_text or "")
        evidence_text = str(item.get("evidence") or "")

        paper_key = get_paper_key(
            paper_id, paper_title, claim_text
        )

        if paper_key not in indexes[category]:
            record = {
                "paper_id": paper_id,
                "paper_title": paper_title,
                "claim": claim_text,
                "claims": [],
                "evidence": evidence_text,
                "evidence_items": [],
                "similarity_score": 0.0,
                "verification_score": None,
                "structured_match_score": None,
                "contradiction_score": 0.0,
                "matched_keywords": [],
            }

            indexes[category][paper_key] = record
            groups[category].append(record)

            metrics[(category, paper_key)] = {
                "seen": set(),
                "similarity_score": [],
                "verification_score": [],
                "structured_match_score": [],
                "contradiction_score": [],
            }

        record = indexes[category][paper_key]
        metric = metrics[(category, paper_key)]

        # Preserve all distinct claims associated with this paper.
        if claim_text and claim_text not in record["claims"]:
            record["claims"].append(claim_text)

        if not record["claim"] and claim_text:
            record["claim"] = claim_text

        if not record["evidence"] and evidence_text:
            record["evidence"] = evidence_text

        # Deduplicate repeated copies of the same claim/evidence pair.
        evidence_key = (
            normalize_text(claim_text),
            normalize_text(evidence_text),
        )

        if evidence_key in metric["seen"]:
            return

        metric["seen"].add(evidence_key)

        record["evidence_items"].append({
            "claim": claim_text,
            "evidence": evidence_text,
            "similarity_score": item.get("similarity_score"),
            "verification_score": item.get("verification_score"),
            "structured_match_score": item.get(
                "structured_match_score"
            ),
            "contradiction_score": item.get(
                "contradiction_score"
            ),
            "classification": item.get("classification"),
        })

        # Keep each score in its own scale and aggregate separately.
        for field in (
            "similarity_score",
            "verification_score",
            "structured_match_score",
            "contradiction_score",
        ):
            value = as_number(item.get(field))

            if value is not None:
                metric[field].append(value)

        keywords = item.get("matched_keywords") or []

        if isinstance(keywords, (list, tuple, set)):
            for keyword in keywords:
                if keyword not in record["matched_keywords"]:
                    record["matched_keywords"].append(keyword)

    for claim in claims:
        if not isinstance(claim, dict):
            continue

        paper_id = claim.get("paper_id", "")
        paper_title = claim.get("paper_title", "")
        claim_text = claim.get("claim", "")

        verification = claim.get("verification") or {}
        skeptic = claim.get("skeptic") or {}

        if not isinstance(verification, dict):
            verification = {}

        if not isinstance(skeptic, dict):
            skeptic = {}

        # Match skeptic results to verifier results where possible,
        # allowing their verification scores to be retained.
        verification_by_text = {}

        for item in verification.get("evidence_results", []):
            if not isinstance(item, dict):
                continue

            evidence_key = normalize_text(item.get("evidence"))

            if evidence_key:
                verification_by_text[evidence_key] = item

        # Supporting evidence
        for item in verification.get("supporting_evidence", []):
            add_evidence(
                "supporting",
                paper_id,
                paper_title,
                claim_text,
                item,
            )

        # Contradicting evidence from the skeptic agent
        for item in skeptic.get("contradicting_evidence", []):
            if not isinstance(item, dict):
                continue

            evidence_key = normalize_text(item.get("evidence"))
            matched = verification_by_text.get(evidence_key, {})

            # Preserve skeptic fields while filling in verifier scores.
            enriched_item = {**matched, **item}

            add_evidence(
                "contradicting",
                paper_id,
                paper_title,
                claim_text,
                enriched_item,
            )

        # Weak/unrelated verifier evidence belongs in the dashboard's
        # existing "Neutral Evidence" section.
        for field in ("weak_evidence", "unrelated_evidence"):
            for item in verification.get(field, []):
                add_evidence(
                    "neutral",
                    paper_id,
                    paper_title,
                    claim_text,
                    item,
                )

        # Include neutral and uncertain skeptic evidence. When the
        # verifier explicitly classified the exact same evidence as
        # supporting, do not duplicate it in the neutral category.
        for field in ("neutral_evidence", "uncertain_evidence"):
            for item in skeptic.get(field, []):
                if not isinstance(item, dict):
                    continue

                evidence_key = normalize_text(item.get("evidence"))
                matched = verification_by_text.get(evidence_key, {})

                if matched.get("classification") == "supporting":
                    continue

                enriched_item = {**matched, **item}

                add_evidence(
                    "neutral",
                    paper_id,
                    paper_title,
                    claim_text,
                    enriched_item,
                )

    # Aggregate scores across each paper's distinct evidence records.
    for category in categories:
        for paper_key, record in indexes[category].items():
            metric = metrics[(category, paper_key)]

            for field in (
                "similarity_score",
                "verification_score",
                "structured_match_score",
                "contradiction_score",
            ):
                values = metric[field]

                if values:
                    average = sum(values) / len(values)
                    record[field] = round(
                        average,
                        4 if field == "similarity_score" else 2,
                    )
                elif field in (
                    "verification_score",
                    "structured_match_score",
                ):
                    record[field] = None
                else:
                    record[field] = 0.0

    return (
        groups["supporting"],
        groups["contradicting"],
        groups["neutral"],
    )



# ============================================================
# COMPLETE ANALYSIS
# ============================================================

@app.post("/api/analyze")
def analyze(
    request: AnalysisRequest
):

    # --------------------------------------------------------
    # VALIDATE QUERY
    # --------------------------------------------------------

    query = request.query.strip()

    if not query:

        raise HTTPException(
            status_code=400,
            detail="Research query cannot be empty."
        )

    print()
    print("=" * 70)
    print("RESEARCHCLAIMAI ANALYSIS REQUEST")
    print("=" * 70)
    print(
        f"Query: {query}"
    )
    print(
        f"Max results: {request.max_results}"
    )
    print("=" * 70)

    try:

        # ====================================================
        # RUN COMPLETE MULTI-AGENT PIPELINE
        # ====================================================

        pipeline_output = run_pipeline(
            query=query,
            max_results=request.max_results,
        )

        # ----------------------------------------------------
        # NORMALIZE PIPELINE OUTPUT
        # ----------------------------------------------------

        result = normalize_pipeline_result(
            pipeline_output
        )

        if not result:

            raise RuntimeError(
                "Pipeline returned an empty result."
            )

        # ====================================================
        # EXTRACT PIPELINE DATA
        # ====================================================

        papers = result.get(
            "papers",
            []
        )

        claims = result.get(
            "claims",
            []
        )

        contradictions = result.get(
            "contradictions",
            []
        )

        confidence = result.get(
            "confidence",
            {}
        )

        if not isinstance(
            papers,
            list
        ):
            papers = []

        if not isinstance(
            claims,
            list
        ):
            claims = []

        if not isinstance(
            contradictions,
            list
        ):
            contradictions = []

        if not isinstance(
            confidence,
            dict
        ):
            confidence = {}

        # ====================================================
        # BUILD EVIDENCE GROUPS
        # ====================================================

        (
            supporting_papers,
            contradicting_papers,
            neutral_papers,
        ) = build_evidence_groups(
            claims
        )

        # ====================================================
        # BUILD SUMMARY
        # ====================================================

        overall_score = confidence.get(
            "overall_score",
            0
        )

        confidence_level = confidence.get(
            "confidence_level",
            "Low"
        )

        summary = (
            f"Analysis completed for '{query}'. "
            f"The system retrieved {len(papers)} "
            f"research papers and extracted "
            f"{len(claims)} benchmark-related claims. "
            f"{len(contradictions)} cross-paper "
            f"comparison records were generated. "
            f"The aggregated confidence score is "
            f"{overall_score}/10 "
            f"({confidence_level})."
        )

        # ====================================================
        # FINAL API RESPONSE
        # ====================================================

        response = {

            "status": "success",

            "query": result.get(
                "query",
                query
            ),

            "papers_retrieved": result.get(
                "papers_retrieved",
                len(papers)
            ),

            "papers": papers,

            "claims_extracted": result.get(
                "claims_extracted",
                len(claims)
            ),

            "claims": claims,

            "supportingPapers": (
                supporting_papers
            ),

            "contradictingPapers": (
                contradicting_papers
            ),

            "neutralPapers": (
                neutral_papers
            ),

            "contradictions": (
                contradictions
            ),

            "confidence": confidence,

            "summary": summary,
        }

        # ====================================================
        # SERVER LOG
        # ====================================================

        print()
        print("=" * 70)
        print("API ANALYSIS COMPLETED")
        print("=" * 70)

        print(
            f"Papers: "
            f"{response['papers_retrieved']}"
        )

        print(
            f"Claims: "
            f"{response['claims_extracted']}"
        )

        print(
            f"Supporting evidence: "
            f"{len(supporting_papers)}"
        )

        print(
            f"Contradicting evidence: "
            f"{len(contradicting_papers)}"
        )

        print(
            f"Neutral evidence: "
            f"{len(neutral_papers)}"
        )

        print(
            f"Contradiction pairs: "
            f"{len(contradictions)}"
        )

        print(
            f"Overall confidence: "
            f"{confidence.get('overall_score', 0)}/10"
        )

        print(
            f"Confidence level: "
            f"{confidence.get('confidence_level', 'Low')}"
        )

        print("=" * 70)

        return response

    except HTTPException:
        raise

    except Exception as error:

        print()
        print("=" * 70)
        print("API ANALYSIS FAILED")
        print("=" * 70)

        print(
            f"Error: {error}"
        )

        traceback.print_exc()

        raise HTTPException(
            status_code=500,
            detail=str(error)
        )


# ============================================================
# RUN DIRECTLY
# ============================================================

if __name__ == "__main__":

    import uvicorn

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
    )