# Preregistration: study 112, usage floors — minimum carries, pass attempts, targets, touchdowns and red-zone targets per game — on his armed Week-5 book, in the harness (DRAFT 2026-10-10)

**Status: DRAFT 2026-10-10** (the times are this file's commits) by the outside reviewer; the design is the lab reviewer's
(decisions of 10-10, about 05:46). The lab reviewer reviews, runs the binding census, freezes, runs and reads; the laptop acks and
reproduces. **A pick goes to study 113** (the fresh-draw check), whose preregistration is committed before this study's READ.
- **Banks and seed (the laptop's reservation, full-set clean):** **3604–3615** (set A 3604–3609, set B 3610–3615; sims bases
  3654–3665, fields 4304–4315); the reader's bootstrap seed **20261155**.

## 1. Why
- **The operator, 10-10 morning, in the laptop's session (verbatim; study list row 92):** "Have we tried anything like “minimum
  rush attempts per game” for a RB and “minimum pass attempts for QB” and “min targets for WR”?" then "And min touchdowns and min
  red zone targets".
- **Never tested as a construction rule** (both ledgers grepped 10-10). Our projection model already uses carries, targets, their
  shares and red-zone usage as inputs. Touchdowns were tested only as lineup ordering (study 52, not supported).
- **The prior: NO DIFFERENCE, leaning negative.** Winners often carry a cheap low-volume player who boomed (Addenda 4 / 5; the
  10-07 brainstorm's within-user cheap odds ratio 1.88, after the fact). A usage floor removes some of them; this study measures
  that trade. The nearest test, study 106's projection floor, is running.

## 2. Arms (`experiments/s112_usage_floors.py`)
**Study 106's harness exactly** (its frozen module `s106_min_proj.py` `45a8d3dd…`, sha-asserted, which pins study 95's and 97's;
`run()` = 106's `run()` with six listed edits, a test asserts it). **Every arm is his armed Week-5 book:**
- the package;
- at most one TE and at most one player under 3%;
- ONECATCH;
- the adopted FAVHI, its pairs computed on each arm's pool.

**One change per arm: a usage floor applied as a pool filter** before the ownership caps, the row-rule sets, the cheap block's
term and the FAVHI pairs (106's `arm_pool` pattern = production's `excl`). DSTs are exempt. **A player with no value (no prior
game, or no feature row) is kept** and counted.
- **RUSH** — RBs with fewer than **X_RUSH carries per game** leave (production's point-in-time feature `carries_l4`).
- **PASS** — QBs with fewer than **X_PASS pass attempts per game** leave (nflverse weekly `attempts`, the mean over his last up to
  4 regular-season games **of the same season** strictly before the slate's week; study 48's source, production's window).
- **TGT** — WRs and TEs with fewer than **X_TGT targets per game** leave (`targets_l4`).
- **TD** — RBs, WRs and TEs with fewer than **X_TD touchdowns per game** leave (nflverse weekly rushing + receiving TDs, the
  same within-season last-4 per-game mean). **DROPPED before the freeze by §3's rule** (no threshold in range; §3).
- **All five measures use production's within-season window:** up to 4 prior games of the same season. The SQL is
  `sql/features/014_player_week_usage.sql`, window `w4 = PARTITION BY gsis_id, season ORDER BY week ROWS BETWEEN 4 PRECEDING AND
  1 PRECEDING`. Early-season slates have fewer or no values, and Week 1 has none; a player with no value is kept.
  - **One small difference, disclosed:** production's window counts the last 4 player-week rows, with inactive weeks inside it
    skipped in the average. The weekly-stats window counts the last 4 games played.
  - **Correction before any run:** the first draft computed attempts and TDs across seasons (the lab reviewer's first call); that
    was fixed after the lab reviewer's static review found production's window is within-season.
- **RZ** — RBs, WRs and TEs with fewer than **X_RZ red-zone targets per game** leave (`rz20_targets_l4`). **DROPPED before the
  freeze by §3's rule** (no threshold in range; §3).
- **Not used:** `xfp_l4` (Addendum 121's voided leak) and every `y_*` column (outcomes).

## 3. THE THRESHOLD RULE (fixed now, BEFORE any census is run; the lab reviewer's)
- **Starting points (placeholders):**
  - RUSH 8 carries;
  - PASS 30 attempts;
  - TGT 4 targets;
  - TD 0.25 TDs (no TD in his last 4 games);
  - RZ 0.5 red-zone targets.
- **The rule, per arm:** take the round value nearest its placeholder, in its step, such that **LIVE's book rows touched average
  between 8 and 15 of 26** per slate-bank on bank 1406. A row is touched when it holds a player the floor removes.
  - The steps: carries 1, attempts 2, targets 0.5, TDs 0.05, red-zone targets 0.1.
  - Ties in distance go to the lower value.
- **AND, at that threshold, the arm's own build passes all of these:**
  - the cheap block is never empty (no slate with 0 players given the term; production refuses that book);
  - ONECATCH drops ≤ 5% of B / C book solves;
  - the RB-mate slots are complete (4 per book).
- **If no threshold meets all of these, the arm is dropped** (recorded).
- **The procedure:**
  - The census's THRESHOLD SCAN reads only LIVE's book composition: each LIVE book row's lowest value per measure. That is
    outcome-blind, and it prints the rule's choice per arm.
  - Where a choice differs from the run's threshold, the threshold is set to the choice and the smoke re-run. The arm's own checks
    are then read at that value.
  - The lab reviewer checks the census lines and the chosen numbers before the freeze; this file records them.
- **THE CHOICES (the lab reviewer's scan census, 10-10: bank 1406, the 36 slates, LIVE == study 97's RBMATE4_FAVHI on 36 of 36;
  `CENSUS_s112_binding.txt` `5cd978bf…` at the placeholders):** LIVE's book rows touched, mean per slate-bank:
  - **RUSH → 13 carries** (12: 7.4; **13: 10.6**; 14: 14.8; the placeholder 8: 1.5);
  - **PASS → 32 attempts** (30: 7.2; **32: 10.5**; 34: 14.3);
  - **TGT → 4.5 targets** (4.0: 7.8; **4.5: 11.4**; 5.0: 15.1);
  - **TD: none in range → DROPPED.** Every value from 0.05 to 0.25 touches 21.5 rows, and 0.3 and up 24.4. A player with no
    touchdown in his window has a per-game mean of 0, so any floor removes all of them at once; there is no dose between "none"
    and "most of the book". His "min touchdowns" cannot be tested as a floor this way.
  - **RZ: none in range → DROPPED.** 0.1 and 0.2 touch 15.7 (just above 15), 0.3 and up 21.3.
  - **Recorded at the placeholders (moot for the dropped arms):** TD and RZ fell back on 19 and 22 of 936 row-rule solves,
    ONECATCH dropped 6 and 9.
  - **To watch at PASS 32 (the re-smoke and the binding census):** at the placeholder some slates had no FAVHI pair left (min
    0); the RB mate's floor was re-solved without it in 5 of 144 slots, as production turns the RB mate off when no pair exists.
    Disclosed here; the binding census reports it at 32.
  - The arms' own checks at the chosen values (the cheap block never empty, ONECATCH ≤ 5% dropped, the RB-mate slots) are read
    in the re-smoke and the binding census before the freeze.

## 4. The read (the reader `scripts/s112_report.py`)
- **Study 100's reader with study 106's edits, relabelled** (a test asserts them); study 63's statistics; two draws and pooled;
  two-sided 0.95, B 20,000.
- **Per arm − LIVE:**
  - P(≥ 1 big seat), its guards and verdict;
  - **his rule's line** (better on both draws AND the pooled expected big seats ratio ≥ 0.80);
  - the mean best real lineup points and P(best ≥ 200), printed.
- **THE PICK (pre-stated; study 106's tested function `floor_pick`):** among the arms passing his rule (guard 1 printed, not
  gating), the largest pooled gain. None → "keep the live book". **A pick goes to study 113.**
- **Multiplicity:** three arms (TD and RZ dropped before the freeze) on the same 36 slates as studies 89–111; about one passes
  by chance.

## 5. Honest limits and production
- **The within-season window:** in 2023–24, early-season slates rest on fewer games, and Week 1 on none (those players kept). In
  Week 5 of 2026, production's window is the same (Weeks 1–4).
- **The harness builds on its own simulated means;** his book uses Fantasy Points' projections. A floor removes the same players
  in both (the usage data is shared), but which lineups result differs.
- **Production has no such flag.** A pass needs:
  - a pool filter on these columns joined to the T-70 frame (the `--min-proj` pattern: `excl` into the pool, caps, rule sets and
    the term block);
  - tests, the Week-4 gate and study 38's classification.
  - It is **information for Week 6** unless it passes clearly and that is built in time.
- **The census:**
  - per arm: the pool, the players dropped by position, the cheap players left and given the term, the TE / low-owned pools,
    LIVE's rows touched, the FAVHI pairs and the spares built;
  - the coverage (frame rows with a value);
  - the threshold scan;
  - the RB-mate slots; ONECATCH; LIVE == study 97's RBMATE4_FAVHI (`--ref97`).
  - Per-slate fields stay outside the blocks the reader compares.

## 6. Smoke and code
- BLAS threads pinned; PYTHONHASHSEED=0; bank 1406 only for the smoke and the census (the unit tests, the mechanics smoke 2023 W3
  / 2023 W11 / 2024 W10, the census with its threshold scan, the full path: reader exit and line count only).
- **The smoke at the placeholders (DONE 10-10, 07:18:17–07:20:44 CDT, in the gap the lab reviewer named after the laptop's
  study-110 census; bank 1406; 2024 W10, 2023 W11, 2023 W3; PYTHONHASHSEED=0; code `24a88fb1`; `results_bank1406.jsonl`
  `75e73545…`):**
  - the unit tests 12 passed;
  - every arm 26 book rows within the package's caps; row rules 78 of 78 ruled, none infeasible; RB-mate slots 12 of 12 and
    ONECATCH 42 of 42, none dropped, every arm; spares 15 of 15; **LIVE identical to study 97's RBMATE4_FAVHI on 3 of 3**;
    coverage 316.7–321.7 frame rows with a value per slate-bank;
  - LIVE's rows touched at the placeholders: RUSH 5.7, PASS 6.0, TGT 8.0, TD 22.7, RZ 24.0 of 26;
  - **the threshold scan on these 3 slates (a preview; the binding census on the 36 slates decides):** RUSH → 12 carries (9.3
    rows), PASS → 32 attempts (10.0), TGT stays 4.0 (8.0); **TD and RZ find no threshold in range** → dropped under §3. Every TD
    floor from 0.05 to 0.25 touches 22.7 rows: a player with no TD in his window has a mean of 0, so any floor removes all of
    them at once. RZ at 0.1 already touches 17.3;
  - the full path: the reader exited 0 (80 lines; 106 two-draw). Only the census, the exit codes and the line counts were
    read.
- **The chosen thresholds:** RUSH 13, PASS 32, TGT 4.5; TD and RZ dropped (§3). **The re-smoke at them:** (filled in when done;
  a gap the lab reviewer names after the study-110 run).
- **Code:** nfl2 `production/s112-usage-floors-20261010` @ `e111a611` (off study 106's frozen `afdfad8c`; the placeholders were
  `24a88fb1`; the chosen thresholds and the two dropped arms at `e111a611`):
  - `experiments/s112_usage_floors.py` `16bbe046…` (pins s106 `45a8d3dd…`)
  - `scripts/s112_drive.py` `c06f7644…`
  - `scripts/s112_census.py` `41a7c150…`
  - **`scripts/s112_report.py` (the reader) `8c8991a9…`** (seed 20261155)
  - `tests/test_s112_usage_floors.py` `45e5f3bd…` (12)
