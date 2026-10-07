# Week 5: the arming checklist (Tue 10-06 → Sun 10-11)

The laptop, 10-06; the reviewer has seen each item's source. One page of what must happen, in order, so nothing rests on
chat. Private paths stay private (no dollars, no entries here).

## Before Friday (laptop)
| when | item | source |
|---|---|---|
| **Wed 10-07, with the SIS acquisition** (never before Tue 13:00 CT) | the weekly vendor run `nfl-weekly-data run --week 5`: every paid page, SIS included. **Schedule rule (route-guards, the reviewer 10-06): the run is agent-started (no timer) on WEDNESDAY with the SIS acquisition, or on Tuesday no earlier than 13:00 CT. The Route importer refuses a source week retrieved before noon CT the day after its last kickoff, so an earlier run would fail the Route page (a true FAIL, never ignored).** Thursday's s-features-route rebuild (the O-25 gate's input) then reads the week imported Wednesday. W4 Route is already imported (repaired 10-06). **PROE POSTED (FP added ATL/NO by 11:20 Tue 10-06: 32 teams); the 11:20 audit-only probe captured 19 of 19 paid pages.** The production checkout was fast-forwarded to integration on 10-06 (c83fc641) so the run uses the route guards; re-check it is clean and current before Wednesday's run. | HANDOFF 10-06 |
| Wed 10-07 | O-3 SIS pass-tail: SIS session check, env check against the CURRENT policy, one outcome-blind dry run per job, then resume the three schedulers (first scheduled run Thu 09:15) | OPEN-DEFECTS O-3 |
| Wed 10-07 (afternoon, outside any build window; one heavy job at a time) | **Three rehearsals on the merged head** (agreed with the reviewer 10-06; no hand-edited receipt, no rehearsal path in verify_k90). **A1, the host chain at K 105** (W4's own env: week_env 4, W4 contests, `EXPECT_SHA` 32cdb61, `REUSE_K90_DIR` = the W4 T-70 run `20261004T155026918221Z-32cdb61`, `SKIP_PAIR=1`, scratch OUT; mix + FP + term, no QB cap): closes O-19 / O-20 / O-23 / O-24 on the real host path (the `--check` refusal, the collected preflight failures, the composite emit, the after-build sweep with a planted stray file), plus the own_shadow scratch row. It is NOT the armed configuration. **A2, the armed settings at K 26 at script level** (W4 T-70 frame, Rev3, MIX + FP + term 0.20 + `--main-qb-cap-rows 5 --main-qb-cap-k 26` + spares; vet_book, vet_replace with a test exclusion, enter_layout, mix_dealt_shares, audit): the receipt shows qb_cap_rows 5 / qb_cap_k 26; the dealt top-QB share is near study 35's .224 (max .245). **A3, one host run in the EXACT armed env on a FRESH Week-5 build** (W4 cannot be rebuilt: live_week asserts now < lock): a new lab worktree at f69598b (run dirs out of the live clone), scratch OUT, Rev3 copy, week_env 5, the arm_env values; verify_k90 with `EXPECT_SHA` f69598b, the K 26 audit, the union receipt, layout with the 1–26 pins, emit, the sweep. Known gap: FP's W5 files are not out yet, so the FP steps take their loud fallbacks. **After A3 (study 38's dress rehearsal, the reviewer 10-06):** `~/.cache/laptop-agent/rehearsal/s38_snapshot.sh <A3 union dir> <A3 OUT> <RUN_TAG> <W5 contest-details> <plan-overrides-w05> ~/private/paper-corun/rehearsal-w05` → MANIFEST to the reviewer for the binding census (if A3's FP steps fell back, the tool refuses: no FP week; then Saturday's frame + Friday's armed union args before lock). **Supply (reviewer: option i):** first one 1280/5120 Saturday-dose build (~39 min) in the same rehearsal clone, so the union takes the path Sunday takes (with a supply; auto's second-dose fallback as a bonus). **Guards:** (1) the `WEEK_WINDOW_START_UTC` override lives ONLY in the rehearsal command's env (never exported in a shell that later arms), and is disclosed in the run record and HANDOFF ("rehearsal: window start moved to <time> so the Wednesday supply qualifies"); (2) isolation: the rehearsal clone's run dirs are on no path the Saturday watcher or auto-selection reads; before Saturday's arming confirm `week5-live-center` has no results dir from it and the scratch OUT was never `~/week5-sunday`; afterwards archive the scratch OUT privately and remove the rehearsal worktree; (3) each FP fallback banner names what it fell back to (LAG ownership 0.10, our means), so Saturday's arming message can tell a real FP failure from Wednesday's expected one. | OPEN-DEFECTS O-19/20/23/24, HANDOFF 10-06 |
| Wed 10-07 (after A1–A3, outside build windows) | **The local Milly graph load** (operator 10-04/10-06; reviewer-approved `production/milly-graph-users-20261006` @ `855379ee`): `neo4j-milly start`; from that branch's worktree, `load_milly_neo4j.py --season 2026 --users-file ~/private/regulars/cohort-2026w1-4.txt` dry run first (counts, resolution, share of field = the top set only), then `--apply` with `--node-limit`/`--rel-limit` raised for the local instance; before/after counts to the reviewer; then `neo4j-milly stop` (the arm and build guards refuse / stop it anyway). Tell him the Browser address and BROWSER_PARAMS (week keys '2026-04'). | HANDOFF 10-06 |
| Thu 10-08 | O-25 Route Share companion-v1: one dry run per job (`SHADOW_DRY_RUN=1`) through the launcher lanes; deadline Sat 12:00 | OPEN-DEFECTS O-2 / O-25 |
| Thu | O-27 cbwu-oi: the fix's dry run | OPEN-DEFECTS O-27 |
| Thu | `check_prospective_gates.py --week 5` must pass (no paused graded gate; env = policy) | CLAUDE.md |
| Wed 10-07 (after A1–A3; added 10-06 by the planned-but-not-done audit) | **C3** for W4 (missed Mon/Tue): the field model's predicted vs realized payout lines, LAG vs FP targets | experiment plan 10-02 §3; Monday reads §7 |
| Wed 10-07 (audit) | **P3** paper toggles: DONE 10-07 as `scripts/p3_arms.sh` + `scripts/p3_score.py` (the frozen P3 prereg f129bc0b; W4 smoke accepted); P1's reader `scripts/p1_record.py` (the frozen P1 prereg + amendment 1) -- both read Mon 10-12 | study list l.112 |
| Wed 10-07 (audit) | **Paper shadow B** recipe (`DROP_FEATURES=qb_cpoe_l6,neutral_pass_rate_l6` on the serve path, as the 10-03 A/B): written down and dry-run, so Sunday builds it and Monday scores it beside ours and FP | OPEN-DEFECTS O-22; HANDOFF 10-06 07:13 |
| Wed 10-07 (audit) | Dashboard: merge the deployed-but-unmerged code into integration (`production/milly-graph-users-20261006` carries `bcd7fc22` / `3e2f76a2` / `f9c67f83`; live revision 00079-5lp runs it) and the `cash_rate` label ("≥ Millionaire cash line"; the reviewer wanted it before Week 5) | HANDOFF 10-05 10:16; Monday reads §8 |
| Sat 10-10 and Sun 10-11, ~10:45 CT (audit) | **OPRK history starts now** (item 8): save the DraftKings draftables JSON for group 154468 pre-lock, `curl -s https://api.draftkings.com/draftgroups/v1/draftgroups/154468/draftables > ~/private/dk-draftables/2026-w05/$(date -u +%Y%m%dT%H%M%SZ).json` (never tracked; no ingest change) | study list item 8 |

## The operator's decisions (decision sheet `briefings/2026-week-05/2026-10-05-week5-decision-sheet.md`)
**DECIDED 2026-10-06 (his formal yes):** "yes to the winners' mix with the tilt and the quarterback cap" = MIXT + the
term at 0.20 + study 35's QB cap A (5 rows at K 26). Still open for Friday: study 36's player cap (only if it passes
and he says yes), the dose confirmation, O-16, O-18's CFB part (the freshness move was OK'd and applied 10-06).

1. The shape: **MIXT** (the winners' mix + the term; his preference, study 31) or CT (Week 4's setup, the safe alternative).
2. FP projections as the projection source (decided in principle).
3. FP + props: the paired paper check (recommended) or a trial now.
4. The ownership term: ON at 0.20 on either shape (study 31 reversed study 29; his choice).
5. Dealing stays head (his pins require it; Rev3 = super-satellites on rows 1–26).
7. **The ownership tilt under FP (decision sheet row 13): DECIDED 10-06 -- 0** ("yes, remove the tilt as you suggested and proceed as planned"); the arm change is `production/arm-w5-no-tilt-20261006` @ `2f2ffa21` (for review); A2 / A3 rehearse WITHOUT the term. Earlier: keep 0.20, 0, or 0.05; the reviewer and the laptop recommended 0. If 0: the arm script's `UNION_MAIN_OWN_TILT` changes in Friday's commit; the build then makes NO FP ownership file, so study 38's snapshot generates it itself (s38_snapshot.sh, before lock). Production's W4 replay (`~/.cache/laptop-agent/rehearsal/b_w4_term_replay.sh`): P(≥1 big) 0.0094 with the term vs 0.0336 without (one week).
8. **The union overlap limit: CHANGED to 4 (10-06 evening, "Use 4"; studies 41 + 42, field audit clean).** Was: **The union overlap limit 5 (decision sheet row 14): DECIDED 10-06 -- enter it** ("Enter it in Week 5"). Mechanism merged (`UNION_MEAN_MAX_SHARED`, default 7; `d68946c7`); the arm change `production/arm-w5-ms5-20261006` @ `d7bc9a70` (for review); A2 and A3 rehearse with 5. The reviewer amends study 38 (the reference reads the live max-shared) BEFORE the W5 lock. Study 40 (the 36-slate harness) is the second source: a WORSE read before Saturday goes to him before arming.
   Note (the reviewer): --mean-max-shared also drives the TAIL SLEEVE's selection (union_reselect select_top_mean*), which can refuse at 5 ("only N rows satisfy the overlap cap"). Week 5 has no sleeve (Rev3 under head: rows 26, sleeve 0), so only the book and spares see it; a later plan WITH a sleeve must be rehearsed at 5 before arming.
9. **The MIX fill order: round-robin (10-06 evening, "Use round-robin"; study 42).** `MIX_FILL=rr` in the arm script (`UNION_MIX_FILL=rr`); Friday's rehearsal runs at 4 + rr; study 38's paper arms follow the live fill and limit (amendment 2).
10. **Switches present but OFF for Week 5 unless he says yes after their reads:** `MIX_COVER=0` (study 43: NO DIFFERENCE, not used) and `MIX_RS=0` (study 46, the half-and-half book, read pending). If `MIX_RS` becomes non-zero: (a) study 38 needs AMENDMENT 5 before the lock (until then the week is refused as invalid by amendment 4's parity); (b) NOT needed (the reviewer and the laptop agree, 10-06): gate contracts pin generation-job env only and the shadow books never mirrored the union, so the weekly record names the live union settings instead; (c) Friday's rehearsal runs with it.
11. **The half-and-half book: RESOLVED 10-06 evening -- CONTRADICTS, OFF for Week 5 (`MIX_RS=0`).** Study 46c on the 17 never-read 2022 slates: HALF − LIVE −0.02268 [−0.09830, +0.03754] (point estimate negative, which the frozen rule calls a contradiction); THIRD / TWOTHIRDS / l02 all negative in 2022; the 53-slate pool +0.014, a wash. Reproduced byte-identically. Study 38 amendment 5 stays (harmless at N = 0). Was:  **The half-and-half book: his 10-06 evening yes, PENDING the 2022 check** (decision sheet row 16). If study 46c (the 17 2022 slates, frozen before its read) does not contradict it -- CONTRADICTS = the 2022 read is WORSE at its frozen rule OR the 2022 point estimate of HALF − LIVE (P(>= 1 big), v2) is below 0: set `MIX_RS=13` in the arm script with Friday's commit, study 38 AMENDMENT 5 lands before the lock, and Friday's rehearsal runs at 4 + rr + 13. If it contradicts: MIX_RS stays 0 and he is told why.
6. The per-QB cap (decision sheet row 10): study 35 read NO DIFFERENCE, leaning positive on every endpoint (+0.026
   [−0.027, +0.083]; both seasons positive; guards 1.048 / +0.005). By its frozen §4 he may choose it as a preference;
   the reviewer and the laptop recommend it. Cap A = 5 rows at K 26.

## After his yes (laptop; the reviewer has approved each branch)
**DONE 2026-10-06 (Tuesday, the reviewer agreed: earlier merges buy rehearsal time):** all seven merged in this order;
integration `231b1ea0`, tree identical to a green trial merge (27 money-path modules: 345 passed, 3 skipped, GCP_PROJECT
unset). Rev3 installed as `~/week5-sunday/contests.json` (sha `8625de0e…` = PLAN_SHA; Rev2 kept as
`contests.json.rev2-94cc61a8`); rows-needed 26 on the merged code. The arm-script commit (SHAPE=mixt + the QB cap in
arm_env, the cap with mixt only; FRIDAY_HEAD empty) is MERGED (`50d42285` + the reviewer's gate `ab6edf8d`, approved). Wednesday's host
rehearsal runs on the merged head in the exact armed env; Friday re-verifies on the final head.
1. Merge into integration, in this order:
   1. `production/main-mix-20261006` @ `ddd470ed` (MIX / WS / FP source / spares / fallbacks): needed for FP
      projections whatever the shape;
   2. `production/o35-plan-weights-pins-20261006` @ `ce7ba02b` (pin-aware MIX weights): needed only for MIX;
   3. `production/vet-cell-order-20261006` @ `030db347` (O-36: vet_book keeps each MIX cell on its own positions;
      mix_dealt_shares counts replacements by shape): needed only for MIX (approved);
   4. `production/fp-gap-flag-20261006` @ `645bddc0` (the O-22 guard: book players without an FP projection are
      printed, recorded and tagged in vetting, `2d84b96e` approved; plus each week's replacement sources counted, with
      the no-term control rows named, `645bddc0`, for re-approval);
   4b. **Only on his yes to decision 6** (study 35 read NO DIFFERENCE, a preference by its §4; the laptop checked the
      branch's rule = the harness's, 10-06): `production/qb-cap-20261006` @ `b5514472` (the per-QB cap in ROWS,
      off by default). Arming then adds `UNION_MAIN_QB_CAP_ROWS=5` to the arm
      script's env WITH `UNION_MAIN_QB_CAP_K=26` (the runtime check refuses a mismatch with BOOK_ENTRIES), and the Friday rehearsal runs with it;
   5. `production/pins-extend-book-20261006` @ `da399bdb` (a pin may add rows without gaps): needed for his Rev3
      plan (super-satellites on rows 1–26; K 22 → 26, caps 13 / 6; approved);
   6. `production/linestar-retire-20261006` @ `b20628fc` (no LineStar capture in the build or at arming).
   7. ~~`production/neo4j-arm-check-20261006` @ `11ed00d4`~~ **MERGED 10-06** (`6af25408`, approved): the arm script
      refuses while the local Neo4j runs. Its follow-up `production/neo4j-build-guard-20261006` @ `e2845f73` (the build
      preflight STOPS a running Neo4j, never refuses) is **MERGED 10-06** (approved), so Wednesday's host rehearsal exercises it.
   8. ~~`production/freshness-after-weather-20261006` @ `dabebd49`~~ **MERGED and APPLIED 10-06** on his OK (O-18 timing:
      live s-freshness `30 8 * * *` CT). Check the Friday 08:30 run shows no weather-stale line.
   Then install Rev3 (`~/private/week5-plan/rev3-26/contests.json`, sha `8625de0e…`) as `~/week5-sunday/contests.json`,
   keeping Rev2 beside it as `contests.json.rev2-94cc61a8` (unmerged production code refuses Rev3's pins, fail-closed).
2. A follow-up for review: the arming banner prints `ENTER_LAYOUT`.
3. The money-path test modules green with `GCP_PROJECT` unset; `check_week_runtime` in the armed env: head / the plan's rows
   / no LayoutError on the installed plan (Rev3: head / 26 rows / caps 13 / 6; Rev2 would be 22).
4. The production checkout `~/projects/nfl-predictions` fast-forwarded to the merged head, clean.
5. **ONE host-level rehearsal on the merged head (the reviewer 10-06: the post-change law applied to ops; it IS the
   shape rehearsal on f69598b, not a second one):** `sunday_build_host.sh` with `REUSE_K90_DIR=<W4 T-70 run>`,
   `SKIP_PAIR=1`, a scratch OUT (never `~/week5-sunday`; no timer touched), under the EXACT `arm_env` of his chosen
   shape (pin f69598b, FP source, the term at 0.20, Rev3, K 26, plus `UNION_MAIN_QB_CAP_ROWS=5 _K=26` only on his yes).
   It re-runs Wednesday's O-19 / O-20 / O-23 / O-24 checks: any failure REOPENS that item, and the register names both
   runs ("closed on <Wed commit>, re-verified on <Fri head>"). With the cap on, the dealt top-QB share should sit near
   study 35's census (0.224 mean, 0.245 max; outcome-free). Then `arm_week5_saturday.sh --check`.
   Inside it, **the FULL REHEARSAL at Week-5 size, archive mode (the reviewer, the K-dependence lesson):** the union on the W4 T-70
   frame with the installed contests (Rev3) and his chosen arm line (e.g. MIXT: MIX + FP + the term at 0.20), `--mix-spares 15`; then vet_book
   and vet_replace with `--test-exclude-dk` of a player in >= 8 entries; then `enter_layout write`. Print and check: (1)
   the dealt cell shares by ENTRIES near A1 .30 / A2 .14 / B .28 / C .28 (pins weighted, O-35 live); (2) the 8 pinned
   contests' ENTER files carry rows 1-5 exactly as pinned; (3) 15 spares in the corpus; (4) the replacement uses
   in-shape spares or the flagged house fallback, and no row ships with the excluded player; (5) audit_build_levers
   PASS. NOT-PUBLISHABLE (test flags). The last proof before the money path runs it. The 10-06 preview found O-36
   (check 1 failed by entries until the vet-cell-order fix); its re-run with the fix passed all five.
6. The lab pin for MIX / WS: `EXPECT_SHA f69598ba…` with `CLONE ~/projects/.nfl2-worktrees/week5-live-center`
   (`optimize(second_game_pair, qb_game_max)`); the house shape could stay on `32cdb61`.

- **THURSDAY 10-08, the order (written 10-07):** (1) 09:30 props pull → `PYTHONPATH=<deployed src> python reports/lab-handoffs/props_guard_precheck.py --season 2026 --week 5` → if it passes, `gcloud run jobs execute project-slate --wait` (Wednesday's thin pull matched 120/497 < 30%: no re-run on 10-07); (2) the FP W5 live pages: `nfl-weekly-data run --week 5 --skip-fp-families --skip-sis-team-context --skip-sis-pass-tail --skip-sis-receiver-copula --skip-odds --no-login-if-needed` (unposted on 10-07); (3) 09:15 / 09:20 the SIS caches run on their schedulers (O-41 fixed): check both executions; (4) `neo4j-milly stop`; (5) A3: `A3_SNAPSHOT_DEST=$HOME/private/paper-corun/rehearsal-w05-a3 bash ~/.cache/laptop-agent/rehearsal/a3_armed_w5.sh <integration head>` (block OFF; heavy ~1.2 h; study 53's run first if it is queued) → the snapshot path to the reviewer; (6) the W5 matchup file from A3's union frame (the live-block section below), committed with its sha; (7) the Route Share dry runs (`~/.cache/laptop-agent/shadow_dry_run.sh` in each job's lane) → `check_prospective_gates.py --week 5` (expect 0 problems).
- **Thursday 10-08, before A3:** `neo4j-milly stop` (the local graph has run since the 10-07 load; the arm refuses while it runs and a build must not compete with its heap). The outside reviewer was told (10-07).

## Thursday 10-08 to Saturday 10-10: the live bonus block (decision sheet rows 21–22; his choice at arming)
- **DECIDED (10-07 ~13:10, the operator, confirmed directly): the CHEAP +2 block** (8 rows, cap 2.0) for Week 5 as a
  REVERSIBLE one-week trial under the adoption track (09-19 §1), instead of matchup. Study 53's NOT ENTERED stays on the
  record beside it. Stop rule (his, accepted): clearly worse paired P(≥1 big) over the trial weeks, or expected big seats
  more than 20% below the unblocked book (not a loss count); first full review Mon 10-19. Rollback: matchup or none.
  Matchup stays on paper (study 38's 6e / 6d arms). His final word is still given at Saturday's arming.
- **Thursday, after A3 (block OFF):** write BOTH files, and commit them under reports/, so the arm's ff-pull accepts them.
  Record both shas in HANDOFF. The helper `~/.cache/laptop-agent/rehearsal/w5_write_block_files.sh <A3 dir> <checkout>` runs
  exactly these, from the FRIDAY_HEAD-to-be checkout:
  - **cheap** (his trial). It comes from draft group 154468's NEWEST DK salary pull: the outside review's H3 (10-07)
    showed that a frame misses late-week cheap players; on W4 the group file built a book byte-identical to the tested
    frame file's. Add `--pulled-before <UTC>` only to fix a pull.
    `.venv/bin/python scripts/cheap_block_file.py --season 2026 --week 5 --group 154468 --points 2.0 --out reports/2026-10-08-live-block/cheap2-w5.csv`
  - **matchup** (the rollback). It comes from A3's union frame, because its z needs the frame's features.
    `.venv/bin/python scripts/matchup_block_file.py --season 2026 --week 5 --frame <A3 union dir>/frame.parquet --out reports/2026-10-08-live-block/matchup-w5.csv`
  - Then run the arm's own check on each, with the arm's flags:
    `scripts/check_term_block_file.py <file> --cap 2.0 --require-bonus`.
  - For the MATCHUP file only: a player on Sunday's frame but not A3's gets no bonus (disclosed; matchup z is over A3's
    skill players). The cheap file covers the whole draft group.
  - A +4 cheap file is written only if study 53 makes CHEAP4_BLOCK8 the enterable dose.
- **Friday (his cheap decision, 10-07 ~13:10):** the A3 rehearsal with the CHEAP +2 block armed exactly as Saturday will
  arm it: `A3_TERM_ROWS=8 A3_TERM_FILE=$WT/reports/2026-10-08-live-block/cheap2-w5.csv A3_TERM_SHA=<its sha>
  A3_TERM_CAP=2.0 A3_SNAPSHOT_DEST=~/private/paper-corun/rehearsal-w05` (the script checks the file against the cap). The
  s38 snapshot is the reviewer's binding 6e gate, source-agnostic: QA0 and DVP carry the armed (cheap) block at ranks
  2..25; NOTERM, MATCHUPX, COMBINED, CHEAP2 and CHEAP4 have 0 term rows; TERM8 its 8. Then the ROLLBACK's readiness:
  `w5_matchup_union_check.sh <A3 dir> <matchup-w5.csv> <sha>` puts the matchup file through Friday's T-70 union too, so
  either block can be armed Saturday without entering an unexercised file.
- **Saturday (arming):** his decision (cheap) -> the arm script's `TERM_ROWS=8`, `TERM_FILE=reports/2026-10-08-live-block/cheap2-w5.csv` (matchup only on a rollback),
  `TERM_SHA=<its sha>`, `TERM_CAP=2.0` (host copy and tracked copy alike); none -> `TERM_ROWS=0` (nothing else changes). Step 0
  runs the sha check and `check_term_block_file.py` (refuses a bonus above TERM_CAP, a cap outside (0, 5], a pred_own that is not
  bonus / 0.20), also under `--check`.

## Wednesday 10-07 to Saturday 10-10: priority-first dealing and his Rev6 contest order (decision sheet row 24)
- **RESULT (10-07 14:36), the screen as frozen:**
  - The SORT is NOT ENTERED (lower in 2 of 3 weeks; e_big ratio 0.587). `PRIORITY_ORDER` stays 0, and A3 runs
    without `A3_PRIORITY_ORDER`.
  - **Rev6 passed** (ratio 1.466) and is INSTALLED: 10-07 14:38, sha `5f8352ee…`; Rev3 is kept as
    `contests.json.rev3-8625de0e`; the arm's PLAN_SHA is Rev6 (`5766b799`, host copy synced). The equivalence
    with the reviewer's s24 Rev6 (`ac10ddf6`) was checked at install.
  - Record: `reports/2026-10-07-priority-deal-replay-result.md`. The steps below stand as written for a later
    week.
- **His request** (to the laptop, 10-07): "Let's try to do this one this week as it seems more promising." His contest order
  (final, 10-07): "4444 (all of them including the showdown...) / 555 / WFFC / 333 / Millionaire / Midseason warmup /
  Everything else including milly qualifiers".
- **The vehicles:**
  - The switch `f19222e0` (`UNION_PRIORITY_ORDER`, off): the 18 non-block rows sort by priority_deal's score; the cheap
    block keeps its ranks.
  - The private plan Rev6 (sha `5f8352ee…`; Rev4 and Rev5 were never installed): Rev3's contests re-ordered, with equal weights, so the same book. It is
    staged as `~/week5-sunday/contests.json.rev6-5f8352ee`, not installed.
- **Wednesday (after study 56's run):** `bash ~/.cache/laptop-agent/rehearsal/priority_deal_replay.sh f19222e0
  ~/week5-sunday/contests.json.rev6-5f8352ee` runs the frozen harm screen
  (`reports/2026-10-07-priority-deal-harm-screen.md`).
  - (i) THE SORT (CB_PRI vs CB_REV6) decides the switch.
  - (ii) THE RE-ORDER (CB_REV6 vs CB) decides Rev6.
  - Report both to him and to the reviewers.
- **Install Rev6** (if pair (ii) passes), before Thursday's A3:
  - `cp -p ~/week5-sunday/contests.json ~/week5-sunday/contests.json.rev3-8625de0e`, then
    `cp -p ~/week5-sunday/contests.json.rev6-5f8352ee ~/week5-sunday/contests.json`.
  - Check the sha is `5f8352ee…`.
  - Set the arm script's `PLAN_SHA` to Rev6 (tracked copy and host copy; the "is not Rev3" message names Rev6).
  - Send the reviewer the equivalence check against the reviewer's Rev6 s24 plan (`~/s24-panel/plan-week5-rev6-s24.json`): the same
    contest_id order and head ranks.
- **Thursday:** study 59's read (the reviewer; CB_PRI − CB on Rev6; by about noon). He decides whether its bar applies.
- **Friday:** if pair (i) passed (and 59, if he set that bar) and the reviewer's 6k is in, A3 runs with
  `A3_PRIORITY_ORDER=1` on top of the cheap block. The union log prints `PRIORITY ORDER: … block positions kept […]`, and
  the receipt carries `config.union.priority_order`.
- **Saturday:** `PRIORITY_ORDER=1` in the arm script only on HIS yes at arming. Otherwise it stays 0, and Rev6 stays as his
  plan order.
- **Rollback:** `PRIORITY_ORDER=0`, and Rev3 from the backup with its PLAN_SHA.

## Sunday 10-11 and Monday 10-12: study 38 (the FP paper co-run; operator 10-06 "yes, please try it, I want to exhaust all reasonable options")
- **Sunday, right after the T-70 union and BEFORE 12:00 CT:** snapshot (copies, read-only reads) the T-70 run dir and the union dir (frame.parquet, candidates.parquet, receipt.json, union_args.txt, lever_audit.json) and OUT's proj_fp-<RUN_TAG>.csv AND its .csv.json sidecar (apply_proj_source refuses without it), ownership_fp-<RUN_TAG> (+ receipts), union-args-<RUN_TAG>, the dk-status-<utc>.csv the T-70 union read (`--dk-status`; unavailable_ids needs it), contests.json and the week's DK contest-details file (for the study's size/seats/big plan; the reviewer's tracked `scripts/s38_plan.py` converts them) and `plan-overrides.json` (any per-contest decision he makes that week, e.g. W5's `{"196421726": {"big": false}}`, the $125 WFFC; `{}` if none) to `~/private/paper-corun/2026-w05/` with MANIFEST.txt (sha256, bytes, source path and mtime, the receipt's built_utc, the snapshot time). Never edits the live dirs; never writes under `~/week5-sunday`. The pre-lock provenance for the paper books, built after lock by the reviewer.
- **The prior-top block on PAPER (the operator 10-07, "Paper only"; study 38 amendment 6b): the snapshot step runs EXACTLY** (all three paper files, absolute paths; the reviewer 10-07) `S38_PAPER_TERM_FILE=$HOME/projects/nfl-predictions/reports/2026-10-07-prior-top-term/priortop-w5.csv S38_PAPER_DVP_FILE=$HOME/private/paper-corun/dvp/2026-w05.csv S38_PAPER_FACTOR_FILE=$HOME/private/paper-corun/factor/2026-w05.csv S38_PAPER_MBLOCK_FILE=$HOME/projects/nfl-predictions/reports/2026-10-08-live-block/matchup-w5.csv bash $HOME/projects/nfl-predictions/scripts/s38_snapshot.sh <union dir> <OUT> <RUN_TAG> <contest-details json> <plan-overrides json | -> $HOME/private/paper-corun/2026-w05` (the DvP and factor files are written by the two steps below, right after the T-70 union) -- an ABSOLUTE path in the FRIDAY_HEAD production checkout (the reviewer: a cwd-relative path dies at snapshot time and costs the week). The file's sha256 must be 694a6622589d50766e290fa3aef92a263fa8d36bea2a8786c305563ac272de0b (`paper-term-priortop-w5.csv` in MANIFEST.txt). Live stays OFF (`TERM_ROWS=0`). **Friday's rehearsal runs this same invocation** (dest `~/private/paper-corun/rehearsal-w05-fri`; the DvP / factor files `.../dvp/rehearsal-w05-fri.csv`, `.../factor/rehearsal-w05-fri.csv`; the integrity gate then checks TERM8, DVP, MATCHUPX and COMBINED together) and its snapshot path goes to the reviewer for the live-mode integrity gate (TERM8 at ranks 2…25; NOTERM == QA0; "live 0, paper 0 / paper block applied"). From W6 a new file each week from the settled fields (make_priortop_files' rule), its sha in HANDOFF.
- **The FP-means DvP on PAPER (the operator 10-07, "Yes, paper arm"; O-40; study 38 amendment 6c, arm MIXT_QA0_DVP):** right after the T-70 union and BEFORE the snapshot, write the week's file from the union's frame (seconds; BigQuery reads only): `cd $HOME/projects/nfl-predictions && .venv/bin/python scripts/paper_dvp_file.py --season 2026 --week 5 --frame <union dir>/frame.parquet --fp <OUT>/proj_fp-<RUN_TAG>.csv --prior 4:$HOME/private/paper-corun/dvp-inputs/w04-t70-frame.parquet:$HOME/private/paper-corun/dvp-inputs/proj_fp-w4.csv --out $HOME/private/paper-corun/dvp/2026-w05.csv` (the W4 inputs pinned 10-07: frame 772ba860, proj_fp-w4.csv 8bba650e; expect `slope +0.585 ... from 152 prior player-weeks (weeks 4)` -- the slope depends only on W4's inputs and the warehouse's W4 actuals, so a different number means the actuals moved: say so in HANDOFF), then add `S38_PAPER_DVP_FILE=$HOME/private/paper-corun/dvp/2026-w05.csv` to the snapshot invocation above (MANIFEST shows `paper-dvp-2026-w05.csv` with the file's sha; the input shas are in the file's `#` line; the arm, lab `05acfee`, takes adj_points - fp, FP's 0 kept at 0). A `PAPER DVP REFUSED` means the arm is missing W5 (no improvised slope; the reviewer 10-07). **Friday's rehearsal** runs the same with `--out $HOME/private/paper-corun/dvp/rehearsal-w05-fri.csv` on the rehearsal union's frame and FP capture, so the integrity gate checks both MIXT_QA0_TERM8 and MIXT_QA0_DVP. **From W6:** one more `--prior` per settled FP week, from that week's snapshot copies (`--prior 5:<2026-w05 snapshot>/frame.parquet:<2026-w05 snapshot>/proj_fp-<RUN_TAG>.csv`).
- **The factor bonuses on PAPER (the operator 10-07, "schedule any necessary experiments this week"; study 38 amendment 6d, arms MIXT_QA0_MATCHUPX and MIXT_QA0_COMBINED; the outside reviewer's Experiment A formulas):** right after the T-70 union and BEFORE the snapshot, beside the DvP file: `cd $HOME/projects/nfl-predictions && .venv/bin/python scripts/paper_factor_file.py --season 2026 --week 5 --frame <union dir>/frame.parquet --fp <OUT>/proj_fp-<RUN_TAG>.csv --out $HOME/private/paper-corun/factor/2026-w05.csv` (seconds; BigQuery reads only; expect `unmatched opponents 0`), then add `S38_PAPER_FACTOR_FILE=$HOME/private/paper-corun/factor/2026-w05.csv S38_PAPER_MBLOCK_FILE=$HOME/projects/nfl-predictions/reports/2026-10-08-live-block/matchup-w5.csv` to the snapshot invocation (MANIFEST shows `paper-factor-2026-w05.csv`). A `PAPER FACTOR REFUSED` means both 6d arms are missing W5. **Friday's rehearsal** runs the same with `--out $HOME/private/paper-corun/factor/rehearsal-w05-fri.csv`. The port reproduces the outside reviewer's own W4 bonus files exactly (270 FP rows, all four bonuses).
- **After lock (Sunday):** the reviewer builds study 38 from the snapshot (lab `d36d07d`, prereg amendment 1b `1d461fba`); the laptop re-builds and compares the printed `books identity` (a content hash) and books.json byte for byte; Monday the laptop re-runs the score byte-identically.
- **If the T-70 build fell back to OUR projections** (both FP captures before the inactives, or any FP refusal): the union has no `--proj-source`, the snapshot tool refuses ("not an FP week") and study 38's week is INVALID by its frozen rule (W9 replaces it). Do NOT force a snapshot.
- **Monday, after settlement imports the standings:** add week 5 to `~/moneygate/weeks.json` (paths + shas), `moneygate_score.py fetch` for W5, then the reviewer's study-38 scorer; the laptop re-runs it byte-identically.
- **Standing Monday line from the Monday after Week 6 (FP weeks 4–6; study 22a, the outside review via the reviewer):** the ownership-information regression (realized points ~ FP projection + FP ownership), the reviewer's script, run by the laptop with the Monday records, so the tilt at 0 never becomes the next untested constant. Descriptive. Command (lab `27a1cfe` -- prints a NOTE while fewer than 3 FP weeks are pooled --, after weeks 5–6's fetch_week and with their s38 snapshots): `scripts/s22a_ownership_line.py --prod <production checkout> --week 4=~/private/paper-corun/ownline-w04 --week 5=~/private/paper-corun/2026-w05 --week 6=~/private/paper-corun/2026-w06`. W4 alone (reproduced by the laptop 10-06): −0.288 [−1.161, +0.284]; both 0 and +0.20 inside.
- **Beside it, study 22b's red-zone line (the reviewer; operator 10-06: do we use our red-zone data appropriately, can it be tested):** red-zone / goal-line usage beyond FP's projection, the mean per SD and big games (>= FP + 10) as an odds ratio per SD, game-week clustered; the same inputs and NOTE as 22a. Command (lab `83fed92`, which also prints the MULTIPLICITY line): `scripts/s22b_redzone_line.py --prod <production checkout> --week 4=~/private/paper-corun/ownline-w04 --week 5=~/private/paper-corun/2026-w05 --week 6=~/private/paper-corun/2026-w06`. W4 alone, reproduced by the laptop 10-06: the NOTE; one interval (WR rz20_targets_smoothed, OR 0.40) excludes no-effect in the NEGATIVE direction, 1 week of 6 features: noise until weeks pool.


**Before Friday's fast-forward:** the outside review file is UNTRACKED in the production checkout; move it into a tracked commit and off the checkout, or the ff-only pull and Saturday's clean-checkout check stop.

## Saturday 10-10 (the laptop arms; fail-stop script, ask only if blocked)
- **CANARY (the reviewer, 10-06):** the 10:30 `d12800-sat` build is the first live K 26 run through the armed host. By
  11:00, check its receipt (identity f69598b, operational_k 26, tail 0), its lever audit PASS, and the union-args file
  (`--main mix`, the FP source, the term, `--main-qb-cap-rows 5 --main-qb-cap-k 26`). Any failure leaves about 24 hours
  to fix before Sunday.
- **APPROVED and MERGED 10-06:** `scripts/arm_week5_saturday.sh` (c68da24c + e13ec346; host-local copy synced).
  - Friday's one commit sets SHAPE and FRIDAY_HEAD in the tracked copy.
  - The chosen shape is rehearsed on pin f69598b.
  - Then `--check` runs Friday evening. It lists the planned units and stops unless the count is 11.
  - If it stops on 12, a non-timer unit name has appeared in arm_week_timers.sh's print-only output (the reviewer). It fails safe.
  - Friday: set SHAPE (mixt | ct) and FRIDAY_HEAD; confirm the dose (0 / 4800).
  - It refuses until those are set. It checks Rev3's sha and K 26, and arms 11 timers (9 late).
  - `--check` runs steps 0 and 6 only.
- A host-local Week-5 arm script from `~/.cache/laptop-agent/w4_arm_saturday.sh`: GROUP 154468; the inputs (sets, lag +
  gate, TabPFN lags); **no LineStar step**; the arm line per his Friday choices, e.g. `UNION_MAIN=mix
  UNION_MIX_PORTFOLIO=mix UNION_PROJ_SOURCE=fp UNION_MAIN_OWN_TILT=0.20 UNION_MAIN_OWN_PREDICTOR=fp` (MIXT: study 31
  recommends the term ON on either shape; his choice) and `EXPECT_SHA` / `CLONE` above; plain MIX without the term is
  not to be armed (study 31); the expected timer count includes the FP projections capture (11, or 9 when
  armed late).
- The FP projections capture runs right after arming; Sunday's runs at 10:40 CT, before the 10:50 T-70 build.
- **The arming message to him names the one-game risk** (the reviewer's pre-mortem follow-up, 10-06): if Saturday's Week-5 build puts most of the book's QBs in one game (Week 4's MIXT replay: 91% in JAX–CIN; the historical slates 25–35%), say so in plain words before lock, with the share and the game.

## Sunday 10-11
- The T-70 build on the post-10:30 salary pull; FP projections (refusal → ours, loud); the ownership chain FP → LAG
  0.10 → none; WS/MIX spares and the house fallback for late scratches (`ddd470ed`).
- Any manual relayout passes `ENTER_LAYOUT=head` (O-34).
- **Overlay monitor** (audit 10-06; built 10-05, never run on a live slate): ~11:15 CT `overlay_monitor.py flag --slate 2026-10-11 --out-dir ~/private/overlay/2026-w05`; after lock `overlay_monitor.py finalize --flags <the flags file>`. Read-only.
- Paper shadow B (O-22): built with Sunday's projections, never entered.

## Monday 10-12
- **FIRST: the cheap +2 block, on vs off, for his Week-6 decision** (the operator 10-07: "Let's keep it on for week 5 and see how it compares for deciding what to do week 6"). From study 38's scoring on the real W5 results:
  - MIXT_QA0 (his live book, the cheap block on) vs MIXT_QA0_NOTERM (the same construction without it): P(≥ 1 big seat),
    expected big seats, and the realized big seats / tickets in his priority contests;
  - plus the 8 block rows' own finishes against the 8 rows they replaced;
  - plain words, with one week's limits stated (a single week rarely separates two books).
  The stop rule's first full review stays Monday 10-19.
- **The W6 trial candidate's first real-week read** (the operator 10-07 agrees with the outside reviewer: study 56's fewer QB + 1
  rows): study 38's MIXT_QA0_QB2HALF vs MIXT_QA0 on the real W5 results, in plain words.
- **Study 60's ladder file for the NEXT week** (the format agreed with the reviewer 10-07), once that week's plan and contest details
  are captured and loaded into the ladder table. First run s38_plan.py (lab) on the week's contests.json and details, then
  `PYTHONPATH=src .venv/bin/python scripts/cash_line_rows.py --week W --plan-s24 <that s24 plan>`. It writes
  `~/private/cash-line/cash-lines-wWW.csv` once; send its sha to the reviewer. W02–W05 were written 10-07.
- **The FP #1 vs the props #1** (study list 60's step 3): the W5 FP-means plain optimizer's top row against the props-means one,
  on the real Millionaire field and the sharpest priority field, with each row's share of the field beaten.
- **Friday, before this:** the side-by-side of the two W5 books (the same snapshot, the block on vs off): which of the 26 rows
  change, the sub-$4,000 players added, the projected points given up per row, and the shapes / QB spread.
- **The weekly Milly-graph refresh -- EVERY Monday from now on** (the operator 10-07: "let's make sure each week we keep the enhanced neo4j data populated and learn from it"): after settlement adds the week to `~/moneygate/weeks.json`, `bash scripts/neo4j_weekly_refresh.sh <week> ~/private/neo4j/users-cohort-plus-ours.txt` -- starts the local Neo4j, loads the week's Millionaire lineups (top set + the cohort's and our portfolios, FP values) and its pre-lock facts, runs the standing learning queries (`scripts/graph_weekly/`, the outside reviewer's, copied byte-identical: the within-portfolio facts, the sub-$4,000 count check, the cheap-tier boom check and `tier_edges.py`, the picks-vs-field edge by salary tier; aggregates to `~/private/neo4j/weekly/<season>-w<NN>/`), and stops Neo4j on every exit IF the refresh started it (an instance already running, e.g. the outside reviewer's, is left as found and must be stopped before Saturday's arming; proven on the W4 run 10-07). Record in the weekly record / HANDOFF: the within-portfolio table's lines (which pre-lock facts separated the regulars' top-1% lineups this week and cumulatively), our T-70 book's sub-$4k counts (W1–W4: 0.79 / 1.13 / 0.85 / 0.91 per row), and tier_edges' running mean (where our picks gain or lose by salary tier; W1–4 ours: QB −1.23, $8k+ −2.22, $6–7.9k −2.12, $4–5.9k −4.51, <$4k +4.75, DST +1.49 points per lineup vs the field); anything that holds every week goes to the study list. Never during a build window. **Every week, before the refresh:** the week's contests must carry a type in the private type CSVs (`~/private/regulars-share/week5_type_mapping.csv` covers W5; extend it the same way for W6+), or learning step 6 (`scripts/priority_field_monitor.py`, his priority contests: $4,444 / $555 / $333 / FFWC; the outside reviewer's fc3aff11) prints "no typed priority contest" for the week. **Monday 10-12, once (after the reviewer's review of 1f82932d):** with Neo4j still up from the W5 refresh (`--keep-running`), re-run the facts-only pass for W1–4 (`load_milly_neo4j.py --season 2026 --week N --users-file <private users file> --include-fp --with-facts --facts-only --apply`, about 1 min each) so the earlier weeks carry the 10-07 result facts (Game pre_total_rank, out_best_stack_pts, out_is_best_stack_game, out_field_qb_share, out_top1_qb_share; Lineup lbl_stack_n / lbl_bring_n / lbl_max_game); then `neo4j-milly stop` and tell the outside reviewer.
- **The early checkpoint** (experiment plan 10-02 §6; audit 10-06): O1 / A3 / B2 interim at the doubled bar; the first P3 weekly read; shadow B scored beside ours and FP in `weekly_projection_accuracy.py`.
- **P1 and P3, the two frozen weekly readers (from W5; the reviewer froze both 10-07), after settlement and the standings import:**
  1. `~/moneygate/weeks.json` gets W5 (t70_run, saturday_run, details = the W5 capture, entered_union, millionaire_contest,
     standings_dir, contests_src); `~/moneygate/books/w5/contests.json` = the contests as entered. Then
     `scripts/moneygate_score.py fetch --weeks 5` and `scripts/moneygate_score.py reconcile --weeks 1,2,3,4,5` (must PASS:
     every real entry reproduced; the scorer is dd8ff1f7, week dates from nfl_raw.schedules).
  2. The ladders: every W5 plan contest must be in `nfl_raw.dk_payout_ladders` (the rev2 capture is loaded, 29
     contests); a contest added later is fetched after settlement (`scripts/dk_contest_details.py`, public, no login)
     and loaded with `scripts/load_payout_ladders.py --season 2026 --week 5 --file <capture> --apply`.
  3. **P1:** `PYTHONPATH=src python scripts/p1_record.py --weeks 1,2,3,4,5 --out ~/moneygate/results/p1_w05.json` --
     per class the week's mean latent z (unique lineups) minus the frozen break-even z; no flag before W8.
  4. **P3:** `CLONE=$HOME/projects/.nfl2-worktrees/week5-live-center bash scripts/p3_arms.sh <the W5 entered union dir>
     ~/moneygate/p3/w05` (ENTERED byte-identical or the week is VOID; twin builds), the week's s38 plan (the lab's
     `scripts/s38_plan.py` on the installed contests.json + the W5 capture + his overrides: the SAME plan study 38 scores
     with), then `PYTHONPATH=src python scripts/p3_score.py --week 5 --arms ~/moneygate/p3/w05 --plan <plan-w05-s24.json>
     --ledger ~/moneygate/results/p3_ledger.csv` -- d = big seats(ENTERED) - big seats(MEAN_MILP) and the class lines.
  4b. **Study 60** (frozen 8a22f5f2; the reviewer re-runs the same and compares): after P3's arms and the reconcile,
     `PYTHONPATH=src python scripts/s60_record.py --census --arms 5=~/moneygate/p3/w05` FIRST (the identity census),
     then `PYTHONPATH=src python scripts/s60_record.py --weeks 5 --arms 5=~/moneygate/p3/w05`. If vetting changed the
     lineup entered at rank 1 or 2, say so in words from the published upload (a disclosure; d is unchanged).
  5. Report P1's and P3's lines side by side (the weekly record and HANDOFF); P3's W8 read is descriptive, its W12 rule
     binding (7 of 8); P1's flag from W8 (>= 4 prospective weeks).
- `weekly_projection_accuracy.py` (ours / FP / blend) and `weekly_fp_props_check.py` (FP vs FP + props), then `pool`.
- Settlement; the entered book vs the paper rebuild of today's house shape on the same slate.
- **The class model refit, a MEASURED step from 10-12 (O-42; the reviewer 10-07):** W5 runs Week 4's model (W1 + W3, `92cec733`) because the 10-05 Monday refit was missed. Monday: fit `scripts/fit_field_class_model.py` on W1 + W3 + W4 (W2 stays out, the defect week) with its leave-one-week-out receipt; score BOTH models out of sample on W5's real Millionaire field (top-1% lift at the model's top 1%: `92cec733` vs the refit); W6 installs the refit (then refit on W1 + W3 + W4 + W5) only if its W5 lift is at least `92cec733`'s, else keep it -- recorded either way, its sha pinned as the W6 arm's CLASS_SHA.
- The monkey benchmark and the scorecard (once `production/moneygate-harness-20261005` merges, under review): `moneygate_monkeys.py --week 5` (1,000 books per monkey; M1 random pool rows, M2 the same under our caps and dealing, M3 random legal lineups; "worse than random" said plainly below the 25th) and `moneygate_scorecard.py`.
- `weekly_picks_vs_field.py week --season 2026 --week 5 --contest <Milly id> --frame <T-70 frame> --cohort ~/private/regulars/cohort-2026w1-4.txt --entry-history <the refreshed private entry history> --out-dir ~/private/picks-vs-field`, then `pool` (ours vs the regulars, picks vs the rest of the field; after the Monday standings load; once its branch merges).

## Week 6 onward: choosing entries for a big contest (study 32's R4; Addendum 137; merged `c67da304`)
- When he holds 2–3 entries in ONE big contest (a $4,444 MEGA, a $333 Wildcat, ...), after the T-70 union and the
  vetting / replacement:
  `scripts/choose_entries.py --run <T-70 union run> --book <entered book.csv> --ownership <ownership_fp-<tag>.csv>
  --contests ~/weekNN-sunday/contests.json --contest-details <contest-details json> --contest-id <id> --m <2|3>
  --out ~/private/entry-choice/wNN-<id>.json`.
  - It prints R4's rows beside book order (R0); enter R4's.
  - With ONE entry, no rule beats random: any row.
- Monday: `scripts/score_entry_choice.py --choice <that json> --standings <the contest's standings csv> --entered R4
  --tally ~/private/entry-choice/tally.jsonl --week NN`.
  - This is the paired R0-vs-R4 tally.
  - After 8 paired contests the decision on keeping R4 goes to him.

