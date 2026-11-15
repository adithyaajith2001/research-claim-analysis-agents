import { useState } from "react";
import { Link } from "react-router-dom";
import {
  FaSearch,
  FaArrowRight,
  FaCheckCircle,
  FaLayerGroup,
  FaTable,
  FaBullseye,
  FaBalanceScale,
  FaChartLine,
  FaFilePdf,
  FaHistory,
  FaBookOpen,
  FaShieldAlt
} from "react-icons/fa";

import Navbar from "../components/layout/Navbar";
import Footer from "../components/layout/Footer";
import useStartAnalysis from "../hooks/useStartAnalysis";

import "../styles/landing.css";

const EXAMPLES = [
  "MMLU accuracy of Mistral 7B",
  "GSM8K accuracy of Mistral 7B",
  "HumanEval score of Llama 2 7B",
  "MMLU accuracy of GPT-4"
];

const STEPS = [
  {
    title: "Retrieve",
    text: "Searches arXiv, Semantic Scholar and CrossRef at the same time and ranks papers by how well they match your question."
  },
  {
    title: "Extract",
    text: "Reads abstracts and the full PDF, including results tables, and pulls out numeric benchmark claims."
  },
  {
    title: "Verify",
    text: "Checks every claim against the paper's own text and shows the exact sentence it relied on."
  },
  {
    title: "Cross-check",
    text: "Compares papers only when they report the same model on the same benchmark and setting."
  },
  {
    title: "Score",
    text: "Combines the checks into one confidence score you can break down and explain."
  }
];

const FEATURES = [
  {
    icon: FaLayerGroup,
    title: "Three sources, one search",
    text: "arXiv, Semantic Scholar and CrossRef are queried in parallel so one slow source never holds you up."
  },
  {
    icon: FaTable,
    title: "Reads results tables",
    text: "Benchmark numbers usually live in PDF tables. We read them, not just the abstract."
  },
  {
    icon: FaBullseye,
    title: "Answers the model you asked about",
    text: "Ask about Mistral 7B and you get Mistral 7B, not a neighbouring model with a similar name."
  },
  {
    icon: FaBalanceScale,
    title: "Finds contradictions",
    text: "When two papers disagree on the same benchmark, the gap is flagged instead of averaged away."
  },
  {
    icon: FaChartLine,
    title: "A score you can explain",
    text: "Strength, verification, agreement and skepticism are weighted and shown, so nothing is a black box."
  },
  {
    icon: FaFilePdf,
    title: "Export as PDF",
    text: "Download a clean report with the score, every claim and its source, ready to attach to your notes."
  }
];

const WEIGHTS = [
  { label: "Evidence strength", value: 40 },
  { label: "Verification in paper", value: 30 },
  { label: "Cross-paper agreement", value: 20 },
  { label: "Skeptic check", value: 10 }
];

function Home() {
  const [query, setQuery] = useState("");
  const startAnalysis = useStartAnalysis();

  const submit = (event) => {
    event.preventDefault();
    startAnalysis(query);
  };

  return (
    <>
      <Navbar />

      <main className="lp">
        {/* ---------------- HERO ---------------- */}
        <section className="lp-hero">
          <div className="lp-glow lp-glow-a" aria-hidden="true" />
          <div className="lp-glow lp-glow-b" aria-hidden="true" />

          <div className="lp-hero-copy">
            <span className="lp-pill">
              <span className="lp-dot" /> Multi-agent research verification
            </span>

            <h1>
              Don't just trust a number in a paper.
              <span> Verify it.</span>
            </h1>

            <p className="lp-lead">
              Ask about a model and a benchmark. ResearchClaimAI finds the
              papers, reads their tables, checks each claim against the
              source and tells you how far to trust it, in about a minute.
            </p>

            <form className="lp-search" onSubmit={submit}>
              <FaSearch className="lp-search-icon" aria-hidden="true" />
              <input
                type="text"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="e.g. MMLU accuracy of Mistral 7B"
                aria-label="Research question"
              />
              <button type="submit" disabled={!query.trim()}>
                Analyze <FaArrowRight />
              </button>
            </form>

            <div className="lp-examples">
              <span>Try:</span>
              {EXAMPLES.map((example) => (
                <button
                  key={example}
                  type="button"
                  onClick={() => startAnalysis(example)}
                >
                  {example}
                </button>
              ))}
            </div>
          </div>

          {/* Example report (static illustration) */}
          <div className="lp-hero-visual">
            <div className="lp-report" aria-label="Example report">
              <div className="lp-report-top">
                <span className="lp-tag">Example report</span>
                <span className="lp-report-time">analysed in 1 min</span>
              </div>

              <h3>MMLU accuracy of Mistral 7B</h3>

              <div className="lp-claim">
                <div>
                  <small>Mistral 7B · MMLU</small>
                  <strong>60.1%</strong>
                </div>
                <span className="lp-verdict">
                  <FaCheckCircle /> Found in paper
                </span>
              </div>

              <div className="lp-source">
                Read from the paper's results table
                <small>Source: Mistral 7B paper (arXiv)</small>
              </div>

              <div className="lp-chips">
                <span>Model matched</span>
                <span>Benchmark matched</span>
                <span>Checked in text</span>
              </div>

              <div className="lp-note">
                <FaShieldAlt /> Single source: confirm with a second paper.
              </div>
            </div>
          </div>
        </section>

        {/* ---------------- FACT STRIP ---------------- */}
        <section className="lp-facts" aria-label="At a glance">
          <div><strong>3</strong><span>paper sources searched together</span></div>
          <div><strong>~1 min</strong><span>for a typical analysis</span></div>
          <div><strong>5</strong><span>agents check every claim</span></div>
          <div><strong>PDF</strong><span>report you can download</span></div>
        </section>

        {/* ---------------- HOW IT WORKS ---------------- */}
        <section className="lp-section" id="how">
          <header className="lp-head">
            <span className="lp-eyebrow">How it works</span>
            <h2>From question to verified answer in five steps</h2>
            <p>
              Each step is handled by its own agent, and each one can be
              inspected in your report.
            </p>
          </header>

          <ol className="lp-steps">
            {STEPS.map((step, index) => (
              <li key={step.title}>
                <span className="lp-step-num">{index + 1}</span>
                <h3>{step.title}</h3>
                <p>{step.text}</p>
              </li>
            ))}
          </ol>
        </section>

        {/* ---------------- FEATURES ---------------- */}
        <section className="lp-section">
          <header className="lp-head">
            <span className="lp-eyebrow">What you get</span>
            <h2>Built for people who need to cite with confidence</h2>
          </header>

          <div className="lp-grid">
            {FEATURES.map(({ icon: Icon, title, text }) => (
              <article key={title} className="lp-card">
                <span className="lp-icon"><Icon /></span>
                <h3>{title}</h3>
                <p>{text}</p>
              </article>
            ))}
          </div>
        </section>

        {/* ---------------- SCORE EXPLAINER ---------------- */}
        <section className="lp-section lp-split">
          <div className="lp-split-copy">
            <span className="lp-eyebrow">Explainable by design</span>
            <h2>A confidence score that shows its working</h2>
            <p>
              Every score is a weighted mix of four checks. You can see how
              much each one contributed, so you know why a claim got a High,
              Medium or Low rating.
            </p>
            <ul className="lp-ticks">
              <li><FaCheckCircle /> High is 8 out of 10 or more, Medium is 6 or more</li>
              <li><FaCheckCircle /> Single-source results are labelled as such</li>
              <li><FaCheckCircle /> Results for other models are listed, never mixed in</li>
            </ul>
          </div>

          <div className="lp-weights">
            {WEIGHTS.map((item) => (
              <div key={item.label} className="lp-weight">
                <div className="lp-weight-head">
                  <span>{item.label}</span>
                  <strong>{item.value}%</strong>
                </div>
                <div className="lp-bar">
                  <i style={{ width: `${item.value * 2.2}%` }} />
                </div>
              </div>
            ))}
          </div>
        </section>

        {/* ---------------- HONESTY ---------------- */}
        <section className="lp-honest">
          <FaBookOpen className="lp-honest-icon" aria-hidden="true" />
          <div>
            <h2>It tells you when it can't find the answer</h2>
            <p>
              If no paper reports your model on your benchmark, you get a
              clear "No results found" and the closest related results for
              context. Never a made-up number.
            </p>
          </div>
          <Link to="/analysis" className="lp-btn-ghost">
            See it in action <FaArrowRight />
          </Link>
        </section>

        {/* ---------------- HISTORY + CTA ---------------- */}
        <section className="lp-cta">
          <FaHistory className="lp-cta-icon" aria-hidden="true" />
          <h2>Ready to check your first claim?</h2>
          <p>
            Your searches are saved to your account, so you can reopen a
            report or run it again any time.
          </p>
          <div className="lp-cta-actions">
            <Link to="/analysis" className="lp-btn">
              Start an analysis <FaArrowRight />
            </Link>
            <Link to="/about" className="lp-btn-ghost">
              Learn more
            </Link>
          </div>
        </section>
      </main>

      <Footer />
    </>
  );
}

export default Home;
