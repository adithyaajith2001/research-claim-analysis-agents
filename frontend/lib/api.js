/**
 * lib/api.js
 *
 * Thin fetch wrapper around the FastAPI backend (backend/main.py).
 * Every function here maps 1:1 to one REST endpoint - keep it that way
 * so the mapping between frontend calls and backend routes stays obvious.
 */

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";

async function request(path, options = {}) {
  const res = await fetch(`${API_BASE_URL}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });

  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body.detail || detail;
    } catch {
      // response wasn't JSON - fall back to statusText
    }
    throw new Error(detail);
  }

  return res.json();
}

/** POST /api/analyze - runs the full agent pipeline for a query. */
export function analyzeQuery(query, maxResults = 8) {
  return request("/api/analyze", {
    method: "POST",
    body: JSON.stringify({ query, max_results: maxResults }),
  });
}

/** GET /api/dashboard-summary - aggregate counts for the dashboard header. */
export function getDashboardSummary() {
  return request("/api/dashboard-summary");
}

/** GET /api/papers - all stored papers. */
export function getPapers() {
  return request("/api/papers");
}

/** GET /api/contradictions - all stored claim-pair contradictions. */
export function getContradictions() {
  return request("/api/contradictions");
}
