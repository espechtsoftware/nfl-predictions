# Decision 2 is not a decision: nothing drifted, some callers still ask for v7

Diagnosing the highest-leverage item on
`reports/2026-09-21-ci-step2-decision-list.md` — `EffectivePolicyInventoryError:
frozen source SHA-256 differs`, 20 failures across three modules.

**Nothing has drifted, and no manifest should be re-frozen.** Re-freezing here
would destroy a version history that is working exactly as designed.

## What is actually true

`effective_policy_rule_inventory` keeps **versioned** pin sets — `FROZEN_`,
`V6_`, `V7_`, `V8_FROZEN_SOURCE_SHA256`. Checked against the working tree:

```
src/nfl_dfs/inference/live_lineups.py
  actual on disk            7290c0797ed83c73
  V8_FROZEN_SOURCE_SHA256   7290c0797ed83c73   MATCHES
  V7_FROZEN_SOURCE_SHA256   95ccc439badad137   differs
  V6_ / base                b37e9c5056bebe02   differs
```

**V8 matches the tree on all 20 pinned sources — 0 drifted.** V7 differs on
exactly two: `live_lineups.py` and `run_projections.py`.

Both changed in `82739685` (2026-09-20), the market-source repair — *"Live
market: props or nothing (operator directive 2026-09-20) … the DK-PPG stand-in
that served Jefferson 25.3 in Week 2 is removed; **inventory source-set v8**;
tests."*

So whoever made that change **did the frozen-chain discipline correctly**: they
changed two pinned sources and minted a new pin set in the same commit. What
was missed is that some callers still ask for the v7 inventory, which by
definition predates those two changes.

## Proven, not proposed

`tests/test_corpus_parametric_snapshot.py` and
`tests/test_corpus_legal_feasibility.py` call
`generate_effective_policy_rule_inventory_v7`. Substituting `_v7` → `_v8` in a
scratch copy, changing nothing else:

```
5 passed in 1.45s
```

`generate_effective_policy_rule_inventory_v8` already exists alongside v6 and
v7, same shape.

**One caveat, stated rather than glossed:** the third module,
`test_prospective_prelock_lineage_shadow_v2.py`, fails with the identical error
but does **not** call the generator directly — it reaches the inventory through
the module under test, and we have not traced which version that binds. Its 9
failures share the cause but may not share the fix.

## The actual question for you

Not "re-freeze or retire". It is:

**Are these tests meant to validate the CURRENT effective policy, or to pin the
v7 inventory historically?**

- **Current policy** → point them at `_v8`. Two call sites, proven to pass.
- **Historical v7** → they can never pass on a post-`82739685` tree, so they
  belong behind the same kind of guard as the runtime-pinned chains: skipped
  with a stated reason, not failing and not re-frozen.

Either way the answer is cheap, and **neither answer is "re-freeze V7"** — V7
is correct as a historical record of what the policy was before the market-source
repair. Overwriting it would erase the one thing that makes the v6/v7/v8
progression auditable.

## Running total on the step-2 list

| item | original claim | after diagnosis |
|---|---|---|
| 1 — A7 Cloud Build contract (40) | your decision | **uncertain**; the chain shells out to git and a depth-1 clone broke it, now fixed |
| 2 — policy inventory (20) | your decision, highest leverage | **not a decision** — two call sites, or a guard |
| 3 — evidence graph (18) | your decision | still yours; recommendation already given (resolve the blob at the recorded commit) |
| 4 — composite retrieval (10) | your decision | still yours — hashes the working tree, no git |
| 5 — A7-v2 lineage (8) | your decision | **confirmed CI artifact** — reports "differs" for "absent" |

Of the ~137 originally handed to you, roughly 28 are genuinely yours to decide.
