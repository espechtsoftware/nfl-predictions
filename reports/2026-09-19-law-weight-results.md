# Historical model-blend learning does not pass

The frozen earlier-season learning rule makes predictive accuracy worse than the
existing equal blend. **Do not advance it to lineup selection or change the live
blend.** This is a completed development screen. Peer `2abe922` completes the
full frozen forecast-to-score rerun: every common report value and bootstrap
bound agrees exactly, and all 24,272 × 55 score-row values match. This supersedes
the earlier score-row arithmetic check. No live change is made.

## Primary result

Lower CRPS is better. Evaluation covers 72 slates in 2021–2024, with 2019 used
only to initialize training. Each year's weight is learned exclusively from
earlier study years. The two simulation banks measure algorithm variability,
not separate football histories.

| Forecast | Balanced skill-player CRPS |
|---|---:|
| Incumbent alone | 4.144919 |
| Hierarchical simulator alone | 4.192887 |
| Existing 50/50 blend | **4.093643** |
| Learned blend | 4.109877 |

Learned minus equal is **+0.016234**, with conditional 95% paired-slate interval
**[+0.004852, +0.027395]**: worse by about 0.40%. Both banks are worse
(+0.015306 and +0.017162). Only one of four evaluation years improves:

| Evaluation year | Learned incumbent weight | CRPS difference |
|---|---:|---:|
| 2021 | 91.14% | +0.003365 |
| 2022 | 84.56% | +0.073867 |
| 2023 | 67.86% | −0.014774 |
| 2024 | 69.17% | +0.002479 |

The frozen rule required improvement in both banks, at least three years, and an
upper interval bound below zero. It fails all three conditions. No alternative
weighting-rule search will be conducted on these outcomes under this protocol.

## Interpretation and limits

The blend benefits from retaining both models even though one has the better
standalone average score. Earlier seasons favoring the incumbent do not justify
giving it that much influence in later seasons. This supports retaining the
existing equal blend against this particular proposed replacement; it does not
prove 50/50 is optimal or establish any 220+ lineup effect.

The prespecified position summaries show deterioration for QB and TE, improvement
for RB and a very small improvement for WR. DST is secondary, excluded from the
weight fit, and also deteriorates. These descriptions are not permission to fit
position-specific weights or splice model states. The four skill positions have
equal weight within each slate; slates and years are also balanced as frozen.

There are 15,093 eligible player/slate observations across construction/training
and evaluation, 12,136 in evaluation; the output repeats each for two banks.
There are **no missing actuals** among eligible or full-frame observations. The
interval treats learned weights as fixed, so it does not include training-weight
uncertainty. These are repeatedly studied development years, not fresh holdout
confirmation. Neither 2025 nor bank991 was opened. No candidate or selected-lineup
outcome was evaluated by this study.

## Reproducible evidence

- [Frozen protocol](2026-09-19-law-weight-protocol.md), production source
  `645ff1ef124890db439af5c655905d02a130f6b7`.
- [Unchanged reader](reviews/evidence/2026-09-19-law-weight-read.py), SHA256
  `2f9f41b1c5bc30e4930f1cdd5981a3df5d30384928e44fb81fd9f6a5d6eb0cd5`.
- [Verbatim result](reviews/evidence/2026-09-19-law-weight-results.json), SHA256
  `7234cb9737ce3cb89a9873c07283dcc600a5c95c5e85b0904a74601e0acc58d4`.
- [Published result identities](reviews/evidence/2026-09-19-law-weight-results-publication.json).
  Full rows are generation `1789793418768380`, SHA256
  `b7404ff1f911edf9db831bce956d7d4677ce623d8c7a3d6c7442acb199056221`, at
  `gs://nfl-2-506823-lab/research/law-weight-20260919/read-v1/score-rows.parquet`.

Forecast Cloud Build `2eb37a28-4779-4ec2-97a7-4d3c918f5390` succeeded at
04:43:16 UTC, constructing 446 artifacts in 882.916 seconds. The separate reader
build `9889814c-81d1-4030-a75b-90fe88d4ac6a` succeeded at 04:50:20 UTC;
its download, validation and evaluation took 73.998 seconds. All forecast files
were generation/size/hash validated before opening actuals. Both result objects
were independently downloaded and checked against their publication receipt.

An initial reader submission failed before build creation because of an argument
length limit. Transport-only correction `21db29de` split the same authenticated
payload into smaller arguments; no analysis source changed. The valid recipe
SHA256 is `4bfa9167f1b2916e9b2949e17600f1b725aee3b83034d16cd403bff313570993`.

## Follow-up disposition

The separately prepared [candidate support census](reviews/evidence/2026-09-19-law-weight-candidate-support.json)
finds 21,420 distinct legal rosters over 89 slates, with every player mapped and
all salary sums matching. It reads only identities and prelock roster fields.
This is the older K1 panel, not the adopted D800 pool. Since the predictive-quality
gate fails, its prepared support will **not** be used to launch the conditional
lineup-transfer experiment. The next research direction should address new
information or coherent opportunity states, consistent with the existing agenda,
rather than search more blend weights on this result.
