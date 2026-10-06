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
8. **The union overlap limit 5 (decision sheet row 14): DECIDED 10-06 -- enter it** ("Enter it in Week 5"). Mechanism merged (`UNION_MEAN_MAX_SHARED`, default 7; `d68946c7`); the arm change `production/arm-w5-ms5-20261006` @ `d7bc9a70` (for review); A2 and A3 rehearse with 5. The reviewer amends study 38 (the reference reads the live max-shared) BEFORE the W5 lock. Study 40 (the 36-slate harness) is the second source: a WORSE read before Saturday goes to him before arming.
   Note (the reviewer): --mean-max-shared also drives the TAIL SLEEVE's selection (union_reselect select_top_mean*), which can refuse at 5 ("only N rows satisfy the overlap cap"). Week 5 has no sleeve (Rev3 under head: rows 26, sleeve 0), so only the book and spares see it; a later plan WITH a sleeve must be rehearsed at 5 before arming.
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

## Sunday 10-11 and Monday 10-12: study 38 (the FP paper co-run; operator 10-06 "yes, please try it, I want to exhaust all reasonable options")
- **Sunday, right after the T-70 union and BEFORE 12:00 CT:** snapshot (copies, read-only reads) the T-70 run dir and the union dir (frame.parquet, candidates.parquet, receipt.json, union_args.txt, lever_audit.json) and OUT's proj_fp-<RUN_TAG>.csv AND its .csv.json sidecar (apply_proj_source refuses without it), ownership_fp-<RUN_TAG> (+ receipts), union-args-<RUN_TAG>, the dk-status-<utc>.csv the T-70 union read (`--dk-status`; unavailable_ids needs it), contests.json and the week's DK contest-details file (for the study's size/seats/big plan; the reviewer's tracked `scripts/s38_plan.py` converts them) and `plan-overrides.json` (any per-contest decision he makes that week, e.g. W5's `{"196421726": {"big": false}}`, the $125 WFFC; `{}` if none) to `~/private/paper-corun/2026-w05/` with MANIFEST.txt (sha256, bytes, source path and mtime, the receipt's built_utc, the snapshot time). Never edits the live dirs; never writes under `~/week5-sunday`. The pre-lock provenance for the paper books, built after lock by the reviewer.
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

## Monday 10-12
- `weekly_projection_accuracy.py` (ours / FP / blend) and `weekly_fp_props_check.py` (FP vs FP + props), then `pool`.
- Settlement; the entered book vs the paper rebuild of today's house shape on the same slate.
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

