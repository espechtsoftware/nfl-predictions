# G3 participation-conditioned allocation Stage A protocol

Date frozen: 2026-08-13, before any G3 held-out likelihood is computed.

## Question and branch

Does strictly prior player participation/action geometry identify stable
within-team target/carry allocation heterogeneity beyond the accepted global
Dirichlet law?

The branch is mechanically fixed by the current accepted book:

- control: active-label fitted Dirichlet `K=28.154043586960896`;
- treatment: a group-specific concentration regularized around that exact K;
- accepted active-label cache: `tabpfn_active_label_treatment_v2`;
- historical panel identity:
  `20260811-pitclean-e80-k1-role12union-a12ab31`.

This is a score-free Stage A gate. It may not read lineup scores, candidate
scores, weekly maxima, ownership or contest outcomes. A pass licenses only the
already-specified G1 dependence evaluation of this fixed allocation law. It
does not license an exact-80 comparison by itself.

## Walk-forward data law

Usage groups and point-in-time component means use the same active-player,
team-week, target/carry construction as
`analysis/usage_dirichlet_calibration.py`:

- calibration target seasons: 2021 and 2022;
- untouched evaluation target seasons: 2023, 2024 and 2025;
- component models are trained strictly before each target season;
- target/carry observations from an evaluation season are used only in its
  final likelihood score.

For each target season, its embedding is independently fitted from nflverse
participation and PBP seasons 2016 through `target_season - 1`. No same-season
play, participation or outcome enters that season's geometry. Report the
source seasons, maximum source season, row counts and SHA-256 identities.

True NFL newcomers with no prior participation remain cold. Missing geometry
falls back exactly to global K; it is never imputed from target-season data.

## Fixed skip-gram-style representation

Use the deterministic shifted-PMI matrix factorization of a negative-sampling
skip-gram objective:

- token: `gsis_id` in `offense_players`;
- context window: all other offensive players on the same valid 11-player
  participation row;
- base unordered pair weight: 1;
- explicit PBP actors: passer, target and rusher; add weight 3 from each actor
  to every other offensive player on that play, so actor/context pairs have
  total weight 4 when the base edge exists;
- embedding dimension: 16;
- negative samples: 5, implemented by the shifted-PMI term `-log(5)`;
- factorization: `TruncatedSVD(n_components=16, n_iter=7,
  random_state=8112026)` on the symmetric positive shifted-PMI matrix;
- row L2 normalization; players with a zero row have no geometry.

This is the standard matrix-factorized SGNS objective, not a supervised slate
model. No GNN, player outcome, DFS score or held-out parameter selection is
included.

## Fixed conditional concentration law

For every usage group, compute the predicted-share-weighted embedding
dispersion

`d = sum_i p_i ||e_i - sum_j p_j e_j||^2`

over players with prior embeddings. Require at least two known players and at
least 80% of the group's predicted probability mass; otherwise set the
standardized feature to zero and use global K. Renormalize known-player shares
only for the dispersion calculation, never for the usage likelihood.

For targets and carries separately, standardize `d` using only the 2021--2022
calibration groups. The treatment is

`K_group = clip(K_global * exp(beta_kind * z_group), 5, 500)`.

Fit one `beta_kind` per kind on calibration likelihood only, with bounds
`[-1.5, 1.5]` and objective

`mean Dirichlet-multinomial NLL + 0.05 * beta_kind^2`.

Endpoint ties select the coefficient closest to zero. No intercept is fitted:
`z=0` is exactly the accepted global K. The mapping, bounds, regularization,
embedding law and coverage rule may not change after evaluation begins.

## Mechanical and scientific gate

Fail closed unless all of the following hold:

1. Every target-season embedding uses only smaller season numbers, all source
   identities are present, usage groups match the existing PIT-clean builder,
   and every treatment K is finite and within `[5, 500]`.
2. Geometry coverage is at least 80% of retained groups for each kind in every
   evaluation season.
3. At least one fitted coefficient has absolute value at least 0.01 and the
   corresponding evaluation K distribution is nonconstant.
4. Treatment aggregate mean NLL per group is lower than global-K control.
5. Targets and carries each improve aggregate mean NLL per group.
6. At least two of the three evaluation seasons improve aggregate mean NLL per
   group.
7. A fixed 2,000-resample team-week clustered bootstrap, seed 8,113,026, has
   an upper 95% bound below zero for treatment-minus-control mean group NLL.

A failure closes this G3 allocation mechanism without a lineup comparison.
A pass licenses one implementation of the exact fixed law in the G1
dependence scorecard. Only a later G1 pass can license a separately frozen
exact-80 score comparison.

