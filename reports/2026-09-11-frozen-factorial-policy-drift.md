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
