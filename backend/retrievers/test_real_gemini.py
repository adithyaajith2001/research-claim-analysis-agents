import os

from dotenv import load_dotenv

load_dotenv()

from google import genai
from google.genai import types

from claim_extraction_agent import extract_claims_from_text


API_KEY = os.environ.get("GEMINI_API_KEY")

if not API_KEY:
    raise RuntimeError(
        "GEMINI_API_KEY is not loaded."
    )


client = genai.Client(
    api_key=API_KEY,
    http_options=types.HttpOptions(
        client_args={
            "verify": False
        }
    )
)


TEST_TEXT = """
We evaluate our instruction-tuned model on standard language
understanding benchmarks. Our model achieves 86.4% accuracy on
MMLU, outperforming the previous baseline by 2.1 percentage
points. On GSM8K, our model achieves 91.2% accuracy.
"""


claims = extract_claims_from_text(
    paper_id="TEST-PAPER-001",
    text=TEST_TEXT,
    client=client
)


print()
print("=" * 70)
print("REAL GEMINI EXTRACTION TEST")
print("=" * 70)

print(
    f"Claims extracted: {len(claims)}"
)

for claim in claims:

    print()
    print("CLAIM:")
    print(
        claim.get("claim")
    )

    print()
    print("SOURCE:")
    print(
        claim.get("source_sentence")
    )

    print()
    print("BENCHMARK:")
    print(
        claim.get("benchmark_name")
    )

    print()
    print("VALUE:")
    print(
        claim.get("reported_value")
    )

    print()
    print("VALUE TYPE:")
    print(
        claim.get("value_type")
    )

print("=" * 70)