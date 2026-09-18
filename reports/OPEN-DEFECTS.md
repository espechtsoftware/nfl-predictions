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
| O-1 | **Fantasy Points live-matchup capture has failed every attempt since 2026-09-09.** Nine Week-1 runs, all `status: failed`, zero reports OK. Errors: "schedule pairs do not match" and "filter label is missing: Schedule Week". Looks like vendor UI/filter drift. CSVs sit on disk under `fantasy-points/automated/*__week-01/`; nothing was imported (the gate fail-closed correctly). Nobody retried after that afternoon. | No live matchup data at all this season. Does NOT affect any entered lineup. Material to the paid-source renewal decision — we are paying for a feed whose automated capture has not succeeded once in 2026. | Before the renewal decision | One capture run reaching `status: ok` against the live vendor, or a recorded decision that the family is abandoned. |
| O-2 | **The Route Share shadow jobs carry `N_BOOM=28`** while the adopted money path is boom-first `N_BOOM=160` / `N_LEV=40`. `shadow-k1-roleunion` and `shadow-k1-route-roleunion`, both PAUSED. | Resuming as-is would burn a graded week comparing a policy we do not run. An invalid week that looks complete is worse than a missing one. Week 2 is deliberately forfeited (see O-6). | **Week 3** | Both jobs updated by `gcloud run jobs deploy` (update, never create — the project is AT the 1000-job quota), before/after env recorded in the gate document, one outcome-blind dry run, then schedulers ENABLED. `scripts/check_prospective_gates.py` must pass. |
| O-3 | **SIS pass-tail: no frozen gate document, no 2026 data, schedulers PAUSED.** Every SIS raw table has zero 2026 rows; last download 2026-08-15. Week-5 eligibility is implementation-derived (the module builds a last-four-weeks context), not written down anywhere. | A paired job with a schedule but no written gate cannot be graded. | **Week 5** | Either the gate is written and its policy contract declared, or the three schedulers move to `DORMANT` in the checker with a written reason. The checker warns from Week 3 and fails at Week 5. |
| O-4 | **Review finding 8: prop dedup keeps moved lines**, and the "props" log count includes fallback rows, so the props-source log line proves the source but not the coverage. Upstream of defect 27. | Data quality in the prop-market blend. Not a break; the blend still runs. | After Week 2 | A failing pytest on a synthetic snapshot with a moved line (requested from the reviewing agent), then a fix against it. |
| O-5 | **Review finding 7: week/DST generalisation gaps** — a TabPFN week literal, 2026-specific anchors, UTC bounds across the DST change, stale exports across repeated `week_env` calls. | None for Week 2 (inside the valid range). Will bite after the November DST change. | **Before the first Sunday after DST ends** | Each anchor parameterised and a test crossing the DST boundary. |
| O-6 | **Week 2 of the Route Share gate is forfeited.** Its four schedulers were PAUSED and were not noticed until two days before lock; fixing them meant a production job update ~40 h before a live entry. | One of five spare weeks. The gate needs 12 complete paired weeks of Weeks 2-18; 16 remain. Zero effect on 2026 results — the gate adjudicates only after Week 18. | Accepted, no deadline | Recorded decision; Week 3 becomes the first graded week. |
| O-7 | **The route-share file loaded on 2026-09-17 was not retained.** `nfl_raw.fantasy_points_route_share` cites `route-share__season-2026__weeks-01__target-week-02.csv` sha256 `07642ab6…`, and no file on this host matches that hash. | That load cannot be audited from source. Applies to future loads too. | Before the renewal decision | Loads retain their source artifact, or the raw file is archived to the bucket with its hash. |
| O-8 | **PREREG-101 is frozen but launch readiness is WITHDRAWN.** The winner's-curse objection is unresolved (§8 retracted — winner's curse imposes no monotonicity law on a threshold ratio). Also unresolved: clip-versus-normalisation contradiction (clip to [0.2,2.0] then normalise to mean 1 cannot satisfy the gate's range check), a mechanics gate demanding a new-bank book reproduce an old-bank roster, undefined FLAT10 and routing rules, an endogenous calibration receipt, underspecified weight fitting. | No spend, no run. Blocks a ~$230 experiment that would otherwise have been wasted. | Before any launch | Staged plan agreed with the reviewing agent: known-law synthetic E0, then a bounded independent-world pilot, then a costed rebuild only if warranted. Operator decides. |
| O-9 | **`scripts/check_prospective_gates.py` has not been independently reviewed.** Its `DORMANT` list classifies thirteen schedulers as deliberately dormant on my judgement alone. | If one of those thirteen is actually a live gate, it is now invisible — the exact failure the checker exists to prevent, moved one level up. | **Week 3** | The reviewing agent validates the registry, or each dormant entry is traced to a written decision. |
| O-10 | **Cloud Run us-central1 is AT the JobsPerProject=1000 quota** (counted exactly 1000 on 2026-09-18). | No new Cloud Run job can be created. Every fix must `deploy` an existing job. Freeing quota deletes execution history and is operator-only. | Standing constraint | Not a defect to fix; a constraint to respect. |

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
