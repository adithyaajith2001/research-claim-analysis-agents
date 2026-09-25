import requests
import xml.etree.ElementTree as ET
import json
import os
from datetime import datetime
import warnings

from paper_schema import StandardPaper

warnings.filterwarnings("ignore")

ARXIV_API_URL = "http://export.arxiv.org/api/query?"


def search_arxiv(query, max_results=5, max_retries=4):
    """Search arXiv for papers."""
    import time

    params = {
        "search_query": f"all:{query}",
        "max_results": max_results,
        "sortBy": "relevance",
        "sortOrder": "descending"
    }

    print(f"Searching arXiv for: '{query}'...")

    for attempt in range(max_retries):
        try:
            response = requests.get(
                ARXIV_API_URL,
                params=params,
                verify=False,
                timeout=30
            )

            if response.status_code == 429:
                retry_after = response.headers.get("Retry-After")
                wait = float(retry_after) if retry_after else (2 ** attempt) * 3
                print(f"  [warn] arXiv rate-limited (429), waiting {wait:.0f}s before retry {attempt + 1}/{max_retries}...")
                time.sleep(wait)
                continue

            response.raise_for_status()
            return response

        except requests.RequestException as e:
            print(f"Error searching arXiv: {e} - retrying ({attempt + 1}/{max_retries})...")
            if attempt < max_retries - 1:
                time.sleep((2 ** attempt) * 2)
                continue
            return None

    print(f"  [error] arXiv still failing after {max_retries} attempts, giving up for this query")
    return None


def generate_metadata_tags(query):
    """Generate metadata tags based on search query."""

    tag_mapping = {
        "transformers": [
            "transformers",
            "attention",
            "nlp",
            "deep-learning"
        ],

        "neural networks": [
            "neural-networks",
            "deep-learning",
            "ml",
            "ai"
        ],

        "machine learning": [
            "machine-learning",
            "ml",
            "ai",
            "algorithms"
        ],

        "deep learning": [
            "deep-learning",
            "neural-networks",
            "cnn",
            "rnn"
        ],

        "nlp": [
            "nlp",
            "transformers",
            "language-models",
            "text-processing"
        ],

        "computer vision": [
            "computer-vision",
            "cnn",
            "image-processing",
            "detection"
        ],
    }

    query_lower = query.lower()

    for key, tags in tag_mapping.items():
        if key in query_lower:
            return tags

    return [
        query.lower().replace(" ", "-")
    ]


def parse_papers_from_xml(xml_string, query):
    """
    Parse arXiv XML response and return StandardPaper objects.
    """

    papers = []

    try:
        root = ET.fromstring(xml_string)

        namespace = {
            "atom": "http://www.w3.org/2005/Atom",
            "arxiv": "http://arxiv.org/schemas/atom"
        }

        entries = root.findall("atom:entry", namespace)

        print(f"Found {len(entries)} papers in XML response.")

        metadata_tags = generate_metadata_tags(query)

        for entry in entries:

            title_element = entry.find("atom:title", namespace)
            title = (
                title_element.text.strip()
                if title_element is not None and title_element.text
                else ""
            )

            id_element = entry.find("atom:id", namespace)
            arxiv_id = ""
            if id_element is not None and id_element.text:
                arxiv_id = id_element.text.split("/abs/")[-1].strip()

            published_element = entry.find("atom:published", namespace)
            published = (
                published_element.text
                if published_element is not None
                else None
            )

            summary_element = entry.find("atom:summary", namespace)
            summary = (
                summary_element.text.strip()
                if summary_element is not None and summary_element.text
                else ""
            )

            authors = []
            for author in entry.findall("atom:author", namespace):
                name_element = author.find("atom:name", namespace)
                if name_element is not None and name_element.text:
                    authors.append(name_element.text.strip())

            pdf_url = None
            for link in entry.findall("atom:link", namespace):
                if link.get("title") == "pdf":
                    pdf_url = link.get("href")
                    break

            year = None
            if published:
                try:
                    year = int(published.split("-")[0])
                except (ValueError, IndexError):
                    year = None

            raw_metadata = {
                "published_date": published,
                "metadata_tags": metadata_tags
            }

            paper = StandardPaper(
                arxiv_id=arxiv_id,
                title=title,
                authors=authors,
                abstract=summary,
                year=year,
                pdf_url=pdf_url,
                source="arXiv",
                retrieved_at=datetime.now().isoformat(),
                raw_metadata=raw_metadata
            )

            papers.append(paper)

        return papers

    except ET.ParseError as e:
        print(f"Error parsing arXiv XML: {e}")
        return []

    except Exception as e:
        print(f"Error processing arXiv papers: {e}")
        return []


class ArxivRetriever:
    """
    PATCHED by Malavika: class wrapper around the module-level functions
    above. unified_retriever.py does `self.arxiv_retriever.search_arxiv(query,
    max_results)` as an instance method.
    """

    def search_arxiv(self, query, max_results=5):
        """Returns List[StandardPaper], not the raw HTTP response."""
        response = search_arxiv(query, max_results)
        if response is None or response.status_code != 200:
            return []
        return parse_papers_from_xml(response.text, query)


def standard_papers_to_dicts(papers):
    """
    Convert StandardPaper objects into dictionaries
    so they can be saved to JSON.
    """

    result = []

    for paper in papers:
        if hasattr(paper, "model_dump"):
            result.append(paper.model_dump())
        elif hasattr(paper, "dict"):
            result.append(paper.dict())
        elif hasattr(paper, "__dict__"):
            result.append(paper.__dict__)
        elif isinstance(paper, dict):
            result.append(paper)
        else:
            raise TypeError(f"Unsupported paper type: {type(paper)}")

    return result


def save_papers_to_json(papers, filename="papers.json"):
    """Save StandardPaper objects to JSON."""

    filepath = f"backend/data/{filename}"

    os.makedirs("backend/data", exist_ok=True)

    try:
        paper_dicts = standard_papers_to_dicts(papers)

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(paper_dicts, f, indent=2, ensure_ascii=False)

        print(f"✓ Saved {len(papers)} papers to {filepath}")

    except Exception as e:
        print(f"Error saving papers to JSON: {e}")


# ============================================================
# MAIN EXECUTION
# ============================================================

if __name__ == "__main__":

    query = "transformers"

    response = search_arxiv(query, max_results=3)

    if response is not None:
        print(f"Status Code: {response.status_code}")

        if response.status_code == 200:
            papers = parse_papers_from_xml(response.text, query)
            save_papers_to_json(papers)

            print(f"\n✓ Retrieved {len(papers)} papers:\n")

            for paper in papers:
                if hasattr(paper, "model_dump"):
                    paper_data = paper.model_dump()
                elif hasattr(paper, "dict"):
                    paper_data = paper.dict()
                else:
                    paper_data = paper.__dict__

                print(f"Title: {paper_data.get('title', '')}")
                print(f"Authors: {', '.join(paper_data.get('authors', []))}")
                print(f"arXiv ID: {paper_data.get('arxiv_id', '')}")
                print(f"Year: {paper_data.get('year', '')}")
                print(f"PDF: {paper_data.get('pdf_url', '')}")

                raw_metadata = paper_data.get("raw_metadata", {})
                print(f"Published: {raw_metadata.get('published_date', '')}")
                print(f"Retrieved: {paper_data.get('retrieved_at', '')}")
                print(f"Tags: {raw_metadata.get('metadata_tags', [])}")
                print("---")

        else:
            print(f"Error: {response.status_code}")

    else:
        print("✗ arXiv request failed.")