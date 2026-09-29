from typing import List, Dict, Optional, Tuple
import re

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


class EvidenceVerificationAgent:
    """
    Evidence verification using structured factual matching plus TF-IDF.

    The original implementation relied only on TF-IDF cosine similarity.
    That is not sufficient for research evidence such as tables because a
    table can contain many correct but irrelevant tokens (other models,
    scores, and columns).  This implementation therefore checks the fields
    that matter for the claim explicitly and uses TF-IDF only as a small
    supplementary signal.

    Verification score returned per evidence item:
        0.0 - 10.0

    Classification is based on the structured verification score normalized
    to 0.0 - 1.0:
        >= 0.75 -> supporting
        >= 0.45 -> weak
        <  0.45 -> unrelated
    """

    def __init__(
        self,
        support_threshold: float = 0.75,
        weak_threshold: float = 0.45,
    ):
        self.support_threshold = support_threshold
        self.weak_threshold = weak_threshold

    # ------------------------------------------------------------------
    # BASIC TEXT HELPERS
    # ------------------------------------------------------------------

    @staticmethod
    def _normalize_text(text: str) -> str:
        return re.sub(r"[^a-z0-9]+", "", (text or "").lower())

    @staticmethod
    def _contains_benchmark(evidence: str, benchmark: str) -> bool:
        if not evidence or not benchmark:
            return False

        escaped = re.escape(benchmark.strip())
        # Treat hyphen as part of benchmark names so MMLU does not match
        # inside MMLU-Pro or Mobile-MMLU.
        pattern = rf"(?<![A-Za-z0-9-]){escaped}(?![A-Za-z0-9-])"
        return re.search(pattern, evidence, flags=re.IGNORECASE) is not None

    @staticmethod
    def _extract_claim_model(claim: str) -> Optional[str]:
        """
        Extract the model subject from common performance-claim wording.
        Examples:
            'gpt-4o achieves 84.84 on MMLU'
            'TestModel-7B obtains 86.4% accuracy on MMLU'
        """
        if not claim:
            return None

        match = re.search(
            r"^\s*(.+?)\s+"
            r"(?:achieves|obtains|reports|records|scores|gets|reaches|"
            r"attains|performs|measures)\b",
            claim.strip(),
            flags=re.IGNORECASE,
        )

        if not match:
            return None

        model = match.group(1).strip(" ,:.-")
        return model or None

    @staticmethod
    def _extract_claim_benchmark(claim: str) -> Optional[str]:
        if not claim:
            return None

        match = re.search(
            r"\bon\s+([A-Za-z0-9][A-Za-z0-9._:+/\-]*)",
            claim,
            flags=re.IGNORECASE,
        )
        return match.group(1).rstrip(".,;:)") if match else None

    @staticmethod
    def _extract_claim_value(claim: str) -> Optional[Tuple[float, bool]]:
        if not claim:
            return None

        # Prefer the number immediately associated with the performance
        # verb so model parameter counts do not get mistaken for the score.
        match = re.search(
            r"\b(?:achieves|obtains|reports|records|scores|gets|reaches|attains|"
            r"measures)\s+"
            r"(?:a\s+score\s+of\s+)?"
            r"([0-9]+(?:\.[0-9]+)?)\s*(%)?",
            claim,
            flags=re.IGNORECASE,
        )

        if not match:
            return None

        try:
            return float(match.group(1)), bool(match.group(2))
        except ValueError:
            return None

    @staticmethod
    def _extract_claim_setting(claim: str) -> Optional[str]:
        if not claim:
            return None

        patterns = [
            (r"\bzero[-\s]?shot\b", "0-shot"),
            (r"\bone[-\s]?shot\b", "1-shot"),
            (r"\btwo[-\s]?shot\b", "2-shot"),
            (r"\bfew[-\s]?shot\b", "few-shot"),
            (r"\b(\d+)[-\s]?shot\b", None),
        ]

        for pattern, fixed in patterns:
            match = re.search(pattern, claim, flags=re.IGNORECASE)
            if match:
                if fixed:
                    return fixed
                return f"{match.group(1)}-shot"

        return None

    @staticmethod
    def _extract_claim_metric(claim: str) -> Optional[str]:
        if not claim:
            return None

        metric_patterns = [
            (r"\baccuracy\b", "accuracy"),
            (r"\bexact\s+match\b", "exact_match"),
            (r"\bf1(?:[-\s]?score)?\b", "f1"),
            (r"\bbleu\b", "bleu"),
            (r"\brouge\b", "rouge"),
            (r"\bauroc\b|\bauc\b", "auc"),
            (r"\bprecision\b", "precision"),
            (r"\brecall\b", "recall"),
        ]

        for pattern, metric in metric_patterns:
            if re.search(pattern, claim, flags=re.IGNORECASE):
                return metric

        return None

    @staticmethod
    def _extract_evidence_settings(evidence: str) -> List[str]:
        if not evidence:
            return []

        settings = []

        if re.search(r"\bzero[-\s]?shot\b", evidence, flags=re.IGNORECASE):
            settings.append("0-shot")

        if re.search(r"\bone[-\s]?shot\b", evidence, flags=re.IGNORECASE):
            settings.append("1-shot")

        if re.search(r"\btwo[-\s]?shot\b", evidence, flags=re.IGNORECASE):
            settings.append("2-shot")

        if re.search(r"\bfew[-\s]?shot\b", evidence, flags=re.IGNORECASE):
            settings.append("few-shot")

        for value in re.findall(r"\b(\d+)[-\s]?shot\b", evidence, flags=re.IGNORECASE):
            setting = f"{value}-shot"
            if setting not in settings:
                settings.append(setting)

        return settings

    @staticmethod
    def _extract_evidence_numbers(evidence: str) -> List[float]:
        if not evidence:
            return []

        numbers = []
        for token in re.findall(
            r"(?<![A-Za-z0-9])(?:\d+\.\d+|\d+)(?![A-Za-z0-9])",
            evidence,
        ):
            try:
                numbers.append(float(token))
            except ValueError:
                continue

        return numbers

    @staticmethod
    def _value_matches(
        claimed_value: float,
        claimed_is_percent: bool,
        evidence: str,
    ) -> bool:
        """
        Match values robustly across common representations:
            0.845 <-> 84.5%
            84.5% <-> 84.5
        """
        evidence_values = EvidenceVerificationAgent._extract_evidence_numbers(
            evidence
        )

        if not evidence_values:
            return False

        candidates = [claimed_value]

        if not claimed_is_percent:
            # A decimal proportion may be reported as a percentage.
            if 0 < claimed_value <= 1:
                candidates.append(claimed_value * 100)
        else:
            # A percentage may appear as a decimal proportion.
            if claimed_value > 1:
                candidates.append(claimed_value / 100)

        for expected in candidates:
            for actual in evidence_values:
                tolerance = max(0.001, abs(expected) * 0.0005)
                if abs(actual - expected) <= tolerance:
                    return True

        return False

    # ------------------------------------------------------------------
    # TF-IDF DIAGNOSTIC SIGNAL
    # ------------------------------------------------------------------

    def calculate_similarity(self, claim: str, evidence: str) -> float:
        documents = [claim or "", evidence or ""]

        if not documents[0].strip() or not documents[1].strip():
            return 0.0

        try:
            vectorizer = TfidfVectorizer(stop_words="english")
            vectors = vectorizer.fit_transform(documents)

            similarity = cosine_similarity(
                vectors[0:1],
                vectors[1:2],
            )[0][0]

            return round(float(similarity), 3)
        except ValueError:
            # Happens when the vectorizer has no usable vocabulary.
            return 0.0

    # ------------------------------------------------------------------
    # STRUCTURED VERIFICATION
    # ------------------------------------------------------------------

    def _structured_match_details(
        self,
        claim: str,
        evidence: str,
        similarity: float,
        claim_model: Optional[str] = None,
        claim_benchmark: Optional[str] = None,
        claim_value: Optional[float] = None,
        claim_is_percent: Optional[bool] = None,
        claim_setting: Optional[str] = None,
        claim_metric: Optional[str] = None,
    ) -> Dict:
        """
        BUGFIX: this used to ALWAYS re-derive the model/benchmark/value from
        the claim's free-text sentence via regex (_extract_claim_model etc),
        even though claim_extraction_agent.py already extracted and
        strictly validated exactly these fields (benchmark_name,
        reported_value, model_name) when it built the claim in the first
        place. Those regexes only recognize a handful of present-tense verb
        phrasings ("X achieves Y on Z"); real Gemini output regularly comes
        back as "X achieved a Y score of Z" (past tense, "an X score of Y"
        instead of "on X") and every one of these functions silently
        returned None, so live claims were scored 0.25-0.3/10 "unrelated"
        regardless of how good the evidence actually was.
        Now: if the caller already knows these values (the normal case,
        via verify_evidence's new keyword args), use them directly and skip
        regex parsing entirely. Only fall back to regex-extracting from the
        claim sentence when the caller doesn't have structured data - e.g.
        the regression tests below, which intentionally exercise the
        free-text parsing path.
        """
        if claim_model is None:
            claim_model = self._extract_claim_model(claim)

        if claim_benchmark is None:
            claim_benchmark = self._extract_claim_benchmark(claim)

        if claim_value is not None:
            claim_value_info = (claim_value, bool(claim_is_percent))
        else:
            claim_value_info = self._extract_claim_value(claim)

        if claim_setting is None:
            claim_setting = self._extract_claim_setting(claim)

        if claim_metric is None:
            claim_metric = self._extract_claim_metric(claim)

        evidence_normalized = self._normalize_text(evidence)
        model_match = bool(
            claim_model
            and self._normalize_text(claim_model) in evidence_normalized
        )

        benchmark_match = bool(
            claim_benchmark
            and self._contains_benchmark(evidence, claim_benchmark)
        )

        value_match = False
        claimed_value = None
        claimed_is_percent = False

        if claim_value_info is not None:
            claimed_value, claimed_is_percent = claim_value_info
            value_match = self._value_matches(
                claimed_value=claimed_value,
                claimed_is_percent=claimed_is_percent,
                evidence=evidence,
            )

        setting_match = None
        if claim_setting:
            setting_match = claim_setting in self._extract_evidence_settings(
                evidence
            )

        metric_match = None
        if claim_metric:
            metric_match = bool(
                re.search(
                    {
                        "accuracy": r"\baccuracy\b",
                        "exact_match": r"\bexact\s+match\b",
                        "f1": r"\bf1(?:[-\s]?score)?\b",
                        "bleu": r"\bbleu\b",
                        "rouge": r"\brouge\b",
                        "auc": r"\bauroc\b|\bauc\b",
                        "precision": r"\bprecision\b",
                        "recall": r"\brecall\b",
                    }.get(claim_metric, re.escape(claim_metric)),
                    evidence,
                    flags=re.IGNORECASE,
                )
                is not None
            )

        # Dynamic weighting: optional fields are only scored when the claim
        # actually establishes them.
        checks = [
            ("model", 0.30, model_match),
            ("benchmark", 0.20, benchmark_match),
            ("value", 0.30, value_match),
        ]

        if claim_setting:
            checks.append(("setting", 0.10, bool(setting_match)))

        if claim_metric:
            checks.append(("metric", 0.05, bool(metric_match)))

        checks.append(("text_similarity", 0.05, similarity))

        total_weight = sum(weight for _, weight, _ in checks)
        weighted_score = (
            sum(weight * float(value) for _, weight, value in checks)
            / total_weight
            if total_weight
            else 0.0
        )

        return {
            "model": claim_model,
            "benchmark": claim_benchmark,
            "reported_value": claimed_value,
            "evaluation_setting": claim_setting,
            "metric": claim_metric,
            "model_match": model_match,
            "benchmark_match": benchmark_match,
            "value_match": value_match,
            "setting_match": setting_match,
            "metric_match": metric_match,
            "structured_match_score": round(weighted_score, 3),
            "verification_score": round(weighted_score * 10, 2),
        }

    def classify_evidence(self, similarity: float) -> str:
        """
        Backwards-compatible classification helper.

        `similarity` now represents the normalized structured verification
        score (0.0 - 1.0), not raw TF-IDF similarity.
        """
        if similarity >= self.support_threshold:
            return "supporting"

        if similarity >= self.weak_threshold:
            return "weak"

        return "unrelated"

    def verify_evidence(
        self,
        claim: str,
        evidence_list: List[Dict],
        claim_model: Optional[str] = None,
        claim_benchmark: Optional[str] = None,
        claim_value: Optional[float] = None,
        claim_is_percent: Optional[bool] = None,
        claim_setting: Optional[str] = None,
        claim_metric: Optional[str] = None,
    ) -> Dict:
        """
        claim_model / claim_benchmark / claim_value / claim_is_percent /
        claim_setting / claim_metric are OPTIONAL. Pass them in whenever
        you already have them (e.g. straight from the claim dict that
        claim_extraction_agent.py produced: model_name, benchmark_name,
        reported_value, value_type == "percentage", evaluation_setting,
        metric) - this is strictly more reliable than making this agent
        re-guess them from the claim sentence's wording. If omitted, this
        falls back to the old regex-based extraction from `claim`.
        """
        results = []

        for evidence in evidence_list:
            paper_id = evidence.get(
                "paper_id",
                "unknown",
            )

            evidence_text = evidence.get(
                "text",
                "",
            )

            lexical_similarity = self.calculate_similarity(
                claim,
                evidence_text,
            )

            match_details = self._structured_match_details(
                claim=claim,
                evidence=evidence_text,
                similarity=lexical_similarity,
                claim_model=claim_model,
                claim_benchmark=claim_benchmark,
                claim_value=claim_value,
                claim_is_percent=claim_is_percent,
                claim_setting=claim_setting,
                claim_metric=claim_metric,
            )

            normalized_match_score = match_details["structured_match_score"]
            classification = self.classify_evidence(
                normalized_match_score
            )

            results.append(
                {
                    "paper_id": paper_id,
                    # Preserve the original field for diagnostics/backwards
                    # compatibility.
                    "similarity_score": lexical_similarity,
                    # New score used by the pipeline.
                    "verification_score": match_details["verification_score"],
                    "structured_match_score": normalized_match_score,
                    "classification": classification,
                    "evidence": evidence_text,
                    "match_details": match_details,
                }
            )

        supporting = [
            item
            for item in results
            if item["classification"] == "supporting"
        ]

        weak = [
            item
            for item in results
            if item["classification"] == "weak"
        ]

        unrelated = [
            item
            for item in results
            if item["classification"] == "unrelated"
        ]

        return {
            "claim": claim,
            "total_evidence": len(results),
            "supporting_evidence": supporting,
            "weak_evidence": weak,
            "unrelated_evidence": unrelated,
            "evidence_results": results,
        }
