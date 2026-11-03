import Hero from "./Hero";
import {
  FaRobot,
  FaSearch,
  FaBalanceScale,
  FaChartBar,
} from "react-icons/fa";

function LeftPanel() {
  return (
    <div className="left-panel">

      {/* Hero Section */}
      <Hero />

      {/* Feature Section */}
      <div className="feature-list">

        {/* Feature 1 */}
        <div className="feature-card">

          <div className="feature-icon">
            <FaRobot />
          </div>

          <div className="feature-content">
            <h3>Multi-Agent AI</h3>

            <p>
              Multiple AI agents collaborate to analyze
              research papers and scientific claims.
            </p>
          </div>

        </div>


        {/* Feature 2 */}
        <div className="feature-card">

          <div className="feature-icon">
            <FaSearch />
          </div>

          <div className="feature-content">
            <h3>Claim Verification</h3>

            <p>
              Verify scientific claims using evidence
              from multiple research papers.
            </p>
          </div>

        </div>


        {/* Feature 3 */}
        <div className="feature-card">

          <div className="feature-icon">
            <FaBalanceScale />
          </div>

          <div className="feature-content">
            <h3>Contradiction Detection</h3>

            <p>
              Identify supporting and conflicting evidence
              across scientific studies.
            </p>
          </div>

        </div>


        {/* Feature 4 */}
        <div className="feature-card">

          <div className="feature-icon">
            <FaChartBar />
          </div>

          <div className="feature-content">
            <h3>Research Dashboard</h3>

            <p>
              Explore research findings through interactive
              analytics and visualizations.
            </p>
          </div>

        </div>

      </div>

    </div>
  );
}

export default LeftPanel;