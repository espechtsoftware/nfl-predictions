# Incumbent Monte Carlo seed-variance result

Date: 2026-08-13

Protocol: `reports/2026-08-13-incumbent-seed-variance-protocol.md`

Successful repaired analyzer execution:
`analyze-incumbent-seed-variance-v1-qh9l8`

Original mechanically failed analyzer execution retained for audit:
`analyze-incumbent-seed-variance-v1-kkg6q`

## Decision

The incumbent is **materially Monte Carlo-sensitive** under the frozen
definition. The repair changed only nullable-boolean equality in the final
analyzer; all twelve expensive replay executions were reused and all
mechanical identity gates passed.

Across R0--R4 on the same 54 evaluation slates:

| threshold | selected min--max | oracle min--max |
|---|---:|---:|
| >=210 | 0--2 | 0--3 |
| >=200 | 1--6 | 2--7 |
| >=194 | 3--9 | 6--11 |
| >=187 | 6--13 | 10--16 |

No replica selected a lineup at or above 220. Per-slate selected-best
max-minus-min was 22.31 points on average, 20.86 at the median and 46.06 at
the maximum; 45/54 weeks exceeded a ten-point seed range. Pairwise selected
portfolio overlap averaged only 12.21 of 80 rosters.

R0's 8 selected >=194 weeks is therefore one draw from a broad 3--9 range,
not a stable baseline count. Future mechanisms must use paired multi-seed
evidence or demonstrate an effect larger than this incumbent envelope. The
result also motivates a separately frozen multi-seed candidate/world union,
because production can exploit multiple independent searches instead of
arbitrarily trusting seed zero.
