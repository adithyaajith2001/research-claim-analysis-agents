import { useContext, useRef, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { FaSearch, FaLightbulb, FaFlask, FaCheckCircle, FaFilePdf } from "react-icons/fa";

import Navbar from "../components/layout/Navbar";
import Footer from "../components/layout/Footer";
import useStartAnalysis from "../hooks/useStartAnalysis";
import { AnalysisContext } from "../context/AnalysisContext";
import { getSession } from "../services/authService";
import { useAuthPrompt } from "../context/AuthPromptContext";
import { uploadPaper } from "../services/analysisService";

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
  const navigate = useNavigate();
  const { setAnalysisData } = useContext(AnalysisContext);
  const { openAuthPrompt } = useAuthPrompt();
  const fileRef = useRef(null);
  const [uploadName, setUploadName] = useState("");

  // Check one uploaded PDF instead of searching for papers.
  const handleFile = async (event) => {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file) return;

    if (!getSession()) {
      openAuthPrompt("");
      return;
    }

    setError("");
    setUploadName(file.name);
    setIsSubmitting(true);

    try {
      const started = await uploadPaper(file);
      const label = `Uploaded paper: ${started.title || file.name}`;

      setAnalysisData((previous) => ({
        ...previous,
        topic: label,
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

      navigate("/loading", {
        state: { topic: label, uploadJobId: started.job_id }
      });
    } catch (uploadError) {
      setError(uploadError.message || "The file could not be uploaded.");
      setUploadName("");
      setIsSubmitting(false);
    }
  };

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

            <div className="analysis-upload">
              <span className="analysis-upload-or">or check your own paper</span>
              <input
                ref={fileRef}
                type="file"
                accept="application/pdf,.pdf"
                className="analysis-sr"
                id="paper-upload"
                onChange={handleFile}
                disabled={isSubmitting}
              />
              <button
                type="button"
                className="analysis-upload-btn"
                onClick={() => fileRef.current?.click()}
                disabled={isSubmitting}
              >
                <FaFilePdf />
                {uploadName && isSubmitting
                  ? `Uploading ${uploadName}…`
                  : "Upload a paper (PDF)"}
              </button>
              <small>
                We read the results reported in the paper and check each number
                against its own text. PDFs with selectable text only, up to 25 MB.
              </small>
            </div>

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
