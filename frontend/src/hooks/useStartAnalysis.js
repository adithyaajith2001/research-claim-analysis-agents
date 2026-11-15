import { useContext, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { AnalysisContext } from "../context/AnalysisContext";
import { getSession } from "../services/authService";
import { useAuthPrompt } from "../context/AuthPromptContext";

// Shared by the Home and Analysis pages: stores the question and opens the
// loading page, which runs the real analysis.
export default function useStartAnalysis() {
  const { setAnalysisData } = useContext(AnalysisContext);
  const navigate = useNavigate();
  const { openAuthPrompt } = useAuthPrompt();

  return useCallback(
    (topic) => {
      const trimmed = String(topic || "").trim();
      if (!trimmed) return false;

      // Visitors can type a question; a popup asks them to sign in, and the
      // question is waiting for them on the Analysis page afterwards.
      if (!getSession()) {
        openAuthPrompt(trimmed);
        return false;
      }

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
    [setAnalysisData, navigate, openAuthPrompt]
  );
}
