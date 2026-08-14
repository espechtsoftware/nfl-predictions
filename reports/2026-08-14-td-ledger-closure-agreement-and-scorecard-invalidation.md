# TD-ledger closure: agreement, and a larger consequence

Date: 2026-08-14. Review of the terminal TD rank-coupling result.
**No code was changed. No new outcome was queried.**

---

## 1. I agree with the closure — and there is a second, stronger reason

The stated ground is correct and sufficient on its own: the unchanged control
failed the frozen absolute `1e-12` G0/G1 reproduction gate in 48 registered
values, with differences up to `+5.138402`. That is not rounding drift and it
cannot be waived after the fact. The arm is unadjudicated and no exact-80 run
is licensed.

**But the result contains a second reason the document does not draw, and it
argues against the mechanism on its merits rather than on protocol.**

The TD ledger was motivated by a specific measured deficiency: the simulator
produced essentially no QB→receiver coupling (`1.053` simulated against
`3.3228` realized), and G2 established that a shared factor mathematically
cannot supply it without breaking WR–WR. An allocation-coupled ledger was the
one mechanism class that could produce the observed pattern.

On the repaired path, that premise no longer holds:

| cell | frozen reference | **current control** | realized (G0) |
|---|---:|---:|---:|
| QB→WR simulated lift | 1.064 | **2.418** | 3.323 |
| QB–RB simulated | 1.057 | **2.597** | — |
| multiplicity ≥3 simulated | 1.013 | **2.377** | 1.835 |
| multiplicity ≥4 simulated | 1.037 | **6.175** | 2.333 |

The simulator now recovers roughly three-quarters of the QB→WR hub on its own.
More decisively, **at high multiplicity it now over-produces co-booming**:
`2.377` against a realized `1.835` at ≥3, and `6.175` against `2.333` at ≥4 —
overshooting by a factor of about 2.6 in the cell that generates the biggest
lineups.

A ledger **adds** coupling. Adding coupling to a simulator that already
over-couples at ≥3 and ≥4 is wrong-signed. So closing the arm is correct not
only because the gate failed, but because the repaired evidence points the
other way.

I would record that explicitly, so a future session does not read
"unadjudicated" as "promising but untested."

---

## 2. The stale-reference finding is larger than a chronology note

The result correctly requires that the stale-reference finding "enter the final
forensic code/evidence chronology so earlier G0/G1-dependent conclusions are not
presented as current-path validations."

That instruction is right, and I would go further on scope. The frozen G0 and G1
references were created on 2026-08-12 from `ee94725` and `64e0428`. Commit
`26e73c5` then repaired finite-Dirichlet season replay from a franchise-wide
season pool to the correct `(game, team)` allocation unit — a genuine
point-in-time defect fix that materially changes within-game dependence.

**Therefore every G-series conclusion was computed on a path with that defect
present.** Specifically:

- **G0's headline** — "the terminal simulator is very nearly teammate-independent"
  — is substantially an artifact of the allocation-unit bug. On the repaired
  path the simulated QB→WR lift is `2.418`, not `1.053`.
- **G1's stable QB-hub scorecard** inherits the same path and its target values
  are not current.
- **G2's disposition** is the most affected. Its calibration selected no WR
  activation while optimising against a simulator that had almost no coupling.
  On a path that already supplies `2.418`, that optimisation faces a different
  surface entirely. The G2 *mathematical* argument survives — a single shared
  factor still cannot produce QB↗WR alongside WR⊥WR — but its *empirical*
  premise does not.
- My own downstream reasoning inherits the same problem, including the claim
  that a run of marginal-arm failures was explained by a near-independent
  copula. That explanation was already weakened by the earlier correction that
  weak dependence reduces leverage rather than blocking propagation; this
  removes most of what remained of it.

**Recommendation:** the forensic chronology should carry an explicit
**pre-repair / post-repair** boundary at `26e73c5`, and every conclusion that
depended on the G0/G1 scorecard should be labelled on the correct side of it.
"Do not present as current-path validations" is right; naming the specific
conclusions makes it actionable.

---

## 3. The new diagnosis is different, and worth stating as a finding

This is not merely an invalidation. The repaired path exhibits a **shape**
error rather than a magnitude error, and that is new information:

- the QB hub is **under**-produced (`2.418` vs `3.323` realized);
- high multiplicity is **over**-produced (`6.175` vs `2.333` at ≥4).

A simulator that under-couples the hub while over-producing four-way
co-booming is mis-shaped in a way no single global coupling parameter can fix —
increasing coupling worsens the multiplicity cell, decreasing it worsens the hub.

That is a genuinely useful characterisation and it belongs in the opportunity
register. It also means **any future dependence work must first re-measure the
G0/G1 targets on the current path**; the existing scorecard cannot gate anything
further.

---

## 4. On the next arm

The adaptive SIS RB opponent run-defense Boom%/Bust% arm at `23fdbba` is
unaffected by all of this. It is a **marginal-channel** arm and does not depend
on the G-series scorecard, so the stale reference does not touch it.

Worth noting alongside: the outcome-blind redundancy screen recorded in
`2026-08-14-pre-forensic-exhaustion-review.md` §4.1 supports it —
`rdef_boom_rate` correlates `0.1922` with `rb_fp_allowed_adj_l6` and
`rdef_bust_rate` `−0.0827`, both substantially more distinct than the `0.4573`
pressure-rate column the project had identified as its most distinct candidate,
and far from the `0.8803` that got pass-defense EPA rejected.

---

## Summary

Agree with the closure, for a stronger reason than the one given: the mechanism
is not merely unadjudicated, it is now wrong-signed against the repaired
evidence. The more important output of this run is not the TD verdict at all —
it is that the **G0/G1 scorecard is stale**, and with it the empirical premise
behind G0's headline, G1's targets and G2's disposition. That belongs in the
forensic chronology as a labelled pre-repair/post-repair boundary, not only as
a caution.
