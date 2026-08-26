# R6 fixed-G0 terminal-recovery clean-head failure addendum

**Date:** 2026-08-26  
**Disposition:** environment-only first invocation failed; one reviewed
clean-head correction passed; no third invocation is allowed

## Purpose

This additive record preserves the complete material facts for the exact
two-file terminal-recovery focused-test command. It does not replace or
rewrite either the earlier one-file collection-environment failure in
`reports/2026-08-26-r6-fixed-g0-recovery-focused-test-environment-failure.md`
or either failed real-artifact adapter smoke. Those are separate events.

No catalog, matchup, candidate, retrieval, scoring, outcome, graph, IAM,
cloud, publication, or production operation occurred in either invocation
described here.

## Failed first exact-argv invocation

The exact command was:

```text
/home/erich/projects/nfl-predictions/.venv/bin/python -m pytest -q -o addopts= --color=no tests/test_corpus_r6_player_catalog_fixed_g0_adapter_v1.py tests/test_corpus_r6_player_catalog_fixed_g0_terminal_recovery_v1.py
```

- working directory:
  `/tmp/nfl-r6-recovery-lock-1df12164`
- `PYTHONPATH`:
  `/tmp/nfl-r6-recovery-lock-1df12164/src`
- pre-run HEAD:
  `d84df6cf751263b34b41f3641a767219abe787d4`
- exit code: `1`
- collected cases: `148`
- passed: `137`
- failed: `11`
- common exception:
  `production repository must be tracked-clean including untracked`
- pytest terminal summary:
  `11 failed, 137 passed in 15.88s`

The exact pre-run dirty-status rows were:

```text
 M src/nfl_dfs/research/corpus_r6_player_catalog_fixed_g0_terminal_recovery_v1.py
 M tests/test_corpus_r6_player_catalog_fixed_g0_adapter_v1.py
 M tests/test_corpus_r6_player_catalog_fixed_g0_terminal_recovery_v1.py
```

All 124 adapter cases passed. Thirteen of the 24 recovery cases passed. The
remaining 11 expanded recovery cases all called
`SubprocessGitRepositoryV1.require_current_clean_head()` and stopped at the
same clean-worktree precondition before their intended assertions. The
failing cases were:

1. `test_exact_tracked_publication_receipt_regression_and_terminal_evidence`
2. `test_review_and_final_locks_truthfully_close_both_attempts`
3. eight expansions of
   `test_review_lock_rejects_coherently_rehashed_semantic_drift`
4. `test_final_lock_rejects_wrong_commands_and_required_count`

The complete raw terminal stream was captured by the execution transport but
was not redirected to a repository file. This report retains its exact
command, progress disposition, complete failing-case census, common
exception, terminal summary, and environment state; it does not falsely
claim a separately persisted raw-output object.

## Reviewed correction

Independent bounded review found P0/P1/P2 all zero for the implementation
bytes and confirmed that committing exactly the three already-reviewed dirty
blobs, without changing their bytes, was the complete environment correction.
The resulting isolated clean-head commit is:

```text
dbc0606fa81ef0b48e9bccba9d595a3455755e65
```

Before the corrected invocation, the repository status was empty under
`git status --porcelain=v1 --untracked-files=all`. The six exact runtime
measurements were:

| File | SHA-256 | Bytes |
| --- | --- | ---: |
| `src/nfl_dfs/research/corpus_r6_player_catalog_fixed_g0_adapter_v1.py` | `46a523ba1b15f1a20d1afdb4bee041d33127b8f78f88e705b510d578c7882cd8` | 244699 |
| `tests/test_corpus_r6_player_catalog_fixed_g0_adapter_v1.py` | `e448003a3160cff833328cb8bb8538b55e0118faf07b717877f1da0c1676edd8` | 142528 |
| `src/nfl_dfs/research/corpus_r6_player_catalog_v1.py` | `5da7905f3caa620597f22bfb348a12d099709feb26a409ecec8c5578c03d99b7` | 68934 |
| `src/nfl_dfs/research/corpus_parametric_batch.py` | `4cb7b3d613ed9dd8c35d4d9120798cf2863bb438a5cb3a7b05596fe97bc99bae` | 62260 |
| `src/nfl_dfs/research/corpus_r6_player_catalog_fixed_g0_terminal_recovery_v1.py` | `bc0761eb9a283720657010ace7a1fe3624c6bbd44e5b835b98bcaa1c94b77776` | 39383 |
| `tests/test_corpus_r6_player_catalog_fixed_g0_terminal_recovery_v1.py` | `3aca6165f236c344b6e6320c7ce8499233582cb0eb8357791ebc6d77b4539068` | 18814 |

## Corrected result

The one independently licensed corrected invocation used the identical argv,
working directory, `PYTHONPATH`, and non-TTY conditions. It exited `0`:

```text
148 passed in 15.18s
```

Its exact stdout is retained at
`reports/2026-08-26-r6-fixed-g0-terminal-recovery-focused-test-output.txt`:

- SHA-256:
  `8ce5c8735b888c9d02439a5a5259d6c4834ea8170952441da5c43b8a81ec017a`
- bytes: `261`

## Invocation accounting

- failed invocations of this exact two-file argv: `1`
- passing corrected invocations of this exact two-file argv: `1`
- lifetime total invocations of this exact two-file argv: `2`
- third invocation: forbidden

The recovery review lock's
`focused_test_invocation_count=1` denotes the one passing invocation bound
to its exact output file. This addendum and the implementation commit preserve
the lifetime two-invocation truth. Real-artifact adapter smoke accounting is
unchanged: two failed adapter smokes, no success receipt, and no third smoke.
