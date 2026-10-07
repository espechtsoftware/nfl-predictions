# Week-5 money path: an independent code review (2026-10-07 evening)

The operator, 10-07: *"do you think you should do a review of the code to be used in production this week?"*

Outside reviewer. This is a read-only review of production integration at `0a974187`, in a clean detached worktree. It
covers the paths Sunday 10-11 actually runs under the armed Week-5 settings: MIX, FP projections, overlap 4, the QB
cap, no ownership term, **the cheap +2 block (the operator's trial)**, plan Rev6, and every new switch OFF. Four
reviewers each took one part: the build core, the Sunday host and upload path, Saturday's arming and preflight, and the
FP projection inputs. I checked every HIGH and MEDIUM myself in the code, and where noted in the data. Nothing in
production was modified. My own script, the cheap-block writer, is fixed on this branch (H3).

**In plain words:**
- Nothing found makes Sunday's lineups illegal.
- The cheap block applies as designed: +2 on sub-$4,000 skill players, 8 rows at ranks 2, 5, 9, 12, 15, 18, 22 and 25,
  with the caps held.
- Every switch that should be off is off, and the book is byte-identical with them off.
- Rev6 and the class model are installed with their pinned shas.
- **Three HIGH items before Saturday:**
  1. A failed 10:50 union silently publishes a book with none of the Week-5 settings.
  2. The "FP is after the inactives" gate checks our capture time, not FP's update time. This needs an operator
     decision.
  3. Thursday's cheap file would miss late-week cheap players. **Fixed in the writer:** write it with `--group 154468`.

## HIGH

**H1. A failed T-70 union publishes the plain T-70 book, and the operator-facing files don't say so.** Found by two
reviewers independently.
- **Where:**
  - `scripts/sunday_build_host.sh:271` marks the plain T-70 dir `audit_passed` before the union runs.
  - Every union failure exit (`:503`, `:507`, `:522`, `:523`, `:557`) writes `union_failed` on it.
  - `scripts/run_dir_publishable.py:66-72` treats `union_failed` as publishable in union mode.
  - The `term_block_missing` stop is written only on the union's own dir (`:527-552`).
- **What happens:** any union failure other than "MAIN REFUSED" (an exception, `PROJ SOURCE REFUSED`, a failed
  verify_k90 or audit) makes the watcher publish the live_week T-70 book. That book is top-26 by our projections, house
  shapes, overlap 7, with no QB cap, no FP and no block. It replaces the 09:10 union in ENTER/.
- **What the operator sees:** TODAY shows only "PROJECTION SOURCE: ours (... or the union did not run)". There is no
  capitals banner.
- **Why it matters:**
  - It contradicts the arm's own rule, "a book built WITHOUT [the block] is not published (his decision)"
    (`arm_week5_saturday.sh:52`).
  - The decision sheet names only two fallbacks.
  - Union failures have happened (the 10-01 smoke).
- **Verified:** the code lines above.
- **Fix:** under `UNION_MAIN=mix` or `UNION_TERM_BLOCK_ROWS≠0`, `union_failed` is a STOP (not publishable without an
  explicit override, like `term_block_missing`), with a TODAY banner.

**H2. The FP freshness gate checks our capture time, not FP's content time.** This needs the operator's decision.
- **Where:**
  - `scripts/fp_projection_override.py:91-94` selects only `retrieved_at`.
  - `:119-126` compares it with the 10:30 CT inactives.
  - FP's own `last_updated` is stored but never read.
- **Verified in the data:** the W4 Sunday capture at 10:38 CT holds the DK Main slate with `lastUpdated` 13:58:38Z,
  which is **08:58 CT**; all of that capture's slates carry the same stamp. The A1 rehearsal printed "AFTER the 10:30 CT
  inactives" for it.
- **Why it matters:**
  - His 10-06 rule is "stale FP → our post-inactives numbers".
  - As built, pre-inactives FP drives the T-70 book whenever FP hasn't refreshed before 10:46, and the sheet says AFTER.
- **Fix (small):** gate on `MAX(last_updated)` for the Main slate, and print both times.
- **Decision:** on W4's pattern the fixed gate would likely send the T-70 back to our numbers, unless FP updates after
  10:30.

**H3. The cheap file written Thursday from A3's frame misses late-week cheap players.** Found by two reviewers
independently. **FIXED in the writer.**
- **Where:**
  - The Thursday helper (`~/.cache/laptop-agent/rehearsal/w5_write_block_files.sh:10-18`) writes from A3's union frame.
  - `cheap_block_file.py` gives rows only to frame players.
  - `union_reselect.py:298-306` gives no term to a player missing from the file. The coverage gate (players at 5+,
    threshold 0.5) never trips.
- **Evidence (W4):**
  - Earlier frames lacked 6–9 of the T-70 frame's 134 sub-$4,000 skill players, among them Sterling Shepard (6.8) and
    Zach Ertz (6.6).
  - Every tested form built the file from the T-70 frame, so the live rule would not be the tested rule.
- **Fix, done (`c18fb62f`):** `cheap_block_file.py --group G` writes every player of draft group G's newest DK salary
  pull. Salaries and positions are fixed for the week, so a file written Thursday covers any later addition.
- **Verified:**
  - `--group 154078` (W4's 15:33 pull) holds all 292 T-70 skill players, all 134 sub-$4,000 at +2.
  - Its bonus equals the tested replay file's on all 292.
  - W5 dry run (`--group 154468`): 284 of 550 skill players at +2.
  - Production's `check_term_block_file.py` passes both at cap 2.0.
  - The writer is now create-once.
- **Thursday:** write `cheap2-w5.csv` with `--group 154468` instead of `--frame`.

## MEDIUM

**M1. A player FP lists with no projection is set to 0 and dropped, silently.**
- **Where:** `fp_projection_override.py:69` (`fillna(0.0)`); the docstring says such players keep ours.
- **How it stays silent:** coverage counts the id, `kept_ours` counts only absent ids, the union's 1.0 floor excludes
  him, and the O-22 guard never names him.
- **Verified:** all four W5 captures on 10-07 have **204 of 571** DK Main players with a null `fantasyPoints`, **82 at
  $4,000+**.
- **Fix:** keep ours for nulls, and count and name them, or refuse above a threshold.

**M2. Term-block arming has no forcing step, and the paper-only prior-top file would pass every gate.**
- **Where:** `arm_week5_saturday.sh:48,53,54`: TERM_ROWS=0, TERM_FILE=priortop-w5.csv, TERM_SHA="".
- **No forcing step:** SHAPE and FRIDAY_HEAD refuse until set, but the term block does not. If Saturday's edit is
  missed, the cheap trial silently does not run, and only `--check` prints the block.
- **Wrong file accepted:** an edit that sets TERM_ROWS=8 and the sha printed at checklist line 163 but leaves TERM_FILE
  would arm the prior-top file. `check_term_block_file.py` accepts the prior-top form by design.
- **Fix:**
  - TERM_ROWS="" refuses until it is 0 or 8.
  - Default TERM_FILE to the cheap path.
  - With TERM_ROWS≠0, refuse a file without `bonus_points`.
  - Print rows, file and sha in the ARMED line.

**M3. Production's code is not pinned between arming and Sunday.**
- **Where:**
  - `arm_week5_saturday.sh:83-88` only requires FRIDAY_HEAD to be an ancestor of HEAD.
  - The units run `$PROD`'s working tree.
  - `check_week_runtime.py:191-198` pins only the lab clone.
  - `union_reselect` records `prod_sha`, but nothing gates on it.
- **Failure:** a `git pull` after arming changes Sunday's code with no stop.
- **Fix:** step 0 requires an empty `git diff --name-only $FRIDAY_HEAD HEAD`, docs and the arm script aside. Record
  PROD's HEAD at arming, and have `check_week_runtime` refuse if it moved.

**M4. The 10:33 T-70 DraftKings pull is a silent single point of failure.** It has existed since Week 4.
- **Where:**
  - The t70-pull and t70-project units are independent (`arm_week_timers.sh:126-130,228-231`).
  - The T-70 gate checks only the projection batch time.
  - There is no other Sunday pull: O-18 says `ingest-dk` returns 403 and `s-dk` is paused.
- **Failure:** a failed pull leaves Questionable players treated as active with stale statuses. That breaks the
  money-path rule that the T-70 rebuild uses the pull made after the 10:30 inactives, and nothing alerts.
- **Fix:** gate the T-70 build on the receipt's `salary_pull` ≥ 10:30 CT, with a loud fallback.

**M5. A stop or a T-70 failure leaves the pre-inactives 09:10 book live, with no sign on TODAY.**
- **Where:**
  - `sunday_build_host.sh:544-548` writes `term_block_missing` and an ALERT nothing reads, then exits 0.
  - TODAY never reads `term_block_missing`, `mix_refused.txt` or `union_failed`.
  - There is no timeout on live_week or the union.
- **Fix:** a TODAY banner for each marker, and timeouts.

**M6. The MIX DEALT line on the upload sheet is wrong every week.**
- **Where:** `mix_dealt_shares.py:78-86` keys by `dk_player_id`, but `sunday_after_build.sh:126` passes the
  draftable-id upload, so every row counts as house.
- **Verified:** the A1 rehearsal's TODAY reads "house 152 (1.0)".
- **Fix:** map the draftable ids through the frame.

**M7. The Sunday FP load depends on three pages the money path doesn't need.**
- **Where:** `fp_projections_capture.sh:23-25` collects all four tables. A failure on any page loses the dfs load, and
  the T-70 then falls back to ours, loudly.
- **Fix:** collect `--tables dfs` alone in the T-70 window.

## LOW

- **The ownership-term retry is triggered by a term-block refusal.**
  - `grep 'OWN TERM REFUSED'` (`sunday_build_host.sh:477`) matches the term-block refusal banner.
  - On a second failure, the host retries with the ownership term he removed, which ends in H1.
  - Fix: anchor the grep, or re-word the refusal. (Two reviewers.)
- **The term-block receipt check passes if its own python crashes** (the empty `TB_WHY`, `:528-551`).
- **An empty capped term crashes the union** instead of taking the not-applied path (`union_reselect.py:1236-1254`). It
  can't be reached with a correct file.
- **A Sunday replacement turns a cheap-block row into a plain row** (`vet_replace_v4.py:305-330`); `vetting.json` still
  says T.
- **Replacements aren't re-checked against the QB cap, the 0.5K player cap or the DST cap** (`vet_replace_v4.py:285-360`).
  This extends O-37.
- **On a union-failure exit, the host skips the `superseded` marking** (`:562-567`). An edge case.
- **FP reporting:**
  - A sibling page's refusal prints "CAPTURE FAILED" even when dfs loaded.
  - A manual T-70 re-run has no `MIN_PROJ_GENERATED_AT`.
  - The fallback label file is appended, never cleared.
- **R4 late swaps rank by our projection, not FP's** (`late_inactive_swaps.py:17, 95`).
- **The arm's file check only tests "bonus ≤ cap",** so an under-dosed file (+1 under cap 2.0) passes.
- **`check_week_runtime.py:151,153` reads `MEAN_OWN_TILT="0"` as on,** so a failing `ownership_sets.py` could stop
  Saturday's arm, although nothing at tilt 0 reads that file.
- **The dead guard in `w5_write_block_files.sh:12`** greps for "LIVE BLOCK ON" in files that never contain it.
- **Docs are out of date:**
  - The Saturday canary can't see union-args; the first armed union runs at Sunday 09:10.
  - The arm header and checklist say 11 timers, but the code expects 12.
- **Stale Week-4 defaults** in `week_env.sh:43,63` (`week4-live-center`, `32cdb61`) affect only a hand-run step.
- **The arm checks TERM_FILE before step 0's pull.** A file arriving in a reports-only commit stops the arm, which
  fails closed.
- **The arm counts a Saturday 10:30 unit armed after 10:30.** Separately, any argument other than exactly `--check` runs
  the real arm.
- **The cheap writer overwrote an existing `--out`.** Fixed: it is now create-once (`c18fb62f`).

## Checked and OK

- **Legality:** every written row is checked against the DK contract and its cell shape before the dir exists. The
  upload's slot and uniqueness checks hold.
- **The cheap block's solve:**
  - The live rows are solved on FP's mean, then the 8 term rows on mean + min(0.20 × pred_own, 2.0). The arithmetic is
    exact, with no clipping.
  - One shared state holds overlap ≤ 4, player 13, DST 6 and QB 5.
  - The receipt fields match the host's check.
  - `tests/test_mix_shapes.py`: 51 passed.
- **Decisions encoded:**
  - mixt → UNION_MAIN=mix; round-robin; overlap 4.
  - The QB cap of 5 at K 26 is checked three times.
  - OWN_TILT is 0.
  - FP is the source, with `--require-after-inactives` only on the 10:50 unit and a loud fallback to ours.
- **OFF switches:**
  - Priority order is 0; MIX_QUOTAS is removed with `env -u`.
  - Winner order and select, cover and half-and-half are 0. The game cap is never passed, and is refused with mix.
  - Each one, unset, takes the original path, with the same calls, bans and order and no randomness.
- **Env names:** every UNION_* from the arm passes through `arm_week_timers` under the same name.
- **Installed state:**
  - `contests.json` = Rev6 `5f8352ee…` (the Rev3 backup is `8625de0e…`).
  - `class_model` `92cec733…`.
  - GROUP 154468 matches all 29 contests.
  - The live clone is at f69598b and clean.
  - The host copies of the arm script and the s38 snapshot are byte-identical to the repo.
- **Timers:** 12 units (10 late). The Sunday order is 04:30 / 04:45 / 05:00, 09:10 / 09:12, then 10:33 / 10:36 /
  10:40 / 10:46 / 10:50.
- **FP join:** exact on the DK draftable id (W4 316/316, r 0.966). FP cannot bring back a player we excluded.
- **Rev6 + head:**
  - 26 rows-needed; 53 entries from 26 rows; no repeated lineup inside a contest.
  - `w5_install_rev6.sh` checks Rev6 against Rev3 and the reviewer's s24 plan.
- **Entry mapping:** by contest id. A partial fill is refused, and `verify_enter_bundle` checks counts and cells.
- **union_fallbacks.sh:** drops the MIX-only and term flags and keeps FP and the QB cap. A MIX refusal under the block
  ends as a `term_block_missing` stop.
- **`check_term_block_file.py`:** refuses a +4 file under cap 2.0, a bad cap, ids, NaN or negative values, and a file
  with no bonus.
- **Tests run:** `test_mix_shapes` (51), `test_check_lab_api` (7) and `test_cheap_block_file` (12, this branch).
