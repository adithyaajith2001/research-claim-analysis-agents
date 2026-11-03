import { useContext } from "react";

import { AnalysisContext } from "../../context/AnalysisContext";

import { confidenceToPercentage } from "../../utils/confidence";

import "../../styles/dashboard.css";


function SummaryCard() {

  const { analysisData } =
    useContext(AnalysisContext);


  // =====================================================
  // TOPIC
  // =====================================================

  const topic =
    analysisData?.topic ||
    "Research Topic";


  // =====================================================
  // PAPERS
  // =====================================================

  const papers =
    typeof analysisData?.papers === "number"
      ? analysisData.papers
      : 0;


  // =====================================================
  // CONFIDENCE
  // =====================================================

  const confidence =
    confidenceToPercentage(
      analysisData?.confidence
    );


  // =====================================================
  // STATUS
  // =====================================================

  const status =
    analysisData?.status ||
    "Not Analyzed";


  // =====================================================
  // RENDER
  // =====================================================

  return (

    <section className="summary-card">


      {/* =================================
          LEFT SIDE
      ================================= */}

      <div className="summary-left">


        <span className="badge">

          AI Research Summary

        </span>


        <h2>

          {topic}

        </h2>


        <p>

          ResearchClaimAI analyzed{" "}

          <strong>

            {papers} research papers

          </strong>{" "}

          from arXiv and scientific literature.

        </p>


        <div className="summary-tags">


          <span>

            🔬 Research Evidence

          </span>


          <span>

            📚 {papers} Papers

          </span>


          <span>

            🤖 AI Analysis

          </span>


        </div>


      </div>


      {/* =================================
          RIGHT SIDE
      ================================= */}

      <div className="summary-right">


        <div className="confidence-circle">

          <span>

            {confidence}%

          </span>

        </div>


        <h3>

          {status}

        </h3>


        <p>

          Overall Confidence

        </p>


      </div>


    </section>

  );

}


export default SummaryCard;