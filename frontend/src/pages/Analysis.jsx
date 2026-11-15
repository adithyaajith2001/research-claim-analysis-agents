import { useState } from "react";
import { useLocation } from "react-router-dom";
import { FaSearch, FaLightbulb, FaFlask, FaCheckCircle } from "react-icons/fa";

import Navbar from "../components/layout/Navbar";
import Footer from "../components/layout/Footer";
import useStartAnalysis from "../hooks/useStartAnalysis";

import "../styles/analysis.css";

const EXAMPLES = [
  "MMLU accuracy of Mistral 7B",
  "GSM8K accuracy of Mistral 7B",
  "HumanEval score of Llama 2 7B",
  "MMLU accuracy of Llama 2 13B",
  "MMLU accuracy of GPT-4"
];

const TIPS = [
  "Name one model and one benchmark for the most precise answer.",
  "Broad topics work too, but you may get fewer verified numbers.",
  "A typical analysis takes about a minute. You can keep this tab open."
];

const MAX_LENGTH = 200;

const Analysis = () => {
  const location = useLocation();
  const [topic, setTopic] = useState(location.state?.topic || "");
  const [error, setError] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const startAnalysis = useStartAnalysis();

  const handleAnalyze = () => {
    if (!topic.trim()) {
      setError("Please enter a question first, for example “MMLU accuracy of Mistral 7B”.");
      return;
    }
    setError("");
    setIsSubmitting(true);
    startAnalysis(topic);
  };

  const handleKeyDown = (event) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      handleAnalyze();
    }
  };

  return (
    <>
      <Navbar />

      <main className="analysis-page">
        <section className="analysis-hero">
          <div className="analysis-hero-content">
            <div className="analysis-badge">
              <FaFlask />
              AI-POWERED RESEARCH ANALYSIS
            </div>

            <h1>
              Ask about a
              <br />
              <span>research claim</span>
            </h1>

            <p>
              Tell us which model and benchmark you want checked. We find the
              papers, read their tables and show how far the number can be
              trusted.
            </p>

            <ul className="analysis-tips">
              {TIPS.map((tip) => (
                <li key={tip}>
                  <FaCheckCircle />
                  {tip}
                </li>
              ))}
            </ul>
          </div>
        </section>

        <section className="analysis-input-section">
          <div className="analysis-card">
            <div className="analysis-card-header">
              <div className="analysis-icon">
                <FaLightbulb />
              </div>
              <div>
                <h2>What do you want to verify?</h2>
                <p>One question is enough. Press Enter to start.</p>
              </div>
            </div>

            <label htmlFor="claim-input" className="analysis-sr">
              Research question
            </label>
            <textarea
              id="claim-input"
              rows="4"
              maxLength={MAX_LENGTH}
              placeholder="e.g. MMLU accuracy of Mistral 7B"
              value={topic}
              onChange={(e) => {
                setTopic(e.target.value);
                if (error) setError("");
              }}
              onKeyDown={handleKeyDown}
              disabled={isSubmitting}
              aria-invalid={Boolean(error)}
              autoFocus
            />

            <div className="analysis-meta">
              <span className="analysis-error" role="alert">
                {error}
              </span>
              <span className="analysis-count">
                {topic.length}/{MAX_LENGTH}
              </span>
            </div>

            <div className="analysis-examples">
              <span>Try an example:</span>
              {EXAMPLES.map((example) => (
                <button
                  key={example}
                  type="button"
                  onClick={() => {
                    setTopic(example);
                    setError("");
                  }}
                  disabled={isSubmitting}
                >
                  {example}
                </button>
              ))}
            </div>

            <button
              type="button"
              className="analyze-btn"
              onClick={handleAnalyze}
              disabled={isSubmitting}
            >
              <FaSearch />
              {isSubmitting ? "Starting analysis…" : "Analyze research claim"}
            </button>

            <p className="analysis-note">
              Results are a research aid. Always confirm important numbers in
              the original paper.
            </p>
          </div>
        </section>
      </main>

      <Footer />
    </>
  );
};

export default Analysis;
