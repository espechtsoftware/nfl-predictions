# Preregistration: study 18, stacking shapes and a shape portfolio at the winners' rates (FROZEN 2026-10-05)

**Status: FROZEN 2026-10-05**, after study 17's read fixed the base selector (§3) and before the binding census and any
scored bank. Later changes are dated deviation notes at the end. The reviewer froze it and reads
it first; the laptop reviewed the design and re-runs the frozen reader before the LEDGER row.

**The operator (10-05, verbatim):** "i still want to understand our stacking better… I think we should be doing more like
what the winners do. Also, have we tried dual stacks, such as QB+1 WR or TE + Bring Back but a WR and bring back from
another high potential game?" Then: "I also want to be cautious that we don't apply one strategy across the entire book of
entries. We saw that nearly all of ours had deep stacks, bring-backs, etc. I think we should be doing strategies like that
at a rate that is comparable to what winners do." And for Week 5: "Yes, let's plan on the new strategies this week and as
long as we can do some testing (not necessarily 6 seasons) in advance, I'm good with it."

## 1. What is known (descriptive; motivates, is not evidence)
- **Our shape is one rigid shape** (the laptop's weekly scorecard, 2026 W1–4 Millionaire, our entries vs the field, gaps in
  field sd): QB + 2 or more 94% vs 30% (+1.40); most players from one game 4.2 vs 3.0 (+1.30); players from the QB's game
  4.2 vs 2.8; games used 4.1 vs 5.3; bring-back 97% vs 43%; QB + 1 only 6% vs 53%; a second game with players from both
  teams 15% vs 46%. Everything else (ownership sum, salary left, cheap players, duplication) is within ±0.3 sd.
- **The winners' and the regulars' shapes** (top 1%, pooled; the 117 users with ≥ 100 entries in all four Millionaires,
  defined by volume): QB + 2+ 44% (range across weeks 26–71%) / regulars 42%; bring-back 59% (41–66%) / 46%; dual 46% /
  43%; players in the QB's game 3.2 / 3.1. The regulars beat the field every week; their edge splits into construction
  (this study) and within-salary-band player choice in the early games (not reproducible from visible habits; the
  regulars report §6).
- **The rates are outcome-measured and swing by week**, so they inspire the cell definitions; the quotas below are fixed
  now from the pooled 2026 rates, which are NOT part of the 2022–24 panel.
- **Prior from L13:** at a p89 line the plain mean beat the alternatives. Week 5's draft plan has shallow lines
  (p78.8–p90.9), so a shape portfolio could plausibly read WORSE here. The test is built to come out either way.

## 2. Arms (one co-run per slate-bank)
Common: K = 105; the objective is each player's simulated mean over the dual-law selection worlds; **no ownership term in
any arm**; ≤ 7 shared with every earlier row; a player banned at 52 rows, a DST at 26; MAX_PER_GAME 4 for every game;
$49k floor; skill players with simulated mean < 1.0 dropped; the BASE selector of §3 in every arm.

- **C (control):** the house shape on every row: QB + 2 WR/TE, ≥ 1 bring-back.
- **MIX (DECISION):** a shape portfolio, quotas by DEALT ENTRIES:
  - **A1 30%:** QB + 2+ WR/TE, ≥ 1 bring-back (the house shape);
  - **A2 14%:** QB + 2+ WR/TE, no bring-back;
  - **B 28%:** QB + exactly 1 WR/TE, ≥ 1 bring-back, ≤ 3 players from the QB's game, AND a second-game pair: ≥ 1
    non-DST player from EACH team of another game (a DST never counts);
  - **C 28%:** QB + exactly 1 WR/TE, no bring-back, ≤ 3 players from the QB's game.
  - Implied marginals: QB + 2+ 44%, bring-back about 58%, a second-game pair at least 28% plus the other cells' natural
    rate (target near 45%). The census verifies them.
  - Cells are solved largest first with the caps and the overlap rule SHARED across cells; a cell row that cannot be
    solved passes to A1 (counted). The rank order is the entry-weighted interleave: each rank goes to the cell furthest
    below its entry quota, weighted by the head layout's multiplicity for the plan.
- **WS (DECISION):** the field-normal shape on every row: QB + ≥ 1 WR/TE, bring-back optional, ≤ 3 from the QB's game,
  and a second-game pair from ANY other game. It is the "one new strategy everywhere" contrast to MIX.
- **DS (EXPLORATORY):** the operator's literal dual stack on every row: QB + exactly 1 WR/TE + ≥ 1 bring-back, ≤ 3 from
  the QB's game, and a second-game pair from one of the slate's top-4 totals other than the QB's game.
- **C_LA, MIX_LA (EXPLORATORY; the operator's "be smart with our ordering"):** C's and MIX's books dealt by a line-aware
  assignment instead of the head layout: contests in descending line each take their entries' rows by the highest
  simulated P(row ≥ that contest's line) over the run's own worlds; never a row twice in one contest; no row used more
  often across contests than the head layout's busiest row. Each is compared with ITS OWN book under the head layout.
  The simulated line uses the run's field sample, which is drawn at the slate's realized Millionaire ownership (ownership,
  not points); a production version would use the pre-lock ownership predictor. Disclosed; exploratory only.
- **Not re-run:** WS without the pair is study 15's looser QB stack (S1/S1HT NO DIFFERENCE). RND is not an arm here
  (study 17 carries the monkey reference on the same panel; a pool would add about five hours of solves).

## 2a. Smoke observations before the freeze (mechanics only; one slate, 2023 W9, bank 1406, placeholder BASE λ 0)
Shares of DEALT entries; outcomes were not read.

| arm | QB+1 only | QB+2+ | bring-back | second-game pair | players in the QB's game | top player's entry share |
|---|---|---|---|---|---|---|
| C | 0.00 | 1.00 | 1.00 | 0.10 | 4.0 | 0.70 |
| MIX | 0.55 | 0.45 | 0.46 | 0.40 | 2.9 | 0.57 |
| WS | 0.94 | 0.06 | **0.00** | 1.00 | 2.1 | 0.69 |
| DS | 1.00 | 0.00 | 1.00 | 1.00 | 3.0 | 0.69 |
| C_LA | 0.00 | 1.00 | 1.00 | 0.01 | 4.0 | **0.85** |
| MIX_LA | 0.45 | 0.55 | 0.90 | 0.45 | 3.4 | **0.88** |

- **WS realizes NO bring-back.** "Optional" is never chosen by the mean objective, so WS is in practice QB + 1 + a
  second-game pair, without a bring-back. It remains the decision contrast "one new shape everywhere"; it is not the
  field's mix. This is the strongest argument for MIX's fixed quotas: whatever is optional, a mean optimizer will not do.
- **The line-aware deals CONCENTRATE** (the top player in 85–88% of entries vs 57–70%): they reuse the rows with the
  highest simulated crossing up to the head layout's busiest-row count. They stay exploratory; their concentration is
  printed beside any ticket difference.
- **MIX's dealt bring-back share (0.46) is below the 0.58 the quotas imply.** The interleave hits its entry quotas before
  the deal (0.305 / 0.143 / 0.276 / 0.276 on this plan's head-layout weights, which are 11, 11, then 1 per rank); the
  small-contest overlap limit then replaces rows in the 5- and 3-entry contests (40 of the 105 entries). The binding
  census reports the realized dealt cell shares over 12 slates; a cell more than 10 points from its quota is a design
  question at that review, not after scoring.
- Build time: about 4.5 minutes per slate single-threaded (no pool), so the scored run is about 40 minutes on 24 workers.

## 3. The base selector (fixed from study 17's read, before the freeze)
`BASE = {"lam": 0.0}`: the plain-mean C. **Study 17 (system study Addendum 127; LEDGER d06fd69; reproduced byte-identically
by the laptop)**: DR tickets −1.623 [−4.057, +0.500], EM −2.575 [−6.481, +0.660], PG −2.972 [−6.723, +0.198], all NO
DIFFERENCE with every point estimate negative and the descriptive guard far below its margin (mean finish −6 to −9
points). No arm passed, so C stands and every study-18 arm is built on it.

## 4. Panel and plan
- The 53 `k1` slates of 2022 (17), 2023 (18), 2024 (18) with Millionaire ownership; **fresh banks 1415/1416** (unused as
  bank labels in the lab's branch scan, 10-05); smokes and the binding census on throwaway bank 1406.
- **The plan:** production's Week-5 DRAFT plan A (`~/week5-plan/contests.draft-A.json`, private, sha256
  `8d97f5ebbc5c92ff6e5b8a19c62e31d6b17035f92e3f33a899fb8485b970e1f6`; 15 contests, 21 entries, lines p78.8–p90.9, all
  mean track), its contest list REPEATED 5× with ids suffixed -c1…-c5 (`~/s18-panel/plan-draftA-copies5.json`, sha256
  `ee6c520748d30536c32ffba8dfc6927df7a01db2cd5de51022c88129fa6bb68c`; 75 contests, 105 entries needing 85 distinct rows,
  within K 105). Each contest keeps its single-entry mechanics (the head layout gives each single-entry contest a
  distinct row) and the deal reaches the book's deeper rows, which restores power. (A 7× copy needs 119 distinct rows,
  more than K; the real draft-A needs 17 rows for its 21 entries.) If the operator's final plan differs materially (deep lines back, a different
  line mix), the dealing results read as plan-specific.

## 5. Endpoints and decision rule (each decision arm against C)
- **PRIMARY = TICKETS:** dealt entries at or above each contest's line, summed per slate, ARM − C, paired; season-clustered
  bootstrap, B 20,000, seed 20261005; **two-sided 0.9875 per decision arm** (0.975 split over MIX and WS).
- **PASS** = lower bound > 0, at most one of the three season means < 0, and the GUARD holds: mean entry finish, one-sided
  0.9875 lower bound > −0.015. **FAIL (guard)**, **WORSE** (upper < 0), **DEAD LEVER** (> 80% dealt identically to C),
  **NO DIFFERENCE** otherwise. The guard is printed for every arm in every branch.
- **Secondaries:** zero-ticket slates, contests with a ticket, best ≥ 200, the worst-decile slate, the SHAPE of the dealt
  entries (QB+1 only, QB+2+, bring-back, second-game pair, players from the QB's game, games used, RB with his QB, RB as
  the bring-back, the top player's entry share) beside the field's and top 1%'s, and the simulated line-crossing share
  (in-sample; the LA deals are chosen on the same worlds; never decision-bearing).
- **Power:** with 105 dealt entries per slate, a tickets effect smaller than about +38% reads NO DIFFERENCE on 53 slates.

## 6. What a verdict can do
- **PASS:** a reason to offer a reversible Week-5 trial of the passing arm, built through production's `--main mix` path
  (re-pinned lab clone `production/live-pin-w5-20261006` @ `f69598b` + the union change, reviewed), "arm + ownership term"
  as the transfer caveat states. The operator decides.
- **NO DIFFERENCE with the guard intact and the shape moved:** a legitimate reason to choose either, stated as such; not
  a PASS.
- **WORSE / FAIL (guard):** the arm is not offered.

## 7. Integrity
- **Code:** nfl2 `production/s18-stack-shapes-20261005` @ `5869a1b`: `experiments/s18_stack_shapes.py` (sha256
  `9e475065…d624`), `scripts/s18_drive.py` (`f99ceecf…03c5`), **`scripts/s18_report.py` (the reader, sha256
  `1dbef2544094a7b6e15ad9487ad33ad92da8536462dfce970e40888ccc8fddda`)**, `scripts/s18_census.py` (`25b4b744…0229`),
  `tests/test_s18_stack_shapes.py` (7) and the optimize() extension's tests (5); 21 tests pass with study 17's. The reader is study 17's frozen reader adapted; a test asserts its printed levels
  against this text.
- **Order:** this freeze → the BINDING outcome-blind census on bank 1406 (all 53 panel slates, mechanics only: realized
  cell shares in rows and entries, shape marginals, passes, short books, changed vs C), reviewed by both parties → the scored run on 1415/1416
  (nothing changes after it starts) → a confirmatory mechanics-only census from the scored rows, committed before the
  reader → the reviewer's read → the laptop's byte-identical re-run → the LEDGER row and an Addendum.
- **Transfer caveat:** no ownership term in any arm; the live book adds the FP term upstream. Any trial is "arm + term".

---

## Deviation note 1 (2026-10-05, after the binding census, BEFORE any scored bank; reviewed by both parties)
**(i) The binding census** (bank 1406, all 53 panel slates, mechanics only, 0 errors; nfl2 `results/s18/CENSUS_s18_binding.txt`
@ `fd23850`):
- MIX cells: realized ROWS A1 .305 / A2 .143 / B .276 / C .276; realized DEALT ENTRIES A1 .269 / A2 .159 / B .224 / C .349
  (quotas .30 / .14 / .28 / .28: within 10 points each, so no design change; the shifts come from the small-contest overlap
  limit and are accepted as the arm, stated). Passes to A1: 0. Short books: 0 in every arm.
- Shape of dealt entries (MIX | C | WS | DS; top 1% | field): QB+1 only .572 | .000 | .923 | 1.00; .48 | .53. QB+2+ .428 |
  1.00 | .077 | 0; .44 | .30. Bring-back .493 | 1.00 | .123 | 1.00; .59 (41–66%) | .43. Second-game pair .477 | .224 | 1.00 |
  1.00; .46 | .46. Players in the QB's game 3.04 | 4.00 | 2.35 | 3.00; 3.2 | 2.8. Games used 4.78 | 4.28 | 4.84 | 4.36; 4.9 |
  5.3. Top player's entry share .580 | .695 | .693 | .690.
- MIX sits at or between the top-1% and the regulars' references on every marginal. WS rarely takes a bring-back (.12).
**(ii) A path typo in §4:** the draft plan's path is `~/private/week5-plan/contests.draft-A.json` (its sha256 `8d97f5eb…e1f6` as
written is correct).
**Next:** the scored run on 1415/1416; nothing in the design changes after it starts.

## Deviation note 2 (2026-10-05, after the scored run, BEFORE the reader): the confirmatory census
- The scored run on 1415/1416 finished: 106/106 slate-banks, 0 errors; nothing in the design changed after it started.
- The confirmatory census (`scripts/s18_census.py` sha256 `25b4b744…0229`, mechanics fields only) is committed at nfl2
  `results/s18/CENSUS_s18_confirm.txt` before the reader runs: MIX dealt cells A1 .266 / A2 .158 / B .227 / C .349; MIX
  shape QB+1 .576, QB+2+ .424, bring-back .493, dual .480, QB's game 3.03, games 4.76, top player .575 (the binding census
  on 1406 within 0.01 on each); passes 0; short books 0.
- Next: the frozen reader (`1dbef254…`) on 1415/1416.
