# Paid-source influence ladder, direct run (2026-09-15)

Design: `reports/2026-09-14-prereg-paid-source-influence-ladder-DRAFT.md` (§2 design, §3 estimands, §4 endpoints and
decision rule, §4 ladder reading table). Runner: `scripts/paid_source_ladder_direct_v1.py` on branch
`production/paid-source-ladder-direct-20260915` (runner sha256 `37d3ae5b6691…`, field sampler `843bb2090683…`, code
base `a0eb8da1`). Evidence: `reports/paid-source-ladder-direct-20260915/` (`manifest.json` with every input's
uri/bytes/sha256, `read.txt` verbatim, `read_table.csv` per slate × cell); per-slate JSON records with the full sidecar
stay on the host (`/home/erich/week1-sunday/direct_runner/results/`, ~54 × 5 MB).

**What ran.** The frozen FP×SIS 2×2 retrieval ablation's pure computation on the frozen inputs — seven-pack v4 rows
(7 objects), the fixed-G0 structural catalogs, the candidate-v2 accepted candidates (3,490–3,993 per slate) and the
exp5 discovery matrices (40,000 worlds per candidate; terminal `23184230…`) — for all 54 slates (2023–2025 W1–18),
four cells each (FP/SIS on-on, off-on, on-off, off-off; raw slices physically removed before component construction;
candidates and worlds byte-identical across cells), admission = top 200 by mean matchup edge, selection =
coverage-194-v1 to K80 in selector order. Outcomes: realized DK points (`nfl_features.player_week_actuals` +
`team_defense_week`), K20/K40/K80 prefix maxima and thresholds; finish = share of an ownership-consistent
200,000-lineup field (real Millionaire ownership, 54/54 slates matched at ≥ 840 mass) above the book's best lineup.
Mechanics smoke on 2023 W1 (outcome-blind) preceded the outcome run; no failures in 54 slates.

## Result (verbatim read in `read.txt`)

| co-primary (K20, family 0.9875) | mean | interval | W/L/T | seasons | sign-test p | verdict |
|---|---|---|---|---|---|---|
| points, FP given SIS on | +0.64 | [−3.71, +5.44] | 25/23/6 | −3.7 / +5.4 / +0.2 | 0.89 | NO_EFFECT |
| points, SIS given FP on | +1.20 | [−1.13, +4.00] | 24/14/16 | +0.7 / +4.0 / −1.1 | 0.14 | NO_EFFECT |
| finish (−best_pct), FP given SIS on | −0.0116 | [−0.0144, −0.0081] | 25/23/6 | all negative | 0.89 | not positive (FP-off finishes slightly better) |
| finish (−best_pct), SIS given FP on | +0.0191 | [+0.0030, +0.0399] | 24/14/16 | +0.040 / +0.014 / +0.003 | 0.14 | **PASS by the frozen rule** |

Secondaries: at K40 and K80 every contrast is null on both axes (e.g. finish SIS|FP-on K80 +0.0005, 20/21/13);
conditionals with the other source off are null; interaction +1.3 points at K20; on-on vs off-off +0.5.

Best-finish percentile means at K20: on-on 10.40 %, FP-off 9.24 %, SIS-off 12.31 %, both-off 10.35 %. Top-1,000
events per slate at K80: on-on 0.15, FP-off 0.06, SIS-off 0.11, both-off 0.04 (the full source set produces the most
top-1,000 finishes even though prefix maxima do not move).

**The ladder (means over 54 slates).**

| cell | raw component changes vs on-on | edge changes | admission Jaccard | K20 Jaccard | K80 Jaccard | K20 max | K80 max | admitted ceiling |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| on-on | 0 | 0 | 1.000 | 1.000 | 1.000 | 165.1 | 176.7 | 181.1 |
| FP off | 648.7 | 318.1 | 0.170 | 0.111 | 0.131 | 164.5 | 175.7 | 181.1 |
| SIS off | 296.6 | 187.6 | 0.336 | 0.232 | 0.260 | 163.9 | 175.6 | 180.8 |
| both off | 773.3 | 320.2 | 0.140 | 0.089 | 0.112 | 164.6 | 176.6 | 181.8 |

Pool realized ceiling 202.7 (36 of 54 slates hold a 194+ candidate); admitted ceiling ≈ 181 in every cell (12–14
slates with a 194+ among the 200 admitted); K80 max ≥ 194 in 9–11 weeks per cell.

## Reading

1. **Rungs 1–2 (wiring, erasure): both sources are consumed and nothing erases them.** Removing Fantasy Points changes
   649 raw component values and 318 edge scores per slate and replaces 87–89 % of the K20/K80 book; removing SIS
   changes 297 / 188 and replaces 74–77 %. The earlier suspicion that paid data might be wired but erased before
   selection is answered: the vendors decide *which* lineups are admitted and selected, almost entirely.
2. **Rung 3 (value): the books they choose are not better on points and only marginally different on finish.** K80
   maxima differ by ≤ 1.1 points across cells; K20 maxima by ≤ 1.2; none of the point contrasts clears zero or a
   sign test. On finish, the one contrast that passes the frozen rule (SIS, K20, +1.9 percentile points, every
   season and every LOSO positive) rests on three season clusters and a 24/14 sign split (p = 0.14) and disappears at
   K40/K80; FP is null-to-slightly-negative on finish (removing FP finishes 1.2 points better at K20, p = 0.89 by
   sign). Read as: no robust source value at the tested form; a weak, K20-only SIS signal on finish that needs a
   prospective replication before it means anything.
3. **The structural finding is about the retrieval strategy, not the vendors.** In every cell the 200 admitted
   candidates carry a realized ceiling of ~181 while the pool's is 202.7: admission by mean matchup edge discards the
   tail two-thirds of the time (36 pool slates with a 194+, 12–14 admitted). The vendors reshuffle which 200 are
   admitted; the cap keeps the tail out regardless. This is the same retrieval regret the 2026-09-12 analysis put at
   ~18 points at K20, now shown to be source-invariant.

Instrument checks: the lever moved (Jaccard 0.09–0.34); the direction is right (on-on carries the most top-1,000
events); the estimands aim at the functionals the draft froze; candidates and worlds are byte-identical across cells
(the same matrix memmap served all four); every input identity is in the manifest.

## Consequences (from the draft's frozen table)

- **Fantasy Points, exact retrieval use:** "selection changes; no co-primary passes" → closed at this form; keep the
  source only if a frozen prospective information-value argument is made separately.
- **SIS:** "one source passes on either co-primary" → promising, **no deployment**; the next step is a 2026
  prospective shadow (record the SIS-on vs SIS-off K20 books before each lock from the exact source state, grade
  after settlement), and family decomposition only if the shadow replicates. Given the sign test and the K40/K80
  nulls, treat it as a hypothesis, not a result.
- **Retrieval:** the admission cap by mean matchup edge should be tested as a lever in its own right (raise the cap,
  or admit by a tail-aware score) — a preregistration for the lab, since the discovery matrices and candidate corpus
  already exist and every cell here shows the same ~20-point ceiling loss.

## Deviations disclosed

Direct runner, not the immutable-authority chain (abandoned at defect 11); identities recorded by sha256 in the
manifest rather than by create-once receipts; the finish endpoint's field uses the PREREG-098 sampler at its gated
parameters; a three-season cluster bootstrap (intervals are only as wide as the between-season spread — sign tests
reported alongside); realized points from the warehouse tables rather than the recognized-outcome authority.
