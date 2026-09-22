# Review: the QB-gate shipping branch is sound — ship it; one closure of mine needs narrowing

Second-party review of `production/week3-qbgate-on-cf630a68-20260922` @ `25a159df`, the
minimal branch the gate ships from because integration cannot currently pass the live lane
(`24604d65`). **Verdict: ship.**

## Checked

| check | result |
|---|---|
| diff against the deployed commit `cf630a68` | 6 files: `cascade_adjust.py`, `run_projections.py`, inventory module, two test files, `cloudbuild.week1-live.yaml` |
| `engine.py` byte-identical to deployed | **yes** |
| both refinements present | `QB_DOUBTFUL_ABSENT` and `QB_NO_DEPTH1_PROMOTE`, both default on |
| gate on the **pre-lock** 2026-09-19 frame | **49 QBs zeroed, 378.6 projection points, Tua zeroed** |
| tests on a real worktree of the branch | **36 passed** (17 gate + 19 inventory) |

Tua is zeroed on the only frame that represents build-time state, which is the case both
refinements exist for. The kill switches (`QB_BACKUP_GATE`, `QB_DOUBTFUL_ABSENT`,
`QB_NO_DEPTH1_PROMOTE`) all revert without a redeploy.

(My first test run showed 15 errors; they came from my extracting `src/` and `tests/` with
`git archive` into a directory without `cloudbuild.yaml`, which the inventory test reads.
Re-run in a proper worktree: all pass. Recorded so nobody chases it.)

## Checked and dismissed: `market_source_log` schema divergence

The shipping branch writes `market_source_log` **without** `model_points_pre` and
`model_weight`; integration writes them. The table does not exist yet, so the first writer
fixes its schema. **No hazard:** `load_dataframe` sets `ALLOW_FIELD_ADDITION` on every
`WRITE_APPEND`, so whichever image writes first, the other appends cleanly.

## One consequence, and it narrows something I said

In closing item 1 (`a2fdb2a9`) I wrote that the forward audit gap was *"already closed by
`market_source_log.model_points_pre`"*. **For Week 3 that is not true**: the deployed image
does not write the column.

It matters less than it sounds, because of the same measurement that closed item 1. The blend
identity is exact (211/211 rows, residual 0.0), so for any prop-sourced row the pre-blend value
is recoverable **exactly** from what the log does record:

```
model_points_pre = (proj_points - (1 - w) * market_points) / w
```

and a model-only row under props-or-nothing is served unblended, so `proj_points` *is* the
pre-blend value. The only thing lost is the self-documenting weight column; `w` lives in the
adopted policy (`BLEND_MODEL_WEIGHT`) instead of in each row. If that weight ever changes
mid-season, a Week-3 row alone would no longer say which `w` produced it — worth remembering,
not worth delaying a ship for.

Correction recorded: **the forward gap is closed in integration, and recoverable-by-exact-
inversion in the deployed Week-3 image.**
