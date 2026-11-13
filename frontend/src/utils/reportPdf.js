import { jsPDF } from "jspdf";
import autoTable from "jspdf-autotable";

import {
  SCORE_WEIGHTS,
  levelInfo,
  formatScore,
  formatSeconds,
  claimVerdict,
  formatValue,
  sourceCount,
  SINGLE_SOURCE_NOTE,
  isSubsetClaim,
  SUBSET_NOTE
} from "./reportHelpers";

const BLUE = [12, 83, 148];
const INK = [30, 36, 54];
const MUTED = [100, 108, 130];

function safeFileName(text) {
  return (
    String(text || "report")
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, "-")
      .replace(/^-+|-+$/g, "")
      .slice(0, 50) || "report"
  );
}

export function downloadReportPdf(analysisData) {
  const data = analysisData || {};

  const claims = Array.isArray(data.extractedClaims) ? data.extractedClaims : [];
  const papers = Array.isArray(data.paperList) ? data.paperList : [];
  const comparisons = Array.isArray(data.contradictions) ? data.contradictions : [];
  const breakdown = data.confidenceBreakdown || {};
  const models = Array.isArray(data.queryModels) ? data.queryModels : [];

  const doc = new jsPDF({ unit: "pt", format: "a4" });
  const pageWidth = doc.internal.pageSize.getWidth();
  const pageHeight = doc.internal.pageSize.getHeight();
  const margin = 44;
  const textWidth = pageWidth - margin * 2;

  let y = margin;

  const ensureSpace = (needed) => {
    if (y + needed > pageHeight - margin) {
      doc.addPage();
      y = margin;
    }
  };

  const heading = (text) => {
    ensureSpace(40);
    doc.setFont("helvetica", "bold");
    doc.setFontSize(14);
    doc.setTextColor(...BLUE);
    doc.text(text, margin, y);
    y += 18;
  };

  const paragraph = (text, size = 10.5, color = INK, bold = false) => {
    doc.setFont("helvetica", bold ? "bold" : "normal");
    doc.setFontSize(size);
    doc.setTextColor(...color);
    const lines = doc.splitTextToSize(String(text), textWidth);
    ensureSpace(lines.length * (size + 4));
    doc.text(lines, margin, y);
    y += lines.length * (size + 4) + 4;
  };

  const afterTable = () => {
    y = doc.lastAutoTable.finalY + 22;
  };

  // ---------- Title ----------
  doc.setFillColor(...BLUE);
  doc.rect(0, 0, pageWidth, 70, "F");
  doc.setFont("helvetica", "bold");
  doc.setFontSize(20);
  doc.setTextColor(255, 255, 255);
  doc.text("ResearchClaimAI", margin, 36);
  doc.setFont("helvetica", "normal");
  doc.setFontSize(11);
  doc.text("Research claim analysis report", margin, 54);
  y = 98;

  paragraph(data.topic || "Untitled analysis", 15, INK, true);
  paragraph(
    `${papers.length} ${papers.length === 1 ? "paper" : "papers"} · ` +
      `${claims.length} ${claims.length === 1 ? "claim" : "claims"} · ` +
      `analysed in ${formatSeconds(data.analysisSeconds)} · ` +
      new Date().toLocaleDateString(),
    10,
    MUTED
  );
  y += 6;

  // ---------- Summary ----------
  const modelLabel = models.join(", ");
  const noClaims = claims.length === 0;
  const info = levelInfo(data.confidenceLevel);

  heading("Summary");

  if (noClaims) {
    paragraph(
      modelLabel
        ? `No results found for ${modelLabel}. The papers found did not report a result for this model that we could verify, so no score is given.`
        : "No numeric benchmark claims were found in these papers, so no score is given.",
      11,
      INK,
      true
    );
  } else {
    paragraph(
      `Overall confidence: ${Number(data.confidence || 0).toFixed(1)} / 10 (${info.label})`,
      12,
      INK,
      true
    );
    paragraph(info.text);
    if (comparisons.length === 0 && sourceCount(claims) <= 1) {
      paragraph(SINGLE_SOURCE_NOTE, 10, MUTED);
    }
  }

  y += 4;

  // ---------- Score breakdown ----------
  if (!noClaims) {
    heading("How the score was built");

    autoTable(doc, {
      startY: y,
      margin: { left: margin, right: margin },
      head: [["Check", "Weight", "Score"]],
      body: SCORE_WEIGHTS.map((item) => [
        item.label,
        `${item.weight}%`,
        `${formatScore(breakdown[item.key])} / 10`
      ]),
      headStyles: { fillColor: BLUE },
      styles: { fontSize: 10, cellPadding: 6 }
    });
    afterTable();
  }

  // ---------- Claims ----------
  heading("Claims found");

  if (noClaims) {
    paragraph("No claims to list.", 10, MUTED);
  } else {
    if (claims.some(isSubsetClaim)) {
      paragraph(SUBSET_NOTE, 10, MUTED);
    }

    autoTable(doc, {
      startY: y,
      margin: { left: margin, right: margin },
      head: [["Claim", "Model", "Result", "Strength", "Verdict"]],
      body: claims.map((claim) => [
        claim.claim || "",
        claim.model_name || "-",
        formatValue(claim),
        `${formatScore(claim.evidence_strength_score)} / 10`,
        claimVerdict(claim).label
      ]),
      headStyles: { fillColor: BLUE },
      styles: { fontSize: 9, cellPadding: 5, overflow: "linebreak" },
      columnStyles: { 0: { cellWidth: 190 } }
    });
    afterTable();
  }

  // ---------- Comparisons ----------
  heading("Cross-paper comparisons");

  if (comparisons.length === 0) {
    paragraph(
      "No comparable results were found, so nothing could be confirmed or contradicted across papers. This does not mean the claims are consistent.",
      10,
      MUTED
    );
  } else {
    autoTable(doc, {
      startY: y,
      margin: { left: margin, right: margin },
      head: [["Model / benchmark", "Paper A", "Paper B", "Gap", "Verdict"]],
      body: comparisons.map((item) => [
        `${item.model_name || "Same model"} / ${item.benchmark_name || ""}`,
        item.reported_value_a,
        item.reported_value_b,
        item.value_diff,
        item.relation_type === "Agrees" ? "Agrees" : "Contradicts"
      ]),
      headStyles: { fillColor: BLUE },
      styles: { fontSize: 9, cellPadding: 5 }
    });
    afterTable();
  }

  // ---------- Papers ----------
  heading("Papers analysed");

  papers.forEach((paper, index) => {
    paragraph(`${index + 1}. ${paper.title || "Untitled"}`, 10.5, INK, true);

    const meta = [paper.authors, paper.year, paper.source].filter(Boolean).join(" · ");
    if (meta) paragraph(meta, 9, MUTED);

    const link = paper.url || paper.pdf_url;
    if (link) paragraph(link, 9, BLUE);
  });

  // ---------- Footer ----------
  const pages = doc.getNumberOfPages();
  for (let page = 1; page <= pages; page += 1) {
    doc.setPage(page);
    doc.setFont("helvetica", "normal");
    doc.setFontSize(8.5);
    doc.setTextColor(...MUTED);
    doc.text(
      "Generated by ResearchClaimAI. Scores are automated estimates; check the source papers.",
      margin,
      pageHeight - 20
    );
    doc.text(`Page ${page} of ${pages}`, pageWidth - margin, pageHeight - 20, { align: "right" });
  }

  doc.save(`researchclaimai-${safeFileName(data.topic)}.pdf`);
}
