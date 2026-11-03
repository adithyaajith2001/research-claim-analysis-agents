"""
unified_retriever.py

Combines arXiv, Semantic Scholar, and CrossRef retrieval.

Enhancements:
- Deduplicates papers by stable identifiers AND normalized title.
- Scores retrieved papers against the user query using title/abstract metadata.
- Treats explicitly requested benchmarks as exact retrieval targets.
- Prevents benchmark variants from receiving the same exact-match boost.
- Filters clearly irrelevant results before downstream PDF enrichment/claim extraction.
- Distinguishes exact benchmark matches from related variants while preserving useful variant recall.
- Prints retrieval diagnostics so paper-selection decisions are traceable.
- Keeps compatibility with StandardPaper objects and legacy dictionaries.
"""

import json
import os
import re
import unicodedata
from typing import List, Dict, Optional, Union, Tuple

from arxiv_retriever import ArxivRetriever
from semantic_scholar_retriever import (
    SemanticScholarRetriever
)
from crossref_retriever import (
    CrossRefRetriever
)
from paper_schema import StandardPaper


PaperLike = Union[
    StandardPaper,
    Dict
]


# ============================================================
# RELEVANCE CONFIGURATION
# ============================================================

# Query terms that are too generic to contribute much to paper relevance.
_STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "by", "for", "from",
    "in", "into", "is", "it", "of", "on", "or", "that", "the", "to",
    "with", "this", "these", "those", "using", "use", "used", "paper",
    "research", "result", "results", "study", "studies", "method",
    "methods", "approach", "approaches", "model", "models",
}

# Terms that indicate benchmark/evaluation relevance. These are intentionally
# generic because the retriever should work for benchmarks beyond MMLU.
_EVALUATION_TERMS = {
    "benchmark",
    "benchmarks",
    "evaluation",
    "evaluations",
    "accuracy",
    "performance",
    "score",
    "scores",
    "dataset",
    "leaderboard",
    "test",
    "testing",
}

# Exact benchmark-family spellings receive an additional title/abstract boost.
# The list is deliberately broader than VALIDATED_BENCHMARKS so variants can
# still be retrieved without being silently normalized into another benchmark.
_BENCHMARK_FAMILY_PATTERNS = (
    "mmlu",
    "mmlu-pro",
    "mobile-mmlu",
    "mobile-mmlu-pro",
    "video-mmlu",
    "video-mmlu-pro",
    "tr-mmlu",
    "mmlu-sr",
    "gsm8k",
    "math",
    "humaneval",
    "mbpp",
)

# A score at or above this threshold is considered relevant enough to pass to
# the downstream pipeline. If too few papers meet the threshold, we keep the
# best few retrieved papers rather than returning nothing.
MIN_RELEVANCE_SCORE = 2.0

# Keep at least this many candidates when possible so one overly strict query
# does not accidentally eliminate the whole result set.
MIN_FALLBACK_RESULTS = 3

# When the user's query explicitly names a benchmark, exact benchmark support
# is preferred over generic family/variant matches. This prevents a query for
# MMLU from treating MMLU-Pro, Mobile-MMLU, or Video-MMLU as exact matches.
EXPLICIT_BENCHMARK_MIN_SCORE = 4.0

# Minimum score required for a benchmark-variant paper to fill remaining
# result slots for an explicit benchmark query. This is intentionally
# lower than the exact-benchmark preference threshold so related variants
# can improve recall without replacing genuine exact matches.
RELATED_VARIANT_MIN_SCORE = 4.0


class UnifiedPaperRetriever:
    """
    Combines arXiv, Semantic Scholar, and CrossRef.

    Retrieval is performed independently for each source, followed by:
        1. cross-source deduplication,
        2. query-relevance scoring,
        3. relevance filtering/ranking,
        4. final result limiting.
    """

    def __init__(self):

        self.arxiv_retriever = (
            ArxivRetriever()
        )

        self.semantic_retriever = (
            SemanticScholarRetriever()
        )

        self.crossref_retriever = (
            CrossRefRetriever()
        )

    # ========================================================
    # GENERIC FIELD HELPERS
    # ========================================================

    @staticmethod
    def _get_field(
        paper: PaperLike,
        *field_names: str
    ):
        """Safely read a field from StandardPaper or legacy dictionaries."""

        if isinstance(paper, dict):
            for field_name in field_names:
                value = paper.get(field_name)
                if value not in (None, ""):
                    return value

            raw_metadata = paper.get("raw_metadata")
            if isinstance(raw_metadata, dict):
                for field_name in field_names:
                    value = raw_metadata.get(field_name)
                    if value not in (None, ""):
                        return value

            return None

        for field_name in field_names:
            try:
                value = getattr(paper, field_name, None)
                if value not in (None, ""):
                    return value
            except Exception:
                pass

        try:
            raw_metadata = getattr(paper, "raw_metadata", None)
            if isinstance(raw_metadata, dict):
                for field_name in field_names:
                    value = raw_metadata.get(field_name)
                    if value not in (None, ""):
                        return value
        except Exception:
            pass

        return None

    @staticmethod
    def _normalize_text(text: str) -> str:
        """Normalize text for matching while preserving semantic tokens."""

        if not text:
            return ""

        text = unicodedata.normalize(
            "NFKC",
            str(text)
        ).lower()

        # Make hyphenated benchmark names searchable in both forms.
        text = text.replace("–", "-").replace("—", "-")
        text = re.sub(r"[^a-z0-9%+.#-]+", " ", text)
        text = re.sub(r"\s+", " ", text).strip()
        return text

    @classmethod
    def _tokenize(cls, text: str) -> List[str]:
        """Tokenize normalized text, retaining benchmark/model tokens."""

        normalized = cls._normalize_text(text)
        if not normalized:
            return []

        return [
            token
            for token in re.findall(r"[a-z0-9]+(?:-[a-z0-9]+)*", normalized)
            if token not in _STOPWORDS
        ]

    # ========================================================
    # ID / TITLE HELPERS
    # ========================================================

    @staticmethod
    def _get_primary_id(
        paper: PaperLike
    ) -> str:
        """
        Safely obtain a primary identifier from either a
        StandardPaper object or a legacy dictionary.
        """

        # Current StandardPaper contract
        if hasattr(
            paper,
            "get_primary_id"
        ):

            try:

                return str(
                    paper.get_primary_id()
                    or ""
                ).strip()

            except Exception:
                pass

        # Legacy / defensive dictionary support
        if isinstance(
            paper,
            dict
        ):

            for key in (
                "arxiv_id",
                "doi",
                "semantic_scholar_id",
                "id",
            ):

                value = paper.get(
                    key
                )

                if value:

                    return str(
                        value
                    ).strip()

        # Final attribute fallback for legacy objects.
        for key in (
            "arxiv_id",
            "doi",
            "semantic_scholar_id",
            "id",
        ):
            try:
                value = getattr(paper, key, None)
                if value:
                    return str(value).strip()
            except Exception:
                pass

        return ""

    @classmethod
    def _get_title(cls, paper: PaperLike) -> str:
        value = cls._get_field(
            paper,
            "title",
            "paper_title",
        )
        return str(value or "").strip()

    @classmethod
    def _get_abstract(cls, paper: PaperLike) -> str:
        value = cls._get_field(
            paper,
            "abstract",
            "summary",
            "description",
            "text",
        )
        return str(value or "").strip()

    @classmethod
    def _get_source(cls, paper: PaperLike) -> str:
        value = cls._get_field(
            paper,
            "source",
            "venue",
            "database",
        )
        return str(value or "Unknown").strip()

    @classmethod
    def _normalized_title(cls, paper: PaperLike) -> str:
        title = cls._get_title(paper)
        normalized = cls._normalize_text(title)
        normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
        return re.sub(r"\s+", " ", normalized).strip()

    @classmethod
    def _dedupe_keys(cls, paper: PaperLike) -> List[str]:
        """
        Build several stable keys so the same paper returned by different
        sources is not processed multiple times.
        """

        keys = []

        data = cls._paper_to_dict(paper)

        for field_name in (
            "arxiv_id",
            "doi",
            "semantic_scholar_id",
            "id",
        ):
            value = data.get(field_name)
            if value:
                cleaned = cls._normalize_text(str(value))
                if cleaned:
                    keys.append(f"id:{cleaned}")

        primary_id = cls._get_primary_id(paper)
        if primary_id:
            cleaned = cls._normalize_text(primary_id)
            if cleaned:
                keys.append(f"primary:{cleaned}")

        title = cls._normalized_title(paper)
        if len(title) >= 12:
            keys.append(f"title:{title}")

        return list(dict.fromkeys(keys))

    # ========================================================
    # SERIALIZATION
    # ========================================================

    @staticmethod
    def _paper_to_dict(
        paper: PaperLike
    ) -> dict:
        """
        Convert a paper object to a normal dictionary for
        persistence / API serialization.
        """

        if isinstance(
            paper,
            dict
        ):

            return dict(
                paper
            )

        if hasattr(
            paper,
            "model_dump"
        ):

            try:
                return paper.model_dump()
            except Exception:
                pass

        if hasattr(
            paper,
            "dict"
        ):

            try:
                return paper.dict()
            except Exception:
                pass

        if hasattr(
            paper,
            "to_dict"
        ):

            try:
                return paper.to_dict()
            except Exception:
                pass

        if hasattr(
            paper,
            "__dict__"
        ):

            try:
                return dict(
                    paper.__dict__
                )
            except Exception:
                pass

        return {}

    # ========================================================
    # QUERY RELEVANCE SCORING
    # ========================================================

    @classmethod
    def _contains_exact_phrase(
        cls,
        text: str,
        phrase: str
    ) -> bool:
        """
        Check whether a phrase/token occurs as a complete lexical unit.

        IMPORTANT:
        A benchmark such as ``MMLU`` must NOT match:
            MMLU-Pro
            Mobile-MMLU
            Video-MMLU

        The previous implementation used substring matching, which caused
        ``MMLU`` to match every benchmark variant containing that text.
        """
        normalized_text = cls._normalize_text(text)
        normalized_phrase = cls._normalize_text(phrase)

        if not normalized_text or not normalized_phrase:
            return False

        pattern = re.compile(
            rf"(?<![a-z0-9-])"
            rf"{re.escape(normalized_phrase)}"
            rf"(?![a-z0-9-])",
            flags=re.IGNORECASE
        )

        return bool(
            pattern.search(normalized_text)
        )

    @classmethod
    def _find_query_benchmark_targets(
        cls,
        query: str
    ) -> List[str]:
        """
        Return benchmark families explicitly named in the user query.

        Longer names are checked first so:
            MMLU-Pro
        is never interpreted as:
            MMLU

        Only exact lexical matches are returned.
        """
        normalized_query = cls._normalize_text(
            query
        )

        if not normalized_query:
            return []

        matches = []

        for pattern in sorted(
            _BENCHMARK_FAMILY_PATTERNS,
            key=lambda value: len(str(value)),
            reverse=True
        ):
            if cls._contains_exact_phrase(
                normalized_query,
                pattern
            ):
                matches.append(
                    pattern
                )

        return list(
            dict.fromkeys(matches)
        )

    @classmethod
    def _benchmark_matches(
        cls,
        query: str,
        paper_text: str
    ) -> List[str]:
        """
        Return benchmark names that appear EXACTLY in both the query and
        paper metadata.

        This deliberately does not use substring matching.
        """
        query_targets = cls._find_query_benchmark_targets(
            query
        )

        normalized_paper = cls._normalize_text(
            paper_text
        )

        matches = []

        for target in query_targets:
            if cls._contains_exact_phrase(
                normalized_paper,
                target
            ):
                matches.append(
                    target
                )

        return matches

    @classmethod
    def _related_benchmark_variants(
        cls,
        query: str,
        paper_text: str
    ) -> List[str]:
        """
        Return benchmark-family variants present in the paper when the query
        names a related benchmark.

        Variants are intentionally treated as secondary evidence rather than
        exact matches.
        """
        query_targets = {
            target.lower()
            for target in cls._find_query_benchmark_targets(
                query
            )
        }

        if not query_targets:
            return []

        normalized_paper = cls._normalize_text(
            paper_text
        )

        matched = []

        for candidate in sorted(
            _BENCHMARK_FAMILY_PATTERNS,
            key=lambda value: len(str(value)),
            reverse=True
        ):
            if candidate.lower() in query_targets:
                continue

            if cls._contains_exact_phrase(
                normalized_paper,
                candidate
            ):
                matched.append(
                    candidate
                )

        return list(
            dict.fromkeys(matched)
        )

    @classmethod
    def _paper_supports_query_benchmark(
        cls,
        query: str,
        paper: PaperLike
    ) -> bool:
        """
        Determine whether a paper's title/abstract contains at least one
        exact benchmark explicitly requested by the user.

        A paper explicitly centered on a related benchmark variant is treated
        as a variant even when its abstract also mentions the base benchmark.
        This distinction is used for ranking/selection when the query names a
        benchmark.
        """
        targets = cls._find_query_benchmark_targets(
            query
        )

        if not targets:
            return True

        title = cls._get_title(paper)
        abstract = cls._get_abstract(paper)
        metadata_text = " ".join(
            value
            for value in (title, abstract)
            if value
        )

        # A title that explicitly names a benchmark variant takes precedence
        # over a generic mention of the base benchmark in the abstract.
        # Example: a Video-MMLU paper may mention the original MMLU dataset,
        # but it is still a Video-MMLU paper for retrieval purposes.
        title_variant_hits = []
        for candidate in _BENCHMARK_FAMILY_PATTERNS:
            if candidate.lower() in {
                target.lower() for target in targets
            }:
                continue
            if cls._contains_exact_phrase(title, candidate):
                title_variant_hits.append(candidate)

        if title_variant_hits:
            return False

        return any(
            cls._contains_exact_phrase(
                metadata_text,
                target
            )
            for target in targets
        )

    @classmethod
    def _calculate_relevance(
        cls,
        query: str,
        paper: PaperLike
    ) -> Tuple[float, List[str]]:
        """
        Calculate a transparent lexical relevance score.

        When the query explicitly names a benchmark:
            - exact benchmark support receives a strong boost;
            - benchmark variants receive only a small secondary boost;
            - final selection can use exact-benchmark support as a hard gate.

        This prevents a query for MMLU from ranking MMLU-Pro, Mobile-MMLU,
        or Video-MMLU as though they were the exact requested benchmark.
        """

        title = cls._get_title(
            paper
        )
        abstract = cls._get_abstract(
            paper
        )

        query_normalized = cls._normalize_text(
            query
        )
        title_normalized = cls._normalize_text(
            title
        )
        abstract_normalized = cls._normalize_text(
            abstract
        )

        query_tokens = set(
            cls._tokenize(
                query_normalized
            )
        )
        title_tokens = set(
            cls._tokenize(
                title_normalized
            )
        )
        abstract_tokens = set(
            cls._tokenize(
                abstract_normalized
            )
        )

        score = 0.0
        reasons = []

        # ----------------------------------------------------
        # Token overlap
        # ----------------------------------------------------

        title_overlap = (
            query_tokens
            & title_tokens
        )
        abstract_overlap = (
            query_tokens
            & abstract_tokens
        )

        if title_overlap:
            score += 3.0 * len(
                title_overlap
            )
            reasons.append(
                "title terms: "
                + ", ".join(
                    sorted(
                        title_overlap
                    )
                )
            )

        if abstract_overlap:
            score += min(
                0.75 * len(
                    abstract_overlap
                ),
                4.5
            )
            reasons.append(
                "abstract terms: "
                + ", ".join(
                    sorted(
                        abstract_overlap
                    )
                )
            )

        # ----------------------------------------------------
        # Exact full-query phrase
        # ----------------------------------------------------

        if cls._contains_exact_phrase(
            query_normalized,
            title_normalized
        ):
            score += 10.0
            reasons.append(
                "exact query phrase in title"
            )

        elif len(
            query_normalized
        ) >= 8 and cls._contains_exact_phrase(
            title_normalized,
            query_normalized
        ):
            score += 10.0
            reasons.append(
                "exact query phrase in title"
            )

        # ----------------------------------------------------
        # Exact benchmark intent
        # ----------------------------------------------------

        query_targets = cls._find_query_benchmark_targets(
            query_normalized
        )

        combined_paper_text = " ".join(
            value
            for value in (
                title_normalized,
                abstract_normalized,
            )
            if value
        )

        exact_benchmark_matches = (
            cls._benchmark_matches(
                query_normalized,
                combined_paper_text
            )
        )

        variant_matches = (
            cls._related_benchmark_variants(
                query_normalized,
                combined_paper_text
            )
        )

        if query_targets:
            if exact_benchmark_matches:
                title_exact_targets = [
                    target
                    for target in exact_benchmark_matches
                    if cls._contains_exact_phrase(
                        title_normalized,
                        target
                    )
                ]

                abstract_exact_targets = [
                    target
                    for target in exact_benchmark_matches
                    if cls._contains_exact_phrase(
                        abstract_normalized,
                        target
                    )
                ]

                if title_exact_targets:
                    score += 12.0
                    reasons.append(
                        "exact requested benchmark in title: "
                        + ", ".join(
                            title_exact_targets
                        )
                    )

                elif abstract_exact_targets:
                    score += 7.0
                    reasons.append(
                        "exact requested benchmark in abstract: "
                        + ", ".join(
                            abstract_exact_targets
                        )
                    )

                else:
                    score += 5.0
                    reasons.append(
                        "exact requested benchmark in metadata: "
                        + ", ".join(
                            exact_benchmark_matches
                        )
                    )

            if variant_matches:
                # Variants are useful recall signals, but must never receive
                # the same boost as the exact requested benchmark.
                score += min(
                    0.75 * len(
                        variant_matches
                    ),
                    1.5
                )
                reasons.append(
                    "related benchmark variants: "
                    + ", ".join(
                        variant_matches
                    )
                )

        else:
            # Backward-compatible family matching when the query does not
            # explicitly identify a benchmark target.
            family_matches = []

            for pattern in _BENCHMARK_FAMILY_PATTERNS:
                if cls._contains_exact_phrase(
                    combined_paper_text,
                    pattern
                ):
                    family_matches.append(
                        pattern
                    )

            if family_matches:
                score += 6.0
                reasons.append(
                    "benchmark family matches: "
                    + ", ".join(
                        family_matches
                    )
                )

        # ----------------------------------------------------
        # Evaluation-language boost
        # ----------------------------------------------------

        evaluation_overlap = (
            set(
                cls._tokenize(
                    query_normalized
                )
            )
            & _EVALUATION_TERMS
            & set(
                cls._tokenize(
                    title_normalized
                    + " "
                    + abstract_normalized
                )
            )
        )

        if evaluation_overlap:
            score += min(
                0.5 * len(
                    evaluation_overlap
                ),
                1.5
            )
            reasons.append(
                "evaluation terms: "
                + ", ".join(
                    sorted(
                        evaluation_overlap
                    )
                )
            )

        # ----------------------------------------------------
        # Direct title benchmark presence
        # ----------------------------------------------------

        title_benchmark_hits = []

        if query_targets:
            title_benchmark_hits = [
                target
                for target in query_targets
                if cls._contains_exact_phrase(
                    title_normalized,
                    target
                )
            ]
        else:
            title_benchmark_hits = [
                pattern
                for pattern in _BENCHMARK_FAMILY_PATTERNS
                if cls._contains_exact_phrase(
                    title_normalized,
                    pattern
                )
            ]

        if title_benchmark_hits:
            score += 4.0
            reasons.append(
                "benchmark in title: "
                + ", ".join(
                    title_benchmark_hits
                )
            )

        # ----------------------------------------------------
        # Related benchmark variant title signal
        # ----------------------------------------------------

        if query_targets and variant_matches:
            title_variant_hits = [
                variant
                for variant in variant_matches
                if cls._contains_exact_phrase(
                    title_normalized,
                    variant
                )
            ]

            if title_variant_hits:
                score += 3.0
                reasons.append(
                    "related benchmark variant in title: "
                    + ", ".join(title_variant_hits)
                )

        # ----------------------------------------------------
        # Penalize variant-only matches for explicit benchmark queries.
        # ----------------------------------------------------

        if (
            query_targets
            and not exact_benchmark_matches
            and variant_matches
        ):
            score -= 1.5
            reasons.append(
                "variant-only benchmark match lightly penalized"
            )

        # ----------------------------------------------------
        # Missing metadata
        # ----------------------------------------------------

        if not title and not abstract:
            score = 0.0
            reasons = [
                "no title/abstract metadata"
            ]

        return round(
            max(score, 0.0),
            3
        ), reasons

    @classmethod
    def _attach_relevance_metadata(
        cls,
        paper: PaperLike,
        score: float,
        reasons: List[str]
    ) -> None:
        """Attach diagnostics when the paper object supports raw_metadata."""

        metadata = {
            "retrieval_relevance_score": score,
            "retrieval_relevance_reasons": reasons,
        }

        if isinstance(paper, dict):
            existing = paper.get("raw_metadata")
            if not isinstance(existing, dict):
                existing = {}
                paper["raw_metadata"] = existing
            existing.update(metadata)
            return

        try:
            existing = getattr(paper, "raw_metadata", None)
            if isinstance(existing, dict):
                existing.update(metadata)
                return
        except Exception:
            pass

        # Do not fail retrieval just because the schema does not allow
        # arbitrary metadata assignment.
        try:
            setattr(
                paper,
                "retrieval_relevance_score",
                score
            )
            setattr(
                paper,
                "retrieval_relevance_reasons",
                reasons
            )
        except Exception:
            pass

    # ========================================================
    # SEARCH ALL SOURCES
    # ========================================================

    def search_all_sources(
        self,
        query: str,
        max_results: int = 10
    ) -> List[PaperLike]:
        """
        Search arXiv, Semantic Scholar, and CrossRef.

        `max_results` is the final number of ranked papers returned. Each
        source is asked for up to `max_results` candidates first; the combined
        set is then deduplicated and relevance-ranked.
        """

        query = str(query or "").strip()
        max_results = max(
            1,
            int(max_results or 1)
        )

        all_papers: List[PaperLike] = []
        seen_keys = set()

        print(
            f"Searching all sources for: {query}"
        )

        # Use the user's full query first, then add a benchmark-focused
        # retrieval query when the user explicitly named a benchmark.
        # This improves recall when source ranking pushes the benchmark's
        # canonical paper below many newer benchmark-variant papers.
        query_benchmark_targets = self._find_query_benchmark_targets(query)
        retrieval_queries = [query]

        for target in query_benchmark_targets:
            benchmark_query = (
                f"{target} benchmark large language model evaluation"
            )
            if benchmark_query.lower() != query.lower():
                retrieval_queries.append(benchmark_query)

        print(
            "Retrieval queries: "
            + " | ".join(retrieval_queries)
        )

        def add_papers(
            source_papers: List[PaperLike],
            source_name: str
        ) -> None:
            """Add papers with cross-source deduplication."""

            added = 0

            for paper in source_papers or []:

                keys = self._dedupe_keys(paper)

                if not keys:
                    continue

                if any(
                    key in seen_keys
                    for key in keys
                ):
                    continue

                for key in keys:
                    seen_keys.add(key)

                # Keep source information useful even when the source object
                # itself does not expose a source field.
                if not self._get_source(paper) or self._get_source(paper) == "Unknown":
                    if isinstance(paper, dict):
                        paper.setdefault("source", source_name)

                all_papers.append(paper)
                added += 1

            print(
                f"  → Added {added} unique papers from {source_name}"
            )

        # ----------------------------------------------------
        # STEP 1: arXiv
        # ----------------------------------------------------

        print(
            "\n[1/3] Searching arXiv..."
        )

        try:

            total_found = 0
            for retrieval_query in retrieval_queries:
                arxiv_papers = self.arxiv_retriever.search_arxiv(
                    retrieval_query,
                    max_results
                )
                total_found += len(arxiv_papers or [])
                add_papers(
                    arxiv_papers,
                    "arXiv"
                )

            print(
                f"  → Found {total_found} candidate rows "
                "across arXiv retrieval queries"
            )

        except Exception as error:

            print(
                "  → arXiv search failed: "
                f"{error}"
            )

        # ----------------------------------------------------
        # STEP 2: Semantic Scholar
        # ----------------------------------------------------

        print(
            "\n[2/3] Searching Semantic Scholar..."
        )

        try:

            total_found = 0
            for retrieval_query in retrieval_queries:
                semantic_papers = (
                    self.semantic_retriever
                    .search_semantic_scholar(
                        retrieval_query,
                        max_results
                    )
                )
                total_found += len(semantic_papers or [])
                add_papers(
                    semantic_papers,
                    "Semantic Scholar"
                )

            print(
                f"  → Found {total_found} candidate rows "
                "across Semantic Scholar retrieval queries"
            )

        except Exception as error:

            print(
                "  → Semantic Scholar search "
                f"failed: {error}"
            )

        # ----------------------------------------------------
        # STEP 3: CrossRef
        # ----------------------------------------------------

        print(
            "\n[3/3] Searching CrossRef..."
        )

        try:

            total_found = 0
            for retrieval_query in retrieval_queries:
                crossref_papers = (
                    self.crossref_retriever
                    .search_crossref(
                        retrieval_query,
                        max_results
                    )
                )
                total_found += len(crossref_papers or [])
                add_papers(
                    crossref_papers,
                    "CrossRef"
                )

            print(
                f"  → Found {total_found} candidate rows "
                "across CrossRef retrieval queries"
            )

        except Exception as error:

            print(
                "  → CrossRef search "
                f"failed: {error}"
            )

        # ----------------------------------------------------
        # FINAL DEDUPLICATION / RELEVANCE RANKING
        # ----------------------------------------------------

        print(
            "\n============================================================"
        )
        print(
            "RETRIEVAL RELEVANCE RANKING"
        )
        print(
            "============================================================"
        )

        scored_papers = []

        for paper in all_papers:

            score, reasons = self._calculate_relevance(
                query,
                paper
            )

            self._attach_relevance_metadata(
                paper,
                score,
                reasons
            )

            scored_papers.append(
                (
                    score,
                    reasons,
                    paper
                )
            )

        scored_papers.sort(
            key=lambda item: (
                item[0],
                self._get_title(item[2]).lower()
            ),
            reverse=True
        )

        print(
            f"Raw unique candidates before relevance filtering: "
            f"{len(scored_papers)}"
        )

        for rank, (score, reasons, paper) in enumerate(
            scored_papers,
            start=1
        ):

            title = self._get_title(paper) or "Untitled"
            source = self._get_source(paper) or "Unknown"

            reason_text = "; ".join(reasons[:3])

            print(
                f"  {rank:02d}. score={score:6.2f} | "
                f"{source:16s} | {title}"
            )

            if reason_text:
                print(
                    f"      ↳ {reason_text}"
                )

        # ----------------------------------------------------
        # Relevance filtering
        # ----------------------------------------------------

        threshold_relevant = [
            item
            for item in scored_papers
            if item[0] >= MIN_RELEVANCE_SCORE
        ]

        query_benchmark_targets = (
            self._find_query_benchmark_targets(
                query
            )
        )

        if query_benchmark_targets:
            exact_benchmark_candidates = [
                item
                for item in scored_papers
                if (
                    item[0] >= EXPLICIT_BENCHMARK_MIN_SCORE
                    and self._paper_supports_query_benchmark(
                        query,
                        item[2]
                    )
                )
            ]

            variant_candidates = []
            for item in scored_papers:
                score, _, paper = item
                if score < RELATED_VARIANT_MIN_SCORE:
                    continue

                title = self._get_title(paper)
                abstract = self._get_abstract(paper)
                metadata_text = " ".join(
                    value
                    for value in (title, abstract)
                    if value
                )

                # Include a paper as a related variant only when the metadata
                # contains a benchmark variant, but not an exact requested
                # benchmark occurrence.
                has_exact = self._paper_supports_query_benchmark(
                    query,
                    paper
                )
                has_variant = bool(
                    self._related_benchmark_variants(
                        query,
                        metadata_text
                    )
                )

                if has_variant and not has_exact:
                    variant_candidates.append(item)

            # Exact benchmark papers always come first. Related variants may
            # fill the remaining slots so retrieval preserves useful recall
            # without treating variants as exact matches.
            selected_pool = []
            selected_keys = set()

            for item in exact_benchmark_candidates:
                key = self._normalized_title(item[2])
                if key not in selected_keys:
                    selected_pool.append(item)
                    selected_keys.add(key)

            for item in variant_candidates:
                if len(selected_pool) >= max_results:
                    break
                key = self._normalized_title(item[2])
                if key not in selected_keys:
                    selected_pool.append(item)
                    selected_keys.add(key)

            # If neither exact nor variant-specific candidates exist, retain
            # the prior threshold behavior as an honest metadata-only fallback.
            if not selected_pool:
                relevant = threshold_relevant
                fallback_minimum = min(
                    MIN_FALLBACK_RESULTS,
                    max_results
                )
                if len(relevant) < fallback_minimum:
                    selected_pool = scored_papers[
                        :max(
                            fallback_minimum,
                            len(relevant)
                        )
                    ]
                    filter_mode = (
                        "fallback-to-top-ranked"
                        "(no-exact-or-variant)"
                    )
                else:
                    selected_pool = relevant
                    filter_mode = (
                        "threshold"
                        "(no-exact-or-variant)"
                    )
            elif variant_candidates:
                filter_mode = "exact-plus-related-variants"
            else:
                filter_mode = "exact-benchmark"

            relevant = exact_benchmark_candidates + variant_candidates
        else:
            relevant = threshold_relevant
            fallback_minimum = min(
                MIN_FALLBACK_RESULTS,
                max_results
            )

            if len(relevant) < fallback_minimum:
                selected_pool = scored_papers[
                    :max(
                        fallback_minimum,
                        len(relevant)
                    )
                ]
                filter_mode = "fallback-to-top-ranked"
            else:
                selected_pool = relevant
                filter_mode = "threshold"

        print(
            f"\nQuery benchmark targets: "
            f"{query_benchmark_targets or 'none'}"
        )

        if query_benchmark_targets:
            print(
                f"Exact benchmark candidates: "
                f"{len(exact_benchmark_candidates)}"
            )
            print(
                f"Related variant candidates: "
                f"{len(variant_candidates)}"
            )
        final_scored = selected_pool[:max_results]

        final_papers = [
            paper
            for _, _, paper in final_scored
        ]

        print(
            f"\nQuery benchmark targets: "
            f"{query_benchmark_targets or 'none'}"
        )

        if query_benchmark_targets:
            print(
                "Exact-benchmark candidates: "
                f"{sum(1 for item in scored_papers if self._paper_supports_query_benchmark(query, item[2]))}"
            )

        print(
            f"Relevance filter mode: {filter_mode}"
        )

        print(
            f"Relevant candidates: {len(relevant)}"
        )

        print(
            f"Final papers returned: {len(final_papers)}"
        )

        if relevant and len(relevant) > max_results:
            print(
                f"Top {max_results} relevant papers selected for downstream processing."
            )

        print(
            "\n✅ Total unique relevant papers returned: "
            f"{len(final_papers)}"
        )

        return final_papers

    # ========================================================
    # GET PAPER BY ARXIV ID
    # ========================================================

    def get_paper_by_arxiv_id(
        self,
        arxiv_id: str
    ) -> Optional[PaperLike]:

        try:

            papers = (
                self.arxiv_retriever
                .search_arxiv(
                    arxiv_id,
                    max_results=1
                )
            )

            if papers:
                return papers[0]

        except Exception:
            pass

        try:

            return (
                self.semantic_retriever
                .get_paper_by_arxiv_id(
                    arxiv_id
                )
            )

        except Exception:
            return None

    # ========================================================
    # GET PAPER BY DOI
    # ========================================================

    def get_paper_by_doi(
        self,
        doi: str
    ) -> Optional[PaperLike]:

        try:

            return (
                self.crossref_retriever
                .search_by_doi(
                    doi
                )
            )

        except Exception:
            return None

    # ========================================================
    # SAVE PAPERS
    # ========================================================

    def save_papers_to_json(
        self,
        papers: List[PaperLike],
        filename: Optional[str] = None
    ):
        """
        Save papers safely to JSON.

        Default location:
            retrievers/data/papers.json
        """

        if filename is None:

            filename = os.path.join(
                os.path.dirname(
                    os.path.abspath(__file__)
                ),
                "data",
                "papers.json"
            )

        try:

            os.makedirs(
                os.path.dirname(
                    os.path.abspath(filename)
                ),
                exist_ok=True
            )

            paper_dicts = [
                self._paper_to_dict(
                    paper
                )
                for paper in papers
            ]

            with open(
                filename,
                "w",
                encoding="utf-8"
            ) as file:

                json.dump(
                    paper_dicts,
                    file,
                    indent=2,
                    ensure_ascii=False,
                    default=str,
                )

            print(
                f"✅ Saved {len(paper_dicts)} "
                f"papers to {filename}"
            )

        except Exception as error:

            print(
                "❌ Error saving papers: "
                f"{error}"
            )

    # ========================================================
    # LOAD PAPERS
    # ========================================================

    def load_papers_from_json(
        self,
        filename: Optional[str] = None
    ) -> List[Dict]:

        if filename is None:

            filename = os.path.join(
                os.path.dirname(
                    os.path.abspath(__file__)
                ),
                "data",
                "papers.json"
            )

        try:

            with open(
                filename,
                "r",
                encoding="utf-8"
            ) as file:

                papers = json.load(
                    file
                )

            print(
                f"✅ Loaded {len(papers)} "
                f"papers from {filename}"
            )

            return papers

        except Exception as error:

            print(
                "❌ Error loading papers: "
                f"{error}"
            )

            return []


# ============================================================
# DIRECT TEST
# ============================================================

if __name__ == "__main__":

    retriever = (
        UnifiedPaperRetriever()
    )

    papers = (
        retriever.search_all_sources(
            "MMLU large language model benchmark evaluation results",
            max_results=5
        )
    )

    retriever.save_papers_to_json(
        papers
    )
