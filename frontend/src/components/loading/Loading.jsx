import React, {
  useContext,
  useEffect,
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
  FaChartLine
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
// ============================================================

const steps = [
  {
    icon: <FaSearch />,
    title: "Literature Retrieval",
    description: "Searching scientific databases"
  },
  {
    icon: <FaFileAlt />,
    title: "Claim Extraction",
    description: "Extracting claims and evidence"
  },
  {
    icon: <FaBrain />,
    title: "AI Reasoning",
    description: "Analyzing relationships"
  },
  {
    icon: <FaCheckCircle />,
    title: "Evidence Verification",
    description: "Comparing supporting studies"
  },
  {
    icon: <FaChartLine />,
    title: "Confidence Score",
    description: "Generating credibility score"
  }
];


// ============================================================
// LOADING COMPONENT
// ============================================================

const Loading = () => {

  const [activeStep, setActiveStep] = useState(0);

  const [analysisStarted, setAnalysisStarted] =
    useState(false);

  const navigate = useNavigate();

  const location = useLocation();


  // ==========================================================
  // ANALYSIS CONTEXT
  // ==========================================================

  const {
    analysisData,
    updateAnalysisData
  } = useContext(AnalysisContext);


  // ==========================================================
  // GET TOPIC
  // ==========================================================

  const topic =
    location.state?.topic ||
    analysisData?.topic ||
    "Research Topic";


  // ==========================================================
  // STEP PROGRESS + BACKEND ANALYSIS
  // ==========================================================

  useEffect(() => {

    console.log(
      "Loading page received topic:",
      topic
    );


    // --------------------------------------------------------
    // MOVE THROUGH VISUAL PIPELINE
    // --------------------------------------------------------

    if (activeStep < steps.length - 1) {

      const timer = setTimeout(() => {

        setActiveStep(
          previousStep =>
            previousStep + 1
        );

      }, 1800);


      return () => {

        clearTimeout(timer);

      };

    }


    // --------------------------------------------------------
    // PREVENT DUPLICATE API REQUEST
    // --------------------------------------------------------

    if (analysisStarted) {

      return undefined;

    }


    setAnalysisStarted(true);


    // ========================================================
    // BACKEND ANALYSIS
    // ========================================================

    const analyze = async () => {

      console.log(
        "======================================"
      );

      console.log(
        "Starting backend analysis"
      );

      console.log(
        "Topic:",
        topic
      );

      console.log(
        "======================================"
      );


      try {

        // ====================================================
        // CALL FASTAPI
        // ====================================================

        const result =
          await analyzeTopic(topic);


        console.log(
          "======================================"
        );

        console.log(
          "Backend result received:"
        );

        console.log(
          result
        );

        console.log(
          "======================================"
        );


        // ====================================================
        // PAPERS
        // ====================================================

        const retrievedPapers =
          Array.isArray(result?.papers)
            ? result.papers
            : [];


        const paperCount =
          Number.isFinite(
            Number(
              result?.papers_retrieved
            )
          )
            ? Number(
                result.papers_retrieved
              )
            : retrievedPapers.length;


        // ====================================================
        // CONFIDENCE
        // ====================================================

        // Backend returns:
        //
        // confidence: {
        //   overall_score: 7.83,
        //   confidence_level: "Medium",
        //   breakdown: {...}
        // }

        const confidence =
          Number(
            result?.confidence?.overall_score
          );

        const safeConfidence =
          Number.isFinite(confidence)
            ? confidence
            : 0;


        const confidenceLevel =
          result?.confidence?.confidence_level ||
          "Low";


        const confidenceBreakdown =
          result?.confidence?.breakdown ||
          {};


        // ====================================================
        // CLAIMS
        // ====================================================

        // Backend returns claims as an ARRAY.

        const extractedClaims =
          Array.isArray(result?.claims)
            ? result.claims
            : [];


        const claimCount =
          Number.isFinite(
            Number(result?.claims_extracted)
          )
            ? Number(result.claims_extracted)
            : extractedClaims.length;


        // ====================================================
        // SUPPORTING PAPERS
        // ====================================================

        const supportingPapers =
          Array.isArray(
            result?.supportingPapers
          )
            ? result.supportingPapers
            : Array.isArray(
                result?.supporting_papers
              )
                ? result.supporting_papers
                : [];


        // ====================================================
        // CONTRADICTING PAPERS
        // ====================================================

        const contradictingPapers =
          Array.isArray(
            result?.contradictingPapers
          )
            ? result.contradictingPapers
            : Array.isArray(
                result?.contradicting_papers
              )
                ? result.contradicting_papers
                : [];


        // ====================================================
        // NEUTRAL PAPERS
        // ====================================================

        const neutralPapers =
          Array.isArray(
            result?.neutralPapers
          )
            ? result.neutralPapers
            : Array.isArray(
                result?.neutral_papers
              )
                ? result.neutral_papers
                : [];


        // ====================================================
        // CONTRADICTIONS
        // ====================================================

        const contradictions =
          Array.isArray(result?.contradictions)
            ? result.contradictions
            : [];


        // ====================================================
        // SUMMARY
        // ====================================================

        const summary =
          result?.summary ||
          `ResearchClaimAI analyzed ${paperCount} research papers related to "${topic}".`;


        // ====================================================
        // DEBUG
        // ====================================================

        console.log(
          "---------------- ANALYSIS DATA ----------------"
        );

        console.log(
          "Topic:",
          result?.query || topic
        );

        console.log(
          "Papers retrieved:",
          paperCount
        );

        console.log(
          "Claims extracted:",
          claimCount
        );

        console.log(
          "Claim objects:",
          extractedClaims
        );

        console.log(
          "Confidence:",
          safeConfidence
        );

        console.log(
          "Confidence level:",
          confidenceLevel
        );

        console.log(
          "Confidence breakdown:",
          confidenceBreakdown
        );

        console.log(
          "Supporting papers:",
          supportingPapers
        );

        console.log(
          "Contradicting papers:",
          contradictingPapers
        );

        console.log(
          "Neutral papers:",
          neutralPapers
        );

        console.log(
          "Contradictions:",
          contradictions
        );

        console.log(
          "Paper list:",
          retrievedPapers
        );

        console.log(
          "------------------------------------------------"
        );


        // ====================================================
        // SAVE COMPLETE RESULT IN CONTEXT
        // ====================================================

        updateAnalysisData({

          // --------------------------------------------------
          // TOPIC
          // --------------------------------------------------

          topic:
            result?.query ||
            topic,


          // --------------------------------------------------
          // CONFIDENCE
          // --------------------------------------------------

          confidence:
            safeConfidence,

          confidenceLevel:
            confidenceLevel,

          confidenceBreakdown:
            confidenceBreakdown,


          // --------------------------------------------------
          // CLAIM COUNT
          // --------------------------------------------------

          claims:
            claimCount,

          claimsExtracted:
            claimCount,


          // --------------------------------------------------
          // ACTUAL CLAIM OBJECTS
          // --------------------------------------------------

          extractedClaims:
            extractedClaims,


          // --------------------------------------------------
          // PAPER COUNT
          // --------------------------------------------------

          papers:
            paperCount,

          papers_retrieved:
            paperCount,


          // --------------------------------------------------
          // ACTUAL PAPERS
          // --------------------------------------------------

          paperList:
            retrievedPapers,


          // --------------------------------------------------
          // SUMMARY
          // --------------------------------------------------

          summary:
            summary,


          // --------------------------------------------------
          // STATUS
          // --------------------------------------------------

          status:
            result?.status === "success"
              ? "Analyzed"
              : result?.status ||
                "Analyzed",


          // --------------------------------------------------
          // SUPPORTING PAPERS
          // --------------------------------------------------

          supportingPapers:
            supportingPapers,


          // --------------------------------------------------
          // CONTRADICTING PAPERS
          // --------------------------------------------------

          contradictingPapers:
            contradictingPapers,


          // --------------------------------------------------
          // NEUTRAL PAPERS
          // --------------------------------------------------

          neutralPapers:
            neutralPapers,


          // --------------------------------------------------
          // CONTRADICTIONS
          // --------------------------------------------------

          contradictions:
            contradictions,


          // --------------------------------------------------
          // RAW BACKEND RESPONSE
          // --------------------------------------------------

          rawResponse:
            result

        });


        // ====================================================
        // GO TO DASHBOARD
        // ====================================================

        navigate(
          "/dashboard",
          {
            replace: true
          }
        );

      } catch (error) {

        console.error(
          "======================================"
        );

        console.error(
          "ANALYSIS FAILED"
        );

        console.error(
          error
        );

        console.error(
          "======================================"
        );


        // ====================================================
        // SAVE FAILURE STATE
        // ====================================================

        updateAnalysisData({

          topic:
            topic,

          confidence:
            0,

          confidenceLevel:
            "Low",

          confidenceBreakdown:
            {},

          papers:
            0,

          papers_retrieved:
            0,

          paperList:
            [],

          claims:
            0,

          claimsExtracted:
            0,

          extractedClaims:
            [],

          summary:
            "Unable to retrieve research papers for this topic.",

          status:
            "Analysis Failed",

          supportingPapers:
            [],

          contradictingPapers:
            [],

          neutralPapers:
            [],

          contradictions:
            [],

          rawResponse:
            null

        });


        // ====================================================
        // GO TO DASHBOARD
        // ====================================================

        navigate(
          "/dashboard",
          {
            replace: true
          }
        );

      }

    };


    analyze();


    return undefined;

  }, [
    activeStep,
    analysisStarted,
    navigate,
    topic,
    updateAnalysisData
  ]);


  // ==========================================================
  // PROGRESS
  // ==========================================================

  const progress =
  activeStep >= steps.length - 1
    ? (analysisStarted ? 90 : 80)
    : ((activeStep + 1) / steps.length) * 80;

  // ==========================================================
  // UI
  // ==========================================================

  return (

    <div className="loading-page">

      <div className="loading-card">


        {/* ====================================================
            HEADER
        ==================================================== */}

        <div className="loading-header">

          <div className="loading-logo">

            <FaBrain />

          </div>


          <h1>
            ResearchClaimAI
          </h1>


          <p>
            Multi-Agent AI Research Analysis
          </p>

        </div>


        {/* ====================================================
            TOPIC
        ==================================================== */}

        <div className="loading-topic-box">

          <span>
            ANALYZING RESEARCH TOPIC
          </span>


          <h2>
            {topic}
          </h2>

        </div>


        {/* ====================================================
            PIPELINE
        ==================================================== */}

        <div className="pipeline">

          {steps.map(
            (step, index) => {

              const isActive =
                index === activeStep;


              const isCompleted =
                index < activeStep;


              return (

                <div
                  key={index}
                  className={`
                    pipeline-step
                    ${isActive ? "active" : ""}
                    ${isCompleted ? "completed" : ""}
                  `}
                >


                  {/* ICON */}

                  <div className="pipeline-icon">

                    {step.icon}

                  </div>


                  {/* NUMBER */}

                  <div className="step-number">

                    {isCompleted
                      ? "✓"
                      : `0${index + 1}`
                    }

                  </div>


                  {/* TITLE */}

                  <h3>
                    {step.title}
                  </h3>


                  {/* DESCRIPTION */}

                  <p>
                    {step.description}...
                  </p>


                  {/* ACTIVE STATUS */}

              {isActive && (
  <div className="step-status">
    {index === steps.length - 1 && analysisStarted
      ? "Analyzing research data..."
      : "Processing"}
  </div>
)}


                  {/* COMPLETED STATUS */}

                  {isCompleted && (

                    <div
                      className="
                        step-status
                        completed-status
                      "
                    >

                      Completed

                    </div>

                  )}

                </div>

              );

            }
          )}

        </div>


        {/* ====================================================
            PROGRESS
        ==================================================== */}

        <div className="progress-section">

          <div className="progress-info">

            <span>
              Analysis Progress
            </span>


            <strong>
              {Math.round(progress)}%
            </strong>

          </div>


          <div className="progress-bar">

            <div
              className="progress-fill"
              style={{
                width:
                  `${progress}%`
              }}
            />

          </div>

        </div>


        {/* ====================================================
            FOOTER
        ==================================================== */}

        <p className="loading-footer">

          ResearchClaimAI is processing
          scientific evidence using
          multiple intelligent agents.

        </p>


      </div>

    </div>

  );

};


export default Loading;