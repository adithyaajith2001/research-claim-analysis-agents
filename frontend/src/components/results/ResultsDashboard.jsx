import "../../styles/resultsDashboard.css";

function ResultsDashboard({ topic }) {

  return (

    <section className="results-dashboard">

      <div className="results-header">

        <h1>{topic}</h1>

        <span className="confidence">
          Confidence 92%
        </span>

      </div>

      <div className="results-grid">

        <div className="card summary">

          <h2>Research Summary</h2>

          <p>

            AI analysis suggests strong scientific evidence
            supporting the relationship between the selected
            topic and existing literature.

          </p>

        </div>

        <div className="card claims">

          <h2>Key Claims</h2>

          <ul>

            <li>Increasing evidence from multiple papers.</li>

            <li>High agreement among researchers.</li>

            <li>Recent studies strengthen confidence.</li>

          </ul>

        </div>

        <div className="card evidence">

          <h2>Supporting Papers</h2>

          <ul>

            <li>Nature (2025)</li>

            <li>IEEE Access (2024)</li>

            <li>ScienceDirect (2023)</li>

          </ul>

        </div>

        <div className="card confidence-card">

          <h2>AI Confidence</h2>

          <div className="circle">

            92%

          </div>

        </div>

      </div>

    </section>

  );

}

export default ResultsDashboard;