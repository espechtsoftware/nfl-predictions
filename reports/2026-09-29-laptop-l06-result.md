# PREREG-L06 result: the ported `qbvar` boom family at equal solve budget

Laptop agent, read once on 2026-09-29 (05:56 CDT), from a clean checkout of the frozen lab commit `a476862c`. Production ran
the panel on the workstation: banks 1150–1153, 144 slate-banks, no errors. Result files are on lab
`production/l06-results-workstation-20260929` @ `f15a7ba`; their sha256 prefixes match production's record (f49855d2 /
d8dc973f / f86c7f1a / 928e0a11). The reader output is also on lab `laptop/l06-read-20260929`. All four banks are
complete, so the read uses all four (the PREREG's "longest complete prefix").

## Reader output (verbatim)

```
identity a476862c0947165b7a2926eeeed4a5208de6172d; 144 slate-banks over banks [1150, 1151, 1152, 1153]
season   arm   n  finish_share_above_best  book_best  book_mean  clears_194  clears_220  pool_oracle  overlap_vs_ctrl  pool_qbvar  book_qbvar
  2023  CTRL  72                  0.02473     186.66     119.97          39           6       205.57             80.0         0.0         0.0
  2023 QBVAR  72                  0.02834     185.85     119.94          44           5       206.18             46.8       640.0        12.7
  2024  CTRL  72                  0.02010     180.42     120.10          42           1       199.68             80.0         0.0         0.0
  2024 QBVAR  72                  0.02241     179.64     119.97          39           0       199.50             47.6       640.0        12.8
   ALL  CTRL 144                  0.02241     183.54     120.03          81           7       202.62             80.0         0.0         0.0
   ALL QBVAR 144                  0.02538     182.74     119.96          83           5       202.84             47.2       640.0        12.8

=== decision (frozen in PREREG-L06.md) ===
QBVAR vs CTRL: mean d +0.00296 [90% -0.00074, +0.00677]; by season 2023 +0.00361, 2024 +0.00232 -> NOT FLIP-ELIGIBLE
VERDICT: QBVAR NOT FLIP-ELIGIBLE; CLOSED for 2026 (90% lower bound > -0.0043)
```

## What it means

- **QBVAR is NOT FLIP-ELIGIBLE, and the question is CLOSED for 2026.**
  - Replacing 25% of the boom solves with same-QB variants made the book's best row *worse* relative to the field in
    both seasons: the share of the field above the book's best rose by +0.00296, 90% interval [−0.00074, +0.00677].
  - The interval's lower bound (−0.00074) rules out an L02-sized gain (−0.0043), which is the closing condition.
- **Co-reported, never decisive:**
  - clears at 194+ are 83 vs 81, and at 220+ 5 vs 7;
  - the book's best and mean are marginally lower; the pool oracle is equal;
  - the qbvar family is 12.8% of the book, and the book overlaps CTRL's on 47 of 144 rows. So the lever was real, not
    vacuous: it changed the books and did not help.
- Scope, as the PREREG states: this tests the **world-objective** port, not the August projection-objective lever.
  Week 4 is unaffected: the generator's boom family is not in use.
- **Production:** please re-run `scripts/l06_report.py --out <dir> --banks 1150,1151,1152,1153` from a clean `a476862c`
  and `cmp` it with `results/l06/reader_output.txt`. The ledger row follows.
