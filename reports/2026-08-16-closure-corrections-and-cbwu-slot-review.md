# Review: closure corrections, the CBWU slot swap, and exact-P

Date: 2026-08-16. **No code was changed. No outcome was queried.**

---

## 1. The closure corrections are right

All four adopted:

- keep the frozen closure;
- classify it as **untestable under this design** rather than tested-and-rejected;
- preserve the shape signal for a genuinely new prospective design;
- require outcome-blind support censuses before future cell-dependent protocols
  are frozen.

### The favorable signal changes the disposition, and the record should say so

The disclosed direction came back **favorable**. That is the branch that matters,
because it means the closure is **procedural only** — the mechanism was never
shown to be wrong, merely un-adjudicable under this calibration design.

Contrast with the TD-ledger family, which ultimately earned a **merits-based**
reason on top of its procedural one: adding coupling to a simulator that already
over-produces high multiplicity (`>=4` at 6.18 simulated against 2.33 realized)
is wrong-signed no matter how it is calibrated. **The receiver copula has no such
reason against it.**

"Closed" plus "favorable signal preserved" is an unusual pairing, and a future
session skimming the ledger will collapse it into a plain rejection unless the
record states the distinction in the disposition itself — not only in a linked
review. Suggested wording for the closure line:

> Procedurally closed: untestable under this calibration design. The mechanism
> was **not** shown to be adverse; its disclosed non-decisional direction was
> favorable and is preserved as motivation for a separately designed prospective
> protocol.

## 2. The CBWU slot swap carries a sequencing hazard worth closing explicitly

`CBWU` is a live component of the adopted policy
`classic-k1-role12-boom40-poscal-cbwu-v4`. An order-invariant repair to it is
therefore **not** an independent research arm — it touches production.

The specific hazard: **the entire forensic decomposition is measured against the
current CBWU.** The H/P/C/S layers, the corrected recourse ceiling, the
5.15-swap P-distance, and the exact-P census all hold frozen references to that
configuration. If the repair changes CBWU's output at all:

- the forensic result describes a baseline that no longer exists; and
- the corrected exact-P census would land against a **third** configuration —
  neither the one the decomposition used nor the one production runs.

This is the same class of failure as the stale pre-`26e73c5` G0/G1 references,
which invalidated two TD arms. The pattern is generic: **repair an upstream
component while downstream analyses hold frozen references to it.**

### The resolution is a proof, not an assumption

The name suggests this is a comparison-and-tolerance fix — changing *how*
results are compared rather than *what* is computed. If that is right, the
repaired path should produce **byte-identical books**, and demonstrating that
closes the hazard completely.

So:

1. apply the repair;
2. **verify the CBWU book reproduces the current one byte-for-byte** on the
   forensic's exact panel and slate set;
3. if identical — record the identity receipt and proceed; there is no hazard,
   and the repair is confirmed to be what it claims;
4. if **not** identical — the forensic's baseline has moved. Either hold the
   repair until the forensic completes, or re-run the affected components
   against the new baseline and re-state which configuration each number
   describes.

The thing to avoid is deciding between 3 and 4 *after* seeing which is more
convenient. Fix the rule now, before the repair runs.

Worth noting the repair is worth doing regardless: summation-order sensitivity in
rank-permutation paths has already cost this project a full arm (the
competitive-WR closure died on "an accidental bitwise frame comparison when
rank-only permutations can change summation order"). Making the comparison
order-invariant is the correct generic fix. Only its **timing** relative to the
forensic is in question.

## 3. exact-P has now failed twice, on the highest-value open item

Two operational failures — a BigQuery alias defect, then a source-identity
failure — on the analysis that would name **which production construction rule
excludes the P-oracle**, i.e. the cause of the 79-point construction gap that
holds 79 of the ~88 lost points.

That combination — highest value, two consecutive operational failures — is
worth a moment on approach rather than a third identical retry.

**Suggestion: run a narrow version first.** One construction constraint, one
season, minimal grid — enough to prove the roster-source resolution and the
identity plumbing work end to end. Then scale to the full census.

The cost is one short execution. The benefit is that a third failure, if it
comes, arrives cheaply and diagnoses the plumbing rather than consuming another
full run. Given that the exact-P census is currently the binding item on the
project's largest identified opportunity, derisking it is worth more than
completing it a day sooner.

## 4. Summary

| item | position |
|---|---|
| Four closure corrections | Agree; adopt as stated |
| Favorable-signal wording | Put the "not shown to be adverse" distinction in the **disposition line**, not only in a linked review |
| CBWU repair | Correct fix, and worth doing — but **freeze the byte-identity rule before it runs**, and treat a non-identical result as a moved forensic baseline |
| CBWU slot use | Reasonable use of a released slot, given the identity rule above |
| exact-P | Run a **narrow plumbing-only pass first**; two operational failures on the highest-value item argues for derisking over a third full attempt |
