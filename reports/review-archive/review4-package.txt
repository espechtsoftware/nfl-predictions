# External review #4: where is the remaining edge? (2026-08-05)

You are reviewing a DraftKings NFL DFS (daily fantasy) prediction and
lineup-construction system at the end of a six-week intensive program.
Three prior external reviews were commissioned; every finding was
verified, and the actionable ones were implemented and tested. This
review has a different brief: **the program has hit a wall of null
results, and we want an independent judgment on whether the wall is
real — and if not, where the remaining exploitable edge is.**

Be adversarial. Do not restate our conclusions back to us. If you
believe a tested-and-buried idea was tested wrong, say exactly how the
test was flawed. If you believe 25/107 is near the practical ceiling,
say so and defend it quantitatively.

---

## 1. What the system is

- **Task**: enter 40-50 lineups/week into DraftKings NFL tournaments
  (a "Milly Maker": ~150k entries, top-heavy payout; plus ~20k-entry
  qualifiers where only ~top-4 seats matter). A lineup = QB, 2-3 RB,
  3-4 WR, 1-2 TE, FLEX, DST under a $50,000 salary cap.
- **Data**: free only. nflverse play-by-play/rosters (2016-2025),
  DraftKings salaries, historical contest standings + ownership for
  ~107 main-slate weeks (2019, 2021-2025), sportsbook prop lines,
  Open-Meteo weather. BigQuery warehouse; Cloud Run jobs (incl. L4
  GPU) for all heavy compute.
- **Player model**: per-component (pass/rush/receiving yards, TDs,
  receptions...) LightGBM ensembles — 3 members, seeded/column-
  shuffled, averaged — trained walk-forward, strictly point-in-time.
  Per-player quantile marginals from TabPFN (zero-shot in-context
  tabular transformer) cached to a table; the sim samples from these
  marginals, correlated by a possession-level Markov game simulator
  (fitted pace/leverage/garbage-time states).
- **Construction**: simulate ~2,000 correlated player-score worlds per
  slate. Candidate lineups come from (a) per-world argmax MILP solves
  ("boom" batch — 13% of candidates, 54% of weekly best entries),
  (b) mean-objective MILP with diversity constraints, (c) leverage
  tilts. Hard rules, each validated: QB + 2 same-team pass-catchers +
  opponent bring-back stack; one sub-$4k punt valued at its p90; fade
  the chalk on OUR projections (ownership model trained on historical
  ownership); salary floor.
- **Selection**: greedy max-coverage over simulated worlds — pick the
  set of 40 whose best-in-world scores cover the most worlds. Entries
  are explicitly co-equal (measured: the sim cannot rank its own
  entries within a week — entry #1 finishes at the 49th percentile of
  its own portfolio's realized scores; Spearman +0.086).
- **Evaluation harness** (hard laws, learned expensively): six-season
  replay panels on Cloud Run, deterministic (same build twice = same
  number), co-run control on every table rebuild, leave-one-season-out
  adoption rule (positive in >=4 of 6, at most 1 negative),
  byte-identical-arm vacuity checks, image-content verification before
  trusting any A/B.

**Headline metric**: weeks (of 107) where the best of 40 entries
clears 194 DK points — the *minimum* winning Milly line across our
seasons (the average winning line is ~237). Current sealed system:
**25/107**, mean best-of-40 = 179.7, median contest percentile 14.1%.

## 2. What is validated and adopted (effect sizes on the 107-week panel)

| Change | Effect (line-clears vs control) |
|---|---|
| 3-member seeded LightGBM ensemble | **25 vs 14** — the largest single gain |
| TabPFN quantile marginals (vs empirical) | +3-4, and better calibrated where boosting under-covers |
| EW draw shaping + punt-boom + QB variants + own-fade | +4-6 combined, cross-build replicated |
| Schedule features (net rest, body clock) | small positive, survived LOSO |
| Stack mandate (QB+2+bring-back) | removing it: 17 vs 25 — costs a third of all tails |
| Chalk fade | best clears the line in 60% of chalk-bust weeks vs 40% of chalk-win weeks |

## 3. The measured challenges — the wall, in numbers

These are measurements, not hypotheses. Each has an addendum in a
70-entry experiment ledger.

**W1. The assembly gap (the central puzzle).** Perfect-hindsight
optimal lineups average ~268 points. Actual Milly winners capture ~88%
of their week's optimal. Our best-of-150 captures 69%. Decomposition:
**84% of the optimal lineup's players are somewhere in our 150-entry
pool** — identification is fine — but the best entry contains only
**1.87 of the optimal 8**, which is BELOW the exposure-preserving
random null of 2.51. Greedy max-coverage selection actively scatters
co-booming players across entries (diversification is the point of
coverage — but it appears to diversify away exactly the co-boom
concentration that wins). Everything we tried to close this failed
(see graveyard): ceiling-wildcard injection, peak-slice replacement,
more boom solves, several tilt families.

**W2. Individuals are unpredictable; only populations rank.** The sim
ranks *configurations* (40-entry strategies) over 107 weeks with clear
separation, but cannot rank its own entries within a week (49th-
percentile problem above). Injecting the players with the highest
TabPFN q99 ceilings directly into lineups made things worse (23 vs
25). The players who actually produce 40+ point booms were not
flaggable ex-ante by any quantile we model.

**W3. The 4-entry coverage cliff.** Our Milly allocation is only 4
entries (bankroll reality). At 4 entries the line-clear rate collapses
to 3/107 (vs 25/107 at 40). An expected-dollars selection objective
(optimize simulated ROI directly instead of tail coverage) tested
NULL: ties on tails/ROI, loses on median percentile.

**W4. The field is modeled naively — and we have measured what real
fields look like.** Opponent lineups are simulated as products of
marginal ownership (an ownership model we trained). Real fields have
lineup-level structure our model lacks: stacking habits, duplication
concentration, salary norms.

*The leaderboard stratum study* (full per-entry standings from 74 real
2021 contests, fields up to ~470k entries, every entry's roster and
ownership — not just winners): we stratified each contest's
leaderboard (winner; places 2-10; top 0.1%; top 1%; top 10%; median;
bottom) and profiled each stratum's lineups. Findings:

- **Only the winner is contrarian.** Winner lineups average an
  ownership-sum of ~235; *every* other stratum — including places
  2-10 and the top 0.1% — sits in a tight 245-254 band,
  indistinguishable from mid-field. Contrarianism does not improve
  finishes generally; it is specifically the trait of the single
  lineup that wins.
- **Only the winner is unique.** ~85% of winner lineups are duplicated
  somewhere in the field vs ~97% for every other stratum — winners are
  3-5x less duplicated. Near-winners are chalk-shaped and heavily
  duplicated; they split their prize.
- **Implication we adopted**: target *winner* anatomy, not top-1%
  anatomy. Optimizing to "finish high" produces chalk mirrors that tie
  with thousands; the objective must be P(beat the field's max) with a
  duplication penalty, not expected percentile.
- Corroborating winner anatomy from our winners-only dataset (all 107
  weeks): winners capture ~88% of that week's hindsight-optimal and
  spend the full cap (2025 median salary left = $0).

Our selection bar currently uses a constant empirical extension (field
sample-max + 0.256 sd, measured by subsampling those 74 contests)
rather than a real field model. A "skeleton resampler" (resample real
historical lineup archetypes onto current-week players, preserving
stack/dupe/salary structure) is designed but not built — the 2021
archive is an older FLEX format, so calibration needs September's
classic-format standings imports.

**W5. An alternate architecture reached only parity.** A from-scratch
rebuild ("greenfield": per-world argmax as the primary generator +
beat-the-field-bar selection, uniqueness emergent rather than
constrained) scored 27 with a bar-scaling bug and exactly 24-25 (=
parity) once the bug was fixed. Two attempts, never ahead once
correct.

**W6. Verdict fragility near the noise floor.** The 107-week panel's
noise band on line-clears is roughly ±2-3 even with determinism and
co-run controls. Most surviving effects are +3 to +6. We may be at the
resolution limit of the instrument — which is why "test more levers"
keeps returning nulls.

## 4. The graveyard (do not re-suggest without a specific flaw in the burial)

All tested on the full six-season panel against the sealed control
(25), post-ensemble, deterministic builds, vacuity-checked:

- Heterogeneous ensemble member (HistGradientBoosting 3rd member): 21.
- TabPFN q99 ceiling-wildcard injection (top-8 uncovered, locked into
  candidates): 23.
- More per-world boom solves (N_BOOM dose): 25 (null).
- Peak-slice: replace last-K selected with argmax-probability picks: 21.
- Loosened stack mandates (2 variants): 17, 17.
- Vacancy-boost redesign v2: 21 (family retired).
- Value-2E redesign: 26 (within noise; near-miss, not adopted).
- Expected-dollars selection at 4 entries: null (Addendum 70).
- Script-feedback, divisional tilt, alt-ceiling, rookie-widen,
  showdown-fade: all null or negative post-ensemble. (A hard law we
  proved three times: single-model-era verdicts DO NOT transfer across
  the ensemble — three "wins" became nulls/negatives when re-tested.)
- Legal late-swap (position/salary-feasible, chase q90 after early
  games lock): +0.9 points mean-best — null. Hindsight-perfect
  swapping is worth +69, but it requires knowing outcomes.
- Learned game simulator (LEM, GPU-trained event model): failed its
  rollout gate (2/5) vs the fitted possession-Markov core.

## 5. Constraints for your recommendations

- Free data only (no paid projections; we do ingest free prop lines).
- Solo operator; September onward is in-season operations with at
  most small code changes; big builds must wait for evidence from
  real 2026 entries.
- BigQuery + Cloud Run (GPU available, ~$0.70/hr, 1h task cap).
- Validation laws are non-negotiable: walk-forward only, six-season
  panels with co-run controls, LOSO adoption rule.
- Real 2026 standings/ownership begin accruing in September; a
  classic-format skeleton-resampler field model is already the #1
  scheduled September build.

## 6. Questions for you

1. **Is W1 (assembly below random null) actually a defect?** Or is it
   a mathematical consequence of max-coverage set selection that
   *should not* be "fixed" (i.e., concentrating co-booms into one
   entry necessarily un-covers other worlds and lowers P(any entry
   clears))? If you think it's fixable, propose a selection objective
   that provably trades coverage for co-boom concentration at the
   right exchange rate — and a panel-testable form of it.
2. **Is 25/107 near the ceiling for this instrument?** Winners capture
   88% of optimal with 150k entries of human diversity; we capture 69%
   with 40. Given W2 (individuals unpredictable), what is the
   theoretical best-of-40 capture rate, and is the remaining gap
   worth chasing versus accepting?
3. **Given W4, what is the highest-value use of the September
   standings data?** Rank: skeleton-resampler field bar, duplication-
   aware selection penalty, ownership-model recalibration, per-contest
   line models, something we haven't considered.
4. **Is there any construction lever we have NOT tested** that is (a)
   implementable in this stack, (b) testable on the six-season panel,
   and (c) not equivalent to something in the graveyard? Be specific:
   what code change, what predicted mechanism, what panel metric moves.
5. **The 4-entry Milly problem (W3)**: with only 4 bullets against
   150k, is there any selection principle that beats "first 4 of the
   40-entry coverage run" — or is 4-entry Milly play simply -EV noise
   we should reallocate to the 20k qualifiers?
6. **What would you delete?** Complexity that survives because it
   never got re-tested post-ensemble, rules that might be fighting
   each other (e.g., does the chalk-fade fight the stack mandate in
   high-ownership game environments?). Name the specific test that
   would justify each deletion.

7. **The 74-contest per-entry archive (W4) is sitting on disk now.**
   We have used it for: the stratum profiles above, the empirical
   field-max extension (0.256 sd), and duplication rates. It is 2021
   FLEX-format, so lineups don't map 1:1 to today's roster rules —
   but ownership, duplication, stacking, and score-distribution
   structure are all measurable. What analyses of this archive have
   we missed that would change construction *before* September data
   arrives?

Answer with numbered findings, each with: the claim, the reasoning,
the concrete test or code change, and what result would falsify it.
