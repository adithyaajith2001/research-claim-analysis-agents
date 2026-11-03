"""
Semantic Scholar Paper Retriever
Author: Adithya Ajith
Retrieves papers from Semantic Scholar API (academic metadata)

PATCHED by Malavika: now returns StandardPaper objects, matching
arxiv_retriever.py and crossref_retriever.py, so unified_retriever.py can
treat all three sources uniformly (get_primary_id(), .to_dict(), etc.)
instead of crashing on a mixed list of dataclasses and dicts.
"""

import requests
from typing import List, Dict, Optional
from datetime import datetime

from paper_schema import StandardPaper


class SemanticScholarRetriever:
    """Retrieves research papers from Semantic Scholar API"""

    def __init__(self):
        self.base_url = "https://api.semanticscholar.org/graph/v1/paper/search"
        self.papers_url = "https://api.semanticscholar.org/graph/v1/paper"

    def _parse_single_paper(self, paper_data: Dict) -> Optional[StandardPaper]:
        """Parse one Semantic Scholar paper into StandardPaper schema."""
        try:
            authors = []
            for author in paper_data.get('authors', []):
                if isinstance(author, dict):
                    authors.append(author.get('name', ''))
                else:
                    authors.append(str(author))

            external_ids = paper_data.get('externalIds', {}) or {}
            arxiv_id = external_ids.get('ArXiv', '') or None
            doi = external_ids.get('DOI', '') or None

            pdf_url = None
            if paper_data.get('openAccessPdf'):
                pdf_url = paper_data['openAccessPdf'].get('url', '')
            if not pdf_url and arxiv_id:
                pdf_url = f"https://arxiv.org/pdf/{arxiv_id}.pdf"

            return StandardPaper(
                semantic_scholar_id=paper_data.get('paperId', '') or None,
                arxiv_id=arxiv_id,
                doi=doi,
                title=paper_data.get('title', ''),
                authors=authors,
                abstract=paper_data.get('abstract', '') or '',
                year=paper_data.get('year'),
                venue=paper_data.get('venue', ''),
                pdf_url=pdf_url,
                citation_count=paper_data.get('citationCount', 0) or 0,
                reference_count=paper_data.get('referenceCount', 0) or 0,
                is_open_access=paper_data.get('isOpenAccess', False),
                source='Semantic Scholar',
                retrieved_at=datetime.now().isoformat(),
                raw_metadata={'semantic_scholar_data': paper_data},
            )
        except Exception as e:
            print(f"Error parsing Semantic Scholar paper: {str(e)}")
            return None

    def search_semantic_scholar(self, query: str, max_results: int = 10) -> List[StandardPaper]:
        """
        Search Semantic Scholar for papers

        Returns:
            List of StandardPaper objects
        """
        import time

        params = {
            'query': query,
            'limit': min(max_results, 100),
            'fields': 'paperId,title,authors,abstract,year,venue,citationCount,referenceCount,isOpenAccess,externalIds,openAccessPdf'
        }

        max_retries = 4
        for attempt in range(max_retries):
            try:
                response = requests.get(self.base_url, params=params, timeout=10)

                if response.status_code == 429:
                    retry_after = response.headers.get("Retry-After")
                    wait = float(retry_after) if retry_after else (2 ** attempt) * 3
                    print(f"  [warn] Semantic Scholar rate-limited (429), waiting "
                          f"{wait:.0f}s before retry {attempt + 1}/{max_retries}...")
                    time.sleep(wait)
                    continue

                response.raise_for_status()

                data = response.json()
                papers = []
                for paper_data in data.get('data', []):
                    paper = self._parse_single_paper(paper_data)
                    if paper is not None:
                        papers.append(paper)
                return papers

            except Exception as e:
                print(f"Error searching Semantic Scholar: {str(e)}")
                if attempt < max_retries - 1:
                    time.sleep((2 ** attempt) * 2)
                    continue
                return []

        print(f"  [error] Semantic Scholar still rate-limited after {max_retries} attempts, giving up for this query")
        return []

    def get_paper_by_arxiv_id(self, arxiv_id: str) -> Optional[StandardPaper]:
        """Get paper from Semantic Scholar using arXiv ID"""
        try:
            url = f"{self.papers_url}/arXiv:{arxiv_id}"
            params = {
                'fields': 'paperId,title,authors,abstract,year,venue,citationCount,referenceCount,isOpenAccess,externalIds,openAccessPdf'
            }

            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()

            paper_data = response.json()
            paper = self._parse_single_paper(paper_data)
            if paper is not None and not paper.arxiv_id:
                paper.arxiv_id = arxiv_id
            return paper

        except Exception as e:
            print(f"Error getting paper by arXiv ID {arxiv_id}: {str(e)}")
            return None