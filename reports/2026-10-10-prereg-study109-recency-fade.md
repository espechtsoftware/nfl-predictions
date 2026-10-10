# Preregistration: study 109, a recency fade — 2 points off a player whose last game was about twice his average — and at most one such player per lineup, on his live book, in the harness (DRAFT 2026-10-10, information for Week 6)

**Status: DRAFT 2026-10-10** (the times are this file's commits) by the outside reviewer; the design is the laptop's, agreed by
the lab reviewer. The lab reviewer reviews, runs the binding census, freezes, runs and reads; the laptop acks and reproduces.
**Information for Week 6 at the earliest** (there is no production switch for a projection fade; HOT1 has a known production
path, `row_rule_sets`, but no switch yet); no confirmation study is planned, since a pick would need one before any use.
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
- **HOT1, added before the freeze.** The research page (`briefings/2026-week-05/2026-10-10-winner-patterns-and-next-tests.md`
  §3.1, merged 10-10 05:47) proposed a row-rule arm beside the doses: in his real Weeks 2–4 fields a lineup holding a player off
  a 2× game was about half as likely to reach the top 1% as the same user's other lineups (odds 0.46 / 0.57 / 0.33), and his
  Sunday book held 0.96 such players per lineup (20 of 26 lineups at least one, 5 with two). Those are after-the-fact
  descriptions, not a build test. **The operator's answer, 10-10 morning (in the laptop's session): "Add both today
  (Recommended)"** — HOT1 here and the value cap in study 110, both before their freezes.

## 2. Arms (`experiments/s109_recency_fade.py`)
- **Pre-freeze change (2026-10-10, before any scored bank; the lab reviewer's call):** the operator adopted study 97 / 99's
  RBMATE4_FAVHI at about 05:00 ("Yes, it seems the RB one should be adopted"; armed for Week 5, production `e8a4d0a4`). Under the
  post-selection law, a read on the book without it would be a verdict for a book he no longer enters, so **every arm now carries
  it**: 96's `combo_rules` with 97's FAVHI pairs replaces 93's `lead_rules`. LIVE = his armed Week-5 book, checked equal to
  study 97's RBMATE4_FAVHI, rows and dealing, on bank 1406 (`--ref97`). The census adds the RB mate's slots (4 per book, every
  arm). For study 109 the FAVHI pairs are computed once on the shared pool (the fade changes only the objective).

**Study 95's harness exactly** (its frozen module `s95_shapes.py` `46b80611…`, sha-asserted; `run()` = 95's `run()` with ten
listed edits, a test asserts it); every arm his armed Week-5 construction (the package + te1 / low1 + ONECATCH + the adopted
FAVHI through 96's `combo_rules`, 89's `own_caps`; QB cap 5, overlap 4, the cheap +2 block on 8 rows, the ownership cap + 15, A1
.30 / A2 .14 / B .28 / C .28), **one change per arm:**
- **LIVE** — no fade.
- **FADE2** — a skill player (QB / RB / WR / TE) whose **last regular-season game this season** scored **≥ 2.0 ×** max(the mean
  of his up to 4 games before it, 5), with ≥ 2 such games, has **2 points taken off his simulated mean** ("twice the average").
- **FADE2_16** — the same at **1.6 ×** (study 65's dose).
- **HOT1** (added before the freeze) — **at most one "hot" skill player per book row**; hot = FADE2's flag exactly (last game ≥
  2.0 × max(the mean of his up to 4 games before it, 5), ≥ 2 such games). **No fade:** the objective is LIVE's. The vehicle is a
  row rule, (the hot ids, ≤ 1), in the same tier as te1 / low1 (study 91's mechanics: an infeasible solve is re-solved without
  the row rules, recorded); spares never.
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
- **Multiplicity:** three arms (two doses and HOT1) on the same 36 slates as studies 89–108.

## 4. Honest limits and the census
- **The harness fades its own simulated mean; his book builds on Fantasy Points' projections, which may already price in a big
  last game** (FP's projections move week to week; the simulator's mean is fit on longer histories). A gain here need not carry
  over.
- **The census, per arm:**
  - the skill players flagged per slate, by position, and how many had a last game this season;
  - LIVE's book rows holding a flagged player, and the arm's own rows holding one (the binding);
  - **HOT1:** the hot players per slate-bank, hot players per book row and rows with 2+ hot, every arm (HOT1 wants 0 rows with
    2+; any is flagged);
  - fallbacks; ONECATCH; the RB mate's slots; rows shared with LIVE; projection per row on the UNFADED mean (the fade's cost);
  - LIVE == study 97's RBMATE4_FAVHI on bank 1406, rows and dealing (`--ref97`).
  - Per-slate fields stay outside the blocks the reader compares.
  - A fade that never binds is reported before the freeze (the fade arms only).

## 5. Smoke and code
- BLAS threads pinned; PYTHONHASHSEED=0; bank 1406 only for the smoke (the unit tests, the mechanics smoke 2023 W3 / 2023 W11 /
  2024 W10, the census, the full path: reader exit and line count only).
- **The re-smoke after HOT1 (REQUIRED before the freeze; a gap the lab reviewer names):** (filled in when done).
- **The first smoke, before HOT1 (DONE in the gap the lab reviewer named during the laptop's study-106 ack; bank 1406; 2024 W10, 2023 W11, 2023 W3;
  PYTHONHASHSEED=0; `results_bank1406.jsonl` `8d508ec6…`; code `f3cd184e`, the census fixed at `070003f1`):** every arm 41 rows
  within the package's caps; RB-mate slots 12 of 12 ruled, every arm; ONECATCH 42 of 42, none dropped, every arm; **LIVE
  identical to study 97's RBMATE4_FAVHI, rows and dealing, on 3 of 3 slate-banks**; **the fade binds:** FADE2 flags 21.0
  skill players per slate-bank (QB / RB / WR / TE 2.3 / 7.0 / 9.7 / 2.0), LIVE's book rows holding one 19.0 of 26 (min 15),
  the arm's own rows 2.0; FADE2_16 flags 36.3, LIVE's rows 23.3 (min 23), its own 8.3; the full path: the reader exited 0 (41
  lines; 52 two-draw); only the census, the exit codes and the line counts were read.
  - **Fixed before the freeze:** 8 of 9 unit tests passed; the outcome-blind test flagged the census's parity line, which read
    the fade's dose setting as `m["own"]["fade"]["points"]`; it now reads `.get("points")`, the same setting (census
    `7025a16e`). No module or reader change; the unit re-run waits for a machine gap.
  - **Fixed after HOT1, before any run:** the census's parity expected te1 / low1 on every arm, so HOT1's recorded rules would
    have stopped it at the first row. It now mirrors the module's rules per arm (a test asserts it) and checks HOT1's recorded
    flag and count. The same defect was found in study 110 first; 106 and 112 were swept and agree.
- **Code:** nfl2 `production/s109-recency-fade-20261010` @ `96745acd` (off study 102's frozen `969f4d3d`; s65 brought in byte for
  byte from `cf53ef1`, s96 / s97 from `3cf3e8eb` / `af07583e`; HOT1 at `3587f594`, the census fix at `96745acd`):
  - `experiments/s109_recency_fade.py` `996077e6…` (pins s95 `46b80611…`, s65 `7667c963…`, s97 `7df6f324…`)
  - `scripts/s109_drive.py` `f1845246…`
  - `scripts/s109_census.py` `30514577…`
  - **`scripts/s109_report.py` (the reader) `99b66dd8…`** (seed 20261151)
  - `tests/test_s109_recency_fade.py` `2f94cce8…` (10)
