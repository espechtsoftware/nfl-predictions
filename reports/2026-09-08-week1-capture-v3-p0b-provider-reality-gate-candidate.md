# Week-1 capture-v3 P0-B provider-reality gate candidate

Date: 2026-09-08

Base: production `origin/main` at
`054b09460a952d4a363d904a27c39f898e342bc0`

Branch: `production/week1-capture-v3-p0b-provider-reality-gate-20260908`

Candidate implementation: `51e3dd4b098b46933fab701d9711065d6bf844a9`
(tree `d8222bcc3a6b4c25e8e27aa4fc023c1dbbf11574`)

## Disposition

**CODE/TEST CANDIDATE; REAL-FACT HOLD.**

This change adds a separately confirmed, outcome-blind, read-only P0-B audit.
It does not assert that any P0-B provider fact is true. It did not contact
DraftKings, Google Cloud, GCS, or any other network service; build or deploy an
image; execute or update a job; publish an object; change a live pin; enter a
contest; or read a score, standing, result, or other outcome.

Every activation/live pin remains absent. The accepted capture-v3 collector
and durable ledger contracts are unchanged. No legacy-v2 fallback or live
call site was added.

## Implemented audit boundary

`src/nfl_dfs/ingest/week1_a5_p0b_provider_reality.py` has two modes:

1. The default `plan` mode emits canonical JSON and performs no file,
   credential, cloud, or provider read.
2. `audit` requires the exact confirmation phrase, a canonical hashed
   pre-contact intent, a private regular locator file, an absent evidence
   directory, and an absent receipt. It writes local evidence create-once and
   leaves partial evidence intact on any HOLD.

Before the single active-entry HTTP probe, the audit authenticates:

- the one active gcloud principal and exact project/folder/organization
  ancestry;
- the exact-generation Cloud Build source object, including a read-only byte
  stream SHA-256/size check, successful build provenance and substitutions,
  and the Artifact Registry fully qualified image digest;
- the authority bucket's provider project, metageneration, locked retention,
  versioning, uniform access, public-access prevention, and full direct IAM
  bindings;
- effective mutation access to the bucket, service-account impersonation
  access to both managed identities, Cloud Run job mutation access, and secret
  access at organization scope through Cloud Asset IAM analysis;
- `fullyExplored`, empty-error analysis, the exact query/options/resource,
  expanded roles/resources/groups, group and resource edges, attachment
  provenance, and the exact independently reviewed principal set for every
  requested permission;
- chained service-account impersonation analysis for both managed service
  accounts;
- the exact Cloud Run job name/UID/generation, observed Ready generation,
  one task, one parallel worker, zero retry, managed collector identity,
  digest-qualified image, exact source/image environment, and one fixed secret
  version mounted only at the collector's fixed storage-state path; and
- the exact enabled Secret Manager version plus direct service-account, job,
  and secret IAM policies.

The audit then instantiates the accepted P0-A `_RequestsSessionTransport`
directly. That transport uses `GET`, disables automatic redirects, admits the
initial locator and every redirect target before the next request, rejects
login surfaces and out-of-family hops, and returns one sealed transport event.
The P0-B receipt retains only redacted locator projections, hop/status facts,
media type, content disposition, response byte count/SHA-256, and structural
DKEntries facts. It retains no provider bytes, row values, query values,
cookies, tokens, or session state. The existing v3 schema is named explicitly;
the shape inspector is not an acquisition authority and publishes nothing.

All IAM, job, bucket and secret facts are fetched and validated again after the
HTTP probe. Any pre/post difference is a HOLD. Provider transcripts and the
intent are local canonical create-once evidence; credentials are rejected
before transcript persistence.

## Command surface

The implementation's gcloud argv is fixed to read-only verbs:

- `auth list`, `projects get-ancestors`;
- `storage buckets describe/get-iam-policy`;
- `storage objects describe` and exact-generation `storage cat`;
- `builds describe`, `artifacts docker images describe`;
- `run jobs describe/get-iam-policy`;
- `iam service-accounts get-iam-policy`;
- `secrets versions describe`, `secrets get-iam-policy`; and
- `asset analyze-iam-policy` with the complete reviewed selectors and
  expansion/output flags.

There is no create, update, delete, execute, submit, IAM write, GCS
publication, or provider-capture publisher in this command surface.

## Adversarial coverage

`tests/test_week1_a5_p0b_provider_reality.py` covers the complete fixture path
and fail-closed behavior for a changed intent hash, mutable image, live-action
authorization, unexpected inherited principal, partial Cloud Asset analysis,
mutable group edge, wrong analysis scope, changed job generation, mutable job
image, multi-task job, floating secret version, wrong media/disposition/CSV
shape, out-of-family redirect, pre/post provider drift, wrong confirmation,
non-private/symlink locator files, and credential-bearing transcripts. It also
asserts that every activation pin remains `None`, that the accepted transport
is constructed with the fixed session-state path, and that the generated
gcloud argv contains no mutation verb.

The accepted P0-A transport suite remains the executable authority for the
stronger pre-contact property: an off-family `Location` target is refused
before a second request, redirects are never followed by the HTTP adapter, and
loops are refused before re-contact.

## Validation

Each pytest command was started only after an empty global pytest census and
ran serially:

```text
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src .venv/bin/python -m pytest -q \
  tests/test_week1_a5_p0b_provider_reality.py
26 passed

PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src .venv/bin/python -m pytest -q \
  tests/test_week1_a5_dk_acquisition.py \
  tests/test_week1_a5_p0b_provider_reality.py
52 passed
```

Ruff passes on the new source and test, Python compilation passes, and
`git diff --check` passes. The accepted P0-A source/test blobs and both v3 and
legacy-v2 contract files are untouched. The fixed legacy-v2 source/test
SHA-256 values remain respectively
`90c712df78e61c290cc4e41cef739de6693b7c1c33de76dd7176eb25a45ff2c8`
and
`78850f72c351411b10a2494b7ca6db8491170583d499a7c97e75e98f2bfe4706`.

## Separately gated real-fact invocation

The following exact invocation is documented for later production review. It
was **not** run. Before authorizing it, production must independently create
and review the canonical intent at the named path, provision the private
locator file with mode `0600`, verify the branch/commit and local interpreter,
and confirm that both output paths are absent. The command performs real
read-only Google provider calls, one authenticated DraftKings active-entry
acquisition with governed redirects, and local create-once evidence writes.

```bash
umask 077
P0B_ATTEMPT_DIR=reports/week1-a5-p0b-provider-reality-runs/20260908-p0b-real-fact-r1
install -d -m 700 "$P0B_ATTEMPT_DIR"
test -f "$P0B_ATTEMPT_DIR/intent.json"
test -f var/week1-a5-p0b/acceptance-download-locator.txt
test ! -e "$P0B_ATTEMPT_DIR/provider-transcripts"
test ! -e "$P0B_ATTEMPT_DIR/receipt.json"
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src \
  .venv/bin/python -m nfl_dfs.ingest.week1_a5_p0b_provider_reality audit \
  --confirm capture-week1-a5-p0b-provider-reality-v1 \
  --intent "$P0B_ATTEMPT_DIR/intent.json" \
  --acceptance-locator-file var/week1-a5-p0b/acceptance-download-locator.txt \
  --evidence-directory "$P0B_ATTEMPT_DIR/provider-transcripts" \
  --receipt "$P0B_ATTEMPT_DIR/receipt.json"
```

Even a successful invocation remains `HOLD_FOR_INDEPENDENT_REVIEW_AND_PIN_ONLY_SUCCESSOR`.
Its receipt and every raw transcript must be independently reviewed before a
separate code change may bind a locator or any other live pin. It grants no
publication, deployment, paid-entry, or outcome authority.
