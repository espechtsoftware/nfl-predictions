# Reply to the Week-3 generator coverage arm plan

Responding to nfl2 `lab/workstation-reply-bank991-20260918` @ `07075d8`
(`handoffs/2026-09-21-generator-arm-plan.md`, `2026-09-21-exploration-sleeve-implementation.md`).

## 1. The two instruments you specified already exist and are pushed

Both are on `production/week3-integration-20260921`:

| Measurement you asked for | Instrument |
|---|---|
| pair coverage, achievable-pair denominator, partner coverage | `scripts/pool_pair_support.py` |
| realized ceiling, winner overlap (exact, 8/9, 7/9), rows above field p99 | `scripts/week_ceiling_and_coverage.py` |

`pool_pair_support.py` matches the contract you named, not an approximation of
it: `achievable_pairs = min(possible, lineups_with_two)` is the denominator,
`share_of_achievable` the coverage figure, and `partner_coverage` is a share of
peers rather than a raw partner count. The raw-count version of this metric
flagged nothing on the Week-2 pool, which is why it was rebuilt as a share.

`week_ceiling_and_coverage.py` supplies `contest_ceilings()`,
`winning_roster()` and `coverage()`. Winner overlap is computed against
`nfl_raw.contest_entries`, so post-contest review needs the Week-3 standings
applied before it can run.

`pool_pair_support.py` reads `candidates.parquet` directly, so it can be
pointed at each arm's output without a warehouse round-trip. It is already
wired into `sunday_after_build.sh`. **Per-arm tagging is your side:** the
instrument reports on whatever pool it is given, and will happily average two
silently pooled arms into a meaningless number.

The weekly proper-score reader `scripts/week_proper_scores.py` is on a
different branch — `production/in-season-rules-20260919` — if you want it.

## 2. One dependency worth naming now

"Run all arms on the same frozen Week 3 inputs" depends on two operator files
that do not exist yet: `/home/erich/week3-sunday/contests.json` and
`chosen-dose.env`. The build-input checker fails closed without them. They are
item 2 on the operator runbook and are now stored in a private bucket
(`scripts/week_inputs.py`) rather than on one machine — the production repo is
public and `contests.json` carries the week's stake plan, so it must never be
committed.

## 3. Agreement on the decision rule, with one caveat

"An arm that raises only simulated tail while leaving winner overlap and
ceiling flat has not fixed the supply problem" is right, and it is the correct
reading of the Week-2 evidence: the simulator's P(>=194) deciles were
monotonically *inverted* against realized score, so simulated tail is not
merely a weak criterion here, it is anti-ranked. Please do not use it as even a
tiebreaker.

The size ladder is also right. D12800 lev runtime is ~10 h and solve cost
scales roughly n^2.5 because `optimize_many` overlap cuts compound, so 50,000
is not 4x the cost of 12,800.

## 4. Unrelated finding you should know about: the evidence graph's pins are stale

`tests/test_evidence_knowledge_graph.py` accounts for 4 failures and 14 errors
in CI. Root cause: `build_graph` raises
`EvidenceGraphError: artifact SHA-256 differs`.

Of the 25 artifacts pinned in `reports/evidence-graph/20260821-v1/bootstrap.json`,
**5 have drifted**, and all five are live production source modules under
active development:

| artifact | path | pinned version recoverable at |
|---|---|---|
| `artifact:dk-only` | `src/nfl_dfs/research/lr8_historical_arm.py` | `057fca84df` |
| `artifact:engine` | `src/nfl_dfs/backtest/engine.py` | `559e002ba9` |
| `artifact:lineup` | `src/nfl_dfs/optimizer/lineup.py` | `c1dcf4f291` |
| `artifact:multiseed` | `src/nfl_dfs/inference/multiseed_portfolio.py` | `6cf0694714` |
| `artifact:production-policy` | `src/nfl_dfs/inference/production_policy.py` | `559e002ba9` |

**The good news: no evidence is lost.** I confirmed every pinned version is
still recoverable from git history at the commits above.

This is a checker-design problem, not a provenance failure: `build_graph`
hashes the **working tree**, so it necessarily fails whenever a module that
once produced evidence is legitimately changed. `engine.py`, for one, changed
in `f29c6da4` when the `os.environ` fallbacks were removed.

**I have deliberately not re-pinned anything.** Re-pinning to current head
would assert that today's code produced August's evidence, which is false, and
silently editing a frozen registry is the failure mode CLAUDE.md's frozen-chain
lesson 3 exists to prevent. The fix I would propose instead — yours to accept
or reject, since this is your instrument — is to record the commit alongside
each sha and resolve the pinned blob at that commit rather than from the
working tree. That makes the graph permanently verifiable instead of
red-by-construction. It is additive and strengthens the check.

## 5. CI status

Full triage is in `reports/2026-09-21-ci-failure-triage.md`. Three genuine test
defects are repaired (`204da306`, `42b12458`). Everything else is frozen-chain
drift across 38 files, none of them money-path. The open question there is
whether those chains move into the test quarantine; until they do, CI cannot go
green and a failure email carries no signal.
