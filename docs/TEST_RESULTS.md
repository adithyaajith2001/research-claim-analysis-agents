# Test results

Each query was run end to end through the system (retrieval, extraction,
verification, scoring). "Published" is the number printed in the model's own
paper, so the last column shows whether the system read it correctly.

Scores below were produced with the current scoring rubric (temperature 0).
Run time includes retrieval, reading the PDFs and scoring.

| # | Query | System result | Published in paper | Match | Confidence | Evidence strength | Time |
|---|---|---|---|---|---|---|---|
| 1 | MMLU accuracy of Mistral 7B | 60.1% | 60.1% (Mistral 7B paper) | Yes | Medium, 7.1 | 6.0 | 43 s |
| 2 | GSM8K accuracy of Mistral 7B | 52.2% | 52.2% (Mistral 7B paper) | Yes | Medium, 6.7 | 5.0 | 61 s |
| 3 | HumanEval score of Llama 2 7B | _to fill_ | _check Llama 2 paper_ | | | | |
| 4 | MMLU accuracy of Llama 2 13B | _to fill_ | _check Llama 2 paper_ | | | | |
| 5 | MMLU accuracy of GPT-4 | _to fill_ | _check GPT-4 report_ | | | | |
| 6 | MMLU accuracy of Gemma 2 27B | 75.2% | 75.2% (Gemma 2 paper) | Yes | Medium (earlier run: 7.2) | | 55 s |

## Behaviour checks

| Check | What was done | Outcome |
|---|---|---|
| Asked model only | Gemma 2 27B asked; Gemma 3, Gemini and Gemma 2 9B/2B rows appear in the paper | Listed under "Results left out", not scored |
| Different benchmark variant | MMLU asked; Gemma 2 27B reported on MMLU-Pro (56.9) | Kept out of the answer, shown under "Closest matches" |
| Missing result | Gemma 2 27B asked before its own paper was retrieved | "No results found", no number invented |
| Repeat query | Same question asked again | Opens instantly as a saved report; "Run again" re-checks the papers |

## Notes

- Every result so far comes from a single paper, so each report carries the
  "single source" warning and cannot reach High confidence.
- Results vary slightly with retrieval, because the sources return different
  papers over time. Scoring and extraction are fixed at temperature 0.
