import { useContext } from "react";

import { AnalysisContext } from "../../context/AnalysisContext";

import { confidenceToPercentage } from "../../utils/confidence";

import "../../styles/dashboard.css";


function ConfidenceGauge() {

    const { analysisData } =
        useContext(AnalysisContext);


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
    // PAPERS
    // =====================================================

    const papers =
        Number(
            analysisData?.papers_retrieved ??
            analysisData?.papers ??
            0
        ) || 0;


    // =====================================================
    // CLAIMS
    // =====================================================

    const claims =
        Number(
            analysisData?.claimsExtracted ??
            analysisData?.claims ??
            0
        ) || 0;


    // =====================================================
    // RENDER
    // =====================================================

    return (

        <section className="confidence-section">


            <h2>
                Confidence Analysis
            </h2>


            <div className="gauge-card">


                {/* =================================================
                    GAUGE
                ================================================= */}

                <div
                    className="gauge"
                    style={{
                        background: `conic-gradient(
                            #2563eb ${confidence}%,
                            #dbeafe 0
                        )`
                    }}
                >

                    <div className="gauge-inner">

                        <span>

                            {confidence}%

                        </span>

                    </div>

                </div>


                {/* =================================================
                    INFORMATION
                ================================================= */}

                <div className="gauge-info">


                    <h3>

                        {status}

                    </h3>


                    <p>

                        The analyzed literature provides
                        an overall confidence of{" "}

                        <strong>

                            {confidence}%

                        </strong>{" "}

                        based on the available research
                        evidence.

                    </p>


                    <ul>


                        <li>

                            ✔ Research Papers Analyzed :{" "}
                            {papers}

                        </li>


                        <li>

                            ✔ Verified Claims :{" "}
                            {claims}

                        </li>


                        <li>

                            ✔ Overall Evidence Status :{" "}
                            {status}

                        </li>


                    </ul>


                </div>


            </div>

        </section>

    );

}


export default ConfidenceGauge;