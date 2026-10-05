# Preregistration: study 17, lineup selection that reduces redundancy while keeping high scores (FROZEN 2026-10-05)

Frozen before the calibration, the census and any scored bank. Later changes are dated deviation notes at the end. The
reviewer froze it and reads it first; the laptop reviewed the design before the freeze and re-runs the frozen reader
before the LEDGER row.

**The operator (10-05, verbatim):** "This is the most important thing that needs to be fixed this week.  I think you need
to do some deep analysis of winning lineups and our current process and figure out how to reduce redundancy while
maintaining high scores.  I believe I have asked for changes to the way we choose lineups so they aren't randomly throwing
players in that seem to help - and to have some kind of strategy so that actual high potential lineups are selected first
so that others with similar players don't take up the slot earlier". Then: "yes please go ahead". And: "If there is
disagreement, perhaps we can try both approaches".

## What the analysis found (descriptive, outcomes already seen; motivates, is not evidence)
- **Week 4's redundancy was made at selection.** The entered book (the T-70 union: PMO_X50 plain-mean sequential MILP + the
  FP ownership term at 0.20, ≤ 7 shared, a player banned at 52 of 105 rows) shared 3.28 players per row pair, against 1.26
  for 110 random rows of the same 19,123-row pool. Its most-used players were 2–4× their pool share (laptop,
  `where_redundancy.py`). The head layout then deals the top rows into every contest: the JAX QB was in 92 of 154 entries.
- **The pool held the high scorers and the book took none.** The Week-4 pool had 122 rows in the field's top 1% (pool best
  211.8); the book's best was 162.4. Week 3: 49 pool rows in the top 1%, none in the book.
- **The field's winners are also concentrated, on the right players.** Among the top 200 Millionaire lineups each week
  (2026 W1–4), the most common player is in 85–94% and two lineups share 3.1–3.6 players (random field lineups: about 1).
  The aim is therefore several cores with a few lineups each, not maximal spread, and not one core in 60% of entries.
- **Pre-lock signals find the eventual top lineups only weakly:** the pool's 50 best realized lineups sat at the 65th–89th
  percentile of the pre-lock mean in W1/W3/W4 and the 26th in W2. Which core hits cannot be called ahead of time, which
  is the argument for spreading the book across cores.
- **A replay on each 2026 week's own pool** (pre-lock information only, 110 rows): expected-max and coverage selection
  halve the redundancy (1.1–1.6 shared players) without losing mean points over the four weeks; no rule wins every week.
- **History (lab LEDGER, system study):** DUAL_EMAX passed PREREG-036 (+1.392 at K80, best-of metric) and ran W1–W3; the
  Week-3 post-mortem and L09/L10/L13 favoured the plain mean at the satellite lines (p89), and PMO_X50 was adopted for
  Week 4 (HANDOFF 2026-09-28). Tighter hard exposure caps were HARMFUL or NEUTRAL (L17, L18), and study 1b's entry-level
  cap FAILED on cost. No soft, diminishing-returns form has been tested.

## Arms (one co-run per slate-bank)
Common to all: K = 105; the objective is each player's simulated mean over the dual-law selection worlds (10,000 law +
10,000 hsim draws, the study-16 harness); **no ownership term in any arm** (so 2022, which has no LAG file, can be used, and
the term is identical across arms); house rules QB + 2 with 1 bring-back, MAX_PER_GAME 4, $49k floor; skill players with
simulated mean < 1.0 dropped.

- **C (control):** the current main book's form without the term: 105 sequential MILP solves maximizing the mean, ≤ 7
  shared with every earlier row, a player banned at 52 rows, a DST at 26.
- **DR, diminishing returns (DECISION):** C, except that before each solve every player's objective (DST included) is his
  mean minus λ × (rows already holding him). Row 1 is C's row 1 (the highest-mean lineup); every later solve values a heavily used
  player less, so a near-copy of an earlier lineup wins a slot only if it is clearly better than an alternative built on
  other players. This is the operator's request as a selection rule over the same optimizer. **λ is fixed before any
  scored bank** by an outcome-blind calibration: on throwaway bank 1406, mechanics only, across the 53 panel slates, the
  smallest λ in {0, 0.01, 0.02, 0.03, 0.05, 0.075, 0.1, 0.15, 0.2, 0.3, 0.5, 0.75, 1.0} whose mean (over slate-banks)
  share of DEALT ENTRIES held by the top non-DST player (after `deal()`, so the head layout's repetition of the top rows
  is counted) is ≤ 0.45.
  λ applies to every player, DST included; the target measures non-DST players only. The calibration record prints row
  and entry shares. If no grid value meets the target, the largest is used and disclosed. Recorded in deviation note 1.
- **DR35 (EXPLORATORY):** the same with the entry-share target 0.35, about random's level. Never decision-bearing.
- **Why 0.45 (amendment before the freeze, both parties):** a one-slate calibrate-path smoke (2024 W6, bank 1406,
  mechanics only) showed the head layout adds 12–25 points of entry share on top of row share: C 0.495 rows → 0.612
  entries; 105 random pool rows 0.286 → 0.347; EM 0.229 → 0.306. A 0.35 entry target is therefore random's level and was
  out of reach of the first grids. 0.45 roughly halves C's excess over random while the best rows still go first. The
  calibration record also prints, for the chosen settings, the per-slate distribution of the dealt-entry share (min,
  median, p90, max); a p90 above 0.55 is disclosed in deviation note 1 (the rule stays the mean).
- **EM, expected-max (DECISION):** the Week 1–3 selector, `nfl2.selectors.select_expected_max` (greedy marginal
  E[max]), over L13's CAP4 boom-first pool (lev 640 + boom 2,560) scored on the same dual-law worlds. No caps.
- **PG, pool-greedy (DECISION; the laptop's arm, the operator's sentence literally):** EM's pool ranked by the same
  simulated mean as C; the highest row first, then each next row only if it shares ≤ s players with every row already
  taken; a pass that ends short of K is filled in mean order (counted in the census). s is fixed by the same calibration:
  the largest s in {6, 5, 4, 3, 2} whose mean dealt-entry share of the top non-DST player is ≤ 0.45 (if none, s = 2,
  disclosed). At matched entry concentration, DR against PG separates "construct with a penalty" from "select from the
  generated pool".
- **RND, the monkey baseline (REFERENCE; the laptop's review):** 105 rows drawn uniformly without replacement from EM's
  pool, in random rank order. Never decision-bearing; each decision arm's difference from RND is reported with intervals.

Every book is dealt into the Week-4 plan's mean-track contests (22 contests) by study 1b's `deal()`: head layout,
small-contest overlap limit M 5, ceiling 10. The rank order is the solve order (C, DR, DR35), the greedy order (EM), the
pool order (PG) or the random order (RND).

**Not an arm:** a pool-side change. The laptop's evidence and the replay agree the pool is diverse and contains the high
scorers. The operator's "try both approaches" is honoured by three decision arms that take different routes to the same
goal: a soft penalty in the optimizer (DR), marginal-value selection from the pool (EM) and best-first selection from the
pool with an overlap limit (PG).

## Panel
The 53 `k1` slates of 2022 (17), 2023 (18) and 2024 (18) that have Millionaire ownership (the field sampler needs it).
**Fresh banks 1413/1414** (unused as bank labels in both repositories' branch scans; reserved 10-05). Smokes and the
calibration on throwaway bank 1406. The realized field is the L02 sampler's 200,000 lineups at the slate's Millionaire
ownership, as in studies 1–16.

## Endpoints and decision rule (each decision arm against C)
- **PRIMARY = TICKETS:** dealt entries at or above each contest's line, summed per slate, ARM − C, paired.
  Season-clustered bootstrap (slates resampled within season), B 20,000, seed 20261005; **two-sided 0.99167 per decision
  arm** (0.975 split over the three decision arms).
- **PASS** = the lower bound > 0, **at most one of the three season means < 0**, and the GUARD holds: mean entry finish,
  one-sided 0.99167 lower bound > −0.015 (the operator's 1.5-point margin, as studies 1b, 16, 16c).
- **FAIL (guard):** tickets would pass, the guard fails. **WORSE:** the upper bound < 0. **DEAD LEVER:** dealt identically
  to C on more than 80% of slate-banks. **NO DIFFERENCE** otherwise. The guard is printed for every arm in every branch.
- **Secondaries:** zero-ticket slates; contests with at least one ticket; best ≥ 200; the worst-decile slate;
  **redundancy of the dealt entries** (the top player's entry share, shared players per entry pair, distinct QBs, the top
  QB's share) and the top player's row share (the manipulation check); each decision arm against RND (tickets and mean
  entry pct, intervals); the simulated line-crossing share (in-sample: EM is selected on the same worlds, which favours it;
  never decision-bearing).

## Power, stated before the read
Study 16's paired SE scaled to 53 slates, at the three-way split level: a tickets effect smaller than about **+35%**
reads NO DIFFERENCE. The redundancy
secondaries will move whatever the tickets do; a DR that cuts redundancy at no ticket or finish cost (NO DIFFERENCE with the
guard intact) is itself information for the operator's decision, reported as such and not as a PASS.

## Integrity
- **Reader** `scripts/s17_report.py` (nfl2 `production/s17-diminishing-returns-20261005` @ `a1a7390`), sha256
  `f5c6c493395d8cf65a247c8ea19a04463e6a4d40996b73986c577a969253b6e3`, frozen here before the calibration; it refuses
  mixed plans, overlap settings or settings (λ, s), mechanics rows and slates missing a bank. A test asserts its printed
  levels against this text. **Census** `scripts/s17_census.py` sha256 `477d4ea3…2a03`; **experiment**
  `experiments/s17_diminishing_returns.py` sha256 `c2d11929…ca17`; **driver** `scripts/s17_drive.py` sha256
  `08ac305d…d39f`. The experiment's `SETTINGS` are set only by deviation note 1, through the repair-sha pattern (the note
  records the experiment's new sha; nothing else in it may change).
- **Smokes before the freeze:** the calibrate path (2022 W5 and, after the census extension, 2024 W6) passed rc 0,
  mechanics only. The scored full-path smoke (2023 W9, placeholder settings, output discarded unread) was still running at
  the freeze; its result is recorded in deviation note 1, before any scored bank.
- **Tests** (`tests/test_s17_diminishing_returns.py`, 9): the penalty reaches every solve (row 1 on plain means; λ per
  prior use thereafter; λ 0 = C), the calibration rule, the redundancy measure over dealt entries, PG's best-first pass,
  skip and fill, the refusal before any simulation or book when the settings are unset, the census reading mechanics
  fields only, the verdicts and the printed levels.
- **Order (the laptop's conditions, 10-05):**
  1. This freeze, with the reader's sha.
  2. **The λ/s calibration on throwaway bank 1406 is the BINDING outcome-blind support census.** Mechanics only, all 53
     slates. Per slate it records, for C, every DR λ, every PG s, EM and RND: rows, short books, the top non-DST player's
     row and dealt-entry shares, the redundancy measures, entries changed vs C and dealt-identical-to-C, and PG fills.
     `scripts/s17_census.py --calibration` summarises it and applies the selection rule. **Both parties review it before
     the scored banks launch; any design change is allowed only at that review**, recorded as deviation note 1 together
     with the chosen λ (DR, DR35) and s (PG).
  3. The scored run on 1413/1414. **Nothing in the design changes after it starts**; a problem found afterwards is
     disclosed as a deviation, never fixed.
  4. A CONFIRMATORY census from the scored run's MECHANICS fields only (`scripts/s17_census.py`, which refuses the score,
     pct and sim_cross fields; its sha in a deviation note), run and committed BEFORE the reader.
  5. The reviewer's read; the laptop's byte-identical re-run; the LEDGER row and an Addendum; the transfer on the real
     2026 W1–W4 inputs (descriptive; the passing arm(s) with and without the live FP term).
- **Adoption** is the operator's decision under the in-season adoption track (class S); a PASS is a reason to offer a
  reversible Week-5 or Week-6 trial, not an adoption.
- **Transfer caveat (the post-ensemble law; the laptop's review):** every panel arm runs WITHOUT the ownership term, while
  the live book applies the FP term (tilt 0.20) upstream of selection. A panel verdict transfers to "arm + term" only
  through the transfer check, which runs the passing arm(s) both with and without the live term on the real 2026 W1–W4
  inputs (descriptive). Any trial offered is "arm + term", stated as such.

---

## Deviation note 1 (2026-10-05, after the binding calibration census, before any scored bank; reviewed by both parties)
**The calibration** (throwaway bank 1406, all 53 panel slates, mechanics only, 0 errors; nfl2
`results/s17/CALIBRATION_s17.txt`) applied the frozen rule:

| arm (setting) | top non-DST row share | dealt-ENTRY share (mean) | entry min / median / p90 / max | shared players per pair | QBs | changed vs C |
|---|---|---|---|---|---|---|
| C | 0.495 | 0.606 | 0.537 / 0.605 / 0.639 / 0.667 | 3.24 | 5.4 | – |
| **DR λ 0.2** | 0.242 | 0.434 | 0.333 / 0.435 / 0.490 / 0.605 | 1.44 | 15.2 | 0.842 |
| **DR35 λ 0.75** | 0.149 | 0.315 | 0.225 / 0.320 / 0.381 / 0.408 | 0.92 | 20.1 | 0.897 |
| **PG s 3** | 0.275 | 0.407 | 0.279 / 0.415 / 0.488 / 0.558 | 1.36 | 19.8 | 1.000 |
| EM | 0.261 | 0.333 | 0.204 / 0.320 / 0.435 / 0.714 | 1.37 | 19.6 | 1.000 |
| RND | 0.271 | 0.303 | 0.191 / 0.292 / 0.386 / 0.456 | 1.08 | 22.7 | 1.000 |

Short books 0 and dealt-identical-to-C 0 for every arm and setting. No grid end was used (PG s 2 needed fills: mean
16, max 57; not chosen). PG lands about 3 points below DR's entry share because of the grid's step: accepted as matched.

**Disclosures:** (a) C's p90 is above 0.55, the control's concentration; (b) DR's and PG's single worst slates are 0.605
and 0.558, but their p90 falls from C's 0.639 to about 0.49 (the bad-week concern); (c) EM has the widest spread (one
slate 0.714); (d) λ ≤ 0.03 changes 65–74% of entries while the top player stays at the 52-row cap: diversity enters
through the QBs first.

**Settings recorded:** `SETTINGS = {"DR": 0.2, "DR35": 0.75, "PG": 3}`. The experiment's sha256 becomes
`db23e754818b7a6488214938949ef158523687068e9b4a2f9a45c2e0d76e6585` (nfl2 `production/s17-diminishing-returns-20261005`);
nothing else in it changed. The reader (`f5c6c493…`) and census (`477d4ea3…`) are unchanged.

**The scored full-path smoke** (2023 W9, bank 1406, placeholder settings): rc 0, every arm 105 rows, PG fills 0,
`sim_cross` present for every arm, output deleted unread. It ran just before the pre-freeze amendment, under the old
`DR25` name and targets; the scored code path is otherwise identical.

**Next:** the scored run on 1413/1414; nothing in the design changes after it starts.
