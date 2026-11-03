import "../../styles/pipeline.css";

function AnalysisPipeline() {
  return (
    <section className="analysis-pipeline">

      <div className="pipeline-heading">
        <span>AI WORKFLOW</span>
        <h2>Research Analysis Pipeline</h2>
        <p>
          A multi-stage process for retrieving, analyzing and verifying
          scientific research claims.
        </p>
      </div>

      <div className="analysis-steps">

        <div className="analysis-step">
          <div className="analysis-icon">🔍</div>

          <div className="step-number">01</div>

          <h3>Retrieve Papers</h3>

          <p>
            Searching research repositories and scientific databases.
          </p>
        </div>


        <div className="pipeline-arrow">→</div>


        <div className="analysis-step">
          <div className="analysis-icon">🧠</div>

          <div className="step-number">02</div>

          <h3>Extract Claims</h3>

          <p>
            Identifying important scientific claims from research papers.
          </p>
        </div>


        <div className="pipeline-arrow">→</div>


        <div className="analysis-step">
          <div className="analysis-icon">🛡️</div>

          <div className="step-number">03</div>

          <h3>Verify Evidence</h3>

          <p>
            Comparing supporting and contradicting research evidence.
          </p>
        </div>


        <div className="pipeline-arrow">→</div>


        <div className="analysis-step">
          <div className="analysis-icon">📊</div>

          <div className="step-number">04</div>

          <h3>Confidence Score</h3>

          <p>
            Generating an explainable AI confidence score.
          </p>
        </div>

      </div>

    </section>
  );
}

export default AnalysisPipeline;