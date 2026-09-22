# Sorting: no sort key — simulator, projection, ownership or field duplication — orders the book reliably across two slates

Assignment from `ee64e8cb`. Scripts: `reports/lab-handoffs/2026-09-22-sort-key-study-week2.py` (the
sequential-layout test) and `…-sort-key-two-weeks.py` (the within-book diagnostic). The grid and
criterion are in each script's header, **written before any number was computed**. The book is the
lineups actually entered (the account is resolved in-query by its 12-contest / 97-entry signature;
no name is printed or stored). This nominates; it does not adopt.

## Grid

| key | direction | deployable? |
|---|---|---|
| sim mean (incumbent hsim, reproduces the book's `sel_mean` exactly) — **current** | high first | yes |
| sim P(≥194) | high first | yes |
| projection sum | high first | yes |
| naive ownership sum (`backtest.field.naive_ownership`) | low first | yes |
| `proj_ownership` from `player_projections` | low first | **unusable: the column is empty both weeks** |
| realized ownership sum (Millionaire) | low first | no — oracle |
| exact duplicates in the real Millionaire field | low first | no — oracle |
| field entries sharing ≥ 7 of 9 ("core" duplication) | low first | no — oracle |
| random (5,000 permutations) | — | the null |

## Test 1 — Week-2 sequential layout (payout order, the 12 contests entered)

Lines come from each real field: ticket contests use the K-th best score (25 / 2 / 4 tickets);
GPPs use the field's top-20% score (payout is NULL in the warehouse).

| key | CASHES (null 5–95%: 0–4) | pctl vs random | Milly lineup %ile | Flea best %ile |
|---|---:|---:|---:|---:|
| sim mean (current) | 2 | 45 | 32.8 | 91.3 |
| sim P(≥194) | 3 | 74 | 24.1 | 91.3 |
| projection sum | 2 | 45 | 32.8 | 91.3 |
| naive ownership | 2 | 45 | 30.5 | 86.0 |
| realized ownership (oracle) | 0 | 3 | 12.8 | 71.5 |
| exact dup (oracle) | 3 | 74 | 25.4 | 86.9 |
| core dup (oracle) | 1 | 17 | 12.8 | 82.1 |
| random (mean) | 2.2 | — | 38.4 | 85.1 |
| perfect hindsight (sort by realized) | **7** | — | 92.8 | 86.9 |

**Week 2 cannot discriminate between keys.** The entered book's best lineup scored **156.2**, and
every satellite line was **164–179**. No ordering could win a ticket; only the 31 GPP slots (lines
137.7–143.4) could cash. Perfect hindsight reaches 7 cashes, and every key falls inside the random
null.

## Test 2 — within-book rank correlation with the realized score, both weeks

Spearman(key, realized) over the distinct entered lineups (W1 80, W2 97), with a two-sided
permutation p. **Declared candidate rule: same sign both weeks and p < 0.10 in both.**

| key | W1 ρ (p) | W2 ρ (p) | candidate? |
|---|---:|---:|---|
| projection sum (≡ sim mean) | +0.036 (0.77) | **−0.266 (0.009)** | no — flips |
| naive ownership, low first | +0.051 (0.66) | +0.239 (0.022) | no — W1 null |
| realized ownership, low first (oracle) | +0.032 (0.78) | −0.247 (0.015) | no — flips |
| exact dup, low first (oracle) | −0.221 (0.051) | −0.117 (0.34) | no — W2 null |
| core dup, low first (oracle) | +0.009 (0.94) | −0.248 (0.018) | no — flips |

**No key qualifies — not even the oracles that see the real field after lock.** The one key with a
consistent sign (exact duplication, where the *more*-duplicated lineups scored higher, both weeks)
is an oracle, and it is null in Week 2.

## What follows

1. **Simulator sort ≡ projection sort.** A lineup's simulated mean is the sum of its players'
   means, so "sort by sim mean" and "sort by projection sum" produced the *identical* order in
   Week 2. The question "is there a simulator-free key that isn't a coin flip" has no separate
   simulator axis to escape: the current key is already the projection key.
2. **Within a book this homogeneous, the realized order is noise.** The book is built from the same
   projection with an exposure structure, so its lineups differ by a few projected points and the
   week's variance swamps that. No pre-lock key orders it, and on these two slates neither did the
   field-side oracles.
3. **The sort is therefore mostly a distribution decision, not a prediction.** Since no key predicts
   which lineup wins, a defensible, outcome-free rule is to **spread** rather than rank: give each
   contest block a mix of the book's stacks and games, so no block holds only one game script. It is
   untested; I name it as the natural next nomination rather than a result.
4. **The binding constraint in Week 2 was construction, not sorting:** a best entered lineup of 156 vs
   ticket lines of 164–179 and a winner at 232. That agrees with production's ordering of the gaps
   (construction > retrieval > sorting).
5. **Data gap:** `player_projections.proj_ownership` is empty for 2026 Weeks 1–2, so production's own
   ownership projection cannot currently serve as a sort key or a leverage input. Worth a README
   deficiency row if it is supposed to be populated.

Limits: two slates, as assigned; the Week-2 sim and projection keys come from the Saturday 15:10Z
frame, not the Sunday T-70 frame; the Week-1 test is within-book only (it used the `top` layout, and
no Week-1 simulator draws are on this host); GPP cash lines are a top-20% convention, not DK's
payout table.
