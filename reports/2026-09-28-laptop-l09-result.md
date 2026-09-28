# PREREG-L09 result: which selector wins satellite tickets

Laptop agent, read once on 2026-09-28 (00:24 CDT). Lab branch `laptop/l09-satellite-objective-20260927` @ `b96f47e` (frozen);
the reader ran from that clean checkout, and every result line carries identity `b96f47e`, not dirty.
72 of 72 slate-banks, 0 errors: the 36 slates of 2023–24 × banks 1160 and 1161, run on the laptop.

## Reader output (verbatim)

```
slate-banks read: 72 (expected 72); seasons [2023, 2024]

K144 (sums over slate-banks; mean/best/share averaged)
        tickets89  tickets95  t89_2023  t89_2024  first5_any89    mean    best  share_above_best  sim_pf89  distinct_players
EMAX        888.0      432.0     363.0     525.0          31.0  119.13  185.63           0.01828    0.1738             133.4
MEAN       1006.0      470.0     442.0     564.0          26.0  122.01  182.83           0.02207    0.1975             117.8
PL160      1009.0      482.0     434.0     575.0          24.0  121.60  183.33           0.02484    0.1981             121.3
PL170      1014.0      490.0     443.0     571.0          26.0  121.61  183.73           0.02334    0.1974             121.9
PLF89      1025.0      490.0     449.0     576.0          26.0  121.84  183.39           0.02352    0.1986             120.1
COVF89      806.0      374.0     335.0     471.0          35.0  117.11  184.70           0.01704    0.1550             150.5

K40 (sums over slate-banks; mean/best/share averaged)
        tickets89  tickets95  t89_2023  t89_2024  first5_any89    mean    best  share_above_best  sim_pf89  distinct_players
EMAX        283.0      122.0     111.0     172.0          31.0  121.08  175.54           0.04913    0.1900             102.8
MEAN        300.0      141.0     142.0     158.0          26.0  124.22  172.71           0.05413    0.2154              76.0
PL160       305.0      146.0     134.0     171.0          24.0  123.69  173.77           0.05673    0.2160              79.0
PL170       296.0      141.0     133.0     163.0          26.0  123.29  174.08           0.05375    0.2151              79.3
PLF89       303.0      142.0     132.0     171.0          26.0  124.15  173.68           0.05636    0.2167              77.7
COVF89      255.0      119.0     102.0     153.0          35.0  118.69  176.02           0.04320    0.1688             112.8

paired slate-banks vs MEAN (K144 tickets89: wins/losses/ties):
  EMAX: (32, 30, 10)
  PL160: (31, 28, 13)
  PL170: (36, 25, 11)
  PLF89: (29, 24, 19)
  COVF89: (26, 41, 5)

DECISION (satellite objective): best challenger PLF89 1025 vs MEAN 1006 (+1.9%); seasons {2023: 449, 2024: 576} vs {2023: 442, 2024: 564}; paired 29-24
  -> MEAN STANDS for the satellite track
CHECK (MEAN vs EMAX at the satellite line): MEAN 1006 vs EMAX 888 (+13.3%); seasons {2023: 442, 2024: 564} vs {2023: 363, 2024: 525}; paired 30-32
  -> MEAN NOT CONFIRMED over EMAX at the satellite line
```

## What it means

1. **MEAN STANDS for the satellite track.** Aiming at the ticket line barely differs from ranking by mean:
   - PLF89 1,025, PL170 1,014 and PL160 1,009 tickets, against MEAN's 1,006. That is +0.3% to +1.9%, all under the
     5% bar.
   - The books overlap heavily.
   - My critique that "the objective is wrong" (`reports/2026-09-27-laptop-critique-of-the-week4-plan.md` §2) is
     **not borne out in practice.** The §1 yardstick point (count tickets at the real line, not at 149.5) still stands.
   - Coverage (COVF89) is worst on tickets (806). The operator's answer (several tickets per user in super satellites)
     already made it irrelevant.
2. **MEAN vs EMAX: +13.3% tickets in total, but NOT CONFIRMED under the frozen rule.**
   - Totals: 1,006 vs 888. Both seasons are better: 2023 442 vs 363, 2024 564 vs 525.
   - Paired slate-banks: 30 wins vs 32 losses.
   - MEAN's gain is lumpy. It uses 118 distinct players against EMAX's 133, so when its core hits, many rows cash at
     once, and when it misses, they miss together.
   - For expected tickets over a season, +13% is real evidence for the direction of the Week-4 plan. For any single
     week it is close to a coin flip.
   - The Week-3 gap (+31 points per lineup) is not the expectation. The historical per-lineup gain here is +2.9
     points (122.0 vs 119.1 at K = 144).
3. **The tail favours EMAX,** consistent with the two-track design.

   | Share of the field above the book's best (lower is better) | EMAX | MEAN |
   |---|---|---|
   | K = 144 | 0.0183 | 0.0221 |
   | K = 40 | 0.0491 | 0.0541 |

4. **Suggestion (not tested):** MEAN's lumpiness comes from concentration. A per-player exposure cap on the mean track
   could keep most of the +13% with fewer all-or-nothing Sundays. It is a candidate for a quick selection-only replay
   on the saved pools if the operator wants it.

## Next

- **Production:** please re-run the frozen reader on the same result files before the ledger row. The files are on the
  laptop at `~/.cache/laptop-agent/l09/`; the laptop can push them to a branch on request, since they contain no
  private data.
- **L10 (MAXGAME5)** started at 00:23 CT, banks 1170–1171. Its primary selector is **MEAN**, as this read designates.
  ETA about 04:30 CT.
