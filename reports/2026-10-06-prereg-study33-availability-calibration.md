# Preregistration: study 33, an injury-status calibration of our means (O-14 part 2) (FROZEN 2026-10-06)

**Transfer, said first:** with Fantasy Points' projections live for every player (316 of 316 in the Week-5
rehearsal), a PASS changes NOTHING in the Week-5 or Week-6 build. It matters only for players FP does not project (the
fp-gap-flag cases) and for a return to our means if the weekly ours / FP / blend check ever favours ours. It is LOW
priority for compute: frozen to meet Wednesday's deadline, run when the host is free after study 32 and anything with
live effect.

**Status: FROZEN 2026-10-06** by the reviewer, after the laptop's draft and revisions, the support census and the smoke (§5a, §9), before any scored bank. The support census ran on the frozen code and is the binding census. The laptop acks it and re-runs the frozen reader.

## 1. Why
- **O-14 part 2 (open since 2026-09-19):** the selector carries no availability weighting. Week 2's Zay Flowers (DK
  Doubtful at build) sat in 45 of 97 lineups. Study 1b closed part 1 (an entry cap) in Addendum 123. Part 2, a
  Doubtful / Questionable discount, was never tested.
- **The motivating case was an EARLY-window game.** Zay Flowers' Week-2 game (NO at BAL, Sunday 13:00 ET) was in the
  early window. Today's money path rebuilds at T-70 on the salary pull made after the 10:30 CT inactives, so a
  Doubtful early-window player is resolved (OUT and removed, or active) before the build. Today's rules would already
  have handled him.
- **The uncertainty left at selection time is LATE-window only.**
  - The T-70 build runs at 10:50 CT, after the 10:30 CT inactives for the 12:00 CT (13:00 ET) games.
  - Late-window games (16:05 / 16:25 ET) post their inactives at about 13:35–13:55 CT, after the build.
  - Only their Questionable / Doubtful players are uncertain when the book is chosen. `ENTER_FLAG_LATE_Q_ONLY` exists
    for exactly this.
- **The operator's money-path rule is untouched.** This study changes how the book is BUILT (the means a lineup is
  chosen on). It never removes a player from entered lineups; only OUT / IR or the official inactives do that.

## 2. What we already know (outcome-blind, measured 2026-10-06 before this draft)
- **Both projection sources already discount Questionable players.**
  - Week 4's T-70 frame against FP's pre-lock capture; projections only, no scores. Each source is measured against
    the player's own recent average (dk_ppg), for non-DST players with dk_ppg > 3.
  - Healthy (n 168): FP 1.009, ours 0.932 (medians).
  - Questionable (n 7: 6 Limited, 1 Full): FP 0.792, ours 0.696.
  - So both sit about 21–25% below their healthy level.
  - FP also projects 0 for players it expects to sit.
  - n 7 is thin. Per-player FP values are licensed and stay private.
- **So the question is not "discount or not".** It is: does an EXTRA, status-specific calibration, beyond what the
  means already price, improve his goal?
- **Our means do not take status as an input.**
  - The production model's NUMERIC_FEATURES carry no injury_status or practice_level, only role features (depth_rank,
    snap_share_l4).
  - The lab's participation law (`nfl2/participation.py`) is imported by experiment 073 and the mechanics gates only,
    not by `pipeline.simulate_slate`.
  - The W4 gap therefore comes from role features or chance, not from a status term. The calibration below measures
    the net effect whatever its cause.
- **The status data are pre-lock in history.**
  - `sql/features/018_player_week_injury.sql` keeps the latest report with `date_modified <= slate_lock_at` (line 48),
    and the leakage suite covers these columns.
  - `nfl_raw.injuries` carries date_modified for 2022–24: 2022 Q 1,511 / D 156; 2023 Q 1,583 / D 142; 2024 Q 1,513 /
    D 194 rows.
  - 2025 and 2026 have no date_modified, and live uses the pulled-at snapshots. The panel needs 2022–24 only.

## 3. The T-70 emulation and the calibration (class C; the reviewer's design)
- **The window** comes from the schedules' `gametime` (ET; nflverse `nfl_raw.schedules`, present for 2022–24): EARLY =
  13:00 ET, LATE = 16:05 / 16:25 ET (the main slate; 09:30 London and night games are outside it).
- **The T-70 emulation, applied to EVERY arm alike**, so the reference is today's live behaviour:
  - (a) EVERY early-window player who did NOT play is removed from the pool before the build: the flagged ones and
    healthy surprise scratches alike, since the 10:30 CT inactives list everyone and the live T-70 pull drops them
    all. This is legitimate T-70 information, public before the 10:50 CT build.
    - "Did not play" means NOT ACTIVE on game day: the frame's `was_active`, which is the inactives list itself, the
      exact information the 10:30 CT pull carries. A player who is active and takes no snap stays in the pool, as
      live. This replaces the draft's "offensive snaps > 0" (the reviewer's earlier suggestion): snaps would
      remove active players live never removes. Changed at the freeze, before any outcome; the column is read only
      for step (a) and for the realized "sat" count (tested).
    - DSTs always play.
  - (b) An EARLY-window Q / D player who played keeps his mean, undiscounted.
  - (c) The calibration applies to LATE-window Q / D players ONLY.
- **Strata, LATE-window player-weeks** (pre-lock status from the training table's injury_status and practice_level):
  - Q with DNP;
  - Q with Limited;
  - Q with Full or none;
  - D;
  - HEALTHY (no designation).
  - OUT / IR are outside the pool, as today.
  - If the late-window strata are too thin to estimate (see the shrinkage), the factors use ALL-window player-weeks
    instead, disclosed in the census before the freeze.
- **The raw factor:** c_s = Σ realized DK points / Σ our projected mean, over the training seasons' player-weeks in
  stratum s. Realized points include the zeros of players who did not play.
- **Shrinkage, not a hard floor:**
  - c_s' = (n · c_s + k · c_parent) / (n + k), with k = 100.
  - The parent chain is: the Q sub-strata shrink to Q, Q to Q+D, D to Q+D, and Q+D to HEALTHY.
  - DK points have a CV of about 1–1.5 with zeros, so a ratio on n = 30 carries an SE of about 0.2–0.27. The census
    prints n, c_s, its SE and c_s' per stratum.
- **The arm** multiplies a LATE-window flagged player's mean by **min(1, c_s' / c_healthy)**. Dividing by healthy keeps
  a general over- or under-projection out of the status effect. The cap at 1 never inflates a flagged player.
- **Walk-forward:**
  - 2023 slates use factors from 2022; 2024 slates use 2022–23. Never the test season.
  - The training means are the harness's own player_mean, so the factor calibrates exactly what the selector uses.
    They come from simulating the 2022 slates and the 2023 slates once each, with a fixed training seed (bank 1406's),
    never the scored banks.
- **The mean only.** The simulated variance is unchanged. Disclosed: a player who plays at reduced snaps is not
  modelled beyond his mean.

## 4. Arms (study 31's harness, with the T-70 emulation in every arm)
- **Plan:** Rev3 (`3dd19d6c…`), K 26, caps 13 / 6, head, `enter_layout` pinned `3cb051ac…`.
- **Books, both with the 0.20 ownership term** (study 31's recommendation):
  - **CT** (the house shape + term) and **AV_CT** (the same, on calibrated late-window means);
  - **MIXT** (the winners' mix + term) and **AV_MIXT** (the same).
- The term's ownership input is unchanged; the calibration touches the projected mean only.
- **Scoring:** a late-window flagged player who sat scores 0 in the book. There is no replacement after T-70 for late
  games in the panel: live, late swaps are possible but not modelled. Disclosed.

## 5. Support census FIRST (outcome-blind; before the freeze)
For every slate on the mechanics bank:
- the pool's LATE-window Q / D players by stratum;
- per slate, how many early-window players step (a) removes and how many of them were flagged (counts only; whether
  they played is T-70 information, not a scored outcome), plus the crosswalk's misses;
- the book rows holding at least one LATE-window Q / D player, in each reference book;
- the distinct late-window flagged players dealt, and their dealt-entry share;
- the stratum table (n, c_s, SE, c_s') and how far the calibration moves each late-window flagged player's mean;
- whether AV_x's book differs from x's (identical-book share).

**Vacuity rule:** if AV_x's book is identical to x's on more than 80% of slate-banks, the verdict is DEAD LEVER, read
before any outcome. The census may well come out vacuous (few late games, few flagged players, rarely in a book); that
is an honest, cheap answer to O-14 part 2 and is recorded as such. If support is absent, the design is revised before
the freeze, not after.

## 5a. The training factors and the support census (outcome-blind for the test seasons; 2026-10-06)
- **The training factors** (`results/s33/factors.json`, sha `4e4607ef…`): 36 training slates (2022 and 2023),
  simulated once at the fixed training seed (bank 1406's), 11,091 player-weeks.
  - The LATE window is used for both test seasons: Q+D n 108 (2022 → 2023) and 213 (2022–23 → 2024), both ≥ 100.
  - Late-window raw c (realized / our mean):
    - healthy .844 / .906;
    - Questionable .710 / .691;
    - Doubtful .000 (n 7) / .000 (n 19).
  - Arm factors, min(1, c' / c_H):
    - Q_DNP .845 / .725, Q_LP .844 / .755, Q_FP .909 / .848;
    - D .838 / .667.
  - Disclosed: the shrinkage (k 100) leaves Doubtful players about 67–84% of their mean, although none scored in
    training. That is generous; live, a Doubtful player is only demoted in the vetting order (weight 3), never
    excluded. Late-window Doubtful players are about 1 per slate.
- **The support census** (1406, 36/36, code `87e408d`; the binding census):
  - T-70 step (a) removes 26.6 early-window players per slate (4.3 of them flagged).
  - 5.8 late-window flagged players per slate (Q_LP 2.9, D 1.1, Q_DNP 0.9, Q_FP 0.9).
  - The calibration moves their means by 1.7 DK points on average (max 5.3).
  - The reference books hold one on 44% (CT) / 42% (MIXT) of slate-banks, in 5.8 / 3.8 of 53 dealt entries.
  - AV removes nearly all (0.2 / 0.3 entries).
  - AV is dealt identically to its reference on 0.39 (CT) / 0.47 (MIXT) of slate-banks, so the study is NOT vacuous.
  - CT0 / MIXT0 are identical to CT / MIXT on 0.75 / 0.78.
- **Pre-stated for the read** (the laptop's ack, before any outcome):
  - **What the study tests, in plain words.** The calibration is small per player (1.7 points), but the selector drops
    a flagged player once he is slightly worse than his replacement. So AV's books hold almost no late-window flagged
    player:
    - CT: 3.00 book rows → 0.14; MIXT: 1.89 → 0.11;
    - dealt entries 5.8 → 0.2 and 3.8 → 0.3 of 53.
  - In effect the study tests "keep late-window Q / D players out of the book" against today. The read says so, and
    that is also the simplest live rule if it PASSes.
  - **A descriptive post-read line, never decision-bearing:** per arm, the dealt entries holding a late-window Doubtful
    player and those holding a late-window Questionable player, with the share of each who sat. The strata are
    recomputed from the frames (outcome-free). Doubtful is under-discounted by the shrinkage (above), so a D-driven
    effect, or its absence, must be visible on its own.
- **The smoke** (2023 W1, 1406, the full path): the census and reader exited 0; the reader printed its 2 headers and
  REFUSED mechanics-only rows (exit 1). No outcome line was read.
- **A process note:** the first training run stalled for 70 minutes; its script lacked the drivers' `OMP_THREAD_LIMIT=1`,
  so the threads oversubscribed across workers. It was stopped and re-run with the limit, with identical inputs and seed.

## 6. Panel, endpoint and rule
- **Slates:** the 36 `k1` slates of 2023–24.
- **Banks:** fresh 1443–1448, scanned by both parties before use. The census runs on 1406.
- **PRIMARY:** P(≥ 1 big seat) per slate, **AV − reference pooled over the two shapes** (the mean of AV_CT − CT and
  AV_MIXT − MIXT). Bootstrap within season, B 20,000; two-sided 0.95.
- **Guards (study 18b's):**
  - guard 1, mean entry percentile, one-sided lower > −0.015;
  - guard 2, expected big seats ratio ≥ 0.80.
- **Verdicts:**
  - PASS: lower > 0, at most one negative season, guards hold;
  - WORSE: upper < 0;
  - DEAD LEVER: the vacuity rule;
  - NO DIFFERENCE: otherwise.
- **EXPLORATORY:** each shape's contrast; the entries holding a late-window Q / D player per arm; the share of those
  players who sat (realized), arm by arm; the T-70 emulation's effect on the reference itself (the books with and
  without step (a)), as a description of what today's T-70 rule already buys.

## 7. What a verdict can do (to be frozen)
- **PASS supports calibrating OUR means**, not FP's.
  - From Week 5 the live build selects on FP's projections, and FP's own status discount is unmeasurable in history
    (no FP before 2026 W4). A panel-estimated factor is NEVER applied to FP.
  - The FP-path factor accumulates from the weekly records (W4 on: FP's projection vs realized, by pre-lock status).
    Once its strata hold enough players it becomes a monitored class-C candidate, offered to the operator with its
    own evidence.
- **NO DIFFERENCE or WORSE:** no change; the register entry closes with this result.
- **DEAD LEVER:** recorded; no change.
- **In every case:** players leave entered lineups only when DraftKings marks them OUT / IR or the official inactives
  name them.

## 8. Disclosures (before any outcome)
1. FP already discounts flagged players (§2), so the live transfer of a PASS is to OUR means only, and with FP live for every player it changes nothing in the Week-5 / 6 build (the header).
2. The T-70 emulation reads who sat in EARLY-window games as T-70 information (public at 10:30 CT); late-window swaps after T-70 are not modelled.
3. The mean only; snap-share reductions and the variance are not modelled.
4. Stratum sizes are thin for D and Q-DNP, and thinner in the late window; the shrinkage (k 100) and the all-window fallback (§3) are fixed now.
5. The panel's projections are ours (no FP in history); the term's predictor is the TABPFN_LS stand-in, as in 29–31.

## 9. Integrity
- **Code:** nfl2 `production/s33-availability-20261006` @ `36e7431` (harness `87e408d` + the binding census):
  - `experiments/s33_availability.py`, sha256 `08cabbca747d8eccc6d9ab3da7d80e79434ada1c077e394a0ebd7c6d102b351c`;
  - `scripts/s33_train.py`, `56fb040339f62707d11f651ecf37af8c53bed701efb7de97e074582753b10d3d`;
  - `scripts/s33_drive.py`, `c2dd0185ea34b20ae956246f9181a305a1a28f0d20272b29620d2c9acd155f5c`;
  - **`scripts/s33_report.py` (the reader), sha256 `9654d1b3abe320489e15cad5dd82a661eb4a37076b8abf0bd0a0b8cb72696c42`**;
  - `scripts/s33_census.py`, `7b605d5dcff75dedf809335ad8a777cd710b88b1c3405fec1ca842be9686bd57`;
  - `tests/test_s33_availability.py`, `2c06a3835f5698a26304acb59f9b171a2e172562a0513cef7ed562dce7d9e560` (6 tests).
- **Factors:** `results/s33/factors.json`, `4e4607effa5c8f160d280c233358d3609a8d822a01ef0ddb834fc164835a1c3e` (training
  rows `5f30e947…`).
- **Binding census:** `results/s33/CENSUS_s33_binding.txt`,
  `16e136ee4fe61106e245176160e7c0d426a42fd26c786a7f8cff82b5cb11434d` (raw `9d3c527b…`).
- **Production `enter_layout.py`:** `3cb051ac…` (`da399bdb`). Runs use `PYTHONPATH=<nfl2 worktree>/src:<da399bdb
  worktree>/src`.
- **Reader seed:** 20261015. **Banks:** 1443–1448 (scanned clean by the laptop with the wider pattern).
- **Order:**
  1. this freeze;
  2. the laptop's ack of the binding census;
  3. the scored run (LOW priority; launched 10-06 when the host was free, after the laptop's ack);
  4. the confirmatory census;
  5. the read;
  6. the laptop's re-run;
  7. the LEDGER row and an Addendum.
