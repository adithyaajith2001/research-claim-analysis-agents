"""
retrieval_adapter.py

WHAT:
    Normalizes UnifiedPaperRetriever output into the exact paper-dict
    shape required by the ResearchClaimAI pipeline.

UPDATED:
    The adapter now enriches each retrieved paper with full PDF text
    using pdf_processor_v2.PDFProcessor before normalization.

PIPELINE:

    UnifiedPaperRetriever
            ↓
    raw StandardPaper / dict
            ↓
    PDFProcessor
            ↓
    raw_metadata["raw_text"]
            ↓
    normalize_paper()
            ↓
    {
        "id": str,
        "title": str,
        "authors": str,
        "year": int | None,
        "source": str,
        "source_url": str,
        "citation_count": int,
        "abstract": str,
        "full_text": str
    }

FULL TEXT RULE:

    1. Use extracted PDF text when available.
    2. Otherwise use existing full_text/raw_text.
    3. Otherwise fall back to abstract.

This allows the claim extraction agent to see actual paper text
instead of only the abstract whenever PDF extraction succeeds.
"""

import re
import html
import urllib.parse

try:
    import requests
except ImportError:
    requests = None

from typing import (
    Dict,
    List,
    Optional,
    Union,
    Any,
    Set,
    Tuple
)

from datetime import datetime


# ============================================================
# FULL-TEXT FALLBACK CONFIGURATION
# ============================================================

LANDING_PAGE_TIMEOUT = 20
MAX_LANDING_PAGE_BYTES = 750_000
MAX_PDF_CANDIDATES = 8

# Text shorter than this is treated as insufficient to prove that a paper
# already has reliable full text. This lets the adapter retry PDF discovery
# for papers that only contain short abstracts or snippets.
MIN_TRUSTED_EXISTING_FULL_TEXT_CHARS = 4000

PDF_REQUEST_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/153.0 Safari/537.36 ResearchClaimAI/1.0"
    )
}


# ============================================================
# STANDARD PAPER
# ============================================================

try:

    from paper_schema import StandardPaper

except ImportError:

    StandardPaper = None


# ============================================================
# PDF PROCESSOR
# ============================================================

try:

    from pdf_processor_v2 import PDFProcessor

except ImportError:

    PDFProcessor = None


# ============================================================
# CONVERT RAW OBJECT TO DICT
# ============================================================

def _as_dict(
    raw: Union["StandardPaper", Dict]
) -> Dict:
    """
    Accept either:

        StandardPaper object
    or:
        plain dictionary

    and return a dictionary representation.
    """

    # --------------------------------------------------------
    # StandardPaper
    # --------------------------------------------------------

    if (
        StandardPaper is not None
        and isinstance(
            raw,
            StandardPaper
        )
    ):

        if hasattr(
            raw,
            "model_dump"
        ):

            return raw.model_dump()

        if hasattr(
            raw,
            "to_dict"
        ):

            return raw.to_dict()

        if hasattr(
            raw,
            "dict"
        ):

            return raw.dict()


    # --------------------------------------------------------
    # Object with to_dict()
    # --------------------------------------------------------

    if hasattr(
        raw,
        "to_dict"
    ):

        return raw.to_dict()


    # --------------------------------------------------------
    # Object with model_dump()
    # --------------------------------------------------------

    if hasattr(
        raw,
        "model_dump"
    ):

        return raw.model_dump()


    # --------------------------------------------------------
    # Object with dict()
    # --------------------------------------------------------

    if hasattr(
        raw,
        "dict"
    ):

        return raw.dict()


    # --------------------------------------------------------
    # Normal Python object
    # --------------------------------------------------------

    if (
        hasattr(
            raw,
            "__dict__"
        )
        and not isinstance(
            raw,
            dict
        )
    ):

        return dict(
            raw.__dict__
        )


    # --------------------------------------------------------
    # Already a dictionary
    # --------------------------------------------------------

    return dict(
        raw
    )


# ============================================================
# PAPER ID
# ============================================================

def _make_paper_id(
    raw: Dict
) -> Optional[str]:
    """
    Prefer identifiers in this order:

        arxiv_id
        doi
        semantic_scholar_id
        id
    """

    for key in (
        "arxiv_id",
        "doi",
        "semantic_scholar_id",
        "id"
    ):

        value = raw.get(
            key
        )

        if value is not None and str(
            value
        ).strip():

            return str(
                value
            )

    return None


# ============================================================
# SOURCE URL
# ============================================================

def _make_source_url(
    raw: Dict,
    paper_id: str
) -> str:
    """
    Build a source URL for the paper.
    """

    if raw.get(
        "abs_url"
    ):

        return str(
            raw["abs_url"]
        )


    if raw.get(
        "source_url"
    ):

        return str(
            raw["source_url"]
        )


    if raw.get(
        "url"
    ):

        return str(
            raw["url"]
        )


    if raw.get(
        "pdf_url"
    ):

        return str(
            raw["pdf_url"]
        )


    if raw.get(
        "arxiv_id"
    ):

        return (
            "https://arxiv.org/abs/"
            f"{raw['arxiv_id']}"
        )


    if raw.get(
        "doi"
    ):

        return (
            "https://doi.org/"
            f"{raw['doi']}"
        )


    return ""


# ============================================================
# CLEAN ABSTRACT
# ============================================================

def _clean_abstract(
    abstract: str
) -> str:
    """
    Remove XML/JATS tags from abstracts.
    """

    if not abstract:

        return ""


    return re.sub(
        r"<[^>]+>",
        " ",
        str(
            abstract
        )
    ).strip()


# ============================================================
# EXTRACT YEAR
# ============================================================

def _extract_year(
    raw: Dict
) -> Optional[int]:
    """
    Extract publication year from either:

        year
    or:
        published_date
    """

    if raw.get(
        "year"
    ):

        try:

            return int(
                raw["year"]
            )

        except (
            TypeError,
            ValueError
        ):

            pass


    published = raw.get(
        "published_date"
    )


    if published:

        try:

            return datetime.fromisoformat(
                str(
                    published
                ).replace(
                    "Z",
                    "+00:00"
                )
            ).year

        except (
            ValueError,
            TypeError
        ):

            pass


    return None


# ============================================================
# NORMALIZE AUTHORS
# ============================================================

def _normalize_authors(
    raw: Dict
) -> str:
    """
    Normalize author representation into one comma-separated string.
    """

    authors = raw.get(
        "authors",
        []
    )


    # List
    if isinstance(
        authors,
        list
    ):

        cleaned = []

        for author in authors:

            if isinstance(
                author,
                dict
            ):

                name = (
                    author.get(
                        "name"
                    )
                    or author.get(
                        "author"
                    )
                    or ""
                )

            else:

                name = str(
                    author
                )


            name = name.strip()


            if name:

                cleaned.append(
                    name
                )


        return ", ".join(
            cleaned
        )


    # Existing string with pipe separators
    if isinstance(
        authors,
        str
    ):

        if "|" in authors:

            return ", ".join(
                part.strip()
                for part in authors.split("|")
                if part.strip()
            )


        return authors.strip()


    return str(
        authors or ""
    )


# ============================================================
# NORMALIZE TITLE
# ============================================================

def _normalize_title(
    title: str
) -> str:
    """
    Normalized title used for duplicate detection.
    """

    return re.sub(
        r"[^\w\s]",
        "",
        (
            title or ""
        ).lower()
    ).strip()


# ============================================================
# PDF ENRICHMENT HELPERS
# ============================================================

def _get_raw_metadata(
    raw
) -> Dict:
    """
    Return the raw_metadata dictionary for either a StandardPaper
    object or a plain dictionary.
    """

    if (
        StandardPaper is not None
        and isinstance(
            raw,
            StandardPaper
        )
    ):

        metadata = getattr(
            raw,
            "raw_metadata",
            {}
        )

        if isinstance(
            metadata,
            dict
        ):

            return metadata

        return {}

    if isinstance(
        raw,
        dict
    ):

        metadata = raw.get(
            "raw_metadata",
            {}
        )

        if isinstance(
            metadata,
            dict
        ):

            return metadata

    return {}


def _set_raw_metadata(
    raw,
    metadata: Dict
) -> None:
    """
    Persist raw_metadata safely.
    """

    if (
        StandardPaper is not None
        and isinstance(
            raw,
            StandardPaper
        )
    ):

        try:

            setattr(
                raw,
                "raw_metadata",
                metadata
            )

        except Exception:
            pass

        return

    if isinstance(
        raw,
        dict
    ):

        raw[
            "raw_metadata"
        ] = metadata


def _get_existing_text(
    raw
) -> str:
    """
    Get any already-available text without treating an empty
    value as usable.
    """

    metadata = _get_raw_metadata(
        raw
    )

    metadata_text = metadata.get(
        "raw_text",
        ""
    )

    if (
        metadata_text
        and str(metadata_text).strip()
    ):

        return str(
            metadata_text
        ).strip()

    if isinstance(
        raw,
        dict
    ):

        for key in (
            "full_text",
            "raw_text",
        ):

            value = raw.get(
                key,
                ""
            )

            if (
                value
                and str(value).strip()
            ):

                return str(
                    value
                ).strip()

    else:

        for key in (
            "full_text",
            "raw_text",
        ):

            try:

                value = getattr(
                    raw,
                    key,
                    ""
                )

                if (
                    value
                    and str(value).strip()
                ):

                    return str(
                        value
                    ).strip()

            except Exception:
                continue

    return ""


def _add_url(
    value: Any,
    candidates: List[str]
) -> None:
    """
    Add a normalized HTTP(S) URL if it is not already present.
    """

    if not value:
        return

    value = html.unescape(
        str(value).strip()
    )

    if not value:
        return

    if not (
        value.startswith("http://")
        or value.startswith("https://")
    ):

        return

    # Remove fragment identifiers.
    value = value.split(
        "#",
        1
    )[0]

    if value not in candidates:

        candidates.append(
            value
        )


def _collect_urls_recursively(
    value: Any,
    found: List[str],
    visited: Optional[Set[int]] = None
) -> None:
    """
    Recursively inspect nested metadata for HTTP(S) URLs.
    """

    if value is None:
        return

    if visited is None:
        visited = set()

    if isinstance(
        value,
        str
    ):

        text = html.unescape(
            value.strip()
        )

        if (
            text.startswith("http://")
            or text.startswith("https://")
        ):

            _add_url(
                text,
                found
            )

        # URLs embedded in JSON/HTML strings.
        for match in re.findall(
            r"https?://[^\s\"'<>]+",
            text
        ):

            _add_url(
                match.rstrip(
                    ".,);]}>'\""
                ),
                found
            )

        return

    if isinstance(
        value,
        dict
    ):

        object_id = id(
            value
        )

        if object_id in visited:
            return

        visited.add(
            object_id
        )

        for nested_value in value.values():

            _collect_urls_recursively(
                nested_value,
                found,
                visited
            )

        return

    if isinstance(
        value,
        (list, tuple, set)
    ):

        object_id = id(
            value
        )

        if object_id in visited:
            return

        visited.add(
            object_id
        )

        for nested_value in value:

            _collect_urls_recursively(
                nested_value,
                found,
                visited
            )


def _normalize_candidate_url(
    url: str
) -> str:
    """
    Convert common arXiv abstract/html URLs to their PDF endpoint.
    Other URLs are returned unchanged.
    """

    if not url:
        return ""

    url = html.unescape(
        str(url).strip()
    )

    if not (
        url.startswith("http://")
        or url.startswith("https://")
    ):

        return ""

    arxiv_match = re.search(
        r"arxiv\.org/(?:abs|html)/([^/?#]+)",
        url,
        flags=re.IGNORECASE
    )

    if arxiv_match:

        arxiv_id = arxiv_match.group(
            1
        ).strip()

        return (
            "https://arxiv.org/pdf/"
            f"{arxiv_id}"
        )

    return url


def _collect_pdf_candidates(
    raw
) -> List[str]:
    """
    Collect explicit PDF/open-access URLs plus landing pages.

    The order is intentional:
        1. explicit PDF URLs
        2. arXiv PDF
        3. open-access/nested metadata
        4. source/abstract/landing URLs
        5. DOI landing page
    """

    raw_dict = _as_dict(
        raw
    )

    candidates = []

    def add_candidate(
        value
    ):

        normalized = _normalize_candidate_url(
            value
        )

        if normalized and normalized not in candidates:

            candidates.append(
                normalized
            )

    # Explicit fields.
    for key in (
        "pdf_url",
        "pdf",
        "pdfUrl",
        "open_access_pdf",
        "openAccessPdf",
        "full_text_url",
        "fullTextUrl",
    ):

        value = raw_dict.get(
            key
        )

        if isinstance(
            value,
            dict
        ):

            for nested_key in (
                "url",
                "href",
                "link",
            ):

                add_candidate(
                    value.get(
                        nested_key
                    )
                )

        else:

            add_candidate(
                value
            )

    # Strong arXiv fallback.
    arxiv_id = (
        raw_dict.get(
            "arxiv_id"
        )
        or raw_dict.get(
            "arXiv_id"
        )
    )

    if arxiv_id:

        add_candidate(
            "https://arxiv.org/pdf/"
            f"{str(arxiv_id).strip()}"
        )

    # Existing source/landing links.
    for key in (
        "source_url",
        "url",
        "abs_url",
    ):

        add_candidate(
            raw_dict.get(
                key
            )
        )

    # DOI landing page.
    doi = raw_dict.get(
        "doi"
    )

    if doi:

        doi_text = str(
            doi
        ).strip()

        if doi_text.startswith(
            "http://"
        ) or doi_text.startswith(
            "https://"
        ):

            add_candidate(
                doi_text
            )

        else:

            add_candidate(
                "https://doi.org/"
                f"{doi_text.lstrip('/')}"
            )

    # Search nested metadata for open-access links.
    nested_values = []

    for key in (
        "links",
        "link",
        "open_access",
        "openAccess",
        "raw_metadata",
        "metadata",
    ):

        if key in raw_dict:

            nested_values.append(
                raw_dict.get(
                    key
                )
            )

    nested_urls = []

    for value in nested_values:

        _collect_urls_recursively(
            value,
            nested_urls
        )

    for url in nested_urls:

        add_candidate(
            url
        )

    return candidates[
        :MAX_PDF_CANDIDATES
    ]


def _looks_like_direct_pdf_url(
    url: str
) -> bool:
    """
    Identify URLs that likely point directly to a PDF.
    """

    lowered = str(
        url or ""
    ).lower()

    parsed = urllib.parse.urlparse(
        lowered
    )

    path = parsed.path

    return (
        path.endswith(
            ".pdf"
        )
        or "/pdf" in path
        or "download=pdf" in lowered
        or "format=pdf" in lowered
        or "type=pdf" in lowered
    )


def _discover_pdf_urls_from_landing_page(
    landing_url: str
) -> List[str]:
    """
    Fetch a landing page and discover direct PDF URLs.

    This handles common scholarly metadata such as:
        citation_pdf_url
    as well as href/src links containing PDF/download markers.
    """

    if (
        not landing_url
        or requests is None
    ):

        return []

    try:

        response = requests.get(
            landing_url,
            timeout=LANDING_PAGE_TIMEOUT,
            verify=False,
            headers=PDF_REQUEST_HEADERS,
            allow_redirects=True,
        )

        if response.status_code >= 400:

            print(
                f"  ⚠ Landing page HTTP "
                f"{response.status_code}"
            )

            return []

        content_type = str(
            response.headers.get(
                "Content-Type",
                ""
            )
        ).lower()

        # Do not parse actual PDF bytes as HTML.
        if (
            "pdf" in content_type
            and "html" not in content_type
        ):

            return [
                response.url
            ]

        if (
            "html" not in content_type
            and "text/" not in content_type
        ):

            return []

        body = response.content[
            :MAX_LANDING_PAGE_BYTES
        ]

        page = body.decode(
            response.encoding
            or "utf-8",
            errors="ignore"
        )

        page = html.unescape(
            page
        )

        discovered = []

        def add_discovered(
            value
        ):

            if not value:
                return

            absolute = urllib.parse.urljoin(
                response.url,
                str(value).strip()
            )

            if not (
                absolute.startswith(
                    "http://"
                )
                or absolute.startswith(
                    "https://"
                )
            ):

                return

            absolute = absolute.split(
                "#",
                1
            )[0]

            if absolute not in discovered:

                discovered.append(
                    absolute
                )

        # Scholarly metadata.
        citation_pattern = re.compile(
            r'<meta[^>]+name=["\']citation_pdf_url["\'][^>]+content=["\']([^"\']+)',
            flags=re.IGNORECASE
        )

        for match in citation_pattern.finditer(
            page
        ):

            add_discovered(
                match.group(
                    1
                )
            )

        # Reverse attribute order as well.
        citation_pattern_reverse = re.compile(
            r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+name=["\']citation_pdf_url["\']',
            flags=re.IGNORECASE
        )

        for match in citation_pattern_reverse.finditer(
            page
        ):

            add_discovered(
                match.group(
                    1
                )
            )

        # href/src links.
        attr_pattern = re.compile(
            r'(?:href|src)=["\']([^"\']+)["\']',
            flags=re.IGNORECASE
        )

        for match in attr_pattern.finditer(
            page
        ):

            value = match.group(
                1
            )

            lowered = value.lower()

            if (
                ".pdf" in lowered
                or "/pdf" in lowered
                or "pdf?" in lowered
                or (
                    "download" in lowered
                    and "pdf" in lowered
                )
            ):

                add_discovered(
                    value
                )

        # Absolute PDF URLs embedded in JSON/scripts.
        absolute_pdf_pattern = re.compile(
            r'https?://[^"\'<>\s]+?(?:\.pdf(?:\?[^"\'<>\s]*)?|/pdf[^"\'<>\s]*)',
            flags=re.IGNORECASE
        )

        for match in absolute_pdf_pattern.finditer(
            page
        ):

            add_discovered(
                match.group(
                    0
                )
            )

        return discovered[
            :MAX_PDF_CANDIDATES
        ]

    except Exception as error:

        print(
            "  ⚠ Landing-page PDF discovery failed: "
            f"{error}"
        )

        return []


def _download_and_extract_pdf(
    processor,
    pdf_url: str
) -> str:
    """
    Download a direct PDF and extract its text.
    """

    try:

        pdf_bytes = processor.download_pdf(
            pdf_url
        )

        if not pdf_bytes:

            return ""

        extracted = processor.extract_text(
            pdf_bytes,
            max_pages=None
        )

        if extracted:

            return str(
                extracted
            ).strip()

    except Exception as error:

        print(
            "  ⚠ PDF extraction attempt failed: "
            f"{error}"
        )

    return ""


def _try_pdf_or_landing_candidate(
    processor,
    candidate_url: str
) -> Tuple[str, str]:
    """
    Try one candidate.

    Returns:
        (text, successful_pdf_url)
    """

    if not candidate_url:

        return "", ""

    print(
        f"  ↳ Trying: {candidate_url[:140]}..."
    )

    if _looks_like_direct_pdf_url(
        candidate_url
    ):

        text = _download_and_extract_pdf(
            processor,
            candidate_url
        )

        if text:

            return (
                text,
                candidate_url
            )

        return "", ""

    discovered_urls = (
        _discover_pdf_urls_from_landing_page(
            candidate_url
        )
    )

    for discovered_url in discovered_urls:

        print(
            f"  🔎 Discovered PDF: "
            f"{discovered_url[:140]}..."
        )

        text = _download_and_extract_pdf(
            processor,
            discovered_url
        )

        if text:

            return (
                text,
                discovered_url
            )

    return "", ""


def _store_full_text(
    raw,
    text: str,
    source_url: str
) -> None:
    """
    Store extracted PDF text with traceability metadata.
    """

    clean_text = str(
        text
    ).strip()

    metadata = _get_raw_metadata(
        raw
    )

    metadata[
        "raw_text"
    ] = clean_text

    metadata[
        "text_length"
    ] = len(
        clean_text
    )

    metadata[
        "pdf_text_extracted"
    ] = True

    metadata[
        "text_quality"
    ] = "pdf_full_text"

    metadata[
        "full_text_source"
    ] = source_url

    metadata[
        "full_text_retrieved_at"
    ] = datetime.now().isoformat()

    _set_raw_metadata(
        raw,
        metadata
    )

    if isinstance(
        raw,
        dict
    ):

        raw[
            "raw_text"
        ] = clean_text

        raw[
            "full_text"
        ] = clean_text

        raw[
            "text_length"
        ] = len(
            clean_text
        )

    else:

        for field in (
            "raw_text",
            "full_text",
        ):

            try:

                setattr(
                    raw,
                    field,
                    clean_text
                )

            except Exception:
                pass


# ============================================================
# PDF ENRICHMENT
# ============================================================

def enrich_paper_with_pdf_text(
    raw: Union["StandardPaper", Dict],
    processor=None
):
    """
    Enrich one paper with full PDF text using multiple fallback paths.

    Order:

        1. Reuse existing extracted text.
        2. Use PDFProcessor.process_paper() for StandardPaper.
        3. Try explicit PDF/open-access URLs.
        4. Try publisher/DOI landing pages and discover PDF links.
        5. Try arXiv PDF when arXiv ID exists.
        6. Preserve the existing abstract/full_text fallback.

    Failures are isolated to the individual paper.
    """

    if PDFProcessor is None:

        print(
            "⚠ PDFProcessor unavailable. "
            "Using existing paper text."
        )

        return raw

    if processor is None:

        processor = PDFProcessor(
            verify_ssl=False,
            max_pages=None
        )

    # --------------------------------------------------------
    # Reuse already extracted text
    # --------------------------------------------------------

    existing_text = _get_existing_text(
        raw
    )

    existing_metadata = _get_raw_metadata(
        raw
    )

    existing_quality = str(
        existing_metadata.get(
            "text_quality",
            ""
        )
        or ""
    ).lower().strip()

    # Reuse only trusted full text. Short abstract/snippet fallbacks should
    # NOT prevent the adapter from trying the PDF again.
    existing_text_is_trusted = (
        existing_quality == "pdf_full_text"
        or (
            existing_quality not in {
                "abstract_only",
                "snippet_only",
            }
            and len(existing_text) >=
            MIN_TRUSTED_EXISTING_FULL_TEXT_CHARS
        )
    )

    if (
        existing_text
        and existing_text_is_trusted
    ):

        if not existing_quality:

            existing_metadata[
                "text_quality"
            ] = "existing_text"

        _set_raw_metadata(
            raw,
            existing_metadata
        )

        print(
            f"✓ Existing trusted full text found: "
            f"{len(existing_text):,} characters"
        )

        return raw

    if existing_text:

        print(
            f"⚠ Existing text is short/fallback-only "
            f"({len(existing_text):,} characters). "
            "Trying PDF enrichment again."
        )

    # --------------------------------------------------------
    # StandardPaper primary processor path
    # --------------------------------------------------------

    target = raw

    if (
        StandardPaper is not None
        and isinstance(
            raw,
            StandardPaper
        )
    ):

        try:

            processed = processor.process_paper(
                raw,
                max_pages=None
            )

            processed_text = _get_existing_text(
                processed
            )

            processed_metadata = _get_raw_metadata(
                processed
            )

            processed_quality = str(
                processed_metadata.get(
                    "text_quality",
                    ""
                )
                or ""
            ).lower().strip()

            processed_text_is_trusted = (
                bool(processed_text)
                and (
                    processed_quality == "pdf_full_text"
                    or (
                        processed_quality not in {
                            "abstract_only",
                            "snippet_only",
                        }
                        and len(processed_text) >=
                        MIN_TRUSTED_EXISTING_FULL_TEXT_CHARS
                    )
                )
            )

            if processed_text_is_trusted:

                if not processed_quality:

                    processed_metadata[
                        "text_quality"
                    ] = "pdf_full_text"

                _set_raw_metadata(
                    processed,
                    processed_metadata
                )

                print(
                    f"✓ PDF enrichment successful: "
                    f"{len(processed_text):,} characters"
                )

                return processed

            if processed_text:

                print(
                    f"⚠ Primary processor returned only "
                    f"{len(processed_text):,} characters. "
                    "Trying alternate URLs."
                )

            target = (
                processed
                or raw
            )

            print(
                "⚠ Primary PDFProcessor path returned "
                "no full text; trying alternate URLs."
            )

        except Exception as error:

            print(
                "⚠ StandardPaper primary PDF enrichment failed:"
            )

            print(
                f"  {error}"
            )

            target = raw

    # --------------------------------------------------------
    # Alternate PDF / landing-page candidates
    # --------------------------------------------------------

    candidates = _collect_pdf_candidates(
        target
    )

    if candidates:

        print(
            f"✓ PDF fallback candidates found: "
            f"{len(candidates)}"
        )

    else:

        print(
            "⚠ No PDF fallback candidates found."
        )

    for index, candidate_url in enumerate(
        candidates,
        start=1
    ):

        if index > MAX_PDF_CANDIDATES:
            break

        try:

            extracted_text, successful_url = (
                _try_pdf_or_landing_candidate(
                    processor,
                    candidate_url
                )
            )

            if (
                extracted_text
                and successful_url
            ):

                _store_full_text(
                    target,
                    extracted_text,
                    successful_url
                )

                print(
                    f"✓ Alternate PDF enrichment successful: "
                    f"{len(extracted_text):,} characters"
                )

                return target

        except Exception as error:

            print(
                f"  ⚠ Candidate {index} failed: "
                f"{error}"
            )

    # --------------------------------------------------------
    # Abstract-only fallback
    # --------------------------------------------------------

    metadata = _get_raw_metadata(
        target
    )

    metadata[
        "pdf_text_extracted"
    ] = False

    metadata[
        "text_quality"
    ] = "abstract_only"

    metadata[
        "full_text_source"
    ] = ""

    _set_raw_metadata(
        target,
        metadata
    )

    print(
        "⚠ All PDF candidates failed. "
        "Retaining best available text/abstract fallback."
    )

    return target



# ============================================================
# NORMALIZE ONE PAPER
# ============================================================

def normalize_paper(
    raw: Union["StandardPaper", Dict]
) -> Optional[Dict]:
    """
    Convert one retrieved paper into the exact structure expected
    by the downstream pipeline.

    FULL TEXT PRIORITY:

        1. raw_metadata["raw_text"]
        2. full_text
        3. raw_text
        4. abstract
    """

    raw_dict = _as_dict(
        raw
    )


    # --------------------------------------------------------
    # Paper ID
    # --------------------------------------------------------

    paper_id = _make_paper_id(
        raw_dict
    )


    # --------------------------------------------------------
    # Raw metadata
    # --------------------------------------------------------

    raw_metadata = raw_dict.get(
        "raw_metadata"
    )


    if not isinstance(
        raw_metadata,
        dict
    ):

        raw_metadata = {}


    # --------------------------------------------------------
    # Full PDF text
    # --------------------------------------------------------

    full_text = (
        raw_metadata.get(
            "raw_text",
            ""
        )
        or raw_dict.get(
            "full_text",
            ""
        )
        or raw_dict.get(
            "raw_text",
            ""
        )
        or raw_dict.get(
            "abstract",
            ""
        )
        or ""
    )


    full_text = str(
        full_text
    ).strip()


    # --------------------------------------------------------
    # Abstract
    # --------------------------------------------------------

    abstract = _clean_abstract(
        raw_dict.get(
            "abstract",
            ""
        )
    )


    # --------------------------------------------------------
    # Reject unusable papers
    # --------------------------------------------------------

    if not paper_id:

        return None


    if not full_text:

        return None


    # --------------------------------------------------------
    # Return normalized paper
    # --------------------------------------------------------

    return {

        "id":
            paper_id,

        "title":
            (
                raw_dict.get(
                    "title",
                    ""
                )
                or ""
            ).strip(),

        "authors":
            _normalize_authors(
                raw_dict
            ),

        "year":
            _extract_year(
                raw_dict
            ),

        "source":
            raw_dict.get(
                "source",
                "Unknown"
            ),

        "source_url":
            _make_source_url(
                raw_dict,
                paper_id
            ),

        "citation_count":
            raw_dict.get(
                "citation_count",
                0
            ) or 0,

        "abstract":
            abstract,

        # IMPORTANT:
        # This is actual PDF text whenever extraction succeeded,
        # otherwise the best available fallback.
        "full_text":
            full_text,

        # Traceability for downstream diagnostics.
        "text_quality":
            raw_metadata.get(
                "text_quality",
                "unknown"
            ),

        "full_text_source":
            raw_metadata.get(
                "full_text_source",
                ""
            ),

    }


# ============================================================
# NORMALIZE + DEDUPLICATE
# ============================================================

def normalize_and_dedupe(
    raw_papers: List[Any]
) -> List[Dict]:
    """
    Enrich, normalize and deduplicate all retrieved papers.
    """

    result = []

    seen_titles = set()

    dropped_unusable = 0

    dropped_dupe = 0

    pdf_full_text_count = 0

    abstract_only_count = 0


    # --------------------------------------------------------
    # Create ONE processor for the complete batch
    # --------------------------------------------------------

    processor = None


    if PDFProcessor is not None:

        processor = PDFProcessor(
            verify_ssl=False,
            max_pages=None
        )


    print()
    print(
        "=" * 70
    )

    print(
        "ENRICHING PAPERS WITH FULL PDF TEXT"
    )

    print(
        "=" * 70
    )


    # ========================================================
    # PROCESS EACH PAPER
    # ========================================================

    for index, raw in enumerate(
        raw_papers,
        start=1
    ):

        print()
        print(
            f"[PDF {index}/{len(raw_papers)}]"
        )


        # ----------------------------------------------------
        # PDF enrichment
        # ----------------------------------------------------

        enriched = enrich_paper_with_pdf_text(
            raw,
            processor=processor
        )


        # ----------------------------------------------------
        # Normalize
        # ----------------------------------------------------

        norm = normalize_paper(
            enriched
        )


        if norm is None:

            dropped_unusable += 1

            print(
                "⚠ Paper dropped: "
                "no stable ID or usable text."
            )

            continue


        # ----------------------------------------------------
        # Duplicate title detection
        # ----------------------------------------------------

        title_key = _normalize_title(
            norm[
                "title"
            ]
        )


        if (
            title_key
            and title_key in seen_titles
        ):

            dropped_dupe += 1

            print(
                "⚠ Duplicate paper dropped: "
                f"{norm['title'][:80]}"
            )

            continue


        if title_key:

            seen_titles.add(
                title_key
            )


        # ----------------------------------------------------
        # Text-quality diagnostics
        # ----------------------------------------------------

        if norm.get(
            "text_quality"
        ) == "pdf_full_text":

            pdf_full_text_count += 1

        elif norm.get(
            "text_quality"
        ) == "abstract_only":

            abstract_only_count += 1


        # ----------------------------------------------------
        # Keep
        # ----------------------------------------------------

        result.append(
            norm
        )


        print(
            f"✓ Paper ready: "
            f"{norm['id']}"
        )

        print(
            f"  Title: "
            f"{norm['title'][:80]}"
        )

        print(
            f"  Full text: "
            f"{len(norm['full_text']):,} characters"
        )

        print(
            f"  Text quality: "
            f"{norm.get('text_quality', 'unknown')}"
        )

        if norm.get(
            "full_text_source"
        ):

            print(
                f"  Text source: "
                f"{norm['full_text_source'][:120]}"
            )


    # ========================================================
    # FINAL SUMMARY
    # ========================================================

    print()
    print(
        "=" * 70
    )

    print(
        "RETRIEVAL ADAPTER SUMMARY"
    )

    print(
        "=" * 70
    )

    print(
        f"Raw papers:       {len(raw_papers)}"
    )

    print(
        f"Usable papers:    {len(result)}"
    )

    print(
        f"Dropped unusable: {dropped_unusable}"
    )

    print(
        f"Dropped duplicate:{dropped_dupe}"
    )

    print(
        f"PDF full-text papers: {pdf_full_text_count}"
    )

    print(
        f"Abstract-only papers: {abstract_only_count}"
    )

    print(
        "=" * 70
    )


    return result


# ============================================================
# PIPELINE ENTRY POINT
# ============================================================

def get_pipeline_ready_papers(
    query: str,
    max_results: int = 10
) -> List[Dict]:
    """
    Retrieve papers from all configured sources and make them
    ready for the claim-extraction pipeline.
    """

    from unified_retriever import (
        UnifiedPaperRetriever
    )


    print()
    print(
        "=" * 70
    )

    print(
        f"SEARCHING PAPERS FOR: {query}"
    )

    print(
        "=" * 70
    )


    # --------------------------------------------------------
    # Retrieve
    # --------------------------------------------------------

    retriever = UnifiedPaperRetriever()


    raw_papers = retriever.search_all_sources(
        query,
        max_results=max_results
    )


    print()
    print(
        f"Retrieved raw papers: "
        f"{len(raw_papers)}"
    )


    # --------------------------------------------------------
    # Enrich + normalize + deduplicate
    # --------------------------------------------------------

    return normalize_and_dedupe(
        raw_papers
    )


# ============================================================
# DIRECT TEST
# ============================================================

if __name__ == "__main__":

    papers = get_pipeline_ready_papers(
        "large language model benchmark evaluation",
        max_results=2
    )


    print()
    print(
        "=" * 70
    )

    print(
        "PIPELINE-READY PAPERS"
    )

    print(
        "=" * 70
    )


    for paper in papers:

        print()

        print(
            f"ID: {paper['id']}"
        )

        print(
            f"Title: {paper['title']}"
        )

        print(
            f"Source: {paper['source']}"
        )

        print(
            f"Full text length: "
            f"{len(paper['full_text']):,}"
        )

        print(
            f"Abstract length: "
            f"{len(paper['abstract']):,}"
        )