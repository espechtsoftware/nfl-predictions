# Review of post-forensic changes

Date: 2026-08-15. Review of work since the final preseason forensic result.
**No code was changed. No outcome was queried.**

---

## 1. Three of my suggestions were implemented, and two produced answers

**1.1 The exact-stack correction is good practice.** Publishing a correction
that supersedes a headline number the project itself had just published — mean
+42.62 and its tail counts — rather than quietly leaving it standing, is the
behaviour that makes the rest of the record trustworthy. The substantive
conclusion is preserved and the correction is scoped.

**1.2 The construction/recourse overlap test was run, and answered.** I had
proposed measuring whether post-swap optima sit closer to the P-oracle than
pre-swap candidates, precisely to avoid double-counting the two largest
opportunities in the register. The result:

> corrected hindsight final roster is closer to exact P than its source entry on
> **41 slates** and closer than the selected weekly best on **27**; mean distance
> from P is still **5.15 player swaps**

That is the right shape of answer — **partial overlap, not equivalence** — and
the disposition draws the correct conclusion: they "must not be added as
independent opportunity sizes." That single sentence prevents a real
double-counting error in the charter.

**1.3 Realistic recourse sizing is in flight**, with a point-in-time scorer
being built to reconstruct what was actually knowable at each lock stage. That
was the item I flagged as leaving the register's largest number unconvertible.
Correctly framed as "descriptive/prospective evidence."

---

## 2. Suggestions on what is running now

### 2.1 The 5.15-swap distance deserves one more cut

Mean distance from P of 5.15 swaps is reported as a single number. It is more
informative split:

- **By slate**, against whether that slate's first failed layer was
  construction. If recourse closes most of the distance precisely on the slates
  where construction failed, the two are more coupled than the mean suggests.
- **By position**. Are the residual 5.15 swaps concentrated in the *late-game*
  slots recourse can actually reach, or in the *early* core it cannot? Only the
  former is addressable by any recourse policy; the latter is a hard ceiling on
  how much recourse can ever recover of the construction gap.

That second split is the one that matters. It converts "partial overlap" into a
number: the fraction of the construction gap that recourse is *structurally
capable* of reaching. Without it, the register still cannot say how much of the
79 points recourse addresses.

### 2.2 Realistic recourse — report the policy-class gap, not only the value

When the realistic figure lands, report three numbers rather than one:

1. **hindsight ceiling** (corrected) — realized late outcomes;
2. **realistic recourse** — early results known, late games simulated;
3. **naive re-optimisation** — the greedy "re-run the optimizer at 4 p.m."
   policy every commercial tool already implements.

The gap between 2 and 3 is **the part attributable to being smarter about
recourse**, and it is the only part that represents an edge over the field,
since the field also late-swaps. The gap between 1 and 2 is the unreachable
part. Reporting only 2 makes it impossible to tell whether the value comes from
recourse *at all* or from recourse done *well*.

This matters for the prospective program: if naive re-optimisation captures most
of realistic recourse, the engineering effort belongs elsewhere and the finding
is "turn on late swap," not "build a recourse-aware constructor."

### 2.3 Liveness should drive the first-stage design question

The forensic and the recourse work both compute per-stage liveness. The design
question that follows has not been asked: **is the incumbent book's liveness
profile close to optimal for a recourse policy?**

A recourse-aware first stage wants entries that are decisively alive or
decisively dead by the first swap point, because a "medium" entry wastes its
option. Measuring the incumbent's distribution of live-entry counts — and
whether high-liveness slates are the ones where recourse gains most — tests
whether the current construction is accidentally well-suited or badly suited to
recourse. That is a cheap descriptive cut over data already produced, and it is
the empirical basis for the "polarised early risk" hypothesis rather than
asserting it.

---

## 3. On the SIS player-grain feasibility pass

The disposition is careful and correct: it establishes that the player-grain
surface supplies volume denominators and identities, explicitly does **not**
establish predictive value, cannot change the money policy, and licenses only
one bounded acquisition plus a score-free G0/G1 protocol, with any pass leading
to a 2026 shadow rather than retrospective promotion. That is the right ladder.

Two cautions before the next protocol is frozen.

**3.1 The prior should be low and stated.** Every SIS mechanism tested so far
has failed, including boom/bust — the most distinct field by the project's own
outcome-blind screen (`r = 0.19` and `−0.08`, against `0.4573` for the column
previously called most distinct and `0.8803` for the one rejected as redundant).
The player-grain data is a better *denominator*, but the closures to date were
not caused by missing denominators; they were caused by marginal-channel
insertion. If the next protocol inserts player-grain coverage as a marginal
feature, it inherits a dozen failures.

**3.2 The only version worth running is copula-channel.** The stated plan —
score-free against the G0/G1 dependence scorecard with QB-WR, QB-TE, WR-WR,
RB-RB and multiplicity metrics — is the right one, and it should be held to
strictly. But note the target has moved: the dependence error is now a **shape**
error, under-coupled at the hub and over-produced at multiplicity ≥4. So the
gate must be **absolute-log error on both sides**, exactly as the competitive-WR
protocol correctly specified, and `>=4` should be reported even though it cannot
gate. A directional "increase coupling" gate would pass something that worsens
the worst cell.

**One thing to verify before freezing:** the G0/G1 reference values must come
from a **post-`26e73c5` run**. Two TD arms died on stale pre-repair references,
and this protocol depends on the same scorecard.

---

## 4. One structural suggestion the current queue does not cover

The forensic says construction is 79 of the ~88 lost points, and the disposition
correctly queues "a separate fixed-budget candidate-reallocation shadow …
without fitting its weights to these outcomes."

That is the right item. One addition to its design:

**Reallocation needs a target, and the P-oracle supplies one.** Rather than
reallocating budget between existing generator tags by their historical yield —
which risks fitting to these outcomes — derive the target from *structure*: the
characterisation of what P-oracle lineups look like that generated candidates do
not (games spanned, largest team block, stack shape, positional spend, salary
distribution).

If P-oracles systematically occupy a structural region the generator's
constraints exclude, then the reallocation is not "more `boom`, less `lev`" but
"generate in this region at all." That is a materially different intervention
and it is derivable from structure rather than from yield, which keeps it clear
of outcome fitting.

The constraint-attribution test — would the P-oracle have been generable under
each production construction rule in turn — is the cheapest way to find out, and
it is the one analysis that could name a specific rule as the cause of the 79
points.

---

## 5. Summary

| # | suggestion | cost |
|---|---|---|
| 1 | Split the 5.15-swap P-distance by **early vs late slots** — bounds how much of construction recourse can ever reach | low |
| 2 | Report **naive re-optimisation** alongside realistic recourse — separates "late swap works" from "recourse-aware construction works" | low |
| 3 | Measure the incumbent book's **liveness profile** — tests the polarised-early-risk hypothesis instead of asserting it | low |
| 4 | Hold the SIS player-grain protocol to the **copula channel**, with two-sided absolute-log gating and post-`26e73c5` references | — |
| 5 | Derive the reallocation target from **P-oracle structure**, not historical tag yield | low |

Nothing here changes the adopted policy, and none of it is a historical arm.
