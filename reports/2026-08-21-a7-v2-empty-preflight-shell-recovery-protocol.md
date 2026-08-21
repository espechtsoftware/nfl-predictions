# A7-v2 empty local preflight-shell recovery protocol

**Recovery ID:** `20260821-a7-v2-empty-preflight-shell-recovery-v1`

**Affected run:** `20260820-a7-select-ladder-phase-s-incumbent-v2`

**Disposition:** administrative prelaunch interruption; no preflight attempt,
job claim, cloud object, job update, execution, lease, science read, or outcome
look occurred

## Scope

The first operator-side A7-v2 watcher process was recorded as PID `2693633`.
Its inner command used the exact immutable A7-v2 image, source
`7057554eb2d930be29e882745e52d271fde09339`, and build
`063251e8-888b-4d64-9c78-1346af5b12bf`, with all three registered transport
repair variables unset. The outer detach wrapper was not durably recorded.
The process disappeared while the launcher was beginning `preflight-prepare`.
It left a zero-byte watcher log and only the newly created, completely empty
local preflight directory. It left no first prefix-inventory file and no ERR
trap message.

External tool-session termination during the first GCS inventory call is the
most plausible explanation for that shape, but it is not proven and this
protocol does not state it as fact. The frozen launcher deliberately refuses
an existing preflight directory, even an empty one. Directly deleting that
directory would bypass its fail-closed rule. Changing the frozen A7 launcher,
watcher, finisher, runner, or science would also be disproportionate and would
break the exact-source preflight contract.

This amendment therefore authorizes one narrow, independently validated local
archive operation. It does not edit any frozen A7 file and does not create a
new scientific or cloud attempt. Its only mutation is an atomic same-filesystem
rename of the exact identified empty directory into a durable incident archive
after all evidence has been written. Once that rename succeeds, the unchanged
A7-v2 watcher may make its first preflight attempt under the existing run ID.

## Exact local incident identity

The recovery accepts only:

- local directory
  `reports/a7-select-ladder-preflight-runs/20260820-a7-select-ladder-phase-s-incumbent-v2`;
- device `2096`, inode `360672`, mode `040755`, UID/GID `1000/1000`, link
  count `2`, size `4096`, mtime/ctime nanoseconds
  `1787288151209315898`;
- no directory entries of any kind, including hidden entries;
- watcher log `/home/erich/nfl-panels/a7-select-ladder-v2-chain.log` on device
  `2096`, inode `360670`, mode `0100644`, UID/GID `1000/1000`, link count `1`,
  size `0`, mtime/ctime nanoseconds `1787288149625316848`, and the SHA-256 of
  the empty byte string; and
- no live PID `2693633` and no local A7 watcher, launcher, runner, or finisher
  process for this run.

Any difference is an ambiguity and forbids recovery.

## Required read-only proof

Immediately before arming the atomic rename, the recovery must validate all of
the following and retain canonical JSON captures:

1. The six frozen A7-v2 protocol/science/runner/launcher/watcher/finisher files
   are byte-identical both locally and at source commit
   `7057554eb2d930be29e882745e52d271fde09339`. No repair override is accepted.
2. The complete A7-v2 GCS prefix is empty. In addition to the definitive empty
   prefix inventory, direct metadata lookups for the job claim, smoke,
   smoke-terminal, support, support-terminal, freeze, and historical result
   objects must each return `NotFound`. Authentication, authorization,
   transport, timeout, and service failures never count as absence.
3. The global historical-outcome lease returns definitive `NotFound`.
4. The local historical-run directory and its pending-prepare directory are
   both absent.
5. The reused Cloud Run job is still exactly
   `atlas-minimal-c-s2023-w1-v1`, UID
   `d6e4b8c1-5950-46b7-8869-7e34dbf29ad2`, generation `12`, with canonical
   spec SHA-256
   `c0e4b6985f79265373d8ada306575470a794f38426e25fbc9188daf551331f94`.
   That spec must also reproduce the retained B1 post-update snapshot whose
   file SHA-256 is
   `dc9082f20a5d885b3aed722075617ce3830a6725d968295dd8f27f64dcac39c4`.
6. The complete live execution-name set is exactly the 261 terminal names in
   the retained B1 pre-execution census plus its one strictly harvested
   execution `atlas-minimal-c-s2023-w1-v1-sm64k`. The anchor file SHA-256
   values are respectively
   `4279fd1cb0df3903a460f698c25208470ccdbcb4b4809a38df6a095a4a1fc547`
   and
   `4b43673aedb987b8c071bd1fc27820940bdbdb75b0e15440fe54e6919602ad3e`.
   Every live execution must be terminal. An extra, missing, nonterminal, or
   duplicate execution forbids recovery.
7. No Cloud Scheduler target URI refers to the reused job.

The recovery has no BigQuery client, log-reading API, Cloud Run update,
execute, retry, cancel, delete, object upload, lease acquire, or artifact-body
read path.

## Archive and crash boundary

The durable local incident archive is
`reports/a7-select-ladder-preflight-recovery-runs/20260821-a7-v2-empty-preflight-shell-recovery-v1`.
It must not already exist. Before moving the shell, the recovery writes
canonical job, execution, scheduler, prefix/absence, process, incident, and
recovery receipts plus SHA-256 ledgers into that archive and fsyncs them. The
complete local/cloud boundary is then read again and must byte-reproduce the
captured job, execution, scheduler, and absence evidence before the move is
armed. The
last state-changing operation is an atomic same-filesystem rename of the exact
empty-shell inode to `empty-preflight-shell` inside that already durable
archive. A stop before the rename leaves the original path present, so the
unchanged watcher remains blocked. The rename either happens or does not; the
empty directory is never recursively removed or discarded.

## Authority and non-authority

A passing recovery licenses only
`same_v2_first_preflight_prepare_licensed=true`: the unchanged watcher may
start the first A7-v2 outcome-blind smoke/support chain under its already
frozen identities. It is not a retry because no v2 execution or cloud attempt
existed. It does not license an alternate run, parameter change, gate change,
result read, historical look, shadow, production-law transfer, money policy,
or production change. All those decisions remain governed by the unchanged
A7-v2 protocol and its future create-once receipts.
