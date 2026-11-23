"""
Measure how accurate ResearchClaimAI is, against a person's own check.

Two steps, both run from the backend folder with the backend already running:

1. COLLECT   python evaluation/evaluate.py collect --queries evaluation/queries.txt --out evaluation/labels.csv
   Runs every question through the backend and writes one row per claim the
   system extracted. Nothing is labelled yet.

2. LABEL     (by a person, in Excel)
   Open labels.csv. For each row, open the paper and look at the table it
   came from. Fill in the column human_correct with:
       yes  - the paper really reports this value for this model on this benchmark
       no   - the value, model or benchmark is wrong, or it is not in the paper
   Results the system MISSED go in a second file, missed.csv, with the columns
   query, paper_title, model, benchmark, value (one row per missed result).

3. SCORE     python evaluation/evaluate.py score --labels evaluation/labels.csv --missed evaluation/missed.csv
   Prints precision, recall, how well the verification step agrees with the
   person, and writes evaluation/report.md.

Only labels written by a person are counted. Rows left blank are skipped and
reported, never guessed.
"""

import argparse
import csv
import math
import sys
import time
from collections import defaultdict
from pathlib import Path

import requests

LABEL_COLUMNS = [
    "query", "paper_title", "model", "benchmark", "reported_value",
    "claim", "source_text", "system_verdict", "verification_score",
    "evidence_strength", "human_correct", "human_note",
]


# ------------------------------------------------------------------
# collect
# ------------------------------------------------------------------

def verdict_of(claim):
    """Same rule the dashboard uses for 'Found in paper' / 'Weak match'."""
    verification = claim.get("verification") or {}

    if verification.get("supporting_evidence"):
        return "Found in paper"
    if verification.get("weak_evidence"):
        return "Weak match"

    try:
        score = float(claim.get("verification_score"))
    except (TypeError, ValueError):
        return "Not found in paper"

    if score >= 7.5:
        return "Found in paper"
    if score >= 4.5:
        return "Weak match"
    return "Not found in paper"


def source_text_of(claim):
    verification = claim.get("verification") or {}
    first = (
        (verification.get("supporting_evidence") or [None])[0]
        or (verification.get("evidence_results") or [None])[0]
        or (verification.get("weak_evidence") or [None])[0]
        or {}
    )
    return " ".join(str(first.get("evidence", "")).split())


def run_query(api, query, timeout_s=900):
    start = requests.post(
        f"{api}/api/jobs",
        json={"query": query, "max_results": 5, "refresh": True, "restart": False},
        timeout=60,
    )
    start.raise_for_status()
    job_id = start.json()["job_id"]

    began = time.time()
    while time.time() - began < timeout_s:
        time.sleep(3)
        job = requests.get(f"{api}/api/jobs/{job_id}", timeout=30).json()
        if job["status"] == "done":
            return job["result"]
        if job["status"] in ("error", "cancelled"):
            raise RuntimeError(job.get("message") or job["status"])
    raise TimeoutError("analysis took too long")


def collect(args):
    queries = [
        line.strip()
        for line in Path(args.queries).read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.startswith("#")
    ]
    rows = []

    for number, query in enumerate(queries, 1):
        print(f"[{number}/{len(queries)}] {query}")
        try:
            result = run_query(args.api, query)
        except Exception as error:
            print(f"    failed: {error}")
            continue

        claims = result.get("claims") or []
        print(f"    {len(claims)} claims")

        for claim in claims:
            rows.append({
                "query": query,
                "paper_title": claim.get("paper_title", ""),
                "model": claim.get("model_name", ""),
                "benchmark": claim.get("benchmark", ""),
                "reported_value": claim.get("reported_value", ""),
                "claim": claim.get("claim", ""),
                "source_text": source_text_of(claim),
                "system_verdict": verdict_of(claim),
                "verification_score": claim.get("verification_score", ""),
                "evidence_strength": claim.get("evidence_strength_score", ""),
                "human_correct": "",
                "human_note": "",
            })

    with open(args.out, "w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=LABEL_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)

    print(f"\nWrote {len(rows)} rows to {args.out}")
    print("Next: fill in the human_correct column, then run the score step.")


# ------------------------------------------------------------------
# score
# ------------------------------------------------------------------

def wilson(successes, total, z=1.96):
    """95% confidence interval for a proportion (honest for small samples)."""
    if total == 0:
        return (0.0, 0.0)
    p = successes / total
    denom = 1 + z * z / total
    centre = (p + z * z / (2 * total)) / denom
    margin = z * math.sqrt(p * (1 - p) / total + z * z / (4 * total * total)) / denom
    return (max(0.0, centre - margin), min(1.0, centre + margin))


def pct(x):
    return f"{100 * x:.1f}%"


def read_csv(path):
    with open(path, newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def score(args):
    rows = read_csv(args.labels)
    missed = read_csv(args.missed) if args.missed and Path(args.missed).exists() else []

    labelled, blank, unclear = [], 0, 0
    for row in rows:
        answer = (row.get("human_correct") or "").strip().lower()
        if answer in ("yes", "y"):
            row["_ok"] = True
            labelled.append(row)
        elif answer in ("no", "n"):
            row["_ok"] = False
            labelled.append(row)
        elif answer == "":
            blank += 1
        else:
            unclear += 1

    if not labelled:
        sys.exit("No rows have been labelled yet. Fill in human_correct with yes or no.")

    correct = sum(1 for r in labelled if r["_ok"])
    total = len(labelled)
    low, high = wilson(correct, total)

    lines = []
    out = lines.append
    out("# Evaluation report\n")
    out(f"Claims labelled by a person: **{total}** "
        f"({blank} blank rows skipped, {unclear} unclear answers skipped)\n")

    out("## Extraction precision\n")
    out("Of the claims the system extracted, how many the paper really reports.\n")
    out(f"- Correct: {correct} of {total}")
    out(f"- **Precision: {pct(correct / total)}** (95% interval {pct(low)} to {pct(high)})\n")

    if missed:
        found = correct
        missed_n = len(missed)
        recall = found / (found + missed_n)
        rl, rh = wilson(found, found + missed_n)
        out("## Extraction recall\n")
        out("Of the results a person found in the papers, how many the system also extracted. "
            "Only the results the person recorded in the missed file count as missed, so if the "
            "person did not read every table, the true recall is lower than this figure.\n")
        out(f"- Extracted correctly: {found}; missed: {missed_n}")
        out(f"- **Recall: {pct(recall)}** (95% interval {pct(rl)} to {pct(rh)})")
        f1 = 2 * (correct / total) * recall / ((correct / total) + recall) if correct else 0.0
        out(f"- F1: {pct(f1)}\n")
    else:
        out("## Extraction recall\n")
        out("Not measured: no missed.csv was given.\n")

    out("## Does the verification step agree with the person?\n")
    out("| System verdict | Person says correct | Person says wrong |")
    out("|---|---|---|")
    for verdict in ("Found in paper", "Weak match", "Not found in paper"):
        yes = sum(1 for r in labelled if r["system_verdict"] == verdict and r["_ok"])
        no = sum(1 for r in labelled if r["system_verdict"] == verdict and not r["_ok"])
        out(f"| {verdict} | {yes} | {no} |")
    out("")

    wrong = [r for r in labelled if not r["_ok"]]
    right = [r for r in labelled if r["_ok"]]
    if right:
        ok = sum(1 for r in right if r["system_verdict"] == "Found in paper")
        out(f"- Correct claims marked 'Found in paper': {ok} of {len(right)} ({pct(ok / len(right))})")
    if wrong:
        caught = sum(1 for r in wrong if r["system_verdict"] != "Found in paper")
        out(f"- Wrong claims NOT marked 'Found in paper' (caught): {caught} of {len(wrong)} ({pct(caught / len(wrong))})")
    else:
        out("- No wrong claims were recorded, so the catch rate cannot be measured.")
    out("")

    def mean(rows_, key):
        values = []
        for r in rows_:
            try:
                values.append(float(r[key]))
            except (TypeError, ValueError, KeyError):
                pass
        return sum(values) / len(values) if values else None

    out("## Scores on correct and wrong claims\n")
    out("| | Verification score | Evidence strength |")
    out("|---|---|---|")
    for name, group in (("Correct claims", right), ("Wrong claims", wrong)):
        v, e = mean(group, "verification_score"), mean(group, "evidence_strength")
        out(f"| {name} (n={len(group)}) | {'-' if v is None else f'{v:.1f}'} | {'-' if e is None else f'{e:.1f}'} |")
    out("")

    by_query = defaultdict(lambda: [0, 0])
    for r in labelled:
        by_query[r["query"]][1] += 1
        by_query[r["query"]][0] += int(r["_ok"])
    out("## By question\n")
    out("| Question | Correct | Labelled |")
    out("|---|---|---|")
    for query, (ok, n) in by_query.items():
        out(f"| {query} | {ok} | {n} |")
    out("")

    out("## Limits\n")
    out("- Labels come from one or more people reading the papers; say who labelled and how "
        "disagreements were settled when you report these numbers.")
    out("- Small samples give wide intervals; report the interval, not just the percentage.")
    report = "\n".join(lines)
    Path(args.out).write_text(report, encoding="utf-8")
    print(report)
    print(f"\nSaved to {args.out}")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)

    c = sub.add_parser("collect", help="run questions and write the labelling sheet")
    c.add_argument("--queries", required=True)
    c.add_argument("--out", default="evaluation/labels.csv")
    c.add_argument("--api", default="http://localhost:8000")
    c.set_defaults(func=collect)

    s = sub.add_parser("score", help="score a labelled sheet")
    s.add_argument("--labels", required=True)
    s.add_argument("--missed", default="")
    s.add_argument("--out", default="evaluation/report.md")
    s.set_defaults(func=score)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
