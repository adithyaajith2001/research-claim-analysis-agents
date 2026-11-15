# ResearchClaimAI

**An Intelligent Multi-Agent Framework for Autonomous Analysis and Verification of Research Claims Across Multiple Papers**

You ask a question such as *"MMLU accuracy of Mistral 7B"*. The system finds the
papers itself, reads their results tables, extracts the numeric benchmark
claims, checks each one against the paper's own text, compares papers that
report the same result, and gives a confidence score you can break down and
explain.

Built at CHRIST (Deemed to be University), Department of Computer Science.

| | |
|---|---|
| Team | Adithya Ajith, Malavika Krishna, Sheethal Krishna K K |
| Guide | Dr. Sindhu V |

---

## How it works

```
Question
   |
   v
1. Retrieval agent         arXiv + Semantic Scholar + CrossRef searched in parallel;
   |                       papers ranked by relevance; the asked model's own paper
   |                       is fetched by arXiv ID so it is never missed
   v
2. Claim extraction        reads abstracts and full PDFs (results tables included);
   |                       Gemini pulls out numeric benchmark claims; a validator
   |                       rejects anything the text does not support
   v
3. Evidence verification   checks each claim against the paper's own text
   v
4. Skeptic agent           flags doubtful or contradicting wording
   v
5. Evidence strength       scores how convincing the evidence is (anchored rubric)
   v
6. Contradiction agent     compares papers only when they report the same model,
   |                       benchmark and setting
   v
7. Confidence aggregation  one 0-10 score, shown with its four parts
```

### Confidence score

| Part | Weight |
|---|---|
| Evidence strength | 40% |
| Verification in the paper | 30% |
| Agreement with other papers | 20% (5/10 when no other paper reports the result) |
| Skeptic review | 10% |

High is 8 or more, Medium is 6 or more, anything lower is Low. A result from a
single paper cannot reach High, because High needs a second paper to agree.

### What makes it trustworthy

- **Answers the model you asked about.** Ask about Gemma 2 27B and results for
  Gemma 3, Gemma 2 9B or MMLU-Pro are listed under "Results left out", never
  mixed into your answer.
- **Says when it cannot find the answer.** You get "No results found" plus the
  closest related results for context, not a guess.
- **Labels weak evidence.** Single-source results and sub-component scores
  carry a visible warning.
- **Repeatable.** Scoring and extraction run at temperature 0.

---

## Features

- Public landing page, a sign-in popup for visitors, accounts with search history
- Explore page: model profiles, benchmark guide, glossary and FAQ
- Live progress while an analysis runs (about 45-80 seconds)
- Saved reports: a repeated question opens instantly; **Run again** re-checks the papers
- Dashboard: confidence ring, score breakdown, claims table with sources,
  results left out, cross-paper comparisons, papers analysed
- Download the report as a PDF

---

## Tech stack

| Layer | Tools |
|---|---|
| Frontend | React, Vite, react-router, Firebase (Google sign-in), jsPDF |
| Backend | Python, FastAPI, SQLAlchemy (SQLite), scikit-learn |
| LLM | Google Gemini (`gemini-flash-lite-latest`) |
| Sources | arXiv, Semantic Scholar, CrossRef |

---

## Run it locally

You need Python 3.10+, Node 18+ and a free
[Gemini API key](https://aistudio.google.com/apikey).

### 1. Backend

```bash
cd backend
python -m venv venv
# Windows:  venv\Scripts\activate        macOS/Linux:  source venv/bin/activate
pip install -r ../requirements.txt
cp .env.example .env        # Windows: copy .env.example .env
# open .env and add your GEMINI_API_KEY
uvicorn main:app --reload
```

The API runs at http://127.0.0.1:8000. Check http://127.0.0.1:8000/api/health.

`.env` values:

| Variable | Needed | Purpose |
|---|---|---|
| `GEMINI_API_KEY` | yes | claim extraction and evidence scoring |
| `SEMANTIC_SCHOLAR_API_KEY` | recommended | free key from semanticscholar.org/product/api; avoids rate-limit waits |

Never commit your real `.env` file.

### 2. Frontend

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:5173.

On a network that reports a certificate error during `npm install`
(Windows PowerShell), run this once in the same terminal first:

```powershell
$env:NODE_OPTIONS="--use-system-ca"
```

### 3. Try it

Sign up, then search **"MMLU accuracy of Mistral 7B"**. Or open **Explore** and
click a model and benchmark.

---

## API

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/api/jobs` | Start an analysis. Body: `{"query": "...", "max_results": 5, "refresh": false}` |
| `GET` | `/api/jobs/{job_id}` | Progress, then the full report when `status` is `done` |
| `GET` | `/api/health` | Health check |
| `GET` | `/api/catalog` | Models that have their own paper built in |

Finished reports that contain claims are cached for 7 days in
`backend/data/analysis_cache.json` (ignored by git). Send `"refresh": true` to
skip the cache.

---

## Project layout

```
backend/
  main.py                       FastAPI app, background jobs, cache
  retrievers/
    unified_retriever.py        parallel search, ranking, model-aware filtering
    known_papers.py             each model's own paper, fetched by arXiv ID
    query_model.py              finds the model named in a question
    retrieval_adapter.py        PDF download and text extraction
    claim_extraction_agent.py   Gemini extraction, validation, table readers
    evidence_strength_agent.py  anchored evidence-strength rubric
    contradiction_agent.py      cross-paper comparison
    confidence_scoring.py       weighted aggregation
    test_pipeline.py            run_pipeline(): the whole pipeline
  agents/                       evidence verification and skeptic agents
frontend/src/
  pages/                        Home, Analysis, Explore, Dashboard, Account, About, Login, SignUp
  components/                   navbar, footer, loading screen, sign-in popup
  services/                     API client, accounts, search history
  utils/                        report helpers, PDF export
```

---

## Known limitations

- **One analysis at a time.** A second request is refused until the first finishes.
- **Table reading depends on the PDF.** Results in images, or in table layouts
  the extractor does not recognise, can be missed. Two table layouts are read
  directly: benchmarks as columns, and model groups over sizes.
- **Mostly single-source answers today.** Cross-paper agreement appears only
  when a second retrieved paper reports the same model, benchmark and setting.
- **The skeptic check is a keyword check**, so a high skeptic score means only
  that no doubtful wording was found.
- **Accounts are demo-grade.** Passwords are hashed in the browser and history
  is stored per browser. A production version would use server-side
  authentication and a database.
- **Results are a research aid.** Always confirm important numbers in the
  original paper.

---

## Test results

See [`docs/TEST_RESULTS.md`](docs/TEST_RESULTS.md) for queries run against the
system and how each result compares with the number published in the paper.
