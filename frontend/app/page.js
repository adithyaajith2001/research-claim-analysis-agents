"use client";

import { useEffect, useState } from "react";
import DashboardLayout, { PendingSlot } from "../components/DashboardLayout";
import QueryInput from "../components/QueryInput";
import ResultsSummary from "../components/ResultsSummary";
import { getDashboardSummary } from "../lib/api";

export default function Page() {
  const [summary, setSummary] = useState(null);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  const [isAnalyzing, setIsAnalyzing] = useState(false);

  async function refreshSummary() {
    try {
      const { summary } = await getDashboardSummary();
      setSummary(summary);
    } catch {
      // Backend may not be running yet - the query form will surface
      // that error more usefully once the user tries to analyze.
    }
  }

  useEffect(() => {
    refreshSummary();
  }, []);

  return (
    <DashboardLayout summary={summary}>
      <QueryInput
        onStart={() => {
          setIsAnalyzing(true);
          setError(null);
          setResult(null);
        }}
        onResult={(r) => {
          setIsAnalyzing(false);
          setResult(r);
          refreshSummary();
        }}
        onError={(message) => {
          setIsAnalyzing(false);
          setError(message);
        }}
      />

      {error && <p className="error-message">{error}</p>}

      {isAnalyzing && !result && (
        <p className="loading-message">
          Running the pipeline — retrieval, extraction, verification,
          skeptic review, and contradiction detection. This can take a
          minute or two.
        </p>
      )}

      <ResultsSummary result={result} />

      <PendingSlot
        title="Contradiction analysis"
        owner="Malavika Krishna"
        description="Charts and tables comparing claims across papers - agreements, contradictions, and severity."
      />

      <PendingSlot
        title="Citation network & evidence cards"
        owner="Sheethal Krishna K K"
        description="D3.js citation graph across retrieved papers, plus detailed evidence cards per claim."
      />

      <style jsx>{`
        .error-message {
          color: var(--clay);
          background: var(--clay-soft);
          border-radius: 4px;
          padding: 0.75rem 1rem;
          font-size: 0.9rem;
        }

        .loading-message {
          color: var(--slate);
          font-size: 0.9rem;
        }
      `}</style>
    </DashboardLayout>
  );
}
