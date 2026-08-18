"""
confidence_scoring.py

WHAT:
Combines outputs from multiple agents into one Overall Confidence Score.

WHY:
Each individual agent evaluates only one aspect of a research claim.
This module aggregates those evaluations into a single confidence value
that can be displayed on the dashboard.

Author: Malavika Krishna
"""

from dataclasses import dataclass


# --------------------------------------------------
# Weights
# --------------------------------------------------

WEIGHTS = {
    "evidence_strength": 0.40,
    "verification": 0.30,
    "contradiction": 0.20,
    "skeptic": 0.10,
}


@dataclass
class ConfidenceResult:
    overall_score: float
    confidence_level: str
    breakdown: dict


def calculate_confidence(
    evidence_strength: float,
    verification_score: float,
    contradiction_score: float,
    skeptic_score: float,
):
    """
    Parameters
    ----------
    evidence_strength : float
        Output of Evidence Strength Agent (0-10)

    verification_score : float
        Output of Verification Agent (0-10)

    contradiction_score : float
        Output of Contradiction Agent (0-10)
        Higher means fewer contradictions.

    skeptic_score : float
        Output of Skeptic Agent (0-10)
        Higher means stronger resistance to skeptical checks.

    Returns
    -------
    ConfidenceResult
    """

    overall = (
        evidence_strength * WEIGHTS["evidence_strength"]
        + verification_score * WEIGHTS["verification"]
        + contradiction_score * WEIGHTS["contradiction"]
        + skeptic_score * WEIGHTS["skeptic"]
    )

    overall = round(overall, 2)

    if overall >= 8:
        level = "High"

    elif overall >= 6:
        level = "Medium"

    else:
        level = "Low"

    return ConfidenceResult(
        overall_score=overall,
        confidence_level=level,
        breakdown={
            "Evidence Strength": evidence_strength,
            "Verification": verification_score,
            "Contradiction": contradiction_score,
            "Skeptic": skeptic_score,
        },
    )


if __name__ == "__main__":

    result = calculate_confidence(
        evidence_strength=8.9,
        verification_score=8.2,
        contradiction_score=9.1,
        skeptic_score=7.8,
    )

    print(result)