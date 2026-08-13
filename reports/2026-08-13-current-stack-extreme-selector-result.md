# Current-stack extreme-selector replication result

Status: terminal rejection. Keep the 194-coverage selector and close the
220->210->200 selector on the terminal active-label stack.

## Execution and validity

Cloud Run execution `current-extreme-selector-replication-95mnt` completed
successfully from immutable digest
`sha256:0d766c187f493c240cd6a5524c53b1a1236b4a32e30caa3843ad5c8d2b6080b5`.
It used exactly current terminal panel
`20260812-pitclean-e80-selected-tabpfn-active-v2` from
`replay_candidates`.

All 54 2023--2025 slates were complete, the persisted 194 selector reproduced
exactly, both books contained exactly 80 unique final lineups, support masks
were valid and nested, and the candidate pool was unchanged. The extreme
selector changed 1,660 slots in each direction.

## Score result

| Selector | >=240 | >=230 | >=220 | >=210 | >=200 | >=194 | >=187 | Mean weekly max |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Persisted 194 coverage | 0 | 0 | 0 | **2** | **6** | **8** | **11** | 170.9070 |
| Frozen 220->210->200 | 0 | 0 | 0 | 1 | 5 | 6 | 9 | 170.9893 |

The books tie at 240, 230 and 220. The first registered difference is at 210,
where the extreme selector loses one week. It also loses one 200-point week,
two 194-point weeks and two 187-point weeks. Paired weekly maxima were 11
wins, 30 ties and 13 losses; the largest gain was `+17.60` and the largest
loss `-21.08`.

## Decision

Retain the 194-coverage selector. The terminal current-stack replication
agrees with the older 107-slate rejection at the first active threshold, so
no selector retune or further historical threshold variant is licensed. The
seed/mask-stability work remains useful for quantifying simulation uncertainty
and future higher-world shadows, but it cannot rescue this rejected realized-
score result.
