# Preregistration: study 109, a recency fade — 2 points off a player whose last game was about twice his average — on his live book, in the harness (DRAFT 2026-10-10, information for Week 6)

**Status: DRAFT 2026-10-10** (the times are this file's commits) by the outside reviewer; the design is the laptop's, agreed by
the lab reviewer. The lab reviewer reviews, runs the binding census, freezes, runs and reads; the laptop acks and reproduces.
**Information for Week 6 at the earliest** (there is no production switch for a projection fade); no confirmation study is
planned, since a pick would need one before any use.
- **Banks and seed (the laptop's full-set check: CLEAN against every used or reserved bank, studies 90–108; text scan to
  follow):** **3506–3517** (set A 3506–3511, set B 3512–3517; sims bases 3556–3567, fields 4206–4217); the reader's bootstrap
  seed **20261151**.

## 1. Why
- **The operator, 10-10 early morning, in the laptop's session (verbatim):** "I believe the pros fade players with a big
  previous week. Perhaps try something like a 2 point reduction in the projection when the players last game was twice the
  average or something similar".
- **The prior, stated first: NO DIFFERENCE, leaning negative.** Study 65 (Addendum 167) read the pros briefing's S3 recency
  fade as an 8-row block in place of the cheap block (−1 for a last game ≥ 1.6× his average, −1 for a salary rise ≥ $300):
  - RECENCY_B8 − the cheap-block book: −2.5 (−7.2 to +2.0), expected big seats ×0.92, contradicted on 2022;
  - the cheap +2 and the recency flags in one block: −2.1, ×0.91.
  - That was a different form (a block, −1 per flag, with the salary flag) from this whole-book −2.
  - **The pros briefing behind the idea** (`briefings/2026-week-05/2026-10-08-how-the-pros-pick-players.md`):
    - §4: the max-entry regulars do sell last week's scorers ("beat our projection last week": −0.90, z −5.3) while the crowd
      buys them; but none of those habits predicted points beyond the market, so they read as leverage, not information;
    - §7 (three seasons): a player who beat the market last game had a lower big-game chance (−1.8 points per sd, z −1.6) and
      a higher bust chance (+1.8, z +2.2) the next week, in all 3 seasons, with no change in mean points beyond the market.
    - So the fade's case is the tail and the crowd's ownership, not the mean; the harness reads it on big seats.

## 2. Arms (`experiments/s109_recency_fade.py`)
**Study 95's harness exactly** (its frozen module `s95_shapes.py` `46b80611…`, sha-asserted; `run()` = 95's `run()` with seven
listed edits, a test asserts it); every arm his live Week-5 construction (the package + te1 / low1 + ONECATCH through 93's
`lead_rules`, 89's `own_caps`; QB cap 5, overlap 4, the cheap +2 block on 8 rows, the ownership cap + 15, A1 .30 / A2 .14 / B .28
/ C .28), **one change: the fade:**
- **LIVE** — no fade.
- **FADE2** — a skill player (QB / RB / WR / TE) whose **last regular-season game this season** scored **≥ 2.0 ×** max(the mean
  of his up to 4 games before it, 5), with ≥ 2 such games, has **2 points taken off his simulated mean** ("twice the average").
- **FADE2_16** — the same at **1.6 ×** (study 65's dose).
- **The flag** is study 65's frozen `last_game()` (`s65_tailtilt.py` `7667c963…`, from its READ `cf53ef1`). It uses nflverse
  weekly DK points in every time slot, prior weeks only, so it is point-in-time. The multiple is a parameter of study 65's own
  `big_last` rule (a test asserts the 1.6 case equals it).
- **The fade enters every row's objective:** the live block, the cheap block's base and the spares. The cheap block's term is
  recomputed on the faded mean (its coverage gate). The pool, the ownership caps and the row-rule sets are unchanged.

## 3. The read (the reader `scripts/s109_report.py`)
- **Study 100's reader with study 106's edits, relabelled** (a test asserts them); study 63's statistics; two draws and pooled;
  two-sided 0.95, B 20,000.
- **Per arm − LIVE:**
  - P(≥ 1 big seat), its guards and verdict;
  - **his rule's line** (better on both draws AND the pooled expected big seats ratio ≥ 0.80);
  - the mean best real lineup points and P(best ≥ 200), printed (information).
- **THE PICK (pre-stated; study 106's tested function `floor_pick`):** among the arms passing his rule (guard 1 printed, not
  gating), the largest pooled gain. None → "keep the live book". **A pick is information for Week 6**; it would need a fresh-draw
  check and a production switch before any use.
- **Multiplicity:** two doses on the same 36 slates as studies 89–108.

## 4. Honest limits and the census
- **The harness fades its own simulated mean; his book builds on Fantasy Points' projections, which may already price in a big
  last game** (FP's projections move week to week; the simulator's mean is fit on longer histories). A gain here need not carry
  over.
- **The census, per arm:**
  - the skill players flagged per slate, by position, and how many had a last game this season;
  - LIVE's book rows holding a flagged player, and the arm's own rows holding one (the binding);
  - fallbacks; ONECATCH; rows shared with LIVE; projection per row on the UNFADED mean (the fade's cost);
  - LIVE == study 102's LIVE on bank 1406 (`--ref102`).
  - Per-slate fields stay outside the blocks the reader compares.
  - A fade that never binds is reported before the freeze.

## 5. Smoke and code
- BLAS threads pinned; PYTHONHASHSEED=0; bank 1406 only for the smoke (the unit tests, the mechanics smoke 2023 W3 / 2023 W11 /
  2024 W10, the census, the full path: reader exit and line count only).
- **The smoke:** (a machine gap the lab reviewer names; filled in when it ends).
- **Code:** nfl2 `production/s109-recency-fade-20261010` @ `d05b72d0` (off study 102's frozen `969f4d3d`; s65 brought in byte for
  byte from `cf53ef1`):
  - `experiments/s109_recency_fade.py` `d3325f39…` (pins s95 `46b80611…`, s65 `7667c963…`)
  - `scripts/s109_drive.py` `f1845246…`
  - `scripts/s109_census.py` `c3955b41…`
  - **`scripts/s109_report.py` (the reader) `f1c0790b…`** (seed 20261151)
  - `tests/test_s109_recency_fade.py` `ca08e23f…` (9)
