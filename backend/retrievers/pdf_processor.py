import requests
import PyPDF2
import json
import io
from typing import Optional, Dict

class PDFProcessor:
    
    @staticmethod
    def download_pdf(pdf_url: str) -> Optional[bytes]:
        """Download PDF from URL"""
        try:
            print(f"📥 Downloading: {pdf_url[:50]}...")
            response = requests.get(pdf_url, timeout=15, verify=False)
            response.raise_for_status()
            print(f"✓ Downloaded")
            return response.content
        except Exception as e:
            print(f"✗ Download failed: {e}")
            return None
    
    @staticmethod
    def extract_text(pdf_content: bytes, max_pages: int = 5) -> str:
        """Extract text from PDF"""
        try:
            pdf_file = io.BytesIO(pdf_content)
            reader = PyPDF2.PdfReader(pdf_file)
            
            text = ""
            pages = min(max_pages, len(reader.pages))
            print(f"📖 Extracting {pages} pages...")
            
            for page_num in range(pages):
                page = reader.pages[page_num]
                text += f"\n--- Page {page_num + 1} ---\n"
                text += page.extract_text()
            
            print(f"✓ Extracted {pages} pages")
            return text
        except Exception as e:
            print(f"✗ Extraction failed: {e}")
            return ""
    
    @staticmethod
    def process_papers_from_json(json_file: str = "backend/data/papers.json", max_pages: int = 5):
        """Process all papers in JSON file"""
        
        # Read papers from JSON
        print(f"\n📂 Reading {json_file}...")
        with open(json_file, 'r', encoding='utf-8') as f:
            papers = json.load(f)
        
        print(f"Found {len(papers)} papers\n")
        
        # Process each paper
        for idx, paper in enumerate(papers, 1):
            print(f"\n{'='*60}")
            print(f"Paper {idx}/{len(papers)}: {paper['title'][:50]}...")
            print(f"{'='*60}")
            
            pdf_url = paper.get('pdf_url')
            if not pdf_url:
                print("✗ No PDF URL found")
                continue
            
            # Download & extract
            pdf_content = PDFProcessor.download_pdf(pdf_url)
            if not pdf_content:
                continue
            
            raw_text = PDFProcessor.extract_text(pdf_content, max_pages)
            if not raw_text:
                continue
            
            # Add to paper
            paper['raw_text'] = raw_text
            paper['text_length'] = len(raw_text)
            print(f"✓ Text length: {len(raw_text)} characters")
        
        # Save updated JSON
        print(f"\n{'='*60}")
        print("💾 Saving updated papers.json...")
        with open(json_file, 'w', encoding='utf-8') as f:
            json.dump(papers, f, indent=2, ensure_ascii=False)
        
        print(f"✓ Saved {len(papers)} papers with extracted text")


if __name__ == "__main__":
    print("\n🚀 Starting PDF Text Extraction\n")
    PDFProcessor.process_papers_from_json(max_pages=3)
    print("\n✅ Done!")