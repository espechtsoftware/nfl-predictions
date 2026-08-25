# Foundry v12 Gate G0 and first T230 smoke runbook

**Frozen:** 2026-08-25 before either v12 lane completed
**Amended:** 2026-08-25 after the Rule-1 gap was identified; the original
support census remains Gate 5A and the mandatory full-stack reality contact is
Gate 5B
**Scope:** outcome-blind lane closure, combined-panel publication, one
accepted-slate support census, and one disposable ordinal-zero full T230
science-stack smoke before any canonical transport contract
**Forbidden here:** realized outcomes, T230 effect inspection, retries,
duplicate lane operators, corpus fill, graph mutation, production policy, or
promotion decisions

## Frozen identities

```text
repository root:
  /home/erich/projects/nfl-predictions

lane A local terminal envelope:
  reports/corpus-parametric-runs/20260823-foundry-production-v12a/transport-live-v12a/batch-accepted.json

lane B local terminal envelope:
  reports/corpus-parametric-runs/20260823-foundry-production-v12b/transport-live-v12b/batch-accepted.json

combined panel object:
  gs://nfl-predictions-503414-corpus-parametric/research/corpus-parametric-research/panels/20260823-foundry-production-v12/foundry-v12-combined-panel-index-v1.json

combined panel local run directory:
  reports/corpus-parametric-runs/20260823-foundry-production-v12-panel-index/panel-index-live

first smoke slate:
  2023-w01
```

The first smoke slate was frozen because it is source task 0, already has
independent v12 acceptance history, and has prior outcome-blind support
context. It was not chosen from a T230 census or realized score.

## Gate 1 — wait for the two original controllers

Do not start a second controller. Lane A must print exactly:

```text
lane a COMPLETE through task 27
```

Lane B must print exactly:

```text
lane b COMPLETE through task 25
```

Each task must have one nonempty verifier-accepted receipt. A failure or
incomplete lane stops this complete-panel path and requires a separately
reviewed non-completion disposition.

## Gate 2 — finish each complete batch once

Run the matching command only after that lane's COMPLETE line. These are the
frozen wrappers, not bare transport invocations.

Lane A:

```bash
(
  set -euo pipefail
  source /home/erich/projects/nfl-predictions/scripts/foundry/foundry_v12a_env.sh
  cd "$CORPUS_PARAMETRIC_SOURCE"
  bash scripts/cloud_corpus_parametric_v1_reuse.sh --execute finish-batch
)
```

Lane B:

```bash
(
  set -euo pipefail
  source /home/erich/projects/nfl-predictions/scripts/foundry/foundry_v12b_env.sh
  cd "$CORPUS_PARAMETRIC_SOURCE"
  bash scripts/cloud_corpus_parametric_v1_reuse.sh --execute finish-batch
)
```

Expected terminal facts:

| Lane | Batch mode | Tasks | Matrix cells |
|---|---|---:|---:|
| A | `lane-a-28-task` | 28 | 196 |
| B | `lane-b-26-task` | 26 | 182 |

Each local envelope must be canonical
`corpus-parametric-batch-accepted/v1`, complete and accepted. The panel
builder treats it only as the carrier of `.batch_acceptance`; the exact
generation-pinned remote batch acceptance and its complete authority graph
are replayed as authority.

## Gate 3 — validate the combined panel without publishing

Use committed code. The two distinct local receipt paths prevent a mode
collision.

```bash
set -euo pipefail
ROOT=/home/erich/projects/nfl-predictions
PANEL_RUN_DIR="$ROOT/reports/corpus-parametric-runs/20260823-foundry-production-v12-panel-index/panel-index-live"
PANEL_URI='gs://nfl-predictions-503414-corpus-parametric/research/corpus-parametric-research/panels/20260823-foundry-production-v12/foundry-v12-combined-panel-index-v1.json'
A_RECEIPT="$ROOT/reports/corpus-parametric-runs/20260823-foundry-production-v12a/transport-live-v12a/batch-accepted.json"
B_RECEIPT="$ROOT/reports/corpus-parametric-runs/20260823-foundry-production-v12b/transport-live-v12b/batch-accepted.json"
mkdir -p "$PANEL_RUN_DIR"

env PYTHONPATH="$ROOT/src" "$ROOT/.venv/bin/python" \
  "$ROOT/scripts/build_corpus_v12_panel_index_v1.py" \
  --lane-id v12a \
  --lane-id v12b \
  --lane-terminal-identity "$A_RECEIPT" \
  --lane-terminal-identity "$B_RECEIPT" \
  --panel-uri "$PANEL_URI" \
  --receipt-output "$PANEL_RUN_DIR/validate-only.json" \
  --validate-only
```

Require `lane_count=2`, `accepted_slate_count=54`,
`exact_input_replay_verified=true`, `published=false`, a valid self-hash, and
all authority fields false.

## Gate 4 — create-once publish and replay the panel

```bash
env PYTHONPATH="$ROOT/src" "$ROOT/.venv/bin/python" \
  "$ROOT/scripts/build_corpus_v12_panel_index_v1.py" \
  --lane-id v12a \
  --lane-id v12b \
  --lane-terminal-identity "$A_RECEIPT" \
  --lane-terminal-identity "$B_RECEIPT" \
  --panel-uri "$PANEL_URI" \
  --receipt-output "$PANEL_RUN_DIR/published.json" \
  --execute
```

Require `mode=create_once`, `published=true`, exact reopen and semantic replay,
and one `panel_object_identity` whose URI, SHA-256 and byte count match the
frozen panel and publication receipt. An equal pre-existing object is an
idempotent reopen; differing content is a hard collision.

## Gate 5A — run one accepted-slate support census

This reads only generation-pinned panel/source/world artifacts. It does not
read historical contest outcomes. `/usr/bin/time -v` is the benchmark source;
retain its stderr with the canonical result.

```bash
SMOKE_DIR="$PANEL_RUN_DIR/extreme-tail-smoke-2023-w01"
mkdir -p "$SMOKE_DIR"

env PYTHONPATH="$ROOT/src" /usr/bin/time -v \
  "$ROOT/.venv/bin/python" \
  "$ROOT/scripts/run_corpus_extreme_tail_one_slate_smoke_v1.py" \
  --panel-publication-receipt "$PANEL_RUN_DIR/published.json" \
  --slate-id 2023-w01 \
  --result-output "$SMOKE_DIR/result.json" \
  >"$SMOKE_DIR/stdout.json" \
  2>"$SMOKE_DIR/time-v.txt"
```

Require one authoritative-dose result, the exact accepted membership and
artifact identities, a replayed support census, all false-authority fields,
and matching canonical output/self-hashes. Record elapsed time and maximum
resident set size in `HANDOFF.md` before deciding whether any selector can
scale.

This smoke result is a diagnostic and benchmark artifact. It is not a
per-slate publication acceptance and must never be promoted into the later
54-slate authoritative join without that runner independently replaying the
carrier-bound inputs.

This census-only smoke does **not** satisfy `CLAUDE.md` Rule 1 for T230. It
does not execute the four-law retrieval suite or support-switch path.

## Gate 5B — mandatory disposable full-stack Rule-1 smoke

Before image evidence E, the transport contract, execution authority, the
canonical T230 benchmark, or any canonical T230 result is published, run the
tracked candidate image on the reused ordinal-zero Cloud Run job. The
candidate must already be resolved to digest D. If the smoke exposes a defect,
repair the source, build a new D, and repeat this gate. Once this gate passes,
that exact D becomes the release candidate and is never rebuilt.

The only science command inside the one-task, retry-zero, 8-CPU/32-Gi Cloud
Run execution is:

```bash
export FOUNDRY_T230_PREFREEZE_SMOKE_ENABLED=1
export T230_PREFREEZE_CANDIDATE_IMAGE="$D"

env LC_ALL=C PYTHONPATH=src \
  /usr/bin/time -v \
  -o /tmp/t230-prefreeze-ordinal-0.time-v.txt \
  python scripts/run_corpus_extreme_tail_t230_prefreeze_smoke_v1.py \
  --execute \
  --receipt-output /tmp/t230-prefreeze-ordinal-0.structural.json
```

There is no slate, dose, threshold, strategy, budget, result URI, output
prefix, or authority override. The command fixes source ordinal zero and
requires `2023-w01`; exact-replays the raw G0 receipt, both lane terminals and
the generation-pinned 54-member panel; reconstructs the accepted carrier and
50,000-world matrix; and calls the same private no-knob census -> four-law
suite -> support-switch helper used by the production worker.

The science CLI writes only one local create-once compact structural receipt.
It never publishes GCS, calls the canonical transport, records support
observations, or serializes ranks, books, selected lineup IDs, metrics, scores
or comparative effects. The receipt binds:

- exact G0 panel object identity and ordinal-zero membership hashes;
- candidate source commit and immutable image D;
- whole-file hashes for the panel executor and smoke CLI, each verified equal
  to its Git blob at that commit;
- Cloud Run job/execution/task and Linux process identity;
- reconstruction/matrix, census, four-law registry/implementation, suite and
  support-switch structural hashes; and
- all outcome, effect-inspection, publication, analytical, promotion,
  decision and release authorities false.

The outer candidate-D worker wrapper, not the science CLI, must strictly
parse and create-once publish the raw GNU `time -v` mechanics, the compact
receipt, and a captured successful Cloud execution projection under the
separate prefreeze-smoke evidence namespace. That projection must bind D, the
reused job, service account, 8 CPU, 32 GiB, one task, parallelism one,
`maxRetries=0`, task index/attempt/count `0/0/1`, execution completion, compact
receipt identity and `runtime_binding_sha256`.

The release phase must exact-read both pinned identities and call the
importable validator directly:

```python
validate_t230_prefreeze_smoke_receipt_v1(
    receipt,
    expected_panel_object_identity=g0_panel_identity,
    expected_source_commit_sha=source_commit_sha,
    expected_immutable_candidate_image=candidate_image_d,
    require_release_runtime=True,
)
```

It must then exact-match the external execution projection to the validated
runtime binding and numeric GNU-time gate. Only that successful conjunction
may allow the Cloud Build release phase to continue to image evidence E and
`journal-evidence-and-contract`. A missing, fixture-only, failed, mismatched,
effect-bearing or false-authority-drifting receipt stops the build. No
canonical T230 object may exist before this gate passes.

## Gate 6 — support decision before selector effects

Do not inspect T230 selector effects until the census-bound support-switch
receipt is frozen:

- a fold uses literal coverage-230 only if every one of its four training
  blocks has nonzero `>=230` opportunity and the aggregate has at least 100
  opportunity worlds;
- otherwise it uses the block-robust bounded 210..250 ladder;
- the all-block final fit requires every R block nonzero and at least 125
  opportunity worlds; and
- general literal-230 nomination later requires at least 80% of all 270 folds
  and at least 80% of all 54 final fits to pass.

The current panel-summary helper may calculate that fraction only as a
non-authoritative diagnostic. It deliberately refuses authoritative mode.
Certification additionally requires the exact published-panel identity and
54 generation/content-bound per-slate receipts proving full census-and-suite
replay; do not substitute free-form or merely self-hashed policy JSON.

Only after the disposable full-stack runtime/memory gate passes may the same D
enter canonical T230 preparation and scale-out. All intended exact 4/14/80
final books must then be immutable before a controlled realized-outcome grade.
The exact scale-out receipt and two-lane publication design is frozen in
`reports/2026-08-25-t230-panel-release-and-authoritative-summary-plan.md`.
