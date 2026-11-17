"""
Each well-known model's own paper, fetched directly from arXiv by ID.

Search engines often miss a model's own paper (for example the Llama 2 or
Gemma 2 paper) because newer papers that merely mention the model rank
above it, and Semantic Scholar rate-limits without an API key. When the
question names a model we know, its paper is fetched by ID so the numbers
in the paper's own results tables are always available.

Every fetched paper is checked against an expected title word, so a wrong
ID can never put an unrelated paper into a report.
"""

import copy
import re
import threading
from typing import Dict, List, Tuple

import requests

from arxiv_retriever import parse_papers_from_xml

# (normalised model prefix, arXiv id, word the title must contain)
KNOWN_MODEL_PAPERS: List[Tuple[str, str, str]] = [
    ("mistral7b", "2310.06825", "mistral"),
    ("mixtral", "2401.04088", "mixtral"),
    ("llama2", "2307.09288", "llama"),
    ("llama3", "2407.21783", "llama"),
    ("llama", "2302.13971", "llama"),
    ("codellama", "2308.12950", "code llama"),
    ("gpt4", "2303.08774", "gpt-4"),
    ("gpt3", "2005.14165", "language models"),
    ("gemma3", "2503.19786", "gemma"),
    ("gemma2", "2408.00118", "gemma"),
    ("gemma", "2403.08295", "gemma"),
    ("gemini1.5", "2403.05530", "gemini"),
    ("gemini", "2312.11805", "gemini"),
    ("phi3", "2404.14219", "phi-3"),
    ("qwen2.5", "2412.15115", "qwen"),
    ("qwen2", "2407.10671", "qwen"),
    ("deepseekv3", "2412.19437", "deepseek"),
    ("deepseekr1", "2501.12948", "deepseek"),
    ("falcon", "2311.16867", "falcon"),
    ("palm", "2204.02311", "palm"),
    ("yi", "2403.04652", "yi"),
    ("olmo", "2402.00838", "olmo"),
]

# Other well-known papers that tabulate a model as a baseline, so a second
# source exists to confirm or question its numbers. Keyed by the same
# normalised prefix as above; values are prefixes from KNOWN_MODEL_PAPERS.
COMPARISON_SOURCES: Dict[str, List[str]] = {
    "mistral7b": ["mixtral", "gemma", "llama3"],
    "mixtral": ["mistral7b", "llama2"],
    "llama2": ["mistral7b", "gemma"],
    "llama3": ["gemma2"],
    "gpt4": ["llama2", "gemini"],
    "gemma2": ["gemma3"],
    "gemma3": ["gemma2"],
    "gemma": ["gemma2", "mistral7b"],
    "gemini": ["gpt4"],
}

MAX_COMPARISON_PAPERS = 2

ARXIV_ENDPOINTS = (
    "https://export.arxiv.org/api/query",
    "https://arxiv.org/api/query",
)

_CACHE: Dict[str, object] = {}
_LOCK = threading.Lock()


def _normalise(text: str) -> str:
    return re.sub(r"[^a-z0-9.]", "", str(text or "").lower())


# A question that names only the family ("MMLU accuracy of Mistral") most
# likely means the family's flagship paper.
BARE_FAMILY_ALIASES = {"mistral": "mistral7b"}


def known_ids_for_models(models: List[str]) -> List[Tuple[str, str]]:
    """Return [(arxiv_id, expected_title_word)] for the asked models."""
    found = []
    seen = set()

    for model in models or []:
        key = _normalise(model)
        key = BARE_FAMILY_ALIASES.get(key, key)
        best = None

        for prefix, arxiv_id, word in KNOWN_MODEL_PAPERS:
            if key.startswith(prefix) and (best is None or len(prefix) > len(best[0])):
                best = (prefix, arxiv_id, word)

        if best and best[1] not in seen:
            seen.add(best[1])
            found.append((best[1], best[2]))

    return found


def _fetch_one(arxiv_id: str, title_word: str):
    with _LOCK:
        if arxiv_id in _CACHE:
            return _CACHE[arxiv_id]

    paper = None

    for endpoint in ARXIV_ENDPOINTS:
        try:
            response = requests.get(
                endpoint,
                params={"id_list": arxiv_id, "max_results": 1},
                timeout=20,
                verify=False,
                headers={"User-Agent": "ResearchClaimAI/1.0"},
            )
            if response.status_code != 200:
                continue

            papers = parse_papers_from_xml(response.text, arxiv_id)
            if papers:
                paper = papers[0]
                break
        except Exception as error:
            print(f"  → known paper {arxiv_id}: {error}")

    if paper is not None:
        title = str(getattr(paper, "title", "") or "").lower()
        if title_word not in title:
            print(
                f"  → known paper {arxiv_id} skipped: title "
                f"{title!r} does not contain {title_word!r}"
            )
            paper = None

    with _LOCK:
        if paper is not None:
            _CACHE[arxiv_id] = paper

    return paper


def fetch_known_papers(models: List[str]):
    """Fetch the asked models' own papers (empty list if none known)."""
    papers = []

    for arxiv_id, word in known_ids_for_models(models):
        paper = _fetch_one(arxiv_id, word)
        if paper is not None:
            print(f"  → known model paper: {paper.title} ({arxiv_id})")
            papers.append(copy.deepcopy(paper))

    return papers


def comparison_ids_for_models(models: List[str]) -> List[Tuple[str, str]]:
    """Return [(arxiv_id, title_word)] of papers that benchmark the asked models."""
    own = {arxiv_id for arxiv_id, _ in known_ids_for_models(models)}
    by_prefix = {prefix: (arxiv_id, word) for prefix, arxiv_id, word in KNOWN_MODEL_PAPERS}
    found = []

    for model in models or []:
        key = _normalise(model)
        best = None

        for prefix in COMPARISON_SOURCES:
            if key.startswith(prefix) and (best is None or len(prefix) > len(best)):
                best = prefix

        for prefix in COMPARISON_SOURCES.get(best, []):
            entry = by_prefix.get(prefix)
            if entry and entry[0] not in own and entry not in found:
                found.append(entry)

    return found[:MAX_COMPARISON_PAPERS]


def fetch_comparison_papers(models: List[str]):
    """Fetch up to MAX_COMPARISON_PAPERS related papers (empty if none known)."""
    papers = []

    for arxiv_id, word in comparison_ids_for_models(models):
        paper = _fetch_one(arxiv_id, word)
        if paper is not None:
            print(f"  → comparison paper: {paper.title} ({arxiv_id})")
            papers.append(copy.deepcopy(paper))

    return papers


def supported_models() -> List[str]:
    """Names shown on the website's Explore page."""
    return [prefix for prefix, _, _ in KNOWN_MODEL_PAPERS]
