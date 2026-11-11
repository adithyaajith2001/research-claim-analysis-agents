"""
Find the model names a user's question asks about, and check whether a
claim is about one of them.

Example: for "What is the MMLU accuracy of Mistral 7B?" the model is
"Mistral 7B". A claim about "Llama 3.2" or "Mistral Large" is a different
model and should not be shown as an answer.
"""

import re
from typing import List, Optional

MODEL_FAMILIES = (
    "mixtral|mistral|llama|gpt|gemini|claude|gemma|qwen|phi|falcon|"
    "deepseek|palm|bloom|olmo|granite|grok|command|yi|opt|t5|bert|"
    "vicuna|alpaca|orca|starcoder|codellama|solar|internlm|baichuan|chatglm"
)

_PART = (
    r"(?:v?\d+(?:\.\d+)*[a-z]?|\d+x\d+b|"
    r"large|small|medium|mini|turbo|pro|flash|ultra|nano|"
    r"sonnet|opus|haiku|instruct|chat|base|coder|vision)"
)

_MODEL_PATTERN = re.compile(
    rf"\b(?:{MODEL_FAMILIES})(?:[\s\-_.]*{_PART})*\b",
    re.IGNORECASE,
)

# What may follow a model name without making it a different model.
_HARMLESS_SUFFIX = re.compile(
    r"^(?:v\d.*|\d{1,3}b.*|instruct.*|chat.*|base.*|it|hf|fp\d+|int\d+)?$"
)


def _normalise(text: str) -> str:
    return re.sub(r"[^a-z0-9]", "", str(text or "").lower())


def extract_query_models(query: str) -> List[str]:
    """Return the model names mentioned in the query (may be empty)."""
    found = []
    seen = set()

    for match in _MODEL_PATTERN.finditer(str(query or "")):
        name = match.group(0).strip(" -_.")
        key = _normalise(name)

        # A bare family word ("gpt", "claude") is too vague to filter on
        # unless it is all the user wrote, so ask for a version/size too.
        if not key or key in seen:
            continue
        seen.add(key)
        found.append(name)

    return found


def model_matches(query_model: str, claim_model: Optional[str], claim_text: str = "") -> bool:
    """True when the claim is about the model the user asked about."""
    wanted = _normalise(query_model)

    if not wanted:
        return True

    candidate = _normalise(claim_model)

    if candidate:
        if candidate == wanted:
            return True

        if candidate.startswith(wanted):
            return bool(_HARMLESS_SUFFIX.match(candidate[len(wanted):]))

        return False

    # The claim gave no model name: fall back to its sentence.
    text = str(claim_text or "")
    for match in _MODEL_PATTERN.finditer(text):
        if model_matches(query_model, match.group(0)):
            return True

    return False


def claim_matches_any(query_models: List[str], claim_model, claim_text="") -> bool:
    if not query_models:
        return True
    return any(model_matches(m, claim_model, claim_text) for m in query_models)
