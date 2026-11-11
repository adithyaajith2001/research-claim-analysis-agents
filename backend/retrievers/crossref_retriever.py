"""
CrossRef Paper Retriever
Author: Adithya Ajith
Retrieves papers from CrossRef API (citations and DOI data)
"""

import requests
from typing import List, Dict, Optional
from datetime import datetime

from paper_schema import StandardPaper


class CrossRefRetriever:
    """Retrieves research papers from CrossRef API"""

    def __init__(self):
        self.base_url = "https://api.crossref.org/v1/works"

        self.headers = {
            "User-Agent": (
                "ResearchClaimAnalyzer/1.0 "
                "(contact: adithya@christ.edu.in)"
            )
        }

    def _parse_single_paper(
        self,
        paper_data: Dict
    ) -> Optional[StandardPaper]:
        """
        Parse a single CrossRef paper into StandardPaper schema.
        """

        try:

            # =========================================
            # FILTER OUT NON-PAPER CROSSREF RECORDS
            # =========================================
            # CrossRef registers individual tables/figures as their own
            # DOIs (type "component"), which show up in search results
            # looking like papers - e.g. "Table 5: Comparison of accuracy
            # results...". They have no abstract and their "PDF" link is
            # really an HTML page, so every one of them wastes a
            # retrieval slot and a doomed download attempt downstream.
            # Reject them here instead of after spending an HTTP request
            # trying to download them as a PDF.
            crossref_type = paper_data.get("type", "")

            if crossref_type == "component":
                return None

            title_parts = paper_data.get("title", [])
            title_preview = (
                "".join(title_parts).strip().lower()
                if title_parts
                else ""
            )

            caption_prefixes = ("table ", "table:", "figure ", "figure:", "fig. ", "fig ")

            if title_preview.startswith(caption_prefixes):
                return None

            # =========================================
            # AUTHORS
            # =========================================

            authors = []

            for author in paper_data.get(
                "author",
                []
            ):

                name = (
                    f"{author.get('given', '')} "
                    f"{author.get('family', '')}"
                ).strip()

                if name:
                    authors.append(name)

            # =========================================
            # DOI
            # =========================================

            doi = paper_data.get(
                "DOI",
                ""
            )

            # =========================================
            # PUBLISHED DATE
            # =========================================

            published_date = None
            year = None

            date_parts = (
                paper_data
                .get("issued", {})
                .get("date-parts")
            )

            if date_parts:

                date_parts = date_parts[0]

                if date_parts:

                    # Year
                    year = date_parts[0]

                    # Full date if available
                    if len(date_parts) >= 3:

                        published_date = (
                            f"{date_parts[0]}-"
                            f"{date_parts[1]:02d}-"
                            f"{date_parts[2]:02d}"
                        )

                    # Year + month
                    elif len(date_parts) >= 2:

                        published_date = (
                            f"{date_parts[0]}-"
                            f"{date_parts[1]:02d}"
                        )

                    # Year only
                    else:

                        published_date = str(
                            date_parts[0]
                        )

            # =========================================
            # JOURNAL / VENUE
            # =========================================

            journal = ""

            if paper_data.get("container-title"):

                journal = (
                    paper_data["container-title"][0]
                )

            # =========================================
            # TITLE
            # =========================================

            title = "".join(
                paper_data.get(
                    "title",
                    []
                )
            )

            # =========================================
            # ABSTRACT
            # =========================================

            abstract = paper_data.get(
                "abstract",
                ""
            )

            # =========================================
            # URL
            # =========================================

            url = paper_data.get(
                "URL",
                ""
            )

            # =========================================
            # CREATE STANDARD PAPER
            # =========================================

            paper = StandardPaper(

                doi=doi or None,

                title=title,

                authors=authors,

                abstract=abstract,

                year=year,

                journal=journal,

                volume=paper_data.get(
                    "volume",
                    ""
                ),

                issue=paper_data.get(
                    "issue",
                    ""
                ),

                pages=paper_data.get(
                    "page",
                    ""
                ),

                url=url,

                citation_count=paper_data.get(
                    "is-referenced-by-count",
                    0
                ),

                reference_count=paper_data.get(
                    "references-count",
                    0
                ),

                source="CrossRef",

                # Actual time our system retrieved
                # the paper
                retrieved_at=datetime.now().isoformat(),

                # Store original CrossRef metadata
                raw_metadata={
                    "published_date": published_date,
                    "crossref_data": paper_data
                }
            )

            return paper

        except Exception as e:

            print(
                f"Error parsing CrossRef paper: {str(e)}"
            )

            return None

    def search_crossref(
        self,
        query: str,
        max_results: int = 10
    ) -> List[StandardPaper]:
        """
        Search CrossRef for papers by title/query.

        Args:
            query: Search term
            max_results: Number of results

        Returns:
            List of StandardPaper objects
        """

        try:

            # =========================================
            # SEARCH PARAMETERS
            # =========================================

            params = {
                "query": query,
                "rows": min(max_results, 1000),
                "sort": "relevance",
                "order": "desc"
            }

            print(
                f"Searching CrossRef for: '{query}'..."
            )

            # =========================================
            # API REQUEST
            # =========================================

            response = requests.get(
                self.base_url,
                params=params,
                headers=self.headers,
                timeout=10
            )

            response.raise_for_status()

            # =========================================
            # PARSE RESPONSE
            # =========================================

            data = response.json()

            papers = []

            items = (
                data
                .get("message", {})
                .get("items", [])
            )

            print(
                f"Found {len(items)} papers on CrossRef."
            )

            # =========================================
            # PARSE EACH PAPER
            # =========================================

            filtered_count = 0

            for paper_data in items:

                paper = self._parse_single_paper(
                    paper_data
                )

                if paper is not None:
                    papers.append(paper)
                else:
                    filtered_count += 1

            if filtered_count:
                print(
                    f"  [info] CrossRef: filtered out {filtered_count} "
                    "non-paper record(s) (table/figure captions, etc.)"
                )

            return papers

        except requests.RequestException as e:

            print(
                f"Error searching CrossRef: {str(e)}"
            )

            return []

        except Exception as e:

            print(
                f"Unexpected CrossRef error: {str(e)}"
            )

            return []

    def search_by_doi(
        self,
        doi: str
    ) -> Optional[StandardPaper]:
        """
        Get paper information by DOI.
        """

        try:

            # =========================================
            # NORMALIZE DOI
            # =========================================

            doi = doi.strip()

            if doi.startswith(
                "https://doi.org/"
            ):

                doi = doi.replace(
                    "https://doi.org/",
                    "",
                    1
                )

            elif doi.startswith(
                "http://doi.org/"
            ):

                doi = doi.replace(
                    "http://doi.org/",
                    "",
                    1
                )

            elif doi.startswith(
                "https://dx.doi.org/"
            ):

                doi = doi.replace(
                    "https://dx.doi.org/",
                    "",
                    1
                )

            # =========================================
            # BUILD URL
            # =========================================

            url = (
                f"{self.base_url}/{doi}"
            )

            # =========================================
            # API REQUEST
            # =========================================

            response = requests.get(
                url,
                headers=self.headers,
                timeout=10
            )

            response.raise_for_status()

            # =========================================
            # PARSE RESPONSE
            # =========================================

            data = response.json()

            paper_data = data.get(
                "message",
                {}
            )

            # =========================================
            # CONVERT TO STANDARD PAPER
            # =========================================

            return self._parse_single_paper(
                paper_data
            )

        except requests.RequestException as e:

            print(
                f"Error getting paper by DOI "
                f"{doi}: {str(e)}"
            )

            return None

        except Exception as e:

            print(
                f"Error getting paper by DOI "
                f"{doi}: {str(e)}"
            )

            return None


# ============================================================
# TESTING
# ============================================================

if __name__ == "__main__":

    retriever = CrossRefRetriever()

    # =========================================
    # TEST SEARCH
    # =========================================

    query = "transformers"

    papers = retriever.search_crossref(
        query,
        max_results=3
    )

    print(
        f"\n✓ Retrieved {len(papers)} papers:\n"
    )

    for paper in papers:

        # Pydantic v2
        if hasattr(
            paper,
            "model_dump"
        ):

            paper_data = paper.model_dump()

        # Pydantic v1
        elif hasattr(
            paper,
            "dict"
        ):

            paper_data = paper.dict()

        else:

            paper_data = paper.__dict__

        print(
            f"Title: {paper_data.get('title', '')}"
        )

        print(
            f"Authors: "
            f"{', '.join(paper_data.get('authors', []))}"
        )

        print(
            f"DOI: {paper_data.get('doi', '')}"
        )

        print(
            f"Year: {paper_data.get('year', '')}"
        )

        print(
            f"Journal: {paper_data.get('journal', '')}"
        )

        print(
            f"Citations: "
            f"{paper_data.get('citation_count', 0)}"
        )

        print(
            f"References: "
            f"{paper_data.get('reference_count', 0)}"
        )

        print(
            f"URL: {paper_data.get('url', '')}"
        )

        raw_metadata = paper_data.get(
            "raw_metadata",
            {}
        )

        print(
            f"Published: "
            f"{raw_metadata.get('published_date', '')}"
        )

        print(
            f"Retrieved: "
            f"{paper_data.get('retrieved_at', '')}"
        )

        print(
            f"Source: {paper_data.get('source', '')}"
        )

        print("---")