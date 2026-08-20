# A2a production-law dependence remeasurement

**Protocol ID:** `20260820-a2a-production-law-dependence-remeasurement-v1`

**Status:** FROZEN before any new realized-outcome query, treatment/outcome
join, or treatment law-shape report

**Scope:** one outcome-bearing dependence diagnostic. It does not construct,
select, or score a lineup and cannot change production.

## 1. Licensed question

The completed score-free A2a census has disposition
`a2a-scorefree-mechanism-passes`. This protocol spends its sole license on the
smallest corresponding historical question: after applying the exact frozen
A2a rank permutation to the exact production-law worlds, does the nine-cell
G0 dependence law become acceptably closer to the already-registered realized
football law?

The remeasurement may license only preparation of a separately frozen
exact-one-QB-partner construction protocol. It cannot directly run that arm,
license exact-80 scoring, license a prospective shadow, or change production.

## 2. Immutable inputs

### A2a mechanism license

- score-free protocol SHA-256:
  `329379ebd7be5e4a92ee34f8a8dd9ae2f6dca90517a81627800f5756852eeab7`;
- passing result URI:
  `gs://nfl-predictions-503414-raw/research/a2a-rank-factor-split-runs/20260820-a2a-rank-factor-split-scorefree-v2/result.json`;
- generation: `1787248289501941`;
- bytes: `884522`;
- result SHA-256:
  `86f72b40b714dd186dd81e698b390eb9e0d5dd3d7b5c96eb42c92f5d213c6774`;
- disposition: `a2a-scorefree-mechanism-passes`;
- sole true license: `historical_remeasurement_licensed=true`.

### Production-law source

Use the same create-once production-law source lock and no regenerated world:

- URI:
  `gs://nfl-predictions-503414-raw/research/production-law-dependence-runs/20260817-production-law-dependence-source-lock-v1/source-lock.json`;
- generation: `1786950155692968`;
- bytes: `1341911`;
- SHA-256:
  `7ede34b6d13dacb6645836a85ff35dc82f757331423e49f84537d710c500346c`;
- 54 Sunday-main slates, 2023--2025 Weeks 1--18;
- five registered blocks `R0`--`R4`, 10,000 worlds each, 270 immutable
  generation-pinned artifacts;
- locked eligible population: 9,469 QB/RB/WR/TE player-slate rows with served
  mean at least 4.0.

The policy is still
`classic-k1-role12-boom40-poscal-cbwu-v4`: production-multinomial usage,
possession game mode, team factors on, blank Dirichlet law and TD ledger off.

### Frozen transform and realized-law references

- transform module
  `src/nfl_dfs/research/a2a_rank_factor_split.py` SHA-256:
  `208bcc1707edc53fec7905025572a447d2deef9fbdb725332016f98c60138d02`;
- G0 estimator
  `src/nfl_dfs/analysis/final_served_dependence.py` SHA-256:
  `85acc05b716fe6d3f39dce46d645c2652e8630a620df8b464dbfb16f2d1e3ffd`;
- frozen decision/accounting module
  `src/nfl_dfs/analysis/a2a_production_law_dependence.py` SHA-256:
  `9bb4cede575bc811abc542e38ec617d7ad5cd822dbe7e1c9c028397af0415978`;
- source-lock/grid/body adapter
  `scripts/run_a2a_rank_factor_split_census.py` SHA-256:
  `24ddb3caceda3d660bed39fcdec84575b3545a2717e75ff944dc86319ef75ad1`;
- immutable production-law control report SHA-256:
  `5b92339b2a9118727d41a8f4b91e982c5478318029c216652d66b7cdd113e696`.

The runner must validate all of these identities plus all 270 live object
metadata receipts before its one actual-outcome query. It may then download
each artifact by content identity. Any mismatch is terminal invalidity, not a
license to substitute or regenerate.

## 3. Intervention remains exact

Apply the frozen A2a V2 transform without changing a coefficient, support
rule, WR choice, tie rule, or row permutation:

- transform only a team-slate group with exactly one eligible QB and at least
  two eligible WRs;
- keep zero-/multi-QB and fewer-than-two-WR groups bit-exact;
- keep the QB anchor bit-exact;
- subtract `0.5 * (team_open_rank - 0.5)` from every eligible non-QB row's
  priority;
- allocate exactly `1.0 * (qb_open_rank - 0.5)` to the already-highest-ranked
  canonical WR in each eligible group-world; and
- remap only by exact stable row permutations, retaining every player's
  sorted draw multiset and q90 boom count.

There is no coefficient grid, starter guess, context weight, support repair,
or follow-up dose. An undershoot or overshoot closes this dose; either would
require a genuinely new prospective protocol, never an adjusted rerun on
these outcomes.

## 4. Reporting-only coverage accounting

The locked catalog contains 1,194 eligible team-slate groups. The transform
covers 1,041 (`1041 / 1194 = 0.871859296482412`) and skips, mutually
exclusively:

- 28 with zero eligible QBs;
- 118 with multiple eligible QBs; and
- seven with exactly one eligible QB but fewer than two eligible WRs.

It directly permutes 7,171 non-QB eligible rows, leaves 1,041 covered-group QB
anchors unchanged, and leaves 1,257 eligible rows in skipped groups unchanged.
The direct-row fraction is `7171 / 9469 = 0.7573133382616961`.

The result must recompute and report these counts, reasons and fractions. They
are disclosure only: they do not change support, select a QB, rescale an
effect, weaken a gate, or create a second dose.

## 5. Frozen realized estimands and equivalence targets

Use the same G0 definitions, strict `draw > row q90` threshold, heterogeneous
Poisson-binomial reference, 2,000 whole-slate bootstrap replicates, seed 1701,
support rules and classification logic. The exact registered realized targets,
bands, and production-law aggregate control point gaps are:

| Cell | Realized target | absolute log band | control log(sim/real) | A2a role |
|---|---:|---:|---:|---|
| multiplicity >=2 | 0.8209974371834499 | 0.09531017980432493 | +0.2586212580069155 | generic attenuation |
| multiplicity >=3 | 0.9970062534524585 | 0.13976194237515863 | +0.7436982933488568 | generic attenuation |
| multiplicity >=4 | 1.0884346795425752 | 0.22314355131420976 | +1.6476273247486672 | generic attenuation |
| QB->WR | 3.3392156862745095 | 0.13976194237515863 | -0.2611202585756975 | targeted one-hot re-coupling plus attenuation |
| QB->TE | 1.8521140513621719 | 0.13976194237515863 | +0.23917750548480823 | attenuation only; no QB-TE re-coupling |
| QB->RB | 0.9106858054226474 | 0.13976194237515863 | +1.166946980838297 | attenuation only; no QB-RB re-coupling |
| WR->WR | 0.9905119347301017 | 0.13976194237515863 | +0.6912856504946393 | generic attenuation plus competitive WR allocation |
| RB->RB | 0.49414928618430465 | 0.13976194237515863 | +1.4883141634549988 | attenuation only; no RB-RB re-coupling |
| TE->TE | 0.42028985507246375 | 0.13976194237515863 | +1.3425354176099444 | attenuation only; no TE-TE re-coupling |

Every block and the 50,000-world aggregate must reproduce every realized
target and band exactly. The five blocks measure Monte Carlo stability of one
law; they are not independent historical replications.

## 6. Exact gate and overshoot rule

All nine cells must remain supported in all five blocks and the aggregate.

The targeted QB-WR mechanism passes only if:

1. the aggregate treatment is classified `equivalent`; and
2. at least three of five blocks are classified `equivalent`.

In particular, an aggregate QB-WR point gap greater than
`+0.13976194237515863` is
`a2a-law-shape-miss-qb-wr-overshoot`. Moving from under-coupled through the
realized band into over-coupling is a miss, never directional success. A gap
below the negative band, or a point inside the band whose interval is not
equivalent, also fails the targeted condition.

The generic attenuation mechanism additionally requires:

1. aggregate multiplicity >=3 is `equivalent` and at least three of five
   blocks are `equivalent`; and
2. each aggregate registered cell is either `equivalent`, or has a strictly
   smaller absolute point gap than its frozen control while remaining on the
   same side of zero.

That final guard applies explicitly to QB-TE, QB-RB, RB-RB and TE-TE as
attenuation-only cells. Crossing through zero outside the realized equivalence
band is regression, not evidence of pair-specific repair.

## 7. Exhaustive dispositions and licenses

- Missing support in any registered block/cell:
  `a2a-law-shape-inconclusive`.
- Aggregate QB-WR above the positive band:
  `a2a-law-shape-miss-qb-wr-overshoot`.
- Other QB-WR equivalence/three-block failure:
  `a2a-law-shape-miss-qb-wr-not-equivalent`.
- QB-WR passes but a generic or protected-cell condition fails:
  `a2a-law-shape-miss-attenuation-or-protected-cell`.
- Every condition passes:
  `a2a-law-shape-passes-single-stack-protocol-licensed`.

Only the last disposition may set
`single_stack_protocol_licensed=true`. Even then the following remain false:

```text
candidate_or_lineup_scores_read
single_stack_arm_licensed
exact80_scoring_licensed
prospective_shadow_licensed
production_change_licensed
```

The exact-one construction arm still requires its own frozen protocol and
immutable execution. No sensitivity analysis, coefficient change, support
change, or secondary endpoint can reverse this one-shot disposition.

## 8. Outcome firewall and execution order

The runner is default-off. Both its explicit frozen-execution argument and
`A2A_REMEASUREMENT_ENABLED=1` must be present before any client is created.

Execution order is fixed:

1. validate this protocol, transform/estimator bytes, the passing A2a result,
   the frozen control report and source-lock content identities;
2. validate all 270 live artifact metadata identities without reading an
   outcome;
3. acquire the shared one-at-a-time historical-outcome lease in the eventual
   launcher;
4. issue exactly one query for `season, week, player_id, actual` from the
   frozen R0 player table;
5. download the pinned player-world bodies, apply A2a once, reproduce every
   exact mechanical invariant, and run only the frozen nine-cell evaluator;
6. create one result at
   `gs://nfl-predictions-503414-raw/research/a2a-production-law-dependence-runs/20260820-a2a-production-law-dependence-remeasurement-v1/report.json`;
7. strict-harvest and generation-pin the result before reading its disposition.

The eventual Cloud Run execution must reuse an idle existing research job,
use one task, `maxRetries=0`, and appear in `scripts/chain_status.sh`. This
protocol does not itself authorize a launch; immutable build validation,
outcome-blind real-artifact smoke, free-lease proof, create-only prefix proof,
and an external launch manifest remain mandatory transport gates.
That manifest must pin the decision module, source adapter, runner, protocol,
Dockerfile and Cloud Build bytes without asking the runner to self-hash.
