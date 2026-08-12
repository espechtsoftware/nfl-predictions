# Deep analysis: dispersion calibration, feature inventory, and why features keep failing

Date: 2026-08-11. Requested scope: audit what has been done, inventory the data
points actually in use, verify the useful ones are used, research what is
possible, and propose how to make this more effective.

**No code was changed.** Findings 1–3 are code/artifact audits with no outcome
selection. Findings 4–5 use warehouse data; where realized outcomes were
queried it is marked.

---

## Read this first

For the agent continuing this work.

**Verify Finding 1 yourself before reading further — it takes ten seconds:**

```bash
grep -rn "fit_widen_factors" src/          # expect: definition only, zero call sites
grep -n "DEFAULT_WIDEN" src/nfl_dfs/models/calibration.py
grep -n "SIM_WIDEN_DRAWS" src/nfl_dfs/inference/production_policy.py
```

If that shows a per-position widen constant fit on 2019+2021, a refit function
that is never called, and `SIM_WIDEN_DRAWS: "fitted"` live in the production
policy, then the tail dispersion of the submitted-lineup path has been frozen
across seven material simulator changes, and Findings 2 and 3 follow from it.

**Do these in order. Neither is an arm; neither needs a lineup panel.**

1. **R1 — run `fit_widen_factors` on the current served path.** Dead code the
   module's own docstring says to run "whenever the simulator changes
   materially." It either closes Findings 1–3 cheaply or invalidates the
   dispersion of everything downstream.
2. **R2 — per-position recalibration.** Served q99 exceedance is WR 1.88% /
   RB 1.57% / TE 0.74% against 1% nominal. Stage A's single global 1.025 scalar
   cannot widen WR and narrow TE simultaneously, so Stage B's null does not
   establish what it was read to establish.

**Then R3** — rerun one feature comparison with each arm independently
recalibrated. This is a new question ("does the feature help once both arms are
correctly calibrated?"), not a re-read of a closed arm.

**Do not act on the "stop" recommendation** in
`2026-08-11-recommendation-scoreboard-and-pivot.md` §4.3 until R1 and R2
resolve. Stopping is a reasonable answer to "we tested everything properly and
found nothing"; it is the wrong answer to "we never refit the parameter our own
code says to refit."

### Supersession

| File | Relationship to this one |
|---|---|
| `2026-08-11-recommendation-scoreboard-and-pivot.md` | §4.1 allocation-untested claim **retracted** here (Finding 4); §4.3 "stop" ranking **deferred**; §8.1 co-exceedance diagnostic **demoted below R1/R2** |
| `2026-08-11-post-window-program-review.md` | gate-power critique stands; §4.2 tail-magnitude claim already superseded |
| `2026-08-11-fantasy-points-data-utilization.md` | inventory stands; Defense PROE redundancy claim retracted |
| `2026-08-10-scoring-strategy-recommendations.md` | §3.1 field/payout item stands unchanged (R6) |

All five outside-review files are **untracked** in git.

---

## Executive summary

Five findings, in order of importance. The first three are connected and I
believe they explain the pattern the operator is reacting to — that a large
amount of well-run work has produced almost no scoring improvement.

1. **The simulator's dispersion calibration is frozen at values fit on the
   2019+2021 replays of a long-obsolete simulator, and the function that refits
   them is dead code.** `DEFAULT_WIDEN = {QB 1.5, RB 1.45, TE 1.05, WR 1.1}`;
   `fit_widen_factors()` is defined and never called anywhere in `src/`.
2. **The served upper tail is badly imbalanced by position** — q99 exceedance
   WR 1.88%, RB 1.57%, TE 0.74% against 1% nominal. The aggregate 1.48% hides
   it, and the single global 1.025 factor tested in Stage A structurally could
   not fix it.
3. **Every control-versus-treatment feature comparison is confounded by (1).**
   A feature that improves mean accuracy narrows the model's raw band; the
   widen multiplier is a constant, so the served band narrows too and the tail
   gate penalises the feature for a calibration artifact. This is directly
   visible in the route-component run.
4. **The Dirichlet allocation concentration was never fitted.** The empirical
   value implied by real target allocation is α₀ ≈ 29; the two tested values
   were 20 and 8, both more dispersed, and the production default is the
   K→∞ limit of the same one-parameter family. The data-consistent region was
   never tested.
5. **19 features are materialized in the feature tables and unused by the
   model**, including `xfp_l4`, `vacated_capture_tgt/car` and
   `team_top2_target_share_l6`.

---

## CORRECTION (2026-08-11, post-code-audit) — Findings 1 and 3 are wrong as stated

The repository's code audit found that `DEFAULT_WIDEN` cannot explain the
served-tail imbalance, and it is right. Verified independently:

- `_widen_draws` is `mu + (draws - mu) * w` with **no clipping** — strictly
  monotone in `draws`, so within-row ranks are preserved exactly and no ties
  are created at zero.
- `apply_draw_shape` orders the operations widen → `_tabpfn_marginals`.
- `_tabpfn_marginals` **rank-remaps each player's draws onto that player's
  cached TabPFN quantiles**. Because widening preserved ranks, the output is
  bit-identical for any positive `w`.

So for TabPFN-covered rows the widen scale is algebraically cancelled.
`TABPFN_MARGINALS=1` and coverage was 100% of the 13,876 held-out rows.
**Finding 1's claim that stale widen constants explain the served imbalance is
withdrawn, and Finding 3's confound mechanism does not operate through this
path.** The constants are operationally dead code on covered rows, which is a
hygiene issue, not the cause.

Three things survive and one becomes sharper:

1. `fit_widen_factors` is still dead code and `DEFAULT_WIDEN` is still stale —
   but it now matters only where it is **not** erased (below).
2. **The served marginal for covered rows is entirely TabPFN's.** Therefore the
   per-position imbalance in Finding 2 is a **TabPFN quantile-calibration
   defect**, not a simulator or widen defect. This is a sharper diagnosis and a
   much cheaper one to test — see R1′.
3. Finding 2's per-position numbers, and the operator's plan to freeze a valid
   per-position **final-served** recalibration, are unaffected. That is the
   right instrument and it acts after shaping, where nothing erases it.
4. Finding 3's *observation* stands even though its mechanism was wrong: the
   route treatment's exceedance rose at all three levels while its MAE and CRPS
   improved. That still needs an explanation; it is now a question about the
   TabPFN/blend layers rather than about widen.

The remainder of Finding 1 is retained below for the dead-code and
`fit_widen_factors` record, with its causal claim withdrawn.

### Where `DEFAULT_WIDEN` is still live

It is erased only where TabPFN coverage exists. It still applies to:

- **`summary` quantiles** — `apply_widen` at `replay.py:146` and
  `run_projections.py:124`. These populate `proj_p10/p50/p90/proj_std`, i.e.
  the UI values and the `slate_player_features.proj_p90` column.
- **Rows with no TabPFN cache**, which fall back to `_empirical_marginals`.
  That path affine-matches to our `(mean, std)`, and `proj_std` carries the
  widen factor — so widen **does** survive there.

The second case is an operational risk rather than a historical one: the
TabPFN cache is regenerated weekly by a GPU job, and a miss silently falls back
to a path where a stale 2019/2021-fit constant governs the tail. **The system's
dispersion behaviour changes exactly when the cache fails.** That should be
alarmed on for 2026 rather than left as a silent fallback.

---

## Finding 1 — the dispersion calibration is stale and its refit is dead code

*(Causal claim withdrawn — see the correction above. Retained for the
dead-code record.)*

`src/nfl_dfs/models/calibration.py`:

```python
DEFAULT_WIDEN = {"QB": 1.5, "RB": 1.45, "TE": 1.05, "WR": 1.1}
```

Its own docstring states the provenance and the maintenance rule:

> "DEFAULT_WIDEN was fit on pooled 2019+2021 replays … **Refit with
> `fit_widen_factors` whenever the simulator changes materially.**"

Verification:

- `production_policy.py` sets `SIM_WIDEN_DRAWS: "fitted"`, so these constants
  are live in the submitted-lineup path.
- `replay.py:146` and `run_projections.py:124` both call `apply_widen`.
- **`fit_widen_factors` has zero call sites in `src/`.** It has never been run
  in the pipeline.

Since those factors were fit, the simulator has changed materially at least
seven times: possession-drive simulation adopted, per-team game factors,
TabPFN marginals, empirical marginal shaping, `MODEL_ENSEMBLE` 3→1, the 45/55
prop-market blend, and CE/role candidate generation. The docstring's own
precondition for refitting has been met repeatedly and the refit never ran.

This is not a subtle bug. It is a maintenance instruction written by the
original author, never executed, on the single parameter that controls how fat
the tails are in a system whose entire objective is tail outcomes.

---

## Finding 2 — the served tail is imbalanced by position, and the one fix that ran could not address it

The served-tail diagnostic (`served-tail-calibration-6fk9k`) reported, as
mandatory descriptive diagnostics:

| position | served q99 exceedance | nominal | ratio |
|---|---:|---:|---:|
| **WR** | **1.8806%** | 1% | **1.88× too thin** |
| RB | 1.5653% | 1% | 1.57× too thin |
| TE | 0.7368% | 1% | 0.74× too **fat** |
| aggregate | 1.4774% | 1% | 1.48× |

The protocol correctly labelled these descriptive and forbade using them to
select position-specific corrections *within that frozen arm*. That was the
right call for that arm. But it means the finding is sitting unexploited, and a
separately preregistered per-position arm is entirely legitimate.

The consequence for Stage B is direct. Stage A selected **one global scalar**,
1.025. A single multiplier cannot simultaneously widen WR (needs a lot) and
narrow TE (needs the opposite). Applying +2.5% uniformly moved every position
in the same direction, over-correcting TE while barely touching WR's 1.88×
deficit. **Stage B's null is therefore not evidence that tail dispersion is
irrelevant to lineup scores — it is evidence that a global scalar is the wrong
instrument.**

Note also the alignment with the standing missed-winner audit: of 36 omitted
Millionaire-winner slots, **WR 12 and TE 11** of 36 — the two positions whose
calibration is furthest from nominal, in opposite directions. WR's band is too
thin to generate its winners; TE's is too fat, which wastes candidate budget on
TE outcomes that do not occur.

And the original factors show the same shape as the defect: WR was assigned the
second-*smallest* widen factor (1.1) of the four positions, while QB got 1.5.
Whatever was true of the 2019/2021 simulator, WR is now the position most
starved of upper-tail mass.

---

## Finding 3 — the feature-comparison design is confounded

This is the finding that reframes the last several weeks of work.

The mechanism:

1. A feature that improves mean accuracy reduces the component models' residual
   spread, so the raw `proj_p10/p50/p90` band narrows.
2. `apply_widen` stretches that band by a **fixed** per-position multiplier.
3. Nothing refits the multiplier for the treatment arm.
4. The treatment therefore serves a band that is narrower *relative to its own
   residuals* than the control's.
5. The tail gate — 30-point Brier, q99 pinball, exceedance — penalises it.

**This is directly observable in the route-component run.** Its mandatory
diagnostics recorded:

| | q90 | q95 | q99 |
|---|---:|---:|---:|
| control exceedance | 11.11% | 7.10% | 2.69% |
| route treatment | 12.04% | 7.57% | 3.04% |

Exceedance *rose* in the treatment at all three levels — the treatment's band
was relatively **more** under-dispersed than the control's. Meanwhile composed
DK-point MAE improved in every fold (3.7879 → 3.7315) and CRPS improved in
every fold (2.5795 → 2.5687).

That is the signature described above: the mean got better, the band did not
follow, and the tail metric recorded a failure. The protocol froze "identical
simulation configuration" between arms — which is correct for isolating the
feature, but it also freezes the *mis*-calibration, and the arms do not need
equal calibration error to be comparable, they need each to be correctly
calibrated to its own residuals.

The same explanation fits the wider historical pattern:

| arm | accuracy evidence | lineup/tail result |
|---|---|---|
| Route Share components | MAE and CRPS better in every fold | tail gate failed |
| Fast-role features | +2.19 DK pts vs matched controls, positive in all 6 seasons | 11/107 vs 17/107 — rejected |
| `depth_rank_delta` | plausible, neutral in noise | −4.6 mean best |
| `team_ol_out` | plausible mechanism | −8.7 mean best |

Four independent cases of "the signal is real, the lineups got worse." A shared
mechanical cause is a better explanation than four unrelated coincidences.

**What this does and does not mean.** It does not retroactively pass any closed
arm, and no closed arm should be re-read. It means the *comparison design* has a
defect, which licenses a new, properly-designed arm: **control and treatment
each independently refit to nominal coverage before the tail comparison.** That
is a different experiment, not a retry.

---

## Finding 4 — the Dirichlet concentration was never fitted, and both tests were on the same side of the data

The pivot reconciliation is right that within-team Dirichlet allocation exists
and was tested; my §4.1 claim that it was untested was wrong. But the detail
matters.

`game_sim.allocate_drive_usage` sets `α_i = share_i × K` with a single global
`K = DIRICHLET_K` (default 20). Two values were ever tested:

- **K=20** (Addendum 26, 2025 only, 17 slates): 177.3 mean-best / 3-of-17 vs
  control 188.4 / 7-of-17.
- **K=8** (Addendum 42): 11 tails / mean 175.0 — worse still.

I estimated the empirical concentration from real target allocation:
2019–2025, team-weeks with ≥15 targets, realized share versus the strictly
prior `target_share_l4`, with multinomial sampling noise removed
(`α₀ = p(1−p)/Var_dirichlet − 1`):

| expected-share band | n | p | Var total | multinomial | Var Dirichlet | implied α₀ |
|---|---:|---:|---:|---:|---:|---:|
| 2–8% | 13,160 | 0.048 | 0.00297 | 0.00143 | 0.00154 | 28.8 |
| 8–14% | 7,670 | 0.100 | 0.00561 | 0.00277 | 0.00284 | 30.6 |
| 14–20% | 4,965 | 0.150 | 0.00832 | 0.00393 | 0.00440 | 28.0 |
| 20–26% | 3,070 | 0.200 | 0.01008 | 0.00496 | 0.00513 | 30.2 |
| 26%+ | 1,899 | 0.240 | 0.01281 | 0.00563 | 0.00718 | 24.4 |

**Row-weighted implied α₀ ≈ 29**, and remarkably stable across bands. This is a
*lower bound*: the `_l4` prior carries its own estimation error, which inflates
the measured variance and depresses α₀. The model's fitted shares are better
than `_l4`, so the model-relevant concentration is higher still.

Translating to a 20%-share receiver:

| K | Dirichlet SD of his share | 1 SD range |
|---:|---:|---|
| 8 (tested) | 13.3 pp | 6.7% – 33.3% |
| 20 (tested) | 8.7 pp | 11.3% – 28.7% |
| **29 (empirical)** | **7.3 pp** | 12.7% – 27.3% |
| 40 | 6.3 pp | 13.8% – 26.2% |
| ∞ | 0 pp | = production default |

Three consequences:

- **The production default is the K→∞ limit of the same family.** With
  `GAME_SIM_USAGE` unset, `opp_draw` returns `rng.poisson(base × game_mult)` —
  no reallocation. So the tested points are 8 and 20; the default is ∞; and the
  data says 29. **The entire data-consistent region, 29 to ∞, is untested.**
- **Both tests moved in the over-dispersion direction and both got worse,
  monotonically.** That is exactly the signature of an optimum on the other
  side.
- **The ledger's inference does not follow.** Addendum 42 concludes "the
  K=20-null verdict was about the MODE being neutral, not about K being
  mis-tuned." Two points on the same side of the data-implied value cannot
  establish that the mode is neutral; they establish that the tested direction
  is wrong.

Critically for protocol: **fitting K from observed usage dispersion is not
tuning on lineup outcomes.** The target quantity is a usage-allocation
statistic from a different table. It can be frozen before any lineup test. The
reconciliation's rule — do not tune another concentration on the known outcomes
— is correct and is fully respected by a data-fitted K.

---

## Finding 5 — materialized-but-unused features

`featureset.py` has 35 active `NUMERIC_FEATURES` and **19
`CANDIDATE_FEATURES` that are computed, stored in the feature tables, and never
seen by the model** unless `EXTRA_FEATURES` names them:

| candidate feature | status |
|---|---|
| `target_share_last`, `carry_share_last`, `snap_share_last` | tested as the six-field fast-role bundle → rejected |
| `target_share_jump`, `carry_share_jump`, `snap_share_jump` | same bundle |
| `fp_route_share_last/_l4/_jump/_cross_season` | component arm closed; 2026 shadow pending |
| `pace_env_l6`, `opp_blitz_rate_l6`, `qb_time_to_throw_l6`, `pa_rate_l6`, `opp_pressure_rate_l6` | **never individually tested in a tracked arm** |
| `team_top2_target_share_l6` | **never tested** — and it is the direct measure of the allocation concentration in Finding 4 |
| `xfp_l4` | **never tested** — expected FP from opportunity alone |
| `vacated_capture_tgt`, `vacated_capture_car` | **never tested** — vacated opportunity × empirical capture rate |

The last three groups matter. `xfp_l4` and the `vacated_capture_*` pair are
opportunity-based rather than production-based, which is the class of feature
that external research consistently finds most stable (expected YPRR y/y ≈0.67
versus realized ≈0.51). `team_top2_target_share_l6` is a per-team concentration
measure — literally the quantity Finding 4 says should parameterize allocation.

I am **not** recommending a feature sweep. Finding 3 says any such sweep is
confounded until the calibration design is fixed. I am recording that the
"we have tested this data thoroughly" conclusion is overstated: the vendor data
has been tested thoroughly; several free, already-materialized features have
not been tested at all.

---

## Data inventory verification

Requested check: are the useful data points actually used?

| source | in warehouse | in model | assessment |
|---|---|---|---|
| nflverse PBP usage/shares | yes | yes (10 usage features) | correctly used |
| NGS separation, CPOE, time-to-throw | yes | `separation_l4`, `qb_cpoe_l6` active; `qb_time_to_throw_l6` candidate-only | partially used |
| FTN charting (blitz, PA, pressure) | yes | **all three candidate-only** | materialized, unused |
| PFR CB/DB coverage allowed | yes | yes (4 features) | correctly used |
| Odds/market | yes | `implied_team_total`, `spread`, `game_total`, plus 45/55 prop blend | correctly used |
| Schedule/rest/body clock | yes | yes | correctly used, panel-proven |
| Weather / dome | yes | `is_dome` only | wind/precip materialized but unused |
| Fantasy Points route share (weekly) | yes | candidate-only, arm closed | tested; 2026 shadow pending |
| Fantasy Points advanced/coverage (season) | yes | no | 4 arms, all closed |
| Contest ownership 2022–25 | yes | ownership model only, not lineup path | **unexploited** — see the strategy review's field-model item |
| Full contest standings/payouts | **no** | no | the standing top-priority gap |

The genuinely unexploited assets are not the paid vendor tables. They are:
FTN charting features, `xfp_l4`/`vacated_capture_*`, and the 2022–25 contest
ownership archive.

---

## Recommendations

Ordered by expected value per unit of cost, and all of them are cheaper than
another vendor family.

### R1′ — Decompose the served imbalance by stage. Zero compute; do this first.

Supersedes R1 after the correction. The served exceedance is measured at the
end of a three-stage pipeline, and each stage is separately checkable. Only the
last one has been measured.

| stage | what to compare | cost |
|---|---|---|
| 1. TabPFN cache | `features.tabpfn_projections` q90/q95/q99 vs realized actuals, **per position** | **pure SQL, no simulation** |
| 2. post-shaping, pre-blend | shaped draws vs actuals, per position | one execution |
| 3. served (post-blend) | already measured: WR 1.88 / RB 1.57 / TE 0.74 | done |

If stage 1 already shows WR at ~1.9× nominal, the defect is in the cached
TabPFN quantiles and belongs upstream — in the weekly `tabpfn-gen` job's own
acceptance check. If stage 1 is clean and stage 3 is not, the **45/55 market
blend** introduced it, which is a different and more interesting problem: a
mean shift that is not accompanied by a spread re-fit.

This also explains how the defect survived adoption. TabPFN was accepted on
**q90 coverage in aggregate** (Addendum 43: 0.908 vs LGB 0.870). A q90-aggregate
check cannot see a q99 per-position defect. Per-position q95/q99 exceedance
should become a standing acceptance check on every weekly TabPFN regeneration.

### R2′ — Per-position final-served recalibration: three design notes

The operator's frozen plan is the right instrument. Three specifics that the
current code will otherwise constrain:

1. **The bound must allow narrowing.** `apply_served_tail_scale` enforces
   `1.0 <= factor <= 1.25` and explicitly refuses position-specific doses. TE at
   0.74% is too **wide**; under a ≥1.0 bound TE can only stay at identity and
   half the imbalance is unfixable. The per-position version needs roughly
   `[0.85, 1.25]`, still mean-invariant.
2. **Consider a WR-only first arm.** WR is unambiguously the largest defect
   (1.88×), occupies the most roster slots (3 + frequent FLEX), and has no
   directional ambiguity. A WR-only widening has fewer moving parts than a full
   four-position refit and a cleaner predicted sign.
3. **Preregister the TE tension.** TE is 11 of the 36 omitted Millionaire-winner
   slots. Narrowing TE improves calibration but reduces simulated TE ceilings
   and may cost TE-driven winners. Report Stage B outcomes **per position**, not
   only in aggregate, so a net-neutral result can be decomposed rather than
   read as another null.
4. **Measure QB even if you do not correct it.** The served diagnostic reported
   only RB/WR/TE, and `apply_served_tail_scale` masks QB out. But QB is the hub
   of the co-boom structure (QB boom → 2.34× WR / 2.50× TE teammate lift). A
   mis-calibrated QB tail propagates through every stack.

### R1 (superseded) — Refit the widen factors. Run `fit_widen_factors`.

This is a one-execution diagnostic against dead code that the module's own
docstring says should have been run seven simulator changes ago. Fit
per-position factors on the current served path, walk-forward, and report the
resulting exceedance grid against the current 10.58/5.46/1.48 aggregate and the
1.88/1.57/0.74 positional split.

This is not an arm and needs no lineup panel. It either shows the factors are
still right (closing Findings 1–3 cheaply) or shows they are materially wrong,
in which case everything downstream is affected.

### R2 — Per-position tail recalibration, replacing the global scalar

Stage A/B tested one global factor because that is what was frozen. The
positional split says a global factor is the wrong instrument. Preregister a
per-position calibration targeting nominal q90/q95/q99 exceedance in each of
QB/RB/WR/TE, fit walk-forward on early seasons exactly as Stage A did, with
mean-invariance enforced, then one Stage B replay.

Prediction, stated in advance so it is falsifiable: WR needs materially more
widening than its current 1.1 and TE needs less than its current 1.05, and the
resulting book gains at 210+ where the global 1.025 tied.

### R3 — Rerun one feature comparison with per-arm recalibration

Finding 3 says the feature-comparison design is confounded. Fix the design and
re-ask the question once, on the strongest candidate: route share, which
already demonstrated better MAE and CRPS in every fold.

Design: control and treatment each independently refit their widen factors to
nominal coverage on training seasons, *then* compare tail metrics. Everything
else — seeds, folds, features, models — exactly as the closed protocol. This
is a new experiment answering a different question ("does route share help once
both arms are correctly calibrated?"), not a re-read of the closed one.

### R4 — Fit the Dirichlet concentration from usage data, then test it once

Freeze `K` at the value implied by observed allocation dispersion — measured
against the *model's fitted shares*, not `_l4`, so the estimate is
model-relevant — with per-team shrinkage toward the league value if support
allows. Then one arm at that frozen K.

This is not a retune on lineup outcomes and must be stated as such. The tested
points were 8 and 20; the default is ∞; the data says ≥29. Expected effect is
modest — the data-fitted value may be close enough to the default that little
changes — but it is one execution and it closes a family that two mis-directed
tests left ambiguous.

### R5 — After R1–R3, test the free unused features, one small block at a time

`xfp_l4`, `vacated_capture_tgt/car`, `team_top2_target_share_l6`, and the FTN
block. These cost nothing, are already materialized, and have never been
individually tested. They should be tested only after the calibration design is
fixed, or they will fail for the same confounded reason.

### R6 — Everything already recommended about the field/payout objective stands

Unchanged from the strategy review, and unaffected by these findings. The
2022–25 ownership archive plus 2026 standings remain the path to an objective
expressed in dollars rather than score thresholds.

---

## What this changes about earlier conclusions

- **"The marginal layer is exhausted" is premature.** It was tested through a
  confounded comparison design. That does not mean the features work; it means
  we do not yet know.
- **"Stage B proves marginal widening is not the 210+ lever" is too strong.**
  What Stage B proved is that a *global scalar* widening is not the lever. The
  positional imbalance was never addressed.
- **My §4.1 allocation claim was wrong** — the mechanism exists and was tested.
  The useful residue is that it was never tested at a data-consistent
  concentration.
- **The pivot document's "stop" option should be deferred** until R1 and R2
  resolve. Stopping is a reasonable answer to "we have tested everything
  properly and found nothing." It is the wrong answer to "we have not yet
  refit the parameter our own code says to refit."

The honest summary: the failures of the last several weeks may be largely
attributable to a stale, positionally-imbalanced dispersion calibration that
sits directly between every feature experiment and the tail metric used to
judge it. That is a cheap thing to check and it should be checked before
anything else is attempted or abandoned.
