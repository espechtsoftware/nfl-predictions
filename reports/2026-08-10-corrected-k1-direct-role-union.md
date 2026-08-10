# Corrected K1 direct role-belief union

Status: preregistered before any corrected direct-role candidate or score was
generated.

## Decision context

The point-in-time-corrected K1 panel
`20260810-lockfix-e80-k1-8677d21` is the accepted incumbent. Its exact-80
selected 187/194/200/210/220/230/240 grid is `34/21/11/7/4/2/1`; its pool
oracle grid is `41/28/16/9/4/2/1`.

The corrected fixed-budget CE12 arm was mechanically valid but rejected. It
improved 187/194/200 and mean, while moving 230/220/210 from `2/4/7` to
`1/3/6`. That result excludes CE from this test, but it does not measure the
distinct alternate-role generator.

The role generator was frozen before the corrected rebaseline and has not
produced a corrected score. Its six role inputs and seed were not chosen from
the CE result. The earlier pre-correction CE+role union is ineligible as score
evidence because its market inputs violated the common DFS lock, but it
established before this rebaseline that the generator is non-vacuous and can
produce high-tail rosters. A single direct K1+role confirmation is therefore
eligible; no role dose, feature, seed, budget or selector sweep is eligible.

## Frozen arm

| Property | Source | Treatment |
|---|---|---|
| Panel | `20260810-lockfix-e80-k1-8677d21` | `20260810-lockfix-e80-k1-role12union-8677d21` |
| Ensemble | K=1 | K=1 |
| CE candidates | 0 | 0 |
| Role candidates | 0 | exactly 12 |
| Boom candidates | 40 | 40 |
| Final entries | exactly 80 | exactly 80 |
| Selector/worlds | production line-194 coverage | unchanged |

The treatment is an added-candidate union, not a fixed candidate-compute
ablation. Added preselection compute is acceptable under the current operator
objective because both arms still return exactly 80 playable entries. The
source pool must be contained exactly in the treatment on all 107 slates.

Role settings are frozen to:

- `EPISTEMIC_FAMILY=role_draws`;
- `ROLE_BELIEF_FEATURES=target_share_last,carry_share_last,snap_share_last,`
  `target_share_jump,carry_share_jump,snap_share_jump`;
- `ROLE_BELIEF_SEED=7331`; and
- 12 role candidates per slate.

Generation must use the same validated common-lock image as the corrected K1
source:
`sha256:215a6729b66980310cfad3f63b06a7c25ce4dcf2fa2b6949a04a5c9afa337221`,
with persisted code identity `8677d21`.

## Mechanical gate

Before any score decision, require:

1. six complete seasons and 107 aligned slates;
2. exactly 80 selected rows per slate in both arms;
3. identical player snapshots, code/config identity, seed identity and
   baseline simulation values;
4. exact source-roster containment and invariant common actual score,
   simulated mean, p-line and line-194 support masks;
5. exactly 12 retained `epi` role candidates on every slate, at least one
   source-novel role roster, and a larger treatment pool on every slate; and
6. canonical artifact, legality, label and mean-parity acceptance.

Any failure makes the arm invalid rather than negative.

## Frozen score decision

For the same 80 final entries, compare selected weekly-best counts in this
exact order: 240, 230, 220, 210. At the first threshold with a difference,
the treatment passes only if it is higher. A treatment that ties every one of
those counts is neutral and does not replace K1. Counts at 200/194/187,
mean/median, pool-oracle counts, role-specific realized frontiers and season
signs are diagnostics and cannot override a loss at a higher active threshold.

There is one historical execution only. No feature, seed, role dose, boom
count, selection line, threshold order or retry may change after a valid
result. If it rejects, corrected K1 remains the incumbent and the queue moves
to the already-preregistered new-data and selector confirmations.

