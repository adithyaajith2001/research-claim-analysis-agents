from typing import List, Dict


class SkepticAgent:

    def __init__(self):
        self.contradiction_keywords = [
            "not",
            "no evidence",
            "unlikely",
            "fails",
            "failed",
            "contradicts",
            "contradictory",
            "however",
            "but",
            "although",
            "inconsistent",
            "disputed",
            "uncertain",
            "limited evidence",
            "insufficient evidence",
        ]

    def analyze_evidence(
        self,
        claim: str,
        evidence_list: List[Dict]
    ) -> Dict:

        results = []

        claim_lower = claim.lower()

        for evidence in evidence_list:

            paper_id = evidence.get(
                "paper_id",
                "unknown"
            )

            text = evidence.get(
                "text",
                ""
            )

            text_lower = text.lower()

            matched_keywords = [
                keyword
                for keyword in self.contradiction_keywords
                if keyword in text_lower
            ]

            contradiction_score = min(
                len(matched_keywords) * 0.15,
                1.0
            )

            if contradiction_score >= 0.45:
                classification = "contradicting"

            elif contradiction_score >= 0.15:
                classification = "uncertain"

            else:
                classification = "neutral"

            results.append({
                "paper_id": paper_id,
                "classification": classification,
                "contradiction_score": round(
                    contradiction_score,
                    3
                ),
                "matched_keywords": matched_keywords,
                "evidence": text
            })

        contradicting = [
            item for item in results
            if item["classification"] == "contradicting"
        ]

        uncertain = [
            item for item in results
            if item["classification"] == "uncertain"
        ]

        neutral = [
            item for item in results
            if item["classification"] == "neutral"
        ]

        return {
            "claim": claim,
            "total_evidence": len(results),
            "contradicting_evidence": contradicting,
            "uncertain_evidence": uncertain,
            "neutral_evidence": neutral
        }