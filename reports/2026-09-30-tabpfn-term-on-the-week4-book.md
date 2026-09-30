# The TabPFN ownership predictor in the term, on the Week-4 book shape

Reviewer, 2026-09-30 04:21 CDT. Branch `review/ownership-term-20260929`. Follows PREREG-L23b (stage 1, PASS) and
PREREG-L24 (stage 2, NEUTRAL at K = 36: +4.2% at p89, paired 31–27; −14% at p99).

**Operator decision, 2026-09-30 (chat):** TabPFN goes on the whole main book for Week 4 if the laptop meets the three
conditions in §3 by Thursday 12:00 CT; otherwise the blend stays. A split (TabPFN on the shallow-line satellites, the
blend on the deep-line supersats) is a Week-5 request (§4), not a Week-4 change.

## 1. The check

L24 read the two predictors at K = 36. This week's main book has 105 rows and holds both the shallow-line satellites
and the deep-line supersats, so the check is at 100 rows on the plan's own dealing:

- The arming report's harness, K = 100, exposure cap 50, DST cap 25; fresh banks 1320 and 1321; 36 slates of 2023–24.
- Arms: no term (X50), the armed blend at 0.20, and TabPFN's stage-1 predictions (L23b, `preds_l23b.parquet`, sha
  `5c8384d6…` pinned) at 0.20. A player without a prediction gets no term, as in L24.
- Each contest of the plan is scored at its own line on its own rows under the head layout. Results are multiples of
  what the field would expect from the same entries; the plan's counts are not printed.

## 2. Result

| Bank | Objective | Points vs field | p89 | p95 | p99 | p99.8 | Shallow-line tickets (× field) | Deep-line tickets (× field) | Slates with no deep ticket |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 1320 | none | +0.4 | 1.20× | 1.35× | 1.83× | 1.67× | 1.17× | 1.92× | 58% |
| 1320 | blend 0.20 | +4.6 | 1.39× | 1.52× | 1.78× | 1.39× | 1.09× | 2.02× | 50% |
| 1320 | TabPFN 0.20 | +4.9 | 1.48× | 1.66× | 1.61× | 0.56× | 1.36× | 1.85× | 50% |
| 1321 | none | +1.4 | 1.19× | 1.23× | 1.19× | 0.56× | 1.17× | 1.42× | 61% |
| 1321 | blend 0.20 | +5.6 | 1.39× | 1.47× | 2.14× | 1.67× | 1.27× | 2.08× | 50% |
| 1321 | TabPFN 0.20 | +5.2 | 1.40× | 1.39× | 1.36× | 0.42× | 1.54× | 1.36× | 56% |

TabPFN against the blend, both banks pooled (72 slate-banks; 90% intervals from a slate bootstrap by season):

| | Difference | 90% interval | Slate-banks up–down | 2023 | 2024 | Totals |
|---|---:|---|---:|---:|---:|---|
| Average score per row (sd vs field) | −0.001 | [−0.038, +0.036] | 35–37 | −0.021 | +0.020 | |
| Shallow-line tickets per slate | +1.29 | [+0.42, +2.27] | 32–26 | +1.31 | +1.28 | 402 → 495 (+23%) |
| Deep-line tickets per slate | −0.38 | [−0.90, +0.11] | 16–17 | +0.25 | −1.00 | 124 → 97 (−22%) |

- The two predictors give the same average lineup. TabPFN's rows are better at the shallow lines (both seasons; the
  interval excludes zero) and worse at the deep line (not distinguishable from zero; L24 found −14% at p99 on other
  banks, and 10 against 8 at p99.8).
- The pattern is the one the term itself shows: a better ownership ranking buys the cash-to-p95 lines and does not buy
  the deepest ones.
- Nothing here reaches the sleeve (the Millionaire seat and the two deep satellites), which is built without any term.

## 3. Conditions for Week 4 (the operator's, restated)

1. A live script that writes the same `pred_own` file `--main-own-source` reads (the laptop's 22:52 plan), fitted on
   the laptop GPU from the rows file plus 2026 Weeks 1–3 and the newest LineStar capture.
2. **Its fallback is the blend, never no term.** TabPFN without LineStar lost to the blend on all 36 slates (L23b), so a
   missing or refused LineStar capture must leave `ownership_blend.py`'s file in place.
3. A passing smoke by Thursday 12:00 CT (the term's gates 1–2 and `main_own_term` on the TabPFN file), and on Monday the
   TabPFN book scored beside the blend book and the no-term control on paper.

If any of the three is not met, the blend stays.

## 4. Week 5: the split

TabPFN on the rows the shallow-line contests take and the blend on the rows the deep-line contests take. On this
week's plan the two classes share the first four rows and interleave through the rest, so a split needs a second main
sequence and a track for it in the layout (three tracks: shallow main, deep main, sleeve). It is a build-and-layout
change and needs its own rehearsal; it is not for the freeze this week. On the panel its value over "TabPFN
everywhere" is the deep-line difference above, small at this week's stakes and larger if the deep-line volume grows.

## 5. Reproduction

`reports/lab-handoffs/2026-09-29-ownership-term/11_panel_term_tabpfn.py` (run: `KROWS=100 WORKERS=14 LAB_WT=… TABPFN_PREDS=…
python 11_panel_term_tabpfn.py 1320 tp100a base=0:,blend20=0.2:blendsets,tabpfn20=0.2:TABPFN_LS`, then bank 1321) and
`12_read_tabpfn.py`. The predictions file is third-party-derived and stays in the private bucket.
