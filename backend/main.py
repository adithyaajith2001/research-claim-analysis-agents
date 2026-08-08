from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import json
import os
import sys
import warnings

warnings.filterwarnings('ignore')

sys.path.insert(0, 'backend/retrievers')
from arxiv_retriever import search_arxiv, parse_papers_from_xml, save_papers_to_json

app = FastAPI(
    title="Research Contradiction Checker",
    description="API for paper retrieval and claim analysis",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def load_papers():
    """Load papers from papers.json"""
    json_file = "backend/data/papers.json"
    if os.path.exists(json_file):
        with open(json_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    return []

@app.get("/")
def root():
    """Root endpoint"""
    return {
        "message": "Research Contradiction Checker API",
        "endpoints": [
            "GET /api/papers",
            "GET /api/papers/{paper_id}",
            "GET /api/papers/{paper_id}/raw-text",
            "POST /api/search?query=...&max_results=5",
            "GET /health",
            "GET /docs"
        ]
    }

@app.get("/api/papers")
def get_all_papers():
    """Get all papers"""
    papers = load_papers()
    return {
        "status": "success",
        "total_papers": len(papers),
        "papers": papers
    }

@app.get("/api/papers/{paper_id}")
def get_paper(paper_id: int):
    """Get a single paper by ID"""
    papers = load_papers()
    for paper in papers:
        if paper['id'] == paper_id:
            return {
                "status": "success",
                "paper": paper
            }
    return {
        "status": "error",
        "message": f"Paper {paper_id} not found"
    }

@app.get("/api/papers/{paper_id}/raw-text")
def get_paper_raw_text(paper_id: int):
    """Get raw text from a paper"""
    papers = load_papers()
    for paper in papers:
        if paper['id'] == paper_id:
            return {
                "status": "success",
                "paper_id": paper_id,
                "title": paper['title'],
                "raw_text": paper.get('raw_text', ''),
                "text_length": paper.get('text_length', 0)
            
            }
            
    return {
        "status": "error",
        "message": f"Paper {paper_id} not found"
    }

@app.post("/api/search")
def search_papers(query: str, max_results: int = 5):
    """Search arXiv for papers and extract text from PDFs"""
    try:
        print(f"\n Searching arXiv for: '{query}'...")
        response = search_arxiv(query, max_results)
        
        if response.status_code == 200:
            # Step 1: Parse papers from XML
            papers = parse_papers_from_xml(response.text, query)
            print(f"\n Retrieved {len(papers)} papers. Now extracting PDFs...\n")
            
            # Step 2: Process each paper's PDF
            for idx, paper in enumerate(papers, 1):
                print(f"{'='*60}")
                print(f"Processing Paper {idx}/{len(papers)}: {paper['title'][:50]}...")
                print(f"{'='*60}")
                
                pdf_url = paper.get('pdf_url')
                if pdf_url:
                    # Download and extract PDF
                    pdf_result = PDFProcessor.process_paper(
                        pdf_url=pdf_url,
                        paper_id=paper['id'],
                        max_pages=5
                    )
                    
                    if pdf_result:
                        paper['raw_text'] = pdf_result['full_text']
                        paper['text_length'] = pdf_result['text_length']
                        print(f"✓ PDF processed: {pdf_result['text_length']} characters extracted\n")
                    else:
                        paper['raw_text'] = ""
                        paper['text_length'] = 0
                        print(f"✗ Failed to process PDF\n")
                else:
                    paper['raw_text'] = ""
                    paper['text_length'] = 0
            
            # Step 3: Save to JSON
            save_papers_to_json(papers, filename="papers.json")
            
            return {
                "status": "success",
                "query": query,
                "papers_retrieved": len(papers),
                "papers": papers
            }
        else:
            return {
                "status": "error",
                "message": f"arXiv API returned status {response.status_code}"
            }
    except Exception as e:
        return {
            "status": "error",
            "message": str(e)
        }
@app.get("/health")
def health_check():
    """Check if API is running"""
    return {"status": "healthy"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)