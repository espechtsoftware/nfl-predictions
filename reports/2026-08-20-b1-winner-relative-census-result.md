# B1 Generated-Union Winner-Relative Census Result

**Date:** 2026-08-20  
**Protocol:** `20260820-b1-winner-relative-census-v1`  
**Disposition:** descriptive complete; no rule, model, selector, or production
license

## Frozen population

The one-shot census reproduced the complete frozen B1 population:

- 51 registered source panels;
- 698,172 source candidate rows;
- 54 slates;
- 127,778 distinct DK-legal rosters that were actually generated;
- zero legality drops;
- zero stored candidate-score versus canonical player-snapshot mismatches; and
- 51 slates with a tracked 2023--2025 Millionaire-Maker winner.

It contains no H/P hindsight construction and no simulated-world optimum.
Protocol SHA-256 is
`bb5851e38ae6a2934fc791997916ce6d1f7be46187d1263682ff15b70725ff03`.
The canonical result SHA-256 is
`23e05731a9509b6b53ef0be6300d9a15b99e47a29333066e241ba3f0d318f823`.

## Direct answer

No actually generated B1-union roster beat or tied its same-week Milly
winner:

- beat: `0/51`;
- tie: `0/51`;
- within 10 points: `1/51`;
- within 25 points: `8/51`; and
- more than 25 points behind: `43/51`.

The mean union-best minus winner margin was `-34.71`; the median was `-34.02`.
The closest week was 2023 Week 2: `187.28` versus `193.94`, a `-6.66` gap.

The actual union-best lineups were nevertheless materially stronger than the
standing money book. Across the 51 matched slates their mean was `198.74`,
median `197.30`, and threshold counts were:

| Actual union-best threshold | Slates |
|---:|---:|
| >=187 | 41 |
| >=194 | 31 |
| >=200 | 24 |
| >=210 | 15 |
| >=220 | 6 |
| >=230 | 2 |
| >=240 | 1 |

The maximum was `240.44` in 2023 Week 3, but that week's winner scored
`296.38`. This illustrates why winner-relative distance and absolute lineup
quality are different endpoints.

## Interpretation

The system can generate genuinely strong tournament lineups, but the complete
valid union is not yet winner-competitive on the same-week maximum endpoint.
The result also shows why winner imitation should not be the primary modeling
target: the corpus supplies 24 weeks at 200+ and 15 at 210+, which is enough to
study its own tail construction, while a single winner per slate is an extreme
and selection-biased label.

The appropriate next modeling target is the probability that a generated
lineup clears a preregistered absolute or field-relative tail endpoint using
only pre-lock inputs. Candidate structure, simulated tail summaries, source
support, role/allocation data, ownership and later full-field duplication may
be evaluated with season-held-out or prospective validation. Winner identity
remains a diagnostic ceiling, never a training target or a source of fitted
construction quotas.

This census is descriptive and heavily outcome-viewed. It cannot license a
historical selector, candidate quota, rule relaxation, or production change.

