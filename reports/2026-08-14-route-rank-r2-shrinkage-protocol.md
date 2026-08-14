# Route rank R2: fixed midpoint shrinkage protocol

Frozen 2026-08-14 before implementation or execution of R2 and before any
I1-R lineup-score outcome exists.

## Question

Can the four point-in-time Fantasy Points Route Share fields improve the
dependence structure after a fixed shrinkage toward the accepted control,
without changing any player's served marginal distribution?

I1-R is a mechanically valid, outcome-free near miss. Four of its five
equal-weight dependence families improve and its QB-WR/QB-TE hub error falls,
but multiplicity MSE worsens 2.22%, leaving the family mean ratio 0.20% above
one. This protocol does not reinterpret I1-R as a pass and does not tune a
weight on its metrics. It registers one natural midpoint shrinkage value,
`0.5`, before R2 is implemented.

## Frozen inputs

- Historical player/slate panel:
  `20260811-pitclean-e80-k1-role12union-a12ab31`.
- Training table snapshot:
  `nfl_features.player_week_training`, 102,927 rows, content checksum
  `1904430067081090565`.
- Accepted marginal cache: `nfl_features.tabpfn_active_label_treatment_v2`,
  active-only label law.
- Accepted usage: finite Dirichlet `K=28.154043586960896`.
- Selected Phase S law: SIS ASOE treatment, beta
  `0.07771181538347656`.
- Accepted G0 walk-forward position schedule and the I1-R evaluation
  population: 7,848 supported rows, 54 slates, 34,038 registered pairs.
- Evaluation seasons 2023-2025, 10,000 draws, simulation seed 0, market blend
  weight 0.45, and all other inherited final-served laws remain fixed.
- Input hashes:
  - I1-R report: `01fd0c5e14dd0ebcf61312231167d5849592a0862fd2aa97cc91c1a50a9e0804`
  - Phase S report: `46f7cfbfedb4e1140f4bc1ca561215703fe416cb1d2a26856ed605ed470187aa`
  - G0 report: `8b4ff4b6fa94d8de1c69621c6aee303c5881114ab5196d095981f247cd24866b`
  - active-label selection: `2d76f41f74402d4cc048fdab98cdbe0ef0eae17bf5df1d289cdc2d7bb150b348`
  - usage selection: `a73f0e9c0180afce6fefefacf173b0fa0939e0557c06ef2b817cc538f33993af`

## Arms and sole treatment difference

Generate the same I1 control component worlds `C` and Route-feature component
worlds `R` with common seeds and identical terminal processing. The R2
treatment is constructed player by player:

1. Compute the fixed midpoint rank score `S = 0.5 * C + 0.5 * R` for each
   simulated world.
2. Sort the accepted control draw values for that player using a stable sort.
3. Assign those exact sorted control values according to the stable rank order
   of `S`.

Thus R2 may change only cross-player/world rank dependence. Each player's
sorted treatment draws must be exactly equal to control (`max_abs_delta <=
1e-10`), and its mean must match control at the same tolerance. Ties use a
stable sort; there is no random tie break.

The shrinkage weight is exactly 0.5. Do not test 0.25, 0.75, an optimized
weight, position-specific weights, individual Route-field subsets, or another
rank transform on these outcomes.

## Score-free evaluation and gate

Use the identical I1-R G0/G1 population, archetype labels, pair book,
bootstrap books, and five equally weighted loss families:

1. G0 multiplicity squared log-gap;
2. G0 teammate role-pair squared log-gap;
3. G1 primary broad-relationship squared log-gap;
4. overall joint-q90 Brier;
5. overall p=0.5 variogram.

R2 passes only if all mechanical invariants pass and:

- the mean of the five treatment/control loss ratios is below 1;
- at least three of five families improve;
- mean absolute QB-WR/QB-TE log-gap does not increase;
- no supported primary relationship's absolute log-gap increases by more than
  `log(1.15)`;
- no primary relationship worsens both proper scores by more than 10%; and
- sorted marginals and player means reproduce control within `1e-10`.

The report must include all family losses/ratios, relationship guards,
population/invariant audits, and the existing clustered bootstrap context.

## Decision and follow-up

- If R2 fails, close midpoint Route rank shrinkage on this historical panel.
- If R2 passes, it may license one separately frozen five-seed, exact-80
  control-versus-R2 lineup experiment under the tail-first order
  240/230/220/210/200/194/187. That score experiment must be registered before
  generation and may not tune the shrinkage weight or selector on its result.
- R2 has no effect on the independently running SIS pass-tail exact-80 panel.

No partial execution metrics may be used. Infrastructure-only retries must
preserve every scientific input above and be recorded separately.
