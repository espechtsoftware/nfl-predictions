# Laptop → production: the finding is correct and verified; the fix is not one line;
# and the fade's top targets are the three players the cap analysis blamed

Review of `55903961`. **Every code claim checks out.** Two things to add: a correction
about cost, and a measurement you do not have.

## Verified independently, at nfl2 `69f98a7`

| claim | result |
|---|---|
| `live_week.py:191` calls `proj_tourney_production(fr, draws)` with `own_est` omitted | **confirmed** — the inline comment even says "degraded ID when no ownership" |
| `own_est=None` takes the degraded branch | **confirmed** — `out = base`, `penalty: 0.0`, formula id `degraded_no_ownership_punt_p90_v1` |
| the docstring admits the degradation | **confirmed** — *"With ownership unavailable this is NOT production parity"* |
| `proj_tourney` is the LEV objective | **confirmed** — `pipeline.py:463`, `optimize_many(..., objective_col="proj_tourney")` |
| `naive_ownership` is a pure function of `proj`, `salary`, `pos` | **confirmed** — 15 lines, pandas/numpy only, no `nfl_dfs` internals |

So the lever is inactive for exactly the reason stated, and the design is honest about it —
the receipt never carries a silent zero under the production label. The defect is the
caller, as you said.

## Correction: "the change is one line" is not right, and the reason matters

`naive_ownership` lives in **`nfl_dfs/backtest/field.py`** — the production repo. The money
path lives in **nfl2**. And:

**nfl2 never imports `nfl_dfs` at runtime.** Grepping `69f98a7` for `nfl_dfs` returns three
files, and in all three the match is **prose inside a docstring or comment** (`simulate.py`
lines 149 and 238 are "See src/nfl_dfs/research/sbi_params.py"). There is no
`import nfl_dfs` anywhere in nfl2.

So restoring the fade is one of:

1. **a real cross-repo runtime dependency** in the money path — install/PYTHONPATH/version
   pinning across two repos with two GCP projects, on the Sunday path;
2. **a port** of `naive_ownership` into nfl2 — feasible, it is self-contained, but it is a
   copy that must not drift, and the proven +2 depends on the weights matching exactly;
3. **computing ownership production-side and passing it in as data** — probably the
   cleanest, since `live_week.py` already builds the frame.

None is one line, and (1) and (2) both create a **parity surface**: the six-season replay
proved +2 with specific weights, so any reimplementation that drifts silently breaks the
thing being restored. That is the defect class this project keeps paying for, so it is
worth choosing the mechanism deliberately rather than by whichever is shortest.

This does not argue against the A/B. It argues that the cost line in the plan is wrong and
the mechanism is a decision, not an implementation detail.

## Measurement you do not have: what the fade would actually do

Ran `naive_ownership` against the **Week-2 served slate** (513 rows,
`player_projections`), penalty `25.0 * own_est`. Probe:
`reports/lab-handoffs/fade_magnitude_probe.py`.

| pos | n | mean fade | median | max |
|---|---:|---:|---:|---:|
| DST | 32 | **0.781** | 0.522 | 3.518 |
| QB | 85 | 0.294 | 0.035 | 1.078 |
| RB | 109 | 0.229 | 0.054 | 1.760 |
| TE | 113 | 0.221 | 0.048 | 1.806 |
| WR | 174 | **0.144** | 0.060 | 2.270 |

Whole slate: mean **0.244**, median **0.056**, max **3.518** — about **4.4%** of mean
projection.

**Two things follow.**

**(a) The fade is position-asymmetric, by construction rather than by intent.**
`naive_ownership` normalizes weights to sum to 1 *within each position group*, so per-player
fade scales inversely with group size. DST is faded **5.4x harder than WR** on average — not
because DSTs are chalkier, but because there are 32 of them and 174 WRs. Four of the eight
largest fades on the slate are DSTs. The replay proved +2 with these same units, so this is
"as proven"; but it means the effective penalty moves with a slate's position mix, and that
is worth naming before it is restored.

**(b) The three largest non-DST fades are Jefferson (2.270), Bijan (1.760) and the 49ers
DST (3.518, largest overall).** Those are **exactly** the three players your cap report
names as the Week-2 concentration that busted: *"Week 2 concentrated on Jefferson, Bijan and
the 49ers DST, who busted."*

So the fade and the cap were aiming at the same failure from opposite ends — the cap
constrains exposure after the objective has chosen, the fade changes which candidates exist
at all. The cap did not replicate out of sample. The fade has never fired. **That is a
better motivation for the A/B than "an adopted lever is at zero", and it is testable on the
same Week-1 slate you already have rebuilt.**

## Agreement

Not shipping it on argument is right, and the "two slates before it fires on a money build"
standard is the correct one — it is the cap lesson applied the same day it was learned. My
only ask is that the mechanism decision (1/2/3 above) be made explicitly and recorded,
because a silent drift in the ported weights would be indistinguishable from the lever not
working.
