# Laptop → production: the per-bug consolidation, derived from the repository

Item 2's broader ask — per bug: introduced commit, reproducer, affected outputs,
regression test, fixed-path replay, in one table.

**This is option (b), and it is provisional.** The source list
`handoffs/2026-09-21-laptop-postmortem-review-round1.md` is not in the repository on
any branch, so this set is derived from `HANDOFF.md` and the committed item 1–7
reports. **Anything raised only in chat is missing from it, and I cannot know what.**
Correct it rather than adopt it. Every commit below was verified with `git log`, not
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

## What is missing from this, by construction

Bugs raised only in the round1 document or in chat. If you push
`handoffs/2026-09-21-laptop-postmortem-review-round1.md` I will diff its eight
requested corrections against this set and report what I missed — that diff is worth
more than either list alone.
