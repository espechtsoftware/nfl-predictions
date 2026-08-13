# SIS team run-context feature audit

Completed 2026-08-13 against terminal active-only player panel
`20260812-pitclean-e80-selected-tabpfn-active-v2`. This is an
**exploratory/adaptive outcome audit**. It cannot alter production or license a
lineup-score comparison. Any selected treatment requires a separately frozen
walk-forward model protocol before its model output is computed.

## Point-in-time and support contract

The audit reads write-once private table
`nfl_raw.sis_team_run_context_game`, reconstructed from the exact 68 valid
original plus 22 recovery artifacts. The invalid Passing Value family is
absent. For each target week, all ratios use sums of their numerator and
denominator over the last four completed same-season team games after
`shift(1)`, with at least two prior games. This volume-weights Value metrics
and Boom%/Bust% instead of giving a two-attempt game the weight of a 30-attempt
game. Both the RB's offense and opponent must have complete support.

Tests prove target-week mutation invariance, unique team-week source keys,
offense/opponent join direction and strict earlier-week provenance. Of 3,961
active evaluation RB rows in 2023--2025, 3,458 (87.30%) are supported across
48 slates. Unsupported early-season rows remain null; there is no same-week,
cross-season, zero or league-average fallback.

## Main exploratory result

The most stable signals are opponent run-defense features, not the offense's
lagged Boom% or Bust%.

| Strict-prior feature | Residual r | Beat +10 r | Actual >=25 r | Actual >=30 r | Residual signs 2023/24/25 |
|---|---:|---:|---:|---:|---|
| Opponent Points Saved/play | -0.0486 | -0.0434 | -0.0506 | -0.0304 | - / - / - |
| Opponent EPA/attempt | +0.0497 | +0.0393 | +0.0607 | +0.0464 | + / + / + |
| Opponent yards/attempt | +0.0359 | +0.0320 | +0.0703 | +0.0427 | + / + / + |
| Opponent YAC/attempt | +0.0411 | +0.0434 | +0.0611 | +0.0550 | + / + / + |
| Opponent positive-play rate | +0.0375 | +0.0299 | +0.0520 | +0.0485 | + / + / + |
| Offense positive-play rate | +0.0462 | +0.0399 | +0.0388 | +0.0384 | + / + / + |
| Offense Boom% | +0.0250 | +0.0290 | +0.0253 | +0.0206 | + / + / - |

Opponent Points Saved/play is the cleanest single candidate: it has the
expected inverse direction for all five audited outcome views and for both
residual and beat-10 in every evaluation season. The vendor's tail-labeled
offensive Boom% is weaker and reverses for residual/30-point outcomes in 2025;
it should not be included merely because its name matches the project utility.
Offense positive-play rate is stable and more distinct, but it is a secondary
candidate rather than grounds for a larger feature bundle.

## Redundancy

SIS opponent EPA/attempt is highly redundant with existing strictly-prior
`epa_per_rush_allowed_l6` (`r=0.8029`) and should not be added. Opponent
yards/attempt is also substantially redundant (`r=0.6159`). Points Saved/play
is more distinct (`r=-0.4531` against existing EPA) and nearly independent of
SIS YAC/attempt (`r=0.0890`); SIS YAC/attempt itself is only `r=0.3651` against
existing EPA. Those facts support a maximum two-column candidate of opponent
Points Saved/play plus opponent YAC/attempt, but the smallest and most
interpretable first arm is Points Saved/play alone.

## Decision

Freeze one RB-only TabPFN treatment that appends exactly
`sis_rb_def_ps_per_play_l4` to the inherited active-only/shared-33 cache law.
Use the same control-reproduction and mechanical contracts as the SIS QB-line
arm. The score-free final-served gate should fit each arm's walk-forward
position scale independently and require aggregate active-RB Brier-30 to
strictly improve; Brier-20, CRPS, pinball, MAE, season folds and uncertainty
are diagnostics without a per-season veto. A pass licenses one separately
frozen exact-80 under the terminal weekly-maximum utility. A fail closes this
one-column arm and does not authorize adding YAC, positive rate or Boom% after
seeing the result.

The player-level defender/receiver alignment and conditional-allocation path
from the SIS usage review remains higher-mechanism-value because it targets
the known dependence deficit rather than another player marginal.

Reproduction:

```bash
source .venv/bin/activate
nfl-dfs sis-team-run-context-audit
```
