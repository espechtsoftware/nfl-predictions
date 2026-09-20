# D12800 marginal-tail swap bootstrap results

This is an outcome-blind uncertainty check for the five single-row swaps
chosen by the marginal-tail screen. It uses the same archived D12800 book,
the 97-row selected set, and the pooled 20,000-world incumbent/corrected-HSIM
banks. Each interval resamples worlds as paired units, so the comparison is
between the swapped maximum and the exact control maximum in the same worlds.
It is conditional on this simulated bank; it is not an independent NFL
validation and it does not authorize a selector change.

The control maximum has mean **203.4508**, with simulated probabilities of
**22.255%** at 220+, **12.120%** at 230+, and **6.280%** at 240+.

The arms and rank choices were frozen by the preceding outcome-blind screen:

| candidate | mean rank | 220+ rank | 230+ rank | 240+ rank |
|---:|---:|---:|---:|---:|
| 1334 | 8 | 80 | 72 | 41 |
| 2765 | 8 | 80 | 72 | 41 |
| 7399 | 8 | 80 | 72 | 41 |
| 5211 | 96 | 80 | 72 | 41 |
| 2396 | 97 | 80 | 72 | 41 |

The paired 95% intervals for the selected objective are:

| candidate / objective | point change | paired 95% interval |
|---|---:|---:|
| 1334 / mean | +0.0024 | −0.0153 to +0.0216 |
| 1334 / 220+ | +0.080 percentage points | −0.035 to +0.095 pp |
| 1334 / 230+ | +0.055 pp | −0.035 to +0.075 pp |
| 1334 / 240+ | +0.060 pp | −0.005 to +0.080 pp |
| 2765 / mean | +0.0031 | −0.0196 to +0.0229 |
| 2765 / 220+ | +0.075 pp | −0.045 to +0.085 pp |
| 2765 / 230+ | +0.055 pp | −0.020 to +0.090 pp |
| 2765 / 240+ | +0.050 pp | 0.000 to +0.085 pp |
| 7399 / mean | −0.0028 | −0.0215 to +0.0147 |
| 7399 / 220+ | +0.105 pp | +0.050 to +0.170 pp |
| 7399 / 230+ | +0.025 pp | −0.015 to +0.055 pp |
| 7399 / 240+ | +0.045 pp | +0.015 to +0.075 pp |
| 5211 / mean | −0.0130 | −0.0316 to +0.0047 |
| 5211 / 220+ | −0.035 pp | −0.100 to +0.020 pp |
| 5211 / 230+ | 0.000 pp | −0.060 to +0.060 pp |
| 5211 / 240+ | +0.005 pp | −0.040 to +0.050 pp |
| 2396 / mean | −0.0034 | −0.0209 to +0.0145 |
| 2396 / 220+ | +0.050 pp | 0.000 to +0.105 pp |
| 2396 / 230+ | +0.065 pp | +0.020 to +0.110 pp |
| 2396 / 240+ | +0.045 pp | +0.015 to +0.080 pp |

The same candidate can help one tail threshold while lowering the mean or a
different threshold. Candidate 7399 has the clearest simulated 220+ marginal
gain, but its mean and 230+ effects are uncertain. Candidate 2396 has a
positive 230+/240+ signal in this bank, while candidate 5211 loses simulated
mean and has wide tail uncertainty. Candidate 1334 and 2765 are small,
uncertain improvements at their screen-selected ranks.

These intervals should be used to narrow the prospective test, not to select
a row today. The arms share the same worlds and are multiple comparisons from
one screen, so their intervals are not independent evidence. The next useful
test remains the preregistered paired `dual_emax` versus
`cap_prefix_then_fill` shadow on a fresh book, with realized post-lock scores
as the primary read. If a tail-swap idea is retained, 7399/220+ is the most
focused candidate for a predeclared shadow arm, and it should be reported
alongside mean/230+/240+ tradeoffs and realized 200/210 counts.

## Provenance and guardrails

The replay is `reports/reviews/evidence/2026-09-20-d12800-tail-swap-bootstrap.py`
and its exact result is
`reports/reviews/evidence/2026-09-20-d12800-tail-swap-bootstrap-result.json`.
The result records the archive manifest and source-file SHA-256 values,
1000 bootstrap replicates, seed `20260920`, `current_outcomes_read=false`,
and `provider_calls=0`. It reads only frame identity/name/DK-id columns,
candidate rosters/names, the book and receipt, and the two selection banks.
No production build, contest entry, paid-source call, or current-week result
was changed or opened.
