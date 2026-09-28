# PREREG-L12 result: the ownership tilt, out of sample

Laptop agent, read once on 2026-09-28 (11:08 CDT). Frozen lab `laptop/l12-own-tilt-20260928` @ `0d1e1d8`, read from that
clean checkout. 72 of 72 slate-banks (banks 1190–1191), 0 errors, run on the laptop. Result files and this output:
lab `laptop/l12-results-20260928` @ `7dfcb96` (`results/l12/`; sha256 of `reader_output.txt` `cce67c71…`).

## Reader output (verbatim)

```
slate-banks read: 72 (expected 72); ownership slot coverage 0.891
      tickets89  tickets95  t89_2023  t89_2024    mean    best  share_above_best  own_sum  overlap_vs_MEAN
MEAN     1012.0      487.0     456.0     556.0  122.44  185.89           0.02409     49.3            144.0
T05      1028.0      496.0     469.0     559.0  122.73  184.66           0.02652     51.3            130.8
T10      1030.0      502.0     475.0     555.0  122.77  185.91           0.02373     53.0            118.7
T20       989.0      476.0     456.0     533.0  122.48  184.25           0.02575     55.6             99.8

T10 vs MEAN tickets89: 1030 vs 1012 (+1.8%); seasons (MEAN, T10) {2023: (456, 475), 2024: (556, 555)}; paired 28-27
VERDICT: INCONCLUSIVE (no out-of-sample evidence either way; the operator's adoption stands on its own grounds)
```

## What it means

1. **Frozen verdict: INCONCLUSIVE.**
   - T10, the value adopted on the morning of 09-28, beat MEAN by **+1.8%** at p89 (1,030 vs 1,012). That is under the
     3% bar.
   - 2023 favoured T10 (475 vs 456), 2024 did not (555 vs 556). Paired 28–27.
   - At p95 T10 was +3.1% (502 vs 487), reported only.
   - The panel neither confirms nor contradicts the tilt.
2. **The tilt is not vacuous.** T10 shares 118.7 of 144 rows with MEAN on average, so it did change the books.
3. **More tilt is worse.** T20 fell below MEAN (989), with a worse share above the book's best (0.02575 vs 0.02409).
   T05 and T10 sit within noise of MEAN.
4. **Book quality is unchanged.** The mean per row (122.44 → 122.77) and the best row (185.89 → 185.91) barely moved.
5. **Declared limitation (from the PREREG):** slot coverage is 0.891. The replay's ownership has one DST row per slate,
   so the tilt acts on skill-player ownership only.

## For the operator (nothing is adopted by this file)

- **Week 4 is unaffected.** `MEAN_OWN_TILT=0` was restored on 09-28 after the laptop showed that the 156.8 used realized
  (hindsight) ownership: the pre-lock sets gave 148.1 against 151.4 with no tilt (HANDOFF 09-28).
- L12 gives no reason to switch the tilt back on. It also does not close the idea: a small tilt is within noise.
- **The one input that could change this is a better ownership predictor.** L05 found the lag model is the bottleneck,
  and PREREG-O1 (Fantasy Points ownership vs the lag model, Weeks 4–7) measures exactly that. A tilt question reopens
  only if O1 selects a predictor materially better than the lag model.
- **Production:** please re-run the frozen reader for the byte-identical check:
  `python scripts/l12_report.py <dir with results/l12/results_bank119*.jsonl>` from a clean checkout of `0d1e1d8`,
  then `cmp` against `results/l12/reader_output.txt`. The ledger row follows.
