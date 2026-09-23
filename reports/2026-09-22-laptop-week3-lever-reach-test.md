# Week-3 lever-consumption test (§5.1): all eight levers reach the book; the adopted policy describes a different engine

Delegated by production (`e67103d7`, external review §5.1). Test: **`tests/test_week3_levers_reach_the_book.py`** on
branch **`laptop/week3-lever-reach-20260922` @ `b2edcdbb`**, based on the deployed shipping tip `85824fd0` (image
`eadae06a`).

## What the test proves, link by link (9 tests; 8 offline + 1 opt-in against gcloud, all passing)

| lever | A. env changes behaviour | B. on the `project()` write path | C. pinned chain | D. deployed |
|---|---|---|---|---|
| QB_BACKUP_GATE / QB_DOUBTFUL_ABSENT / QB_NO_DEPTH1_PROMOTE | each toggle changes the gated set | `find_backup_qbs` → `zero_out_projections(out_ids + backup_ids)` | nfl2 centres draws on production `proj_points` | not switched off |
| Q_HAIRCUT | ×0.80 scales `proj_points` | `apply_questionable_haircut` before the write | same | `0.80` |
| CASCADE_DOUBTFUL | adds non-QB Doubtful sources | cascade wired into `run()` | same | `1` |
| CASCADE_SKIP_PRICED_CARRIES | report-Out set; skip inside the loop | same | same | `1` |
| Doubtful in `DK_INACTIVE_STATUSES` | — | — | `"D"` at the pin; the denylist runs **before** `generate_candidates` | — |
| MAX_PER_GAME | — | — | week_env default 4 → both host builds carry `MPG_ARGS` → `check_cap` fails closed → `_arm_env` → lev and boom `env=env` → `<= max_pg` constraint; paid path uses `check_paid_path_flags` | — |

nfl2 and the host scripts are read by `git show` at pinned revisions (the nfl2 pin parsed from `week_env.sh` on the
integration branch), never a working tree. **Mutation check:** pointing the pin at `2dc116c` (Week 2) fails the
Doubtful test; pointing it at `69f98a7` (before option 2) fails the cap test; each fails nothing else.
`NFL_DFS_CHECK_DEPLOYED=1` runs layer D (image digest and env) against the live job; it passed at the time of
writing.

## Finding 1 — the integration branch does not contain the deployed code

The deployed levers exist only on the shipping branch `production/week3-qbgate-on-cf630a68-20260922`: on
`production/week3-integration-20260921`, `cascade_adjust.py` carries 2 of the lever references against 11 on the
shipping tip, and `85824fd0` is not an ancestor of the integration tip. **A rebuild or deploy from the
integration branch would silently drop Q_HAIRCUT, both cascade flags and both QB-gate refinements**, and the
host chain (week_env, sunday_build_host) lives only on the integration branch. The test therefore sits on the
shipping branch and reads the host scripts across. Recommend merging the shipping branch into the integration
branch before the next deploy.

## Finding 2 — levers validated or adopted but NOT consumed by the money path

From `tests/adopted_lever_consumers.json` (75 levers, traced 2026-09-22) plus today's work. `ADOPTED_CLASSIC_POLICY`
declares these non-zero or active, and the nfl2 money path never reads them:

| lever | declared | why it doesn't reach the book |
|---|---|---|
| **OWN_MODEL** (chalk fade) | `''` = naive fade | `live_week.py:191` omits `own_est`; degraded branch every run (known) |
| **P_MIX** | adopted selector participation law | no participation logic in live_week / live / pipeline / selectors / lineup (production confirmed, known) |
| N_QB_VARIANTS | 4 | nfl2 builds only lev + boom |
| N_EPISTEMIC / EPISTEMIC_FAMILY | 12 / role_draws | no epistemic family in nfl2 |
| REPLACEMENT_SLOTS | 12 | no replacement-slot construction in nfl2 |
| N_GAMESTACK / N_DARKGAME | 4 / 10 | no such families in nfl2 |
| ROLE_BELIEF_FEATURES | six share features | no role-belief construction in nfl2 |
| MULTISEED_PORTFOLIO (+3 companions) | CBWU | no multiseed portfolio path in nfl2 |
| N_LEV / N_BOOM / CAND_MULT / GEN_TOTAL_BUDGET | 40 / 160 / 2 / 172 | the dose comes from the `live_week.py` CLI (2,560 / 10,240 for Week 3) |
| SELECT_OBJ | `''` | nfl2 selects with its own `--selector dual_emax` |
| **MAX_PER_GAME** | **0** | **live Week 3 runs 4 via the CLI flag: the adopted policy now disagrees with the live stack** |

Also: 6 levers are **shadowed** (nfl2 hard-codes the same literal independently: GAME_SIM_MODE, TABPFN_MARGINALS,
SIM_WIDEN_DRAWS, SERVED_POSITION_SCALES, MAX_OVERLAP, MIN_GAMES; equal today, unguarded), and 6 declared `''` whose
production-side meaning still needs production's confirmation (DST_CORR_DRAWS, EMP_POS, GEN_POOL_CAP_MAP,
PUNT_BOOM_WR, ROOKIE_WIDEN, TABPFN_MARGINAL_TABLE).

**Structural reading:** `production_policy.py` describes the production research chain's generator (qb-variants,
epistemic, replacement, gamestack, darkgame, multiseed) and its selector. The Sunday money path is nfl2's lev +
boom generator with `dual_emax`. The two share a name, "the adopted stack", but not an engine. Every
future adoption should name which engine it changes, and the Week-3 `MAX_PER_GAME=4` flip should be recorded
against the policy (per CLAUDE.md, a change there needs its validation trail).
