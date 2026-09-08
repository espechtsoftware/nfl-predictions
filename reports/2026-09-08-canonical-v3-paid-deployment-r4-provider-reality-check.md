# Canonical-v3 paid/deployment R4 provider reality check

Date: 2026-09-08

Probe window ended: `2026-09-08T06:43:18Z`

Reviewed integration branch:
`production/canonical-paid-r4-integration-20260908`

Reviewed integration commit:
`1d75c71f9a08fd61b281435895b59116a9b1ff3c`

Reviewed integration worktree:
`/home/erich/projects/nfl-predictions-canonical-paid-r4-integration-20260908`

Reality-check branch:
`codex/canonical-paid-r4-provider-reality-check-20260908`

Upstream candidate/review:

- candidate `9dfc767f141053efd29e6471519c711bce3a86f6`, tree
  `9b3a3fc70bfc0481d77926a1a14b0f0a288cd558`;
- independent PASS `eb57454677c074603b8a9d5a360937a6582436fa`;
- candidate report
  `reports/2026-09-08-canonical-v3-paid-deployment-r4-repair-candidate.md`;
- independent review
  `reports/2026-09-08-canonical-v3-paid-deployment-r4-independent-review.md`.

Disposition: **HOLD for paid-v3 deployment, traffic cutover, final activation,
and paid output.** The R4 implementation remains fail-closed and its generic
GCS list/exact-read path passed a real outcome-blind probe, but the exact
hard-coded authority bucket does not exist. Consequently there is no target
soft-delete policy or bucket IAM policy to authenticate, and neither deployer
nor runtime capability against the target can pass. This result does not
reverse the independent code PASS; it closes the required operational
readiness check as HOLD.

No Cloud Build, deployment, Cloud Run execution, service traffic, bucket/IAM
configuration, GCS object mutation, graph operation, score/outcome read,
contest entry, or paid action occurred. No pytest command ran.

## Executive findings

| Capability | Evidence | Disposition |
|---|---|---|
| Exact authority bucket exists | Both the active gcloud account and the Python ADC saw zero exact bucket names; bucket metadata reload returned `NotFound` / HTTP 404 for `nfl-predictions-503414-paid-authority`. | **HOLD** |
| Target has a nonzero soft-delete policy | No target bucket exists, so no policy exists to inspect. The effective project constraint allows any supported duration; it does not create a policy or bucket. | **HOLD** |
| Target live listing | The exact R4 reader failed with `NotFound` before returning a census. Absence of a bucket is not an empty generation census. | **HOLD** |
| Target `versions=True` listing | Same target-bucket 404. | **HOLD** |
| Target `soft_deleted=True` listing | Same target-bucket 404. | **HOLD** |
| Target exact-generation `reload()` and `download_as_bytes()` | There can be no target generation while the bucket is absent. | **HOLD** |
| Active deployer/ADC identity resolved | gcloud and ADC both resolved to `espechtsoftware@gmail.com`; the credential token was never printed or retained. The principal has project `roles/owner`. | **PASS for identity; HOLD for target IAM** |
| Actual local ADC list/get behavior | The exact R4 code fully consumed all three list views and generation-pinned read a documented zero-outcome pre-lock manifest in another same-project bucket. Bytes/SHA matched its durable identity without decoding content. | **PASS for client/provider path; not transferable to missing target** |
| Current Cloud Run runtime identity resolved | `nfl-dfs-app` currently names `817589974517-compute@developer.gserviceaccount.com`, with project `roles/editor`. The deploy script does not pass `--service-account`; no future R4 revision yet exists. | **PASS for current observation; HOLD for future exact revision identity** |
| Runtime identity target data-plane ability | The target is absent. Out-of-service impersonation also failed because the active operator lacks `iam.serviceAccounts.getAccessToken`; no traffic or execution was used as a workaround. Project `roles/editor` is not accepted as an object-read proof for a future uniform-access bucket. | **HOLD** |
| Installed local Storage API | Shared production venv has `google-cloud-storage==3.13.1`; the installed signatures expose separate `versions` and `soft_deleted` listing, generation-bound blob construction, `reload()`, `download_as_bytes()`, and conditional upload. A real soft-delete query succeeded on a policy-enabled bucket. | **PASS locally** |
| Exact future release-image Storage API | No R4 release image exists and building one was outside this read-only authorization. `pyproject.toml` permits `google-cloud-storage>=2.13`, while upstream added soft-delete support in 2.16.0. | **HOLD until exact image inspection; dependency floor should be repaired** |
| Existing target activation history | Cannot be adjudicated as empty: the complete reader terminates 404 at the bucket boundary. | **HOLD** |

## Exact reviewed target

The reviewed deployer fixes these coordinates in
`scripts/deploy_paid_boundary_v3_image.sh`:

```text
PROJECT=nfl-predictions-503414
REGION=us-central1
AUTHORITY_BUCKET=nfl-predictions-503414-paid-authority
SERVICE=nfl-dfs-app
FINAL_ACTIVATION_URI=gs://nfl-predictions-503414-paid-authority/paid-v3/nfl-dfs-app/<active-revision>/activation.json
```

`<active-revision>` is not knowable until an authorized build ID exists; the
script derives it as
`nfl-dfs-app-paidv3-<first-eight-code-SHA>-<first-eight-build-ID>`. Bucket
existence, policy, and IAM are prefix-independent, so the missing bucket is a
complete blocker for every possible reviewed final URI.

R4 calls the provider separately and fully materializes each result:

```python
bucket.list_blobs(prefix=object_name)
bucket.list_blobs(prefix=object_name, versions=True)
bucket.list_blobs(prefix=object_name, soft_deleted=True)
```

For its selected live generation it constructs
`bucket.blob(object_name, generation=int(generation))`, calls `reload()`,
checks the returned generation, and calls `download_as_bytes()`.

## Read-only command ledger and redacted evidence

### 1. Source and branch identity

```bash
git status --short --branch
git rev-parse HEAD
git rev-parse origin/production/canonical-paid-r4-integration-20260908
```

```text
## codex/canonical-paid-r4-provider-reality-check-20260908
1d75c71f9a08fd61b281435895b59116a9b1ff3c
1d75c71f9a08fd61b281435895b59116a9b1ff3c
```

The worktree was clean before this report was added.

### 2. Active credentials and current service identity

```bash
gcloud auth list --filter='status:ACTIVE' --format='value(account)'
gcloud config get-value project
gcloud run services describe nfl-dfs-app \
  --project=nfl-predictions-503414 --region=us-central1 \
  --platform=managed \
  --format='csv[no-heading](spec.template.spec.serviceAccountName,status.latestReadyRevisionName,status.latestCreatedRevisionName,spec.template.spec.containers[0].image)'
```

Redacted evidence (there were no secrets in the provider response):

```text
gcloud active account: espechtsoftware@gmail.com
gcloud configured project: nfl-predictions-503414
runtime service account: 817589974517-compute@developer.gserviceaccount.com
latest ready/created revision: nfl-dfs-app-e0-0f30c925
live image digest: sha256:3da77cb5625ec5b7362f1478def5e3fc8ee5b09f8f9354590acea81bfdc161e4
```

`google.auth.default()` returned user credentials with default/quota project
`nfl-predictions-503414`. An in-process OAuth token-info request selected only
the verified email and immediately cleared the token:

```text
ADC email: espechtsoftware@gmail.com
email_verified: true
token printed or retained: false
```

Project IAM was read and locally filtered to only these two principals:

```bash
gcloud projects get-iam-policy nfl-predictions-503414 --format=json \
  | jq -r '.bindings[] as $b | $b.members[]? |
      select(. == "user:espechtsoftware@gmail.com" or
             . == "serviceAccount:817589974517-compute@developer.gserviceaccount.com") |
      [., $b.role] | @tsv' | sort
```

```text
serviceAccount:817589974517-compute@developer.gserviceaccount.com  roles/editor
user:espechtsoftware@gmail.com                                    roles/owner
```

These broad project roles are configuration observations, not substitutes for
an explicit target-bucket object-read probe. In particular, Cloud Storage's
basic-role convenience mappings and object ACLs differ from uniform
bucket-level access. The new authority bucket should receive explicit narrow
bucket bindings.

### 3. Exact target bucket and policy

```bash
gcloud storage buckets describe \
  gs://nfl-predictions-503414-paid-authority \
  --format='json(name,location,soft_delete_policy,versioning_enabled,uniform_bucket_level_access)'
```

```text
ERROR: gs://nfl-predictions-503414-paid-authority not found: 404
exit 1
```

An independent project bucket-list query returned a successful, authoritative
zero count:

```bash
gcloud storage buckets list --project=nfl-predictions-503414 \
  --filter='name:nfl-predictions-503414-paid-authority' \
  --format='value(name)'
```

```text
exact_authority_bucket_count=0
exit 0
```

The Python ADC independently produced both signals:

```text
Client.list_buckets(..., prefix=target), exact-name count: 0
Client.bucket(target).reload(): NotFound, HTTP 404
```

The effective project policy does not prohibit a nonzero soft-delete duration:

```bash
gcloud resource-manager org-policies describe \
  constraints/storage.softDeletePolicySeconds \
  --project=nfl-predictions-503414 --effective --format=json
```

```json
{"constraint":"constraints/storage.softDeletePolicySeconds","listPolicy":{"allValues":"ALLOW"}}
```

It remains necessary to specify and then read back an actual nonzero bucket
policy; a permissive organization constraint is not such a policy.

### 4. Exact R4 target call

With bytecode disabled and the integration source first on `PYTHONPATH`, the
following call used the reviewed function unchanged:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src \
  /home/erich/projects/nfl-predictions/.venv/bin/python - <<'PY'
from nfl_dfs.optimizer.paid_classic_deployment_v3 import (
    read_paid_classic_final_generation_census_v3,
)

read_paid_classic_final_generation_census_v3(
    "gs://nfl-predictions-503414-paid-authority/paid-v3/"
    "nfl-dfs-app/provider-reality-check-1d75c71f/activation.json"
)
PY
```

The caught/redacted observation was:

```text
exception_type=NotFound
http_code=404
no census returned
```

This is the intended fail-closed behavior. It must not be normalized into
`{"live":[],"noncurrent":[],"soft_deleted":[]}`.

### 5. Installed API signatures

```bash
/home/erich/projects/nfl-predictions/.venv/bin/python - <<'PY'
import inspect
from importlib.metadata import version
from google.cloud.storage import Blob, Bucket, Client

print(version("google-cloud-storage"))
for owner, method in (
    (Bucket, "list_blobs"),
    (Client, "list_blobs"),
    (Blob, "reload"),
    (Blob, "download_as_bytes"),
    (Blob, "upload_from_string"),
):
    print(owner.__name__, method, inspect.signature(getattr(owner, method)))
print(inspect.signature(Blob))
PY
```

Material installed evidence:

```text
google-cloud-storage=3.13.1
Bucket.list_blobs(..., versions=None, ..., soft_deleted=None, ...)
Client.list_blobs(..., versions=None, ..., soft_deleted=None, ...)
Blob(name, bucket, ..., generation=None)
Blob.reload(...)
Blob.download_as_bytes(...)
Blob.upload_from_string(..., if_generation_match=None, ...)
```

The installed `Bucket.list_blobs` documentation says `soft_deleted=True`
lists soft-deleted generations, requires a bucket soft-delete policy, and
cannot be combined with `versions=True`. R4 correctly makes separate calls.

There is a packaging gap: `pyproject.toml` declares
`google-cloud-storage>=2.13`, but the provider library's upstream changelog
records soft-delete support as introduced in 2.16.0. The current venv passes,
but the repository's declared minimum does not guarantee the reviewed API.
See the official
[Python Storage changelog](https://github.com/googleapis/python-storage/blob/main/CHANGELOG.md)
and current
[Bucket.list_blobs reference](https://docs.cloud.google.com/python/docs/reference/storage/latest/google.cloud.storage.bucket.Bucket#google_cloud_storage_bucket_Bucket_list_blobs).

### 6. Outcome-blind real-object list/reload/download probe

The bounded probe used only the already documented Week-1 public-contest
pre-lock manifest. `HANDOFF.md` and
`reports/2026-09-04-week1-a5-live-contest-capture.md` attest that it contains
zero paid entries and that zero outcome fields were read when it was produced:

```text
gs://nfl-predictions-503414-raw/week1/prelock/2026-w01/contests/a5/20260904T105535Z/manifest.json
generation 1788519340044066
bytes 2664
sha256 28408ab4e57d8f994d29d8afe16b86d9d2fc14cf02f0a89ccd2af76929d17dd4
```

The probe did not decode, print, or inspect the downloaded bytes. It invoked
the exact R4 census reader, then the exact R4 generation-pinned helper:

```python
census = read_paid_classic_final_generation_census_v3(safe_uri)
identity, raw = _read_exact_gcs_final_activation_v3(
    safe_uri, "1788519340044066"
)
```

Returned evidence:

```text
census.live=['1788519340044066']
census.noncurrent=[]
census.soft_deleted=[]
exact generation=1788519340044066
exact bytes=2664
exact sha256=28408ab4e57d8f994d29d8afe16b86d9d2fc14cf02f0a89ccd2af76929d17dd4
known identity match=true
content inspected=false
```

The source bucket's provider metadata was also read without mutation:

```text
name=nfl-predictions-503414-raw
location=US (multi-region)
versioning not enabled
softDeletePolicy.retentionDurationSeconds=604800
softDeletePolicy.effectiveTime=2026-07-24T14:18:56.896Z
uniform bucket-level access=false
```

Thus the real provider accepts all three reviewed listing forms even with
Object Versioning disabled, provided a nonzero soft-delete policy exists.
The exact-generation reload/download path also behaves as R4 expects.

### 7. Runtime service-account probe boundary

The current operator is not allowed to mint an access token for the Cloud Run
runtime service account:

```bash
gcloud auth print-access-token \
  --impersonate-service-account=817589974517-compute@developer.gserviceaccount.com \
  >/dev/null
```

Redacted evidence:

```text
PERMISSION_DENIED: iam.serviceAccounts.getAccessToken
reason=IAM_PERMISSION_DENIED
exit 1
```

No access token was printed. This is not evidence that the service account
lacks Storage access when running as itself. It means the required exact-
identity data-plane check cannot be replaced by operator impersonation under
the current IAM configuration. The Policy Troubleshooter API was also found
disabled; it was not enabled because that would mutate project configuration.
No Cloud Run user traffic or execution was used as a workaround; the only
Cloud Run operation was the read-only service description recorded above.

## Required remediation before a new readiness check

An operator with separate infrastructure authority must provision the exact
reviewed bucket and IAM. The following is a concrete least-privilege template,
not an executed or authorized command sequence:

```bash
gcloud storage buckets create \
  gs://nfl-predictions-503414-paid-authority \
  --project=nfl-predictions-503414 \
  --location=us-central1 \
  --uniform-bucket-level-access \
  --public-access-prevention \
  --soft-delete-duration=7d

gcloud storage buckets add-iam-policy-binding \
  gs://nfl-predictions-503414-paid-authority \
  --member='user:espechtsoftware@gmail.com' \
  --role='roles/storage.objectViewer'
gcloud storage buckets add-iam-policy-binding \
  gs://nfl-predictions-503414-paid-authority \
  --member='user:espechtsoftware@gmail.com' \
  --role='roles/storage.objectCreator'
gcloud storage buckets add-iam-policy-binding \
  gs://nfl-predictions-503414-paid-authority \
  --member='serviceAccount:817589974517-compute@developer.gserviceaccount.com' \
  --role='roles/storage.objectViewer'
```

The location is immutable. `us-central1` is shown because the reviewed runtime
is pinned there; the infrastructure owner must confirm that choice before
creation. If the globally unique bucket name cannot be created, the hard-coded
R4 bucket name must change through a separately reviewed code repair instead
of silently substituting another bucket.

The deployer needs `storage.objects.create`, `storage.objects.get`, and
`storage.objects.list`; the viewer+creator pair supplies those without delete
authority. The runtime needs only `storage.objects.get` and
`storage.objects.list`, supplied by Object Viewer. Google documents those two
permissions for `roles/storage.objectViewer` in its
[Cloud Storage IAM guide](https://docs.cloud.google.com/storage/docs/access-control/iam).

The repository dependency floor should be raised to at least
`google-cloud-storage>=2.16.0`, or preferably locked to an exact reviewed
release. Independently of that metadata repair, the exact future image must
print and authenticate its installed version and the relevant method
signatures before cutover. The current live image is not the R4 release image
and was not pulled or executed.

After provisioning, repeat from the actual deployer ADC and from the exact
runtime identity:

1. bucket metadata reload and explicit positive soft-delete retention;
2. exact-name live list;
3. exact-name `versions=True` list;
4. exact-name `soft_deleted=True` list;
5. `storage.objects.get` and `storage.objects.list` permission proof;
6. bounded generation-pinned reload/download of a governed non-sensitive
   object, without decoding or printing content; and
7. the actual intended `activation.json` all-generation census, which must be
   exactly empty before any provider mutation.

Do not grant `roles/iam.serviceAccountTokenCreator` merely to make this report
green without a separately reviewed need. A probe can instead run inside an
already authorized, no-traffic environment using the service account itself,
or under separately approved short-lived impersonation. Whichever route is
chosen must bind the exact future Cloud Run revision's actual service account;
the current observation alone is not durable proof of that future identity.

## Final adjudication

- **R4 generic provider method contract: PASS** in the installed 3.13.1 client
  and against a real policy-enabled bucket.
- **R4 fail-closed response to missing provider state: PASS.** The target 404
  does not become an empty census.
- **Exact paid-authority bucket/policy/history: HOLD.** The bucket is absent.
- **Exact deployer target permissions: HOLD.** There is no target resource on
  which to exercise them.
- **Exact runtime target permissions: HOLD.** There is no target resource, no
  R4 revision, and current operator impersonation is unavailable.
- **Exact release-image library capability: HOLD.** No R4 image exists and the
  declared package floor predates soft-delete support.
- **Overall operational readiness: HOLD.** No deployment, traffic, activation,
  or paid-v3 output may proceed on this evidence.
