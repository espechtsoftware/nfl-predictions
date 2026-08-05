# LSE arm diagnostics — follow-up package for review #4, finding 1 (2026-08-05)

Context: your F1 proposed replacing binary greedy max-coverage with a
log-sum-exp selection objective, predicting mean best-of-40 would rise
from 179.7 and/or best-entry overlap with the hindsight optimal would
clear the 2.51 random null. We implemented it exactly as specified
(greedy on sum_w log sum_{i in S} exp(alpha*(score_iw - bar)), alpha =
0.08 per DK point, still submodular) and ran the full six-season
panel. Result: **tails 25/107 (exact tie with control), mean best
179.3 vs 179.7 — your falsification condition triggered.** Per-season
tails {2019:6, 2021:2, 2022:3, 2023:4, 2024:5, 2025:5} vs control
{5,1,3,4,7,5}. The lever verifiably fired: means, medians, and season
profiles all moved. One striking invariant: the WEEKLY MAX lineup was
identical to control in every season — the best entry survives every
selector, more evidence selection is not the binding stage.

Also relevant since the package: the alternate architecture
(per-world-argmax + empirical field bar) measured EXACT parity
25/107 once an env bug was fixed. And your F7 co-ownership claim was
tested on the 74-contest archive: median joint/product inflation of
top-20 pairs is 0.87 (mild REPULSION from cap substitution), max
chalk-pair inflation 1.7x (RB + own DST) — independence is mildly
conservative there, not blind (showdown-format caveat noted).

Below are the complete per-season diagnostic blocks from the LSE runs
(the control's equivalents match its sealed baseline; its 2025
assembly battery: capture 67.5%, pool-hit 77.8%, best-entry overlap
2.00 vs random-null 2.38, optimal pairs co-rostered 25.8%, optimal QB
in best entry 4/18). The LSE assembly battery is queued and will
follow.

Questions:
1. Given LSE's null AND the identical-weekly-max invariant, do you
   accept the generator-bounded conclusion, or is there a selection
   variant that could still matter (e.g. different alpha regimes —
   0.08 too soft/too sharp)?
2. The entries-to-line tables below show median N(194) ~ 1.7k-2.6k and
   N(237) in the millions on most weeks. Does anything in these
   distributions suggest a construction change, or do they confirm
   the EVT ceiling?
3. "best scorer's selection rank: median 22, rank-1 hit 0/18" — the
   selector cannot identify its own winner ex-ante. Is there ANY
   signal you'd mine from these diagnostics that we haven't?

## LSE season 2019 — full diagnostic block
```
  entry selection: P(best >= 194) greedy coverage over correlated draws
=== Contest replay: 2019 (field 15% optimizer-built) ===
contest=gpp  entries=680
  2019: ROI +115462.5%
  TOTAL: ROI +115462.5%
  median finish percentile: 12.3% (lower is better)
  tail: mean best 187.8  max 250.4  weeks best>=237 (avg 2025 milly line): 1/17  >=194 (min line): 6/17
  playable weeks (<=16): mean best 189.0  >=194: 6/16  >=187 (20k-qualifier line): 6/16
  vs REAL winning lines (17 wks known): beat 0/17  mean gap 67 pts  within 20: 0
  salary left on table: mean 339  median 300  p90 800  share >$1k: 0%
  entries-to-line (N for 50% chance best-of-N >= line); top3 = the week's three best entry scores:
    week     mu    sd                 top3  brk N@194 N@237
       1  123.1  29.0    170.8,168.6,163.3   13      96   16310
       2  120.6  19.8    169.0,162.2,153.4    2    6569 331699452
       3  142.7  22.1    195.4,188.7,188.6    5      67   67523
       4  136.1  28.0    202.9,192.4,190.7   37      35    4330
       5  157.5  33.3    250.4,229.0,208.3   30       5      81
       6  141.0  21.9    199.5,174.9,174.7   14      88  113471
       7  125.0  28.9    186.3,180.1,175.2   35      82   13412
       8  148.6  22.1    209.8,186.8,181.5   21      34   21114
       9  116.9  22.9    162.9,160.2,155.3   29    1839 9054348
      10  134.4  24.4    179.5,175.8,172.4   14      95   52875
      11  122.2  21.6    170.8,157.1,156.4   20    1612 13953831
      12  117.4  29.7    183.0,182.0,169.5   15     141   25063
      13  113.4  24.8    165.3,157.1,152.9   26    1170 2103441
      14  120.9  29.1    182.6,172.0,170.9    4     114   20336
      15  143.5  24.1    184.9,179.1,176.3   21      38   13067
      16  125.8  33.5    211.5,182.5,180.4   31      33    1508
      17  128.0  22.3    167.3,166.0,165.3    4     456 1414528
    best scorer's selection rank: median 20  rank-1 hit 0/17 weeks  in top-5 4/17  in top-10 4/17
    line 194: median N 95  weeks reachable within a 150k-entry field: 17/17
    line 237: median N 25,063  weeks reachable within a 150k-entry field: 12/17
  app-confidence ordering, best scorer's rank: median 24  rank-1 hit 0/17  in top-5 1/17  in top-10 2/17
  entry anatomy (what wins within our own 40):
    weekly best by generator: lev:1/17 (pool 8%)  boom:14/17 (pool 75%)  game:0/17 (pool 3%)  nostk:0/17 (pool 0%)  midqb:0/17 (pool 0%)  dark:1/17 (pool 5%)
    weekly best: score 187.8  max-from-game 4.47  QB stack 2.06  punt pts  18.9  chalk 0.49  salary 49865
     top-8/week: score 166.9  max-from-game 4.51  QB stack 2.04  punt pts  16.9  chalk 0.50  salary 49723
           rest: score 121.3  max-from-game 4.43  QB stack 2.03  punt pts  12.8  chalk 0.53  salary 49645
  capture rates across our 40 (per week):
    slate-best PUNT held: 7/17 weeks  (distinct punts held avg 34.5, miss gap avg 4.1 pts)
    slate-best QB held:   15/17 weeks  (distinct QBs held avg 17.9, miss gap avg 0.3 pts)
  duplication risk (est copies in a 150k field, naive ownership): median 0.000  p90 0.00  max 0.0  entries with >=1 est copy: 0/680

```

## LSE season 2021 — full diagnostic block
```
  entry selection: P(best >= 194) greedy coverage over correlated draws
=== Contest replay: 2021 (field 15% optimizer-built) ===
contest=gpp  entries=720
  2021: ROI +39644.3%
  TOTAL: ROI +39644.3%
  median finish percentile: 13.8% (lower is better)
  tail: mean best 177.8  max 218.1  weeks best>=237 (avg 2025 milly line): 0/18  >=194 (min line): 2/18
  playable weeks (<=16): mean best 176.8  >=194: 1/16  >=187 (20k-qualifier line): 6/16
  salary left on table: mean 270  median 200  p90 700  share >$1k: 0%
  entries-to-line (N for 50% chance best-of-N >= line); top3 = the week's three best entry scores:
    week     mu    sd                 top3  brk N@194 N@237
       1  125.0  23.0    187.8,166.8,158.4   21     508 1204583
       2  115.7  24.4    180.8,162.0,161.1    6    1041 2079277
       3  127.7  24.2    181.0,180.5,172.8   40     228  226783
       4  128.3  27.0    191.9,186.3,171.1    1      92   24579
       5  129.4  26.7    178.7,172.0,167.2   27      88   24167
       6  130.6  24.0    190.6,175.2,170.9   16     167  147208
       7  131.2  22.5    179.9,178.5,169.7   39     260  520657
       8  106.6  21.9    166.8,149.8,146.1   10   21542 556784100
       9  110.9  17.2    140.0,138.4,138.1   35  979097 5495875676202
      10  112.4  14.7    155.5,138.3,133.4   12 43946316     inf
      11  138.2  28.0    203.3,179.9,179.5   26      30    3318
      12  124.0  27.0    189.7,173.9,170.5   25     146   49034
      13  130.8  21.0    177.0,171.3,170.8    8     538 3385673
      14  143.5  23.1    187.5,174.9,172.7    1      48   26440
      15   98.4  22.2    143.3,131.4,130.6   37   85416 3382821340
      16  115.9  21.1    175.5,167.8,148.8    8    6251 135031312
      17  122.0  33.5    218.1,178.9,178.3    8      44    2367
      18  113.7  20.1    153.4,146.7,139.6    1   21137 1572199625
    best scorer's selection rank: median 14  rank-1 hit 3/18 weeks  in top-5 3/18  in top-10 8/18
    line 194: median N 508  weeks reachable within a 150k-entry field: 16/18
    line 237: median N 1,204,583  weeks reachable within a 150k-entry field: 7/18
  app-confidence ordering, best scorer's rank: median 15  rank-1 hit 0/18  in top-5 4/18  in top-10 7/18
  entry anatomy (what wins within our own 40):
    weekly best by generator: lev:3/18 (pool 9%)  boom:10/18 (pool 70%)  game:0/18 (pool 6%)  nostk:0/18 (pool 0%)  midqb:0/18 (pool 0%)  dark:3/18 (pool 9%)
    weekly best: score 177.8  max-from-game 4.39  QB stack 2.00  punt pts  18.4  chalk 0.42  salary 49750
     top-8/week: score 155.4  max-from-game 4.45  QB stack 2.03  punt pts  15.5  chalk 0.40  salary 49728
           rest: score 114.2  max-from-game 4.53  QB stack 2.04  punt pts  11.9  chalk 0.41  salary 49731
  capture rates across our 40 (per week):
    slate-best PUNT held: 6/18 weeks  (distinct punts held avg 33.3, miss gap avg 6.4 pts)
    slate-best QB held:   17/18 weeks  (distinct QBs held avg 17.9, miss gap avg 6.3 pts)
  duplication risk (est copies in a 150k field, naive ownership): median 0.000  p90 0.00  max 0.0  entries with >=1 est copy: 0/720

```

## LSE season 2022 — full diagnostic block
```
  entry selection: P(best >= 194) greedy coverage over correlated draws
=== Contest replay: 2022 (field 15% optimizer-built) ===
contest=gpp  entries=720
  2022: ROI +34215.4%
  TOTAL: ROI +34215.4%
  median finish percentile: 15.0% (lower is better)
  tail: mean best 175.1  max 205.3  weeks best>=237 (avg 2025 milly line): 0/18  >=194 (min line): 3/18
  playable weeks (<=16): mean best 176.4  >=194: 3/16  >=187 (20k-qualifier line): 6/16
  salary left on table: mean 200  median 100  p90 600  share >$1k: 0%
  entries-to-line (N for 50% chance best-of-N >= line); top3 = the week's three best entry scores:
    week     mu    sd                 top3  brk N@194 N@237
       1  124.3  23.8    181.0,172.5,164.1    8     411  652544
       2  122.1  25.9    198.9,186.6,167.2   16     254  154389
       3  112.8  20.0    160.1,151.1,146.8   18   28269 2619906072
       4  123.0  29.4    200.0,186.3,168.3   27      87   12952
       5  130.8  27.2    180.4,177.5,169.9   27      68   14255
       6  112.7  18.5    158.4,153.3,145.2   30  118794 67735481145
       7  114.3  29.2    189.3,165.2,162.5   39     219   52908
       8  127.4  27.0    188.1,185.8,169.7   33     103   29116
       9  112.5  23.8    160.0,159.3,155.0    2    2297 8588351
      10  122.1  20.1    156.1,155.2,155.0   38    4011 129499540
      11  107.9  23.1    156.8,155.3,145.4    7    6902 56187996
      12  136.8  28.4    188.1,179.5,178.6    6      31    3356
      13  123.7  21.0    156.1,154.8,154.7    4    1689 19976503
      14  121.6  28.8    205.3,184.9,166.8   26     117   23189
      15  121.2  26.3    180.9,167.2,162.0   11     247  131761
      16  112.7  20.9    163.4,158.1,146.7    9   13330 471359414
      17  107.5  29.1    175.4,163.4,151.9   30     469  161529
      18   96.3  20.5    153.3,128.2,127.0   19  704263 188386432762
    best scorer's selection rank: median 18  rank-1 hit 0/18 weeks  in top-5 2/18  in top-10 6/18
    line 194: median N 469  weeks reachable within a 150k-entry field: 17/18
    line 237: median N 652,544  weeks reachable within a 150k-entry field: 7/18
  app-confidence ordering, best scorer's rank: median 14  rank-1 hit 1/18  in top-5 4/18  in top-10 6/18
  entry anatomy (what wins within our own 40):
    weekly best by generator: lev:5/18 (pool 10%)  boom:9/18 (pool 62%)  game:1/18 (pool 11%)  nostk:0/18 (pool 0%)  midqb:0/18 (pool 0%)  dark:3/18 (pool 8%)
    weekly best: score 175.1  max-from-game 4.50  QB stack 2.06  punt pts  16.6  chalk 0.29  salary 49844
     top-8/week: score 153.7  max-from-game 4.52  QB stack 2.05  punt pts  13.8  chalk 0.32  salary 49810
           rest: score 109.5  max-from-game 4.54  QB stack 2.02  punt pts  11.4  chalk 0.33  salary 49797
  capture rates across our 40 (per week):
    slate-best PUNT held: 9/18 weeks  (distinct punts held avg 35.2, miss gap avg 6.9 pts)
    slate-best QB held:   16/18 weeks  (distinct QBs held avg 17.5, miss gap avg 1.5 pts)
  duplication risk (est copies in a 150k field, naive ownership): median 0.000  p90 0.00  max 0.0  entries with >=1 est copy: 0/720

```

## LSE season 2023 — full diagnostic block
```
  entry selection: P(best >= 194) greedy coverage over correlated draws
=== Contest replay: 2023 (field 15% optimizer-built) ===
contest=gpp  entries=720
  2023: ROI +50953.3%
  TOTAL: ROI +50953.3%
  median finish percentile: 13.4% (lower is better)
  tail: mean best 176.4  max 199.9  weeks best>=237 (avg 2025 milly line): 0/18  >=194 (min line): 4/18
  playable weeks (<=16): mean best 176.8  >=194: 4/16  >=187 (20k-qualifier line): 4/16
  vs REAL winning lines (17 wks known): beat 0/17  mean gap 60 pts  within 20: 1
  salary left on table: mean 256  median 200  p90 700  share >$1k: 0%
  entries-to-line (N for 50% chance best-of-N >= line); top3 = the week's three best entry scores:
    week     mu    sd                 top3  brk N@194 N@237
       1  122.7  30.7    174.2,172.4,170.6   39      68    6881
       2  128.9  22.0    178.1,177.7,163.4   34     455 1600179
       3  134.9  25.8    198.8,184.5,176.6    4      63   18875
       4  130.0  28.4    194.6,177.6,165.7   27      57    8344
       5  114.0  29.5    194.5,177.7,158.7    3     207   45627
       6  107.5  20.2    155.6,150.3,133.2    5   71606 8676042334
       7  125.5  21.5    181.3,177.8,170.4    6     932 6019722
       8  131.2  21.6    177.9,171.7,170.8   15     375 1374233
       9  105.0  32.8    199.9,157.1,156.3   19     207   24011
      10  124.5  24.5    180.5,173.8,159.2   13     304  316780
      11  110.3  17.3    145.4,140.0,138.6   23 1002485 5092426401440
      12  129.3  19.8    174.1,160.1,159.1   30    1283 26016043
      13  131.1  23.0    170.5,159.2,159.0   18     221  332750
      14  108.4  20.4    161.9,142.0,139.4   20   50020 4593563866
      15  137.6  22.5    174.7,170.5,168.9    8     113  138228
      16  116.7  20.3    167.1,156.8,149.5    2    9517 411435713
      17  118.0  24.2    179.7,165.3,161.5   20     826 1601848
      18  126.9  23.8    166.1,162.7,162.4   24     289  374201
    best scorer's selection rank: median 18  rank-1 hit 0/18 weeks  in top-5 4/18  in top-10 6/18
    line 194: median N 375  weeks reachable within a 150k-entry field: 17/18
    line 237: median N 1,374,233  weeks reachable within a 150k-entry field: 6/18
  app-confidence ordering, best scorer's rank: median 21  rank-1 hit 0/18  in top-5 1/18  in top-10 2/18
  entry anatomy (what wins within our own 40):
    weekly best by generator: lev:2/18 (pool 14%)  boom:13/18 (pool 55%)  game:2/18 (pool 9%)  nostk:0/18 (pool 0%)  midqb:0/18 (pool 0%)  dark:1/18 (pool 11%)
    weekly best: score 176.4  max-from-game 4.67  QB stack 2.00  punt pts  13.3  chalk 0.26  salary 49750
     top-8/week: score 155.6  max-from-game 4.62  QB stack 2.01  punt pts  14.6  chalk 0.25  salary 49761
           rest: score 114.0  max-from-game 4.60  QB stack 2.03  punt pts  12.5  chalk 0.25  salary 49739
  capture rates across our 40 (per week):
    slate-best PUNT held: 9/18 weeks  (distinct punts held avg 35.9, miss gap avg 4.8 pts)
    slate-best QB held:   16/18 weeks  (distinct QBs held avg 17.2, miss gap avg 8.8 pts)
  duplication risk (est copies in a 150k field, naive ownership): median 0.000  p90 0.00  max 0.0  entries with >=1 est copy: 0/720

```

## LSE season 2024 — full diagnostic block
```
  entry selection: P(best >= 194) greedy coverage over correlated draws
=== Contest replay: 2024 (field 15% optimizer-built) ===
contest=gpp  entries=720
  2024: ROI +25557.9%
  TOTAL: ROI +25557.9%
  median finish percentile: 15.9% (lower is better)
  tail: mean best 178.9  max 206.5  weeks best>=237 (avg 2025 milly line): 0/18  >=194 (min line): 5/18
  playable weeks (<=16): mean best 177.1  >=194: 4/16  >=187 (20k-qualifier line): 5/16
  vs REAL winning lines (17 wks known): beat 0/17  mean gap 47 pts  within 20: 2
  salary left on table: mean 245  median 100  p90 700  share >$1k: 0%
  entries-to-line (N for 50% chance best-of-N >= line); top3 = the week's three best entry scores:
    week     mu    sd                 top3  brk N@194 N@237
       1  114.2  22.9    174.7,162.7,157.4   27    2758 16038566
       2  115.2  21.7    150.9,150.7,145.9   31    4952 71069319
       3  116.9  19.3    163.9,150.8,148.6   31   22138 3042728994
       4  120.0  19.5    165.1,153.0,147.3   40    9075 647618678
       5  133.1  21.8    178.8,175.3,169.4   36     270  771804
       6  122.8  18.1    163.2,155.8,153.4    4   16948 5238466823
       7  120.1  21.3    172.6,167.4,147.9    3    2653 33847424
       8  116.2  20.7    165.3,146.7,144.1   34    8344 278326645
       9  123.7  19.7    163.5,161.0,158.7   15    3837 154833855
      10  107.5  24.8    173.2,151.1,149.4   38    2872 7989844
      11  128.3  32.5    206.5,187.0,184.2   11      32    1708
      12  125.4  22.4    178.7,157.4,157.0   32     629 2186751
      13  119.8  24.0    195.4,156.8,154.0   20     696 1322525
      14  127.7  22.6    188.8,166.5,159.5    9     414 1054263
      15  115.9  31.8    197.0,195.3,159.4   23      99   10081
      16  130.2  26.6    196.9,187.3,171.4   22      83   22828
      17  135.6  25.6    188.4,182.0,178.6   25      62   18904
      18  142.9  27.4    197.9,192.6,184.9   20      22    2338
    best scorer's selection rank: median 24  rank-1 hit 0/18 weeks  in top-5 2/18  in top-10 3/18
    line 194: median N 2,653  weeks reachable within a 150k-entry field: 18/18
    line 237: median N 7,989,844  weeks reachable within a 150k-entry field: 5/18
  app-confidence ordering, best scorer's rank: median 14  rank-1 hit 0/18  in top-5 4/18  in top-10 5/18
  entry anatomy (what wins within our own 40):
    weekly best by generator: lev:2/18 (pool 8%)  boom:15/18 (pool 53%)  game:0/18 (pool 12%)  nostk:0/18 (pool 0%)  midqb:0/18 (pool 0%)  dark:0/18 (pool 13%)
    weekly best: score 178.9  max-from-game 4.33  QB stack 2.06  punt pts  16.1  chalk 0.22  salary 49850
     top-8/week: score 156.5  max-from-game 4.49  QB stack 2.03  punt pts  14.3  chalk 0.22  salary 49795
           rest: score 114.7  max-from-game 4.59  QB stack 2.05  punt pts  12.1  chalk 0.22  salary 49745
  capture rates across our 40 (per week):
    slate-best PUNT held: 9/18 weeks  (distinct punts held avg 32.5, miss gap avg 7.3 pts)
    slate-best QB held:   15/18 weeks  (distinct QBs held avg 18.1, miss gap avg 3.3 pts)
  duplication risk (est copies in a 150k field, naive ownership): median 0.000  p90 0.00  max 0.0  entries with >=1 est copy: 0/720

```

## LSE season 2025 — full diagnostic block
```
  entry selection: P(best >= 194) greedy coverage over correlated draws
=== Contest replay: 2025 (field 15% optimizer-built) ===
contest=gpp  entries=720
  2025: ROI +44767.8%
  TOTAL: ROI +44767.8%
  median finish percentile: 14.0% (lower is better)
  tail: mean best 179.8  max 229.2  weeks best>=237 (avg 2025 milly line): 0/18  >=194 (min line): 5/18
  playable weeks (<=16): mean best 182.0  >=194: 5/16  >=187 (20k-qualifier line): 5/16
  vs REAL winning lines (17 wks known): beat 0/17  mean gap 56 pts  within 20: 0
  salary left on table: mean 273  median 200  p90 700  share >$1k: 0%
  entries-to-line (N for 50% chance best-of-N >= line); top3 = the week's three best entry scores:
    week     mu    sd                 top3  brk N@194 N@237
       1  110.8  21.7    167.6,165.6,156.6   28   10613 213082095
       2  114.8  23.3    166.0,158.1,149.4   22    2095 9277839
       3  124.9  20.0    160.1,157.1,153.7    3    2499 65801644
       4  142.3  22.4    196.4,187.8,168.7   14      66   60896
       5  140.3  19.8    175.4,175.0,170.0   26     205 1311644
       6  126.2  23.0    180.2,174.4,161.3    3     435  967146
       7  137.6  32.3    207.6,199.4,188.2   22      17     667
       8  117.9  21.8    162.3,159.9,147.8    8    2911 30623638
       9  136.6  24.2    203.3,180.9,169.2   12      78   41730
      10  133.3  27.1    181.5,172.9,172.4   27      55   10800
      11  125.6  31.1    202.2,183.8,172.7   39      50    4127
      12  137.1  35.3    229.2,186.1,177.8   10      13     298
      13  119.1  22.5    167.0,157.7,150.3   28    1578 8506639
      14  120.7  20.1    171.7,148.7,147.5   39    5125 184203885
      15  122.7  21.1    178.9,164.2,156.3   27    1847 21272084
      16  125.1  20.0    163.3,157.1,155.9   38    2429 62790352
      17  129.4  19.3    163.9,158.0,157.7    2    1731 59575264
      18  118.5  18.7    160.4,143.2,142.3    6   25919 6057553822
    best scorer's selection rank: median 22  rank-1 hit 0/18 weeks  in top-5 3/18  in top-10 6/18
    line 194: median N 1,731  weeks reachable within a 150k-entry field: 18/18
    line 237: median N 9,277,839  weeks reachable within a 150k-entry field: 6/18
  app-confidence ordering, best scorer's rank: median 13  rank-1 hit 1/18  in top-5 4/18  in top-10 7/18
  entry anatomy (what wins within our own 40):
    weekly best by generator: lev:1/18 (pool 9%)  boom:8/18 (pool 58%)  game:2/18 (pool 8%)  nostk:0/18 (pool 0%)  midqb:0/18 (pool 0%)  dark:5/18 (pool 12%)
    weekly best: score 179.8  max-from-game 4.67  QB stack 2.00  punt pts  16.6  chalk 0.26  salary 49711
     top-8/week: score 159.1  max-from-game 4.56  QB stack 2.04  punt pts  16.3  chalk 0.27  salary 49730
           rest: score 118.8  max-from-game 4.53  QB stack 2.04  punt pts  12.6  chalk 0.27  salary 49726
  capture rates across our 40 (per week):
    slate-best PUNT held: 10/18 weeks  (distinct punts held avg 32.7, miss gap avg 6.9 pts)
    slate-best QB held:   11/18 weeks  (distinct QBs held avg 17.5, miss gap avg 6.2 pts)
  duplication risk (est copies in a 150k field, naive ownership): median 0.000  p90 0.00  max 0.0  entries with >=1 est copy: 0/720

```

