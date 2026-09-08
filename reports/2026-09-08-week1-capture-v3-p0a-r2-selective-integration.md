# Week-1 capture-v3 P0-A R2 selective integration

Date: 2026-09-08

Integration branch:
`production/week1-capture-v3-p0a-r2-integration-20260908`

Production parent:
`6381dc422ef5a346d64507547bf91818f982b7ee`

Reviewed candidate:
`563af790efc475a85e4cd8da7de4f58384643a10` (tree
`67cc749e`)

Independent review:
`b8e6904928b97db11da2acf944c4b25eac4a065e` (tree
`1c705eea21d7c997895aa1224c6507a9265303ba`)

## Disposition

The independently accepted, additive and default-off governed DraftKings
collector plus durable-ledger v3 capture/evidence contracts have been
selectively materialized onto the current production line. All implementation,
test, contract-document and review files are blob-exact to the reviewed trees.

This integration grants no live authority. P0-B provider facts, pin binding,
real acquisition, publication, deployment, paid entry, and outcome access all
remain HOLD behind separate review and authorization.

## Integrated behavior

- A fixed repository-owned authenticated collector writes raw response,
  transport trace and acquisition receipt before a separate create-once
  root-last issuance ledger.
- The v3 provider-capture artifact durably binds that ledger's exact object
  identity, provider creation time, authority event and cutoff.
- Downstream evidence creation exact-reopens the stored provider-capture
  generation and current sole ledger authority, then enforces
  `receipt <= ledger <= provider capture <= cutoff`.
- Final-field evidence performs the ordering proof independently for the
  contest-detail and full-standings sources.
- Automatic redirects are disabled and every effective URL and redirect target
  is admitted before another request.
- Existing v2 capture contracts remain byte-identical.

## Exact selection method

The production parent did not yet contain the P0-A collector files. Rather
than merge unrelated handoff history, integration selected the exact final
reviewed blobs from candidate `563af790` and the independent report blob from
`b8e6904`. Blob identities were compared before validation and all matched.
The production `HANDOFF.md` is updated separately so current production history
is preserved.

## Validation on the integration tree

Each pytest invocation began after a separate empty global Python/pytest
census and ran serially.

- Governed collector and durable-ledger v3 suite: **26/26 passed**.
- Unchanged generic P2 contract suite: **42/42 passed**.
- Unchanged legacy-v2 rehearsal suite: **15/15 passed**.
- Python byte compilation: passed.
- Ruff lint on the integrated Python files: passed.
- `git diff --check`: passed.

No network, provider, DraftKings, GCS, Cloud Build, Cloud Run, deployment,
paid-entry, generation, selection, scoring, or outcome action occurred.

## Next action

Keep the integration dormant. Separately complete P0-B by observing and binding
the real provider/runtime/governance facts, then obtain review before filling
pins or performing one real outcome-blind acquisition. The future whole-root
capture path must consume v3 evidence and must not silently fall back to live
v2 evidence.
