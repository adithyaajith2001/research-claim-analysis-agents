import { useEffect, useMemo, useState } from "react";
import {
  FaSearch,
  FaBolt,
  FaInfoCircle,
  FaExternalLinkAlt,
  FaGraduationCap,
  FaMicrochip,
  FaClipboardList,
  FaQuestionCircle
} from "react-icons/fa";

import Navbar from "../components/layout/Navbar";
import Footer from "../components/layout/Footer";
import useStartAnalysis from "../hooks/useStartAnalysis";
import {
  MODELS,
  BENCHMARKS,
  BASICS,
  GLOSSARY,
  FAQ
} from "../data/learnContent";

import "../styles/explore.css";

const TABS = [
  { id: "models", label: "Models", icon: FaMicrochip },
  { id: "benchmarks", label: "Benchmarks", icon: FaClipboardList },
  { id: "learn", label: "Learn the basics", icon: FaGraduationCap },
  { id: "faq", label: "Glossary & FAQ", icon: FaQuestionCircle }
];

const WORD = Object.fromEntries(BENCHMARKS.map((b) => [b.name, b.word]));

const readHash = () => {
  const id = window.location.hash.replace("#", "");
  return TABS.some((tab) => tab.id === id) ? id : "models";
};

function Explore() {
  const [tab, setTab] = useState(readHash);
  const [search, setSearch] = useState("");
  const [benchmark, setBenchmark] = useState("All");
  const startAnalysis = useStartAnalysis();

  // Keep the tab in the address so it can be shared or bookmarked.
  useEffect(() => {
    const onHash = () => setTab(readHash());
    window.addEventListener("hashchange", onHash);
    return () => window.removeEventListener("hashchange", onHash);
  }, []);

  const openTab = (id) => {
    setTab(id);
    window.history.replaceState(null, "", `#${id}`);
  };

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
          <span className="ex-pill"><FaBolt /> Learn it, then check it</span>
          <h1>
            Explore models, benchmarks and <span>how to read them</span>
          </h1>
          <p>
            New to AI research? Start with the basics. Already know your way
            around? Pick a model and a benchmark and we'll check the number
            against the papers.
          </p>

          <div className="ex-tabs" role="tablist" aria-label="Explore sections">
            {TABS.map(({ id, label, icon: Icon }) => (
              <button
                key={id}
                type="button"
                role="tab"
                id={`tab-${id}`}
                aria-selected={tab === id}
                aria-controls={`panel-${id}`}
                className={tab === id ? "on" : ""}
                onClick={() => openTab(id)}
              >
                <Icon aria-hidden="true" /> {label}
              </button>
            ))}
          </div>
        </header>

        {/* ---------------- MODELS ---------------- */}
        {tab === "models" && (
          <section className="ex-section" id="panel-models" role="tabpanel" aria-labelledby="tab-models">
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
                {["All", ...BENCHMARKS.slice(0, 5).map((b) => b.name)].map((name) => (
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
                        <small>{model.org} · {model.year} · {model.size}</small>
                      </div>
                      <span className={model.kind === "Closed" ? "ex-kind closed" : "ex-kind"}>
                        {model.kind}
                      </span>
                    </div>

                    <p className="ex-blurb">{model.blurb}</p>

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

                    <a
                      className="ex-paper"
                      href={
                        model.link ||
                        `https://arxiv.org/search/?query=${encodeURIComponent(model.name)}&searchtype=title`
                      }
                      target="_blank"
                      rel="noopener noreferrer"
                    >
                      {model.linkLabel || "Find the paper on arXiv"} <FaExternalLinkAlt aria-hidden="true" />
                    </a>
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
        )}

        {/* ---------------- BENCHMARKS ---------------- */}
        {tab === "benchmarks" && (
          <section className="ex-section" id="panel-benchmarks" role="tabpanel" aria-labelledby="tab-benchmarks">
            <p className="ex-intro">
              A benchmark is an exam for AI models. Each one tests something
              different, so a high score on one says little about another.
            </p>

            <div className="ex-bench-list">
              {BENCHMARKS.map((item) => (
                <article key={item.name} className="ex-bench">
                  <header>
                    <h3>{item.name}</h3>
                    <span className="ex-tag">{item.tests}</span>
                    <small>{item.made}</small>
                  </header>

                  <p>{item.what}</p>

                  <div className="ex-example">
                    <small>Example of the kind of question</small>
                    <q>{item.example}</q>
                  </div>

                  <dl>
                    <div>
                      <dt>How it's scored</dt>
                      <dd>{item.scored}</dd>
                    </div>
                    <div>
                      <dt>Watch out for</dt>
                      <dd>{item.watch}</dd>
                    </div>
                  </dl>

                  <button
                    type="button"
                    className="ex-try"
                    onClick={() => run("Mistral 7B", item.name)}
                  >
                    See a real example: {item.name} for Mistral 7B
                  </button>
                </article>
              ))}
            </div>
          </section>
        )}

        {/* ---------------- LEARN ---------------- */}
        {tab === "learn" && (
          <section className="ex-section" id="panel-learn" role="tabpanel" aria-labelledby="tab-learn">
            <p className="ex-intro">
              Six short answers that make everything else on this site easier
              to follow.
            </p>

            <ol className="ex-basics">
              {BASICS.map((item, index) => (
                <li key={item.title}>
                  <span className="ex-step">{index + 1}</span>
                  <div>
                    <h3>{item.title}</h3>
                    <p>{item.text}</p>
                  </div>
                </li>
              ))}
            </ol>

            <div className="ex-callout">
              <h3>Ready to try it?</h3>
              <p>Pick a model and a benchmark and see a real, verified answer.</p>
              <button type="button" onClick={() => openTab("models")}>
                Browse models
              </button>
            </div>
          </section>
        )}

        {/* ---------------- GLOSSARY + FAQ ---------------- */}
        {tab === "faq" && (
          <section className="ex-section" id="panel-faq" role="tabpanel" aria-labelledby="tab-faq">
            <h2 className="ex-h2">Glossary</h2>
            <dl className="ex-glossary">
              {GLOSSARY.map(([term, meaning]) => (
                <div key={term}>
                  <dt>{term}</dt>
                  <dd>{meaning}</dd>
                </div>
              ))}
            </dl>

            <h2 className="ex-h2">Frequently asked questions</h2>
            <div className="ex-faq">
              {FAQ.map(([question, answer]) => (
                <details key={question}>
                  <summary>{question}</summary>
                  <p>{answer}</p>
                </details>
              ))}
            </div>
          </section>
        )}
      </main>

      <Footer />
    </>
  );
}

export default Explore;
