// Shared by the dashboard page and the PDF report.

export const SCORE_WEIGHTS = [
  {
    key: "Evidence Strength",
    label: "Evidence strength",
    weight: 40,
    help: "How convincing the evidence is: clear results on a trusted benchmark."
  },
  {
    key: "Verification",
    label: "Verification",
    weight: 30,
    help: "Whether the paper's own text backs up the claim."
  },
  {
    key: "Contradiction",
    label: "Agreement with other papers",
    weight: 20,
    help: "Whether other papers report the same result for the same model."
  },
  {
    key: "Skeptic",
    label: "Skeptic review",
    weight: 10,
    help: "A simple keyword check for doubtful or contradicting wording. A high score only means none was found; it is a limited signal."
  }
];

export function levelInfo(level) {
  const value = String(level || "Low").toLowerCase();

  if (value === "high") {
    return {
      tone: "high",
      label: "High confidence",
      headline: "Strong supporting evidence",
      text: "The claims found match their source papers and the evidence behind them is strong."
    };
  }

  if (value === "medium") {
    return {
      tone: "medium",
      label: "Medium confidence",
      headline: "Moderate evidence: check the details",
      text: "The claims match what their papers say, but the evidence has gaps and was not confirmed by other papers. Review each claim before relying on it."
    };
  }

  return {
    tone: "low",
    label: "Low confidence",
    headline: "Weak or limited evidence",
    text: "The evidence found is limited. Treat these claims with caution."
  };
}

export function scoreTone(score) {
  const value = Number(score);

  if (!Number.isFinite(value)) return "none";
  if (value >= 7) return "high";
  if (value >= 5) return "medium";
  return "low";
}

// Shows one decimal, or two when one decimal would hide which side of a
// confidence boundary (6 and 8) the score is on. 5.96 must not read as 6.0
// next to a "Low" label.
export function formatScore(score) {
  const value = Number(score);
  if (!Number.isFinite(value)) return "-";

  const oneDecimal = value.toFixed(1);
  const crossesBoundary = [6, 8].some(
    (edge) => value < edge && Number(oneDecimal) >= edge
  );

  return crossesBoundary ? value.toFixed(2) : oneDecimal;
}

export function formatSeconds(totalSeconds) {
  const seconds = Math.round(Number(totalSeconds));

  if (!Number.isFinite(seconds) || seconds <= 0) return "-";

  const minutes = Math.floor(seconds / 60);
  const rest = seconds % 60;

  return minutes > 0 ? `${minutes}m ${rest}s` : `${rest}s`;
}

export function claimVerdict(claim) {
  const verification = claim?.verification || {};

  if ((verification.supporting_evidence || []).length > 0) {
    return { tone: "high", label: "Found in paper" };
  }

  if ((verification.weak_evidence || []).length > 0) {
    return { tone: "medium", label: "Weak match" };
  }

  const score = Number(claim?.verification_score);

  if (Number.isFinite(score)) {
    if (score >= 7.5) return { tone: "high", label: "Found in paper" };
    if (score >= 4.5) return { tone: "medium", label: "Weak match" };
  }

  return { tone: "low", label: "Not found in paper" };
}

export function claimSourceText(claim) {
  const verification = claim?.verification || {};

  const first =
    (verification.supporting_evidence || [])[0] ||
    (verification.evidence_results || [])[0] ||
    (verification.weak_evidence || [])[0];

  return first?.evidence || "";
}

export function formatValue(claim) {
  const value = Number(claim?.reported_value);

  if (!Number.isFinite(value)) return "-";

  const isScore = String(claim?.value_type || "").includes("accuracy");

  return isScore ? `${value}%` : String(value);
}


// Number of different papers the claims come from.
export function sourceCount(claims) {
  return new Set((claims || []).map((claim) => claim.paper_id ?? claim.paper_title)).size;
}

export const SINGLE_SOURCE_NOTE =
  "Single source: these results come from one paper and were not confirmed by another paper, so treat the score as provisional.";

// True when a claim is about one part of a benchmark (for example the
// "Clinical Knowledge" sub-component of MMLU) rather than the whole score.
export function isSubsetClaim(claim) {
  return /sub-?components?|sub-?sets?|sub-?tasks?|sub-?categor|sub-?jects?/i.test(
    String(claim?.claim || "")
  );
}

export const SUBSET_NOTE =
  "Some results below are for one part of a benchmark (for example the Clinical Knowledge section of MMLU), not the full benchmark score. They should not be read as the overall number.";
