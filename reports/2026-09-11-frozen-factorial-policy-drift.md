# The 115 extreme-tail factorial failures are a true positive

**Date:** 2026-09-11 · **Status:** diagnosed, NOT repaired — the repair is a
protocol decision, not a code fix

## Summary

Roughly 115 tests in `test_corpus_extreme_tail_*` fail on `main` at `8d7140f4`.
They are not flaky, not environmental, and not a test-harness problem. They are
a frozen-chain guard correctly reporting that **the live production policy has
moved 11 environment keys away from the protocol these tests were frozen
against**.

Silencing them deletes the alarm. Re-freezing them is a research decision with
comparability consequences. Neither is a five-minute fix, and neither blocks
Week 1.

## Proof

The manifest pins `P0_GENERATION_ENVIRONMENT_SHA256 = 7a638d18…`, frozen at
`c876e7f2 Freeze preweek factorial core manifest` (2026-08-24).

Reconstructing `ClassicProductionPolicy().engine_environment()` from the policy
file **as it stood at that commit** reproduces that hash exactly:

```
frozen-era sha : 7a638d185a5cffdbbd47a336c970a5c211d4c86c08e590fc4015b8d385cd9b51
pinned target  : 7a638d185a5cffdbbd47a336c970a5c211d4c86c08e590fc4015b8d385cd9b51   MATCH
```

So the reconstruction is authoritative, and the drift below is exact rather
than inferred.

## What drifted (11 keys)

```
GEN_TOTAL_BUDGET     frozen '52'        now '172'
N_BOOM               frozen '40'        now '160'
N_LEV                frozen <absent>    now '40'
MAX_OVERLAP          frozen <absent>    now '7'
MIN_GAMES            frozen <absent>    now '2'
MIN_LOWOWN           frozen <absent>    now '0'
OWN_BARBELL_HIGH     frozen <absent>    now '0.2'
OWN_BARBELL_LOW      frozen <absent>    now '0.05'
OWN_BARBELL_NHIGH    frozen <absent>    now '2'
OWN_BARBELL_NLOW     frozen <absent>    now '3'
VALUE2_MAX           frozen <absent>    now '5300'
```

The `N_BOOM` move is deliberate and documented in
`src/nfl_dfs/inference/production_policy.py`:

> Adopted 2026 Week-1 generator: equal-core-solve boom-first allocation,
> direct-role 12 + boom 160, with leverage fixed at 40. This is the money path;
> the prior 160/40 population is available only through
> `incumbent_control_environment`.

The other nine keys are new construction levers (ownership barbell, overlap and
game-count floors, a value ceiling) added since the freeze.

## Why the obvious fixes are wrong

**Do not relax the `BOOM_UNIQUE_FILL` sentinel.** The first failure in the chain
is `incumbent policy unexpectedly materializes BOOM_UNIQUE_FILL`. It is
tempting to accept a policy that declares the same `"0"` the manifest sets,
since the resulting environment is byte-identical. That change was tried and
reverted here: it removes the earliest and most specific alarm in what turns
out to be one true signal, and merely defers the failure to the hash check a
few frames later with a vaguer message.

**Do not repoint the manifest at `incumbent_control_environment()`.** The
manifest's docstring says it returns "the complete explicit *incumbent*
environment", and that accessor does restore `n_boom = 40`. But it does not
reproduce the frozen hash either:

```
incumbent_control_environment sha : 112a01b1fffd48f9d0410d4a4c9eddc12afa00e8aaf7c42752a36cda190c4a42
pinned target                     : 7a638d185a5cffdbbd47a336c970a5c211d4c86c08e590fc4015b8d385cd9b51
```

because the nine added levers are present there too. `N_BOOM` was the visible
part of the drift, not the whole of it.

## The actual decision

Someone with protocol authority must choose one of:

1. **Re-freeze** the factorial manifest against the current policy. This is a
   protocol amendment: arms generated before and after are no longer directly
   comparable, and every prior result under the old hash must be labelled.
2. **Pin the frozen chain to a fixed historical environment** rather than
   deriving it live from a policy that is expected to keep moving. This is what
   "frozen" was supposed to mean; deriving a frozen constant from a mutable
   source is the underlying design defect.
3. **Retire the chain** if its question has been answered.

Option 2 is the one that stops this recurring. The chain currently re-derives
its own frozen input from a live object, so every legitimate production change
breaks it again.

## Week-1 impact: none

This is a research chain (extreme-tail factorial / preweek additions). It is not
on the Week-1 money path, does not gate any live cadence job, and its failure
does not affect lineup construction, scoring, or the production stack. It should
not hold up the season.

## Note on the ledger

`CLAUDE.md` still documents the production stack as `N_CE=0, N_BOOM=40`. The
live policy is now `N_BOOM=160` with `N_LEV=40` on the money path. Whichever way
the protocol decision goes, that line needs updating so the documented stack and
the code agree.

---

## Resolution (2026-09-12): option 2 implemented — and the drift was hiding a second signal

**Option 2 is done.** `corpus_extreme_tail_factorial_manifest.py` now carries
the complete 66-key P0 generation environment as a literal
(`_FROZEN_P0_GENERATION_ENVIRONMENT`), reconstructed from
`ClassicProductionPolicy().engine_environment()` at the freeze commit
`c876e7f2` plus the manifest's own `BOOM_UNIQUE_FILL=0`. Its canonical hash
reproduces the pinned `P0_GENERATION_ENVIRONMENT_SHA256` (`7a638d18…`) and the
three-key PB derivation reproduces `5af2b682…`. The manifest no longer imports
the production policy at all; the dependency validator checks the literal
(`CAND_MULT=2`, `N_BOOM=40`, `N_EPISTEMIC=12`, `REPLACEMENT_SLOTS=12`,
`N_CE=0`, and the five R-block seed pairs encoded in `MULTISEED_SEED_PAIRS`)
instead of asserting properties of a live object. Tests:
`test_live_production_policy_is_never_consulted` (the live policy is
monkeypatched to raise; the manifest still builds with the frozen hash) and
`test_pinned_frozen_environment_literal_drift_is_rejected` (four mutations of
the literal each refuse with "dependency constants drifted").

**The "one true signal" claim above was wrong.** Removing the P0 alarm
dropped the failures from 115 to 97, and every remaining one is a different
fail-closed guard: `corpus_retrieval_v2_implementation_contract` — "public v2
numerical runtime identity drifted". That contract (frozen 2026-08-24,
`5e49d774`) pins the interpreter binary itself, and exactly one runtime fact
differs:

```
python_executable_bytes    pinned 7,481,192   current 7,477,160
python_executable_sha256   pinned b8d8288f…   current 52e0a13e…
(python_version 3.14.4, numpy 2.5.1 and its core binary, CPU features: identical)
```

`.venv/bin/python -> python3 -> /usr/bin/python3.14`, and apt upgraded
`python3.14-minimal` from `3.14.4-1ubuntu0.1` to `1ubuntu0.2` on
2026-09-09. The pre-upgrade package is still in `/var/cache/apt/archives/`;
its `usr/bin/python3.14` hashes to the pinned identity exactly. Running the
factorial, companion and contract modules under that extracted binary (no
system change, `PYTHONPATH=src:.venv site-packages`) gives **160 passed**, and
the two sibling modules the inventory listed in this band
(`test_corpus_extreme_tail_generation_additions`, `test_corpus_expansion_build`)
pass under the current binary too — they only ever saw the P0 drift.

So the factorial band decomposes as: P0 policy drift (fixed, this commit) +
interpreter binary change (a real runtime change the guard is designed to
catch; not a code defect). The three affected modules stay quarantined on this
workstation with the corrected reason in `scripts/test_lanes.sh`.

**Remaining decision (operator, not urgent, no Week-1 impact):** either hold or
downgrade `python3.14-minimal` to `1ubuntu0.1` so the workstation matches the
frozen runtime, or amend the v2 implementation contract's runtime identity —
which re-keys `_EXPECTED_CONTRACT_SHA256` and therefore every retained receipt
that embeds it (`test_corpus_r6_full_union_grade_release_v1` and the score
report CLI both compare retained contract identity against current), so it is
a sweep, not a constant edit. Note that the pinned identity is the
workstation's Ubuntu binary, not the `python:3.14.4-slim` image binary; the
contract can never have validated inside the cloud image as pinned.
