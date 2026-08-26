# R6 fixed-G0 recovery focused-test environment failure

Date: 2026-08-26

The independently licensed command

```text
.venv/bin/python -m pytest -q tests/test_corpus_r6_player_catalog_fixed_g0_adapter_v1.py
```

was invoked once from isolated worktree
`/tmp/nfl-r6-fixed-g0-443f0746`. It exited 2 during collection before any
test item ran. The isolated `.venv` linked the main repository virtual
environment, whose editable installation resolved
`nfl_dfs.research.corpus_r6_player_catalog_fixed_g0_adapter_v1` from the main
worktree rather than the reviewed isolated source. Collection therefore
stopped at test-module line 3555 because that older module did not expose
`FIXED_TASK0_SMOKE_RECOVERY_REVIEW_LOCK_PATH`.

Exact reported exception:

```text
AttributeError: module 'nfl_dfs.research.corpus_r6_player_catalog_fixed_g0_adapter_v1' has no attribute 'FIXED_TASK0_SMOKE_RECOVERY_REVIEW_LOCK_PATH'
```

Pytest reported one collection error and no passing or failing test items.
The reviewed recovery candidate was not imported or executed. The command
constructed no GCS client, made no cloud read or mutation, created no recovery
lock or v2 smoke marker, published nothing, and read no result, lineup,
world-matrix, score, or realized outcome.

The environment-only correction is to track the already-reviewed candidate
on main and invoke the same fixed command from that worktree, where the
editable installation and reviewed source resolve to the same bytes. No
scientific, artifact, pin, smoke, or authority rule changes.
