
"""
Shared retry wrapper for Gemini model calls.
"""

import time
from google.genai.errors import ServerError


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

    for attempt in range(1, max_attempts + 1):
        try:
            return client.models.generate_content(
                model=model,
                contents=contents,
                config=config,
            )

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
