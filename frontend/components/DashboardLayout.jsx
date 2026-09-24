/**
 * components/DashboardLayout.jsx
 *
 * OWNER: Adithya Ajith - Frontend: Dashboard Layout.
 *
 * The page shell: wordmark/nav, a stats strip fed by
 * GET /api/dashboard-summary, and a content grid with clearly labelled
 * slots for the teammates' visualization components:
 *
 *   - <slot: contradiction analysis>   -> Malavika (charts/tables)
 *   - <slot: citation network + cards> -> Sheethal (D3.js + evidence cards)
 *
 * Until those land, each slot renders whatever `children` it's given, or
 * a placeholder panel so the layout is demonstrably complete on its own.
 */

const STAT_LABELS = {
  papers: "Papers analyzed",
  claims: "Claims extracted",
  evidence: "Evidence items",
  contradictions: "Contradictions found",
  average_confidence: "Avg. evidence strength",
};

function StatCard({ label, value }) {
  return (
    <div className="stat-card">
      <span className="stat-value">{value}</span>
      <span className="stat-label">{label}</span>
    </div>
  );
}

export default function DashboardLayout({ summary, children }) {
  const stats = summary
    ? Object.entries(STAT_LABELS).map(([key, label]) => ({
        key,
        label,
        value: summary[key] ?? "—",
      }))
    : [];

  return (
    <div className="shell">
      <header className="topbar">
        <div className="wordmark">
          <span className="wordmark-mark">RC</span>
          <div>
            <h1>ResearchClaimAI</h1>
            <p className="tagline">
              Multi-agent verification for research claims
            </p>
          </div>
        </div>
      </header>

      {stats.length > 0 && (
        <section className="stats-strip" aria-label="Dashboard summary">
          {stats.map((s) => (
            <StatCard key={s.key} label={s.label} value={s.value} />
          ))}
        </section>
      )}

      <main className="content">{children}</main>

      <footer className="footer">
        <p>
          ResearchClaimAI — an intelligent multi-agent framework for
          autonomous analysis and verification of research claims across
          multiple papers.
        </p>
        <p className="footer-meta">
          CHRIST (Deemed to be University) · Dept. of Computer Science ·
          Master of Data Science mini-project
        </p>
      </footer>

      <style jsx>{`
        .shell {
          min-height: 100vh;
          display: flex;
          flex-direction: column;
        }

        .topbar {
          border-bottom: 1px solid var(--rule);
          background: var(--paper-raised);
          padding: 1.5rem clamp(1.25rem, 4vw, 3rem);
        }

        .wordmark {
          display: flex;
          align-items: center;
          gap: 0.9rem;
          max-width: 72rem;
          margin: 0 auto;
        }

        .wordmark-mark {
          font-family: var(--font-serif);
          font-weight: 700;
          font-size: 1.1rem;
          color: var(--paper-raised);
          background: var(--ink);
          width: 2.5rem;
          height: 2.5rem;
          border-radius: 6px;
          display: flex;
          align-items: center;
          justify-content: center;
          flex-shrink: 0;
        }

        h1 {
          font-size: 1.35rem;
        }

        .tagline {
          margin: 0.15rem 0 0;
          color: var(--slate);
          font-size: 0.9rem;
        }

        .stats-strip {
          max-width: 72rem;
          width: 100%;
          margin: 0 auto;
          padding: 1.5rem clamp(1.25rem, 4vw, 3rem) 0;
          display: grid;
          grid-template-columns: repeat(auto-fit, minmax(11rem, 1fr));
          gap: 1px;
          background: var(--rule);
          border: 1px solid var(--rule);
        }

        :global(.stat-card) {
          background: var(--paper-raised);
          padding: 1.1rem 1.25rem;
          display: flex;
          flex-direction: column;
          gap: 0.25rem;
        }

        :global(.stat-value) {
          font-family: var(--font-serif);
          font-size: 1.6rem;
          font-weight: 600;
          color: var(--ink);
        }

        :global(.stat-label) {
          font-size: 0.82rem;
          color: var(--slate);
        }

        .content {
          flex: 1;
          max-width: 72rem;
          width: 100%;
          margin: 0 auto;
          padding: 2rem clamp(1.25rem, 4vw, 3rem) 3rem;
          display: flex;
          flex-direction: column;
          gap: 2rem;
        }

        .footer {
          border-top: 1px solid var(--rule);
          padding: 1.5rem clamp(1.25rem, 4vw, 3rem);
          color: var(--slate);
          font-size: 0.85rem;
        }

        .footer p {
          max-width: 72rem;
          margin: 0 auto 0.35rem;
        }

        .footer-meta {
          opacity: 0.75;
        }

        @media (max-width: 640px) {
          .wordmark {
            gap: 0.6rem;
          }
        }
      `}</style>
    </div>
  );
}

/**
 * Placeholder panel for a slot a teammate's component will eventually
 * fill. Renders a clearly-labelled empty state instead of nothing, so
 * the dashboard reads as complete-but-pending rather than broken.
 */
export function PendingSlot({ title, owner, description }) {
  return (
    <section className="pending-slot" aria-label={title}>
      <h2>{title}</h2>
      <p className="owner">Owner: {owner}</p>
      <p className="description">{description}</p>

      <style jsx>{`
        .pending-slot {
          border: 1px dashed var(--rule);
          border-radius: 4px;
          padding: 1.75rem;
          background: var(--paper-raised);
        }

        h2 {
          font-size: 1.1rem;
          margin-bottom: 0.35rem;
        }

        .owner {
          font-size: 0.8rem;
          color: var(--amber);
          font-weight: 600;
          margin: 0 0 0.5rem;
        }

        .description {
          color: var(--slate);
          font-size: 0.92rem;
          margin: 0;
          max-width: 42rem;
        }
      `}</style>
    </section>
  );
}
