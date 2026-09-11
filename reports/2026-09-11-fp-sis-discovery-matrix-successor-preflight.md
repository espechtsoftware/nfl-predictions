# FP/SIS discovery-matrix successor preflight

Date: 2026-09-11
Scope: provider-free launch preparation only
Disposition: **HOLD until the integrated commit is built and the crash-closed
host chain is independently reviewed**

## Exact successor namespace

- Run ID: `20260911-fp-sis-discovery-matrix-successor-v1`
- Namespace:
  `gs://nfl-predictions-503414-corpus-retrieval/research/corpus-r6-paid-source-discovery-matrices/20260911-fp-sis-discovery-matrix-successor-v1/`
- Canonical local controller state:
  `/home/erich/.local/state/nfl-dfs/fp-sis-retrieval/20260911-fp-sis-discovery-matrix-successor-v1/`
- At `2026-09-11T06:29:12Z`, a read-only recursive metadata listing returned
  no object under the exact namespace and the exact local state path did not
  exist. This is an absence preflight, not continuing authority: repeat both
  checks immediately before the first create-once prepare intent. Do not list
  or infer a different prefix.

No build, Cloud Run execution, BigQuery query, GCS write, outcome read, score
read, or policy action was performed while preparing this document.

## Frozen input identities

The matrix branch is independent of source-v3. It consumes only these two
already-frozen scientific roots plus the not-yet-known runtime build
attestation for the final integrated commit.

Candidate authority root:

```json
{"bytes":216639,"generation":"1788081739195827","sha256":"ae6d0ba73ac627f652f2cfc542da3f43885f4b9090885457fa313ecb6a7faea8","uri":"gs://nfl-predictions-503414-corpus-retrieval/research/corpus-r6-fixed-g0-candidate-authorities-v2/20260830-fixed-g0-candidate-authority-v2/candidate-authority-release-v2.json"}
```

- Schema: `corpus-r6-fixed-g0-candidate-authority-release/v2`
- Run ID: `20260830-fixed-g0-candidate-authority-v2`
- Task/candidate census: 54 / 199,244
- Inner authority SHA-256:
  `adf6ab5fc514562df6f9aaf3fee8729f33189e39f0e1b3f090d8e9b9ed4a1b9f`
- Object-manifest SHA-256:
  `0980cc4997f972777cc9246bd4c0a848c28dce88b90641bed833716222d1294a`

Later-source freeze:

```json
{"bytes":4566802,"generation":"1787367678830738","sha256":"c63251a3dee0b455502a8e37d03c731c671457b9b17ff41dd9249edb0bae654a","uri":"gs://nfl-predictions-503414-corpus-source/research/source/20260821-corpus-artifact-source-authority-v3/source/later-source-freeze.json"}
```

- Schema/protocol: `lr8-later-period-source-freeze-v1` /
  `20260820-lr8-historical-residual-columns-v1`
- Slate/artifact census: 54 / 270
- World blocks: `R0,R1,R2,R3,R4`, 10,000 worlds each
- Inner freeze SHA-256:
  `841c9121cb7afa5562e4cc8a607bb96f92a96dbae0388a7e63669a1e7bfb8216`
- Only R0--R3 bodies are matrix inputs. R4 is identity-bound and must not be
  read by task0 or construction tasks.

The final prepare request must have exactly seven fields:
`run_id`, `code_sha`, `immutable_image`, `build_id`,
`runtime_build_attestation_identity`, `candidate_root_identity`, and
`later_source_freeze_identity`. The code, image, build, and attestation
identities remain intentionally unfilled until integration and the exact
direct-Git-source build are complete.

## Exact task and byte census

Each matrix is canonical header plus row-major little-endian float64 body with
40,000 discovery columns. The 54 candidate artifacts were generation/hash/byte
matched to the root before calculating this table. The canonical JSON digest
of the ordered 54 row objects (`ordinal`, `slate`, `candidates`,
`header_bytes`, `body_bytes`, `matrix_bytes`) is
`5ca8f38dc2644bef83658df3047e1cb89cef0b16db3d6b97bae6fbaaca8ff991`.

| Ordinal | Slate | Candidates | Header bytes | Body bytes | Matrix bytes |
|---:|:---:|---:|---:|---:|---:|
| 0 | 2023-w01 | 3,815 | 284,057 | 1,220,800,000 | 1,221,084,057 |
| 1 | 2023-w02 | 3,835 | 285,537 | 1,227,200,000 | 1,227,485,537 |
| 2 | 2023-w03 | 3,648 | 271,699 | 1,167,360,000 | 1,167,631,699 |
| 3 | 2023-w04 | 3,575 | 266,297 | 1,144,000,000 | 1,144,266,297 |
| 4 | 2023-w05 | 3,593 | 267,629 | 1,149,760,000 | 1,150,027,629 |
| 5 | 2023-w06 | 3,593 | 267,629 | 1,149,760,000 | 1,150,027,629 |
| 6 | 2023-w07 | 3,650 | 271,847 | 1,168,000,000 | 1,168,271,847 |
| 7 | 2023-w08 | 3,678 | 273,919 | 1,176,960,000 | 1,177,233,919 |
| 8 | 2023-w09 | 3,724 | 277,323 | 1,191,680,000 | 1,191,957,323 |
| 9 | 2023-w10 | 3,575 | 266,301 | 1,144,000,000 | 1,144,266,301 |
| 10 | 2023-w11 | 3,556 | 264,895 | 1,137,920,000 | 1,138,184,895 |
| 11 | 2023-w12 | 3,693 | 275,033 | 1,181,760,000 | 1,182,035,033 |
| 12 | 2023-w13 | 3,654 | 272,147 | 1,169,280,000 | 1,169,552,147 |
| 13 | 2023-w14 | 3,533 | 263,193 | 1,130,560,000 | 1,130,823,193 |
| 14 | 2023-w15 | 3,536 | 263,415 | 1,131,520,000 | 1,131,783,415 |
| 15 | 2023-w16 | 3,661 | 272,665 | 1,171,520,000 | 1,171,792,665 |
| 16 | 2023-w17 | 3,609 | 268,817 | 1,154,880,000 | 1,155,148,817 |
| 17 | 2023-w18 | 3,558 | 265,043 | 1,138,560,000 | 1,138,825,043 |
| 18 | 2024-w01 | 3,679 | 273,993 | 1,177,280,000 | 1,177,553,993 |
| 19 | 2024-w02 | 3,715 | 276,657 | 1,188,800,000 | 1,189,076,657 |
| 20 | 2024-w03 | 3,780 | 281,467 | 1,209,600,000 | 1,209,881,467 |
| 21 | 2024-w04 | 3,648 | 271,699 | 1,167,360,000 | 1,167,631,699 |
| 22 | 2024-w05 | 3,767 | 280,505 | 1,205,440,000 | 1,205,720,505 |
| 23 | 2024-w06 | 3,666 | 273,031 | 1,173,120,000 | 1,173,393,031 |
| 24 | 2024-w07 | 3,560 | 265,187 | 1,139,200,000 | 1,139,465,187 |
| 25 | 2024-w08 | 3,633 | 270,589 | 1,162,560,000 | 1,162,830,589 |
| 26 | 2024-w09 | 3,593 | 267,629 | 1,149,760,000 | 1,150,027,629 |
| 27 | 2024-w10 | 3,519 | 262,157 | 1,126,080,000 | 1,126,342,157 |
| 28 | 2024-w11 | 3,506 | 261,195 | 1,121,920,000 | 1,122,181,195 |
| 29 | 2024-w12 | 3,736 | 278,215 | 1,195,520,000 | 1,195,798,215 |
| 30 | 2024-w13 | 3,600 | 268,151 | 1,152,000,000 | 1,152,268,151 |
| 31 | 2024-w14 | 3,490 | 260,011 | 1,116,800,000 | 1,117,060,011 |
| 32 | 2024-w15 | 3,584 | 266,967 | 1,146,880,000 | 1,147,146,967 |
| 33 | 2024-w16 | 3,552 | 264,599 | 1,136,640,000 | 1,136,904,599 |
| 34 | 2024-w17 | 3,604 | 268,447 | 1,153,280,000 | 1,153,548,447 |
| 35 | 2024-w18 | 3,689 | 274,737 | 1,180,480,000 | 1,180,754,737 |
| 36 | 2025-w01 | 3,745 | 278,877 | 1,198,400,000 | 1,198,678,877 |
| 37 | 2025-w02 | 3,965 | 295,157 | 1,268,800,000 | 1,269,095,157 |
| 38 | 2025-w03 | 3,965 | 295,157 | 1,268,800,000 | 1,269,095,157 |
| 39 | 2025-w04 | 3,993 | 297,229 | 1,277,760,000 | 1,278,057,229 |
| 40 | 2025-w05 | 3,889 | 289,533 | 1,244,480,000 | 1,244,769,533 |
| 41 | 2025-w06 | 3,780 | 281,467 | 1,209,600,000 | 1,209,881,467 |
| 42 | 2025-w07 | 3,740 | 278,507 | 1,196,800,000 | 1,197,078,507 |
| 43 | 2025-w08 | 3,768 | 280,579 | 1,205,760,000 | 1,206,040,579 |
| 44 | 2025-w09 | 3,733 | 277,989 | 1,194,560,000 | 1,194,837,989 |
| 45 | 2025-w10 | 3,759 | 279,917 | 1,202,880,000 | 1,203,159,917 |
| 46 | 2025-w11 | 3,786 | 281,915 | 1,211,520,000 | 1,211,801,915 |
| 47 | 2025-w12 | 3,737 | 278,289 | 1,195,840,000 | 1,196,118,289 |
| 48 | 2025-w13 | 3,620 | 269,631 | 1,158,400,000 | 1,158,669,631 |
| 49 | 2025-w14 | 3,676 | 273,775 | 1,176,320,000 | 1,176,593,775 |
| 50 | 2025-w15 | 3,900 | 290,351 | 1,248,000,000 | 1,248,290,351 |
| 51 | 2025-w16 | 3,737 | 278,289 | 1,195,840,000 | 1,196,118,289 |
| 52 | 2025-w17 | 3,814 | 283,987 | 1,220,480,000 | 1,220,763,987 |
| 53 | 2025-w18 | 3,830 | 285,171 | 1,225,600,000 | 1,225,885,171 |
| **Total** | **54 slates** | **199,244** | **14,838,502** | **63,758,080,000** | **63,772,918,502** |

Task 0 is 1,221,084,057 bytes. The maximum task is ordinal 39
(`2025-w04`), 1,278,057,229 bytes; the minimum is ordinal 31
(`2024-w14`), 1,117,060,011 bytes. Every matrix remains below the 2 GiB
one-slate ceiling.

Expected final namespace census is exactly **165 objects**:

- one prepare manifest;
- 54 construction matrices plus 54 construction task results;
- one original `terminal.json`, published last for construction;
- 54 independent reopen task receipts; and
- one `reopen-terminal.json`, published last for independent reopen.

Matrix-body transport is about 191.319 GB: 63.773 GB uploaded, 63.773 GB
downloaded for each construction task's immediate generation-exact reopen, and
63.773 GB downloaded by the independent reopen cohort. JSON and source NPZ
traffic are additional. Peak task-local large-file space is approximately two
copies of the largest matrix (2,556,114,458 bytes), plus bounded inputs and
small receipts.

## Required crash-closed host chain

`prepare` must first create the manifest under its own durable local intent.
Then exactly one invocation of `scripts/launcher_registry.sh run` must hold the
canonical production lane lease for
`atlas-cbc-32g-full-2023-w8-v1` across this uninterrupted sequence:

1. reconcile/install the default-off 54-task job template;
2. launch and accept the one-task task0 execution;
3. launch and accept the 54-task construction execution;
4. collect all 54 task results and create the original terminal;
5. launch and accept the 54-task independent reopen execution, using the
   **original terminal identity** as its payload; and
6. collect all 54 reopen receipts and create the reopen terminal.

Every mutating step needs an exclusive local canonical intent before the
provider call and a canonical receipt afterward. An existing intent without a
receipt is reconciliation-only forever: compare the exact pre-intent latest
execution with the job's exact current `latestCreatedExecution`, describe any
new exact provider claim, and attach it only if its job UID, job generation,
image, command, args, environment census/payload hash, resources, task count,
parallelism, zero-retry law, and timeout all match. A command returning nonzero,
empty, multiple, or malformed output is ambiguous, not proof of no launch.
Never issue a second `jobs execute` after such a return. If no exact provider
claim can yet be identified, stop with the intent consumed for manual/read-only
adjudication.

Wait only on the exact execution name. Provider-description failures are
read-only transients and may be retried with a bound. A missing `Completed`
condition, or exactly one `Completed=Unknown`, is nonterminal when all counts
are nonnegative integers, their sum does not exceed the exact task count, and
failed/cancelled/retried are zero. Partial success in a 54-task execution is
therefore normal. A lagging completion timestamp is admitted only when all
tasks already succeeded and none is running; it still is not success before
`Completed=True`. `Completed=True` is accepted only with exact task-count
success, zeros elsewhere, no running task, a completion timestamp, exact
provider configuration, and no contradictory condition. `Completed=False`
is terminal failure only with a completion timestamp, zero running tasks, and
a nonzero failed/cancelled count; stop permanently.

Task0 stdout collection may lag provider completion, so only its read-only log
query may be retried. It must constrain the exact job, execution, task index
zero, and stdout log name, and accept exactly one row with exactly one of
`textPayload` or `jsonPayload`; the canonical schema/runtime execution must
match.

Prepare, construction collect, and reopen collect are themselves create-once
GCS mutations. After an ambiguous host return, reconcile and deeply validate
the one known URI; never invoke the same collector again. The chain seal must
retain two distinct identities:

- `discovery_matrix_freeze_terminal_identity`: the original `terminal.json`;
- `independent_reopen_terminal_identity`: the separate reopen proof.

The downstream FP/SIS ablation request consumes the **original terminal
identity**, and only after the independent reopen terminal validates the same
original root and all matrix bodies. Substituting `reopen-terminal.json` as the
scientific matrix input is forbidden.

## Prepared host implementation

The isolated successor branch adds
`scripts/finish_corpus_r6_paid_source_discovery_matrix_v1.py` and keeps it out
of the runtime image. The host controller is inert without both `--execute`
and the literal confirmation below. It requires exact clean `HEAD ==
origin/main`, validates direct-Git Cloud Build provenance and immutable image
digest, uses only the canonical per-run state directory, and refuses to run
the shared-job chain unless it is the live descendant of the exact production
launcher-registry receipt while that lane's flock remains held.

The controller records exact requests, predecessor observations, intents,
provider attributions, launches, numbered provider observations, terminal
provider bodies, collector results, and the final chain seal. A supplied
recovery name/UID is rejected unless that phase already has a consumed launch
intent. If a crash occurs after provider attribution but before the launch
receipt, recovery retains the original attribution observation hash while
revalidating the execution's current exact immutable envelope; normal status
progress therefore cannot create a false local create-once collision.
Transient failed provider describes do not consume or skip a numbered
observation slot.

Prepare and both collectors now expose explicit reconciliation-only CLI
actions. Those paths compute the one expected canonical body, generation-open
the one known destination URI, require exact bytes/hash/identity plus a second
generation-exact read, and contain no publication call. The normal mutation
path is unreachable whenever its local intent already exists.

The final host terminal is deeply self-checked before publication and on every
resume. It binds the exact prepare/install/collect receipt hashes, all three
distinct execution names and UIDs, each exact terminal provider hash, the
original matrix terminal identity, and the separate reopen identity. No
Cloud Build, Cloud Run execution, GCS publication, warehouse query, score
read, or policy mutation was performed in this implementation pass.

Local validation passes 106/106 unique tests: 58 discovery core, runner,
wrapper, and finisher tests plus the 48-test shared reused-job predecessor
suite. Python compilation, shell syntax, every runner/controller help seam,
the inert container-help seam, and `git diff --check` also pass. Ruff and
ShellCheck are unavailable in the installed environment.

## Integration order

This work must layer after the active seven-pack/capture freeze blocker is
sealed, capture-plan Commit B is locked, and source-v3 plus discovery fixes are
integrated. Source-v3 and discovery remain independent DAG branches; they meet
only in the final FP/SIS ablation request. The final integrated commit must be
clean, equal to `origin/main`, built from direct Git source, and used for the
runtime attestation. Re-run the focused discovery core/runner/cloud tests and
an independent controller review before any prepare or launch.

After replacing only the four build placeholders with reviewed integrated
values and writing the canonical seven-field request to an absolute regular
file, activate that exact checkout's dependency-complete virtual environment
so the executable controller's `python3` resolves there. The intended
operator shape is:

```bash
source /absolute/clean/integrated/checkout/.venv/bin/activate

scripts/finish_corpus_r6_paid_source_discovery_matrix_v1.py \
  --run-id 20260911-fp-sis-discovery-matrix-successor-v1 \
  --code-sha FULL_INTEGRATED_COMMIT \
  --build-id EXACT_CLOUD_BUILD_UUID \
  --image us-central1-docker.pkg.dev/nfl-predictions-503414/nfl-dfs/nfl-dfs@sha256:EXACT_DIGEST \
  --prepare-request /absolute/path/to/prepare-request.json \
  --execute \
  --confirmation I_UNDERSTAND_DISCOVERY_MATRIX_COMPLETE_CHAIN_V1 \
  prepare

scripts/launcher_registry.sh run \
  --root /absolute/clean/integrated/checkout \
  --state-root /home/erich/.local/state/nfl-dfs/production-launcher-registry \
  --lane atlas-cbc-32g-full-2023-w8-v1 \
  --owner production \
  --target-prefixes 20260911-fp-sis-discovery-matrix-successor-v1 \
  -- /absolute/clean/integrated/checkout/scripts/finish_corpus_r6_paid_source_discovery_matrix_v1.py \
  --run-id 20260911-fp-sis-discovery-matrix-successor-v1 \
  --code-sha FULL_INTEGRATED_COMMIT \
  --build-id EXACT_CLOUD_BUILD_UUID \
  --image us-central1-docker.pkg.dev/nfl-predictions-503414/nfl-dfs/nfl-dfs@sha256:EXACT_DIGEST \
  --prepare-request /absolute/path/to/prepare-request.json \
  --execute \
  --confirmation I_UNDERSTAND_DISCOVERY_MATRIX_COMPLETE_CHAIN_V1 \
  chain
```

These are design templates, not current launch authorization. Never copy the
literal placeholders into a call, and never invoke `chain` until `prepare`
has a validated local result and manifest identity.
