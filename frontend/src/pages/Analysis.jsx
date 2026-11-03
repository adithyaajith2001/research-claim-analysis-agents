import React, {
  useContext,
  useState
} from "react";

import {
  FaSearch,
  FaLightbulb,
  FaFlask
} from "react-icons/fa";

import {
  useNavigate
} from "react-router-dom";

import Navbar from "../components/layout/Navbar";
import Footer from "../components/layout/Footer";

import {
  AnalysisContext
} from "../context/AnalysisContext";

import "../styles/analysis.css";


const Analysis = () => {

  const [topic, setTopic] = useState("");

  const [isSubmitting, setIsSubmitting] = useState(false);

  const navigate = useNavigate();


  // ============================================================
  // GET ANALYSIS CONTEXT
  // ============================================================

  const {
    setAnalysisData
  } = useContext(AnalysisContext);


  // ============================================================
  // ANALYZE BUTTON
  // ============================================================

  const handleAnalyze = () => {

    const trimmedTopic = topic.trim();


    // ----------------------------------------------------------
    // VALIDATION
    // ----------------------------------------------------------

    if (!trimmedTopic) {

      alert(
        "Please enter a research claim or topic."
      );

      return;
    }


    console.log(
      "======================================"
    );

    console.log(
      "ResearchClaimAI"
    );

    console.log(
      "Selected topic:",
      trimmedTopic
    );

    console.log(
      "======================================"
    );


    setIsSubmitting(true);


    // ==========================================================
    // SAVE ONLY THE TOPIC
    // ==========================================================
    //
    // The actual arXiv/backend search will happen in Loading.jsx.
    //
    // ==========================================================

    setAnalysisData((previousData) => ({

      ...previousData,

      topic: trimmedTopic,

      // Reset previous analysis results
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


    // ==========================================================
    // GO TO LOADING PAGE
    // ==========================================================

    navigate(
      "/loading",
      {
        state: {
          topic: trimmedTopic
        }
      }
    );

  };


  // ============================================================
  // EXAMPLE BUTTON
  // ============================================================

  const handleExampleClick = (
    example
  ) => {

    setTopic(example);

  };


  // ============================================================
  // UI
  // ============================================================

  return (

    <>

      <Navbar />


      <main className="analysis-page">


        {/* =====================================================
            HERO SECTION
        ===================================================== */}

        <section className="analysis-hero">

          <div className="analysis-hero-content">


            <div className="analysis-badge">

              <FaFlask />

              AI-POWERED RESEARCH ANALYSIS

            </div>


            <h1>

              Analyze Scientific

              <br />

              <span>
                Research Claims
              </span>

            </h1>


            <p>

              Enter a research claim or topic
              and let ResearchClaimAI retrieve
              scientific evidence, verify claims
              and generate an explainable
              confidence score.

            </p>


          </div>

        </section>


        {/* =====================================================
            INPUT SECTION
        ===================================================== */}

        <section className="analysis-input-section">

          <div className="analysis-card">


            {/* =================================================
                HEADER
            ================================================= */}

            <div className="analysis-card-header">


              <div className="analysis-icon">

                <FaLightbulb />

              </div>


              <div>

                <h2>

                  Enter Your Research Claim

                </h2>


                <p>

                  Our AI pipeline will analyze
                  the available research evidence
                  for your claim.

                </p>

              </div>


            </div>


            {/* =================================================
                TEXT AREA
            ================================================= */}

            <textarea

              rows="6"

              placeholder="Example: Does artificial intelligence improve healthcare?"

              value={topic}

              onChange={(e) =>
                setTopic(
                  e.target.value
                )
              }

              disabled={
                isSubmitting
              }

            />


            {/* =================================================
                EXAMPLE TOPICS
            ================================================= */}

            <div className="analysis-examples">


              <span>

                Try an example:

              </span>


              <button

                type="button"

                onClick={() =>
                  handleExampleClick(
                    "Climate Change"
                  )
                }

                disabled={
                  isSubmitting
                }

              >

                Climate Change

              </button>


              <button

                type="button"

                onClick={() =>
                  handleExampleClick(
                    "Artificial Intelligence in Healthcare"
                  )
                }

                disabled={
                  isSubmitting
                }

              >

                AI in Healthcare

              </button>


              <button

                type="button"

                onClick={() =>
                  handleExampleClick(
                    "Blockchain"
                  )
                }

                disabled={
                  isSubmitting
                }

              >

                Blockchain

              </button>


              <button

                type="button"

                onClick={() =>
                  handleExampleClick(
                    "Machine Learning"
                  )
                }

                disabled={
                  isSubmitting
                }

              >

                Machine Learning

              </button>


            </div>


            {/* =================================================
                ANALYZE BUTTON
            ================================================= */}

            <button

              type="button"

              className="analyze-btn"

              onClick={
                handleAnalyze
              }

              disabled={
                isSubmitting
              }

            >

              <FaSearch />

              {isSubmitting

                ? "Starting Analysis..."

                : "Analyze Research Claim"

              }

            </button>


            {/* =================================================
                NOTE
            ================================================= */}

            <p className="analysis-note">

              ResearchClaimAI uses a multi-stage
              AI workflow to retrieve, extract,
              verify and score research evidence.

            </p>


          </div>

        </section>


      </main>


      <Footer />

    </>

  );

};


export default Analysis;