import { useContext, useEffect, useMemo, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { signOut } from "firebase/auth";

import Navbar from "../components/layout/Navbar";
import Footer from "../components/layout/Footer";
import { AnalysisContext } from "../context/AnalysisContext";
import { auth } from "../firebase";
import {
  clearSession,
  getSession,
  updateDisplayName
} from "../services/authService";
import {
  clearHistory,
  deleteHistoryEntry,
  getHistory,
  syncHistory,
  timeAgo
} from "../services/historyService";

import "../styles/report.css";
import "../styles/account.css";


function levelTone(level) {
  const value = String(level || "").toLowerCase();
  if (value === "high") return "high";
  if (value === "medium") return "medium";
  return "low";
}

function formatSeconds(total) {
  const seconds = Math.round(Number(total));
  if (!Number.isFinite(seconds) || seconds <= 0) return "-";
  const minutes = Math.floor(seconds / 60);
  return minutes > 0 ? `${minutes}m ${seconds % 60}s` : `${seconds}s`;
}


function Account() {
  const navigate = useNavigate();
  const location = useLocation();

  const { updateAnalysisData } = useContext(AnalysisContext);

  const [user, setUser] = useState(getSession());
  const [history, setHistory] = useState(() =>
    user ? getHistory(user.email) : []
  );
  const [editing, setEditing] = useState(false);
  const [nameDraft, setNameDraft] = useState(user?.name || "");
  const [confirmClear, setConfirmClear] = useState(false);

  // Bring in this account's saved history from the backend.
  useEffect(() => {
    if (!user) return undefined;
    let cancelled = false;
    syncHistory(user.email).then((merged) => {
      if (!cancelled) setHistory(merged);
    });
    return () => {
      cancelled = true;
    };
  }, [user?.email]);

  // Scroll to the history section when linked as /account#history
  useEffect(() => {
    if (location.hash === "#history") {
      document.getElementById("history")?.scrollIntoView({ behavior: "smooth" });
    }
  }, [location.hash]);

  const stats = useMemo(() => {
    const scored = history.filter((entry) => entry.claims > 0);
    const average = scored.length
      ? scored.reduce((sum, entry) => sum + entry.confidence, 0) / scored.length
      : null;

    return {
      total: history.length,
      average,
      last: history[0]?.timestamp || null
    };
  }, [history]);

  const displayName = user?.name || user?.email || "";
  const initial = displayName.trim().charAt(0).toUpperCase();
  const provider = user?.provider === "google" ? "Google" : "Email and password";

  const openReport = (entry) => {
    updateAnalysisData({ ...entry.analysis, status: "Analyzed" });
    navigate("/dashboard");
  };

  const runAgain = (entry) => {
    navigate("/loading", { state: { topic: entry.topic } });
  };

  const removeEntry = (id) => {
    deleteHistoryEntry(user.email, id);
    setHistory(getHistory(user.email));
  };

  const clearAll = () => {
    clearHistory(user.email);
    setHistory([]);
    setConfirmClear(false);
  };

  const saveName = () => {
    const updated = updateDisplayName(nameDraft);
    if (updated) setUser(updated);
    setEditing(false);
  };

  const logout = async () => {
    try {
      await signOut(auth);
    } catch {
      /* not signed in with Google: ignore */
    }
    clearSession();
    navigate("/", { replace: true });
  };

  if (!user) return null;

  return (
    <>
      <Navbar />

      <main className="rc-page">
        <div className="rc-container">

          {/* ---------- PROFILE ---------- */}
          <section className="rc-card ac-profile">
            {user.photoURL ? (
              <img
                className="ac-avatar"
                src={user.photoURL}
                alt=""
                referrerPolicy="no-referrer"
              />
            ) : (
              <div className="ac-avatar ac-avatar-initial">{initial}</div>
            )}

            <div className="ac-profile-text">
              {editing ? (
                <div className="ac-edit">
                  <input
                    className="ac-input"
                    value={nameDraft}
                    maxLength={60}
                    autoFocus
                    onChange={(event) => setNameDraft(event.target.value)}
                    onKeyDown={(event) => {
                      if (event.key === "Enter") saveName();
                    }}
                    aria-label="Display name"
                  />
                  <button type="button" className="rc-button rc-button-primary" onClick={saveName}>
                    Save
                  </button>
                  <button type="button" className="rc-button" onClick={() => setEditing(false)}>
                    Cancel
                  </button>
                </div>
              ) : (
                <h1>{displayName}</h1>
              )}

              <p className="rc-meta">{user.email}</p>
              <p className="rc-meta">Signed in with {provider}</p>
            </div>

            <div className="rc-header-actions">
              {user.provider !== "google" && !editing && (
                <button
                  type="button"
                  className="rc-button"
                  onClick={() => {
                    setNameDraft(user.name || "");
                    setEditing(true);
                  }}
                >
                  Edit name
                </button>
              )}
              <button type="button" className="rc-button" onClick={logout}>
                Log out
              </button>
            </div>
          </section>


          {/* ---------- STATS ---------- */}
          <section className="rc-stats" aria-label="Your activity">
            <div className="rc-card rc-stat">
              <strong>{stats.total}</strong>
              <span>Analyses run</span>
            </div>
            <div className="rc-card rc-stat">
              <strong>{stats.average === null ? "-" : stats.average.toFixed(1)}</strong>
              <span>Average confidence</span>
            </div>
            <div className="rc-card rc-stat">
              <strong>{stats.last ? timeAgo(stats.last) : "-"}</strong>
              <span>Last analysis</span>
            </div>
          </section>


          {/* ---------- HISTORY ---------- */}
          <section className="rc-card" id="history">
            <div className="ac-history-head">
              <div>
                <h2 className="rc-section-title">Search history</h2>
                <p className="rc-section-note">
                  Your past analyses, saved in this browser. Open one to see
                  its report again without waiting.
                </p>
              </div>

              {history.length > 0 &&
                (confirmClear ? (
                  <div className="rc-header-actions">
                    <button type="button" className="rc-button" onClick={clearAll}>
                      Yes, clear all
                    </button>
                    <button type="button" className="rc-button" onClick={() => setConfirmClear(false)}>
                      Keep
                    </button>
                  </div>
                ) : (
                  <button type="button" className="rc-button" onClick={() => setConfirmClear(true)}>
                    Clear history
                  </button>
                ))}
            </div>

            {history.length === 0 ? (
              <div className="rc-notice">
                No analyses yet. Run one and it will appear here.
                <div className="ac-empty-action">
                  <button
                    type="button"
                    className="rc-button rc-button-primary"
                    onClick={() => navigate("/analysis")}
                  >
                    Start an analysis
                  </button>
                </div>
              </div>
            ) : (
              <ul className="ac-history">
                {history.map((entry) => (
                  <li className="ac-item" key={entry.id}>
                    <div className="ac-item-main">
                      <button
                        type="button"
                        className="ac-item-title"
                        onClick={() => openReport(entry)}
                      >
                        {entry.topic}
                      </button>
                      <p className="rc-meta">
                        {new Date(entry.timestamp).toLocaleString()} ·{" "}
                        {entry.papers} {entry.papers === 1 ? "paper" : "papers"} ·{" "}
                        {entry.claims} {entry.claims === 1 ? "claim" : "claims"} ·{" "}
                        {formatSeconds(entry.seconds)}
                      </p>
                    </div>

                    <span
                      className={`rc-badge rc-badge-${
                        entry.claims > 0 ? levelTone(entry.confidenceLevel) : "none"
                      }`}
                    >
                      {entry.claims > 0
                        ? `${entry.confidence.toFixed(1)} / 10`
                        : "No results"}
                    </span>

                    <div className="ac-item-actions">
                      <button type="button" className="rc-button" onClick={() => openReport(entry)}>
                        Open
                      </button>
                      <button type="button" className="rc-button" onClick={() => runAgain(entry)}>
                        Run again
                      </button>
                      <button
                        type="button"
                        className="rc-button"
                        aria-label={`Delete ${entry.topic}`}
                        onClick={() => removeEntry(entry.id)}
                      >
                        Delete
                      </button>
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </section>

        </div>
      </main>

      <Footer />
    </>
  );
}

export default Account;
