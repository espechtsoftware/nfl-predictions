# Injury type adds no useful target-mean gain in this fixed screen

The frozen injury-type study does **not** nominate a follow-up model or a live
change. Among active Questionable receivers with prior playing-time support,
adding the21 injury-type flags slightly worsens mean Poisson deviance:
**+0.000560**, with a paired slate-bootstrap95% interval
**[-0.000897,+0.002061]**. Lower is better. The interval does not establish
improvement, and the primary point estimate is adverse.

| Frozen metric | Control | Injury-type treatment | Treatment−control |
|---|---:|---:|---:|
| Questionable, slate/year-balanced deviance | 1.968751 | 1.969311 | +0.000560 |
| All active eligible, slate/year-balanced deviance | 1.656040 | 1.655948 | −0.000092 |

The frozen gate required primary upper95% bound<0 and no all-active degradation.
The primary requirement fails. The tiny secondary improvement does not rescue it.
This closes this particular21-flag, fixed-capacity Poisson model screen with its
existing information set and training budget. It does not establish that injury
information, daily trajectories, severity, availability or another opportunity
model is generally useless. Those would be separately specified questions.

## Support and whether the treatment actually changed forecasts

| Season | Active scored | Questionable | Questionable slates | Primary delta | Active forecasts changed |
|---|---:|---:|---:|---:|---:|
| 2019 | 2,944 | 126 | 16 | +0.001418 | 2,944 |
| 2021 | 3,150 | 199 | 17 | 0 | 0 |
| 2022 | 2,915 | 180 | 17 | 0 | 0 |
| 2023 | 2,990 | 161 | 17 | +0.000924 | 2,990 |
| 2024 | 3,024 | 130 | 17 | +0.000458 | 3,024 |

There are15,023 scored active player-weeks and796 Questionable observations.
Every year exceeds the frozen30-Questionable/two-slate support minimum; missing
activity and active missing-target counts are zero. Predictions cover all16,357
eligible target-year rows before availability labels are read. The study then
scores conditional on playing. Historical activity coverage differs by year;
this is not a clean prospective availability model or a causal injury estimate.

The treatment is **exactly prediction-identical in2021 and2022**. Peer `272bbb8` independently verifies this on every predicted row, including unscored rows (3,155/3,387). The pattern is not monotone in training size: the smaller2019window already produces changed predictions. A claim about which tree splits were chosen would require a separate estimator audit. In the other
three years it changes predictions but slightly worsens the primary score.
Maximum absolute target-mean shifts are0.209,0.122 and0.094 respectively. The
vacuous folds must not be sold as evidence against the whole injury family;
they show this fixed learner made no use of the extra representation there.
There will be no post-read category/capacity search on this same study.

This is a target-count information screen, not a complete distribution test,
lineup generation/selection test, paid-source renewal verdict or proof about220+
lineups. Reused historical labels were disclosed before execution. The bootstrap
conditions on the fitted models; it does not include retraining uncertainty.

## Execution and reproducibility

[Protocol](2026-09-19-injury-type-opportunity-protocol.md) retains the original
freeze, two disclosed mechanical corrections and failed build IDs. An all-missing
QB feature is removed using training covariates only; the corrected first-boundary
cloud smoke and five-year forecast build passed. The separate cloud reader
completed evaluation but failed JSON serialization on NumPy integer year keys.
The local authenticated adapter reran the **unchanged reader** on those same
forecasts, converting NumPy scalar keys/values only for serialization. It neither
retrained nor changed a gate after outcomes.

- Forecast build: `32334063-4581-4aa1-b428-b771f3332072`.
- Study/reader SHA256: `6914d7f3a4b6f0d06defa128cc20380d165b88004fde1f5ea8aa641e96d32274`.
- Forecast publication generation: `1789797085467118`.
- Result JSON SHA256: `718b1467b186869980032f3d2b8e43dc87f253bc7d2bd5492541dcd90ca70003`.
- Scored rows SHA256: `075cbf8f58042e37b470a49bb10b624a2a9bcae3a5a6731263efd09747790bf7`.
- Create-once cloud prefix: `gs://nfl-2-506823-lab/research/injury-type-opportunity-20260919/v2/`.

[Verbatim result](reviews/evidence/2026-09-19-injury-type-score-result.json),
[publication identities](reviews/evidence/2026-09-19-injury-type-publication.json),
[support/vacuity detail](reviews/evidence/2026-09-19-injury-type-support-and-vacuity.json),
[authenticated reader adapter](reviews/evidence/2026-09-19-injury-type-authenticated-read.py).
Independent full frozen-reader cross-read is requested before a ledger entry.
