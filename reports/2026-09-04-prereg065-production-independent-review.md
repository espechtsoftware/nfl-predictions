# PREREG-065 / experiment 094 production independent review

Date: 2026-09-04 UTC

Disposition: **sealed result accepted; neither historical contrast passes;
PG_AWARE is unreplicated and remains shadow-only with no live consideration;
the tested redistribution cascade closes; the next score-bearing nomination is
a new generation-by-retrieval crossing, not further tuning of redistribution.**

## Independent replay

Production ran the exact amended reader from the sealed lab release over the
three registered efficacy runs:

```text
scripts/prereg065_report.py
  094b680r1-20260904T103431Z
  094b681r1-20260904T103705Z
  094b682r1-20260904T121250Z
```

The reader SHA-256 was
`4fab3ff4b1200370457267ec5b69b0ddff5071c7f71261e4b09e18397fc69d62`.
Its output SHA-256 was
`9be2380283969623b059e38b98b5fba1ae8429f489a617f357c31b5dc348b8d4`,
exactly matching the lab's committed first-read transcript. The reader exited
zero. Production also verified that the ledger result and the amended top
label in `handoffs/004-participation-aware-generation.md` agree with the
reproduced output.

The exact registered results are:

- primary mechanism, `PG_REDIST - PG_AWARE`: winner-CDF proxy `+0.00150`,
  family interval `[-0.00282, +0.00711]`, verdict
  `UNPASSED_NEAR_MISS`; bank effects `-0.00851`, `+0.00696`, and
  `+0.00605`; three of four leave-one-season-out estimates positive; raw K80
  weekly-maximum change `+0.536 [-0.265, +1.399]`;
- co-primary replication, `PG_AWARE - PG_CTRL`: proxy `+0.00205`, family
  interval `[-0.00141, +0.00648]`, verdict `UNPASSED_NEAR_MISS`; all three
  banks and all four leave-one-season-out estimates positive; raw K80 change
  `+0.031 [-0.768, +0.944]`;
- mean corpus oracle `193.949 -> 194.288 -> 194.507` for control, aware, and
  redistribution respectively;
- candidate counts at 200+ `251 -> 263 -> 314`, at 210+ `80 -> 83 -> 108`,
  at 220+ `26 -> 27 -> 35`, and at 230+ `7 -> 7 -> 8`;
- beneficiary-only 200+ candidates `120 -> 136 -> 184` and inactive-player
  contamination `16.57% -> 15.91% -> 15.73%`;
- mean realized K80 maximum `180.747 -> 180.778 -> 181.314`; selected weeks
  at 200+ `6 -> 7 -> 9`, while selected 220+/230+ weeks remain `1/1` in all
  three arms;
- the descriptive A5 raw prefixes for `PG_REDIST - PG_AWARE` are all
  positive: K3 `+0.500`, K10 `+1.131`, K20 `+1.496`, and K57 `+1.314`.

Amendment 1's receipt disclosure also reproduces: one of 216 slate-bank cells
has negative unallocated mass (`-30.55`) while exact conservation holds.

## Interpretation and disposition

The redistribution treatment materially enlarges the high-score candidate
supply—about 25% more 200+ candidates than PG_AWARE—and slightly improves the
pool oracle and contamination. The current K80 retrieval converts only a small
part of that extra supply into book performance. This is useful mechanism
evidence, but it is not a passed efficacy result and does not authorize live
use.

Production accepts the frozen routing verbatim:

1. The 093 PG_AWARE result did not replicate at the 0.975 family level.
   `handoffs/004-participation-aware-generation.md` is therefore correctly
   downgraded to **unreplicated—shadow only, no live consideration**.
2. The PG_REDIST cascade closes in its tested form. Do not search another
   redistribution dose, cap, transfer law, or same-panel variant.
3. The strong PREREG-054 P_MIX judge result is unaffected. Experiment 094
   changed generation and does not invalidate the separately reproduced
   P_MIX selection result or its live-certification conditions.
4. Experiment 091 remains held. Its phenotype mechanism failed the frozen D1
   screen; it is not revived by 094.

## Next nomination

Production nominates one bounded **generation-by-retrieval crossing** as the
next new score-bearing preregistration. It should use the already-defined
PG_CTRL and PG_REDIST candidate-generation mechanisms at the same 800-solve
budget, the same P_MIX judge, and fresh banks. Each frozen pool should be
selected by:

- the incumbent D800_DEMAX retrieval control; and
- the already-defined conditional-novelty retrieval from PREREG-060, which
  found complementary 210/220 candidates on a held-out bank but diluted its
  advantage by K80.

This is a 2 x 2 mechanism crossing, not a request to refit either component.
The primary question is whether conditional-novelty retrieval captures more of
PG_REDIST's added 200--230 supply than it captures from the control pool. The
reader should report the registered winner-CDF proxy and raw weekly maximum at
K3/K10/K20/K57/K80, the 194/200/210/220/230 tail surface, per-pool oracle and
regret, treatment turnover, and the generation-by-retrieval interaction.
Multiplicity, bank-veto, leave-one-season-out, exact-K, shared-judge,
fixed-budget, and independent-evaluation-bank rules remain required.

This nomination deliberately prefers a new intervention test over pooling the
already-open 093 and 094 results. A pooled estimate may be reported later as
descriptive synthesis, but it cannot replace the crossing and must not be used
to rescue the failed family-level replication.

No production scoring code, live policy, paid-entry state, graph state, or
cloud execution was changed by this independent review.
