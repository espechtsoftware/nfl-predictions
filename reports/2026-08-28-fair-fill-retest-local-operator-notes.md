# Fair fill retest local operator notes

> **Review status:** this lane remains uncommitted and is not yet a 54-slate
> evidentiary operator. The local select/evaluate boundary is executable, but
> a task-manifest-driven source loader that exact-opens the real F7/F8/F9
> authorities without opening a fold's held-out world bytes before selection
> still must be completed and tested on the sealed task-0 artifact.

## Purpose and boundary

`scripts/run_corpus_r6_fair_fill_retest_v1.py` is the local operator for the
minimum fill-strategy × construction-profile × selector historical retest
lane. It deliberately has no GCS, BigQuery, Cloud Run, contest-result, or
deployment integration. Its only score inputs are local simulated-world
matrices. Output files are create-once: an existing path is never overwritten.

The operator exposes three stages:

1. `registry` exports the nine fill strategies, F0/F7/F8/F9 construction
   profiles, seven existing selectors, and the explicit support/missing-source
   matrix.
2. `compile` validates score-free candidate-cell JSON, removes the chosen
   held-out origin before admission, proves work-dose/cohort compatibility,
   and freezes a common-count fold plan.
3. `select` opens only the four training-block matrix and publishes a
   create-once selection result.
4. `evaluate` first reopens that frozen selection result and only then opens
   the held-out simulated R-block matrix. There is no combined command capable
   of opening both inputs before selection freezes.

Realized contest results are not an accepted input. Production defaults and
deployment artifacts are not changed.

## Candidate-cell package

Candidate-cell JSON should be built and validated through
`build_candidate_cell_from_occurrences_v1` or a source-specific adapter. The
existing `candidate_cell_from_population_profile_lineups_v1` adapter can bind
validated F7/F8/F9 per-world-exact artifacts only when it receives their exact
object identity and validated crossed-task request; otherwise its output is
explicitly test-only and non-authoritative. A cell contains:

- one slate, fill strategy, construction profile, and comparison cohort;
- R0--R4 candidate occurrences with arm-independent lineup IDs and family
  tags;
- per-origin scheduled/attempted/optimal/infeasible/error work receipts;
- a complete-profile-audit claim and exact source bindings; and
- explicit false outcome/promotion claims plus a canonical self-hash.

Tagged `epi`, `game`, and `dark` subsets can be built with
`build_tagged_family_control_cell_v1`, but they remain diagnostic filters.
They are not causal replacements for regenerating those families under a
relaxed construction profile.

## Commands

Export the registries:

```bash
.venv/bin/python scripts/run_corpus_r6_fair_fill_retest_v1.py registry \
  --output /tmp/fair-fill-registry.json
```

Compile comparable cells into an R4-held-out fold:

```bash
.venv/bin/python scripts/run_corpus_r6_fair_fill_retest_v1.py compile \
  --cell /path/to/per-world-F7-cell.json \
  --cell /path/to/per-world-F9-cell.json \
  --heldout-block R4 \
  --controller-output /tmp/fair-fill-controller-R4.json \
  --plan-output /tmp/fair-fill-plan-R4.json
```

`--allow-non-authoritative` is an explicit test seam. It should not be used
for an evidentiary historical run. `--allow-diagnostic` is required when the
input cells are tagged-family isolates.

Freeze selection for one cell from its training matrix:

```bash
.venv/bin/python scripts/run_corpus_r6_fair_fill_retest_v1.py select \
  --plan /tmp/fair-fill-plan-R4.json \
  --cell-id per-world-exact-v1--F7-qb-and-bringback-relaxed \
  --full-training-matrix /path/to/per-world-F7-R4-full-training.npy \
  --selector-output /tmp/per-world-F7-R4-selectors.json
```

Only after that command succeeds, evaluate the frozen selection:

```bash
.venv/bin/python scripts/run_corpus_r6_fair_fill_retest_v1.py evaluate \
  --plan /tmp/fair-fill-plan-R4.json \
  --cell-id per-world-exact-v1--F7-qb-and-bringback-relaxed \
  --selector-result /tmp/per-world-F7-R4-selectors.json \
  --full-heldout-matrix /path/to/per-world-F7-R4-full-heldout.npy \
  --evaluation-output /tmp/per-world-F7-R4-simulated-evaluation.json
```

## Matrix package law

The two files must be NumPy `.npy` arrays saved with `allow_pickle=False`
compatible contents and exact `float64` dtype:

- rows: the cell plan's ascending full `eligible_candidate_rows`, without
  reordering;
- training columns: the four canonical training blocks in the plan's order,
  then world ordinal, exactly 40,000 columns;
- held-out columns: the plan's one held-out R block, then world ordinal,
  exactly 10,000 columns; and
- every value finite.

Matrix preparation must likewise preserve the separation: produce the four
training blocks without opening the held-out artifact, freeze selection, and
only then reopen the held-out block for evaluation. The operator revalidates
shapes, dtype, candidate provenance, and all selector input bindings.

Selection reports the frozen coverage-194, strict-200, 200/210/220 tail
ladder, and expected-max controls twice: once over the complete fit-eligible
corpus and once over the deterministic equal-size view used by the successor
selectors. This prevents the 250-row successor ceiling from being mistaken
for a full-corpus population result.

## Currently executable versus missing

With current immutable artifacts:

- F7/F8/F9 per-world-exact cells are directly adaptable and executable.
- Frozen P0 legacy mix, PB all-boom unique-fill, and F0 tagged family controls
  need a narrow adapter from their occurrence-provenance artifact into the
  candidate-cell schema.
- Boom-heavy equal-work, all-boom equal-attempt, and expanded-QBVAR cells need
  generation under the requested construction profile.
- Historical role-belief sources are not present for honest F7--F9
  regeneration; inherited incumbent role rosters must not be relabeled.
- Five-player `game`/`dark` generation is mechanically incompatible with F8's
  maximum-three-from-game rule.
- Frozen PB unique-fill may be used as a retained-count comparator, but it is
  not in the equal-attempt causal cohort because unique filling can require
  additional optimizer work.

The provisional boom-heavy and expanded-QBVAR doses are outcome-blind
controller mechanics, not promotion authority. Actual optimizer-call receipts
remain the fairness authority.

## Sealed current-bank authority bridge (2026-08-28)

`corpus_r6_fair_fill_current_bank_authority_v1.py` now supplies the real,
source-specific bridge. It validates the already sealed V6/V7-compatible
current-bank broad-selection manifest and compiles its exact 54-slate by
five-fold lattice without opening any referenced body. Selection preparation
then opens only the topology, projection bundle, one fold process budget, and
later-source catalog. The process budget must expose exactly four training
world identities; a fifth/held-out identity fails closed and is not copied
into the selection package.

The local operator commands are:

```bash
.venv/bin/python scripts/run_corpus_r6_fair_fill_current_bank_authority_v1.py \
  header --manifest /path/to/sealed-selection-manifest.json

.venv/bin/python scripts/run_corpus_r6_fair_fill_current_bank_authority_v1.py \
  prepare-selection --manifest /path/to/sealed-selection-manifest.json \
  --source 0 --fold 0 \
  --authority /path/to/topology.json \
  --authority /path/to/projection.json \
  --authority /path/to/fold-process-budget.json \
  --authority /path/to/later-source-freeze.json
```

Every supplied body is matched by its sealed SHA-256 and byte count. The CLI
has no cloud launcher and accepts no realized-outcome input.

Real sealed task-0 validation used slate `2023-w01`, fold 0 (R0 held out):

- header: 54 sources, five folds, 270 recipes, zero object-body opens;
- selection package: 3,051 candidates and R1/R2/R3/R4 only;
- real cross-score matrix: shape `[3051, 40000]`, exact `float64`;
- observed matrix SHA-256:
  `3382b98621226582552131f4de3c84ed516edf3079d227d22f156b82d05e0148`;
- sealed expected SHA-256: the same value; and
- R0 world bytes were not opened.

This proves the sealed candidate/catalog/world lineage can reproduce the
selection matrix before held-out access. It does **not** assert that any new
boom-heavy, QBVAR, role/epistemic, no-good, or quality-diversity corpus has
already been generated. Those arms remain unsupported until their own
source-specific optimizer artifacts and work receipts exist. Likewise, the
matrix replay is simulated-world evidence, not a realized historical read or
promotion decision.
