# Preregistration: study 106, a projection floor — "no player with a projected score less than 8" — on his live book, in the harness (DRAFT 2026-10-10)

**Status: DRAFT 2026-10-10** (the times are this file's commits) by the outside reviewer; the design is the lab reviewer's final
call, following the laptop's plan. The lab reviewer reviews, runs the binding census, freezes, runs and reads; the laptop acks and
reproduces. **Information for his decision; a pick goes to study 107**, whose preregistration is committed before this study's
READ.
- **Banks and seed (the laptop's full-set check and text scan: CLEAN against every used or reserved bank, studies 90–105;
  the only hits salaries, timings, counts, player ids or hex):** **3482–3493** (set A 3482–3487, set B 3488–3493; sims bases 3532–3543, fields 4182–4193); the reader's bootstrap
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
- **Pre-freeze change (2026-10-10, before any scored bank; the lab reviewer's call):** the operator adopted study 97 / 99's
  RBMATE4_FAVHI at about 05:00 ("Yes, it seems the RB one should be adopted"; armed for Week 5, production `e8a4d0a4`). Under the
  post-selection law, a read on the book without it would be a verdict for a book he no longer enters, so **every arm now carries
  it**: 96's `combo_rules` with 97's FAVHI pairs replaces 93's `lead_rules`. LIVE = his armed Week-5 book, checked equal to
  study 97's RBMATE4_FAVHI, rows and dealing, on bank 1406 (`--ref97`). The census adds the RB mate's slots (4 per book, every
  arm). For study 106 the FAVHI pairs are computed **on each arm's pool**: production's `rb_mate_scope_teams` runs
  on the frame minus `excl`, so a floor that drops a QB or an RB drops its pair.

**Study 95's harness exactly** (its frozen module `s95_shapes.py` `46b80611…`, sha-asserted; `run()` = 95's `run()` with eight
listed edits, a test asserts it); every arm his live Week-5 construction (the package + te1 / low1 + ONECATCH through 93's
`lead_rules`, 89's `own_caps`; QB cap 5, overlap 4, the cheap +2 block on 8 rows, the ownership cap + 15, A1 .30 / A2 .14 / B .28
/ C .28), **one change: the projection floor:**
- **LIVE** — floor 1.0 (the harness's MIN_PROJ = production's `--min-proj` 1.0).
- **MINPROJ8 / MINPROJ10** — floors 8 (his number) and 10 (a stronger dose).
- **Pre-freeze change 2 (2026-10-10, before any scored bank): a floor of 12 is not an arm.** The laptop's Week-4 check on
  FRIDAY_HEAD `b00c5e43` found that **production refuses that book** with the cheap block on: a floor of 12 removes every
  cheap-block player ("term_rows 8 needs … a term_bonus"), where the harness's `block_term` would build it silently without
  the block — a book production cannot build. The census now flags any arm whose cheap block is empty or unapplied on a slate.
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
- **MULTIPLICITY, plainly:** two floors on the same 36 slates as studies 89–105; about one passes by chance in two studies.

## 4. What the harness can and cannot say — honest limits
- **A live floor is one existing setting** (`LIVE_MIN_PROJ` = X) **and floors Fantasy Points' projection**, which is exactly his
  question. With `UNION_PROJ_SOURCE=fp`, production's `apply_proj_source` replaces the frame's projection with FP's before the
  floor is applied (`union_reselect` l. 1673, then the floor at l. 1683 / 1765). The laptop's Week-4 check (his armed book with
  FAVHI): an FP floor of 8 changes 3 of 26 lineups; 10 changes 23, with sub-$4,000 skill slots 35 → 9; every book slot clears its
  floor by FP. **Correction (2026-10-10, before the freeze):** an earlier draft of this section said production floors our
  model's projection and that an FP floor needs a production change; both were wrong.
- **The harness floors its own simulated mean** (it has no FP history), so a passing harness floor transfers to the FP floor at
  the same number only approximately: the two remove different players. The census's pool removed per arm shows the
  harness's binding beside the Week-4 numbers. The thresholds stay at his 8 and a stronger 10, not matched by pool share.
- **A side effect to disclose for any production switch:** the host also passes `LIVE_MIN_PROJ` to the lab's candidate
  generation (`MINPROJ_ARGS`) for the supply builds.
- **Still standing:** production refuses a floor of 12 with the cheap block on (§2).
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
- **Code:** nfl2 `production/s106-min-proj-20261010` @ `3dfe4c95` (off study 102's frozen `969f4d3d`; s96 / s97 byte for byte,
  `0363a84f…` / `7df6f324…`):
  - `experiments/s106_min_proj.py` `02fae29e…` (pins s95 `46b80611…`, s97 `7df6f324…`)
  - `scripts/s106_drive.py` `8d5b58e5…`
  - `scripts/s106_census.py` `1258f948…`
  - **`scripts/s106_report.py` (the reader) `9d3b4dbb…`** (seed 20261149)
  - `tests/test_s106_min_proj.py` `9aa83d42…` (9)
