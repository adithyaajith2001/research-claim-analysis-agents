import React from "react";

import Navbar from "../components/layout/Navbar";
import Footer from "../components/layout/Footer";

import "../styles/about.css";


function About() {

  return (

    <>

      <Navbar />


      <main className="about-page">


        {/* =====================================================
            HERO
        ===================================================== */}

        <section className="about-hero">

          <div className="about-content">

            <div className="about-badge">
              AI-POWERED RESEARCH ANALYSIS
            </div>


            <h1>
              About
              <span> ResearchClaimAI</span>
            </h1>


            <p>
              ResearchClaimAI is a research claim analysis system
              designed to help users examine scientific claims using
              relevant research literature and structured evidence.
            </p>

          </div>

        </section>


        {/* =====================================================
            ABOUT CONTENT
        ===================================================== */}

        <section className="about-section">


          {/* ===================================================
              WHAT IS RESEARCHCLAIMAI?
          =================================================== */}

          <div className="about-card">

            <h2>
              What is ResearchClaimAI?
            </h2>


            <p>
              ResearchClaimAI helps users investigate a scientific
              claim by retrieving relevant research papers and
              analyzing the evidence contained in those papers.
              Instead of relying only on a simple search result,
              the system organizes the retrieved literature into
              research evidence that can be examined more easily.
            </p>


            <p>
              The current system retrieves papers from arXiv,
              extracts relevant research claims from their abstracts,
              and classifies the retrieved evidence into supporting,
              contradicting, or neutral categories.
            </p>

          </div>


          {/* ===================================================
              WHY RESEARCHCLAIMAI?
          =================================================== */}

          <div className="about-card">

            <h2>
              Why ResearchClaimAI?
            </h2>


            <p>
              Scientific information is spread across a large number
              of research papers, making it difficult to quickly
              determine whether a particular claim is strongly
              supported by available literature.
            </p>


            <p>
              ResearchClaimAI addresses this challenge by bringing
              literature retrieval, claim extraction, evidence
              comparison, and confidence estimation into a single
              workflow.
            </p>

          </div>


          {/* ===================================================
              HOW IT WORKS
          =================================================== */}

          <div className="about-card">

            <h2>
              How It Works
            </h2>


            <div className="workflow">


              {/* STEP 1 */}

              <div className="workflow-item">

                <span>
                  01
                </span>

                <h3>
                  Research Claim
                </h3>

                <p>
                  The user enters a research claim or topic that
                  they want to investigate.
                </p>

              </div>


              {/* STEP 2 */}

              <div className="workflow-item">

                <span>
                  02
                </span>

                <h3>
                  Literature Retrieval
                </h3>

                <p>
                  The system searches arXiv for relevant scientific
                  research papers related to the submitted claim.
                </p>

              </div>


              {/* STEP 3 */}

              <div className="workflow-item">

                <span>
                  03
                </span>

                <h3>
                  Paper Processing
                </h3>

                <p>
                  Retrieved papers are collected and their titles,
                  authors, abstracts, publication information, and
                  source links are prepared for analysis.
                </p>

              </div>


              {/* STEP 4 */}

              <div className="workflow-item">

                <span>
                  04
                </span>

                <h3>
                  Claim Extraction
                </h3>

                <p>
                  Relevant statements from the retrieved research
                  papers are extracted as individual research claims.
                </p>

              </div>


              {/* STEP 5 */}

              <div className="workflow-item">

                <span>
                  05
                </span>

                <h3>
                  Evidence Classification
                </h3>

                <p>
                  The extracted evidence is organized as supporting,
                  contradicting, or neutral with respect to the
                  submitted research claim.
                </p>

              </div>


              {/* STEP 6 */}

              <div className="workflow-item">

                <span>
                  06
                </span>

                <h3>
                  Confidence Scoring
                </h3>

                <p>
                  The available research evidence is summarized into
                  an overall confidence score for the analysis.
                </p>

              </div>


            </div>

          </div>


          {/* ===================================================
              SYSTEM OUTPUTS
          =================================================== */}

          <div className="about-card">

            <h2>
              What Does the System Provide?
            </h2>


            <div className="about-features">


              <div className="about-feature">

                <div className="about-feature-number">
                  01
                </div>

                <div>

                  <h3>
                    Retrieved Research Papers
                  </h3>

                  <p>
                    Displays the scientific papers retrieved for
                    the submitted research claim, including source
                    information and links to arXiv.
                  </p>

                </div>

              </div>


              <div className="about-feature">

                <div className="about-feature-number">
                  02
                </div>

                <div>

                  <h3>
                    Extracted Research Claims
                  </h3>

                  <p>
                    Shows important evidence statements extracted
                    from the retrieved research literature.
                  </p>

                </div>

              </div>


              <div className="about-feature">

                <div className="about-feature-number">
                  03
                </div>

                <div>

                  <h3>
                    Evidence Classification
                  </h3>

                  <p>
                    Groups research papers into supporting,
                    contradicting, and neutral evidence categories.
                  </p>

                </div>

              </div>


              <div className="about-feature">

                <div className="about-feature-number">
                  04
                </div>

                <div>

                  <h3>
                    Confidence Analysis
                  </h3>

                  <p>
                    Provides an overall confidence value based on
                    the available research evidence.
                  </p>

                </div>

              </div>


            </div>

          </div>


          {/* ===================================================
              OBJECTIVE
          =================================================== */}

          <div className="about-card">

            <h2>
              Our Objective
            </h2>


            <p>
              The objective of ResearchClaimAI is to make scientific
              claim analysis more accessible, structured, and
              transparent. By combining research retrieval with
              evidence extraction and classification, the system
              helps users understand the literature surrounding a
              claim without manually examining every retrieved paper
              from the beginning.
            </p>

          </div>


          {/* ===================================================
              PROJECT SCOPE
          =================================================== */}

          <div className="about-card">

            <h2>
              Current Scope
            </h2>


            <p>
              The current implementation focuses on research-paper
              retrieval from arXiv, claim extraction from paper
              abstracts, evidence categorization, and dashboard-based
              presentation of the results.
            </p>


            <p>
              The system is intended as a research-assistance tool.
              Its results should be interpreted together with the
              original scientific papers rather than treated as a
              replacement for expert research evaluation.
            </p>

          </div>


          {/* ===================================================
              MEET THE TEAM
          =================================================== */}

          <div className="about-card team-section">

            <h2>
              Meet the Team
            </h2>


            <p className="team-intro">
                 ResearchClaimAI was developed by our team as part of our project at the Department of Computer Science, CHRIST (Deemed to be) University.
            </p>


            <div className="team-grid">


              {/* =================================================
                  ADITHYA
              ================================================= */}

              <div className="team-card">

                <div className="team-image-wrapper">

                  <img
                  src="/team/Adithya.jpeg"
                    alt="Adithya Ajith"
                  className="team-image"
/>

                </div>


                <h3>
                  Adithya Ajith
                </h3>


                <p className="team-role">
                  Project Team Member
                </p>


                <p className="team-id">
                  2548439
                </p>

              </div>


              {/* =================================================
                  MALAVIKA
              ================================================= */}

              <div className="team-card">

                <div className="team-image-wrapper">

                  <img
                  src="/team/Malavika.jpeg"
                     alt="Malavika Krishna"
                         className="team-image"
                        />

                </div>


                <h3>
                  Malavika Krishna
                </h3>


                <p className="team-role">
                  Project Team Member
                </p>


                <p className="team-id">
                  2548416
                </p>

              </div>


              {/* =================================================
                  SHEETHAL
              ================================================= */}

              <div className="team-card">

                <div className="team-image-wrapper">

                  <img
                    src="/team/Sheethal.jpeg"
                       alt="Sheethal Krishna K K"
                      className="team-image"
                        />

                </div>


                <h3>
                  Sheethal Krishna K K
                </h3>


                <p className="team-role">
                  Project Team Member
                </p>


                <p className="team-id">
                  2548425
                </p>

              </div>


            </div>


           


          </div>


        </section>


      </main>


      <Footer />

    </>

  );

}


export default About;