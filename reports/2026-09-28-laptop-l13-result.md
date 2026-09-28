# PREREG-L13 result: selectors at the 99th-percentile lines; the plain-mean optimizer (R5)

Laptop agent, read once on 2026-09-28 (14:03 CDT). Frozen lab `laptop/l13-p99-selectors-20260928` @ `5d3aaa9`, read from that
clean checkout. 72 of 72 slate-banks (banks 1200–1201), 0 errors, run on the laptop. Result files and this output:
lab `laptop/l13-results-20260928` @ `2aa8046` (`results/l13/`; `reader_output.txt` sha256 `8ad461d1…`).

## Reader output (verbatim)

```
slate-banks read: 72 (expected 72)
         tickets89  tickets95  tickets99  tickets99.8  t99_2023  t99_2024    mean    best  distinct_players  max_exposure
EMAX         934.0      438.0      106.0         27.0      37.0      69.0  119.25  189.02             133.0          63.8
MEAN        1085.0      512.0      106.0         27.0      52.0      54.0  122.95  186.77             118.1          84.2
PMO         1175.0      524.0      107.0         13.0      42.0      65.0  128.24  176.57              56.7         132.2
PMO_X50     1386.0      699.0      184.0         46.0      68.0     116.0  129.21  181.20              55.8          72.0

VERDICT 1 (p99 lines): top arm PMO_X50; vs EMAX 184 vs 106 (+73.6%, seasons {2023: (68, 37), 2024: (116, 69)}, paired 23-23); MEAN 184 vs 106 (+73.6%, seasons {2023: (68, 52), 2024: (116, 54)}, paired 24-19); PMO 184 vs 107 (+72.0%, seasons {2023: (68, 42), 2024: (116, 65)}, paired 23-9)
  -> NO CLEAR LEADER AT P99
VERDICT 2 (PMO vs MEAN, tickets89): 1175 vs 1085 (+8.3%); seasons {2023: (526, 492), 2024: (649, 593)}; paired 27-40 -> NOT SUPPORTED
VERDICT 2 (PMO_X50 vs MEAN, tickets89): 1386 vs 1085 (+27.7%); seasons {2023: (609, 492), 2024: (777, 593)}; paired 32-31 -> SUPPORTED
```

## What it means

1. **R5: the plain-mean optimizer with a 50% per-player exposure cap (PMO_X50) is SUPPORTED against MEAN at the p89
   satellite line.**
   - 1,386 vs 1,085 tickets (+27.7%), better in both seasons (2023 609 vs 492, 2024 777 vs 593); paired 32–31.
   - Realized mean per row 129.21 vs 122.95 (+6.3), in line with the review's historical +8.0.
   - At p95, 699 vs 512.
2. **The uncapped optimizer (PMO) is NOT SUPPORTED:** +8.3% in aggregate, but paired 27–40. Its average maximum
   exposure is 132 of 144 rows: it is nearly one lineup repeated, all or nothing. **The cap is what makes the
   optimizer work.**
3. **At p99 the frozen verdict is NO CLEAR LEADER.** PMO_X50 leads every arm in aggregate: 184 tickets vs 106–107
   (+72–74%), both seasons, and paired wins against MEAN (24–19) and PMO (23–9). But it only ties EMAX on the paired
   count (23–23), and the rule requires more wins than losses against every arm. At p99.8 PMO_X50 has 46, against
   27 for MEAN/EMAX and 13 for PMO.
4. **Diversity:** PMO_X50's books use about 56 distinct players (MEAN about 118): fewer players, capped exposure.

## A live-week sanity check (Week 3, one week, hindsight; not part of the preregistration)

The PMO_X50 form (house rules, cap 4, $49k floor, MIN_PROJ 1.0, OUT/IR/D excluded, ≤ 7 shared, 50% cap) was built on
the Week-3 frames and compared with the mean book from the pool (Q4b, DST cap 25%):

| Week 3 | MEAN from the pool: projected / realized / max exposure | PMO_X50: projected / realized / max exposure | PMO_X50 solve time |
|---|---|---|---|
| K 58, Saturday projections | 131.2 / **155.1** / 57 of 58 | 132.7 / 133.0 / 29 | 13 s |
| K 144, Saturday projections | 130.6 / **151.8** / 138 of 144 | 132.4 / 132.8 / 72 | 53 s |
| K 144, Sunday 10:50 projections (the union frame) | 130.3 / 148.4 / 133 of 144 | 132.7 / 132.9 / 72 | 56 s |

- On Week 3 the mean book carried one player in almost every row, and he hit. The capped optimizer projects higher but
  spreads that risk.
- Across the 72 preregistered slate-banks the cap's diversification and higher mean won (+27.7%, both seasons). Week 3
  is one slate where concentration paid.
- The solve takes under a minute for 144 rows on the laptop, so it fits the T-70 window.

## For the operator (nothing is adopted by this file)

- The standing instruction (12:2x CDT) was: "if L13 supports it, add plain-mean-optimizer rows … to the same union."
- **What L13 supports is the capped optimizer's own book, not uncapped rows added to a pool that the mean selector then
  picks from.** That form resembles PMO, which failed. The union's `--pmo N` today solves uncapped rows and selects by
  mean.
- **The faithful Week-4 form:** the main (mean-track) book = the PMO_X50 book solved on the T-70 frame (K rows, 50%
  exposure cap), while the deep-line sleeve stays the union's mean selection. Verdict 1 did not change the p99 rule.
- The operator decides whether it enters Week 4 or is papered first. **Production: please re-run the frozen reader for
  the byte-identical check.**
