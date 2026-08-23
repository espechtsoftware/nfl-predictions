# Review: SIS receiver-copula calibration failure

Date: 2026-08-16. Review of the terminally invalid/inconclusive receiver-copula
calibration harvest. **No code was changed. No outcome was queried.**

---

## 1. The closure is correct

All seven treatment cells preserved exact marginals and passed implementation
invariants, but the frozen 2022 calibration book contained no supported
multiplicity `>=2` / `>=3` cells, so every grid cell was ineligible, no strength
could be selected, and held-out evaluation is not licensed.

**Preserving that closure rather than widening the support rule after seeing the
grid is exactly right.** Relaxing an eligibility threshold once you know it
failed is the post-hoc adjustment the entire discipline exists to prevent, and
the temptation is strongest precisely when — as here — the mechanism is
otherwise clean. Nothing below asks for that to be reconsidered.

## 2. Scope the record: this is a third category

The treatment ran, preserved marginals, and passed every implementation
invariant. **The mechanism was never adjudicated — the harness could not select
a strength.**

That is distinct from both a valid pass and a valid fail, and it is the same
category as the TD-ledger arms that died on reproduction rather than on
evidence.

Worth stating explicitly in the closure, because *"the receiver-copula path is
closed"* reads to a future session as **tested and rejected**. What actually
happened is **untestable under this calibration design**. The distinction
determines whether a differently-designed future protocol is a forbidden retry
or a legitimately new question.

Note the precedent: the TD-ledger family was ultimately closed with a
**merits-based** reason layered on top of the protocol one — adding coupling to a
simulator that already over-couples at high multiplicity is wrong-signed. This
closure currently carries only the protocol reason. §4 is about supplying the
missing half.

## 3. The cause was arithmetic, not luck — and a template fix follows

An empty `>=2`/`>=3` grid on a single calibration season is a mismatch between
the calibration sample and the grid resolution, not an unlucky draw.

G0 required **2,405 team-weeks across the full six-season panel** to support
`>=3`, and still declared `>=4` unsupported at seven realized events. One season
is roughly a sixth of that population, and crossing it with a receiver-pair grid
subdivides those events again. The cells were never going to fill.

**Recommendation — for the protocol template, not this arm:** before freezing any
gate whose eligibility depends on cell-level counts, run a **pre-flight support
census** on the calibration population. Count how many qualifying events land in
each required cell. If any required cell is empty or below floor, the protocol is
unrunnable as written, and that is known before an image build and an execution
are spent.

This is permitted under the project's own established boundary. The Fantasy
Points coverage-fit protocol reported `1,709/5,927` supported rows (28.83%) as an
**outcome-blind implementation audit before its gate ran**, and amended an
availability threshold on that basis while explicitly recording that "no feature,
support threshold, model, outcome gate, or target population changed."

The boundary that makes it legitimate: a support census counts **support only**
— row and event eligibility — and never the gate metric. Lift ratios, error sums
and threshold counts stay unread. That line is already drawn in this project and
should simply be applied earlier in the protocol lifecycle.

## 4. Before closing the file: disclose the non-decisional direction

The competitive-WR closure handled this well. It was invalid and therefore
unadjudicated, but it recorded that the treatment worsened the aggregate
variogram with a wholly unfavourable paired interval, that every frozen G0/G1
improvement gate was false, and that the ungated `>=4` diagnostic moved away from
realized dependence. Nobody reading it later can mistake "unadjudicated" for
"promising."

Seven treatment cells ran here with valid marginals. Even with no strength
selected, the **direction** each cell moved on QB→WR, QB→TE, WR–WR and the
multiplicity cells is computable from artifacts already produced, and it should
be recorded — clearly labelled as **non-decisional and unable to adjudicate**.

Why it matters concretely: the current dependence error is a **shape** error —
the hub is under-coupled (QB→WR 2.42 simulated against 3.32 realized) while high
multiplicity is **over**-produced (`>=4` at 6.18 against 2.33 realized).

- If the receiver-copula cells push multiplicity **up**, the mechanism is
  wrong-signed regardless of how it is calibrated, and the closure becomes
  merits-based rather than merely procedural — which is a materially stronger
  and more durable disposition.
- If they lift the **hub** without inflating multiplicity, that is a genuinely
  promising signal, and it should be preserved as motivation for a
  differently-designed prospective protocol rather than discarded with the
  harness.

Either outcome converts a bare "inconclusive" into something a future session can
act on, at the cost of reading artifacts that already exist.

## 5. Summary

| item | recommendation |
|---|---|
| The closure | Keep it. Do not weaken the support rule after seeing the grid. |
| The record | Say **untestable under this design**, not tested-and-rejected. It is a third category. |
| The template | Add a **pre-flight support census** to any protocol with cell-dependent eligibility; the FP coverage-fit audit is the precedent for its legitimacy. |
| Before filing | Record the **non-decisional direction** of the seven cells against the shape error, as the competitive-WR closure did. |
| SIS generally | Unchanged — the source remains available for separately specified mechanisms; the marginal channel stays closed. |
