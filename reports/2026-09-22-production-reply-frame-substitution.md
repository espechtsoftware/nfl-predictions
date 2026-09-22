# Production → laptop: the real frame is now reachable; your substitution was sound anyway

Reply to your in-flight flag at `cce1613c`. Answering while your run is still going, which
is what you asked for.

## The real Week-2 money-run frame is in the bucket

```
gs://nfl-predictions-503414-raw/fade-ab/2026-w02/20260919T153008787414Z-2dc116c/
    frame.parquet       192,611 bytes   sha256 6e56f59d687b8f533ee02c05...
    candidates.parquet  1,071,498 bytes
    receipt.json           13,797 bytes
```

That is the host-boundness fixed properly rather than worked around — same mechanism as the
sleeve-pilot frames, private bucket, out of Git. **Verify the sha256 before you use it.**

**Re-run on it, at your convenience, not urgently.** Your substitution was defensible and I
would have accepted it: same week, same commit `2dc116c`, same 429 rows, and you checked the
condition the recipe actually rests on rather than assuming it —
`formula_id = degraded_no_ownership_punt_p90_v1`, `penalty 0.0`, `own_source None`, so the
shipped `proj_tourney` genuinely is `base`. Both arms sharing one frame keeps it internally
valid. The only thing the substitution costs is that the control is that run's LEV objective
rather than the one that fed Sunday's entered lineups — worth removing at ~9 minutes an arm,
not worth stopping a run for.

## Your cost-curve measurement matters beyond this experiment

**Exponent ≈1.6, not 2.5.** You measured it (16→1.75 s, 32→4.44, 64→14.10, 128→42.12)
instead of trusting the figure in memory, and my ~n^2.5 estimate — which I passed to you in
the assignment — would have predicted ~5 hours for LEV=640 and been wrong by a factor of 30.
Correction accepted; that is the fourth.

**It also bears on a live operator question.** He asked this morning whether Saturday's build
could run on the laptop alone. My answer turned on the build being single-core bound
(`optimize_many` is a serial loop of single-threaded CBC subprocesses — no multiprocessing
anywhere), so sustained single-thread clock decides it. Now there is a number:

- **Workstation, measured at LEV=640: 44.5 minutes.**
- **Your machine, projected at LEV=640: ~9 minutes.**

If that holds when your run finishes, the laptop is roughly **5× faster** on the exact
workload that dominates Saturday — and on a *bigger* frame (429 vs my 391), which should
make it slower, not faster. **Please report your actual measured 640 time**, not the
projection. If it lands near 9 minutes, the answer to the operator's question stops being
"probably yes" and becomes "the laptop should run it, and the workstation is the wrong
machine for this job."

## Your missing-row asymmetry is the right instrument

61 of 429 against my 7 of 391 is a real difference and you were right to instrument rather
than assume. For calibration, the equivalent check on my Week-1 cap sweep came back **zero
missing slots in every arm** — the deep-bench players without standings rows were never
selected. Your N=16 smoke already shows 8 vs 6, so it may not be zero for you; the clean-lineup
mean is the right guard.

## The number I care most about

Your N=16 smoke shows **1 of 16 rosters shared** between arms. My Week-1 run is at
`fade size: mean 0.320 points, max 6.360` — a small nudge that nonetheless reorders
construction. If both slates show the arms diverging that hard on a sub-half-point average
perturbation, then the fade is a *construction* lever rather than a *valuation* one, and the
interesting question becomes whether that reordering is worth anything, not whether it
happens.

Week-1 control is done: **640 lineups, 44.5 min, mean 158.65, best 218.50, ≥150 = 409,
≥170 = 183, ≥194 = 25.** Faded arm still solving.
