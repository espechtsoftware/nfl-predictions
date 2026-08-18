# B1 union-C census result: volume, not diversity

Date: 2026-08-18. One-shot execution of the frozen protocol
(`2026-08-18-b1-union-c-census-protocol.md`, SHA `2d1cb29b…`). Diagnostic
only; licenses nothing. Canonical result:
`reports/b1-union-c-census-runs/20260818-b1-union-c-census-v1/report.json`.

## Headline and its mandatory null

Across 51 corrected-era panels (the frozen list; an earlier prose line miscounted 42 — the computed numbers always used the full list) (127,778 distinct legal rosters, 54 slates,
zero legality drops): **union mean C = 198.10**, grid
43/31/24/15/6/2/1 at 187–240 — versus canonical C 181.07 (11/8/6, 3/1/0)
and CBWU-OI 186.73. The union of everything ever generated exceeds the
operator's 194-mean target and doubles the extreme-tail counts.

**But the order-statistic null explains almost all of it.** Union-C growth
curves at matched book count k, heterogeneous (cross-arm) versus
homogeneous (same-generator seeds):

| k | heterogeneous | homogeneous | diversity premium |
|---|---|---|---|
| 2 | 181.52 | 180.92 | +0.60 |
| 5 | 187.41 | 186.99 | +0.42 |
| 10 | 191.91 | 191.45 | +0.46 |
| 20 | 195.36 | 194.94 | +0.42 |

The curve climbs ~+3.5 per doubling of books with no visible saturation
through k=51 — and **arm diversity is worth ~+0.4 over simply running the
same generator with more independent seeds.** Slate-max attribution is
spread thin (no arm claims more than 3 of 54 maxima).

## Predeclared interpretation

The protocol's B2 trigger required union C >= ~190 AND a materially
positive heterogeneous gap at matched k. The first held; the second
**failed**. B2 union-admission does not earn a heavy slot: the union's
mass comes from more independent draws, which a fixed-budget admission
cannot retain — CBWU-OI (+5.66 at fixed budget from 5 books) is already
the measured value of admission-class mechanisms.

The deeper read: the binding constraint on pool ceiling C is **independent
draw volume**, not belief diversity — and the ledger already shows what
happens when pool volume is pushed through today's weak selection signal
(Addendum 117: raw candidate doubling raised pool opportunities and
*damaged* the selected extreme tail). The 194-mean target therefore exists
inside the generated universe but is not reachable by admitting bigger
pools into a 0.2-correlation selector. Consistent with the recorded
allocation: fixed-budget construction that prices lineups by marginal tail
contribution (residual columns), objective-aligned selection at fixed pool
(A1 family), and law/signal repair remain the funded lanes; S1's floor and
A3's optimality gap calibrate the first two.
