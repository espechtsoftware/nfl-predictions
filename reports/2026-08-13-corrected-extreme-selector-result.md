# Corrected-history extreme-selector result

Status: terminal rejection under the preregistered tail-first rule.

## Execution and mechanical validity

Cloud Run execution `corrected-extreme-selector-cjqq6` completed successfully
against the exact preregistered source panel
`20260810-lockfix-e80-k1-role12union-8677d21` in `replay_candidates`, using
immutable image
`sha256:370695d6f576b6d71d770b4a0f9fa6745376167600188a481db51e9eedc34fce`.

All 107 slates were complete, both selectors returned exactly 80 unique
lineups, the persisted 194-coverage control was reproduced, the 187/194/200/
210/220 support masks were nested and valid, and the candidate pool was
identical. The selector changed 2,208 slots in each direction across the
107 books.

## Score result

| Selector | >=240 | >=230 | >=220 | >=210 | >=200 | >=194 | >=187 | Mean weekly max |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Persisted 194 coverage | 2 | 3 | 5 | **7** | 11 | 22 | 34 | **180.1207** |
| Frozen 220->210->200 | 2 | 3 | 5 | 6 | **12** | 22 | 34 | 179.6650 |

The selectors tie at 240, 230 and 220. The first registered difference is at
210, where the extreme selector loses one week. Its additional 200-point week
therefore cannot promote it under the operator's fixed high-to-low objective.
Paired weekly maxima were 10 wins, 76 ties and 21 losses, with largest gain
`+13.94` and largest loss `-24.52`.

## Decision

Keep the persisted 194-coverage selector. Close this exact historical
220->210->200 mechanism without changing thresholds, weights or tie rules.
This result is consistent with the later outcome-free support audit: 210/220
masks are exceptionally sparse at 10,000 worlds and should not be treated as
stable direct selection targets without a separately frozen robustness
mechanism.
