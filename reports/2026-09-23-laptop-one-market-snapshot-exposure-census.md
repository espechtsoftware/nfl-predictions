# Which lab verdicts rest on the one-market 2023–24 snapshot (read-only census; no outcome re-read)

Follows the finding in HANDOFF `14c71222` (verified by production `6fedd863`, README deficiency row). For 2023–24,
`snap_pitclean_k1` blends a **one-market** price, mostly an anytime-TD line alone, for 3,530 rows: cheap depth players, served
mean 2.72 → 1.64, and 58 QBs whose lone market sits about 5 points under the model. Live production has refused one-market sums
since 2026-09-04.

**Method.** Nothing was re-run and no outcome was re-read. Existing ledger verdicts were read from nfl2 `origin/main` @ `60b7109`
(LEDGER, PREREG files, experiment scripts) to see which cohorts use 2023–24 slates, how they centre, and whether their arms differ in how
they treat cheap or depth players. PREREG-099 and bank 991 were not opened. Two load-bearing claims were verified by hand:
1. **The hsim law calibrates each player's opportunity share to `mean_projection` regardless of `NFL2_CENTER`**
   (`src/nfl2/hsim/world.py:84` `target = frame.mean_projection`; the pilot loop rescales target and carry weights to it). Every cohort with a
   v0.x / V14 / DUAL-law arm or the P_MIX judge therefore carries the defect inside team-opportunity shares, not only in marginals.
2. **PREREG-007 (`experiments/032_market_blend.py:13-14`) compared the snapshot blend (one-market rows included) against model-only.**
   "The market blend is retained" was measured against a *defective* blend; the live-faithful blend (≥ 2 markets) was never compared with
   the model.

**Exposure rule of thumb.** Every mean-centred cohort since 031 includes the 36 2023–24 slates (of 72 or 89). Paired arms that share one
frame and differ only in selection or dose carry the defect in both arms (**low** exposure). Arms that differ in how they treat cheap,
depth or prop-covered players, punts or salary floors, or in whether the hsim law is used, are **not** defect-neutral.

## Most worth re-checking (the operator's / lab's call; none started)
| # | cohort | why it is exposed | status today |
|---|---|---|---|
| 1 | **PREREG-007 (032) market blend vs model** + **PREREG-064 pkg A (092) market-source gate** | the treatment *is* the defective blend; 2024 alone carries the −2.2 result; 064's incumbent MAE and "−1.13 covered-cohort bias" include the defective rows | **adopted** (blend kept); every later cohort builds on it |
| 2 | **PREREG-011 (037) centring proj→mean** | the arms differ exactly in how sub-\$4k rows are centred, and the fix moved those rows onto the one-market blend; "+1.34 centring" and "punt share 31.5→21.8%" are the most directly exposed numbers | **adopted**: foundation of the mean-centred programme |
| 3 | **PREREG-072 → 076 → 077 (CP-1 prop universe, UNION_EMAX nomination)** | 100% 2023–24 (bank 740); the arms split on prop coverage and on DK-only (no floor or punt rule) vs context | UNION_EMAX **nominated** for prospective 2026 evaluation (the 2026 run uses live frames, so only the nomination evidence is affected) |
| 4 | **PREREG-065 / 066 / 067 (REDIST cascade, interaction PASS, beneficiary rescue)** | points are redistributed to backup beneficiaries whose means and hsim shares come from one-market rows | closed or near-miss; re-check before any PREREG-068 route reopens |
| 5 | **PREREG-054 (P_MIX, adopted in D800_DEMAX + P_MIX)** and **PREREG-036 (DUAL_EMAX, adopted)** | the hsim law bakes the defect into opportunity shares, so DUAL vs BASE is not defect-neutral; P_MIX pulls in cheaper replacements | **adopted**; medium exposure (paired on a shared pool) |

**Lower exposure (paired arms on a shared frame, or selector/judge-only):** dose, breadth and schedule (041/047/048/049/052, PREREG-097 D3200),
PREREG-100 vet_book, selector cohorts 031/033/035/087/090. **Not exposed:** PREREG-020 sealed 2025 (048), which is outside the defect and an
independent confirmation of boom-first. **Proj-centred early cohorts (001–005):** low; sub-\$4k rows were centred on the p90 punt
valuation. **Open:** whether that p90 is itself drawn around the blended mean (if so these are exposed too).

## What a clean re-check needs
A **live-faithful substrate**: the snapshot's `mean_projection` recomputed with one-market rows served by the model (exactly L03's
`CTRL_LIVE` recompute, `experiments/l03_market_conversion_replay.py::arm_frame` with the PLAIN export). Re-reading any verdict on it is a new
outcome read of an already-examined panel, so under LAB_RULES it needs its own preregistration with a reopening condition written first.
This census does not propose re-running anything; it names where the exposure is. The full per-cohort table (about 25 rows with file:line
citations) is in the census agent's working notes and can be committed on request.
