# Week-5 money gate: design, frozen before any arm is scored (2026-10-04, laptop agent)

Written for the operator and the reviewer. The operator asked (2026-10-04): "test it selecting over weeks 1-4 and
determine if it would have made any money before I decide if im putting any money in."

This document fixes:
- the arms;
- the inputs;
- the metrics;
- the decision rule.

It is fixed BEFORE any arm below is scored (reviewer integrity rule 4). Anything added later is a new, disclosed replay.
The answer goes to the operator by Friday 10-09.

## 1. What is being tested, and what is not

**What is tested.** The SELECTION and LAYOUT step is tested on each week's REAL archived pools: which lineups we pick
from the pools we built, and how we deal them into contests. This is where the post-mortem points:
- the pools beat random legal lineups in 66 of 86 contests;
- our picks from those pools are indistinguishable from random picks (M2 72nd percentile over W1–4; 50 of 86
  contests).

**What is not tested.** Pool GENERATION is held fixed. Every week's pools are 98–100% "QB + 2 pass-catchers + a
bring-back" (outcome-blind census, 10-04). So a different stack shape (for example QB + 1) cannot be tested by
selection: it needs regenerated pools, a separate and heavier replay. Listed in §7 and not part of Friday's answer.

## 2. Inputs (point in time only; integrity rules 1–2)

| Week | Saturday pool | T-70 pool | Projections | Ownership term input |
|---|---|---|---|---|
| 1 | fa5d035 09-12 runs (workstation copy, verified) | e7255e9 D800 `20260913T160405364118Z` | archived batch 09-13 16:03:49 (frame equal to the batch) | none (no 2026 lag yet), so the tilt arm equals the plain arm |
| 2 | D12800 `20260919T153008787414Z-2dc116c` (MANIFEST-verified) | T-70 runs in `week2-release-2dc116c` (workstation copy) | archived batch | point-in-time lag file if archived; otherwise none, disclosed |
| 3 | D12800 `20260926T153408285093Z-65305f5` | `20260927T155027472554Z` (5e80d6b1, verified) | archived batches 09-26 / 09-27 | the W3 sets file `10175b0e…` (point in time) |
| 4 | `20261004T100027765133Z` | `20261004T155026918221Z` | T-70 batch 10-04 15:40:30.984 | FP file `0ec90a6b…` scaled by `ownership_lag.csv` (`5e1b0ade…`), as entered |

- **Models:** walk-forward by construction. The pools were built pre-lock by the deployed cuts (W32/W39/W40, registered
  before each week's first game).
- **No re-projection.** Today's feature tables are never used.
- **Fields:** the REAL captured fields. `nfl_raw.contest_entries` for W1–3; the 26 local standings files for W4,
  imported Monday.
- **Payouts:** the REAL payout ladders. Contest-details for W1 (3/3), W2 (12/12, fetched 10-04), W3 (45/45) and W4
  (25/26). The W4 hand-entry contest 196305080 is excluded from every arm alike.
- **Contests:** each week's real contest list and entry counts (the week's `contests.json`, private), dealt with
  today's layout code.

## 3. Arms (all run with the same, current code: `scripts/union_reselect.py --rehearsal` plus `enter_layout`)

| Arm | What it is | Flags beyond the week's defaults |
|---|---|---|
| **A1 CURRENT** | The system as entered in Week 4 | `--main pmo_x50 --main-cap-share 0.5 --main-own-tilt 0.20` (with that week's point-in-time ownership file); field sleeve on the Millionaire row; head layout, `ENTER_SMALL_MAX_SHARED=5`, overlap ceiling 10 |
| **A2 MEAN** | Top lineups by projected mean under the caps: the "simple" arm | `--main mean` (top-K by T-70 mean, at most 7 shared, DST cap 0.25); same sleeve and layout |
| **A3 CAP30** | A1 with a tighter per-player exposure cap (concentration, study 1) | `--main-cap-share 0.30` |
| **A4 NO-TILT** | A1 without the ownership term (isolates the tilt) | `--main-own-tilt 0` (the union's own `book_main_control`) |
| A0 ENTERED | What we actually entered | reference only (W1–3 used older code) |
| M1, M2, M3 | The monkeys, as built (1,000 books each; M2 = random pool rows under the caps and dealing) | reference |

**Disclosed contamination.** A2 is proposed partly because the pool's top-105 by mean scored 121.9 on Week 4 (an
outcome already seen). So A2's Week-4 result is not independent evidence; its W1–3 results are. A3 is motivated by the
Week-4 concentration (Chase in 49% of the book), so the same caveat applies to its Week 4.

## 4. Metrics (per week, then pooled over W1–4)

- **Return multiple:** winnings, with tickets at face, over entry fees. Dollars stay private (`~/private/moneygate/`);
  multiples are public.
- **Cashes** and **per-contest finish percentile** of each entry.
- **Each arm's percentile against M2** (book level, mid-rank), and the **per-contest sign test against M2** (reviewer
  note 2).
- **Pool skill beside every week:** the projected-vs-realized rank correlation (W1 0.33, W2 −0.49, W3 0.32, W4 0.06;
  reviewer note 1).
- **Uncertainty:** a contest-level bootstrap (10,000 resamples within week, weeks fixed) of the pooled return multiple
  and of each arm-vs-A1 difference. Reported as a range, plus an explicit "cannot tell" when the range crosses the
  comparison.

## 5. Decision rule (what I will recommend; the operator decides)

1. **Would the current system have made money?** Report A1's pooled multiple and its range.
   - If the range's upper end is below 1.0×: "No: on Weeks 1–4 the current system would have lost money."
   - If the range's lower end is above 1.0×: "Yes."
   - Otherwise: "Cannot tell from four weeks", with the point estimate.
2. **Is it better than chance?** A1 vs M2 (the reviewer's primary): the book percentile and the per-contest sign test.
3. **Should Week 5 switch to another arm?** Recommend arm X over A1 only if ALL hold:
   - (a) X's pooled multiple exceeds A1's;
   - (b) X beats A1 on mean entry finish percentile in at least 3 of 4 weeks;
   - (c) the per-contest sign test X vs A1 over W1–4 favours X with two-sided p < 0.20 (lenient on purpose: four weeks
     cannot do better, and this is a reversible trial under adoption track v2, not a permanent adoption);
   - (d) X's M2 percentile is at least 50.

   If several arms qualify, take the simplest (A2 before A3 before A4). If none qualifies, keep A1, and say plainly
   whether A1 beats chance.
4. **What any recommendation is.** A reversible Week-5 trial with a stated rollback (return to A1 the following week)
   and a weekly scorecard line. Never a stake recommendation: the stake is the operator's.

## 6. Integrity checks before any scoring

- Each arm's book is rebuilt twice and must be byte-identical (`union_paper_rebuild.sh` determinism).
- A vacuity check: an arm whose book is byte-identical to A1's is reported as a dead lever (W1 A4 by construction).
- Every written roster is DK-valid (`union_reselect` revalidates it).
- An outcome-blind smoke of the full path on Week 4 BEFORE the scoring code reads any outcome (CLAUDE.md rule 1).
- Inputs are identified by content (sha256 against receipts and manifests), never by path.

## 7. Not in Friday's answer (listed so nobody mistakes them for tested)

- **A different stack shape** (QB + 1, no forced bring-back): needs regenerated W1–4 pools (`STACK_QB_MIN=1`), a local
  multi-hour build per week. Proposed as the next replay after Friday if the operator wants it.
- **A minimum exposure to every high-total game:** needs new selection code. Proposed, not built.
- **The 2022–25 field-relative check:** no fields exist for those seasons, so it is a different yardstick; later.
