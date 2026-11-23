import truststore
truststore.inject_into_ssl()
import html
import json
import os
import re
import sys
import threading
import time
import traceback
import uuid

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field


# ============================================================
# PROJECT PATH SETUP
# ============================================================

BACKEND_DIR = os.path.dirname(
    os.path.abspath(__file__)
)

RETRIEVERS_DIR = os.path.join(
    BACKEND_DIR,
    "retrievers"
)

# test_pipeline.py and the supporting backend modules
# are inside the retrievers folder.
if RETRIEVERS_DIR not in sys.path:
    sys.path.insert(
        0,
        RETRIEVERS_DIR
    )


# ============================================================
# IMPORT COMPLETE PIPELINE
# ============================================================

from test_pipeline import run_pipeline
from cancel import AnalysisCancelled, clear_stop, request_stop


# ============================================================
# FASTAPI APP
# ============================================================

app = FastAPI(
    title="ResearchClaimAI API",
    description=(
        "Multi-agent research claim analysis backend"
    ),
    version="1.0.0",
)


# ============================================================
# CORS
# ============================================================

app.add_middleware(
    CORSMiddleware,
    # Extra allowed sites can be added with CORS_ORIGINS="https://a.com,https://b.com"
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        *[o.strip() for o in os.environ.get("CORS_ORIGINS", "").split(",") if o.strip()],
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================
# REQUEST MODEL
# ============================================================

class AnalysisRequest(BaseModel):

    query: str = Field(
        ...,
        min_length=1,
        description=(
            "Research topic or benchmark to analyze"
        ),
    )

    refresh: bool = Field(
        default=False,
        description="Ignore any saved report and analyse again",
    )

    restart: bool = Field(
        default=False,
        description=(
            "Stop the analysis that is running now (if any) "
            "and start this one instead"
        ),
    )

    max_results: int = Field(
        default=8,
        ge=1,
        le=20,
        description=(
            "Maximum number of papers to retrieve"
        ),
    )


# ============================================================
# ROOT
# ============================================================

@app.get("/")
def root():

    return {
        "status": "success",
        "message": "ResearchClaimAI backend is running",
    }


# ============================================================
# HEALTH CHECK
# ============================================================

@app.get("/api/health")
def health():

    return {
        "status": "healthy",
        "message": "FastAPI backend is running",
    }


# ============================================================
# SUPPORTED MODELS AND BENCHMARKS (for the Explore page)
# ============================================================

@app.get("/api/catalog")
def catalog():

    from known_papers import KNOWN_MODEL_PAPERS

    return {
        "models_with_own_paper": [
            {"key": key, "arxiv_id": arxiv_id}
            for key, arxiv_id, _ in KNOWN_MODEL_PAPERS
        ],
        "cached_reports": len(ANALYSIS_CACHE),
    }


# ============================================================
# HELPER:
# NORMALIZE PIPELINE RETURN VALUE
# ============================================================

def normalize_pipeline_result(
    pipeline_output
):
    """
    Accept both possible return formats:

    New:
        run_pipeline() -> final_result

    Older:
        run_pipeline() -> (session, final_result)

    Returns:
        final_result dictionary
    """

    if isinstance(
        pipeline_output,
        tuple
    ):

        if len(pipeline_output) >= 2:
            result = pipeline_output[1]

        else:
            result = {}

    elif isinstance(
        pipeline_output,
        dict
    ):

        result = pipeline_output

    else:

        result = {}

    return result


# ============================================================
# HELPER:
# BUILD PAPER EVIDENCE GROUPS
# ============================================================


def build_evidence_groups(claims):
    """
    Build paper-level evidence groups for the React dashboard.

    Each paper appears once per category. Individual claims and
    evidence records are preserved within the paper-level record.

    similarity_score: TF-IDF similarity, 0.0 to 1.0
    verification_score: structured verification, 0.0 to 10.0
    structured_match_score: normalized structured score, 0.0 to 1.0
    """

    categories = ("supporting", "contradicting", "neutral")

    groups = {category: [] for category in categories}
    indexes = {category: {} for category in categories}
    metrics = {}

    def normalize_text(value):
        return " ".join(str(value or "").casefold().split())

    def as_number(value):
        try:
            number = float(value)
            return number if number == number else None
        except (TypeError, ValueError):
            return None

    def get_paper_key(paper_id, paper_title, claim_text):
        normalized_title = normalize_text(paper_title)

        if normalized_title:
            return ("title", normalized_title)

        if paper_id:
            return ("id", str(paper_id))

        return ("claim", normalize_text(claim_text))

    def add_evidence(category, paper_id, paper_title, claim_text, item):
        if not isinstance(item, dict):
            return

        paper_id = str(paper_id or "")
        paper_title = str(
            paper_title or "Unknown research paper"
        ).strip()
        claim_text = str(claim_text or "")
        evidence_text = str(item.get("evidence") or "")

        paper_key = get_paper_key(
            paper_id, paper_title, claim_text
        )

        if paper_key not in indexes[category]:
            record = {
                "paper_id": paper_id,
                "paper_title": paper_title,
                "claim": claim_text,
                "claims": [],
                "evidence": evidence_text,
                "evidence_items": [],
                "similarity_score": 0.0,
                "verification_score": None,
                "structured_match_score": None,
                "contradiction_score": 0.0,
                "matched_keywords": [],
            }

            indexes[category][paper_key] = record
            groups[category].append(record)

            metrics[(category, paper_key)] = {
                "seen": set(),
                "similarity_score": [],
                "verification_score": [],
                "structured_match_score": [],
                "contradiction_score": [],
            }

        record = indexes[category][paper_key]
        metric = metrics[(category, paper_key)]

        # Preserve all distinct claims associated with this paper.
        if claim_text and claim_text not in record["claims"]:
            record["claims"].append(claim_text)

        if not record["claim"] and claim_text:
            record["claim"] = claim_text

        if not record["evidence"] and evidence_text:
            record["evidence"] = evidence_text

        # Deduplicate repeated copies of the same claim/evidence pair.
        evidence_key = (
            normalize_text(claim_text),
            normalize_text(evidence_text),
        )

        if evidence_key in metric["seen"]:
            return

        metric["seen"].add(evidence_key)

        record["evidence_items"].append({
            "claim": claim_text,
            "evidence": evidence_text,
            "similarity_score": item.get("similarity_score"),
            "verification_score": item.get("verification_score"),
            "structured_match_score": item.get(
                "structured_match_score"
            ),
            "contradiction_score": item.get(
                "contradiction_score"
            ),
            "classification": item.get("classification"),
        })

        # Keep each score in its own scale and aggregate separately.
        for field in (
            "similarity_score",
            "verification_score",
            "structured_match_score",
            "contradiction_score",
        ):
            value = as_number(item.get(field))

            if value is not None:
                metric[field].append(value)

        keywords = item.get("matched_keywords") or []

        if isinstance(keywords, (list, tuple, set)):
            for keyword in keywords:
                if keyword not in record["matched_keywords"]:
                    record["matched_keywords"].append(keyword)

    for claim in claims:
        if not isinstance(claim, dict):
            continue

        paper_id = claim.get("paper_id", "")
        paper_title = claim.get("paper_title", "")
        claim_text = claim.get("claim", "")

        verification = claim.get("verification") or {}
        skeptic = claim.get("skeptic") or {}

        if not isinstance(verification, dict):
            verification = {}

        if not isinstance(skeptic, dict):
            skeptic = {}

        # Match skeptic results to verifier results where possible,
        # allowing their verification scores to be retained.
        verification_by_text = {}

        for item in verification.get("evidence_results", []):
            if not isinstance(item, dict):
                continue

            evidence_key = normalize_text(item.get("evidence"))

            if evidence_key:
                verification_by_text[evidence_key] = item

        # Supporting evidence
        for item in verification.get("supporting_evidence", []):
            add_evidence(
                "supporting",
                paper_id,
                paper_title,
                claim_text,
                item,
            )

        # Contradicting evidence from the skeptic agent
        for item in skeptic.get("contradicting_evidence", []):
            if not isinstance(item, dict):
                continue

            evidence_key = normalize_text(item.get("evidence"))
            matched = verification_by_text.get(evidence_key, {})

            # Preserve skeptic fields while filling in verifier scores.
            enriched_item = {**matched, **item}

            add_evidence(
                "contradicting",
                paper_id,
                paper_title,
                claim_text,
                enriched_item,
            )

        # Weak/unrelated verifier evidence belongs in the dashboard's
        # existing "Neutral Evidence" section.
        for field in ("weak_evidence", "unrelated_evidence"):
            for item in verification.get(field, []):
                add_evidence(
                    "neutral",
                    paper_id,
                    paper_title,
                    claim_text,
                    item,
                )

        # Include neutral and uncertain skeptic evidence. When the
        # verifier explicitly classified the exact same evidence as
        # supporting, do not duplicate it in the neutral category.
        for field in ("neutral_evidence", "uncertain_evidence"):
            for item in skeptic.get(field, []):
                if not isinstance(item, dict):
                    continue

                evidence_key = normalize_text(item.get("evidence"))
                matched = verification_by_text.get(evidence_key, {})

                if matched.get("classification") == "supporting":
                    continue

                enriched_item = {**matched, **item}

                add_evidence(
                    "neutral",
                    paper_id,
                    paper_title,
                    claim_text,
                    enriched_item,
                )

    # Aggregate scores across each paper's distinct evidence records.
    for category in categories:
        for paper_key, record in indexes[category].items():
            metric = metrics[(category, paper_key)]

            for field in (
                "similarity_score",
                "verification_score",
                "structured_match_score",
                "contradiction_score",
            ):
                values = metric[field]

                if values:
                    average = sum(values) / len(values)
                    record[field] = round(
                        average,
                        4 if field == "similarity_score" else 2,
                    )
                elif field in (
                    "verification_score",
                    "structured_match_score",
                ):
                    record[field] = None
                else:
                    record[field] = 0.0

    return (
        groups["supporting"],
        groups["contradicting"],
        groups["neutral"],
    )



# ============================================================
# HELPERS: CLEAN TEXT + BUILD API RESPONSE
# ============================================================

def unescape_strings(value):
    """
    Papers from CrossRef/arXiv sometimes contain HTML entities such as
    '&amp;' or '&lt;'. Decode them everywhere in the response so the
    dashboard shows plain text.
    """

    if isinstance(value, str):
        return html.unescape(value)

    if isinstance(value, list):
        return [unescape_strings(item) for item in value]

    if isinstance(value, dict):
        return {
            key: unescape_strings(item)
            for key, item in value.items()
        }

    return value


def build_analysis_response(query, pipeline_output, elapsed_seconds):
    """
    Turn the raw pipeline result into the JSON the React dashboard reads.
    """

    result = normalize_pipeline_result(pipeline_output)

    if not result:
        raise RuntimeError("Pipeline returned an empty result.")

    papers = result.get("papers", [])
    claims = result.get("claims", [])
    contradictions = result.get("contradictions", [])
    confidence = result.get("confidence", {})

    if not isinstance(papers, list):
        papers = []

    if not isinstance(claims, list):
        claims = []

    if not isinstance(contradictions, list):
        contradictions = []

    if not isinstance(confidence, dict):
        confidence = {}

    (
        supporting_papers,
        contradicting_papers,
        neutral_papers,
    ) = build_evidence_groups(claims)

    overall_score = confidence.get("overall_score", 0)
    confidence_level = confidence.get("confidence_level", "Low")

    summary = (
        f"Analysis completed for '{query}'. "
        f"The system retrieved {len(papers)} research papers and "
        f"extracted {len(claims)} benchmark-related claims. "
        f"{len(contradictions)} cross-paper comparison records were "
        f"generated. The aggregated confidence score is "
        f"{overall_score}/10 ({confidence_level})."
    )

    response = {
        "status": "success",
        "query": result.get("query", query),
        "papers_retrieved": result.get("papers_retrieved", len(papers)),
        "papers": papers,
        "claims_extracted": result.get("claims_extracted", len(claims)),
        "claims": claims,
        "supportingPapers": supporting_papers,
        "contradictingPapers": contradicting_papers,
        "neutralPapers": neutral_papers,
        "contradictions": contradictions,
        "confidence": confidence,
        "summary": summary,
        "analysis_seconds": round(float(elapsed_seconds), 1),
        "query_models": result.get("query_models", []),
        "claims_skipped_other_models": result.get("claims_skipped_other_models", 0),
        "skipped_claims": result.get("skipped_claims", []),
    }

    print()
    print("=" * 70)
    print("API ANALYSIS COMPLETED")
    print("=" * 70)
    print(f"Papers: {response['papers_retrieved']}")
    print(f"Claims: {response['claims_extracted']}")
    print(f"Supporting evidence: {len(supporting_papers)}")
    print(f"Contradicting evidence: {len(contradicting_papers)}")
    print(f"Neutral evidence: {len(neutral_papers)}")
    print(f"Contradiction pairs: {len(contradictions)}")
    print(f"Overall confidence: {overall_score}/10")
    print(f"Confidence level: {confidence_level}")
    print(f"Analysis time: {response['analysis_seconds']}s")
    print("=" * 70)

    return unescape_strings(response)


# ============================================================
# COMPLETE ANALYSIS (one request, waits for the full result)
# ============================================================

@app.post("/api/analyze")
def analyze(
    request: AnalysisRequest
):

    query = request.query.strip()

    if not query:
        raise HTTPException(
            status_code=400,
            detail="Research query cannot be empty."
        )

    print()
    print("=" * 70)
    print("RESEARCHCLAIMAI ANALYSIS REQUEST")
    print("=" * 70)
    print(f"Query: {query}")
    print(f"Max results: {request.max_results}")
    print("=" * 70)

    try:
        started = time.perf_counter()

        pipeline_output = run_pipeline(
            query=query,
            max_results=request.max_results,
        )

        return build_analysis_response(
            query,
            pipeline_output,
            time.perf_counter() - started,
        )

    except HTTPException:
        raise

    except Exception as error:

        print()
        print("=" * 70)
        print("API ANALYSIS FAILED")
        print("=" * 70)
        print(f"Error: {error}")
        traceback.print_exc()

        raise HTTPException(
            status_code=500,
            detail=str(error)
        )


# ============================================================
# BACKGROUND JOBS (used by the dashboard: live progress)
# ============================================================
#
# POST /api/jobs        -> starts an analysis, returns {job_id}
# GET  /api/jobs/{id}   -> {status, stage, percent, message,
#                           elapsed_seconds, result (when done)}
#
# Only ONE analysis can run at a time, because each run resets the
# working database so contradiction detection sees only that run.

JOBS = {}
JOBS_LOCK = threading.Lock()
ACTIVE_JOB = {"id": None}


# ------------------------------------------------------------
# RESULT CACHE
# A question that was answered recently is returned instantly, so the
# second time (or in a live demo) nobody waits a minute. Only reports
# that actually contain claims are kept, so a temporary network problem
# is never remembered as "no results".
# ------------------------------------------------------------

CACHE_FILE = os.path.join(BACKEND_DIR, "data", "analysis_cache.json")
CACHE_TTL_SECONDS = 7 * 24 * 3600
CACHE_LOCK = threading.Lock()
ANALYSIS_CACHE = {}


def _cache_key(query, max_results):
    return " ".join(str(query).lower().split()) + f"|{int(max_results)}"


def _load_cache():
    try:
        with open(CACHE_FILE, "r", encoding="utf-8") as handle:
            data = json.load(handle)
        if isinstance(data, dict):
            ANALYSIS_CACHE.update(data)
    except Exception:
        pass


def _save_cache():
    try:
        os.makedirs(os.path.dirname(CACHE_FILE), exist_ok=True)
        with open(CACHE_FILE, "w", encoding="utf-8") as handle:
            json.dump(ANALYSIS_CACHE, handle)
    except Exception as error:
        print(f"Could not save analysis cache: {error}")


def _cache_get(query, max_results):
    with CACHE_LOCK:
        entry = ANALYSIS_CACHE.get(_cache_key(query, max_results))
    if not entry:
        return None
    if time.time() - entry.get("saved_at", 0) > CACHE_TTL_SECONDS:
        return None
    return entry.get("result")


def _cache_put(query, max_results, result):
    if not result or not result.get("claims"):
        return
    with CACHE_LOCK:
        ANALYSIS_CACHE[_cache_key(query, max_results)] = {
            "saved_at": time.time(),
            "result": result,
        }
        _save_cache()


_load_cache()


def _run_job(job_id, query, max_results, papers=None):

    job = JOBS[job_id]

    def progress(stage, percent, message):
        job["stage"] = stage
        job["percent"] = percent
        job["message"] = message

    try:
        clear_stop()
        started = time.perf_counter()

        pipeline_output = run_pipeline(
            query=query,
            max_results=max_results,
            progress_callback=progress,
            papers_override=papers,
        )

        job["result"] = build_analysis_response(
            query,
            pipeline_output,
            time.perf_counter() - started,
        )
        if papers is None:  # uploaded papers are never shared through the cache
            _cache_put(query, max_results, job["result"])
        job["stage"] = "done"
        job["percent"] = 100
        job["message"] = "Analysis complete"
        job["status"] = "done"

    except AnalysisCancelled:
        print(f"Analysis stopped by the user: {job['query']}")
        job["status"] = "cancelled"
        job["message"] = "Analysis stopped"

    except Exception as error:

        print()
        print("=" * 70)
        print("API ANALYSIS FAILED")
        print("=" * 70)
        traceback.print_exc()

        job["status"] = "error"
        job["message"] = str(error) or "Analysis failed."

    finally:
        job["finished_at"] = time.time()

        with JOBS_LOCK:
            if ACTIVE_JOB["id"] == job_id:
                ACTIVE_JOB["id"] = None


def _stop_active_job(wait_seconds=0):
    """Ask the running analysis to stop; optionally wait until it has."""

    with JOBS_LOCK:
        active_id = ACTIVE_JOB["id"]
        active = JOBS.get(active_id) if active_id else None

        if active is not None and active["status"] == "running":
            active["status"] = "cancelled"
            active["message"] = "Analysis stopped"
            request_stop()

    deadline = time.time() + wait_seconds

    while wait_seconds and time.time() < deadline:
        with JOBS_LOCK:
            if ACTIVE_JOB["id"] is None:
                return True
        time.sleep(0.4)

    with JOBS_LOCK:
        return ACTIVE_JOB["id"] is None


@app.post("/api/jobs/{job_id}/cancel")
def cancel_job(job_id: str):
    """Stop an analysis the user no longer wants."""

    job = JOBS.get(job_id)

    if job is None:
        raise HTTPException(status_code=404, detail="Unknown analysis job.")

    if job["status"] == "running" and ACTIVE_JOB["id"] == job_id:
        _stop_active_job()

    return {"job_id": job_id, "status": job["status"]}


@app.post("/api/jobs")
def start_job(
    request: AnalysisRequest
):

    query = request.query.strip()

    if not query:
        raise HTTPException(
            status_code=400,
            detail="Research query cannot be empty."
        )

    cached = None if request.refresh else _cache_get(query, request.max_results)

    if cached is not None:
        job_id = uuid.uuid4().hex
        now = time.time()
        result = dict(cached)
        result["from_cache"] = True
        JOBS[job_id] = {
            "job_id": job_id,
            "query": query,
            "status": "done",
            "stage": "done",
            "percent": 100,
            "message": "Loaded a saved report",
            "started_at": now,
            "finished_at": now,
            "result": result,
        }
        print(f"Served from cache: {query}")
        return {"job_id": job_id, "status": "done"}

    if request.restart:
        _stop_active_job(wait_seconds=90)

    with JOBS_LOCK:

        active_id = ACTIVE_JOB["id"]

        if active_id is not None:
            active = JOBS[active_id]

            if active["status"] == "cancelled":
                raise HTTPException(
                    status_code=409,
                    detail=(
                        "The previous analysis is still stopping. "
                        "Please try again in a few seconds."
                    ),
                )

            # Same query again (double click / page reload): reuse it.
            if active["query"].casefold() == query.casefold():
                return {"job_id": active_id, "status": active["status"]}

            raise HTTPException(
                status_code=409,
                detail=(
                    "Another analysis is still running. "
                    "Please wait for it to finish."
                ),
            )

        job_id = uuid.uuid4().hex

        JOBS[job_id] = {
            "job_id": job_id,
            "query": query,
            "status": "running",
            "stage": "starting",
            "percent": 1,
            "message": "Starting analysis",
            "started_at": time.time(),
            "finished_at": None,
            "result": None,
        }

        ACTIVE_JOB["id"] = job_id

    print()
    print("=" * 70)
    print("RESEARCHCLAIMAI ANALYSIS JOB STARTED")
    print("=" * 70)
    print(f"Job: {job_id}")
    print(f"Query: {query}")
    print(f"Max results: {request.max_results}")
    print("=" * 70)

    threading.Thread(
        target=_run_job,
        args=(job_id, query, request.max_results),
        daemon=True,
    ).start()

    return {"job_id": job_id, "status": "running"}



# ============================================================
# UPLOAD A PDF
# ============================================================

MAX_UPLOAD_BYTES = 25 * 1024 * 1024


def _paper_from_pdf(pdf_bytes, filename):
    """Read an uploaded PDF into the paper shape the pipeline expects."""

    from pdf_processor_v2 import PDFProcessor

    text = PDFProcessor(verify_ssl=True).extract_text(pdf_bytes) or ""
    text = text.strip()

    if len(text) < 500:
        raise HTTPException(
            status_code=422,
            detail=(
                "No readable text was found in this PDF. Scanned pages "
                "(images of text) are not supported."
            ),
        )

    base = os.path.splitext(os.path.basename(filename or "paper"))[0]
    base = re.sub(r"[_-]+", " ", base).strip() or "Uploaded paper"

    # The title is usually the first reasonable-looking line.
    title = base
    for line in text.splitlines()[:12]:
        line = " ".join(line.split())
        if 15 <= len(line) <= 200 and not line.lower().startswith(("arxiv", "http", "preprint")):
            title = line
            break

    abstract = ""
    match = re.search(r"abstract[\s:.\-—]*(.{200,2500}?)(?:\n\s*(?:1\.?\s*)?introduction|\Z)", text, re.I | re.S)
    if match:
        abstract = " ".join(match.group(1).split())
    if not abstract:
        abstract = " ".join(text[:1500].split())

    return {
        "id": "upload-" + uuid.uuid4().hex[:10],
        "title": title,
        "authors": "",
        "year": None,
        "source": "Uploaded PDF",
        "source_url": "",
        "citation_count": 0,
        "abstract": abstract,
        "full_text": text,
    }


@app.post("/api/jobs/upload")
async def start_upload_job(request: Request, filename: str = "paper.pdf"):
    """
    Check the claims of one uploaded PDF. The file is sent as the raw
    request body (no multipart library is needed) with ?filename=...
    """

    pdf_bytes = await request.body()

    if not pdf_bytes:
        raise HTTPException(status_code=400, detail="No file was received.")

    if len(pdf_bytes) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=413,
            detail="This file is larger than 25 MB.",
        )

    if not pdf_bytes.startswith(b"%PDF"):
        raise HTTPException(
            status_code=415,
            detail="Only PDF files can be uploaded.",
        )

    paper = _paper_from_pdf(pdf_bytes, filename)
    query = f"Uploaded paper: {paper['title']}"

    with JOBS_LOCK:
        if ACTIVE_JOB["id"] is not None:
            raise HTTPException(
                status_code=409,
                detail="Another analysis is still running. Please wait for it to finish.",
            )

        job_id = uuid.uuid4().hex
        JOBS[job_id] = {
            "job_id": job_id,
            "query": query,
            "status": "running",
            "stage": "starting",
            "percent": 1,
            "message": "Reading the uploaded paper",
            "started_at": time.time(),
            "finished_at": None,
            "result": None,
        }
        ACTIVE_JOB["id"] = job_id

    threading.Thread(
        target=_run_job,
        args=(job_id, query, 1, [paper]),
        daemon=True,
    ).start()

    return {"job_id": job_id, "status": "running", "title": paper["title"]}


@app.get("/api/jobs/{job_id}")
def get_job(job_id: str):

    job = JOBS.get(job_id)

    if job is None:
        raise HTTPException(
            status_code=404,
            detail="Unknown analysis job."
        )

    end = job["finished_at"] or time.time()

    payload = {
        "job_id": job["job_id"],
        "query": job["query"],
        "status": job["status"],
        "stage": job["stage"],
        "percent": job["percent"],
        "message": job["message"],
        "elapsed_seconds": round(end - job["started_at"], 1),
    }

    if job["status"] == "done":
        payload["result"] = job["result"]

    return payload


# ============================================================
# ACCOUNT HISTORY
#
# Each account's past reports are kept on the server (keyed by the
# account's email), not only in the browser, so the history is still
# there after the browser's site data is cleared or on another device.
# This is demo-grade: there is no server-side login, so the email is
# trusted as given.
# ============================================================

HISTORY_FILE = os.path.join(BACKEND_DIR, "data", "history.json")
HISTORY_LOCK = threading.Lock()
HISTORY_MAX = 100


def _history_email(email: str) -> str:
    return str(email or "").strip().lower()


def _history_read() -> dict:
    try:
        with open(HISTORY_FILE, "r", encoding="utf-8") as handle:
            data = json.load(handle)
        return data if isinstance(data, dict) else {}
    except FileNotFoundError:
        return {}
    except Exception as error:
        print(f"[warn] could not read history: {error}")
        return {}


def _history_write(data: dict) -> None:
    os.makedirs(os.path.dirname(HISTORY_FILE), exist_ok=True)
    temp = HISTORY_FILE + ".tmp"
    with open(temp, "w", encoding="utf-8") as handle:
        json.dump(data, handle)
    os.replace(temp, HISTORY_FILE)


class HistoryEntryRequest(BaseModel):
    email: str
    entry: dict


@app.get("/api/history")
def get_history(email: str, id: str = ""):
    """
    Without `id`: the account's list, newest first, WITHOUT the full
    reports (they are large). With `id`: that one entry, full report included.
    """
    key = _history_email(email)
    if not key:
        raise HTTPException(status_code=400, detail="email is required")

    with HISTORY_LOCK:
        entries = _history_read().get(key, [])

    if id:
        for entry in entries:
            if entry.get("id") == id:
                return {"entry": entry}
        raise HTTPException(status_code=404, detail="History entry not found.")

    return {
        "entries": [
            {name: value for name, value in entry.items() if name != "analysis"}
            for entry in entries
        ]
    }


@app.post("/api/history")
def add_history(request: HistoryEntryRequest):
    key = _history_email(request.email)
    entry = request.entry
    if not key or not entry.get("id"):
        raise HTTPException(status_code=400, detail="email and entry id are required")
    with HISTORY_LOCK:
        data = _history_read()
        entries = [e for e in data.get(key, []) if e.get("id") != entry["id"]]
        entries.insert(0, entry)
        entries.sort(key=lambda e: str(e.get("timestamp", "")), reverse=True)
        data[key] = entries[:HISTORY_MAX]
        _history_write(data)
    return {"ok": True, "count": len(data[key])}


@app.delete("/api/history")
def delete_history(email: str, id: str = ""):
    key = _history_email(email)
    if not key:
        raise HTTPException(status_code=400, detail="email is required")
    with HISTORY_LOCK:
        data = _history_read()
        if id:
            data[key] = [e for e in data.get(key, []) if e.get("id") != id]
        else:
            data[key] = []
        _history_write(data)
    return {"ok": True}


# ============================================================
# RUN DIRECTLY
# ============================================================

if __name__ == "__main__":

    import uvicorn

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
    )