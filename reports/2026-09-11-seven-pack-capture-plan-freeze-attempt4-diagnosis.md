# Seven-pack capture-plan freeze, attempt 4: diagnosis and repair

**Date:** 2026-09-11 · **Status:** gate failure explained, repaired, not yet re-run

## What failed

`nfl-week1-capture-plan-freeze-v3.service` exited 2 at 06:32:17 CDT with:

```
seven-pack independent reopen failed: warehouse query spec differs from the frozen query registry
```

The unit ran:

```
/home/erich/projects/nfl-predictions/.venv/bin/python \
  scripts/run_corpus_r6_matchup_seven_pack_capture_v1.py freeze-capture-plan \
  --release-identity /tmp/capture-plan-freeze-attempt4.ahujca/release-identity.json \
  --repository-root /home/erich/projects/.nfl-predictions-worktrees/capture-plan-terminal-lock-v2-20260911 \
  --confirm-freeze
```

## The artifact is sound

The release object was fetched at its pinned generation and verified:

```
uri     gs://.../20260911-fp-sis-seven-pack-successor-v4/upstream-release.json
bytes   22925    == declared
sha256  1de61029e63907530d1d4182c1b37189828be4a9d9e635bd61fe2529b8af34e5  == declared
```

All five warehouse query receipts were pulled at their pinned generations and
each stored `query_spec` was diffed field-by-field against a live
re-derivation, bounding the **union** of both key sets so a key present only
in the stored spec could not hide:

| pack | under worktree code `e9915372` | under `main` code `8d7140f4` |
|---|---|---|
| nfl-schedules-2022-2025 | IDENTICAL | differs |
| nfl-weekly-stats-2022-2025 | IDENTICAL | differs |
| nfl-legacy-depth-2022-2024 | IDENTICAL | differs |
| nfl-snapshot-depth-2025 | IDENTICAL | differs |
| nfl-pfr-defense-and-snaps-2022-2025 | IDENTICAL | differs |

Divergent fields are `canonical_query`, `query_sha256`, `job_id`,
`query_spec_sha256` — all downstream of `canonical_query`. `main` lacks the
`relation_columns` CTE and the `frozen_tables.`-qualified projections that
the branch commits added.

**The gate was correct. The invocation was wrong.**

## Root cause

`--repository-root` fixes the tree whose commit is recorded as the run's
provenance. It does **not** influence which files Python imports. The venv at
`/home/erich/projects/nfl-predictions/.venv` is an editable install rooted in
the main checkout, so `nfl_dfs` resolved to `main`'s `src/` while the declared
root was the worktree:

```
imported from: /home/erich/projects/nfl-predictions/src/nfl_dfs/research/...
declared root: /home/erich/projects/.nfl-predictions-worktrees/capture-plan-terminal-lock-v2-20260911
git diff on that one module, main vs worktree: 21 insertions, 65 deletions
```

The capture was produced by the worktree's code at 00:59:19; the last commit
touching that module landed at 00:17:07. No code changed between capture and
validation — the two sides simply never ran the same code.

## The part that matters more than the failure

The freeze failing is the **good** outcome. This run would otherwise have
stamped the worktree commit `e9915372` as provenance on a result computed by
`8d7140f4`'s code. It was caught only incidentally, because this particular
module's SQL happens to be hash-gated. The same invocation error in a module
whose output is not hash-gated produces a **provenance-mislabelled artifact
with no failure at all** — the frozen-chain equivalent of a silent lie.

`repository_root` is used for git HEAD, git blobs, git status and output path
construction. It was never bound to module resolution anywhere.

## Repair

`_bind_executing_code_to_repository_root` is added at
`_trusted_repository_root`, the single chokepoint every subcommand passes
through. It refuses unless the CLI itself and all four imported `nfl_dfs`
authorities resolve under the declared root. It can only refuse more, never
less.

Mutation-checked two-sided: accepts when the root owns the code, refuses the
exact attempt-4 invocation, and with the guard neutered that invocation is
accepted again — so the guard is load-bearing. A second test derives the
imported-alias set from the CLI's own import block and fails if any alias is
unbound; dropping one binding fails it by name.

`44 passed` across the five seven-pack test modules.

## Not done

- The freeze has **not** been re-run. Attempt 5 must either run under the
  worktree's own interpreter or set `PYTHONPATH` to the worktree `src/`; the
  new guard now refuses the wrong combination rather than proceeding.
- The defect class was swept across the 13 scripts taking `--repository-root`.
  Several derive the root from `__file__` and are structurally safe. The
  remaining flag-taking siblings are **not** yet guarded and should be.
- `HANDOFF.md` and several other files carry uncommitted production edits.
  They were deliberately left untouched.
