# Verification: independent mechanism queue dispositions

Date: 2026-08-14. Independent verification of the claim that G3, the SIS
team-defense schema path, Route marginal, Route component rank and R2 midpoint
shrinkage all hold terminal frozen dispositions, and that SIS pass-tail is the
only active historical score experiment.

**No code was changed. No outcome was read.** Every check below reads
dispositions, execution IDs and provenance only.

---

## 1. The claim verifies

| item | evidence | status |
|---|---|---|
| **G3** | score-free Stage A execution `g3-participation-allocation-v1-tl2cr`; handoff records "With G3 closed…" | ✅ terminal |
| **Route marginal** | `tabpfn-route-channel-final-served-fails` | ✅ terminal |
| **Route component rank (I1)** | `route-rank-dependence-i1-fails` | ✅ terminal |
| **R2 midpoint shrinkage** | `route-rank-dependence-r2-fails`, execution `route-rank-dependence-r2-v1-gkbtw` | ✅ terminal |
| **SIS team-defense schema path** | closed at the schema gate | ✅ terminal, **but narrowed — §2** |
| **Pass-tail is the only active score experiment** | pass-tail exact-80 at 25/30 cells; Phase S complete at 30/30 with ASOE selected; multi-seed I2 recorded as "not-yet-launched"; Phase R harvested | ✅ correct |

The sequencing conclusion follows and is sound.

---

## 2. One phrase to tighten

Describing the SIS team-defense schema path as flatly "terminal" is true but
risks reintroducing precisely the over-broad reading its reconciliation was
written to prevent. The **binding** kill-list wording is narrower:

> Team Pass Defense Totals, Wide/Slot × Man/Zone, team/game grain: closed only
> as a source of coverage-snap-normalized efficiency because the export lacks
> coverage snaps and targets. `Att`-composition ASOE and player/defender-grain
> denominators remain separately testable under new protocols.

That narrowing has already been vindicated. **The ASOE mechanism the original
queue consequence would have foreclosed subsequently ran and was selected** —
Phase S completed all 30 cells and the frozen tail-first decision selects SIS
alignment-based target allocation. Under the broader reading, that adoption
would never have been attempted.

**Recommendation:** whenever this item appears in a summary, carry the
qualifier with it. "The schema path is closed" and "SIS team defense is closed"
are different statements, and only the first is true.

---

## 3. What the three Route dispositions establish together

More consequential than the queue summary conveys.

The channel-separation recommendation was implemented, and **both channels have
now been tested, and both failed**:

| channel | insertion point | disposition |
|---|---|---|
| marginal | TabPFN feature list | `tabpfn-route-channel-final-served-fails` |
| rank / copula | component model | `route-rank-dependence-i1-fails` |
| rank / copula, shrunk | midpoint shrinkage on ranks | `route-rank-dependence-r2-fails` |

R2 is a **strong negative, not a null**. It preserved marginals exactly —
`0.0` maximum sorted-marginal delta, player means within `7.11e-15` — while
making dependence substantially worse:

| family | treatment / control loss ratio |
|---|---:|
| equal-weight mean | **2.073476** |
| multiplicity | 4.331711 |
| role-pair | 2.096520 |
| primary-broad | 1.932749 |
| joint-q90 Brier | 1.001729 |
| variogram | 1.004671 |

QB-WR/QB-TE hub error rose from `0.169897` to `0.216526`, with material
regressions in QB_TE, QB_RB, WR_WR and RB_RB.

**Consequence:** Route share is now genuinely closed on the historical panel in
a way the earlier component arm alone did not establish. The earlier result was
a single-channel test whose channel was ambiguous; these three together close
both channels explicitly. Only the 2026 prospective shadow remains.

This is worth stating in the closure record, because "Route share failed" and
"Route share failed in both the marginal and rank channels, with the rank
channel actively harmful under shrinkage" support very different future
decisions.

---

## 4. Implementation issue

`reports/tabpfn-sis-pass-tail-runs/20260814-sis-pass-tail-exact80-v1/executions.txt`
is **modified and uncommitted**.

That file is the live execution ledger for a 30-cell panel currently mid-flight
at 25 released cells. The mapping from execution ID to `(arm, replicate,
season)` for the released cells therefore exists **only in the working tree**.

Two reasons this matters more than usual:

- `CLAUDE.md` is explicit that local-only state is "supporting evidence, never
  the sole handoff," and this is the authoritative record of a running
  experiment;
- the Phase S experience showed what reconstruction costs — twenty execution
  IDs substituted by hand, in the one place a hand error would be least
  detectable.

**Recommendation:** commit the ledger at each release batch rather than at panel
completion. It is a one-line change to the release loop and it removes the only
piece of this panel's state that a machine loss would destroy.

---

## 5. Recommendations already adopted

Recorded because both were flagged as blocking and both are visibly in place:

- **Hard ten-cell concurrency cap** on the pass-tail panel, replacing the
  30-cell burst that produced a 67% infrastructure failure rate in Phase S.
- **Manifest-verified cell assignment** — the Phase S finisher verified every
  immutable image, code SHA, arm, replicate, season, panel and execution before
  the analyzer ran. This was the blocking item from the Phase S review, since a
  mis-assigned cell in a factorial would corrupt the seed-variance envelope and
  the interaction term while leaving every row internally valid.

The sequencing argument also holds **operationally**, not only by protocol: a
second concurrent historical arm would contend for exactly the capacity whose
exhaustion caused the twenty Phase S infrastructure failures. That is a stronger
justification than the closure-ordering rationale alone, and worth recording
alongside it.

---

## Summary

The queue statement is accurate. Two amendments to how it is written down:
attach the narrowing qualifier to the SIS schema item so it is not read as
closing SIS team defense, and record the Route closure as covering **both**
channels rather than as a single failed arm. One operational fix: commit the
in-flight execution ledger per batch.
