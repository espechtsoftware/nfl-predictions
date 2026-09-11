# PREREG-083 minimal-core neighborhood diagnostic

Date: 2026-09-10  
Status: outcome-viewed development diagnostic; no adoption or Week-1 policy change

## Decision

Stop work on Neo4j importer packaging. The loaded graph and its immutable source
artifact have already isolated a narrower scoring hypothesis: the current system
often reaches a useful QB-centered seed but chooses the wrong remaining six-player
completion. Test fixed-work multi-completion mechanics next. Do not interpret this
diagnostic as evidence that the proposed treatment improves prospective scores.

## What the diagnostic found

- Across the two PREREG-083 arms, 24 candidates scored at least 200 points. Every
  one had at least one alternative in the same cell and arm sharing its quarterback
  and at least one same-team WR/TE.
- The control arm's median high-score neighborhood contained nine alternatives;
  the treatment arm's median contained 7.5. Median counts already selected into
  K80 were three and 4.5 respectively. The generator therefore had multiple legal
  completions around the seed; this is not simply a missing-core problem.
- The three 220+ candidates make the failure concrete:

  | Candidate | Book result | Alternatives | Selected alternatives | Best selected alternative | Belief rank in neighborhood |
  |---|---:|---:|---:|---:|---:|
  | 2023 Week 9 control, 227.20 | rank 64 | 10 | 5 | 172.40 | 5/11 |
  | 2023 Week 3 treatment, 225.64 | rejected | 10 | 7 | 202.14 | 4/11 |
  | 2023 Week 3 treatment, 221.50 | rejected | 6 | 4 | 217.06 | 2/7 |

- The K20-to-pool hindsight gap is not dominated by the headline stack. Comparing
  each arm's best pool candidate with its best K20 candidate, the mean realized
  gap attributable to the top three scoring players is `+6.735` control and
  `+5.904` treatment. The remaining six players contribute `+11.972` and
  `+11.511`. Completion is the larger recoverable component.
- This is consistent with the broader funnel: K20 leaves `18.707/17.415` points of
  control/treatment hindsight headroom, K80 still leaves `6.106/5.001`, and the
  PREREG-083 pool itself never reaches 230. Ordering work can recover some existing
  value, but a championship-range result also requires better candidate supply.

## Immediate experiment

Run the bounded PREREG-086 mechanics comparison, not a graph-product project:

1. Preserve equal work: D800 standard control versus 400 standard treatment solves
   plus 40 minimal QB/receiver seeds times ten deterministic, distinct completion
   attempts.
2. Allow legal core expansion while retaining the seed; require at least eight
   unique legal completions for at least 38 of 40 seeds before any outcome read.
3. Bind ordered candidate IDs and exact matrix bytes for the incumbent and
   corrected-hsim-v0.14 critics on disjoint search, validation, and audit banks.
4. Read full-pool 230+ supply and oracle first, then K20 and K80 capture. A ranking
   gain without new high-tail supply does not answer the main scoring problem.

The graph remains available for follow-up questions, but no importer polish,
deployment, visualization, or schema generalization is on this critical path.

## Exact reproduction

Work from `/home/erich/projects/nfl2-review-prereg083-r2-20260910` with
`PYTHONPATH=src /home/erich/projects/nfl2/.venv/bin/python`. Input is
`results/prereg083_direct_tail_score_r1.json`, physical SHA-256
`2e291abbad5792c8ec72da802891ba49575b9aeca260b771b3df46cb47778e9a` and internal
result SHA-256
`fece63a5449985424c8b502fe387b2eebd1ae9a540694edf198fbc3eabf19d56`. Join player
position, team, opponent, and actual score using `nfl2.pipeline.slate_frame` and
`drop_duplicates("id")` for the cell's season and week.

For each focal candidate with realized score at least 200, define its neighborhood
within the same cell and arm as candidates sharing its unique QB and at least one
same-team WR/TE from the focal roster. The bring-back may vary. Exclude the focal
candidate when counting alternatives; `selected_rank is not None` denotes K80.
Rank belief by descending `fresh_bank_sim_mean` with stable ties.

For the top-three/bottom-six split, choose the realized-score maximum from the full
200-candidate pool and from `selected_rank <= 20` in each cell and arm. Map roster
IDs to immutable actual scores, sort each roster's nine values descending, and
subtract K20 from pool for the top three and remaining six values separately. Take
the arithmetic mean of each component over the 36 slates.
