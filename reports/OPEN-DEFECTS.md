# Open defects and deliberate non-fixes

**This file is the authoritative list of what is known-broken and NOT being fixed right now, and why.**
Last reviewed 2026-09-18. Every entry states the impact, the deadline by which it must be resolved, and what
"resolved" means. An item leaves this file only by being fixed and tested, or by an explicit recorded decision to
accept it — never by being forgotten.

Nothing in this file is on the Sunday money path unless its Impact column says so. That distinction is the point of
the file: research and vendor plumbing failures cost information over months, and are not the same as a defect that
can cost an entry.

## Live now

| # | Defect | Impact | Deadline | Resolved means |
|---|---|---|---|---|
| O-1 | **CORRECTED 2026-09-18 — my original entry here was wrong.** I reported that the Fantasy Points Week-1 capture "failed every attempt" and that the feed was broken. **It is not.** All three report families were CAPTURED in every run; I had counted per-report `status == "ok"` when the actual value is `"captured"`, and read the run-level `status: failed` as total failure. What is really true: the run fails if ANY report's schedule gate fails, and in the final run `wr-coverage-matchup` (44 pairs) and `line-matchups` (exactly the 32 expected pairs) both PASSED, while `qb-coverage-matchup` failed missing one directional pair, `['ARI','LAC']`. ARI at LAC was a real 2026 Week-1 game, so that is a genuine but single-game vendor gap. Separately, all three carry `source_seasons=[2025]`, `source_regime=vendor-prior-season-early` — prior-season metrics applied to current matchups, which is the vendor's early-season behaviour, not a defect. **Remaining real defect: the run-level status cannot distinguish partial success from total failure**, which is what misled me. | Reporting/observability only. The capture itself works. Two of three families sealed clean for Week 1. | Before Week 3 | Manifest and any summary surface per-family status, so "2 of 3 families sealed, QB short one pair" is legible without opening the JSON. |
| O-2 | **The Route Share shadow jobs carry `N_BOOM=28`** while the adopted money path is boom-first `N_BOOM=160` / `N_LEV=40`. `shadow-k1-roleunion` and `shadow-k1-route-roleunion`, both PAUSED. | Resuming as-is would burn a graded week comparing a policy we do not run. An invalid week that looks complete is worse than a missing one. Week 2 is deliberately forfeited (see O-6). | **Week 3** | Both jobs updated by `gcloud run jobs deploy` (update, never create — the project is AT the 1000-job quota), before/after env recorded in the gate document, one outcome-blind dry run, then schedulers ENABLED. `scripts/check_prospective_gates.py` must pass. |
| O-3 | **SIS pass-tail: no frozen gate document, no 2026 data, schedulers PAUSED.** Every SIS raw table has zero 2026 rows; last download 2026-08-15. Week-5 eligibility is implementation-derived (the module builds a last-four-weeks context), not written down anywhere. | A paired job with a schedule but no written gate cannot be graded. | **Week 5** | Either the gate is written and its policy contract declared, or the three schedulers move to `DORMANT` in the checker with a written reason. The checker warns from Week 3 and fails at Week 5. |
| O-3a | **The "no Week-1 SIS pull" decision looks like a budget rule applied where it does not govern.** The operator asked why a week was deliberately left out. The pass-tail shadow is **team-grain**: it keys on `["season","team"]` over `pdef_*` and `prush_*` columns. The usage review says team-game grain is **32 rows per week and safe** — one query covers all 32 teams. The 1,000-query weekly allowance binds only for **player-level** pass defense at game grain, where a 200-row cap forces a split by team and a six-season backfill runs to tens of thousands of queries. **So a weekly team-grain pull costs on the order of one query per week against a 1,000/week allowance.** Skipping Week 1 saved roughly that, and gave up a pre-lock snapshot and protection against later vendor revision. | The week-1 numbers are still obtainable retrospectively, so no data is permanently lost — but there is no point-in-time snapshot, and a prospective gate is exactly the thing that needs one. | **Week 5**, with O-3 | A recorded decision either to pull team-grain SIS weekly from now on (including a Week 1-4 backfill) with the query cost stated, or to keep the retrospective plan with the revision risk accepted in writing. |
| O-3b | **No guard against the vendor revising already-published weeks.** The shadow filters to weeks strictly before the target, which its docstring calls point-in-time safe on rerun. That holds only if earlier weeks never change. Stat corrections are ordinary in football data and nothing in the module checks for them. | A retrospective pull is not equivalent to a pre-lock capture if the source moved. Undermines the one property a prospective gate exists to have. | **Week 5**, with O-3 | Either weekly snapshots with retained hashes, or a recorded check that re-pulled earlier weeks match what was first seen. |
| O-3c | **Week 5 is a preference, not a limit, and is written down nowhere.** The code needs a minimum of two prior weeks (`rolling(4, min_periods=2)`), so the earliest computable target is **Week 3**. Week 5 is simply the first week the four-week window is full. | The start week was reported as a technical constraint when it is a design choice. | **Week 5**, with O-3 | The gate document states the true earliest week, the chosen start week, and why. |
| O-3d | ~~EXPIRED session~~ **RENEWED 2026-09-18 by the operator and verified.** The monitoring half is STILL OPEN: nothing surfaces expiry in advance. Original entry: **the saved SIS session was EXPIRED and nothing watched it.** Verified 2026-09-18: `verify_login` fails with "saved session is missing, expired, or cannot load Player Leaderboards". The Playwright profile was last touched 2026-08-13. Renewal is interactive (`sis-download login`) and cannot be automated. | **If this had gone unnoticed, the Week-5 pull would simply have failed** — the one pull the whole SIS plan depends on, on a deadline, with no earlier attempt to fall back on. It was found only because the operator asked for a Week-1 backfill. | **Before Week 5** | Session renewed and verified, AND a check that surfaces expiry in advance rather than at use. |
| O-3e | **The Week-5 restriction is enforced in code, not policy.** `weekly_vendor_data` gates the SIS step behind `if week >= 5`, and `run_pass_tail_weekly_acquisition` raises for any target week outside 5..18. So "the approved workflow intentionally made zero SIS queries for Week 1" is that hardcoded condition, not a written decision. | The start week cannot be changed without a code change, and the reason for it is recorded nowhere. | **Week 5**, with O-3c | The chosen start week is stated in the gate document and the code cites it. |
| O-11 | **The book and the upload files key on DIFFERENT player identifiers, and nothing declares either.** Verified 2026-09-18 on the Week-2 population: every one of the 142 distinct ids in `book.csv` matches `frame.dk_player_id` and **none** matches `dk_draftable_id`; every id in the published `ENTER-*.csv` files matches `dk_draftable_id` and **none** matches `dk_player_id`. Both are correct for their purpose -- DraftKings uploads require draftable ids -- but the mismatch is undeclared, there is no header or receipt field naming the id space, and the conversion happens silently in the emit step. | **Silent-empty-join.** Joining `book.csv` on the draftable id matches zero of ninety lineups and returns an empty result rather than an error, which reads as "no data" instead of "wrong key". It cost real debugging time today and would cost it again. Analytical, not an upload risk: the filler validates exact counts and 9/9 cells against the real DraftKings export and was rehearsed end to end. | **Week 3**, with O-2 | `receipt.json` declares `id_spaces` for every artifact it writes, and the production side documents the ENTER id space. Fix is already written into the pending patch (v4). |
| O-12 | **No 2026 in-season usage history reaches the model. Root cause: a contract mismatch between the DraftKings ingest and the feature build.** `dk_job.season_week_for` returns `week = None` **deliberately** (its comment: "week resolution happens downstream by joining game_start against nfl_raw.schedules"), so all 722,516 raw 2026 salary rows carry a NULL week — measured, 0 non-null. But `sql/features/001a_dk_salary_week.sql:37` filters `WHERE ... s.week IS NOT NULL`, so **0 rows qualify** and `nfl_features.dk_salary_week` has **zero 2026 rows** (it stops at 2025 week 18). Nothing joins `game_start` to `schedules` in between. The historical `usage` branch in `014_player_week_usage.sql` starts FROM `dk_salary_week`, so week-1 history never enters the rolling windows. | **Every usage feature is null for all 928 Week-2 players and `games_played_prior = 0`.** Verified on the live table, not a stale snapshot: a build completed 2026-09-17T10:18:40Z, four days after Week 1, and produced these zeros, so **the Saturday refresh does not repair it.** Inputs are all present (`weekly_stats` 1,118 wk-1 rows, `snap_counts` 1,492, `player_week_actuals` 1,117, `player_week_role` 921). This is the same condition behind the Week-1 projection-level defect and predates Week 2. **Magnitude of harm to entered projections is NOT established** — production centres on market-blended `proj_points`. | **Week 3** | `001a` resolves the week by joining `game_start` to `nfl_raw.schedules`, or the ingest sets it; `dk_salary_week` holds 2026 rows; usage windows populate; and `build-features` leakage checks pass on a full build. Deliberately NOT shipped before the Week-2 build: it changes every usage feature, hence model inputs, hence the book, twelve hours before a live entry with no time to validate point-in-time correctness. |
| O-4 | **Review finding 8: prop dedup keeps moved lines**, and the "props" log count includes fallback rows, so the props-source log line proves the source but not the coverage. Upstream of defect 27. | Data quality in the prop-market blend. Not a break; the blend still runs. | After Week 2 | A failing pytest on a synthetic snapshot with a moved line (requested from the reviewing agent), then a fix against it. |
| O-5 | **Review finding 7: week/DST generalisation gaps** — a TabPFN week literal, 2026-specific anchors, UTC bounds across the DST change, stale exports across repeated `week_env` calls. | None for Week 2 (inside the valid range). Will bite after the November DST change. | **Before the first Sunday after DST ends** | Each anchor parameterised and a test crossing the DST boundary. |
| O-6 | **Week 2 of the Route Share gate is forfeited.** Its four schedulers were PAUSED and were not noticed until two days before lock; fixing them meant a production job update ~40 h before a live entry. | One of five spare weeks. The gate needs 12 complete paired weeks of Weeks 2-18; 16 remain. Zero effect on 2026 results — the gate adjudicates only after Week 18. | Accepted, no deadline | Recorded decision; Week 3 becomes the first graded week. |
| O-7 | **The route-share file loaded on 2026-09-17 was not retained.** `nfl_raw.fantasy_points_route_share` cites `route-share__season-2026__weeks-01__target-week-02.csv` sha256 `07642ab6…`, and no file on this host matches that hash. | That load cannot be audited from source. Applies to future loads too. | Before the renewal decision | Loads retain their source artifact, or the raw file is archived to the bucket with its hash. |
| O-8 | **PREREG-101 is frozen but launch readiness is WITHDRAWN.** The winner's-curse objection is unresolved (§8 retracted — winner's curse imposes no monotonicity law on a threshold ratio). Also unresolved: clip-versus-normalisation contradiction (clip to [0.2,2.0] then normalise to mean 1 cannot satisfy the gate's range check), a mechanics gate demanding a new-bank book reproduce an old-bank roster, undefined FLAT10 and routing rules, an endogenous calibration receipt, underspecified weight fitting. | No spend, no run. Blocks a ~$230 experiment that would otherwise have been wasted. | Before any launch | Staged plan agreed with the reviewing agent: known-law synthetic E0, then a bounded independent-world pilot, then a costed rebuild only if warranted. Operator decides. |
| O-9 | **`scripts/check_prospective_gates.py` has not been independently reviewed.** Its `DORMANT` list classifies thirteen schedulers as deliberately dormant on my judgement alone. | If one of those thirteen is actually a live gate, it is now invisible — the exact failure the checker exists to prevent, moved one level up. | **Week 3** | The reviewing agent validates the registry, or each dormant entry is traced to a written decision. |
| O-10 | **Cloud Run us-central1 is AT the JobsPerProject=1000 quota** (counted exactly 1000 on 2026-09-18). | No new Cloud Run job can be created. Every fix must `deploy` an existing job. Freeing quota deletes execution history and is operator-only. | Standing constraint | Not a defect to fix; a constraint to respect. |

## Loaded 2026-09-18: SIS Week-1 is in BigQuery, where the rest of the seasons live

The operator's point, and he was right: the data ends up in the warehouse anyway, so storing a week as loose files
plus a bucket copy is storing it where it can be lost. `nfl_raw.sis_team_context_game` already held every prior
season — 2019 and 2021-2025, 17-18 weeks each — and **2026 was empty**.

**Week 1 2026 is now loaded: 32 team-game rows, 73 columns, six `source_sha256_*` lineage columns.** All six report
families captured (`pass-defense-totals`, `pass-defense-value`, `pass-rush-totals`, `pass-rush-value`,
`blocking-totals`, `blocking-value`), 32 rows each, six requests against a 1,000/week allowance.

- **Why a new loader.** `sis_team_context.read_tranche` is frozen to the historical acquisition: exactly 108 specs, a
  specific plan hash, a run-state file, and per-season row counts for 2019/2021-2025. Relaxing any of those to admit a
  weekly load would weaken a validator guarding the historical table. `scripts/sis_load_inseason_week.py` instead
  reuses the per-artifact PARSER (same position-based schemas, same lineage stamping) and does its own weekly
  assembly. **The frozen path is untouched.**
- **Safety checked before writing:** nothing in `sql/features/` reads this table, so the load is inert for the Sunday
  build. The loader refuses a (season, week) that already has rows, so it cannot double-load. It dry-runs by default.
- **The frozen Week-5 protocol is unaffected** — it reads its own downloaded files, not this table.
- The byte-exact CSVs and manifests remain at
  `gs://nfl-predictions-503414-raw/licensed/sis-revision-baseline/2026-w01-20260918T201025Z/` with SHA256SUMS. Keeping
  both is deliberate: BigQuery holds parsed rows, the bucket holds the original bytes, and the hashes tie them.
  That is what makes the Week-5 revision diff possible.
- **Now part of the weekly cadence:** capture and load each week once its games are complete, rather than waiting for
  a single retrospective pull. Week 2 after Sunday.

## Captured 2026-09-18: the SIS Week-1 revision baseline

At the operator's instruction, Week-1 team-grain SIS was captured **now** rather than left to the Week-5 retrospective
fetch. Three views (`pass-defense-totals`, `pass-defense-value`, `pass-rush-totals`), team entity, season 2026,
weeks 1-1, **32 rows each** — one per team, exactly the team-grain expectation. Three requests against a 1,000/week
allowance.

- Local: `sis/revision-baseline-2026-w01-20260918T201025Z/` (the `/sis/` tree is gitignored — licensed vendor data
  must not be committed).
- **Durable copy: `gs://nfl-predictions-503414-raw/licensed/sis-revision-baseline/2026-w01-20260918T201025Z/`**,
  8 objects, alongside the existing `licensed/draftkings/` and `licensed/fantasy-points/` archives. Local-only would
  not have survived to Week 5.
- `SHA256SUMS.txt` accompanies it. **At Week 5, diff the protocol's retrospective fetch of week 1 against these
  hashes.** A mismatch is proof the vendor revised published data, which is what O-3b warns is unguarded. A match
  retires O-3b with evidence instead of assumption.
- This snapshot carries **no protocol standing**. It is not `prospective-sis-pass-tail-weekly-acquisition-v1`, it
  lives outside the protocol tree, and the frozen Week-5 run must still happen exactly as specified. Writing the
  frozen artifact early would have burned its one-shot slot with weeks 2-4 missing.
- Noted while reading the files: the vendor's `Rank` column serialises as `[object Object]`. Harmless for the
  columns the shadow consumes, but it means the export captures a UI artifact rather than a clean value.

## How this file is kept honest

- `scripts/check_prospective_gates.py` enforces O-2, O-3 and O-9 mechanically and fails on any unclassified scheduler.
- CLAUDE.md carries the standing rule to run it weekly before the Saturday build.
- Anything added here must name a deadline and a definition of resolved. "Later" is not a deadline.
- Closing an entry requires a test or a recorded decision, and the entry is struck through rather than deleted so the
  history of what we chose to live with stays readable.

## Closed since this file was created

- **Review finding 6 (both halves), closed 2026-09-18 with tests.** The Sunday late-status watcher tracked a SET of
  flagged players, so a player already listed doubtful at startup could turn OUT with no alert and no break — the one
  transition the watcher exists for. It also read the entered books once at startup, so a scratch swap left it
  watching the old roster. It now tracks status per player, prints each transition, breaks only on an escalation into
  an out status, and re-reads the entered books every poll. Six tests, including two that reproduce the old behaviour
  and assert it was blind.
