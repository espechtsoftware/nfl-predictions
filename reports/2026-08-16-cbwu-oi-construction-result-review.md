# Review: CBWU-OI fixed-budget construction diagnostic

Date: 2026-08-16. **No code was changed. No outcome was queried.**

---

## 1. This is the first measured gain in the construction layer

At **exactly equal candidate budget** (241–265, mean 253.81), the best available
candidate improves:

| metric | canonical | OI | change |
|---|---:|---:|---:|
| mean weekly C | 181.07 | 186.73 | **+5.66** |
| ≥194 | 11 | 18 | **+7** |
| ≥200 | 8 | 14 | **+6** |
| ≥210 | 6 | 10 | **+4** |

Positive in all three seasons, improving 25 slates, tying 25, declining 4.

The forensic put **78.99 of the ~88 lost points in construction**, and nothing
had ever moved that layer. This does — and at fixed budget, so it is not the
added-budget effect the CE and role unions had to be discounted for.

## 2. The mechanism is more valuable than the score

The structural detail is the part to carry forward:

| quantity | canonical | OI |
|---|---:|---:|
| mean unique player-pair reach | 3,056.35 | **4,307.80** (+41%) |
| mean QB stack-core reach | 118.78 | **181.09** (+52%) |
| shared pool identities | — | 103.26 of ~254 (40.7%) |

And decisively: **OI retains all nine P players on only 44 slates against
canonical's 54.** Its player coverage is *worse* while its results are better.

> **Combination breadth, not player breadth, is the lever.**

That converges with the exact-P census, which independently found the failure is
"combination assembly/search, not broad player eligibility." Two analyses, two
methods, one conclusion. That is the design principle ATLAS should be built on,
and it is now empirically grounded rather than inferred.

## 3. The caveat that matters most: the gains stop at 220

| threshold | canonical | OI |
|---|---:|---:|
| ≥220 | 3 | **3** |
| ≥230 | 1 | **1** |
| ≥240 | 0 | **0** |

All gains sit at 194–210. **Nothing moves at 220 and above.**

This matters because the standing decision law compares
**240 → 230 → 220 → 210 → 200**, taking the first non-zero difference. On these
C-layer counts the first three thresholds are **exact ties**, and a frozen
exact-80 comparison would only reach a non-zero difference at 210.

Two things follow:

1. **Do not let the +5.66 mean and +7/+6 counts create an expectation of a
   tail-first pass.** The layer improved in a band the decision law examines
   fourth. A neutral or narrow result at the book level would be consistent with
   this diagnostic, not a contradiction of it.
2. **State this in the prospective protocol before it runs.** Predeclaring
   "gains are expected at 200–210 and not above" turns a modest exact-80 outcome
   into confirmation rather than disappointment, and prevents a post-hoc
   argument about which threshold should have governed.

The honest summary: this improves the *shoulder*, and the objective is the
*extreme*.

## 4. C-to-S conversion is unknown, and the protocol is right to forbid measuring it

The forensic measured `C − S = 5.007`. OI improves `C` by 5.66. So the realizable
`S` gain is bounded above by the C gain and reduced by whatever the selector
fails to convert.

Note the interaction: the selector is **saturated at 220+** (selected equals pool
oracle), but OI's gains are all **below** 220 — precisely the band where the
5-point selection gap lives. So the conversion rate is genuinely uncertain here
in a way it would not be if the gains were at the extreme.

Refusing to compute the hindsight S is correct. Just record the uncertainty
explicitly so nobody assumes C-gain equals S-gain.

## 5. This updates two of my own recommendations

**5.1 Evaluate successors on `C`, never on reaching P — now demonstrated, not
argued.** I made this point on theoretical grounds in the census review: P is a
hindsight target no pre-lock criterion can aim at. OI proves it empirically —
it gained **+5.66 points of C while moving only 0.30 swaps closer to P**
(5.17 → 4.87, better on 16 slates, tied on 35). You do not need to approach P to
gain. **P-distance is a useful diagnostic and a poor optimisation target**, and
ATLAS should be scored on C.

**5.2 My tenfold-budget min-swap diagnostic should be deprioritised.** I proposed
it to separate search *capacity* from search *direction*. OI substantially
answers the question: it improved C at **exactly equal budget** by changing which
combinations are admitted. That is direct evidence that **composition, not
capacity, is binding** — more candidates of the same character would not have
produced this. The diagnostic would now be confirmatory rather than decisive,
and the budget is better spent elsewhere.

## 6. On the prospective framing

Correct as written. Production unchanged; promotion requires prospective
evidence plus full P/C/S and selector revalidation against the changed pool.

One addition for that revalidation: since OI's pool shares only **40.7%** of
identities with canonical, the selector's behaviour on it is genuinely untested —
coverage masks, support counts and tie structure all change. The selector
resampling instability already measured (54.28/80 disjoint-half overlap on the
canonical pool) should be re-measured on the OI pool before its book is trusted,
not assumed to carry over.

## 7. Summary

| item | position |
|---|---|
| The result | First measured construction-layer gain; fixed budget, so not a budget artifact |
| The mechanism | **Combination breadth beats player breadth** — worse player coverage, better C. Build ATLAS on this |
| **Main caveat** | **Gains stop at 220.** Predeclare that in the prospective protocol so a narrow exact-80 result reads as confirmation |
| C→S | Deliberately unmeasured and correctly so; record that C-gain ≠ S-gain, especially below 220 where the selection gap lives |
| My census caveat | **Confirmed empirically** — +5.66 C on 0.30 swaps toward P. Score successors on C |
| My tenfold diagnostic | **Deprioritised** — equal-budget gain implies composition, not capacity |
| Revalidation | Re-measure selector stability on the OI pool; 40.7% shared identities means it does not carry over |
