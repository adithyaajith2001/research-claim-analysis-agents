import { createContext, useState } from "react";

export const AnalysisContext = createContext();

export function AnalysisProvider({ children }) {

    const [analysisData, setAnalysisData] = useState({

        // =====================================================
        // RESEARCH TOPIC / CLAIM
        // =====================================================

        topic: "",


        // =====================================================
        // ANALYSIS RESULTS
        // =====================================================

        confidence: 0,

        confidenceLevel: "Low",

        confidenceBreakdown: {},

        papers: 0,

        papers_retrieved: 0,

        claims: 0,

        claimsExtracted: 0,


        // =====================================================
        // ACTUAL RETRIEVED PAPERS
        // =====================================================

        paperList: [],


        // =====================================================
        // EXTRACTED CLAIMS
        // =====================================================

        extractedClaims: [],


        // =====================================================
        // EVIDENCE GROUPS
        // =====================================================

        supportingPapers: [],

        contradictingPapers: [],

        neutralPapers: [],


        // =====================================================
        // CONTRADICTIONS
        // =====================================================

        contradictions: [],


        // =====================================================
        // AI SUMMARY
        // =====================================================

        summary: "",


        // =====================================================
        // RAW BACKEND RESPONSE
        // =====================================================

        rawResponse: null,


        // =====================================================
        // STATUS
        // =====================================================

        status: "Not Analyzed",


        // =====================================================
        // ANALYSIS STATE
        // =====================================================

        isAnalyzing: false

    });


    // =========================================================
    // START ANALYSIS
    // =========================================================

    const startAnalysis = (topic) => {

        setAnalysisData({

            topic: topic,

            confidence: 0,

            confidenceLevel: "Low",

            confidenceBreakdown: {},

            papers: 0,

            papers_retrieved: 0,

            claims: 0,

            claimsExtracted: 0,

            paperList: [],

            extractedClaims: [],

            supportingPapers: [],

            contradictingPapers: [],

            neutralPapers: [],

            contradictions: [],

            summary: "",

            rawResponse: null,

            status: "Analyzing",

            isAnalyzing: true

        });

    };


    // =========================================================
    // UPDATE ANALYSIS DATA
    // =========================================================

    const updateAnalysisData = (newData) => {

        setAnalysisData((previousData) => ({

            ...previousData,

            ...newData,

            isAnalyzing: false

        }));

    };


    // =========================================================
    // PROVIDER
    // =========================================================

    return (

        <AnalysisContext.Provider
            value={{
                analysisData,
                setAnalysisData,
                startAnalysis,
                updateAnalysisData
            }}
        >

            {children}

        </AnalysisContext.Provider>

    );

}