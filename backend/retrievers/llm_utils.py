# """
# llm_utils.py

# WHAT: shared retry wrapper around client.models.generate_content(), used by
# both claim_extraction_agent.py and evidence_strength_agent.py.

# WHY shared: both agents make the same kind of call to the same model and
# hit the same transient-503 risk. One retry implementation, imported twice,
# beats maintaining two copies that can drift out of sync.
# """

# import time
# from google.genai.errors import ServerError


# def call_with_retry(client, model, contents, config, max_retries=4):
#     """Retry on transient 503 (model overloaded). Raises after max_retries."""
#     for attempt in range(1, max_retries + 1):
#         try:
#             return client.models.generate_content(
#                 model=model,
#                 contents=contents,
#                 config=config,
#             )
#         except ServerError as e:
#             if getattr(e, "code", None) == 503 and attempt < max_retries:
#                 wait = 2 ** attempt  # 2s, 4s, 8s, 16s
#                 print(f"[warn] 503 UNAVAILABLE, retrying in {wait}s (attempt {attempt}/{max_retries})...")
#                 time.sleep(wait)
#                 continue
#             raise

"""
llm_utils.py

WHAT: shared retry wrapper around client.models.generate_content(), used by
both claim_extraction_agent.py and evidence_strength_agent.py.

WHY shared: both agents make the same kind of call to the same model and
hit the same transient-503 risk. One retry implementation, imported twice,
beats maintaining two copies that can drift out of sync.
"""

import time
from google.genai.errors import ServerError, ClientError


def call_with_retry(client, model, contents, config, max_retries=4):
    """Retry on transient 503 (model overloaded) and 429 (rate limit).
    Raises after max_retries.

    WHY 429 was added: ServerError (5xx) was already retried, but a Gemini
    rate-limit hit (very easy to trigger on a free-tier key during a long
    multi-paper run) raises ClientError with code 429, which was previously
    uncaught here - it would propagate up, get swallowed by the broad
    except Exception around each chunk in claim_extraction_agent.py, and
    silently skip that chunk with zero retry. Same failure mode as the
    arXiv/Semantic Scholar 429s fixed earlier, just on the Gemini side.
    """
    for attempt in range(1, max_retries + 1):
        try:
            return client.models.generate_content(
                model=model,
                contents=contents,
                config=config,
            )
        except ServerError as e:
            if getattr(e, "code", None) == 503 and attempt < max_retries:
                wait = 2 ** attempt  # 2s, 4s, 8s, 16s
                print(f"[warn] 503 UNAVAILABLE, retrying in {wait}s (attempt {attempt}/{max_retries})...")
                time.sleep(wait)
                continue
            raise
        except ClientError as e:
            code = getattr(e, "code", None)
            if code == 429 and attempt < max_retries:
                wait = min(60, 15 * attempt)  # 15s, 30s, 45s, 60s
                print(f"[warn] Gemini rate-limited (429), waiting {wait}s "
                      f"before retry {attempt}/{max_retries}...")
                time.sleep(wait)
                continue
            raise