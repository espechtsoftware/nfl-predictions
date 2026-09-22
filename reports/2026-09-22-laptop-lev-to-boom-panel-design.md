# Design proposal (NOT frozen): re-test an all-`boom` pool under the live selector, after Sunday

For the operator and production. Nothing here is frozen or launched; freezing a PREREG, choosing banks
and launching through the launcher registry are production's and the operator's decisions. This
collects the evidence and a design, so the post-Sunday panel can be frozen in one sitting.

## Why re-test — the evidence so far

| source | finding |
|---|---|
| lab 036 (diagnostic, 89 slates) | `lev` rosters are the worst-calibrated tail rosters: realized ≥194 is 36% of predicted (boom 74%) |
| lab 045 / **PREREG-017** (72 slates × 3 banks, old K=1 selector, 200 solves) | ABc (lev 0, boom 200, ceiling order) **+1.88 fam[−0.14, +3.52]**, every bank positive (+2.72/+2.35/+0.56), LOSO +1.37…+2.64, all secondaries pass; **failed the primary family-wise bound by 0.14**, so not nominated. AB (total order) +0.49, unresolved |
| lab knowledge graph `q:lev-ceiling-error` (twelve 071/078 panels) | lev 3.2% of selections, **0** hits at 210+/220+ vs boom 117/30 |
| 2026 W2 pool (laptop, `fec39fc9`) | lev 0 of 25.7 expected top-1%; clean lev 0 of 8.0 (P = 0.0002) |
| 2026 W1 pool (production, `b1af8137`) | lev top-1% lift 0.94 (≈ null), but **0 at ≥220 and ≥230** (boom 6 and 3) |
| cost (production, sleeve-pilot §6) | lev's solve cost grows ~n^2.5 and **is what makes D12800 a ~10-hour job**; 12,800 boom solves take ~17 min |

**Why the old verdict does not settle it:** PREREG-017 ran on the K=1 selector at 200 solves. The live
package uses the `dual_emax` selector at a far larger dose. The post-selection law says a verdict
does not transfer across a changed downstream stage, so the question is open at the live
configuration, not closed.

## Proposed design

- **Arms (a single contrast, to avoid the multiplicity that sank 017's primary):**
  `CTRL` = the live generator as shipped (lev + boom at the live split and dose) vs
  `ALLBOOM_CEIL` = the same total solve count, all `boom`, in **ceiling order** (017's best geometry).
  The total-order variant is secondary and descriptive only.
- **Held fixed:** frame, simulator law, the `dual_emax` selector, K, stack/env constraints, the QB gate
  and availability rules as live in Week 3, co-run on the **same image build**, shared worlds.
- **Panel:** six seasons (2020–2025, or whatever the current standard panel is) × 3 fresh banks; LOSO
  with at most one negative season; per-bank replication rule as in 017.
- **Primary:** the lab's current proxy endpoint at K80 (the one PREREG-053/055/097 use), with raw K80
  max and weeks ≥200/210/220 co-reported.
- **Decision rule (to be frozen):** nominate `ALLBOOM_CEIL` if the pooled interval excludes 0, every bank
  is ≥ 0 and LOSO has at most one negative. Otherwise close at this dose, recording the compute
  saving as a separate operational question.
- **Vacuity check:** confirm the two arms' books differ (017-style byte-identity check); report the
  share of CTRL book slots that came from lev (Week 2: 8 of 97).
- **Preflight (outcome-blind, per CLAUDE.md):** a support census that every slate yields ≥ K unique
  all-boom candidates at the chosen dose and that ceiling order is defined on every frame; one
  production-size smoke of the boom fill loop; the plain full-path smoke at small scale.
- **Compute:** reuse an existing Cloud Run job (rule 5), driven through `scripts/launcher_registry.sh`.
  The all-boom arm is cheap; CTRL's lev solves dominate.

## Reopening condition, stated now

If `ALLBOOM_CEIL` fails, the question reopens only on a new mechanism (for example, lev with a
world-conditional objective), never by re-running the same contrast on new banks.
