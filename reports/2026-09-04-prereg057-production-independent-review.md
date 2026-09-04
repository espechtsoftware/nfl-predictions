# Production independent review of PREREG-057 / experiment 088

Date: 2026-09-04  
Production review basis: frozen lab source `0f53a5ace9e1a8d612520faa804e9a0abf9096d4`  
Disposition: **the accepted 088 result is reproduced; close the exact KG-4 forms and do not rerun them**

## Production finding

Production independently reran the frozen PREREG-057 reader against the exact
registered runs:

- bank 620: `088b620r1-20260902T202127Z`, execution `lab-run-gf29b`;
- bank 621: `088b621r1-20260902T202320Z`, execution
  `lab-run-slow-8gzth`;
- bank 622: `088b622r1-20260902T210550Z`, execution
  `lab-run-slow-cf44g`.

Provider state independently confirms that each execution completed 18/18
tasks with zero failures and zero retries. The frozen reader completed with
exit status zero. Its stdout transcript SHA-256 is:

`71b1104605cc24da23e3f05bf0a6053d2f108ba14411db0a05574b7ffee8b998`

The production rerun reproduced the lab's decision-bearing estimates exactly:

- `K4_CAL - K4_CTRL`: `+0.00030`, family interval
  `[-0.00071, +0.00138]`, `p = 0.7771`, verdict
  `UNPASSED_NEAR_MISS`;
- `K4_SLV_LEV - K4_CTRL`: `+0.00063`, family interval
  `[-0.00067, +0.00154]`, `p = 0.5505`, verdict
  `UNPASSED_NEAR_MISS`;
- `K4_SLV_STRUCT - K4_CTRL`: `-0.00075`, family interval
  `[-0.00263, +0.00044]`, `p = 0.1887`, verdict `FAIL`.

The corresponding descriptive realized K80 weekly-maximum changes were
`+0.088`, `+0.206`, and `-0.276` points. The leverage arm was directionally
positive in banks 621 and 622 but negative in bank 620; calibration was mixed;
and the structural arm included the preregistered bank-620 veto. None clears
the frozen adoption gate.

## Interpretation

This closes the inexpensive KG-4 calibration, leverage-retention, and
structural-retention forms at the tested doses. The positive point estimates
for calibration and leverage are not adoption evidence: intervals span zero,
the effects are small, and bank behavior is inconsistent. The structural form
is not adopted.

The result does **not** close the broader Neo4j selection-gap program. All 088
arms operated on the same candidate set (`candidate-J = 1.000`), while the
original E0 finding concerns valuable lineups being lost across generation,
admission, and retrieval. Complete candidate lineage and first-loss routing
remain necessary before assigning those misses to selection. Conditional on a
candidate reaching the selectable pool, the direct remaining test is the
walk-forward identical-pool reranker; admission and supply losses route to
their respective interventions instead.

## Production disposition

1. Accept the lab's 088 seal and require no rerun.
2. Do not promote `K4_CAL`, `K4_SLV_LEV`, or `K4_SLV_STRUCT` into the Week-1
   generator or selector.
3. Do not tune a nearby dose on the same 72-slate panel from these results.
4. Keep the candidate-lineage/first-loss program moving, because 088 did not
   test the full generation-to-final-book loss mechanism.

No scoring code, production policy, graph state, paid-entry state, or cloud
experiment was changed by this independent review.
