"""
claim_extraction_agent.py

Real Gemini-based claim extraction for ResearchClaimAI.

Pipeline:

    paper full text
        ↓
    text chunks
        ↓
    benchmark anchor detection
        ↓
    bounded neighboring contexts
        ↓
    Gemini
        ↓
    deterministic full-paper evidence recovery
        ↓
    JSON claims
        ↓
    strict validation
        ↓
    paper_id attachment
        ↓
    deduplication
        ↓
    final paper-specific claims

Important:
- No synthetic/mock claim fallback.
- Only explicit numeric claims are accepted.
- Benchmark names must be exact validated benchmarks.
- Benchmark variants such as MMLU-Pro, Mobile-MMLU and
  Video-MMLU are not silently converted to MMLU.
- Model identifiers must be specific enough to establish model identity;
  generic labels such as GPT or Gemini are rejected.
- Table claims must contain enough source text to justify
  benchmark/value mapping.
"""

import json
import os
import re
import time
import math


from llm_utils import call_with_retry


from config import (
    MODEL_NAME,
    MAX_OUTPUT_TOKENS_EXTRACTION,
    SECONDS_BETWEEN_CALLS,
    MAX_RETRIES,
    VALIDATED_BENCHMARKS,
)


# ============================================================
# EXTRACTION CONTEXT LIMITS
# ============================================================

# A Gemini request may contain up to five 6,000-character chunks.
MAX_CONTEXT_CHUNKS = 5

# Hard safety limit for the complete Gemini input context.
MAX_CONTEXT_CHARS = 20000

# Gemini should return no more than eight claims per context.
MAX_CLAIMS_PER_RESPONSE = 8

# Expand benchmark anchors far enough to recover PDF-extracted table headers
# and rows that are split across neighboring chunks.
ANCHOR_NEIGHBOR_RADIUS = 3

# Perform at most one focused recovery request when Gemini returns [] but
# the context visibly contains benchmark + numeric-result evidence.
MAX_RECOVERY_ATTEMPTS = 1

# When Gemini omits a table header from source_sentence, recover it from the
# FULL paper text rather than depending only on the current 5-chunk context.
# This is the key fix for table settings such as "MMLU (0-shot)" being lost
# when a PDF table header and model row fall into different Gemini windows.
FULLTEXT_TABLE_LOOKBACK_LINES = 40
FULLTEXT_TABLE_LOOKAHEAD_LINES = 12


# ============================================================
# BENCHMARK VARIANTS
# ============================================================

BENCHMARK_VARIANTS = (
    "mmlu-pro",
    "mobile-mmlu",
    "mobile-mmlu-pro",
    "video-mmlu",
    "tr-mmlu",
    "mmlu-sr",
)

# Benchmark names that may appear as table columns even when they are not
# part of VALIDATED_BENCHMARKS. They are used only to preserve column
# positions; they are never emitted as accepted claim benchmark names.
TABLE_BENCHMARK_NAMES = tuple(
    dict.fromkeys(
        list(VALIDATED_BENCHMARKS)
        + list(BENCHMARK_VARIANTS)
    )
)


# ============================================================
# GEMINI CLIENT
# ============================================================

def get_gemini_client(
    client=None
):
    """
    Return the Gemini client supplied by the pipeline.

    If the pipeline does not supply one, create a client using
    GEMINI_API_KEY.

    The pipeline-created client may contain custom HTTP settings,
    including SSL configuration for the current development
    environment.
    """

    # --------------------------------------------------------
    # Use supplied client
    # --------------------------------------------------------

    if client is not None:

        return client


    # --------------------------------------------------------
    # Read API key
    # --------------------------------------------------------

    api_key = os.environ.get(
        "GEMINI_API_KEY"
    )


    if not api_key:

        raise RuntimeError(
            "GEMINI_API_KEY is not available. "
            "Please check backend/.env."
        )


    # --------------------------------------------------------
    # Create Gemini client
    # --------------------------------------------------------

    from google import genai


    return genai.Client(
        api_key=api_key
    )


# ============================================================
# GEMINI PROMPT
# ============================================================

EXTRACTION_PROMPT = """
You are a careful scientific claim extraction agent.

You are analyzing ONE research paper.

Your task is to extract ONLY explicit quantitative research claims
that report model performance on one of these validated benchmarks:

{benchmarks}

The supplied text may have been extracted from a PDF. PDF extraction
can break:

- sentences
- tables
- rows
- columns
- table headers
- section headings
- words

You must reconstruct relationships ONLY when the supplied context
contains enough evidence to support the result.

Pay special attention to:

- Results
- Experiments
- Evaluation
- Benchmark tables
- Accuracy tables
- Model comparison tables
- Table captions
- Performance discussions

For every valid claim return an object containing exactly:

"claim":
    A concise one-sentence statement of the quantitative result.

"source_sentence":
    EXACT supporting text from the supplied context.

    For a normal prose result, reproduce the exact sentence.

    For a TABLE result, this field MUST include:

    1. The relevant table header/column text identifying the
       benchmark.

    AND

    2. The exact model row containing the reported value.

    Example:

        Header:
        Model | MMLU | GSM8K

        Row:
        Model-A | 72.4 | 83.1

    The source_sentence must contain enough exact text to establish
    that 72.4 belongs to MMLU.

    If the benchmark-to-value mapping cannot be established from
    the supplied context, DO NOT extract the claim.

"section":
    Examples:

    "Abstract"
    "Results"
    "Experiments"
    "Evaluation"
    "Conclusion"

    Use "Unknown" when unclear.

"claim_type":
    One of:

    "performance_claim"
    "finding"
    "conclusion"

"benchmark_name":
    Must be EXACTLY one of:

    {benchmarks}

    Do NOT convert benchmark variants into another benchmark.

    Examples:

        MMLU-Pro     != MMLU
        Mobile-MMLU  != MMLU
        Video-MMLU   != MMLU

"reported_value":
    The numeric value explicitly reported in the supplied context.

    This field MUST NOT be null.

    Never calculate or derive a value.

"value_type":
    One of:

    "absolute_accuracy"
        A standalone benchmark score or accuracy.

    "absolute_improvement"
        An explicitly stated percentage-point improvement.

    "relative_improvement"
        An explicitly stated relative/proportional improvement.

IMPORTANT OUTPUT LIMITS:

1. Return at most 8 claim objects.

2. Prefer explicit numeric benchmark performance results.

3. Do not return qualitative claims such as:
   "the model performs well on MMLU."

4. Do not return a claim with reported_value = null.

5. The exact validated benchmark must appear in source_sentence.

6. The reported numeric value must appear in source_sentence.

7. A benchmark variant must never be relabeled as another benchmark.

8. Do not infer table column mappings.

9. For table claims, include the benchmark header and the model row
   together in source_sentence.

10. Do not combine values from different rows.

11. Do not combine values from different benchmark columns.

12. Do not calculate or derive values.

13. A percentage score is not automatically an improvement.

14. Only use "absolute_improvement" when the source explicitly states
    a percentage-point improvement.

15. Only use "relative_improvement" when the source explicitly
    describes a relative/proportional improvement.

16. Ignore references, acknowledgements, background discussion,
    funding text and unrelated sections.

17. Do not extract benchmark results from graphs unless the numerical
    value is explicitly written in the supplied text.

18. Do not invent a model name, number, benchmark or result.

19. The model identifier must be specific enough to identify the exact
    evaluated model or model variant. Reject bare generic labels such as
    "GPT", "Gemini", "Claude", "Llama", "Llama3", "Qwen", or "the model"
    when no explicit variant, version, size, or other identifier is given.

20. Prefer the exact model identifier shown in the source table row or
    result sentence, for example "GPT-4o", "GPT-4o-mini",
    "Llama3-70B", or "Qwen2.5-3B-Instruct".

21. Do not shorten a specific model identifier into a generic family name.

22. Every quantitative claim must be directly supported by the
    supplied text.

23. Return ONLY a JSON array.

24. Do not use markdown code fences.

25. CRITICAL: EACH CLAIM MUST REFER TO EXACTLY ONE BENCHMARK.

26. CRITICAL: EACH CLAIM MUST CONTAIN EXACTLY ONE REPORTED
    PERFORMANCE VALUE.

27. If a table contains multiple benchmark columns, DO NOT write a
    compound claim such as:
        "Model-A achieves 72.4 on MMLU and 83.1 on GSM8K."

28. Instead, create separate claim objects, one per benchmark:
        "Model-A achieves 72.4 on MMLU."
        "Model-A achieves 83.1 on GSM8K."

29. The "benchmark_name" field must match the ONLY benchmark mentioned
    in the claim text.

30. The "reported_value" field must be the value from that SAME
    benchmark column. Never choose a different number from the row.

28. For a table claim, the source_sentence MUST contain both the table
    header and the exact model row so the benchmark-to-value mapping can
    be checked.

32. If the table header and row do not provide enough information to
    map the reported value to the selected benchmark column, DO NOT
    return the claim.

33. Model names can contain numbers (for example Qwen2.5-3B-Instruct).
    These are model identifiers, not reported performance values.

34. Keep the claim itself simple: one model, one benchmark, one numeric
    result.

35. Do not return an empty array when the supplied context contains an
    explicit numeric benchmark result that can be supported from the text.

36. Carefully inspect table rows even when PDF extraction removed visible
    column spacing; use the supplied header and row together to establish
    the mapping.

PAPER TEXT:

{chunk}
"""


# ============================================================
# RECOVERY / RESULT SIGNALS
# ============================================================

RESULT_CONTEXT_TERMS = (
    "result",
    "results",
    "evaluation",
    "evaluated",
    "accuracy",
    "score",
    "performance",
    "achieves",
    "reported",
    "benchmark",
    "table",
    "%",
)


RECOVERY_PROMPT = """
The previous extraction attempt returned an empty JSON array.
Reinspect the supplied evidence carefully.

Return quantitative benchmark-performance claims when the evidence
explicitly supports them. Do NOT return an empty array merely because
the PDF text is imperfect. Reconstruct only relationships that are
explicitly supported by the supplied benchmark header, model row, or
prose sentence.

STRICT RULES:
- Each claim must contain exactly one validated benchmark.
- Each claim must contain exactly one reported numeric result.
- Never combine multiple benchmark columns into one claim.
- Never move a value from one benchmark column to another.
- For tables, source_sentence must include the benchmark header and the
  complete model row whenever that information is present.
- MMLU, MMLU-Pro, Mobile-MMLU, and Video-MMLU are distinct benchmarks.
- Do not calculate values.
- reported_value must be explicitly present in the supplied text.
- EVERY returned claim object MUST contain these fields:
  "claim",
  "source_sentence",
  "section",
  "claim_type",
  "benchmark_name",
  "reported_value",
  "value_type",
  "model_name".

- "value_type" MUST be exactly one of:
  "absolute_accuracy",
  "absolute_improvement",
  "relative_improvement".

- For a benchmark score/accuracy reported as a model performance result,
  use "absolute_accuracy".

- For tables, source_sentence MUST include the table header containing
  the relevant metric/benchmark column and the complete model row whenever
  that information is present in the supplied evidence.

- When the evidence is a model-performance result, include the exact model
  identifier as "model_name" and the benchmark as "benchmark_name".







- Do not treat relevance scores, topic statistics, or benchmark-analysis
  scores as model performance unless the source explicitly identifies them
  as a model benchmark result.
- Return ONLY a JSON array.

VALIDATED BENCHMARKS:
{benchmarks}

SUPPLIED EVIDENCE:
{chunk}
"""


# ============================================================
# BENCHMARK HELPERS
# ============================================================

def _canonical_benchmark(
    value
):
    """
    Convert benchmark spelling/case to the canonical configured
    benchmark name.

    Example:
        mmlu -> MMLU
    """

    if value is None:

        return None


    value = str(
        value
    ).strip()


    for benchmark in VALIDATED_BENCHMARKS:

        if value.lower() == benchmark.lower():

            return benchmark


    return None


def _normalize_benchmark_text(text):
    """
    Normalize formatting artifacts that commonly appear in PDF-extracted
    benchmark names without changing benchmark identity.

    Examples:
        MMLU - Pro   -> MMLU-Pro
        Mobile - MMLU -> Mobile-MMLU
        MMLU-\nPro   -> MMLU-Pro
    """

    if not text:
        return ""

    normalized = str(text)

    normalized = normalized.replace("\u00ad", "")

    # Normalize common Unicode dash characters.
    normalized = (
        normalized
        .replace("\u2010", "-")
        .replace("\u2011", "-")
        .replace("\u2012", "-")
        .replace("\u2013", "-")
        .replace("\u2014", "-")
        .replace("\u2212", "-")
    )

    # Some PDF table extraction collapses the first header cell and the
    # first benchmark into one token, for example "ModelMMLU" or
    # "ModelMMLU-Pro". Insert a separator only for this known table artifact.
    normalized = re.sub(
        r"\bModel(?=(?:MMLU|Mobile-MMLU|MMLU-SR|TR-MMLU|Video-MMLU)\b)",
        "Model ",
        normalized,
        flags=re.IGNORECASE,
    )

    # Join line-broken / whitespace-separated hyphenated benchmark names.
    normalized = re.sub(r"\s*-\s*", "-", normalized)

    # Collapse repeated whitespace.
    normalized = re.sub(r"\s+", " ", normalized)

    return normalized.strip()


def _contains_exact_benchmark(
    text,
    benchmark
):
    """
    Check whether a benchmark appears as an exact benchmark token.

    The text is normalized first so PDF variants such as "MMLU - Pro"
    still match MMLU-Pro. At the same time, MMLU will NOT match MMLU-Pro,
    Mobile-MMLU, or Video-MMLU.
    """

    if not text or not benchmark:
        return False

    normalized_text = _normalize_benchmark_text(text)
    normalized_benchmark = _normalize_benchmark_text(benchmark)

    pattern = re.compile(
        rf"(?<![\w-])"
        rf"{re.escape(normalized_benchmark)}"
        rf"(?![\w-])",
        flags=re.IGNORECASE
    )

    return bool(pattern.search(normalized_text))

def _contains_benchmark_variant(
    text
):
    """
    Detect known benchmark variants.
    """

    if not text:

        return False


    lowered = _normalize_benchmark_text(
        text
    ).lower()


    return any(
        variant in lowered
        for variant in BENCHMARK_VARIANTS
    )


# ============================================================
# TEXT CHUNKING
# ============================================================

def chunk_text(
    text,
    max_chars=6000
):
    """
    Split full paper text into manageable chunks.

    Paragraphs are kept together whenever possible.

    A paragraph larger than max_chars is safely divided.
    """

    if not text:

        return []


    # --------------------------------------------------------
    # Normalize line endings
    # --------------------------------------------------------

    text = (
        str(text)
        .replace(
            "\r\n",
            "\n"
        )
        .replace(
            "\r",
            "\n"
        )
    )


    # --------------------------------------------------------
    # Paragraph split
    # --------------------------------------------------------

    paragraphs = [

        paragraph.strip()

        for paragraph in text.split(
            "\n\n"
        )

        if paragraph.strip()

    ]


    chunks = []

    current = ""


    # ========================================================
    # BUILD CHUNKS
    # ========================================================

    for paragraph in paragraphs:

        # ----------------------------------------------------
        # Start a new chunk
        # ----------------------------------------------------

        if not current:

            if len(
                paragraph
            ) <= max_chars:

                current = paragraph

                continue


            # ------------------------------------------------
            # Single paragraph larger than max_chars
            # ------------------------------------------------

            start = 0


            while start < len(
                paragraph
            ):

                end = (
                    start
                    + max_chars
                )


                chunks.append(
                    paragraph[
                        start:end
                    ].strip()
                )


                start = end


            continue


        # ----------------------------------------------------
        # Try to append paragraph
        # ----------------------------------------------------

        proposed_length = (
            len(current)
            + len(paragraph)
            + 2
        )


        if proposed_length <= max_chars:

            current += (
                "\n\n"
                + paragraph
            )


        else:

            chunks.append(
                current
            )


            if len(
                paragraph
            ) <= max_chars:

                current = paragraph

            else:

                start = 0


                while start < len(
                    paragraph
                ):

                    end = (
                        start
                        + max_chars
                    )


                    chunks.append(
                        paragraph[
                            start:end
                        ].strip()
                    )


                    start = end


                current = ""


    # --------------------------------------------------------
    # Final chunk
    # --------------------------------------------------------

    if current:

        chunks.append(
            current
        )


    return [
        chunk
        for chunk in chunks
        if chunk.strip()
    ]


# ============================================================
# BENCHMARK ANCHOR DETECTION
# ============================================================

def _chunk_contains_benchmark(
    chunk
):
    """
    Determine whether a chunk contains an exact validated benchmark.

    IMPORTANT:

    We intentionally do NOT require the number or result language
    to appear in the SAME chunk.

    PDF extraction can split:

        Table header
        benchmark name
        model row
        numeric value

    across several neighboring chunks.

    Therefore the benchmark itself acts as the anchor.
    """

    if not chunk:

        return False


    for benchmark in VALIDATED_BENCHMARKS:

        if _contains_exact_benchmark(
            chunk,
            benchmark
        ):

            return True


    return False


def _find_relevant_chunk_indices(
    chunks
):
    """
    Find exact benchmark anchor chunks and expand each anchor
    by ANCHOR_NEIGHBOR_RADIUS chunks on either side.

    This deliberately keeps nearby table context available.
    """

    if not chunks:

        return set()


    anchor_indices = set()


    # --------------------------------------------------------
    # Find benchmark anchors
    # --------------------------------------------------------

    for index, chunk in enumerate(
        chunks
    ):

        if _chunk_contains_benchmark(
            chunk
        ):

            anchor_indices.add(
                index
            )


    # --------------------------------------------------------
    # Expand around each anchor
    # --------------------------------------------------------

    relevant = set()


    for anchor in anchor_indices:

        start = max(
            0,
            anchor - ANCHOR_NEIGHBOR_RADIUS
        )


        end = min(
            len(chunks),
            anchor + ANCHOR_NEIGHBOR_RADIUS + 1
        )


        for index in range(
            start,
            end
        ):

            relevant.add(
                index
            )


    return relevant


# ============================================================
# CONTEXT BUILDING
# ============================================================

def _build_context_chunks(
    chunks,
    relevant_indices,
    neighbor_radius=2
):
    """
    Build bounded Gemini contexts.

    Each context contains at most:

        MAX_CONTEXT_CHUNKS

    and:

        MAX_CONTEXT_CHARS

    Relevant regions are broken into bounded windows so that a
    large paper never becomes one huge Gemini request.
    """

    if (
        not chunks
        or not relevant_indices
    ):

        return []


    sorted_indices = sorted(
        set(
            relevant_indices
        )
    )


    contexts = []


    # --------------------------------------------------------
    # Process relevant regions
    # --------------------------------------------------------

    position = 0


    while position < len(
        sorted_indices
    ):

        region_start = (
            sorted_indices[position]
        )


        # ----------------------------------------------------
        # First window:
        # keep two chunks before the first relevant chunk
        # ----------------------------------------------------

        window_start = max(
            0,
            region_start - neighbor_radius
        )


        window_end = min(
            len(chunks) - 1,
            window_start
            + MAX_CONTEXT_CHUNKS
            - 1
        )


        # ----------------------------------------------------
        # Build context
        # ----------------------------------------------------

        candidate_indices = list(
            range(
                window_start,
                window_end + 1
            )
        )


        parts = []

        total_chars = 0


        for index in candidate_indices:

            piece = (
                "\n"
                f"--- CHUNK {index + 1} ---\n"
                f"{chunks[index].strip()}\n"
            )


            if (
                total_chars
                + len(piece)
                > MAX_CONTEXT_CHARS
            ):

                break


            parts.append(
                piece
            )


            total_chars += len(
                piece
            )


        if parts:

            actual_end_index = (
                candidate_indices[
                    len(parts) - 1
                ]
            )


            contexts.append(
                {
                    "start_index":
                        candidate_indices[0],

                    "end_index":
                        actual_end_index,

                    "text":
                        "".join(
                            parts
                        )
                }
            )


        # ----------------------------------------------------
        # Advance past relevant chunks covered by this window
        # ----------------------------------------------------

        next_position = position


        while (
            next_position
            < len(sorted_indices)
            and sorted_indices[
                next_position
            ] <= window_end
        ):

            next_position += 1


        # Safety against infinite loops
        if next_position == position:

            next_position += 1


        position = next_position


    # --------------------------------------------------------
    # Remove duplicates
    # --------------------------------------------------------

    unique_contexts = []

    seen = set()


    for context in contexts:

        key = (
            context[
                "start_index"
            ],

            context[
                "end_index"
            ],
        )


        if key in seen:

            continue


        seen.add(
            key
        )


        unique_contexts.append(
            context
        )


    return unique_contexts


# ============================================================
# QUANTITATIVE CONTEXT SIGNAL
# ============================================================

def _context_has_quantitative_benchmark_signal(context_text):
    """
    Detect whether a Gemini context visibly contains enough signal for a
    focused recovery request: an exact validated benchmark, at least one
    numeric value, and benchmark/result language.
    """

    if not context_text:
        return False

    text = str(context_text)

    has_benchmark = any(
        _contains_exact_benchmark(text, benchmark)
        for benchmark in VALIDATED_BENCHMARKS
    )

    if not has_benchmark:
        return False

    has_number = bool(
        re.search(
            r"(?<![\w.-])\d+(?:\.\d+)?(?:\s*%)?(?![\w.-])",
            text
        )
    )

    if not has_number:
        return False

    lowered = text.lower()

    return any(
        term in lowered
        for term in RESULT_CONTEXT_TERMS
    )


# ============================================================
# NUMERIC VALUE VALIDATION
# ============================================================

def _numeric_value_appears_in_source(
    value,
    source_text
):
    """
    Verify that the numeric value reported by Gemini is actually
    present in the source evidence.

    Numeric formatting differences such as 72.1 vs 72.10 are treated
    as the same numeric value. Numbers embedded inside model identifiers
    such as Qwen2.5-3B-Instruct are ignored.
    """

    if (
        value is None
        or not source_text
    ):

        return False

    try:

        numeric = float(
            value
        )

    except (
        TypeError,
        ValueError
    ):

        return False

    # Use a token-aware numeric pattern so model identifiers such as
    # Qwen2.5-3B-Instruct are not mistaken for reported scores.
    pattern = re.compile(
        r"(?<![\w.-])"
        r"-?\d+(?:\.\d+)?"
        r"(?:\s*%)?"
        r"(?![\w.-])"
    )

    for match in pattern.finditer(
        str(source_text)
    ):

        raw = match.group(0).replace("%", "").strip()

        try:

            source_numeric = float(raw)

        except (
            TypeError,
            ValueError
        ):

            continue

        if math.isclose(
            source_numeric,
            numeric,
            rel_tol=0.0,
            abs_tol=1e-9,
        ):

            return True

    return False



# ============================================================
# CLAIM SHAPE / TABLE MAPPING VALIDATION
# ============================================================

def _claim_has_single_benchmark(
    claim
):
    """
    Ensure the claim text refers to exactly one validated benchmark.
    """

    if not isinstance(
        claim,
        dict
    ):

        return False

    claim_text = str(
        claim.get(
            "claim",
            ""
        )
    ).strip()

    benchmark_name = _canonical_benchmark(
        claim.get(
            "benchmark_name"
        )
    )

    if not claim_text or benchmark_name is None:
        return False

    mentioned_benchmarks = []

    # Check longer benchmark names first so a variant is never treated
    # as its base benchmark.
    benchmarks_to_check = sorted(
        VALIDATED_BENCHMARKS,
        key=lambda value: len(str(value)),
        reverse=True
    )

    for benchmark in benchmarks_to_check:

        if _contains_exact_benchmark(
            claim_text,
            benchmark
        ):

            mentioned_benchmarks.append(
                benchmark
            )

    if len(
        mentioned_benchmarks
    ) != 1:

        return False

    return mentioned_benchmarks[0] == benchmark_name


def _extract_result_numbers(
    claim_text
):
    """
    Extract standalone performance-like numbers while ignoring numbers
    embedded inside model identifiers such as Qwen2.5-3B-Instruct.
    """

    if not claim_text:
        return []

    pattern = re.compile(
        r"(?<![\w.-])"
        r"-?\d+(?:\.\d+)?"
        r"(?:\s*%)?"
        r"(?![\w.-])"
    )

    values = []

    for match in pattern.finditer(
        str(claim_text)
    ):

        raw = match.group(
            0
        ).strip()

        cleaned = raw.replace(
            "%",
            ""
        ).strip()

        try:

            values.append(
                float(
                    cleaned
                )
            )

        except (
            TypeError,
            ValueError
        ):

            continue

    return values


def _claim_contains_exactly_one_reported_value(
    claim
):
    """
    Require exactly one standalone result number in the claim text and
    require it to equal reported_value.
    """

    if not isinstance(
        claim,
        dict
    ):

        return False

    claim_text = str(
        claim.get(
            "claim",
            ""
        )
    ).strip()

    reported_value = claim.get(
        "reported_value"
    )

    if not claim_text or reported_value is None:
        return False

    try:

        numeric_value = float(
            reported_value
        )

    except (
        TypeError,
        ValueError
    ):

        return False

    if not math.isfinite(
        numeric_value
    ):

        return False

    claim_numbers = _extract_result_numbers(
        claim_text
    )

    if len(
        claim_numbers
    ) != 1:

        return False

    return abs(
        claim_numbers[0]
        - numeric_value
    ) < 1e-9


def _extract_table_header_and_row(
    source_text
):
    """
    Extract table header/row columns from the two formats commonly emitted
    by Gemini for PDF-derived tables:

    1. Explicit format:
         Header: Model | MMLU | MMLU-Pro
         Row:    Model-A | 72.4 | 61.2

    2. Whitespace-normalized format:
         Model MMLU MMLU-Pro
         Model-A 72.4 61.2

    For PDF text containing a table caption followed by a pipe-delimited
    header, the parser isolates the actual header beginning at the "Model"
    column so benchmark mentions in the caption do not shift column order.

    The parser is conservative. When the row and header cannot be mapped
    unambiguously, it returns (None, None) so validation does not invent
    a column mapping.
    """

    if not source_text:
        return None, None

    text = str(source_text).strip()

    # --------------------------------------------------------
    # Format 1: explicit Header:/Row:
    # --------------------------------------------------------

    match = re.search(
        r"Header\s*:\s*(.*?)"
        r"\s*Row\s*:\s*(.*)",
        text,
        flags=re.IGNORECASE | re.DOTALL
    )

    if match:

        header_text = match.group(1).strip()
        row_text = match.group(2).strip()

        if "|" in header_text and "|" in row_text:

            header_columns = [
                part.strip()
                for part in header_text.split("|")
                if part.strip()
            ]

            row_columns = [
                part.strip()
                for part in row_text.split("|")
                if part.strip()
            ]

            if header_columns and row_columns:
                return header_columns, row_columns

    # --------------------------------------------------------
    # Format 2: whitespace-normalized / pipe-like table.
    # --------------------------------------------------------

    lines = [
        re.sub(r"\s+", " ", line).strip()
        for line in text.splitlines()
        if line.strip()
    ]

    if len(lines) < 2:
        return None, None

    header_candidates = []

    for index, line in enumerate(lines):

        # When a PDF/table extractor places the caption and actual pipe
        # header on the same line, isolate the real header segment.
        header_line = line

        model_pipe_match = re.search(
            r"\bModel\s*\|",
            line,
            flags=re.IGNORECASE,
        )

        if model_pipe_match and "|" in line[model_pipe_match.start():]:
            header_line = line[model_pipe_match.start():].strip()

        # Some PDF extraction outputs collapse "Model" and the first
        # benchmark label into one token, e.g. "ModelMMLU".
        header_line = re.sub(
            r"\bModel(?=MMLU(?:-Pro)?\b)",
            "Model ",
            header_line,
            flags=re.IGNORECASE,
        )

        matches = [
            benchmark
            for benchmark in sorted(
                TABLE_BENCHMARK_NAMES,
                key=lambda value: len(str(value)),
                reverse=True
            )
            if _contains_exact_benchmark(header_line, benchmark)
        ]

        if not matches:
            continue

        # A benchmark mention in a title/caption is not by itself a table
        # header. Require either an explicit model column or multiple
        # benchmark columns.
        has_model_header = bool(
            re.search(
                r"\bModel\b",
                header_line,
                flags=re.IGNORECASE,
            )
        )

        if not has_model_header and len(matches) < 2:
            continue

        header_candidates.append(
            (index, header_line, matches)
        )

    if not header_candidates:
        return None, None

    # Prefer actual model headers, then headers with more benchmark columns.
    header_candidates.sort(
        key=lambda item: (
            "model" not in item[1].lower(),
            -len(item[2]),
            item[0],
        )
    )

    for header_index, header_line, _ in header_candidates:

        benchmark_columns = []
        normalized_header_line = _normalize_benchmark_text(
            header_line
        )

        for benchmark in sorted(
            TABLE_BENCHMARK_NAMES,
            key=lambda value: len(str(value)),
            reverse=True
        ):

            pattern = re.compile(
                rf"(?<![\w-])"
                rf"{re.escape(_normalize_benchmark_text(benchmark))}"
                rf"(?![\w-])",
                flags=re.IGNORECASE,
            )

            for match in pattern.finditer(
                normalized_header_line
            ):

                benchmark_columns.append(
                    (
                        match.start(),
                        benchmark,
                    )
                )

        benchmark_columns.sort(
            key=lambda item: item[0]
        )

        ordered_benchmarks = []
        seen_benchmark_keys = set()

        for _, benchmark in benchmark_columns:
            canonical = _canonical_benchmark(benchmark)
            label = canonical if canonical is not None else benchmark
            key = str(label).strip().lower()

            if key not in seen_benchmark_keys:
                seen_benchmark_keys.add(key)
                ordered_benchmarks.append(label)

        if not ordered_benchmarks:
            continue

        for row_index in range(
            header_index + 1,
            min(len(lines), header_index + 6)
        ):

            row_line = lines[row_index]

            if any(
                _contains_exact_benchmark(
                    row_line,
                    benchmark
                )
                for benchmark in ordered_benchmarks
            ):
                continue

            values = _numeric_values_from_cell(
                row_line
            )

            if len(values) != len(ordered_benchmarks):
                continue

            prefix = re.split(
                r"(?<![\w.-])\d+(?:\.\d+)?(?:\s*%)?(?![\w.-])",
                row_line,
                maxsplit=1,
            )[0].strip()

            row_columns = [prefix] + [
                str(value)
                for value in values
            ]

            header_columns = ["Model"] + ordered_benchmarks

            return header_columns, row_columns

    return None, None

def _benchmark_in_header_cell(
    header_cell
):
    """
    Return the single validated benchmark represented by a header cell.
    """

    if not header_cell:
        return None

    matches = []

    for benchmark in sorted(
        VALIDATED_BENCHMARKS,
        key=lambda value: len(str(value)),
        reverse=True
    ):

        if _contains_exact_benchmark(
            header_cell,
            benchmark
        ):

            matches.append(
                benchmark
            )

    if len(
        matches
    ) == 1:

        return matches[0]

    return None


def _numeric_values_from_cell(
    cell
):
    """
    Extract standalone numeric values from a table cell.
    """

    if not cell:
        return []

    pattern = re.compile(
        r"(?<![\w.-])"
        r"-?\d+(?:\.\d+)?"
        r"(?:\s*%)?"
        r"(?![\w.-])"
    )

    values = []

    for match in pattern.finditer(
        str(cell)
    ):

        cleaned = match.group(
            0
        ).replace(
            "%",
            ""
        ).strip()

        try:

            values.append(
                float(
                    cleaned
                )
            )

        except (
            TypeError,
            ValueError
        ):

            continue

    return values


def _table_value_matches_whitespace_table(
    claim
):
    """
    Validate a benchmark/value mapping when Gemini returned a table without
    explicit Header:/Row: labels or pipe separators.

    The parser is conservative and requires:
    - a header line containing validated benchmark names,
    - a nearby model row,
    - exactly one numeric value per benchmark column, and
    - the claim's model name to be present in that row.

    Returns:
        True  -> mapping verified
        None  -> no usable whitespace table detected
        False -> table detected but mapping is invalid
    """

    if not isinstance(claim, dict):
        return False

    source_text = str(
        claim.get("source_sentence", "") or ""
    ).strip()

    benchmark = _canonical_benchmark(
        claim.get("benchmark_name")
    )

    claim_text = str(
        claim.get("claim", "") or ""
    ).strip()

    if not source_text or benchmark is None or not claim_text:
        return False

    if "header:" in source_text.lower() or "row:" in source_text.lower():
        return None

    # A pipe table is handled by the existing structured-table validator.
    if "|" in source_text:
        return None

    # Extract model name from claim text.
    model_match = re.match(
        r"^\s*(.*?)\s+"
        r"(?:achieves|reports|obtains|scores|gets|has)\s+",
        claim_text,
        flags=re.IGNORECASE,
    )

    if not model_match:
        return None

    model_name = model_match.group(1).strip()

    if not model_name:
        return None

    lines = [
        re.sub(r"\s+", " ", line).strip()
        for line in source_text.splitlines()
        if line.strip()
    ]

    if len(lines) < 2:
        return None

    # Find likely table-header lines containing the selected benchmark.
    # A title/caption that merely mentions MMLU is not a table header.
    header_indices = []

    for index, line in enumerate(lines):

        normalized_line = re.sub(
            r"\bModel(?=MMLU(?:-Pro)?\b)",
            "Model ",
            line,
            flags=re.IGNORECASE,
        )

        if not _contains_exact_benchmark(
            normalized_line,
            benchmark
        ):
            continue

        all_matches = [
            candidate
            for candidate in sorted(
                TABLE_BENCHMARK_NAMES,
                key=lambda value: len(str(value)),
                reverse=True
            )
            if _contains_exact_benchmark(
                normalized_line,
                candidate
            )
        ]

        has_model_header = bool(
            re.search(
                r"\bModel\b",
                normalized_line,
                flags=re.IGNORECASE,
            )
        )

        if not has_model_header and len(all_matches) < 2:
            continue

        header_indices.append(index)

    if not header_indices:
        return None

    for header_index in header_indices:

        header_line = lines[header_index]

        header_line = re.sub(
            r"\bModel(?=MMLU(?:-Pro)?\b)",
            "Model ",
            header_line,
            flags=re.IGNORECASE,
        )

        normalized_header = _normalize_benchmark_text(header_line)

        benchmark_positions = []

        for candidate in sorted(
            TABLE_BENCHMARK_NAMES,
            key=lambda value: len(str(value)),
            reverse=True
        ):

            pattern = re.compile(
                rf"(?<![\w-])"
                rf"{re.escape(_normalize_benchmark_text(candidate))}"
                rf"(?![\w-])",
                flags=re.IGNORECASE,
            )

            for match in pattern.finditer(
                normalized_header
            ):

                benchmark_positions.append(
                    (match.start(), candidate)
                )

        benchmark_positions.sort(
            key=lambda item: item[0]
        )

        ordered_benchmarks = []
        seen_benchmark_keys = set()

        for _, candidate in benchmark_positions:
            canonical = _canonical_benchmark(candidate)
            label = canonical if canonical is not None else candidate
            key = str(label).strip().lower()

            if key not in seen_benchmark_keys:
                seen_benchmark_keys.add(key)
                ordered_benchmarks.append(label)

        if not ordered_benchmarks:
            continue

        if benchmark not in ordered_benchmarks:
            continue

        target_index = ordered_benchmarks.index(
            benchmark
        )

        # Search nearby rows for the model named in the claim.
        for row_index in range(
            header_index + 1,
            min(len(lines), header_index + 6)
        ):

            row_line = lines[row_index]

            if not re.search(
                re.escape(model_name),
                row_line,
                flags=re.IGNORECASE,
            ):
                continue

            # Remove the model identifier before numeric extraction. This
            # avoids treating 2.5 or 3B in Qwen2.5-3B-Instruct as scores.
            model_pattern = re.compile(
                re.escape(model_name),
                flags=re.IGNORECASE,
            )

            row_without_model = model_pattern.sub(
                " ",
                row_line,
                count=1,
            )

            values = _numeric_values_from_cell(
                row_without_model
            )

            if len(values) != len(ordered_benchmarks):
                return False

            try:
                reported_value = float(
                    claim.get("reported_value")
                )
            except (
                TypeError,
                ValueError,
            ):
                return False

            return math.isclose(
                values[target_index],
                reported_value,
                rel_tol=0.0,
                abs_tol=1e-9,
            )

    return None


def _table_value_matches_benchmark(
    claim
):
    """
    Verify that reported_value belongs to the exact table column named
    by benchmark_name when explicit Header/Row evidence is supplied.

    Returns:
        True  -> explicit mapping verified
        None  -> source is not in structured Header/Row form
        False -> structured table is present but mapping is invalid
    """

    if not isinstance(
        claim,
        dict
    ):

        return False

    source_text = str(
        claim.get(
            "source_sentence",
            ""
        )
    ).strip()

    benchmark = _canonical_benchmark(
        claim.get(
            "benchmark_name"
        )
    )

    if not source_text or benchmark is None:
        return False

    header_columns, row_columns = _extract_table_header_and_row(
        source_text
    )

    if (
        header_columns is None
        or row_columns is None
    ):

        return _table_value_matches_whitespace_table(
            claim
        )

    if len(
        header_columns
    ) != len(
        row_columns
    ):

        return False

    benchmark_indices = []

    for index, header_cell in enumerate(
        header_columns
    ):

        if _benchmark_in_header_cell(
            header_cell
        ) == benchmark:

            benchmark_indices.append(
                index
            )

    if len(
        benchmark_indices
    ) != 1:

        return False

    benchmark_index = benchmark_indices[0]

    values = _numeric_values_from_cell(
        row_columns[benchmark_index]
    )

    if len(
        values
    ) != 1:

        return False

    try:

        reported_value = float(
            claim.get(
                "reported_value"
            )
        )

    except (
        TypeError,
        ValueError
    ):

        return False

    return abs(
        values[0]
        - reported_value
    ) < 1e-9


def _split_compound_table_claim(
    claim
):
    """
    Split a compound table claim into one claim per benchmark only when
    the supplied Header/Row evidence provides an explicit mapping.

    No values are calculated or inferred.
    """

    if not isinstance(
        claim,
        dict
    ):

        return []

    claim_text = str(
        claim.get(
            "claim",
            ""
        )
    ).strip()

    source_text = str(
        claim.get(
            "source_sentence",
            ""
        )
    ).strip()

    if not claim_text or not source_text:
        return []

    header_columns, row_columns = _extract_table_header_and_row(
        source_text
    )

    if (
        header_columns is None
        or row_columns is None
        or len(header_columns) != len(row_columns)
    ):

        return []

    # Find benchmark mentions in their order of appearance in the claim.
    # Longer benchmark names are preferred when two names could overlap.
    benchmark_mentions = []

    for benchmark in VALIDATED_BENCHMARKS:

        pattern = re.compile(
            rf"(?<![\w-])"
            rf"{re.escape(benchmark)}"
            rf"(?![\w-])",
            flags=re.IGNORECASE
        )

        match = pattern.search(
            claim_text
        )

        if match:

            benchmark_mentions.append(
                (
                    match.start(),
                    benchmark
                )
            )

    benchmark_mentions.sort(
        key=lambda item: item[0]
    )

    mentioned_benchmarks = [
        benchmark
        for _, benchmark in benchmark_mentions
    ]

    # Remove accidental duplicates while keeping claim order.
    ordered_unique_benchmarks = []

    for benchmark in mentioned_benchmarks:

        if benchmark not in ordered_unique_benchmarks:

            ordered_unique_benchmarks.append(
                benchmark
            )

    mentioned_benchmarks = ordered_unique_benchmarks

    # Only split a genuinely compound claim.
    if len(
        mentioned_benchmarks
    ) <= 1:

        return []

    split_claims = []

    row_model = (
        row_columns[0].strip()
        if row_columns
        else ""
    )

    for benchmark in mentioned_benchmarks:

        matching_columns = []

        for index, header_cell in enumerate(
            header_columns
        ):

            if _benchmark_in_header_cell(
                header_cell
            ) == benchmark:

                matching_columns.append(
                    index
                )

        if len(
            matching_columns
        ) != 1:

            continue

        column_index = matching_columns[0]

        values = _numeric_values_from_cell(
            row_columns[column_index]
        )

        if len(
            values
        ) != 1:

            continue

        value = values[0]

        new_claim = dict(
            claim
        )

        new_claim[
            "benchmark_name"
        ] = benchmark

        new_claim[
            "reported_value"
        ] = value

        if row_model:

            new_claim[
                "claim"
            ] = (
                f"{row_model} achieves "
                f"{value:g} on {benchmark}."
            )

        else:

            new_claim[
                "claim"
            ] = (
                f"The model achieves "
                f"{value:g} on {benchmark}."
            )

        split_claims.append(
            new_claim
        )

    return split_claims


# ============================================================
# GEMINI CLAIM SCHEMA NORMALIZATION
# ============================================================

def _coerce_reported_value(value):
    """
    Convert Gemini numeric output into a plain float when safe.

    Recovery responses sometimes return percentages as strings such as
    "72%". The value is only converted; it is never calculated.
    """

    if value is None:
        return None

    if isinstance(value, (int, float)):
        try:
            numeric = float(value)
        except (TypeError, ValueError):
            return None
        return numeric if math.isfinite(numeric) else None

    text = str(value).strip()
    if not text:
        return None

    text = text.replace("%", "").strip()

    try:
        numeric = float(text)
    except (TypeError, ValueError):
        return None

    return numeric if math.isfinite(numeric) else None


def _normalize_gemini_claim_schema(claim):
    """
    Normalize small schema variations produced by the focused recovery call.

    The main extraction prompt already asks for the canonical schema. The
    recovery prompt may occasionally return aliases such as:

        benchmark   -> benchmark_name
        model       -> model_name
        evaluation_type -> evaluation_setting

    This helper only renames explicit fields and constructs a minimal claim
    sentence when Gemini supplied the model, benchmark, value, and evidence.
    No benchmark result is calculated or inferred.
    """

    if not isinstance(claim, dict):
        return None

    normalized = dict(claim)

    if not normalized.get("benchmark_name") and normalized.get("benchmark"):
        normalized["benchmark_name"] = normalized.get("benchmark")

    if not normalized.get("model_name") and normalized.get("model"):
        normalized["model_name"] = normalized.get("model")

    if not normalized.get("evaluation_setting") and normalized.get("evaluation_type"):
        normalized["evaluation_setting"] = normalized.get("evaluation_type")

    if normalized.get("reported_value") is not None:
        coerced = _coerce_reported_value(normalized.get("reported_value"))
        if coerced is not None:
            normalized["reported_value"] = coerced

    benchmark_name = _canonical_benchmark(
        normalized.get("benchmark_name")
    )

    model_name = str(
        normalized.get("model_name", "") or ""
    ).strip()

    reported_value = normalized.get("reported_value")

    if not normalized.get("claim"):
        if benchmark_name and model_name and reported_value is not None:
            value_text = f"{reported_value:g}" if isinstance(reported_value, (int, float)) else str(reported_value)
            normalized["claim"] = (
                f"{model_name} achieves {value_text} on {benchmark_name}."
            )

    if not normalized.get("section"):
        normalized["section"] = "Unknown"

    if not normalized.get("claim_type"):
        normalized["claim_type"] = "performance_claim"

    if not normalized.get("value_type"):
        metric_text = " ".join(
            [
                str(normalized.get("metric", "") or ""),
                str(normalized.get("claim", "") or ""),
                str(normalized.get("source_sentence", "") or ""),
            ]
        ).lower()

        if "accuracy" in metric_text:
            normalized["value_type"] = "absolute_accuracy"

    return normalized


# ============================================================
# RECOVERY EVIDENCE RECONSTRUCTION
# ============================================================

def _evidence_units(text):
    """
    Split original PDF context into conservative evidence units.

    A unit is either a short sentence-like span or a non-empty line. We use
    this only for recovery, never for ordinary extraction. The purpose is to
    find original text that simultaneously contains the model, benchmark and
    reported value so that recovery cannot manufacture evidence by joining
    unrelated sentences.
    """

    if not text:
        return []

    normalized = str(text).replace("\r\n", "\n").replace("\r", "\n")
    units = []

    # Keep explicit table labels intact.
    for block in re.split(r"\n\s*\n+", normalized):
        block = block.strip()
        if not block:
            continue

        # If the block contains explicit Header:/Row: structure, keep the
        # whole block as one evidence unit.
        if re.search(r"\bHeader\s*:", block, flags=re.IGNORECASE) and re.search(
            r"\bRow\s*:", block, flags=re.IGNORECASE
        ):
            units.append(block)
            continue

        # Otherwise use line-level units first. PDF extraction often puts a
        # complete result on a single line even when sentence punctuation is
        # missing.
        for line in block.splitlines():
            line = re.sub(r"\s+", " ", line).strip()
            if line:
                units.append(line)

        # Also preserve sentence spans for normal prose that wraps across
        # extracted PDF lines.
        sentence_spans = re.split(r"(?<=[.!?])\s+", re.sub(r"\s+", " ", block))
        for span in sentence_spans:
            span = span.strip()
            if span and span not in units:
                units.append(span)

    return units


def _model_and_value_supported(unit, model_name, benchmark, reported_value):
    """
    Return True only when one original evidence unit contains all required
    identity/value components.
    """

    if not unit or not model_name or not benchmark:
        return False

    if not _model_identity_supported_by_source(model_name, unit):
        return False

    if not _contains_exact_benchmark(unit, benchmark):
        return False

    return _numeric_value_appears_in_source(reported_value, unit)


def _extract_explicit_header_row_evidence(context_text, model_name, benchmark, reported_value):
    """
    Recover a complete original Header:/Row: table block when its positional
    mapping explicitly supports the requested benchmark/value.

    No values are inferred. The returned block is copied from the supplied
    context.
    """

    if not context_text:
        return None

    lines = [
        line.rstrip()
        for line in str(context_text).replace("\r\n", "\n").replace("\r", "\n").splitlines()
    ]

    for index, line in enumerate(lines):
        if not re.match(r"^\s*Header\s*:", line, flags=re.IGNORECASE):
            continue

        header_lines = [re.sub(r"^\s*Header\s*:\s*", "", line, flags=re.IGNORECASE).strip()]
        row_lines = []
        row_index = None

        for j in range(index + 1, min(len(lines), index + 8)):
            if re.match(r"^\s*Header\s*:", lines[j], flags=re.IGNORECASE):
                break
            if re.match(r"^\s*Row\s*:", lines[j], flags=re.IGNORECASE):
                row_index = j
                row_lines.append(
                    re.sub(r"^\s*Row\s*:\s*", "", lines[j], flags=re.IGNORECASE).strip()
                )
                break
            if lines[j].strip():
                header_lines.append(lines[j].strip())

        if row_index is None:
            continue

        row_text = " ".join(part for part in row_lines if part).strip()
        header_text = " ".join(part for part in header_lines if part).strip()

        if not header_text or not row_text:
            continue

        evidence = f"Header: {header_text}\nRow: {row_text}"

        if not _model_identity_supported_by_source(model_name, evidence):
            continue

        if not _contains_exact_benchmark(evidence, benchmark):
            continue

        # Pipe-delimited Header/Row: positional validation.
        if "|" in header_text and "|" in row_text:
            header_columns = [part.strip() for part in header_text.split("|") if part.strip()]
            row_columns = [part.strip() for part in row_text.split("|") if part.strip()]
            if len(header_columns) != len(row_columns):
                continue

            matching = [
                i for i, cell in enumerate(header_columns)
                if _benchmark_in_header_cell(cell) == benchmark
            ]
            if len(matching) != 1:
                continue

            values = _numeric_values_from_cell(row_columns[matching[0]])
            if len(values) != 1:
                continue

            if not math.isclose(float(values[0]), float(reported_value), rel_tol=0.0, abs_tol=1e-9):
                continue

            return evidence

    return None


def _source_has_explicit_evaluation_setting(source_text):
    """
    Return True when the supplied evidence explicitly states an evaluation
    shot-setting such as 0-shot, 5-shot, few-shot, or zero-shot.
    """

    if not source_text:
        return False

    normalized = " ".join(str(source_text).split()).lower()

    return bool(
        re.search(r"\b(?:zero|one|two|few)[\s-]+shot\b", normalized)
        or re.search(r"\b\d+[\s-]+shot\b", normalized)
        or re.search(r"\bno[\s-]+examples?\b", normalized)
    )


def _extract_benchmark_columns_from_header(header_line):
    """
    Return validated benchmark columns in their order of appearance.

    This helper is intentionally based on the same benchmark normalization
    rules used by the existing table validators.
    """

    if not header_line:
        return []

    normalized_header = _normalize_benchmark_text(header_line)
    benchmark_positions = []

    for candidate in sorted(
        TABLE_BENCHMARK_NAMES,
        key=lambda value: len(str(value)),
        reverse=True,
    ):
        normalized_candidate = _normalize_benchmark_text(candidate)

        pattern = re.compile(
            rf"(?<![\w-])"
            rf"{re.escape(normalized_candidate)}"
            rf"(?![\w-])",
            flags=re.IGNORECASE,
        )

        for match in pattern.finditer(normalized_header):
            benchmark_positions.append(
                (match.start(), candidate)
            )

    benchmark_positions.sort(
        key=lambda item: item[0]
    )

    ordered = []
    seen = set()

    for _, candidate in benchmark_positions:
        canonical = _canonical_benchmark(candidate)
        label = canonical if canonical is not None else candidate
        key = str(label).strip().lower()

        if key not in seen:
            seen.add(key)
            ordered.append(label)

    return ordered


def _fulltext_table_evidence_for_claim(
    full_text,
    model_name,
    benchmark,
    reported_value,
):
    """
    Recover the exact table header + model row from the FULL paper text.

    This is deliberately deterministic. It never asks Gemini to reconstruct a
    missing header. It scans the original extracted paper text for a nearby
    header/row pair and validates the reported value against the benchmark
    column position before returning the copied evidence.

    Handles both:
      - explicit Header:/Row: blocks
      - ordinary PDF text where header and row are separate lines
    """

    if not full_text or not model_name or not benchmark:
        return None

    # ------------------------------------------------------------
    # 1. First try the existing explicit Header:/Row: parser over
    #    the complete paper text.
    # ------------------------------------------------------------

    explicit = _extract_explicit_header_row_evidence(
        full_text,
        model_name,
        benchmark,
        reported_value,
    )

    if explicit:
        return explicit

    # ------------------------------------------------------------
    # 2. Scan normal line-oriented PDF text.
    # ------------------------------------------------------------

    normalized_full_text = (
        str(full_text)
        .replace("\r\n", "\n")
        .replace("\r", "\n")
    )

    raw_lines = [
        line.rstrip()
        for line in normalized_full_text.splitlines()
    ]

    # Keep line positions intact; only normalize repeated spaces for matching.
    lines = [
        re.sub(r"\s+", " ", line).strip()
        for line in raw_lines
    ]

    normalized_model = _normalize_benchmark_text(
        str(model_name)
    ).strip()

    if not normalized_model:
        return None

    model_pattern = re.compile(
        rf"(?<![\w-])"
        rf"{re.escape(normalized_model)}"
        rf"(?![\w-])",
        flags=re.IGNORECASE,
    )

    for row_index, row_line in enumerate(lines):

        if not model_pattern.search(
            _normalize_benchmark_text(row_line)
        ):
            # Controlled fallback for PDF line-break/spacing differences.
            compact_row = re.sub(
                r"[^a-z0-9]",
                "",
                _normalize_benchmark_text(row_line).lower(),
            )
            compact_model = re.sub(
                r"[^a-z0-9]",
                "",
                normalized_model.lower(),
            )

            if not compact_model or compact_model not in compact_row:
                continue

        # Search backward for the nearest *structured table* header.
        #
        # Important: a normal prose sentence can contain both the benchmark
        # name and the word "model" (or a model identifier).  Such a sentence
        # must never be promoted to synthetic Header:/Row: evidence.  Require
        # visible table structure before considering a line as a header.
        header_start = max(
            0,
            row_index - FULLTEXT_TABLE_LOOKBACK_LINES,
        )

        for header_index in range(
            row_index - 1,
            header_start - 1,
            -1,
        ):
            header_line = lines[header_index]

            if not _contains_exact_benchmark(
                header_line,
                benchmark,
            ):
                continue

            header_lower = header_line.lower()
            has_pipe_structure = "|" in header_line
            has_table_header_token = bool(
                re.search(r"\b(?:model|models)\b", header_lower)
            )

            # For the ordinary line-oriented PDF fallback, at least one of
            # these must be true.  The pipe case covers extracted Markdown /
            # table-like text; the model-token case covers whitespace tables
            # whose columns are separated by spaces.
            if not (has_pipe_structure or has_table_header_token):
                continue

            ordered_benchmarks = _extract_benchmark_columns_from_header(
                header_line
            )

            if not ordered_benchmarks:
                continue

            if benchmark not in ordered_benchmarks:
                continue

            target_index = ordered_benchmarks.index(
                benchmark
            )

            # The normal case is that the model row itself contains all
            # benchmark values.
            candidate_rows = [(row_index, row_line)]

            # Some PDF extractors split model and numbers across the next
            # one or two lines. Include a small forward neighborhood.
            for next_index in range(
                row_index + 1,
                min(
                    len(lines),
                    row_index + FULLTEXT_TABLE_LOOKAHEAD_LINES + 1,
                ),
            ):
                candidate_rows.append(
                    (next_index, lines[next_index])
                )

            for candidate_row_index, candidate_row in candidate_rows:

                normalized_candidate_row = _normalize_benchmark_text(
                    candidate_row
                )

                # Remove only the first model identifier occurrence before
                # extracting numeric benchmark values.
                if model_pattern.search(normalized_candidate_row):
                    row_without_model = model_pattern.sub(
                        " ",
                        normalized_candidate_row,
                        count=1,
                    )
                else:
                    compact_model = re.sub(
                        r"[^a-z0-9]",
                        "",
                        normalized_model.lower(),
                    )

                    # Controlled compact fallback: remove the model token
                    # from a compact copy only for validation.
                    compact_row = re.sub(
                        r"[^a-z0-9.\-]",
                        "",
                        normalized_candidate_row.lower(),
                    )

                    if compact_model not in compact_row:
                        continue

                    row_without_model = normalized_candidate_row

                values = _numeric_values_from_cell(
                    row_without_model
                )

                # A valid table row must expose one numeric value per
                # benchmark column represented by the header.  This blocks
                # prose such as "accuracy of 0.949 for gpt-4o" from being
                # wrapped as a fake Header:/Row: pair.
                if len(values) != len(ordered_benchmarks):
                    continue

                try:
                    reported_numeric = float(
                        reported_value
                    )
                except (
                    TypeError,
                    ValueError,
                ):
                    continue

                if not math.isclose(
                    values[target_index],
                    reported_numeric,
                    rel_tol=0.0,
                    abs_tol=1e-9,
                ):
                    continue

                # Verify the model is actually supported by the candidate
                # row, not just by the surrounding paper.
                if not _model_identity_supported_by_source(
                    model_name,
                    candidate_row,
                ):
                    compact_candidate = re.sub(
                        r"[^a-z0-9]",
                        "",
                        candidate_row.lower(),
                    )
                    compact_model = re.sub(
                        r"[^a-z0-9]",
                        "",
                        normalized_model.lower(),
                    )
                    if (
                        not compact_model
                        or compact_model not in compact_candidate
                    ):
                        continue

                evidence = (
                    f"Header: {header_line}\n"
                    f"Row: {candidate_row}"
                )

                # Final safety checks.
                if not _contains_exact_benchmark(
                    evidence,
                    benchmark,
                ):
                    continue

                if not _numeric_value_appears_in_source(
                    reported_numeric,
                    evidence,
                ):
                    continue

                return evidence

    return None


def _reconstruct_recovery_evidence(
    claim,
    context_text,
    full_text="",
):
    """
    Recover stronger source evidence for a Gemini claim.

    Recovery priority:
        1. Keep current source_sentence when it already establishes the
           evaluation setting.
        2. Search the current Gemini context.
        3. Search the FULL paper text.

    The full-paper search is deterministic and does not invent values or
    mappings. It only returns copied source text after validating that the
    exact model, benchmark, and reported value align with the table column.

    This fixes the failure mode where a table header such as:
        MMLU (0-shot)
    is outside the current Gemini context even though the model row is inside
    it.
    """

    if not isinstance(claim, dict):
        return False

    current_source = str(
        claim.get("source_sentence", "") or ""
    ).strip()

    # Do not overwrite already-good evidence.
    if current_source and _source_has_explicit_evaluation_setting(
        current_source
    ):
        return True

    model_name = str(
        claim.get("model_name", "") or ""
    ).strip()

    benchmark = _canonical_benchmark(
        claim.get("benchmark_name")
    )

    reported_value = _coerce_reported_value(
        claim.get("reported_value")
    )

    if (
        not model_name
        or not benchmark
        or reported_value is None
    ):
        return False

    # ------------------------------------------------------------
    # 1. Search the current bounded Gemini context.
    # ------------------------------------------------------------

    contextual_evidence = _extract_explicit_header_row_evidence(
        context_text,
        model_name,
        benchmark,
        reported_value,
    )

    if contextual_evidence:
        claim["source_sentence"] = contextual_evidence
        return True

    # Also try the normal PDF table parser over the current context.
    temp_claim = dict(claim)
    temp_claim["source_sentence"] = current_source

    if (
        current_source
        and _table_value_matches_whitespace_table(temp_claim) is True
        and _source_has_explicit_evaluation_setting(current_source)
    ):
        return True

    # ------------------------------------------------------------
    # 2. Search the FULL paper text.
    # ------------------------------------------------------------

    fulltext_evidence = _fulltext_table_evidence_for_claim(
        full_text,
        model_name,
        benchmark,
        reported_value,
    )

    if fulltext_evidence:
        claim["source_sentence"] = fulltext_evidence

        print(
            "[extract] recovered full-paper table evidence: "
            f"{model_name} | {benchmark} | {reported_value}"
        )

        return True

    # ------------------------------------------------------------
    # 3. If no stronger evidence was found, preserve the original
    #    source_sentence. It may still be valid for storage even
    #    though evaluation setting remains unknown.
    # ------------------------------------------------------------

    return False



def _normalize_malformed_whitespace_table_evidence(
    claim
):
    """
    Normalize PDF-extracted whitespace table evidence into the same explicit
    Header:/Row: representation used by the normal table path.

    This is specifically for cases such as:

        ModelMMLU
        (0-shot)MMLU-Pro
        (0-shot)Mobile-MMLU
        (0-shot)Mobile-MMLU-Pro
        (0-shot)
        Mobile-Friendly Models
        Falcon3-3B-Instruct 55.8 22.3 42.6 37.2

    The transformation is accepted only when:
      - the exact model row is found,
      - benchmark columns are identifiable in order,
      - there is exactly one numeric value per benchmark column, and
      - the requested benchmark column contains the requested reported value.

    Shot labels are assigned positionally only when their count equals the
    number of benchmark columns. This keeps the transformation deterministic
    rather than guessing from unrelated prose.
    """

    if not isinstance(claim, dict):
        return False

    source_text = str(claim.get("source_sentence", "") or "").strip()

    if not source_text:
        return False

    # Already normalized: do not touch it.
    if re.search(r"\bHeader\s*:", source_text, flags=re.IGNORECASE) and re.search(
        r"\bRow\s*:", source_text, flags=re.IGNORECASE
    ):
        return False

    model_name = str(
        claim.get("model_name", "") or ""
    ).strip()

    benchmark = _canonical_benchmark(
        claim.get("benchmark_name")
    )

    reported_value = _coerce_reported_value(
        claim.get("reported_value")
    )

    if not model_name or not benchmark or reported_value is None:
        return False

    lines = [
        re.sub(r"\s+", " ", line).strip()
        for line in source_text.splitlines()
        if line.strip()
    ]

    if len(lines) < 2:
        return False

    # Locate the exact model row and require a non-empty numeric sequence.
    row_index = None
    row_line = None

    model_pattern = re.compile(
        re.escape(model_name),
        flags=re.IGNORECASE,
    )

    for index, line in enumerate(lines):

        if not model_pattern.search(line):
            continue

        row_without_model = model_pattern.sub(" ", line, count=1)
        values = _numeric_values_from_cell(row_without_model)

        if values:
            row_index = index
            row_line = line
            break

    if row_index is None or row_line is None:
        return False

    # Look backward for the closest plausible table-header line. Captions can
    # also mention MMLU, so require a Model token or the known ModelMMLU PDF
    # artifact rather than accepting a benchmark mention alone.
    header_start = None

    for index in range(row_index - 1, max(-1, row_index - 13), -1):
        candidate = lines[index]
        has_model_marker = bool(
            re.search(r"\bModel\b", candidate, flags=re.IGNORECASE)
            or re.search(r"\bModelMMLU\b", candidate, flags=re.IGNORECASE)
        )
        has_benchmark = any(
            _contains_exact_benchmark(candidate, name)
            for name in TABLE_BENCHMARK_NAMES
        )

        if has_model_marker and has_benchmark:
            header_start = index
            break

    if header_start is None:
        return False

    header_lines = lines[header_start:row_index]

    # Discard obvious table-section labels between the header and row.
    header_lines = [
        line
        for line in header_lines
        if line.lower() not in {
            "mobile-friendly models",
            "large models",
            "small models",
        }
    ]

    if not header_lines:
        return False

    header_blob = " ".join(header_lines)

    # Normalize the known PDF artifact.
    header_blob = re.sub(
        r"\bModel(?=MMLU\b)",
        "Model ",
        header_blob,
        flags=re.IGNORECASE,
    )

    # Normalize shot labels that were extracted before the following
    # benchmark name rather than after it.
    header_blob = re.sub(
        r"\((zero|one|two|few|\d+)[-\s]?shot\)\s*(?=([A-Za-z0-9][A-Za-z0-9._:+/\-]*))",
        lambda match: " | " + match.group(2) + " (" + match.group(1).lower() + "-shot)",
        header_blob,
        flags=re.IGNORECASE,
    )

    # Extract benchmark columns in left-to-right order, preferring variants
    # before base names so MMLU is never taken from inside MMLU-Pro.
    benchmark_hits = []

    normalized_header = _normalize_benchmark_text(header_blob)

    for candidate in sorted(
        TABLE_BENCHMARK_NAMES,
        key=lambda value: len(str(value)),
        reverse=True,
    ):
        pattern = re.compile(
            rf"(?<![\w-])"
            rf"{re.escape(_normalize_benchmark_text(candidate))}"
            rf"(?![\w-])",
            flags=re.IGNORECASE,
        )

        for match in pattern.finditer(normalized_header):
            benchmark_hits.append((match.start(), candidate))

    benchmark_hits.sort(key=lambda item: item[0])

    ordered_benchmarks = []
    seen = set()

    # Keep one stable display spelling for benchmark headers. This prevents
    # downstream agents from seeing cosmetic variants such as "mobile-mmlu"
    # and "Mobile-MMLU" as different header labels.
    benchmark_display_lookup = {
        str(name).strip().lower(): name
        for name in TABLE_BENCHMARK_NAMES
    }

    benchmark_display_lookup.update({
        "mmlu": "MMLU",
        "mmlu-pro": "MMLU-Pro",
        "mobile-mmlu": "Mobile-MMLU",
        "mobile-mmlu-pro": "Mobile-MMLU-Pro",
        "video-mmlu": "Video-MMLU",
        "video-mmlu-pro": "Video-MMLU-Pro",
        "tr-mmlu": "TR-MMLU",
        "mmlu-sr": "MMLU-SR",
    })

    for _, candidate in benchmark_hits:
        canonical = _canonical_benchmark(candidate)
        raw_label = canonical if canonical is not None else candidate
        label = benchmark_display_lookup.get(
            str(raw_label).strip().lower(),
            raw_label,
        )
        key = str(label).lower()
        if key not in seen:
            seen.add(key)
            ordered_benchmarks.append(label)

    if not ordered_benchmarks or benchmark not in ordered_benchmarks:
        return False

    # Extract ordered shot labels. Assign them positionally only when the
    # count is exactly equal to the number of benchmark columns.
    shot_labels = re.findall(
        r"\((zero|one|two|few|\d+)[-\s]?shot\)",
        header_blob,
        flags=re.IGNORECASE,
    )

    normalized_shots = []
    for shot in shot_labels:
        shot_lower = shot.lower()
        if shot_lower == "zero":
            normalized_shots.append("0-shot")
        elif shot_lower == "one":
            normalized_shots.append("1-shot")
        elif shot_lower == "two":
            normalized_shots.append("2-shot")
        elif shot_lower == "few":
            normalized_shots.append("few-shot")
        else:
            normalized_shots.append(f"{shot_lower}-shot")

    benchmark_labels = list(ordered_benchmarks)
    if len(normalized_shots) == len(benchmark_labels):
        benchmark_labels = [
            f"{name} ({setting})"
            for name, setting in zip(benchmark_labels, normalized_shots)
        ]

    # Remove model identifier before extracting performance values so model
    # versions such as Qwen2.5-7B do not create extra numeric cells.
    row_without_model = model_pattern.sub(" ", row_line, count=1)
    values = _numeric_values_from_cell(row_without_model)

    if len(values) != len(ordered_benchmarks):
        return False

    target_index = ordered_benchmarks.index(benchmark)

    if not math.isclose(
        float(values[target_index]),
        float(reported_value),
        rel_tol=0.0,
        abs_tol=1e-9,
    ):
        return False

    normalized_header_columns = ["Model"] + benchmark_labels
    normalized_row_columns = [model_name] + [str(value) for value in values]

    claim["source_sentence"] = (
        "Header:\n"
        + " | ".join(normalized_header_columns)
        + "\n\nRow:\n"
        + " | ".join(normalized_row_columns)
    )

    return True

# ============================================================
# CLAIM VALIDATION
# ============================================================

def _validate_claim(
    claim
):
    """
    Strictly validate one Gemini-generated claim.

    A claim must satisfy ALL of the following:

    - required fields present
    - exact validated benchmark
    - benchmark present in source evidence
    - benchmark present in claim text
    - exactly one benchmark in claim text
    - numeric reported value
    - exactly one reported performance number in claim text
    - numeric value present in source evidence
    - explicit table benchmark/value mapping when structured table
      evidence is supplied
    - valid claim type
    - valid value type
    - valid improvement semantics
    """

    # --------------------------------------------------------
    # Basic object validation
    # --------------------------------------------------------

    if not isinstance(
        claim,
        dict
    ):

        return False


    # --------------------------------------------------------
    # Required fields
    # --------------------------------------------------------

    required_fields = (

        "claim",
        "source_sentence",
        "section",
        "claim_type",
        "benchmark_name",
        "reported_value",
        "value_type",

    )


    for field in required_fields:

        if field not in claim:

            return False


    # --------------------------------------------------------
    # Claim text
    # --------------------------------------------------------

    claim_text = str(
        claim.get(
            "claim",
            ""
        )
    ).strip()


    if not claim_text:

        return False


    # --------------------------------------------------------
    # Source evidence
    # --------------------------------------------------------

    source_text = str(
        claim.get(
            "source_sentence",
            ""
        )
    ).strip()


    if not source_text:

        return False


    # --------------------------------------------------------
    # Benchmark
    # --------------------------------------------------------

    benchmark = _canonical_benchmark(
        claim.get(
            "benchmark_name"
        )
    )


    if benchmark is None:

        return False


    # Normalize Gemini's casing to configured casing.
    claim[
        "benchmark_name"
    ] = benchmark


    # --------------------------------------------------------
    # Benchmark must appear EXACTLY in source
    # --------------------------------------------------------

    if not _contains_exact_benchmark(
        source_text,
        benchmark
    ):

        return False


    # --------------------------------------------------------
    # Benchmark must appear EXACTLY in claim
    # --------------------------------------------------------

    if not _contains_exact_benchmark(
        claim_text,
        benchmark
    ):

        return False


    # --------------------------------------------------------
    # Prevent variant confusion
    # --------------------------------------------------------

    if benchmark == "MMLU":

        lowered_claim = (
            claim_text.lower()
        )


        for variant in BENCHMARK_VARIANTS:

            if variant in lowered_claim:

                return False


    # --------------------------------------------------------
    # Claim shape
    # --------------------------------------------------------

    if not _claim_has_single_benchmark(
        claim
    ):

        return False


    if not _claim_contains_exactly_one_reported_value(
        claim
    ):

        return False


    # --------------------------------------------------------
    # Specific model identity
    # --------------------------------------------------------

    # Generic labels such as "GPT" are unsafe for cross-paper comparison.
    # Require a specific model identifier and verify it against the source.
    if not _validate_model_identity(
        claim
    ):

        return False


    # --------------------------------------------------------
    # Claim type
    # --------------------------------------------------------

    allowed_claim_types = {

        "performance_claim",
        "finding",
        "conclusion",

    }


    if claim.get(
        "claim_type"
    ) not in allowed_claim_types:

        return False


    # --------------------------------------------------------
    # Value type
    # --------------------------------------------------------

    allowed_value_types = {

        "absolute_accuracy",
        "absolute_improvement",
        "relative_improvement",

    }


    value_type = claim.get(
        "value_type"
    )


    if value_type not in allowed_value_types:

        return False


    # --------------------------------------------------------
    # REPORTED VALUE IS REQUIRED
    # --------------------------------------------------------

    reported_value = claim.get(
        "reported_value"
    )


    if reported_value is None:

        return False


    # --------------------------------------------------------
    # Numeric value
    # --------------------------------------------------------

    try:

        numeric_value = float(
            reported_value
        )

    except (
        TypeError,
        ValueError
    ):

        return False


    # --------------------------------------------------------
    # Finite number
    # --------------------------------------------------------

    if not math.isfinite(
        numeric_value
    ):

        return False


    # --------------------------------------------------------
    # Accuracy range
    # --------------------------------------------------------

    if value_type == "absolute_accuracy":

        if (
            numeric_value < 0
            or numeric_value > 100
        ):

            return False


    # --------------------------------------------------------
    # Numeric value must appear in source
    # --------------------------------------------------------

    if not _numeric_value_appears_in_source(
        numeric_value,
        source_text
    ):

        return False


    # --------------------------------------------------------
    # Explicit table benchmark/value mapping
    # --------------------------------------------------------

    table_mapping_valid = _table_value_matches_benchmark(
        claim
    )

    # None means this is not the structured Header/Row format.
    if table_mapping_valid is False:

        return False


    # --------------------------------------------------------
    # Improvement validation
    # --------------------------------------------------------

    source_lower = source_text.lower()


    if value_type == "absolute_improvement":

        improvement_phrases = (

            "percentage point",
            "percentage points",
            "point improvement",
            "points improvement",

        )


        if not any(
            phrase in source_lower
            for phrase in improvement_phrases
        ):

            return False


    # --------------------------------------------------------
    # Relative improvement validation
    # --------------------------------------------------------

    if value_type == "relative_improvement":

        relative_terms = (

            "relative improvement",
            "relative increase",
            "relative gain",
            "improved by",
            "improvement of",

        )


        if not any(
            term in source_lower
            for term in relative_terms
        ):

            return False


    # --------------------------------------------------------
    # Save normalized numeric value
    # --------------------------------------------------------

    claim[
        "reported_value"
    ] = numeric_value


    return True


# ============================================================
# CLAIM NORMALIZATION FOR DEDUPLICATION
# ============================================================

_DEDUP_MODEL_VERBS = (
    "achieves",
    "achieved",
    "reports",
    "reported",
    "obtains",
    "obtained",
    "scores",
    "scored",
    "gets",
    "got",
    "has",
    "shows",
    "showed",
    "records",
    "recorded",
    "attains",
    "attained",
    "reaches",
    "reached",
)


_DEDUP_GENERIC_SUBJECTS = {
    "model",
    "the model",
    "system",
    "the system",
    "method",
    "the method",
    "approach",
    "the approach",
    "model achieves",
}


def _normalize_for_dedup(
    claim_text
):
    """
    Normalize claim wording for fallback duplicate comparison.

    This is retained for diagnostics/fallbacks, but it is no longer the
    primary duplicate key. Structural measurement fields are preferred.
    """

    normalized = str(
        claim_text
    ).lower().strip()

    normalized = re.sub(
        r"[^a-z0-9.%\s-]",
        "",
        normalized
    )

    normalized = re.sub(
        r"\s+",
        " ",
        normalized
    )

    return normalized.strip()


def _normalize_model_for_dedup(
    model_name
):
    """
    Normalize a model identifier for structural duplicate detection.

    The model identity is used only for deduplication within ONE paper.
    Formatting differences such as hyphens, spaces, and case are ignored.
    """

    if not model_name:
        return ""

    value = str(
        model_name
    ).strip().lower()

    value = re.sub(
        r"^\s*(?:the\s+)?",
        "",
        value
    )

    value = re.sub(
        r"\bmodel\b",
        "",
        value
    )

    value = re.sub(
        r"[^a-z0-9]+",
        "",
        value
    )

    if value in {
        "",
        "the",
        "model",
        "system",
        "method",
        "approach",
    }:
        return ""

    return value



# ============================================================
# MODEL IDENTITY VALIDATION
# ============================================================

# Bare family names are not specific enough to establish that two claims
# refer to the same evaluated model across papers.
_AMBIGUOUS_MODEL_IDENTIFIERS = {
    "gpt",
    "gemini",
    "claude",
    "llama",
    "llama2",
    "llama3",
    "llama4",
    "qwen",
    "mistral",
    "mixtral",
    "phi",
    "palm",
    "palm2",
    "model",
    "themodel",
    "system",
    "thesystem",
    "method",
    "themethod",
    "approach",
    "theapproach",
    "baseline",
    "ourmodel",
    "oursystem",
}

def _extract_model_name_for_validation(
    claim
):
    """
    Extract the literal model subject from the claim text.

    This preserves the original identifier spelling (for example
    "GPT-4o-mini") so it can be attached as claim metadata after validation.
    """

    if not isinstance(
        claim,
        dict
    ):
        return ""

    structured_model_name = str(
        claim.get(
            "model_name",
            ""
        ) or ""
    ).strip()

    if structured_model_name:
        # Preserve the human-readable identifier exactly enough for source
        # matching. Do NOT run the dedup normalizer here because it removes
        # spaces/punctuation (for example, "Mistral Large" ->
        # "mistrallarge"), which can make a valid source match fail.
        structured_model_name = re.sub(
            r"\s+(?:model|system)\s*$",
            "",
            structured_model_name,
            flags=re.IGNORECASE
        ).strip()
        return structured_model_name

    claim_text = str(
        claim.get(
            "claim",
            ""
        ) or ""
    ).strip()

    if not claim_text:
        return ""

    escaped_verbs = sorted(
        (
            re.escape(
                verb
            )
            for verb in _DEDUP_MODEL_VERBS
        ),
        key=len,
        reverse=True
    )

    verb_pattern = "|".join(
        escaped_verbs
    )

    match = re.match(
        rf"^\s*(?P<subject>.+?)\s+(?:{verb_pattern})\b",
        claim_text,
        flags=re.IGNORECASE
    )

    if not match:
        return ""

    subject = match.group(
        "subject"
    ).strip(
        " .,:;-"
    )

    subject = re.sub(
        r"^(?:the|a|an)\s+",
        "",
        subject,
        flags=re.IGNORECASE
    ).strip()

    # "GPT-4o model" -> "GPT-4o"
    subject = re.sub(
        r"\s+(?:model|system)\s*$",
        "",
        subject,
        flags=re.IGNORECASE
    ).strip()

    return subject


def _normalize_model_identity_for_validation(
    model_name
):
    """
    Normalize a model label only for ambiguity checks.
    """

    if not model_name:
        return ""

    normalized = str(
        model_name
    ).strip().lower()

    normalized = re.sub(
        r"[^a-z0-9]+",
        "",
        normalized
    )

    return normalized


def _is_ambiguous_model_identity(
    model_name
):
    """
    Return True when the model label is too generic to establish exact
    cross-paper model identity.
    """

    normalized = _normalize_model_identity_for_validation(
        model_name
    )

    if not normalized:
        return True

    if normalized in _AMBIGUOUS_MODEL_IDENTIFIERS:
        return True

    # Common generic forms such as "GPT model" are normalized above to
    # "gpt" after the trailing descriptor is removed.
    return False


def _model_identity_supported_by_source(
    model_name,
    source_text
):
    """
    Verify that the extracted model identifier is visibly present in the
    supporting source evidence.

    A model name generated by Gemini is not accepted when it cannot be found
    in the exact source evidence attached to the claim.
    """

    if not model_name or not source_text:
        return False

    # Normalize line breaks/whitespace and common Unicode dash forms while
    # preserving the model's meaningful tokens. This allows source variants
    # such as "Llama-3.2-1B-Instruct" vs. line-broken PDF text to match.
    normalized_source = _normalize_benchmark_text(
        str(source_text)
    )
    normalized_model = _normalize_benchmark_text(
        str(model_name)
    ).strip()

    if not normalized_model:
        return False

    # First try an exact token-aware match.
    pattern = re.compile(
        rf"(?<![\w-])"
        rf"{re.escape(normalized_model)}"
        rf"(?![\w-])",
        flags=re.IGNORECASE
    )

    if pattern.search(normalized_source):
        return True

    # PDF extraction may insert spaces around hyphens. Compare a compact
    # representation as a controlled fallback, still requiring the whole
    # model identifier to occur in the evidence.
    compact_source = re.sub(
        r"[^a-z0-9]",
        "",
        normalized_source.lower()
    )
    compact_model = re.sub(
        r"[^a-z0-9]",
        "",
        normalized_model.lower()
    )

    return bool(
        compact_model
        and compact_model in compact_source
    )


def _validate_model_identity(
    claim
):
    """
    Validate and attach a specific model identity.

    Returns:
        True  -> explicit model identity is supported by source
        False -> identity is missing, generic, or unsupported
    """

    model_name = _extract_model_name_for_validation(
        claim
    )

    if not model_name:
        return False

    if _is_ambiguous_model_identity(
        model_name
    ):
        return False

    source_text = str(
        claim.get(
            "source_sentence",
            ""
        ) or ""
    ).strip()

    validation_context = str(
        claim.get(
            "_validation_context",
            ""
        ) or ""
    ).strip()

    # Prefer the exact evidence sentence, but allow the surrounding bounded
    # context to establish the named model when the sentence itself says
    # "the model". The result still has to pass all benchmark/table checks.
    if not _model_identity_supported_by_source(
        model_name,
        source_text
    ) and not _model_identity_supported_by_source(
        model_name,
        validation_context
    ):
        return False

    claim[
        "model_name"
    ] = model_name

    # Preserve useful structured metadata for downstream components without
    # requiring a database/schema change at this stage.
    claim[
        "evaluation_setting"
    ] = _extract_setting_for_dedup(
        claim
    ) or ""

    metric = _extract_metric_for_dedup(
        claim
    )

    if (
        not metric
        and claim.get(
            "value_type"
        ) == "absolute_accuracy"
    ):
        metric = "accuracy"

    claim[
        "metric"
    ] = metric

    return True


def _extract_model_for_dedup(
    claim
):
    """
    Extract the model subject from common claim wording.

    Examples:
        GPT-4o achieves 84.5 on MMLU.
        Qwen2.5-3B-Instruct achieves 65.4 on MMLU.
        GPT-4o achieves an average accuracy of 0.845 on MMLU.

    The parser intentionally returns an empty string for generic subjects
    such as "the model", because guessing the identity would make
    deduplication unsafe.
    """

    if not isinstance(
        claim,
        dict
    ):
        return ""

    claim_text = str(
        claim.get(
            "claim",
            ""
        ) or ""
    ).strip()

    if not claim_text:
        return ""

    escaped_verbs = sorted(
        (
            re.escape(
                verb
            )
            for verb in _DEDUP_MODEL_VERBS
        ),
        key=len,
        reverse=True
    )

    verb_pattern = "|".join(
        escaped_verbs
    )

    match = re.match(
        rf"^\s*(?P<subject>.+?)\s+(?:{verb_pattern})\b",
        claim_text,
        flags=re.IGNORECASE
    )

    if not match:
        return ""

    subject = match.group(
        "subject"
    ).strip(
        " .,:;-"
    )

    # Remove common determiners.
    subject = re.sub(
        r"^(?:the|a|an)\s+",
        "",
        subject,
        flags=re.IGNORECASE
    ).strip()

    if subject.lower() in _DEDUP_GENERIC_SUBJECTS:
        return ""

    return _normalize_model_for_dedup(
        subject
    )


def _extract_setting_for_dedup(
    claim
):
    """
    Extract an explicitly stated evaluation setting.

    Examples:
        0-shot
        5-shot
        few-shot
        zero-shot

    Returns "" when the setting cannot be established explicitly.
    """

    if not isinstance(
        claim,
        dict
    ):
        return ""

    combined_text = " ".join(
        [
            str(
                claim.get(
                    "claim",
                    ""
                ) or ""
            ),
            str(
                claim.get(
                    "source_sentence",
                    ""
                ) or ""
            ),
        ]
    )

    normalized = re.sub(
        r"\s+",
        " ",
        combined_text
    ).strip().lower()

    zero_shot_patterns = (
        r"\bzero[\s-]+shot\b",
        r"\b0[\s-]+shot\b",
    )

    for pattern in zero_shot_patterns:
        if re.search(
            pattern,
            normalized
        ):
            return "0-shot"

    shot_match = re.search(
        r"\b([1-9]\d*)[\s-]+shot\b",
        normalized
    )

    if shot_match:
        return (
            f"{shot_match.group(1)}-shot"
        )

    if re.search(
        r"\bfew[\s-]+shot\b",
        normalized
    ):
        return "few-shot"

    if re.search(
        r"\bno[\s-]+examples?\b",
        normalized
    ):
        return "0-shot"

    return ""


def _extract_metric_for_dedup(
    claim
):
    """
    Extract an explicitly stated metric for structural deduplication.

    The metric is intentionally conservative. When it cannot be established,
    an empty string is used instead of guessing.
    """

    if not isinstance(
        claim,
        dict
    ):
        return ""

    combined_text = " ".join(
        [
            str(
                claim.get(
                    "claim",
                    ""
                ) or ""
            ),
            str(
                claim.get(
                    "source_sentence",
                    ""
                ) or ""
            ),
        ]
    )

    normalized = re.sub(
        r"\s+",
        " ",
        combined_text
    ).strip().lower()

    metric_patterns = (
        (
            "exact_match",
            r"\bexact[\s-]+match\b|\bem\b",
        ),
        (
            "accuracy",
            r"\baccuracy\b|\baccurate\b",
        ),
        (
            "f1",
            r"\bf1(?:[\s-]+score)?\b",
        ),
        (
            "precision",
            r"\bprecision\b",
        ),
        (
            "recall",
            r"\brecall\b",
        ),
        (
            "bleu",
            r"\bbleu\b",
        ),
        (
            "rouge",
            r"\brouge(?:-[a-z0-9]+)?\b",
        ),
        (
            "perplexity",
            r"\bperplexity\b",
        ),
        (
            "map",
            r"\bmap\b|\bmean average precision\b",
        ),
    )

    for metric_name, pattern in metric_patterns:
        if re.search(
            pattern,
            normalized
        ):
            return metric_name

    return ""


def _normalized_dedup_value(
    claim
):
    """
    Normalize the numeric measurement for structural deduplication only.

    Absolute accuracy may be represented as either:
        0.845
        84.5

    so both are canonicalized to 84.5 for duplicate detection.

    The stored claim value is NEVER modified by this helper.
    """

    if not isinstance(
        claim,
        dict
    ):
        return None

    value = claim.get(
        "reported_value"
    )

    try:
        numeric = float(
            value
        )
    except (
        TypeError,
        ValueError
    ):
        return None

    if not math.isfinite(
        numeric
    ):
        return None

    if (
        claim.get(
            "value_type"
        ) == "absolute_accuracy"
        and 0 < abs(numeric) <= 1
    ):
        numeric *= 100.0

    return round(
        numeric,
        8
    )


def _claim_measurement_identity(
    claim
):
    """
    Return the setting-independent identity of a quantitative measurement.

    This is deliberately narrower than wording-based deduplication. It uses:
        model + benchmark + value_type + normalized value + metric

    The evaluation setting is handled separately because one extraction may
    establish it (for example, 0-shot from a PDF table header) while another
    overlapping extraction may omit it. In that situation, the two records
    can still represent the same physical table cell and should be merged.
    """

    if not isinstance(claim, dict):
        return None

    benchmark = _canonical_benchmark(
        claim.get("benchmark_name")
    )

    value_type = str(
        claim.get("value_type", "") or ""
    ).strip().lower()

    model_key = _extract_model_for_dedup(
        claim
    )

    metric = _extract_metric_for_dedup(
        claim
    )

    if not metric and value_type == "absolute_accuracy":
        metric = "accuracy"

    normalized_value = _normalized_dedup_value(
        claim
    )

    if not model_key or not benchmark or normalized_value is None:
        return None

    return (
        model_key,
        str(benchmark).strip().lower(),
        value_type,
        normalized_value,
        metric,
    )


def _claim_settings_are_compatible(
    claim_a,
    claim_b
):
    """
    Check evaluation-setting compatibility for duplicate merging.

    Equal settings are compatible. An unknown setting is compatible with a
    known setting because overlapping PDF/Gemini contexts can omit the table
    header from one extraction while another extraction recovers it. Two
    different explicit settings are NEVER merged.
    """

    setting_a = _extract_setting_for_dedup(claim_a)
    setting_b = _extract_setting_for_dedup(claim_b)

    if setting_a and setting_b:
        return setting_a == setting_b

    return True


def _is_structured_table_evidence(
    claim
):
    source_text = str(
        claim.get("source_sentence", "") or ""
    ).strip() if isinstance(claim, dict) else ""

    return bool(
        re.search(r"(?im)^\s*Header:\s*$", source_text)
        and re.search(r"(?im)^\s*Row:\s*$", source_text)
    )


def _merge_equivalent_claims(
    existing,
    incoming
):
    """
    Merge two records known to represent the same measurement.

    Canonical evidence policy:
      1. Prefer a normalized Header:/Row: evidence record whenever one exists.
      2. Otherwise retain the richer source evidence.
      3. Preserve an explicitly established evaluation setting.
      4. Preserve the earliest chunk position for traceability.

    No numeric value is calculated or changed.
    """

    existing_structured = _is_structured_table_evidence(existing)
    incoming_structured = _is_structured_table_evidence(incoming)

    # Normalize both candidates before choosing the canonical evidence.
    _normalize_malformed_whitespace_table_evidence(existing)
    _normalize_malformed_whitespace_table_evidence(incoming)

    existing_structured = _is_structured_table_evidence(existing)
    incoming_structured = _is_structured_table_evidence(incoming)

    if incoming_structured and not existing_structured:
        canonical = incoming
        secondary = existing
    elif existing_structured and not incoming_structured:
        canonical = existing
        secondary = incoming
    else:
        if _claim_richness_score(incoming) > _claim_richness_score(existing):
            canonical = incoming
            secondary = existing
        else:
            canonical = existing
            secondary = incoming

    # Prefer the known evaluation setting when one record has it.
    canonical_setting = _extract_setting_for_dedup(canonical)
    secondary_setting = _extract_setting_for_dedup(secondary)

    # Persist the setting explicitly on the surviving claim. This is important
    # because downstream agents read claim.metadata, not only the evidence text.
    canonical["evaluation_setting"] = (
        canonical_setting
        or secondary_setting
        or ""
    )

    # Preserve normalized metric metadata if present on the other record.
    if not canonical.get("metric") and secondary.get("metric"):
        canonical["metric"] = secondary.get("metric")

    # Keep earliest extraction position for traceability.
    for key in ("chunk_index", "context_end_index"):
        values = [
            value
            for value in (
                canonical.get(key),
                secondary.get(key),
            )
            if isinstance(value, (int, float))
        ]
        if values:
            canonical[key] = min(values)

    return canonical


def _claim_dedup_key(
    claim
):
    """
    Build a structural deduplication key.

    IMPORTANT CHANGE FROM V5:
    The primary key no longer hard-partitions by evaluation setting. This is
    necessary for overlapping PDF contexts where one Gemini extraction sees
    only the table row while another sees the same row plus the 0-shot header.

    The setting is checked separately by _claim_settings_are_compatible():
      - same explicit setting -> merge
      - one setting unknown, one known -> merge
      - two different explicit settings -> do not merge

    This lets the following two Falcon records collapse into ONE canonical
    claim without ever merging a 0-shot and 5-shot record when both settings
    are explicitly known.
    """

    identity = _claim_measurement_identity(claim)

    if identity is not None:
        return (
            "structural_measurement",
            *identity,
        )

    # Generic subjects such as "the model" cannot safely be identified.
    # Fall back to normalized wording so unrelated measurements do not collapse.
    benchmark = str(
        claim.get("benchmark_name", "") or ""
    ).strip().lower()

    value_type = str(
        claim.get("value_type", "") or ""
    ).strip().lower()

    return (
        "textual_fallback",
        benchmark,
        value_type,
        _normalized_dedup_value(claim),
        _normalize_for_dedup(
            claim.get("claim", "")
        ),
    )


def _claim_richness_score(
    claim
):
    """
    Score a candidate duplicate for which version to retain.

    Higher score prefers:
      - explicit model identity
      - explicit evaluation setting
      - explicit metric
      - table evidence
      - longer source evidence

    This affects only which duplicate representation survives; it does not
    alter the measurement itself.
    """

    if not isinstance(
        claim,
        dict
    ):
        return 0

    score = 0

    if _extract_model_for_dedup(
        claim
    ):
        score += 4

    if _extract_setting_for_dedup(
        claim
    ):
        score += 2

    if _extract_metric_for_dedup(
        claim
    ):
        score += 1

    source_text = str(
        claim.get(
            "source_sentence",
            ""
        ) or ""
    )

    if re.search(
        r"\btable\b",
        source_text,
        flags=re.IGNORECASE
    ):
        score += 3

    score += min(
        len(source_text) // 250,
        4
    )

    return score


# ============================================================
# DEDUPLICATE CLAIMS
# ============================================================

def _dedupe_claims(
    claims
):
    """
    Deduplicate measurements within one paper while merging complementary
    evidence records into one canonical claim.

    The grouping strategy is intentionally setting-aware:
      - same model/benchmark/value/value_type/metric is the base measurement
        identity;
      - if both records explicitly state a setting, the settings must match;
      - if one record lacks a setting, it may merge with a record that explicitly
        establishes that setting;
      - different explicit settings remain separate measurements.

    For equivalent records, a normalized Header:/Row: evidence representation
    is always preferred as the single surviving source_sentence.
    """

    measurement_groups = {}
    textual_groups = {}
    duplicate_count = 0

    for claim in claims:
        identity = _claim_measurement_identity(claim)

        if identity is None:
            key = _claim_dedup_key(claim)
            existing = textual_groups.get(key)

            if existing is None:
                _normalize_malformed_whitespace_table_evidence(claim)
                textual_groups[key] = claim
            else:
                duplicate_count += 1
                textual_groups[key] = _merge_equivalent_claims(
                    existing,
                    claim,
                )
            continue

        group = measurement_groups.setdefault(identity, [])

        # Find an existing record with a compatible setting. This avoids the
        # earlier dictionary-key problem where an unknown setting and a known
        # setting became different buckets and could not be merged.
        compatible_index = None

        for index, existing in enumerate(group):
            if _claim_settings_are_compatible(existing, claim):
                compatible_index = index
                break

        if compatible_index is None:
            _normalize_malformed_whitespace_table_evidence(claim)
            group.append(claim)
            continue

        duplicate_count += 1
        group[compatible_index] = _merge_equivalent_claims(
            group[compatible_index],
            claim,
        )

    deduped = []

    for group in measurement_groups.values():
        deduped.extend(group)

    deduped.extend(textual_groups.values())

    deduped.sort(
        key=lambda claim: (
            claim.get("chunk_index", float("inf")),
            claim.get("context_end_index", float("inf")),
        )
    )

    if duplicate_count:
        print(
            f"[dedupe] merged "
            f"{duplicate_count} duplicate/complementary measurement(s) "
            f"using structural measurement identity and canonical evidence"
        )

    return deduped


# ============================================================
# CLEAN GEMINI JSON RESPONSE
# ============================================================

def _clean_json_response(
    response_text
):
    """
    Remove markdown fences and isolate a JSON array.
    """

    if not response_text:

        return ""


    cleaned = str(
        response_text
    ).strip()


    # --------------------------------------------------------
    # Remove markdown
    # --------------------------------------------------------

    cleaned = cleaned.replace(
        "```json",
        ""
    )


    cleaned = cleaned.replace(
        "```JSON",
        ""
    )


    cleaned = cleaned.replace(
        "```",
        ""
    )


    cleaned = cleaned.strip()


    # --------------------------------------------------------
    # Locate JSON array
    # --------------------------------------------------------

    first_bracket = cleaned.find(
        "["
    )


    last_bracket = cleaned.rfind(
        "]"
    )


    if (
        first_bracket != -1
        and last_bracket != -1
        and last_bracket > first_bracket
    ):

        cleaned = cleaned[
            first_bracket:
            last_bracket + 1
        ]


    return cleaned.strip()


# ============================================================
# REAL GEMINI CLAIM EXTRACTION
# ============================================================

def extract_claims_from_text(
    paper_id: str,
    text: str,
    client=None
) -> list:
    """
    Extract quantitative claims from ONE paper using Gemini.

    Paper identity is always supplied by the pipeline.

    Gemini never controls paper_id.
    """

    # --------------------------------------------------------
    # Validate text
    # --------------------------------------------------------

    if (
        not text
        or not str(text).strip()
    ):

        print(
            f"[extract] paper {paper_id}: "
            "no usable text"
        )

        return []


    # --------------------------------------------------------
    # Gemini client
    # --------------------------------------------------------

    gemini_client = get_gemini_client(
        client
    )


    # --------------------------------------------------------
    # Chunk full paper
    # --------------------------------------------------------

    chunks = chunk_text(
        text,
        max_chars=6000
    )


    print(
        f"[extract] paper {paper_id}: "
        f"text length = {len(text)}"
    )


    print(
        f"[extract] paper {paper_id}: "
        f"total chunks = {len(chunks)}"
    )


    if not chunks:

        print(
            f"[extract] paper {paper_id}: "
            "no chunks created"
        )

        return []


    # ========================================================
    # BENCHMARK ANCHORS
    # ========================================================

    relevant_indices = (
        _find_relevant_chunk_indices(
            chunks
        )
    )


    print(
        f"[extract] paper {paper_id}: "
        f"benchmark-relevant chunks = "
        f"{len(relevant_indices)}"
    )


    if not relevant_indices:

        print(
            f"[extract] paper {paper_id}: "
            "no validated benchmark anchors found; "
            "Gemini call skipped"
        )


        print(
            f"[extract] paper {paper_id}: "
            "FINAL VALID CLAIMS = 0"
        )


        return []


    # ========================================================
    # BOUNDED CONTEXTS
    # ========================================================

    context_groups = _build_context_chunks(
        chunks,
        relevant_indices,
        neighbor_radius=ANCHOR_NEIGHBOR_RADIUS
    )


    print(
        f"[extract] paper {paper_id}: "
        f"Gemini context groups = "
        f"{len(context_groups)}"
    )


    all_claims = []


    # ========================================================
    # PROCESS EACH CONTEXT
    # ========================================================

    for group_index, group in enumerate(
        context_groups,
        start=1
    ):

        context_text = group[
            "text"
        ]


        start_index = group[
            "start_index"
        ]


        end_index = group[
            "end_index"
        ]


        print(
            f"[extract] paper {paper_id}: "
            f"Gemini context "
            f"{group_index}/{len(context_groups)} "
            f"(chunks "
            f"{start_index + 1}-"
            f"{end_index + 1})"
        )


        parsed = None


        # ====================================================
        # GEMINI RETRIES
        # ====================================================

        for attempt in range(
            MAX_RETRIES
        ):

            try:

                response = call_with_retry(
                    gemini_client,
                    MODEL_NAME,
                    EXTRACTION_PROMPT.format(
                        benchmarks=", ".join(
                            VALIDATED_BENCHMARKS
                        ),
                        chunk=context_text
                    ),
                    {
                        "max_output_tokens":
                            MAX_OUTPUT_TOKENS_EXTRACTION
                    },
                )


                raw_response = (
                    _clean_json_response(
                        response.text
                    )
                )


                # ------------------------------------------------
                # Debug output
                # ------------------------------------------------

                print()

                print(
                    "=" * 70
                )

                print(
                    f"[DEBUG] RAW GEMINI RESPONSE "
                    f"FOR PAPER {paper_id}"
                )

                print(
                    "=" * 70
                )

                print(
                    raw_response
                )

                print(
                    "=" * 70
                )


                print(
                    f"[extract] paper {paper_id}: "
                    f"Gemini response length = "
                    f"{len(raw_response)}"
                )


                # ------------------------------------------------
                # Parse JSON
                # ------------------------------------------------

                parsed = json.loads(
                    raw_response
                )


                break


            except json.JSONDecodeError as error:

                print(
                    f"[extract] paper {paper_id}: "
                    f"invalid JSON on attempt "
                    f"{attempt + 1}/{MAX_RETRIES}: "
                    f"{error}"
                )


                if attempt < (
                    MAX_RETRIES - 1
                ):

                    time.sleep(
                        2
                    )


            except Exception as error:

                print(
                    f"[extract] paper {paper_id}: "
                    f"Gemini error on attempt "
                    f"{attempt + 1}/{MAX_RETRIES}: "
                    f"{error}"
                )


                if attempt < (
                    MAX_RETRIES - 1
                ):

                    time.sleep(
                        2
                    )


        # ====================================================
        # FAILED CONTEXT
        # ====================================================

        if parsed is None:

            print(
                f"[extract] paper {paper_id}: "
                f"context {group_index} skipped"
            )

            continue


        # ====================================================
        # FOCUSED RECOVERY FOR EMPTY GEMINI RESPONSES
        # ====================================================

        if (
            parsed == []
            and _context_has_quantitative_benchmark_signal(
                context_text
            )
        ):

            print(
                f"[extract] paper {paper_id}: "
                f"empty Gemini response in context {group_index}; "
                "running focused benchmark-recovery request"
            )

            for recovery_attempt in range(
                MAX_RECOVERY_ATTEMPTS
            ):

                try:

                    recovery_response = call_with_retry(
                        gemini_client,
                        MODEL_NAME,
                        RECOVERY_PROMPT.format(
                            benchmarks=", ".join(
                                VALIDATED_BENCHMARKS
                            ),
                            chunk=context_text,
                        ),
                        {
                            "max_output_tokens":
                                MAX_OUTPUT_TOKENS_EXTRACTION
                        },
                    )

                    recovery_raw = _clean_json_response(
                        recovery_response.text
                    )

                    print()
                    print(
                        "=" * 70
                    )
                    print(
                        f"[DEBUG] RECOVERY GEMINI RESPONSE "
                        f"FOR PAPER {paper_id}"
                    )
                    print(
                        "=" * 70
                    )
                    print(
                        recovery_raw
                    )
                    print(
                        "=" * 70
                    )

                    recovered = json.loads(
                        recovery_raw
                    )

                    if isinstance(
                        recovered,
                        list
                    ):
                        parsed = recovered

                    break

                except json.JSONDecodeError as error:

                    print(
                        f"[extract] paper {paper_id}: "
                        f"invalid recovery JSON on attempt "
                        f"{recovery_attempt + 1}/"
                        f"{MAX_RECOVERY_ATTEMPTS}: "
                        f"{error}"
                    )

                except Exception as error:

                    print(
                        f"[extract] paper {paper_id}: "
                        f"recovery error on attempt "
                        f"{recovery_attempt + 1}/"
                        f"{MAX_RECOVERY_ATTEMPTS}: "
                        f"{error}"
                    )

        # ====================================================
        # REQUIRE JSON ARRAY
        # ====================================================

        if not isinstance(
            parsed,
            list
        ):

            print(
                f"[extract] paper {paper_id}: "
                "Gemini did not return a JSON array"
            )

            continue


        # ====================================================
        # VALIDATE ALL CLAIMS
        #
        # We validate FIRST and apply the 8-claim limit AFTER
        # validation so invalid claims don't consume the quota.
        # ====================================================

        valid_claims = []

        invalid_count = 0


        for raw_claim in parsed:

            raw_claim = _normalize_gemini_claim_schema(
                raw_claim
            )

            if isinstance(raw_claim, dict):
                raw_claim[
                    "_validation_context"
                ] = context_text

                # Recovery responses can describe a valid result but attach
                # a source sentence that omits the benchmark/model context.
                # Before strict validation, replace that generated evidence
                # only when the ORIGINAL PDF context contains an explicit
                # model + benchmark + value relationship.
                _reconstruct_recovery_evidence(
                    raw_claim,
                    context_text,
                    full_text=text,
                )

                # Normalize malformed PDF whitespace-table evidence into the
                # same explicit Header:/Row: representation before strict
                # validation. This preserves the exact model/value mapping
                # while making downstream verification consistent.
                _normalize_malformed_whitespace_table_evidence(
                    raw_claim
                )

            # ----------------------------------------------------
            # Gemini should already return one benchmark per claim.
            # When it violates that rule for a table, recover only
            # from explicit Header/Row column mappings.
            # ----------------------------------------------------

            claim_candidates = [
                raw_claim
            ]

            if not _claim_has_single_benchmark(
                raw_claim
            ):

                split_claims = _split_compound_table_claim(
                    raw_claim
                )

                if split_claims:

                    claim_candidates = split_claims

                    print(
                        f"[extract] paper {paper_id}: "
                        "split compound table claim into "
                        f"{len(split_claims)} single-benchmark claim(s)"
                    )


            for claim in claim_candidates:

                # Re-run the canonicalizer after any benchmark-column splitting
                # so every surviving candidate has the same evidence contract.
                _normalize_malformed_whitespace_table_evidence(
                    claim
                )

                if not _validate_claim(
                    claim
                ):

                    invalid_count += 1

                    model_name = _extract_model_name_for_validation(
                        claim
                    )

                    if model_name and _is_ambiguous_model_identity(
                        model_name
                    ):
                        print(
                            f"[extract] paper {paper_id}: "
                            f"dropped ambiguous model identity "
                            f"'{model_name}'"
                        )

                    continue


                claim.pop(
                    "_validation_context",
                    None
                )

                valid_claims.append(
                    claim
                )


        # ----------------------------------------------------
        # Enforce maximum VALID claims
        # ----------------------------------------------------

        if len(
            valid_claims
        ) > MAX_CLAIMS_PER_RESPONSE:

            print(
                f"[extract] paper {paper_id}: "
                f"Gemini produced "
                f"{len(valid_claims)} valid claims; "
                f"keeping first "
                f"{MAX_CLAIMS_PER_RESPONSE}"
            )


            valid_claims = valid_claims[
                :MAX_CLAIMS_PER_RESPONSE
            ]


        # ====================================================
        # ATTACH PIPELINE METADATA
        # ====================================================

        for claim in valid_claims:

            # ------------------------------------------------
            # IMPORTANT:
            # The pipeline owns paper identity.
            # ------------------------------------------------

            claim[
                "paper_id"
            ] = paper_id


            # ------------------------------------------------
            # Traceability
            # ------------------------------------------------

            claim[
                "chunk_index"
            ] = start_index


            claim[
                "context_end_index"
            ] = end_index


        # ----------------------------------------------------
        # Diagnostics
        # ----------------------------------------------------

        if invalid_count:

            print(
                f"[extract] paper {paper_id}: "
                f"dropped {invalid_count} invalid claim(s)"
            )


        if valid_claims:

            print(
                f"[extract] paper {paper_id}: "
                f"accepted {len(valid_claims)} claim(s) "
                f"from context group "
                f"{group_index}"
            )

        else:

            print(
                f"[extract] paper {paper_id}: "
                f"no valid claims from context group "
                f"{group_index}"
            )


        all_claims.extend(
            valid_claims
        )


        # ----------------------------------------------------
        # Rate-limit delay
        # ----------------------------------------------------

        if (
            SECONDS_BETWEEN_CALLS
            > 0
        ):

            time.sleep(
                SECONDS_BETWEEN_CALLS
            )


    # ========================================================
    # DEDUPLICATE
    # ========================================================

    before = len(
        all_claims
    )


    all_claims = _dedupe_claims(
        all_claims
    )


    after = len(
        all_claims
    )


    if before != after:

        print(
            f"[extract] paper {paper_id}: "
            f"deduped {before} -> {after}"
        )


    # ========================================================
    # FINAL RESULT
    # ========================================================

    print(
        f"[extract] paper {paper_id}: "
        f"FINAL VALID CLAIMS = "
        f"{len(all_claims)}"
    )


    return all_claims