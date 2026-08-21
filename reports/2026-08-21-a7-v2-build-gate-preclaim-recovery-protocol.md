# A7-v2 build-gate failed-preclaim recovery protocol

**Recovery ID:** `20260821-a7-v2-build-gate-preclaim-recovery-v1`

**Affected run:** `20260820-a7-select-ladder-phase-s-incumbent-v2`

**Disposition:** administrative build-metadata gate failure before the first
job claim; no Cloud Run update or execution, cloud object, lease, science
artifact read, or outcome look occurred

## Scope and finding

After the separately completed empty-shell recovery, the unchanged A7-v2
watcher entered `preflight-prepare` with successful build
`063251e8-888b-4d64-9c78-1346af5b12bf`, source
`7057554eb2d930be29e882745e52d271fde09339`, and immutable image
`us-central1-docker.pkg.dev/nfl-predictions-503414/nfl-dfs/nfl-dfs@sha256:f9ecbcc6a45046b4155bb22e0497e7b7c1c618655bad2a7852bfc8fb04c2370f`.
It validated an empty v2 cloud prefix, retained canonical successful build
metadata, and then failed closed in
`finish_a7_select_ladder.py::_validate_build_metadata` before copying the A3
release, reading/updating the reused job, creating the v2 job claim, or
launching an execution.

The defect is exact and administrative. The successful build contains the
exact 70-line smoke step in its own submitted
`7057554eb2d930be29e882745e52d271fde09339:cloudbuild.yaml`. The later working
tree contains a 78-line step because an unrelated LR8 transport added four
checks after that build. Reconstructing expected metadata from a hardcoded or
working-tree smoke list therefore coupled an immutable build to future
unrelated changes.

The repair loads `cloudbuild.yaml` from the build's already-validated exact
Git `code_sha`, parses its registered three-step shape without a YAML runtime
dependency, substitutes only that build's `_IMAGE`, and compares every
normalized step byte-exactly. A later working-tree smoke addition cannot
invalidate an older exact build; the same addition at the submitted commit
must invalidate metadata that lacks it. Failures name the exact step and
changed fields with expected/actual content hashes. This does not normalize
metadata, relax a comparison, or change science.

Although the repaired validator correctly recognizes that the old build
matches its own source-time Cloud Build contract, the old build/image remain
ineligible for A7-v2: the repaired finisher is absent from their source and
image, and v2 preflight forbids a post-commit transport override. A fresh
direct-Git build from the exact repair commit is still required.

No A7-v2 scientific or cloud attempt exists, so the run ID can remain v2 if
and only if this exact failed-preclaim shell is durably preserved first. The
v2 protocol does not pre-pin a code or image identity before its create-only
job claim; the future first claim will bind the fresh exact source, successful
build, and immutable image. This is therefore an administrative preclaim
recovery, not a retry of a smoke or historical experiment.

## Exact local incident identity

The recovery accepts only directory
`reports/a7-select-ladder-preflight-runs/20260820-a7-select-ladder-phase-s-incumbent-v2`
with device `2096`, inode `360769`, mode `040755`, UID/GID `1000/1000`, link
count `2`, size `4096`, and mtime/ctime nanoseconds
`1787289233956666000`. It must contain exactly these two regular files and no
others:

- `.inventory-empty`: device `2096`, inode `360770`, mode `0100644`, link
  count `1`, UID/GID `1000/1000`, size `0`, mtime/ctime nanoseconds
  `1787289232100667109`, SHA-256
  `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`;
- `build-metadata.json`: device `2096`, inode `360773`, mode `0100644`, link
  count `1`, UID/GID `1000/1000`, size `10237`, mtime/ctime nanoseconds
  `1787289233818215783`, canonical-JSON SHA-256
  `7695c0fc86a2f0afaf4c41cf3106d49532a296c23eeb8cbcf6328f72939613d2`.

The watcher log
`/home/erich/nfl-panels/a7-select-ladder-v2-chain.log` is a regular file on
device `2096`, inode `360670`, mode `0100644`, link count `1`, UID/GID
`1000/1000`, size `370`, mtime/ctime nanoseconds
`1787289234624665601`, and SHA-256
`9e71eb3266710a458b6950e5f1093b6271d657514c2edaaf69899baa72b0d514`.
Its exact bytes are retained in the recovery archive and end with the frozen
launcher's immutable-directory error after the build/test/image gate
traceback. Any path, stat, byte, entry, or process difference blocks recovery.

## Required proof and final boundary

Before arming the archive rename, the recovery must prove and retain:

1. The v2 protocol, scientific module, runner, freeze builder, launcher, and
   watcher are byte-identical to source
   `7057554eb2d930be29e882745e52d271fde09339`. Among those frozen A7 files,
   only the finisher may differ. The submitted-commit Cloud Build, repaired
   finisher, this protocol, recovery tool, and focused tests must all be
   byte-identical to one caller-supplied fresh local Git commit distinct from
   the old source.
2. The complete v2 GCS prefix is empty. Direct metadata lookups for claim,
   smoke, smoke terminal, support, support terminal, freeze, and result must
   each return definitive `NotFound`; the historical-outcome lease must also
   return definitive `NotFound`. Authentication, authorization, timeout,
   transport, or service failure never proves absence.
3. The local historical output and pending directories are absent.
4. The reused A7 job remains UID
   `d6e4b8c1-5950-46b7-8869-7e34dbf29ad2`, generation `12`, with canonical
   spec SHA-256
   `c0e4b6985f79265373d8ada306575470a794f38426e25fbc9188daf551331f94`.
   Its complete execution-name set remains the same 262 strictly terminal
   executions proved by the prior recovery, and no scheduler targets it.
5. No A7 watcher, launcher, runner, or finisher process is live.

The local/cloud boundary is read twice. Evidence and an exact copy of the
nonempty log are fsynced before the second read. The final and only mutation
is an atomic same-filesystem rename of the exact two-file directory to
`reports/a7-select-ladder-preflight-recovery-runs/20260821-a7-v2-build-gate-preclaim-recovery-v1/failed-preclaim-shell`.
The shell is never deleted or edited. A stop before the rename leaves it in
place and keeps v2 blocked.

## Authority and non-authority

A passing recovery licenses only a fresh exact-source direct-Git Cloud Build
and, after that build passes, the first A7-v2 `preflight-prepare` job claim.
The old build/image may not be reused. The original frozen v2 protocol—not
this recovery—continues to govern smoke, support, freeze, lease, historical
execution, and harvest after a valid first claim exists.

This recovery has no Cloud Run mutation/execute/cancel/delete path, object
upload/delete/body-read path, BigQuery client, log API, lease mutation, or
science/result read. It licenses no repair override, retry, score read,
historical look, shadow, production-law transfer, or production change.
