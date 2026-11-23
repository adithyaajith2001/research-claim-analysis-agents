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
  FaExclamationTriangle,
  FaStop,
  FaRedoAlt
} from "react-icons/fa";

import {
  AnalysisContext
} from "../../context/AnalysisContext";

import {
  analyzeTopic,
  cancelAnalysis
} from "../../services/analysisService";

import { getSession } from "../../services/authService";
import { addHistoryEntry } from "../../services/historyService";

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
    setAnalysisData,
    updateAnalysisData
  } = useContext(AnalysisContext);

  const topic =
    location.state?.topic ||
    analysisData?.topic ||
    "Research Topic";

  // An uploaded paper is already running on the backend: this page only
  // follows it. Starting it again would search the web for its title.
  const uploadJobRef = useRef(location.state?.uploadJobId || null);
  const isUpload = Boolean(location.state?.uploadJobId);

  const startedRef = useRef(false);
  const mountedRef = useRef(true);
  const runIdRef = useRef(0);          // which run is the current one
  const jobIdRef = useRef(null);       // backend job of the current run
  const stopWantedRef = useRef(false); // Stop pressed before the job id arrived

  const [progress, setProgress] = useState({
    stage: "retrieval",
    percent: 2,
    message: "Starting analysis"
  });
  const [elapsed, setElapsed] = useState(0);
  const [errorMessage, setErrorMessage] = useState("");
  const [stopped, setStopped] = useState(false);

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
    };
  }, []);


  // ----------------------------------------------------------
  // Elapsed-time clock
  // ----------------------------------------------------------

  useEffect(() => {
    if (errorMessage || stopped) {
      return undefined;
    }

    const timer = setInterval(() => {
      setElapsed((previous) => previous + 1);
    }, 1000);

    return () => clearInterval(timer);
  }, [errorMessage, stopped]);


  // ----------------------------------------------------------
  // Run one analysis and follow its real progress.
  // `restart` tells the backend to stop whatever is running first.
  // ----------------------------------------------------------

  // Nothing is running any more, so the dashboard must not wait for it.
  const markIdle = () => {
    setAnalysisData((previous) =>
      previous.status === "Analyzing"
        ? { ...previous, status: "Not Analyzed", isAnalyzing: false }
        : previous
    );
  };

  const runAnalysis = async (restart, refresh) => {
    if (isUpload && !uploadJobRef.current) {
      // A stopped or failed upload cannot be repeated from here.
      navigate("/analysis");
      return;
    }

    runIdRef.current += 1;
    const myRun = runIdRef.current;
    const isCurrent = () => myRun === runIdRef.current;

    jobIdRef.current = null;
    stopWantedRef.current = false;

    setErrorMessage("");
    setStopped(false);
    setElapsed(0);
    setAnalysisData((previous) => ({
      ...previous,
      topic,
      status: "Analyzing",
      isAnalyzing: true
    }));
    setProgress({ stage: "retrieval", percent: 2, message: "Starting analysis" });

    try {
      const result = await analyzeTopic(
        topic,
        5,
        (update) => {
          if (!isCurrent()) return;
          setProgress({
            stage: update.stage,
            percent: update.percent,
            message: update.message
          });
        },
        refresh,
        {
          restart,
          existingJobId: uploadJobRef.current,
          onJobId: (id) => {
            jobIdRef.current = id;
            // Stop was pressed while the job was still being created.
            if (stopWantedRef.current) cancelAnalysis(id);
          }
        }
      );

      if (!isCurrent()) return;

      uploadJobRef.current = null;

      const confidenceScore = Number(result.confidence?.overall_score);

      const finished = {
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
        queryModels: result.query_models,
        fromCache: result.from_cache,
        claimsSkippedOtherModels: result.claims_skipped_other_models,
        skippedClaims: result.skipped_claims,
        rawResponse: result.rawResponse
      };

      // These two always run, even if the person has opened another page
      // while waiting, so the dashboard and history are up to date.
      updateAnalysisData(finished);

      const session = getSession();
      if (session) {
        addHistoryEntry(session.email, finished);
      }

      if (mountedRef.current) {
        navigate("/dashboard", { replace: true });
      }
    } catch (error) {
      if (!isCurrent()) return;

      uploadJobRef.current = null; // an upload can only be followed once
      markIdle();

      if (error?.cancelled) {
        if (mountedRef.current) setStopped(true);
        return;
      }

      console.error("ResearchClaimAI analysis failed:", error);

      if (mountedRef.current) {
        setErrorMessage(
          error?.message ||
            "Something went wrong while analysing this topic."
        );
      }
    }
  };

  useEffect(() => {
    if (startedRef.current) {
      return;
    }

    startedRef.current = true;
    runAnalysis(false, Boolean(location.state?.refresh));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);


  // Stop the analysis that is running.
  const handleStop = () => {
    uploadJobRef.current = null;
    runIdRef.current += 1; // ignore anything the stopped run still reports
    stopWantedRef.current = true;
    cancelAnalysis(jobIdRef.current);
    markIdle();
    setStopped(true);
  };

  // Stop the current analysis and begin the same question again.
  const handleRestart = () => {
    if (jobIdRef.current) cancelAnalysis(jobIdRef.current);
    runAnalysis(true, true);
  };


  const activeStep = stepIndexForStage(progress.stage);
  const percent = Math.min(Math.max(Number(progress.percent) || 0, 0), 100);


  // ----------------------------------------------------------
  // Stopped screen
  // ----------------------------------------------------------

  if (stopped) {
    return (
      <div className="loading-page">
        <div className="loading-card">
          <div className="loading-header">
            <div className="loading-logo error-logo">
              <FaStop />
            </div>
            <h1>Analysis stopped</h1>
            <p>Nothing was saved. You can start this question again or ask a different one.</p>
          </div>

          <div className="loading-topic-box">
            <span>RESEARCH TOPIC</span>
            <h2>{topic}</h2>
          </div>

          <div className="loading-actions">
            <button
              type="button"
              className="loading-button primary"
              onClick={() => runAnalysis(true, true)}
            >
              Start this topic again
            </button>
            <button
              type="button"
              className="loading-button"
              onClick={() => navigate("/analysis")}
            >
              Try another topic
            </button>
          </div>
        </div>
      </div>
    );
  }


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
              onClick={() => runAnalysis(true, true)}
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

        <div className="loading-actions">
          <button
            type="button"
            className="loading-button"
            onClick={handleStop}
          >
            <FaStop aria-hidden="true" /> Stop analysis
          </button>
          <button
            type="button"
            className="loading-button"
            onClick={handleRestart}
          >
            <FaRedoAlt aria-hidden="true" /> Start over
          </button>
        </div>

        <p className="loading-footer">
          Time elapsed {formatElapsed(elapsed)}. A full analysis usually
          takes 1–3 minutes. Please keep this tab open.
        </p>
      </div>
    </div>
  );
};

export default Loading;
