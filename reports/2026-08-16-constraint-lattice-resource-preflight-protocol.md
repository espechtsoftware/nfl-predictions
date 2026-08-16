# Constraint-lattice exact-full-cell resource-preflight protocol

Date frozen: 2026-08-16, before any constraint-lattice treatment execution or
result and before any control-support count was opened. The ATLAS 32-GiB
preflight remained nonterminal.

Protocol ID: `20260816-constraint-lattice-resource-preflight-v1`.

## Purpose and fixed cell

The lattice workload differs from ATLAS but otherwise inherits an untested
4-CPU/16-GiB envelope. Before any 54-cell treatment population, run one exact
full five-fold lattice cell solely to determine whether that envelope can
complete the workload.

The preflight cell is 2023 Week 1. It was selected before any lattice result
from the frozen CBWU-OI source ledger because its five source artifacts have
the largest combined byte footprint, 163,064,634 bytes. 2025 Week 3 has the
largest candidate-row count, 1,325, but a smaller combined byte footprint;
there is no result-dependent cell choice.

## Exact execution

- Run ID: `20260816-constraint-lattice-resource-preflight-v1`.
- Create-only object:
  `gs://nfl-predictions-503414-raw/research/constraint-lattice-resource-preflight-runs/20260816-constraint-lattice-resource-preflight-v1/slate-2023-1.json`.
- Use the same validated image, code, source artifacts, player catalog,
  five-fold control construction, five atomic cells, MILP proposal limits,
  ranking, admission and held-out measurement implementation intended for the
  full grid.
- Resources: one task, 4 CPU, 16 GiB, task-level `maxRetries=0`, 43,200-second
  timeout and the same service account.

The exact job and execution identity, image, code, command, environment,
resources and object metadata are retained. The runner may emit only the five
fold-completion markers and final object-upload receipt to logs.

## Outcome/effect blindness

This is a resource decision, not a one-cell scientific result. The strict
preflight finisher must not download or parse the output object, list a lineup,
open a control/treatment metric or inspect any realized outcome. It validates
only:

- the exact execution completed successfully with one successful task;
- all five distinct R0--R4 fold-completion markers exist;
- the exact create-only object exists with a positive byte count and generation;
  and
- all source/build/queue/support identities match.

The object remains quarantined and cannot be reused as one of the future 54
scientific shards.

## Frozen resource branch

- A strict success licenses the separately launched 54-cell lattice population
  at 4 CPU/16 GiB, subject to its completed control-support disposition and
  bounded platform-attempt contract.
- A configured-memory-limit or native SIGKILL failure licenses one new
  separately frozen 8-CPU/32-GiB resource preflight of the same cell and no
  scientific grid.
- A literal zero-object `Internal error running task` may receive at most one
  separately receipted platform replacement only after a bounded-attempt
  amendment is frozen; absent that amendment it is mechanically inconclusive.
- Timeout, solver, ordinary nonzero-exit, malformed markers/object, ambiguous
  failure or a failed 32-GiB escalation closes this lattice execution path
  without a treatment result.

Sampled Cloud Monitoring memory may be recorded afterward as non-gating
context. It is not an exact process/cgroup peak and cannot override terminal
evidence.
