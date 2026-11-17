// Search history, kept separately for every signed-in account.
//
// Stored in this browser under the account's email, so each person sees
// only their own searches. (To sync across devices, swap these functions
// for Firestore calls; the rest of the app does not need to change.)

const MAX_ENTRIES = 30;

// History is also saved on the backend (per account email) so it survives
// clearing the browser's site data. If the backend is unreachable the
// browser copy keeps working on its own.
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

// Save the list in the browser. If the browser is full, drop the oldest
// saved reports first; as a last resort keep the newest entries without
// their full report (the backend still has them), so a new search never
// disappears from the list.
function saveHistoryList(email, list) {
  const key = historyKey(email);
  const items = [...list];

  while (items.length > 1 && !write(key, items)) {
    items.pop();
  }

  if (items.length && write(key, items)) return items;

  const light = items.map(({ analysis, ...rest }) => rest);
  write(key, light);
  return light;
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

  const list = [entry, ...getHistory(email)].slice(0, MAX_ENTRIES);

  saveHistoryList(email, list);

  sendQuietly(`${API_BASE_URL}/api/history`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, entry })
  });

  return entry;
}

export function deleteHistoryEntry(email, id) {
  write(
    historyKey(email),
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
    if (!response.ok) return getHistory(email);
    const data = await response.json();
    remote = Array.isArray(data.entries) ? data.entries : [];
  } catch {
    return getHistory(email);
  }

  // Read the browser copy only now. A report saved while the request was
  // in flight must not be overwritten by an older copy.
  const local = getHistory(email);

  const byId = new Map();
  [...remote, ...local].forEach((entry) => {
    if (entry?.id && !byId.has(entry.id)) byId.set(entry.id, entry);
  });

  const merged = [...byId.values()]
    .sort((a, b) => String(b.timestamp).localeCompare(String(a.timestamp)))
    .slice(0, MAX_ENTRIES);

  const saved = saveHistoryList(email, merged);

  const remoteIds = new Set(remote.map((entry) => entry.id));
  merged
    .filter((entry) => !remoteIds.has(entry.id))
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
