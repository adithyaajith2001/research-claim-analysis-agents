"""
Semantic Scholar Paper Retriever
Author: Adithya Ajith
Retrieves papers from Semantic Scholar API (academic metadata)
"""

import requests
import json
from typing import List, Dict, Optional

class SemanticScholarRetriever:
    """Retrieves research papers from Semantic Scholar API"""
    
    def __init__(self):
        self.base_url = "https://api.semanticscholar.org/graph/v1/paper/search"
        self.papers_url = "https://api.semanticscholar.org/graph/v1/paper"
    
    def search_semantic_scholar(self, query: str, max_results: int = 10) -> List[Dict]:
        """
        Search Semantic Scholar for papers
        
        Args:
            query: Search term
            max_results: Number of results
        
        Returns:
            List of paper dictionaries
        """
        try:
            params = {
                'query': query,
                'limit': min(max_results, 100),
                'fields': 'paperId,title,authors,abstract,year,venue,citations,referenceCount,isOpenAccess,externalIds,openAccessPdf'
            }
            
            response = requests.get(self.base_url, params=params, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            papers = []
            
            for paper_data in data.get('data', []):
                # Extract authors
                authors = []
                for author in paper_data.get('authors', []):
                    if isinstance(author, dict):
                        authors.append(author.get('name', ''))
                    else:
                        authors.append(str(author))
                
                # Get external IDs
                external_ids = paper_data.get('externalIds', {})
                arxiv_id = external_ids.get('ArXiv', '')
                doi = external_ids.get('DOI', '')
                
                # Get PDF URL
                pdf_url = None
                if paper_data.get('openAccessPdf'):
                    pdf_url = paper_data['openAccessPdf'].get('url', '')
                
                # Build paper dict
                paper = {
                    'semantic_scholar_id': paper_data.get('paperId', ''),
                    'arxiv_id': arxiv_id,
                    'doi': doi,
                    'title': paper_data.get('title', ''),
                    'authors': authors,
                    'abstract': paper_data.get('abstract', ''),
                    'year': paper_data.get('year', ''),
                    'venue': paper_data.get('venue', ''),
                    'citation_count': paper_data.get('citationCount', 0),
                    'reference_count': paper_data.get('referenceCount', 0),
                    'is_open_access': paper_data.get('isOpenAccess', False),
                    'pdf_url': pdf_url or (f"https://arxiv.org/pdf/{arxiv_id}.pdf" if arxiv_id else None),
                    'source': 'Semantic Scholar'
                }
                
                papers.append(paper)
            
            return papers
            
        except Exception as e:
            print(f"Error searching Semantic Scholar: {str(e)}")
            return []
    
    def get_paper_by_arxiv_id(self, arxiv_id: str) -> Optional[Dict]:
        """Get paper from Semantic Scholar using arXiv ID"""
        try:
            url = f"{self.papers_url}/arXiv:{arxiv_id}"
            params = {
                'fields': 'paperId,title,authors,abstract,year,venue,citations,referenceCount,isOpenAccess,externalIds,openAccessPdf'
            }
            
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            
            paper_data = response.json()
            
            # Parse single paper
            authors = []
            for author in paper_data.get('authors', []):
                if isinstance(author, dict):
                    authors.append(author.get('name', ''))
                else:
                    authors.append(str(author))
            
            external_ids = paper_data.get('externalIds', {})
            pdf_url = None
            if paper_data.get('openAccessPdf'):
                pdf_url = paper_data['openAccessPdf'].get('url', '')
            
            paper = {
                'semantic_scholar_id': paper_data.get('paperId', ''),
                'arxiv_id': arxiv_id,
                'title': paper_data.get('title', ''),
                'authors': authors,
                'abstract': paper_data.get('abstract', ''),
                'year': paper_data.get('year', ''),
                'citation_count': paper_data.get('citationCount', 0),
                'is_open_access': paper_data.get('isOpenAccess', False),
                'pdf_url': pdf_url or f"https://arxiv.org/pdf/{arxiv_id}.pdf",
                'source': 'Semantic Scholar'
            }
            
            return paper
            
        except Exception as e:
            print(f"Error getting paper by arXiv ID {arxiv_id}: {str(e)}")
            return None