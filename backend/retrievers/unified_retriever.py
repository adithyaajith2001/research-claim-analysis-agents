"""
Unified Paper Retriever - Combines all 3 sources
Author: Adithya Ajith
"""

import json
from typing import List, Dict, Optional
from arxiv_retriever import ArxivRetriever
from semantic_scholar_retriever import SemanticScholarRetriever
from crossref_retriever import CrossRefRetriever
from paper_schema import StandardPaper

class UnifiedPaperRetriever:
    """Combines arXiv, Semantic Scholar, and CrossRef"""
    
    def __init__(self):
        self.arxiv_retriever = ArxivRetriever()
        self.semantic_retriever = SemanticScholarRetriever()
        self.crossref_retriever = CrossRefRetriever()
    
    def search_all_sources(self, query: str, max_results: int = 10) -> List[StandardPaper]:
        """
        Search all 3 sources and combine results

        Args:
            query: Search term
            max_results: Max results per source

        Returns:
            List of deduplicated StandardPaper objects from all sources

        PATCHED by Malavika: all three retrievers now return StandardPaper
        objects (not plain dicts), so dedup uses paper.get_primary_id()
        instead of paper.get('arxiv_id', '') - the old dict-style access
        would crash with AttributeError on StandardPaper.
        """
        all_papers = []
        paper_ids = set()  # For deduplication

        print(f"Searching all sources for: {query}")

        # STEP 1: Search arXiv
        print("\n[1/3] Searching arXiv...")
        try:
            arxiv_papers = self.arxiv_retriever.search_arxiv(query, max_results)
            print(f"  → Found {len(arxiv_papers)} papers on arXiv")

            for paper in arxiv_papers:
                paper_id = paper.get_primary_id()
                if paper_id and paper_id not in paper_ids:
                    all_papers.append(paper)
                    paper_ids.add(paper_id)
        except Exception as e:
            print(f"  → arXiv search failed: {str(e)}")

        # STEP 2: Search Semantic Scholar
        print("\n[2/3] Searching Semantic Scholar...")
        try:
            semantic_papers = self.semantic_retriever.search_semantic_scholar(query, max_results)
            print(f"  → Found {len(semantic_papers)} papers on Semantic Scholar")

            for paper in semantic_papers:
                paper_id = paper.get_primary_id()
                if paper_id and paper_id not in paper_ids:
                    all_papers.append(paper)
                    paper_ids.add(paper_id)
        except Exception as e:
            print(f"  → Semantic Scholar search failed: {str(e)}")

        # STEP 3: Search CrossRef
        print("\n[3/3] Searching CrossRef...")
        try:
            crossref_papers = self.crossref_retriever.search_crossref(query, max_results)
            print(f"  → Found {len(crossref_papers)} papers on CrossRef")

            for paper in crossref_papers:
                paper_id = paper.get_primary_id()
                if paper_id and paper_id not in paper_ids:
                    all_papers.append(paper)
                    paper_ids.add(paper_id)
        except Exception as e:
            print(f"  → CrossRef search failed: {str(e)}")

        print(f"\n✅ Total unique papers found: {len(all_papers)}")

        return all_papers
    
    def get_paper_by_arxiv_id(self, arxiv_id: str) -> Optional[StandardPaper]:
        """Get paper by arXiv ID"""
        try:
            paper = self.arxiv_retriever.search_arxiv(arxiv_id, max_results=1)
            if paper:
                return paper[0]
        except Exception:
            pass
        
        try:
            return self.semantic_retriever.get_paper_by_arxiv_id(arxiv_id)
        except Exception:
            return None
    
    def get_paper_by_doi(self, doi: str) -> Optional[StandardPaper]:
        """Get paper by DOI"""
        try:
            return self.crossref_retriever.search_by_doi(doi)
        except Exception:
            return None
    
    def save_papers_to_json(self, papers: List[StandardPaper], filename: str = "backend/data/papers.json"):
        """Save all papers to JSON. PATCHED: converts StandardPaper -> dict first."""
        try:
            paper_dicts = [p.to_dict() if hasattr(p, "to_dict") else p for p in papers]
            with open(filename, 'w') as f:
                json.dump(paper_dicts, f, indent=2)
            print(f"✅ Saved {len(papers)} papers to {filename}")
        except Exception as e:
            print(f"❌ Error saving papers: {str(e)}")
    
    def load_papers_from_json(self, filename: str = "backend/data/papers.json") -> List[Dict]:
        """Load papers from JSON"""
        try:
            with open(filename, 'r') as f:
                papers = json.load(f)
            print(f"✅ Loaded {len(papers)} papers from {filename}")
            return papers
        except Exception as e:
            print(f"❌ Error loading papers: {str(e)}")
            return []


# ==================== USAGE EXAMPLE ====================
if __name__ == "__main__":
    retriever = UnifiedPaperRetriever()
    
    # Search all sources
    papers = retriever.search_all_sources("Transformers vision", max_results=5)
    
    # Save to JSON
    retriever.save_papers_to_json(papers)