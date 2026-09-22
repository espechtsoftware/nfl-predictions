# `--max-per-game` readiness for Week 3: the cap works, but the Sunday command refuses it as written

Assignment from `543ca417`. nfl2 read at the live pin **`69f98a7`** (clone `week3-live-center`); my
worktree `.nfl2-worktrees/laptop-max-per-game-20260922` (branch
`laptop/max-per-game-readiness-20260922`, no changes). The pinned live clone was not touched. Scripts:
`reports/lab-handoffs/2026-09-22-max-per-game-{smoke,lev-timing}.py` (outcome-blind, archived
Week-2 frame).

## 1. Semantics (from the code)

- **`live_week.py --max-per-game N`** sets `MAX_PER_GAME=N` in the env dict passed to
  `generate_candidates`, which passes it to **both** `optimize_many` (lev) and `optimize` (boom).
  **The help text, "in every boom solve", is wrong: it caps `lev` too.**
- The constraint (`core/lineup.py:226–238`) caps **every player with that `game_id`**, so it
  **counts the QB and the DST** (DST rows carry `game_id`, verified on the Week-2 frame).
- **Interaction with the production stack** (QB + ≥ 2 same-team WR/TE + ≥ 1 opponent skill player):
  the QB's game already holds at least 4, so **cap 4 leaves zero slack**. The QB's game holds exactly
  QB + 2 catchers + 1 bring-back, with no DST, RB or third catcher from that game. Other games are
  capped at 4.
- **Cap 3 is infeasible for every solve under the production stack.**
- **No back door:** the setting is read only from the passed env dict, and the live path always
  passes one, so exporting `MAX_PER_GAME` in the shell does nothing. Correct design.

## 2. Mechanics smoke (archived Week-2 frame, 20 lev + 150 boom, outcome-blind)

| cap | lev | boom | boom s/solve | max-per-game distribution in the pool | ledger |
|---|---:|---:|---:|---|---|
| none | 20/20 | 150/150 | 0.057 | 4: 116, 5: 51, 6: 3 | all new |
| 5 | 20/20 | 150/150 | 0.060 | 4: 116, 5: 54 | all new |
| **4** | 20/20 | 150/150 | 0.063 | **4: 170** (no violation) | all new |
| 3 | **0/20** | **0/150** | **1.557** | — | lev exhausted, boom **infeasible** |

- Without a cap, **68%** of candidates already sit at exactly 4 from one game, so cap 4 reshapes
  only the roughly one-third that load 5–6 into one game.
- `select_expected_max` composes with the capped pool (K10 distinct, tags mixed), and the receipt
  records `arm.max_per_game` (`live_week.py:197`, written at `:343`).
- **Production's {3, 4, 5} sweep:** cap 3 cannot be the live flag under the production stack.
  Infeasible boom solves are slow (1.56 s each: ~4.4 hours at 10,240), and the exact-K contract would
  then fail the build. If your replica produced cap-3 pools, its stack rules differ from live.

## 3. Build time

| lev solves | uncapped | cap 4 |
|---:|---:|---:|
| 80 | 23.4 s | 21.2 s |
| 160 | 61.1 s | 62.6 s |

Boom: +~10% per solve (0.057 → 0.063 s), which is ~1 minute at 10,240. **No material build-time cost
at D12800.** Lev scaling is unchanged by the cap.

## 4. The blocker: the Sunday command cannot carry the flag

`scripts/sunday_build_host.sh:114–116` runs `live_week.py … --selector dual_emax … --emit-a5-sidecars`,
and `live_week.py:55` exits on **any** shadow flag with the sidecars:
`"--emit-a5-sidecars is the paid path; shadow-arm flags are not allowed with it"`. Adding
`--max-per-game 4` to that command fails the build at start-up. Options, all production's and the
operator's call:

1. **Drop `--emit-a5-sidecars` for Week 3**, if nothing downstream still needs the A5 capture contract
   (the D800_WEMAX same-pool book and retained banks). Production knows the consumers; I don't.
2. **A one-line nfl2 change** letting `max_per_game` through with the sidecars. That is a new commit
   and therefore a new `EXPECT_SHA` for the live clone.
3. **Leave it off.**

Whichever is chosen, rehearse it once on the real Week-3 inputs before Saturday. `live_week.py`
asserts `now < lock`, so it cannot be rehearsed on Week-2 inputs; that is why this smoke called
`generate_candidates` directly.
