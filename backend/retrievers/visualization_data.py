"""
visualization_data.py

WHAT
-----
Prepares visualization-ready JSON for the frontend dashboard.

This module DOES NOT create charts.

Instead it converts database objects into clean JSON structures
for React/D3.js visualizations.

Visualizations Supported
------------------------

1. Contradiction Table
2. Evidence Strength Chart
3. Claim Summary Cards
4. Dashboard Statistics

Author:
Malavika Krishna
"""

from db_schema import (
    get_session,
    Paper,
    Claim,
    Evidence,
    Contradiction,
)

# -------------------------------------------------------------
# Dashboard Statistics
# -------------------------------------------------------------

def dashboard_summary():
    """
    Returns high-level statistics for the dashboard.
    """

    session = get_session()

    papers = session.query(Paper).count()
    claims = session.query(Claim).count()
    evidence = session.query(Evidence).count()
    contradictions = session.query(Contradiction).count()
    avg_confidence = session.query(Claim).all()

    if avg_confidence:
        avg_score = round(
            sum(c.evidence_strength_score or 0 for c in avg_confidence) /
            len(avg_confidence),
            2
        )
    else:
        avg_score = 0

    session.close()

    return {
        "papers": papers,
        "claims": claims,
        "evidence": evidence,
        "contradictions": contradictions,
        "average_confidence": avg_score}


# -------------------------------------------------------------
# Evidence Strength Chart
# -------------------------------------------------------------

def evidence_strength_chart():
    """
    Returns chart-ready JSON.

    React can directly render this as a bar chart.
    """

    session = get_session()

    claims = session.query(Claim).all()

    data = []

    for claim in claims:

        data.append({
            "claim_id": claim.id,
            "benchmark": claim.benchmark_name,
            "claim": claim.claim_text[:70] + "...",
            "score": claim.evidence_strength_score
        })

    session.close()

    return data


# -------------------------------------------------------------
# Claim Cards
# -------------------------------------------------------------

def claim_cards():
    """
    Returns summary cards for each claim.
    """

    session = get_session()
    claims = session.query(Claim).all()
    cards = []
    for claim in claims:
        paper = claim.paper
        cards.append({
            "claim_id": claim.id,
            "paper_title": paper.title,
            "benchmark": claim.benchmark_name,
            "reported_value": claim.reported_value,
            "evidence_strength_score": claim.evidence_strength_score,
            "claim": claim.claim_text})

    session.close()

    return cards


# -------------------------------------------------------------
# Contradiction Table
# -------------------------------------------------------------

def contradiction_table():
    """
    Returns table-ready contradiction data.

    Adithya's agent will populate this table.
    """

    session = get_session()

    rows = []

    contradictions = session.query(Contradiction).all()

    for c in contradictions:

        claim_a = session.get(Claim, c.claim_a_id)

        claim_b = session.get(Claim, c.claim_b_id)

        rows.append({
            "claim_a": claim_a.claim_text,
            "claim_b": claim_b.claim_text,
            "relation": c.relation_type,
            "severity": c.severity})

    session.close()

    return rows


# -------------------------------------------------------------
# Dashboard Export
# -------------------------------------------------------------

def dashboard_json():
    """
    Returns everything required by the frontend.
    """

    return {
        "summary": dashboard_summary(),
        "claim_cards": claim_cards(),
        "evidence_strength": evidence_strength_chart(),
        "contradictions": contradiction_table()}


# -------------------------------------------------------------
# Testing
# -------------------------------------------------------------

if __name__ == "__main__":
    import json
    dashboard = dashboard_json()
    print(json.dumps(dashboard, indent=4))