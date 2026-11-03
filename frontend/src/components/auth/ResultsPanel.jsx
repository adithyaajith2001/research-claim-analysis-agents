import { FaCheckCircle, FaExclamationTriangle } from "react-icons/fa";

function ResultsPanel() {
  return (
    <div className="results-panel">

      <h3>Analysis Results</h3>

      <div className="results-grid">

        <div className="result-card">

          <FaCheckCircle className="green-icon"/>

          <h4>Claim Verified</h4>

          <p>High confidence evidence</p>

          <span className="success">
            Confidence 94%
          </span>

        </div>

        <div className="result-card">

          <FaExclamationTriangle className="orange-icon"/>

          <h4>Contradiction Found</h4>

          <p>Conflicting evidence</p>

          <span className="warning">
            Confidence 62%
          </span>

        </div>

        <div className="confidence-card">

          <div className="confidence-circle">

            <span>87%</span>

          </div>

          <p>Overall Confidence</p>

        </div>

      </div>

    </div>
  );
}

export default ResultsPanel;