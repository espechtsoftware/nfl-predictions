# PIT-clean Tier-1 production revalidation

Frozen 2026-08-11 after the outcome-free warehouse reconciliation passed and
before any repaired lineup outcome was queried.

## Fixed lineage

- warehouse gate:
  `reports/pit-repair-runs/20260811-pit-clean-v2/reconciliation.json`;
- application generation code: `a12ab31` and only its validated immutable
  application-image digest;
- canonical marginals:
  `nfl_features.tabpfn_projections_pit_v2`, only after its independent
  validation passes;
- isolated registry prefix: `models_pit_v2`, so qualification cannot mutate
  the currently served registry before adoption;
- production-availability registries: canonical K=3, `tail_k1`, and
  `tail_k1_role`, all retrained from the reconciled table before any repaired
  score panel; and
- seasons 2019, 2021, 2022, 2023, 2024 and 2025, Sunday main only, exact 80
  final lineups per slate, unchanged seeds/selector/possession simulation,
  `N_BOOM=40`, and no CE/Gumbel candidates.

Both base controls explicitly set
`TABPFN_MARGINAL_TABLE=tabpfn_projections_pit_v2`. Any missing cache row,
empirical/stale cache substitution, mixed code/config identity, incomplete
slate, candidate/player-mean mismatch or failed ensemble mechanism audit makes
the comparison invalid.

## Predeclared panels and branch

1. K=3 control: `20260811-pitclean-e80-k3-a12ab31`.
2. K=1 challenger: `20260811-pitclean-e80-k1-a12ab31`, differing only by
   `MODEL_ENSEMBLE=1` and its member/seed provenance.
3. Mechanically selected base proceeds to exactly one direct-role union:
   - if K=3 wins: `20260811-pitclean-e80-k3-role12union-a12ab31`;
   - if K=1 wins: `20260811-pitclean-e80-k1-role12union-a12ab31`.

The role arm adds exactly 12 `role_draws` candidates per slate, with frozen
features `target_share_last,carry_share_last,snap_share_last,target_share_jump,
carry_share_jump,snap_share_jump`, seed 7331 and `REPLACEMENT_SLOTS=12`, while
retaining boom 40 and the selected base's ensemble law. It still returns
exactly 80 final entries. The unselected branch is never launched.

## Operator decision law

Mechanism validity and 107 aligned exact-80 slates are prerequisites. Among
valid books, compare the count of weekly selected maxima clearing thresholds
in this fixed lexicographic order:

`240, 230, 220, 210, 200, 194, 187`.

The first non-zero difference selects the book with the larger count. If all
seven counts tie, mean weekly maximum is the tiebreaker; if that also ties,
retain the simpler K=3/base book. Average score and season signs are reported
but are not vetoes, matching the operator's stated preference for the one
exceptional lineup among 80. The same law governs the role union. This rule is
frozen before repaired outcomes and supersedes older gates that privileged a
200-count lift or season-average stability over higher thresholds.

## Downstream qualification

After the base/role branch is terminal, refit served-position calibration and
data-fitted usage concentration from repaired inputs without scores, then run
their already-scoped gates. Active-label v2 final-served consumes the terminal
usage branch and repaired panel explicitly. No old calibration factor,
fitted-K value, cache validation hash or historical panel result may be copied
into the repaired decision.

Every report must include old-versus-repaired input coverage, cache and model
identity, player-distribution deltas, candidate/selection overlap, the full
threshold grid, weekly paired changes and season slices. Only after all
deployment/fallback checks pass may the live policy/registry change.
