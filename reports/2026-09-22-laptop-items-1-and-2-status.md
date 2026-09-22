# Laptop → production: items 1 and 2 re-checked at the serving commit — one is
# closed, one is half-closed and will repeat on Sunday

Follow-up to `reports/2026-09-22-laptop-doubtful-verification.md`. Production ranked
the two reporting items after the Doubtful check; this is that work. Checked against
`origin/production/week3-integration-20260921` @ `a4378fdd`.

Two of the four findings below are **time-sensitive** and are stated first.

---

## A. TIME-SENSITIVE — the market-source log's mutation guard has a hole (new)

Item 1's standing recommendation — add the pre-blend model value to
`market_source_log` — **is implemented**, and item 1's report is stale on that point.
`source_log_frame` takes `model_points_pre` and `model_weight`, and
`run_projections.py:412` passes `_pre_blend` and the weight actually used. Ten tests
pass, including a genuinely good AST guard
(`test_the_projection_run_actually_passes_the_model_side`) that pins the *wiring*, not
just the function, precisely so the column cannot silently land NULL.

**The guard checks that the kwarg is present and is not a literal `None`. It does not
check what is passed.** I mutated the call site to

```python
model_points_pre=preds["proj_points"].to_numpy(),   # the BLENDED output
```

and **all four tests still pass**. That mutation recreates the original defect in a
subtler and more dangerous form: the column would be populated, would look observed
rather than derived, and would record the blend's output as its own input. The Week-2
lesson was that a derived number indistinguishable from an observed one is what made
Jefferson unauditable — this mutation puts exactly that back, past a guard written to
stop it.

Severity is low-probability, high-consequence: it needs someone to edit that line
wrongly. But the fix is two lines in the existing test — assert the argument is the
`_pre_blend` *name*, not an arbitrary expression:

```python
for k in call.keywords:
    if k.arg == "model_points_pre":
        assert isinstance(k.value, ast.Name) and k.value.id == "_pre_blend", (
            "model_points_pre must be the pre-blend array, not a derived expression")
```

**Why now:** this is a test-only change, touching no money-path behaviour, and
`market_source_log` does not exist yet — it is created the first time `project-slate`
runs on the repaired image. Tightening the guard before that run costs nothing.

## B. TIME-SENSITIVE — item 2's fix is built but nothing calls it, so Week 3 repeats

Item 2 recommended making the candidate-write loss **loud** rather than fatal. That
instrument now exists and is well built: `_CANDIDATE_PERSIST` carries
`state/rows/run/asynchronous/required/error`, `candidate_persist_status()` reads it,
and `flush_candidate_persistence(timeout=30.0)` joins the in-flight thread and
distinguishes `ok` / `failed` / `timeout` from `started`.

**Nothing in the money path calls either one.** `flush_candidate_persistence`'s own
docstring says so — *"Callers opt in. Not called anywhere in the money path"* — and
grep across `scripts/` and `src/` confirms zero callers outside `engine.py` and tests.

The warehouse agrees that nothing has changed:

| season | week | rows | most recent write |
|---|---|---|---:|
| 2024 | 3 | 20,665 | **2026-09-21 01:57** |
| 2022 | 1 | 124 | 2026-08-05 |

**Still zero 2026 rows**, and the 2024 rows are still the synthetic offline-run
contamination, written the day before this branch was cut.

So item 2's prediction stands unchanged: **Week 3's book will again not record the
levers that produced it**, and the next post-mortem will again be unable to say which
ownership input generation consumed. The half that was built is the hard half; the
missing half is one call at the end of the build wrapper, recording the returned status
in the receipt. It cannot stall the money path — the flush is bounded at 30 seconds and
`cand_log_async` is untouched.

I have **not** implemented it. It is money-path-adjacent and production owns that call
this week. Say the word and it ships with a test.

---

## C. Item 1 is now closable in principle, and only historically open

With A above implemented, the *forward* audit gap is closed: from the first
`project-slate` run on the repaired image, every row records the model side, the market
side, the weight and the output, so `proj == w·model_pre + (1−w)·market` is checkable
rather than invertible.

What remains of item 1 is **only the retrospective question** — Jefferson's Week-2
pre-blend value — and its obstacle is unchanged and now confirmed twice over:
`nfl_predictions.player_projections` has no pre-blend column, and `market_source_log`
did not exist in Week 2. The value was never written. Option (1), a re-run at the
serving commit, remains the only path, and it is a research re-run, not a money-path
action.

**I have not started that re-run**, for two reasons worth stating: it is a GCP cost the
operator has not authorised, and the Week-3 Cloud Run sequence is explicitly on hold
pending the operator's go-ahead — starting an unrelated re-run in that window risks
confusion about what wrote what. It is the right next task once Sunday is clear.

## D. The consolidation table needs your source list

Item 2's broader ask — per bug: introduced commit, reproducer, affected outputs,
regression test, fixed-path replay, in one table — I cannot build faithfully, because
`handoffs/2026-09-21-laptop-postmortem-review-round1.md` is **not in the repository** on
any branch. It is referenced by both item reports and by `HANDOFF.md`, but was never
committed; it appears to have lived on your side only.

I can either (a) work from your round1 list if you push it, or (b) derive the defect set
myself from `HANDOFF.md` and the item 1–7 reports and send it back for correction. (b)
is honest but will miss anything that was only ever raised in chat — which, given this
project's own rule that findings travel as committed files, is worth knowing either way.

Tell me which, and it is the next thing I do. It does not expire, which is why it is
last in this report.

---

## Method note

Mutation testing followed the documented order — the worktree was committed and pushed
clean *before* the call site was mutated, and restored with `git checkout --` only after
the run, so nothing uncommitted was at risk. Suites were run with
`PYTHONPATH=<worktree>/src` so the worktree's own source was under test rather than
main's editable install. Nothing was run on Cloud Run, no clone was moved, and
`week2-release-2dc116c` was not touched.
