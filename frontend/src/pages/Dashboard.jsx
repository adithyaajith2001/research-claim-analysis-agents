import { useContext } from "react";

import Navbar from "../components/layout/Navbar";
import Footer from "../components/layout/Footer";

import { AnalysisContext } from "../context/AnalysisContext";

import SummaryCard from "../components/dashboard/SummaryCard";
import AISummary from "../components/dashboard/AISummary";
import ConfidenceGauge from "../components/dashboard/ConfidenceGauge";

import "../styles/dashboard.css";


function Dashboard() {

  const { analysisData } = useContext(
    AnalysisContext
  );


  // =========================================================
  // DEBUG
  // =========================================================

  console.log(
    "======================================"
  );

  console.log(
    "DASHBOARD ANALYSIS DATA:"
  );

  console.log(
    analysisData
  );

  console.log(
    "======================================"
  );


  // =========================================================
  // TOPIC
  // =========================================================

  const topic =
    analysisData?.topic ||
    analysisData?.query ||
    "No topic analyzed";


  // =========================================================
  // RETRIEVED PAPERS
  // =========================================================

  const paperList =
    Array.isArray(
      analysisData?.paperList
    )
      ? analysisData.paperList
      : [];


  // =========================================================
  // PAPER COUNT
  // =========================================================

  const paperCount =
    Number.isFinite(
      Number(
        analysisData?.papers_retrieved
      )
    )
      ? Number(
          analysisData.papers_retrieved
        )
      : paperList.length;


  // =========================================================
  // RAW CONFIDENCE
  // =========================================================
  //
  // Backend confidence remains on a 0–10 scale.
  //
  // Example:
  //     7.83
  //
  // SummaryCard.jsx and ConfidenceGauge.jsx convert this
  // value to 78.3% using the shared confidence helper.
  // =========================================================

  const rawConfidence =
    Number(
      analysisData?.confidence
    ) || 0;


  // =========================================================
  // CLAIM COUNT
  // =========================================================

  const extractedClaims =
    Array.isArray(
      analysisData?.extractedClaims
    )
      ? analysisData.extractedClaims
      : [];


  const claims =
    Number.isFinite(
      Number(
        analysisData?.claimsExtracted
      )
    )
      ? Number(
          analysisData.claimsExtracted
        )
      : Number.isFinite(
          Number(
            analysisData?.claims
          )
        )
        ? Number(
            analysisData.claims
          )
        : extractedClaims.length;


  // =========================================================
  // EVIDENCE GROUPS
  // =========================================================

  const supportingPapers =
    Array.isArray(
      analysisData?.supportingPapers
    )
      ? analysisData.supportingPapers
      : [];


  const contradictingPapers =
    Array.isArray(
      analysisData?.contradictingPapers
    )
      ? analysisData.contradictingPapers
      : [];


  const neutralPapers =
    Array.isArray(
      analysisData?.neutralPapers
    )
      ? analysisData.neutralPapers
      : [];


  // =========================================================
  // CONTRADICTIONS
  // =========================================================

  const contradictions =
    Array.isArray(
      analysisData?.contradictions
    )
      ? analysisData.contradictions
      : [];


  // =========================================================
  // SUMMARY
  // =========================================================

  const summary =
    analysisData?.summary ||
    `Retrieved ${paperCount} research papers for "${topic}".`;


  // =========================================================
  // ALL CLAIM RECORDS
  // =========================================================
  //
  // Prefer extractedClaims from context.
  // If that is unavailable, use rawResponse.claims.
  //
  // This is important because the backend claim records contain
  // verification.supporting_evidence with paper-specific
  // similarity_score values.
  // =========================================================

  const claimRecords =
    extractedClaims.length > 0
      ? extractedClaims
      : Array.isArray(
          analysisData?.rawResponse?.claims
        )
        ? analysisData.rawResponse.claims
        : [];


  // =========================================================
  // FIND ORIGINAL PAPER
  // =========================================================

  const findOriginalPaper = (
    evidencePaper
  ) => {

    if (!evidencePaper) {
      return null;
    }


    // -------------------------------------------------------
    // Match by ID
    // -------------------------------------------------------

    if (
      evidencePaper.id !== undefined &&
      evidencePaper.id !== null
    ) {

      const matchById =
        paperList.find(
          paper =>
            String(
              paper?.id
            ) ===
            String(
              evidencePaper.id
            )
        );


      if (matchById) {
        return matchById;
      }

    }


    // -------------------------------------------------------
    // Match by paper_id
    // -------------------------------------------------------

    if (
      evidencePaper.paper_id
    ) {

      const matchByPaperId =
        paperList.find(
          paper =>
            String(
              paper?.id ||
              paper?.paper_id ||
              ""
            ) ===
            String(
              evidencePaper.paper_id
            )
        );


      if (matchByPaperId) {
        return matchByPaperId;
      }

    }


    // -------------------------------------------------------
    // Match by arXiv ID
    // -------------------------------------------------------

    if (
      evidencePaper.arxiv_id
    ) {

      const matchByArxiv =
        paperList.find(
          paper =>
            String(
              paper?.arxiv_id || ""
            ) ===
            String(
              evidencePaper.arxiv_id
            )
        );


      if (matchByArxiv) {
        return matchByArxiv;
      }

    }


    // -------------------------------------------------------
    // Match by title
    // -------------------------------------------------------

    if (
      evidencePaper.title ||
      evidencePaper.paper_title
    ) {

      const targetTitle =
        String(
          evidencePaper.title ||
          evidencePaper.paper_title ||
          ""
        ).trim();


      const matchByTitle =
        paperList.find(
          paper =>
            String(
              paper?.title || ""
            ).trim() ===
            targetTitle
        );


      if (matchByTitle) {
        return matchByTitle;
      }

    }


    return null;

  };


  // =========================================================
  // GET EVIDENCE SIMILARITY
  // =========================================================
  //
  // Supporting evidence normally has:
  //
  //     similarity_score: 0.776
  //
  // which becomes:
  //
  //     77.6%
  //
  // Neutral evidence may not contain the score directly.
  // In that case, find the corresponding claim by paper_id
  // and read its verification.supporting_evidence.
  // =========================================================

  const getEvidenceSimilarity = (
    evidencePaper
  ) => {

    if (!evidencePaper) {
      return 0;
    }


    // =======================================================
    // 1. DIRECT SIMILARITY SCORE
    // =======================================================

    const directSimilarity =
      Number(
        evidencePaper?.similarity_score
      );


    if (
      Number.isFinite(
        directSimilarity
      )
    ) {

      return Math.round(
        directSimilarity * 1000
      ) / 10;

    }


    // =======================================================
    // 2. IDENTIFY PAPER
    // =======================================================

    const targetPaperId =
      String(
        evidencePaper?.paper_id ||
        evidencePaper?.id ||
        ""
      );


    if (!targetPaperId) {
      return 0;
    }


    // =======================================================
    // 3. FIND CLAIM FOR SAME PAPER
    // =======================================================

    const matchingClaim =
      claimRecords.find(
        claim =>
          String(
            claim?.paper_id ||
            claim?.id ||
            ""
          ) ===
          targetPaperId
      );


    if (!matchingClaim) {
      return 0;
    }


    // =======================================================
    // 4. SEARCH VERIFICATION SUPPORTING EVIDENCE
    // =======================================================

    const verificationEvidence =
      Array.isArray(
        matchingClaim?.verification?.supporting_evidence
      )
        ? matchingClaim.verification.supporting_evidence
        : [];


    const matchingEvidence =
      verificationEvidence.find(
        item =>
          String(
            item?.paper_id ||
            ""
          ) ===
          targetPaperId
      );


    const verificationSimilarity =
      Number(
        matchingEvidence?.similarity_score
      );


    if (
      Number.isFinite(
        verificationSimilarity
      )
    ) {

      return Math.round(
        verificationSimilarity * 1000
      ) / 10;

    }


    // =======================================================
    // 5. NO SCORE AVAILABLE
    // =======================================================

    return 0;

  };


  // =========================================================
  // NORMALIZE EVIDENCE PAPER
  // =========================================================

  const normalizeEvidencePaper = (
    evidencePaper
  ) => {

    const originalPaper =
      findOriginalPaper(
        evidencePaper
      );


    return {

      ...(originalPaper || {}),

      ...(evidencePaper || {}),


      // -----------------------------------------------------
      // TITLE
      // -----------------------------------------------------

      title:
        evidencePaper?.title ||
        evidencePaper?.paper_title ||
        originalPaper?.title ||
        "Untitled Paper",


      // -----------------------------------------------------
      // AUTHORS
      // -----------------------------------------------------

      authors:
        Array.isArray(
          evidencePaper?.authors
        )
          ? evidencePaper.authors
          : Array.isArray(
              originalPaper?.authors
            )
            ? originalPaper.authors
            : [],


      // -----------------------------------------------------
      // ABSTRACT
      // -----------------------------------------------------

      abstract:
        evidencePaper?.abstract ||
        originalPaper?.abstract ||
        "",


      // -----------------------------------------------------
      // SOURCE URL
      // -----------------------------------------------------

      abs_url:
        evidencePaper?.abs_url ||
        evidencePaper?.source_url ||
        originalPaper?.abs_url ||
        originalPaper?.source_url ||
        "",


      // -----------------------------------------------------
      // RELEVANCE / SIMILARITY
      // -----------------------------------------------------

      relevance_score:
        getEvidenceSimilarity(
          evidencePaper
        ),


      // -----------------------------------------------------
      // EXTRACTED EVIDENCE
      // -----------------------------------------------------

      extracted_claims:
        Array.isArray(
          evidencePaper?.extracted_claims
        )
          ? evidencePaper.extracted_claims
          : []

    };

  };


  // =========================================================
  // EVIDENCE CARD
  // =========================================================

  const renderEvidencePaper = (
    paper,
    index,
    type
  ) => {

    const normalizedPaper =
      normalizeEvidencePaper(
        paper
      );


    const title =
      normalizedPaper.title;


    const authors =
      normalizedPaper.authors;


    const relevance =
      normalizedPaper.relevance_score;


    const extractedEvidence =
      normalizedPaper.extracted_claims;


    return (

      <div
        className="paper-item"
        key={
          normalizedPaper.paper_id ||
          normalizedPaper.id ||
          normalizedPaper.arxiv_id ||
          `${type}-${index}`
        }
      >


        {/* =================================================
            TITLE
        ================================================= */}

        <strong>
          {title}
        </strong>


        {/* =================================================
            AUTHORS
        ================================================= */}

        {authors.length > 0 && (

          <p>

            <strong>
              Authors:
            </strong>{" "}

            {authors.join(", ")}

          </p>

        )}


        {/* =================================================
            RELEVANCE
        ================================================= */}

        <p>

          <strong>
            Evidence Similarity:
          </strong>{" "}

          {Number(
            relevance
          ).toFixed(1)}%

        </p>


        {/* =================================================
            EXTRACTED EVIDENCE
        ================================================= */}

        {extractedEvidence.length > 0 && (

          <p>

            <strong>
              Evidence:
            </strong>{" "}

            {extractedEvidence[0]}

          </p>

        )}


        {/* =================================================
            SOURCE LINK
        ================================================= */}

        {normalizedPaper.abs_url && (

          <div>

            <a
              href={
                normalizedPaper.abs_url
              }
              target="_blank"
              rel="noopener noreferrer"
            >

              View on arXiv →

            </a>

          </div>

        )}

      </div>

    );

  };


  // =========================================================
  // RENDER
  // =========================================================

  return (

    <>

      <Navbar />


      <main className="dashboard-container">


        {/* =================================================
            RESEARCH TOPIC
        ================================================= */}

        <div className="dashboard-topic">

          <p>
            Research Claim
          </p>


          <h1>
            {topic}
          </h1>

        </div>


        {/* =================================================
            SUMMARY
        ================================================= */}

        <SummaryCard
          topic={topic}
          paperCount={paperCount}
          confidence={rawConfidence}
          claims={claims}
        />


        {/* =================================================
            AI SUMMARY
        ================================================= */}

        <AISummary
          topic={topic}
          paperCount={paperCount}
          confidence={rawConfidence}
          claims={claims}
          summary={summary}
        />


        {/* =================================================
            CONFIDENCE
        ================================================= */}

        <ConfidenceGauge
          confidence={rawConfidence}
          topic={topic}
        />


        {/* =================================================
            EVIDENCE OVERVIEW
        ================================================= */}

        <section className="dashboard-bottom">


          {/* =================================================
              SUPPORTING PAPERS
          ================================================= */}

          <div className="dashboard-card">

            <h2>
              🟢 Supporting Evidence
            </h2>


            <p>

              {supportingPapers.length} paper
              {supportingPapers.length !== 1
                ? "s"
                : ""}{" "}
              classified as supporting the claim.

            </p>


            {supportingPapers.length === 0 ? (

              <p>
                No supporting papers were identified.
              </p>

            ) : (

              supportingPapers.map(
                (paper, index) =>
                  renderEvidencePaper(
                    paper,
                    index,
                    "supporting"
                  )
              )

            )}

          </div>


          {/* =================================================
              CONTRADICTING PAPERS
          ================================================= */}

          <div className="dashboard-card">

            <h2>
              🔴 Contradicting Evidence
            </h2>


            <p>

              {contradictingPapers.length} paper
              {contradictingPapers.length !== 1
                ? "s"
                : ""}{" "}
              classified as contradicting.

            </p>


            {contradictingPapers.length === 0 ? (

              <p>
                The current analysis did not classify any evidence as contradicting. This does not establish that all research claims are consistent.
              </p>

            ) : (

              contradictingPapers.map(
                (paper, index) =>
                  renderEvidencePaper(
                    paper,
                    index,
                    "contradicting"
                  )
              )

            )}

          </div>


        </section>


        {/* =================================================
            NEUTRAL EVIDENCE
        ================================================= */}

        <section className="dashboard-card">

          <h2>
            ⚪ Neutral Evidence
          </h2>


          <p>

            {neutralPapers.length} paper
            {neutralPapers.length !== 1
              ? "s"
              : ""}{" "}
            classified as neutral or not directly
            related to the specific claim.

          </p>


          {neutralPapers.length === 0 ? (

            <p>
              No neutral papers were identified.
            </p>

          ) : (

            neutralPapers.map(
              (paper, index) =>
                renderEvidencePaper(
                  paper,
                  index,
                  "neutral"
                )
            )

          )}

        </section>


        {/* =================================================
            EXTRACTED CLAIMS
        ================================================= */}

        <section className="dashboard-card">

          <h2>
            🧠 Extracted Research Claims
          </h2>


          <p>

            {claims} claims were extracted
            from the retrieved research papers.

          </p>


          {extractedClaims.length === 0 ? (

            <p>
              No extracted claims available.
            </p>

          ) : (

            extractedClaims.map(
              (item, index) => (

                <div
                  className="paper-item"
                  key={
                    item?.claim_id ||
                    item?.paper_id ||
                    index
                  }
                >

                  <strong>
                    Claim {index + 1}
                  </strong>


                  <p>

                    {item?.claim ||
                      "No claim text available."}

                  </p>


                  <small>

                    Source:{" "}

                    {item?.paper_title ||
                      item?.source ||
                      "Unknown paper"}

                  </small>

                </div>

              )
            )

          )}

        </section>


        {/* =================================================
            CROSS-PAPER COMPARISONS
        ================================================= */}

      

          <section className="dashboard-card">

            <h2>
              🔎 Cross-Paper Comparisons
            </h2>

{contradictions.length === 0 ? (
  <p>
    No cross-paper comparison records were returned for this
    analysis. This does not prove that all research claims are
    consistent.
  </p>
) : (
  <p>
    {contradictions.length} cross-paper comparison record
    {contradictions.length !== 1 ? "s" : ""} were generated.
  </p>
)}
           


            {contradictions.map(
              (item, index) => (

                <div
                  className="paper-item"
                  key={
                    item?.id ||
                    `${item?.claim_a_id}-${item?.claim_b_id}` ||
                    index
                  }
                >

                  <strong>
                    Comparison {index + 1}
                  </strong>


                  <p>

                    <strong>
                      Relation:
                    </strong>{" "}

                    {item?.relation_type ||
                      item?.relation ||
                      "Unknown"}

                  </p>


                  {item?.severity && (

                    <p>

                      <strong>
                        Severity:
                      </strong>{" "}

                      {item.severity}

                    </p>

                  )}


                  {item?.claim_a_text && (

                    <p>

                      <strong>
                        Claim A:
                      </strong>{" "}

                      {item.claim_a_text}

                    </p>

                  )}


                  {item?.claim_b_text && (

                    <p>

                      <strong>
                        Claim B:
                      </strong>{" "}

                      {item.claim_b_text}

                    </p>

                  )}

                </div>

              )
            )}

          </section>

        


        {/* =================================================
            RETRIEVED RESEARCH PAPERS + STATISTICS
        ================================================= */}

        <section className="dashboard-bottom">


          {/* =================================================
              RETRIEVED RESEARCH PAPERS
          ================================================= */}

          <div className="dashboard-card">

            <h2>
              📚 Retrieved Research Papers
            </h2>


            {paperList.length === 0 ? (

              <p>
                No research papers were retrieved.
              </p>

            ) : (

              paperList.map(
                (paper, index) => (

                  <div
                    className="paper-item"
                    key={
                      paper?.id ||
                      paper?.arxiv_id ||
                      index
                    }
                  >

                    <strong>

                      {paper?.title ||
                        "Untitled Paper"}

                    </strong>


                    {/* AUTHORS */}

                    {Array.isArray(
                      paper?.authors
                    ) &&
                      paper.authors.length > 0 && (

                        <p>

                          <strong>
                            Authors:
                          </strong>{" "}

                          {paper.authors.join(
                            ", "
                          )}

                        </p>

                      )}


                    {/* ABSTRACT */}

                    {paper?.abstract && (

                      <p>
                        {paper.abstract}
                      </p>

                    )}


                    {/* YEAR */}

                    {paper?.year && (

                      <small>

                        Published:{" "}
                        {paper.year}

                      </small>

                    )}


                    {paper?.published_date &&
                      !paper?.year && (

                        <small>

                          Published:{" "}
                          {String(
                            paper.published_date
                          ).slice(0, 10)}

                        </small>

                      )}


                    {/* SOURCE LINK */}

                    {(
                      paper?.abs_url ||
                      paper?.source_url
                    ) && (

                      <div>

                        <a
                          href={
                            paper.abs_url ||
                            paper.source_url
                          }
                          target="_blank"
                          rel="noopener noreferrer"
                        >

                          View on arXiv →

                        </a>

                      </div>

                    )}

                  </div>

                )
              )

            )}

          </div>


          {/* =================================================
              RESEARCH STATISTICS
          ================================================= */}

          <div className="dashboard-card">

            <h2>
              📊 Research Statistics
            </h2>


            <div className="stats">


              <div className="stat">

                <h3>
                  {paperCount}
                </h3>

                <p>
                  Papers Retrieved
                </p>

              </div>


              <div className="stat">

                <h3>
                  {rawConfidence}/10
                </h3>

                <p>
                  Confidence
                </p>

              </div>


              <div className="stat">

                <h3>
                  {claims}
                </h3>

                <p>
                  Claims Extracted
                </p>

              </div>


              <div className="stat">

                <h3>
                  2.4s
                </h3>

                <p>
                  Analysis Time
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


export default Dashboard;