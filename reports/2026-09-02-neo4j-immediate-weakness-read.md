# Neo4j immediate weakness read

**Read time:** 2026-09-02T17:32:02Z  
**Evidence class:** descriptive development only  
**Decision/promotion authority:** none

## Outcome

The existing local Neo4j E0 slice is usable now and already identifies a
material weakness: the historical system produced valuable lineups that its
retrieval books usually did not retain. It also exposes a strong structural
bias in the coverage-194 selector. It does not yet contain enough point-in-time
feature data to explain boom, coverage-map, ownership, projection, or SIS/Fantasy
Points matchup effects.

The highest-value path is therefore:

1. use E0 now for fixed-pool generation/retrieval hypotheses;
2. test those hypotheses as bounded selector sleeves, never new universal laws;
3. add the adopted D800 artifact adapter to the new pre-lock lineage collector;
4. attach a summary-only point-in-time phenotype companion after exact source
   coverage is known; and
5. keep Neo4j read-only and downstream of scoring and selection.

## Live graph verification

The localhost-only Neo4j 5.26.30 service answered through Bolt/HTTP on
`127.0.0.1:7687` and `127.0.0.1:7474`. Direct read-only Cypher reproduced the
receipt-bound E0 plan
`e852521d97d3cb37d8e46c6336694f003114b72aa9908277ee7783a1fe1b6821`:

- 4,258 `HistoricalCorpusEntity` nodes;
- 8,623 historical relationships;
- 54 slates;
- 199,244 reconciled eligible candidates;
- 378,000 generation visits;
- 432 K80 final-fit books / 34,560 selections; and
- 279 persisted lineups with realized score at least 200.

No write query, graph load, scoring operation, cloud action, or outcome rescore
was performed.

## Weakness 1: final-book retention is poor

Of 279 distinct eligible 200+ lineups, only 38 appeared in any observed K80
book; 241 were absent from all eight final-fit strategies. Twenty-nine of 54
slates offered at least one 200+ eligible lineup. Any strategy converted only
10 of those slates, and coverage-194 converted six.

For coverage-194 specifically:

- mean selected weekly maximum: **176.882**;
- mean hindsight eligible-corpus maximum: **202.662**;
- descriptive within-corpus regret: **25.780**;
- positive-regret slates: 50 of 54; and
- eligible 200+ opportunity but selected below 200: 23 slates.

This does not mean a forecastable selector can recover 25.780 points. The
eligible maximum is outcome-known. It does establish that supply alone is not
the whole problem and that fixed-pool retrieval tests deserve priority.

The largest coverage-194 gaps are concentrated enough to audit directly:

| Slate | Eligible max | Coverage max | Gap |
|---|---:|---:|---:|
| 2025-W09 | 234.34 | 181.30 | 53.04 |
| 2025-W06 | 213.28 | 160.48 | 52.80 |
| 2023-W09 | 229.60 | 176.90 | 52.70 |
| 2024-W09 | 209.76 | 159.94 | 49.82 |
| 2025-W16 | 200.76 | 155.96 | 44.80 |

## Weakness 2: coverage-194 has a dense-stack blind spot

The selector's captured 200+ lineups are not structurally representative of
the available 200+ set:

- it captured **0 of 48** high scorers with zero QB teammates;
- **0 of 43** with one QB teammate;
- 2 of 129 with two;
- 6 of 55 with three; and
- 1 of 4 with four.

It captured **0 of 124** high scorers whose largest same-game group was three
players or fewer. All nine coverage-captured 200+ lineups had a four-player-or-
larger same-game group. It also captured 0 of 37 high scorers spanning seven or
more games.

Across every final-fit strategy, captured high scorers averaged 2.211 QB
teammates and a 4.105-player largest game group, versus 1.651 and 3.585 among
missed high scorers. This is selection-conditioned evidence: it describes what
the current selector rewards and must not be turned into a universal anti-stack
or pro-stack rule.

The same pattern appears in team concentration. Any strategy captured 23 of 57
high scorers with four players from one team, but only 7 of 144 whose maximum
same-team count was three. Most available high scorers had two QB teammates
(129), yet only seven reached any final-fit book; 21 of the 55 three-teammate
lineups were captured. The present strategy family is collectively concentrated
on the smaller three-teammate phenotype.

The blind spot persists in the extreme tail. Coverage-194 retained only 4 of
34 lineups scoring at least 220, missing 30. Its top misses included 241.10,
239.96, 239.10, and 235.60. Two of the top three spanned seven games and had
only one or two QB teammates.

## Weakness 3: one threshold is an inadequate generation objective

At the 200 threshold, global rule removal generally did not improve generation
density on this old panel:

| Arm | 200+ visits / 54,000 | Rate per 1,000 | 220+ visits | 230+ visits |
|---|---:|---:|---:|---:|
| allow-rb-vs-dst | 94 | 1.741 | 13 | 2 |
| incumbent | 93 | 1.722 | 12 | 1 |
| allow-two-rb | 91 | 1.685 | 13 | 1 |
| remove-salary-floor | 88 | 1.630 | 13 | 1 |
| remove-bring-back | 80 | 1.481 | 12 | 3 |
| remove-qb-stack | 75 | 1.389 | 9 | 2 |
| remove-all-five-shared-constraints | 53 | 0.981 | 6 | 0 |

This argues against simply deleting every construction rule. It also shows why
200+ count alone is insufficient: remove-bring-back is weak at 200 but has the
most 230+ occurrences, while world block R2 has the most 220+ occurrences (28)
despite R0 having the most 200+ occurrences. A generation allocation should be
evaluated across a threshold vector and weekly maximum, not tuned to one count.

These are reused-panel hypothesis coordinates. The later D800 no-bring-back
sleeve did not validate, so this graph read does not resurrect it.

One precise funnel hole is nevertheless worth preserving: `remove-bring-back/R0`
generated 19 distinct 200+ lineups, including the highest lineup missed by every
strategy at 239.96, and none of those 19 appeared in any final-fit book. This is
an especially clean candidate for a retrieval-only diagnostic because the
lineups already existed in the eligible pool; generation need not change.

## Weakness 4: selector families contain useful but unexploited complementarity

On the same eligible pools, the best historical final-fit strategy was the
block-supported tail ladder at 178.435 mean weekly maximum, 1.553 above
coverage-194. Mean-score selected the most distinct 200+ lineups (22 versus
coverage's nine) but had the lowest mean weekly maximum (176.003). Counting
high scorers is therefore not enough; severity, slate coverage, and book
interaction matter.

Coverage and the block-supported ladder shared six 200+ lineups. Coverage had
three unique captures and the ladder seven. A hindsight best-of-the-two weekly
union averaged 179.951, 1.516 above the ladder alone; coverage won eight weeks,
the ladder 15, with 31 ties. This is evidence of complementarity, not an
achievable fixed-K gain. It supports testing a predeclared K80 split or
diversity sleeve on frozen D800 pools rather than choosing a winner after
outcomes.

## What Neo4j cannot answer yet

The 54 historical attribution shards explicitly record
`point_in_time_player_traits_attached = null` and contain no player realized
contribution decomposition. The graph has player ID, position, team, opponent,
game, salary, lineup structure, generation arm/block, final-book membership,
and realized roster score. It does **not** currently carry:

- boom classification or boom probability;
- Fantasy Points/SIS/FantasyPros receiver-defender coverage grades;
- opponent allowance to WR1/WR2/slot/TE roles;
- point-in-time ownership, projection distribution, leverage, or market blend;
- selector marginal values or complete admission/rejection transitions;
- official winner identity/score authority; or
- the adopted D800 single-bank dual-EMAX candidate/book lineage.

Consequently E0 localizes the current evidence only to
`FIRST_OBSERVED_ABSENCE_AT_FINAL_BOOK`; it cannot yet prove the earlier causal
loss stage or attribute the miss to a specific pre-lock feature.

## Concrete implementation and test sequence

### Today: use the evidence already present

1. Preserve the queries above as the baseline weakness read.
2. Audit the five largest-regret slates and the 34 lineups at 220+ by structure,
   originating arm/block, and strategy overlap.
3. Specify two fixed-pool, exact-K historical tests:
   - coverage-194 versus the already defined block-supported ladder; and
   - coverage-194 K80 versus a predeclared mixed book that reserves a small
     sleeve for candidates underrepresented by coverage (initial diagnostic:
     two-or-fewer QB teammates, with an explicitly reported
     `remove-bring-back/R0` subcohort).
4. Select the sleeve using pre-lock candidate attributes only. Freeze its size
   before realized scoring. Treat it as a selector experiment, not a new lineup
   legality law.

Experiment 087 is already the decision-bearing aligned-selection crossing on
the adopted D800 pools. Its read should be consumed before launching a redundant
selector test; the E0 findings should be used to explain its result and choose
the next bounded sleeve.

The existing bounded API can be used immediately without a new graph load:

- `GET /api/corpus-research/historical-realized-summary`
- `GET /api/corpus-research/historical-realized-summary/first-observed-absence`
- `GET /api/corpus-research/historical-realized-summary/rescue`
- `GET /api/corpus-research/historical-realized-summary/rescue?strategy_id=coverage-194-v1`

The current corpus-research dashboard is not yet connected to these endpoints,
and graph-v2 has no loaded nodes. UI wiring is presentation work after the
retrieval hypotheses and D800 capture path are settled; it should not block
today's reads.

### Next code slice: trace the real production book

The newly merged pre-lock lineage infrastructure is default-off and repaired,
but its runner invokes the legacy five-seed CBWU path. Add one narrow adapter
that either calls the adopted D800 generator/selector or consumes the immutable
D800 candidate, matrix, and selected-book artifacts. Preserve candidate order,
world order, dual-EMAX law, K80 selection, and exact roster identities. Do not
change scoring or selection to satisfy the lineage collector.

Before a provider shadow, add a fixed launcher receipt binding Cloud Run
execution UID, job generation, image digest, resource envelope, timeout, and
retry law. Then run one candidate-only pre-lock D800 smoke and exact-reopen its
five-object root.

### Then: add feature intelligence as a separate summary companion

For each frozen candidate, join the exact point-in-time player feature snapshot
by slate and player ID outside Neo4j. Emit only bounded cohort summaries for
captured versus missed 200+/220+ lineups, including missingness and source
identity for every field. Candidate-level feature rows remain in immutable
artifacts; Neo4j receives aggregates only.

First priority fields are boom probability/class, coverage matchup and role,
ownership/leverage, projection distribution, salary, stack/correlation shape,
and market context. No field may enter the comparison if it was created after
lock or lacks an exact historical source. This companion is what will answer
whether the selector missed a lineup because it undervalued boom, receiver-
defender matchup, ownership, or correlation—not merely that the lineup was
absent from the book.
