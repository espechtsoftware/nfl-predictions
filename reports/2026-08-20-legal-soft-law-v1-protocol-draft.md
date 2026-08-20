# Legal-soft-law-v1 integrated policy — protocol draft

**Protocol ID:** `20260820-legal-soft-law-v1`

**Status:** `READY-AWAITING-A2A-AND-B1` — mocked scaffold only; not frozen,
not smoke-licensed, not outcome-licensed, not deployed, and not adopted

**Scope:** one integrated construction-and-ranking policy, no factorial

## 1. Question

Can the program replace most house construction mandates with a DK-legal
candidate domain and a learned corpus-tail ranker, while preserving enough
deterministic incumbent and exact-one-stack candidate support to avoid the
naked-QB collapse observed in A3?

The target is the weekly maximum of an exact-80 book. The practical design
goal is:

- mean treatment candidate ceiling `C >= 205`; and
- mean treatment conversion gap `C-S <= 5`, where `S` is the treatment
  exact-80 weekly maximum.

These are necessary milestones for a credible path toward a 200-point mean
weekly maximum, not a promise that the system will reach 200. The current
evidence does not support that promise:

- the registered selected baseline is about `176.06`;
- the all-boom pool raised mean `C` to `196.64`, but its exact-80 mean reached
  only `179.91`; and
- the full generated B1 union's hindsight ceiling is about `198.10` over the
  54-slate corpus (`198.74` on the 51 winner-matched slates).

Thus a perfect selector cannot average 200 from today's union. A successful
policy must improve candidate supply and conversion together. The measured
ordinary conversion gap is about five points, which is why 205, rather than
200, is the registered on-track ceiling.

## 2. Boundary and hard prerequisites

This draft is deliberately prepared before either prerequisite result can be
used to redesign it. It may not advance to a real-artifact outcome-blind smoke
or be SHA-frozen unless both of these independently harvested, content-pinned
results pass literally:

1. **A2a realized-law:**
   `passes=true`, disposition
   `a2a-law-shape-passes-single-stack-protocol-licensed`, the exact registered
   A2a license map, and no candidate or lineup score read.
2. **B1 corpus-tail model:**
   `historical_pass=true`, version
   `b1-corpus-tail-historical-evaluation-v1`, the exact positive B1 license
   map, no winner feature/target, and a portable
   `b1-corpus-tail-logit-v1` artifact with
   `historical_gate_passed=true`, `production_licensed=false`, and a complete
   generation/bytes/SHA identity.

Any A2a miss or B1 miss closes this draft. Neither result may trigger a dose
change, support allocation change, alternate model, feature search, or grid.

The current files accept only `mocked=true` and `mock://` identities. Even a
mocked favorable truth-table evaluation leaves every real smoke, freeze,
historical, shadow, retry, and production license false.

## 3. What remains hard

Only the following are universal feasibility or scientific constraints:

1. DraftKings Classic legality:
   - exactly nine unique players;
   - one QB and one DST, 2--3 RB, 3--4 WR, and 1--2 TE;
   - salary at or below $50,000;
   - at least two games represented; and
   - no more than eight players from one team.
2. Slate eligibility, pre-lock eligibility, and a timezone-aware feature
   snapshot strictly before contest lock.
3. Exactly 80 unique control entries and 80 unique treatment entries.
4. Equal, declared compute, solve, world, and candidate budgets within every
   paired slate.
5. Content identity for sources, player worlds, solve schedule, prerequisite
   reports, and model artifact.
6. Walk-forward/season-held-out model evidence and the historical-outcome
   firewall required by `CLAUDE.md`.

These safeguards are not the rules being relaxed. They protect the score
claim from leakage, hindsight, unequal compute, and unverifiable execution.

## 4. What becomes soft

The following house-strategy traits are no longer universal treatment
constraints and may never become final-book quotas in v1:

- same-team QB WR/TE partner count, including naked, exact-one, and double;
- bring-back count;
- the $49,000 salary floor and unused salary;
- RB versus opposing DST and two same-team RB;
- games and teams represented beyond DK's minimum, plus maximum game/team
  concentration; and
- point-in-time ownership-sum and duplication-risk estimates when available.

Every treatment candidate records the exact feature surface:

```text
salary_total, unused_salary,
qb_partner_count, bring_back_count,
rb_vs_dst_count, same_team_rb_pair_count,
games_represented, teams_represented,
largest_game_block, largest_team_block,
ownership_sum_est, duplication_risk_est
```

Salary, stack, bring-back, games, teams, and concentration already overlap the
frozen B1 corpus-tail feature set. The two RB traits remain explicit audited
features and are retained inside the support sleeves; they receive no
hand-written ranking penalty. Ownership and duplication are point-in-time
signals only and may be null; v1 does not refit or add an ownership model.

The pure module reconstructs every structural feature from the roster where
possible. It therefore detects a disguised hard constraint or a malformed
feature receipt instead of trusting caller assertions.

## 5. Fixed control and treatment

### Control

The control is the incumbent canonical R0-native candidate pool and its stored
current exact-80 selected book. Control is reproduced, not reranked.

### Treatment

Treatment uses the same A2a-transformed worlds, seed IDs, world counts, solve
attempt count, solve-schedule identity, and per-slate candidate count as
control. It changes only construction feasibility/support and final ranking.

For each slate, let `B_s` be the incumbent R0-native candidate count fixed
before any outcome read. The observed range is 241--265; the scaffold requires
at least 241. Treatment must return exactly `B_s` unique legal candidates:

- exactly 80 incumbent-law support candidates;
- exactly 80 exact-one QB-partner support candidates, retaining incumbent
  bring-back, salary, and RB rules; and
- exactly `B_s - 160` legality-only candidates.

This is a fixed **candidate-generation support allocation**, not a final-book
quota. Eighty candidates in each protected sleeve allow either sleeve to fill
an exact-80 book if the model prefers it; the remaining supply is fully open.
The allocation is frozen in this draft and may not be tuned after either
prerequisite or any treatment outcome.

The compute contract is:

- five seed/world blocks, IDs `0..4`;
- exactly 10,000 worlds per block, 50,000 total;
- the same five immutable world-draw identities in both arms;
- identical total solve attempts and one common solve-schedule SHA per slate;
- exact paired candidate budget `B_s`; and
- exactly 80 final entries per arm.

No extra candidates, worlds, solves, retries, or fallback family may be added
to make treatment fill.

## 6. Learned ranking and absence of final quotas

Every legal treatment candidate receives the score produced by the exact
portable B1 corpus-tail artifact. The future real runner must recompute that
score from the artifact and candidate feature vector; it may not trust a
caller-supplied probability. The present mocked scaffold accepts a supplied
`model_score` only to exercise deterministic accounting and ranking.

Treatment ranking is exactly:

1. descending corpus-tail model score;
2. descending point-in-time simulated `p_line` only as a deterministic tie;
3. descending point-in-time simulated q99 only as a deterministic tie; and
4. ascending canonical roster key.

Take the first 80. There is no overlap cap, sleeve minimum, stack minimum,
bring-back minimum, salary floor, RB rule, game-spread rule, ownership quota,
or duplication quota in final selection. A legal book of 80 naked-QB lineups
or 80 incumbent-shaped lineups is allowed if the fixed model order produces
it. The receipt reports selected sleeve/feature counts descriptively.

## 7. Required outcome-blind reality contact before freeze

Only after both prerequisites pass, one real-artifact 2023 Week 1 smoke may be
implemented and run. Before that smoke this draft still lacks production glue
and intentionally cannot access data.

The future smoke must prove, without selecting any actual score, winner,
contest rank, payout, or realized ownership:

1. exact A2a and B1 result/artifact identities;
2. exact point-in-time source completion before lock;
3. byte-identical worlds and solve schedule across arms;
4. exact paired solve and candidate budgets;
5. direct DK legality reconstruction for every roster;
6. exact `80/80/(B_s-160)` support allocation;
7. exact corpus-tail score recomputation from the pinned model artifact;
8. deterministic treatment rank and exact-80 fill; and
9. non-vacuity: at least one legality-only candidate reaches a treatment book
   and that book differs from control.

Failure closes the draft or requires a new pre-outcome protocol. It does not
authorize an in-place receipt/schema repair followed by outcome access.

## 8. One historical comparison and registered reading

If, and only if, the prerequisites, real smoke, freeze, clean exact-source
build, empty create-only prefix, free historical lease, and independent launch
review all pass, one historical comparison may be proposed. The future freeze
must hash-pin the complete 2023--2025 slate lattice and every `B_s` before the
outcome query. Partial result bodies are never inspected.

For both arms report:

- weekly candidate ceiling `C`;
- exact-80 weekly maximum `S`;
- complete 194/200/210 weekly counts; and
- mean `C`, mean `S`, and mean `C-S`.

The basic selection gate requires all four:

1. treatment mean `S` strictly exceeds control mean `S`;
2. treatment produces strictly more 200+ weeks;
3. treatment 194+ weeks are noninferior; and
4. treatment 210+ weeks are noninferior.

The 200-track gate additionally requires both:

5. treatment mean `C >= 205`; and
6. treatment mean `C-S <= 5`.

If the selection gate and 200-track gate pass, the historical result may
license the design of one fixed 2026 prospective shadow and may describe the
policy as on track for the 200 objective. If the basic selection gate passes
but either 200-track gate misses, the result may license only an incremental
shadow design and must not make a 200 claim. Any basic selection-gate miss
closes v1. No historical result directly licenses a shadow execution,
production, a retry, or another historical model/rule variant.

## 9. No factorial and no salvage tree

There is exactly one treatment. This draft forbids:

- rule-by-rule arms;
- alternate support allocations;
- k/dose sweeps;
- alternate candidate or compute budgets;
- model, feature, coefficient, threshold, overlap, or tie-break grids;
- post-result optimizer changes;
- a constraint-lattice resurrection; and
- combining a bring-back, ownership, spread, world, or selector variant.

A failure is a failure of this integrated policy. It is not permission to
inspect the losing slates and choose a more favorable rule subset.

## 10. Current implementation boundary

Exactly four isolated files constitute this preparation:

- this draft;
- `src/nfl_dfs/research/legal_soft_law.py`, pure validation/accounting/rank;
- `scripts/run_legal_soft_law.py`, canonical local mocked JSON only; and
- `tests/test_legal_soft_law.py`, focused mocked contracts.

There is no optimizer seam, model fitting, warehouse query, GCS client, cloud
launcher, watcher, lease, outcome source, deployment integration, production
lever, or shared-file change. No protocol/source hash is frozen yet. The next
action is simply to wait for strict terminal A2a and B1 dispositions. Only a
double pass can authorize designing the real-artifact smoke glue; it cannot
authorize running outcomes or changing production.
