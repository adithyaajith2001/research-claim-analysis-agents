"""
Improved PDF Processor with error handling and SSL verification
"""

import requests
import PyPDF2
import json
import os
from io import BytesIO
from typing import Optional, List
from paper_schema import StandardPaper

class PDFProcessor:
    
    def __init__(self, verify_ssl: bool = True, max_pages: int = 5):
        """
        Args:
            verify_ssl: Whether to verify SSL certificates
            max_pages: Default max pages to extract
        """
        self.verify_ssl = verify_ssl
        self.max_pages = max_pages
    
    def download_pdf(self, pdf_url: str, timeout: int = 15) -> Optional[bytes]:
        """
        Download PDF from URL with proper error handling
        
        Args:
            pdf_url: URL to PDF
            timeout: Request timeout in seconds
        
        Returns:
            PDF bytes or None if failed
        """
        try:
            if not pdf_url:
                print(f"❌ No PDF URL provided")
                return None
            
            print(f"📥 Downloading: {pdf_url[:60]}...")
            
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            
            response = requests.get(
                pdf_url,
                headers=headers,
                timeout=timeout,
                verify=self.verify_ssl,  # Configurable
                allow_redirects=True
            )
            
            response.raise_for_status()
            
            # Verify it's actually a PDF
            if 'application/pdf' not in response.headers.get('content-type', ''):
                print(f"❌ URL did not return PDF (content-type: {response.headers.get('content-type')})")
                return None
            
            print(f"✓ Downloaded ({len(response.content)} bytes)")
            return response.content
            
        except requests.exceptions.RequestException as e:
            print(f"❌ Download failed: {str(e)}")
            return None
        except Exception as e:
            print(f"❌ Unexpected error downloading PDF: {str(e)}")
            return None
    
    def extract_text(self, pdf_bytes: bytes, max_pages: Optional[int] = None) -> Optional[str]:
        """
        Extract text from PDF bytes with error handling
        
        Args:
            pdf_bytes: PDF content
            max_pages: Max pages to extract (uses default if None)
        
        Returns:
            Extracted text or None if failed
        """
        
        if max_pages is None:
            max_pages = self.max_pages
        
        try:
            pdf_file = BytesIO(pdf_bytes)
            reader = PyPDF2.PdfReader(pdf_file)
            
            num_pages = len(reader.pages)
            pages_to_extract = min(max_pages, num_pages)
            
            print(f"📖 Extracting {pages_to_extract} pages...")
            
            extracted_text = ""
            
            for page_num in range(pages_to_extract):
                try:
                    page = reader.pages[page_num]
                    page_text = page.extract_text()
                    
                    # Handle None text
                    if page_text is None:
                        print(f"  ⚠ Page {page_num + 1}: No text extracted (blank/scanned page)")
                        continue
                    
                    extracted_text += f"\n--- Page {page_num + 1} ---\n"
                    extracted_text += page_text
                    
                except Exception as page_error:
                    print(f"  ⚠ Page {page_num + 1} extraction failed: {str(page_error)}")
                    continue
            
            if not extracted_text.strip():
                print(f"❌ No text extracted (likely scanned PDF)")
                return None
            
            print(f"✓ Extracted {len(extracted_text)} characters")
            return extracted_text
            
        except Exception as e:
            print(f"❌ PDF extraction failed: {str(e)}")
            return None
    
    def process_paper(self, paper: StandardPaper, max_pages: Optional[int] = None) -> StandardPaper:
        """
        Download and extract PDF text for a single paper
        
        Args:
            paper: StandardPaper object
            max_pages: Pages to extract (uses default if None)
        
        Returns:
            Updated StandardPaper with raw_text
        """
        
        pdf_url = paper.get_pdf_url()
        if not pdf_url:
            print(f"⚠ No PDF URL for: {paper.title[:50]}...")
            return paper
        
        print(f"\n{'='*60}")
        print(f"Processing: {paper.title[:50]}...")
        print(f"Source: {paper.source}")
        print(f"{'='*60}")
        
        # Download
        pdf_bytes = self.download_pdf(pdf_url)
        if not pdf_bytes:
            return paper
        
        # Extract
        text = self.extract_text(pdf_bytes, max_pages)
        if not text:
            return paper
        
        # Add to paper (don't modify original, return updated copy)
        paper.raw_metadata['raw_text'] = text
        paper.raw_metadata['text_length'] = len(text)
        
        return paper
    
    def process_papers_from_json(self, 
                                 input_file: str = "backend/data/papers.json",
                                 output_file: str = "backend/data/papers_with_text.json",
                                 max_pages: Optional[int] = None,
                                 skip_existing: bool = True) -> List[StandardPaper]:
        """
        Process all papers in JSON file
        
        Args:
            input_file: Path to input papers.json
            output_file: Path to save updated papers (different file!)
            max_pages: Max pages per paper
            skip_existing: Skip papers that already have raw_text
        
        Returns:
            List of processed papers
        """
        
        if max_pages is None:
            max_pages = self.max_pages
        
        try:
            # Load papers
            with open(input_file, 'r', encoding='utf-8') as f:
                papers_data = json.load(f)
            
            print(f"\n📂 Loaded {len(papers_data)} papers from {input_file}")
            
            processed_papers = []
            
            for idx, paper_dict in enumerate(papers_data, 1):
                # Convert dict to StandardPaper
                paper = StandardPaper(**paper_dict)
                
                # Skip if already has text
                if skip_existing and paper.raw_metadata.get('raw_text'):
                    print(f"\n[{idx}/{len(papers_data)}] Skipping (already has text): {paper.title[:40]}...")
                    processed_papers.append(paper)
                    continue
                
                # Process
                updated_paper = self.process_paper(paper, max_pages)
                processed_papers.append(updated_paper)
            
            # Save to NEW file (don't overwrite original)
            print(f"\n{'='*60}")
            print(f"💾 Saving to {output_file}...")
            
            os.makedirs("backend/data", exist_ok=True)
            
            papers_dict = [p.to_dict() for p in processed_papers]
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(papers_dict, f, indent=2, ensure_ascii=False)
            
            print(f"✓ Saved {len(processed_papers)} papers")
            print(f"{'='*60}\n")
            
            return processed_papers
            
        except FileNotFoundError:
            print(f"❌ File not found: {input_file}")
            return []
        except json.JSONDecodeError:
            print(f"❌ Invalid JSON in: {input_file}")
            return []
        except Exception as e:
            print(f"❌ Error processing papers: {str(e)}")
            return []


# Usage example
if __name__ == "__main__":
    processor = PDFProcessor(verify_ssl=True, max_pages=5)
    papers = processor.process_papers_from_json(
        input_file="backend/data/papers.json",
        output_file="backend/data/papers_with_text.json",
        skip_existing=True
    )