"use client";

/**
 * components/QueryInput.jsx
 *
 * OWNER: Adithya Ajith - Frontend: Query Input Component.
 *
 * The entry point into the whole pipeline: a researcher types a topic,
 * keyword, or DOI, and this calls POST /api/analyze. Hands the result
 * (or an error) back up via onResult / onError - it doesn't own how the
 * result gets displayed, that's the dashboard's job.
 */

import { useState } from "react";
import { analyzeQuery } from "../lib/api";

export default function QueryInput({ onResult, onError, onStart }) {
  const [query, setQuery] = useState("");
  const [maxResults, setMaxResults] = useState(8);
  const [isLoading, setIsLoading] = useState(false);

  async function handleSubmit(e) {
    e.preventDefault();
    const trimmed = query.trim();
    if (trimmed.length < 3) {
      onError?.("Enter a topic, keyword, or DOI (at least 3 characters).");
      return;
    }

    setIsLoading(true);
    onStart?.(trimmed);

    try {
      const result = await analyzeQuery(trimmed, maxResults);
      onResult?.(result);
    } catch (err) {
      onError?.(err.message || "Analysis failed. Check the backend is running.");
    } finally {
      setIsLoading(false);
    }
  }

  return (
    <form className="query-form" onSubmit={handleSubmit}>
      <label htmlFor="query-input" className="query-label">
        What research topic should we verify?
      </label>

      <div className="query-row">
        <input
          id="query-input"
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="e.g. MMLU large language model benchmark evaluation"
          disabled={isLoading}
          autoComplete="off"
        />
        <button type="submit" disabled={isLoading}>
          {isLoading ? "Analyzing…" : "Analyze"}
        </button>
      </div>

      <div className="query-options">
        <label htmlFor="max-results">Papers to retrieve</label>
        <input
          id="max-results"
          type="number"
          min={1}
          max={10}
          value={maxResults}
          onChange={(e) => setMaxResults(Number(e.target.value))}
          disabled={isLoading}
        />
        <span className="hint">
          Runs retrieval, claim extraction, evidence verification, skeptic
          review, and contradiction detection. Expect roughly 60–90s per
          paper.
        </span>
      </div>

      <style jsx>{`
        .query-form {
          background: var(--paper-raised);
          border: 1px solid var(--rule);
          border-radius: 4px;
          padding: 1.75rem;
          display: flex;
          flex-direction: column;
          gap: 0.9rem;
        }

        .query-label {
          font-family: var(--font-serif);
          font-size: 1.15rem;
          color: var(--ink);
        }

        .query-row {
          display: flex;
          gap: 0.6rem;
        }

        input[type="text"] {
          flex: 1;
          font-size: 1rem;
          padding: 0.7rem 0.85rem;
          border: 1px solid var(--rule);
          border-radius: 3px;
          background: var(--paper);
          color: var(--charcoal);
        }

        input[type="text"]:focus {
          background: var(--paper-raised);
        }

        button {
          background: var(--ink);
          color: var(--paper-raised);
          border: none;
          padding: 0 1.4rem;
          border-radius: 3px;
          font-weight: 600;
          font-size: 0.95rem;
          cursor: pointer;
          transition: background 0.15s ease;
        }

        button:hover:not(:disabled) {
          background: var(--ink-soft);
        }

        button:disabled {
          opacity: 0.6;
          cursor: progress;
        }

        .query-options {
          display: flex;
          align-items: center;
          gap: 0.6rem;
          flex-wrap: wrap;
          font-size: 0.85rem;
          color: var(--slate);
        }

        .query-options label {
          font-weight: 500;
        }

        input[type="number"] {
          width: 4rem;
          padding: 0.35rem 0.5rem;
          border: 1px solid var(--rule);
          border-radius: 3px;
          background: var(--paper);
        }

        .hint {
          flex-basis: 100%;
          color: var(--slate);
          opacity: 0.85;
        }

        @media (max-width: 560px) {
          .query-row {
            flex-direction: column;
          }
        }
      `}</style>
    </form>
  );
}
