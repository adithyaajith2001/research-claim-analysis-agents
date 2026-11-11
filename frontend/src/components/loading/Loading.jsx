import React, {
  useContext,
  useEffect,
  useRef,
  useState
} from "react";

import {
  useNavigate,
  useLocation
} from "react-router-dom";

import {
  FaSearch,
  FaFileAlt,
  FaBrain,
  FaCheckCircle,
  FaChartLine,
  FaExclamationTriangle
} from "react-icons/fa";

import {
  AnalysisContext
} from "../../context/AnalysisContext";

import {
  analyzeTopic
} from "../../services/analysisService";

import "../../styles/loading.css";


// ============================================================
// ANALYSIS STEPS
// Each backend stage name maps to one visible step.
// ============================================================

const steps = [
  {
    key: "retrieval",
    icon: <FaSearch />,
    title: "Find Papers",
    description: "Searching arXiv, Semantic Scholar and CrossRef"
  },
  {
    key: "extraction",
    icon: <FaFileAlt />,
    title: "Read Papers",
    description: "Finding the results each paper claims"
  },
  {
    key: "scoring",
    icon: <FaBrain />,
    title: "Check Evidence",
    description: "Testing each claim against its evidence"
  },
  {
    key: "contradictions",
    icon: <FaCheckCircle />,
    title: "Compare Papers",
    description: "Looking for agreement and conflict"
  },
  {
    key: "confidence",
    icon: <FaChartLine />,
    title: "Trust Score",
    description: "Combining everything into one score"
  }
];

function stepIndexForStage(stage) {
  const index = steps.findIndex((step) => step.key === stage);
  return index === -1 ? 0 : index;
}

function formatElapsed(totalSeconds) {
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  return `${minutes}:${String(seconds).padStart(2, "0")}`;
}


// ============================================================
// LOADING COMPONENT
// ============================================================

const Loading = () => {
  const navigate = useNavigate();
  const location = useLocation();

  const {
    analysisData,
    updateAnalysisData
  } = useContext(AnalysisContext);

  const topic =
    location.state?.topic ||
    analysisData?.topic ||
    "Research Topic";

  const startedRef = useRef(false);

  const [progress, setProgress] = useState({
    stage: "retrieval",
    percent: 2,
    message: "Starting analysis"
  });
  const [elapsed, setElapsed] = useState(0);
  const [errorMessage, setErrorMessage] = useState("");


  // ----------------------------------------------------------
  // Elapsed-time clock
  // ----------------------------------------------------------

  useEffect(() => {
    if (errorMessage) {
      return undefined;
    }

    const timer = setInterval(() => {
      setElapsed((previous) => previous + 1);
    }, 1000);

    return () => clearInterval(timer);
  }, [errorMessage]);


  // ----------------------------------------------------------
  // Run the analysis once and follow its real progress
  // ----------------------------------------------------------

  useEffect(() => {
    if (startedRef.current) {
      return;
    }

    startedRef.current = true;

    const run = async () => {
      try {
        const result = await analyzeTopic(
          topic,
          5,
          (update) => {
            setProgress({
              stage: update.stage,
              percent: update.percent,
              message: update.message
            });
          }
        );

        const confidenceScore = Number(result.confidence?.overall_score);

        updateAnalysisData({
          topic: result.query || topic,
          confidence: Number.isFinite(confidenceScore)
            ? confidenceScore
            : 0,
          confidenceLevel: result.confidence?.confidence_level || "Low",
          confidenceBreakdown: result.confidence?.breakdown || {},
          claims: result.claims_extracted,
          claimsExtracted: result.claims_extracted,
          extractedClaims: result.claims,
          papers: result.papers_retrieved,
          papers_retrieved: result.papers_retrieved,
          paperList: result.papers,
          summary: result.summary,
          status: "Analyzed",
          supportingPapers: result.supportingPapers,
          contradictingPapers: result.contradictingPapers,
          neutralPapers: result.neutralPapers,
          contradictions: result.contradictions,
          analysisSeconds: result.analysis_seconds,
          rawResponse: result.rawResponse
        });

        navigate("/dashboard", { replace: true });
      } catch (error) {
        console.error("ResearchClaimAI analysis failed:", error);

        setErrorMessage(
          error?.message ||
            "Something went wrong while analysing this topic."
        );
      }
    };

    run();
  }, [navigate, topic, updateAnalysisData]);


  const activeStep = stepIndexForStage(progress.stage);
  const percent = Math.min(Math.max(Number(progress.percent) || 0, 0), 100);


  // ----------------------------------------------------------
  // Error screen
  // ----------------------------------------------------------

  if (errorMessage) {
    return (
      <div className="loading-page">
        <div className="loading-card">
          <div className="loading-header">
            <div className="loading-logo error-logo">
              <FaExclamationTriangle />
            </div>
            <h1>Analysis could not finish</h1>
            <p>{errorMessage}</p>
          </div>

          <div className="loading-topic-box">
            <span>RESEARCH TOPIC</span>
            <h2>{topic}</h2>
          </div>

          <div className="loading-actions">
            <button
              type="button"
              className="loading-button primary"
              onClick={() => navigate("/analysis")}
            >
              Try another topic
            </button>
            <button
              type="button"
              className="loading-button"
              onClick={() => window.location.reload()}
            >
              Retry this topic
            </button>
          </div>
        </div>
      </div>
    );
  }


  // ----------------------------------------------------------
  // Progress screen
  // ----------------------------------------------------------

  return (
    <div className="loading-page">
      <div className="loading-card">

        <div className="loading-header">
          <div className="loading-logo">
            <FaBrain />
          </div>
          <h1>ResearchClaimAI</h1>
          <p>Multi-Agent AI Research Analysis</p>
        </div>

        <div className="loading-topic-box">
          <span>ANALYZING RESEARCH TOPIC</span>
          <h2>{topic}</h2>
        </div>

        <div className="pipeline">
          {steps.map((step, index) => {
            const isActive = index === activeStep;
            const isCompleted = index < activeStep;

            return (
              <div
                key={step.key}
                className={
                  "pipeline-step" +
                  (isActive ? " active" : "") +
                  (isCompleted ? " completed" : "")
                }
              >
                <div className="pipeline-icon">{step.icon}</div>

                <div className="step-number">
                  {isCompleted ? "✓" : `0${index + 1}`}
                </div>

                <h3>{step.title}</h3>
                <p>{step.description}</p>

                {isActive && (
                  <div className="step-status">In progress</div>
                )}

                {isCompleted && (
                  <div className="step-status completed-status">
                    Done
                  </div>
                )}
              </div>
            );
          })}
        </div>

        <div className="progress-section">
          <div className="progress-info">
            <span>{progress.message}</span>
            <strong>{Math.round(percent)}%</strong>
          </div>

          <div className="progress-bar">
            <div
              className="progress-fill"
              style={{ width: `${percent}%` }}
            />
          </div>
        </div>

        <p className="loading-footer">
          Time elapsed {formatElapsed(elapsed)}. A full analysis usually
          takes 2–4 minutes. Please keep this tab open.
        </p>
      </div>
    </div>
  );
};

export default Loading;
