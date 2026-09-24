"""
test_pipeline.py

WHAT:
Runs the complete ResearchClaimAI agent pipeline end-to-end.

Pipeline

Retrieval
    ↓
Claim Extraction
    ↓
Evidence Strength Scoring
    ↓
Evidence Verification
    ↓
Skeptic Review
    ↓
Store Results
    ↓
Contradiction Detection
    ↓
Confidence Aggregation
    ↓
Print Final Analysis

This file is currently used as the backend integration test runner.
After this pipeline works correctly, the same orchestration will be exposed
through FastAPI and then consumed by the React frontend.
"""

import os
import sys

# ============================================================
# ENSURE THIS SCRIPT USES THE CURRENT BACKEND PROJECT
# ============================================================
# test_pipeline.py is inside backend/retrievers/. When executed
# directly as a script, Python may put backend/retrievers/ first
# on sys.path and can resolve project packages from another copy
# of the project. Force this file's own backend directory to the
# front of sys.path before importing any project modules.
BACKEND_DIR = os.path.dirname(
    os.path.dirname(
        os.path.abspath(__file__)
    )
)

if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)
else:
    sys.path.remove(BACKEND_DIR)
    sys.path.insert(0, BACKEND_DIR)

from dotenv import load_dotenv

load_dotenv()

from config import MOCK_MODE

# ============================================================
# GEMINI CLIENT
# ============================================================

api_key = os.environ.get("GEMINI_API_KEY")
client = None

if MOCK_MODE:
    print(
        "[info] MOCK_MODE is ON - deterministic responses will be used."
    )
else:
    if not api_key:
        raise ValueError(
            "GEMINI_API_KEY not found - check your .env file."
        )

    from google import genai
    from google.genai import types

    client = genai.Client(
        api_key=api_key,
        http_options=types.HttpOptions(
            client_args={
                "verify": False
            }
        )
    )


# ============================================================
# DATABASE
# ============================================================

from db_schema import (
    get_session,
    upsert_paper,
    insert_claim_with_evidence,
    update_claim_score,
    Evidence,
)

# ============================================================
# EXISTING AGENTS
# ============================================================

from claim_extraction_agent import extract_claims_from_text
from evidence_strength_agent import score_claim

# ============================================================
# NEW AGENTS
# ============================================================

from agents.evidence_verification.agent import (
    EvidenceVerificationAgent,
)

from agents.skeptic.agent import (
    SkepticAgent,
)

# ============================================================
# CONTRADICTION AGENT
# ============================================================

from contradiction_agent import (
    detect_all_contradictions,
    store_contradictions,
)

# ============================================================
# CONFIDENCE AGGREGATION
# ============================================================

from confidence_scoring import calculate_confidence


# ============================================================
# INITIALIZE NEW AGENTS
# ============================================================

evidence_verification_agent = EvidenceVerificationAgent()
skeptic_agent = SkepticAgent()

# Import-resolution diagnostic. This confirms the regression test and
# live pipeline are using the same evidence-verification module.
try:
    import inspect

    _evidence_agent_source = inspect.getfile(
        EvidenceVerificationAgent
    )

    print(
        "[info] EvidenceVerificationAgent loaded from: "
        f"{_evidence_agent_source}"
    )

except (OSError, TypeError):
    pass


# ============================================================
# RETRIEVAL
# ============================================================

def get_papers_from_retrieval(
    query: str,
    max_results: int = 10
):
    """
    Uses the existing retrieval adapter.

    The adapter normalizes papers into the structure required by
    the downstream pipeline.
    """

    from retrieval_adapter import (
        get_pipeline_ready_papers
    )

    return get_pipeline_ready_papers(
        query,
        max_results=max_results
    )


# ============================================================
# OPTIONAL LOCAL TEST PAPERS
# ============================================================

def get_test_papers_stub():
    """
    Deterministic local papers for offline testing.
    """

    return [

        {
            "id": "2401.00001",

            "title":
                "Scaling Instruction Tuning for Reasoning Benchmarks",

            "authors":
                "A. Author, B. Coauthor",

            "year":
                2024,

            "source":
                "arXiv",

            "abstract":
                (
                    "We evaluate our new instruction-tuned model "
                    "across standard benchmarks. "
                    "Our model achieves 86.4% on MMLU, "
                    "substantially outperforming prior open-weight "
                    "baselines. "
                    "On GSM8K, the model solves 91.2% of problems "
                    "correctly. "
                    "We release our code and evaluation scripts "
                    "publicly."
                ),

            "full_text":
                (
                    "Abstract: We evaluate our new instruction-tuned "
                    "model across standard benchmarks. "
                    "Our model achieves 86.4% on MMLU, "
                    "substantially outperforming prior open-weight "
                    "baselines. "
                    "On GSM8K, the model solves 91.2% of problems "
                    "correctly. "
                    "We release our code and evaluation scripts "
                    "publicly."
                ),
        },

        {
            "id":
                "2402.00002",

            "title":
                "A Contrasting Evaluation of Instruction-Tuned Models",

            "authors":
                "C. Researcher",

            "year":
                2024,

            "source":
                "arXiv",

            "abstract":
                (
                    "We independently re-evaluate several public "
                    "models. "
                    "We find the model from prior work achieves only "
                    "79.5% on MMLU under our stricter evaluation "
                    "protocol, notably lower than originally reported. "
                    "On GSM8K we measure 91.0% accuracy, consistent "
                    "with prior claims."
                ),

            "full_text":
                (
                    "Abstract: We independently re-evaluate several "
                    "public models. "
                    "We find the model from prior work achieves only "
                    "79.5% on MMLU under our stricter evaluation "
                    "protocol, notably lower than originally reported. "
                    "On GSM8K we measure 91.0% accuracy, consistent "
                    "with prior claims."
                ),
        },
    ]


# ============================================================
# TEST CONFIGURATION
# ============================================================

USE_LIVE_RETRIEVAL = True

LIVE_QUERY = (
    "MMLU large language model benchmark evaluation results"
)

# ============================================================
# DEVELOPMENT DATABASE RESET
# ============================================================
# The contradiction detector reads claims stored in SQLite.
# For reproducible testing, this file uses an explicit database path
# next to test_pipeline.py instead of relying on the current working
# directory. This prevents stale claims from another folder/run from
# contaminating the contradiction test.

RESET_DATABASE_ON_RUN = os.getenv(
    "RESET_DATABASE_ON_RUN",
    "true"
).lower() in {"1", "true", "yes"}

BASE_DIR = os.path.dirname(
    os.path.abspath(__file__)
)

PIPELINE_DB_PATH = os.path.join(
    BASE_DIR,
    "claims_audit.db"
)

REGRESSION_DB_PATH = os.path.join(
    BASE_DIR,
    "claims_audit_regression.db"
)


def _sqlite_url(db_path: str) -> str:
    """Build a portable absolute SQLite URL for Windows/Linux/macOS."""
    absolute_path = os.path.abspath(db_path)
    return "sqlite:///" + absolute_path.replace("\\", "/")


def _remove_sqlite_database(db_path: str, label: str = "database") -> None:
    """Remove an SQLite DB and its WAL/SHM sidecar files if present."""
    for path in (
        db_path,
        f"{db_path}-wal",
        f"{db_path}-shm",
    ):
        if os.path.exists(path):
            try:
                os.remove(path)
                print(
                    f"[info] Removed previous {label} file: {path}"
                )
            except PermissionError:
                print(
                    f"[warning] Could not remove {label} file because it is in use: {path}"
                )


def reset_test_database():
    """Remove the main pipeline SQLite database before a development run."""
    if RESET_DATABASE_ON_RUN:
        _remove_sqlite_database(
            PIPELINE_DB_PATH,
            label="pipeline database"
        )


def get_pipeline_session():
    """Open the pipeline DB at the same absolute path used by reset_test_database()."""
    return get_session(
        db_url=_sqlite_url(PIPELINE_DB_PATH)
    )


def get_regression_session():
    """Open the isolated DB used only by the contradiction regression test."""
    return get_session(
        db_url=_sqlite_url(REGRESSION_DB_PATH)
    )


# ============================================================
# SCORE HELPERS
# ============================================================

def calculate_verification_score(
    verification_result: dict
) -> float:
    """
    Converts per-evidence verification scores into the pipeline's
    0 - 10 verification score.

    EvidenceVerificationAgent now returns a structured
    `verification_score` for each evidence item.  The older
    `similarity_score` field is retained only as a lexical/diagnostic
    signal and is used as a fallback for backwards compatibility.
    """

    all_results = (
        verification_result.get(
            "supporting_evidence", []
        )
        + verification_result.get(
            "weak_evidence", []
        )
        + verification_result.get(
            "unrelated_evidence", []
        )
    )

    if not all_results:
        return 0.0

    scores = []

    for item in all_results:
        if "verification_score" in item:
            try:
                scores.append(
                    float(item["verification_score"])
                )
                continue
            except (TypeError, ValueError):
                pass

        # Backwards-compatible fallback for results produced by the
        # previous TF-IDF-only verifier.
        try:
            scores.append(
                float(item.get("similarity_score", 0)) * 10
            )
        except (TypeError, ValueError):
            scores.append(0.0)

    average_verification_score = (
        sum(scores) / len(scores)
    )

    return round(
        min(max(average_verification_score, 0), 10),
        2
    )


def calculate_skeptic_score(
    skeptic_result: dict
) -> float:
    """
    Converts the Skeptic Agent's contradiction score into a
    confidence-oriented 0 - 10 score.

    A higher contradiction score means stronger skeptical/
    contradictory signals, so it is inverted here.
    """

    all_results = (
        skeptic_result.get(
            "contradicting_evidence", []
        )
        + skeptic_result.get(
            "uncertain_evidence", []
        )
        + skeptic_result.get(
            "neutral_evidence", []
        )
    )

    if not all_results:
        return 0.0

    average_contradiction = sum(
        float(item.get("contradiction_score", 0))
        for item in all_results
    ) / len(all_results)

    skeptic_score = (
        1.0 - min(
            max(average_contradiction, 0),
            1
        )
    ) * 10

    return round(
        min(max(skeptic_score, 0), 10),
        2
    )


def calculate_contradiction_confidence(
    contradiction_results: list
) -> float:
    """
    Converts contradiction relationships into a 0 - 10
    confidence-oriented score.

    Higher score = fewer contradictions.

    When comparable claim pairs exist:
        Agrees       -> positive
        Contradicts  -> negative

    When no comparable pairs exist, the score is 5.0 because
    there is insufficient cross-paper comparison evidence to
    justify either a high or low contradiction-confidence score.
    """

    if not contradiction_results:
        return 5.0

    agrees = sum(
        1
        for item in contradiction_results
        if item.get("relation_type") == "Agrees"
    )

    total = len(contradiction_results)

    return round(
        (agrees / total) * 10,
        2
    )


# ============================================================
# EVIDENCE VERIFICATION REGRESSION TEST
# ============================================================

def run_evidence_verification_regression_test() -> dict:
    """
    Regression tests for structured evidence verification.

    The exact table evidence must score highly even when raw TF-IDF
    similarity is only moderate.  Mismatched and unrelated evidence
    must not be classified as supporting.
    """

    print()
    print("=" * 70)
    print("EVIDENCE VERIFICATION REGRESSION TEST")
    print("=" * 70)

    agent = EvidenceVerificationAgent()

    exact_table_claim = (
        "Nemotron-Mini-4B-Instruct achieves 56.8 on MMLU "
        "in the 0-shot setting."
    )

    exact_table_evidence = (
        "Header:\n"
        "Model | MMLU (0-shot) | MMLU-Pro (0-shot) | "
        "Mobile-MMLU (0-shot) | Mobile-MMLU-Pro (0-shot)\n\n"
        "Row:\n"
        "Nemotron-Mini-4B-Instruct | 56.8 | 18.1 | 35.1 | 30.8"
    )

    unrelated_evidence = (
        "The paper discusses image classification training costs "
        "and dataset construction."
    )

    wrong_model_evidence = (
        "Header:\n"
        "Model | MMLU (0-shot)\n\n"
        "Row:\n"
        "DifferentModel | 56.8"
    )

    exact_result = agent.verify_evidence(
        claim=exact_table_claim,
        evidence_list=[
            {
                "paper_id": "REGRESSION-EVIDENCE-EXACT",
                "text": exact_table_evidence,
            }
        ],
    )

    unrelated_result = agent.verify_evidence(
        claim=exact_table_claim,
        evidence_list=[
            {
                "paper_id": "REGRESSION-EVIDENCE-UNRELATED",
                "text": unrelated_evidence,
            }
        ],
    )

    wrong_model_result = agent.verify_evidence(
        claim=exact_table_claim,
        evidence_list=[
            {
                "paper_id": "REGRESSION-EVIDENCE-WRONG-MODEL",
                "text": wrong_model_evidence,
            }
        ],
    )

    exact_item = exact_result["evidence_results"][0]
    unrelated_item = unrelated_result["evidence_results"][0]
    wrong_model_item = wrong_model_result["evidence_results"][0]

    exact_score = calculate_verification_score(exact_result)
    unrelated_score = calculate_verification_score(unrelated_result)
    wrong_model_score = calculate_verification_score(wrong_model_result)

    if exact_score < 8.5:
        raise AssertionError(
            "Exact structured table evidence should score at least 8.5/10, "
            f"got {exact_score}."
        )

    if exact_item["classification"] != "supporting":
        raise AssertionError(
            "Exact structured table evidence must be classified as supporting, "
            f"got {exact_item['classification']!r}."
        )

    if unrelated_item["classification"] == "supporting":
        raise AssertionError(
            "Unrelated evidence must not be classified as supporting."
        )

    if wrong_model_item["classification"] == "supporting":
        raise AssertionError(
            "Evidence for a different model must not be classified as supporting."
        )

    print()
    print("✅ EVIDENCE VERIFICATION REGRESSION TEST PASSED")
    print()
    print("Exact table evidence:")
    print(f"  TF-IDF similarity : {exact_item['similarity_score']}")
    print(f"  Structured score  : {exact_item['structured_match_score']}")
    print(f"  Verification      : {exact_score}/10")
    print(f"  Classification    : {exact_item['classification']}")

    print()
    print("Wrong-model evidence:")
    print(f"  Verification      : {wrong_model_score}/10")
    print(f"  Classification    : {wrong_model_item['classification']}")

    print()
    print("Unrelated evidence:")
    print(f"  Verification      : {unrelated_score}/10")
    print(f"  Classification    : {unrelated_item['classification']}")
    print("=" * 70)

    return {
        "passed": True,
        "exact_table_score": exact_score,
        "wrong_model_score": wrong_model_score,
        "unrelated_score": unrelated_score,
        "exact_classification": exact_item["classification"],
        "wrong_model_classification": wrong_model_item["classification"],
        "unrelated_classification": unrelated_item["classification"],
    }


# ============================================================
# CONTRADICTION REGRESSION TEST
# ============================================================

def run_contradiction_regression_test() -> dict:
    """
    Self-contained regression test for contradiction detection.

    Two synthetic papers report the SAME:
        - model
        - benchmark
        - value_type
        - metric
        - evaluation setting

    but DIFFERENT values.

    Expected behavior:
        exactly one cross-paper comparison pair
        relation_type = "Contradicts"
        value_diff = 6.9

    The test uses a separate SQLite database so it cannot contaminate
    live pipeline data.
    """

    print()
    print("=" * 70)
    print("CONTRADICTION REGRESSION TEST")
    print("=" * 70)

    _remove_sqlite_database(
        REGRESSION_DB_PATH,
        label="regression database"
    )

    session = get_regression_session()

    try:
        # --------------------------------------------------------
        # Synthetic papers
        # --------------------------------------------------------
        paper_a = {
            "id": "REGRESSION-PAPER-A",
            "title": "Synthetic Baseline Evaluation",
            "authors": "Regression Author A",
            "year": 2026,
            "source": "regression-test",
            "abstract": "Synthetic regression paper A.",
            "source_url": "https://example.invalid/regression-a",
        }

        paper_b = {
            "id": "REGRESSION-PAPER-B",
            "title": "Synthetic Independent Re-evaluation",
            "authors": "Regression Author B",
            "year": 2026,
            "source": "regression-test",
            "abstract": "Synthetic regression paper B.",
            "source_url": "https://example.invalid/regression-b",
        }

        upsert_paper(session, paper_a)
        upsert_paper(session, paper_b)

        # --------------------------------------------------------
        # Same model / benchmark / metric / setting; different values
        # --------------------------------------------------------
        claim_a = {
            "paper_id": paper_a["id"],
            "claim": (
                "TestModel-7B achieves 86.4% accuracy on MMLU "
                "in the 5-shot setting."
            ),
            "section": "Results",
            "claim_type": "performance_claim",
            "source_sentence": (
                "TestModel-7B achieves 86.4% accuracy on MMLU "
                "in the 5-shot setting."
            ),
            "benchmark_name": "MMLU",
            "reported_value": 86.4,
            "value_type": "absolute_accuracy",
        }

        claim_b = {
            "paper_id": paper_b["id"],
            "claim": (
                "TestModel-7B achieves 79.5% accuracy on MMLU "
                "in the 5-shot setting."
            ),
            "section": "Results",
            "claim_type": "performance_claim",
            "source_sentence": (
                "TestModel-7B achieves 79.5% accuracy on MMLU "
                "in the 5-shot setting."
            ),
            "benchmark_name": "MMLU",
            "reported_value": 79.5,
            "value_type": "absolute_accuracy",
        }

        claim_row_a = insert_claim_with_evidence(
            session,
            claim_a
        )

        claim_row_b = insert_claim_with_evidence(
            session,
            claim_b
        )

        session.commit()

        # --------------------------------------------------------
        # Run the actual contradiction agent
        # --------------------------------------------------------
        contradiction_results = detect_all_contradictions(
            session
        )

        # --------------------------------------------------------
        # Assertions
        # --------------------------------------------------------
        if len(contradiction_results) != 1:
            raise AssertionError(
                "Expected exactly 1 comparable cross-paper pair, "
                f"but found {len(contradiction_results)}."
            )

        result = contradiction_results[0]

        if result["claim_a_id"] not in {
            claim_row_a.id,
            claim_row_b.id,
        } or result["claim_b_id"] not in {
            claim_row_a.id,
            claim_row_b.id,
        }:
            raise AssertionError(
                "The detected pair does not contain the two synthetic claims."
            )

        if result["relation_type"] != "Contradicts":
            raise AssertionError(
                "Expected relation_type='Contradicts', "
                f"got {result['relation_type']!r}."
            )

        if result["value_diff"] != 6.9:
            raise AssertionError(
                "Expected value_diff=6.9, "
                f"got {result['value_diff']!r}."
            )

        if result["benchmark_name"].lower() != "mmlu":
            raise AssertionError(
                "Unexpected benchmark in regression result: "
                f"{result['benchmark_name']!r}."
            )

        if result["value_type"] != "absolute_accuracy":
            raise AssertionError(
                "Unexpected value_type in regression result: "
                f"{result['value_type']!r}."
            )

        if result["evaluation_setting"] != "5-shot":
            raise AssertionError(
                "Expected evaluation_setting='5-shot', "
                f"got {result['evaluation_setting']!r}."
            )

        if result["metric"] != "accuracy":
            raise AssertionError(
                "Expected metric='accuracy', "
                f"got {result['metric']!r}."
            )

        stored_rows = store_contradictions(
            session,
            contradiction_results
        )

        if len(stored_rows) != 1:
            raise AssertionError(
                "Expected exactly 1 contradiction row to be stored, "
                f"got {len(stored_rows)}."
            )

        # --------------------------------------------------------
        # Print the result in a dashboard-friendly format
        # --------------------------------------------------------
        print()
        print("✅ CONTRADICTION REGRESSION TEST PASSED")
        print()
        print("Expected / actual comparison:")
        print("  Paper A value       : 86.4")
        print("  Paper B value       : 79.5")
        print("  Benchmark           : MMLU")
        print("  Value type          : absolute_accuracy")
        print("  Evaluation setting  : 5-shot")
        print("  Metric              : accuracy")
        print("  Value difference    : 6.9")
        print(f"  Relation             : {result['relation_type']}")
        print(f"  Severity             : {result['severity']}")
        print(f"  Stored rows          : {len(stored_rows)}")
        print()
        print("Regression result object:")
        print(result)
        print()
        print(
            f"Regression database: {REGRESSION_DB_PATH}"
        )
        print("=" * 70)

        return {
            "passed": True,
            "expected_pairs": 1,
            "actual_pairs": len(contradiction_results),
            "stored_rows": len(stored_rows),
            "result": result,
        }

    finally:
        session.close()


# ============================================================
# MAIN PIPELINE
# ============================================================

def run_pipeline(
    query: str = LIVE_QUERY,
    max_results: int = 8
):

    # Start this development run with a clean database so
    # contradiction detection only sees the current run.
    reset_test_database()

    session = get_pipeline_session()

    all_claim_results = []

    all_verification_scores = []
    all_skeptic_scores = []
    all_evidence_strength_scores = []

    try:

        # ====================================================
        # STEP 1: RETRIEVAL
        # ====================================================

        print()
        print("=" * 70)
        print("STEP 1: RETRIEVING PAPERS")
        print("=" * 70)

        papers = (
            get_papers_from_retrieval(
                query,
                max_results=max_results,
            )
            if USE_LIVE_RETRIEVAL
            else get_test_papers_stub()
        )
        print(
            f"Papers retrieved: {len(papers)}"
        )

        # ====================================================
        # STEP 2: PROCESS EACH PAPER
        # ====================================================

        for paper in papers:

            print()
            print("=" * 70)
            print(
                f"PROCESSING PAPER: {paper['title']}"
            )
            print("=" * 70)

            # ------------------------------------------------
            # Store paper
            # ------------------------------------------------

            upsert_paper(
                session,
                paper
            )

            # ------------------------------------------------
            # Select best available text
            # ------------------------------------------------

            paper_text = (
                paper.get("full_text")
                or paper.get("abstract")
                or ""
            )

            if not paper_text.strip():
                print(
                    "[warning] No usable text found. "
                    "Skipping paper."
                )
                continue

            # =================================================
            # STEP 3: CLAIM EXTRACTION
            # =================================================

            print()
            print(
                "STEP 3: Extracting claims..."
            )

            claims = extract_claims_from_text(
                paper_id=paper["id"],
                text=paper_text,
                client=client
            )

            print(
                f"Claims extracted: {len(claims)}"
            )

            # =================================================
            # PROCESS EACH CLAIM
            # =================================================

            for claim in claims:

                print()
                print("-" * 70)
                print(
                    f"CLAIM: {claim.get('claim')}"
                )
                print("\n" + "=" * 70)
                print("[PIPELINE CLAIM BEFORE DB INSERT]")
                print("Claim ID:", claim.get("claim"))
                print("Benchmark:", claim.get("benchmark_name"))
                print("Reported value:", claim.get("reported_value"))
                print("Evaluation setting:", claim.get("evaluation_setting"))
                print("Source sentence:")
                print(claim.get("source_sentence", "<NO SOURCE SENTENCE>"))
                print("=" * 70)
                # ---------------------------------------------
                # STEP 4: STORE CLAIM + EVIDENCE
                # ---------------------------------------------

                claim_row = insert_claim_with_evidence(
                    session,
                    claim
                )

                # The exact supporting sentence created by
                # the Claim Extraction Agent.
                evidence_text = (
                    claim.get(
                        "source_sentence",
                        ""
                    )
                    or ""
                )

                # =============================================
                # STEP 5: EVIDENCE VERIFICATION
                # =============================================

                evidence_list = [
                    {
                        "paper_id":
                            str(paper["id"]),

                        "text":
                            evidence_text
                    }
                ]

                verification_result = (
                    evidence_verification_agent.verify_evidence(
                        claim=claim["claim"],
                        evidence_list=evidence_list
                    )
                )

                verification_score = (
                    calculate_verification_score(
                        verification_result
                    )
                )

                all_verification_scores.append(
                    verification_score
                )

                print(
                    "Evidence Verification:"
                )

                print(
                    f"  Score: "
                    f"{verification_score}/10"
                )

                print(
                    f"  Supporting: "
                    f"{len(verification_result.get('supporting_evidence', []))}"
                )

                print(
                    f"  Weak: "
                    f"{len(verification_result.get('weak_evidence', []))}"
                )

                print(
                    f"  Unrelated: "
                    f"{len(verification_result.get('unrelated_evidence', []))}"
                )

                # =============================================
                # SAVE VERIFICATION SCORE
                # =============================================

                evidence_row = (
                    session.query(Evidence)
                    .filter(
                        Evidence.claim_id ==
                        claim_row.id
                    )
                    .first()
                )

                if evidence_row:

                    # reliability_score is stored on a 0-10
                    # scale for the dashboard/database.
                    evidence_row.reliability_score = (
                        verification_score
                    )

                    session.commit()

                # =============================================
                # STEP 6: SKEPTIC REVIEW
                # =============================================

                skeptic_result = (
                    skeptic_agent.analyze_evidence(
                        claim=claim["claim"],
                        evidence_list=evidence_list
                    )
                )

                skeptic_score = (
                    calculate_skeptic_score(
                        skeptic_result
                    )
                )

                all_skeptic_scores.append(
                    skeptic_score
                )

                print(
                    "Skeptic Review:"
                )

                print(
                    f"  Score: "
                    f"{skeptic_score}/10"
                )

                print(
                    f"  Contradicting: "
                    f"{len(skeptic_result.get('contradicting_evidence', []))}"
                )

                print(
                    f"  Uncertain: "
                    f"{len(skeptic_result.get('uncertain_evidence', []))}"
                )

                print(
                    f"  Neutral: "
                    f"{len(skeptic_result.get('neutral_evidence', []))}"
                )

                # =============================================
                # STEP 7: EVIDENCE STRENGTH
                # =============================================

                evidence_strength_score, reasoning = (
                    score_claim(
                        claim_row=claim_row,

                        evidence_text=evidence_text,

                        paper_context=(
                            paper.get("title", "")
                            + "\n"
                            + paper.get("abstract", "")
                        ),

                        client=client,

                        citation_count=(
                            paper.get(
                                "citation_count"
                            )
                        ),
                    )
                )

                update_claim_score(
                    session=session,
                    claim_id=claim_row.id,
                    evidence_strength_score=(
                        evidence_strength_score
                    )
                )

                all_evidence_strength_scores.append(
                    evidence_strength_score
                )

                print(
                    "Evidence Strength:"
                )

                print(
                    f"  Score: "
                    f"{evidence_strength_score}/10"
                )

                if reasoning:
                    print(
                        f"  Reasoning: {reasoning}"
                    )

                # =============================================
                # SAVE CLAIM RESULT
                # =============================================

                all_claim_results.append({

                    "claim_id":
                        claim_row.id,

                    "paper_id":
                        str(paper["id"]),

                    "paper_title":
                        paper["title"],

                    "claim":
                        claim["claim"],

                    "benchmark":
                        claim.get(
                            "benchmark_name"
                        ),

                    "value_type":
                        claim.get(
                            "value_type"
                        ),

                    "reported_value":
                        claim.get(
                            "reported_value"
                        ),

                    "evidence_strength_score":
                        evidence_strength_score,

                    "evidence_strength_reasoning":
                        reasoning,

                    "verification_score":
                        verification_score,

                    "verification":
                        verification_result,

                    "skeptic_score":
                        skeptic_score,

                    "skeptic":
                        skeptic_result,

                })

        # ====================================================
        # STEP 8: CONTRADICTION DETECTION
        # ====================================================

        print()
        print("=" * 70)
        print("STEP 8: DETECTING CONTRADICTIONS")
        print("=" * 70)

        contradiction_results = (
            detect_all_contradictions(
                session
            )
        )

        contradiction_rows = (
            store_contradictions(
                session,
                contradiction_results
            )
        )

        contradiction_confidence = (
            calculate_contradiction_confidence(
                contradiction_results
            )
        )

        print(
            f"Comparable pairs: "
            f"{len(contradiction_results)}"
        )

        print(
            f"New contradiction rows stored: "
            f"{len(contradiction_rows)}"
        )

        print(
            f"Contradiction confidence: "
            f"{contradiction_confidence}/10"
        )

        # ====================================================
        # STEP 9: OVERALL CONFIDENCE
        # ====================================================

        print()
        print("=" * 70)
        print("STEP 9: CALCULATING OVERALL CONFIDENCE")
        print("=" * 70)

        evidence_strength_average = (
            sum(all_evidence_strength_scores)
            / len(all_evidence_strength_scores)
            if all_evidence_strength_scores
            else 0
        )

        verification_average = (
            sum(all_verification_scores)
            / len(all_verification_scores)
            if all_verification_scores
            else 0
        )

        skeptic_average = (
            sum(all_skeptic_scores)
            / len(all_skeptic_scores)
            if all_skeptic_scores
            else 0
        )

        confidence_result = calculate_confidence(

            evidence_strength=round(
                evidence_strength_average,
                2
            ),

            verification_score=round(
                verification_average,
                2
            ),

            contradiction_score=(
                contradiction_confidence
            ),

            skeptic_score=round(
                skeptic_average,
                2
            ),
        )

        print(
            f"Evidence Strength : "
            f"{confidence_result.breakdown['Evidence Strength']}/10"
        )

        print(
            f"Verification     : "
            f"{confidence_result.breakdown['Verification']}/10"
        )

        print(
            f"Contradiction    : "
            f"{confidence_result.breakdown['Contradiction']}/10"
        )

        print(
            f"Skeptic          : "
            f"{confidence_result.breakdown['Skeptic']}/10"
        )

        print()
        print(
            f"OVERALL CONFIDENCE: "
            f"{confidence_result.overall_score}/10"
        )

        print(
            f"CONFIDENCE LEVEL: "
            f"{confidence_result.confidence_level}"
        )

        # ====================================================
        # STEP 10: FINAL SUMMARY
        # ====================================================

        final_result = {
            "status": "success",

            "query": query,

            "papers_retrieved": len(papers),

            "papers": papers,

            "claims_extracted": len(all_claim_results),

            "claims": all_claim_results,

            "contradictions": contradiction_results,

            "confidence": {
                "overall_score":
                    confidence_result.overall_score,

                "confidence_level":
                    confidence_result.confidence_level,

                "breakdown":
                    confidence_result.breakdown,
            },
        }

        print()
        print("=" * 70)
        print("PIPELINE COMPLETED")
        print("=" * 70)

        return final_result

    except Exception:

        session.rollback()

        raise

    finally:

        session.close()


# ============================================================
# RUN
# ============================================================

if __name__ == "__main__":

    # Run only the deterministic contradiction regression test with:
    #     python test_pipeline.py --regression
    #
    # Run only the deterministic evidence verification regression test with:
    #     python test_pipeline.py --evidence-regression
    #
    # Run the normal live integration pipeline with:
    #     python test_pipeline.py
    if "--regression" in sys.argv:
        run_contradiction_regression_test()
        raise SystemExit(0)

    if "--evidence-regression" in sys.argv:
        run_evidence_verification_regression_test()
        raise SystemExit(0)

    result = run_pipeline()

    print()
    print("=" * 70)
    print("FINAL RESULT")
    print("=" * 70)

    print(
        f"Query: "
        f"{result['query']}"
    )

    print(
        f"Papers: "
        f"{result['papers_retrieved']}"
    )

    print(
        f"Claims: "
        f"{result['claims_extracted']}"
    )

    print(
        f"Contradiction pairs: "
        f"{len(result['contradictions'])}"
    )

    print(
        f"Overall confidence: "
        f"{result['confidence']['overall_score']}/10"
    )

    print(
        f"Confidence level: "
        f"{result['confidence']['confidence_level']}"
    )