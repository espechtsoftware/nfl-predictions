# Dependence repair — design log (DRAFT, not frozen)

**Status:** design direction recorded 2026-08-19, same day as the
remeasurement verdict. No law change is licensed; the remeasurement
disposition licenses only the sparse-ledger PROTOTYPE
(`sparse_ledger_prototype_licensed=true`,
`exact80_scoring_licensed=false`). Any adopted repair runs through the
standard frozen one-shot discipline with its own protocol.

## The measured target (remeasurement `20260817-…-v1`)

log(simulated/realized) teammate co-boom, 54 slates, cluster-bootstrap
supported, reproduced in ≥3 of 5 blocks:

| Cell | log(sim/real) | Direction of repair |
|---|---|---|
| multiplicity ≥2 / ≥3 / ≥4 | +0.26 / +0.74 / +1.65 | shrink generic team coupling, hardest at high multiplicity |
| QB–RB | +1.17 | shrink |
| RB–RB | +1.49 | shrink |
| TE–TE | +1.34 | shrink |
| WR–WR | +0.69 | shrink |
| QB–TE | +0.24 | inconclusive — do not tune |
| **QB–WR** | **−0.26** | **raise** |

Success criterion for any candidate repair (to be frozen): all
material-miss cells move inside their equivalence bands (or strictly
toward them without any cell regressing), measured by the SAME
remeasurement instrument on a fresh protocol version, plus two guard
metrics that must not regress: book-tail expected-exceedance calibration
(currently realized 6 vs expected 2.76 at 210 — under-coupled QB–WR is
plausibly the cause) and the optimum-realism metric (median +19.3
never-realized points per deep-world optimum).

## Candidate mechanisms (pick ONE lever per frozen arm)

1. **Factor split:** shrink the shared team game-factor variance and add
   a QB→pass-catcher pair factor concentrated on WRs. Mechanically small
   (game_sim team factors + draw shaping); directly matches the sign
   pattern (all generic cells over, QB–WR under).
2. **TD-allocation coupling:** couple TD placement to the QB's passing
   outcome rather than a team-level pool. Ledger caution: parametric TD
   coupling (TDLEDGER2) was validly buried at 19 vs 27 in the OLD
   universe/selector — that verdict does not transfer across the changed
   stack (post-ensemble law), but expectations must be modest and the
   old failure mode (season pooling) must be designed out.
3. **Usage-share reallocation:** condition WR target shares on QB boom
   draws (Dirichlet tilt). Heavier surface; only if 1 fails.

## Sequencing

Design freeze AFTER the all-boom S read (its result decides whether the
generation lane or the law lane owns the next heavy build slot). The
remeasurement instrument itself is frozen and reusable; each candidate
repair gets: outcome-blind mechanism census (co-boom rates on simulated
worlds only) → frozen protocol → one-shot remeasurement + guard metrics
→ candidate-arm C/S test only if the law-shape gate passes.
