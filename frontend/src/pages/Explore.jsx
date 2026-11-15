import { useMemo, useState } from "react";
import { FaSearch, FaBolt, FaBookOpen, FaInfoCircle } from "react-icons/fa";

import Navbar from "../components/layout/Navbar";
import Footer from "../components/layout/Footer";
import useStartAnalysis from "../hooks/useStartAnalysis";

import "../styles/explore.css";

// Models whose own paper is built in, so their results tables are always
// available to the analysis.
const MODELS = [
  { name: "Mistral 7B", org: "Mistral AI", year: 2023, kind: "Open weights",
    benchmarks: ["MMLU", "GSM8K", "HumanEval", "HellaSwag", "ARC"] },
  { name: "Mixtral 8x7B", org: "Mistral AI", year: 2024, kind: "Open weights",
    benchmarks: ["MMLU", "GSM8K", "HumanEval", "HellaSwag", "ARC"] },
  { name: "Llama 2 7B", org: "Meta", year: 2023, kind: "Open weights",
    benchmarks: ["MMLU", "GSM8K", "HumanEval", "HellaSwag", "ARC"] },
  { name: "Llama 2 13B", org: "Meta", year: 2023, kind: "Open weights",
    benchmarks: ["MMLU", "GSM8K", "HumanEval", "HellaSwag", "ARC"] },
  { name: "Llama 2 70B", org: "Meta", year: 2023, kind: "Open weights",
    benchmarks: ["MMLU", "GSM8K", "HumanEval", "HellaSwag", "ARC"] },
  { name: "Llama 3 8B", org: "Meta", year: 2024, kind: "Open weights",
    benchmarks: ["MMLU", "GSM8K", "HumanEval", "ARC"] },
  { name: "GPT-4", org: "OpenAI", year: 2023, kind: "Closed",
    benchmarks: ["MMLU", "GSM8K", "HumanEval", "HellaSwag", "ARC"] },
  { name: "Gemma 2 27B", org: "Google", year: 2024, kind: "Open weights",
    benchmarks: ["MMLU", "GSM8K", "HumanEval", "HellaSwag", "ARC"] },
  { name: "Gemma 3 27B", org: "Google", year: 2025, kind: "Open weights",
    benchmarks: ["MMLU", "GSM8K", "HumanEval"] },
  { name: "Gemini 1.5 Pro", org: "Google", year: 2024, kind: "Closed",
    benchmarks: ["MMLU", "GSM8K", "HumanEval"] },
  { name: "Qwen2.5 7B", org: "Alibaba", year: 2024, kind: "Open weights",
    benchmarks: ["MMLU", "GSM8K", "HumanEval"] },
  { name: "Phi-3 mini", org: "Microsoft", year: 2024, kind: "Open weights",
    benchmarks: ["MMLU", "GSM8K", "HumanEval", "HellaSwag", "ARC"] },
  { name: "DeepSeek-V3", org: "DeepSeek", year: 2024, kind: "Open weights",
    benchmarks: ["MMLU", "GSM8K", "HumanEval"] }
];

const BENCHMARKS = [
  { name: "MMLU", what: "57 school and professional subjects, from law to physics. A broad test of knowledge.", word: "accuracy" },
  { name: "GSM8K", what: "Grade-school maths word problems that need several steps of reasoning.", word: "accuracy" },
  { name: "HumanEval", what: "164 coding problems. A solution counts only if it passes the tests.", word: "score" },
  { name: "HellaSwag", what: "Pick the most sensible ending to an everyday scenario. Tests common sense.", word: "accuracy" },
  { name: "ARC", what: "Science questions from school exams, with a harder Challenge set.", word: "accuracy" }
];

const WORD = Object.fromEntries(BENCHMARKS.map((b) => [b.name, b.word]));

function Explore() {
  const [search, setSearch] = useState("");
  const [benchmark, setBenchmark] = useState("All");
  const startAnalysis = useStartAnalysis();

  const visible = useMemo(() => {
    const needle = search.trim().toLowerCase();

    return MODELS.filter((model) => {
      const matchesText =
        !needle ||
        model.name.toLowerCase().includes(needle) ||
        model.org.toLowerCase().includes(needle);
      const matchesBenchmark =
        benchmark === "All" || model.benchmarks.includes(benchmark);
      return matchesText && matchesBenchmark;
    });
  }, [search, benchmark]);

  const run = (model, bench) =>
    startAnalysis(`${bench} ${WORD[bench] || "accuracy"} of ${model}`);

  return (
    <>
      <Navbar />

      <main className="ex">
        <header className="ex-hero">
          <span className="ex-pill"><FaBolt /> One click, no typing</span>
          <h1>
            Explore models and <span>benchmarks</span>
          </h1>
          <p>
            Pick a model and a benchmark. We find the papers, read their
            results tables and check the number for you. Models below have
            their own paper built in, so the original results are always
            looked up.
          </p>

          <div className="ex-tools">
            <label className="ex-search">
              <FaSearch aria-hidden="true" />
              <input
                type="text"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="Search a model or company, e.g. Llama or Google"
                aria-label="Search models"
              />
            </label>

            <div className="ex-filters" role="group" aria-label="Filter by benchmark">
              {["All", ...BENCHMARKS.map((b) => b.name)].map((name) => (
                <button
                  key={name}
                  type="button"
                  className={benchmark === name ? "on" : ""}
                  aria-pressed={benchmark === name}
                  onClick={() => setBenchmark(name)}
                >
                  {name}
                </button>
              ))}
            </div>
          </div>
        </header>

        <section className="ex-section" aria-label="Models">
          <div className="ex-count">
            {visible.length} model{visible.length === 1 ? "" : "s"}
            {benchmark !== "All" ? ` reported on ${benchmark}` : ""}
          </div>

          {visible.length === 0 ? (
            <div className="ex-empty">
              <p>No model matches that search.</p>
              <button type="button" onClick={() => { setSearch(""); setBenchmark("All"); }}>
                Clear filters
              </button>
            </div>
          ) : (
            <div className="ex-grid">
              {visible.map((model) => (
                <article key={model.name} className="ex-card">
                  <div className="ex-card-top">
                    <span className="ex-avatar" aria-hidden="true">
                      {model.name.charAt(0)}
                    </span>
                    <div>
                      <h3>{model.name}</h3>
                      <small>{model.org} · {model.year}</small>
                    </div>
                    <span className={model.kind === "Closed" ? "ex-kind closed" : "ex-kind"}>
                      {model.kind}
                    </span>
                  </div>

                  <p className="ex-hint">Check a result:</p>
                  <div className="ex-chips">
                    {model.benchmarks.map((bench) => (
                      <button
                        key={bench}
                        type="button"
                        className={benchmark === bench ? "on" : ""}
                        onClick={() => run(model.name, bench)}
                        title={`Verify ${bench} for ${model.name}`}
                      >
                        {bench}
                      </button>
                    ))}
                  </div>
                </article>
              ))}
            </div>
          )}

          <p className="ex-note">
            <FaInfoCircle aria-hidden="true" /> Not every model has a
            published number for every benchmark. When a paper doesn't report
            one, you'll see "No results found" with the closest related
            results, never a guess.
          </p>
        </section>

        <section className="ex-section">
          <header className="ex-head">
            <span className="ex-eyebrow"><FaBookOpen /> Benchmark guide</span>
            <h2>What the benchmarks measure</h2>
          </header>

          <div className="ex-guide">
            {BENCHMARKS.map((item) => (
              <article key={item.name}>
                <h3>{item.name}</h3>
                <p>{item.what}</p>
              </article>
            ))}
          </div>
        </section>
      </main>

      <Footer />
    </>
  );
}

export default Explore;
