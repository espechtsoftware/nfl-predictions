# Week-1 capture-v3 P0-B local provider rehearsal R2

Date: 2026-09-08

Parent implementation: `51e3dd4b098b46933fab701d9711065d6bf844a9`

Branch: `production/week1-capture-v3-p0b-local-rehearsal-r2-20260908`

Implementation commit: `be3062405ff4b59df318a458bfb22d0376bca3e4`

Implementation tree: `1d08d9f6ec386a4d1aa88bf031eef30ed5c67be2`

Rehearsal module SHA-256:
`4f96b259608fec19674d1d85b45fe7d0455f0b294cbd91a9073af4a882234ed5`

Focused test SHA-256:
`810782fc07329f4c4af774362e116b53bb97fbc5368859ece2f6f60257ea5270`

## Disposition

**CODE/TEST CANDIDATE; LOCAL PROVIDER CONTACT HOLD.**

R2 narrows the immediate Week-1 gate to one local authenticated DraftKings
acceptance-download rehearsal. The prior organization-wide Cloud Asset, IAM,
Cloud Build, Artifact Registry, bucket, Cloud Run job, service-account and
Secret Manager census has been removed from this command. Deployment
certification remains a later, separately named concern and cannot block this
provider-response rehearsal.

No provider/network, gcloud, Google Cloud, GCS, build, deployment, job,
publication, contest-entry, standings, score or outcome action occurred while
preparing R2. Every activation/live pin remains absent. The accepted P0-A
collector, capture-v3 implementation and legacy-v2 files are byte-unchanged.

## Local gate

The default command emits an inert canonical plan. The `intent` command emits
an offline canonical hashed pre-contact intent. Only `audit`, with the exact
confirmation phrase `rehearse-week1-a5-acceptance-download-v1`, can construct
an HTTP session. The private test core requires an explicitly injected session
factory and has no default-network mode; only the fully gated CLI branch can
select `requests.Session`.

Before constructing that session, `audit`:

1. validates the canonical intent/hash, exact current rehearsal-module SHA,
   accepted P0-A collector-module SHA, A5 role, GET-only method, accepted v3
   schema, code-owned locator families, redirect bound and all negative
   authorities;
2. proves every live/activation pin is still absent;
3. requires one shared existing owner-only mode-0700 output parent, then
   exclusively reserves a new mode-0700 evidence directory and empty mode-0600
   evidence/receipt files so no post-contact collision is possible;
4. securely opens the locator using `O_NOFOLLOW`, validates the same fd as one
   owner-owned, single-link, nonempty, bounded, exact-mode-0600 regular file,
   and requires one canonical UTF-8 locator line in a fixed DraftKings HTTPS
   family, outside the explicitly rejected authentication, entry/action and
   outcome/standings path markers; and
5. only then securely opens the Playwright storage-state file under the same
   fd/mode/owner/link/size rules, parses it in memory, and requires at least one
   nonempty DraftKings-domain cookie.

Neither private path nor either file's bytes, hash, cookie names or cookie
values enter evidence, stdout or stderr.

The local transport sets `trust_env=False`, supplies cookies only to an
in-memory session, performs GET only, requests identity transfer encoding,
keeps TLS verification enabled, disables automatic redirects, and admits the
initial URL plus every `Location` target before the next request. It rejects
off-family locators, named authentication/action/outcome path markers,
ambiguous or traversal paths, loops, excessive hops, unsupported redirects,
and discontinuous chains. Network exception detail is replaced with a fixed
message so signed URLs and credentials cannot reach stderr.

The terminal response must be exact HTTP 200 (therefore successful 2xx), have
no `Location`, no adapter history, identity/no content encoding, a bounded
body, reviewed `text/csv` media/charset and a structurally parsed attachment
with one safe `.csv` filename. The body must begin with the exact outcome-free
13-column DKEntries header, every nonempty row must have that width, and the
accepted outcome-blind shape inspector must prove the selected A5 role's exact
contest ID/name/fee/K, unique entry IDs, and nine unique draftables per roster.

The local attempt retains only:

- the canonical reviewed intent copy, which contains no locator or credential;
- code/schema/intent hashes;
- observation time, private-input validation booleans, completion state and
  negative-operation flags;
- host/fixed-family locator projections with path suffix and query contents
  removed;
- hop ordinals/statuses, response/redirect counts and terminal status;
- normalized media/charset/disposition class;
- body byte count and SHA-256; and
- exact header and role-level structural booleans/counts.

It retains no raw locator suffix, query name/value, cookie, response body,
header filename, entry ID, row, player, roster, or entry-projection hash. The
receipt binds the evidence SHA and remains
`HOLD_FOR_INDEPENDENT_REVIEW_AND_PIN_ONLY_SUCCESSOR`.

## Private artifacts production must supply

Production must prepare these locally and outside version control. Do not
send their contents through chat, logs, shell tracing or a commit.

1. `var/week1-a5-p0b/playwright-storage-state.json`: a Playwright
   `browser_context.storage_state()` JSON snapshot from the authenticated
   DraftKings account, owned by the invoking user, one hard link, exact mode
   `0600`, nonempty and at most 4 MiB. It must contain a nonempty
   DraftKings-domain cookie. The command never persists or prints it.
2. `var/week1-a5-p0b/acceptance-download-locator.txt`: exactly one canonical
   HTTPS URL line for the active-entry DKEntries download, optionally followed
   by one LF, with the same owner/link/mode/size rules. It may contain signed
   query material; the command never persists or prints that material. Its
   host/path must already fall under a code-owned family.
3. A reviewed canonical intent generated offline for the exact committed R2
   source and the selected A5 role. The intent contains no credential or URL.
4. An existing private mode-0700 parent directory for the attempt. The
   `evidence/` directory and `receipt.json` named below must both be absent.

On success, the command creates exactly `evidence/` at mode `0700`,
`evidence/intent.json` and `evidence/rehearsal-evidence.json` at mode `0600`,
and `receipt.json` at mode `0600`. A HOLD after reservation deliberately
leaves the attempt reserved: the intent copy can be populated and the evidence
or receipt can remain empty (or partially complete if a later local write
fails). Such an attempt is non-authoritative and must never be reused or
overwritten; production must select a fresh absent attempt path.

Both `var/week1-a5-p0b/` and the local attempt subtree below are explicitly
ignored by the repository. Production must still keep each private input at
exact mode `0600` and must not place either value in shell tracing, logs, chat,
or any tracked file.

## Separately gated exact rehearsal preparation and invocation

This sequence is documentation only and was not run. Production must first
independently review the exact pushed commit and the generated intent. Replace
the fixed creation timestamp below only through that review; do not reuse an
attempt directory after any HOLD because its exclusive reservation files are
deliberately left behind.

```bash
set -euC
umask 077
P0B_LOCAL_ROOT=reports/week1-a5-p0b-local-runs
P0B_LOCAL_ATTEMPT=$P0B_LOCAL_ROOT/20260908-local-r1
install -d -m 700 "$P0B_LOCAL_ROOT"
mkdir -m 700 "$P0B_LOCAL_ATTEMPT"
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src \
  .venv/bin/python -m nfl_dfs.ingest.week1_a5_p0b_provider_reality intent \
  --created-at-utc 2026-09-08T20:00:00Z \
  --contest-role milly-5 \
  > "$P0B_LOCAL_ATTEMPT/intent.json"
chmod 0600 "$P0B_LOCAL_ATTEMPT/intent.json"
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src \
  .venv/bin/python -m nfl_dfs.ingest.week1_a5_p0b_provider_reality audit \
  --confirm rehearse-week1-a5-acceptance-download-v1 \
  --intent "$P0B_LOCAL_ATTEMPT/intent.json" \
  --storage-state-file var/week1-a5-p0b/playwright-storage-state.json \
  --acceptance-locator-file var/week1-a5-p0b/acceptance-download-locator.txt \
  --evidence-directory "$P0B_LOCAL_ATTEMPT/evidence" \
  --receipt "$P0B_LOCAL_ATTEMPT/receipt.json"
```

The first command is offline. The second performs real authenticated provider
contact and therefore requires a distinct production authorization after code
and intent review. Success does not authorize a pin change, cloud deployment,
GCS publication, contest entry, standings read or outcome access.

## Validation

Validation was local, network-free and serial after an empty global pytest
census:

- 69/69 focused R2 adversarial tests passed;
- 95/95 combined accepted P0-A plus R2 tests passed;
- a fresh read-only source/docs safety audit returned PASS after rechecking the
  sole-contact path, redirect admission, response bound, redaction, and absent
  cloud surface;
- Ruff, Python compilation, `git diff --check`, and repository-ignore checks
  passed; and
- byte-identity checks against parent `e71ce651791fe6539876112068c211be0af2bf1e`
  passed for the accepted P0-A collector, its tests, capture contracts and
  capture-v3 module:
  - collector: `3f2cf6f359b7120ace7bf9e3833750601ce97b921b06a8e11d4f5dc188a71435`;
  - P0-A tests: `3625757ef10698b4cfa77212585d650e662494fa91ce08fb8dceaa880674755c`;
  - capture contracts: `90c712df78e61c290cc4e41cef739de6693b7c1c33de76dd7176eb25a45ff2c8`;
  - capture-contract tests: `78850f72c351411b10a2494b7ca6db8491170583d499a7c97e75e98f2bfe4706`;
  - capture-v3: `2f6c014af3c07755f150cd5b40d8475733b03faed9afdd4c196686d9a52cef37`.

No provider, DNS, external network, gcloud, cloud API or GCS action was part
of these checks.
