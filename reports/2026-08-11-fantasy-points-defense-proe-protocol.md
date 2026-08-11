# Fantasy Points weekly Defense PROE protocol

Preregistered on 2026-08-11 CDT after a source-only redundancy/support audit
and before any Fantasy Points Defense PROE value was joined to a player
outcome, projection residual or tail label.

## Question and source

Does the opposing defense's recent tendency to induce pass rate over
expectation improve 30-point tail forecasts for pass-game players beyond the
corrected pre-lock projection and existing point-in-time controls?

Use only the four untouched licensed weekly Defense PROE exports already
hash-registered in `reports/2026-08-10-fantasy-points-data-intake.md`:

- 2022 `ea07de3d...be2b`;
- 2023 `f7ab1747...5dc6`;
- 2024 `38951d50...425c`; and
- 2025 `07940fda...435b`.

The importer must require 32 unique defenses per season, the exact 25-column
schema, declared Season, and exactly `G` populated weekly cells. It normalizes
2,174 team-game values. Target Week W may use only the mean of calendar Weeks
W-4 through W-1 for the target player's opponent. A bye is a legitimate
missing game; support requires at least three populated games. Same-week and
season-end aggregate `PROE` are forbidden.

## Outcome-blind evidence

The source-only audit joined the proposed strict-prior window to 1,646 unique
2022--2025 scheduled defense-week contexts for target Weeks 5--18. All 1,646
had at least three prior games, or 100% coverage in every season. The largest
absolute Spearman correlation with any existing opponent input was 0.2955
(`wr_fp_allowed_adj_l6`). Other correlations were 0.2817 with adjusted QB
fantasy points allowed, 0.1283 with EPA/dropback allowed, -0.1840 with
pressure rate, and no more than 0.2065 for the remaining allowed/blitz/rush
features. No outcome column was queried or available to this audit.

This licenses one compact diagnostic. It does not establish predictive value.

## Frozen population and treatment

Use research-eligible QB, WR and TE rows from corrected accepted panel
`20260810-lockfix-e80-k1-8677d21`, target Weeks 5--18 and seasons 2022--2025.
The pass-game population is fixed by the feature's football meaning before
outcomes; RB is excluded rather than adding an outcome-sensitive sign or
position interaction.

Treatment adds exactly one coefficient-free numeric feature:

`fp_def_proe_l4 = mean(opponent Defense PROE in Weeks W-4..W-1) / 100`.

No last-game value, trend, season aggregate, offense PROE, threshold, rank,
interaction, position subset, shrinkage alternative or field sweep is
licensed.

## Frozen walk-forward evaluation

Use held-out seasons 2023, 2024 and 2025:

- 2023 trains on target-season 2022;
- 2024 trains on 2022--2023; and
- 2025 trains on 2022--2024.

Reuse the completed receiver/QB diagnostics' fixed control inputs,
imputation, standardization and models: residual `Ridge(alpha=10.0)` plus
20/30-point `LogisticRegression(C=0.1, solver="lbfgs", max_iter=2000)` over
`mean_projection`, salary, target/snap last and jump, team vacated target
share, depth rank, games played prior and position one-hot encoding.

Report support coverage, fold and aggregate 20/30-point Brier, residual MAE,
calibration deciles, event counts, per-position diagnostics and descriptive
feature correlations. Correlations and per-position results cannot select a
new population or interaction.

## Frozen gate and consequence

The mechanism passes only if:

1. supported coverage is at least 90% in every held-out fold; and
2. aggregate 30-point Brier loss is strictly lower for treatment.

Fold/position 30-point Brier, aggregate 20-point Brier and residual MAE are
mandatory diagnostics but not vetoes under the operator's current tail-first
objective. A pass licenses one separately preregistered candidate-union test;
it does not directly change production. A valid failure closes this exact
mechanism. No feature/window/support/model/population/gate retry is licensed
on its outcomes.

## Pre-outcome status

The hash-locked importer, strict-prior attachment and source-only redundancy
audit are implemented; seven focused Defense PROE/backup tests pass, with
compilation, CLI discovery and whitespace checks clean. The raw table has not
been written. The outcome diagnostic, cloud runner, outcome query and lineup
generation have not started.
