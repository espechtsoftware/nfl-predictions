# Preregistration: study 106, a projection floor — "no player with a projected score less than 8" — on his live book, in the harness (DRAFT 2026-10-10)

**Status: DRAFT 2026-10-10** (the times are this file's commits) by the outside reviewer; the design is the lab reviewer's final
call, following the laptop's plan. The lab reviewer reviews, runs the binding census, freezes, runs and reads; the laptop acks and
reproduces. **Information for his decision; a pick goes to study 107**, whose preregistration is committed before this study's
READ.
- **Banks and seed (the laptop's full-set check: CLEAN against every used or reserved bank, studies 90–105; text scan to
  follow):** **3482–3493** (set A 3482–3487, set B 3488–3493; sims bases 3532–3543, fields 4182–4193); the reader's bootstrap
  seed **20261149**.

## 1. Why
- **The operator, 10-10 early morning, in the laptop's session (verbatim):** "Have you tried any kind of rules like "no player
  with a projected score less than 8"". And then: "Maybe start with that and if it's successful, try different min projections
  per position".
- **Neither ledger has a floor above 1.0** (production's `--min-proj` 1.0 drops only the near-inactive).
- **The prior, stated first: NO DIFFERENCE, leaning negative.** The ledger's construction evidence favors cheap players:
  - Milly winners carry a sub-$4,000 punt (Addenda 4–5);
  - in his real W1–4 Millionaires, a lineup with 2+ sub-$4,000 non-DST players reached the top 1% more often than the same
    user's other lineups: odds ratio 1.88 [1.75, 2.01], within user-week (`reports/2026-10-07-brainstorm-data-and-models.md`
    §1.1). That is after the fact, like any outcome-conditioned profile;
  - the cheap +2 block is in the live book as a trial.
  - A floor of 8 or more removes most sub-$4,000 skill players.
- **On his armed Week-4 book, by Fantasy Points' projections (the laptop):** a floor of 6 touches 0 of 26 lineups; 8 touches 3;
  10 touches 13.

## 2. Arms (`experiments/s106_min_proj.py`)
**Study 95's harness exactly** (its frozen module `s95_shapes.py` `46b80611…`, sha-asserted; `run()` = 95's `run()` with eight
listed edits, a test asserts it); every arm his live Week-5 construction (the package + te1 / low1 + ONECATCH through 93's
`lead_rules`, 89's `own_caps`; QB cap 5, overlap 4, the cheap +2 block on 8 rows, the ownership cap + 15, A1 .30 / A2 .14 / B .28
/ C .28), **one change: the projection floor:**
- **LIVE** — floor 1.0 (the harness's MIN_PROJ = production's `--min-proj` 1.0).
- **MINPROJ8 / MINPROJ10 / MINPROJ12** — floors 8 / 10 / 12.
- **The floor's mechanics, as production applies `--min-proj`:** every skill player (QB, RB, WR, TE; DSTs exempt) whose simulated
  mean is below the floor leaves the pool **before** the ownership caps, the row-rule sets (TEs, low-owned) and the cheap block's
  term are computed. Production's `excl` feeds the pool, `own_cap_rows`, `row_rule_sets` and the term block's coverage
  (`union_reselect` 5faf2f05). The predicted ownership is rescaled once over the frame, as production's `own_cap_rows` rescales
  over the frame's skill players; each arm takes its slice.

## 3. The read (the reader `scripts/s106_report.py`)
- **Study 100's reader** with listed edits (a test asserts them); study 63's statistics; two draws and pooled; two-sided 0.95, B
  20,000.
- **Per arm − LIVE:**
  - P(≥ 1 big seat), its guards and verdict;
  - **his rule's line** (better on both draws AND the pooled expected big seats ratio ≥ 0.80);
  - the mean best real lineup points and P(best ≥ 200), printed (information).
- **THE PICK (pre-stated; a tested function `floor_pick`):** among the arms passing **his rule** (guard 1 printed, not gating),
  the **largest pooled gain** in P(≥ 1 big seat). None → **"keep the live book"**. A pick goes to study 107.
- **MULTIPLICITY, plainly:** three floors on the same 36 slates as studies 89–105; about one passes by chance.

## 4. What the harness can and cannot say — honest limits
- **The floor here is on the harness's simulated mean; his book builds on Fantasy Points' projections.**
- **Production's `--min-proj` filters on `fr.mean_projection`, OUR model's projection (the laptop's finding).** A live "FP
  projection ≥ X" floor needs a small production change (filter on the projection source the book uses). `LIVE_MIN_PROJ` also
  cuts the supply builds' candidates.
- **So this study is information for Week 6** unless a floor passes clearly, study 107 holds it, and that production change is
  built and checked.
- **The census per arm:**
  - the pool and its skill players;
  - the players each floor drops by position;
  - the cheap players left (eligible / given the term);
  - the TE and low-owned pools;
  - LIVE's book rows that held a dropped player (each floor's binding on the harness's own scale);
  - fallbacks; ONECATCH; rows shared with LIVE; projection per row;
  - LIVE == study 102's LIVE on bank 1406 (`--ref102`).
  - Per-slate fields stay outside the blocks the reader compares.

## 5. Smoke, census and integrity
- BLAS threads pinned; PYTHONHASHSEED=0; bank 1406 only for the smoke (the unit tests, the mechanics smoke 2023 W3 / 2023 W11 /
  2024 W10, the census, the full path: reader exit and line count only).
- **The smoke:** (a machine gap the lab reviewer names; filled in when it ends).
- **Code:** nfl2 `production/s106-min-proj-20261010` @ `c484751f` (off study 102's frozen `969f4d3d`):
  - `experiments/s106_min_proj.py` `66265fbc…` (pins s95 `46b80611…`)
  - `scripts/s106_drive.py` `8d5b58e5…`
  - `scripts/s106_census.py` `5c92123f…`
  - **`scripts/s106_report.py` (the reader) `fb32ae7a…`** (seed 20261149)
  - `tests/test_s106_min_proj.py` `6c7df8bf…` (9)
