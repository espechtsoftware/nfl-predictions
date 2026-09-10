# Generation shadow `j5qzl` preflight failure and single-source repair

Date: 2026-09-10

## Disposition

Cloud Run execution `generation-shadow-suite-j5qzl` is a terminal failure and
is not an accepted Week-1 generation-shadow root. It failed in the repaired
source preflight before the first candidate solve, candidate-log append,
world-artifact write, manifest, or terminal publication. Preserve the
execution and do not collect, retry, adopt, or relabel it.

## Exact failed execution

- source commit: `e7572a315aa42d2d7f318ded6e596da1c28e8cf6`
- immutable Cloud Build: `7fcf9d2a-09eb-4f84-9c80-f6a97fcaa4c4`
- immutable image:
  `us-central1-docker.pkg.dev/nfl-predictions-503414/nfl-dfs/nfl-dfs@sha256:2ea4548f14e284ec0e70750175ede36dcb2213e55cc79edae0ac508274fd43ce`
- execution: `generation-shadow-suite-j5qzl`
- execution UID: `d27793ab-e535-4315-83bd-9a0b43594ef1`
- created: `2026-09-10T14:06:39.999752Z`
- started: `2026-09-10T14:07:33.347024Z`
- completed: `2026-09-10T14:15:15.226784Z`
- terminal count: one failed task, zero successful tasks, zero retries
- terminal exception: `ProspectiveGenerationShadowError: frozen
  generation-shadow preflight source drift`

## Root cause

The first paired-input-v2 repair cached each completed player/draw matrix, but
assembled that cache by invoking the live slate builder eleven times. Each
invocation independently queried current features, inactive/cascade inputs,
prop markets, DST inputs, and model registry state. Comparing those eleven
results correctly detected a real source change, but the implementation had
not actually taken one atomic upstream snapshot. The run stopped safely at
preflight and therefore spent no optimizer work and published no partial
generation-shadow authority.

## Repair

The prospective suite now installs one restored-on-exit, suite-local provider
snapshot around preflight. At first use it freezes and then serves deep copies
of the Week-1 feature frame, late-inactive cascade inputs, prop-market frame,
DST frame, and one exact loaded object per named component-model variant. The
eleven simulation banks are still derived independently from their registered
projection, role, and audit seeds. Only the common live provider inputs are
shared. The adopted live-lineup implementation and all frozen production
policy files remain unchanged.

Preflight diagnostics now name candidate/role seed labels and stable receipt
hashes if a future mismatch survives the source snapshot boundary.

## Validation

- Python compilation: pass.
- Focused suite/evaluation/live-multiseed/portfolio/boom-first/deployment
  tests: 88/88 pass in 211.91 seconds.
- A regression supplies providers that mutate on every call. Across all eleven
  seeded builds the feature, cascade, market, and DST providers are each read
  exactly once; each named model variant is loaded exactly once; all provider
  functions are restored after preflight.
- A bounded real Week-1 source check produced two distinct 10,000-world
  projection banks with one identical 395-row stable candidate-source receipt,
  SHA-256
  `31a757f3569c7eeb376c73cf871f2b2fb69ad7200def44a696d49a195e5789af`.
  The role check produced a 395-row stable receipt, SHA-256
  `0ee86dec4bc430850991e3dfa1e55c09d12fff17f787c1e73aa92b42b3808a34`,
  and a 493-by-10,000 draw bank before exact slate restriction.
- `git diff --check`: pass.

## Next action

Commit and push the single-source repair, build one new exact-commit immutable
image, update the same dedicated zero-retry job, and launch one fresh Week-1
execution. Accept only a successful paired-input-v2 terminal. Preserve both
failed predecessors (`vx76b` and `j5qzl`) and do not reuse their incomplete
state.
