# Preregistration: study 92, S1 (shrink the projection the solver sees toward the slate's salary curve) and S2 (at least one $8,000+ player per lineup), on his armed Week-5 version, in the harness (DRAFT 2026-10-09)

**Status: DRAFT 2026-10-09 (15:09 CDT)** by the outside reviewer; the code is pushed, the smoke follows study 90's run. The
reviewer reviews, runs the binding census and FREEZES; the laptop acks.
- **Banks and seed:** **3012–3023** (set A 3012–3017, set B 3018–3023; sims bases 3062–3073, fields 3712–3723), seed 20261137 — the
  reviewer's block, clear of study 91's by construction; the laptop scans it.

**Units:** probabilities, counts and rates only. Dollars stay in BigQuery and private files.

## 1. Why — his request and his gates
- **The source:** `briefings/2026-week-05/2026-10-09-lineup-construction-suggestions.md` (review/construction-suggestions-20261009 @
  `3fb9e9d7`), S1 and S2.
- **The operator, 10-09 (in the outside reviewer's session; the laptop records it verbatim):** asked "What do you want done with S1
  (shrink projections toward salary, k = 0.7) and S2 (one $8,000+ star per lineup)?", he chose **"Test both tonight for live"**
  ("Same gate for S2 as S1; note the test model can't really measure S2, so its gate would be the Week-4 real-field check alone").
- **THE GATES (as put to him):**
  - **S1 (this study decides it):** GO LIVE iff SHRINK07 − ARMED > 0 on BOTH draws AND the pooled expected big seats ratio ≥ 0.80.
  - **S2 (this study does NOT decide it):** the laptop's Week-4 real-field replay — the armed version + the star rule beats the armed
    version on a higher mean finish percentile over all his Week-4 contests AND no fewer cashes. STAR1 here is informational.
- **The prior:** **S1 is new** — no construction-time shrinkage toward a salary curve in either ledger (the lab's salary-implied DST
  prior and the feature-level empirical-Bayes shrink are different things). **S2** relates to study 78 (Addendum 176): two $8,000+
  players on the first 8 rows was mixed (2023 −0.8, 2024 +4.5), a guard failed; its one-star side arm leaned positive but barely bound
  (the harness's books already hold a star in about 18.5 of 26 rows). **Prior: NO DIFFERENCE for both.**
- **THE TRANSFER CAVEAT (study 91's lesson, stated before the read):** in the harness the shrink acts on the simulator's means (the
  harness base), which are noisier than Fantasy Points' projections, so a shrink is likely to help MORE here than on his FP-built
  book. The laptop's outcome-blind Week-4 check of the shrink on his FP book (production flag `b4934067`) is required before the freeze
  and reported beside the read.

## 2. Arms (`experiments/s92_shrink_star.py`)
**Study 91's harness exactly** (its frozen module `s91_row_rules.py` `9cde18bd…`, sha-asserted; `rule_sets`, `arm_constraints`, 6p's
`row_rules`, 89's `own_caps` imported); **every arm is his ARMED W5 version**: the player cap 0.35 + the ownership cap at + 15 + at most
one TE and one player predicted < 3% per book row; the QB cap 5, the DST cap 6, the overlap limit 4, the cheap +2 block, 15 spares, Rev6.
- **ARMED** — the reference.
- **SHRINK07 (S1)** — the solver maximises base' = typical + 0.7 × (base − typical), where **typical = the MEDIAN of the raw base
  projection over the pool's players of the SAME position whose salary is within ±$500 of his (inclusive, himself included)**; the pool
  is the harness's after the min-projection filter (production: the union's pool after `excl`); **a player alone in his band keeps his
  projection** (typical = his own); DSTs unchanged. The cheap term is computed on the raw base and added unchanged; the pool, the caps,
  the ownership cap and the row rules are unchanged; the projection per row is reported on the RAW base.
- **STAR1 (S2)** — + at least one RB / WR / TE priced ≥ $8,000 per book row: a third constraint in the SAME `row_rules` list as te1 /
  low1 (two `row_rules` wrappers do not compose; the reviewer's point 3). **An infeasible solve drops all three row rules together**
  (the ownership cap kept), recorded; the census flags it above 0.5% of solves.
- **SHRINK07_STAR1** — both.

## 3. The read (the reader `scripts/s92_report.py`)
- 2023–24 only (36 slates); twelve banks as **two disjoint draws** and pooled; study 63's frozen statistics (a test asserts them);
  two-sided 0.95, B 20,000; the guards gate a PASS only.
- **DECISION: SHRINK07 − ARMED** on P(≥ 1 big seat) per slate; **his S1 rule printed as one line** (GO LIVE iff > 0 on both draws AND
  seats ≥ 0.80), guard 1 beside it.
- Also STAR1 − ARMED and SHRINK07_STAR1 − ARMED (informational; S2's gate is the real-field replay).
- **Under no true effect** a "better on both draws" rule passes about one time in four to one in three (the draws share slates and
  outcomes). **MULTIPLICITY:** tonight's go-live gates (study 89's arming, 91, now 92) all read the same 36 slates and real outcomes;
  the more such gates, the likelier a false GO — the real-week paper arms (study 38) are the check.

## 4. What the harness can and cannot say
- The harness cannot read S2 (stars already in most rows); STAR1's binding (rows with a star, ARMED vs STAR1) is reported.
- The shrink's size: the census prints the mean move of a skill projection per slate-bank and SHRINK07's rows shared with ARMED.
- The real-book check (before the freeze) and the real-field replay (S2's gate) are the laptop's, with the production flags.

## 5. Production — only on a GO
- Flags (`review/shrink-star-flags-20261009` @ `b4934067`, the outside reviewer's; parity against this module's `shrink` / `star_set`
  and 6p's `row_rules` byte for byte): `--proj-shrink-k 0.7 --proj-shrink-window 500` (an objective column only; the frame's proj /
  proj_tourney untouched) and `--mix-min-star 1 --mix-star-salary 8000` (with the row rules only). The laptop wires, merges on a GO,
  moves FRIDAY_HEAD; study 38 amendment 6r (the reviewer's) pairs the armed version without each live change on paper.

## 6. Smoke, census and integrity
- BLAS threads pinned to 1 (89's driver). Bank 1406 only for the smoke (after study 90's run): the unit tests, the mechanics smoke
  (2023 W3, 2023 W11, 2024 W10), the binding census, the full-path smoke (reader exit and line count only).
- **Code:** nfl2 `production/s92-shrink-star-20261009` @ `7913aefc` (branched from study 91's frozen branch `2515e42b`):
  `experiments/s92_shrink_star.py` `37980da6…`; `scripts/s92_drive.py` `55d3fab8…`; `scripts/s92_census.py` `7045bc40…`;
  **`scripts/s92_report.py` (the reader) `74aff8ae…`** (seed 20261137); `tests/test_s92_shrink_star.py` `e70d7b1b…` (7).
