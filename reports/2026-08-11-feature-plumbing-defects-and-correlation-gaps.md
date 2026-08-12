# Feature plumbing defects and correlation gaps

Date: 2026-08-11. Audit of the post-calibration state. **No code was changed.**
Findings A–C are code/schema audits with no outcome selection. Findings D–E are
warehouse coverage counts, also outcome-free.

---

## Context: what changed, and why it changes the target

The per-position final-served calibration passed and was adopted — the first
scoring gain in this sequence (200: `11→13`, pool oracle `16→19`, 210+
preserved, WR q99 `1.881%→1.439%`). The stage decomposition confirmed the
imbalance originates in the TabPFN cache, and the Route final-served result
established the structural fact that governs everything below:

> **TabPFN marginal coverage is 100%. `_tabpfn_marginals` rank-remaps each
> player's draws onto that player's cached TabPFN quantiles. Therefore, for
> covered rows, the served per-player marginal is entirely TabPFN's, and the
> LightGBM component models contribute only the *ranks* — the copula.**

That splits the system into two channels which must be targeted differently:

| channel | owner | what changes it |
|---|---|---|
| **per-player marginal** (levels, tails, 30-pt probability) | `features.tabpfn_projections` | `scripts/tabpfn_gen/features.txt` + the GPU job |
| **joint structure** (who booms together, stack value) | LightGBM components → possession sim | `featureset.NUMERIC_FEATURES` |

**Every feature arm since TabPFN marginals went default-on (2026-08-04) added
features to the second channel and was then judged by a metric that reads the
first.** That is a plausible unified explanation for the run of nulls, and it is
consistent with the Route result's own interpretation section.

---

## A. `features.txt` is out of sync with `NUMERIC_FEATURES` — a panel-proven feature is missing

```
model NUMERIC_FEATURES: 35
tabpfn features.txt   : 33
IN MODEL, MISSING FROM TABPFN: ['net_rest_diff', 'body_clock_hour']
IN TABPFN, NOT IN MODEL      : []
order identical for shared subset: True
```

The two missing entries are the **SCHED pair** — `featureset.py` records them as
"ADOPTED 2026-08-04 (final candidate panel, Addendum 49): +6 tails vs same-build
post-QF control (24 vs 18), best 2019 and 2025 of the panel." That is one of
only **two** features ever to pass a six-season panel; the other,
`qb_cpoe_l6`, *is* present in `features.txt`.

Consequence: because TabPFN owns the served marginal at 100% coverage, **the
SCHED pair contributes nothing to the served per-player distribution in
production.** It survives only through the rank-coupling channel. A
panel-proven, adopted feature is operating at partial effect.

Timeline note: SCHED was adopted 2026-08-04 (Addendum 49) and TabPFN marginals
went default-on 2026-08-04 (Addendum 50) — the same day. The panel that earned
SCHED its adoption very likely ran in a regime where LightGBM marginals still
reached the served distribution. Its measured `+6 tails` may not describe
current production behaviour.

**Sequencing warning.** The frozen TabPFN active-label protocol requires both
arms to share "the same … feature list." Correcting `features.txt` inside that
regeneration would confound two changes in one cache. Run the active-label arm
exactly as frozen, then treat the feature-list sync as its own separately
preregistered arm on the next regeneration. Do not fold them together, and do
not quietly add the two columns while the GPU job is already running.

## B. Nothing enforces the sync

```
grep -rln "features.txt" tests/ src/   →  (no results)
```

`research/config_manifest.py` — which the project requires to show zero
discrepancies, with tests enforcing it — does not cover the TabPFN feature
list. Two feature lists must be kept identical by hand, in two different
languages (Python constant, text file baked into a separate Docker image), with
no check.

**Recommendation:** add `NUMERIC_FEATURES ↔ scripts/tabpfn_gen/features.txt` to
the config manifest with an exact set-and-order assertion. This is a few lines,
it is offline-testable, and it permanently closes a class of silent defect that
has already fired once. Do this regardless of what happens with A.

## C. TabPFN's feature list excludes every candidate feature

`features.txt` contains none of the 19 `CANDIDATE_FEATURES`: no `xfp_l4`, no
`vacated_capture_tgt/car`, no `team_top2_target_share_l6`, no FTN block
(`pa_rate_l6`, `opp_blitz_rate_l6`, `opp_pressure_rate_l6`), no fast-role
fields, no route share.

So the correct home for a **mean/tail** feature experiment is `features.txt`
and the GPU regeneration — not `EXTRA_FEATURES` on the component models. The
existing `EXTRA_FEATURES` mechanism tests the copula channel. Both are
legitimate experiments; they answer different questions and neither has been
labelled as such.

---

## D. `qb_cpoe_l6` reaches no pass-catcher

Coverage in `nfl_features.player_week_training`, 2022+:

| position | rows | % `qb_cpoe_l6` populated | % `neutral_pass_rate_l6` | % `separation_l4` |
|---|---:|---:|---:|---:|
| QB | 7,171 | **29.4%** | 94.6% | 0.0% |
| RB | 12,533 | **0.0%** | 94.8% | 0.0% |
| TE | 11,921 | **0.0%** | 94.9% | 17.5% |
| WR | 20,682 | **0.0%** | 94.8% | 27.6% |

Two observations.

**Team pass-*volume* context is broadcast to pass-catchers; QB *quality*
context is not.** `neutral_pass_rate_l6` is a team value present on ~95% of all
rows. `qb_cpoe_l6` is present on QB rows only. Every WR and TE is therefore
projected with zero information about how well his quarterback throws.

This matters specifically because of the measured co-boom structure: the
dependence is star-shaped through the QB (QB exceeds his own p90 → TE exceeds at
**2.50×**, WR at **2.34×**, RB at 1.31×). The quarterback is the hub, and the
hub's quality is invisible to every spoke.

**`qb_cpoe_l6` is only 29.4% populated even on QB rows.** Worth a separate look
— a feature that passed a six-season panel while present on under a third of its
own position's rows is either very strong where it exists or is picking up a
selection effect.

## E. Wind and temperature are materialized and unused

`nfl_features.game_weather` carries `temp_f`, `wind_mph`, `is_dome`. Only
`is_dome` is in `NUMERIC_FEATURES` (and in `features.txt`).

Wind is the classic passing-game suppressor and, unlike most features, it is a
**game-level** variable — it moves every player in a game together. That makes
it relevant to *both* channels: it should compress a stack's joint upside, not
just each player's mean. It is the cheapest unused correlated-context variable
in the warehouse.

---

## Correlation gaps worth testing, ranked

These are pairs of data we already hold that are currently used independently
and would plausibly be stronger combined. All are outcome-blind proposals; none
has been tested.

1. **QB process → his pass-catchers.** Broadcast the team QB's `qb_cpoe_l6`
   (and, if wanted, `qb_time_to_throw_l6`, already a materialized candidate) onto
   RB/WR/TE rows as a team-level column. Highest expected value of anything in
   this document: it is the hub variable of the measured dependence structure,
   it costs one SQL join, and the data already exists. Test it in
   **`features.txt`** (marginal channel), since the target is each
   pass-catcher's level and tail.
2. **`wind_mph` as a game-level context feature.** Materialized, unused,
   mechanically motivated, and relevant to the joint channel. Cheap.
3. **Route share × `team_vacated_target_share`.** Vacancy says opportunity
   opened; route share says who is actually on the field to absorb it. Neither
   alone identifies the beneficiary. `vacated_capture_tgt` (materialized, never
   tested) attempts this using empirical position/depth capture rates — route
   participation is the more direct denominator. Note the standing constraint:
   route share's exact four-field contract is closed historically and reserved
   for the 2026 shadow; an interaction term is a different construct and needs
   its own preregistration, not a reopening.
4. **`implied_team_total` × `team_top2_target_share_l6`.** A high team total says
   the offence scores; concentration says who collects it. The product is the
   direct ceiling construct and `team_top2_target_share_l6` has never been
   tested at all. This is a **copula-channel** feature — concentration is
   literally a statement about joint structure — so test it via
   `EXTRA_FEATURES`, not `features.txt`.

Explicitly **not** recommended: TPRR (`target_share ÷ route_share`) — measured
earlier as already priced, residual near zero; and any further coverage-shell
matchup construct — bounded at ~0.05–0.09 DK points.

---

## Suggested order

1. **B** (manifest test) — a few lines, offline, prevents recurrence.
2. Run the frozen **TabPFN active-label** arm exactly as written. It is the
   best-motivated open item: ~46% of TabPFN's training rows are synthetic
   inactive zeros, which is a strong candidate cause of the WR q99 compression
   that the per-position calibration is currently correcting downstream.
3. **A** (feature-list sync) as its own arm on the next regeneration.
4. **D1** (QB quality → pass-catchers) as the first new marginal-channel
   feature arm, in `features.txt`.
5. **E**, then **D4**, then **D3**.

Finally: with the two channels now distinguished, every future feature protocol
should state **which channel it targets** and be judged by a metric that can see
that channel. Judging a copula-channel change by served-marginal 30-point Brier
is the error that produced several of the recent nulls.
