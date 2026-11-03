// ============================================================
// CONFIDENCE UTILITY
// ============================================================
// Backend confidence:
//     0  - 10
//
// Frontend display:
//     0  - 100%
//
// Example:
//     7.83 -> 78.3%
// ============================================================

export function confidenceToPercentage(score) {

    const numericScore =
        Number(score);

    // --------------------------------------------------------
    // Invalid / missing value
    // --------------------------------------------------------

    if (!Number.isFinite(numericScore)) {
        return 0;
    }


    // --------------------------------------------------------
    // Keep backend score inside the expected 0–10 range
    // --------------------------------------------------------

    const clampedScore =
        Math.min(
            Math.max(
                numericScore,
                0
            ),
            10
        );


    // --------------------------------------------------------
    // Convert 0–10 to 0–100
    // --------------------------------------------------------

    const percentage =
        clampedScore * 10;


    // --------------------------------------------------------
    // Keep one decimal place
    // --------------------------------------------------------

    return Math.round(
        percentage * 10
    ) / 10;
}