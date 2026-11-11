import { Fragment, useContext, useMemo, useState } from "react";
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
  formatValue
} from "../utils/reportHelpers";
import { downloadReportPdf } from "../utils/reportPdf";

import "../styles/report.css";


// ============================================================
// SMALL HELPERS
// ============================================================

function Badge({ tone, children }) {
  return <span className={`rc-badge rc-badge-${tone}`}>{children}</span>;
}


// ============================================================
// CONFIDENCE RING
// ============================================================

function ConfidenceRing({ score, tone }) {
  const numeric = Math.min(Math.max(Number(score) || 0, 0), 10);
  const radius = 62;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference * (1 - numeric / 10);

  return (
    <div className="rc-ring" role="img" aria-label={`Confidence ${numeric.toFixed(1)} out of 10`}>
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
        <strong>{numeric.toFixed(1)}</strong>
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

  const { analysisData } = useContext(AnalysisContext);

  const [openClaim, setOpenClaim] = useState(null);
  const [openPaper, setOpenPaper] = useState(null);

  const topic = analysisData?.topic || "";
  const status = analysisData?.status || "";

  const claims = Array.isArray(analysisData?.extractedClaims)
    ? analysisData.extractedClaims
    : [];

  const papers = Array.isArray(analysisData?.paperList)
    ? analysisData.paperList
    : [];

  const comparisons = Array.isArray(analysisData?.contradictions)
    ? analysisData.contradictions
    : [];

  const queryModels = Array.isArray(analysisData?.queryModels)
    ? analysisData.queryModels
    : [];
  const skippedOther = Number(analysisData?.claimsSkippedOtherModels) || 0;
  const modelLabel = queryModels.join(", ");

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

  const downloadReport = () => {
    downloadReportPdf(analysisData);
  };


  // ----------------------------------------------------------
  // No analysis / failed analysis
  // ----------------------------------------------------------

  const hasResult =
    topic && status !== "Analysis Failed" && status !== "Analyzing" && status !== "Not Analyzed";

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

  return (
    <>
      <Navbar />

      <main className="rc-page">
        <div className="rc-container">

          {/* ---------- HEADER ---------- */}
          <header className="rc-header">
            <div>
              <p className="rc-eyebrow">Analysis report</p>
              <h1>{topic}</h1>
              <p className="rc-meta">
                {papers.length} {papers.length === 1 ? "paper" : "papers"} · {claims.length} {claims.length === 1 ? "claim" : "claims"} ·
                analysed in {formatSeconds(analysisData?.analysisSeconds)}
              </p>
            </div>

            <div className="rc-header-actions">
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
          <section className="rc-card rc-summary">
            <div className="rc-summary-text">
              <Badge tone={info.tone}>{info.label}</Badge>
              <h2>{info.headline}</h2>
              <p>{info.text}</p>

              <ul className="rc-summary-facts">
                <li>
                  <strong>{verdictCounts.high}</strong> found in the paper's text
                </li>
                <li>
                  <strong>{verdictCounts.medium}</strong> weak match
                </li>
                <li>
                  <strong>{verdictCounts.low}</strong> not found
                </li>
              </ul>
            </div>

            {claims.length > 0 && (
              <ConfidenceRing score={score} tone={info.tone} />
            )}
          </section>


          {/* ---------- STAT TILES ---------- */}
          <section className="rc-stats" aria-label="Key numbers">
            <div className="rc-card rc-stat">
              <strong>{papers.length}</strong>
              <span>{papers.length === 1 ? "Paper" : "Papers"} analysed</span>
            </div>
            <div className="rc-card rc-stat">
              <strong>{claims.length}</strong>
              <span>Claims extracted</span>
            </div>
            <div className="rc-card rc-stat">
              <strong>{comparisons.length}</strong>
              <span>Cross-paper comparisons</span>
            </div>
            <div className="rc-card rc-stat">
              <strong>{formatSeconds(analysisData?.analysisSeconds)}</strong>
              <span>Analysis time</span>
            </div>
          </section>


          {/* ---------- SCORE BREAKDOWN ---------- */}
          {claims.length > 0 && (
          <section className="rc-card">
            <h2 className="rc-section-title">How the score was built</h2>
            <p className="rc-section-note">
              Four checks are combined into the overall score. Stronger
              signals count for more.
            </p>

            <div className="rc-bars">
              {SCORE_WEIGHTS.map((item) => {
                const value = Number(breakdown[item.key]);
                const tone = scoreTone(value);
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
                        className={`rc-bar-fill rc-fill-${tone}`}
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
          </section>
          )}


          {/* ---------- CLAIMS ---------- */}
          <section className="rc-card">
            <h2 className="rc-section-title">Claims found</h2>
            <p className="rc-section-note">
              Each result a paper reports, checked against the paper's own
              text. Select a row to see the reasoning and source text.
            </p>
            {modelLabel && skippedOther > 0 && (
              <p className="rc-section-note">
                Showing only claims about {modelLabel}.{" "}
                {skippedOther} claim{skippedOther === 1 ? "" : "s"} about other
                models {skippedOther === 1 ? "was" : "were"} left out.
              </p>
            )}

            {claims.length === 0 ? (
              <div className="rc-notice">
                {modelLabel
                  ? `No claims about ${modelLabel} were found in the retrieved papers.`
                  : "No numeric benchmark claims could be extracted from these papers."}
                {" "}Try a more specific question, for example
                “MMLU accuracy of GPT-4”.
              </div>
            ) : (
              <div className="rc-table-wrap">
                <table className="rc-table">
                  <thead>
                    <tr>
                      <th>Claim</th>
                      <th>Result</th>
                      <th>Evidence strength</th>
                      <th>Verdict</th>
                    </tr>
                  </thead>

                  <tbody>
                    {sortedClaims.map((claim, index) => {
                      const id = claim.claim_id ?? index;
                      const isOpen = openClaim === id;
                      const verdict = claimVerdict(claim);
                      const source = claimSourceText(claim);

                      return (
                        <Fragment key={`claim-${id}`}>
                          <tr
                            className={isOpen ? "rc-row rc-row-open" : "rc-row"}
                          >
                            <td>
                              <button
                                type="button"
                                className="rc-row-button"
                                aria-expanded={isOpen}
                                onClick={() => setOpenClaim(isOpen ? null : id)}
                              >
                                <span className="rc-claim-text">{claim.claim}</span>
                                <span className="rc-claim-tags">
                                  {claim.model_name && (
                                    <span className="rc-tag">{claim.model_name}</span>
                                  )}
                                  {claim.benchmark && (
                                    <span className="rc-tag">{claim.benchmark}</span>
                                  )}
                                </span>
                              </button>
                            </td>
                            <td className="rc-num">{formatValue(claim)}</td>
                            <td>
                              <Badge tone={scoreTone(claim.evidence_strength_score)}>
                                {formatScore(claim.evidence_strength_score)} / 10
                              </Badge>
                            </td>
                            <td>
                              <Badge tone={verdict.tone}>{verdict.label}</Badge>
                            </td>
                          </tr>

                          {isOpen && (
                            <tr className="rc-detail-row">
                              <td colSpan={4}>
                                <div className="rc-detail">
                                  <p>
                                    <strong>Paper:</strong> {claim.paper_title}
                                  </p>

                                  {claim.evidence_strength_reasoning && (
                                    <p>
                                      <strong>Why this strength score:</strong>{" "}
                                      {claim.evidence_strength_reasoning}
                                    </p>
                                  )}

                                  {source && (
                                    <blockquote>{source}</blockquote>
                                  )}

                                  <p className="rc-detail-scores">
                                    Verification {formatScore(claim.verification_score)} / 10
                                    {" · "}
                                    Skeptic {formatScore(claim.skeptic_score)} / 10
                                  </p>
                                </div>
                              </td>
                            </tr>
                          )}
                        </Fragment>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}
          </section>


          {/* ---------- COMPARISONS ---------- */}
          <section className="rc-card">
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
              <div className="rc-table-wrap">
                <table className="rc-table">
                  <thead>
                    <tr>
                      <th>Model and benchmark</th>
                      <th>Paper A</th>
                      <th>Paper B</th>
                      <th>Gap</th>
                      <th>Verdict</th>
                    </tr>
                  </thead>

                  <tbody>
                    {comparisons.map((item, index) => {
                      const agrees = item.relation_type === "Agrees";
                      const tone = agrees
                        ? "high"
                        : item.severity === "High"
                        ? "low"
                        : "medium";

                      return (
                        <tr key={index}>
                          <td>
                            <span className="rc-claim-text">
                              {item.model_name || "Same model"}
                            </span>
                            <span className="rc-claim-tags">
                              <span className="rc-tag">{item.benchmark_name}</span>
                              {item.evaluation_setting && (
                                <span className="rc-tag">{item.evaluation_setting}</span>
                              )}
                            </span>
                          </td>
                          <td className="rc-num">{item.reported_value_a}</td>
                          <td className="rc-num">{item.reported_value_b}</td>
                          <td className="rc-num">{item.value_diff}</td>
                          <td>
                            <Badge tone={tone}>
                              {agrees
                                ? "Agrees"
                                : `Contradicts${item.severity ? ` (${item.severity})` : ""}`}
                            </Badge>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}
          </section>


          {/* ---------- SOURCES ---------- */}
          <section className="rc-card">
            <h2 className="rc-section-title">Papers analysed</h2>
            <p className="rc-section-note">
              The sources behind this report.
            </p>

            <ul className="rc-papers">
              {papers.map((paper, index) => {
                const id = paper.id ?? index;
                const isOpen = openPaper === id;
                const abstract = paper.abstract || "";
                const link = paper.url || paper.pdf_url;

                return (
                  <li className="rc-paper" key={id}>
                    <h3>
                      {link ? (
                        <a href={link} target="_blank" rel="noreferrer">
                          {paper.title}
                        </a>
                      ) : (
                        paper.title
                      )}
                    </h3>

                    <p className="rc-paper-meta">
                      {[paper.authors, paper.year, paper.source]
                        .filter(Boolean)
                        .join(" · ")}
                    </p>

                    {abstract && (
                      <>
                        <p className={isOpen ? "rc-abstract" : "rc-abstract rc-clamp"}>
                          {abstract}
                        </p>
                        <button
                          type="button"
                          className="rc-link-button"
                          onClick={() => setOpenPaper(isOpen ? null : id)}
                        >
                          {isOpen ? "Show less" : "Read more"}
                        </button>
                      </>
                    )}
                  </li>
                );
              })}
            </ul>
          </section>

        </div>
      </main>

      <Footer />
    </>
  );
}

export default Dashboard;
