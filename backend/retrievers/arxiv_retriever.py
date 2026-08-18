# import requests
# import xml.etree.ElementTree as ET
# import json
# import os
# from datetime import datetime
# import warnings

# from paper_schema import StandardPaper

# warnings.filterwarnings("ignore")

# ARXIV_API_URL = "http://export.arxiv.org/api/query?"


# def search_arxiv(query, max_results=5):
#     """Search arXiv for papers."""

#     params = {
#         "search_query": f"all:{query}",
#         "max_results": max_results,
#         "sortBy": "relevance",
#         "sortOrder": "descending"
#     }

#     print(f"Searching arXiv for: '{query}'...")

#     try:
#         response = requests.get(
#             ARXIV_API_URL,
#             params=params,
#             verify=False,
#             timeout=15
#         )

#         response.raise_for_status()

#         return response

#     except requests.RequestException as e:
#         print(f"Error searching arXiv: {e}")
#         return None


# def generate_metadata_tags(query):
#     """Generate metadata tags based on search query."""

#     tag_mapping = {
#         "transformers": [
#             "transformers",
#             "attention",
#             "nlp",
#             "deep-learning"
#         ],

#         "neural networks": [
#             "neural-networks",
#             "deep-learning",
#             "ml",
#             "ai"
#         ],

#         "machine learning": [
#             "machine-learning",
#             "ml",
#             "ai",
#             "algorithms"
#         ],

#         "deep learning": [
#             "deep-learning",
#             "neural-networks",
#             "cnn",
#             "rnn"
#         ],

#         "nlp": [
#             "nlp",
#             "transformers",
#             "language-models",
#             "text-processing"
#         ],

#         "computer vision": [
#             "computer-vision",
#             "cnn",
#             "image-processing",
#             "detection"
#         ],
#     }

#     query_lower = query.lower()

#     for key, tags in tag_mapping.items():
#         if key in query_lower:
#             return tags

#     return [
#         query.lower().replace(" ", "-")
#     ]


# def parse_papers_from_xml(xml_string, query):
#     """
#     Parse arXiv XML response and return StandardPaper objects.
#     """

#     papers = []

#     try:
#         # Parse XML
#         root = ET.fromstring(xml_string)

#         # arXiv XML namespaces
#         namespace = {
#             "atom": "http://www.w3.org/2005/Atom",
#             "arxiv": "http://arxiv.org/schemas/atom"
#         }

#         # Find all paper entries
#         entries = root.findall(
#             "atom:entry",
#             namespace
#         )

#         print(
#             f"Found {len(entries)} papers in XML response."
#         )

#         # Generate metadata tags
#         metadata_tags = generate_metadata_tags(query)

#         for entry in entries:

#             # =========================================
#             # TITLE
#             # =========================================

#             title_element = entry.find(
#                 "atom:title",
#                 namespace
#             )

#             title = (
#                 title_element.text.strip()
#                 if title_element is not None
#                 and title_element.text
#                 else ""
#             )

#             # =========================================
#             # ARXIV ID
#             # =========================================

#             id_element = entry.find(
#                 "atom:id",
#                 namespace
#             )

#             arxiv_id = ""

#             if id_element is not None and id_element.text:

#                 arxiv_id = (
#                     id_element.text
#                     .split("/abs/")[-1]
#                     .strip()
#                 )

#             # =========================================
#             # PUBLISHED DATE
#             # =========================================

#             published_element = entry.find(
#                 "atom:published",
#                 namespace
#             )

#             published = (
#                 published_element.text
#                 if published_element is not None
#                 else None
#             )

#             # =========================================
#             # ABSTRACT
#             # =========================================

#             summary_element = entry.find(
#                 "atom:summary",
#                 namespace
#             )

#             summary = (
#                 summary_element.text.strip()
#                 if summary_element is not None
#                 and summary_element.text
#                 else ""
#             )

#             # =========================================
#             # AUTHORS
#             # =========================================

#             authors = []

#             for author in entry.findall(
#                 "atom:author",
#                 namespace
#             ):

#                 name_element = author.find(
#                     "atom:name",
#                     namespace
#                 )

#                 if (
#                     name_element is not None
#                     and name_element.text
#                 ):
#                     authors.append(
#                         name_element.text.strip()
#                     )

#             # =========================================
#             # PDF URL
#             # =========================================

#             pdf_url = None

#             for link in entry.findall(
#                 "atom:link",
#                 namespace
#             ):

#                 if link.get("title") == "pdf":

#                     pdf_url = link.get("href")

#                     break

#             # =========================================
#             # YEAR
#             # =========================================

#             year = None

#             if published:

#                 try:

#                     year = int(
#                         published.split("-")[0]
#                     )

#                 except (
#                     ValueError,
#                     IndexError
#                 ):

#                     year = None

#             # =========================================
#             # RAW METADATA
#             # =========================================

#             raw_metadata = {
#                 "published_date": published,
#                 "metadata_tags": metadata_tags
#             }

#             # =========================================
#             # CREATE STANDARD PAPER
#             # =========================================

#             paper = StandardPaper(

#                 arxiv_id=arxiv_id,

#                 title=title,

#                 authors=authors,

#                 abstract=summary,

#                 year=year,

#                 pdf_url=pdf_url,

#                 source="arXiv",

#                 # This is when OUR SYSTEM
#                 # retrieved the paper
#                 retrieved_at=datetime.now().isoformat(),

#                 # Publication date stays here
#                 raw_metadata=raw_metadata
#             )

#             papers.append(paper)

#         return papers

#     except ET.ParseError as e:

#         print(
#             f"Error parsing arXiv XML: {e}"
#         )

#         return []

#     except Exception as e:

#         print(
#             f"Error processing arXiv papers: {e}"
#         )

#         return []


# def standard_papers_to_dicts(papers):
#     """
#     Convert StandardPaper objects into dictionaries
#     so they can be saved to JSON.
#     """

#     result = []

#     for paper in papers:

#         # Pydantic v2
#         if hasattr(
#             paper,
#             "model_dump"
#         ):

#             result.append(
#                 paper.model_dump()
#             )

#         # Pydantic v1
#         elif hasattr(
#             paper,
#             "dict"
#         ):

#             result.append(
#                 paper.dict()
#             )

#         # Normal Python object
#         elif hasattr(
#             paper,
#             "__dict__"
#         ):

#             result.append(
#                 paper.__dict__
#             )

#         # Already a dictionary
#         elif isinstance(
#             paper,
#             dict
#         ):

#             result.append(paper)

#         else:

#             raise TypeError(
#                 f"Unsupported paper type: {type(paper)}"
#             )

#     return result


# def save_papers_to_json(
#     papers,
#     filename="papers.json"
# ):
#     """Save StandardPaper objects to JSON."""

#     filepath = f"backend/data/{filename}"

#     # Create directory if it doesn't exist
#     os.makedirs(
#         "backend/data",
#         exist_ok=True
#     )

#     try:

#         # Convert StandardPaper objects
#         # to dictionaries
#         paper_dicts = standard_papers_to_dicts(
#             papers
#         )

#         # Save JSON
#         with open(
#             filepath,
#             "w",
#             encoding="utf-8"
#         ) as f:

#             json.dump(
#                 paper_dicts,
#                 f,
#                 indent=2,
#                 ensure_ascii=False
#             )

#         print(
#             f"✓ Saved {len(papers)} papers "
#             f"to {filepath}"
#         )

#     except Exception as e:

#         print(
#             f"Error saving papers to JSON: {e}"
#         )


# # ============================================================
# # MAIN EXECUTION
# # ============================================================

# if __name__ == "__main__":

#     query = "transformers"

#     # =========================================
#     # STEP 1: Search arXiv
#     # =========================================

#     response = search_arxiv(
#         query,
#         max_results=3
#     )

#     if response is not None:

#         print(
#             f"Status Code: {response.status_code}"
#         )

#         if response.status_code == 200:

#             # =========================================
#             # STEP 2: Parse XML
#             # =========================================

#             papers = parse_papers_from_xml(
#                 response.text,
#                 query
#             )

#             # =========================================
#             # STEP 3: Save papers
#             # =========================================

#             save_papers_to_json(
#                 papers
#             )

#             # =========================================
#             # STEP 4: Print results
#             # =========================================

#             print(
#                 f"\n✓ Retrieved "
#                 f"{len(papers)} papers:\n"
#             )

#             for paper in papers:

#                 # Convert to dictionary
#                 if hasattr(
#                     paper,
#                     "model_dump"
#                 ):

#                     paper_data = (
#                         paper.model_dump()
#                     )

#                 elif hasattr(
#                     paper,
#                     "dict"
#                 ):

#                     paper_data = (
#                         paper.dict()
#                     )

#                 else:

#                     paper_data = (
#                         paper.__dict__
#                     )

#                 print(
#                     f"Title: "
#                     f"{paper_data.get('title', '')}"
#                 )

#                 print(
#                     f"Authors: "
#                     f"{', '.join(paper_data.get('authors', []))}"
#                 )

#                 print(
#                     f"arXiv ID: "
#                     f"{paper_data.get('arxiv_id', '')}"
#                 )

#                 print(
#                     f"Year: "
#                     f"{paper_data.get('year', '')}"
#                 )

#                 print(
#                     f"PDF: "
#                     f"{paper_data.get('pdf_url', '')}"
#                 )

#                 raw_metadata = paper_data.get(
#                     "raw_metadata",
#                     {}
#                 )

#                 print(
#                     f"Published: "
#                     f"{raw_metadata.get('published_date', '')}"
#                 )

#                 print(
#                     f"Retrieved: "
#                     f"{paper_data.get('retrieved_at', '')}"
#                 )

#                 print(
#                     f"Tags: "
#                     f"{raw_metadata.get('metadata_tags', [])}"
#                 )

#                 print("---")

#         else:

#             print(
#                 f"Error: {response.status_code}"
#             )

#     else:

#         print(
#             "✗ arXiv request failed."
#         )

import requests
import xml.etree.ElementTree as ET
import json
import os
from datetime import datetime
import warnings

from paper_schema import StandardPaper

warnings.filterwarnings("ignore")

ARXIV_API_URL = "http://export.arxiv.org/api/query?"


def search_arxiv(query, max_results=5):
    """Search arXiv for papers."""

    params = {
        "search_query": f"all:{query}",
        "max_results": max_results,
        "sortBy": "relevance",
        "sortOrder": "descending"
    }

    print(f"Searching arXiv for: '{query}'...")

    try:
        response = requests.get(
            ARXIV_API_URL,
            params=params,
            verify=False,
            timeout=15
        )

        response.raise_for_status()

        return response

    except requests.RequestException as e:
        print(f"Error searching arXiv: {e}")
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
        # Parse XML
        root = ET.fromstring(xml_string)

        # arXiv XML namespaces
        namespace = {
            "atom": "http://www.w3.org/2005/Atom",
            "arxiv": "http://arxiv.org/schemas/atom"
        }

        # Find all paper entries
        entries = root.findall(
            "atom:entry",
            namespace
        )

        print(
            f"Found {len(entries)} papers in XML response."
        )

        # Generate metadata tags
        metadata_tags = generate_metadata_tags(query)

        for entry in entries:

            # =========================================
            # TITLE
            # =========================================

            title_element = entry.find(
                "atom:title",
                namespace
            )

            title = (
                title_element.text.strip()
                if title_element is not None
                and title_element.text
                else ""
            )

            # =========================================
            # ARXIV ID
            # =========================================

            id_element = entry.find(
                "atom:id",
                namespace
            )

            arxiv_id = ""

            if id_element is not None and id_element.text:

                arxiv_id = (
                    id_element.text
                    .split("/abs/")[-1]
                    .strip()
                )

            # =========================================
            # PUBLISHED DATE
            # =========================================

            published_element = entry.find(
                "atom:published",
                namespace
            )

            published = (
                published_element.text
                if published_element is not None
                else None
            )

            # =========================================
            # ABSTRACT
            # =========================================

            summary_element = entry.find(
                "atom:summary",
                namespace
            )

            summary = (
                summary_element.text.strip()
                if summary_element is not None
                and summary_element.text
                else ""
            )

            # =========================================
            # AUTHORS
            # =========================================

            authors = []

            for author in entry.findall(
                "atom:author",
                namespace
            ):

                name_element = author.find(
                    "atom:name",
                    namespace
                )

                if (
                    name_element is not None
                    and name_element.text
                ):
                    authors.append(
                        name_element.text.strip()
                    )

            # =========================================
            # PDF URL
            # =========================================

            pdf_url = None

            for link in entry.findall(
                "atom:link",
                namespace
            ):

                if link.get("title") == "pdf":

                    pdf_url = link.get("href")

                    break

            # =========================================
            # YEAR
            # =========================================

            year = None

            if published:

                try:

                    year = int(
                        published.split("-")[0]
                    )

                except (
                    ValueError,
                    IndexError
                ):

                    year = None

            # =========================================
            # RAW METADATA
            # =========================================

            raw_metadata = {
                "published_date": published,
                "metadata_tags": metadata_tags
            }

            # =========================================
            # CREATE STANDARD PAPER
            # =========================================

            paper = StandardPaper(

                arxiv_id=arxiv_id,

                title=title,

                authors=authors,

                abstract=summary,

                year=year,

                pdf_url=pdf_url,

                source="arXiv",

                # This is when OUR SYSTEM
                # retrieved the paper
                retrieved_at=datetime.now().isoformat(),

                # Publication date stays here
                raw_metadata=raw_metadata
            )

            papers.append(paper)

        return papers

    except ET.ParseError as e:

        print(
            f"Error parsing arXiv XML: {e}"
        )

        return []

    except Exception as e:

        print(
            f"Error processing arXiv papers: {e}"
        )

        return []


class ArxivRetriever:
    """
    PATCHED by Malavika: class wrapper around the module-level functions
    above. unified_retriever.py does `from arxiv_retriever import
    ArxivRetriever` and calls `self.arxiv_retriever.search_arxiv(query,
    max_results)` as an instance method - but this file only had bare
    functions, so that import was crashing with ImportError. This wraps
    the existing search_arxiv() + parse_papers_from_xml() into the class
    shape unified_retriever.py expects, matching CrossRefRetriever and
    SemanticScholarRetriever's interface (a .search_x(query, max_results)
    method returning List[StandardPaper]).
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

        # Pydantic v2
        if hasattr(
            paper,
            "model_dump"
        ):

            result.append(
                paper.model_dump()
            )

        # Pydantic v1
        elif hasattr(
            paper,
            "dict"
        ):

            result.append(
                paper.dict()
            )

        # Normal Python object
        elif hasattr(
            paper,
            "__dict__"
        ):

            result.append(
                paper.__dict__
            )

        # Already a dictionary
        elif isinstance(
            paper,
            dict
        ):

            result.append(paper)

        else:

            raise TypeError(
                f"Unsupported paper type: {type(paper)}"
            )

    return result


def save_papers_to_json(
    papers,
    filename="papers.json"
):
    """Save StandardPaper objects to JSON."""

    filepath = f"backend/data/{filename}"

    # Create directory if it doesn't exist
    os.makedirs(
        "backend/data",
        exist_ok=True
    )

    try:

        # Convert StandardPaper objects
        # to dictionaries
        paper_dicts = standard_papers_to_dicts(
            papers
        )

        # Save JSON
        with open(
            filepath,
            "w",
            encoding="utf-8"
        ) as f:

            json.dump(
                paper_dicts,
                f,
                indent=2,
                ensure_ascii=False
            )

        print(
            f"✓ Saved {len(papers)} papers "
            f"to {filepath}"
        )

    except Exception as e:

        print(
            f"Error saving papers to JSON: {e}"
        )


# ============================================================
# MAIN EXECUTION
# ============================================================

if __name__ == "__main__":

    query = "transformers"

    # =========================================
    # STEP 1: Search arXiv
    # =========================================

    response = search_arxiv(
        query,
        max_results=3
    )

    if response is not None:

        print(
            f"Status Code: {response.status_code}"
        )

        if response.status_code == 200:

            # =========================================
            # STEP 2: Parse XML
            # =========================================

            papers = parse_papers_from_xml(
                response.text,
                query
            )

            # =========================================
            # STEP 3: Save papers
            # =========================================

            save_papers_to_json(
                papers
            )

            # =========================================
            # STEP 4: Print results
            # =========================================

            print(
                f"\n✓ Retrieved "
                f"{len(papers)} papers:\n"
            )

            for paper in papers:

                # Convert to dictionary
                if hasattr(
                    paper,
                    "model_dump"
                ):

                    paper_data = (
                        paper.model_dump()
                    )

                elif hasattr(
                    paper,
                    "dict"
                ):

                    paper_data = (
                        paper.dict()
                    )

                else:

                    paper_data = (
                        paper.__dict__
                    )

                print(
                    f"Title: "
                    f"{paper_data.get('title', '')}"
                )

                print(
                    f"Authors: "
                    f"{', '.join(paper_data.get('authors', []))}"
                )

                print(
                    f"arXiv ID: "
                    f"{paper_data.get('arxiv_id', '')}"
                )

                print(
                    f"Year: "
                    f"{paper_data.get('year', '')}"
                )

                print(
                    f"PDF: "
                    f"{paper_data.get('pdf_url', '')}"
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
                    f"Tags: "
                    f"{raw_metadata.get('metadata_tags', [])}"
                )

                print("---")

        else:

            print(
                f"Error: {response.status_code}"
            )

    else:

        print(
            "✗ arXiv request failed."
        )