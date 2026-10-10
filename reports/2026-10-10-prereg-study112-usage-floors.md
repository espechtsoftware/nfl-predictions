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
- **PASS** — QBs with fewer than **X_PASS pass attempts per game** leave (nflverse weekly `attempts`, the mean over his last 4
  regular-season games strictly before the slate's week, across seasons; study 48's source and window, as a per-game mean).
- **TGT** — WRs and TEs with fewer than **X_TGT targets per game** leave (`targets_l4`).
- **TD** — RBs, WRs and TEs with fewer than **X_TD touchdowns per game** leave (nflverse weekly rushing + receiving TDs, the
  last-4 per-game mean, across seasons).
- **RZ** — RBs, WRs and TEs with fewer than **X_RZ red-zone targets per game** leave (`rz20_targets_l4`).
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

## 4. The read (the reader `scripts/s112_report.py`)
- **Study 100's reader with study 106's edits, relabelled** (a test asserts them); study 63's statistics; two draws and pooled;
  two-sided 0.95, B 20,000.
- **Per arm − LIVE:**
  - P(≥ 1 big seat), its guards and verdict;
  - **his rule's line** (better on both draws AND the pooled expected big seats ratio ≥ 0.80);
  - the mean best real lineup points and P(best ≥ 200), printed.
- **THE PICK (pre-stated; study 106's tested function `floor_pick`):** among the arms passing his rule (guard 1 printed, not
  gating), the largest pooled gain. None → "keep the live book". **A pick goes to study 113.**
- **Multiplicity:** five arms on the same 36 slates as studies 89–111; about one to two pass by chance.

## 5. Honest limits and production
- **Last-4 games across seasons (the lab reviewer's call):** in 2023–24 early weeks the windows include the previous season. In
  Week 5 of 2026, production's last-4 are this season's Weeks 1–4, so the windows match there.
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
- **The smoke and the chosen thresholds:** (filled in when done).
- **Code:** nfl2 `production/s112-usage-floors-20261010` @ `7451b5dd` (off study 106's frozen `afdfad8c`):
  - `experiments/s112_usage_floors.py` `fb6ee63c…` (pins s106 `45a8d3dd…`)
  - `scripts/s112_drive.py` `c06f7644…`
  - `scripts/s112_census.py` `59d9a542…`
  - **`scripts/s112_report.py` (the reader) `0e54f0d1…`** (seed 20261155)
  - `tests/test_s112_usage_floors.py` `d4bac8f6…` (12)
  - The module's thresholds change if the rule's choices differ; the code line is then updated before the freeze.
