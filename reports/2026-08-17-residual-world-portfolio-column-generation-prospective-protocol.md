# Residual-world portfolio column generation: prospective score-free protocol

Date frozen: 2026-08-17
Protocol ID: `20260817-residual-world-column-generation-scorefree-v1`
Status: prospective protocol only; no residual column, treatment book,
historical score, or cloud execution existed when this document was written.

## Decision boundary

This pilot asks one narrow question:

> Under the exact current production-multinomial player worlds, can a lineup
> generated for its marginal contribution to the current 80-lineup book add
> out-of-training-world tail coverage at a fixed candidate budget, while the
> unchanged exact-80 selector remains usable and sufficiently stable?

It is a construction experiment, not a selector arm, a new simulation law,
an ATLAS continuation, or a historical-scoring arm. It may not query or read
realized player scores, realized lineup scores, contest ranks, ownership,
payouts, standings, or any current partial ATLAS treatment output. A simulated
pass can license only (1) the fully specified all-five-block shadow build
below and then (2) a separately frozen historical/prospective shadow. It
cannot directly alter the money policy or UI.

The deterministic queue remains:

1. close the already-running ATLAS repair/historical/parity chain;
2. close the already-frozen constraint-lattice support/resource preflight;
3. acquire the heavy-compute lease and run this residual-world pilot;
4. only then release the later DST, coherent-state, recourse, and stack-shell
   mechanisms in their registered order.

Implementation and local tests may be prepared earlier. No residual-world
Cloud Run job may overlap another heavy experiment.

## Frozen review inputs and prior

This protocol reconciles these exact documents:

- `reports/2026-08-17-extreme-tail-system-review-and-recommendations.md`,
  SHA-256
  `c2eedcae7c9f7dce15dd3ca4051d964a48284cb87647e254eea52e07f5175017`;
- `reports/2026-08-17-extreme-tail-review-reconciliation-and-queue-amendment.md`,
  SHA-256
  `48fd7ac14feecb58db20121ce97f8daea99619c9206eefa99dc6726cf5811dcb`.

The honest prior is deliberately modest: the most likely favorable outcome
is movement in the shoulder (`194`, `200`, and possibly `210`) with `220`,
`230`, and `240` tied. That result would still be informative because it
would demonstrate that portfolio-aware construction closes a real candidate
gap, but it would not be described as evidence of new extreme-tail support.
Every threshold is reported. At least one registered `210+` gain remains
mandatory for a pass; a gain confined to `194` or `200` is a null result for
this pilot.

The prior does not change the objective. The pricing objective gives strict
priority to rarer, higher weekly maxima so that any number of additional 194
clears cannot buy away one lost 230 or 240 clear. This is intentionally
aligned with the operator's stated priority: the best lineup in the weekly
book matters more than its average lineup score.

## Source law and immutable receipts

### Required source

The only eligible world source is the completed current-money acquisition:

- panels `20260815-atlas-money-worlds-r0-v1` through
  `20260815-atlas-money-worlds-r4-v1`;
- seasons 2023--2025, Weeks 1--18: exactly 54 slates x 5 blocks x 10,000
  worlds;
- policy `classic-k1-role12-boom40-poscal-cbwu-v4`;
- simulation law: possession mode, team factors on, production-multinomial
  usage, `GAME_SIM_USAGE=""`, no finite Dirichlet K, and `TD_LEDGER` off;
- production environment receipt SHA-256
  `b0aef9d0bec9d3fa1fdefeed237991c6e6089a967473973c0fd909a2daf563bb`;
- acquisition code
  `545ddae1b8e1256fde8e345683e0004aa5463b5e`;
- immutable acquisition image
  `us-central1-docker.pkg.dev/nfl-predictions-503414/nfl-dfs/nfl-dfs@sha256:ad4604d86f1b1f7938136650f3d3940c9f1d6edd6a3427d618e6f943822602c8`.

Existing receipt material is bound as follows:

| receipt | required SHA-256 |
|---|---|
| `reports/atlas-money-transfer-runs/20260815-atlas-current-money-transfer-v1/report.json` | `8e568f8e5e343319ab4e4f48421b41f3266e56ecb592abce77f3ed6d246cd446` |
| acquisition `source-grid.json` payload | `9a18458c63f0155b72f3847c705fbd0bdde9b64c923a5b63cc4a1f42bfe3445b` |
| acquisition `candidate-grid.json` payload | `b18216ca8900b54381c3f5ed5031442143f2d5e1ee38c6ae193e2f5dfbc6bac0` |
| acquisition completion payload | `a29f773f35d4121db785fc5be2e1a18895f897bf91c248dd24c1566ace5c34cb` |
| repair validation | `4938df8c8f7f84dea40baf2f76cd84f78cdc9e1a097c271b419e3dc8c6b5cd37` |
| repair completion | `7bbff5dd3721ba436f79cb984091e7aa5815642629ab2c5615a6f2d9aacaa592` |

The older `20260813-sis-asoe-treatment-r0..r4-v1` Phase S worlds are not an
eligible substitute: they are a finite-K plus SIS-ASOE research law, not the
current production-multinomial law. The production-law dependence lock may be
used as corroborating artifact-identity evidence, but its filtered
candidate-union player population is not sufficient for this optimizer. The
pilot needs the complete aligned player-world and legality catalog.

### Mandatory R3/2025 Week 1 substitution

For R3/2025 Week 1 only, the candidate/catalog binding is the registered
repair panel `20260816-atlas-mvp-repair-r3-2025-v1`, and the artifact is:

`gs://nfl-predictions-503414-raw/cand_scores/20260816-atlas-mvp-repair-r3-2025-v1/2025_w1_1b661a12cf24.npz`

Its SHA-256 must be
`7eaef50c890150f6cdc329e80e4d68f08b4a8d2aac402fa5a51ba9ce4f860805`.
The validation proves all five arrays byte-identical to the original transfer
artifact, with 248 unique legal candidates, 589 players, and 10,000 worlds.
The new lock must query and retain the repaired object's current GCS
generation, size, MD5, CRC32C, and SHA-256; equality of SHA alone does not
permit silently using an unregistered object.

### New source-lock object

Before a solver image can launch, a small source-lock job creates exactly one
write-once `source-lock.json`. Its BigQuery query is statically allowlisted to:

- candidate rows: `panel_run_id`, `season`, `week`, `cand_ix`, `tag`,
  `all_tags`, `players`, `score_artifact_uri`, and
  `score_artifact_sha256` from `replay_candidates_staging`;
- R0 legality rows: `season`, `week`, `id`, `pos`, `team`, `opp`, `game_id`,
  and `salary` from `slate_player_features`.

No projection is needed to formulate the residual pricing problem; scores
come only from the locked player-world arrays. The query must not use
`SELECT *`, views, wildcard tables, mutable current-week rows, or fields whose
names contain `actual`, `rank`, `ownership`, `selected`, `payout`, `label`, or
`standings`. No field containing `score` is allowed except the two explicitly
allowlisted immutable simulated-artifact receipt fields
`score_artifact_uri` and `score_artifact_sha256`. The lock stores the literal
query text, query SHA, job ID, referenced-table metadata, and returned
canonical-row hashes.

The source lock must reproduce these pre-existing mechanical invariants:

- 68,199 candidate rows and the complete 270 panel/slate cells;
- contiguous `cand_ix=0..n-1` in every cell;
- exactly nine distinct IDs in each roster;
- 29,605 unique R0 season/week/player legality rows across the 54 slates;
- one artifact URI and SHA per panel/slate, with the registered repair
  substitution above;
- exact artifact arrays
  `{cand_ix, totals, tail_line, player_ids, player_draws}`;
- candidate totals shaped `n_candidates x 10,000` and player worlds shaped
  `n_players x 10,000`, finite and aligned;
- identical player-ID universe across R0--R4 within a slate; each block's
  order is retained in its receipt and mapped bijectively to canonical R0
  order before cross-block scoring;
- reconstruction of every native candidate total from its nine player rows,
  with `rtol=0` and `atol=1e-4` and the observed maximum error retained.

Every source GCS object is rechecked against URI, generation, bytes, MD5,
CRC32C, and SHA immediately before use. The heavy runner receives no BigQuery
permissions and consumes only the source lock and named GCS generations. This
is the hard outcome firewall.

### Point-in-time and leakage rules

The pilot consumes the already-frozen PIT replay worlds; it does not rebuild
features from today's warehouse. Candidate identities and legality fields are
read only at the exact historical `panel_run_id`, serialized into the source
lock, and never joined to another table during construction. In particular:

- no same-week realized Fantasy Points/SIS metric, late injury result, final
  ownership, game result, post-lock projection, or later-season aggregate may
  be joined to a slate;
- no 2026 row or current mutable live table is eligible;
- the R0 legality catalog supplies only identity, position, team/opponent,
  game, and salary; it supplies no target, label, or outcome;
- player scores are exclusively simulated values already inside the named
  immutable NPZ generations. Calling them `totals` or `player_draws` does not
  authorize a realized-score column;
- input JSON is recursively rejected if an unallowlisted key contains
  `actual`, `rank`, `ownership`, `payout`, `standings`, `label`, or
  `selected_score`;
- the runner has no BigQuery client code or IAM role, takes no arbitrary local
  path/glob, and accepts only objects enumerated by the locked manifest.

The source-lock job itself may read the two allowlisted BigQuery tables, but
its canonical result rows are persisted and hashed before the solver image is
released. A table mutation after that point cannot enter the pilot. Any need
to repair a source row requires a new lock, protocol amendment, and run ID;
the 54-slate population may not mix old and repaired mutable rows.

## Notation and exact tail utility

For slate `s`, block `r`, and world `w`:

- `S(l,r,w)` is the nine-player score of lineup `l` reconstructed from the
  locked player-world matrix;
- `M(B,r,w) = max[l in B] S(l,r,w)` is a candidate pool or selected book's
  best score;
- the ordered thresholds are
  `T = (240, 230, 220, 210, 200, 194, 187)`;
- `N_t(B; Omega) = sum[(r,w) in Omega] 1[M(B,r,w) >= t]`.

The exact utility vector is:

`U(B; Omega) = (N_240, N_230, N_220, N_210, N_200, N_194, N_187, sum M)`.

Vectors are compared lexicographically from left to right. `sum M` is only a
final tie-break after all seven tail counts are exactly tied. It is never
allowed to trade average points for a higher-threshold clear. No weighted
scalar approximation may replace this ordering unless a future amendment
proves exact integer equivalence and is frozen before treatment output.
For pruning and solver decisions, `sum M` is computed in the same integer
micro-DK representation specified below. Raw float32/float64 values are
reported only after identity is frozen.

Given a reference book with current maximum `m(r,w)`, a new lineup's exact
marginal pricing vector is:

`G(l | B) = (g_240, ..., g_187, sum d(l,r,w))`, where

`g_t = sum 1[m(r,w) < t <= S(l,r,w)]` and
`d(l,r,w) = max(0, S(l,r,w)-m(r,w))`.

This is the marginal change in tail coverage and, only after every registered
tail tier ties, the marginal increase in book maximum from adding `l`.
Worlds already covered at `t` have zero threshold value; a lineup receives no
final-tier credit merely for scoring well below the existing book maximum.
Pricing maximizes `G` lexicographically.

## Fixed control, book, and candidate budgets

For every slate, construct the canonical control candidate pool `C_s` by
calling `combine_cbwu_books` in the fixed order `(R0,R1,R2,R3,R4)`. This is
the current score-blind quota/fill law, not the order-invariant CBWU-OI
research repair.

- Candidate budget `B_s`: exactly the native R0 candidate count for that
  slate, as returned by the canonical combiner. It may vary by slate, but the
  control and every treatment for that slate have the identical `B_s`.
- Selected-book budget: exactly 80 unique lineups.
- Selector: unchanged `select_tail_entries(..., line=194,
  env={"SELECT_LSE":"0"})`.
- Residual-column maximum dose: `K_max=8` per construction fold.
- The generated sequence stops prospectively at the first pricing solve with
  no positive registered-threshold marginal. A fold with `k=0` is a valid
  candidate-null result, not a mechanical failure; a fold with `1<=k<8`
  retains and evaluates those useful columns rather than discarding evidence
  because a later complement does not exist. It may not skip a null column,
  resume at a different active set, add candidates, relax a rule, or
  substitute a different slate.

### Prospective two-fold separation

Each slate is constructed twice:

| fold | construction/training blocks | untouched evaluation blocks |
|---|---|---|
| A | R0, R2, R4 | R1, R3 |
| B | R1, R3 | R0, R2, R4 |

The folds are independent. Identities, active worlds, objective values, or
solver outputs from A may not influence B, and vice versa. A roster may
naturally be rediscovered in both folds; that is reported rather than banned.
Every source block is therefore evaluation evidence exactly once. Aggregate
cross-fitted results weight each of the five evaluation blocks equally, then
each of the 54 slates equally. They do not overweight the three-block
evaluation fold.

Within fold `f`:

1. Select the control book `Q_C^f` (80 entries) from `C_s` using only the
   fold's construction blocks.
2. Protect every identity in `Q_C^f` from candidate-budget removal.
3. Compute and freeze an eight-identity reverse-greedy pruning order from
   `C_s - Q_C^f`. For each prospective dose `j=1..8`, the retained interim
   control pool removes exactly the first `j` identities. Selecting each
   `B_s-j` interim pool must reproduce the same ordered `Q_C^f`; otherwise the
   fold is mechanically invalid.
4. Generate up to eight residual columns sequentially against a current
   exact-80 reference book. Before column 1 this is `Q_C^f`. After each
   positive column, append it to the dose-matched retained interim pool,
   rerun the unchanged selector on construction blocks, and use that newly
   selected exact-80 book as the residual reference for the next column.
   Previously generated columns remain in the candidate pool even if they
   leave the current 80. Stop at the first null pricing vector.
5. If `k` positive columns were generated, append them after `C_s` with the
   first `k` pruning identities removed. The fold treatment candidate pool
   `C_T^f` therefore has exactly `B_s` candidates, including when `k=0`.
6. Select `Q_T^f` from `C_T^f`, again using construction blocks only.
7. Evaluate both candidate pools and both selected books only on that fold's
   untouched blocks.

The independent selector evaluation is therefore honest: selection is fit on
one group of random streams and the selected book is scored on different
registered streams from the same frozen law.

### Candidate-budget pruning

Pruning uses all construction worlds, never the 66-world pricing subset and
never an evaluation block. At each of eight reverse-greedy steps, calculate
`U(C_without_candidate; construction_worlds)` for every unprotected remaining
candidate and remove the candidate leaving the lexicographically greatest
utility. If utilities tie exactly, remove the lexicographically greatest
canonical nine-ID tuple. This preserves the smallest canonical identity and
is deterministic. The initial and each intermediate utility vector are
retained.

All original control identities, including the eight removed candidates, are
still banned from pricing. A treatment cannot restore a removed control
roster under a new tag and claim it as a generated column.

## Bounded residual-world set

World IDs are the immutable pair `(Rk, 0..9999)`. Active-world selection is
outcome-free and uses only locked simulated player scores and the current
reference book maximum.

### Exact sizes

The two cross-fitting folds each use:

- a fixed 96-world reservoir;
- a fixed 66-world active pricing set at every column iteration.

This keeps pricing inside the preregistered 64--256 range. Per-block quotas
are:

| fold | reservoir per construction block | active per construction block |
|---|---:|---:|
| A (3 blocks) | 32 | 22 |
| B (2 blocks) | 48 | 33 |

The post-pass all-five-block shadow builder is already fixed at a 100-world
reservoir (20 per block) and 70 active worlds (14 per block).

### Reservoir algorithm

For each construction block:

1. Compute the position-shape upper bound `U_w` with exact Classic skill
   patterns `(2 RB,4 WR,1 TE)`, `(2,3,2)`, and `(3,3,1)`. This relaxes salary,
   team, game, and stack rules and is used only to rank a bounded reservoir.
2. For every threshold in descending `T`, create an eligible queue of worlds
   satisfying `m_w < t <= U_w`.
3. Sort each queue by `(t-m_w ascending, U_w-t descending, world_id
   ascending)`.
4. Cycle through thresholds `240 -> ... -> 187`, taking the first not-yet-
   selected world from each nonempty queue until the block's reservoir quota
   is full. Skip duplicates and exhausted queues. If a complete cycle adds no
   world before the quota is full, the fold fails support.
5. On every reservoir world solve both the exact minimum `L_w` and exact
   maximum `H_w` attainable by a lineup under all production construction
   rules below. These are one-time, per-world legal-domain bounds; they are
   not generic constants.

At each of the eight column iterations, rebuild the threshold queues inside
the fixed reservoir using updated `m_w` and exact `H_w` in place of `U_w`.
Apply the same cyclic selection and ranking
`(t-m_w ascending, H_w-t descending, world_id ascending)` until the exact
active quota is reached in every block. A reservoir world is selected once
even if it is eligible at multiple thresholds. Failure to fill 66 active
worlds is terminal; there is no reservoir expansion after treatment begins.

## Pricing MILP

### Production-feasible domain

The pricing, exact-minimum, and exact-maximum models share one constraint
builder. They explicitly enforce:

- 9 players, exactly 1 QB and 1 DST;
- 2--3 RB, 3--4 WR, and 1--2 TE;
- salary from $49,000 through $50,000 inclusive;
- no more than 8 players from one team and at least 2 games;
- QB plus at least 2 same-team WR/TE;
- at least 1 opposing RB/WR/TE bring-back;
- no RB against the selected opposing DST;
- no two RBs from the same team;
- no punt mandate, ownership rule, game cap, lock, or other research lever.

The optimizer dataclass defaults are only QB+1 and bring-back 0, so the
research runner must pass `StackRules(qb_stack_min=2,
bring_back_min=1, forbid_rb_vs_dst=True,
forbid_two_rb_same_team=True)` explicitly. Inferring the current production
stack from dataclass defaults is forbidden.

Let `x_p` be a binary roster indicator. Scores are converted solely for MILP
numerics to integer micro-DK points:

`a_p,w = np.rint(float64(player_draw_p,w) * 1_000_000).astype(int64)`

and `S_w = sum_p a_p,w x_p`; threshold `t` becomes the exact integer
`T_t=t*1_000_000`. The same integer coefficients define exact `L_w` and
`H_w` under the production-feasible domain.

For a currently uncovered active world/threshold with
`m_w < t <= H_w`, add binary `y_w,t` and both implications:

`S_w >= T_t - (T_t-L_w)(1-y_w,t)`

`S_w <= (T_t-1) + (H_w-(T_t-1))y_w,t`.

Thus `y=1` if and only if the candidate reaches the threshold. `T_t-L_w` and
`H_w-(T_t-1)` are the tight world-specific legal-domain bounds. If the book
already clears `t`, or exact `H_w<t`, no indicator is created and its
marginal contribution is fixed at zero.

For the final raw-score tie tier, define integer `d_w=max(0,S_w-m_w)`.
When `L_w <= m_w < H_w`, introduce binary `b_w` and enforce the exact graph:

`S_w-m_w <= (H_w-m_w)b_w`

`S_w-m_w >= 1-(m_w-L_w+1)(1-b_w)`

`d_w >= S_w-m_w`, `d_w >= 0`,

`d_w <= (H_w-m_w)b_w`, and

`d_w <= S_w-m_w+(m_w-L_w)(1-b_w)`.

If `H_w<=m_w`, fix `d_w=0`; if `L_w>m_w`, set `d_w=S_w-m_w` without a
binary. This exact positive-part formulation is independently reconstructed.
It prevents the final tier from reverting to standalone lineup score.

After every solve, the float64 sum of the nine stored float32 player rows must
reproduce every active threshold indicator. The integer/raw lineup difference
must be at most `4.5e-6 + 1e-9` DK points (nine independently rounded rows).
Any indicator disagreement or larger error invalidates the cell; it is not
resolved by a tolerance change.

### Exact lexicographic solve

For each new column, run sequential exact solves:

1. maximize `sum y_w,240`; freeze the integer optimum by equality;
2. repeat in order for 230, 220, 210, 200, 194, and 187;
3. maximize `sum_w d_w` over the 66 active worlds and freeze its integer
   optimum;
4. choose the deterministic canonical identity as described below.

All seven tail counts are therefore true tiers, not numerical weights. The
column is admissible only if at least one `g_t>0`; a mean-only solution is not
a residual column.

### Novelty, deduplication, and exact ties

Every original control roster and every earlier generated roster in the same
fold receives the no-good cut:

`sum[p in roster] x_p <= 8`.

Roster identity is the sorted tuple of nine string player IDs; tags, slots,
and order cannot create a second identity. A returned roster must be legal,
unique, absent from the complete control pool, and reconstruct to its stated
score in every block.

After all utility tiers and residual-score-gain sum are fixed, minimize the sum of
canonical player ranks (IDs sorted by UTF-8 string order). Then add a no-good
cut for that solution and resolve with the same rank sum:

- infeasible means the identity is uniquely determined;
- if another exact tie exists, obtain the canonical incidence vector by
  fixing `x_p` sequentially in ascending player-ID order, preferring `x_p=1`
  whenever it remains feasible under all frozen objectives.

This slow fallback is used only for a proven rank-sum ambiguity. Solver
iteration order, hash-set order, an approximate objective tolerance, and an
unseeded random tie may never decide identity.

## Cross-scoring and unchanged selection

Immediately after a column is found, score it on all 50,000 ordinary worlds,
including the untouched fold, by summing the nine named player rows. Only its
construction blocks update the residual reference for the next iteration.
Persist one `k x 50,000` float32 matrix per fold (including a canonical empty
matrix when `k=0`) plus its roster identities, source block order, and SHA-256.

For every fold, retain:

- control and treatment candidate identities and exact `B_s`;
- control and treatment selected ordered identities and exact count 80;
- all threshold masks and candidate/book maxima on construction and
  evaluation worlds;
- pair reach, QB-stack-core reach, player reach, dominant-game reach, and
  source tags before and after treatment;
- generated-column survival in the selected 80 and its marginal clears at
  every threshold;
- changed-slate and changed-book indicators.

The production selector is called directly. The pilot may not reimplement,
retune, bag, raise its line, change its tie-breaks, or select on evaluation
worlds.

## Frozen score-free endpoints and gates

For threshold `t`, define the cross-fitted count delta over all 54 slates and
the five blocks, each evaluated by the treatment that did not train on it:

`Delta_C(t) = N_t(treatment candidate pool) - N_t(control candidate pool)`

and analogously `Delta_S(t)` for the training-selected exact-80 books.
Because every block has 10,000 worlds, counts and equal-block rates have the
same ordering. Both are reported, overall, by season, block, and slate.

### Mechanical gate

All of the following must hold:

- one validated source lock, exact 54 x 5 source grid, and valid repair bind;
- 108/108 fold/slate constructions complete;
- `0<=k<=K_max=8`, the registered stop-at-first-null rule, fixed candidate
  budget, exact 80, and exact reservoir/active sizes in every attempted cell;
- every CBC status `Optimal`, parsed zero gap, all integer objectives and
  constraints independently reconstructed;
- no duplicate/illegal roster, nonfinite value, cross-score mismatch,
  quantization mismatch, missing object, or available-case aggregation;
- two canary runs reproduce byte-identical scientific payloads.

Any failure produces `mechanically-invalid-or-inconclusive` and stops. A
partial population is never evidence.

### Candidate endpoint: primary construction gate

The candidate endpoint passes only if all conditions hold:

1. `(Delta_C(240), Delta_C(230), Delta_C(220), Delta_C(210),
   Delta_C(200), Delta_C(194), Delta_C(187))` is lexicographically greater
   than the all-zero vector;
2. `Delta_C(194) >= 0` (the separately required shoulder no-harm floor);
3. at least one of `Delta_C(240)`, `Delta_C(230)`, `Delta_C(220)`, or
   `Delta_C(210)` is strictly positive;
4. at the highest `210+` threshold with a positive aggregate delta, at least
   two source blocks and at least two distinct slates are positive. Negative
   source blocks are reported but not capped: the operator has explicitly
   accepted some season/seed declines in exchange for more very-high-scoring
   weeks, so the retired no-more-than-one-negative rule is not reintroduced.

If this gate fails, disposition is `candidate-endpoint-null` and the
experiment stops score-free. Selector movement cannot rescue a candidate
failure.

### Exact-80 transfer gate

If the candidate gate passes, the selected endpoint must independently meet
the same four conditions with `Delta_S` replacing `Delta_C`. A candidate pass
and selector failure is classified
`portfolio-construction-supported-selector-transfer-null`. It may motivate a
separately frozen integration study, but it does not license historical
scoring or a live shadow.

### Structural and uncertainty diagnostics

Pair reach, stack-core reach, player reach, dominant-game reach, source
attribution, selected generated-column count, and changed-slate count are
mandatory but non-gating; arbitrary reach weights are not introduced after
seeing treatment. For each threshold report treatment-only clears,
control-only clears, paired net clears, and 10,000 fixed-seed (`17081701`)
season-stratified slate-cluster bootstrap replicates with all five blocks kept
together. Intervals are diagnostics, not a second mutable pass rule.

### Predeclared interpretation labels

- `extreme-tail-support`: all gates pass and either 220, 230, or 240 improves
  at both candidate and selected endpoints;
- `shoulder-plus-210-support`: all gates pass, 210 improves, and 220/230/240
  are exactly tied or do not improve. This is the honest-prior favorable case;
- `portfolio-construction-supported-selector-transfer-null`: candidate passes
  but selected endpoint fails;
- `candidate-endpoint-null`: primary candidate gate fails;
- `mechanically-invalid-or-inconclusive`: source, solver, population, or
  reconstruction contract fails.

These labels may not be reassigned after reading a result.

## Selector-stability gate

Stability uses identical world samples for control and treatment and never
changes candidate identities. For each slate/fold:

- create one deterministic reciprocal split of every construction block into
  5,000/5,000 worlds using the existing split seed `19,408,014` plus the
  global block ID and fold ID;
- create 32 deterministic block-stratified bootstrap samples using base seed
  `8,132,027` plus season, week, fold, replicate, and global block ID;
- each bootstrap has exactly 10,000 worlds: 5,000 per block in fold B; in
  fold A use 3,334 from the lowest global block and 3,333 from each other
  block;
- run the unchanged exact-80/194 selector on control and treatment samples;
- report pairwise exact-80 overlap, prefix overlap at
  1/5/10/20/40/60/80, overlap with the full construction-world book,
  candidate selection frequencies, reciprocal train-minus-validation
  coverage optimism, and matched control/treatment identity overlap.

Aggregate with equal slate and equal fold weight. A selector-stability pass
requires all three prospective paired floors:

1. treatment minus control mean bootstrap pairwise overlap `>= -6.0`
   lineups;
2. treatment minus control mean disjoint-half overlap `>= -5.0` lineups;
3. treatment minus control mean reciprocal coverage optimism `<= +0.0030`.

These limits were fixed from the already-known canonical/CBWU-OI scale before
any residual treatment: OI moved pairwise overlap by `-6.5466`, disjoint-half
overlap by `-4.8148`, and optimism by `+0.0030174`. The conventional
high/intermediate/low band (`>=72`, `>=56`, `<56`) is still reported but does
not independently gate because two- and three-block training books have a
different evidence width from the existing five-block diagnostic.

A tail/selector pass with a stability failure is labeled
`scorefree-tail-positive-operationally-unstable`; it cannot proceed to
historical scoring or a weekly shadow without a newly frozen stabilization
mechanism.

## Solver and resource preflight

The current optimizer calls `PULP_CBC_CMD(msg=0)` without an explicit time,
thread, seed, log, or gap contract. The residual runner must not inherit that
call. It uses the CBC binary pinned in its immutable image with:

- one CBC thread per solve;
- random seed and CBC random seed `170817`;
- elapsed-time mode;
- maximum 120 seconds for an exact bound solve;
- maximum 600 seconds for one pricing/tie solve;
- solver log retained for every solve;
- `Optimal` and parsed zero gap required; an incumbent at timeout is failure.

Independent bound solves may use exactly two outer worker processes. Results
are assembled only in sorted `(fold, block, world, min/max)` order. Pricing is
sequential within a fold; the two folds may run concurrently in two fixed
processes. BLAS/OpenMP thread counts are pinned to one. The runner records
CBC, PuLP, Python, NumPy, libc, architecture, CPU, and memory receipts.

Before the full grid:

1. brute-force toy pools must exactly match the MILP on legal minima/maxima,
   every indicator, every lex tier, no-good cuts, and identity tie-breaking;
2. a source-only 54-slate census must pass without constructing a column;
3. run the full real path on the prospectively chosen canary, 2023 Week 1,
   twice in separate Cloud Run executions from the same digest and source
   lock;
4. require identical canonical scientific JSON and canonical array digests
   (`dtype`, `shape`, and C-order uncompressed bytes; compression-container
   metadata is excluded). Operational timestamps and execution names live in
   separate receipts. Wall time must be at most 6 hours, peak RSS at most 24
   GiB, with no solve at its limit and no solver warning.

The planned shard is one slate per Cloud Run execution, 4 vCPU, 32 GiB,
8-hour task timeout, task concurrency one, and at most four simultaneous
slate executions inside this single experiment. Cloud Run retries are zero.
A failed canary or shard does not license more memory, another solver, a
smaller active set, a longer limit, or a replacement cell; any such change
requires a new prospective amendment and run ID. Valid and invalid shards may
not be spliced into one scientific result.

## Cloud serialization and immutable evidence

The launcher must:

1. verify the queue dependencies are terminal from durable Cloud Run/GCS
   evidence, not a local watcher;
2. acquire a new shared heavy-experiment lease atomically before creating any
   job;
3. pin one git archive, full test/build receipt, image digest, protocol hash,
   source-lock generation/SHA, solver receipt, and literal environment;
4. refuse an existing output prefix and use create-only GCS writes;
5. release the heavy lease only after writing immutable terminal execution
   and release receipts. No later watcher releases merely because a local
   process ended.

The shared heavy lease is a required implementation prerequisite, not an
already-existing repository capability. Implement it as a create-only GCS
object at
`gs://nfl-predictions-503414-raw/research-governance/heavy-experiment-active-v1.json`
containing run ID, job family, code SHA, image digest, protocol SHA and
acquisition time. Acquisition uses generation-match zero. Release requires
the original generation/content hash plus a terminal full-population or
fail-closed completion receipt; deletion uses that exact generation match.
An occupied or unverifiable/stale lease stops the launcher and requires a
separately recorded operator recovery—never automatic expiry. Before this
pilot launches, the constraint-lattice and every later score-free watcher
must either use this same lease or be durably terminal/disabled, closing the
multi-watcher race identified in the reconciliation.

Each slate/fold shard retains:

- complete source object identities and repair substitution;
- control candidate/order hash and exact80 order hash;
- pruning sequence and utility vectors;
- reservoir and per-iteration active world IDs, `m`, `L`, `H`, and queue tier;
- every sequential solver status/objective, canonical roster, no-good list,
  solver log SHA, wall time, nodes, and peak RSS;
- generated-column identities, actual dose `k`, null-stop receipt, active
  indicators, `k x 50,000` cross-score arrays, raw/integer parity, and
  SHA-256;
- control/treatment candidate and selected endpoint summaries;
- pair/core/player/game reach and source attribution;
- full stability metrics and compressed candidate-frequency artifact;
- `uses_realized_outcomes=false`, `production_change_licensed=false`, and
  `historical_scoring_licensed=false`.

The strict harvester requires exactly 54 terminal slate objects and 108
complete construction cells, verifies every content hash and source
generation, independently recomputes budgets/gates, and writes a create-only
aggregate plus a human report. Partial objects remain diagnostic only. Raw
column identities and cross-scores remain in GCS long enough for independent
review and are never joined to actual outcomes by this run.

## Already-frozen post-pass all-law build

Only after candidate, selected, and stability gates all pass, the same image
may construct one score-free all-law shadow per slate using all R0--R4 worlds:

- control `C_s` and exact80/194 selector unchanged;
- up to eight protected-book candidate replacements, stopping at the first
  null pricing vector and pruning exactly the realized positive dose;
- reservoir 100 (20 per block), active set 70 (14 per block);
- identical threshold order, bounds, MILP, no-good, pruning, cross-score, and
  tie rules;
- fixed candidate count `B_s` and exact selected count 80;
- all-law candidate and selected vectors must still be lex-positive,
  non-worse at 194, and positive at one `210+` threshold.

This all-law object freezes the identities eligible for a later shadow. A
separate document must then freeze the historical outcome query and gates
before any actual score is read. The historical result, if favorable, is
still only retrospective evidence. Money-policy promotion requires the
separately labeled 2026 pre-lock prospective shadow and the project's normal
promotion authority.

## Current code insertion audit

Audit base: git `dbb2630542a4f4237ffc1abc53afba26dd9cfc79` plus the following
observed source identities. The implementation commit and image must replace
these with their own final manifest; they are insertion evidence, not
permission to run a dirty tree.

| current seam | observed SHA-256 | implementation consequence |
|---|---|---|
| `src/nfl_dfs/research/atlas_money_source_grid.py` | `8987a26d3d08a25a3bb577bb461a77a6d154355fbaebd1debe82d2f27b18e960` | Reuse exact NPZ/environment validation; extend with full legality catalog, candidate tags, GCS metadata and repair substitution. |
| `scripts/run_cbwu_seed_order_audit.py::_candidate_batch` | bound by final implementation manifest | Reuse candidate/artifact reconstruction rather than inventing a second roster decoder. |
| `src/nfl_dfs/inference/multiseed_portfolio.py::combine_cbwu_books` | `8c7530cb515b32f29b6b20a260fca562dd75a3eece1eba915e00ed03f2700c21` | This is the canonical control. Do not use `combine_cbwu_order_invariant_books`. |
| `src/nfl_dfs/backtest/engine.py::CandidateBatch` and `candidate_transform` | `394e54a77260d5972ab2ad1c94824a42592a33eeba2255c436232ec53eed8e95` | The batch validates aligned candidates/player worlds, and `candidate_transform` is the eventual 2026 shadow seam. The historical score-free runner should operate offline first. |
| `src/nfl_dfs/optimizer/lineup.py::optimize` and stack constraints | `81544e5f80769012fccef66b38c6bea54a830ac15dbed447952a593aa40b3bee` | Extract a shared constraint builder before pricing; copying the roster/stack constraints would create drift. Preserve ordinary `optimize` behavior and default CBC call byte-for-byte. |
| `src/nfl_dfs/analysis/atlas_world_ranking.py::roster_slot_upper_bound` | `7ccec773b4b3da31860081b0525f496d394ff0bf8f0a7229f32a691be5849f33` | Reuse only for reservoir ranking. Add exact integer legal min/max solves; do not use the relaxed bound as an indicator M. |
| `src/nfl_dfs/optimizer/lineup.py::select_tail_entries` | included in lineup hash above | Call unchanged on construction worlds, then evaluate on held-out worlds. Existing tie behavior must reproduce in the two-process canary. |
| `src/nfl_dfs/research/cbwu_oi_selector_stability.py` | `0f08d680c6284d0c12dfc36e53eb9a5807e96be3490d0e2d3ec6659478361a02` | Reuse paired overlap/optimism calculations in a new fold-aware module; do not mutate the prior CBWU-OI report contract. |

Recommended new units are:

- `src/nfl_dfs/research/residual_world_columns.py`: frozen constants,
  reservoir selection, exact bounds, pricing, pruning, cross-scoring, and
  per-cell metrics;
- `src/nfl_dfs/research/residual_selector_stability.py`: fold-aware paired
  stability over unchanged candidate identities;
- `scripts/run_residual_world_source_lock.py`;
- `scripts/run_residual_world_column_generation.py --season --week`;
- strict aggregate/finish scripts and a queue-aware Cloud Run launcher.

The shared optimizer refactor must have parity tests showing the pre-refactor
and post-refactor ordinary optimizer return identical status and roster on a
fixed fixture corpus. Research solver limits must be injected only into the
new caller; changing production CBC behavior would confound the pilot.

## Mandatory implementation tests

At minimum, the exact implementation must test:

1. source SQL allowlist and poison columns that raise if any outcome-facing
   field is accessed;
2. all 270 source cells, repair binding, GCS generation/SHA checks, player
   order, candidate indices, tags, and reconstructed totals;
3. canonical CBWU control budget/order and exact80 reproduction across
   separate processes;
4. brute-force equality of exact `L/H`, indicator truth values, exact
   positive-part residual `d`, seven-tier lex objective, residual-gain tie,
   ambiguous identity tie, and no-good constraints;
5. deterministic eight-identity pruning order, protected 80, adaptive
   `0..8` dose with stop-at-first-null, no control-identity resurrection, and
   exact treatment candidate count at every dose;
6. active/reservoir block quotas, deterministic queue ordering, adaptive
   residual updates, and fail-closed exhaustion;
7. fold isolation: changing any held-out score must not change that fold's
   removals, active worlds, or generated identities;
8. raw/micro-DK indicator parity and all-five-block generated-column
   reconstruction;
9. unchanged selector calls, held-out-only endpoint calculation, equal block
   and slate aggregation, nested-threshold identities, and gate truth tables;
10. stability sample identity across arms, fixed seeds, exact bootstrap size,
    prefixes, optimism, frequency compression, and paired floors;
11. create-only outputs, strict full-population harvest, zero Cloud Run
    retries, and byte-identical repeated canary payloads;
12. full clean-archive test/build success before publishing the immutable
    image.

## Frozen conclusion rules

The pilot is worth running because it attacks the measured construction
interface directly: it asks the optimizer for a complement to the current
book, not another individually attractive lineup. It is also deliberately
easy to falsify. Failure to improve the matched-budget candidate endpoint
ends this mechanism before any historical score query. A candidate gain that
does not survive the unchanged selector is reported as an interface failure,
not promoted. A simulated tail gain with unstable membership is retained as
a research clue, not a weekly policy.

Conversely, a clean shoulder-plus-210 result is not minimized merely because
220/230/240 tie; that is the favorable outcome the prior expects. It licenses
the already-specified all-law shadow and a separate score-facing protocol.
Only a registered 220+ gain may be described as new extreme-tail support, and
no score-free result alone authorizes money deployment.
