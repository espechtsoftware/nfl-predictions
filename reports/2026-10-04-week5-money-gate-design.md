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

## Addendum 1 (2026-10-04, reviewer's review of 838b3c46): committed BEFORE any arm is scored

1. **Contamination changes the rule.**
   - A2 and A3 were motivated by Week-4 outcomes, so their Week 4 cannot count toward switching.
   - Their conditions (a)–(d) are evaluated on **Weeks 1–3 only**, with (b) becoming "at least 2 of 3 weeks". Week 4
     is shown beside them, labelled "not independent".
   - A1 and A4 keep Weeks 1–4.
   - A1 = A4 in Weeks 1 and 2 (no point-in-time ownership input), so **the ownership tilt is evaluated on Weeks 3–4
     only**.
   - Week 2 runs without the term, disclosed. No lag file is rebuilt: past-week ownership sets collapse without the
     implied team total (the 09-29 finding).
2. **One payout must not decide it.**
   - Every return multiple is reported twice: as is, and **excluding that arm's single largest payout**.
   - Condition (a) must hold on BOTH.
   - Cashes and ticket value are also shown by contest class.
3. **Contests are not independent.** With the head layout the same rows are dealt into many contests.
   - **The resampling unit becomes the cluster:** within each week, the connected component of contests linked by any
     shared book row, taken over the union of A1 and the arm compared.
   - The bootstrap resamples clusters, and condition (c)'s sign test runs over clusters (cluster statistic = the sum
     over its contests of the arm-minus-A1 difference in mean entry finish percentile).
   - The effective number of independent units (clusters) is reported for every comparison.
   - If a week collapses into a single cluster, (c) is evaluated with weeks as the units. With four (or three) units
     that cannot reach p < 0.20, so (c) then fails rather than being waived.
   - The contest-level sign test is still printed, labelled **anti-conservative**.
4. **Multiplicity.**
   - Three alternatives are tested against A1. Under a null of no difference, (c) alone passes about 10% of the time
     per arm in the favourable direction; (a), (b) and (d) are positively correlated with it and cut that roughly in
     half.
   - So the **expected false-qualifier rate is about 5% per arm and about 10–15% for "any of the three"**.
   - The harness also estimates it by permuting arm labels within clusters, and the estimate is printed beside the
     result.
5. **A pre-written rollback trigger for any Week-5 trial.** If an alternative arm X is adopted for Week 5:
   - A1 is still built every week as a paper book.
   - **Trial ends and Week 6 returns to A1 if, in Week 5:** (i) X's book is below the M2 median (book percentile
     < 50), OR (ii) X's mean entry finish percentile is more than 5 points below A1's paper book on the same contests.
   - Either test is computed Monday from the settled standings and recorded in the weekly scorecard.
   - **Otherwise the trial continues week by week** under the same two tests.

Answers to the design's questions (reviewer):
- p < 0.20 stands only together with points 1–5.
- Week 2 runs without the ownership term, disclosed.

## Addendum 2 (2026-10-05 early, reviewer ruling on a flaw found outcome-blind by the harness; committed BEFORE any arm is scored)

**The flaw.** The harness (`production/moneygate-harness-20261005` @ `1ee3ba8a`) found it from the layout alone,
before any arm was scored.
- Under the head layout, Weeks 1 and 2 are each ONE cluster for every comparison. Week 3 has 2–14 clusters and Week 4
  2–6, each dominated by one large cluster.
- By Addendum 1.3, condition (c) therefore fell back to weeks as units, and it failed for every arm whatever the
  outcomes.
- Addendum 1's premise was also wrong: 4 of 4 week-units gives an exact two-sided p of 0.125.

**The rule, replaced:**
1. **Condition (c) uses weeks as the units, with the exact sign test.** **No arm can be licensed statistically from
   these weeks:**
   - A2 and A3 have 3 units (Weeks 1–3; minimum p 0.25);
   - A4 has 2 units (Weeks 3–4).

   The replay answers **Q1** (would the current system have made money?) and **Q2** (does it beat chance, A1 vs M2).
   The alternative arms are shown **descriptively**, for the operator's judgment.
2. **A4's condition (b) is read on Weeks 3–4** ("2 of 2"), because A4 equals A1 in Weeks 1–2.
3. **A descriptive line per arm, never a pass or fail.**
   - Each distinct book row is scored by its finish percentile in that week's Millionaire field.
   - The statistic is the mean, X − A1, over the symmetric difference of the two books' rows.
   - Its significance comes from a permutation of arm labels within week. The effective n is shown, and the result is
     labelled anti-conservative (rows share players).
4. **No default arm.** A1 has not been shown to beat chance either. The honest default: **no arm is statistically
   preferred; the operator chooses; any switch is a reversible trial with the written rollback trigger (Addendum 1.5).**

**Disclosed deviations (accepted by the reviewer):**
- **Lab source.** One lab source (32cdb61) for all weeks. The older pins lack `nfl2/two_track.py`, so this tests
  today's selection on each week's archived pool.
- **W1 supply.** A single Saturday run: `20260912T132523949270Z`, the one with banks.
- **W2 T-70 pool.** The D800 T-70-slot run (`20260920T155005557498Z`). W2's A0 entered the Saturday K97, so A0 and A1
  are not like-for-like in Week 2.
- **Ownership term.** A1 = A4 in Weeks 1–2 (no point-in-time ownership file).
- **Routing.** Today's routing rule for W1–3; it reproduces Week 4's routing exactly.
- **No vetting in any arm.** Every arm EXCLUDES vetting (point-in-time vetting inputs do not exist for all weeks), so A1
  is "the current selection and layout, before vetting". Week 4 is dealt in union order; the entered bundle was
  re-ordered at vetting, so 8 of 25 contests differ.
- **M2 scope.** The M2 comparisons exclude the W4 Millionaire (its entry count differs from the arms').
- **Scorer validated:** the A0 known-answer gate passed exactly. All 534 entries match rank, fee and tickets, and each
  week's total equals the settled entry history. A 0.01-point mutation fails the gate.
