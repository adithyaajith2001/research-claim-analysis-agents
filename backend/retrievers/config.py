"""
config.py

WHY THIS FILE EXISTS:
Your guide's feedback was "narrow the project to ONE domain and validate only on
that." That decision has to be enforced consistently everywhere - extraction
prompt, scoring weights, test data - or different agents will silently drift
into judging different kinds of papers differently.

Putting the domain decision in ONE file means:
  1. You can show your guide exactly what you scoped down to and why.
  2. If you ever need to expand to another domain, you change this file only -
     not every agent's prompt.

DOMAIN CHOSEN: LLM / NLP Benchmark Evaluation papers
WHY THIS DOMAIN (feasibility-driven, not preference-driven):
  - Fully open access on arXiv -> no paywall issues, no API-key issues for retrieval.
  - Claims are numeric and structured ("Model X scores Y% on benchmark Z"),
    which small/free LLMs (gemini-flash-lite) can extract reliably.
  - Claims usually appear in the ABSTRACT itself -> we can prototype today using
    abstracts only, without a full-PDF-parsing pipeline. Fewer Gemini calls,
    which matters given your rate-limit situation.
  - Multiple papers report scores for the SAME model on the SAME benchmark ->
    contradiction detection is testable on real, checkable disagreements
    instead of fuzzy semantic judgment calls.
"""

# --- Domain scope -----------------------------------------------------------
DOMAIN_NAME = "LLM/NLP Benchmark Evaluation"

# Keep this list SHORT and SPECIFIC. A narrow benchmark list is what makes
# contradiction detection meaningful - two papers need to be talking about the
# same yardstick (e.g. both reporting GSM8K accuracy) to be comparable at all.
VALIDATED_BENCHMARKS = [
    "MMLU", "GSM8K", "HumanEval", "HellaSwag", "TruthfulQA", "BIG-Bench",
]

# Used to build arXiv search queries later (Adithya's retrieval agent will
# use something similar - keep this consistent with hers when she sends it).
DOMAIN_SEARCH_KEYWORDS = [
    "large language model benchmark evaluation",
    "LLM reasoning accuracy",
]

# --- LLM provider settings ---------------------------------------------------
# WHAT: which model + how much text per call.
# WHY small chunk sizes: you're on the Gemini free tier, so every call to
# gemini-flash-lite counts against your per-minute/per-day quota. Since this
# domain's claims live mostly in abstracts (short), we don't need big chunks.
MODEL_NAME = "gemini-flash-lite-latest"
MAX_OUTPUT_TOKENS_EXTRACTION = 4096
MAX_OUTPUT_TOKENS_SCORING = 512
SECONDS_BETWEEN_CALLS = 15  # rate-limit spacing, tune down if your quota allows
MAX_RETRIES = 3

# --- Contradiction detection -------------------------------------------------
# WHAT: how far apart two reported_value scores (same benchmark, different
# papers) need to be before they count as disagreeing, and how far before
# that disagreement is "High" severity vs "Medium".
# WHY these numbers: benchmark scores routinely vary by 1-3 points between
# runs/seeds/prompt formats even for the "same" underlying result (see
# GSM8K 91.2% vs 91.0% in the test fixtures - that's noise, not conflict).
# A gap past ~5 points on a standardized benchmark is hard to explain as
# noise and starts to look like a real methodological or reporting
# disagreement between papers.
CONTRADICTION_AGREE_MAX_DIFF = 3.0
CONTRADICTION_HIGH_SEVERITY_DIFF = 5.0

# --- Mock mode ---------------------------------------------------------------
# WHEN this matters: if GEMINI_API_KEY isn't set (e.g. you're testing pipeline
# logic without burning API quota, or Anthropic's sandbox has no network
# access to Gemini), MOCK_MODE lets every agent run on deterministic fake
# responses so you can test DB writes, scoring math, and JSON parsing for free.
import os
MOCK_MODE = os.environ.get("GEMINI_API_KEY") is None