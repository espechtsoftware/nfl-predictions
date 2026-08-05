# Post-review-6 execution plan (2026-08-05, revised after code audit)

Both reviews are triaged below. Sol's two critical findings are accepted
as errors in the review-6 package. Commit `34432a5` is a useful first
persistence patch, but a second audit found that it does **not yet close
the persistence contract**: multi-tag attribution remains incomplete,
live labels become zero rather than NULL, the UUID is minted per slate
rather than per panel, and the clear-world mask silently truncates
simulations beyond 2,048. These are prerequisites of ACTION 1 rather
than assumed complete.

Nothing labeled SCHEDULED below has been run. The plan deliberately puts
cheap instrument checks ahead of six-season compute.

---

## A. Corrections to the review-6 record

### A1. The oracle was not measured on the shipping baseline — accepted

The 30-pool/22-selected decomposition came from the instrumented build
whose selected book cleared 22 weeks. The shipping baseline cleared 27,
and the weekly CSV in the package was the 26-clear GUMBEL arm. Three
artifacts from three builds were presented as one experiment.

"Eight recoverable weeks" is therefore established only for the
22-clear build. On HF2 the residual might be three weeks, eight different
weeks, or a different frontier. The first substantive action is one
canonical HF2 run that emits, from the same image and candidate pools:

- Shipping baseline scores.
- Shipping candidate-oracle frontier.
- Complete labeled candidate records.
- The simulation support needed to reproduce selection offline.

No cross-build subtraction is allowed in future packages.

### A2. The labeled candidate set did not exist — accepted, partially fixed

Before `34432a5`, persisted rows carried salary, `p_line`, simulation
mean/q99, first-producer tag and player IDs, but no actual score. The
warehouse contained only 910 live candidate rows across six runs and two
slate-weeks. The normalized schema declared actuals, but no six-season
labeled table existed.

Commit `34432a5` usefully added actual score/rank, more simulation
summaries, an intended `all_tags` field, and a packed clear-world mask.
The following defects must be corrected before the canonical harvest.

#### A2.1 Multi-generator provenance still records only the first producer

At later generator sites, `_note()` is currently inside `if ids not in
seen`. Duplicate rosters therefore never record the later generator.
Record provenance before the uniqueness test:

```python
if lu is not None:
    _note(lu.ids, generator_tag)  # record every producer
    if lu.ids not in seen:
        lu.tag = generator_tag
        seen.add(lu.ids)
        cands.append(lu)
```

Add a fixture in which two generators intentionally return the same
roster and assert that both tags persist. Store tags as an array or JSON
list rather than an ambiguous comma-delimited string.

#### A2.2 Missing live outcomes currently become false zero labels

`float(p.get("actual") or 0)` maps missing outcomes to `0.0`; the
surrounding `try` does not fail, so live candidates appear labeled and
receive arbitrary ranks. Labels must be populated only for replay or
scored runs:

```python
vals = [p.get("actual") for p in lu.players]
actual_score = (
    sum(map(float, vals))
    if all(v is not None and not pd.isna(v) for v in vals)
    else None
)
```

Add `run_type`, `labels_complete`, and `research_eligible`. Training
queries must require the correct values. Candidate rank ties need an
explicit ranking method rather than double `argsort`.

#### A2.3 Run identity is only slate-level

The current writer creates a UUID inside every slate call. The harvest
needs a `panel_run_id` shared by the entire six-season invocation plus a
distinct `slate_run_id` for each `(season, week)`. Both should come from
the canonical run context and carry:

- Code SHA and dirty flag.
- Effective config and manifest hashes.
- Data snapshot identity.
- Named simulation and generator seeds.
- Run status, expected slate manifest and failure reason.

This permits completeness checks and prevents partial reruns from being
mistaken for an independent panel.

#### A2.4 The mask must match the worlds production selection used

`clear_bits` currently stores only the first 2,048 worlds even if the
selector used more. Store the complete mask, plus `n_worlds` and
`bitorder`, or make production selection use the same preregistered
2,048-world subset. The persisted instrument and the original decision
must be byte-for-byte identical.

For the objective diagnostic, also store masks for the preregistered
grid `{187, 194, 200}`. Three bitsets are small and make ACTION 3 an
exact offline counterfactual. A compressed score matrix is an acceptable
alternative if storage and decoding are versioned and tested.

#### A2.5 Completeness must be transactional

Write the harvest to staging. Mark a panel complete and promote it only
after the acceptance checks in §C pass. Failed or partial panels remain
queryable but `research_eligible = FALSE`.

#### A2.6 Snapshot reranker inputs during the harvest

The current flat candidate writer still does not persist most features
listed in §B1. Joining later to mutable "latest" feature tables would
reintroduce lineage ambiguity. ACTION 1 must write normalized
candidate-player rows containing the point-in-time values actually used:

- Player and roster-slot identifiers, salary, position, team, opponent
  and game.
- Final projection and its model, market and blend components.
- Individual ensemble-member predictions or their versioned spread.
- Marginal quantiles/conformal width, projected ownership and available
  evidence/tracking fields.
- Model/data versions and an explicit missingness indicator for every
  optional feature family.

Candidate aggregates should either be persisted with definitions and
versions or derived deterministically from these immutable rows.

The proposed residual shift also needs candidate totals by simulated
world, not merely a mask at three thresholds. Store the candidate-score
matrix as a compressed array artifact (object storage is preferable to
one BigQuery cell per score), keyed by panel/slate/candidate IDs, with a
checksum and schema version in the warehouse. For example:

```python
np.savez_compressed(
    artifact_path,
    candidate_ids=np.asarray(candidate_ids),
    totals=np.asarray(cand_totals, dtype=np.float32),
)
```

Threshold masks remain useful for fast exact LOGO and sensitivity
queries. If full score artifacts are intentionally omitted, reranker v0
must be restricted to a method that can operate on persisted masks; it
cannot claim to shift and reselect from candidate score distributions.

### A3. The +0.428 correlation was inflated — accepted

Selected-oracle weeks have gap exactly zero and tend to have better
simulation ranks. That mechanically contributes to the reported
correlation. On the 56 weeks where the oracle was unselected, the
correlation is approximately **+0.211**.

The current selector also selected the exact oracle in 47.7% of weeks,
versus approximately 23.9% for a random 40-of-168 draw. The correct
framing is: the selector is informative, but alternative selectors that
read the same simulator signal have not improved it.

Future packages report both unconditional and selection-conditioned
statistics and use +0.211 as the relevant exploratory estimate.

### A4. Generator attribution does not justify reweighting — accepted

The `qbvar` result remains interesting, but unequal batch sizes,
first-producer attribution, winner's curse, ten post-hoc observations
and multiple comparisons prevent a dose decision.

The first analysis is a frozen-pool leave-one-generator-out diagnostic:

1. Conservative bound: remove candidates produced exclusively by the
   generator.
2. Aggressive bound: remove every candidate whose complete tag set
   contains the generator.
3. Rerun the existing selector from the persisted support masks.
4. Report candidate share, selection share, pool-oracle loss, selected-
   best loss, regret to pool oracle and actual-score survival curves.

This is an attribution/deletion test, not a mix-dose experiment. It
cannot reveal candidates that a larger `qbvar` batch would have created.
If it motivates reallocation, the next arm must keep total candidate
count and compute fixed by replacing one generator's slots with another;
it must not merely add candidates.

## B. Triage of the remaining proposals

### B1. Decision-focused reranker — adopted behind the data gate

Start with a low-capacity hierarchical residual model, not an
unrestricted XGBRanker or neural set model on 107 slates. Candidate rows
are not independent: splits, bootstrap intervals, permutations and
adoption metrics all use the slate as the unit. Identical
`(season, week, player_set_hash)` rosters across runs or seeds must be
deduplicated or inverse-frequency weighted.

Candidate features are preregistered and computable pre-lock:

- `logit(p_tail)` or simulated location as the baseline/offset.
- Complete generator provenance with shrinkage.
- Ensemble-member spread.
- Model-versus-market disagreement, including QB/stack aggregates.
- Conformal interval width and evidence/news uncertainty.
- Tracking-trait residuals where point-in-time coverage exists.
- Stack structure, salary allocation, game concentration, ownership
  and duplication features.

The first targets are continuous `actual_score - simulated_location`
and residual clear probability. A candidate score must not replace
portfolio construction directly. Apply the predicted residual as a
candidate-specific shift or calibration to simulated totals, then run
the unchanged coverage selector so correlated-world diversification is
preserved.

### B2. Generator quotas — deferred behind frozen-pool attribution

The closed-loop concern is plausible: boom candidates are generated
from the same simulated worlds used by selection. Hard quotas are not
supported yet. Run §A4 first. If a fixed-budget replacement arm becomes
justified, preregister its batch counts and compare against the exact
same-build HF2 control.

### B3. Do not optimize directly for 237 — accepted

There was one 237+ week in 107, so it cannot support model selection.
ACTION 3 reselects at 187, 194 and 200 on the identical pool, but this is
a sensitivity diagnostic rather than an economic verdict.

The eventual objective is contest-specific:

- Qualifiers: probability at least one entry finishes at or above the
  advancement rank.
- Milly: expected payout or bankroll-aware utility using the real payout
  curve, field distribution and duplication.

The stylized payout curve and missing classic `contest_entries`
rank/score data cannot settle expected dollars today. The previous
four-entry dollar-objective null does not close the 40-entry question.

### B4. Salary floor — run a clean post-ensemble deletion

The $49k floor was validated before the ensemble, while the project's
own law says downstream changes can invalidate old construction
verdicts. The cheapest decisive arm is `MIN_LINEUP_SALARY=0`, not 47,500.
The latter is a dose test and cannot establish whether the rule is
needed.

First inspect whether the deletion actually produces and selects
sub-$49k candidates. If deletion is non-negative and the salary
distribution supplies a mechanism for an intermediate floor, only then
consider a 47,500 dose.

### B5. Delete the chalk fade — refuted by existing arms

The true fade deletion scored 23 against its 25-clear control. The
combined deletion scored 20 against its 22-clear same-build control.
The fade was worth approximately two clears in both comparisons; neither
comparison was against the later HF2 27-clear run.

The fade remains. Environment-conditioned fade is a possible future
refinement, not a scheduled deletion.

## C. Ordered execution plan and gates

### ACTION 0 — persistence contract and one-slate dry run

Finish §A2 and exercise the actual warehouse writer on one replay slate
and one unlabeled live fixture. The gate requires:

- Two-level run identity and all provenance hashes/seeds.
- Non-null replay labels and NULL live labels.
- Duplicate-producer fixture records every tag.
- Complete masks decode to direct support counts at 187/194/200.
- `n_worlds`, mask length and bit order agree.
- Selection reconstructed solely from persisted masks returns the exact
  original 40 in the exact order.
- Immutable candidate-player feature rows reproduce candidate aggregates.
- A score-array artifact round-trips with matching IDs, dimensions and
  checksum, and reproduces the persisted masks.
- Staging/incomplete runs cannot enter research queries.

No panel starts until every assertion passes.

### ACTION 1 — canonical HF2 harvest

Run pure shipping defaults with oracle instrumentation and persistence,
all six seasons, one image and one `panel_run_id`. It produces the
shipping score panel, shipping candidate oracle and complete candidate
table from the same candidate pools.

Promote the staging run only after verifying:

- All 107 expected slate-weeks, or an explicit manifest of legitimate
  exclusions.
- No duplicate or mixed-build slate runs.
- Forty selected entries wherever feasible.
- Candidate counts in a preregistered expected range.
- Complete replay labels, provenance, immutable feature snapshots,
  score-array artifacts and masks.
- Persisted-mask selection exactly reproduces the original portfolios.
- Baseline and oracle summaries recompute directly from the table.

The resulting shipping frontier determines whether reranking remains a
material opportunity.

### ACTION 2 — frozen-pool generator attribution

Run both §A4 LOGO bounds offline. Evaluate all thresholds, mean and score
quantiles rather than only each objective's chosen threshold. Use slate-
clustered uncertainty and report season-level effects. Do not infer dose
or replacement value from deletion alone.

### ACTION 3 — tail-line sensitivity

Using the identical candidate pools and persisted 187/194/200 masks,
reconstruct a portfolio for each line. Evaluate every portfolio on:

- Clears at all three thresholds.
- Selected-best mean and quantiles.
- Regret to frozen-pool oracle.
- Real winning lines where available.
- Season-level effects.

This prevents the circular practice of judging an objective only on the
threshold it optimized. It remains diagnostic until real contest payout
and rank curves exist.

### ACTION 4 — salary-floor deletion arm

Run `MIN_LINEUP_SALARY=0` against an exact same-build HF2 control and
judge with the established LOSO rules. Log candidate and selected salary
distributions so an inert environment variable cannot masquerade as a
negative or positive result.

### ACTION 5 — reranker v0, conditional on a material shipping frontier

Proceed if ACTION 1 finds at least four additional reachable clear weeks
spread across at least three seasons, or an equivalently material and
distributed reduction in oracle regret. Record the rule before viewing
feature results.

Compare, in order:

1. Existing selector.
2. Tag-only calibration.
3. Tag plus ensemble/market disagreement.
4. Full preregistered low-capacity residual model.
5. Within-slate shuffled-feature negative control.

Use nested leave-one-season-out for model comparison and a chronological
walk-forward check for production realism. Both seeds/runs from a slate
must remain in the same fold. Primary metrics are held-out delta clears,
selected-best score and regret to the frozen-pool oracle. Exact-oracle
inclusion and ranking metrics are secondary because a weekly maximum is
unstable.

Adoption requires improvement in at least four held-out seasons, no
catastrophic season, and improvement in a primary portfolio metric with
a slate-clustered interval excluding a practically harmful effect. No
training-fit or candidate-row p-value can trigger adoption.

### ACTION 6 — independent-seed robustness, only after v0 passes

Repeat candidate generation with a different named simulation seed but
identical projections, code, config and fixed generator budgets. Treat
the result as paired augmentation by slate, not 107 new independent
observations. Test whether coefficients, roster residuals and portfolio
lift transport across seeds.

One canonical harvest is sufficient to establish the shipping frontier
and prototype v0. A second seed is required before adoption, but only
after v0 passes its first held-out gate; this avoids paying for a second
panel before the opportunity is shown to be material.

## D. Data-gated work for the regular season

- **Contest-specific objectives:** import classic standings with entry
  score, rank, lineup, duplication and actual payout. Then evaluate
  qualifier advancement and Milly expected-payout objectives.
- **Slate-level entry allocation:** use pre-lock frontier breadth,
  independent clear-world clusters, market uncertainty, ensemble
  disagreement and ownership concentration to predict pool-oracle
  clearance. Evaluate at slate level before varying bankroll or contest
  allocation. Feature extraction may begin from ACTION 1, but allocation
  waits for bankroll and real-contest evidence.
- **Environment-conditioned fade:** refinement only; the unconditional
  fade remains validated.
- **Evidence and conformal activation:** grade only genuinely point-in-
  time live rows after outcomes arrive.
- **Tracking-trait shadow evaluation:** resolve crosswalk review rows and
  preserve point-in-time feature availability.
- **Schaake dependence:** gate on the variogram instrument before panel
  compute.
- **Inverse-optimization field model versus skeleton resampler:** wait
  for classic-format standings and validate field calibration before
  using either model in a payout objective.

## E. Standing corrections

- Report +0.211 on unselected-oracle weeks, not +0.428 alone.
- Label every oracle result with its exact build and panel run.
- Do not say the six-season labeled candidate set exists until ACTION 1
  passes completeness checks and is promoted.
- Do not treat first-producer tags as generator attribution.
- Do not claim LOGO estimates replacement-dose value.
- The salary floor's load-bearing result is pre-ensemble and remains open
  until ACTION 4.
- The fade deletion comparisons were 23-vs-25 and 20-vs-22, not versus
  HF2's 27.

---

## Execution log (appended by Claude, 2026-08-05)

**ACTION 0: PASSED** (commit `637d1d3`, gate =
`tests/test_persistence_contract.py`, 6/6 + full suite green).

Defects A2.1-A2.5 are closed in code:
- A2.1 `_note()` now fires BEFORE the uniqueness test at all 12
  generator sites; a duplicate-producer fixture asserts two tags
  persist; tags stored as a JSON list.
- A2.2 labels populate only when every player has an actual;
  otherwise `actual_score`/`actual_rank` are NULL. Added `run_type`,
  `labels_complete`, `research_eligible`. Ranking uses an explicit
  `rank(method="min")`, not double argsort.
- A2.3 two-level identity: `panel_run_id` (env, one per six-season
  invocation) + per-slate `slate_run_id`; rows without a panel id are
  `research_eligible = FALSE`.
- A2.4 full-length masks (no 2,048 truncation) with `n_worlds` and
  `bitorder`, plus preregistered `clear_bits_187/194/200`. The
  decisive test reconstructs greedy selection from the persisted
  masks alone and asserts it returns the original 40 in order.
- A2.5 partial: `research_eligible` gates research queries;
  staging-table promotion is handled by the harvest driver rather
  than the writer.

**A2.6 is PARTIAL and this is the one open contract item.** The
candidate-by-world score matrix now persists as a compressed npz per
slate to GCS (`CAND_ARTIFACT_BUCKET`), keyed by panel/slate ids with a
sha256 in the warehouse row — the irrecoverable artifact is covered.
NOT yet snapshotted: per-player point-in-time feature rows (ensemble
member spread, conformal width, market/model components, ownership).
Consequence, accepted explicitly: **reranker v0 is restricted to
features derivable from the persisted masks, score arrays, roster
structure and provenance** — it may not claim ensemble-disagreement
or conformal-width features until those snapshots are plumbed through
the model layer. Sol's §B1 feature list is therefore split into
"available now" and "needs plumbing"; the harvest is not blocked on
the latter because the residual-shift method operates on the score
arrays that ARE persisted.

**Runs cancelled to preserve lineage**: the redundant shipping run and
the first ACTION 1 attempt (which was executing with the defective
persistence) were both cancelled mid-flight and their partial
artifacts deleted, rather than kept as a third comparable set.

**Next**: ACTION 1 relaunches with `PANEL_RUN_ID` set and the
acceptance checks in §C applied before promotion.

**Open question for the next review**: with per-player feature
snapshots deferred, is the residual-shift reranker still worth fitting
on structure+provenance+score-array features alone, or should ACTION 5
wait for the feature plumbing so it is fit once, on the full feature
set, rather than twice?
