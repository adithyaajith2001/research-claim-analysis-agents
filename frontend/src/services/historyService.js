// Search history, kept separately for every signed-in account.
//
// The backend is the source of truth: every finished analysis is saved
// there under the account's email, with its full report. This browser only
// keeps a small list (topic, score, time) plus the few newest full reports,
// because a browser can hold only about 5 MB and full reports are large.
// Opening an older entry fetches its report from the backend.

const MAX_ENTRIES = 100;
const FULL_REPORTS_KEPT = 3; // newest reports also kept whole in the browser

// History is saved on the backend per account email. If the backend is
// unreachable the browser copy keeps working on its own.
const API_BASE_URL =
  import.meta.env.VITE_API_URL || "http://localhost:8000";

const apiHistoryUrl = (email, extra = "") =>
  `${API_BASE_URL}/api/history?email=${encodeURIComponent(email)}${extra}`;

const sendQuietly = (url, options) => {
  try {
    fetch(url, options).catch(() => {});
  } catch {
    /* backend not reachable: the browser copy still works */
  }
};

const historyKey = (email) => `researchClaimHistory:${email}`;
const seenKey = (email) => `researchClaimNotificationsSeen:${email}`;

let lastSyncFailed = false;

// True when the last refresh could not reach the backend, so the list shown
// is only what this browser remembers.
export function historyOffline() {
  return lastSyncFailed;
}

function read(key, fallback) {
  try {
    const raw = localStorage.getItem(key);
    return raw ? JSON.parse(raw) : fallback;
  } catch {
    return fallback;
  }
}

function write(key, value) {
  try {
    localStorage.setItem(key, JSON.stringify(value));
    return true;
  } catch {
    return false;
  }
}

// Keep the whole report only for the newest few entries; every other entry
// is kept as a short line. The short list is tiny, so it always fits.
function trimForBrowser(list) {
  return list.map((entry, index) => {
    if (index < FULL_REPORTS_KEPT || !entry.analysis) return entry;
    const { analysis, ...rest } = entry;
    return rest;
  });
}

function saveHistoryList(email, list) {
  const key = historyKey(email);
  let items = trimForBrowser(list).slice(0, MAX_ENTRIES);

  if (write(key, items)) return items;

  // Still too big (browser nearly full): keep only the short list.
  items = items.map(({ analysis, ...rest }) => rest);
  write(key, items);
  return items;
}

export function getHistory(email) {
  if (!email) return [];
  const list = read(historyKey(email), []);
  return Array.isArray(list) ? list : [];
}

// `analysis` is the same object the dashboard reads, so a past report can
// be reopened without running the analysis again.
export function addHistoryEntry(email, analysis) {
  if (!email || !analysis?.topic) return null;

  const { rawResponse, ...compact } = analysis;

  const entry = {
    id: `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
    topic: analysis.topic,
    timestamp: new Date().toISOString(),
    confidence: Number(analysis.confidence) || 0,
    confidenceLevel: analysis.confidenceLevel || "Low",
    papers: Number(analysis.papers_retrieved ?? analysis.papers) || 0,
    claims: Number(analysis.claimsExtracted ?? analysis.claims) || 0,
    seconds: Number(analysis.analysisSeconds) || 0,
    analysis: compact
  };

  saveHistoryList(email, [entry, ...getHistory(email)]);

  sendQuietly(`${API_BASE_URL}/api/history`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, entry })
  });

  return entry;
}

// The full report of a history entry: from this browser if it is still
// here, otherwise from the backend. Resolves to null if neither has it.
export async function getFullReport(email, entry) {
  if (entry?.analysis) return entry.analysis;
  if (!email || !entry?.id) return null;

  try {
    const response = await fetch(apiHistoryUrl(email, `&id=${encodeURIComponent(entry.id)}`));
    if (!response.ok) return null;
    const data = await response.json();
    return data?.entry?.analysis || null;
  } catch {
    return null;
  }
}

export function deleteHistoryEntry(email, id) {
  saveHistoryList(
    email,
    getHistory(email).filter((entry) => entry.id !== id)
  );
  sendQuietly(apiHistoryUrl(email, `&id=${encodeURIComponent(id)}`), {
    method: "DELETE"
  });
}

export function clearHistory(email) {
  write(historyKey(email), []);
  sendQuietly(apiHistoryUrl(email), { method: "DELETE" });
}

// Merge the account's history from the backend with this browser's copy,
// keep the newest MAX_ENTRIES, and return the merged list. Entries that exist
// only in this browser are sent to the backend so nothing is lost.
const inFlightSync = new Map();

export function syncHistory(email) {
  if (!email) return Promise.resolve([]);

  // Pages ask for a sync as they open; share one request instead of
  // running several at once.
  if (!inFlightSync.has(email)) {
    const job = doSync(email).finally(() => inFlightSync.delete(email));
    inFlightSync.set(email, job);
  }

  return inFlightSync.get(email);
}

async function doSync(email) {
  let remote = [];

  try {
    const response = await fetch(apiHistoryUrl(email));
    if (!response.ok) throw new Error(`history ${response.status}`);
    const data = await response.json();
    remote = Array.isArray(data.entries) ? data.entries : [];
    lastSyncFailed = false;
  } catch {
    lastSyncFailed = true;
    return getHistory(email);
  }

  // Read the browser copy only now. A report saved while the request was
  // in flight must not be overwritten by an older copy.
  const local = getHistory(email);

  const byId = new Map();
  [...local, ...remote].forEach((entry) => {
    if (!entry?.id) return;
    const known = byId.get(entry.id);
    // Prefer the copy that still carries its full report.
    if (!known || (!known.analysis && entry.analysis)) byId.set(entry.id, entry);
  });

  const merged = [...byId.values()]
    .sort((a, b) => String(b.timestamp).localeCompare(String(a.timestamp)))
    .slice(0, MAX_ENTRIES);

  const saved = saveHistoryList(email, merged);

  // Anything that exists only in this browser goes to the backend.
  const remoteIds = new Set(remote.map((entry) => entry.id));
  local
    .filter((entry) => entry?.id && !remoteIds.has(entry.id))
    .forEach((entry) =>
      sendQuietly(`${API_BASE_URL}/api/history`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, entry })
      })
    );

  return saved;
}

// ---------------- notifications (built from history) ----------------

export function getNotifications(email) {
  const lastSeen = Number(read(seenKey(email), 0)) || 0;

  return getHistory(email)
    .slice(0, 6)
    .map((entry) => ({
      id: entry.id,
      title: "Analysis finished",
      text: entry.topic,
      timestamp: entry.timestamp,
      unread: new Date(entry.timestamp).getTime() > lastSeen
    }));
}

export function markNotificationsSeen(email) {
  write(seenKey(email), Date.now());
}

export function timeAgo(isoString) {
  const seconds = Math.max(
    0,
    Math.round((Date.now() - new Date(isoString).getTime()) / 1000)
  );

  if (seconds < 60) return "just now";
  if (seconds < 3600) return `${Math.floor(seconds / 60)} min ago`;
  if (seconds < 86400) return `${Math.floor(seconds / 3600)} h ago`;
  return `${Math.floor(seconds / 86400)} d ago`;
}
