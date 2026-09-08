# Canonical-v3 paid/deployment R4 provider-readiness repair candidate

Date: 2026-09-08

Integration parent: `1d75c71f9a08fd61b281435895b59116a9b1ff3c`

Provider HOLD report parent:
`b5fe57af11729459d2b6763b1cb81446d5e4a32b`

Repair branch:
`codex/canonical-paid-r4-provider-readiness-repair-20260908`

Disposition: **code-only review candidate. The provider HOLD remains. Do not
provision, build, deploy, change traffic, activate, or emit paid output from
this report.**

## Outcome

This bounded repair addresses the two operational gaps in the R4 provider
reality check without changing the accepted R4 money-authority law:

1. every project-extra release image is now constrained to
   `google-cloud-storage>=2.16.0`, the first release with the soft-delete list
   API used by R4; and
2. a default-off operator command now describes, can explicitly provision,
   and can read-only authenticate the exact paid-v3 authority bucket.

The command is pinned to:

```text
project                 nfl-predictions-503414
project number          817589974517
bucket                  nfl-predictions-503414-paid-authority
location                us-central1
uniform access          enabled
public access prevention enforced
soft-delete retention   604800 seconds (7 days) when newly created
deployer                 user:espechtsoftware@gmail.com
runtime                  serviceAccount:817589974517-compute@developer.gserviceaccount.com
```

The required unconditional bucket IAM bindings are deployer Object Viewer
plus Object Creator and runtime Object Viewer. Existing bindings are
preserved. The apply path contains no bucket delete/recreate or existing
bucket-configuration/object update/delete/overwrite operation. Its only
existing-state mutation is adding a missing required IAM member.

## Package/build closure

The dependency census found one project dependency declaration, no standard
Python requirement/constraint/lock file, three Dockerfiles and one Cloud Build
contract already pinned to `google-cloud-storage==3.13.1`, and one standalone
LEM Dockerfile with an unbounded direct install.

The repair:

- raises the authoritative `gcp` extra from `>=2.13` to `>=2.16.0` in
  `pyproject.toml`; every Dockerfile that installs `.[gcp]` inherits the new
  floor;
- raises the standalone `scripts/lem_train/Dockerfile` direct install to the
  same floor; and
- adds an offline, `--network none` exact paid-v3 image smoke which checks the
  installed distribution version, `Bucket.list_blobs` `prefix`/`versions`/
  `soft_deleted` parameters, generation-bound `Blob`, exact reload/download,
  and conditional-create support before Cloud Build can succeed.

The paid-v3 Cloud Build release suite includes the new offline test module.
There is no new lock file and no below-2.16 direct Storage requirement remains
in a tracked Dockerfile or Cloud Build YAML.

## Default-off operator contract

The installed command is `paid-v3-authority-readiness`. With no subcommand it
is identical to `plan`: it renders canonical JSON and does not import
credentials, instantiate a Storage client, contact GCP, or authorize a cloud
mutation.

The apply path is a distinct subcommand, not a dry-run flag inversion. It
requires the exact phrase
`provision-nfl-predictions-503414-paid-authority`, resolves ADC to the exact
deployer email without printing or retaining the access token, requires the
running source/image/digest environment to match a full commit plus immutable
image argument, and writes a create-only local intent before any provider
mutation. It then:

1. fully inventories the exact bucket name in the fixed project;
2. creates it only when absent, with location, uniform access, public-access
   prevention and 7-day soft delete set on the create request;
3. validates an existing bucket and stops before IAM/object work if any fixed
   property differs; it never updates or recreates an existing bucket;
4. adds only missing unconditional required IAM members while preserving the
   fetched policy and etag;
5. conditionally creates the fixed outcome-blind capability canary only if its
   three-view history is empty; and
6. exact-reopens the provider-returned generation and writes a create-only
   receipt after the complete postcondition is authenticated.

Automatic retries are disabled on all three mutation calls. Read-only
inventory/reconciliation may retry safely, but a failed mutation response is
never followed by another mutation call.

An exception after a potentially accepted create/set/create call is reconciled
only from the exact provider postcondition. The receipt does not claim
`created_now` for an ambiguous response. A failed invocation leaves its intent
and must not be blindly retried.

The fixed canary is:

```text
gs://nfl-predictions-503414-paid-authority/paid-v3/provider-readiness/capability-v1.json
```

Its canonical bytes explicitly say `outcome_data:false`. Its body is compared
byte-for-byte but never decoded or printed during preflight.

## Read-only release preflight

`preflight` requires a full source commit and immutable `image@sha256` and
requires the running environment's `IMAGE_SOURCE_COMMIT_SHA`, `IMAGE_URI`, and
`IMAGE_DIGEST` to match. It resolves the caller through token-info, discards
the token, and accepts only one of the fixed deployer/runtime principals.

Both actor modes fully consume exact-name:

```python
bucket.list_blobs(prefix=object_name)
bucket.list_blobs(prefix=object_name, versions=True)
bucket.list_blobs(prefix=object_name, soft_deleted=True)
```

They require exactly one live canary generation, no noncurrent or soft-deleted
generation, construct a generation-pinned blob, call `reload()` and
`download_as_bytes()`, compare generation/bytes/SHA-256 to the fixed canary,
and repeat the complete census. Provider, permission, pagination,
representation, history, or race uncertainty fails closed.

The deployer mode also reloads the bucket and reads its version-3 IAM policy.
Runtime Object Viewer is not assumed to possess `getIamPolicy`; runtime mode
instead requires one hash-valid exact deployer receipt, binds the same canary
generation and independently proves the list/get data plane as the runtime
service account. Independent review must adjudicate this pairing before any
provider use.

The canary check does **not** replace the R4 final-activation absence law. Once
an authorized build ID determines the final revision, the unchanged deployer
must still census the exact derived `activation.json` name and require all
three views empty before its first Cloud Run mutation.

## Operator shape after separate authorization

These examples document the reviewed interface; they are not an apply/build/
preflight authorization.

Default no-contact plan:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src \
  /home/erich/projects/nfl-predictions/.venv/bin/python -m \
  nfl_dfs.ops.paid_v3_authority_readiness
```

Separately authorized infrastructure apply, with a new durable attempt
directory prepared in advance:

```bash
paid-v3-authority-readiness apply \
  --confirm provision-nfl-predictions-503414-paid-authority \
  --source-commit <full-40-character-release-commit> \
  --image <immutable-image@sha256> \
  --receipt reports/paid-v3-authority-readiness-runs/<attempt>/provisioning.json
```

Exact-image deployer check:

```bash
paid-v3-authority-readiness preflight \
  --actor deployer \
  --source-commit <full-40-character-release-commit> \
  --image <immutable-image@sha256> \
  --receipt reports/paid-v3-authority-readiness-runs/<attempt>/deployer.json
```

Exact-image runtime check, executed only through a separately authorized
no-traffic environment running as the fixed runtime service account:

```bash
paid-v3-authority-readiness preflight \
  --actor runtime \
  --source-commit <same-full-release-commit> \
  --image <same-immutable-image@sha256> \
  --deployer-receipt <exact-deployer-receipt.json> \
  --receipt <create-only-runtime-receipt.json>
```

The command writes canonical receipt JSON both to the exclusive receipt path
and stdout. Capture stdout durably when the runtime filesystem is ephemeral.
Store intent/receipts under tracked `reports/paid-v3-authority-readiness-runs/`,
commit and push them, retain exact source/image/execution identities, and never
record a credential token. On any nonzero or ambiguous return, stop and
authenticate exact provider state; do not blindly retry.

## Changed surface

- `pyproject.toml`
- `scripts/lem_train/Dockerfile`
- `cloudbuild.paid-boundary-v3.yaml`
- `src/nfl_dfs/ops/paid_v3_authority_readiness.py`
- `tests/test_paid_v3_authority_readiness.py`
- this report and `HANDOFF.md`

No paid book, canonical-game policy, generator, selector, score, outcome,
Neo4j, application route, R4 census/publisher/runtime reader, Cloud Run
deployer, or traffic logic changed.

## Validation completed without the pytest lane

The serial pytest lane remained owned by PREREG-074/R25. No pytest command
ran. Static validation completed:

- AST parse of the new implementation and test module;
- TOML parse of `pyproject.toml`;
- YAML parse of `cloudbuild.paid-boundary-v3.yaml`;
- no-contact default plan render and JSON contract check;
- offline installed Storage API check against local
  `google-cloud-storage==3.13.1`;
- offline construction-property check proving the installed client serializes
  uniform access, enforced public-access prevention, and 604800-second soft
  delete on a new `Bucket`; and
- `git diff --check`.

Ruff is unavailable in the shared production environment; no package was
installed. No Cloud Build, deployment, traffic, GCS/provider call or mutation,
bucket/IAM change, paid action, contest entry, graph operation, score, or
outcome read occurred.

## Remaining gates and GO decisions

1. Independently review this exact candidate, including the deployer-receipt
   pairing used because runtime Object Viewer is not granted bucket-IAM read.
2. Obtain a fresh serial lane and run the new focused unit/static module, then
   the exact paid-v3 Cloud Build release module list. No test result is claimed
   yet.
3. Separately authorize one exact release build. The identity of that future
   immutable image and permission to run `apply` from it remain an explicit
   operational **HOLD**; this candidate does not select or authorize either.
4. Separately authorize the immutable `us-central1` bucket creation, exact
   deployer/runtime principals, 7-day policy, IAM additions and fixed canary.
   A code PASS alone is not infrastructure authority.
5. Select and approve a durable receipt destination before apply. No
   destination is selected by this candidate; intent, apply, deployer and
   runtime receipts must not be left only on an ephemeral container filesystem
   or in assistant/cloud logs.
6. From the same future immutable image, obtain matching deployer and runtime
   preflight receipts and prove the executing runtime identity is exactly
   `817589974517-compute@developer.gserviceaccount.com`. The mechanism and
   authorized no-traffic runtime execution remain an explicit operational
   **HOLD**.
7. Only then adjudicate the unchanged exact final-activation empty-history
   gate and a distinct deployment/traffic/activation/paid-output GO.

Until all gates pass, canonical paid-v3 remains **HOLD**.
