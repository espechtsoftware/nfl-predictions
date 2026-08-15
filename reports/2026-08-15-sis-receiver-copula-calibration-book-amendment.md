# SIS receiver-copula calibration-book amendment

Date frozen: 2026-08-15 12:02 CDT  
Parent protocol: `20260815-sis-receiver-copula-v1`  
Status: pre-value implementation clarification; no SIS artifact or dependence
score has been read

## Reason

The parent protocol fixes the 2022 Weeks 5--18 calibration season, strength
grid, score, tiebreaks and held-out terminal book, but it does not explicitly
name the marginal cache and usage law used to reconstruct the 2022 control
book. That choice can affect rank dependence and therefore must be fixed before
the first usable SIS artifact is acquired or any calibration outcome is read.

This amendment resolves only that ambiguity. It does not change the SIS
acquisition, context, treatment, strength grid, objective, held-out book, gate
or consequence. The acquisition continues to bind the unchanged parent
protocol hash.

## Frozen 2022 calibration book

Reconstruct only season 2022 from historical splice
`20260811-pitclean-e80-k1-role12union-a12ab31`, using:

- PIT cache `tabpfn_projections_pit_v2`;
- the cache's accepted persisted historical allocation law: production
  multinomial usage (`GAME_SIM_USAGE` and `DIRICHLET_K` blank);
- no served-position adjustment, because the accepted strictly-prior served
  schedule begins with the held-out 2023 fold;
- 45/55 model/market blend, 10,000 worlds and seed 0; and
- exact parity with the immutable accepted 2022 player snapshot before the
  Week 5--18 filter or treatment is applied.

The calibration loader must query only 2022 accepted outcomes. It may load
strictly prior feature/training inputs needed to reconstruct 2022 projections,
but it may not query 2019, 2021 or any 2023--2025 outcome. After exact parity,
filter the book to 2022 Weeks 5--18, attach only the frozen strictly-prior SIS
and Fantasy Points context, and compute the complete seven-cell grid.

Every grid cell uses the same 2022 control marginals. The registered
absolute-log-error sum is the unweighted sum of these six two-sided errors:

1. G1 broad `QB_WR`;
2. G1 broad `WR_WR`;
3. G0 `qb_wr`;
4. G0 `wr_wr`;
5. G0 `multiplicity_ge2`; and
6. G0 `multiplicity_ge3`.

All six cells must be supported for a grid cell to be eligible. Aggregate
joint-q90 Brier and p=0.5 variogram use the same fixed relationship weights as
the repaired held-out scorebook: `QB_WR=3`, `QB_TE=2`, `QB_RB=1`, `WR_WR=2`,
`RB_RB=1`, `TE_TE=1`, `QB_OPP_QB=1`, `QB_OPP_WR=1`, `QB_OPP_TE=1`, and
`WR_OPP_WR=1`. Thus the proper-score tiebreak uses the complete registered
primary G1 relationship scorebook, not only the two receiver relationships.

## Split execution boundary

Calibration and held-out evaluation are separate Cloud Run executions. The
calibration harvester must create a checksum-verified immutable artifact with
all seven grid cells and the selected cell before the held-out job is deployed.
The held-out job pins that artifact's report and manifest hashes as well as the
fresh repaired-path reference hashes. This is stricter than merely printing the
grid before continuing in one process.

No result from this amendment can license a retrospective exact-80 run or a
production change. All consequences remain those of the parent protocol.
