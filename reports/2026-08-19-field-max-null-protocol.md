# Field-max null protocol (N1d) — FROZEN 2026-08-19

**Protocol id:** `20260819-field-max-null-v1`. Operator direction:
"please proceed as you recommend" (2026-08-19). One-shot: executes
exactly once per version.

## Question

The N1 headline (51 winners at median percentile 1.0 of their own
simulated distributions) is confounded: winners are field maxima, and
under a PERFECTLY correct law the field-max roster's realized score
sits near the top of its own distribution. This protocol computes the
null N1 was missing: how extreme should winners look under our own law,
as a function of field size — and how large would the field have to be
for a correct law to produce what N1 observed?

## Method (implemented and unit-tested before this freeze)

Entirely under the archived law; no realized outcome is read. Per seed
block (candidate sets differ across blocks — a pre-freeze smoke
finding; contests therefore pool at the contest level, 5 x 10,000 per
slate): every archived world is one contest; the winner is the argmax
registered candidate in that world; its null percentile is the mid-rank
placement of that total within the SAME candidate's other 9,999 worlds
(self-world excluded, matching the observed semantics). Field-size
scaling via fixed-seed subsampling at 32/64/128 candidates (5 reps,
seed 20260819), with the winning candidate's reference distribution
kept at its full row. The implied effective field size at each pool
size inverts p = 1 − 0.999^N; the effectiveness ratio (implied/actual)
extrapolates to the observed exceedance fraction.

## Preregistered decision rule (frozen in the module before any number)

1. If the full-pool null reproduces the observed beyond-p999 count
   (47/51) with Poisson-binomial probability >= 0.01: **selection alone
   explains N1 at pool size.**
2. Else if the required raw field size is <= 300,000 (a generous cap on
   literal Milly entries, frozen before any number was seen): **N1 is
   non-diagnostic** — consistent with a correct law and a plausible
   field; the only surviving law-deficit evidence at winner scale is
   the book-tail factor-of-two.
3. Else: **missing joint mass confirmed at winner scale.**

Descriptive extras: expected counts at p95/p99, null probability of at
least one pr=0 winner (the observed `min Pr_sim = 0.0` analog).
Whatever the verdict, N1b's geometry (generating worlds at ranks
41–511) is unaffected — it compares rosters within the same worlds.

## Governance

Pure self-law computation plus published N1 constants; no lease needed;
no collision with the in-flight all-boom arm. Create-only output;
`uses_realized_outcomes: false`, `gate_decision: null`,
`production_change_licensed: false`. Local sequential numpy, matching
the N1 execution mode.

## Reality smoke (rule-1, outcome-blind, run BEFORE this freeze)

First smoke attempt FAILED CLOSED on the stacking contract: seed blocks
register different candidate sets (255/257/254/256/254 on 2023 week 1),
so cross-block candidate stacking is invalid. The design was corrected
to per-block contests (statistically equivalent: the selection effect
depends on competitor count, not reference-world count) and the false
assumption's stacker was deleted, not kept. Re-smoke passed: 50,000
contests, percentiles finite and in [0,1], computation and subsampling
deterministic. No comparison against observed counts was made.

## Pins (sha256 prefixes)

- Module `src/nfl_dfs/analysis/field_max_null.py`: `6fcf427aefa5fc47`
- Runner `scripts/analyze_field_max_null.py`: `67bc3081cb740659`
- N1 report (slate list + observed exceedance): `c715cd78`
- Local artifact manifest: `915d4a06a586eb52`
- Output: `reports/winner-law-audit-runs/20260819-field-max-null-v1-report.json`
