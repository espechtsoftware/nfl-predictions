# LR8 training-source smoke v2: salary-boundary repair protocol

Date: 2026-08-21
Status: bounded source repair, not a scientific-result or launch license

## Closed predecessor

Smoke v1, `20260820-lr8-training-source-smoke-v1`, is permanently closed.
Its sole execution, `atlas-md-prefix-r4-smoke-wqzpc`, reached strict
`Completed=False` with one failed task and zero retries. The retained failure
closure has SHA-256
`79d496df434dbe007041cc51a356052ff15a5069ce0059d3418aa00a6f1d2636`;
the canonical failed-execution metadata has SHA-256
`2c357f17410f61868657a55ea14206641054d1da06f165f0cd65c620b0933ca6`.
The closure records that no result body was read, no historical-outcome lease
was acquired, no production change was licensed, and no relaunch is licensed.
V1 must never be passed to a success finisher or relaunched.

The terminal traceback stopped in
`run_lr8_training_source.py:_catalog_inputs` when
`residual_world_columns.PlayerSpec` correctly rejected a floating salary as
not being an integer. Metadata-only schema inspection established the source
fact that `nfl_predictions.slate_player_features.salary` is `FLOAT NULLABLE`
(3,478,322 table rows at inspection), not `INT64`. This is a source-boundary
type defect, not evidence that the DK salary value itself is fractional.

## Sole repair

The canonical query and create-once extract continue to retain the source
salary exactly as a FLOAT JSON number. There is no SQL cast, rounding,
truncation, imputation, fill, or filtering repair. Immediately before
constructing `PlayerSpec`, the runner accepts a Python/NumPy integer directly,
or a Python/NumPy floating scalar only after all of the following exact checks:

1. it is not a boolean;
2. it is finite;
3. its stored floating value is mathematically integral;
4. integer conversion compares equal to the stored floating value; and
5. it is positive.

Only then is the proved value converted to `int`. Fractional values (including
values that could be rounded), NaN, either infinity, booleans, strings, nulls,
and nonpositive values fail closed. The raw query extract and its content
identity remain truthful and independently inspectable. The exact query text
continues to select `p.salary` without a cast, and the before/after table
metadata receipt continues to bind the complete source-schema hash.

No lattice, season/week, projection seed, world count, prior-season fit,
candidate budget, exact-CBC law, DK-only legality law, former-house-rule
status, evidence contract, or target/candidate outcome prohibition changes.

## Fresh successor identity

- attempt: `20260821-lr8-training-source-smoke-v2`
- local directory:
  `reports/lr8-training-source-smoke-runs/20260821-lr8-training-source-smoke-v2/`
- result prefix:
  `gs://nfl-predictions-503414-raw/research/lr8-training-source/20260821-lr8-training-source-smoke-v2/`
- governance prefix:
  `gs://nfl-predictions-503414-raw/research-governance/lr8-training-source-smoke/20260821-lr8-training-source-smoke-v2/`
- reused job: `atlas-md-prefix-r4-smoke`, UID
  `51545eb0-59e4-424e-91c9-98dd318285f4`
- execution budget: exactly one task, 8 CPU, 32 GiB, six hours,
  `maxRetries=0`

The v2 prepare path must validate the exact retained v1 execution name,
canonical failure-closure SHA-256, and canonical terminal-metadata SHA-256
before any cloud read or mutation. The offline transport test opens the actual
retained files and poisons both an alternate failed execution and a closure
whose metadata hash was recomputed consistently. It then applies
the existing update-only, idle/unscheduled-job, empty-prefix, exact-build,
create-once intent, one-execution, terminal-metadata-first, and no-relaunch
transport laws under the fresh v2 paths. It never creates or deletes a Cloud
Run job and never acquires the historical-outcome lease.

## Validation and stop point

Offline validation must include the complete source-runner suite with the
catalog salary carried through the query-extract round trip as FLOAT, positive
acceptance cases for Python/NumPy/pandas exact integer scalars and integral
FLOAT scalars, and poisons for fractional, non-finite, boolean, string, null,
and nonpositive values. The transport suite must prove the fresh v2 identity
and byte-pinned, terminal-failed v1 predecessor gate. Python compilation, Ruff,
shell syntax, and whitespace checks must also pass.

No real BigQuery query, Cloud Build, Cloud Run update/execution, GCS write,
result-body read, historical-outcome lease action, or full-source execution is
licensed by this implementation checkpoint. A separate operator/source review
must occur first. After that review, the only permitted reality contact is the
fresh, outcome-blind v2 smoke under the unchanged one-shot transport; v1 is
not retried. A v2 terminal failure is again permanent no-relaunch.

## Implementation identities

The exact implementation SHA-256 values are recorded after the bounded patch
and validation are byte-final:

- `scripts/run_lr8_training_source.py`:
  `9272f95abfd134fb566b6531705dc8f38eda38ae39b57f5e810b0aa93e1e919f`
- `tests/test_run_lr8_training_source.py`:
  `4ccad0a52518e70057785b8c3261f0e52c83de35ac2b340f52b8ecbe310c8c32`
- `scripts/finish_lr8_training_source_smoke.py`:
  `ec4afcf94e617b05c0af4af49566a44dc74e3ec8b7159d7f7ea16071b2e97a46`
- `scripts/cloud_lr8_training_source_smoke.sh`:
  `762d0cdddf60be5565892e9a59415c1f7a7f645bcce6b172cee526963abe1bf4`
- `scripts/watch_lr8_training_source_smoke_queue.sh`:
  `ed90925e5103487d58174671eb399a8f01d788bc220421533fab305cc7bd1fd2`
- `tests/test_lr8_training_source_smoke_transport.py`:
  `06cdfa91666003c981340a9078565b66dc4ea9cf286e5b7024148f46012c672c`
