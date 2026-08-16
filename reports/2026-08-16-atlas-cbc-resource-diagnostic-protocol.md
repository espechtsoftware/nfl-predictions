# ATLAS CBC child-process and cgroup resource diagnostic protocol

Date frozen: 2026-08-16, after the native-log diagnostic launched but before
either native-log diagnostic reached terminal state or any diagnostic artifact
was opened.
Protocol ID: `20260816-atlas-cbc-resource-diagnostic-v1`

## Purpose and relationship to the first diagnostic

The already-launched native-log diagnostic remains immutable. It can retain a
CBC log and MPS file, but it cannot distinguish a child killed by the cgroup OOM
killer from another nonzero CBC exit. This independent, prospective diagnostic
closes only that observability gap. It does not supersede, mutate, retry or
interpret the first diagnostic.

The one-minute Cloud Monitoring memory samples are inconclusive. Repair2 was
the first interaction-heavy ATLAS grid run at one CPU and 4 GiB, down from the
16--32 GiB used by completed ATLAS jobs. Memory pressure is therefore the
leading hypothesis, not a ruled-out explanation.

## Fixed cells and calculation

Run 2024 Weeks 7, 15 and 16 from the immutable repair2 image
`sha256:ce03feb739e51aabedd7cea79f46e13a06a097a7f85e9a5817f38184b67f4fcb`
and source `60f296fdad769b30c0bb7334118698f156e462b9`. Week 7 is retained because
its lower sampled memory profile could identify a distinct mechanism.

For every cell load the identical five native books and player catalog and run
only the exact failed R0 construction prefix: native interaction pricing,
exact top-40 worlds, structural clustering and 40-lineup matched-diversity
enumeration with an empty prior-ATLAS set. Objective, floors, stack rules,
ordering, tolerance, interaction integrality, packaged CBC binary and solver
options remain unchanged.

## Sole permitted changes

- execute the diagnostic source through `python -c` in the unchanged image;
- retain the native CBC log and final MPS via `keepFiles=True` and `logPath`;
- wrap, but do not replace or alter, the `subprocess.Popen` instance used by
  PuLP to record its exact integer return code and terminating signal;
- read the current process cgroup immediately before CBC starts and immediately
  after `wait()` returns, retaining `memory.events`, `memory.current`,
  `memory.peak` and `memory.max` where exposed; use the corresponding cgroup-v1
  files only as a compatibility fallback;
- persist a mechanical failure or R0-success receipt and the failure log/MPS;
- discard all returned lineups in memory and never address a normal ATLAS
  result prefix.

Every task retains one CPU, 4 GiB, zero retries, one task, parallelism one, the
same service account and a 12-hour timeout. The three tasks are evidence-only.

## Firewall

The diagnostic source and SQL may not reference realized outcomes. No lineup,
candidate summary, selector output, tail probability, gate, effect or score may
be printed or persisted. Permitted receipts contain only fixed identities,
terminal status, solver/process counts, exception type/message, child return
code/signal, cgroup counters/limits/high-water marks, and diagnostic artifact
metadata. Native CBC text and its MPS input remain permitted score-free solver
evidence.

Do not inspect any task artifact until all three tasks are terminal. Then invoke
only the strict finisher. This diagnostic cannot license an ATLAS result or a
production change.

## Frozen interpretation

- Any positive `oom_kill` delta is definitive resource-failure evidence.
- A negative child return code records the terminating signal. `-9` without an
  `oom_kill` increment is SIGKILL evidence but is not, by itself, proof of OOM.
- A successful isolated R0 run with zero `oom_kill` increments is not
  automatically "transient." If observed `memory.peak / memory.max` is at
  least `0.80`, it remains resource-pressure evidence.
- Only if all three isolated R0 runs succeed, all cgroup reads are available,
  every OOM delta is zero and every peak ratio is below `0.80` may the result be
  labeled isolated-success with memory clear of the frozen pressure boundary.
- Missing/inconsistent process or cgroup evidence is inconclusive. Native logs
  may identify a deterministic parser/model defect, but no model repair may be
  inferred from a generic PuLP exception alone.

Repair3 must in all cases use new identities and rerun all 54 cells. If resource
pressure is supported, freeze repair3 at 16 GiB (and the CPU count Cloud Run
requires for that allocation) rather than relaunching the 4 GiB grid. The exact
continuous-interaction formulation may be considered separately only with a
hard old-binary/new-continuous exact-roster parity gate where the old solver
completes.
