# Receiver/defender matchup intelligence for winners and corpus tails

**Date:** 2026-08-22

**Status:** implementation plan; no model, Foundry, graph, deployment, or money-policy change is authorized by this document

**Primary objective:** determine whether point-in-time receiver matchup characteristics distinguish Millionaire Maker winners and high-scoring corpus lineups, then test whether those characteristics improve fixed-budget corpus population and retrieval
**First operational target:** a frozen, auditable Week 1 matchup annotation layer and one prospective shadow strategy

## Executive overview

The project currently understands Millionaire Maker winners and simulated
`>200` corpus lineups much better as **rosters** than as **football matchups**.
Winner work measures stack shape, bring-backs, game dispersion, ownership,
candidate-pool proximity, simulated-law placement, and world-optimum realism.
The accepted corpus phenotype work measures generator origin, player pairs,
team/game stacks, stack topology, selector membership, event-world recurrence,
and redundancy. Those are valuable, but neither analysis presently tells us
whether the receivers were facing favorable coverage.

In particular, the accepted corpus artifact has no populated coverage
annotations: `easy_coverage.available=false`, zero annotated players, zero
complete lineups, and no count of lineups with easy coverage. The current
analyzer accepts an optional `easy_coverage` boolean supplied by another
process; it does not calculate the matchup. The winner analyses do not join a
coverage source at all.

The requested football question is therefore still open:

> Did winners and high-scoring corpus lineups contain WR1s, WR2s, slot
> receivers, or stack partners facing defenses and defenders that had been
> weak against those roles and alignments before that slate locked?

Answering it properly requires more than a raw “fantasy points allowed to
wide receivers” column. That number is confounded by opponent quality, pass
volume, game script, touchdowns, and the definition of WR1. The implementation
must separate:

1. the receiver's expected pre-lock role;
2. the defense's prior concessions to that role;
3. Wide/Slot and Man/Zone matchup fit;
4. named-defender quality and availability;
5. the confidence that a defender was relevant to that receiver; and
6. the game, projection, ownership, and opportunity variables that can make a
   matchup merely *look* predictive.

The central recommendation is to build one immutable, point-in-time
`receiver_matchup_week` evidence layer in BigQuery/GCS, attach it to every
winner and every corpus lineup, and project compact relationships into the
dedicated research Neo4j database for analysis and UI. BigQuery/GCS remain the
authoritative computation and evidence stores. Neo4j remains a rebuildable,
read-only reasoning projection; it must never become the source of a scoring
feature or an automatic policy-feedback loop.

The implementation should proceed in two depths:

- **Immediately answerable:** team concessions to pre-lock WR1/WR2/WR3 roles,
  PFR secondary quality, Fantasy Points shell/alignment fit, and SIS Wide/Slot
  defender vulnerability.
- **Not yet directly observed:** the exact named corner assigned to a given
  receiver on each route. Until a source supplies that relationship, the UI
  and graph may show a defender's expected involvement, but must label it as
  inferred and must not create a factual `COVERED_BY` relationship.

The first implementation is an annotation and analysis layer, not a hard
lineup rule. Only after matched, cross-slate analysis shows incremental value
should it enter one bounded Foundry fill sleeve and one bounded admission
strategy. That distinction is important because the earlier Fantasy Points
coverage-fit player model made a very small valid calibration improvement,
while its licensed twelve-candidate portfolio arm changed 33 selected slots
and changed **zero** weekly maxima across 107 slates.

## 1. What is analyzed today

### 1.1 Millionaire Maker winners

The governed winner work currently analyzes:

- salary use and DraftKings legality;
- QB teammate count, bring-back count, naked/double stacks, secondary stacks,
  maximum team/game concentration, and number of represented games;
- cumulative ownership, low-owned player counts, ownership product, and
  chalk-versus-leverage shape;
- candidate-pool and selected-book overlap with each winner;
- whether a winner was constructible under production rules;
- the winner's simulated percentile, generating worlds, visit rank, and gap
  to the simulated world optimum; and
- whether simulated optima depend on player outcomes beyond anything those
  players realized historically.

The key sources are:

- [`2026-08-19-winner-structure-census-results.md`](./2026-08-19-winner-structure-census-results.md)
- [`2026-08-19-winner-anatomy-results.md`](./2026-08-19-winner-anatomy-results.md)
- [`2026-08-19-winner-world-optima-and-field-null-results.md`](./2026-08-19-winner-world-optima-and-field-null-results.md)
- [`2026-08-20-b1-winner-relative-census-result.md`](./2026-08-20-b1-winner-relative-census-result.md)

Those reports do **not** currently analyze defender identity, expected
receiver assignment, coverage snaps, targets or yards allowed by the likely
defender, role-specific concessions, or receiver alignment against the
opponent's weakness.

The current winner universe must also remain explicit:

- 68 canonical known first-place lines across 2019 and 2023–2025;
- 51 governed, feature-complete winners across 2023–2025; and
- no complete historical field rosters for the old contests.

The 68-winner registry still requires the source-integrity reconciliation in
the offseason roadmap. Until that is complete, analyses must name the exact
68- or 51-row cohort and never silently mix them.

### 1.2 Corpus lineups and `>200` evidence

The accepted task-0 phenotype artifact analyzes 585 unique 2023 Week 1
lineups across 50,000 simulated worlds: 29.25 million lineup-world scores and
27,117 strict `>200` events. It records:

- salary, projection sum, team count, game count, and team/game
  concentration;
- QB stack size, bring-back size, generator tags, and source memberships;
- exact player pairs, position pairs, team/game stacks, and phenotype
  combinations;
- event counts and rates in discovery blocks R0–R3 and descriptive held-out
  block R4;
- selector membership and rank; and
- high-event-world concentration and roster/event-set redundancy.

Its retained artifact is
[`analysis.json`](./corpus-gt200-runs/20260822-task0-simulated-gt200-phenotype-v1/analysis.json).
The optional annotation seam is in
[`corpus_gt200_analysis.py`](../src/nfl_dfs/research/corpus_gt200_analysis.py),
but version 1 accepts arbitrary player-row properties after only shallow
identity checks. Before matchup data can influence an analysis, the annotation
contract needs generation-pinned source identities, exact field validation,
lock/source timestamps, missingness, and explicit outcome exclusion.

The phrase “top corpus scorer” must always retain its score semantics:

- `simulated_world_tail`: a lineup-world score crosses a threshold in an
  Atlas world;
- `realized_corpus_tail`: a generated historical lineup's actual players
  scored across a threshold; or
- `contest_result`: an entered lineup achieved an observed contest rank or
  payout.

These are different evidence populations. They may be compared, but they
must never be pooled into one unlabeled positive class.

## 2. Coverage and defender data already available

The repository has more raw material than the current winner and corpus
reports use. The limitation is integration and grain, not total absence.

| Source | Available information | Current limitation | Permitted first use |
|---|---|---|---|
| PFR/nflverse advanced defense | Per-defender nearest-defender targets, completions and yards; existing trailing CB/DB team aggregates and top-CB-out flag from 2018 onward | No receiver assignment; current production features are broadcast opponent-team context | Backfill secondary quality and named-defender prior quality with explicit uncertainty |
| Fantasy Points prior-season coverage | Receiver Man/Zone TPRR, YPRR, FP/RR and separation crossed with opponent shell rates | Prior-season, only about 29% support in the evaluated WR/TE rows, small/unstable effects, closed twelve-candidate arm | One component of a richer phenotype; do not rerun the closed construction arm |
| Fantasy Points prior-window alignment | Player Wide/Slot route profiles from W-4 through W-1 | Only supported windows; missingness is material | Weight SIS Wide/Slot defensive vulnerability by the receiver's expected alignment |
| Fantasy Points WR Coverage Matchup sample | Team-level matchup presentation | Existing sample is schedule-stale and has no cornerback identities | Schema reference only; prospective capture must have its own immutable source contract |
| SIS team pass-tail context | Prior-window pass-defense boom, bust and pressure context | Team context, not individual coverage; WR marginal result was neutral | Context/control feature, not a direct defender claim |
| SIS receiver-copula acquisition | 15,477 defender-game rows, 376 defenders, all 32 teams, 2022–2025, Wide/Slot, coverage snaps, targets, completions, yards and TDs; 3,324 strict-prior defense/alignment rows | Identifies defender and alignment but not the receiver he covered; historical copula calibration was untestable under its frozen design | Build defender and alignment vulnerability annotations; do not revive or alter the closed copula protocol |
| SIS filtered team pass-defense view | Wide/Slot × Man/Zone team metrics and Points Saved | Team Totals lacked coverage-snaps and target denominators, so that exact path failed its schema gate | Do not reuse that failed estimand; use player-grain denominators instead |

Relevant source records are:

- [`2026-08-10-fantasy-points-coverage-fit-experiment.md`](./2026-08-10-fantasy-points-coverage-fit-experiment.md)
- [`2026-08-10-fantasy-points-coverage-tail-union.md`](./2026-08-10-fantasy-points-coverage-tail-union.md)
- [`2026-08-13-wr-defense-coverage-inventory-reconciliation.md`](./2026-08-13-wr-defense-coverage-inventory-reconciliation.md)
- [`2026-08-15-sis-player-pass-defense-grain-feasibility-result.md`](./2026-08-15-sis-player-pass-defense-grain-feasibility-result.md)
- [`2026-08-15-sis-receiver-copula-protocol.md`](./2026-08-15-sis-receiver-copula-protocol.md)
- [`2026-08-15-sis-receiver-copula-calibration-result.md`](./2026-08-15-sis-receiver-copula-calibration-result.md)
- [`017a_defense_week_coverage.sql`](../sql/features/017a_defense_week_coverage.sql)

### 2.1 The exact limitation on named-defender claims

The acquired SIS rows can answer questions such as:

- How often was a defender targeted per Wide or Slot coverage snap?
- What completion rate, yards per target, TD rate, and receiving points per
  target had he allowed before the target week?
- Which defenders carried the largest prior coverage workload for a team and
  alignment?
- Was the secondary's most-used corner unavailable?

They cannot presently answer:

- Which exact receiver the defender covered on each route;
- how often a corner shadowed one named receiver;
- what fraction of a receiver's routes were against that corner; or
- the realized WR-versus-CB result for a named pair.

Until a direct assignment source is captured, the implementation may compute
`defender_exposure_weight` from prior alignment workload. It must not call
that value an assignment probability without validating that interpretation,
and it must not create a factual `Receiver COVERED_BY Defender` graph edge.

## 3. Questions this work must answer

### 3.1 Descriptive questions

1. What percentage of winners rostered at least one pre-lock WR1 with a
   favorable role matchup?
2. How many favorable receiver matchups did winners contain, and how does that
   compare with same-slate legal controls?
3. Among simulated and realized corpus tails, how do role, alignment, shell,
   secondary, and named-defender quality differ from the rest of the corpus?
4. Are favorable matchup traits concentrated in boom-tagged lineups, QB
   stacks, bring-backs, or particular generator families?
5. Do favorable receiver matchups occur in distinct event worlds, or merely
   duplicate the same game environments already covered by the incumbent?

### 3.2 Incremental-signal questions

1. Does matchup context explain receiver outcomes after controlling for
   projection, salary, ownership, target/route share, implied team total,
   player role, and slate?
2. Does it distinguish `>200`, `>210`, and higher lineup tails after the same
   controls?
3. Does named-defender information add anything beyond team role concessions
   and Wide/Slot context?
4. Is `boom × favorable matchup` more informative than either boom or matchup
   alone?
5. Does an admitted matchup-supported lineup add marginal scenario value to
   an exact-80 book rather than merely ranking well by itself?

### 3.3 Operational questions

1. Can every Week 1 receiver receive a pre-lock, source-receipted matchup row
   or an explicit unsupported reason?
2. Can a model reproduce the exact historical annotation from immutable
   source bytes?
3. Can the web UI explain whether a claim is team-level, alignment-level,
   defender-level, or directly observed assignment-level?
4. Can a frozen shadow be graded after settlement without changing the money
   lineup path?

## 4. Non-negotiable design laws

1. **Point-in-time role labels.** A source-game receiver may not be called
   WR1 using that game's targets, routes, or fantasy points. His role for game
   W must be derived only from information available before W locked.
2. **Strictly prior defense windows.** A target week may use only completed
   games whose kickoff preceded the target lock. Use canonical game time/order,
   not an unverified row order.
3. **Missing is not neutral.** Unsupported role, alignment, defender, or shell
   values remain null with a reason. They may not become zero or “average.”
4. **Continuous measures before labels.** Preserve the underlying opportunity
   and efficiency metrics. `easy_coverage` is a versioned descriptor, not a
   vendor truth or a causal fact.
5. **No direct assignment invention.** Inferred defender involvement and
   observed receiver-defender assignments use different fields, labels, and
   graph relationships.
6. **Matched denominators.** “X% of winners had easy coverage” is never
   reported alone. It must be shown beside same-slate prevalence and a matched
   or conditional effect estimate.
7. **Separate simulated and realized evidence.** R0–R3 may inform discovery;
   R4 is descriptive only. Realized outcomes are joined only after features,
   models, and selected books are frozen.
8. **No retry of closed mechanisms.** This is not another twelve-candidate
   prior-season Fantasy Points coverage arm and not a repair of the closed SIS
   receiver-copula calibration. It is a multi-source, role/alignment/defender
   annotation and set-selection question.
9. **One new historical read.** These matchup features are genuinely new
   pre-lock information, so they can justify one preregistered historical
   evaluation. Do not tune repeatedly on the same 54/107 slates.
10. **Graph is a projection.** Canonical tables and immutable GCS objects own
    truth. Neo4j stores compact relationships, measurements, and pointers only.

## 5. Canonical point-in-time data model

### 5.1 `receiver_role_week_pit/v1`

Create one row per eligible `(season, week, slate_id, gsis_id)` for WR and TE.
The historical construction must use the target slate's actual eligible player
universe where available; otherwise it must name the broader roster/salary
universe used and must not compare unlike universes without a flag.

Required keys and provenance:

- `season`, `week`, `slate_id`, `game_id`, `lock_time_utc`;
- `gsis_id`, `team`, `opponent`, `position`;
- `role_contract_version`;
- maximum source season/week/time for every component;
- source object identities and feature-table build identity;
- `role_supported`, `role_support_reason`, and component missingness.

Do not use the existing season-partitioned `target_share_last` by itself for
Week 1 because it is naturally null at a season boundary. Build
analysis-specific, game-ordered, cross-season as-of components from strictly
prior games:

- last and last-four target share;
- last and last-four snap share;
- last and last-four air-yards share/WOPR where available;
- Fantasy Points last and last-four route share, already cross-season capable;
- current pre-lock depth rank; and
- current salary only as a deterministic final tie-break, never as the main
  definition of role.

For v1, calculate a transparent consensus role score:

1. Within each offense/team/week, convert every available continuous role
   component to a within-team receiver percentile, oriented so larger means a
   larger expected receiving role. Convert depth rank the opposite direction.
2. Average the available component percentiles for each receiver.
3. Require at least two non-null components and at least two eligible team WRs
   before assigning WR ranks.
4. Rank the consensus score descending; tie-break by depth rank ascending,
   salary descending, then canonical player ID.
5. Store `WR1`, `WR2`, and `WR3+` as a label, while retaining the consensus
   score, every component rank, the number of components, and the number of
   components voting the player first.
6. Rank TEs separately and label `TE1`/`TE2+`.

Also retain sensitivity definitions:

- target-share-only role rank;
- route-share-only role rank;
- depth-chart-only role rank; and
- consensus agreement/confidence.

A WR1 result that reverses under these reasonable definitions is not stable
enough to become a lineup rule.

### 5.2 `defense_receiver_role_concession_week_pit/v1`

This table directly implements “the opponent gives up points to WR1s.” It has
one row per target `(season, week, defense, receiver_role)` and is constructed
from earlier source games only.

For every prior source game:

1. attach each opposing receiver's **pre-game** role from §5.1;
2. calculate receiving opportunity and outcome measures; and
3. attribute them to the defense and role bucket.

Retain separate opportunity and efficiency measures:

- routes where a valid route source exists;
- targets, receptions, air yards, receiving yards, and red-zone targets;
- target rate per route and team target share;
- catch rate, yards per target, TDs per target, and receiving DK points per
  target;
- receiving-only DK points allowed; and
- total player DK points allowed as a separately labeled, broader diagnostic.

For each target week, aggregate the last eight completed defense games, crossing
the season boundary where possible. Require at least four games for a supported
row. Preserve last-four and last-eight variants for sensitivity, but do not
select a window after reading outcomes.

Raw points allowed are not sufficient. Add two adjusted views:

- `role_allowed_vs_pit_expectation`: observed source-game result minus that
  receiver's frozen pre-lock expectation, where a receipted historical
  projection exists; and
- `role_allowed_vs_prior_role_baseline`: observed result minus a hierarchical
  role/season expectation fitted only from games preceding that source game.

Shrink rates toward the contemporaneous league role prior using denominator
geometry fixed before outcomes are analyzed. Store raw numerators,
denominators, prior sizes, shrunk values, source-game count, source-receiver
count, and maximum source kickoff.

Primary output examples:

- `wr1_targets_allowed_l8`
- `wr1_receiving_dk_allowed_l8`
- `wr1_receiving_dk_over_expectation_l8`
- `wr1_target_rate_allowed_shrunk_l8`
- `wr1_points_per_target_allowed_shrunk_l8`
- corresponding `wr2`, `wr3plus`, and `te1` values

### 5.3 `defender_alignment_quality_week_pit/v1`

Build this table from the already-retained SIS player-grain source and PFR.
Keep vendor-specific estimates separate; do not average incompatible
attribution laws into one number without a later frozen validation.

For every defender, target week, and supported alignment (`wide`, `slot`, and
`all` where valid), calculate from the last eight prior games:

- coverage snaps;
- targets and target rate per coverage snap;
- completions and completion rate;
- yards and yards per target;
- touchdowns and TDs per target;
- receiving DK points allowed per target;
- prior-game count and effective denominators; and
- empirical-Bayes shrunk versions of every rate.

Additional fields:

- SIS player ID, PFR ID, resolved GSIS ID when available, and resolution state;
- team and current pre-lock roster/injury state;
- team/alignment share of prior coverage snaps;
- `defender_exposure_weight`, defined only as the defender's share of the
  team's prior coverage workload for that alignment;
- top-one and top-two workload defenders for Wide and Slot;
- top-defender-out and remaining-secondary quality; and
- exact source identities and source-week bounds.

`defender_exposure_weight` is not a shadow probability. The first version may
use it to form a workload-weighted expected defender-quality context for a
receiver's alignment mix, but the field and UI label must say
`inferred-from-prior-alignment-workload`.

PFR can extend secondary/defender priors back to 2018, but it lacks the SIS
Wide/Slot split. Store a `source_grain` enum such as:

- `sis-defender-alignment`;
- `pfr-nearest-defender`;
- `pfr-secondary-group`; or
- `direct-receiver-defender-assignment` (reserved; absent in v1).

### 5.4 `receiver_shell_alignment_fit_week_pit/v1`

Reuse existing guarded sources rather than re-importing or redefining them:

- Fantasy Points prior-season Man/Zone and Cover 2/3/4/6 fit;
- Fantasy Points prior-window Wide/Slot receiver alignment;
- SIS prior-window Wide/Slot defense vulnerability;
- SIS pass boom/bust/pressure team context; and
- PFR secondary group quality.

Keep each component and its support status. The previous Fantasy Points
coverage delta can be present as historical context, but it cannot be the sole
matchup score and cannot trigger the closed twelve-candidate construction law.

### 5.5 `receiver_matchup_week_pit/v1`

Join §§5.1–5.4 at player/slate grain. This is the canonical annotation source
for winners, corpus lineups, Neo4j, and the UI.

Required field families:

| Family | Required fields |
|---|---|
| Identity | player/slate/game/team/opponent, role and annotation contract versions |
| Role | consensus role, alternate role ranks, role support/confidence |
| Role defense | raw/adjusted WR1/WR2/WR3+/TE1 concessions and denominators |
| Alignment | receiver Wide/Slot shares, defense Wide/Slot vulnerability, retained route mass |
| Shell | Man/Zone and supported shell-fit components |
| Defender | workload-weighted defender quality, top workload defenders, injury status, source grain |
| Context | projection, target/route share, ownership, salary, implied total, boom probability/tag |
| Provenance | lock time, maximum source time, table/object identities, source hashes |
| Missingness | component support booleans and explicit reason codes |

#### A versioned definition of “easy coverage”

Do not hand-label easy matchups from a single raw statistic. First compute
four continuous, within-slate, receiver-eligible percentiles oriented so that
larger is more favorable to the offense:

1. role-specific adjusted concession;
2. receiver-alignment-weighted SIS vulnerability;
3. workload-weighted defender/secondary vulnerability; and
4. supported Fantasy Points shell-fit edge.

For `easy_coverage_v1`:

- require at least two supported components;
- set `matchup_edge_score` to the unweighted mean of supported component
  percentiles;
- set `easy_coverage=true` only when `matchup_edge_score >= 0.75` and no
  supported component is below `0.40`;
- set it false when supported but the condition fails; and
- leave it null when fewer than two components are supported.

The percentile reference population is the same target slate's eligible
receivers, so the definition is servable at lock and does not use an outcome.
Retain the raw score and components; the boolean exists for counts and UI, not
as the primary model input. Freeze these thresholds before the first matchup
effect is read. If the outcome-blind support census shows the definition is
nearly empty, redesign it before any outcome analysis rather than weaken it
afterward.

### 5.6 Annotation contract v2

Do not place these rows into the permissive
`corpus-gt200-context-annotations/v1` contract. Add a versioned successor such
as `corpus-matchup-context-annotations/v2` with exact fields and identities.

The contract must include:

- exact task and slate IDs;
- exact player-catalog identity;
- exact feature-build/source manifest identities using URI, generation,
  SHA-256, and bytes;
- lock time and maximum source observation/game time;
- a fixed field dictionary and type/range validation;
- one unique player row for every annotated catalog player;
- allowed missingness reasons;
- `realized_outcomes_present=false` and a forbidden-column scan;
- `active_in_score_matrix=false`; and
- canonical content hash plus create-once publication.

The analyzer must independently verify these guards before calculating a
single association. Carrying a vendor name in a free-form array is not enough.

## 6. Lineup-level matchup features

Aggregate the player-week rows into every winner and corpus lineup. Preserve
the receiver denominator so a two-TE lineup is not silently compared with a
four-WR lineup as though exposure were equal.

Required lineup fields:

- `eligible_receiver_count`;
- `matchup_supported_receiver_count` and share;
- `role_supported_receiver_count` and share;
- `easy_coverage_receiver_count` and share;
- `easy_coverage_wr1_count`, `easy_coverage_wr2_count`, and
  `easy_coverage_te1_count`;
- mean, maximum, minimum, and standard deviation of `matchup_edge_score`;
- target-share-weighted and projection-weighted matchup edge;
- QB-stack receiver matchup mean/minimum;
- bring-back receiver matchup mean/minimum;
- count of boom-tagged receivers with easy coverage;
- sum and maximum of `boom_probability × matchup_edge_score` where a true
  pre-lock boom probability is available;
- number of receivers supported at role, alignment, defender, and shell grain;
- count of direct receiver-defender assignments (expected to be zero in v1);
- top workload defender and injury context for explanation only; and
- explicit incomplete-lineup reason codes.

Do not drop unsupported lineups. Keep them in the denominator and stratify
results by annotation completeness.

## 7. Analyses to run

### 7.1 Analysis A: receiver-level incremental matchup value

Before interpreting lineup cohorts, establish whether the underlying football
features have incremental signal.

Population: historical WR/TE player-weeks with frozen pre-lock projections,
roles, and authoritative actuals.

Controls:

- mean projection and ceiling/boom probability;
- salary and within-slate salary rank;
- target share, route share, air-yards share, snap share, and red-zone role;
- implied team total, spread, game total, and expected plays;
- ownership where historically available;
- season, slate, position, and role; and
- matchup-component missingness.

Outcomes:

- actual minus pre-lock mean projection;
- receiving-only DK points;
- actual thresholds 20, 25, and 30; and
- opportunity outcomes separately from efficiency outcomes.

Use outer folds by season, never random folds. Report calibration, Brier,
residual MAE, rank correlation, average precision, and slate-clustered effect
intervals. Compare nested models:

- `P0`: controls only;
- `P1`: P0 + role-specific team concessions;
- `P2`: P1 + alignment/shell context;
- `P3`: P2 + defender-quality context; and
- `P4`: P3 + boom/ownership/role interactions.

This decomposition answers whether named-defender information adds anything
beyond the easier-to-obtain team matchup.

### 7.2 Analysis B: Millionaire winner matchup census

Run separately on:

- the canonical 68-winner registry when the source reconciliation completes;
- the governed 51 feature-complete winners; and
- season-held-out subsets.

For each winner, select same-slate controls from the legal generated union.
The preferred estimator is a conditional logistic or strongly regularized
hierarchical model with slate strata. At minimum, controls must be balanced on:

- salary and roster-position shape;
- projection sum and ceiling;
- ownership shape where available;
- game/team concentration and stack topology;
- implied totals; and
- annotation completeness.

Use many controls per winner, but treat the slate—not each control row—as the
independent unit. Report:

- winner prevalence and matched-control prevalence for every matchup trait;
- within-slate standardized differences;
- conditional odds ratios with uncertainty;
- leave-one-season-out direction;
- sensitivity across the alternate WR1 definitions; and
- exact winner case records showing which receivers drove the classification.

Until full contest fields exist, label the estimand correctly:

> winner enrichment versus our same-slate legal corpus, not winner enrichment
> versus the Millionaire Maker field.

### 7.3 Analysis C: simulated corpus phenotype enrichment

Expand from the accepted task 0 to all accepted Foundry slates. For each
threshold in `{194, 200, 210, 220, 230, 240}`:

- calculate lineup event counts by R0–R4;
- use R0–R3 for discovery/model inputs;
- keep R4 descriptive and sealed from ranking;
- estimate event rates with beta-binomial or hierarchical shrinkage across
  blocks/slates; and
- report support in lineups, slates, seasons, and world blocks.

The primary comparisons are continuous matchup edge, easy-coverage count,
WR1 favorable count, and boom × matchup interactions. Do not treat the 29.25
million task-0 lineup-world cells as independent observations.

### 7.4 Analysis D: realized corpus tails

Join the frozen pre-lock annotations to historical candidate actuals only
after the annotation artifacts and analysis protocol are frozen. Analyze:

- actual score and thresholds `{194, 200, 210, 220, 230, 240}`;
- within-slate corpus rank and distance from corpus ceiling;
- distance from the known winner;
- candidate source/generator family; and
- whether the lineup was admitted and selected by each strategy.

Use leave-one-season-out predictions, slate-clustered intervals, average
precision/lift at fixed shortlist size, and exact-80 book outcomes. The
realized-tail model is allowed to inform only held-out folds and later
prospective shadows.

### 7.5 Predeclared primary hypotheses

Limit the first historical read to these hypotheses:

1. Winners are enriched for at least one favorable pre-lock WR1 matchup versus
   matched same-slate corpus controls.
2. Higher target-share-weighted matchup edge is associated with simulated and
   realized lineup tails after projection, role, ownership, and slate controls.
3. `boom × matchup_edge` adds held-out information beyond boom and matchup
   main effects.
4. A favorable QB-stack receiver matchup contributes more than an equally
   favorable unstacked receiver matchup to set-level tail coverage.
5. Defender-grain context adds held-out information beyond team role and
   alignment context.

Correct for multiplicity across these hypotheses. Everything else is
exploratory and cannot license a strategy.

### 7.6 Negative and falsification controls

- Replace the true opponent with a deterministic within-slate permutation;
  the matchup effect should disappear.
- Test defender-quality features on RB rushing outcomes; a broad “benefit”
  there suggests a game-environment confound rather than receiver coverage.
- Compare raw WR points allowed with opponent-adjusted role concessions; a
  raw-only result is not portable enough for a policy.
- Re-run the winner comparison under target-, route-, depth-, and
  consensus-role labels.
- Stratify by projection and implied-total bands to expose residual chalk/game
  environment confounding.
- Report results with and without TDs; a TD-only matchup effect is especially
  fragile.

## 8. Transfer into corpus population and retrieval

Matchup intelligence should enter the Foundry only after §§7.1–7.4 produce a
cross-fitted, multi-slate signal. The first transfer is bounded and paired.

### 8.1 Population preset

Register `F5-matchup-supported-v1` as a challenger to the incumbent fill:

- retain an incumbent component;
- use a fixed, preregistered number of matchup-supported solves;
- apply a soft objective bonus from a cross-fitted matchup/boom interaction;
- include separate WR1, QB-stack, and bring-back sleeves only if the discovery
  protocol nominated them before the held-out read;
- never hard-ban an unsupported or unfavorable player; and
- retain the exact reason each generated lineup entered the sleeve.

The bonus scale and sleeve dose must be selected inside development folds or
fixed from score-free geometry. They cannot be swept on outer-fold realized
scores.

### 8.2 Retrieval/admission preset

Register `R6-matchup-admission-v1` as an admission policy, not a replacement
for portfolio marginal utility:

- reserve a bounded shortlist sleeve for matchup-supported candidates;
- require a cross-fitted lower-bound or calibrated score, not the historical
  label itself;
- preserve novelty/scenario information;
- then run the same expected-max/tail-LCB/regime-robust set selector over the
  admitted union; and
- retain a pick-by-pick trace showing whether matchup support or marginal
  world utility admitted/selected each lineup.

Selecting the top 80 individual matchup scores is explicitly out of scope.

### 8.3 Required A/B/C/D experiment

| | Incumbent retrieval | Matchup-aware admission/retrieval |
|---|---|---|
| Incumbent fill | A: baseline | B: retrieval-only effect |
| Matchup-supported fill | C: fill-only effect | D: joint effect |

Every cell must use the same slate snapshot, player worlds, candidate/entry
budget, and realized-outcome opening time. Report:

- generated-union ceiling and source of the ceiling;
- exact-80 weekly maximum and threshold grid;
- simulated discovery and held-out block utility;
- scenario/event-set redundancy;
- matchup trait exposure and missingness;
- season and slate wins/ties/losses; and
- whether a failure occurred in generation, admission, or set selection.

The earlier coverage-tail arm is a warning: it generated 432 novel candidates
and changed 33 slots but changed no weekly maximum. A new matchup signal is
useful only if the final book converts it.

## 9. Neo4j projection

Use the dedicated corpus research database and preserve the existing
namespaces/firewall. Add a distinct namespace such as
`corpus-matchup-research`. Do not put raw licensed vendor rows, score matrices,
or credentials in the graph.

### 9.1 Nodes

- `ReceiverWeek`
- `DefenderWeek`
- `DefenseRoleContext`
- `AlignmentContext`
- `CoverageShellContext`
- `LineupEvidence`
- `WinnerObservation`
- `CorpusTailCohort`
- `Slate`
- `FillPreset`
- `RetrievalPreset`
- `ExperimentCell`
- `SourceArtifact`

### 9.2 Relationships

- `HAS_MATCHUP_CONTEXT`
- `PLAYS_ROLE`
- `FACES_DEFENSE`
- `HAS_ALIGNMENT_CONTEXT`
- `HAS_DEFENDER_EXPOSURE` with source grain and workload weight
- `CONTAINS_RECEIVER`
- `MEMBER_OF_COHORT`
- `GENERATED_BY`
- `ADMITTED_BY`
- `SELECTED_BY`
- `OBSERVED_IN_SLATE`
- `DERIVED_FROM_SOURCE`

Reserve `COVERED_BY` for directly observed receiver-defender assignment only.
The v1 loader must reject that relationship because no accepted source can
support it.

Every measurement node/edge must carry or point to:

- source URI/generation/SHA/bytes;
- annotation contract/version;
- target lock and maximum source time;
- outcome semantics;
- support/missingness;
- discovery/evaluation partition; and
- authority flags showing no automatic fill, retrieval, or money-policy
  mutation.

### 9.3 Read-only query catalog

Add immutable, parameterized queries for:

1. winner versus matched-control matchup prevalence;
2. simulated/realized threshold enrichment by matchup trait;
3. boom × matchup interaction by slate/season;
4. WR1/WR2/WR3+ concessions by defense and week;
5. defender workload/quality histories by alignment;
6. lineup matchup composition and selected-strategy lineage;
7. strategy performance versus matchup exposure;
8. source coverage and missingness by slate;
9. inferred versus directly observed defender evidence; and
10. immutable source/provenance drilldown.

Graph queries are explanatory reads. They may not write a new preset or update
a score.

## 10. Web UI visualizations

Extend the existing `/corpus-research` page and its governed projection rather
than create an unreceipted dashboard.

### 10.1 Cohort comparison

A grouped bar/dot chart showing, for winners, matched controls, simulated
tails, realized tails, and all corpus lineups:

- mean matchup edge;
- easy-coverage count distribution;
- percentage with a favorable WR1;
- percentage with a favorable QB-stack receiver; and
- annotation completeness.

Display slate-clustered intervals and the exact cohort denominator beside
every value.

### 10.2 Role × defense map

A heatmap with defenses on one axis and WR1/WR2/WR3+/TE1 on the other,
selectable by targets, receiving DK points, adjusted residual, target rate, or
points per target. The week selector must show the prior window and maximum
source week used.

### 10.3 Lineup matchup strip

For one lineup, display each receiver as a compact row containing:

- role and role confidence;
- Wide/Slot mix;
- team role-concession edge;
- alignment/shell edge;
- defender/secondary edge and evidence grain;
- boom/ownership/projection context;
- final matchup percentile/easy label; and
- missingness/provenance drilldown.

### 10.4 Defender involvement view

Show a receiver connected to the opponent's top workload defenders with
dashed edges sized by prior alignment workload. The legend must say
“inferred involvement, not observed assignment.” Use a solid assignment edge
only if a future direct source supports it.

### 10.5 Strategy outcome view

For each Foundry scenario, show:

- matchup-supported candidates generated/admitted/selected;
- A/B/C/D weekly maximum deltas;
- threshold wins/ties/losses;
- event-world/scenario breadth; and
- whether improvement came from fill or retrieval.

### 10.6 Source-quality view

A coverage matrix by season/week/source/grain showing supported, partial,
missing, stale, or rejected. This visualization is mandatory because a strong
effect on 20% of receivers must not look like a universal feature.

## 11. Implementation work packages

### P0 — Freeze identities, definitions, and support geometry

**Code/doc targets**

- `src/nfl_dfs/research/receiver_matchup_contract.py`
- `tests/test_receiver_matchup_contract.py`
- a frozen source/support manifest under `reports/receiver-matchup-runs/`

**Tasks**

1. Reconcile the 68-winner registry and preserve the governed 51-row subset.
2. Inventory exact BigQuery/GCS identities for PFR, Fantasy Points, SIS,
   player snapshots, slates, lineups, and outcomes.
3. Run an outcome-blind support census for every role/alignment/defender
   component by season/week.
4. Freeze role law, easy-coverage law, source windows, folds, primary
   hypotheses, and minimum support before reading effects.
5. Define v2 annotation and analysis schemas with canonical hashes.

**Exit criteria**

- every target row maps to a precise slate/player/lock;
- every source has a content identity and legal prior-time rule;
- every support threshold is feasible or redesigned before outcome access;
- no performance metric or target outcome is read.

### P1 — Build role and role-concession features

**Suggested targets**

- `sql/features/017l_receiver_week_role_pit.sql`
- `sql/features/017m_defense_receiver_role_concession_pit.sql`
- `src/nfl_dfs/analysis/receiver_role_matchup.py`
- `tests/test_receiver_role_matchup.py`

**Tasks**

1. Build cross-season strictly-prior role components.
2. Assign consensus and sensitivity roles.
3. Attribute prior-game outcomes to pre-game roles.
4. Build raw, adjusted, and shrunk last-four/last-eight concessions.
5. Add independent PIT reconstruction tests to the leakage suite.

**Exit criteria**

- no source game is on/after target lock;
- no role label reads its own game's outcomes;
- Week 1 either has valid prior-season support or an explicit null reason;
- duplicate player/week and defense/role/week rows fail closed.

### P2 — Build alignment and defender context

**Suggested targets**

- `src/nfl_dfs/research/receiver_defender_context.py`
- `tests/test_receiver_defender_context.py`

**Tasks**

1. Reopen and validate the existing SIS receiver-copula source/table
   identities without changing its closed experimental law.
2. Build defender/alignment prior quality and workload weights.
3. Join Fantasy Points receiver alignment, shell-fit, SIS alignment context,
   PFR secondary quality, and injury state.
4. Build an explicit SIS/PFR/GSIS defender crosswalk with resolved,
   ambiguous, and unresolved states.
5. Reserve direct assignment fields but populate none without a new source.

**Exit criteria**

- the 15,477 SIS rows and 3,324 prior rows reproduce exact retained audits;
- every populated defender value has positive denominators and strictly prior
  source games;
- no ambiguous identity is guessed;
- inferred involvement is mechanically distinguishable from assignment.

### P3 — Publish canonical matchup annotations

**Suggested targets**

- `src/nfl_dfs/research/receiver_matchup_annotations.py`
- updates to `src/nfl_dfs/research/corpus_gt200_analysis.py` through a
  versioned v2 path that leaves v1 replay byte-compatible
- `tests/test_receiver_matchup_annotations.py`
- v2 fixtures in `tests/test_corpus_gt200_analysis.py`

**Tasks**

1. Join the canonical player-week layer.
2. calculate continuous component percentiles and `easy_coverage_v1`;
3. produce source/missingness manifests;
4. create-once publish annotation objects;
5. attach lineup aggregates without reading outcomes; and
6. run an outcome-blind reality smoke against the real accepted task-0 player
   catalog and one governed winner slate before freezing the runner.

**Exit criteria**

- exact v1 replay remains unchanged;
- v2 rejects source, generation, schema, PIT, catalog, or forbidden-column
  drift;
- every annotated lineup exposes receiver coverage completeness;
- matrices and simulated scores remain byte-identical because annotations do
  not rescore worlds.

### P4 — Run winner, simulated-tail, and realized-tail analyses

**Suggested targets**

- `src/nfl_dfs/analysis/winner_matchup_census.py`
- `src/nfl_dfs/analysis/corpus_matchup_phenotypes.py`
- `tests/test_winner_matchup_census.py`
- `tests/test_corpus_matchup_phenotypes.py`

**Tasks**

1. Freeze matched-control construction and statistical estimands.
2. Run player-level nested models P0–P4.
3. Run the winner census.
4. Expand simulated phenotype annotations across accepted Foundry slates.
5. Freeze cross-fitted models/books, then open realized outcomes once.
6. Publish effect estimates, intervals, denominators, fold results, and case
   studies—not only ranked traits.

**Exit criteria**

- simulated, realized, and contest outcomes remain separate;
- all discovery inputs exclude R4;
- inference clusters by slate/season;
- primary and exploratory findings are labeled;
- no policy authority is inferred from descriptive enrichment.

### P5 — Project to Neo4j and expose the governed UI

**Suggested targets**

- `src/nfl_dfs/research/corpus_matchup_neo4j.py`
- `cypher/corpus_matchup_analysis_queries.cypher`
- versioned extensions to `corpus_research_ui_bridge.py`,
  `app/corpus_research.py`, `app/static/corpus_research.js`, and
  `app/static/corpus_research.css`
- corresponding Neo4j, bridge, API, and rendering tests

**Tasks**

1. Validate canonical annotation/analysis receipts before building a plan.
2. Add immutable nodes/relationships in the matchup namespace.
3. Add the exact read-only query catalog.
4. Materialize a create-once, query-receipted UI projection.
5. Implement §§10.1–10.6 with clear evidence-grain and missingness legends.

**Exit criteria**

- no raw licensed rows or matrices are stored in Neo4j;
- repeated identical loads are idempotent and conflicts fail closed;
- the API can operate in a clear not-ready state;
- mutation keywords are rejected before graph contact;
- every chart number maps to an immutable query receipt.

### P6 — Implement the bounded Foundry challenger

**Suggested targets**

- versioned fill/retrieval presets in the strategy registry;
- one adapter from matchup annotations to the accepted Foundry task schema;
- deterministic A/B/C/D evaluator and focused tests.

**Tasks**

1. Nominate at most one matchup interaction from P4.
2. Freeze `F5-matchup-supported-v1` and `R6-matchup-admission-v1`.
3. Run the exact paired design with fixed budgets/worlds.
4. Open realized outcomes after every book is frozen.
5. Retain selection traces and graph/UI scenario evidence.

**Exit criteria**

- the challenger changes actual candidates and/or admissions;
- every cell is exact-80 and budget-identical;
- fill and retrieval effects are separately identifiable;
- promotion requires book-level held-out improvement, not a classifier metric;
- no money policy changes from historical evidence alone.

### P7 — Week 1 and 2026 prospective operation

1. Capture Fantasy Points and SIS sources before lock under their weekly
   immutable contracts.
2. Build the Week 1 annotation object with 2025/prior-game fallbacks and
   current injury/depth information.
3. Freeze incumbent and matchup challenger shadows from the same snapshot.
4. Export/upload only the incumbent unless a separately authorized policy
   says otherwise.
5. After settlement, capture the full contest field while available, grade
   both books, and update the graph/UI with a distinct outcome receipt.
6. Accumulate enough prospective weeks to decide whether direct assignment or
   matchup-aware construction deserves a later promotion test.

## 12. Validation checklist

### Data and PIT

- [ ] Every role component carries a source game/time earlier than target lock.
- [ ] Every defense/defender window ends before target lock.
- [ ] Week 1 cross-season values retain their source season/week.
- [ ] Target-week actuals are absent from annotation schemas and objects.
- [ ] Future-row injection fixtures fail.
- [ ] Missing, ambiguous, and unsupported values remain null with reason codes.
- [ ] Player/team/defender crosswalk ambiguity fails closed.

### Evidence and reproducibility

- [ ] URI/generation/SHA/bytes identities bind every immutable source.
- [ ] Canonical sorting and content hashes reproduce independently.
- [ ] One real-artifact outcome-blind smoke passes before protocol freeze.
- [ ] v1 artifacts replay byte-identically.
- [ ] Full score matrices stay in GCS and are never copied into Neo4j.
- [ ] Historical outcome lease rules are observed for the one outcome read.

### Statistical validity

- [ ] Same-slate controls accompany every winner prevalence.
- [ ] Player models control projection, role, opportunity, game context, and
  ownership when available.
- [ ] Outer folds are by season and uncertainty clusters by slate.
- [ ] Simulated lineup-world events are not treated as independent slates.
- [ ] R4 never trains or ranks.
- [ ] Primary hypotheses and multiplicity handling are frozen.
- [ ] Role-definition and TD-exclusion sensitivity results are reported.

### Foundry and production safety

- [ ] Matchup annotations do not alter existing score matrices.
- [ ] Score-relevant levers are registered and self-identifying.
- [ ] A/B/C/D budgets, snapshots, and worlds are identical.
- [ ] The closed Fantasy Points candidate arm and SIS copula protocol are not
  silently retried.
- [ ] Graph and UI authority flags forbid automatic policy feedback.
- [ ] Historical success licenses only a prospective shadow.

## 13. Decision rules

The work can end in four valid states:

1. **Explanatory and actionable:** matchup features show stable incremental
   player and lineup signal, and the paired Foundry challenger improves a
   held-out exact-80 book. Freeze one prospective challenger.
2. **Explanatory but not actionable:** winners/high scorers are enriched, but
   the signal adds no held-out book value after controls. Keep it in the graph
   and UI; do not change fill/retrieval.
3. **No incremental signal:** apparent raw enrichment disappears after
   adjustment or season holdout. Retain the result and stop spending candidate
   budget on this mechanism.
4. **Inconclusive:** source coverage, direct assignment, or slate support is
   insufficient. Preserve the pipeline and prospective collector; do not
   convert missing evidence into a favorable rule.

No result should be summarized merely as “coverage matters” or “coverage does
not matter.” The required conclusion names the evidence grain: role, alignment,
team shell, secondary, named defender, or direct assignment.

## 14. Recommended order for the implementing model

The next model should not begin with Neo4j or a new optimizer weight. The
shortest path to a trustworthy answer is:

1. implement the outcome-blind P0 support census and v2 contract;
2. build pre-lock receiver roles and team concessions to WR1/WR2/WR3+;
3. join the already-retained SIS defender/alignment and Fantasy Points/PFR
   context;
4. produce the canonical player and lineup annotation objects;
5. verify them against the real task-0 and one winner slate;
6. freeze and run the matched winner and cross-slate phenotype analyses;
7. only then add graph/UI views; and
8. only after incremental evidence exists, implement one paired Foundry
   challenger and one prospective Week 1 shadow.

The first meaningful milestone is not a new score. It is a receipted table
where every receiver in a winner or corpus lineup can be described accurately
as:

> expected pre-lock role, opponent role concession, alignment fit,
> defender/secondary context, evidence confidence, and missingness.

Once that exists, the system can finally answer the user's original question
honestly—and can learn whether the answer helps win tournaments rather than
merely producing an appealing football story.
