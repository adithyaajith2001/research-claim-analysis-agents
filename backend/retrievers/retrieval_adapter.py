# """
# retrieval_adapter.py

# WHAT: Normalizes Adithya's retrieval output into the exact paper-dict shape
# etl_pipeline.process_paper / test_pipeline.run_pipeline require.

# UPDATED (see repo: research-claim-analysis-agents, backend/retrievers/) -
# she now has a `paper_schema.StandardPaper` dataclass that both
# arxiv_retriever.py and crossref_retriever.py return objects of. This
# adapter accepts EITHER a StandardPaper object OR a plain dict (since
# semantic_scholar_retriever.py has NOT been updated yet and still returns
# dicts - see message to her). Handling both here means my pipeline doesn't
# break the moment she finishes that update; I just delete the dict branch
# later if I want to tidy up.

#     {
#         "id": str,              <- Paper.id (primary key) - REQUIRED, unique
#         "title": str,
#         "authors": str,         <- comma-joined; db_schema.Paper.authors is a String column
#         "year": int | None,
#         "source": str,
#         "source_url": str,
#         "citation_count": int,
#         "abstract": str,
#         "full_text": str,       <- prefers raw_metadata['raw_text'] from her
#                                     pdf_processor_v2.py when present, else abstract
#     }

# WHY full_text now prefers raw_text: her pdf_processor_v2.PDFProcessor
# already downloads the PDF and extracts real full text into
# paper.raw_metadata['raw_text'] when a pdf_url is available. Previously I
# only had abstracts to work with (per config.py's original abstract-only
# scoping), so this is a genuine upgrade - claim_extraction_agent.chunk_text()
# will now see much more of the paper when her PDF step has run.

# WHAT GETS DROPPED, AND WHY:
#   - Papers with no id we can build a stable primary key from (uses her
#     get_primary_id() when available - already handles the arxiv > doi >
#     semantic_scholar priority correctly).
#   - Papers with no abstract AND no extracted full_text - nothing for
#     claim_extraction_agent to extract from.
#   - Cross-source duplicates sharing a normalized title.
# """

# import re
# from typing import Dict, List, Optional, Union
# from datetime import datetime
# from pdf_processor_v2 import PDFProcessor

# try:
#     from paper_schema import StandardPaper
# except ImportError:
#     StandardPaper = None  # adapter still works on plain dicts if her schema isn't on disk


# def _as_dict(raw: Union["StandardPaper", Dict]) -> Dict:
#     """Accepts either a StandardPaper object (arxiv_retriever, crossref_retriever)
#     or a plain dict (semantic_scholar_retriever, until she updates it) and
#     returns a plain dict either way."""
#     if StandardPaper is not None and isinstance(raw, StandardPaper):
#         return raw.to_dict()
#     if hasattr(raw, "to_dict"):
#         return raw.to_dict()
#     if hasattr(raw, "__dict__") and not isinstance(raw, dict):
#         return dict(raw.__dict__)
#     return raw


# def _make_paper_id(raw: Dict) -> Optional[str]:
#     """Prefer arxiv_id > doi > semantic_scholar_id (same priority as her
#     own StandardPaper.get_primary_id(), kept independent here so this still
#     works on the plain dicts semantic_scholar_retriever.py currently returns,
#     which have no get_primary_id() method)."""
#     for key in ("arxiv_id", "doi", "semantic_scholar_id"):
#         val = raw.get(key)
#         if val:
#             return str(val)
#     return None



# def _make_source_url(raw: Dict, paper_id: str) -> str:
#     if raw.get("pdf_url"):
#         return raw["pdf_url"]
#     if raw.get("url"):
#         return raw["url"]
#     if raw.get("arxiv_id"):
#         return f"https://arxiv.org/abs/{raw['arxiv_id']}"
#     if raw.get("doi"):
#         return f"https://doi.org/{raw['doi']}"
#     return ""


# def _clean_abstract(abstract: str) -> str:
#     """WHY: CrossRef abstracts, when present at all, are usually wrapped in
#     JATS XML tags (e.g. <jats:p>...</jats:p>). Without stripping these, the
#     tags would land inside claim_extraction_agent's chunks as noise text."""
#     if not abstract:
#         return ""
#     return re.sub(r"<[^>]+>", " ", abstract).strip()
#     # (naive tag-strip is fine here - we only need clean prose for the LLM
#     # prompt, not a real XML parse)


# def _extract_year(raw: Dict) -> Optional[int]:
#     """WHY: CrossRef/Semantic Scholar give a "year" key directly. arXiv's
#     retriever (as written) does NOT - it only gives "published_date" as a
#     full ISO timestamp (e.g. "2024-01-01T00:00:00Z"). Without this, every
#     arXiv-sourced Paper.year in the DB would silently come back None."""
#     if raw.get("year"):
#         try:
#             return int(raw["year"])
#         except (TypeError, ValueError):
#             pass
#     published = raw.get("published_date")
#     if published:
#         try:
#             return datetime.fromisoformat(published.replace("Z", "+00:00")).year
#         except ValueError:
#             pass
#     return None


# def _normalize_authors(raw: Dict) -> str:
#     """WHY: Semantic Scholar/CrossRef give authors as a list; the arXiv
#     retriever (as written) gives a single string joined with " | ". Both
#     get normalized to a comma-joined string, matching db_schema.upsert_paper's
#     existing convention."""
#     authors = raw.get("authors", [])
#     if isinstance(authors, list):
#         return ", ".join(a for a in authors if a)
#     if isinstance(authors, str) and "|" in authors:
#         return ", ".join(a.strip() for a in authors.split("|") if a.strip())
#     return str(authors or "")


# def _normalize_title(title: str) -> str:
#     return re.sub(r"[^\w\s]", "", (title or "").lower()).strip()


# def normalize_paper(raw: Union["StandardPaper", Dict]) -> Optional[Dict]:
#     """WHAT: converts one raw paper (StandardPaper object OR dict, see
#     _as_dict) into the schema process_paper() / run_pipeline() expect.

#     Returns None if the paper isn't usable downstream (no stable id, and no
#     abstract/full-text to extract claims from).
#     """
#     raw = _as_dict(raw)
#     paper_id = _make_paper_id(raw)

#     # Prefer real extracted PDF text (pdf_processor_v2 stores this in
#     # raw_metadata['raw_text']) over the abstract, when it's available -
#     # gives claim_extraction_agent far more to work with than abstract-only.
#     raw_metadata = raw.get("raw_metadata") or {}
#     full_text = _clean_abstract(raw_metadata.get("raw_text", "")) or _clean_abstract(raw.get("abstract", ""))
#     abstract = _clean_abstract(raw.get("abstract", ""))

#     if not paper_id or not full_text:
#         return None

#     return {
#         "id": paper_id,
#         "title": (raw.get("title") or "").strip(),
#         "authors": _normalize_authors(raw),
#         "year": _extract_year(raw),
#         "source": raw.get("source", "Unknown"),
#         "source_url": _make_source_url(raw, paper_id),
#         "citation_count": raw.get("citation_count", 0) or 0,
#         "abstract": abstract,
#         "full_text": full_text,
#     }


# def normalize_and_dedupe(raw_papers: List[Dict]) -> List[Dict]:
#     """WHAT: normalizes a whole batch from Adithya's retriever and drops
#     title-duplicate papers that slipped past her id-based dedup."""
#     seen_titles = set()
#     result = []
#     dropped_unusable = 0
#     dropped_dupe = 0

#     for raw in raw_papers:
#         norm = normalize_paper(raw)
#         if norm is None:
#             dropped_unusable += 1
#             continue
#         title_key = _normalize_title(norm["title"])
#         if title_key and title_key in seen_titles:
#             dropped_dupe += 1
#             continue
#         if title_key:
#             seen_titles.add(title_key)
#         result.append(norm)

#     print(
#         f"[info] retrieval_adapter: {len(raw_papers)} raw -> {len(result)} usable "
#         f"({dropped_unusable} dropped: no id/abstract, {dropped_dupe} dropped: duplicate title)"
#     )
#     return result


# def get_pipeline_ready_papers(
#     query: str,
#     max_results: int = 10,
#     fetch_full_text: bool = True,
#     max_pdf_downloads: int = 8,
# ) -> List[Dict]:
#     from unified_retriever import UnifiedPaperRetriever
#     retriever = UnifiedPaperRetriever()
#     raw_papers = retriever.search_all_sources(query, max_results=max_results)

#     if fetch_full_text:
#         processor = PDFProcessor(verify_ssl=True, max_pages=6)
#         pdf_budget = max_pdf_downloads
#         for raw in raw_papers:
#             if pdf_budget <= 0:
#                 break
#             has_abstract = bool(getattr(raw, "abstract", None) or
#                                  (isinstance(raw, dict) and raw.get("abstract")))
#             get_pdf_url = getattr(raw, "get_pdf_url", None)
#             pdf_url = get_pdf_url() if callable(get_pdf_url) else None
#             if has_abstract or not pdf_url:
#                 continue
#             try:
#                 processor.process_paper(raw)
#                 pdf_budget -= 1
#             except Exception as e:
#                 title = getattr(raw, "title", "") or ""
#                 print(f"[warn] PDF extraction failed for '{title[:50]}': {e}")

#     return normalize_and_dedupe(raw_papers)


# if __name__ == "__main__":
#     papers = get_pipeline_ready_papers("large language model benchmark evaluation", max_results=5)
#     for p in papers:
#         print(f"- {p['id']}: {p['title'][:60]}")

"""
retrieval_adapter.py

WHAT: Normalizes Adithya's retrieval output into the exact paper-dict shape
etl_pipeline.process_paper / test_pipeline.run_pipeline require.

UPDATED (see repo: research-claim-analysis-agents, backend/retrievers/) -
she now has a `paper_schema.StandardPaper` dataclass that both
arxiv_retriever.py and crossref_retriever.py return objects of. This
adapter accepts EITHER a StandardPaper object OR a plain dict (since
semantic_scholar_retriever.py has NOT been updated yet and still returns
dicts - see message to her). Handling both here means my pipeline doesn't
break the moment she finishes that update; I just delete the dict branch
later if I want to tidy up.

    {
        "id": str,              <- Paper.id (primary key) - REQUIRED, unique
        "title": str,
        "authors": str,         <- comma-joined; db_schema.Paper.authors is a String column
        "year": int | None,
        "source": str,
        "source_url": str,
        "citation_count": int,
        "abstract": str,
        "full_text": str,       <- prefers raw_metadata['raw_text'] from her
                                    pdf_processor_v2.py when present, else abstract
    }

WHY full_text now prefers raw_text: her pdf_processor_v2.PDFProcessor
already downloads the PDF and extracts real full text into
paper.raw_metadata['raw_text'] when a pdf_url is available. Previously I
only had abstracts to work with (per config.py's original abstract-only
scoping), so this is a genuine upgrade - claim_extraction_agent.chunk_text()
will now see much more of the paper when her PDF step has run.

WHAT GETS DROPPED, AND WHY:
  - Papers with no id we can build a stable primary key from (uses her
    get_primary_id() when available - already handles the arxiv > doi >
    semantic_scholar priority correctly).
  - Papers with no abstract AND no extracted full_text - nothing for
    claim_extraction_agent to extract from.
  - Cross-source duplicates sharing a normalized title.
"""

import re
from typing import Dict, List, Optional, Union
from datetime import datetime
from pdf_processor_v2 import PDFProcessor

try:
    from paper_schema import StandardPaper
except ImportError:
    StandardPaper = None  # adapter still works on plain dicts if her schema isn't on disk


def _as_dict(raw: Union["StandardPaper", Dict]) -> Dict:
    """Accepts either a StandardPaper object (arxiv_retriever, crossref_retriever)
    or a plain dict (semantic_scholar_retriever, until she updates it) and
    returns a plain dict either way."""
    if StandardPaper is not None and isinstance(raw, StandardPaper):
        return raw.to_dict()
    if hasattr(raw, "to_dict"):
        return raw.to_dict()
    if hasattr(raw, "__dict__") and not isinstance(raw, dict):
        return dict(raw.__dict__)
    return raw


def _make_paper_id(raw: Dict) -> Optional[str]:
    """Prefer arxiv_id > doi > semantic_scholar_id (same priority as her
    own StandardPaper.get_primary_id(), kept independent here so this still
    works on the plain dicts semantic_scholar_retriever.py currently returns,
    which have no get_primary_id() method)."""
    for key in ("arxiv_id", "doi", "semantic_scholar_id"):
        val = raw.get(key)
        if val:
            return str(val)
    return None



def _make_source_url(raw: Dict, paper_id: str) -> str:
    if raw.get("pdf_url"):
        return raw["pdf_url"]
    if raw.get("url"):
        return raw["url"]
    if raw.get("arxiv_id"):
        return f"https://arxiv.org/abs/{raw['arxiv_id']}"
    if raw.get("doi"):
        return f"https://doi.org/{raw['doi']}"
    return ""


def _clean_abstract(abstract: str) -> str:
    """WHY: CrossRef abstracts, when present at all, are usually wrapped in
    JATS XML tags (e.g. <jats:p>...</jats:p>). Without stripping these, the
    tags would land inside claim_extraction_agent's chunks as noise text."""
    if not abstract:
        return ""
    return re.sub(r"<[^>]+>", " ", abstract).strip()
    # (naive tag-strip is fine here - we only need clean prose for the LLM
    # prompt, not a real XML parse)


def _extract_year(raw: Dict) -> Optional[int]:
    """WHY: CrossRef/Semantic Scholar give a "year" key directly. arXiv's
    retriever (as written) does NOT - it only gives "published_date" as a
    full ISO timestamp (e.g. "2024-01-01T00:00:00Z"). Without this, every
    arXiv-sourced Paper.year in the DB would silently come back None."""
    if raw.get("year"):
        try:
            return int(raw["year"])
        except (TypeError, ValueError):
            pass
    published = raw.get("published_date")
    if published:
        try:
            return datetime.fromisoformat(published.replace("Z", "+00:00")).year
        except ValueError:
            pass
    return None


def _normalize_authors(raw: Dict) -> str:
    """WHY: Semantic Scholar/CrossRef give authors as a list; the arXiv
    retriever (as written) gives a single string joined with " | ". Both
    get normalized to a comma-joined string, matching db_schema.upsert_paper's
    existing convention."""
    authors = raw.get("authors", [])
    if isinstance(authors, list):
        return ", ".join(a for a in authors if a)
    if isinstance(authors, str) and "|" in authors:
        return ", ".join(a.strip() for a in authors.split("|") if a.strip())
    return str(authors or "")


def _normalize_title(title: str) -> str:
    return re.sub(r"[^\w\s]", "", (title or "").lower()).strip()


def normalize_paper(raw: Union["StandardPaper", Dict]) -> Optional[Dict]:
    """WHAT: converts one raw paper (StandardPaper object OR dict, see
    _as_dict) into the schema process_paper() / run_pipeline() expect.

    Returns None if the paper isn't usable downstream (no stable id, and no
    abstract/full-text to extract claims from).
    """
    raw = _as_dict(raw)
    paper_id = _make_paper_id(raw)

    # Prefer real extracted PDF text (pdf_processor_v2 stores this in
    # raw_metadata['raw_text']) over the abstract, when it's available -
    # gives claim_extraction_agent far more to work with than abstract-only.
    raw_metadata = raw.get("raw_metadata") or {}
    full_text = _clean_abstract(raw_metadata.get("raw_text", "")) or _clean_abstract(raw.get("abstract", ""))
    abstract = _clean_abstract(raw.get("abstract", ""))

    if not paper_id or not full_text:
        return None

    return {
        "id": paper_id,
        "title": (raw.get("title") or "").strip(),
        "authors": _normalize_authors(raw),
        "year": _extract_year(raw),
        "source": raw.get("source", "Unknown"),
        "source_url": _make_source_url(raw, paper_id),
        "citation_count": raw.get("citation_count", 0) or 0,
        "abstract": abstract,
        "full_text": full_text,
    }


def normalize_and_dedupe(raw_papers: List[Dict]) -> List[Dict]:
    """WHAT: normalizes a whole batch from Adithya's retriever and drops
    title-duplicate papers that slipped past her id-based dedup."""
    seen_titles = set()
    result = []
    dropped_unusable = 0
    dropped_dupe = 0

    for raw in raw_papers:
        norm = normalize_paper(raw)
        if norm is None:
            dropped_unusable += 1
            continue
        title_key = _normalize_title(norm["title"])
        if title_key and title_key in seen_titles:
            dropped_dupe += 1
            continue
        if title_key:
            seen_titles.add(title_key)
        result.append(norm)

    print(
        f"[info] retrieval_adapter: {len(raw_papers)} raw -> {len(result)} usable "
        f"({dropped_unusable} dropped: no id/abstract, {dropped_dupe} dropped: duplicate title)"
    )
    return result


# Cheap relevance gate before spending a PDF download on a paper. This
# doesn't remove papers from the result set - it only decides whether
# they're worth the slow download step. Without it, "Llama 3 herd of
# models" pulls in real veterinary papers ("Camelid Herd Health and
# Nutrition") that burn through the PDF-download budget for zero benefit,
# since the actual topic search terms (llama, herd) collide with an
# unrelated English word.
_AI_RELEVANCE_KEYWORDS = (
    "language model", "llm", "benchmark", "gpt", "transformer",
    "neural network", "fine-tun", "instruction-tun", "reasoning",
    "accuracy", "nlp", "large language",
)


def _looks_ai_relevant(paper) -> bool:
    title = getattr(paper, "title", "") or ""
    abstract = getattr(paper, "abstract", "") or ""
    text = f"{title} {abstract}".lower()
    return any(kw in text for kw in _AI_RELEVANCE_KEYWORDS)


def get_pipeline_ready_papers(
    query: str,
    max_results: int = 10,
    fetch_full_text: bool = True,
    max_pdf_downloads: int = 8,
) -> List[Dict]:
    from unified_retriever import UnifiedPaperRetriever
    retriever = UnifiedPaperRetriever()
    raw_papers = retriever.search_all_sources(query, max_results=max_results)

    if fetch_full_text:
        processor = PDFProcessor(verify_ssl=True, max_pages=6)
        pdf_budget = max_pdf_downloads
        skipped_off_topic = 0
        for raw in raw_papers:
            if pdf_budget <= 0:
                break
            has_abstract = bool(getattr(raw, "abstract", None) or
                                 (isinstance(raw, dict) and raw.get("abstract")))
            get_pdf_url = getattr(raw, "get_pdf_url", None)
            pdf_url = get_pdf_url() if callable(get_pdf_url) else None
            if has_abstract or not pdf_url:
                continue
            if not _looks_ai_relevant(raw):
                skipped_off_topic += 1
                continue
            try:
                processor.process_paper(raw)
                pdf_budget -= 1
            except Exception as e:
                title = getattr(raw, "title", "") or ""
                print(f"[warn] PDF extraction failed for '{title[:50]}': {e}")
        if skipped_off_topic:
            print(f"[info] retrieval_adapter: skipped PDF download for "
                  f"{skipped_off_topic} likely off-topic paper(s)")

    return normalize_and_dedupe(raw_papers)


if __name__ == "__main__":
    papers = get_pipeline_ready_papers("large language model benchmark evaluation", max_results=5)
    for p in papers:
        print(f"- {p['id']}: {p['title'][:60]}")