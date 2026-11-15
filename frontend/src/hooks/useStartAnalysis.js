import { useContext, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { AnalysisContext } from "../context/AnalysisContext";

// Shared by the Home and Analysis pages: stores the question and opens the
// loading page, which runs the real analysis.
export default function useStartAnalysis() {
  const { setAnalysisData } = useContext(AnalysisContext);
  const navigate = useNavigate();

  return useCallback(
    (topic) => {
      const trimmed = String(topic || "").trim();
      if (!trimmed) return false;

      setAnalysisData((previous) => ({
        ...previous,
        topic: trimmed,
        confidence: 0,
        papers: 0,
        papers_retrieved: 0,
        claims: 0,
        paperList: [],
        summary: "",
        status: "Analyzing",
        supportingPapers: [],
        contradictingPapers: [],
        isAnalyzing: true
      }));

      navigate("/loading", { state: { topic: trimmed } });
      return true;
    },
    [setAnalysisData, navigate]
  );
}
