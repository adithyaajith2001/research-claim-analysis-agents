
"""
Shared retry wrapper for Gemini model calls.
"""

import hashlib
import json
import os
import threading
import time
from types import SimpleNamespace

from google.genai.errors import ClientError, ServerError

# ----------------------------------------------------------------------
# Answer memory: the same question to Gemini always gets the same answer.
#
# A language model can word its answer slightly differently each time, which
# made the same query give different claims on different runs. Every Gemini
# answer is stored on disk under a fingerprint of the exact prompt, so an
# identical prompt (same paper text, same question) is answered from memory.
# Results are therefore repeatable, and repeat runs are much faster.
#
# Delete backend/data/llm_cache.jsonl to start fresh. Set LLM_CACHE=off to
# turn the memory off.
# ----------------------------------------------------------------------

_CACHE_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "data",
    "llm_cache.jsonl",
)
_CACHE: dict = {}
_CACHE_LOADED = False
_CACHE_LOCK = threading.Lock()


def _cache_enabled() -> bool:
    return os.environ.get("LLM_CACHE", "on").strip().lower() != "off"


def _load_cache() -> None:
    global _CACHE_LOADED
    if _CACHE_LOADED:
        return
    _CACHE_LOADED = True
    try:
        with open(_CACHE_PATH, "r", encoding="utf-8") as handle:
            for line in handle:
                try:
                    row = json.loads(line)
                    _CACHE[row["k"]] = row["t"]
                except Exception:
                    continue
    except FileNotFoundError:
        pass
    except Exception as error:
        print(f"[warn] could not read the answer memory: {error}")


def _fingerprint(model, contents, config) -> str:
    payload = json.dumps(
        [str(model), str(contents), config],
        sort_keys=True,
        default=str,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _remember(key: str, text: str) -> None:
    try:
        with _CACHE_LOCK:
            _CACHE[key] = text
            os.makedirs(os.path.dirname(_CACHE_PATH), exist_ok=True)
            with open(_CACHE_PATH, "a", encoding="utf-8") as handle:
                handle.write(json.dumps({"k": key, "t": text}) + "\n")
    except Exception as error:
        print(f"[warn] could not save the answer memory: {error}")


def call_with_retry(
    client,
    model,
    contents,
    config,
    max_retries=3,
):
    """
    Retry transient 503 errors with shorter exponential backoff.
    max_retries is the maximum total number of attempts.
    """
    max_attempts = max(1, int(max_retries))

    # A fixed seed plus temperature 0 keeps the model as repeatable as it can be.
    if isinstance(config, dict):
        config = {"seed": 42, **config}

    use_cache = _cache_enabled()
    key = None

    if use_cache:
        with _CACHE_LOCK:
            _load_cache()
            key = _fingerprint(model, contents, config)
            cached = _CACHE.get(key)
        if cached is not None:
            return SimpleNamespace(text=cached, from_cache=True)

    for attempt in range(1, max_attempts + 1):
        try:
            response = client.models.generate_content(
                model=model,
                contents=contents,
                config=config,
            )

            text = getattr(response, "text", None)
            if use_cache and key and isinstance(text, str) and text.strip():
                _remember(key, text)

            return response

        except ServerError as error:
            is_overloaded = getattr(error, "code", None) == 503

            if not is_overloaded or attempt == max_attempts:
                raise

            wait_seconds = min(2 ** (attempt - 1), 4)

            print(
                f"[warn] Gemini 503 UNAVAILABLE. "
                f"Retrying in {wait_seconds}s "
                f"(attempt {attempt}/{max_attempts})..."
            )

            time.sleep(wait_seconds)

        except ClientError as error:
            # 429 = rate limit (easy to hit on a free-tier key). Wait and retry.
            if getattr(error, "code", None) != 429 or attempt == max_attempts:
                raise

            wait_seconds = min(15 * attempt, 60)

            print(
                f"[warn] Gemini rate-limited (429). "
                f"Waiting {wait_seconds}s "
                f"(attempt {attempt}/{max_attempts})..."
            )

            time.sleep(wait_seconds)
