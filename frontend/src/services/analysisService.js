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
export async function analyzeTopic(query, maxResults = 5, onProgress) {
  const trimmedQuery = String(query || "").trim();

  if (!trimmedQuery) {
    throw new Error("Research query cannot be empty.");
  }

  let jobId;

  try {
    const start = await axios.post(
      `${API_BASE_URL}/api/jobs`,
      { query: trimmedQuery, max_results: maxResults },
      { headers: { "Content-Type": "application/json" }, timeout: 30000 }
    );

    jobId = start.data.job_id;
  } catch (error) {
    throw friendlyError(error);
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

    if (job.status === "error") {
      throw new Error(job.message || "Research analysis failed.");
    }
  }

  throw new Error(
    "The analysis is taking longer than expected. " +
      "Please try again with a more specific topic."
  );
}
