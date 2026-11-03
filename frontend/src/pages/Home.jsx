import { Link } from "react-router-dom";

import Navbar from "../components/layout/Navbar";
import Footer from "../components/layout/Footer";

import FeatureCards from "../components/common/FeatureCards";
import AnalysisPipeline from "../components/results/AnalysisPipeline";
import CitationNetwork from "../visualizations/CitationNetwork";

import "../styles/home.css";

function Home() {
  return (
    <>
      <Navbar />

      <main className="home-page">

        {/* ================= HERO SECTION ================= */}
        <section className="home-hero">

          {/* Background decorative elements */}
          <div className="hero-glow hero-glow-one"></div>
          <div className="hero-glow hero-glow-two"></div>

          <div className="home-hero-content">

            <div className="home-badge">
              <span className="badge-dot"></span>
              AI-POWERED RESEARCH VERIFICATION
            </div>

            <h1>
              Research<span>ClaimAI</span>
            </h1>

            <h2>
              Intelligent Analysis of
              <span> Scientific Research Claims</span>
            </h2>

            <p>
              ResearchClaimAI helps researchers analyze scientific claims
              by retrieving relevant research papers, extracting evidence,
              verifying supporting and contradicting findings, and generating
              an explainable confidence score.
            </p>

            <div className="home-actions">

              <Link
                to="/analysis"
                className="home-analyze-btn"
              >
                <span>Start Research Analysis</span>
                <span className="btn-arrow">→</span>
              </Link>

              <Link
                to="/dashboard"
                className="home-dashboard-btn"
              >
                View Dashboard
              </Link>

            </div>

            {/* Small trust indicators */}
            <div className="home-trust">

              <div className="trust-item">
                <strong>01</strong>
                <span>Retrieve</span>
              </div>

              <div className="trust-line"></div>

              <div className="trust-item">
                <strong>02</strong>
                <span>Verify</span>
              </div>

              <div className="trust-line"></div>

              <div className="trust-item">
                <strong>03</strong>
                <span>Score</span>
              </div>

            </div>

          </div>


          {/* ================= RIGHT VISUAL ================= */}
          <div className="home-hero-visual">

            <div className="visual-orbit orbit-one"></div>
            <div className="visual-orbit orbit-two"></div>

            <div className="research-engine-card">

              <div className="engine-header">

                <div className="engine-icon">
                  ✦
                </div>

                <div>
                  <span>AI RESEARCH ENGINE</span>
                  <strong>Evidence Analysis</strong>
                </div>

                <div className="engine-status">
                  <span></span>
                  LIVE
                </div>

              </div>


              <div className="engine-claim">

                <span>RESEARCH CLAIM</span>

                <p>
                  Does artificial intelligence improve
                  healthcare outcomes?
                </p>

              </div>


              <div className="engine-analysis">

                <div className="analysis-node node-blue">
                  <div className="node-icon">⌕</div>
                  <span>Research</span>
                  <strong>84 Papers</strong>
                </div>

                <div className="node-connector"></div>

                <div className="analysis-node node-purple">
                  <div className="node-icon">◈</div>
                  <span>Evidence</span>
                  <strong>Verified</strong>
                </div>

                <div className="node-connector"></div>

                <div className="analysis-node node-green">
                  <div className="node-icon">✓</div>
                  <span>Confidence</span>
                  <strong>95%</strong>
                </div>

              </div>


              <div className="confidence-preview">

                <div className="confidence-info">

                  <span>Overall Confidence</span>

                  <strong>Highly Supported</strong>

                </div>

                <div className="confidence-bar">

                  <div className="confidence-fill"></div>

                </div>

                <div className="confidence-percent">
                  95%
                </div>

              </div>

            </div>

          </div>

        </section>


        {/* ================= FEATURES ================= */}
        <section className="home-features-section">
          <FeatureCards />
        </section>


        {/* ================= ANALYSIS PIPELINE ================= */}
        <section className="home-pipeline-section">
          <AnalysisPipeline />
        </section>


        {/* ================= CITATION NETWORK ================= */}
        <section className="home-citation-section">
          <CitationNetwork />
        </section>

      </main>

      <Footer />
    </>
  );
}

export default Home;