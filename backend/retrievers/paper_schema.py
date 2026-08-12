"""
Standardized Paper Schema
All retrievers must return papers in this format
"""

from typing import Optional, Dict, List
from dataclasses import dataclass, asdict

@dataclass
class StandardPaper:
    """Unified paper structure for all retrievers"""
    
    # Primary identifiers (at least one must exist)
    arxiv_id: Optional[str] = None
    doi: Optional[str] = None
    semantic_scholar_id: Optional[str] = None
    
    # Core metadata
    title: str = ""
    authors: List[str] = None  # List, not string
    abstract: str = ""
    year: Optional[int] = None
    
    # Publication info
    journal: Optional[str] = None  # Use 'journal' for all sources
    venue: Optional[str] = None    # Fallback to venue if journal missing
    volume: Optional[str] = None
    issue: Optional[str] = None
    pages: Optional[str] = None
    
    # URLs (standardized to 'pdf_url')
    pdf_url: Optional[str] = None
    url: Optional[str] = None
    
    # Citation data
    citation_count: int = 0
    reference_count: int = 0
    is_open_access: bool = False
    
    # Source tracking
    source: str = ""  # "arXiv", "Semantic Scholar", "CrossRef"
    retrieved_at: Optional[str] = None
    
    # Raw metadata from source
    raw_metadata: Dict = None
    
    def __post_init__(self):
        if self.authors is None:
            self.authors = []
        if self.raw_metadata is None:
            self.raw_metadata = {}
    
    def get_primary_id(self) -> Optional[str]:
        """Get the best identifier for deduplication"""
        # Priority: arxiv_id > doi > semantic_scholar_id
        if self.arxiv_id:
            return f"arxiv:{self.arxiv_id}"
        if self.doi:
            return f"doi:{self.doi}"
        if self.semantic_scholar_id:
            return f"semantic:{self.semantic_scholar_id}"
        return None
    
    def get_publication_venue(self) -> str:
        """Get journal/venue (standardized)"""
        return self.journal or self.venue or "Unknown"
    
    def get_pdf_url(self) -> Optional[str]:
        """Get PDF URL (standardized)"""
        return self.pdf_url or self.url
    
    def to_dict(self) -> Dict:
        """Convert to dictionary"""
        return asdict(self)