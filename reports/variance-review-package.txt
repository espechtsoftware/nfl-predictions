# Targeted external review — build-to-build variance of a small-data LightGBM stack (2026-08-04)

## The one question

This NFL DFS system trains ~11 LightGBM component models on ~30k rows
weekly, walk-forward. We have MEASURED (controlled experiments below)
that rebuilding the BigQuery feature tables — which only reorders row
tie-breaking — shifts the six-season portfolio outcome by ±5 tail weeks
out of 107 ("order luck"): identical code drew 23, 18, and 15 across
three table builds in 48 hours, while the RELATIVE gains of levers
replicated within every build. Feature columns are already canonically
sorted; replays are bit-deterministic on a fixed build.

You are reviewing ONE question: **how would you make this model stack's
output stable across data rebuilds, and is our diagnosis complete?**
Specifically:
1. Critique our new mitigation (MODEL_ENSEMBLE in components.py: K
   members on shuffled column orders + per-member seeds, averaged) —
   is it the right treatment? What K? What would you do instead or in
   addition (deterministic row ordering upstream? monotonic feature
   binning? different tie-break handling? distributional averaging
   rather than mean-averaging, since downstream consumes Monte-Carlo
   draws shaped by per-player quantile caches)?
2. Are there LightGBM parameters or training-procedure changes that
   reduce tie-break sensitivity at the SOURCE (e.g. min_data_in_leaf,
   deterministic=true, force_row_wise, feature_pre_filter)?
3. Is ±5/107 on portfolio TAILS consistent with ~30k rows and 11
   boosted models feeding a 10k-draw Monte Carlo + greedy selection —
   i.e., is the variance mostly model-side or selection-side? How
   would you attribute it?
Do NOT review anything else; assume the rest of the system is audited.

## Measured evidence (experiment ledger extract, Addenda 34+)

## Addendum 34 (2026-08-01): column-order sensitivity discovered; dollars selection declined; canonical ordering adopted

The night's three verdicts:
1. **Column-order sensitivity.** A "determinism anomaly" (2019 baseline
   shifting 186.9 -> 181.8 across images with identical feature sets)
   was isolated by control run: LightGBM split tie-breaking depends on
   feature COLUMN ORDER. EXTRA_FEATURES arms append candidates last;
   adoption inserts them mid-list -- same features, different order,
   different (equally valid) model, ~+/-5 mean-best of order luck.
   Consequence: single-run A/Bs were exact only up to ordering; the
   panel discipline absorbs this, single-season adoptions don't. FIX:
   build_X now sorts active features alphabetically -- candidate arms
   and post-adoption baselines train byte-identical models forever.
   The sort is itself one final re-ordering, so the six-season harvest
   (next) defines the definitive shipping baseline.
2. **SELECT_OBJ=dollars declined.** Expected-dollars selection lost on
   every metric INCLUDING ROI (tails 9 vs 21 across the panel). Root
   cause recorded: a 1,000-lineup field resolves ranks to 1e-3 of
   field, but the GPP curve concentrates payouts at 1e-5 -- the
   estimator cannot see first place. Fix path: tail-resolved field
   estimation (importance-sample the top of the field). Code + gate
   remain.
3. **OWN_MODEL yardstick: available, deferred.** Fallback verified
   clean (walk-forward: 2019-22 have no prior ownership data and
   reproduce the naive field exactly). Standard yardstick stays naive
   for ledger continuity; the model field becomes natural in-season
   when weekly refits give it fresh data.

## Addendum 35 (2026-08-01): the selection-objective panel — dollars fix validated, tail-coverage retained; OWN_MODEL rejected

The user stopped the final harvest so the Addendum 34 fix path could be
tested BEFORE the definitive run — the right call. Commit 27ddf23
implemented tail-resolved rank estimation in select_dollar_entries:
empirical rank when >=10 sampled field lineups score above a candidate,
else a parametric normal tail capped at (count+1)/n. A regression test
pins the failure (two candidates both beating the whole sampled field
must rank by depth into the true tail).

Three arms, six seasons, one canonical-ordering image (all include
GAME_SIM_MODE=possession), plus a deconfounding re-run:

1. **OWN_MODEL=1 rejected as a replay field.** 2019-22 reproduce the
   naive field exactly (walk-forward, no prior data). In 2023-25 where
   it binds: tails equal, median finish roughly DOUBLES (13.6->25.8,
   16.3->25.3, 14.6->20.7%), ROI collapses (+44,792 -> +3,118%). The
   pre-canonical "Wave A tails 21" was order luck. The naive yardstick
   stays; the ownership model remains valuable where validated —
   leverage/chalk analysis and live-season use after weekly refits.
2. **The dollars fix is real.** First run was contaminated by
   OWN_MODEL; re-run clean on 2023-25, the fix's effect stands alone:
   2023 median 26.4->16.0%, ROI +3,113 -> +44,794%. The estimator can
   now see the top of the field (Addendum 34's exact defect).
3. **Tail-coverage retained as shipping default.** Clean six-season
   comparison: tails 15 vs 15; >=237 weeks 2 vs 1 — tail-coverage
   caught 2021's 238.9 slate-breaker, dollars topped out at 206.4 that
   season; median 14.6 vs 15.1%; ROI +219,749 vs +257,008% for
   dollars. The dollars objective buys mid-distribution ROI (+17%) at
   the cost of extreme-tail depth — exactly the trade a 35-40 entry
   Milly strategy must refuse. **SELECT_OBJ=dollars is now a validated
   lever for the ~20k qualifier contest mix**, where advancement/ROI
   dominates and the 237 anchor is irrelevant.

Note the baseline ledger shift: on the canonical-ordering image the
six-season panel reads 15/101 tail weeks (was 23/101 pre-canonical,
Addendum 32) — order luck cut both ways and the honest number is the
reproducible one. The sequential harvest running now (baseline config)
defines the shipping baseline and produces the per-year lineup book.

## Addendum 36 (2026-08-01): harvest attribution — the assembly gap; concentration levers tested, declined for GPP

Full attribution sweep over the harvest lineup book (four analyses, all
deterministic against the 49f8dac baseline):

1. **The ceiling always exists.** Perfect-hindsight optimal (MILP over
   actuals, 8 skill slots + our DST) scored >=194 in 101/101 weeks and
   >=237 in 99/101 (avg ~283). Our capture: 63.5% of optimal; a 237
   Milly winner runs ~84%. Misses are never "the slate had no ceiling."
2. **Identification is fine; assembly is the gap.** 71% of each week's
   top-3 actual scorers per position appear somewhere in our 40; the
   slate's #1 QB is rostered 71% of weeks; entry diversity healthy (14%
   pairwise overlap, ~120 unique players/week). But the 40 spread over
   ~16 distinct QBs (~2.5 tickets/stack), and the best single-lineup
   overlap with the weekly optimal-8 is TWO players in the median week
   (2.8 in boom weeks). Right stacks, wrong pieces.
3. **Punt anatomy validated, punt quality poor.** Optimal lineups carry
   ~1.0 sub-$4k skill player (the mandatory-punt rule matches winning
   anatomy). Our punts: mean 7.3 pts, 45% under 5. A perfect
   same-position punt swap crosses 194 in 16 of 28 near-miss weeks
   (oracle bound). Punt-boom prediction (Addendum 24 next-man-up
   detector) is now the highest-value untested lever.
4. **The near-miss band is dense**: 28 weeks at 180-194.

Levers built and tested (eb69be0, env-gated, off by default):
MAX_QBS (distinct-QB cap in tail selection, cap-aware greedy) and
N_QB_VARIANTS (per-top-QB catcher-combination candidates). Six-season
panel vs the 49f8dac baseline (tails / >=237 / median / ROI):
baseline 15 / 2 / 14.6% / +220k; cap8+var4 14 / 1 / 14.2% / +248k;
cap12+var4 15 / 1 / 13.7% / +244k; cap8-only 13 / 1 / +249k.

Verdict: **declined for the GPP default.** Every arm loses 2021 week
5's 238.9 (one of only two >=237 weeks in six seasons — the 4-Raven
Lamar build survives only under uncapped coverage), and none adds tail
weeks. Concentration buys mid-distribution consistency (median and ROI
up in every arm) at the extreme tail's expense — the same trade
direction as dollars selection, and the same reason to refuse it for
the Milly. cap12+var4 joins SELECT_OBJ=dollars as a validated
qualifier-mix candidate (equal 194-tails, better median, +11% ROI).

The assembly gap is real but is evidently not closed by concentration
alone: with the cap on, selection holds more combos of the stacks the
MODEL likes, which converts only when the projections rank the right
stacks. The binding constraint under the cap becomes projection quality
on stack ordering, not coverage breadth. Remaining levers from this
sweep, in value order: (a) punt-boom scoring in the punt slot
(next-man-up + depth-rank transition, Addendum 24), (b) stack-ordering
quality (QB p90 calibration), (c) nothing else visible in the book.

## Addendum 37 (2026-08-02): PUNT_BOOM adopted at +2 — the first strict improvement of the program

The Addendum 36 fix path, built and validated in one cycle. The lever
(f9b2886): punt-priced skill players matching a winning-punt archetype
get +PUNT_BOOM points on OUR objective only (field untouched, same
asymmetry as the chalk fade). Archetypes from the Addendum 24 study of
actual Milly-winning punts, all point-in-time from player_week_training:
cheap starting TEs (depth_rank 1), newly-promoted rank-1s (prev rank
>= 2), top-decile within-week vacated share (>0).

Six-season dose-response panel vs the 49f8dac baseline
(tails / >=237 / median / ROI / mean-best):

- baseline:      15 / 2 / 14.6% / +220k / 178.4
- PUNT_BOOM=2:   **16 / 2 / 14.4% / +256k / 179.7**  <- adopted
- PUNT_BOOM=4:   15 / 1 / 14.7% / +241k / 178.8
- PUNT_BOOM=8:   14 / 0 / 14.8% / +223k / 178.4

+2 is the only configuration in the entire off-season program to beat
the baseline on EVERY headline metric simultaneously — one more tail
week (2022), both >=237 slate-breakers kept, median, ROI, and mean-best
all better. The dose-response is textbook: at +4/+8 the boost overrides
the p90 punt valuation and forces archetype punts into lineups that
didn't want them, killing 2019's 271.1 and 2021's 238.9. The signal
helps as a tiebreak among near-equal punts and hurts as a mandate.

Adoption: default PUNT_BOOM=2 in code on BOTH paths — replay
(build_slates) and the live app pool (_player_pool via
punt_boom_flags_live, which unions training history with the upcoming
week's player_week_inference rows so a fresh promotion is visible in
its first week). Env still overrides; 0 disables. The shipping baseline
of record is now the PB2 row; the six-season lineup book is being
regenerated to match.

## Addendum 38 (2026-08-02): real Milly winners 2019/2023/2024 — the honest bar, and where the 55 points live

The user supplied player-level Milly-winning rosters for 2019, 2023 and
2024 (reports/milly-winners-2019-2023-2024.csv; 2024 wk9 is a duplicate
of wk7 in the source and is excluded). Combined with the 2025 file this
gives 68 real per-week winning lines — now wired into replay reporting
(backtest/real_lines.py, "vs REAL winning lines" output row).

**Ground truth vs our book: beat the actual same-week winner 1/64
weeks** (2024 wk10, a 178.3 line). Mean gap 51-68 pts by season. Real
lines: median ~237 (2023-25) but 252 in 2019; season minima 178-222.
The long-standing "194 min line" was a season minimum, not a typical
bar — and 2025's softest line (193.9) was WEEK 1, the week replays
never covered until today's cold-start fix. The market is most beatable
exactly where our validation was blind.

**Winner anatomy (50 lineups):** ~120% summed ownership (~13%/player),
~2 sub-5% players, ~1.9 chalk (>=20%) pieces, punt in 73%, salary to
the cap. QB: 60% under $6.5k, mean 8.3% owned. Boom density: 3.4
players >=30 pts and ~1.0 >=40 per winner (ours: 1.8 and 0.6).

**Slot decomposition of the gap** (winners vs our weekly-best):
WR 29.9 vs 19.9 (x3 slots = ~30 pts — THE deficit), TE 21.5 vs 15.4,
DST 16.7 vs 12.7, RB 26.8 vs 22.0, QB 32.6 vs 28.3. Winning WRs are
mid-priced eruptions (Fuller 56.7 @ $4.5k, Jennings 49.5 @ $4.1k).
67% of winning players were already somewhere in our 40 that week —
identification holds, assembly + WR-ceiling capture fail.

Prescriptions queued (both already-coded env levers, panel next):
N_MIDQB (winner QBs are exactly mid-priced low-owned) and
LEV_POS_WEIGHTS (Levitan: crowd accurate on RB chalk, weak on WR/TE/DST
— fade where the crowd is wrong). Strategy implication unchanged but
sharpened: 4 Milly entries are lottery tickets against a 237 median;
the ~187 qualifier line (cleared 7/17 weeks in 2025) is where the
edge actually cashes.

## Addendum 39 (2026-08-03): the rebuild-nondeterminism incident — and the corrected 9-arm verdicts

A 9-arm panel (rest-week training exclusion, draw widening x2, FTN
features x2, WR levers x2, ownership-shape constraint, DST bonus) came
back with a shared fingerprint: unrelated selection-only arms all showed
2021 at ~170 mean-best vs the prior control's 178.8 — byte-identical
ROIs across arms that shouldn't share anything. A clean CONTROL arm on
the same image reproduced the shifted numbers exactly, proving the
cause: **feature-table REBUILDS are not deterministic** (BigQuery
tie-breaking; the FTN-column rebuild between panels silently moved the
shared baseline). Replays are exact within a table build; a rebuild is
a new world.

**New law: after any build-features run, every panel co-runs its own
CONTROL arm on the same table build.** (CLAUDE.md, validation laws.)

Corrected verdicts vs the same-build control (16/107 tails):
TRAIN_MAX_WEEK=16 **+5** (21; retrain reshuffle inflates it — see
Addendum 40's combo), SIM_WIDEN_DRAWS=fitted **+4** (20, +1 >=237),
EXTRA=pa_rate_l6 +3 (19), widen-WR-bump +1, FTN pressure / WR-punt
archetype / MIN_LOWOWN=2 / DST_PUNT_BONUS all 0, WR_BOOM=2 **-3**
(declined). SIMS30K (32Gi retry after 12Gi OOM): +2 tails with the
program's best ROI and medians — not worth 3x compute as the panel
default; recorded as a live-Sunday candidate (one slate, pennies).

## Addendum 40 (2026-08-03): EW adopted — the largest gain of the program; live sim-mode closes the fidelity gap

**Final single-lever panel** (same-build control 16/107): BIGPLAY=1
(deep-threat house-call mixture) 16 tails but +1 >=237 (2019 244.2),
best-of-night ROI and 4/6 better medians — flavor, not tails.
EMP_MARGINALS=1 (empirical per-position/tier families from the
NFL-DFS-Tools fit, rank-reordered onto our copula, moments preserved)
**+5 CLEAN** (21; models byte-identical to control — no reshuffle
excuse). LEV_SHAPE=sqrt 16 tails but the night's best median (13.1%) —
qualifier pile.

**Combo panel:** EMPMARG x WIDENFIT ("EW") **24/107 tails, 2 >=237
weeks — the strongest configuration in program history** (2019: mean
best 195.2, 8/17 tail weeks). EMPMARG x TRAINW16 23. All three stacked
20 (2024 collapsed to 0 — triple-stack overshoots; rest-week exclusion
stays a recorded lever, its solo +5 mostly retrain shuffle).

**ADOPTED: SIM_WIDEN_DRAWS=fitted + EMP_MARGINALS=1 as code defaults**
(backtest.replay.apply_draw_shape). Mechanism, in one line: the fitted
widening supplies the width the calibration always measured as missing,
and the empirical families shape that width into realistic right-skew —
composed, mean-preserving, correlation structure untouched.

**Live fidelity fix (the biggest architectural find of the audit):**
the live CLASSIC path had never consumed draws — plain MILP + a
normal-approximation ranking — so every draws-side gain existed only in
replays. inference/live_lineups.py now runs the validated pipeline on
the live slate (features -> cold-start -> components -> usage notes ->
correlated sims -> EW shaping -> market blend as an additive mean shift
-> replay-identical tournament tilts -> boom-draw candidates ->
tail-coverage selection), POST /lineups sim=true by default with a
fail-safe MILP fallback (locks/bans/slate-restricted requests use the
MILP path). What was validated is now what fires on Sundays.

Also this cycle: repo-mining rounds 2-3 (RTS field-model blueprint with
measured 0.43->0.72 dupe-correlation value; Picking Winners overlap
datapoint; DK standings purge ~4 days -> Mon/Tue download law),
vendor-methodology audit (Lev% shipped on lineup cards; salary-residual
et al. recorded), and the pre-built September machinery: lossless
contest-entry import, field-calibration harness, accuracy grading,
proj_tail ceiling lever, external-projection consensus diff. The EW
harvest (sequential, weeks 1-18, book export) is the shipping baseline
of record; its numbers land in six-season-harvest-summary.md.

## Addendum 41 (2026-08-03): EW-book attribution + the closing proposal panel — the program ends at a measured local optimum

**EW harvest of record: 23/107 tails, 2 >=237, mean best 180.6, first
WEEK-1 replays (2019 wk1 = 199.3, a tail week), and the program's first
real head-to-head win vs an actual same-week Milly winner (2024 wk10).**
Book: six-season-harvest-summary.md + six-season-replay-lineups.csv
(4,280 lineups).

Attribution sweep on the new book: vs the PB2 book EW converted 15
weeks and regressed 9 (net +6 on common weeks) — it reshapes selection,
not uniformly lifts. QB slot nearly closed (30.3 vs winners' 32.6),
boom density 2.01/lineup (from 1.8; winners 3.4), punt oracle partially
harvested (10/24 near-misses from 16/28). Remaining gaps: WR slot 20.9
vs 29.9, TE slot regressed to 13.1 under the empirical TE family.

Closing proposal panel (co-run CONTROL reproduced the harvest exactly —
the new law works): SHAPE_MIX=0.5 (hedge shaped/raw worlds) 20 tails —
mixing DILUTES the shaped edge, declined; BIGPLAY on EW 22 (2022 max
240.3) — declined; EMP_POS without TE 23 — equal, declined (churn
without gain). With EWT (20) and SIMS30K (+2 at 3x cost) earlier, five
attack angles have failed to beat EW. The pre-season program closes at
a measured local optimum; remaining upside is in-season data (field
calibration, qualifier curves, ownership refits) rather than more
pre-season search. Levers all remain env-gated for future panels.

## Addendum 42 (2026-08-03): the FINAL EXAM — every survivor and graveyard retry, one panel, one control

Ten arms, six seasons each (2019, 2021–2025), all on the same table build
and image; CONTROL reproduces the EW baseline exactly (23/107 ≥194 tail
weeks; the 2019 execution's metrics were recovered from Cloud Logging
after a truncated log fetch — job succeeded, fetch didn't).

| Arm | Levers | Tails ≥194 | Δ | Mean best | Median fin % |
|---|---|---|---|---|---|
| CONTROL | (EW baseline) | 23 | — | 178.7 | 15.1 |
| **QBVAR4** | N_QB_VARIANTS=4 | **25** | **+2** | 178.8 | 15.0 |
| OWNFADE | OWN_MODEL=fade | 24 | +1 | 178.9 | 14.7 |
| COMBO2 | PUNT_MAX=3500 + no game-stack batches | 24 | +1 | 178.6 | 15.6 |
| PMAX3500 | PUNT_MAX=3500 | 23 | 0 | 178.7 | 15.0 |
| NOGSTACK | N_GAMESTACK=0, N_DARKGAME=0 | 23 | 0 | 178.6 | 15.3 |
| RATEDW | RATE_DENOM_WEIGHTS=1 | 23 | 0 | 179.3 | **14.6** |
| VALUE2 | VALUE2_MIN=2 | 22 | −1 | 178.6 | 15.2 |
| WRBOOM1 | WR_BOOM=1 | 22 | −1 | 178.7 | 15.1 |
| TMW17 | TRAIN_MAX_WEEK=17 | 21 | −2 | 177.6 | 14.9 |

Verdicts: QBVAR4 is the lone clear positive and the adoption leader —
consistent with Addendum 36's qualifier finding (best median) now
carrying the Milly tail too. OWNFADE's +1 with the best-median tie
(14.7) makes it the second candidate. COMBO2 (+1) beats its own parts
(both 0), a real interaction. VALUE2/WRBOOM1/TMW17 are rejected and
return to the graveyard with proper burials (correctly tested this
time). Because +1/+2 on 107 weeks is within tie-breaking distance, the
QF (QBVAR4+OWNFADE) and QFC (QF + COMBO2's pair) combination arms are
running before anything is adopted — combos have failed to add before
(Addendum 33).

Also in this pass, all committed pre-panel: thesis constraints
(per-combo portfolio floors through the sim path and POST /lineups),
the showdown captain board (salary-free p_top/p_top6 from the build's
draws + salary-aware CPT/FLEX-optimal rates counted over every per-draw
MILP solve, rendered under the showdown lineups), and the XFP +
schedule-context candidate features (017j: opportunity-valued FP from
2014–18 bucket rates; net_rest_diff; body_clock_hour) — table rebuild
deliberately held until the running panel queue drains. Node-checking
every served page's inline JS surfaced two pre-existing page-breaking
newline-escape bugs in the late-swap prompts, now fixed.

**Showdown bring-back A/B (2025, 43 slates, 40 entries):** CONTROL 82.3%
mean capture, 10/43 slates ≥90%; SHOWDOWN_BRING_BACK=1 82.4%, 10/43. A
wash — the pass-position captain almost always carries an opposing
bring-back organically in the correlated draws, so the hard constraint
binds too rarely to move capture. Stays OFF by default; it remains a
free judgment lever for slates where the field will captain a one-sided
blowout script.

**Punt-shape / graveyard-retry panel (same image and tables, exam CONTROL
= control):** PSLOPE (PUNT_SLOPE=1) 23 tails, PSTRICT (punt_elig
eligibility) 23, LOWSAL (10-lineup min-salary-47k batch) 23 — all exact
nulls; the salary-related graveyard verdicts are confirmed under their
"different approach" retries and stay buried. DIRK8
(GAME_SIM_USAGE=dirichlet, K=8) 11 tails / mean 175.0 — a severe
regression: sharpening usage concentration collapses tail weeks, so the
K=20-null verdict was about the MODE being neutral, not about K being
mis-tuned. Default usage mode retained.

## Addendum 43 (2026-08-03): research rounds 7-8 — three offline verdicts (TabPFN, conformal, persona field)

Scripts preserved in `scripts/`; all on the real panel, walk-forward
2019-24 train -> 2025 test (the validation law, one split).

**TabPFN-v2 beats our LightGBM shape zero-shot.** 8k-row context, no
training, CPU: RMSE 6.539 vs 6.580, pinball90 1.347 vs 1.388 (better at
ALL four positions), q90 coverage 0.908 vs LGB's 0.870 under-coverage —
the first model to arrive properly calibrated out of the box. Caveats:
reference was the quick-LGB stand-in (not the component system); v2.5+
weights are license-gated (priorlabs.ai, TABPFN_TOKEN); CPU inference
(~9 min per 5k predictions at 8k context) is too slow for replay panels
— adoption path is the licensed API or a GPU job, queued as the first
post-season-start model experiment. Full-context (29k) confirmation run
in flight.

**Conformal calibration: real, small, direction-confirming.** Raw LGB
q90 under-covers (0.870, QB worst at 0.839); a single CQR shift (+1.31
pts, calibrated on 2024) restores 0.899 AND improves pinball (1.378 vs
1.399). Gaussian mean+1.28sd covers only 0.836 — independent
confirmation of the EW/empirical-marginals adoption. Candidate use: a
per-season conformal shift on the projection layer; low priority while
EMP_MARGINALS carries the same correction inside the sim.

**LLM persona field passes the offline screen — decisively, with a
contamination asterisk.** Four personas (casual 55 / value 25 / sharp 15
/ homer 5), public info only (salary, l4 form, Vegas totals), aggregate
exposure vs REAL pct_drafted from imported contests (raw.contest_ownership,
72 weeks of 2022-25 — the data was already in house): Spearman 0.554 vs
naive_ownership 0.393, MAE 0.851 vs 1.156 share-points, persona better
on all three test weeks (w5/w10/w15 2025), gap widest late season (.502
vs .233). ASTERISK: the LLM's training window includes the 2025 season,
so memorized hindsight may inflate this; the clean test is live 2026
weeks. Verdict: mechanism validated, cost trivial (~4 calls/slate);
promote to a September live shadow scored by the field-calibration
harness against real standings before any adoption into the field sim.

## Addendum 44 (2026-08-03): causal vacated-opportunity study — who actually captures absent teammates' usage

Research round 9's causal-ML item, run as an event study on 2019-2025
(scripts/causal_vacated_study.py): treatment = team-weeks where a
target hog (trailing share >=18%, 553 events) or carry hog (>=35%, 369
events) is absent; outcome = each teammate's ACTUAL share minus his own
trailing expectation; uplift vs no-absence control weeks, by (position x
depth) cell.

Findings, both t>2.8 in the load-bearing cells:
- **Vacated targets flow LATERALLY, not down:** WR2 +2.61 share pts,
  WR1 +2.51, WR3 +1.86, TE1/TE2 +1.2-1.4 — and RBs capture ~nothing
  (RB1 +0.71 at t=1.9, RB3 +0.23). The "check-down bump" folklore fails.
- **Vacated carries CONCENTRATE:** RB2 +15.8 share pts (t=10.8), RB1
  +9.5, RB3 +7.5; receivers/TEs gain ~nothing from a lost carry hog.
- Accounting honesty: teammates in the panel capture only ~10 of the
  mean 25.5 vacated share pts — the remainder goes to call-ups outside
  the panel — so the CELL STRUCTURE is the finding, not the absolutes.

Shipped as EXTRA_FEATURES candidates `vacated_capture_tgt`/`_car`
(021/023: team vacated sum x empirical cell capture rate — the
interaction the team-level-sum feature left for the GBM to discover).
Final-panel arm VACC judges them; the raw team-level features stay.

**Round 9 remainder (LEM / players-as-tokens):** the Large Event Model
is the most promising architecture idea yet for the sim — but it's a
GPU training project, and the honest gate is compute, not data. Shipped
tonight: scripts/lem_corpus.py tokenizes the full nflverse pbp
(1999-2025, ~1.25M plays; smoke-tested 143k plays / 855 games / 31k
composite vocab on 2023-25) into the SAME state space as the
possession-Markov engine, so the adoption bar is pre-registered:
held-out next-event log-loss vs the Markov transition model
(walk-forward, train <=2023, eval 2024-25), and only a winner earns
GAME_SIM_MODE=lem integration. nanoGPT ~10M params, one 24GB GPU,
hours-scale — first offseason/GPU-quota project. RisingBALLER-style
player embeddings fold into the same effort (player-conditioned LEM is
EventGPT exactly); the cheap proxy already in-system is archetype
clustering + the new causally-directed vacated features (Addendum 44),
which cover the same cold-start/role-change gap at feature scale.

## Addendum 45 (2026-08-03): market-implied distributions from alternate prop ladders — validated, endpoint shipped

Round 10's no-new-model idea, run on data already in house (prop_lines
holds DK alternate ladders 2023-25: 102k reception-yds rows / 141
distinct lines, 47k rush, 27k pass). Pairwise de-vig of Over/Under at
each alt line -> monotone implied P(over x) -> implied quantiles
(scripts/prop_implied_study.py; two bugs found en route: prices are
AMERICAN odds, and the naive first pass produced garbage curves that
the coverage check caught immediately).

Results (matched player-weeks vs panel actuals):
- The market's implied q90 arrives CALIBRATED out of the box: coverage
  0.921 recv / 0.917 rush vs target 0.90 — better than our LGB
  quantiles (0.863/0.843 on the same 2025 rows) — and beats us on rush
  pinball (5.87 vs 6.00), ties on recv (5.94 vs 5.95).
- **Disagreement is predictive BOTH directions** (the leverage
  finding): top-20% "model q90 >> market q90" rows outperform the
  market median by ~+6 yards on actuals; bottom-20% underperform it by
  ~-5. Neither source dominates -> the diff itself is the signal.

Shipped: inference/market_implied.py (tested de-vig/curve/quantile
module) + GET /api/market-tails (our p90-mean spread vs the market's
q90-q50 spread in DK pts, biggest gaps first) — a watchlist flag under
the ETR contract (never a silent model input). September follow-ups
queued: migrate market_ceilings' vig-naive ladder onto this module;
market-implied quantiles as EXTRA_FEATURES candidates (NULL pre-2023,
same precedent as FTN) for a replay arm.

**Round 10 remainder (cold-start pooling, ensemble weather, synthetic
data):**
- **Hierarchical Bayesian partial pooling: NULL on the slice it exists
  for.** On 1,316 cold-start 2025 rows (<=2 career games), explicit
  empirical-Bayes shrinkage (player -> pos x draft-round x depth group
  -> position) loses to the plain LGB (RMSE 6.103 vs 5.843); a 50/50
  blend is within noise (5.831) with worse MAE and bias. The GBM sees
  draft_round/depth_rank/is_cold_start and already pools implicitly.
  NumPyro build not justified; scripts/coldstart_bayes_study.py holds
  the harness if the 2026 rookie class reopens the question.
- **Ensemble weather (GenCast): right idea, staged on-ramp.** GenCast
  itself (TPU, ERA5 init pipeline) is an offseason project; the
  same-shaped cheap step is Open-Meteo's free ensemble endpoint (GFS/
  ECMWF members) — wire wind-speed SPREAD per stadium into the weather
  ingest in September and pass scenario weights into the sim
  (wind-sensitive draws already exist via temp/wind features).
  Historical ensemble forecasts aren't in house, so no backtest is
  possible tonight — live-data-gated, genuinely.
- **TabPFN synthetic data: queued behind the TabPFN projection
  experiment** — generation quality inherits from the same license-
  gated 2.5 model, and the stress-test use (rare regimes: snow games,
  backup QBs) needs a regime taxonomy first. Not data-gated, but
  effort-vs-evidence says it waits for the TabPFN main-line verdict.

## Addendum 46 (2026-08-04): research round 11 — kNN comps null, LLM env-forecast scaffolded, CV gated

- **Retrieval-augmented projection (kNN comps): null for adoption,
  third confirmation of the calibration pattern.** K=100 comps over
  standardized feature space (position-weighted, strictly prior
  seasons): RMSE 6.752 vs LGB 6.583, pinball90 1.408 vs 1.393 — LGB
  keeps the accuracy crown — but kNN's q90 coverage is exactly 0.900
  vs LGB's 0.871. Conformal (Add. 43), the betting market (Add. 45),
  and now comps all agree: OUR POINT-MODEL TAILS UNDER-COVER; every
  distribution-native method arrives calibrated. The sim already
  corrects in-draw (EMP_MARGINALS), so no adoption — but any DISPLAYED
  p90 (lineup cards, /api/market-tails) should eventually carry the
  conformal shift. Comps stay attractive as an explain-layer UI
  (scripts/knn_comps_study.py).
- **LLM game-environment forecasts (ForecastBench pattern): built for
  live validation, not backtested** — fuzzy-question backtests are
  contaminated (the model knows how 2025 games went). scripts/
  env_forecast.py runs the multi-stage pipeline (context -> sub-
  question forecasts -> critique -> final JSON: shootout_p, run_lean_p,
  pace) per game and logs to reports/env_forecasts/ for post-slate
  grading. Contract: watchlist context first; sim scenario weights only
  after a few graded live weeks show calibration.
- **CV on film: genuinely gated** — no footage pipeline in house and
  broadcast-video licensing is its own problem; nearest in-house proxy
  (NGS separation, snap shares) already feeds the models. Revisit only
  if a specific role-ambiguity (committee backfield) costs us a week.

**LEM v0 verdict (GPU run, 2026-08-04):** the composite-token
transformer (11.3M params, 49.5k vocab) LOST to the add-k bigram on
held-out 2024-25 next-event NLL — 8.192 vs 8.120, top-1 13.5% vs 16.8%
— exactly the failure the vocab math predicted (~9 training samples per
embedding). GPU quota turned out to exist (Cloud Run L4,
--no-gpu-zonal-redundancy, 1h task cap, ~$1/run), so the "offseason"
gate was imaginary; v1 with FACTORED tokens (7 small vocabs, summed
input embeddings, 7 output heads — the standard fix) launched the same
night. v0 checkpoint + metrics in gs://.../lem/.

**LEM v1 verdict (same night): FACTORED model BEATS the bigram on the
pre-registered bar** — held-out NLL/event 4.599 vs 8.120, with 1.9M
params and a 7-minute L4 run (~$0.15). Honest caveats logged with the
win: (a) a large share of the gap is the factorization itself — the
composite bigram hemorrhages probability on unseen exact transitions —
so the NEXT bar is a factored bigram (each factor conditioned on the
prior event); (b) on exact-match top-1 the bigram still edges v1
(16.8% vs 16.4%) by memorizing modal transitions — NLL is the metric
that matters for a generative sim, but the number is recorded. Road to
GAME_SIM_MODE=lem, in order: factored-bigram hurdle -> ROLLOUT REALISM
harness (generate full games; compare score distributions, drive
lengths, play counts vs held-out 2024-25 actuals; this is the gate
that counts) -> player-conditioning (EventGPT proper) -> replay A/B
vs the possession-Markov engine. Checkpoints/metrics in gs://.../lem/.

## Addendum 47 (2026-08-04): QF ADOPTED — N_QB_VARIANTS=4 + OWN_MODEL=fade become the defaults

Combo arms complete the exam: QF (QBVAR4+OWNFADE) 25 tails / median
14.6% (program best) / TWO >=237 weeks incl. a 254.6 max (program
high); QFC (QF + PUNT_MAX 3500 + no-game-stack) 24 — the extra pair
subtracts (and craters 2022 to 0/18); QBVAR4 alone 25 at median 15.0.
Adopted QF: equal-best tails, strictly better median, deeper ceiling.
Defaults now in code (engine N_QB_VARIANTS=4; replay OWN_MODEL=fade;
live fade upgraded to the trained ownership model with naive as a
LOGGED fallback only). "0"/"" restore the old behavior; the final
candidate panel (XFP/SCHED/VACC/MPG3/QD2) will run against the
post-adoption CONTROL. PMAX3500, NOGSTACK, RATEDW retire to the
registry as validated-neutral; VALUE2, WRBOOM1, TMW17, DIRK8 buried.

## Addendum 48 (2026-08-04): the four-reviewer pipeline audit — 17 verified findings, 3 commits of fixes

User-requested full audit of the sim pipeline and everything around it,
run as four parallel reviewers (selection engine, app/export, sim
pipeline, commit-range review) with every finding verified against the
code before fixing. Committed as 26cd477, f936052, 80f4051; every HIGH
carries a regression test or hard guard.

The five that mattered most:
1. **Thesis batch crashed the live endpoint** (UnboundLocalError on any
   feasible thesis — the block landed above its own seen-init) and its
   tags were clobbered. The unit test had passed because it tested the
   repair function, not the generation path — an end-to-end test now
   exercises the real path.
2. **/api/market-tails was dead on arrival** (guarded on 'p90'; the
   column is 'proj_p90') — the Addendum-45 feature returned [] forever,
   indistinguishable from "no props". Plus pass-yards priced 2.5x hot.
3. **xfp_l4 was structurally NULL at live inference** — exact-week join
   onto a pbp table with no upcoming-week rows; the replay A/B was real
   but adoption would have shipped silent train/serve skew (the exact
   class 023's header warns about). As-of join now.
4. **Late-swap locked rows could upload invalid slots** — sequential
   fill misaligned positions whenever the locked player sat in a
   different slot index in the new lineup; position-aware fill now, and
   genuinely un-arrangeable locks leave the row untouched.
5. **The prop-market merge could shift every draw index** on duplicate
   name-norm keys (each player scored with the NEXT player's draws)
   — dedup + hard length assert.
Also fixed: OWN_MODEL falsy-spelling footgun (own_mode()), TabPFN
live-parity gap + empty-cache fallback, NaN-game pseudo-correlation,
SHAPE_MIX=0 inversion, Lev% ~10x field-pct overstatement, lock-aware
churn assignment, DST rng decoupling, vacated CASE position source,
xfp offensive-TD-only rates.

Standing caveat: the in-flight final-panel arms (VACC/XFP/XSCHED) run
the PRE-fix SQL columns — replay signal stands, but any adoption
re-confirms on rebuilt tables (which the deploy requires anyway).
Ledger corrections: PMAX3500's exam null is PARTIALLY EXPLAINED — the
PUNT_MIN/PUNT_MAX levers only ever reached the ~2N lev candidates, not
the boom/qbvar/game batches, so the dose arms tested a weaker lever
than documented. Same for the cross-thesis repair regression and
_select_tail_qb_capped underfill (documented, low priority).

## Addendum 49 (2026-08-04): the final candidate panel — SCHED adopted, TabPFN validated on tails

Post-rebuild, post-QF-adoption build (CONTROL 18/107 on the new tables
— the rebuild law bit again: 23 -> 18 baseline shift, all arms co-run):

| Arm | Tails | Mean | Med% | Verdict |
|---|---|---|---|---|
| CONTROL | 18 | 176.0 | 15.1 | — |
| **SCHED** (net_rest_diff + body_clock_hour) | **24 (+6)** | 178.4 | 14.4 | **ADOPTED** |
| **TABPFN** (TabPFN marginals) | **24 (+6)** | 178.4 | **14.7** | validated; combo pending |
| XSCHED (XFP + SCHED) | 24 (+6) | 178.5 | 15.2 | = SCHED alone; XFP doesn't stack |
| XFP | 20 (+2) | 179.4 | 14.8 | positive alone; stays candidate |
| QD2 (MAP-Elites archive) | 18 (0) | 175.7 | 14.8 | validated-neutral |
| VACC (causal vacated capture) | 13 (−5) | 177.4 | 14.8 | REJECTED |
| MPG3 | vacuous | — | — | cap 3 < mandatory stack shape; MPG4 running |

SCHED is in NUMERIC_FEATURES (the XSCHED arm proves the exact adopted
model via sorted columns). TabPFN's +6 with the panel-best median
converts Addendum 43's calibration win into a TAIL win — the marginal
shapes matter where it pays. The SCHED+TABPFN stack arm (STPFN) decides
whether both ship as defaults; TabPFN live adoption additionally needs
the weekly projection-cache GPU job (built: tabpfn-gen; ~$0.05/wk) and
falls back to empirical marginals when the cache is missing (audit
round 3). VACC's -5 despite t>10 causal evidence is the program's
cleanest "true fact ≠ good feature" exhibit; the event-study finding
stands as scouting knowledge (Addendum 44).

**MPG4 verdict (the corrected MAX_PER_GAME dose):** 20 tails (+2) but
mean 175.7 and median 15.2 both WORSE than control — noise-band mixed,
not adoption-grade next to the clean +6s. Closes the winners-
concentration question the diffusion pitch raised: our 4.6-per-game
concentration vs winners' 2.96 is real but capping at 4 (the largest
dose compatible with the mandatory stack) doesn't buy tails — the
concentration gap is a symptom of our stack construction, not an
independent leak. MAX_PER_GAME retires to the registry as
tested-neutral; MPG3 recorded as infeasible-vacuous (cap < stack shape,
caught only because the audit taught us to look for vacuous arms).

## Addendum 50 (2026-08-04): STPFN — TabPFN marginals ADOPTED default-on; the stack verdict

SCHED+TabPFN together: 24 tails (equal to each alone — the +6s share a
mechanism budget, they don't add) but the BEST mean-best of the entire
panel (179.5 vs 178.4) at the tied-best median (14.7), deterministic
same-build comparison. Adopted: TABPFN_MARGINALS defaults to 1 —
per-player TabPFN quantile marginals over the possession-engine copula,
with automatic fallback to the EW empirical marginals when the
projection cache is absent (so live weeks degrade to the previous
default, never to raw). Operational contract: the tabpfn-gen GPU job
(~64s/season, ~$0.05) regenerates features.tabpfn_projections after
every feature-table rebuild and weekly in-season (runbook entry).
Final adopted stack of the program: EW + PUNT_BOOM=2 + QF
(N_QB_VARIANTS=4, OWN_MODEL=fade) + SCHED features + TabPFN marginals.

## Addendum 51 (2026-08-04): external model review (Gemini) — triage, fixes, and the LOSO consistency table

An independent Gemini review of the full ledger + complete source
(reports/external-review-package + code companion) returned findings;
each verified against code before acting. Its implementation
cross-checks all CONFIRMED our Addendum-48 fixes.

**1.1 Multiple comparisons (HIGH) — accepted, with evidence both ways.**
The reviewer's LOSO rule (adopt only if positive in >=4 of 6 seasons)
was computed retroactively for every current adoption:
| Adoption | +seasons | -seasons | LOSO 4-of-6 |
|---|---|---|---|
| SCHED | 4 | 0 | PASS |
| TABPFN | 4 | 1 | PASS |
| STPFN (shipped combo) | 4 | 0 | PASS |
| QF | 2 | 1 | **FAIL** |
QF stays adopted on cross-build replication (QBVAR4 +2 on a different
table build; Addendum 36's independent qualifier panel) plus
equal-tails/best-median — but it is now FLAGGED as the weakest adoption
and gets re-judged against real September standings at the qualifier
recalibration. LOSO >=4-of-6 (with no more than 1 negative) is ADOPTED
as a prospective validation law for future single-build adoptions.

**1.2 Silent TabPFN fallback (HIGH) — accepted, fixed.** /lineups now
returns model_health (cache probe per season/week) and the builder UI
shows a red warning when the sim used empirical-fallback marginals —
"never silently -6 tails on a Sunday."

**4.x Missing tests — all three added**: massive-lock late-swap stress
(6 locked cells, position-aware fill of the rest), DST variance guard
(gate-on rel-sd > 0.3), and the salary-lag threshold contract (pure
is_salary_lagged predicate mirroring the SQL; Gadsden-type promotion
must flag).

**1.3 Script-feedback pace multiplier — accepted as a lever to test**
(queued: SCRIPT_FEEDBACK env in game_sim, panel arm after the harvest).
**3.1 CQR live calibration** — queued for September (needs rolling live
accuracy; pairs with /api/accuracy). **3.2 consensus-divergence
feature** — queued as a candidate for the next panel round (market
data 2023+, FTN-style NULL precedent). **3.3 LEM "game flow"
attention** — PARTIAL REBUT: LEM v1's factored tokens already embed
score-differential and quarter (the sd/qtr factors); the real v2 items
are continuous embeddings and longer context, noted in the LEM road.

## Addendum 52 (2026-08-04): expansion-review verdicts, part 1 — showdown fade, and two vacuous-A/B catches

**SHOWDOWN_FADE (naive-ownership chalk fade for Captain Mode):** the
first two A/B attempts were VACUOUS and caught by the byte-identical
check — (1) stale :review image lacking the lever, (2) both arms on the
replay's MILP default while the lever (and live builds) run the sim
path. Law recorded: showdown A/Bs need SHOWDOWN_SIM=1 in BOTH arms +
an image probe. The real A/B (sim path, 43 slates 2025): capture-WASH —
84.8% vs 84.9% mean, 9/43 vs 8/43 slates ≥90%, median −1.1. Expected
shape: capture measures scoring accuracy, a fade buys leverage capture
can't see (no showdown field model exists). Verdict: costs ~nothing,
benefit unmeasurable pre-season → OFF by default, re-judged against
real showdown standings once September imports accrue.

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


## The two relevant source files


===== FILE: src/nfl_dfs/models/featureset.py =====
```python
"""The shared model feature matrix.

One canonical feature list for the baseline and component models so a
model loaded from the registry always sees the columns it trained on.
Columns absent from an input frame become NaN (LightGBM handles missing
natively); extra columns are ignored.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

POSITIONS = ["QB", "RB", "WR", "TE"]

# LightGBM thread cap shared by every model in this package. Our panels are
# small (tens of thousands of rows at most); letting OpenMP grab all cores
# adds per-split sync overhead and has livelocked outright on WSL. Eight is
# plenty and matches Cloud Run job sizing.
import os as _os  # noqa: E402

LGB_THREADS = max(1, min(8, _os.cpu_count() or 1))

NUMERIC_FEATURES = [
    # Usage (point-in-time rollups, §5.2)
    "target_share_l4",
    "carry_share_l4",
    "wopr_l4",
    "rz20_targets_smoothed",
    "ez_targets_l4",
    "deep_targets_l4",
    "separation_l4",
    "stacked_box_l4",
    "gl3_carries_smoothed",
    "snap_share_l4",
    # Production trail
    "dk_points_l4",
    "dk_points_std",
    "dk_points_vol",
    # Game environment
    "implied_team_total",
    "spread",
    "game_total",
    "expected_game_script",
    "is_home",
    "is_dome",
    # Experience / role
    "games_played_prior",
    "is_cold_start",
    "depth_rank",
    # depth_rank_delta (Addendum 24) was REMOVED from the model inputs
    # 2026-08-01: the replay pipeline turned out to be fully
    # deterministic (3 identical confirmation runs), which retroactively
    # converts its "neutral within noise" replay result into a real
    # -4.6 mean-best cost (188.4 -> 183.8). The SQL column remains in
    # the feature tables for analysis; it just doesn't feed the model.
    # Game environment extras (2026-08-01): referee-crew flag tendency
    # (strictly-prior; NULL live until midweek crew assignments are
    # sourced) and script-stripped neutral pass rate.
    "ref_flags_prior",
    "neutral_pass_rate_l6",
    # qb_cpoe_l6 ADOPTED 2026-08-01 (Addendum 32): the first feature to
    # pass a six-season panel -- tail weeks 18 -> 23 of 101 at flat
    # mean/median. Found via the audit (ngs_passing was fully unused).
    "qb_cpoe_l6",
    # team_ol_out was REMOVED 2026-08-01 same day it was added: exact
    # replay cost -8.7 mean-best / -4 tail weeks (180.8/4-17 vs
    # 189.5/8-17). Plausible mechanism, bad feature -- likely confounded
    # (teams missing linemen are bad teams). Column remains in the
    # tables for analysis.
    # Next-man-up: opportunity vacated by teammates ruled Out this week
    "team_vacated_target_share",
    "team_vacated_carry_share",
    # Opponent secondary (CB coverage from PFR advstats; NULL before 2018)
    "cb_ypt_allowed_l6",
    "cb_comp_rate_allowed_l6",
    "db_ypt_allowed_l6",
    "top_cb_out",
    # Market signal
    "salary",
    "salary_delta_wow",
    # SCHED pair ADOPTED 2026-08-04 (final candidate panel, Addendum 49):
    # +6 tails vs same-build post-QF control (24 vs 18), best 2019 and
    # 2025 of the panel; the XSCHED combo arm proves this exact model
    # (sorted columns => EXTRA_FEATURES == adoption). Pure pre-game
    # schedule facts — available live by construction.
    "net_rest_diff",
    "body_clock_hour",
]

FEATURES = NUMERIC_FEATURES + ["position"]

# Candidate features (2026-08-01): materialized in the feature tables but
# EXCLUDED from the model unless named in the EXTRA_FEATURES env var
# (comma-separated) -- so one table rebuild supports N parallel exact
# feature A/Bs, each arm enabling exactly one. The deterministic-replay
# lesson (depth_rank_delta -4.6, team_ol_out -8.7): every feature pays
# its own way through a replay before joining NUMERIC_FEATURES.
CANDIDATE_FEATURES = (
    "pace_env_l6",                # own off plays + opp def plays faced (l6)
    "opp_blitz_rate_l6",          # opponent defense blitz rate (FTN, 2022+)
    "team_top2_target_share_l6",  # target concentration -> stack strength
    "qb_time_to_throw_l6",        # NGS avg time to throw (2016+)
    "pa_rate_l6",                 # team play-action rate (FTN, 2022+) — deep-shot / WR-ceiling context
    "opp_pressure_rate_l6",       # opp pressure GENERATED per dropback (FTN, 2022+) — outcome, not rushers sent
    "xfp_l4",                     # expected FP from opportunity alone (bucketed pbp rates; FantasyPoints lineage)
    "vacated_capture_tgt",        # vacated targets x empirical (pos,depth) capture rate (Addendum 44 event study)
    "vacated_capture_car",        # vacated carries x empirical capture rate (backfield-concentrated)
)


def _active_numeric_features() -> list[str]:
    """EXTRA_FEATURES adds registered candidates; DROP_FEATURES removes
    any baseline feature -- the ablation mirror (2026-08-01: built to test
    whether the pre-A/B-era salary features earn their slots, after the
    salary backfill's -4.4 on 2025 suggested consensus features eat tails).
    Both call-time envs; unset = the validated baseline."""
    import os

    extra = [f.strip() for f in os.environ.get("EXTRA_FEATURES", "").split(",")
             if f.strip()]
    drop = {f.strip() for f in os.environ.get("DROP_FEATURES", "").split(",")
            if f.strip()}
    base = [f for f in NUMERIC_FEATURES if f not in drop]
    return base + [f for f in extra if f in CANDIDATE_FEATURES]


def build_X(df: pd.DataFrame) -> pd.DataFrame:
    # SORTED columns (2026-08-01, Addendum 34): LightGBM's split
    # tie-breaking depends on column ORDER, so the same feature set in a
    # different order trains a different (equally valid) model -- worth
    # ~+/-5 mean-best of "order luck". Discovered when adopting
    # qb_cpoe_l6 (EXTRA_FEATURES appends last; adoption inserted
    # mid-list) shifted deterministic replays. Canonical alphabetical
    # order makes candidate arms and post-adoption baselines train
    # IDENTICAL models, restoring exact A/B equivalence forever.
    X = pd.DataFrame(index=df.index)
    for c in sorted(_active_numeric_features()):
        if c in df.columns:
            X[c] = pd.to_numeric(df[c], errors="coerce")
        else:
            X[c] = np.nan
    X["position"] = pd.Categorical(df["position"], categories=POSITIONS)
    return X

```

===== FILE: src/nfl_dfs/models/components.py =====
```python
"""Component models (guide §6.2): predict opportunity and efficiency
separately, then let the simulator compose them. Losses match the label's
distribution (§7.2) — counts get Poisson, rates get plain regression on the
observed ratio with the denominator as support.

Position masks are applied at prediction time: a QB gets zero expected
targets and a WR gets zero pass attempts, no matter what the trees say.
"""

from __future__ import annotations

from dataclasses import dataclass

import lightgbm as lgb
import numpy as np
import pandas as pd

from .featureset import LGB_THREADS, build_X
from .weights import sample_weights

COUNT_PARAMS = dict(
    num_threads=LGB_THREADS,
    objective="poisson",
    metric="poisson",
    learning_rate=0.06,
    num_leaves=31,
    min_data_in_leaf=40,
    feature_fraction=0.8,
    bagging_fraction=0.8,
    bagging_freq=1,
    lambda_l2=5.0,
    verbosity=-1,
)
RATE_PARAMS = {**COUNT_PARAMS, "objective": "regression", "metric": "mae"}

# name -> (label expression, row filter, params). Rates are trained only on
# rows where the denominator exists; counts on every row of the position
# group so the zeros are learned, not imputed.
_RECEIVING = lambda df: df.position != "QB"  # noqa: E731
_PASSING = lambda df: df.position == "QB"  # noqa: E731
_ALL = lambda df: pd.Series(True, index=df.index)  # noqa: E731

# Clips keep composed distributions sane even when a model extrapolates.
RATE_CLIPS = {
    "catch_rate": (0.2, 0.95),
    "ypr": (2.0, 25.0),
    "ypc": (1.5, 9.0),
    "ypa": (4.0, 12.0),
}

COMPONENT_NAMES = [
    "targets",
    "catch_rate",
    "ypr",
    "rec_tds",
    "carries",
    "ypc",
    "rush_tds",
    "pass_attempts",
    "ypa",
    "pass_tds",
    "interceptions",
]


@dataclass
class ComponentModels:
    models: dict[str, lgb.Booster]

    def predict_components(self, df: pd.DataFrame) -> pd.DataFrame:
        X = build_X(df)
        out = pd.DataFrame(index=df.index)
        for name in COMPONENT_NAMES:
            # Slice to the booster's own training columns: a registry model
            # trained before a featureset addition must keep predicting until
            # the next weekly retrain picks the new columns up.
            out[name] = self.models[name].predict(X[self.models[name].feature_name()])

        for name, (lo, hi) in RATE_CLIPS.items():
            out[name] = out[name].clip(lo, hi)
        for name in ("targets", "rec_tds", "carries", "rush_tds",
                     "pass_attempts", "pass_tds", "interceptions"):
            out[name] = out[name].clip(lower=0.0)

        is_qb = (df.position == "QB").to_numpy()
        out.loc[is_qb, ["targets", "rec_tds"]] = 0.0
        out.loc[~is_qb, ["pass_attempts", "pass_tds", "interceptions"]] = 0.0
        return out


class _EnsembleBooster:
    """Booster-compatible average of K members trained on shuffled
    column orders (MODEL_ENSEMBLE lever). Implements the two methods the
    predict path uses: predict() and feature_name()."""

    def __init__(self, members):
        self.members = members

    def feature_name(self):
        return self.members[0].feature_name()

    def predict(self, X):
        preds = [m.predict(X[m.feature_name()]) for m in self.members]
        return np.mean(preds, axis=0)


def _fit(
    tr: pd.DataFrame,
    label: pd.Series,
    target_season: int,
    params: dict,
    num_boost_round: int,
    denom: pd.Series | None = None,
) -> lgb.Booster:
    w = sample_weights(tr, target_season)
    # A/B lever (env RATE_DENOM_WEIGHTS, off by default; data audit
    # 2026-08-03 finding 7): rate components (catch_rate, ypr, ypc, ypa)
    # weigh a 1-target rate the same as a 12-target rate, inflating rate
    # noise. With the lever on, rate rows are weighted by recency x
    # denominator so high-volume observations dominate the rate fit.
    import os as _os

    if denom is not None and _os.environ.get("RATE_DENOM_WEIGHTS"):
        w = w * denom.to_numpy(dtype=float)
    X = build_X(tr)
    # A/B lever (env MODEL_ENSEMBLE=K, off by default = 1; 2026-08-04,
    # the order-luck treatment): train K members with per-member seeds
    # AND per-member COLUMN ORDER, average predictions. Column order is
    # the measured tie-break dimension (Addendum 34: ±5 tail weeks of
    # "order luck" per rebuild); averaging over shuffled orders directly
    # attenuates the band every rebuild draws from. K=1 is byte-identical
    # to the pre-lever behavior.
    import os as _os2

    K = int(_os2.environ.get("MODEL_ENSEMBLE", "1") or 1)
    if K <= 1:
        dset = lgb.Dataset(X, label, weight=w,
                           categorical_feature=["position"])
        return lgb.train(params, dset, num_boost_round=num_boost_round)
    members = []
    for k in range(K):
        rng = np.random.default_rng(9000 + k)
        cols = list(X.columns)
        rng.shuffle(cols)
        pk = {**params, "seed": 9000 + k,
              "feature_fraction_seed": 9100 + k,
              "bagging_seed": 9200 + k, "data_random_seed": 9300 + k}
        dset = lgb.Dataset(X[cols], label, weight=w,
                           categorical_feature=["position"])
        members.append(lgb.train(pk, dset, num_boost_round=num_boost_round))
    return _EnsembleBooster(members)


def train(
    panel: pd.DataFrame, target_season: int, num_boost_round: int = 400
) -> ComponentModels:
    """Train every component on seasons before `target_season`."""
    tr = panel[panel.season < target_season]
    # A/B lever (env TRAIN_MAX_WEEK, off by default): drop late-season
    # training rows. Rest-week dynamics (playoff-locked starters on a
    # half, surprise backups) generate labels unrepresentative of the
    # weeks the user actually plays; fully-rested stars vanish entirely
    # (no stats row), so the residue is systematically weird. 16 keeps
    # ~88% of rows and excludes the modern weeks 17-18.
    import os as _os

    max_wk = int(_os.environ.get("TRAIN_MAX_WEEK", "0"))
    if max_wk:
        tr = tr[tr.week <= max_wk]
    if tr.empty:
        raise ValueError(f"no training rows before season {target_season}")

    recv = tr[_RECEIVING(tr)]
    qb = tr[_PASSING(tr)]
    caught = recv[recv.y_targets > 0]
    with_rec = recv[recv.y_receptions > 0]
    rushed = tr[tr.y_carries > 0]
    attempted = qb[qb.y_pass_attempts > 0]

    specs: dict = {
        "targets": (recv, recv.y_targets, COUNT_PARAMS, None),
        "catch_rate": (caught, caught.y_receptions / caught.y_targets,
                       RATE_PARAMS, caught.y_targets),
        "ypr": (with_rec, with_rec.y_rec_yards / with_rec.y_receptions,
                RATE_PARAMS, with_rec.y_receptions),
        "rec_tds": (recv, recv.y_rec_tds, COUNT_PARAMS, None),
        "carries": (tr[_ALL(tr)], tr.y_carries, COUNT_PARAMS, None),
        "ypc": (rushed, rushed.y_rush_yards / rushed.y_carries,
                RATE_PARAMS, rushed.y_carries),
        "rush_tds": (tr[_ALL(tr)], tr.y_rush_tds, COUNT_PARAMS, None),
        "pass_attempts": (qb, qb.y_pass_attempts, COUNT_PARAMS, None),
        "ypa": (attempted, attempted.y_pass_yards / attempted.y_pass_attempts,
                RATE_PARAMS, attempted.y_pass_attempts),
        "pass_tds": (qb, qb.y_pass_tds, COUNT_PARAMS, None),
        "interceptions": (qb, qb.y_interceptions, COUNT_PARAMS, None),
    }

    models = {
        name: _fit(rows, label, target_season, params, num_boost_round,
                   denom=denom)
        for name, (rows, label, params, denom) in specs.items()
    }
    return ComponentModels(models=models)

```

