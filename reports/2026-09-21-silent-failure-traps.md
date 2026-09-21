# Traps that report success while being wrong

For whoever runs the weekly build. Every item here was hit for real on
2026-09-21. They share one property: **none of them raises an error at the
point you make the mistake.** They return a plausible answer, or a green
check, and you find out later.

Ordinary bugs announce themselves. These do not, so they are worth knowing
before you need them.

---

## 1. `project-slate` run on a Monday builds the PREVIOUS week

`run_projections.run()` resolves its target week with:

```sql
SELECT MIN(week) FROM schedules
WHERE season = @season AND game_type = 'REG'
  AND gameday >= CAST(CURRENT_DATE() AS STRING)
```

A Monday-night game is still `gameday >= CURRENT_DATE()`, so on that Monday the
"upcoming" week is **the week that is ending**, not the one starting.

Hit on 2026-09-21: `project-slate` was executed to populate Week 3. It resolved
to **week 2** because `NYG @ LA` had not kicked off. Execution
`project-slate-pgvjz`.

**Rule: do not run `project-slate` until every game of the previous week has
been played.** Tuesday onward is safe. The normal Wednesday cadence is safe,
which is why this has never bitten before.

It failed rather than writing the wrong week — but only by luck, see §2.

## 2. The thing that saved us: `MarketMatchError` is the repair working

That same run died on:

> `MarketMatchError: prop lines exist in the feed for 19 slate player(s) but
> did not match a projection row`

All 19 were on **LAR (11) and NYG (8)** — exactly the two teams playing that
night. Week-2 projections had been built for the Sunday main slate, which did
not include the Monday game, so those depth players had prop lines and no
projection row.

**The old image would have silently substituted DK-PPG for all 19.** That is
precisely the Week-2 Justin Jefferson failure (25.35 from a prop name-match
miss plus a one-game DK-PPG fallback). The repaired image refuses instead.

So a `MarketMatchError` is not a regression to route around. It is the
no-silent-fallbacks rule catching a real gap. Diagnose the gap.

Corollary, and the only reliable proof the repoint took:

```
market-source log:      <- ONLY the repaired image writes this
market blend source:    <- the OLD image writes this too; USELESS as a check
```

## 3. `tabpfn-gen` before `build-features` writes a cache that PASSES the gate

CLAUDE.md says run it "WEEKLY Wed + **after every build-features**". That
ordering is load-bearing, not stylistic.

Run out of order on 2026-09-21: `TABPFN_UPCOMING=2026:3` succeeded
(`succeededCount=1`) and wrote **51 rows** for week 3, against 813 classic
players posted on DK, because Week-3 `build-features` had not run and there were
almost no inference rows to build marginals from. It also truncated the 877
week-2 rows.

**The gate then went green.** `assess_tabpfn` in
`src/nfl_dfs/inference/build_inputs.py` checks only:

```python
if rows_for_week <= 0: problems.append(...)
```

Presence, not sufficiency. A cache covering one game's worth of players is
indistinguishable from a complete one. Note that `assess_files`, ten lines
below, does carry `min_book_entries: int = 90` — the pattern exists; TabPFN
lacks it.

**Rule: run `build-features` first, then `tabpfn-gen`. If the week-3 row count
is in the tens rather than the high hundreds, the cache is incomplete no matter
what the gate says.** Re-running truncates and rewrites, so it is
self-correcting.

## 4. Running from a worktree imports the MAIN checkout's `src`

The venv is an editable install pointing at
`/home/erich/projects/nfl-predictions/src`. Working inside a worktree does not
change that:

```
cd /home/erich/projects/.nfl-predictions-worktrees/<wt>
.../.venv/bin/python -c "import nfl_dfs.bq as b; print(b.__file__)"
  -> /home/erich/projects/nfl-predictions/src/nfl_dfs/bq.py     # NOT the worktree
```

Scripts invoked by path (`scripts/*.py`, `scripts/*.sh`) **do** come from the
worktree. That mixture is what makes it deceptive: you can run the worktree's
script against the main checkout's library.

Hit twice on 2026-09-21. The second time, `check-freshness` reported
`cfb_dk_salaries` STALE from the main checkout even though the integration
branch sets that feed `alert=False` — a false "your fix did not work".

**Rule: `PYTHONPATH=<worktree>/src` for anything that imports `nfl_dfs`. When a
result surprises you, print `module.__file__` before believing it.**

`scripts/host_ingest_dk_loop.sh` gets this right (`export
PYTHONPATH="$PROD/src"`), which is why the DK loop swap ran the intended code.

## 5. `check_build_inputs.py` reports both operator files MISSING unless you pass their paths

The readiness gate does **not** read `$OUT`. It takes explicit flags:

```bash
python scripts/check_build_inputs.py --season 2026 --week 3 \
  --chosen-dose $OUT/chosen-dose.env \
  --contests    $OUT/contests.json
```

Run without them, `dose` and `contests` are `None` and the gate reports
`chosen-dose file missing or without CHOSEN_LEV/CHOSEN_BOOM; contests.json
missing or empty` — **whether or not the files exist**.

Hit on 2026-09-21: `chosen-dose.env` had just been written and validated, and
the bare invocation still called it missing. The failure direction is safe (it
cries missing when present, never present when missing), but it wastes time and
it will make a correctly-prepared week look unready. If you are checking
readiness, pass the paths.

## 6. Smaller ones, same family

- **`pytest -q`**: `addopts` is already quiet, so `-q` makes it `-qq` and drops
  the "N passed" summary line. An empty collection then exits 0 and looks like
  a pass. Never pass `-q` here.
- **BigQuery reserved words**: `nulls` and `groups` are both reserved and fail
  as column aliases with a bare syntax error that does not name the cause. Use
  `null_team`, `n_groups`.
- **`scripts/test_lanes.sh` from a worktree**: `PY` was hardcoded to a relative
  `.venv/bin/python` that no worktree has. Fixed 2026-09-21 — it now fails
  closed naming the override rather than silently using a system interpreter.
- **Cloud Run acceptance**: an unset `failedCount` means zero, not failure.
  Require `succeededCount=1` AND a `completionTime`; do not read the absence of
  a failure count as success.

---

## The pattern

Most of these are one defect class in different clothing: **a selector — which
week, which tree, which interpreter — was resolved implicitly instead of being
stated.** The week came from today's date (§1), the module came from an
editable install (§4), the interpreter came from `$PATH` (§6). In each case
something guessed, guessed plausibly, and was believed.

The standing rule that prevents all of them: *an argument that selects which
data a run operates on must be required or derived from the artifact, never
both optional and defaulted.*

**§5 is the instructive exception: it is that rule working correctly.**
`check_build_inputs.py` refuses to guess which files you mean, so it reports
nothing rather than inventing a path — and it errs toward "missing" rather than
toward "fine". That is the right direction to fail, and the only fault is
wording: it says *missing* when it means *not specified*. Worth remembering
when the rule feels inconvenient, because a tool that guessed `$OUT` for you
would eventually check last week's files and call the week ready.
