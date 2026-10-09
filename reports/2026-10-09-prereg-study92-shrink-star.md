# Preregistration: study 92, S1 (shrink the projection the solver sees toward the slate's salary curve) and S2 (at least one $8,000+ player per lineup), on his armed Week-5 version, in the harness (FROZEN 2026-10-09)

**Status: FROZEN 2026-10-09 (15:57 CDT)** by the reviewer, after the outside reviewer's DRAFT, the smoke, the W4 real-book checks
and the binding census, before any scored bank. The text changed at the freeze in this status block and §6 only. The laptop acks.
- **Banks 3012–3023** (set A 3012–3017, set B 3018–3023), **seed 20261137**. The laptop's scan of both repositories (whole repos; the larger blobs not searched) found only incidental counts (3712–3723 as salaries and timings; 30xx pair-coverage counts in an old report; 3012–3023 as small counts), never a bank or seed; the reader seed 20261137 appears only in 92's own files; its full-set check of {b, b + 50, b + 700} over every used bank (nfl2 history, the recent studies, 90's 1992–2003, 91's 3000–3011) is clean.
- **Run environment:** PYTHONHASHSEED=0 for the census and the scored run (O-63), recorded in `RUN_ENV_s92.txt` committed with
  the confirmatory census.

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
- **The smoke (DONE after study 90's run; bank 1406; 2023 W3, 2023 W11, 2024 W10; `results_bank1406.jsonl` `be0c57a0…`; code `7913aefc`):**
  7 unit tests pass; every arm 41 rows within the armed caps, 8 term rows, in the pool; **0 infeasible** row-rule and ownership-cap
  solves in every arm (78 of 78); the pool per slate-bank: RB / WR / TE priced ≥ $8,000 6.0 (min 4); **the shrink moves a skill
  projection by 0.41 points on average**; rows with a star: ARMED 19.7 → STAR1 26.0 of 26 (stars per row 0.95 → 1.13); rows shared
  with ARMED: SHRINK07 0.67, STAR1 5.0, SHRINK07_STAR1 0.0 (none identical); the raw-base projection per row vs ARMED: SHRINK07
  −0.23, STAR1 −0.37, both −0.51; flex WR / TE / RB: ARMED 14.3 / 0 / 11.7, STAR1 18.0 / 0 / 8.0; the full path: the reader exited 0
  (43 lines; 55 with the two-draw path on a copy); only those were read.
- BLAS threads pinned to 1 (89's driver). Bank 1406 only for the smoke (after study 90's run): the unit tests, the mechanics smoke
  (2023 W3, 2023 W11, 2024 W10), the binding census, the full-path smoke (reader exit and line count only).
- **The W4 real-book checks** (the laptop's, outcome-blind, his FP book with the W5 arming, OFF `a4ab2839`; production flags
  `b4934067` on a local merge with integration, union_reselect `7b69025e`; `~/rehearsals/flagcheck-armed{S1,S2,S1S2}-20261009T2036*`),
  all against the ARMED book (the package + te1_low1: FP 140.00 per row; 1.00 TE, 0.231 low-owned and 0.769 stars per row; 14 rows
  with a star; 57 distinct players):
  - **+ S1** (k 0.7, ± $500): FP 139.86 (−0.14); 21 of 26 rows change; stars 0.615 per row (12 rows); 51 distinct players; the
    shrink moves 235 skill players by 0.435 points on average (max 1.83); the row rules applied, 0 re-solved.
  - **+ S2:** FP 139.73 (−0.27); 26 of 26 rows change; 26 rows with a star (from 14); 55 distinct players. **Only four non-QB skill
    players were priced $8,000+ on W4, so every row holds one of those four** (each at most 9 rows) -- the rule concentrates the
    book on the slate's few stars; the census reports the harness's pool (6.0 per slate-bank, min 4).
  - **+ S1 + S2:** FP 139.41 (−0.59); 26 of 26 rows change.
- **The binding (support) census** (the reviewer's; outcome-blind; bank 1406; all 36 slate-banks of 2023–24; code `7913aefc`
  clean; PYTHONHASHSEED=0; 7 tests pass; lab `results/s92/CENSUS_s92_binding.txt` `f1d048f0…`, the raw mechanics rows
  `census_mechanics_bank1406.jsonl` `ecc85823…` with no outcome field, committed at `065841ef`):
  - every arm 41 rows within the package's caps (9 / 6, QB 5, overlap 4), 8 term rows, in the pool; the ownership cap held on
    every solve in every arm;
  - the pool per slate-bank: RB / WR / TE priced ≥ $8,000 5.2 (min 1); the shrink moves a skill projection by 0.44 points on average;
  - **SHRINK07 (the decision):** 0 of 936 row-rule solves infeasible; rows shared with ARMED 1.17 of 26, none identical (not a
    dead change); projection per row on the raw base −0.31; star rows 15.1 → 12.8;
  - **STAR1 and SHRINK07_STAR1 (informational; S2 is decided by the laptop's replay, which it FAILED):** **47 of 936 row-rule
    solves (5.0%) fell back, ABOVE the 0.5% flag** -- on slate-banks with one or two stars the star rule is infeasible under the
    9-row cap, and the fallback (one row_rules list) drops the armed rules too; so these arms read as "the armed rules plus a
    star where feasible, otherwise neither" (2+ TE rows 0.75 / 0.97 of 26 against ARMED's 0). Disclosed; not decision-bearing.
    Star rows 15.1 → 24.7 of 26.
  - **PARITY:** ARMED builds identical rows to study 91's OWN15_TE1_LOW1 binding census on all 36 slate-banks.
- **Code:** nfl2 `production/s92-shrink-star-20261009` @ `7913aefc` (branched from study 91's frozen branch `2515e42b`):
  `experiments/s92_shrink_star.py` `37980da6…`; `scripts/s92_drive.py` `55d3fab8…`; `scripts/s92_census.py` `7045bc40…`;
  **`scripts/s92_report.py` (the reader) `74aff8ae…`** (seed 20261137); `tests/test_s92_shrink_star.py` `e70d7b1b…` (7).
