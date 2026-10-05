# Preregistration: study 16, the thesis portfolio (scenario allocation) (FROZEN 2026-10-05)

This study replaces study list items 13 and 14 and absorbs X1's sleeve. It runs alongside study 15. The design brief is
the reviewer's (10-05), sent at the operator's "yes"; the reviewer's second-pass definitions are applied. Frozen before any experiment, driver or reader exists; later changes are dated deviation notes at the end.

**The operator's thesis (10-05, verbatim):** "begin with a thesis: games A, B, C and D are expected to be high scoring;
from those games identify the high-upside / boom players; those are the core, then other players mixed in, a small
percentage of contrarian plays (individual players paired with the core lineups, and full lineups based on a game going
differently than predicted)."

## Why this is new
- The pool is already scenario-built: boom lineups are the best lineup per simulated world.
- The SELECTION step is what collapses the scenarios toward the mean. In Week 4, 61% of entries went to the top-total
  game.
- The money gate's monkeys show that selection adds nothing over random rows from our own pool.
- This study replaces mean-max selection with deliberate SCENARIO ALLOCATION. It selects among rows the existing
  optimizer produces. It is not a new generator, which keeps it outside EPI's closure.

## Arms (the L-series / study-1 harness; co-run; fresh banks)
- **C:** the current book (study 1's C builder, the head layout, the overlap limit M 5 / ceiling 10, hard-set).
- **TP, the thesis portfolio, with K = 105 rows allocated by cell.** A row's primary game is its QB's game. Game rank =
  the pre-lock total rank (study 1's `game_ranks`: rank 1 = highest total; ties broken by game id, ascending).
  1. **The core (85% of rows):** rows whose QB's game ranks ≤ 4. The share per game is ∝ P3(rank), from study 1's
     frozen 2014–21 table (rank 1 0.409, 2 0.336, 3 0.234, 4 0.241), renormalised over ranks 1–4.
  2. **The alternative scenarios (15%, fixed): "a game goes differently than predicted"**, split evenly between:
     - (b) **mid-total shootouts:** the QB's game ranks 5–8, the row holds ≥ 5 players from that game, including ≥ 1
       bring-back. The share is even across ranks 5–8;
     - (c) **favourite blowouts:** the QB's team is favoured by ≥ 6 (the frame's pre-lock `spread` ≤ −6). The row holds
       that team's QB AND its lead RB, and AT MOST 1 player from the opponent.
       - The lead RB is the team's RB with `depth_rank` 1, with ties broken by the higher projected carries
         (`component_mean_carries`).
       - If no team on the slate is favoured by ≥ 6, or the spread is missing, cell (c) is empty and its share goes to
         the core. The census counts it.
  3. **Rows per cell:** largest-remainder rounding of share × 105.
  4. **Rows within a cell:**
     - Each comes from the same sequential optimizer, objective (mean + 0.10 × LAG) and caps (player 52, DST 26,
       ≤ 7 shared), with cell membership as constraints.
     - Cells are filled in descending size, and the player and DST caps are shared across cells.
     - A cell that cannot be filled passes its shortfall to the core game with the highest P3. The census counts
       every pass.
  5. **What it is:** an ALLOCATION rule over the same projection-based solves, like study 1's game cap. It creates no
     new worlds or distributions, so it is not a new generator and stays outside EPI's closure. The transfer check
     implements it in `union_reselect`'s pmo_x50 main, as study 1's AG did.
- **Exploratory, never decision-bearing:** TP10 and TP20 (alternative share 10% / 20%).
- **Excluded: player-level contrarian.** The operator's "individual players paired with the core" is NOT an arm.
  - The winners study found chalk lift at the 2026 top 0.1%.
  - The ownership term moved +0.19 sd TOWARD chalk on the panel.
  - A4 (no tilt) did worse than A1 in the money gate.
  - L05's chalk-core cells.
  - The game-level form of contrarianism is the alternative-scenario share above.

## Fixed across arms
K 105; the LAG 0.10 term; the Week-4 mean-track plan (147 entries); L13's 36 slates; the gated field sampler; banks
1409/1410 (scanned before use); smokes on throwaway bank 1406. 2022 is NOT used: no point-in-time LAG ownership file exists for it (`results/l20_sets/lag` covers 2023–24 only), and the term must be identical and pre-lock across arms.

## Endpoints and decision rule
- **PRIMARY = TICKETS:** dealt entries at or above each contest's line, summed per slate, TP − C, paired.
  - Season-clustered bootstrap, B 20,000, seed 20261005. One decision arm, two-sided 0.975.
  - **PASS** = lower bound > 0, both season means ≥ 0, and the guard holds.
- **GUARD:** mean entry finish, non-inferiority at **m = 0.015**, confirmed by the operator for THIS study (10-05, his answer: "1.5 points (same as 1b)"). One-sided lower bound at 0.975 > −0.015.
- **Secondaries:** zero-ticket slates, best ≥ 200, the worst-decile slate, the share of entries per cell (realized
  allocation), and the maximum entry exposure.
- **(iii) A simulated line-crossing SECONDARY (never decision-bearing; the reviewer):**
  - per book, the mean over the run's own simulated worlds of the share of dealt entries at or above their
    contest's line, with the line taken from the simulated field in that world;
  - it is outcome-free and far better powered, and shows whether TP shifts the crossing distribution even when
    realized tickets cannot resolve it.
- **Rationale:** studies 1 and 1b moved line-crossings UP while moving the mean DOWN. For satellites, crossing the line
  is the objective. Those secondaries motivate the primary; they are not evidence (5 arms, no intervals).
- **Counter-prior:** the winners study found concentration +EV at the satellite lines. The test is built to come out
  either way.

## Power: tickets on 36 slates (from studies 1 and 1b's already-read banks; outcome-blind about 16)
C averages 8.7 tickets per slate under the Week-4 plan. The table gives the paired per-slate SE of the ticket
difference for books that change by different amounts.

| analogue | how much the book changes | SE (tickets / slate) | two-sided 0.975 half-width | 80% power MDE |
|---|---|---|---|---|
| study 1 G (game cap) | small | 0.35 | 0.78 | 1.07 (≈ 12% of C) |
| study 1 G+P4 | moderate | 0.78 | 1.75 | 2.41 (≈ 28%) |
| study 1b EW35 | large | 1.19 | 2.67 | 3.67 (≈ 42%) |
| study 1b EW | large | 1.32 | 2.95 | 4.05 (≈ 46%) |

TP re-allocates the whole book, so it will sit near the EW rows. **On 36 slates the tickets primary resolves only a
very large effect, about +40–45% more tickets. A tickets effect smaller than about +40% will read NO DIFFERENCE.** The
operator was told this before freezing (10-05). Of the options considered:
- (ii), more slates, was not available: there is no 2022 LAG file;
- the study runs as (i), with (iii) as a secondary.

## Integrity
- The reader is frozen before any scored bank.
- An outcome-blind census: cell sizes, cell shortfalls and passes, the realized allocation, entries changed vs C.
- A full-path smoke, discarded unread.
- Unit tests, including that cell membership binds, plus a mutation check.
- A transfer check on the real 2026 pools afterwards (descriptive).

## Priors cited
- X1 steps 1–2:
  - the top-total game is the week's top scorer 16–19% of the time;
  - field leverage is 1.31 on the top total, negative on low totals;
  - our error was concentration size.
- Studies 1 and 1b: the secondaries motivate the primary.
- LEDGER 016 and PREREG-015: the stack and the house rules.
- EPI's closure: this is SELECTION, not a new generator.

## Reviewer decisions (10-05)
- Cells (b) and (c) and the core are defined as above.
- The constraint form counts as selection, an allocation rule, not EPI.
- Power: (ii) if 2022 has frames AND a pre-lock LAG file. It has the frames but not the LAG file, so the study runs as
  (i), with (iii) as a secondary.
- The margin is confirmed by the operator for this study.

---

## Deviation note 1 (2026-10-05, before any smoke, census or scored bank): two build mechanics the frozen text left open
1. **The book's RANK ORDER.**
   - The head layout deals the top ranks into most contests, so the order of TP's rows decides the entry allocation.
   - TP's ranks interleave the cells by D'Hondt: at each rank, the cell with the largest rows / (taken + 1); ties go
     to the earlier cell (core by game rank, then mid, then blow). Each cell's rows are in its own solve order.
   - So every prefix of ranks carries the target shares. C keeps its solve order.
2. **Several blowout teams on one slate.** When more than one team is favoured by ≥ 6, the blowout share is split
   EVENLY across them, largest-remainder.

Also fixed in the code, consistent with the frozen text:
- The opponent's "at most 1 player" counts the opponent's DST.
- Cell (b)'s "≥ 5 players from that game" counts a DST toward its real game (study 1's `game_key_map`).
- The simulated line-crossing secondary uses 1,000 of the run's 20,000 worlds (every 20th) and the first 20,000 of the
  200,000 sampled field lineups, in chunks of 100 worlds.
- Code: nfl2 `production/s16-thesis-portfolio-20261005`. Tests: 7 pass; a mutation that drops the cell constraints is
  caught.

## Deviation note 2 (2026-10-05, after an outcome-blind mechanics smoke, before any census or scored bank): cells (b) and (c) redefined (reviewer-accepted)
**Evidence** (throwaway bank 1406, 2023 W9, mechanics only):
- MAX_PER_GAME 4 is a house rule fixed across arms. It counts every player whose `game_id` is the game. DSTs carry
  side ids, so a DST is NEVER counted.
- **(c) as frozen was INFEASIBLE.** A row needs the favoured QB, 2 WR/TE (the stack rule), the lead RB and 1
  bring-back: 5 players from one game.
  - Three teams qualified (BAL, CLE, NO; spread ≤ −6). All three cells filled 0 rows, and 8 rows passed to the core.
- **(b) as frozen was perverse.** "≥ 5 players from that game" could be met ONLY through that game's DST, because the
  stack's QB + 2 + 1 = 4 is the per-game maximum. So every mid row carried a DST from the game it bet would shoot out.
- **The smoke allocation:** rows core/mid/blow 0.924 / 0.076 / 0.000, against the target 0.85 / 0.075 / 0.075.

**The change** (made outcome-blind, before any census):
- **(b) mid-total shootout:** the QB's game at total rank 5–8, with the full stack (QB + 2 WR/TE + bring-back = 4, the
  per-game maximum). "≥ 5 players" is dropped.
- **(c) favourite blowout, RB-led** (the reviewer's original brief): the favoured team's (spread ≤ −6) lead RB
  (depth_rank 1, ties by projected carries) AND that team's DST, with at most 1 opponent player.
  - The QB stack goes wherever the optimizer puts it, under the usual rule.
  - It is legal: MAX_PER_GAME never counts a DST (side ids), and the RB-vs-DST rule bars only the OPPOSING DST.
- MAX_PER_GAME is NOT lifted for any arm. That would change a house rule inside one arm and confound it.
- The census reports, per arm and per cell type, the TARGET share against the REALIZED share and the pass-to-core
  count, so a cell that rarely fills is visible before scoring.

## Deviation note 3 (2026-10-05, before any scored bank): the reader is frozen and the census is in
**Code:** nfl2 `production/s16-thesis-portfolio-20261005` @ e9b329e.
- Reader `scripts/s16_report.py`, sha256 `04ed4fda8d67ccc194bd90165843aeced115aae025edfa22e205996bb0b40b9f`.
- Experiment `experiments/s16_thesis_portfolio.py`, sha256
  `8d3414a3b7fd77f41d049638cb881133075e9fe41cc12ebe8555db450f186930`.
- **Tests (8):**
  - allocation, D'Hondt, the cells (note 2), shortfall passes, the cell constraints reaching every solve (a mutation
    dropping them is caught), and the verdicts;
  - the reader's printed and used LEVELS asserted against this text: primary two-sided 0.975, guard one-sided 0.975.
- **The re-smoke on throwaway 1406 (2023 W9 mechanics; 2024 W6 full path) passed:** build and reader rc 0, output
  deleted unread.
- **Banks 1409/1410:** unused in the all-branch scan; since then the only bank labels committed are 1404–1408 (this
  session).

**The outcome-blind census** (banks 1409/1410, mechanics only, 72 slate-banks, no errors, no short books; verbatim in
the lab at `results/s16/CENSUS_s16.txt`). Shares are core / mid / blow.

| arm | TARGET share | REALIZED rows | REALIZED dealt entries | shortfall passes (mean, max) | entries changed vs C |
|---|---|---|---|---|---|
| TP | 0.852 / 0.075 / 0.073 | 0.873 / 0.076 / 0.050 | 0.891 / 0.068 / 0.041 | 2.18, 8 | 0.959 |
| TP10 | 0.901 / 0.050 / 0.049 | 0.921 / 0.044 / 0.035 | 0.934 / 0.037 / 0.029 | 1.57, 6 | 0.958 |
| TP20 | 0.803 / 0.100 / 0.097 | 0.822 / 0.113 / 0.065 | 0.838 / 0.109 / 0.054 | 2.69, 10 | 0.957 |

**Read before any outcome:**
- A blowout team (spread ≤ −6) exists on 70 of 72 slate-banks.
- The RB-led blowout cell fills about 2/3 of its target, and its shortfall passes to the core. So TP realizes about
  89% core / 7% mid / 4% blow in dealt entries.
- The mid cell fills fully.
- TP changes about 96% of dealt entries, so it is not a dead lever.
