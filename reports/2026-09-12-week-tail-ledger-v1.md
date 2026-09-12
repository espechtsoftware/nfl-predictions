# Week tail ledger v1 — the per-week post-settlement tail record

**Date:** 2026-09-12 · **Source:** state audit §5.1 · **Status:** built, smoke-tested
against the real Week-1 publish with fabricated actuals; first real row is due
after Week-1 settlement.

## What it records

One self-hashed JSON row per slate, written only after every represented game
is final:

- for each candidate pool (`D800_DEMAX`, `D400_DEMAX`): size, realized maximum,
  mean, and the count of lineups at or above 194/200/210/220/230/240;
- for each published book (`P_MIX`, `P_CTRL`, `D400_DEMAX`, `D800_WEMAX`):
  the same, plus — against each pool — the retrieval gap (pool max minus book
  max), whether the pool's best lineup was in the book and at what rank, the
  rank of the book's best score inside the pool, and how many book rosters
  came from that pool;
- the contest winning score when supplied, with the margin of every book and
  pool maximum to it and two flags (`beaten_by_any_book`, `beaten_by_any_pool`);
- the exact identity (uri/generation/sha256/bytes) of every input, and
  `uses_target_week_outcomes: true` with every authority field pinned false.

With ~17 slates a season no arm reaches significance at 220, so the honest
weekly KPIs are 200+/210+ supply and the pool oracle; 220+/230+ are counted
and reported, never gated (audit §5.1).

## Code

- `src/nfl_dfs/research/week_tail_ledger_v1.py` — pure builder and validator.
  The scorer fails closed on any roster id without an actual, any non-finite
  actual, repeated rosters or lineup ids, ranks that are not exactly 1..n, and
  a capture time not after lock. The validator re-derives the self-hash,
  monotone tail counts, max-vs-count agreement, retrieval gaps, winner margins
  and flags (it never trusts a caller's arithmetic).
- `scripts/run_week_tail_ledger_v1.py` — reads the A5 publish by run id,
  exact-reopens each book by its pinned identity
  (`GCSImmutableObjectStore.read_exact`), loads both pools and frames, joins
  actuals, and writes the row create-only. Warehouse mode queries
  `nfl_features.player_week_actuals` and `team_defense_week` and refuses unless
  the latest `nfl_raw.pbp` row of every represented game is an end-of-game
  marker. JSON mode exists for smokes and labels itself in the row.
- `tests/test_week_tail_ledger_v1.py` — exact synthetic scoring, determinism,
  twelve bad-input mutations, six tampered-row mutations (with coherent
  rehash where the self-hash would otherwise mask the check), and a coherent
  rehash that cannot hide a max-vs-count contradiction.

## Reality-contact smoke (rule 1 of the frozen-chain lessons)

Run against the real `20260910t2315z-fa5d035` publish with constant fabricated
actuals (`producer_class: smoke-fabricated-constant-actuals-not-a-result`):
nine identities captured (terminal, four books, two pools, two frames), 4 × 80
book entries and 800/400 pool rosters scored, every book roster found in the
D800 pool, the row validated. Nothing was published; the smoke row lives in
the session scratchpad only.

## Tuesday procedure (after Monday's standings capture)

```
cd <clean checkout of main>
PYTHONPATH=src .venv/bin/python scripts/run_week_tail_ledger_v1.py \
  --run-id <the Sunday --execute publish run id> --season 2026 --week 1 \
  --captured-at <ISO-8601 UTC, after settlement> \
  --actuals-source bigquery \
  --winner-score <Millionaire winning score> \
  --winner-source "dk standings capture <contest_id> <captured_at>" \
  --winner-contest-id <contest_id> \
  --output reports/week-tail-ledger/2026-w01.json
git add reports/week-tail-ledger/2026-w01.json   # the row is the record
```

If the warehouse actuals for Week 1 have not landed yet, the script refuses
(no actual for an id, or a game not final); do not fall back to JSON mode for a
real row.
