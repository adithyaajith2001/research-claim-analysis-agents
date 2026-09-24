/**
 * components/ResultsSummary.jsx
 *
 * Minimal rendering of a POST /api/analyze response: the overall
 * confidence score and a plain list of extracted claims. This exists so
 * the dashboard is demonstrably working end-to-end without waiting on
 * Malavika's contradiction charts or Sheethal's citation network -
 * those replace/extend this, they don't block it.
 */

const LEVEL_CLASS = {
  High: "level-high",
  Medium: "level-medium",
  Low: "level-low",
};

export default function ResultsSummary({ result }) {
  if (!result) return null;

  const { confidence, claims, papers_retrieved, query } = result;

  return (
    <section className="results" aria-label="Analysis results">
      <div className="results-header">
        <h2>Results for “{query}”</h2>
        <span className={`level-badge ${LEVEL_CLASS[confidence?.confidence_level] || ""}`}>
          {confidence?.confidence_level ?? "—"} confidence · {confidence?.overall_score ?? "—"}/10
        </span>
      </div>

      <p className="summary-line">
        {papers_retrieved} paper{papers_retrieved === 1 ? "" : "s"} analyzed,{" "}
        {claims?.length ?? 0} claim{claims?.length === 1 ? "" : "s"} extracted.
      </p>

      <ul className="claim-list">
        {(claims || []).map((c) => (
          <li key={c.claim_id} className="claim-item">
            <p className="claim-text">{c.claim}</p>
            <div className="claim-meta">
              <span>{c.paper_title}</span>
              {c.benchmark && <span>· {c.benchmark}</span>}
              <span>· evidence strength {c.evidence_strength_score ?? "—"}/10</span>
            </div>
          </li>
        ))}
      </ul>

      <style jsx>{`
        .results {
          background: var(--paper-raised);
          border: 1px solid var(--rule);
          border-radius: 4px;
          padding: 1.75rem;
        }

        .results-header {
          display: flex;
          align-items: baseline;
          justify-content: space-between;
          gap: 1rem;
          flex-wrap: wrap;
          margin-bottom: 0.4rem;
        }

        h2 {
          font-size: 1.2rem;
        }

        .level-badge {
          font-size: 0.85rem;
          font-weight: 600;
          padding: 0.25rem 0.65rem;
          border-radius: 999px;
          white-space: nowrap;
        }

        .level-high {
          background: var(--sage-soft);
          color: var(--sage);
        }

        .level-medium {
          background: var(--amber-soft);
          color: var(--amber);
        }

        .level-low {
          background: var(--clay-soft);
          color: var(--clay);
        }

        .summary-line {
          color: var(--slate);
          font-size: 0.9rem;
          margin: 0 0 1.25rem;
        }

        .claim-list {
          list-style: none;
          margin: 0;
          padding: 0;
          display: flex;
          flex-direction: column;
          gap: 0.9rem;
        }

        .claim-item {
          border-top: 1px solid var(--rule);
          padding-top: 0.9rem;
        }

        .claim-text {
          font-family: var(--font-serif);
          margin: 0 0 0.3rem;
          color: var(--charcoal);
        }

        .claim-meta {
          font-size: 0.8rem;
          color: var(--slate);
          display: flex;
          gap: 0.4rem;
          flex-wrap: wrap;
        }
      `}</style>
    </section>
  );
}
