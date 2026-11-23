import axios from "axios";

// Backend address. Set VITE_API_URL in frontend/.env to change it.
const API_BASE_URL =
  import.meta.env.VITE_API_URL || "http://localhost:8000";

const POLL_INTERVAL_MS = 2000;
const MAX_WAIT_MS = 15 * 60 * 1000;
const MAX_CONSECUTIVE_POLL_ERRORS = 5;

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

/**
 * Turn the backend JSON into the shape the dashboard uses.
 */
function shapeResult(data, trimmedQuery) {
  return {
    status: data.status || "success",
    query: data.query || trimmedQuery,
    papers_retrieved: data.papers_retrieved || 0,
    papersRetrieved: data.papers_retrieved || 0,
    papers: Array.isArray(data.papers) ? data.papers : [],
    claims_extracted: data.claims_extracted || 0,
    claimsExtracted: data.claims_extracted || 0,
    claims: Array.isArray(data.claims) ? data.claims : [],
    supportingPapers: Array.isArray(data.supportingPapers)
      ? data.supportingPapers
      : [],
    contradictingPapers: Array.isArray(data.contradictingPapers)
      ? data.contradictingPapers
      : [],
    neutralPapers: Array.isArray(data.neutralPapers)
      ? data.neutralPapers
      : [],
    contradictions: Array.isArray(data.contradictions)
      ? data.contradictions
      : [],
    confidence: data.confidence || {
      overall_score: 0,
      confidence_level: "Low",
      breakdown: {},
    },
    summary: data.summary || "Analysis completed.",
    analysis_seconds: Number(data.analysis_seconds) || 0,
    from_cache: Boolean(data.from_cache),
    query_models: Array.isArray(data.query_models) ? data.query_models : [],
    claims_skipped_other_models: Number(data.claims_skipped_other_models) || 0,
    skipped_claims: Array.isArray(data.skipped_claims) ? data.skipped_claims : [],
    rawResponse: data,
  };
}

function friendlyError(error) {
  if (error.response && error.response.data) {
    const backendMessage =
      error.response.data.detail || error.response.data.message;

    if (backendMessage) {
      return new Error(
        typeof backendMessage === "string"
          ? backendMessage
          : JSON.stringify(backendMessage)
      );
    }
  }

  if (error.request && !error.response) {
    return new Error(
      "Could not connect to the ResearchClaimAI backend. " +
        `Make sure FastAPI is running on ${API_BASE_URL}.`
    );
  }

  return new Error(
    error.message || "Unable to complete research analysis."
  );
}

/**
 * Run the complete multi-agent analysis.
 *
 * The backend runs the analysis in the background; this function polls
 * it every 2 seconds and calls onProgress({stage, percent, message,
 * elapsedSeconds}) so the loading page can show what is really happening.
 */
export async function analyzeTopic(
  query,
  maxResults = 5,
  onProgress,
  refresh = false,
  options = {}
) {
  const { restart = false, onJobId, existingJobId } = options;
  const trimmedQuery = String(query || "").trim();

  if (!trimmedQuery) {
    throw new Error("Research query cannot be empty.");
  }

  let jobId = existingJobId || null;

  if (jobId) {
    // Already started (an uploaded paper): just follow it.
    if (typeof onJobId === "function") {
      onJobId(jobId);
    }
  } else {
    try {
      const start = await axios.post(
        `${API_BASE_URL}/api/jobs`,
        { query: trimmedQuery, max_results: maxResults, refresh, restart },
        { headers: { "Content-Type": "application/json" }, timeout: 30000 }
      );

      jobId = start.data.job_id;

      if (typeof onJobId === "function") {
        onJobId(jobId);
      }
    } catch (error) {
      throw friendlyError(error);
    }
  }

  const startedAt = Date.now();
  let consecutiveErrors = 0;

  while (Date.now() - startedAt < MAX_WAIT_MS) {
    await sleep(POLL_INTERVAL_MS);

    let job;

    try {
      const response = await axios.get(
        `${API_BASE_URL}/api/jobs/${jobId}`,
        { timeout: 15000 }
      );

      job = response.data;
      consecutiveErrors = 0;
    } catch (error) {
      consecutiveErrors += 1;

      if (consecutiveErrors >= MAX_CONSECUTIVE_POLL_ERRORS) {
        throw friendlyError(error);
      }

      continue;
    }

    if (typeof onProgress === "function") {
      onProgress({
        stage: job.stage,
        percent: job.percent,
        message: job.message,
        elapsedSeconds: job.elapsed_seconds,
      });
    }

    if (job.status === "done") {
      return shapeResult(job.result || {}, trimmedQuery);
    }

    if (job.status === "cancelled") {
      const stopped = new Error("The analysis was stopped.");
      stopped.cancelled = true;
      throw stopped;
    }

    if (job.status === "error") {
      throw new Error(job.message || "Research analysis failed.");
    }
  }

  throw new Error(
    "The analysis is taking longer than expected. " +
      "Please try again with a more specific topic."
  );
}


/**
 * Ask the backend to stop a running analysis. Never throws: if the backend
 * cannot be reached there is nothing left running to stop.
 */
export async function cancelAnalysis(jobId) {
  if (!jobId) return;

  try {
    await axios.post(
      `${API_BASE_URL}/api/jobs/${jobId}/cancel`,
      {},
      { timeout: 10000 }
    );
  } catch {
    /* ignore */
  }
}


/**
 * Upload one PDF. The backend starts the analysis straight away and
 * returns the job to follow. The file is sent as the raw request body.
 */
export async function uploadPaper(file) {
  if (!file) {
    throw new Error("Please choose a PDF file.");
  }

  if (!/\.pdf$/i.test(file.name) && file.type !== "application/pdf") {
    throw new Error("Only PDF files can be uploaded.");
  }

  if (file.size > 25 * 1024 * 1024) {
    throw new Error("This file is larger than 25 MB.");
  }

  try {
    const response = await axios.post(
      `${API_BASE_URL}/api/jobs/upload`,
      file,
      {
        params: { filename: file.name },
        headers: { "Content-Type": "application/pdf" },
        timeout: 120000,
        maxBodyLength: Infinity
      }
    );

    return response.data; // { job_id, title }
  } catch (error) {
    throw friendlyError(error);
  }
}
