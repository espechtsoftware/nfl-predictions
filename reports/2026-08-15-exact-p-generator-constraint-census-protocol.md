# Exact-P generator constraint census protocol

Date: 2026-08-15  
Protocol: `20260815-exact-p-generator-constraint-census-v1`  
Evidence class: outcome-viewed descriptive diagnosis and prospective hypothesis generation only

## Question

The corrected exact-P roster obeys the production legality contract but is on
average 5.17 player swaps from the nearest retained CBWU candidate. Determine
where it was lost without fitting a new generator allocation to historical
scores:

1. native generator search;
2. five-seed fixed-budget CBWU admission; or
3. a generator-family structural restriction.

This is not a historical arm and cannot promote a policy.

## Immutable sources

- Corrected P identities: repair4 oracle table
  `nfl-predictions-503414.nfl_forensic_review.final_forensic_20260814_oracle_rosters_repair4`,
  scope `phase-s-cbwu-54`, layer `P`.
- Corrected player metadata, excluding actual scores:
  `...final_forensic_20260814_player_corpus_repair4`.
- Retained CBWU candidates, excluding actual scores:
  `...final_forensic_20260814_candidate_corpus_repair4`.
- Complete native candidate books, excluding `actual_score` and
  `actual_rank`, from `nfl_predictions.replay_candidates_staging` for exactly:
  `20260813-sis-asoe-treatment-r0-v1` through
  `20260813-sis-asoe-treatment-r4-v1`.
- Frozen prelock identity: 68,493 candidate rows, 54 slates and prelock row
  hash `869a648ade3919b8942d8489795b208484c448ca73873cfcacede84effb13e7e`.
- Repair4 manifest SHA-256
  `51edbe124846dc936ade71c4e5a9a07e252bcf6c7d7872b979715ccd1f6bab02`.
- Corrected exact-stack result generation `1786794534795445`, SHA-256
  `1d9e6b1f8d4e6174ae4aa717acf62fe657f0f3fbfd9271289a36b4a58664e7f3`.

All source-table manifest labels, row counts, slate keys and the exact-P
legality audit must reproduce before the census. No candidate outcome, rank,
selection yield or lineup score may be queried or used by the census.

## Frozen analysis

For every slate:

1. Reconstruct the exact P roster and audit the unchanged $49,000--$50,000,
   QB+2, one-bring-back, no same-team two-RB, no RB-opposing-DST and minimum
   two-game contract.
2. Reconstruct each complete native seed book in `cand_ix` order and the
   deterministic five-seed CBWU quota/fill roster set. It must reproduce the
   repair4 retained CBWU identities exactly.
3. Report whether exact P occurs in each native seed, the all-seed native
   union and retained CBWU. Classify a roster present natively but absent from
   CBWU as `fixed-budget-admission`; classify one absent from the native union
   as `native-generation-search`. Any exact-P roster found in retained CBWU is
   an invalid reproduction because corrected P-C is positive.
4. Normalize `all_tags` only into the registered base families `lev`, `boom`,
   `epi`, `qbvar`, `game` and `dark`. Scenario suffixes remain provenance but
   do not create new families. For each seed and family report candidate
   count, exact-P membership, closest roster swap distance, number of closest
   rosters and exact-P player-slot coverage. Do not report candidate scores or
   tag yield.
5. Report these static structural eligibility checks:
   - `lev`, `boom` and `epi`: exact P is universally legal; failure to appear
     is objective/search-budget miss, not hard infeasibility;
   - `qbvar`: P's quarterback must appear in that seed's `qbvar` family;
   - `game`/`dark`: P must contain at least five players from one game. If it
     does not, the family is structurally incapable of producing P.
   These checks do not claim the optimizer would choose P under a family
   objective.
6. Compare exact-P structure with every native family and seed on salary,
   distinct games, largest team block, stack/bring-back count and positional
   salary. Report P's within-pool percentile and two-sided distance from the
   family median. Do not use actual ownership because it is post-lock.
7. Report exact-P player representation by seed/family and distinguish
   `player absent`, `player thinly represented`, `combination absent` and
   `combination removed by CBWU admission`.

Aggregate all counts across 54 slates and also disclose each season and slate.
No threshold, tail-count, mean realized score, ROI or candidate performance
metric belongs in this result.

## Interpretation and next decision

The result may name only one of these descriptive diagnoses:

- `native-generation-search-dominant`;
- `fixed-budget-admission-material`;
- `specific-family-structural-exclusion-material`;
- `mixed`; or
- `invalid-or-inconclusive`.

The result may inform one separately frozen, constant-realized-candidate-budget
2026 shadow. It may suggest entering an under-covered structural region, but
must not set generator weights from historical tag yield, exact-P player
identities, exact-P scores or exact-P weekly amounts. The production policy,
salary floor, stack rules and exact-80 selector remain unchanged.
