# Canonical-v3 paid/deployment bounded R3 repair candidate

Date: 2026-09-08

Exact repaired R2: `7fbcf5c310185e7ce5d6aa183485318bf0bbe10a`

Independent R2 HOLD: production-main commit
`12532ec6842967e4b0cece0740e32fbb068aa29b`, report
`reports/2026-09-08-canonical-v3-paid-deployment-r2-independent-review.md`

Repair branch: `codex/canonical-v3-paid-r3-repair-20260908`

Disposition: **review candidate only; do not merge, build, deploy, load, score,
read outcomes, or use for paid output before independent review**

## Executive disposition

This is the narrow activation/cutover R3 requested by the independent HOLD.
It preserves all accepted R2 engine-result, native/combined-world, and
provider-build-law work. It does not change scoring, generation, selection,
money policy, experiment defaults, frozen v1/v2 algorithms, or canonical-v3
Neo4j semantics.

The executable boundary now has two objects with different authority:

1. a generation-pinned **pretraffic deployment authorization** lets Cloud Run
   stage one exact runtime revision but cannot enable a money response; and
2. a distinct create-once **final activation authority** can exist only after
   the exact active revision and canonical 100% provider traffic have been
   attested. Every paid-v3 request must exact-read and validate this final
   posttraffic object.

Thus a successful traffic mutation followed by a failed final attestation and
failed rollback leaves the serving revision's money path disabled because no
valid final activation object exists.

## Authority and runtime repair

- The pretraffic object moved to the policy-derived
  `.../<revision>/deployment-authorization.json` URI and has the distinct
  `paid-classic-pretraffic-deployment-authorization/v1` schema. Its exact
  `{uri,generation,sha256,bytes}` remains in the staged runtime environment so
  the revision and its provider attestation are immutable and cross-bound.
- The money gate remains the policy-derived `.../<revision>/activation.json`
  URI, but its closed schema now requires the exact deployment-authorization
  identity and hash plus the complete final active-traffic attestation.
- Final validation reopens both nested authorities, requires the traffic-stage
  receipt, exact 100% provider traffic, the exact active revision, and
  agreement on project, region, build, source commit, immutable image,
  service, revision, and deployment-authorization identity.
- Runtime first exact-reads the environment-pinned deployment authorization,
  then snapshots the current final object generation and downloads that exact
  generation. It checks byte length and hash before parsing. The returned
  activation envelope and downstream paid catalog use the exact **final**
  object identity and authority hash, not the staging object.
- The active Week-1 v2 successor uses the same two-object runtime gate. A
  separate injectable final-object reader was added only for offline
  adversarial validation; production defaults to the exact GCS reader.
- A provider-authenticated absence check runs before the first Cloud Run
  mutation. A pre-existing final gate or any inability to distinguish
  NotFound from permission/transport failure stops the deployment.

The existing `PAID_V3_ACTIVATION_*` environment names are retained as the
immutable coordinates of the pretraffic deployment authorization so a
revision can be built without self-reference. They are not accepted as the
money authority; the runtime independently requires the final object.

## Cutover and rollback repair

The deployment order is now:

1. authenticate the exact build and prove the create-once final gate absent;
2. stage and attest a no-traffic revision;
3. create, upload, and exact-reopen the pretraffic deployment authorization;
4. stage and attest the exact runtime revision with that immutable identity;
5. arm rollback and move traffic;
6. authenticate the exact active revision and 100% provider traffic;
7. durably upload the active-traffic receipt while the final money gate is
   still absent;
8. construct the final authority from the exact deployment authorization and
   active-traffic receipt; and
9. disarm rollback immediately before the atomic
   `if-generation-match=0` final upload, the last state change.

Before step 9, every error and signal attempts restoration of the complete
provider-exported prior service. If both final attestation and rollback fail,
the final upload has not run and the runtime rejects. At step 9, an ambiguous
upload has only two safe results: the atomic create did not occur and the gate
is absent, or the complete already-validated posttraffic authority exists.

## Adversarial coverage

New cases prove that:

- the exact pretraffic object alone cannot satisfy the money boundary;
- a final object with a rehashed preactivation traffic receipt is rejected;
- final-gate existence and absence-check uncertainty both fail closed;
- the successful runtime path consumes the exact posttraffic final object and
  exposes its identity downstream; and
- the real deployment shell, run with deterministic provider stubs, applies
  traffic and then encounters both a final-attestation failure and a rollback
  failure without publishing `activation.json`. The retained runtime state
  consequently lacks a valid paid gate.

## Changed surface

- `scripts/deploy_paid_boundary_v3_image.sh`
- `src/nfl_dfs/optimizer/paid_classic_deployment_v3.py`
- `src/nfl_dfs/app/week1_operating_book_api.py`
- `tests/test_paid_classic_deployment_v3.py`
- `tests/test_week1_operating_book_api.py`
- this report and `HANDOFF.md`

No accepted R2 engine, world-binding, build-law, scoring, selector, generator,
policy, graph, or experiment-default module is changed.

## Validation

A fresh machine-wide process census immediately before each serial pytest run
showed no other `python -m pytest` process. The lane was announced to the two
other active reviewers before use and explicitly released afterward.

Focused repaired surface, with explicit source path and no cache provider:

```text
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src \
  /home/erich/projects/nfl-predictions/.venv/bin/python -m pytest \
  -q -o addopts='' -p no:cacheprovider \
  tests/test_paid_classic_book_v3.py \
  tests/test_paid_classic_deployment_v3.py \
  tests/test_week1_operating_book_api.py \
  tests/test_week1_operating_book_export.py

131 passed in 7.67s
```

The exact focused release-gate module list from
`cloudbuild.paid-boundary-v3.yaml` passed **281/281** in 20.88 seconds.
After that serial gate, the final upload precondition was strengthened from
`--no-clobber` to the provider-atomic `--if-generation-match=0`; the affected
real-shell failure exercise and deployment-order assertion were rerun directly
and passed. No Python runtime logic changed after the serial gates.

Additional checks:

- `scripts/build_winner_registry_v2.py --check`: verified, 117 observations,
  four source artifacts, registry remains candidate-only/unadjudicated;
- `git diff --check`: pass;
- `bash -n` for both paid build/deployment wrappers: pass;
- paid Cloud Build YAML parse, four-step shape, queue TTL, and service-account
  assertions: pass;
- Python compilation of every modified Python/test module: pass; and
- direct activation/runtime and executable failure-path exercises outside
  pytest: pass.

Ruff 0.16.5 from the lab environment was used for import normalization. A
full lint scan continues to report the R2 module's existing timezone-alias and
broad fail-closed exception-style rules; no accepted R2 behavior was churned
to satisfy stylistic findings.

## Scope boundaries and next action

No Cloud Build was submitted. No Cloud Run service, revision, traffic, GCS
object, Neo4j graph, lineup, score, outcome, contest entry, or paid artifact
was read or mutated. Provider documents and mutations in tests are local
fixtures/stubs only.

The next action after a green serial release gate is independent review of the
exact repair commit against the R2 HOLD reproduction. Do not merge or take a
cloud/paid action merely because the candidate tests pass.
