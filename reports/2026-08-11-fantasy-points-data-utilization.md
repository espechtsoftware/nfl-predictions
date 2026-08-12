# Fantasy Points Data Suite — utilization review and recommendations

Date: 2026-08-11. Scope: the four `nfl_raw.fantasy_points_*` tables now in
BigQuery, the four frozen experiments already run against them, external
research on the underlying metrics, and new descriptive measurements taken
directly from the warehouse.

**No code was changed.** Nothing here alters, retunes, or reopens a frozen
protocol.

> **Epistemic status — read before using anything below.** The measurements in
> §3 are *outcome-viewed descriptive diagnostics*. I queried realized DK points
> directly. Under the project's standing law they are hypothesis-generating
> only. Nothing in §3 may be used to tune a dose, coefficient, threshold, fold,
> or feature set on the 107 historical slates. Every recommendation in §5 is
> written as "freeze this, then test it", and several are explicitly scoped to
> prospective 2026 grading.

---

## 1. Inventory: what the $200 actually bought

| Table | Grain | Rows | Seasons | Coverage | Genuinely new? |
|---|---|---:|---|---|---|
| `fantasy_points_route_share` | **player-week** | 27,305 (26,881 resolved) | 2022–2025, W1–18 | 93–96% of candidate roster appearances | **Yes** |
| `fantasy_points_advanced_prior` | player-season (N−1) | 3,771 | 2022–2025 | 60–67% | Partly |
| `fantasy_points_receiver_coverage_prior` | player-season (N−1) | 2,093 | 2022–2025 | 29% *supported* | Yes |
| `fantasy_points_defense_coverage_prior` | team-season (N−1) | 128 | 2022–2025 | 100% | Yes |

Unresolved-identity rates are low and stable (1.07–2.78% by season), and the
importers are hash-locked with `WRITE_EMPTY` guards. The intake discipline here
is good; nothing below is a data-quality complaint.

### 1a. The single most important structural fact

**Route share is the only weekly, non-redundant asset in the purchase.** The
other three tables are full-season aggregates usable only as strict N−1 priors,
which means for a Week 10 slate they carry information that is 10–27 games
stale and covers ~60% of the player pool.

**Amended 2026-08-11 — this limitation is an artefact of how the reports were
exported, not of the product.** The Data Suite's report screens carry a
`Week(s)` filter alongside `Schedule Week`. The operator confirmed that
restricting `Week(s)` to 1–4 changes the returned values, so the
"season aggregate" reports are in fact aggregates *over the selected week
range*. Every season-level family in §1 can therefore be re-exported at
same-season, point-in-time cumulative grain. See §5.0, which supersedes the
ranking in §5.1–5.6.

The weekly-report menu was also confirmed directly: the Data Suite exposes
exactly five weekly reports — Fantasy Points Scored, Snap Share, Route Share,
Target Share, and Pass Rate Over Expectation (Offense/Defense). There is no
weekly coverage, separation, alignment, or cornerback report to find. Combined
with §1b, the Data Suite's *natively* weekly information content for this
project is exactly one column: route share.

### 1b. Validated-but-not-ingested files: do not bother

The intake report validates Weekly Target Share, Weekly Snap Share, Weekly PROE
(Offense) and Weekly PROE (Defense). Checking each against the warehouse:

| Vendor file | Existing equivalent | Verdict |
|---|---|---|
| Weekly Target Share | `player_week_usage.target_share_last / _l4 / _jump` (PBP-derived) | Redundant |
| Weekly Snap Share | `player_week_usage.snap_share_*` (nflverse snap counts) | Redundant |
| Weekly PROE (Off/Def) | `sql/features/016_team_week_context.sql` computes `proe_l4` against a league-expectation baseline | Redundant |

Ingesting these would add vendor-identity risk and importer surface for no new
information. Recommend closing them as acquisition-complete/not-needed and
recording that in the intake report, so a future session does not re-litigate
it.

The one genuine gap in that list is **Red Zone route participation**, which
lives inside the Separation-by-Coverage export's Red Zone block. `player_week_usage`
has red-zone *targets* and *carries* from PBP, but not red-zone *route
participation* — who was on the field running a route inside the 20. Since
touchdowns are what turn a 15-point game into a 30-point game, this is the one
remaining vendor field with a clear mechanism. It is season-aggregate, so it
inherits the staleness problem in §1a.

---

## 2. What the four completed experiments established

| Experiment | Disposition | Headline number |
|---|---|---|
| Route Share player-tail | **passes** | Aggregate 30-pt Brier 0.00968358 → 0.00965675 (−0.28% rel.); WR/TE-only 0.00763166 → 0.00760188; coverage 82.4%/83.0% |
| Advanced prior-season (QB/RB/WR/TE) | **fails** | Aggregate 30-pt Brier improved marginally, but QB (0.024372→0.024432) and RB (0.018832→0.018881) worsened; only WR/TE improved. 20-pt Brier and MAE both worsened |
| Coverage-fit (receiver × opponent shell) | **passes** | Aggregate 30-pt Brier 0.01813348 → 0.01809495; 2025 fold *worsened* 0.20%; 3,392 rows, **62 observed 30-point events**; max abs. Spearman 0.0596 |
| Route-tail / coverage-tail candidate unions | preregistered, **not yet launched** | `proj_tourney + 30 × delta_30`, 12 candidates, 2024–2025 only |

Two observations about these dispositions before adding anything.

**The Route Share pass is real but the effect size is being read at the wrong
altitude.** A 0.28% relative Brier improvement pooled over 13,288 RB/WR/TE
player-weeks is what you get when a strong signal is diluted across a population
where most members' route share is already implied by their snap share. §3 shows
where the signal actually concentrates.

**The coverage-fit pass is statistically negligible and should be treated as
such.** 62 events across 3,392 rows, an aggregate Brier delta of 0.0000385
(0.21% relative), one of two held-out folds worsening, and maximum absolute
feature Spearman of 0.0596. The report itself says "a narrow ensemble-calibration
signal, not evidence that a single coverage metric should be hand-ranked" —
that is the right reading, and it should be extended one step further: with 62
events this is indistinguishable from noise. The union it licenses is
underpowered before it launches. Running it as frozen is fine (the protocol is
clean); expecting it to mean anything is not.

---

## 3. New measurements from the warehouse

Method: strictly-prior route share via `LAG(route_share) OVER (PARTITION BY
gsis_id ORDER BY season, week)` — the same cross-season carry-forward the frozen
protocol uses — joined to `nfl_features.player_week_actuals` for raw outcomes
and to corrected K1 snapshot panel `20260810-lockfix-e80-k1-8677d21` for
projection-matched comparisons. Seasons 2022–2025.

### 3.1 Route share is a powerful raw ceiling discriminator

Prior-week route share vs realized DK points, all RB/WR/TE:

| pos | prior route share | n | mean DK | ≥20 | ≥30 | q99 |
|---|---|---:|---:|---:|---:|---:|
| WR | <20% | 2,904 | 1.70 | 0.69% | 0.00% | 16.6 |
| WR | 60–80% | 2,210 | 8.72 | 9.19% | 1.95% | 34.1 |
| WR | **80%+** | 2,652 | 12.80 | **20.02%** | **5.84%** | **41.1** |
| TE | <20% | 2,745 | 1.27 | 0.04% | 0.04% | 11.4 |
| TE | **80%+** | 400 | 11.40 | **15.00%** | **2.25%** | **33.3** |
| RB | <20% | 3,208 | 3.11 | 1.37% | 0.22% | 22.1 |
| RB | **80%+** | 29 | 20.69 | **41.38%** | **20.69%** | **44.7** |

Monotone at every step, in every position, on both the mean and the tail. The
q99 spread for WR is 16.6 → 41.1 points.

### 3.2 But it is nearly collinear with a feature the model already has

| pos | n | corr(route, snap) | corr(route, DK) | corr(snap, DK) |
|---|---:|---:|---:|---:|
| WR | 9,561 | **0.967** | 0.542 | 0.530 |
| TE | 5,862 | 0.896 | **0.597** | 0.529 |
| RB | 6,131 | 0.888 | 0.568 | **0.601** |

For WR, route share and snap share are 0.967 correlated — most of §3.1 is
already available to the model through `snap_share_last`. **TE is the exception**:
route share is meaningfully decoupled from snaps (a TE can play 90% of snaps and
run routes on 45% of dropbacks because he is blocking) and it out-predicts snap
share. For RB the ordering reverses.

This has a direct consequence: *the incremental value of the purchase is
TE-first, WR-second, RB-least* — and the missed-winner audit found TE
over-represented in the misses (11 of 36 omitted winner slots for a position
that occupies 1 of 9 roster spots).

### 3.3 The decisive test: at matched projection, high-route players beat their projection

Corrected K1 snapshots, RB/WR/TE, banded by the production `mean_projection`:

| projection band | route share | n | mean proj | mean actual | **residual** | ≥20 | ≥30 |
|---|---|---:|---:|---:|---:|---:|---:|
| <6 | lo <50% | 8,749 | 1.99 | 2.26 | +0.27 | 0.47% | 0.03% |
| <6 | **hi 75%+** | 261 | 4.45 | 5.25 | **+0.80** | 3.07% | **0.00%** |
| 6–10 | lo <50% | 1,058 | 7.75 | 7.96 | +0.21 | 7.28% | 1.98% |
| 6–10 | **hi 75%+** | 920 | 8.24 | 9.20 | **+0.96** | 9.02% | 1.96% |
| 10–14 | lo <50% | 675 | 11.86 | 11.88 | +0.01 | 14.37% | 1.78% |
| 10–14 | **hi 75%+** | 1,136 | 11.96 | 12.71 | **+0.75** | 18.13% | **4.31%** |
| 14+ | lo <50% | 345 | 16.11 | 16.25 | +0.14 | 31.01% | 9.28% |
| 14+ | **hi 75%+** | 735 | 16.65 | 17.24 | **+0.59** | 33.06% | 11.84% |

Three findings, in order of importance:

1. **The production projection systematically under-projects high-route-share
   players by roughly +0.6 to +1.0 points at every projection level**, while
   low-route-share players sit at ~0. This is a sign-stable, magnitude-stable
   mean bias, not a tail artifact.
2. **The 30-point lift concentrates in the 10–14 projection band: 4.31% vs
   1.78% at essentially identical mean projection (11.96 vs 11.86)** — a 2.4×
   tail lift on a properly matched comparison. This is the mid-priced starter
   at full route share.
3. **In the sub-6 projection band there are effectively zero 30-point events
   regardless of route share** (0.00% for hi-route, n=261). The cheap end of
   the pool has no 30-point mass to capture.

The same pattern holds within every target-share band, and is *largest* among
high-target players — so this is not a "role without volume yet" breakout
detector:

| prior target share | route share | n | mean proj | residual | ≥30 |
|---|---|---:|---:|---:|---:|
| <12% | lo <75% | 6,700 | 2.55 | +0.25 | 0.10% |
| <12% | hi 75%+ | 414 | 7.95 | +0.65 | 1.21% |
| 12–20% | lo <75% | 1,174 | 6.91 | −0.05 | 0.68% |
| 12–20% | hi 75%+ | 798 | 10.10 | +0.37 | 3.01% |
| 20%+ | lo <75% | 549 | 9.83 | +0.11 | 3.10% |
| 20%+ | **hi 75%+** | 1,630 | 12.82 | **+1.00** | **7.06%** |

Position decomposition at projection ≥6 (note: bucket mean projections differ
here, so read the residual column, not the raw rates):

| pos | route | n | mean proj | residual | ≥30 |
|---|---|---:|---:|---:|---:|
| WR | hi 75%+ | 2,286 | 12.13 | +0.76 | 5.99% |
| WR | lo <75% | 1,155 | 9.36 | −0.24 | 1.82% |
| TE | hi 75%+ | 456 | 10.60 | +0.71 | 1.97% |
| TE | lo <75% | 720 | 8.66 | −0.15 | 1.39% |
| RB | hi 75%+ | 49 | 16.87 | **+2.10** | **16.33%** |
| RB | lo <75% | 2,248 | 11.86 | +0.29 | 4.49% |

### 3.4 Two hypotheses that do *not* survive contact with the data

**Targets-per-route (TPRR) is already priced.** Using `target_share_last ÷
prior-week route_share` as a TPRR proxy (exact up to a team-week
dropback constant), WR/TE at projection ≥6:

| TPRR proxy band | n | mean proj | residual | ≥20 | ≥30 |
|---|---:|---:|---:|---:|---:|
| <0.15 | 613 | 8.66 | −0.05 | 7.34% | 1.14% |
| 0.15–0.22 | 886 | 9.92 | +0.58 | 12.98% | 3.39% |
| 0.22–0.30 | 1,148 | 10.82 | −0.21 | 12.28% | 2.87% |
| 0.30+ | 1,417 | 12.20 | +0.35 | 19.83% | **6.56%** |

The raw ceiling gradient is strong (1.14% → 6.56% at 30+), but the **residual is
non-monotone and near zero** — the projection already absorbs TPRR through its
existing target-share features. Route *level* carries the incremental signal;
the TPRR *ratio* does not. Do not build a TPRR feature expecting it to add
what §3.3 adds.

**The RB route-minus-snap gap is not a receiving-back detector.** Among RBs
with snap share ≥40%, bucketing on (route share − snap share) gives 20+ rates of
19.32% / 22.06% / 19.29% across gap<−15pp / −15..0 / ≥0. Flat. Drop this idea.

**Route-share jump is non-monotone in the tail.** For players ≤$5,000, week-over-week
route-share jump vs 20+ rate: WR 2.40% (<10pp) → 4.01% (10–25pp) → 2.39% (25pp+);
TE 1.40% → 3.43% → 2.76%; and at 30+ the largest-jump bucket is 0.00% for both.
The frozen `fp_route_share_jump` enters the diagnostic as a **linear** Ridge/
logistic term, which cannot represent a signal that rises then reverses. The
mechanism is straightforward: a 25pp+ jump usually means the player started from
a tiny base, so his post-jump *level* is still low — and level is what matters.

---

### 3.5 Coverage matchup: testing the intuition directly

The operator asked whether coverage matchup should matter more than the
coverage-fit gate's tiny effect implies. Two clarifications and a measurement.

**The "cornerback coverage" export contains no cornerbacks.**
`wrCoverageMatchupExport.csv` (375 rows) is a *team coverage-shell* report:
per-shell receiver splits (`FP/RTE`, `RTE %`, `YPRR`) paired with the opponent
team's deployment rates (`DEF MAN %`, `DEF FP/DB`, …) and a `COV GRADE`. There
is no CB identity, shadow rate, or individual assignment anywhere in it.

**Both premises of the intuition hold.** Measured on the four ingested seasons,
WR/TE with ≥200 overall, ≥50 man and ≥100 zone routes:

| quantity | value |
|---|---:|
| y/y correlation, overall YPRR (skill baseline) | 0.587 |
| y/y correlation, man-minus-zone YPRR edge | **0.283** (305 pairs) |
| y/y correlation, man-minus-zone TPRR edge | 0.357 |
| SD of man-minus-zone YPRR edge | 0.736 |
| defensive man rate: min / mean / max | 0.106 / 0.261 / 0.464 |
| SD of defensive man rate | 0.077 |
| y/y correlation, defensive man rate | 0.44 |

"He is a man-beater" is a real, persisting trait, and defenses differ
persistently in how much man they play. Neither is noise.

**But the product of the two is small.** Shrinking the receiver edge by its
reliability gives a predictable edge SD of `0.736 × 0.283 ≈ 0.21` YPRR. At
~26.4 routes per game:

| matchup extremity | rec. yards/game | ≈ DK points |
|---|---:|---:|
| 1 SD receiver × 1 SD defense | 0.42 | 0.04–0.09 |
| 2 SD × 2 SD | 1.69 | 0.17–0.34 |
| 3 SD × 3 SD | 3.81 | 0.38–0.76 |

Route share's measured effect is +0.75 to +1.00 DK points (§3.3). Coverage-shell
matchup reaches that only at a near-maximal 3-SD-by-3-SD pairing.

This arithmetic **explains** the coverage-fit result rather than contradicting
it: an aggregate Brier delta of 0.0000385 and maximum feature Spearman of
0.0596 is what a ~0.05-point effect looks like at 62 events. The diagnostic was
sound; the effect is genuinely that size.

**The honest limit of this finding.** Shell coverage is a diffuse, team-average
property, averaged across every defender a receiver faces. An individual
shadow matchup — one elite corner on one receiver for 70% of routes — is a
different, concentrated mechanism, and nothing in this dataset measures it. The
conclusion supported here is "coverage *shell* matchup is small", **not**
"coverage is small". If a CB-level or shadow-rate source is ever identified, it
is a separate hypothesis and should be ranked above the shell family.

## 4. What the external research says about these metrics

- **TPRR** has recognized thresholds (~20% baseline, 25–30% excellent, 30%+
  elite; top-24 WRs almost always exceed 20%) and is described as a leading
  indicator that precedes production by a week or two. Consistent with §3.4:
  it is a good *descriptor*, and by now a widely-consumed one, which is exactly
  why a market-adjacent projection already prices it.
- **YPRR** has year-over-year stability ≈0.51, while **expected YPRR** reaches
  ≈0.67 — the expected/volume-based version is the more stable quantity. This
  favours `fp_adv_rec_xfp_per_route` (already in `advanced_prior`) over realized
  YPRR for any future prior-season work.
- **Route share is itself a conditioning variable in the published work**: for
  tight ends restricted to 65%+ route share, YPRR rises to second in predictive
  power with ≈0.65 correlation to next-season PPG. This independently supports
  §3.2's TE-first conclusion and argues that route share's best use is as a
  *gate/segment definer*, not only as a linear regressor.
- **Man vs zone**: practitioners report more confidence in a receiver's man
  performance than his zone performance. The frozen coverage-fit features blend
  both symmetrically; if that mechanism is ever revisited under a new protocol,
  the man component is the better-motivated half.
- **aDOT / air-yard share**: aDOT is described as characterising *role* more
  than predicting points, with >10 aDOT marking a volatile high-ceiling profile,
  and 30%+ air-yard share historically associating with ~14.4 FPG. For a
  tail-first objective this is the right shape of signal — it identifies
  variance, not mean — which is an argument for using air-yard share as a
  *dispersion* input rather than a mean input.

---

## 5. Recommendations

Ranked by expected value per unit of cost and risk.

### 5.0 Re-export the season-aggregate reports at point-in-time cumulative grain

**Added 2026-08-11. This changes what the other three tables are worth and
should be resolved before §5.4 is considered.**

The `Week(s)` filter is confirmed to change returned values. Every family that
§1 recorded as an immovable season aggregate can therefore be re-exported as a
same-season cumulative view. That converts them from strict N−1 priors at
~60% coverage — 12 to 29 games stale for a mid-season slate — into same-season,
properly-lagged features covering any player with a few games.

Design notes, in order of importance:

1. **Do the opponent join in our own SQL, never from the vendor's `OPP`
   column.** The quarantined QB/WR matchup exports failed precisely because the
   vendor pairs a chosen `Schedule Week`'s opponent with whatever stat window is
   selected, and an offseason pull produced completed-season stats against Week
   1 opponents. Exporting the *base player reports* (Advanced Receiving, Man vs
   Zone) at a week cutoff and joining opponents from `nfl_raw.schedules`
   sidesteps that failure mode entirely.
2. **Confirm the filter's semantics before bulk-exporting.** Does
   `Week(s) = 5–8` return only weeks 5–8, or weeks 1–8? If it is a true
   arbitrary multi-select, it yields *windowed* features (a last-four-games
   view) directly comparable to the existing `_l4` family, which is more useful
   than cumulative alone. Check this on one file first.
3. **Do not export all 17 cutoffs.** Cumulative values move fast early and
   plateau; cutoffs at weeks {3, 5, 7, 9, 11, 13, 15, 17} give 8 exports per
   season, 32 per report family across 2022–2025 — an evening of work, not a
   project. For target week W, use the largest cutoff ≤ W−1 and assert that
   inequality per row exactly as the existing importers do.
4. **Pick one family first.** Ranked by expected value:
   - **Advanced Receiving is the clear first choice.** Its mechanism failed on
     *data quality* grounds (N−1 staleness plus 60% coverage), not on mechanism
     grounds, and it contains the three fields most directly tied to ceilings:
     air-yard share, first-read rate, and `XFP/RR` — the last being the metric
     external research identifies as the most stable of the family (≈0.67 y/y
     versus ≈0.51 for realized YPRR). Same-season cumulative at ~90% coverage is
     **materially different data, not a forbidden subset retry** of the closed
     test, and should be preregistered as such and stated explicitly.
   - Man vs Zone / Coverage second, and only if Advanced pays — §3.5's
     arithmetic caps the shell mechanism near 0.05–0.09 DK points, and better
     input freshness raises input quality without raising that ceiling.
   - Separation by Routes / Breaks / Alignment last. These are large sparse
     grids with the weakest football-motivated prior and the highest
     search-overfitting risk. Do not export them speculatively.
5. **Early-season fallback.** In Weeks 1–3 the same-season cumulative view is
   empty or unstable, so the N−1 prior remains the fallback there. Reuse the
   existing `fp_route_cross_season` pattern: serve the cumulative value when
   ≥3 games are available, else the prior, with an explicit indicator column so
   the model can learn the difference rather than silently mixing the two.
6. **This also improves the live path.** Prospectively this is one extra
   Wednesday export with `Week(s) = 1..W−1` — cheap, and unlike an N−1 prior it
   is actually informative in-season.

Expected value is real but should not be oversold: it raises the *quality* of
inputs whose measured mechanism sizes are unknown (Advanced) or small (§3.5).
Route share (§5.1) remains the larger measured signal and should not be
displaced in the queue by this work.

### 5.1 Put route share in the projection model, not only in a candidate objective

**This is the headline recommendation and it is not what either completed
experiment or either pending union tests.**

The measured defect in §3.3 is a *mean bias*: high-route-share players beat the
production projection by ~+0.6 to +1.0 points, consistently, across every
projection band, every target-share band, and every position. The natural repair
is to give the weekly training feature set the route inputs so the projection
stops making that error.

What has actually been tested instead:

- the **player-tail diagnostic** bolted a separate logistic classifier on top of
  a frozen `mean_projection` and measured 30-point Brier — it can detect that the
  bias exists but cannot fix it;
- the **candidate union** uses `proj_tourney + 30 × delta_30` to tilt *generation*
  — it changes which lineups get built, not what any player is projected to score.

Neither touches the mean. A projection-side test is a different intervention with
a much larger surface: it propagates into `proj`, `proj_tourney`, the simulator's
marginals, salary-value ranking, ownership estimates, and every candidate
generator at once.

Suggested frozen protocol (write it before looking at anything further):

1. Add exactly the four already-registered route inputs (`fp_route_share_last`,
   `_l4`, `_jump`, `_cross_season`) to `player_week_training` /
   `player_week_inference` behind an `EXTRA_FEATURES`-style gate, with the
   existing leakage checks asserting source `(season, week) < target`.
2. Grade at the **model** layer first, walk-forward by season on 2023–2025:
   residual MAE, CRPS, and — because the objective is tail-first — q90/q95/q99
   exceedance rates, reported separately for the high-route segment and the
   rest. The specific thing to prove is that the +0.6/+1.0 residual gap in
   §3.3 collapses toward zero without the low-route segment degrading.
3. Only then a candidate/oracle arm, then one fixed-budget lineup panel.

Note the interaction with the standing production stack: 2022 is the first
season with route data, so a route-fed model cannot serve 2019/2021 replay
slates. Any panel is therefore a **2022–2025 comparison**, which halves the
already-thin high-threshold event counts. Preregister that the comparison is on
the 2022–2025 subset with its own control, rather than silently mixing.

### 5.2 Use route share as a segment definer for tail calibration

This is the direct bridge to the previously identified miscalibration (ordinary
players clear q90/q99 at 7.37%/0.72% against nominal 10%/1%).

§3.3 shows high-route-share players are under-projected in the *mean*. §3.1 shows
they also have a materially fatter realized tail (WR q99 41.1 vs 16.6). A single
global conformal multiplier cannot express both. Route share is an excellent,
cheap, pre-lock segment variable for a segment-conditional quantile
recalibration: `position × route-share tercile` is a defensible three-way split
with adequate cell counts in every position (WR 80%+ alone has n=2,652).

This is complementary to §5.1, not an alternative: §5.1 fixes the mean, §5.2
fixes the dispersion. Do them as separate gated steps so their effects are
separable.

### 5.3 Concentrate the signal where the 30-point mass is

If a future generation-side arm is designed after the currently frozen unions
resolve, §3.3 argues for a **projection-band-conditional** application rather
than a uniform bonus:

- the sub-6 projection band produced **zero** 30-point events among high-route
  players (n=261), so a uniform `+30 × delta_30` bonus spends candidate budget
  on a population with no accessible tail;
- the payoff band is projection 10–14 (4.31% vs 1.78% at matched projection),
  i.e. mid-priced starters at full route share.

I want to be explicit about protocol here: **the currently frozen route-tail
union should run exactly as written.** It is preregistered, its coefficient and
dose are frozen, and changing it now on the basis of §3 would be precisely the
outcome-driven tuning the project prohibits. The recommendation is that §3.3 be
recorded *now*, before that union's result is known, as the predeclared
explanation to consult afterward — and as the design basis for a successor arm
if one is ever licensed. If the union fails, §3.3 offers a mechanism rather than
a mystery; if it passes, §3.3 predicts the gain came from the mid-band.

### 5.4 Treat the prior-season tables as an early-season-only hypothesis

The Advanced prior mechanism failed its pooled multi-position gate and is
closed. A *subset retry* is forbidden and I am not proposing one.

There is a distinct, football-motivated population it never tested. Season N−1
aggregates are most valuable exactly when no same-season data exists — Weeks
1–4 — and least valuable in Week 15 when 14 games of live data are available.
The completed diagnostic pooled all weeks, so the strong late-season control
features swamped the prior. **Restricting the evaluation population to early-season
weeks is a different question, not a subset of the same one**, and it can be
preregistered cleanly with the same fields, folds, model and gate as the failed
test — changing only the row population, declared in advance.

Expected value is modest and should be stated as such: coverage is 60–67%, and
the effect must be large enough to matter across only ~4 weeks per season. Rank
this below §5.1 and §5.2. If it is run, the external research argues for
`fp_adv_rec_xfp_per_route` (expected YPRR, stability ≈0.67) over realized
efficiency fields.

### 5.5 Close out the redundant vendor families explicitly

Record in the intake report that Weekly Target Share, Weekly Snap Share, and
both Weekly PROE families are **acquisition-complete and deliberately not
ingested** because `player_week_usage` and `016_team_week_context.sql` already
supply equivalent PBP-derived series. This prevents a future session from
spending a build cycle on redundant importers, and it narrows the 2026 weekly
download checklist to the one report that matters.

### 5.6 Establish the 2026 weekly route-share operating path before Week 1

Route share is the only vendor asset with live value, and it is worthless if it
cannot be refreshed before lock. Before the season starts, confirm and document:

- which vendor view produces the weekly Route Share export in-season, and when
  it updates relative to Sunday 1 p.m. ET (the intake report notes vendor data
  is postgame; a Week N slate needs Week N−1 routes, so a Monday–Wednesday
  refresh is sufficient — but this must be verified, not assumed);
- that the export schema matches the frozen 25-column contract the importer
  requires;
- the fallback when the file is late or malformed. Because §3.3's effect is a
  ~1-point mean bias rather than a lineup-flipping constraint, the correct
  fallback is to serve the model without route features, labeled — not to delay
  the slate.

The QB/WR Coverage Matchup and OL/DL Matchup exports were correctly quarantined
as schema samples after their opponent pairs proved to reproduce the 2025
schedule. Keep that verification step as a permanent precondition on any
prospective vendor matchup file: **mechanically check exported opponent pairs
against the target-season schedule before the file is allowed near a projection.**

---

## 6. Power caution specific to this data

Two of the four experiments turn on very small event counts, and the pending
unions are smaller still.

- Coverage-fit: 62 observed 30-point events, aggregate Brier delta 0.0000385,
  one fold worsening. Not meaningfully distinguishable from noise.
- Both pending unions add **12 candidates on 2024–2025 slates only** — 36 of the
  107 slates. The adopted book's control counts on the full panel are 12/6/3/2 at
  210/220/230/240; restricted to two seasons those counts are roughly 2–4/1–2/1/0.
  A promotion decision made at 230 or 240 on a 36-slate subset is a one- or
  two-event decision.

Recommendation, consistent with the guardrail proposed in the strategy review:
require the paired weekly-maximum comparison (wins/ties/losses over the treated
slates, with a sign test) to be reported alongside the threshold grid for both
unions, and do not promote on a threshold whose control count within the treated
subset is below ~5 unless that paired comparison is also favourable. This does
not weaken the tail-first law; it prevents a 36-slate, 12-candidate arm from
being adopted on a single realized event.

---

## 7. Summary

| Asset | Best use | Priority |
|---|---|---|
| Route share (weekly) | **Feature in the projection model** — it corrects a measured +0.6/+1.0 pt mean bias | 1 |
| Route share (weekly) | Segment definer for position × route-tercile tail recalibration | 2 |
| **Advanced Receiving, re-exported cumulatively** | Same-season point-in-time via `Week(s)`; `AY Share` / `1READ %` / `XFP/RR`; distinct from the closed N−1 test | 3 |
| Route share (weekly) | Projection-band-conditional generation tilt (10–14 band), successor arm only | 4 |
| Man vs Zone / coverage, re-exported cumulatively | Only if Advanced pays; §3.5 caps the mechanism near 0.05–0.09 DK pts | 5 |
| Advanced prior (N−1) | Superseded by the cumulative re-export; early-season fallback only | 6 |
| Receiver/defense coverage prior (N−1) | Underpowered (62 events); let the frozen union run, expect nothing | 7 |
| Separation by Routes / Breaks / Alignment | Sparse grids, weak prior, high search risk — do not export speculatively | — |
| Weekly Target/Snap/PROE exports | Redundant — close them out | — |
| Red-zone route participation | Only unexploited field with a clear TD mechanism | watch |
| CB-level / shadow coverage | Not present in this product; a separate hypothesis if ever sourced | watch |

The one-sentence version: **the purchase's value is concentrated almost entirely
in weekly route share, its measured effect is a systematic under-projection of
high-route-share players, and the highest-leverage response is to feed it to the
projection model rather than to bolt a classifier or a generation bonus on top
of a projection that is still making the error.**

The one-sentence amendment (2026-08-11): **the `Week(s)` filter means the
season-aggregate families are not permanently stale — they can be re-exported
at same-season point-in-time grain, which makes Advanced Receiving worth one
properly-preregistered second look, and which is the only thing that has
changed the value of this purchase since the four experiments closed.**

---

## Sources

Internal: `reports/2026-08-10-fantasy-points-data-intake.md`,
`-route-share-experiment.md`, `-route-tail-union.md`,
`-prior-season-advanced-tail.md`, `-coverage-fit-experiment.md`,
`-coverage-tail-union.md`; executions `fantasy-points-route-diagnostic-rthzs`,
`fantasy-points-advanced-diagnostic-vb9xz`,
`fantasy-points-coverage-diagnostic-wbwlf`; panel
`20260810-lockfix-e80-k1-8677d21`; `sql/features/016_team_week_context.sql`.

External:

- [What is Targets Per Route Run (TPRR)? — Fantasy Life](https://www.fantasylife.com/articles/redraft/what-is-targets-per-route-run-tprr)
- [Targets Per Route Run Report — The Fantasy Footballers](https://www.thefantasyfootballers.com/analysis/targets-per-route-run-report-2025-season-preview-fantasy-football/)
- [Revisiting Yards Per Route Run — SumerSports](https://sumersports.com/the-zone/revisiting-yards-per-route-run/)
- [The Most Predictable Wide Receiver Stats — 4for4](https://www.4for4.com/2024/preseason/most-predictable-wide-receiver-stats)
- [Statistically Significant: Yards/Route Run — Fantasy Points](https://www.fantasypoints.com/nfl/articles/2024/statistically-significant-yards-per-route-run)
- [What Matters For Tight Ends — Fantasy Life](https://www.fantasylife.com/articles/fantasy/what-matters-for-tight-ends-in-fantasy-football-2026-ypg)
- [Fantasy Football WR Report: man/zone coverage performance — PFF](https://www.pff.com/news/fantasy-football-wide-receiver-report-man-zone-coverage-performance-nfl-week-14-2025)
- [Examining Wide Receiver Metrics — SumerSports](https://sumersports.com/the-zone/examining-wide-receiver-metrics/)
- [The importance of YAC and aDOT — PFF](https://www.pff.com/news/fantasy-football-yac-adot-top-players-2025)
- [PlayerProfiler Guide to NFL Advanced Stats, Vol. 2: WRs](https://www.playerprofiler.com/article/playerprofilers-guide-to-nfl-advanced-stats-metrics-vol-2-wide-receivers/)
