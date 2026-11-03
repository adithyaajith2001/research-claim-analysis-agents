"""
arxiv_retriever.py

Searches arXiv and converts every retrieved paper into the project's
StandardPaper object before returning it to the unified retriever.

The unified retriever expects objects that implement get_primary_id().
"""

import json
import os
import warnings
import xml.etree.ElementTree as ET
from datetime import datetime

import requests

from paper_schema import StandardPaper

warnings.filterwarnings("ignore")


# ============================================================
# ARXIV API
# ============================================================

ARXIV_API_URLS = [
    "https://export.arxiv.org/api/query",
    "https://arxiv.org/api/query",
]


# ============================================================
# BASE DIRECTORY
# ============================================================

BASE_DIR = os.path.dirname(
    os.path.abspath(__file__)
)

DATA_DIR = os.path.join(
    BASE_DIR,
    "data"
)

os.makedirs(
    DATA_DIR,
    exist_ok=True
)


# ============================================================
# SEARCH ARXIV
# ============================================================

def search_arxiv(
    query,
    max_results=5
):
    """
    Search arXiv and return the raw requests.Response object.
    """

    try:
        max_results = int(max_results)
    except (ValueError, TypeError):
        max_results = 5

    max_results = max(
        1,
        min(max_results, 20)
    )

    params = {
        "search_query": f"all:{query}",
        "start": 0,
        "max_results": max_results,
        "sortBy": "relevance",
        "sortOrder": "descending",
    }

    print()
    print("=" * 70)
    print("ARXIV SEARCH")
    print("=" * 70)
    print(f"Query: {query}")
    print(f"Maximum results: {max_results}")

    last_error = None

    for api_url in ARXIV_API_URLS:

        print()
        print("Trying endpoint:")
        print(api_url)

        try:

            response = requests.get(
                api_url,
                params=params,
                timeout=30,
                verify=False,
                headers={
                    "User-Agent":
                        "ResearchClaimAI/1.0"
                },
            )

            print(
                "HTTP status:",
                response.status_code
            )

            if response.status_code == 200:

                print(
                    "✓ arXiv request successful."
                )
                print("=" * 70)

                return response

            print(
                "✗ arXiv returned HTTP",
                response.status_code
            )

            print(
                "Response:",
                response.text[:300]
            )

        except requests.exceptions.SSLError as error:

            last_error = error

            print(
                "✗ SSL error:"
            )
            print(error)

        except requests.exceptions.Timeout as error:

            last_error = error

            print(
                "✗ Request timed out."
            )
            print(error)

        except requests.exceptions.ConnectionError as error:

            last_error = error

            print(
                "✗ Connection error:"
            )
            print(error)

        except requests.exceptions.RequestException as error:

            last_error = error

            print(
                "✗ Request error:"
            )
            print(error)

        except Exception as error:

            last_error = error

            print(
                "✗ Unexpected error:"
            )
            print(error)

    print()
    print("=" * 70)
    print("ARXIV SEARCH FAILED")
    print("=" * 70)

    if last_error:
        print(
            "Last error:",
            last_error
        )

    print("=" * 70)

    return None


# ============================================================
# METADATA TAGS
# ============================================================

def generate_metadata_tags(query):

    tag_mapping = {

        "transformers": [
            "transformers",
            "attention",
            "nlp",
            "deep-learning",
        ],

        "neural networks": [
            "neural-networks",
            "deep-learning",
            "ml",
            "ai",
        ],

        "machine learning": [
            "machine-learning",
            "ml",
            "ai",
            "algorithms",
        ],

        "deep learning": [
            "deep-learning",
            "neural-networks",
            "cnn",
            "rnn",
        ],

        "nlp": [
            "nlp",
            "transformers",
            "language-models",
            "text-processing",
        ],

        "computer vision": [
            "computer-vision",
            "cnn",
            "image-processing",
            "detection",
        ],

        "climate change": [
            "climate-change",
            "climate",
            "environment",
            "global-warming",
        ],

        "air quality": [
            "air-quality",
            "pollution",
            "environment",
            "atmosphere",
        ],

        "artificial intelligence": [
            "artificial-intelligence",
            "ai",
            "machine-learning",
            "deep-learning",
        ],

        "healthcare": [
            "healthcare",
            "medical",
            "ai",
            "medicine",
        ],

        "blockchain": [
            "blockchain",
            "distributed-ledger",
            "security",
            "decentralization",
        ],
    }

    query_lower = str(
        query
    ).lower()

    for key, tags in tag_mapping.items():

        if key in query_lower:
            return tags

    words = query_lower.split()

    tags = []

    for word in words:

        cleaned = word.strip(
            ".,!?;:"
        )

        if cleaned:
            tags.append(
                cleaned.replace(
                    " ",
                    "-"
                )
            )

    return (
        tags
        if tags
        else ["research"]
    )


# ============================================================
# XML TEXT HELPER
# ============================================================

def get_element_text(
    element,
    namespace,
    tag
):

    child = element.find(
        tag,
        namespace
    )

    if (
        child is not None
        and child.text
    ):
        return child.text.strip()

    return ""


# ============================================================
# PARSE ARXIV XML
# ============================================================

def parse_papers_from_xml(
    xml_string,
    query
):
    """
    Parse arXiv XML and return List[StandardPaper].

    IMPORTANT:
    The older implementation returned plain dictionaries.
    UnifiedPaperRetriever now uses StandardPaper.get_primary_id(),
    so returning dictionaries caused:

        'dict' object has no attribute 'get_primary_id'

    This function now creates StandardPaper objects directly.
    """

    papers = []

    if xml_string is None:

        print(
            "ERROR: XML response is None."
        )

        return []

    if hasattr(
        xml_string,
        "text"
    ):

        xml_string = xml_string.text

    if not isinstance(
        xml_string,
        (str, bytes)
    ):

        print(
            "ERROR: Invalid XML type:",
            type(xml_string)
        )

        return []

    if not xml_string:

        print(
            "ERROR: Empty XML response."
        )

        return []

    try:

        root = ET.fromstring(
            xml_string
        )

    except ET.ParseError as error:

        print(
            "ERROR parsing arXiv XML:",
            error
        )

        return []

    except Exception as error:

        print(
            "ERROR reading arXiv response:",
            error
        )

        return []

    namespace = {
        "atom":
            "http://www.w3.org/2005/Atom",
        "arxiv":
            "http://arxiv.org/schemas/atom",
    }

    entries = root.findall(
        "atom:entry",
        namespace
    )

    print(
        f"Found {len(entries)} papers "
        "in XML response."
    )

    metadata_tags = generate_metadata_tags(
        query
    )

    for index, entry in enumerate(
        entries,
        start=1
    ):

        try:

            # ------------------------------------------------
            # TITLE
            # ------------------------------------------------

            title = get_element_text(
                entry,
                namespace,
                "atom:title"
            )

            title = " ".join(
                title.split()
            )

            # ------------------------------------------------
            # ARXIV ID
            # ------------------------------------------------

            arxiv_id = get_element_text(
                entry,
                namespace,
                "atom:id"
            )

            if "/abs/" in arxiv_id:

                arxiv_id = (
                    arxiv_id
                    .split("/abs/")[-1]
                )

            arxiv_id = arxiv_id.strip()

            # ------------------------------------------------
            # ABSTRACT
            # ------------------------------------------------

            abstract = get_element_text(
                entry,
                namespace,
                "atom:summary"
            )

            abstract = " ".join(
                abstract.split()
            )

            # ------------------------------------------------
            # AUTHORS
            # ------------------------------------------------

            authors = []

            author_elements = entry.findall(
                "atom:author",
                namespace
            )

            for author in author_elements:

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

            # ------------------------------------------------
            # DATES
            # ------------------------------------------------

            published = get_element_text(
                entry,
                namespace,
                "atom:published"
            )

            updated = get_element_text(
                entry,
                namespace,
                "atom:updated"
            )

            year = None

            if published:

                try:
                    year = int(
                        published[:4]
                    )

                except (
                    ValueError,
                    IndexError
                ):
                    year = None

            # ------------------------------------------------
            # LINKS
            # ------------------------------------------------

            pdf_url = ""
            abs_url = ""

            for link in entry.findall(
                "atom:link",
                namespace
            ):

                href = link.get(
                    "href"
                )

                link_title = link.get(
                    "title"
                )

                link_type = link.get(
                    "type"
                )

                if not href:
                    continue

                if (
                    link_title == "pdf"
                    or link_type ==
                    "application/pdf"
                ):

                    pdf_url = href

                if (
                    link_title == "alternate"
                    or link_type ==
                    "text/html"
                ):

                    if "/abs/" in href:
                        abs_url = href

            # ------------------------------------------------
            # FALLBACK URLS
            # ------------------------------------------------

            if arxiv_id:

                if not abs_url:

                    abs_url = (
                        "https://arxiv.org/abs/"
                        f"{arxiv_id}"
                    )

                if not pdf_url:

                    pdf_url = (
                        "https://arxiv.org/pdf/"
                        f"{arxiv_id}"
                    )

            # ------------------------------------------------
            # STANDARD PAPER OBJECT
            # ------------------------------------------------

            paper = StandardPaper(

                arxiv_id=arxiv_id,

                title=title,

                authors=authors,

                abstract=abstract,

                year=year,

                pdf_url=pdf_url,

                source="arXiv",

                retrieved_at=(
                    datetime.now().isoformat()
                ),

                raw_metadata={
                    "published_date":
                        published,

                    "updated_date":
                        updated,

                    "metadata_tags":
                        metadata_tags,

                    "raw_text":
                        "",

                    "text_length":
                        0,
                },
            )

            papers.append(
                paper
            )

            print(
                f"✓ Paper {index}: "
                f"{title[:100]}"
            )

        except Exception as error:

            print(
                f"✗ Error processing paper "
                f"{index}: {error}"
            )

            continue

    print()

    print(
        f"Successfully parsed "
        f"{len(papers)} papers."
    )

    return papers


# ============================================================
# SAVE PAPERS
# ============================================================

def standard_papers_to_dicts(
    papers
):
    """
    Convert StandardPaper objects or dictionaries
    to JSON-safe dictionaries.
    """

    result = []

    for paper in papers:

        if isinstance(
            paper,
            dict
        ):

            result.append(
                paper
            )

        elif hasattr(
            paper,
            "model_dump"
        ):

            result.append(
                paper.model_dump()
            )

        elif hasattr(
            paper,
            "dict"
        ):

            result.append(
                paper.dict()
            )

        elif hasattr(
            paper,
            "to_dict"
        ):

            result.append(
                paper.to_dict()
            )

        elif hasattr(
            paper,
            "__dict__"
        ):

            result.append(
                paper.__dict__
            )

        else:

            raise TypeError(
                "Unsupported paper type: "
                f"{type(paper)}"
            )

    return result


def save_papers_to_json(
    papers,
    filename="papers.json"
):
    """
    Save papers relative to retrievers/data.
    """

    filepath = os.path.join(
        DATA_DIR,
        filename
    )

    try:

        paper_dicts = (
            standard_papers_to_dicts(
                papers
            )
        )

        with open(
            filepath,
            "w",
            encoding="utf-8"
        ) as file:

            json.dump(
                paper_dicts,
                file,
                indent=2,
                ensure_ascii=False
            )

        print()
        print(
            f"✓ Saved {len(paper_dicts)} papers"
        )

        print(
            f"Location: {filepath}"
        )

        return filepath

    except Exception as error:

        print(
            "ERROR saving papers:",
            error
        )

        return None


# ============================================================
# CLASS WRAPPER
# ============================================================

class ArxivRetriever:
    """
    Adapter expected by UnifiedPaperRetriever.

    Always returns StandardPaper objects.
    """

    def search_arxiv(
        self,
        query,
        max_results=5
    ):

        response = search_arxiv(
            query,
            max_results
        )

        if (
            response is None
            or response.status_code != 200
        ):

            return []

        return parse_papers_from_xml(
            response.text,
            query
        )


# ============================================================
# TEST
# ============================================================

if __name__ == "__main__":

    print()
    print("=" * 70)
    print(
        "ResearchClaimAI - arXiv Retriever Test"
    )
    print("=" * 70)

    test_query = "climate change"
    test_max_results = 5

    response = search_arxiv(
        test_query,
        test_max_results
    )

    if response is None:

        print()
        print(
            "✗ arXiv request failed."
        )

    else:

        papers = parse_papers_from_xml(
            response.text,
            test_query
        )

        save_papers_to_json(
            papers
        )

        print()
        print(
            f"Retrieved {len(papers)} papers."
        )

        for paper in papers:

            print()
            print("-" * 70)

            print(
                "Title:",
                getattr(
                    paper,
                    "title",
                    ""
                )
            )

            print(
                "Authors:",
                ", ".join(
                    getattr(
                        paper,
                        "authors",
                        []
                    )
                )
            )

            print(
                "Year:",
                getattr(
                    paper,
                    "year",
                    None
                )
            )

            print(
                "arXiv ID:",
                getattr(
                    paper,
                    "arxiv_id",
                    ""
                )
            )

            print(
                "Abstract URL:",
                getattr(
                    paper,
                    "abs_url",
                    ""
                )
            )

            print(
                "PDF URL:",
                getattr(
                    paper,
                    "pdf_url",
                    ""
                )
            )

        print()
        print("=" * 70)
        print("TEST COMPLETED")
        print("=" * 70)
