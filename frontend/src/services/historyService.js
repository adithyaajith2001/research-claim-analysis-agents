// Search history, kept separately for every signed-in account.
//
// Stored in this browser under the account's email, so each person sees
// only their own searches. (To sync across devices, swap these functions
// for Firestore calls; the rest of the app does not need to change.)

const MAX_ENTRIES = 30;

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

  // If the browser is full, drop the oldest saved reports until it fits.
  while (list.length && !write(historyKey(email), list)) {
    list.pop();
  }

  return entry;
}

export function deleteHistoryEntry(email, id) {
  write(
    historyKey(email),
    getHistory(email).filter((entry) => entry.id !== id)
  );
}

export function clearHistory(email) {
  write(historyKey(email), []);
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
