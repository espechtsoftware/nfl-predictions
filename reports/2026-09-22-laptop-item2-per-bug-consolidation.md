# Laptop → production: the per-bug consolidation, derived from the repository

Item 2's broader ask — per bug: introduced commit, reproducer, affected outputs,
regression test, fixed-path replay, in one table.

**RESOLVED 2026-09-22 — the source document is now in hand and this table survives it.**
It was first derived as option (b) because the round-1 document appeared to be in no
repository. That premise was wrong and the error was mine: it is in **nfl2**
`handoffs/`, and I searched only `nfl-predictions`. Production pushed a byte-identical
mirror at `reports/lab-handoffs/2026-09-21-laptop-postmortem-review-round1.md`, sha256
`4f409801…a4404`, which I verified equal across both nfl2 branches and the mirror.

Reading the source changes the table not at all, for a reason worth stating: **round 1
does not enumerate bugs.** It lists eight requested corrections, and item 2 asks for the
five fields "for each confirmed bug" without naming them. So the bug set was always
something to be assembled from the repository, which is what this is. See §diff. Every commit below was verified with `git log`, not
copied from prose; every test file was confirmed present and collected.

## Summary

| # | bug | introduced | fixed | regression test | replayed on the affected path | status |
|---|---|---|---|---|---|---|
| 1 | Composite ordering scored Week 2 against Week 1 | `player_score.py` `--week` default `1` + caller omission | `3a942f49` | `test_player_score_week_resolution.py` (22) | **no** — cost unmeasured | FIXED |
| 2 | DK-PPG stand-in served Jefferson 25.3 | pre-`82739685` market fallback | `82739685` | `test_market_source.py` (6), `test_live_smoke.py` (7) | **no** — Week 2 not re-run | FIXED |
| 3 | `market_source_log` recorded output without inputs | original table design | `63b1e3ae` + `1282d62d` | `test_market_source_log_records_blend_inputs.py` (4) | n/a — table not yet created | FIXED, guard incomplete (#9) |
| 4 | `test_bq_load.py` silently disabled by its own guard | `10430879` | `204da306` | `test_bq_load.py` (3) | yes — mutation-checked | FIXED |
| 5 | `test_persistence_contract.py` drifted off removed env fallbacks | `f29c6da4` (2026-08-29) | `204da306` | `test_persistence_contract.py` (19) | yes | FIXED |
| 6 | Launcher-receipt helper raced the registry's atomic write | `pathlib.glob("*")` matching dotfiles | `42b12458` | `test_launcher_registry.py` (13) | yes | FIXED |
| 7 | Doubtful players retained at DK-status eligibility | nfl2, long-standing | nfl2 `69f98a7` | `test_dk_status_invariant_excludes_doubtful.py`, `test_live_roster_status.py` | **no** — Week 2 not re-run | FIXED, verified `a4378fdd` |
| 8 | `live_candidates` / `own_shadow` lose the lever record silently | `cand_log_async=True`, `cand_log_required=False` | **instrument only** | none in the money path | no | **OPEN — repeats Week 3** |
| 9 | AST guard accepts a derived expression as the model side | `1282d62d` (guard as written) | — | — | no | **OPEN — two-line fix** |
| 10 | CI "tracked read failed" ×22 | depth-1 clone in `ci.yml` | `48a12c1d` | reproduced locally (exit 128 vs 0) | yes | FIXED |

## The column that matters most: fixed-path replay

**Five of the ten fixes have never been replayed against the artifact they broke**
(#1, #2, #3, #7, and necessarily #8/#9). That is the honest headline of this table,
and it is the same shape as the Jefferson problem in item 1: the fix is proven by
construction and by unit test, not by re-running the week it damaged.

For #1 and #2 that gap is quantitative — the Week-2 book was ordered on week-old
projections and Jefferson was served by a stand-in, and **neither cost is measured**.
HANDOFF is explicit that the composite ordering still beat the book's own order by
+44.0 on the promoted row, so the staleness cost is *unmeasured, not zero*. Both would
be closed by the same re-run at the serving commit that item 1 needs. That is an
argument for doing that re-run once, after Sunday, and having it close three items.

For #7 the replay is available and cheap and I have done the equivalent: the Week-1/2
outcome join in `reports/2026-09-22-laptop-doubtful-verification.md` is a replay of the
rule against the weeks it would have changed — 13 Doubtful player-weeks, all zero.

## Per-bug detail where the summary is not enough

**#1 Composite ordering.** Two halves, each harmless alone: a `--week` default of `1`
and a caller omitting the flag. The projection join is by player, not by week, so the
lookup succeeded and the receipt's coverage block read healthy. The fix moved the
authority rather than supplying the flag — season/week resolve from the run's own
`receipt.json`, flags may only confirm, contradiction is refused, and the receipt
records `week_source`. The generalisable rule is in HANDOFF and is worth repeating:
*an argument that selects which data a run operates on must be required or derived,
never both optional and defaulted.*

**#3 and #9 together.** #3 is fixed: `model_points_pre` and `model_weight` are recorded
and `run_projections.py:412` passes `_pre_blend`. #9 is the residue — the AST guard
pins that the kwarg is *present*, not *what it is*, so passing the blended output as
the model side leaves all four tests green. Detail and fix in
`reports/2026-09-22-laptop-items-1-and-2-status.md` §A.

**#8 is the one that will recur this Sunday.** `candidate_persist_status()` and
`flush_candidate_persistence()` exist and correctly separate `ok`/`failed`/`timeout`
from `started`; nothing calls them. `live_candidates` still holds zero 2026 rows and
its 2024 rows are still synthetic offline output written 2026-09-21. Unless a caller
lands, Week 3's levers go unrecorded exactly as Week 2's did.

## Two notes on accuracy

- HANDOFF records `test_player_score_week_resolution.py` as **14 tests**; it collects
  **22**. The count grew after the entry was written — not a defect, but it is why a
  test count in prose should not be cited without collecting it.
- #5's introducing commit `f29c6da4` is dated **2026-08-29**, three weeks before the
  failure surfaced. The defect was latent until `10430879` and the lane change made it
  visible, which is worth noting because "introduced commit" and "commit that made it
  fail" are not the same column and this table uses the former.

## §diff — round 1's eight items against what was answered

> **CORRECTED 2026-09-22 — the conclusion below about item 1's second clause is WRONG.**
> It IS answered, by `reports/2026-09-21-season-window-audit-week2.md` (commit `737104bb`,
> branch `production/in-season-rules-20260919`, sha256 `7c348722…c5b77`), now mirrored to
> this branch. I had grepped only the integration branch's `reports/`. See
> `reports/2026-09-22-laptop-correction-item1-second-clause.md`. The rest of this
> document — the ten-bug table and the replay-column finding — is unaffected.

Now that the source is readable, the promised diff. Seven of eight items are answered by
committed reports. **One clause is not answered anywhere**, and it is not a small one.

| item | subject | status |
|---|---|---|
| 1 | Jefferson pre-blend trace | answered (open on the re-run) |
| ~~1 (second clause)~~ | season-partitioned windows, training vs serving contracts, cold-start | **ANSWERED** — `737104bb`; my claim was wrong, see the correction report |
| 2 | per-bug table + telemetry vs money-path input | this document + item-2 report |
| 3 | caps compared on the same objective/pool/K/assignment | answered |
| 4 | stack counts and overlap definition | answered (87/8/2 reproduced) |
| 5 | injured concentration, feed gaps vs observation times | answered |
| 6 | all entrants stratified, not winners only | answered |
| 7 | standings validator, ties/duplicates/rejected rows | answered |
| 8 | Tuesday handover: image identities, pending vs done, risks | answered by the handover chain |

### ~~The unanswered clause~~ — superseded, retained for the record

Item 1 is two questions, and only the first was ever engaged:

> Season-partitioned windows alone do not prove a new defect or justify classifying
> cross-season training-feature changes as a repair; compare the training and serving
> contracts and historical cold-start behavior.

The item-1 report is entirely about the Jefferson trace. Grepping every committed report
under `reports/` for `season-partitioned window`, `cross-season training-feature` and
`historical cold-start` returns **nothing**; the only near-hits inside the item-1 report
are two incidental uses of the word "repair" about the market-source commit.

**Why it matters more than a missed sub-bullet.** It challenges a *classification*, not a
number: whether a cross-season training-feature change was properly called a repair at
all. If it was not, then something recorded as a fix is actually a behavioural change to
the training contract, and the distinction decides whether a downstream verdict
transfers — which is exactly what this project's post-ensemble and post-selection law
exists to protect. It is also the one item-1 question that does **not** need the re-run
at the serving commit, so it is unblocked today.

I am not answering it inside this table; it needs its own comparison of the training and
serving contracts. Flagging it as the diff's actual finding.

## Verifications run against production's 2026-09-22 reply

Claims checked rather than accepted, all confirmed exactly:

| claim | result |
|---|---|
| round-1 mirror is byte-identical to nfl2 | sha256 `4f409801…a4404` equal across both nfl2 branches and the mirror |
| `build-features` wrote Week-3 rows | `player_week_inference` season 2026 week 3 = **928** |
| `tabpfn-gen` recovered from 51 rows | `tabpfn_projections` 2026 week 3 = **928**, matching inference one-for-one |
| week resolver returns 3 | exact `project-slate` query returns **3** today |

One observation production did not state: `tabpfn_projections` holds **only** week 3 for
2026 — weeks 1 and 2 are still absent, the known truncate-and-rewrite damage from the
bad early run. Already logged; noted here so the 928 is not read as a full-season cache.
