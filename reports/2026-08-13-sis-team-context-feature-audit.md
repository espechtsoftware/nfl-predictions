# SIS team-context feature audit

Completed 2026-08-13 against the terminal active-only TabPFN player panel
`20260812-pitclean-e80-selected-tabpfn-active-v2`. This is an
**exploratory/adaptive outcome audit**. It does not alter production, license
an exact-80 score comparison or permit coefficients to be chosen from these
results. Any treatment selected here needs a separately frozen protocol
before model output is computed.

## Point-in-time construction

The audit reads the private write-once table
`nfl_raw.sis_team_context_game`. For every target week, each SIS feature is a
mean over the last four completed team games, requires at least two prior
games and uses `shift(1)` before rolling. Both the player's offense and its
opponent must have prior support. Tests prove that mutating a target-week
source row cannot change that target week's attached features and that every
source week is strictly less than its target week.

The terminal panel contains 28,411 eligible QB/RB/WR/TE rows. Strict-prior SIS
context supports 24,709 rows (86.97%) across 48 slates. Weeks 1--2 of each
2023--2025 evaluation season are intentionally unsupported by the two-game
minimum rather than backfilled with target-season outcomes.

The seven audited features are opponent pass-defense EPA/play and Points
Saved/play; opponent pressure rate and pass-rush Points Saved/play; and the
offense's pass blown-block rate, run blown-block rate and aggregate blocking
Points Earned/play.

## Outcome-blind redundancy check

SIS opponent pass-defense EPA is highly redundant with the existing
strictly-prior `epa_per_dropback_allowed_l6` feature (`r=0.8803`, 3,212
team-weeks). SIS pressure rate is more distinct from existing
`opp_pressure_rate_l6` (`r=0.4573`). The broad pass-defense EPA column should
therefore not be added wholesale merely because it is proprietary.

## Exploratory tail associations

All correlations are small, as expected for lagged team context against noisy
individual DFS outcomes. The useful evidence is mechanism plus sign
repeatability, not magnitude alone.

| Position / feature | Residual r | Beat projection by 10 r | Residual signs, 2023/24/25 | Beat-10 signs, 2023/24/25 |
|---|---:|---:|---|---|
| QB offense pass blown-block rate | -0.0566 | -0.0407 | - / - / - | - / - / - |
| QB offense blocking Points Earned/play | +0.0545 | +0.0264 | + / + / + | + / + / + |
| QB opponent pressure rate | -0.0220 | -0.0151 | - / + / - | - / - / - |
| RB offense run blown-block rate | -0.0301 | -0.0235 | - / - / - | - / - / - |
| RB offense blocking Points Earned/play | +0.0413 | +0.0274 | + / + / + | + / ~0 / + |
| RB opponent pressure rate | -0.0299 | -0.0210 | - / - / - | - / - / - |
| TE opponent pass-defense EPA/play | +0.0345 | +0.0315 | + / + / + | - / + / + |
| WR opponent pass-defense EPA/play | +0.0034 | +0.0108 | + / + / + | + / + / + |

The clearest tranche-1 candidate is a compact **QB offensive-line bundle**:
lagged pass blown-block rate plus blocking Points Earned/play. Both directions
are mechanistically coherent and repeat across all three evaluation seasons.
The broad RB line signal is also repeatable, but it should wait for the
already-frozen rushing/run-defense tranche so that the RB protocol can use the
more direct context rather than selecting from this partial view.

The WR effects are too small to justify a broad defense-context arm. WR/TE
work should instead use predeclared receiver-vs-coverage/alignment splits
paired with opponent coverage deployment. That is precisely the information
the next bounded filtered-view plan should target after the request window and
broad tranches are complete.

## Next decisions

1. Freeze a small QB line-context model protocol using exactly the two
   offensive-line features above; do not tune a threshold or hand coefficient.
2. Finish and audit team Passing, Rushing and Run Defense tranche 2 before
   freezing an RB bundle.
3. Freeze a bounded coverage/receiver export design before downloading
   man/zone, shell, alignment or route splits. Do not explore an unrestricted
   Cartesian product of filters.
4. Treat this report as hypothesis generation. Only a valid score-free
   walk-forward model gate may authorize a separately frozen exact-80 test.

Reproduction command:

```bash
source .venv/bin/activate
nfl-dfs sis-team-context-audit
```
