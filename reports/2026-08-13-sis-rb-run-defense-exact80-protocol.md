# SIS RB run-defense conditional exact-80 protocol

Status: frozen 2026-08-13 before the score-free final-served result and before
either candidate book or any lineup score is read. This protocol is dormant
unless `tabpfn-sis-rb-rdef-final-served-v1-lmb74` passes every frozen gate.

## Conditional license

If the score-free report disposition is not
`tabpfn-sis-rb-rdef-final-served-passes`, or its aggregate active-RB 30-point
Brier and mean-preservation gates do not both pass, stop. Do not generate a
candidate or read a lineup score. A pass licenses exactly the paired comparison
below; it does not itself select or deploy the SIS feature.

## Paired books

- Historical source for 2019/2021/2022: the exact active-label selection's
  bound `historical_source`, unchanged and promoted.
- Control evaluation panel:
  `20260813-pitclean-e80-selected-tabpfn-sis-rb-rdef-control-v1`.
- Treatment evaluation panel:
  `20260813-pitclean-e80-selected-tabpfn-sis-rb-rdef-treatment-v1`.
- Evaluation seasons: 2023, 2024 and 2025.
- Each arm must persist exactly 80 distinct legal selected lineups per slate.

Both books inherit the accepted K1/direct-role construction, active-only label
law, shared-33 feature law, finite Dirichlet
`K=28.154043586960896`, candidate budget, seeds, possession simulator, fitted
widening, 45/55 model/prop-market blend and optimizer. Each arm uses its own
unrounded 2023--2025 walk-forward position-factor schedule from the sole
score-free report.

The only distributional input difference is:

- control `TABPFN_MARGINAL_TABLE=tabpfn_sis_rb_rdef_control_v1`;
- treatment `TABPFN_MARGINAL_TABLE=tabpfn_sis_rb_rdef_treatment_v1`.

The treatment cache itself differs only by the frozen RB-only
`sis_rb_def_ps_per_play_l4` feature. The comparator must prove identical player
keys, actuals, invariant point-in-time inputs, seeds, common levers, terminal
laws and complete selected-book structure. Candidate membership/means and
selected books must change. Only registered distribution-derived prediction
fields may differ.

## Decision

Compare the complete 107-slate selected weekly maxima in lexicographic order:

`240, 230, 220, 210, 200, 194, 187`.

The first nonzero treatment-minus-control threshold count decides. If every
count ties, mean weekly maximum decides; an exact tie retains control. Season
signs, average lineup score, median, pool oracle and winner-position
contributions are diagnostics, not vetoes. If treatment wins, record it as the
selected historical research baseline and queue live/UI integration; do not
silently mutate production in the comparator.

