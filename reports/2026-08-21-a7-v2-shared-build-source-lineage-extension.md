# A7-v2 shared-build source-lineage extension

**Extension ID:** `20260821-a7-v2-shared-build-source-lineage-v1`

**Affected run:** `20260820-a7-select-ladder-phase-s-incumbent-v2`

**Status:** administrative source-equivalence authority for the first A7-v2
preflight claim only

## Purpose

The completed A7-v2 build-gate preclaim recovery bound its fresh repair source
to commit `f389f33336868d552220bcc9e6decfe557a85220`.  Its first replacement
Cloud Build, `f500c3ed-1960-427a-a415-2f4a4bff804b`, then failed the full test
gate because the historical empty-shell recovery test copied the later A7
finisher from the checkout instead of reconstructing the recovery-era bytes.
That build and image remain ineligible.

Commit `2bec2965442b90ec87990fb25f086de9005265dc` makes that test
archive-hermetic with a content-addressed fixture.  It does not change the A7
protocol, science, source query, optimizer, runner, freeze builder, finisher,
launcher, watcher, Cloud Build contract, Dockerfile, or package declaration.
This extension proves that narrow lineage and permits one successful
direct-Git build of the later exact source to satisfy the unchanged A7 build
gate.  Because LR8 requires the tag
`us-central1-docker.pkg.dev/nfl-predictions-503414/nfl-dfs/nfl-dfs:lr8-smoke-2bec296`
and A7 accepts the exact `_IMAGE` recorded by its build metadata without an
A7-specific tag prefix, that same successful build ID and immutable digest may
also be presented to A7 `preflight-prepare`.

This extension grants no LR8 authority.  LR8 remains governed by its own v2
salary-boundary repair protocol and predecessor-failure gate.

## Immutable predecessor

The retained recovery body is
`reports/a7-select-ladder-preflight-recovery-runs/20260821-a7-v2-build-gate-preclaim-recovery-v1/recovery.json`
with SHA-256
`f25b87b7bce3dd170ad47f647c3f7d3606ad7de5cd646082c0b6ce34463e0e66`.
Its two-entry receipt ledger has SHA-256
`df10db0113f177f33b24c4039e9c9bb677955c2f01caf56e11b263a112a28411`,
and it binds fresh repair source
`f389f33336868d552220bcc9e6decfe557a85220`.  The incident body and evidence
ledger remain byte-pinned by the validator.  This extension neither edits nor
reinterprets those completed recovery records.

## Required source proof

`scripts/validate_a7_v2_source_lineage_extension.py` must prove all of the
following from Git objects and the real retained recovery files:

1. Both full commits resolve exactly, and `f389f333...` is an ancestor of
   `2bec2965...`.
2. Every path in the unchanged A7 implementation manifest, including its
   complete in-repository import closure, the A7-v2 protocol, `Dockerfile`,
   and `pyproject.toml` is present and byte-identical at both commits and in
   the current checkout.  The three registered empty package markers remain
   exactly empty.  The build-gate and empty-shell recovery
   protocols/tools, plus the build-gate focused tests, are also
   byte-identical.
3. The canonical 43-source/61-delta-row evidence fixture is exactly 15,806
   bytes with SHA-256
   `f94b75786d7eac28b1508554794b02cf0903492afd14d65f99e5dfdca1a64a84`.
   It binds both full commits, the ancestry assertion, every registered
   base/target source hash or absence, and the complete no-rename delta.  The
   compressed historical base-test fixture is exactly 4,183 bytes with
   SHA-256
   `b19495dccd8aa1ebd823a0019f81d8e4a14302fad46ec4d266e19c623933fa30`;
   it decodes to exactly 9,588 bytes with the registered old-test hash.
4. The old empty-shell test has SHA-256
   `1c8a5e3a3a9b89217bba30575d789d800d3e5ecbb2181edd9191f2c40196ea22`;
   the target test has SHA-256
   `bd9bee4395977c8ff392b8dd7321951924dc2e44f14a59e9e6d0577e4e1317b2`.
   The new Base64/LZMA fixture has SHA-256
   `a75dfbe29b76ae1ce756eae4794ee18d3c7f9772920692e75de58637588cf86c`
   and decodes to exactly 229,783 bytes with historical finisher SHA-256
   `f9963fead2b4cccca035b03e09f0b17519c8e12e02273c2f93cad960982030d8`.
5. The complete no-rename Git delta contains exactly 61 paths: two registered
   archive-fixture paths, 14 retained administrative record paths, and 45
   LR8-only paths.  Its canonical status/path receipt SHA-256 is
   `362e3513e2beb37771c0b738a92c847ee4cabdc59093cba3f5b73870fed496da`.
   There are 50 additions and 11 modifications.  Any extra A7 implementation
   path or unclassified path fails closed.
6. The extension emits the exact target source and LR8 tag.  It never accepts
   an abbreviated or caller-substituted commit.

The public validator is local, read-only, and live-Git-only.  It pins this
protocol's exact bytes, requires both commit objects and their ancestry, and
has no evidence fallback.  Archive-only tests replay the same validation
logic through explicit injected seams backed by the two content-addressed
fixtures; that replay is test evidence and never grants authority.  The
validator has no BigQuery, GCS, Cloud Build, Cloud Run, log, scheduler, lease,
or outcome client.

## Build and preflight boundary

A shared build is eligible for A7 only when the unchanged A7 finisher accepts
the build metadata with all of these values from the same build:

- resolved direct-Git source and declared code:
  `2bec2965442b90ec87990fb25f086de9005265dc`;
- substitution and declared/result image name:
  `us-central1-docker.pkg.dev/nfl-predictions-503414/nfl-dfs/nfl-dfs:lr8-smoke-2bec296`;
- terminal build status `SUCCESS`, all three exact source-time build steps
  successful, and the registered service account/log bucket/options/timeout;
- one immutable digest whose result row names that exact LR8 tag.

The exact same build ID, code SHA, and immutable digest must be passed to both
preparers.  A second tag, rebuilt digest, local upload, dirty-worktree build,
old `f500c3ed...` build, transport-repair override, or cross-build mixture is
not equivalent.

The focused synthetic metadata test proves only that the unchanged A7 and
LR8 validators have a nonempty exact-contract intersection.  It does not
license a build.  Eligibility still requires the real terminal metadata from
the named successful build to pass both validators independently.

The A7 prefix and local preflight directory must still be empty at the real
preflight gate, and the unchanged launcher/finisher must revalidate every
existing job, scheduler, A3 release, failed-v1 release, and build condition.
This source extension does not replace any of those live preconditions.

## Authority and non-authority

A passing local lineage validation plus a successful exact build licenses
only reuse of that one build identity for the first A7-v2
`preflight-prepare` claim.  After a valid claim, the original frozen A7-v2
protocol exclusively governs smoke, support census, freeze, historical lease,
execution, harvest, and disposition.

This extension licenses no outcome read, historical scoring, smoke relaunch,
retry, lease action, Cloud Run creation/deletion, repair override, prospective
shadow, production-law transfer, or production change.  It does not revive or
make reusable any failed or cancelled build.
