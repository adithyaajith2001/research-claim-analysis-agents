"""
contradiction_agent.py

WHAT: finds pairs of claims that report a value for the SAME benchmark but
come from DIFFERENT papers, and classifies each pair as "Agrees" or
"Contradicts" (with a severity), then writes them to the Contradiction
table defined in db_schema.py.

WHY rule-based (same pattern as evidence_strength_agent.py's
benchmark_is_standard check): whether two numbers are far apart is a FACT
you can compute, not a judgment call an LLM needs to render. Two papers
reporting 86.4% vs 79.5% on MMLU is a checkable disagreement - keeping this
rule-based makes it deterministic, free (no API quota spent), and directly
explainable on the dashboard ("6.9 points apart on MMLU" beats "the AI felt
these disagreed").

WHY only same-benchmark, SAME-value_type, cross-paper pairs: comparable
claims need a shared yardstick. config.VALIDATED_BENCHMARKS enforces the
"same benchmark" half of that at extraction time (see
claim_extraction_agent.py); value_type enforces the other half. An early
version of this agent grouped by benchmark_name alone, which meant a
standalone accuracy score (e.g. "95.22% on GSM8K") got numerically diffed
against improvement deltas (e.g. "a 1.3% absolute improvement") as if they
were the same measurement - they are not, and doing so produced 13/14 pairs
flagged "Contradicts" on a live run where most of that spread was really
just different quantity types, not real disagreement. Grouping by
(benchmark_name, value_type) fixes this: only claims that are genuinely
measuring the same thing get compared.

Two claims from the SAME paper reporting the same number twice (e.g. once
in the abstract, once in the results table) aren't a contradiction between
two papers either - they're restating one paper's own finding, so those
pairs are skipped too.

Thresholds (CONTRADICTION_AGREE_MAX_DIFF, CONTRADICTION_HIGH_SEVERITY_DIFF)
live in config.py, same as every other domain decision, so scoring/
extraction/contradiction detection can't silently drift out of sync.

WHEN this runs: after multiple papers have been processed by
etl_pipeline.process_paper() (or test_pipeline.run_pipeline()) and their
claims are sitting in the claims table - contradiction detection is a
cross-paper analysis, so it can't run per-paper the way extraction/scoring
do. Run it as a separate pass: `python contradiction_agent.py`.

IDEMPOTENT: reruns won't create duplicate Contradiction rows for the same
claim pair - see db_schema.contradiction_exists().
"""

import itertools
from db_schema import get_session, Claim, insert_contradiction

from config import (
    CONTRADICTION_AGREE_MAX_DIFF,
    CONTRADICTION_HIGH_SEVERITY_DIFF,
)


def _classify(diff: float) -> tuple:
    """WHAT: turns a numeric gap between two reported values into
    (relation_type, severity).

    WHY these specific bands: diff <= CONTRADICTION_AGREE_MAX_DIFF is treated
    as the same finding within normal measurement/eval noise (e.g. 91.2%
    vs 91.0% on GSM8K - basically the same result, reported twice).
    Anything past that is a real disagreement worth flagging; severity
    escalates to "High" once the gap is large enough that the two papers
    can't both be describing the same underlying capability
    (CONTRADICTION_HIGH_SEVERITY_DIFF).
    """
    if diff <= CONTRADICTION_AGREE_MAX_DIFF:
        return "Agrees", "Low"
    severity = "High" if diff > CONTRADICTION_HIGH_SEVERITY_DIFF else "Medium"
    return "Contradicts", severity


def find_contradictions_in_group(claims_for_one_group: list) -> list:
    """WHAT: pairwise-compares every claim in a single (benchmark_name,
    value_type) group - caller groups them so every claim passed in here
    already shares both a benchmark AND a value_type, meaning they're
    genuinely the same kind of measurement.

    Returns a list of dicts, NOT yet written to the DB - see
    store_contradictions() / run_contradiction_detection() for that.
    """
    results = []
    for a, b in itertools.combinations(claims_for_one_group, 2):
        if a.paper_id == b.paper_id:
            continue  # same paper restating its own finding isn't a contradiction
        if a.reported_value is None or b.reported_value is None:
            continue  # nothing numeric to compare

        diff = round(abs(a.reported_value - b.reported_value), 2)
        relation_type, severity = _classify(diff)

        results.append({
            "claim_a_id": a.id,
            "claim_b_id": b.id,
            "claim_a_text": a.claim_text,
            "claim_b_text": b.claim_text,
            "benchmark_name": a.benchmark_name,
            "relation_type": relation_type,
            "severity": severity,
            "value_diff": diff,
        })
    return results


def detect_all_contradictions(session=None) -> list:
    """WHAT: pulls every claim that has a benchmark_name, a reported_value,
    AND a value_type, groups by (benchmark_name, value_type), and compares
    within each group.

    WHY group by (benchmark_name, value_type) and not benchmark_name alone:
    comparing an MMLU claim to a GSM8K claim is meaningless (different
    yardsticks) - that's why benchmark_name is part of the key. But two
    claims can share a benchmark and still not be comparable numbers: a
    standalone accuracy score and a percentage-point improvement are
    different quantities even when both are "about GSM8K". value_type
    closes that gap - see the module docstring for the live-run evidence
    that motivated this.

    WHY claims with no value_type are skipped entirely (not grouped as
    their own "unknown" bucket): an untyped number could be anything, and
    silently comparing untyped claims to each other risks reintroducing the
    exact bug this fix addresses. Better to under-report contradictions on
    old/malformed data than to report a false one.
    """
    close_session = False
    if session is None:
        session = get_session()
        close_session = True

    claims = (
        session.query(Claim)
        .filter(Claim.benchmark_name.isnot(None))
        .filter(Claim.reported_value.isnot(None))
        .filter(Claim.value_type.isnot(None))
        .all()
    )

    skipped_untyped = (
        session.query(Claim)
        .filter(Claim.benchmark_name.isnot(None))
        .filter(Claim.reported_value.isnot(None))
        .filter(Claim.value_type.is_(None))
        .count()
    )
    if skipped_untyped:
        print(f"[info] skipping {skipped_untyped} claim(s) with a reported_value "
              f"but no value_type (likely extracted before this fix) - rerun "
              f"extraction to backfill, or they'll be excluded from comparison")

    by_group = {}
    for c in claims:
        by_group.setdefault((c.benchmark_name, c.value_type), []).append(c)

    all_results = []
    for (benchmark_name, value_type), group in by_group.items():
        pairs = find_contradictions_in_group(group)
        if pairs:
            print(f"[info] {benchmark_name} ({value_type}): compared {len(group)} "
                  f"claim(s), found {len(pairs)} pair(s)")
        all_results.extend(pairs)

    if close_session:
        session.close()
    return all_results


def store_contradictions(session, contradiction_dicts: list) -> list:
    """WHAT: writes each contradiction dict to the DB via
    db_schema.insert_contradiction(), which skips any pair already stored
    (see db_schema.contradiction_exists) so reruns are safe.
    """
    stored_rows = []
    skipped = 0
    for cd in contradiction_dicts:
        row = insert_contradiction(
            session,
            claim_a_id=cd["claim_a_id"],
            claim_b_id=cd["claim_b_id"],
            relation_type=cd["relation_type"],
            severity=cd["severity"],
        )
        if row is None:
            skipped += 1
            continue
        stored_rows.append(row)

    if skipped:
        print(f"[info] skipped {skipped} pair(s) already in the contradictions table")
    return stored_rows


def run_contradiction_detection() -> dict:
    """WHAT: full pipeline - detect across the whole DB, then store.

    WHEN to call: after test_pipeline.run_pipeline() (or
    etl_pipeline.process_paper() for several papers) has populated the
    claims table with claims from more than one paper. Contradiction
    detection needs at least two papers reporting the same benchmark to
    find anything.
    """
    session = get_session()
    found = detect_all_contradictions(session)
    stored = store_contradictions(session, found)
    session.close()

    return {
        "pairs_compared": len(found),
        "contradictions_stored": len(stored),
        "results": found,
    }


if __name__ == "__main__":
    from pprint import pprint
    summary = run_contradiction_detection()
    print(f"\nDone. {summary['contradictions_stored']} new contradiction row(s) stored "
          f"out of {summary['pairs_compared']} pair(s) compared.\n")
    pprint(summary["results"])