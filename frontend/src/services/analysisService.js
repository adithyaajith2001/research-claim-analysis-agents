
import axios from "axios";

const API_BASE_URL = "http://localhost:8000";

/**
 * Run the complete ResearchClaimAI multi-agent analysis.
 */
export async function analyzeTopic(query, maxResults = 5) {
  const trimmedQuery = String(query || "").trim();

  if (!trimmedQuery) {
    throw new Error("Research query cannot be empty.");
  }

  try {
    const startTime = Date.now();

    console.log("ResearchClaimAI: Starting analysis...");
    console.time("ResearchClaimAI API request");

    const response = await axios.post(
      `${API_BASE_URL}/api/analyze`,
      {
        query: trimmedQuery,
        max_results: maxResults,
      },
      {
        headers: {
          "Content-Type": "application/json",
        },
        timeout: 600000,
      }
    );

    console.timeEnd("ResearchClaimAI API request");

    console.log(
      `ResearchClaimAI: Completed in ${
        ((Date.now() - startTime) / 1000).toFixed(1)
      } seconds`
    );

    const data = response.data;

    if (!data) {
      throw new Error("Backend returned an empty response.");
    }

    if (data.status === "error") {
      throw new Error(data.message || "Research analysis failed.");
    }

    return {
      status: data.status || "success",
      query: data.query || trimmedQuery,
      papersRetrieved: data.papers_retrieved || 0,
      papers: Array.isArray(data.papers) ? data.papers : [],
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
      rawResponse: data,
    };
  } catch (error) {
    console.error("ResearchClaimAI analysis error:", error);

    if (error.response && error.response.data) {
      const backendMessage =
        error.response.data.detail ||
        error.response.data.message;

      throw new Error(
        backendMessage || "Backend analysis request failed."
      );
    }

    if (error.code === "ECONNABORTED") {
      throw new Error(
        "Analysis timed out. The backend may still be processing the papers."
      );
    }

    if (error.request && !error.response) {
      throw new Error(
        "Could not connect to the ResearchClaimAI backend. " +
        "Make sure FastAPI is running on http://localhost:8000."
      );
    }

    throw new Error(
      error.message || "Unable to complete research analysis."
    );
  } finally {
    console.log("ResearchClaimAI: Analysis request finished.");
  }
}
