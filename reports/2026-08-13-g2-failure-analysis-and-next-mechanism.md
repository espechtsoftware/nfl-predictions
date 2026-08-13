# G2 failure analysis: why the WR channel could not activate

Date: 2026-08-13. Review of the G2 QB-Gumbel result. **No code was changed.**

---

## What G2 actually showed

The headline is recorded as negative, but three of the four registered
dependence measures moved favourably with intervals wholly on one side of zero:

| metric | control | treatment | Δ | paired 95% interval |
|---|---:|---:|---:|---|
| joint-q90 Brier | 0.018490246 | 0.018467120 | −0.000023125 | [−0.0000403, −0.0000072] |
| variogram p=0.5 | 1.434919238 | 1.433817879 | −0.001101359 | [−0.0018369, −0.0003663] |
| G0 supported abs-log-error sum | 3.312852 | 2.747302 | −0.565550 | — |
| G1 weighted abs-log-error sum | 6.944177 | 5.965699 | −0.978478 | — |

And the per-cell detail is stark:

| cell | control sim | treatment sim | realized | abs-log-error Δ |
|---|---:|---:|---:|---:|
| QB→TE | 1.0788 | **1.7438** | 2.3709 | −0.480236 |
| QB→WR | 1.0644 | **1.0644** | 3.3228 | **0.000000** |

**This is the first mechanism in the program to move a dependence metric with a
clean interval.** It repaired well over half the QB-TE miss. It did literally
nothing for WR — the treatment value is identical to control to four decimals,
because score-free calibration selected no WR activation at all.

## Why no WR activation is not a search failure

The calibration did not fail to find a WR setting. **A single shared factor
cannot produce the structure G0 measured, and the calibration correctly
discovered that.**

For a one-factor model `X_i = a_i·F + ε_i`:

```
corr(X_i, X_j)  ∝  a_i · a_j
```

If the factor couples QB↔WR1 positively and QB↔WR2 positively, then
`a_QB·a_WR1 > 0` and `a_QB·a_WR2 > 0`, which **forces** `a_WR1·a_WR2 > 0` —
hence WR1↔WR2 positive. The same monotone logic holds for a Gumbel link: a
shared factor with positive upper-tail dependence to several variables induces
positive upper-tail dependence among them.

G0 measured **QB→WR = 3.3228** and **WR–WR at or near independence**. Those two
facts are *jointly unachievable* with one factor loading on all receivers. Any
θ_WR > 0 buys a QB-WR improvement and pays for it with a WR-WR degradation, and
the aggregate objective nets out unfavourable. Zero is the correct answer to the
question that was asked.

**This also explains why TE worked.** A team has essentially one relevant tight
end, so there is no TE-TE side effect to pay for. A single loading target is
exactly the case where a one-factor mechanism is well specified — and it
delivered, cutting the QB-TE error by 61%.

So the disposition is right, but the reason matters: **the mechanism class is
mis-specified for WR, and that was diagnosable a priori.** Another factor
variant — different link family, different θ grid, per-player loadings — will
hit the same wall, because the wall is structural rather than parametric.

## What class *can* produce the observed structure

A **shared production ledger with competitive allocation**:

1. Draw the team's passing production (volume, touchdowns) once. This couples
   the QB positively to *every* receiver — shared volume.
2. Allocate that production among receivers competitively — multinomial or
   Dirichlet. At fixed team production this induces *negative* WR-WR: one
   receiver's eight targets are another's two.
3. Net effect: **QB ↗ each receiver positive; WR–WR ≈ neutral**, because the
   positive shared-volume force and the negative competition force cancel.

That is precisely the structure G0 measured, and it is the same two-force
cancellation that explains why WR-WR sits near 1.0 in reality while QB-WR sits
at 3.3.

## The mechanism already exists in the codebase

`simulate.py` implements `TD_LEDGER`:

> "a passing TD and its catch are ONE EVENT. The ledger draws each (GAME, TEAM)
> unit's passing-TD count once (game-factor scaled) and allocates the same
> totals to catchers and passers."

That is exactly the class described above. It is **off in production**
(`TD_LEDGER: ""` in `production_policy.py` and in the served-tail environment).

It was buried in Addendum 84 (2026-08-05) at 18 vs 22 tail weeks, and again as
TDLEDGER2 at 19 vs 27 after defect repairs. Both verdicts were reached:

- **before** G0/G1 existed, so against no dependence scorecard at all;
- **before** per-position served calibration was adopted;
- **before** active-only TabPFN labels and the fitted-K allocation law;
- and on a **lineup-score** gate rather than a score-free dependence gate.

The project's standing rule — *"verdicts don't transfer across a changed
downstream stage"* — applies directly. Every stage downstream of the dependence
law has changed since those verdicts, and the question now being asked is a
different one: not "does this improve exact-80 tail weeks" but "does this reduce
the measured QB-WR dependence error."

## Recommendation

**Preregister a score-free ledger-coupling arm against the G0/G1 scorecard,
before any further factor variant.**

Design notes:

1. **Motivate it from the impossibility argument, not from G2's result.** The
   G2 protocol correctly requires that any future QB-WR mechanism be "newly
   motivated" and "separately preregistered" rather than a post-result retune.
   A ledger is a *different mechanism class*, and its motivation is the
   structural argument above — that a one-factor model cannot represent
   QB↗WR with WR⊥WR. State that argument in the preregistration so the arm is
   plainly not a G2 retune.
2. **Gate it score-free**, on the same registered cells G2 used: QB→WR and
   QB→TE lift error, ≥2/≥3 multiplicity, WR-WR and RB-RB as
   must-not-worsen guards, plus joint-q90 Brier and variogram. No lineup panel.
   This costs no panel budget and cannot mine the 107 outcomes.
3. **Require WR-WR not to worsen.** That is the specific failure mode a shared
   factor has and a ledger is claimed to avoid; making it an explicit gate turns
   the structural argument into a falsifiable prediction.
4. **Expect TD-only coupling to be partial, and say so in advance.** QB-WR
   dependence flows through yardage as well as touchdowns — a 60-yard completion
   feeds both stat lines. A TD-only ledger captures one channel. If it moves
   QB-WR materially but not fully, the designated follow-up is a **passing-yards
   ledger** on the same principle, not a θ retune. Naming that now prevents a
   post-result choice.
5. **Carry G2's TE result forward rather than discarding it.** The QB-TE
   repair was real and clean. If a ledger arm passes, the natural terminal
   mechanism may be *ledger for WR + factor for TE*, since the factor is
   well-specified exactly where there is a single loading target. Preregister
   whether the two compose or whether the ledger subsumes TE.

## Secondary observation

The effective-rank diagnostic is now frozen against the unchanged incumbent,
which is correct given G2 did not change the dependence law. One consequence
worth recording in that run: because the incumbent simulator under-states
QB-receiver dependence by roughly 3× at the WR cell, its participation ratio is
an **upper bound** on the book's true independent-bet count. If a ledger arm
later passes, re-running the diagnostic should show the number *fall*. That
before/after pair is a cheap and direct check that a dependence repair actually
propagates to the portfolio — which is the thing six marginal arms failed to do.

---

## Summary

G2 is a good result recorded as a negative one. It repaired QB-TE substantially,
moved two aggregate dependence metrics with clean intervals, and — most
usefully — demonstrated that the WR channel is not reachable by a shared factor.
That is a structural finding, not a tuning failure, and it points at a specific
alternative mechanism class whose implementation is already in the repository
and whose prior burial does not transfer under the project's own downstream-change
law.
