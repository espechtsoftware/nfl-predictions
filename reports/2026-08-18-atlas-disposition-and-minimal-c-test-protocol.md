# ATLAS disposition and minimal world-selection C-test protocol

Date: 2026-08-18. **No code was changed. No outcome was queried.**

Two parts: (A) formal disposition of the existing ATLAS evidence, and (B) a
proposed frozen protocol for the one test ATLAS has never had.

---

# Part A — Disposition of the existing ATLAS evidence

## A.1 The two "passes" are near-tautological and are retired as adoption evidence

ATLAS selects worlds using `roster_slot_upper_bound`
(`src/nfl_dfs/analysis/atlas_world_ranking.py:34`), documented in its own source
as a "cheap roster-sized upper bound" that "enforces the exact QB/DST and
RB/WR/TE slot counts, but relaxes salary, team, minimum-games, stack,
rb-anticorrelation."

Both completed ATLAS experiments then evaluated **mean exact attainable legal
optimum** — the exact MILP solve of the best legal lineup in the worlds ATLAS
selected.

**The ranking key is a relaxation of the evaluation metric.** The transfer
result itself records a proxy/exact union rank correlation of **0.6064** with
**27.0615** points of mean proxy-minus-exact slack. Selecting worlds by a
0.61-correlated proxy of a quantity and then measuring that quantity will pass
under nearly any implementation.

| result | reported effect | what it establishes |
|---|---|---|
| Phase S score-free | +12.8754 mean, +14.8784 q25, 5/5 blocks | the sort key sorts |
| Production-law transfer | +10.9340 mean, +12.5817 q25, 270/270 cells | the sort key sorts under the money law |

Both remain **mechanically valid and honestly reported**. Neither was ever
framed by its authors as a score result. But they are **not evidence that ATLAS
improves anything the operator is paid for**, and they may not be cited in an
opportunity register, a queue-priority argument, or an adoption case. Their
correct standing is: *the world ranker ranks worlds as designed.*

## A.2 What ATLAS has never measured

| endpoint | measured? |
|---|---|
| attainable world quality | yes (A.1, circular) |
| **candidate `C`** | **never** |
| **selected `S`** | **never** |
| **realized DK score** | **never** |

## A.3 The six grid attempts produced no science

| grid | outcome |
|---|---|
| repair2 | CBC `SIGKILL` at ~84% of a 4 GiB cap |
| repair3 | all 54 cells rejected a new prefix (hard-coded constant) |
| repair4 | one 16 GiB memory failure + 6 platform errors |
| repair5 | `ATLAS world <n> identity tiebreak is infeasible` |
| repair6 | dual-canary execution failed; closed `no-scoreable-population` |

**Every one of these was an attempt at the matched-diversity MVP**, not at ATLAS
itself. The MVP adds eight structural world clusters x five near-optimal
lineups, pair/triple interaction pricing with leave-one-seed-out robust support,
and a three-stage MILP with interaction floors — producing the 9,277-row x
3,401-column models that killed CBC repeatedly.

**The MVP is what is unrunnable. The ATLAS hypothesis was never tested.**

## A.4 Disposition

- The matched-diversity MVP is **closed**. It may not be attempted a seventh
  time in any form.
- The ATLAS world-ranking hypothesis is **not closed**, because it has never
  been tested against a paying endpoint. It gets exactly one minimal test
  (Part B) and no more.

---

# Part B — Proposed protocol: minimal world-selection C test

**Status: proposal.** It must be frozen with real source/image/protocol hashes
by whoever implements the runner, before any outcome is opened.

Protocol ID: `20260818-atlas-minimal-world-selection-c-v1`

## B.1 Question

At **exactly equal candidate budget**, does ranking boom-family worlds by a
roster-shaped attainable upper bound rather than by total slate points improve
the best generated candidate `C`?

## B.2 The treatment is one line

The incumbent boom family selects worlds at
`src/nfl_dfs/backtest/engine.py:1067`:

```python
boom_order = np.argsort(rd.sum(axis=0))[::-1]      # control: total slate points
```

The treatment replaces that ranking key only:

```python
boom_order = rank_worlds(roster_slot_upper_bound(rd, positions), n)  # treatment
```

using the existing deterministic `rank_worlds` lexsort tiebreak on world id.

**Nothing else changes.** Same generator, same six families, `N_BOOM = 40` in
both arms, same role-12 allocation, same salary floor, same stacking contract,
same selector, same seeds, same dedup. Budget parity is exact **by
construction**, not by post-hoc trimming.

This isolates the ATLAS hypothesis — *is a roster-shaped world ranking better
than a naive points-sum ranking?* — from every confound the MVP introduced.

## B.3 Population and sources

- 54 slates, 2023-2025 Weeks 1-18. No slate may be dropped.
- Worlds: the **already-acquired, already-validated** 270 production-multinomial
  artifacts from `20260815-atlas-current-money-transfer-v1` (269
  `candidate_table` bindings plus the one preregistered GCS recovery cell). No
  new world acquisition is required or permitted.
- Realized scores: `nfl_predictions.slate_player_features.actual`, joined on
  exact `(season, week, id)`, with the existing 68,199-row actual-score parity
  preflight recomputed in the scorer.

## B.4 Execution envelope

Ordinary lineup MILPs with **no interaction variables**. This is the same solve
class the production generator already runs weekly, and it is the reason this
test is affordable where the MVP was not.

- Shard by slate; 54 create-only cells; 4 CPU / 16 GiB.
- **Real-path canary**: run cell 1 on the actual launch path, job and output
  prefix, confirm a valid object, then release the remaining 53.
- **Bounded retry**: one replacement execution, admissible only for a literal
  platform error with zero objects written. Never for memory, timeout, solver,
  signal, or ambiguous failure.
- Capture per-execution peak memory from Cloud Monitoring metadata.

## B.5 Endpoint and gate

Primary endpoint is candidate `C` = max realized score over the pool. The
unchanged exact-80 selector is also run and `S` reported.

**Gate — all must hold:**

1. mean `C` strictly improves;
2. no decline in distinct slates reaching **220**, **230** or **240**; and
3. all mechanical and parity invariants pass.

**Mandatory context, explicitly non-gating:** counts at 187/194/200/210,
per-season rows, **the number of distinct slates that moved** (not the nested
threshold grid), mean/median/paired win-tie-loss, leave-one-slate-out ranges,
and the three diversity measures — **player-pair reach, QB-stack-core reach and
dominant-game reach**.

No alternate threshold weighting, post-hoc band, season veto or re-parameterized
ranker may rescue a failure.

## B.6 Predeclared prior: this is expected to fail

Recorded before any outcome is opened, so that a null reads as confirmation
rather than disappointment:

- ATLAS reduced mean player-pair reach to **0.9520** and dominant-game reach to
  **0.9080** under the production law.
- CBWU-OI — the **only** mechanism that has ever moved `C` (+5.66) — achieved it
  with pair reach **+41%** and stack-core reach **+52%**, while *worsening*
  player coverage.
- On that evidence combination breadth is the mechanism, and ATLAS moves it the
  wrong way.
- Conceptually, high-attainable worlds are extreme worlds; lineups built for
  them are specialized, and dominant-game concentration means being wrong about
  *which* game explodes costs the whole batch.

**Expected result: no improvement in `C`, possibly a decline.**

## B.7 Consequence

- **Pass:** ATLAS world ranking becomes a live candidate-generation lever and
  earns a separately frozen prospective 2026 shadow. It does not change
  production on this result alone.
- **Fail or null:** the **entire ATLAS world-ranking family is closed
  permanently.** No variant proxy, no re-parameterized `N`, no threshold sweep,
  no reopening on these 54 slates. The world-quality passes in Part A remain
  retired.
- Either way this licenses no production change, no money-book change and no
  UI change.

## B.8 Why this is the last ATLAS test

Ten days of the single heavy research slot have produced six failed grids, zero
scoreable populations, and two circular passes. The hypothesis deserves one
clean, cheap, decisive measurement against a paying endpoint. It does not
deserve a seventh elaborate one.
