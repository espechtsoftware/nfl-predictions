# Code review of the Week-5 Sunday path, before the 17:55 arm (2026-10-10, late afternoon)

**For:** Erich, and the laptop who arms tonight. Written by the outside model after your request: "review all the code for the
live that's going live this weekend and let me know any concerns." Three independent read-only reviews of the production
checkout at integration head `23a108d3` (clean; identical to origin): the union builder and its rules, the host chain from the
arm to the upload, and the offline tests plus the defects register. Nothing was edited or run except reads and the tests, which
ran in a separate worktree. The laptop was sent the actionable items at 16:30 CT.

## In one page

| Severity | Concern | What to do |
|---|---|---|
| **BLOCKER for tonight's 18:00 supply units** | The Saturday supply builds (18:00 D12800, 18:05 D6400) check that the newest projection batch is under 120 minutes old (`run_week_build.sh` passes no `--max-age-minutes`; `build_inputs.assess_projections` fails above 120). The newest project-slate finished at 15:52 CT, so at 18:00 the batch is about 128 minutes old and both units die in the preflight: no Saturday supply, no canary. Sunday would then rest on the 05:00 build alone; if its 04:45 project-slate fails, both Sunday unions fail and there is no book | Run project-slate once more so it finishes between about 16:10 and 17:50 CT (it takes about 3 minutes). Nothing in the arm checks projection age; this is a manual step. Week 4 passed only because the 09:47 refresh preceded the 10:30 supply |
| **HIGH** | The Saturday lag file is on the money path at tilt 0 (the ownership cap's export uses it as its only scale reference), but the arm only WARNs if the lag step fails; nothing else gates it. A BigQuery hiccup at 17:55 completes the arm with a warning, and on Sunday the ownership cap is not applied and the row rules, one-catcher rule and RB rule cascade off: today's book is published with the package off, loud only in the build log and alert files | After the arm: `~/week5-sunday/ownership_lag.csv` must exist and pass `scripts/check_ownership_lag.py`; treat any "WARN … lag" line from the arm as a stop tonight. Week 6: make the lag step a stop when the ownership cap is armed |
| **HIGH** | The TODAY sheet surfaces only the projection source. A book built with the ownership cap, row rules, one-catcher or RB rule NOT applied, or on a pre-inactives salary pull, reads as an ordinary success on the sheet; the evidence sits in `ALERT-*` files and the union directory | Before upload Sunday: list `~/week5-sunday/ALERT-*` and the union directory's `*_not_applied.txt` / `mix_refused.txt`; confirm `union_args.txt` carries the package, the row rules, the one-catcher, the RB rule with scope favhi and 8 term rows; confirm TODAY's "Source run" is the 10:50 union, not the 09:10 one. Week 6: print those markers into TODAY |
| MEDIUM | The arm's "not too late" check (17:58) runs after its BigQuery input steps; the arm is not idempotent at the timer step (fixed unit names); any post-arm commit outside docs (the arm script and tests included) fails every Sunday unit's runtime check | Start the arm by 17:35. A redo means stopping all 13 Week-5 timers, committing, pulling and re-arming. After the final arm, pull only documentation commits into the production checkout until lock |
| MEDIUM | No Fantasy Points session check runs at arming (the predictor is "blend"); a failed Sunday ownership collect silently reuses the newest capture under 30 hours old, i.e. Saturday's pre-inactives ownership | Confirm the 16:40 manual ownership capture succeeded before the arm. Week 6: verify the session at arming whenever the ownership cap is armed |
| MEDIUM | Spare rows carry none of the week's rules, and a Sunday replacement from a spare is re-checked only for legality, cell shape and salary floor, not for one TE, one low-owned player, one catcher per team, the caps or the ownership cap (extends O-54c/d) | Hand-check each replacement row on Sunday; prefer a same-cell spare that satisfies the rules. Register as a new O-54 letter |
| MEDIUM | The audit records the rules by row identity but does not verify the ownership cap or the row rules on the written rows; a row-rule fallback is receipt-only | At the canary and on Sunday read the receipt: exposure cap share 0.35, ownership cap applied, row rules applied with an empty `resolved_without`, one-catcher applied, RB mate applied with scope favhi, the term block's sha and 8 rows; no alert files |
| MEDIUM | The designed fail-closed stop at T-70 (a refused mix or term block) withholds the book that carries the inactives and needs a human decision between about 11:00 and 11:15 | Be reachable in that window |
| LOW | Fantasy Points' ownership is matched to our players by name; a mismatch silently caps a player at 3 rows and counts him as low-owned, and the 0.9 coverage gates tolerate 10% unmatched | Checked on today's 12:55 capture: 3 of 565 skill players fail an exact-name match, all $3,000–4,000 bench players. Read the "unmatched" line of Sunday's own-cap file |
| LOW | The 09:10 floor book uses Saturday-evening Fantasy Points numbers by design; a T-70 failure before a run directory exists leaves the 09:10 book as TODAY with no stop marker | At about 11:05: the T-70 unit's status, its build log, and TODAY's "Source run" |

**Checked and correct.** All 41 offline test modules that read the money-path scripts pass (rc 0 each). The arm's stops are
coherent and currently satisfiable; the plan (Rev7) needs 26 rows with no gaps; the pair rule allows only (0.35, 15) or
(0.5, 0); the Sunday units' times and gates are as designed (10:33 and 10:47 pulls, 10:36 project-slate, 10:40 and 10:46
captures, 10:50 build with a 10:30 projection floor; a slow 09:10 union can never displace the T-70 union). The Fantasy
Points projection override gates (coverage 95%, salary equality, correlation 0.7, Sunday 06:00 update floor on the T-70
build) fall back loudly to our projections. The ownership cap reads Fantasy Points' raw ownership, rescales to 800, caps at
floor(26 × (own/100 + 0.15)), refuses below 90% coverage and falls back to the 0.5 book with four alerts. The FAVHI scope
takes the top third of game totals and a margin of 3 or more, and a missing input switches the RB rule off loudly, never wider.
The term block's sha is checked at the arm and in the receipt. Every refusal in the code added since 10-08 is a caught exit
that becomes a loud fallback; no new "0"/"" environment hazards. The study-38 snapshot and the four paper files are isolated
from the money path. The DraftKings ingest loop fix is live (no restarts since 05:54). The defects register has nothing with a
Sunday deadline unfixed in the armed code; O-60 (late-scratch bump) is open by your Week-6 decision and O-16 (`--dk-status`
never set) is still open with the frame's own OUT/IR exclusion as the live guard.

## Sources

The three review reports (this session, 16:08–16:30 CT) on `/home/erich/projects/nfl-predictions` at `23a108d3`: scripts
`arm_week5_saturday.sh`, `arm_week_timers.sh`, `week_env.sh`, `run_week_build.sh`, `check_build_inputs.py`,
`sunday_build_host.sh`, `union_fallbacks.sh`, `sunday_after_build.sh`, `run_dir_publishable.py`, `check_week_runtime.py`,
`check_t70_statuses.py`, `fp_projection_override.py`, `ownership_fp.py`, `vet_book.py`, `vet_replace_v4.py`,
`host_ingest_dk_loop.sh`, `s38_snapshot.sh`, `union_reselect.py`; `src/nfl_dfs/inference/{build_inputs,market_monitor,
enter_layout,mix_shapes}.py`; `src/nfl_dfs/ops/fantasy_points_ownership.py`; `reports/OPEN-DEFECTS.md`; the project-slate
execution list (`gcloud run jobs executions list`).
