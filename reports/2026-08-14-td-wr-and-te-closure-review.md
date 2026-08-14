# Review: competitive-WR closure, TE prerequisite, and queue exhaustion

Date: 2026-08-14. **No code was changed. No new outcome was queried.**

---

## 1. Both closures are sound

**Competitive WR allocation.** Stage T returned invalid, so unadjudicated — and
the protocol correctly refuses a post-result repair on the same outcomes.

**TE-only prerequisite.** Does not pass, on three independent grounds: no stable
repaired-path QB→TE deficiency to target, no supported TE–TE structure on which
to freeze a competitive law, and no passed WR mechanism to compose with.

I agree with both, and with the conclusion that the preregistered historical
mechanism queue is exhausted.

## 2. The ≥4 diagnostic earned its place

I recommended adding multiplicity `>=4` as a **mandatory but ungated**
diagnostic, on the reasoning that it carries the largest current-path error
(`6.175` simulated against `2.333` realized) and is the cell that generates the
biggest lineups, so a treatment concentrating WR outcomes onto high-QB worlds
could plausibly worsen it invisibly.

It was added, and **it moved away from realized dependence.**

That is exactly the failure mode the gate structure could not have caught, since
`>=4` is unsupported at seven realized events and cannot gate. Without it the
disposition would have recorded an adverse movement in the most consequential
cell as simply absent. Worth keeping as a standing diagnostic on any future
dependence mechanism.

It also confirms the concern I raised when the arm was proposed: the competitive
construction was meant to strengthen QB→WR *without* forcing broad co-booming,
and the `>=4` movement says it did not achieve that separation.

## 3. Record the disclosed direction, not only the invalidity

The disposition is right that invalidity means unadjudicated. But this closure
differs from the two before it in an important way, and the record should say so.

| TD arm | outcome | disclosed direction |
|---|---|---|
| v2 final-served | invalid (float precision) | gates passed; genuinely untested |
| v3 rank-coupling | invalid (stale references) | diagnostic only; not adjudicable |
| **v4 competitive WR** | invalid (summation-order comparison) | **adverse on every frozen gate** |

For v4 specifically: the variogram worsened `1.422472 → 1.447709` with a paired
95% interval of `[0.016816, 0.033812]` — **wholly unfavourable** — joint-q90
Brier moved slightly worse, every frozen G0/G1 improvement gate was false, and
`>=4` moved away from realized.

So unlike v2 and v3, where invalidity left a mechanism genuinely untested, v4
carries strong disclosed evidence *against*. A future session reading
"unadjudicated" should not infer "promising." I would record that distinction
explicitly, as it was recorded for the earlier ledger closure.

## 4. A pattern worth carrying forward: rank-permutation mechanisms are hard to validate

Three TD arms, three reproduction failures, zero adjudications:

- v2 — control failed `1e-12` variogram reproduction after a shared
  floating-point transform changed;
- v3 — control failed the frozen G0/G1 reproduction gate in 48 values against
  stale pre-repair references;
- v4 — an accidental bitwise frame comparison, where rank-only permutations
  change summation order.

The generic lessons recorded in the v4 result — snapshot control arrays before
loading intervention books, and audit simulated means with the registered
numerical tolerance rather than a bitwise comparison — are correct and worth
keeping.

The meta-lesson is more general and belongs in the forensic register:
**rank-permutation mechanisms are unusually difficult to validate, because
permuting ranks changes summation order and therefore floating-point sums,
which then trips tight or bitwise invariants that were designed for
value-preserving changes.** Any future mechanism of this class should budget for
it and adopt order-invariant comparison from the outset rather than discovering
the problem after an execution.

Three arms lost to this is expensive, and none of the three losses was
scientific.

## 5. The finding that should be the headline

The TE audit contains, almost in passing, the most important scientific result
of the G-series program:

> there is **no stable repaired-path QB-to-TE deficiency to target**

Combined with QB→WR moving from `1.053` to `2.418` on the repaired path, the
picture is now coherent and it is not the one the program operated under for
weeks: **the `(game, team)` allocation-unit defect repaired in `26e73c5` was
responsible for most of the apparent teammate-dependence deficit across the
board — WR and TE alike.**

G0's headline finding, G1's targets, G2's disposition and the entire ledger
motivation all rested on a deficit that was substantially an artifact.

That belongs at the front of the forensic code/evidence chronology as a labelled
pre-repair / post-repair boundary, not as a line inside a TE prerequisite audit.
It is the single most consequential thing the dependence program produced, and
it will be invisible to anyone reading the arm ledger in order.

## 6. On proceeding to forensics

Agreed. With SIS marginal, Route, pass-tail, selector, multi-seed, G-series, TD
and the TE follow-up all terminal, the historical queue is genuinely exhausted.

One item from the pre-forensic exhaustion review remains open and it is **not**
a historical arm: **Odds API market expansion** — alternate team totals and
alternate game totals, which give the market-implied *distribution* of team
points rather than the point estimate currently used, plus the volume markets.
Ten of roughly twenty-five available markets are stored and the Priority-3
expansion has never been executed.

That is acquisition and prospective work. It does not gate the forensic program
and should proceed alongside it, entered in the opportunity register with its
`prereq` field set so the 2026 charter inherits it rather than rediscovering it.
