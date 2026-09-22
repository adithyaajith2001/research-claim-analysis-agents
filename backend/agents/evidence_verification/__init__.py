from typing import List

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from agents.evidence_verification.agent import EvidenceVerificationAgent
from agents.skeptic.agent import SkepticAgent


# ============================================================
# RESEARCHCLAIMAI BACKEND
# ============================================================

app = FastAPI(
    title="ResearchClaimAI API",
    description="Backend API for ResearchClaimAI multi-agent analysis",
    version="1.0.0"
)


# ============================================================
# CORS
# ============================================================

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================
# REQUEST MODELS
# ============================================================

class Evidence(BaseModel):
    paper_id: str
    text: str


class AnalysisRequest(BaseModel):
    claim: str
    evidence: List[Evidence]


# ============================================================
# INITIALIZE AGENTS
# ============================================================

evidence_agent = EvidenceVerificationAgent()
skeptic_agent = SkepticAgent()


# ============================================================
# ROOT ENDPOINT
# ============================================================

@app.get("/")
def root():
    return {
        "message": "ResearchClaimAI Backend is running"
    }


# ============================================================
# HEALTH CHECK
# ============================================================

@app.get("/api/health")
def health():

    return {
        "status": "healthy",
        "agents": {
            "evidence_verification": "ready",
            "skeptic": "ready"
        }
    }


# ============================================================
# CLAIM ANALYSIS
# ============================================================

@app.post("/api/analyze")
def analyze_claim(request: AnalysisRequest):

    # Convert Pydantic objects into dictionaries
    evidence_data = [
        item.model_dump()
        for item in request.evidence
    ]

    # --------------------------------------------------------
    # Agent 1: Evidence Verification
    # --------------------------------------------------------

    evidence_result = evidence_agent.verify_evidence(
        request.claim,
        evidence_data
    )

    # --------------------------------------------------------
    # Agent 2: Skeptic
    # --------------------------------------------------------

    skeptic_result = skeptic_agent.analyze_evidence(
        request.claim,
        evidence_data
    )

    # --------------------------------------------------------
    # Create a simple summary for the frontend
    # --------------------------------------------------------

    supporting_count = len(
        evidence_result.get("supporting_evidence", [])
    )

    weak_count = len(
        evidence_result.get("weak_evidence", [])
    )

    unrelated_count = len(
        evidence_result.get("unrelated_evidence", [])
    )

    contradicting_count = len(
        skeptic_result.get("contradicting_evidence", [])
    )

    uncertain_count = len(
        skeptic_result.get("uncertain_evidence", [])
    )

    neutral_count = len(
        skeptic_result.get("neutral_evidence", [])
    )

    total_evidence = len(evidence_data)

    # --------------------------------------------------------
    # Combined response
    # --------------------------------------------------------

    return {

        "status": "analysis_completed",

        "claim": request.claim,

        "summary": {
            "total_evidence": total_evidence,

            "supporting_evidence": supporting_count,

            "weak_evidence": weak_count,

            "unrelated_evidence": unrelated_count,

            "contradicting_evidence": contradicting_count,

            "uncertain_evidence": uncertain_count,

            "neutral_evidence": neutral_count
        },

        "evidence_verification": evidence_result,

        "skeptic_analysis": skeptic_result
    }