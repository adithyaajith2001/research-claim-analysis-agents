import { Fragment, useContext, useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";

import Navbar from "../components/layout/Navbar";
import Footer from "../components/layout/Footer";
import { AnalysisContext } from "../context/AnalysisContext";

import {
  SCORE_WEIGHTS,
  levelInfo,
  scoreTone,
  formatScore,
  formatSeconds,
  claimVerdict,
  claimSourceText,
  formatValue,
  sourceCount,
  shortAuthors,
  SINGLE_SOURCE_NOTE,
  isSubsetClaim,
  SUBSET_NOTE
} from "../utils/reportHelpers";
import { downloadReportPdf } from "../utils/reportPdf";
import { getSession } from "../services/authService";
import { getFullReport, getHistory, syncHistory } from "../services/historyService";

import "../styles/report.css";
import "../styles/reportView.css";


// ============================================================
// SMALL HELPERS
// ============================================================

function Badge({ tone, children }) {
  return <span className={`rc-badge rc-badge-${tone}`}>{children}</span>;
}


// ============================================================
// CONFIDENCE RING
// ============================================================

function CountUp({ value, duration = 700 }) {
  const target = Number(value) || 0;
  const [shown, setShown] = useState(0);

  useEffect(() => {
    const calm = window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;

    if (calm) {
      setShown(target);
      return undefined;
    }

    let frame;
    const start = performance.now();

    const tick = (now) => {
      const t = Math.min((now - start) / duration, 1);
      setShown(Math.round(target * (1 - Math.pow(1 - t, 3))));
      if (t < 1) frame = requestAnimationFrame(tick);
    };

    frame = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frame);
  }, [target, duration]);

  return <>{shown}</>;
}

function ConfidenceRing({ score, tone }) {
  const numeric = Math.min(Math.max(Number(score) || 0, 0), 10);
  const radius = 62;
  const circumference = 2 * Math.PI * radius;

  // Start empty and fill to the score, so the ring draws itself on arrival.
  const [shown, setShown] = useState(0);

  useEffect(() => {
    const id = requestAnimationFrame(() => setShown(numeric));
    return () => cancelAnimationFrame(id);
  }, [numeric]);

  const offset = circumference * (1 - shown / 10);

  return (
    <div className="rc-ring" role="img" aria-label={`Confidence ${formatScore(numeric)} out of 10`}>
      <svg viewBox="0 0 160 160" width="190" height="190">
        <circle
          cx="80"
          cy="80"
          r={radius}
          className="rc-ring-track"
        />
        <circle
          cx="80"
          cy="80"
          r={radius}
          className={`rc-ring-value rc-ring-${tone}`}
          strokeDasharray={circumference}
          strokeDashoffset={offset}
          transform="rotate(-90 80 80)"
        />
      </svg>

      <div className="rc-ring-label">
        <strong>{formatScore(numeric)}</strong>
        <span>out of 10</span>
      </div>
    </div>
  );
}


// ============================================================
// PAGE
// ============================================================

function Dashboard() {
  const navigate = useNavigate();

  const { analysisData, updateAnalysisData } = useContext(AnalysisContext);

  const [loadingLatest, setLoadingLatest] = useState(false);
  const [openClaim, setOpenClaim] = useState(null);
  const [openPaper, setOpenPaper] = useState(null);

  const topic = analysisData?.topic || "";
  const status = analysisData?.status || "";

  // Opened with nothing in memory (page reloaded, or opened from the menu
  // before running anything): show this account's latest saved report
  // instead of an empty page.
  const nothingLoaded = !topic || status === "Not Analyzed";

  useEffect(() => {
    if (!nothingLoaded) return undefined;

    const user = getSession();
    if (!user) return undefined;

    let cancelled = false;

    const open = async (list) => {
      const latest = (list || [])[0];
      if (!latest) return;
      const analysis = await getFullReport(user.email, latest);
      if (analysis && !cancelled) {
        updateAnalysisData({ ...analysis, status: "Analyzed" });
      }
    };

    const local = getHistory(user.email);

    if (local.length) {
      open(local);
      return () => {
        cancelled = true;
      };
    }

    setLoadingLatest(true);
    syncHistory(user.email)
      .then(open)
      .finally(() => {
        if (!cancelled) setLoadingLatest(false);
      });

    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [nothingLoaded]);

  const claims = Array.isArray(analysisData?.extractedClaims)
    ? analysisData.extractedClaims
    : [];

  const papers = Array.isArray(analysisData?.paperList)
    ? analysisData.paperList
    : [];

  // Which paper a compared claim came from, looked up by claim id.
  const paperOf = (claimId) =>
    claims.find((c) => String(c.claim_id) === String(claimId))?.paper_title || "";

  const comparisons = Array.isArray(analysisData?.contradictions)
    ? analysisData.contradictions
    : [];

  const queryModels = Array.isArray(analysisData?.queryModels)
    ? analysisData.queryModels
    : [];
  const skippedOther = Number(analysisData?.claimsSkippedOtherModels) || 0;
  const modelLabel = queryModels.join(", ");

  const skippedClaims = Array.isArray(analysisData?.skippedClaims)
    ? analysisData.skippedClaims
    : [];

  // Same model, different benchmark (e.g. MMLU-Pro when MMLU was asked).
  const closestMatches =
    claims.length === 0
      ? skippedClaims.filter((item) => item.same_model).slice(0, 6)
      : [];

  const score = Number(analysisData?.confidence) || 0;
  const level = analysisData?.confidenceLevel || "Low";
  const breakdown = analysisData?.confidenceBreakdown || {};
  const info =
    claims.length === 0
      ? {
          tone: "low",
          label: "No matching claims",
          headline: modelLabel
            ? `No results found for ${modelLabel}`
            : "No claims could be extracted",
          text: modelLabel
            ? `The papers found did not report a ${modelLabel} result we could verify, so no score can be trusted. Try a more specific question or a different model name.`
            : "No numeric benchmark claims were found in these papers, so no score can be trusted."
        }
      : levelInfo(level);

  const sortedClaims = useMemo(
    () =>
      [...claims].sort(
        (a, b) =>
          (Number(b.evidence_strength_score) || 0) -
          (Number(a.evidence_strength_score) || 0)
      ),
    [claims]
  );

  const verdictCounts = useMemo(() => {
    const counts = { high: 0, medium: 0, low: 0 };

    claims.forEach((claim) => {
      counts[claimVerdict(claim).tone] += 1;
    });

    return counts;
  }, [claims]);

  // ----------------------------------------------------------
  // Page state: tabs, filters, paper drawer
  // ----------------------------------------------------------

  const TAB_IDS = ["claims", "compare", "score", "leftout"];

  const [tab, setTab] = useState(() => {
    const fromHash = window.location.hash.replace("#", "");
    return TAB_IDS.includes(fromHash) ? fromHash : "claims";
  });
  const [verdictFilter, setVerdictFilter] = useState("all");
  const [paperFilter, setPaperFilter] = useState(null);
  const [drawerPaper, setDrawerPaper] = useState(null);

  const changeTab = (id) => {
    setTab(id);
    try {
      window.history.replaceState(window.history.state, "", `#${id}`);
    } catch {
      /* the address bar is only a convenience */
    }
  };

  // Which claims came from which paper.
  const claimsOfPaper = (paper) =>
    claims.filter(
      (claim) =>
        (claim.paper_id != null &&
          paper.id != null &&
          String(claim.paper_id) === String(paper.id)) ||
        (claim.paper_title && claim.paper_title === paper.title)
    );

  // Papers that gave a claim come first.
  const papersView = papers
    .map((paper, index) => ({
      paper,
      index,
      paperClaims: claimsOfPaper(paper)
    }))
    .sort(
      (a, b) =>
        Number(b.paperClaims.length > 0) - Number(a.paperClaims.length > 0) ||
        a.index - b.index
    );

  const inComparison = (paperClaims) =>
    paperClaims.some((claim) =>
      comparisons.some(
        (item) =>
          String(item.claim_a_id) === String(claim.claim_id) ||
          String(item.claim_b_id) === String(claim.claim_id)
      )
    );

  const visibleClaims = sortedClaims.filter((claim) => {
    if (verdictFilter !== "all" && claimVerdict(claim).tone !== verdictFilter) {
      return false;
    }
    if (paperFilter) {
      const owner = papers.find((p) => (p.id ?? null) === paperFilter.id && p.title === paperFilter.title);
      if (owner && !claimsOfPaper(owner).includes(claim)) return false;
    }
    return true;
  });

  // Close the drawer with Escape and stop the page behind it from scrolling.
  useEffect(() => {
    if (!drawerPaper) return undefined;

    const onKey = (event) => {
      if (event.key === "Escape") setDrawerPaper(null);
    };

    document.addEventListener("keydown", onKey);
    const previous = document.body.style.overflow;
    document.body.style.overflow = "hidden";

    return () => {
      document.removeEventListener("keydown", onKey);
      document.body.style.overflow = previous;
    };
  }, [drawerPaper]);

  const onTabKey = (event, visibleTabs) => {
    const keys = ["ArrowRight", "ArrowLeft"];
    if (!keys.includes(event.key)) return;
    const at = visibleTabs.findIndex((t) => t.id === tab);
    const next = event.key === "ArrowRight" ? at + 1 : at - 1;
    const target = visibleTabs[(next + visibleTabs.length) % visibleTabs.length];
    changeTab(target.id);
    requestAnimationFrame(() => document.getElementById(`tab-${target.id}`)?.focus());
  };

  const downloadReport = () => {
    downloadReportPdf(analysisData);
  };


  // ----------------------------------------------------------
  // No analysis / failed analysis
  // ----------------------------------------------------------

  const hasResult =
    topic && status !== "Analysis Failed" && status !== "Analyzing" && status !== "Not Analyzed";

  if (status === "Analyzing") {
    return (
      <>
        <Navbar />
        <main className="rc-page">
          <div className="rc-container">
            <section className="rc-card rc-empty">
              <h1>Your analysis is still running</h1>
              <p>
                “{topic}” is being checked. This page fills in by itself as
                soon as the report is ready, so you can leave it open.
              </p>
            </section>
          </div>
        </main>
        <Footer />
      </>
    );
  }

  if (!hasResult && loadingLatest) {
    return (
      <>
        <Navbar />
        <main className="rc-page">
          <div className="rc-container">
            <section className="rc-card rc-empty">
              <h1>Loading your latest report…</h1>
            </section>
          </div>
        </main>
        <Footer />
      </>
    );
  }

  if (!hasResult) {
    return (
      <>
        <Navbar />
        <main className="rc-page">
          <div className="rc-container">
            <section className="rc-card rc-empty">
              <h1>No analysis to show yet</h1>
              <p>
                Enter a research topic or a benchmark question and
                ResearchClaimAI will find papers, check their claims
                and give you a trust score.
              </p>
              <button
                type="button"
                className="rc-button rc-button-primary"
                onClick={() => navigate("/analysis")}
              >
                Start an analysis
              </button>
            </section>
          </div>
        </main>
        <Footer />
      </>
    );
  }


  // ----------------------------------------------------------
  // Report
  // ----------------------------------------------------------

  const tabs = [
    { id: "claims", label: "Claims", count: claims.length },
    { id: "compare", label: "Cross-paper comparisons", count: comparisons.length },
    ...(claims.length > 0 ? [{ id: "score", label: "How the score was built" }] : []),
    ...(skippedClaims.length > 0
      ? [{ id: "leftout", label: "Results left out", count: skippedClaims.length }]
      : [])
  ];
  const activeTab = tabs.some((t) => t.id === tab) ? tab : "claims";

  const verdictOptions = [
    { id: "all", label: "All", count: claims.length },
    { id: "high", label: "Found in paper", count: verdictCounts.high },
    { id: "medium", label: "Weak match", count: verdictCounts.medium },
    { id: "low", label: "Not found", count: verdictCounts.low }
  ];

  const openPaperFilter = (paper) => {
    setPaperFilter({ id: paper.id ?? null, title: paper.title });
    setVerdictFilter("all");
    setDrawerPaper(null);
    changeTab("claims");
    requestAnimationFrame(() =>
      document.getElementById("workspace")?.scrollIntoView({ behavior: "smooth", block: "start" })
    );
  };

  const drawerClaims = drawerPaper ? claimsOfPaper(drawerPaper) : [];

  return (
    <>
      <Navbar />

      <main className="rc-page db-page">
        <div className="db-wrap">

          {/* ---------- HEADER ---------- */}
          <header className="rc-header db-rise">
            <div>
              <p className="rc-eyebrow">Analysis report</p>
              <h1>{topic}</h1>
              <p className="rc-meta">
                {papers.length} {papers.length === 1 ? "paper" : "papers"} · {claims.length} {claims.length === 1 ? "claim" : "claims"} ·
                analysed in {formatSeconds(analysisData?.analysisSeconds)}
                {analysisData?.fromCache && " · saved report"}
              </p>
            </div>

            <div className="rc-header-actions">
              {!String(topic || "").startsWith("Uploaded paper:") && (
                <button
                  type="button"
                  className="rc-button"
                  onClick={() =>
                    navigate("/loading", {
                      state: { topic: analysisData?.topic, refresh: true }
                    })
                  }
                  title="Search the papers again instead of showing the saved report"
                >
                  Run again
                </button>
              )}
              <button
                type="button"
                className="rc-button"
                onClick={downloadReport}
              >
                Download PDF report
              </button>
              <button
                type="button"
                className="rc-button rc-button-primary"
                onClick={() => navigate("/analysis")}
              >
                New analysis
              </button>
            </div>
          </header>


          {/* ---------- SUMMARY ---------- */}
          <section className="db-hero">
            <div className="rc-card db-verdict db-rise" style={{ "--i": 1 }}>
              <div><Badge tone={info.tone}>{info.label}</Badge></div>
              <h2>{info.headline}</h2>
              <p>{info.text}</p>

              {claims.length > 0 &&
                comparisons.length === 0 &&
                sourceCount(claims) <= 1 && (
                  <p className="rc-single-source">{SINGLE_SOURCE_NOTE}</p>
                )}

              <div className="db-chips">
                <span className="db-chip">
                  <strong>{verdictCounts.high}</strong> found in the paper's text
                </span>
                <span className="db-chip">
                  <strong>{verdictCounts.medium}</strong> weak match
                </span>
                <span className="db-chip">
                  <strong>{verdictCounts.low}</strong> not found
                </span>
              </div>
            </div>

            <div className="rc-card db-gauge db-rise" style={{ "--i": 2 }}>
              {claims.length > 0 && (
                <ConfidenceRing score={score} tone={info.tone} />
              )}

              <div className="db-mini" aria-label="Key numbers">
                <div>
                  <strong><CountUp value={papers.length} /></strong>
                  <span>{papers.length === 1 ? "Paper" : "Papers"} analysed</span>
                </div>
                <div>
                  <strong><CountUp value={claims.length} /></strong>
                  <span>Claims extracted</span>
                </div>
                <div>
                  <strong><CountUp value={comparisons.length} /></strong>
                  <span>Cross-paper comparisons</span>
                </div>
                <div>
                  <strong>{formatSeconds(analysisData?.analysisSeconds)}</strong>
                  <span>Analysis time</span>
                </div>
              </div>
            </div>
          </section>


          {/* ---------- PAPERS (up front) ---------- */}
          <section id="papers" aria-labelledby="papers-title">
            <div className="db-section-head">
              <div>
                <h2 id="papers-title">Papers analysed</h2>
                <p>
                  The sources behind this report. Select a paper to read its
                  abstract and see the claims taken from it.
                </p>
              </div>
              {papers.length > 3 && (
                <span className="db-rail-hint">Scroll sideways for more →</span>
              )}
            </div>

            <div className="db-rail">
              {papersView.map(({ paper, index, paperClaims }, position) => {
                const count = paperClaims.length;
                const active =
                  paperFilter &&
                  paperFilter.title === paper.title &&
                  paperFilter.id === (paper.id ?? null);

                return (
                  <button
                    type="button"
                    key={paper.id ?? index}
                    className={
                      "db-paper db-rise" +
                      (count === 0 ? " is-muted" : "") +
                      (active ? " is-filter" : "")
                    }
                    style={{ "--i": position + 3 }}
                    onClick={() => setDrawerPaper(paper)}
                    aria-label={`Open details for ${paper.title}`}
                  >
                    <span className="db-paper-top">
                      <span className="db-src">{paper.source || "Paper"}</span>
                      <span>{paper.year || ""}</span>
                    </span>
                    <h3>{paper.title}</h3>
                    <p className="db-paper-authors">{shortAuthors(paper.authors)}</p>
                    <span className="db-paper-foot">
                      <span className={count > 0 ? "db-pill on" : "db-pill"}>
                        {count} {count === 1 ? "claim" : "claims"}
                      </span>
                      {inComparison(paperClaims) && (
                        <span className="db-pill link">in a comparison</span>
                      )}
                      <span className="db-open">Details ›</span>
                    </span>
                  </button>
                );
              })}
            </div>
          </section>


          {/* ---------- WORKSPACE (tabs) ---------- */}
          <section className="db-workspace" id="workspace">
            <div
              className="db-tabs"
              role="tablist"
              aria-label="Report sections"
              onKeyDown={(event) => onTabKey(event, tabs)}
            >
              {tabs.map((item) => (
                <button
                  key={item.id}
                  type="button"
                  role="tab"
                  id={`tab-${item.id}`}
                  aria-selected={activeTab === item.id}
                  aria-controls={`panel-${item.id}`}
                  tabIndex={activeTab === item.id ? 0 : -1}
                  className="db-tab"
                  onClick={() => changeTab(item.id)}
                >
                  {item.label}
                  {item.count !== undefined && <small>{item.count}</small>}
                </button>
              ))}
            </div>


            {/* ----- CLAIMS ----- */}
            {activeTab === "claims" && (
              <div
                className="db-panel"
                role="tabpanel"
                id="panel-claims"
                aria-labelledby="tab-claims"
                key="claims"
              >
                <h2 className="rc-section-title">Claims found</h2>
                <p className="rc-section-note">
                  Each result a paper reports, checked against the paper's own
                  text. Select a claim to see the reasoning and source text.
                </p>
                {claims.some(isSubsetClaim) && (
                  <p className="rc-notice rc-subset-note">{SUBSET_NOTE}</p>
                )}
                {skippedOther > 0 && (
                  <p className="rc-section-note">
                    Showing only results{modelLabel ? ` for ${modelLabel}` : ""} that match your question.{" "}
                    {skippedOther} claim{skippedOther === 1 ? "" : "s"} about other
                    models or benchmarks {skippedOther === 1 ? "was" : "were"} left out.
                  </p>
                )}

                {claims.length === 0 ? (
                  <>
                    <div className="rc-notice">
                      {modelLabel
                        ? `No claims about ${modelLabel} were found in the retrieved papers.`
                        : "No numeric benchmark claims could be extracted from these papers."}
                      {" "}Try a more specific question, for example
                      “MMLU accuracy of GPT-4”.
                    </div>

                    {closestMatches.length > 0 && (
                      <>
                        <h2 className="rc-section-title">Closest matches</h2>
                        <p className="rc-section-note">
                          No result for the exact benchmark you asked about was found,
                          but the papers report {modelLabel || "this model"} on other
                          benchmarks. These are shown for context only. They are
                          different tests, so they are not scored and should not be
                          read as your answer.
                        </p>
                        <ul className="db-skipped">
                          {closestMatches.map((item, index) => (
                            <li key={index}>
                              <strong>{item.model_name || "Unknown model"}</strong>
                              {" · "}
                              {item.benchmark || "Unknown benchmark"}
                              {" · "}
                              {item.reported_value}
                              <small>{item.paper_title}</small>
                            </li>
                          ))}
                        </ul>
                      </>
                    )}
                  </>
                ) : (
                  <>
                    <div className="db-filters" role="group" aria-label="Filter claims">
                      {verdictOptions.map((option) => (
                        <button
                          key={option.id}
                          type="button"
                          className="db-filter"
                          aria-pressed={verdictFilter === option.id}
                          onClick={() => setVerdictFilter(option.id)}
                        >
                          {option.label} ({option.count})
                        </button>
                      ))}
                      {paperFilter && (
                        <button
                          type="button"
                          className="db-filter db-filter-paper"
                          aria-pressed="true"
                          onClick={() => setPaperFilter(null)}
                          title="Show claims from every paper again"
                        >
                          Paper: {paperFilter.title.length > 36
                            ? `${paperFilter.title.slice(0, 36)}…`
                            : paperFilter.title} ✕
                        </button>
                      )}
                    </div>

                    {visibleClaims.length === 0 ? (
                      <div className="rc-notice">
                        No claims match these filters.
                      </div>
                    ) : (
                      <ul className="db-claims">
                        {visibleClaims.map((claim, index) => {
                          const id = claim.claim_id ?? index;
                          const isOpen = openClaim === id;
                          const verdict = claimVerdict(claim);
                          const source = claimSourceText(claim);
                          const owner = papers.find(
                            (p) =>
                              (claim.paper_id != null &&
                                p.id != null &&
                                String(claim.paper_id) === String(p.id)) ||
                              p.title === claim.paper_title
                          );

                          return (
                            <li
                              key={`claim-${id}`}
                              className={isOpen ? "db-claim is-open" : "db-claim"}
                            >
                              <button
                                type="button"
                                className="db-claim-main"
                                aria-expanded={isOpen}
                                onClick={() => setOpenClaim(isOpen ? null : id)}
                              >
                                <span>
                                  <span className="db-claim-text">{claim.claim}</span>
                                  <span className="rc-claim-tags">
                                    {claim.model_name && (
                                      <span className="rc-tag">{claim.model_name}</span>
                                    )}
                                    {isSubsetClaim(claim) && (
                                      <span className="rc-tag rc-tag-warn">Part of benchmark</span>
                                    )}
                                    {claim.benchmark && (
                                      <span className="rc-tag">{claim.benchmark}</span>
                                    )}
                                  </span>
                                </span>
                                <span className="db-claim-value">{formatValue(claim)}</span>
                                <span className="db-claim-badges">
                                  <Badge tone={scoreTone(claim.evidence_strength_score)}>
                                    {formatScore(claim.evidence_strength_score)} / 10
                                  </Badge>
                                  <Badge tone={verdict.tone}>{verdict.label}</Badge>
                                </span>
                                <span className="db-chev" aria-hidden="true">▾</span>
                              </button>

                              {isOpen && (
                                <div className="db-claim-detail">
                                  <p>
                                    <strong>Paper:</strong> {claim.paper_title}
                                  </p>

                                  {claim.evidence_strength_reasoning && (
                                    <p>
                                      <strong>Why this strength score:</strong>{" "}
                                      {claim.evidence_strength_reasoning}
                                    </p>
                                  )}

                                  {source && <blockquote>{source}</blockquote>}

                                  <p>
                                    Verification {formatScore(claim.verification_score)} / 10
                                    {" · "}
                                    Skeptic {formatScore(claim.skeptic_score)} / 10
                                  </p>

                                  {owner && (
                                    <button
                                      type="button"
                                      className="db-linkbtn"
                                      onClick={() => setDrawerPaper(owner)}
                                    >
                                      Read this paper's details ›
                                    </button>
                                  )}
                                </div>
                              )}
                            </li>
                          );
                        })}
                      </ul>
                    )}
                  </>
                )}
              </div>
            )}


            {/* ----- COMPARISONS ----- */}
            {activeTab === "compare" && (
              <div
                className="db-panel"
                role="tabpanel"
                id="panel-compare"
                aria-labelledby="tab-compare"
                key="compare"
              >
                <h2 className="rc-section-title">Cross-paper comparisons</h2>
                <p className="rc-section-note">
                  Results are only compared when two papers report the same
                  model on the same benchmark and setting.
                </p>

                {comparisons.length === 0 ? (
                  <div className="rc-notice">
                    No comparable results were found, so nothing could be
                    confirmed or contradicted across papers. This is not a
                    sign that the claims are consistent. Try a query that
                    covers more papers evaluating the same model.
                  </div>
                ) : (
                  <ul className="db-cmps">
                    {comparisons.map((item, index) => {
                      const agrees = item.relation_type === "Agrees";
                      const tone = agrees
                        ? "high"
                        : item.severity === "High"
                        ? "low"
                        : "medium";
                      const a = Number(item.reported_value_a);
                      const b = Number(item.reported_value_b);
                      const scale = Math.max(100, a || 0, b || 0);

                      return (
                        <li className="db-cmp db-rise" style={{ "--i": index }} key={index}>
                          <div className="db-cmp-head">
                            <div>
                              <span className="db-cmp-title">
                                {item.model_label || item.model_name || "Same model"}
                              </span>
                              <span className="rc-claim-tags">
                                <span className="rc-tag">{item.benchmark_name}</span>
                                {item.evaluation_setting && (
                                  <span className="rc-tag">{item.evaluation_setting}</span>
                                )}
                                {item.setting_note && (
                                  <span className="rc-tag" title={item.setting_note}>
                                    setting not stated in one paper
                                  </span>
                                )}
                              </span>
                            </div>
                            <Badge tone={tone}>
                              {agrees
                                ? "Agrees"
                                : `Contradicts${item.severity ? ` (${item.severity})` : ""}`}
                            </Badge>
                          </div>

                          <div className="db-cmp-rows">
                            {[
                              [paperOf(item.claim_a_id) || "Paper A", item.reported_value_a, a],
                              [paperOf(item.claim_b_id) || "Paper B", item.reported_value_b, b]
                            ].map(([name, shownValue, numeric], row) => (
                              <div className="db-cmp-row" key={row}>
                                <span className="db-cmp-name">{name}</span>
                                <strong>{shownValue}</strong>
                                <div className="db-track">
                                  <span style={{ width: `${Math.min((numeric / scale) * 100, 100)}%` }} />
                                </div>
                              </div>
                            ))}
                          </div>

                          <p className="db-cmp-note">
                            Gap: <span className="db-gap">{item.value_diff}</span> points.{" "}
                            {agrees
                              ? "Within 3 points counts as agreeing."
                              : "More than 3 points apart counts as contradicting."}
                          </p>
                        </li>
                      );
                    })}
                  </ul>
                )}
              </div>
            )}


            {/* ----- SCORE ----- */}
            {activeTab === "score" && claims.length > 0 && (
              <div
                className="db-panel"
                role="tabpanel"
                id="panel-score"
                aria-labelledby="tab-score"
                key="score"
              >
                <h2 className="rc-section-title">How the score was built</h2>
                <p className="rc-section-note">
                  Four checks are combined into the overall score. Stronger
                  signals count for more.
                </p>

                <div className="db-formula" aria-label="Score formula">
                  {SCORE_WEIGHTS.map((item, i) => (
                    <span key={item.key}>
                      {i > 0 && "+ "}
                      {item.weight}% × <b>{formatScore(Number(breakdown[item.key]))}</b>
                    </span>
                  ))}
                  <span className="db-eq">= <b>{formatScore(score)}</b> / 10</span>
                </div>

                <div className="rc-card">
                  <div className="rc-bars">
                    {SCORE_WEIGHTS.map((item) => {
                      const value = Number(breakdown[item.key]);
                      const barTone = scoreTone(value);
                      const width = Number.isFinite(value)
                        ? Math.min(Math.max(value, 0), 10) * 10
                        : 0;

                      return (
                        <div className="rc-bar-row" key={item.key}>
                          <div className="rc-bar-head">
                            <span className="rc-bar-label">
                              {item.label}
                              <small>counts for {item.weight}%</small>
                            </span>
                            <strong>{formatScore(value)} / 10</strong>
                          </div>

                          <div className="rc-bar-track">
                            <div
                              className={`rc-bar-fill rc-fill-${barTone}`}
                              style={{ width: `${width}%` }}
                            />
                          </div>

                          <p className="rc-bar-help">
                            {item.key === "Contradiction" && comparisons.length === 0
                              ? "No other paper reported a comparable result, so this check is neutral (5/10)."
                              : item.help}
                          </p>
                        </div>
                      );
                    })}
                  </div>
                </div>
              </div>
            )}


            {/* ----- LEFT OUT ----- */}
            {activeTab === "leftout" && skippedClaims.length > 0 && (
              <div
                className="db-panel"
                role="tabpanel"
                id="panel-leftout"
                aria-labelledby="tab-leftout"
                key="leftout"
              >
                <h2 className="rc-section-title">Results left out ({skippedClaims.length})</h2>
                <p className="rc-section-note">
                  These were found in the papers but are about other models
                  or other benchmarks than your question, so they are not
                  scored.
                </p>
                <ul className="db-skipped">
                  {skippedClaims.map((item, index) => (
                    <li key={index}>
                      <strong>{item.model_name || "Unknown model"}</strong>
                      {" · "}
                      {item.benchmark || "Unknown benchmark"}
                      {" · "}
                      {item.reported_value}
                      <small>{item.paper_title}</small>
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </section>

        </div>
      </main>


      {/* ---------- PAPER DRAWER ---------- */}
      {drawerPaper && (
        <>
          <div className="db-overlay" onClick={() => setDrawerPaper(null)} />
          <aside
            className="db-drawer"
            role="dialog"
            aria-modal="true"
            aria-label={`Details for ${drawerPaper.title}`}
          >
            <div className="db-drawer-head">
              <div>
                <span className="db-src">{drawerPaper.source || "Paper"}</span>
                <h2>{drawerPaper.title}</h2>
                <p>
                  {[shortAuthors(drawerPaper.authors, 6), drawerPaper.year]
                    .filter(Boolean)
                    .join(" · ")}
                </p>
              </div>
              <button
                type="button"
                className="db-close"
                aria-label="Close paper details"
                onClick={() => setDrawerPaper(null)}
                autoFocus
              >
                ✕
              </button>
            </div>

            <div className="db-drawer-body">
              <div className="db-drawer-actions">
                {(drawerPaper.url || drawerPaper.pdf_url) && (
                  <a
                    className="rc-button rc-button-primary"
                    href={drawerPaper.url || drawerPaper.pdf_url}
                    target="_blank"
                    rel="noreferrer"
                  >
                    Open the paper ↗
                  </a>
                )}
                {drawerClaims.length > 0 && (
                  <button
                    type="button"
                    className="rc-button"
                    onClick={() => openPaperFilter(drawerPaper)}
                  >
                    Show only its claims
                  </button>
                )}
              </div>

              <div>
                <h3>Abstract</h3>
                <p className="db-abstract">
                  {drawerPaper.abstract || "No abstract was available for this paper."}
                </p>
              </div>

              <div>
                <h3>Claims taken from this paper ({drawerClaims.length})</h3>
                {drawerClaims.length === 0 ? (
                  <p className="rc-section-note" style={{ margin: 0 }}>
                    No result matching your question was found in this paper.
                  </p>
                ) : (
                  <ul className="db-drawer-claims">
                    {drawerClaims.map((claim, index) => {
                      const verdict = claimVerdict(claim);
                      return (
                        <li key={claim.claim_id ?? index}>
                          <span>{claim.claim}</span>
                          <span className="rc-claim-tags">
                            <strong>{formatValue(claim)}</strong>
                            <Badge tone={verdict.tone}>{verdict.label}</Badge>
                            <Badge tone={scoreTone(claim.evidence_strength_score)}>
                              {formatScore(claim.evidence_strength_score)} / 10
                            </Badge>
                          </span>
                        </li>
                      );
                    })}
                  </ul>
                )}
              </div>
            </div>
          </aside>
        </>
      )}

      <Footer />
    </>
  );
}

export default Dashboard;
