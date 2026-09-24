"""
main.py

FastAPI backend for the Intelligent Multi-Agent Research Claim Analysis
Platform.

OWNER: Adithya Ajith - Backend: FastAPI Design & REST API Endpoints.

WHAT THIS FILE DOES:
Exposes the already-built multi-agent pipeline (retrieval -> claim
extraction -> evidence verification -> skeptic review -> evidence
strength scoring -> contradiction detection -> confidence aggregation,
all implemented across backend/retrievers/ and backend/agents/) as a REST
API the frontend (Next.js) can call.

This file does NOT re-implement any agent logic. It only routes HTTP
requests to the pipeline entrypoint (`run_pipeline`, from test_pipeline.py)
and to read-only query helpers backed by the shared SQLite/PostgreSQL
database (db_schema.py).

ENDPOINTS
---------
GET  /                          API info
GET  /health                    liveness check
POST /api/analyze               runs the full pipeline for a query (FR1-FR5)
GET  /api/papers                list all stored papers
GET  /api/papers/{paper_id}     one paper + its claims
GET  /api/claims/{claim_id}     one claim, with its evidence
GET  /api/contradictions        all stored claim-pair contradictions
GET  /api/dashboard-summary     aggregate stats for the dashboard header
"""

import os
import sys
import traceback

# ---------------------------------------------------------------------
# Make backend/retrievers importable regardless of the process's CWD.
# (The existing retriever/agent modules import each other with bare
# names like `from db_schema import ...`, so their directory has to be
# on sys.path - not just the repo root.)
# ---------------------------------------------------------------------
BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
RETRIEVERS_DIR = os.path.join(BACKEND_DIR, "retrievers")
for path in (BACKEND_DIR, RETRIEVERS_DIR):
    if path not in sys.path:
        sys.path.insert(0, path)

# Repeated /api/analyze calls should ADD to the shared database, not wipe
# it before every request - RESET_DATABASE_ON_RUN=true is meant for the
# `python test_pipeline.py` regression/dev-run workflow, not the live API.
# Must be set before test_pipeline is imported (it reads this at import
# time).
os.environ.setdefault("RESET_DATABASE_ON_RUN", "false")

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from db_schema import get_session, Paper, Claim, Evidence, Contradiction
from test_pipeline import run_pipeline
import visualization_data

app = FastAPI(
    title="ResearchClaimAI API",
    description=(
        "REST API for the Intelligent Multi-Agent Framework for "
        "Autonomous Analysis and Verification of Research Claims."
    ),
    version="1.0.0",
)

# Frontend dev servers (Next.js default port + common alternates).
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# =======================================================================
# Request / response models
# =======================================================================

class AnalyzeRequest(BaseModel):
    query: str = Field(..., min_length=3, description="Research topic, keyword, or DOI to analyze")
    max_results: int = Field(8, ge=1, le=10, description="Max papers to retrieve (NFR caps batch at 10)")


# =======================================================================
# Root / health
# =======================================================================

@app.get("/")
def root():
    """API info and a map of available endpoints."""
    return {
        "message": "ResearchClaimAI API",
        "endpoints": {
            "POST /api/analyze": "Run the full agent pipeline for a query",
            "GET /api/papers": "List all stored papers",
            "GET /api/papers/{paper_id}": "Paper detail + its claims",
            "GET /api/claims/{claim_id}": "Claim detail + evidence",
            "GET /api/contradictions": "All stored contradictions",
            "GET /api/dashboard-summary": "Aggregate stats for dashboard header",
            "GET /health": "Liveness check",
            "GET /docs": "Interactive API docs (Swagger UI)",
        },
    }


@app.get("/health")
def health_check():
    return {"status": "healthy"}


# =======================================================================
# Core pipeline endpoint (FR1-FR5)
# =======================================================================

@app.post("/api/analyze")
def analyze(request: AnalyzeRequest):
    """
    Runs the full multi-agent pipeline for a research topic/keyword:

      retrieval -> claim extraction -> evidence verification ->
      skeptic review -> evidence-strength scoring -> contradiction
      detection -> overall confidence score

    and persists every step's output to the database.

    NOTE: this is a long-running synchronous call (the SRS's Performance
    NFR budgets 60-90s per paper) because each claim makes one or more
    LLM calls. Point any frontend "Analyze" button at this and show a
    loading state - don't expect an instant response.
    """
    try:
        result = run_pipeline(query=request.query, max_results=request.max_results)
        return result
    except Exception as exc:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Pipeline failed: {exc}")


# =======================================================================
# Read endpoints - backed by the persistence layer (FR5 / dashboard)
# =======================================================================

def _claim_to_dict(claim: Claim) -> dict:
    return {
        "claim_id": claim.id,
        "paper_id": claim.paper_id,
        "claim": claim.claim_text,
        "claim_type": claim.claim_type,
        "section": claim.section,
        "benchmark_name": claim.benchmark_name,
        "reported_value": claim.reported_value,
        "value_type": claim.value_type,
        "evidence_strength_score": claim.evidence_strength_score,
        "evidence": [
            {
                "evidence_id": e.id,
                "citation_text": e.citation_text,
                "reliability_score": e.reliability_score,
            }
            for e in claim.evidence
        ],
    }


@app.get("/api/papers")
def list_papers():
    session = get_session()
    try:
        papers = session.query(Paper).all()
        return {
            "status": "success",
            "total_papers": len(papers),
            "papers": [
                {
                    "id": p.id,
                    "title": p.title,
                    "authors": p.authors,
                    "year": p.year,
                    "source": p.source,
                    "source_url": p.source_url,
                    "claim_count": len(p.claims),
                }
                for p in papers
            ],
        }
    finally:
        session.close()


@app.get("/api/papers/{paper_id}")
def get_paper(paper_id: str):
    session = get_session()
    try:
        paper = session.get(Paper, paper_id)
        if not paper:
            raise HTTPException(status_code=404, detail=f"Paper '{paper_id}' not found")
        return {
            "status": "success",
            "paper": {
                "id": paper.id,
                "title": paper.title,
                "authors": paper.authors,
                "year": paper.year,
                "source": paper.source,
                "source_url": paper.source_url,
            },
            "claims": [_claim_to_dict(c) for c in paper.claims],
        }
    finally:
        session.close()


@app.get("/api/claims/{claim_id}")
def get_claim(claim_id: int):
    session = get_session()
    try:
        claim = session.get(Claim, claim_id)
        if not claim:
            raise HTTPException(status_code=404, detail=f"Claim {claim_id} not found")
        return {"status": "success", "claim": _claim_to_dict(claim)}
    finally:
        session.close()


@app.get("/api/contradictions")
def list_contradictions():
    session = get_session()
    try:
        rows = session.query(Contradiction).all()
        results = []
        for c in rows:
            claim_a = session.get(Claim, c.claim_a_id)
            claim_b = session.get(Claim, c.claim_b_id)
            results.append({
                "id": c.id,
                "relation_type": c.relation_type,
                "severity": c.severity,
                "claim_a": {
                    "id": claim_a.id if claim_a else None,
                    "text": claim_a.claim_text if claim_a else None,
                    "paper_id": claim_a.paper_id if claim_a else None,
                },
                "claim_b": {
                    "id": claim_b.id if claim_b else None,
                    "text": claim_b.claim_text if claim_b else None,
                    "paper_id": claim_b.paper_id if claim_b else None,
                },
            })
        return {"status": "success", "total": len(results), "contradictions": results}
    finally:
        session.close()


@app.get("/api/dashboard-summary")
def dashboard_summary():
    """Aggregate stats (paper/claim/evidence/contradiction counts, avg
    confidence) for the dashboard header. Delegates to
    visualization_data.py so the frontend's dashboard components and this
    endpoint always agree on shape."""
    try:
        return {"status": "success", "summary": visualization_data.dashboard_summary()}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
