# Preregistration: study 33, an injury-status calibration of our means (O-14 part 2) (DRAFT 2026-10-06)

**Transfer, said first:** with Fantasy Points' projections live for every player (316 of 316 in the Week-5
rehearsal), a PASS changes NOTHING in the Week-5 or Week-6 build. It matters only for players FP does not project (the
fp-gap-flag cases) and for a return to our means if the weekly ours / FP / blend check ever favours ours. It is LOW
priority for compute: frozen to meet Wednesday's deadline, run when the host is free after study 32 and anything with
live effect.

**Status: DRAFT 2026-10-06, revised the same day after the reviewer's review.** The laptop drafted it at the reviewer's request; the register's deadline is "preregister
by Wed 10-07". The reviewer reviews it, builds the harness and freezes it after the support census and the smokes. The
laptop acks the census and re-runs the frozen reader.

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
  - (a) An EARLY-window player with a Q / D designation who did NOT play is removed from the pool before the build.
    This is legitimate T-70 information: the inactives are public at 10:30 CT, before the 10:50 CT build. "Did not
    play" is read from the inactive / active record, the same fact the live pull reflects.
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
- the pool's LATE-window Q / D players by stratum, and the early-window flagged players the emulation resolves (their
  count only; whether they played is T-70 information, not a scored outcome);
- the book rows holding at least one LATE-window Q / D player, in each reference book;
- the distinct late-window flagged players dealt, and their dealt-entry share;
- the stratum table (n, c_s, SE, c_s') and how far the calibration moves each late-window flagged player's mean;
- whether AV_x's book differs from x's (identical-book share).

**Vacuity rule:** if AV_x's book is identical to x's on more than 80% of slate-banks, the verdict is DEAD LEVER, read
before any outcome. The census may well come out vacuous (few late games, few flagged players, rarely in a book); that
is an honest, cheap answer to O-14 part 2 and is recorded as such. If support is absent, the design is revised before
the freeze, not after.

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

## 9. Integrity (to be filled at the freeze)
Code (nfl2 branch and module shas), reader sha, census sha; the production `enter_layout` pin. Order:
1. this draft;
2. the reviewer's review;
3. the support census;
4. the smokes;
5. the freeze;
6. the binding census;
7. the laptop's ack;
8. the scored run;
9. the confirmatory census;
10. the read;
11. the laptop's re-run;
12. the LEDGER row and an Addendum.
