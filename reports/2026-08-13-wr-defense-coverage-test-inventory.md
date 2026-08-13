# WR / defense-coverage: complete test inventory and one gap

Date: 2026-08-13. Every coverage test performed, its disposition, and a finding
about what is running in production. **No code was changed.**

---

## The tests

### 1. Prior-season coverage-fit diagnostic — passed, negligibly

`fantasy-points-coverage-diagnostic-wbwlf`. Four frozen features: opponent-weighted
Man/Zone TPRR, YPRR and FP/RR edges, plus a Cover 2/3/4/6 separation edge.
Season N−1 receiver splits × season N−1 opponent shell deployment.

| metric | control | treatment | |
|---|---:|---:|---|
| aggregate 30-pt Brier | 0.01813348 | **0.01809495** | improved 0.21% rel. |
| 2024 fold | 0.01887666 | **0.01876602** | improved |
| 2025 fold | **0.01737883** | 0.01741351 | **worsened** |
| aggregate 20-pt Brier | **0.07376448** | 0.07394482 | worsened |
| residual MAE | **4.88346** | 4.89579 | worsened |

Coverage 28.83% / 29.14%; **62 observed 30-point events** over 3,392 rows;
maximum absolute feature Spearman **0.0596**, unstable in sign across folds.
The report itself called it "a narrow ensemble-calibration signal."

At 62 events this is not distinguishable from noise. It passed by the letter of
its gate and licensed exactly one union.

### 2. Coverage-tail candidate union — rejected, and about as clean a null as exists

`fantasy-points-coverage-tail-union-gxfwg`, disposition `keep-source-incumbent`.

The mechanism was demonstrably active — 432 novel coverage candidates added,
33 selected slots changed in each direction — and:

> **the source and union weekly maxima tied on all 107 slates.**

Both selected grids `34/22/11/7/5/3/2`; both pool-oracle grids
`42/28/16/9/5/3/2`. Identical at every threshold. A mechanism that changes 33
roster slots and moves nothing across 107 slates is not underpowered, it is
inert.

### 3. Same-season coverage, last-four window — failed both gates

`fantasy-points-same-season-coverage-k2zt2`, disposition
`same-season-coverage-player-tail-fails`.

- Support 23.41% / 22.74% / 21.79% against a 30% requirement — failed in
  **every** fold.
- Aggregate 30-pt Brier 0.02956174 → **0.02971345** (worsened).
- 20-pt Brier worsened; residual MAE improved slightly.
- Registered matchup-edge correlations "uniformly small and unstable in sign."

The support failure is structural: over four games the median receiver has ~10
man routes and ~27 zone routes, which cannot support a stable split estimate.

### 4. Effect-size arithmetic — explains all three outcomes

Measured on the four ingested seasons (outcome-viewed, descriptive):

| quantity | value |
|---|---:|
| y/y correlation, man-minus-zone YPRR edge | **0.283** |
| y/y correlation, overall YPRR (skill baseline) | 0.587 |
| y/y correlation, man-minus-zone TPRR edge | 0.357 |
| defensive man rate: min / mean / max | 0.106 / 0.261 / 0.464 |
| SD of defensive man rate | 0.077 |
| y/y correlation, defensive man rate | 0.44 |

Both premises hold — "he beats man" persists at r≈0.28, and defenses differ
persistently in how much man they play. But the *product* is small. Shrinking
the receiver edge for reliability gives a predictable edge SD of
`0.736 × 0.283 ≈ 0.21` YPRR; at ~26 routes/game:

| matchup extremity | rec. yds/game | ≈ DK points |
|---|---:|---:|
| 1 SD × 1 SD | 0.42 | **0.04–0.09** |
| 2 SD × 2 SD | 1.69 | 0.17–0.34 |
| 3 SD × 3 SD | 3.81 | 0.38–0.76 |

Route share's measured effect, for comparison, is +0.75 to +1.00 DK points. The
coverage-shell mechanism reaches that only at a near-maximal pairing. A 0.21%
Brier movement on 62 events is exactly what a 0.05-point effect looks like.

### 5. `wrCoverageMatchupExport.csv` — never testable

375 rows, per-shell receiver splits paired with opponent deployment rates and a
`COV GRADE`. **No cornerback appears in it** — it is a team coverage-*shell*
report, not a CB matchup report. Its `OPP` column reproduces the 2025 Week 1
schedule while its player stats are completed 2025 season totals, so it is
hindsight-paired and correctly quarantined as a schema sample.

---

## The gap: four coverage features are live and unvalidated

`featureset.NUMERIC_FEATURES` contains, under "Opponent secondary (CB coverage
from PFR advstats)":

- `cb_ypt_allowed_l6`
- `cb_comp_rate_allowed_l6`
- `db_ypt_allowed_l6`
- `top_cb_out`

All four entered in a single commit, `eecac23` on **2026-07-25**
("Cornerback coverage metrics: PFR advstats ingest, defense_week_coverage,
model features"). A search of the experiment ledger, the weekly-metrics and
ablation CSVs, and every report finds **no panel, ablation or replay record for
any of them.** The only mentions outside `featureset.py` are in code-review
packages and my own PIT audit.

Why this matters: `featureset.py` itself states the standing law —

> "every feature pays its own way through a replay before joining
> `NUMERIC_FEATURES`"

— and that law was articulated on **2026-08-01**, one week *after* these four
were added, in response to `depth_rank_delta` (−4.6 mean best) and
`team_ol_out` (−8.7). Two features from the same pre-law era were tested and
both proved materially harmful. These four were never tested at all.

**Be precise about what this does and does not imply.** The three failed
mechanisms above test *matchup fit* — a receiver's coverage-specific skill
crossed with an opponent's shell deployment. The `cb_*` features test something
different: *opponent secondary quality* from PFR charting. And `top_cb_out` is
different again — an availability signal closer to a vacancy/news feature, with
arguably the better prior of the four. The failures lower the prior on the
family; they do not refute these specific columns. The issue is that nobody
knows.

---

## Recommendation

**Add a `DROP_FEATURES` ablation of the `cb_*` / `top_cb_out` block to the
end-of-program forensic census.**

- The lever already exists (`DROP_FEATURES` is a registered environment
  variable in the engine's controlled list), so this is configuration, not code.
- It is one arm answering a question that has never been asked about four
  features that have shipped for three weeks.
- Given three independent failures of adjacent coverage constructs and a
  measured ~0.05-point ceiling on the shell-fit family, the prior that they
  contribute is low. If they are neutral, deleting them simplifies the model and
  removes a PFR-advstats dependency from the live path. If they are negative —
  as `team_ol_out` was, from the same era, at −8.7 — that is a free gain.
- Ablate the block **and** `top_cb_out` separately. The availability signal has
  a different mechanism from the three rate stats and deserves its own answer.

Two further notes for the forensic program:

1. **Record the coverage family on the kill list explicitly.** Three mechanisms,
   three failures, one of them a perfect 107-slate tie, plus arithmetic that
   caps the effect near 0.05 DK points. That is enough to close the shell-fit
   family durably so no future session re-derives it. The kill-list entry should
   carry the effect-size arithmetic, not just the dispositions — the numbers are
   what prevent the retry.
2. **Cornerback-level matchup remains untested, because no cornerback data
   exists in any source held.** Everything tested is team-shell. If a genuine
   CB/shadow-rate source is ever identified — CB identity, shadow rate, coverage
   snaps against a specific receiver — it is a *separate* hypothesis with a
   materially better mechanism story (concentrated and individual rather than
   diffuse and team-averaged) and should not be considered closed by the shell
   results.
