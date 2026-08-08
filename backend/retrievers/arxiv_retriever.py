import requests
import xml.etree.ElementTree as ET
import json
import os
from datetime import datetime
import warnings

warnings.filterwarnings('ignore')

ARXIV_API_URL = "http://export.arxiv.org/api/query?"

def search_arxiv(query, max_results=5):
    """Search arXiv for papers"""
    
    params = {
        "search_query": f"all:{query}",
        "max_results": max_results,
        "sortBy": "relevance",
        "sortOrder": "descending"
    }
    
    print(f"Searching arXiv for: '{query}'...")
    response = requests.get(ARXIV_API_URL, params=params, verify=False)
    
    return response


def generate_metadata_tags(query):
    """Generate metadata tags based on search query"""
    
    # Map common queries to metadata tags
    tag_mapping = {
        "transformers": ["transformers", "attention", "nlp", "deep-learning"],
        "neural networks": ["neural-networks", "deep-learning", "ml", "ai"],
        "machine learning": ["machine-learning", "ml", "ai", "algorithms"],
        "deep learning": ["deep-learning", "neural-networks", "cnn", "rnn"],
        "nlp": ["nlp", "transformers", "language-models", "text-processing"],
        "computer vision": ["computer-vision", "cnn", "image-processing", "detection"],
    }
    
    # Check if query matches any mapping
    query_lower = query.lower()
    for key, tags in tag_mapping.items():
        if key in query_lower:
            return tags
    
    # Default: use the query itself as a tag
    return [query.lower().replace(" ", "-")]


def parse_papers_from_xml(xml_string, query):
    """Parse XML response and extract paper details"""
    
    papers = []
    
    # Parse the XML
    root = ET.fromstring(xml_string)
    
    # Define namespace (arXiv uses namespaces in XML)
    namespace = {
        'atom': 'http://www.w3.org/2005/Atom',
        'arxiv': 'http://arxiv.org/schemas/atom'
    }
    
    # Find all <entry> tags (each entry is one paper)
    entries = root.findall('atom:entry', namespace)
    
    # Generate metadata tags based on query
    metadata_tags = generate_metadata_tags(query)
    
    for entry in entries:
        # Extract paper information
        title = entry.find('atom:title', namespace).text.strip()
        arxiv_id = entry.find('atom:id', namespace).text.split('/abs/')[-1]
        published = entry.find('atom:published', namespace).text
        summary = entry.find('atom:summary', namespace).text.strip()
        
        # Extract authors
        authors = []
        for author in entry.findall('atom:author', namespace):
            name = author.find('atom:name', namespace).text
            authors.append(name)
        
        # Extract PDF URL
        pdf_url = None
        for link in entry.findall('atom:link', namespace):
            if link.get('title') == 'pdf':
                pdf_url = link.get('href')
                break
        
        # Create paper dict
        paper = {
            "id": len(papers) + 1,
            "title": title,
            "arxiv_id": arxiv_id,
            "authors": " | ".join(authors),
            "abstract": summary,
            "pdf_url": pdf_url,
            "source": "arxiv",
            "published_date": published,
            "metadata_tags": metadata_tags,  # Now dynamic based on query
            "retrieved_at": datetime.now().isoformat()
        }
        
        papers.append(paper)
    
    return papers


def save_papers_to_json(papers, filename="papers.json"):
    """Save papers to JSON file"""
    
    filepath = f"backend/data/{filename}"
    
    # Create directory if it doesn't exist
    os.makedirs("backend/data", exist_ok=True)
    
    # Write to JSON file
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(papers, f, indent=2, ensure_ascii=False)
    
    print(f"✓ Saved {len(papers)} papers to {filepath}")


# Main execution
if __name__ == "__main__":
    query = "transformers"
    
    # Step 1: Search arXiv
    response = search_arxiv(query, max_results=3)
    
    print(f"Status Code: {response.status_code}")
    
    if response.status_code == 200:
        # Step 2: Parse XML (pass query to get proper tags)
        papers = parse_papers_from_xml(response.text, query)
        
        # Step 3: Save to JSON
        save_papers_to_json(papers)
        
        # Step 4: Print results
        print(f"\n✓ Retrieved {len(papers)} papers:\n")
        for paper in papers:
            print(f"Title: {paper['title']}")
            print(f"Authors: {paper['authors']}")
            print(f"Tags: {paper['metadata_tags']}")
            print(f"---\n")
    else:
        print(f"Error: {response.status_code}")