# Targeted external review #3 — THE OBJECTIVE FUNCTION and THE FIELD MODEL (2026-08-05)

You are reviewing an NFL DFS system at the end of its pre-season
program. Two questions ONLY — the two places its own builder believes
an outsider could still change its mind about something big. Do not
review anything else; assume the rest is audited (it is — 67 addenda).

## Question 1: Is the objective function right?

Current objective: select 40-150 entries to maximize
P(best-of-portfolio >= L) where L is a FIXED line per contest
(qualifier ~187, Milly-min 194), lines estimated from field size via
extreme-value scaling and provisional until real standings arrive.
The operator's REAL September portfolio: 3 qualifiers x 14 entries
(~20k-entry fields, seat-style winner-take-most payouts) + 4 entries
in a $5/832k-entry Millionaire (top-heavy lottery).

Evidence to reason over:
- Measured curve: P(best-of-N >= 187) = 1.9% @1, 20% @15, 31.5% @40,
  44% @150 (3 seasons, 54 weeks).
- Real winners average 88% of hindsight-optimal; our best-of-150 is
  69%; per-entry engine is field-typical; median finish top-14%.
- Leaderboard stratum (19.5k entries, 63 contests): only the WINNER is
  contrarian and unique (own-sum 235 vs 245-254 for every other
  stratum; 3-5x less duplicated). Near-winners are chalk-shaped.
- The system performs BEST in chalk-bust weeks (60% line-clearance vs
  40% in chalk-win weeks).
- An expected-dollars selection objective (payout-curve-aware) exists
  and beat tail-coverage on simulated ROI, held back pending real
  payout curves.
Critique: is fixed-line tail-coverage the right objective for
seat-style qualifiers (advancement, not score, pays)? For the Milly
lottery slice? Should the objective be P(rank 1) against a modeled
field max (see Q2), expected dollars under the real payout curve,
or something else? What would you change GIVEN the operator's actual
contest mix, and how would you validate the change under six-season
panels + LOSO?

## Question 2: Is the field model right?

Current field model: a value/salary softmax ("naive ownership") for
field simulation, plus a LightGBM marginal-ownership model (OOS corr
.727) used in the chalk fade. The field's LINEUP DISTRIBUTION
(duplication, stack habits, intra-lineup correlation) is NOT modeled.
A branch experiment (code below) replaces the fixed line with a
per-world Gumbel-extended sampled-field maximum and reached parity
with the tuned incumbent (27 vs 25 of 107 tail weeks) on its first
attempt.

Evidence: the stratum table above; per-entry standings data (63
contests, 2021, FLEX format) on disk; the operator's own September
imports will provide classic-format per-entry data weekly.
Critique: what field-model architecture would you build from these
assets (explicit generative lineup model? dupe-count model? copula
over ownership?), what does it change about the selection objective,
and what is the cheapest validation path? Be specific about the
Gumbel extension's assumptions in the branch code (sampled max +
sigma*(sqrt(2 ln N)-sqrt(2 ln n)) — is that defensible for a
150k field from a 1.5k sample?).

Respond as a numbered findings list, most decision-relevant first,
each with severity and a concrete recommended action + validation
plan compatible with the panel rules.

## Evidence extract (Addenda 53-67)

## Addendum 53 (2026-08-04): the entries sweet-spot curve (3 seasons) and the LEM rollout gate

**Entries study complete** (2023-25, 54 week-slates, one 150-entry
sequential run per season; prefix-nested selection makes the first N
entries ~ the optimal N-entry portfolio; reports/entries_study/):
P(best-of-N ≥ 187 qualifier line) = 1.9% @N=1 → 16.7% @10 → 20.4% @15 →
31.5% @40 → 33.3% @50 → 44.4% @150. Marginal efficiency per entry:
~15-28/1000 through N≈10, ~4-7/1000 from 10-40, <1/1000 past 75. The
2025-only knee (~15) softens on three seasons — value keeps accruing to
~75 at reduced rate. Portfolio guidance stands: 30-50 entries per
contest across 2-4 contests beats one max-entry block (a week's entries
are identical across contests, so the benefit is multiple lines/fields,
not independent lotteries); never below ~15/contest (coverage cliff).
Full curve: sweet_spot_curve.csv.

**LEM rollout gate: FAILED 2/5** (400 generated games vs held-out
2024-25): TDs (4.72 vs 5.12 ✓borderline-pass rule) and turnovers pass;
punts over-generated (8.81 vs 7.19), FGs under (3.12 vs 4.03),
play-count sd too wide (15.9 vs 12.5). v1 stays OUT of the sim.
September v2 targets are now concrete: special-teams event calibration
+ drive-count variance, then re-gate — scripts/lem_train/rollout_eval.py
is the fixed yardstick.

## Addendum 54 (2026-08-04): the final harvest — and the honest cross-build picture

The shipping configuration (every adoption as a code default) on the
final tables (audit-fixed SQL) with the regenerated TabPFN cache:
**15/107 tail weeks** (7/1/2/1/1/3 by season), mean-best 175.1, median
14.1%, one ≥237 week (2019's 248.2 — its 193.0 mean-best is the best
2019 of the program). TabPFN mapping verified firing on every row; no
mechanical failure. This is a LOW order-luck draw, and it must be
recorded exactly that way:

| Table build | Same-build control | Adopted-stack result |
|---|---|---|
| A (exam, 2026-08-03) | 23 | QF 25 (+2) |
| B (candidate panel) | 18 | SCHED/TABPFN +6 each, STPFN 24 |
| C (final, fixed SQL) | (CONTROL2 pending) | **15** |

What bounces across builds is the ABSOLUTE level (±5 order luck per
rebuild, twice compounded here: new tables AND a regenerated marginal
cache). What replicated within every build is the RELATIVE gain of the
adopted levers. September's weekly retrains re-draw from this
distribution every Tuesday — the honest expectation is the
distribution's center with the adopted deltas, not any single draw,
and NO re-rolling of builds to chase a pretty number (that is
selecting on noise). The V2 panel's CONTROL2 runs the identical config
on the identical build and will confirm whether 15 is the build's
level or this run drew low within it.

## Addendum 55 (2026-08-04): the variance review (Gemini Pro) — determinism hardening adopted at the source

The targeted second review returned an expert-grade answer; triage:
**ACCEPTED (the cure, commit b0f7d9b):** (1) read-order determinism —
the panel load had NO ORDER BY (the reviewer said "before write"; in
BigQuery the fix belongs at READ time and in the feature SQL's windows
— corrected in implementation); (2) LightGBM deterministic=True +
force_row_wise=True + bin_construct_sample_cnt > N — all three
mechanisms verified real (thread-order histogram accumulation, the
row/col heuristic flip, subsampled bin boundaries); (3) the window
audit found two genuinely unkeyed ranks (017b referee had NO order at
all; 017g ranks tied target counts) — both now keyed. These change
numerics: the next rebuild panel validates them, and the definitive
cross-build test (rebuild twice, diff tables + replays byte-for-byte)
is a documented September experiment.
**DEFERRED with reasoning:** min_data_in_leaf 40→60-80 is a model
change wearing a determinism costume — it needs its own panel, queued.
**KEPT AS DATA DECIDES:** MODEL_ENSEMBLE — the reviewer's
variance-compression critique is right in general but partially
blunted here (TabPFN quantile mapping RESETS per-player marginal
widths after the mean ensemble, so compression affects ranks/levels,
not the simulated spread). The ENS3 arm is mid-flight; its verdict
stands alongside the source fix. Its "sample one member per draw"
suggestion is the better ensemble design if ensembling ever returns.
**CONFIRMED:** its attribution (model-side instigation, selection-side
amplification through the dense 180-194 near-miss band) matches
Addendum 36's own data — meaning source determinism suffices; no
selection-layer intervention needed.

## Addendum 56 (2026-08-04): MODEL_ENSEMBLE=3 ADOPTED — the largest gain of the program, born from the variance investigation

CONTROL2 (14/107) confirmed build C's low level; the ENS3 arm — three
LightGBM members per component, shuffled column orders + distinct
seeds, mean-averaged — scored **26/107** on the same build: +12, LOSO
+5/−1, best median (13.7%), and ABOVE every single-model build level
ever measured (23/18/15). Reading: averaging over the order-luck
dimension doesn't just stabilize the draw, it removes noise the greedy
selection layer was amplifying through the dense near-miss band — the
variance investigation's diagnostic chain (external review attribution
→ ensemble treatment → determinism hardening) converted the program's
biggest nuisance into its biggest win. The Gemini reviewer's
variance-compression objection is empirically refuted here (TabPFN
quantile mapping resets marginal spread after the mean average), while
its determinism-at-source fixes are ALSO adopted (b0f7d9b) — the two
treatments are complementary, not rivals. Registry persists ensembles
(member files + manifest, round-trip tested), so the September weekly
retrain carries K=3 with no operator action. TABCOMP (21, +7) is
superseded as the mean-layer treatment; it retires to the registry as
validated-positive-but-dominated. Shipping baseline: **26/107 —
ENS3's run IS the harvest of record** (identical config to the new
defaults, same tables).

## Addendum 57 (2026-08-05): V2 verdicts — and the ensemble changes what levers mean

Clean-build V2 panel (all arms one build, one image; CONTROL2 14
confirms build C's level):
| Arm | Tails | Δ | Verdict |
|---|---|---|---|
| SCRIPT2 (pace feedback) | 21 | +7 | see below — NOT adopted |
| ALTC2 (market ceiling room) | 19 | +5 (LOSO 3+/0−) | stack test running |
| DIVTILT2 | 16 | +2 | noise-band, retired |
| TABMEAN2 | 15 | +1 | null (marginals already carry TabPFN), retired |

**The lesson of the night, twice-taught:** single-model lever verdicts
do not survive the ensemble. SCRIPT2's +7 became **−2** stacked on
ENS3 (ENSSCRIPT 24 vs 26, LOSO 1+/3−) — the pace-feedback variance
that helped noisy single models is pure distortion once the ensemble
tames their noise. SCRIPT_FEEDBACK stays off. NEW VALIDATION LAW: with
MODEL_ENSEMBLE adopted, every lever verdict must come from (or be
confirmed on) an ensemble-based arm — pre-ensemble arms measure a
model that no longer ships. ALTC2's +5 gets the same stack test
(ENSALTC) before any adoption; the rookie-widen arm (RWIDEN) runs on
the current chain likewise. Also recorded: V1 of this panel was
destroyed by a mid-panel rebuild (my sequencing error) and its file
deleted at Erich's direction — V2 is the only citable version.

**ENSALTC verdict (2026-08-05): ALT_CEIL retired for good.** 22 vs
ENS3's 26 (0+/2− LOSO) — the second lever whose single-model gain
(+5) inverted under the ensemble (−4). The pattern is now law twice
over: the ensemble removes the noise these levers were unknowingly
harvesting. ALT_CEIL's history is a complete arc — vacuous (never
plumbed), revived (audit), single-model-positive (V2), and finally
rejected on the shipping config — the graveyard's best-documented
burial. Only RWIDEN remains open (it runs ON the ensemble config, so
its verdict is directly citable).

**RWIDEN verdict (final open lever): 22 vs 26 — rejected, 1+/4−.**
Third and cleanest confirmation of the post-ensemble law: the rookie
q90 gap is real (0.888 measured), the fitted 1.07 correction restores
coverage exactly, and it still costs 4 tail weeks — marginal
calibration and portfolio tails are different objectives once the
ensemble owns the noise budget. ROOKIE_WIDEN retires to judgment-lever
status (fitted constant preserved for rookie-extreme slates).
**THE PROGRAM'S FINAL ADOPTION SET IS CLOSED**: EW shaping + PUNT_BOOM
+ QF + SCHED features + TabPFN marginals + MODEL_ENSEMBLE=3 — nothing
else survived the ensemble era. The seal sequence (final image, full
deploy, keyed-window rebuild, cache regen, HARVEST-FINAL) measures the
shipping baseline.

## Addendum 58 (2026-08-05): THE SEAL — HARVEST-FINAL 25/107, and the variance work passes its first cross-build test

The sealed image (every adoption a code default) on freshly rebuilt
tables (keyed windows, ordered reads, deterministic LightGBM) with a
regenerated marginal cache: **25/107 tail weeks** (5/1/3/4/7/5), mean-
best 179.7, median 14.1%. THE SEPTEMBER BASELINE.

The cross-build ledger, complete:
| Build | Config | Result |
|---|---|---|
| A (exam) | pre-ensemble control | 23 |
| B (candidate panel) | pre-ensemble control | 18 |
| C (final-1) | pre-ensemble control | 14-15 |
| C | ENS3 (adopted stack) | 26 |
| **D (sealed, hardened)** | **adopted stack** | **25** |

Pre-hardening, three rebuilds of the same single-model config spanned
23→14 (±5 band). The adopted stack crossed a rebuild 26→25. One data
point, not proof — the rebuild-twice protocol remains September's
experiment — but it is precisely the signature the ensemble+determinism
work predicted, and it means the weekly Tuesday retrains should hold
their level rather than lottery-draw it. App and all 14 jobs serve the
sealed image. The pre-season program is CLOSED: six adoptions, a
57-addenda evidence ledger, a graveyard where every burial has a cause
of death, and a baseline measured on the exact bits that will build
Erich's week-1 lineups.

## Addendum 59 (2026-08-05): the gap decomposition — where the missing points actually live

Erich: "the maxes still seem low." Quantified against 54 weeks of
perfect-hindsight optimals (skill-8 MILP on full-slate actuals + ~10
DST, scripts era; gap_decomposition.csv):

| Quantity | Value |
|---|---|
| Hindsight optimal, avg (max) | ~268 (297-321) |
| Real Milly winners, avg | ~237 = 88% of optimal (best of 150k entries) |
| Our best-of-40 / best-of-150 | 66% / 69% of optimal |
| **Optimal players ANYWHERE in our 150 entries** | **84%** (50/54 weeks have ≥6 of 8) |
| **Optimal players in our BEST entry** | **1.87 of 8** |

**The gap is ASSEMBLY, not identification.** We roster the right
players — then scatter them. (Confirms the harvest attribution's
"right stacks, wrong pieces" at scale.) Order-statistics honesty: a
150k field draws 1000x more combinations than our 150 entries; parity
alone predicts the winner beats our best by ~25-35 — our 45-55 deficit
says our per-entry tail engine is field-typical while our MEDIAN is
top-14% — we are consistently good, rarely THE one. Realistic target:
capture 69% -> ~75% (+12-15 pts on best-of-150).

**Structural findings vs optimal (and winners):**
- Optimal lineups are BARELY stacked: 1.65 players from the QB's team
  incl. QB; max-any-team 1.87. Winners ~2.5-3. Our MANDATORY QB+2+
  bring-back forces a 4-man block — more correlated than either. The
  stack minimum PREDATES the A/B era and was never dose-tested — arms
  QBS1 (STACK_QB_MIN=1) and QBS1NB (+no bring-back) launched on the
  sealed config vs HARVEST-FINAL 25.
- Salary: optimal full-equiv ≈ 49.2k -> our 49k floor is CORRECT, not
  binding. Punts: optimal carries 1.30 sub-$4k -> punt rule CORRECT.
- The 16% of optimal players we never rostered skew WR (34/69), mean
  salary $4.8k, mean actual 30.3 (Achane 54.3, Jennings 49.5) — the
  mid-cheap boom our mean-anchored candidates skip. Lever design
  (September): q99-wildcard injection — force the week's top-N
  TabPFN-q99 sub-$6k skill players into ≥1 candidate each (cache
  column already exists); assembly batch — per top boom-sim, solve
  restricted to that sim's top-12 scorers (attacks 1.87/8 directly).

## Addendum 60 (2026-08-05): the graveyard design review — which burials were of ideas, which of implementations

Erich's question — could a better-constructed version of each rejected
arm succeed — audited against the gap decomposition and the
post-ensemble law:

**Retests justified (arms queued on the sealed config):**
- VACC2: the causal capture features were ADDED alongside the raw
  team-vacated sums they derive from — collinear pairs degrade GBMs.
  Clean design: capture features REPLACE the raw ones (DROP_FEATURES).
- VALUE2E: the ≥2-cheap-skill rule matches optimal structure exactly
  (missed booms avg $4.8k; optimal carries multiple cheap pieces) and
  its −1 verdict is pre-ensemble = stale by law.
- MPG3-conditional: infeasible only because of the 4-man stack
  mandate; if QBS1 wins, retest as a combo.

**Burials that survive the autopsy:**
- ALT_CEIL / WRBOOM: failed as OBJECTIVE TILTS (distort every build);
  the same players' correct mechanism is CANDIDATE INJECTION (q99
  wildcards — designed, September). Mechanism rejected, target alive.
- ROOKIE_WIDEN: draw-wide was wrong; narrow redesign = rookie
  punt-valuation correction only (September).
- TABMEAN: dead by construction (marginals already carry the center).
- SCRIPT: clean ensemble-era negative; refined pace design only if
  September shows a shootout-miss pattern.
- TMW17, DIRK8, PSLOPE/PSTRICT/LOWSAL: no mechanism evidence surfaced
  by any later analysis; buried on merits.

## Addendum 61 (2026-08-05): model-technique audit, GPU verification, and the eval upgrade

**GPU artifacts verified sound, not just present**: marginal cache —
100% monotone ladders, zero nulls, stable ~10-pt q90−q50 spreads, all
six seasons. Component cache — actuals-correlations IMPROVE with
context size (targets r .545→.623, the ICL signature); TabPFN's
occasional negative counts (539 rows at the smallest 2019 context,
~0 later) are neutralized by the production clips at consumption.

**Technique audit**: every model uses a defensible technique; the real
gaps are UNTRIED TabPFN placements, ranked: (1) DST projections — the
stack's weakest model (trailing means) and a pure cache-pattern
experiment; (2) ownership vs the .727 booster; (3) the licensed v2.5
upgrade (Erich accepts at priorlabs.ai → TABPFN_TOKEN → regenerate
caches → one panel). Plus the best remaining ensemble idea:
**heterogeneous members** — the K=3 ensemble is all-LGBM; a mixed
family (LGBM + CatBoost + TabPFN-mean member) adds diversity that
seed/column shuffles cannot. All September arms.

**Eval strategy upgraded** (Erich: "would a better eval find problems
easier?" — yes, proven tonight): the tails metric is outcome-only;
every mechanism discovery of the last 24h came from ad-hoc analysis.
scripts/diagnose_portfolio.py now packages that battery (capture%,
pool-hit%, assembly-vs-random-null, pair co-occurrence, QB anchoring,
generator attribution) as a one-command standing diagnosis. New eval
rule: an arm that moves tails without moving ANY diagnostic is
suspected of winning on noise; an arm that moves a diagnostic without
moving tails is a mechanism lead worth a redesign.

## Addendum 62 (2026-08-05): the selection-ordering audit — coverage is real, ranking is decorative

Erich asked whether the selection process ITSELF had been analyzed.
The ordering had not — and it fails: across 54 weeks, entry #1 (the
sim's single highest-P(>=line) pick, crowned "strongest" in the UI)
lands at the 49th percentile of our own portfolio's realized scores —
a coin flip. Spearman(selection order, realized score) = +0.086
(mildly INVERTED); 187-clearers sit at median rank 68; the 81-150
bucket has the highest realized mean. What survives: the first-40
CONTAINS the weekly best 50% vs 27% uniform — the prefix has portfolio
breadth value while its internal order is noise. Formal statement:
tail-coverage selection is validated at the PORTFOLIO level (what
panels measure); the sim cannot rank its own entries because hero
status is decided by co-boom realizations it models only
approximately. Consequences: (a) UI relabeled honestly (entries are
co-equal shots); (b) PRE-REGISTERED PREDICTION: the in-flight PEAK10
arm doubles down on the discredited p_line ranking and should return
null — if it does, the diagnostic-eval rule caught a bad lever before
its panel; (c) trimming 150->N loses breadth, not "the best ones" —
consistent with the sweet-spot curve's shape.

## Addendum 63 (2026-08-05): the stack mandate survives its first test ever — decisively

QBS1 (STACK_QB_MIN=1): 17 vs HARVEST-FINAL 25 (0+/4−). QBS1NB (also
no bring-back): 17 (0+/5−). Both loosening doses lose ~a third of the
tails. The QB+2-catchers+bring-back mandate — adopted pre-A/B-era on
winner anatomy, and challenged tonight by the hindsight-optimal
structure (avg 1.65 QB-team players) — is validated at last, and the
apparent contradiction resolves the program's closing principle:
hindsight optimals are made of INDEPENDENT booms nobody can predict;
a strategy manufactures correlated ones. WHAT WON is not HOW TO HUNT.
The assembly finding (below-random 1.87/8) stands, but its remedy is
candidate injection and assembly batches (queued), NOT loosening the
correlation skeleton — that was just tested and bled. Remaining
in-flight: VACC2, VALUE2E, then NBOOM and PEAK10 (PEAK10 carries
Addendum 62's pre-registered null prediction).

## Addendum 64 (2026-08-05): the leaderboard-pool analysis — aggregate stratum done, per-entry stratum specced

Winner-level anatomy existed (Addenda 38+); the FIELD-level stratum is
now analyzed via the ownership aggregates (54 contest-weeks x top-60
owned): splitting weeks by the field's collective chalk performance,
our best-of-150 clears 187 in 60% of chalk-BUST weeks vs 40% of
chalk-WIN weeks (corr −0.11) — the fade construction is positioned
exactly as designed, paying differentially when the crowd fails
without collapsing when it succeeds. Field top-10 chalk hits the
top-10 scoreboard only ~2.7/10 in every regime — the crowd's ceiling
blindness is persistent, and it is the edge.

**Per-entry leaderboard stratum (top-N anatomy beyond the winner):
GENUINELY September-gated** — contest_entries populates only from
Erich's standings imports (machinery built, table empty). Specced for
the first 2-3 weeks of imports: top-1% vs top-10% vs median entries on
ownership-sum, stack shape, salary left, dupe counts, punt usage —
the question being whether NEAR-winners share the winner anatomy or
the winner is an outlier of a different process (changes whether we
target the top-1% shape or the winner shape).

## Addendum 65 (2026-08-05): the per-entry leaderboard stratum — found in-repo, analyzed, and the winner IS different

Erich was right: full per-entry standings existed in the
RTS-Little-Data-Bowl clone — 74 contests from 2021, up to 408k entries
each (FLEX-6 format; behavior universals transfer, construction rules
do not). 63 large contests, 19,507 stratified entries:

| Stratum | own-sum | min-own | duped% |
|---|---|---|---|
| winner | **235** | **11.9** | **85%** |
| top 0.05% | 245 | 13.7 | 97% |
| top 1% | 251 | 14.7 | 97% |
| top 10% | 254 | 15.3 | 97% |
| median | 250 | 14.3 | 95% |

**The September question is answered early: near-winners do NOT share
the winner's anatomy — the top-1% looks like the median on ownership;
only the WINNER is contrarian and unique.** Consequences: (a) target
the winner's shape (leverage + uniqueness), not the top-1% shape —
chasing the leaderboard's average anatomy optimizes for
almost-winning; (b) this independently validates the fade + uniqueness
construction from field data at scale; (c) re-run this exact analysis
on Erich's own September imports (classic format, his fields) to
calibrate the DOSE — the 2021 FLEX data fixes the direction, not the
magnitude. Also noted for the ledger: the winner-vs-leaderboard
uniqueness gap (3-5x) is the empirical justification for max_overlap
diversity in selection that the ordering audit (Add. 62) could not
supply.

**Redesign-arm verdicts (Addendum 60's retests, on the shipping
config vs HARVEST-FINAL 25):** VACC2 (capture features REPLACING the
raw vacated sums) 21 — the collinearity redesign did not rescue it;
the causal vacated family retires with idea AND implementation both
fairly tested. VALUE2E 26 (+1, LOSO 2+/1−) — inside the noise band,
fails the bar honestly; the cheap-skill mechanism is already carried
by the punt rule. Remaining in flight: NBOOM, PEAK10 (pre-registered
null), GREEN (the branch architecture comparison).

**Assembly-arm verdicts:** NBOOM (boom solves 40→100) 25 vs 25 —
exact null; the 40 saturate. PEAK10 21 vs 25 (0+/3−) — Addendum 62's
PRE-REGISTERED prediction confirmed and exceeded: reserving slots for
p_line-ranked picks costs breadth for a ranking that carries no
realized signal. The diagnostic-eval rule's first full catch:
designed on a discredited signal → predicted null → delivered
negative. Combined with the stack-mandate validation, the assembly
gap's remedy is now narrowed to ONE untested mechanism: the
architecture itself (GREEN, running last).

## Addendum 66 (2026-08-05): GREEN — the alternate architecture reaches parity on its first attempt

The greenfield-v1 branch (per-world argmax primary generator +
beat-the-Gumbel-extended-field-bar selection, sharing the validated
worlds engine): **27 vs HARVEST-FINAL's 25** — but +2 inside the noise
band, LOSO 2+/2−, and the incumbent keeps the better mean (179.7 vs
178.7), median (14.1 vs 14.6), and the only ≥237 week. NOT adopted.
The finding is nonetheless the day's most forward-looking: a v1
architecture reached PARITY with the 66-addenda incumbent in one
attempt, with none of its refinements. The branch survives as the
September iteration vehicle; its v2 backlog (from the greenfield doc,
not yet in v1): the field bar from REAL imported standings instead of
the sampled naive field; dupe-aware bar margins; hybrid generation
(world-argmax + the incumbent's diversity batch feeding ONE selection);
and the diagnostic battery run on its exports to see whether its
assembly overlap beats the incumbent's 1.87 — if it does, the
architecture wins on mechanism even at score parity, and iteration is
justified by the eval rule.

**THE LEDGER CLOSES HERE.** Final state: six adoptions (EW, PUNT_BOOM,
QF, SCHED, TabPFN marginals, MODEL_ENSEMBLE=3), baseline 25/107 sealed
and deployed, twelve challengers repelled on the final day, one
alternate architecture at parity on a branch, and every question that
can be answered without September data — answered.

## Addendum 67 (2026-08-05): the no-settling sweep — three "September" items tested tonight instead

Erich refused to settle; three deferred items got built and tested:
1. **Late-swap score alpha: NULL, measured honestly.** The unconstrained
   tease (+24 mean-best) was pure legality inflation; position-legal,
   salary-feasible q90-chasing nets +0.9 with flat P(187). The perfect-
   swap upper bound (+69, 100% of weeks ≥187) is hindsight-only —
   individuals remain unpredictable. What SURVIVES for September:
   late-swap's leverage/uniqueness value (post-lock ownership is
   REVEALED information the fade could exploit) — unmeasurable by
   score-capture pre-season, same epistemic class as the showdown
   fade. The churn-min pipeline already preserves the optionality.
2. **Q99_WILD** (ceiling-wildcard injection — the untested assembly
   mechanism; gsis plumbed after a vacuity near-miss): arm running.
3. **MODEL_ENSEMBLE_MIX** (heterogeneous third member, sklearn HistGB,
   replay-only until registry support): arm running.


## The four relevant source files


===== FILE: src/nfl_dfs/backtest/field.py =====
```python
"""Field simulation (guide §10 step 5): approximate the opposing field with
ownership-weighted random lineups from the player pool.

Without real ownership, use the naive model — ownership correlates strongly
with value (proj/salary) and salary rank; a regression trained on scraped
post-hoc ownership slots in behind the same interface later.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

ROSTER = (("QB", 1), ("RB", 2), ("WR", 3), ("TE", 1), ("FLEX", 1), ("DST", 1))
SALARY_CAP = 50_000


def naive_ownership(players: pd.DataFrame) -> np.ndarray:
    """Ownership proxy from value and salary within position. Returns
    weights normalized to sum to 1 within each position group."""
    df = players.copy()
    value = df["proj"] / (df["salary"] / 1000.0)
    # Softmax on standardized value; salary as mild popularity boost
    weights = np.zeros(len(df))
    for _pos, idx in df.groupby("pos").groups.items():
        loc = df.index.get_indexer(idx)
        v = value.iloc[loc]
        z = (v - v.mean()) / (v.std() + 1e-9)
        s = df["salary"].iloc[loc]
        zs = (s - s.mean()) / (s.std() + 1e-9)
        w = np.exp(1.2 * z + 0.3 * zs)
        weights[loc] = w / w.sum()
    return weights


def sharp_field(
    players: pd.DataFrame,
    n_lineups: int,
    n_distinct: int = 20,
    noise: float = 0.08,
    seed: int | None = 42,
) -> list[np.ndarray]:
    """Optimizer-built entrants: the slice of a real field that runs an
    optimizer over its own (imperfect) projections. Each batch jitters the
    projection column and takes a handful of optimal lineups; distinct
    lineups are then duplicated up to `n_lineups`, mirroring how heavily
    sharp lineups duplicate in large contests."""
    from ..optimizer.lineup import optimize_many

    rng = np.random.default_rng(seed)
    players = players.reset_index(drop=True)
    row_of = {r["id"]: i for i, r in players.iterrows()}
    distinct: list[np.ndarray] = []
    per_batch = 5
    for _ in range(2 * (n_distinct // per_batch + 1)):
        if len(distinct) >= n_distinct:
            break
        pool = players.to_dict("records")
        for p in pool:
            p["proj"] = float(p["proj"]) * float(rng.normal(1.0, noise))
        try:
            batch = optimize_many(pool, n_lineups=per_batch)
        except Exception as exc:  # noqa: BLE001 - a flaky CBC subprocess
            # shouldn't kill a whole replay; the field falls back to fewer
            # (or zero) sharp entrants.
            import logging

            logging.getLogger(__name__).warning("sharp_field batch failed: %s", exc)
            continue
        for lu in batch:
            distinct.append(np.array([row_of[p["id"]] for p in lu.players]))
    if not distinct:  # infeasible slate; let the caller fall back
        return []
    picks = rng.integers(0, len(distinct), n_lineups)
    return [distinct[i] for i in picks]


def sample_field(
    players: pd.DataFrame,
    n_lineups: int = 10_000,
    seed: int | None = 42,
    ownership: np.ndarray | None = None,
    sharp_fraction: float = 0.0,
) -> list[np.ndarray]:
    """Generate opposing lineups by ownership-weighted sampling per slot.
    Salary is enforced loosely (retry a few times, keep the best attempt) —
    the field is approximated, not optimized; most real entrants aren't
    optimal either. `sharp_fraction` of the field is instead built by
    `sharp_field` (optimizer entrants), which is what keeps GPP payout
    tails honest. Returns arrays of positional indices into `players`."""
    rng = np.random.default_rng(seed)
    n_sharp = int(n_lineups * sharp_fraction)
    sharp = sharp_field(players, n_sharp, seed=seed) if n_sharp else []
    n_lineups = n_lineups - len(sharp)
    own = ownership if ownership is not None else naive_ownership(players)
    players = players.reset_index(drop=True)
    pos_idx = {
        pos: players.index[players["pos"] == pos].to_numpy()
        for pos in ("QB", "RB", "WR", "TE", "DST")
    }
    flex_idx = players.index[players["pos"].isin(["RB", "WR", "TE"])].to_numpy()
    pos_weights = {
        pos: own[idx] / own[idx].sum() for pos, idx in pos_idx.items() if len(idx)
    }
    flex_w = own[flex_idx] / own[flex_idx].sum()
    salaries = players["salary"].to_numpy()

    field: list[np.ndarray] = []
    for _ in range(n_lineups):
        best: np.ndarray | None = None
        for _attempt in range(6):
            picks: list[int] = []
            ok = True
            for pos, n in ROSTER:
                if pos == "FLEX":
                    cand, w = flex_idx, flex_w
                else:
                    cand, w = pos_idx.get(pos, np.array([])), pos_weights.get(pos)
                    if cand is None or len(cand) < n:
                        ok = False
                        break
                avail = ~np.isin(cand, picks)
                if avail.sum() < n:
                    ok = False
                    break
                w_avail = w[avail] / w[avail].sum()
                chosen = rng.choice(cand[avail], size=n, replace=False, p=w_avail)
                picks.extend(chosen.tolist())
            if not ok:
                continue
            arr = np.array(picks)
            if salaries[arr].sum() <= SALARY_CAP:
                best = arr
                break
            if best is None:
                best = arr
        if best is not None:
            field.append(best)
    return sharp + field


def field_scores(field: list[np.ndarray], actual_points: np.ndarray) -> np.ndarray:
    """Actual DK points for each field lineup."""
    return np.array([actual_points[lu].sum() for lu in field])

```

===== FILE: src/nfl_dfs/backtest/payout.py =====
```python
"""Contest payout curves. ROI is the only metric that pays (guide §10):
a model with worse RMSE can have better ROI if its ceilings are calibrated.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class Contest:
    name: str
    entry_fee: float
    field_size: int
    # (top_fraction_of_field, multiple_of_entry_fee) tiers, best first.
    tiers: tuple[tuple[float, float], ...]

    def payout_for_rank(self, rank: int) -> float:
        """rank is 1-based; returns dollars won."""
        frac = rank / self.field_size
        cum = 0.0
        for top_frac, mult in self.tiers:
            cum += top_frac
            if frac <= cum + 1e-12:
                return self.entry_fee * mult
        return 0.0


def double_up(entry_fee: float = 5.0, field_size: int = 10_000) -> Contest:
    """Cash game: top ~45% roughly doubles (rake-adjusted)."""
    return Contest("double-up", entry_fee, field_size, ((0.45, 2.0),))


def gpp(entry_fee: float = 5.0, field_size: int = 100_000) -> Contest:
    """Stylized winner-take-most tournament curve, ~15% of field paid,
    ~85% of the prize pool concentrated up top."""
    return Contest(
        "gpp",
        entry_fee,
        field_size,
        (
            (0.00001, 20000.0),   # 1st
            (0.00009, 2000.0),
            (0.0009, 200.0),
            (0.009, 20.0),
            (0.04, 5.0),
            (0.10, 2.0),
        ),
    )


def roi(winnings: np.ndarray, entry_fee: float) -> float:
    """Aggregate return on investment across entries."""
    w = np.asarray(winnings, dtype=float)
    staked = entry_fee * len(w)
    return float((w.sum() - staked) / staked) if staked else 0.0

```

===== FILE: src/nfl_dfs/models/entries_curve.py =====
```python
"""The measured entries sweet-spot curve (2026-08-04, Addendum 53):
P(best-of-N >= line) from the 3-season 150-entry study (54 week-slates,
reports/entries_study/). Powers the contest comparator.

p_reach interpolates in N (log-spaced between measured points) and in
the line dimension (log-linear through the three measured anchors —
capped extrapolation, honest about its range).
"""
from __future__ import annotations

import math

ANCHOR_LINES = (187.0, 194.0, 199.0)
# N: (P>=187, P>=194, P>=199)
CURVE: dict[int, tuple[float, float, float]] = {
    1: (0.019, 0.001, 0.001), 2: (0.037, 0.019, 0.019),
    3: (0.056, 0.019, 0.019), 5: (0.074, 0.019, 0.019),
    8: (0.111, 0.037, 0.037), 10: (0.167, 0.056, 0.037),
    15: (0.204, 0.074, 0.056), 20: (0.204, 0.093, 0.056),
    25: (0.241, 0.130, 0.074), 30: (0.259, 0.130, 0.074),
    40: (0.315, 0.130, 0.074), 50: (0.333, 0.130, 0.074),
    75: (0.407, 0.222, 0.111), 100: (0.426, 0.241, 0.148),
    150: (0.444, 0.259, 0.148),
}
_NS = sorted(CURVE)


def _interp_n(n: int, k: int) -> float:
    n = max(1, min(int(n), 150))
    if n in CURVE:
        return CURVE[n][k]
    lo = max(x for x in _NS if x < n)
    hi = min(x for x in _NS if x > n)
    f = (math.log(n) - math.log(lo)) / (math.log(hi) - math.log(lo))
    return CURVE[lo][k] + f * (CURVE[hi][k] - CURVE[lo][k])


def p_reach(n_entries: int, line: float) -> float:
    """P(best of first n_entries >= line), interpolated from the study.
    Lines outside ~180-210 are capped extrapolations — treat as rough."""
    ps = [max(_interp_n(n_entries, k), 1e-4) for k in range(3)]
    xs = ANCHOR_LINES
    line = float(line)
    if line <= xs[0]:
        # extrapolate below 187 on the 187-194 slope, capped
        slope = (math.log(ps[1]) - math.log(ps[0])) / (xs[1] - xs[0])
        return float(min(math.exp(math.log(ps[0]) + slope * (line - xs[0])),
                         0.95))
    if line >= xs[2]:
        slope = (math.log(ps[2]) - math.log(ps[1])) / (xs[2] - xs[1])
        return float(max(math.exp(math.log(ps[2]) + slope * (line - xs[2])),
                         1e-5))
    if line <= xs[1]:
        f = (line - xs[0]) / (xs[1] - xs[0])
        return float(math.exp(math.log(ps[0]) + f * (math.log(ps[1]) - math.log(ps[0]))))
    f = (line - xs[1]) / (xs[2] - xs[1])
    return float(math.exp(math.log(ps[1]) + f * (math.log(ps[2]) - math.log(ps[1]))))

```

===== FILE: (branch) src/nfl_dfs/backtest/greenfield.py =====
```python
"""Greenfield construction (branch experiment, 2026-08-05): the
alternate architecture from reports/greenfield-redesign.md, sharing
the validated worlds engine (slate + correlated draws) and differing
ONLY in construction:

1. PRIMARY generator = per-world argmax ("if the slate resolves like
   world k, the best lineup is..."), not a mean-objective batch with
   boom solves bolted on. Attribution basis: boom solves were 13% of
   candidates and 54% of weekly bests.
2. Selection objective = BEAT THE FIELD'S MAX per world, not clear a
   fixed line. The bar is world-correlated (chalk worlds raise it),
   and uniqueness emerges naturally: a candidate that mirrors the
   field's chalk TIES the field max in its boom worlds — it never
   beats it. (Leaderboard stratum, Addendum 65: only the winner is
   unique; near-winners are chalk-shaped.)

Env GREENFIELD=1 routes tail_select_lineups here. Same pool, same
draws, same stack/punt/salary skeleton (all panel-validated).
"""
from __future__ import annotations

import logging
import os

import numpy as np

from ..optimizer.lineup import StackRules, optimize
from . import field as field_sim

log = logging.getLogger(__name__)

FIELD_SAMPLE = 1500


def greenfield_select(slate, pool, rd, tail_line, n_entries, stack,
                      objective_col, locks=None, theses=None):
    """Alternate construction. rd = per-row draw matrix (rows align with
    pool order). Returns list[Lineup]."""
    locks = set(locks or ())
    n_rows, n_sims = rd.shape

    # --- field bar per world: sampled field maxima, Gumbel-extended to
    # the true field size (150k default; env GREENFIELD_FIELD).
    own_vec = None
    fld = field_sim.sample_field(slate, n_lineups=FIELD_SAMPLE, seed=42,
                                 ownership=own_vec, sharp_fraction=0.15)
    F = np.stack([rd[list(f)].sum(axis=0) for f in fld])  # (field, sims)
    field_n = int(os.environ.get("GREENFIELD_FIELD", "150000") or 150000)
    mu, sd = F.mean(axis=0), F.std(axis=0) + 1e-6
    ext = (np.sqrt(2 * np.log(field_n)) - np.sqrt(2 * np.log(FIELD_SAMPLE)))
    bar = F.max(axis=0) + sd * ext  # per-world winning bar

    # --- primary generator: per-world argmax lineups on the boomiest
    # worlds (by field bar height AND by total pool output, mixed).
    n_cand = max(4 * n_entries, 160)
    order_hot = np.argsort(rd.sum(axis=0))[::-1]
    worlds = list(order_hot[:n_cand])
    cands, seen = [], set()
    for k in worlds:
        sim_pool = [{**p, "proj_gf": float(rd[i, k])}
                    for i, p in enumerate(pool)]
        try:
            lu = optimize(sim_pool, stack=stack, objective_col="proj_gf",
                          locks=set(locks), max_overlap=8)
        except Exception:
            continue
        if lu is None or lu.ids in seen:
            continue
        seen.add(lu.ids)
        lu.tag = "world"
        cands.append(lu)
    if not cands:
        return []

    id_ix = {p["id"]: i for i, p in enumerate(pool)}
    totals = np.stack([
        rd[[id_ix[p["id"]] for p in lu.players]].sum(axis=0)
        for lu in cands])

    # --- selection: greedy max-coverage of BEAT-THE-BAR indicators.
    wins = totals > bar[None, :]
    picked: list[int] = []
    covered = np.zeros(n_sims, dtype=bool)
    for _ in range(min(n_entries, len(cands))):
        marg = (wins & ~covered[None, :]).sum(axis=1)
        marg[picked] = -1
        j = int(np.argmax(marg))
        if marg[j] <= 0:
            # coverage exhausted: fill by highest raw win count unpicked
            rest = [i for i in np.argsort(wins.sum(axis=1))[::-1]
                    if i not in picked]
            picked.extend(rest[:n_entries - len(picked)])
            break
        picked.append(j)
        covered |= wins[j]
    picked = picked[:n_entries]
    log.info("greenfield: %d world-candidates, %d picked, "
             "P(beat field bar) portfolio=%.3f",
             len(cands), len(picked),
             float(wins[picked].any(axis=0).mean()))
    return [cands[i] for i in picked]

```

