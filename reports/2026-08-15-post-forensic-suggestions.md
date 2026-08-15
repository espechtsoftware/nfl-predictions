# Post-forensic suggestions

Date: 2026-08-15. Additional suggestions after the final preseason forensic
result. **No code was changed. No outcome was queried.**

---

## 1. What the result settled, including against my own prediction

The H/P/C/S decomposition is decisive and it did not go the way I expected.

| gap | mean points |
|---|---:|
| H − P (player support) | **3.583** |
| **P − C (construction)** | **78.994** |
| C − S (selection) | 5.007 |

First failed layer at 210: construction 44 slates, player support 3, selection
**0**.

**My predeclared expectation was wrong in one half.** I wrote that L2 would
dominate at 210+ *and* that L1 would be large, citing the 33 winner-slots absent
from the pool. L2 does dominate, overwhelmingly. But L1 is 3.58 points — the
player universe is essentially fine. **The union of players already in the pool
supports a 240-point legal lineup on 44 of 54 slates.**

The players are there. The combinations are not.

### Two of my suggestions are now dead and should be recorded as such

**Pool admission is dead.** I proposed a route-share floor to admit players the
projection-based pool never builds, and proposed a retrospective admission check
to size it. The forensic answers that question directly and more completely:
`H − P = 3.583` points, and the result states it plainly — "merely admitting
more players is not enough; the union already supports a high-scoring legal
lineup on almost every slate." Whatever those 33 winner-slots cost, it is not
where the score is going. Close it.

**The salary-floor question is answered and the answer is the opposite of what
I suspected.** I argued the floor might be excluding the cheap high-participation
population and that L1 could not detect it. The floor-free solve produced +0.534
mean, median zero, and **zero new threshold-reaching slates at any line from 187
to 240**. The floor costs nothing. The suggestion to measure it was worth
making; the hypothesis behind it is refuted.

Both belong in the kill list with these numbers attached, since both are ideas a
future session would otherwise regenerate.

---

## 2. The one large gap the forensic leaves open

**The construction layer is 79 points and nothing yet explains it.**

`P − C = 78.994` says: from **the same players already in the candidate pool**,
a legal lineup exists scoring 79 points more than anything the generator built.
That is not a belief problem, not a selection problem, and not a universe
problem. It is combinatorial coverage.

The forensic identifies the layer but does not characterise it. That is the
highest-value follow-up available and it is cheap, because the P-oracle roster
is already solved per slate as part of the decomposition.

**Suggested analysis — P-oracle versus the generated pool:**

1. **Swap distance.** For each slate, the minimum number of player swaps from
   any generated candidate to the P-oracle. This is the single most decisive
   number: if the median is 2, this is a near-miss problem and local search
   around existing candidates recovers much of it. If it is 7, the generator
   occupies a different region entirely and only a diversity change helps.
2. **Structural contrast.** P-oracle versus pool distribution on games spanned,
   largest single-team block, stack shape, positional spend, salary
   distribution, and aggregate ownership. Which structural constraints does the
   P-oracle violate that the generator implicitly enforces?
3. **Which players.** Are P-oracle players thinly represented in the pool
   (appearing in a handful of candidates) or well represented but never
   *combined*? This distinguishes "the generator underweights these players" from
   "the generator never puts these players together."
4. **Constraint attribution.** Test whether the P-oracle would have been
   generable under each production construction rule in turn — stack mandate,
   QB+2+bring-back, salary floor, candidate budget. If a rule excludes the
   P-oracle on many slates, that rule is the construction gap.

Item 4 is the one that could produce an actionable answer directly. The
construction constraints were each adopted on one-shot tail evidence; none has
been tested against "does this rule exclude the best available lineup."

This is the natural target for the subgroup-discovery and UMAP tools proposed
earlier — no longer "what did we leave in the corpus" in general, but
specifically **what region does the P-oracle occupy that the generated
candidates do not.**

---

## 3. The realistic recourse value is still unmeasured

The hindsight ceiling is large — 53 of 54 slates improved, mean +42.62, and 12
new ≥240 slates. The result correctly states this is an upper bound using
realized late outcomes and "must never be advertised as achievable."

But the **realistic** figure — late slots optimised knowing realized *early*
results and only the *simulated distribution* for late games — appears not to
have been computed. Without it, the opportunity register carries a 42.6-point
number with no convertible counterpart, which is precisely the failure mode
flagged when the ceiling was designed.

**It is computable historically and needs no new data.** The world matrices
already exist; the change is to optimise the late slots against simulated late
distributions rather than realized scores, conditional on the realized early
core. That yields the value of a policy that could actually have been executed.

**Suggestion:** compute it before the register is finalised, and put the
realistic figure — not the hindsight one — in `size_estimate`. Report the ratio
between them; it is the fraction of the ceiling that is structurally
unreachable, and it is the number that determines how much recourse engineering
is worth.

Also apply the distinct-slate convention here: "32 new ≥200, 30 new ≥210, 24 new
≥220" across nested thresholds is not 86 improvements. Report the count of
distinct slates that moved.

---

## 4. A connection worth testing: are the construction gap and the recourse gap the same gap?

Late swap gives access to **different combinations of late-game players**. The
construction gap is **combinations never built**. These may be measuring
overlapping opportunity rather than two independent ones.

The test is cheap and it matters for sizing: **is the post-swap optimal lineup
closer to the P-oracle than the pre-swap best candidate?** Measure swap distance
from both to the P-oracle.

- If recourse recovers P-oracle-like lineups, then the two gaps largely coincide
  and recourse is a *mechanism for reaching* the construction opportunity — in
  which case they must not be summed in the register, and recourse becomes the
  concrete way to attack construction.
- If the post-swap optima are structurally different from the P-oracle, they are
  genuinely additive opportunities.

Getting this wrong in the register means either double-counting the largest two
opportunities or missing that one is the delivery mechanism for the other.

---

## 5. Generator budget reallocation is now the highest-leverage known change

With construction identified as the dominant layer, the standing generator-yield
finding becomes much more consequential than when it was recorded: **`lev` is
roughly two-thirds of the candidate pool, 8% of selections, and its deletion
costs one clear**, while `boom` deletion costs fifteen and `dark` is the best
value per candidate.

Two-thirds of the construction budget is being spent on the batch that is now
known to sit in the layer where all the loss is, at the lowest yield per
candidate.

Every previous test of this was a **deletion at reduced budget**. The untested
change is **reallocation at constant budget** — hold total candidates fixed and
move `lev`'s share to `boom`, `dark`, role and scenario-conditional generation.
That is a single-lever, exact-budget arm using existing runner and comparator
infrastructure.

Given the closure posture this is a 2026 prospective candidate rather than a new
historical arm — but it should be at the top of the prospective construction
program, because it is the only known lever that acts directly on the layer the
forensic identifies and costs no additional compute.

---

## 6. Summary of suggestions

| # | suggestion | cost | why now |
|---|---|---|---|
| 1 | **Characterise the P-oracle versus the pool** — swap distance, structure, constraint attribution | low | the 79-point layer is identified but unexplained; item 4 could name the responsible rule |
| 2 | **Compute realistic recourse** and register it instead of the hindsight ceiling | low | otherwise the register's largest number is unconvertible |
| 3 | **Test whether construction and recourse gaps coincide** | low | prevents double-counting the two largest opportunities |
| 4 | **Constant-budget generator reallocation** | prospective | only known lever acting directly on the dominant layer |
| 5 | **Record pool admission and salary floor as closed**, with the forensic numbers | trivial | both are ideas a future session would otherwise regenerate |

---

*Unrelated note: the claude.ai Gmail, Google Calendar and Google Drive
connectors require authorisation through claude.ai connector settings before
their tools can be used; they are unavailable in this session.*
