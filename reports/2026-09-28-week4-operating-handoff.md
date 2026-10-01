# Week-4 operating handoff (written 2026-09-28, Monday) — read this first

This is the take-over document for whoever runs production in Week 4. From Week 4 that is **the laptop**: production
hosting moves at the Tuesday 09-29 cutover. The workstation stays available for lab panels through Friday 10-02 and must
be free by the weekend: no nfl processes, nothing the money path depends on, result files pushed by Friday evening
(operator, 21:20 CDT 09-28). It is written so another model can run
the week without the operator re-explaining anything.

- It complements `HANDOFF.md` (the chronological log, newest first) and supersedes, for current state,
  `reports/2026-09-15-week2-operating-handoff.md` and `reports/2026-09-24-production-moves-to-the-laptop.md`.
- The machine-move document stays authoritative for the **cutover checklist** (its §3) and the data to carry (§4).
- Where this document and a newer `HANDOFF.md` entry disagree, the newer entry wins.

Times are CT (Central, UTC−5) unless marked Z.

**Week 4 at a glance:**
- DraftKings main draft group **154078**: lock **Sunday 2026-10-04 12:00 CT** (17:00Z); late kickoffs 15:05 and
  15:25 CT; 619 players priced.
- TNF: Thursday 10-01. MNF: Monday 10-05.

Sections:
0. Ground rules
1. Where everything is
2. The Week-4 configuration and its evidence
3. What is running now
4. The week, day by day
5. The Sunday money path
6. Monday/Tuesday settlement and the paper arms
7. Lab operations on the laptop
8. Production Cloud Build / Cloud Run
9. Open defects and risks
10. File index

---

## 0. Ground rules (each one cost money, a day, or trust when broken)

**Security. The production repo is PUBLIC.**
1. `contests.json` (the stake plan) is never committed or printed. The same goes for licensed vendor data (`/sis/`,
   `fantasy-points/`), raw DraftKings entries and standings exports, `DKEntries*.csv`, entry IDs, user handles,
   credentials, and dollar figures.
2. Private artifacts go to `gs://nfl-predictions-503414-raw/private/…` or `~/.cache/laptop-agent/`.
3. The rehearsal tools print dollar values only with `--show-value`. Never paste those values into a tracked file.

**Money path** (Week 1–3 lessons; each one cost real money):
1. **Never enter an untested rule on an entered book.** Test it on the historical books first.
2. **Scratch protocol.** Remove a player from entered lineups only when DraftKings marks him OUT/IR or the official
   inactives name him. Answer "replace X" with his live DraftKings status first.
3. **Never select on raw expected payout** (a 1-in-10,000 event decides it).
4. **The T-70 rebuild must use the salary pull made after the 10:30 CT inactives.** Week 1's T-70 ran on an earlier
   pull and missed them.
5. **The satellite late swap touches only flat-payout contests** (§5.4). A row that also sits in the Millionaire or a
   cash qualifier stays exactly as entered.
6. **Check the ledgers before recommending any lever.** Late swap for the tail objective was already closed negative
   (lab 023/024, system study Addendum 67). The laptop recommended it on 09-27 without checking and had to correct
   itself (HANDOFF `cb453929`).
7. **Never tune on a hindsight input.** The Week-3 ownership tilt's 156.8 came from realized ownership; the pre-lock
   sets gave 148.1 against 151.4 with no tilt. The tilt was reverted to 0.

**Harness and host:**
1. **Operator-only actions.** The harness refuses:
   - pushes to `main`;
   - systemd unit writes;
   - create-once publishes;
   - the automated DraftKings standings downloader.

   **Cloud Run cadence jobs are the agent's (operator, 2026-09-29: "can we make it so you can run these commands so I
   don't ever miss anything").** The laptop agent executes `ingest-nflverse`, `build-features`, `ingest-props`,
   `tabpfn-gen`, and `project-slate` with or without the T-70 flags itself, on schedule. It checks each execution's
   `succeededCount` and the proof lines. If the harness ever refuses one again, stop and print the command for the
   operator.

   Never route around a refusal. Print the exact one-line command for the operator, naming **which machine and which
   day**, record it in `HANDOFF.md`, and carry on with everything else.
2. **No heavy Cloud Run** (operator, cost). Panels, replays and rehearsals run on the laptop. Cloud Run is used only
   for the production cadence jobs (`project-slate`, the ingest jobs).
3. **Running worktrees.** Never commit or check out in a worktree that a running panel or runner uses: runners stamp
   HEAD per slate. Never `git checkout --` a file with uncommitted work.
4. **Process and git hygiene.**
   - Never put a script name in `pkill -f`/`pgrep -f`; kill by pid.
   - Never pass `-q` to pytest.
   - `git fetch --all`, never `--prune`.
5. **HANDOFF headings** are stamped from `date`, never an estimate.
6. **Commit trailer:** `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
7. **Hardware.** At most one heavy local command at a time (one panel, one build, one targeted pytest module).
8. **Lab exclusions** (standing):
   - do not launch PREREG-101;
   - do not re-run or re-read PREREG-099;
   - do not read bank 991;
   - do not touch `~/projects/.nfl2-worktrees/week2-release-2dc116c`;
   - do not work in the nfl2 main checkout.

**Decisions:**
1. **The operator owns every protocol and bankroll decision:** contest mix, entry counts, dose, and adopting any
   selector, filter or late-swap rule. Present the measured case; do not decide for him.
2. **The external reviewer's rulings reach the laptop only through the operator.** Record them verbatim in `HANDOFF.md`.

---

## 1. Where everything is (laptop)

| What | Path / id |
|---|---|
| Production repo (GCP `nfl-predictions-503414`, us-central1), PUBLIC | `~/projects/nfl-predictions`. The cutover switches this clean checkout to the integration branch (machine-move §3 step 4). Its `.venv` is an editable install of that checkout: pass `PYTHONPATH=<worktree>/src` when running a worktree's code |
| Integration branch (HANDOFF, reports, Sunday scripts) | `production/week3-integration-20260921`; the laptop's worktree is `~/projects/.nfl-predictions-worktrees/laptop-agent-intro-20260922` |
| Lab repo (GCP `nfl-2-506823`), private | `~/projects/nfl2` (do not work in the main checkout); worktrees under `~/projects/.nfl2-worktrees/` |
| **Lab code for Week 4** | branch `laptop/two-track-selector-20260927` @ `54dd512` (`54dd5126be04020a2267dc41a0ef1504d1415296`): the mean selector, the tail sleeve by mean, the class sleeve (`boom_sleeve`), the late-swap policy `nfl2.sat_late_swap`, `--min-proj`, and the DST cap. `EXPECT_SHA` moves to it after Wednesday's full-size smoke (§4). The live clone must be a clean detached worktree at exactly that commit |
| Week-3 lab pin (fallback) | `65305f5a6c33dba6ffa299813ee689b618bbcd30` (the Week-3 `EXPECT_SHA` and `week_env`'s current default; branch `laptop/flex-latest-kickoff-20260924`). 54dd512 descends from it and from the Week-2 repair `2dc116ce` |
| Ledger rows (laptop) | lab `laptop/ledger-laptop-rows-20260924` (rows L02–L11; L12/L13 go here after production re-runs the readers) |
| Class model (private) | `gs://nfl-predictions-503414-raw/private/week4/class_model_w4_w1w3.json` (sha256 `92cec733…`); local copy `~/.cache/laptop-agent/class-model/`. Fitted by `scripts/fit_field_class_model.py` on Weeks 1 and 3 only |
| Private rehearsal inputs | `~/.cache/laptop-agent/rehearsal-w01/`, `rehearsal-w03/` (run dirs + contest details), `w3-bundle/` (the entered Week-3 bundle; contains entry IDs, never print); bucket `gs://…/private/rehearsal/` |
| Lab panel outputs | `~/.cache/laptop-agent/l09` … `l13` (results jsonl + `drive.log`) |
| Host working dir | `~/week1-sunday/` (created at cutover; the DK loop's pid file lives there); `~/week4-sunday/` for the week's `contests.json`, `ENTER/`, `ENTERED/` (never commit) |
| Warehouse | BigQuery `nfl_raw`, `nfl_features`, `nfl_predictions` in `nfl-predictions-503414` |
| Assistant memory | `~/.claude/projects/-home-erich-projects-nfl-predictions/memory/` (supporting only; never the handoff) |

---

## 2. The Week-4 configuration and its evidence

Settled 2026-09-28. The operator relayed the reviewer's ruling at 10:26 CDT (HANDOFF) and production armed it at
`c7e820b6`. Nothing here may change without the operator.

| Lever | Week-4 setting | Evidence |
|---|---|---|
| **Main-track book (from 14:05 CDT 09-28)** | **the capped plain-mean optimizer (PMO_X50)** solved on the build's frame inside the union step (`UNION_MAIN=pmo_x50`): K sequential solves, ≤ 7 shared, no player in ≥ half the rows (`UNION_MAIN_CAP=0.5`; L17 09-29: 67%/80%/uncapped HARMFUL; L18 09-29: 40% NEUTRAL, 33%/25% HARMFUL — 50% is the peak), **no DST in ≥ 25%** (`UNION_MAIN_DST_CAP=0.25`); a short solve falls back, named, to the union's mean main | L13 R5: PMO_X50 vs MEAN +27.7% tickets at p89, both seasons, SUPPORTED (`reports/2026-09-28-laptop-l13-result.md`); operator decisions (HANDOFF 14:05 and 14:3x). The DST cap is an untested addition, chosen by the operator |
| Deep-line sleeve source | the union pool's mean selection, **including the PMO_X50 rows** (`UNION_SLEEVE_INCLUDES_MAIN=1`) | operator 14:3x; an untested combination (L13: no clear leader at p99; PMO_X50 +74% in aggregate) |
| Selector (the pool, the fallback main) | **mean**: top-K by simulated projected sum, ≤ 7 shared players (`LIVE_SELECTOR=mean`) | L09: MEAN stands against every satellite challenger; MEAN vs EMAX +13.3% (not confirmed, paired 30–32); L10 replicated +20.8% (`reports/2026-09-28-laptop-l09-result.md`, `…-l10-result.md`) |
| Deep-line contests | paid line ≥ the field's p98, plus the Millionaire (`track_override: tail`) → **tail sleeve, also by mean** (`TAIL_SLEEVE_SELECTOR=mean`), dealt Millionaire first, then by depth | Rehearsed, exact ladders: Week 3 **23** paid vs 20 for all-main; Week 1 **40** vs 31 (Millionaire 27 vs 17). Dealing order alone moves nothing (HANDOFF 10:29 and 10:35 CDT, 09-28) |
| Layout / order | `ENTER_LAYOUT=head`, `ENTER_ORDER=greedy` | `reports/2026-09-24-laptop-head-layout-review.md` |
| Class sleeve | `CLASS_SLEEVE_EVERY=2`: every second boom visit solves inside the class model's shape (QB ≤ $5,500, 2 TE, salary ≥ $49,800, projection between the pre-lock map's p50 and p95) | Week-1 gate: 3.54% of sleeve rows ≥ 193 vs 1.00% for plain boom (`reports/2026-09-28-laptop-class-gates-evidence.md`) |
| Class **selector** | **withdrawn for entry**; a paper arm, re-selected deterministically on Monday from the Sunday run dir | Week 3 30 vs 20, but Week 1 8 vs 31 (fails) |
| Ownership tilt | `MEAN_OWN_TILT=0` | The 156.8 used realized ownership (hindsight); L12 is the out-of-sample check (§7) |
| DST cap | `MEAN_DST_CAP=0.25` (≤ 25% of mean rows on one DST) | Week-3 post-mortem Q5: 98 rows on two DSTs scoring 3 and 7; the cap costs 0.3 simulated points |
| Minimum projection | `LIVE_MIN_PROJ=1.0` (skill players projected under 1 point are dropped) | Week-3 post-mortem Q4b: 399 boom lineups held a non-player |
| Sunday build | **the T-70 build is primary** (projections on the post-inactives pull); the Saturday D12800 is the fallback | reviewer ruling 09-28 |
| T-70 rules (operator decision 2, 07:30 CDT 09-28) | `T70_VACATED_BUMP=1` (the depth-2 backup of an out/doubtful depth-1 starter gets RB/TE +1.6, WR +0.7, other +1.0, net of the cascade); `T70_ACTIVE_Q=1` (no Questionable haircut for a player whose game starts within 90 min and who is not marked out); `ENTER_FLAG_LATE_Q_ONLY=1` (flag only late-game Q). They run in the `project-slate` job alongside its live env (`Q_HAIRCUT=0.80`, `CASCADE_DOUBTFUL=1`, `CASCADE_SKIP_PRICED_CARRIES=1`, `QB_Q_PRIMARY_BACKUP_SCALE=0.20`) | production D1 (HANDOFF 09:05 CDT 09-28); the laptop's replay found the missing `game_start` and fixed it (`reports/lab-handoffs/t70_rules_replay.py`, HANDOFF 08:27 CDT) |
| Sunday dose | proposal `PAID_LEV=0`, `PAID_BOOM=4800` (2,400 sleeve visits); **the laptop sets `dose.env` from Wednesday's full-size timing** | Week-3 gate: ~0.15 s per boom visit → ~12 min + banks |
| Satellite late swap | **PAPER ONLY in Week 4** (operator 2026-09-30, after L22: −2.9% on the armed main book, paired 13–24; was: enters Week 4). Score-based, flat-payout contests only (§5.4) | L11: +11.1% tickets in aggregate, both seasons, but paired 30–32 → NOT SUPPORTED by the frozen rule; the operator's call |

**What is NOT in Week 4:**
- a nonzero ownership tilt, EMAX, P(≥line), coverage or class selection for entry;
- `MAX_PER_GAME=5` (L10: not flip-eligible);
- the late swap for top-heavy contests;
- Fantasy Points ownership as a live input (PREREG-O1 only records it prospectively, Weeks 4–7).

---

## 3. What is running now (2026-09-28, Monday 11:19 CDT)

- **DK loop (from 07:59 CDT 09-29): the laptop's `nfl-host-dk-ingest` user unit**, hourly at about :59. Stop or
  restart it **only** with `systemctl --user stop|restart nfl-host-dk-ingest`. A bare `kill <pid>` does not stop it:
  bash defers the signal while it sits in its hour-long `sleep`, which is how the workstation's loop survived the
  operator's kill until production killed the sleep and the loop together. Never run two loops.
- **Workstation (until 09-29 07:57):** the hourly DK loop, then the only DK salary source. Its last pull was 14:57Z today; group 154078 is
  in the warehouse. It is killed at the cutover, before the laptop unit starts (machine-move §3 step 5). **Never run
  two loops.**
- **Laptop, PREREG-L13** (selectors at p99, the plain-mean optimizer): started 11:06, 72 slate-banks, 24 workers.
  - Output: `~/.cache/laptop-agent/l13`.
  - Frozen checkout: `~/projects/.nfl2-worktrees/laptop-l13-p99-selectors-20260928` @ `5d3aaa9`. Do not commit there
    while it runs.
- **Laptop, MNF live-feed dry run:** `live_dk_points.py` snapshots at 20:30, 21:30 and 23:15 into
  `~/.cache/laptop-agent/live-dry-run-mnf/`. This proves the ESPN feed on a live game before Sunday.
- **Done today:**
  - L12 read, INCONCLUSIVE; production's re-run byte-identical; ledger row written.
  - L11 ledger row.
  - The Week-4 chain fixes (`4df5a5b7`), reviewed and approved by production.
  - The late-swap fixes: flat-payout contests only, a required status snapshot, bare tokens, unknown ladders refused
    (`6c22d379`, `c858d5f3`, `b70dbbc0`, `d4c360a1`).
- **Reminder:** the operator gets the cutover reminder Tuesday 09-29 at 08:57.

---

## 4. The week, day by day

Operator steps are marked **(operator, laptop)**. Everything else is the agent's.

### Tuesday 09-29 — the cutover

0. **The workstation after the cutover:** L06 finishes about 01:00–02:00 Tuesday, and L14 runs after it (a read about
   06:00–08:00). Further workstation panels need a frozen preregistration and must finish by Friday evening. The
   checklist's step 9 ("stop any remaining nfl processes") moves to **Friday 10-02 evening**, after every panel's
   files are pushed.
1. The machine-move checklist, §3, in order:
   - fetch; auth; venvs;
   - switch `~/projects/nfl-predictions` to the integration branch;
   - DK loop: **workstation kill first**, then the laptop unit **(operator, laptop)**;
   - vendor logins **(operator, laptop)**;
   - `week_inputs pull`.
2. **Add one login the checklist lacks (operator, laptop):** `fantasy-points-ownership login --terminal-credentials`,
   then `fantasy-points-ownership verify-login` and `fantasy-points-ownership inspect`.
   - The ownership page lives on `www.fantasypoints.com`, a separate session from the Data Suite.
   - `nfl_raw.fantasy_points_projected_ownership` does **not exist yet**: `collect` has never loaded a row. PREREG-O1's
     Week-4 capture is its first real run, so exercise it before Saturday (Rule 1).
3. **Vendor capture A–E** (production's order, HANDOFF 05:40 CDT 09-28; the operator: "Fix that"):
   - A: cumulative Fantasy Points windows from Week 4, plus Advanced Rushing and cumulative Advanced Passing;
   - B: SIS receiver copula weekly;
   - C: a GCS archive for the SIS team-context CSVs;
   - D: the "N of N paid pages" completeness gate;
   - E: an outcome-blind `--audit-only-fp-families` smoke on the laptop's session.

   **Status 09-28:** A, C and D are merged into integration (`685d8055`…`551334bd`). B (the SIS receiver copula
   weekly, its own frozen protocol `bc30947a…`) is merged too (`182d73df`…`4e399cd0`). Its first live run is
   Wednesday's. **E, after the logins (operator present for the sessions):**
   ```
   nfl-weekly-data run --week 4 --audit-only-route --audit-only-fp-families --skip-matchups --skip-odds --skip-sis-team-context --skip-sis-receiver-copula --no-login-if-needed
   ```
   - Expected: `PAID PAGES: 11 of 11 paid pages captured for Week 4 (16 skipped by --skip-matchups,
     --skip-sis-receiver-copula, --skip-sis-team-context) (audit-only, …)`. The copula pages first run on Wednesday
     inside the weekly run.
   - A failing Route Share import is still fatal and runs first. The per-page fallback is
     `fantasy-points-download run --plan automation/fantasy_points/plans/2026-<family>-cumulative-weekly-v1.json --target-week 4`,
     then `python -m nfl_dfs.ingest.fantasy_points_weekly_2026 <family>-cumulative <run dir> --target-week 4` (add
     `--write` to load).

   **Say by Tuesday 18:00 CT what will not be ready for Wednesday.**
4. **SIS receiver-copula backfill** (operator: "Yes", 12:23 CDT 09-28), on the laptop's SIS session after the logins,
   **before** Wednesday's weekly run, so the Week-4 import can write the defense prior:
   ```
   sis-download verify-login
   sis-download receiver-copula-weekly --target-week 2          # source week 1, 2 submits
   nfl-dfs import-sis-receiver-copula-weekly --input-dir sis/receiver-copula-weekly/2026-w02 --target-week 2           # audit
   nfl-dfs import-sis-receiver-copula-weekly --input-dir sis/receiver-copula-weekly/2026-w02 --target-week 2 --write
   ```
   Repeat with `--target-week 3` (source week 2). Record both runs' manifests (sha256, rows, archive URIs) in HANDOFF.
   Append-once and outcome-blind; nothing reads the rows.
5. **Tuesday night:** post the "will not make Thursday" list (reviewer's order, HANDOFF 09:15 CDT 09-28).

### Wednesday 09-30

1. **~09:30 weekly data run** from the integration checkout, after the logins:
   `nfl-weekly-data run --week 4 --skip-odds --no-login-if-needed`.
   - It must run unattended (Week 3's attended run died at `sis-session`).
   - It must end with **`PAID PAGES: 27 of 27 paid pages captured for Week 4`**:
     - Route Share and Defense PROE for Week 3;
     - 3 live matchups;
     - the 9 cumulative Fantasy Points pages for Weeks 1–3, including the new Advanced Rushing;
     - 11 SIS team-context reports;
     - 2 SIS receiver-copula pages (wide and slot, Week 3).

     The copula steps are new and non-fatal and run last among the SIS steps. Nothing reads their rows, and the
     defense prior is withheld while 2026 Weeks 1–2 are missing. The backfill is the operator's call (4 more SIS
     submits): `sis-download receiver-copula-weekly --target-week 2`, then 3, each followed by
     `nfl-dfs import-sis-receiver-copula-weekly --input-dir … --target-week N --write`.

     Anything less names the missing pages. Re-run the named pages with the per-page recovery, not the whole run. The
     new `fantasy_points_*_cumulative` tables are created by their first append.
   - Needs `GCP_PROJECT=nfl-predictions-503414` in the environment: every archive's bucket derives from it.
   - SIS-only rerun: `nfl-weekly-data run --week 4 --skip-fantasy-points --skip-odds --skip-matchups --no-login-if-needed`.
2. **Rebuild the `project-slate` image from the integration branch**, which carries D1 and the `game_start` fix (§8).
   Then `gcloud run jobs update`, one execution **(operator)**, and the proof lines.
3. **The Week-4 pre-lock smoke on group 154078**, at full size. It needs Week-4 inputs first. On 09-28 the input gate
   read 0 projection rows, no market batch and no TabPFN rows for Week 4, so the operator runs the refresh trio
   (build-features → tabpfn-gen `TABPFN_UPCOMING=2026:4` → project-slate) after the new image is live. The clone is a
   clean detached lab worktree at 54dd512 (created 09-28):
   ```
   git -C ~/projects/.nfl2-worktrees/week4-live-center checkout --detach 826d8de6129eaeefe2235467212cc4cfccb57deb   # done 09-29 (the LAR->LA alias on top of 54dd512)
   ```
   - Measure the lev-0 / boom-4800 / class-sleeve build time; that confirms `chosen-dose.env`.
   - Check the receipt and the audit (`audit_build_levers.py`, `t70_rules_effect`).
   - Then move `week_env.sh`'s `CLONE`/`EXPECT_SHA` defaults to it, with `tests/test_week_env_defaults.py`'s pin and
     lineage assertion.
   - **The publish and swap path with the sleeve's repeated rows (sweep item 2; no rehearsal has run it yet):**
     - on the smoke's union dir, `REQUIRE_AUDIT_PASSED=1 scripts/sunday_after_build.sh once <union dir> smoke`;
     - it must publish (vetting, the emit with repeats across blocks, `ENTER/`, TODAY file, no "STALE INPUTS"),
       and one `sunday_swap.sh ROW:OUT:IN` on a repeated row must re-publish.
     - Use a scratch `OUT`: the smoke is before Saturday, so the window never lets it reach Sunday.
   - **Union checks in the smoke:** the published dir carries `audit_passed` and `config.union`, and there is exactly one
     `process_run` per build. Time T-70 build end → union → published → filled export. Compare the top-144 projected
     sum of the lev-0 pool with the union's (S5).
   - Already checked on 09-28 with placeholder contests: both `check_week_runtime.py` preflights pass on this clone
     (build and watchers; the head layout printed; the class model json + `.sha256`; `chosen-dose.env` 0/4800).
     Export `OUT`/`CLONE`/`EXPECT_SHA` before calling `week_env`: bash `VAR=x week_env` assignments revert when the
     function returns.
4. `$OUT/class_model.json` + `.sha256` from `gs://…/private/week4/class_model_w4_w1w3.json` (sha256 `92cec733…`).
   Regenerate the `.sha256` under the installed name (`sha256sum class_model.json > class_model.json.sha256`).
   `sunday_build_host.sh` exits 1 without both files.

### Thursday 10-01

1. **TNF dry run of the afternoon path** on a **Thursday-to-Monday Classic** slate (operator, 09-28). Not Showdown: the
   format differs from Sunday's, and nothing is swappable after kickoff.
   - The vehicle: the operator's own entry in contest 196186394, Thu–Mon Classic **draft group 154077** (production
     22:03 CDT 09-28).
   - Thursday ~15:00–16:00: a small paper build on that group (the Week-4 configuration, main = pmo_x50) gives the
     frame and banks the tools need. **Give the operator its top lineup** (names, positions, salary) **by ~16:30.** He
     enters it once in a cheap, large-field Thu–Mon tournament before the 19:15 CT kickoff.
   - ~20:30 (mid-game): the operator clicks that contest's Export CSV and says where the file landed.
   - Then the chain below runs on his entry; a real edit upload is his option (the Sunday/Monday players are unlocked).

   The chain:
   - the operator's mid-game Millionaire-style **Export CSV** click. Whether DraftKings serves the export mid-slate is
     **unverified**, and it is the late swap's hard dependency;
   - `live_dk_points.py --date 20261001`, then `dk_status_snapshot.py --group 154077`. Pass the group: with
     `week_env` sourced, the default is Sunday's 154078;
   - `sat_late_swap_live.py --rehearsal --min-field 300`. The Huddle is top-heavy, so the tool skips its row by design;
     to exercise the swap mechanics, pass a scratch copy of its details with the ladder treated as flat (paper only);
   - `apply_swaps.py --no-fresh-dk`;
   - a manual fill of an edit-entries export with `fill_dk_entries.py` (the afternoon upload format has never been
     rehearsed).
2. **Freeze 18:00 CT.** Anything not rehearsed by then stays off. The fail-loud audit and the flag preflight enforce
   it.

### Friday 10-02

1. The operator downloads the **Sunday-main** entries export: exports are per draft group, and the Thu–Mon export
   does not carry Sunday contests. Then:
   - `dk_contest_details.py` on its contest ids;
   - `scripts/contests_from_entries.py --group <Sunday main> --out $OUT/contests.json` (other groups go to
     `.other.json`);
   - set `"track_override": "tail"` on the Millionaire. `contests.json` is never committed or printed.
   - Push it with `scripts/week_inputs.py push --season 2026 --week 4 --contests … --dose …`.
   - Pull it with `… pull --season 2026 --week 4 --out ~/week4-sunday`.
2. `python scripts/dk_contest_details.py --contests $OUT/contests.json --out $OUT/contest-details-<date>.json` (public
   API; exits 2 on any unresolved id).
3. `python scripts/set_contest_tracks.py --contests $OUT/contests.json --details $OUT/contest-details-<date>.json --rule line --write`.
   - **`--rule` defaults to `field`, so pass `line`.**
   - The printout must name the Millionaire as a tail contest; "NONE - is the Millionaire missing…" means the override
     is absent.
   - **Routing (operator's choice, 09-29):** add `--hold-on-main 2378,190` (the funded supersats' field sizes) so those
     deep-line contests take the main book's rows, not the sleeve's. Each held contest prints "held on the main book by
     track_override mean". A size that matches no contest refuses. BOOK_ENTRIES grows with them automatically.
4. First capture of the FP ownership page (O1): `fantasy-points-ownership collect --week 4`.

### Saturday 10-03

1. 09:30 props pull (cloud scheduler); 09:35 props-guard pre-check.
2. **(the laptop agent)** 09:45 the refresh, in order (the agent runs these since 09-29). If the Week-4 rosters are
   not in `rosters_weekly`, run `ingest-nflverse` first: `project-slate` refuses a stale roster receipt, as the
   scheduled 09:30 run did on 09-29:
   - `gcloud run jobs execute build-features … --wait`;
   - `tabpfn-gen … --update-env-vars TABPFN_UPCOMING=2026:4 --wait`;
   - `project-slate … --wait`.

   `arm_week_timers.sh 4` prints the exact lines.
3. ~10:15 proof lines: `reports/lab-handoffs/week3_proof_lines.py`. Then the sets file:
   `PYTHONPATH=src $PROD_PY scripts/ownership_sets.py sets --week 4 --group 154078 --out ~/week4-sunday/ownership_sets.csv`.
   It is required by the preflight even with the tilt at 0, and it is O1's LAG predictor.
   **The ownership term (operator 09-29; reviewer 16c293b7), when armed:**
   - The lag-model file:
     `PYTHONPATH=src $PROD_PY scripts/ownership_sets.py sets --season 2026 --week 4 --group 154078 --lag-features --out ~/week4-sunday/ownership_lag.csv`.
   - Its gate: `$PROD_PY scripts/check_ownership_lag.py ~/week4-sunday/ownership_lag.csv` must print OK (sum ≥ 280).
     Below that, arm with `UNION_MAIN_OWN_TILT=0`. Never rebuild this file on Sunday: a past or stale week collapses.
   - A Saturday LineStar capture (Sunday's fallback):
     `$PROD_PY scripts/linestar_ownership_capture.py --season 2026 --week 4 --out ~/week4-sunday/linestar --label saturday`.
   - Sunday needs nothing by hand. Each union captures LineStar, blends, and solves the main with the term. A refused
     capture keeps Saturday's. A refused blend or term builds the main without it, named in capitals.
4. The FP ownership capture: `fantasy-points-ownership collect --week 4`.
5. **(operator, laptop) arm**, after `chosen-dose.env` holds `CHOSEN_LEV=0` / `CHOSEN_BOOM=4800` (or Wednesday's
   measured boom):
   ```
   GROUP=154078 EXPECT_SHA=826d8de6129eaeefe2235467212cc4cfccb57deb CLONE=$HOME/projects/.nfl2-worktrees/week4-live-center \
   D3200_LEV=0 D3200_BOOM=4800 D800_LEV=0 D800_BOOM=4800 SKIP_UNITS="d6400sat d6400" \
   T70_MIN_PROJ_CT=10:30 T70_PROJECT=1 UNION_SATURDAY_RUN=auto UNION_PMO=0 scripts/arm_week_timers.sh 4 --run
   ```
   **Additions (operator 09-29/09-30):** `UNION_MAIN_OWN_TILT=0.20 UNION_MAIN_OWN_PREDICTOR=tabpfn` (the ownership term
   with the TabPFN predictor on the laptop GPU, armed unconditionally by the operator 09-30 08:0x; the preflight refuses
   without a passing lag file, the lags file, the L23 rows file and a CUDA device; any Sunday failure falls back LOUDLY
   to the blend for that union). `ENTER_SMALL_MAX_SHARED=5` (the small-contest overlap limit, PREREG-L25 SUPPORTED; operator 09-30 "in effect this week";
   week_env's default is 5, so the arm line need not carry it and a hand-run `sunday_swap.sh` checks with the same value;
   `ENTER_SMALL_MAX_SHARED=` turns it off). `UNION_SLEEVE_CAP=0.5` (operator 09-30 20:0x after L19 SUPPORTED; at T = 5 at most 2 sleeve rows per player).
   Conditional: `ENTER_SMALL_OVERLAP_MAX_ENTRIES=10` (only if Thursday's smoke covers it; then the week_env default).
   **The union (operator-authorized 12:2x CDT 09-28; production `025ad2c5`, `57bdc8b7`, `c753be99`):**
   - Each Sunday build (09:10 and T-70) is followed by `union_reselect.py`: the build's pool plus every Saturday D12800
     candidate that survives the build's frame (no OUT/IR/Doubtful/inactive or below-MIN_PROJ player).
   - The union is re-selected by mean on the build's projections and verified and audited like any build.
   - **The watcher publishes only a dir marked `audit_passed`.** With the union on, that means the union dir, or the
     build itself if the host marked `union_failed`.
   - `UNION_PMO` stays 0 unless L13's R5 supports it.
   Run it without `--run` first and read every line. The `week_env` defaults supply `LIVE_SELECTOR=mean`,
   `TAIL_SLEEVE_SELECTOR=mean`, `CLASS_SLEEVE_EVERY=2`, `MEAN_DST_CAP=0.25`, `MEAN_OWN_TILT=0`,
   `LIVE_MIN_PROJ=1.0`, `ENTER_LAYOUT=head`, `ENTER_ORDER=greedy` and the T-70 flags.
6. 10:30 the Saturday D12800 (2560/10240). **It is now a required input: the union's supply.** It takes about 6 h on
   the laptop and must finish, with its sidecars, before Sunday 09:10. If it is missing, the union refuses and the
   Sunday builds publish on their own (lev 0; S5). It is promoted on its own only if `chosen-dose.env` is changed to
   2560/10240.

---

## 5. The Sunday money path (10-04)

### 5.0 The failure order (second review S8, agreed 09-28): what may fail and what stands

1. **The 09:10 book (its union with the Saturday pool) is the floor.** It is uploaded if anything after it fails. The
   union repairs S5's lev-0 supply gap. Still open for the operator: whether the book is scored on Sunday's or
   Saturday's projections (HANDOFF 12:53 CDT 09-28).
2. **The T-70 build replaces it only if its input gate and audit pass.** A refusal is a normal outcome, not an
   incident.
3. **The class sleeve is the first thing to switch off** (`CLASS_SLEEVE_EVERY=0`) if Wednesday's smoke is slow or the
   sleeve's projection band is empty on the Week-4 frame.
4. **R4 runs.** The satellite late swap runs only if Thursday's TNF dry run passed end to end, including the edit
   upload, and only on flat-payout rows (the tool enforces the latter).
5. **No other entry-path change enters this week,** whatever Monday's paper numbers say.

### 5.1 Morning (CT)

| Time | What | Who |
|---|---|---|
| 09:10 | `nfl-week4-d3200-build`: lev 0 / boom 4800 + class sleeve on the 09:03 projections, then **its union with the Saturday pool**. The watcher publishes the union (`audit_passed`) about 09:30. **This is the automatic fallback book**, pre-inactives | timer |
| 09:12 | `nfl-week4-watchers`: after-build (until 11:50), DK entries (until **15:20**), late inactives | timer |
| 10:30 | official inactives | — |
| 10:33 | `nfl-week4-t70-pull`: `nfl-dfs ingest-dk`. The hourly loop pulls at whatever minute it started (the workstation's at :57), so it cannot be relied on for a post-10:30 pull | timer |
| 10:36 | `nfl-week4-t70-project`: `project-slate` with `T70_ACTIVE_Q=1,T70_VACATED_BUMP=1` (about 3 min) | timer (operator-armed) |
| ~10:40 | check that the T-70 batch landed: proof lines, and the receipt columns `t70_active_q`/`t70_vacated_net` on the out starters' backups. Capture the FP ownership page at T-70 (O1) | agent |
| 10:50 | `nfl-week4-t70-build`: lev 0 / boom 4800. **Refuses projections generated before 10:30** (`MIN_PROJ_GENERATED_AT`); a refusal leaves the 09:10 book in ENTER. Then the union (under a minute; written under `.tmp`, renamed when complete) and its `verify_k90` + audit | timer |
| ~11:05 | the watcher publishes the T-70 **union** → `ENTER/` (or the T-70 build if `union_failed`), and refills `DKEntries-FILLED-keepers-first.csv` | watcher |
| ~11:05 | read `TODAY-30-LATEST.md`, the audit, the vetting. Scratch swaps only for DK OUT/IR or the official inactives: `scripts/sunday_swap.sh ROW:OUT_DD:IN_DD …` | agent → operator's go |
| by 11:15 | **upload** the filled export | **operator** |
| 12:00 | lock | — |

If the T-70 build fails, the 09:10 book stands. Apply the morning scratch swaps to it and upload by 11:15. If both
Sunday builds fail, change `chosen-dose.env` to `CHOSEN_LEV=2560 CHOSEN_BOOM=10240` and restart the watcher, or run
`sunday_after_build.sh once <D12800 run dir> <tag>`.

### 5.2 R4, late-game inactives (~13:35–13:55)

```
PYTHONPATH=src python scripts/dk_status_snapshot.py --group 154078            # -> $OUT/dk-status-<utc>.csv
PYTHONPATH=src python scripts/late_inactive_swaps.py --upload $OUT/ENTER/ENTER-all-rows-*-KEEPERS.csv \
    --frame <T-70 run dir>/frame.parquet --snapshot $OUT/dk-status-<utc>.csv --out $OUT/r4-receipt.json
scripts/sunday_swap.sh $(… the last stdout line of the previous command …)
```

- R4 exits 2 on any UNREPAIRED row. Read it; never ignore it.
- The watcher refills the export, and the **operator re-uploads** the affected entries.
- **If the operator entered the cash pilot** (`$OUT/upload-<run tag>-cash-A.csv`, production `8b3a326f`): those
  entries are outside the bundle, so `sunday_swap.sh` cannot reach them. Run R4 on the same snapshot to list their
  repairs:
  `late_inactive_swaps.py --upload $OUT/upload-<run tag>-cash-A.csv --frame <run dir>/frame.parquet --snapshot <snap> --out $OUT/r4-cash.json`
  (the same emitter's format: a slot header, then draftable ids). The operator applies them by hand on DraftKings.
- Do not use `sunday_live_relayout.sh --dry-run` for the snapshot. It refuses under `greedy` order and on a swapped
  bundle.

### 5.3 The satellite late swap (~14:30–15:05) — **PAPER ONLY in Week 4** (operator, 2026-09-30)

**Operator decision 2026-09-30 (after L22's co-report: the swap on the armed main book read −2.9% tickets89, paired
13–24):** the late swap does **not** edit entered lineups in Week 4. The steps below run **with `--rehearsal`, the
output to a scratch receipt, and nothing passed to `sunday_swap.sh`**; there is no re-upload. Monday grades the paper
swaps against the realized scores. Everything else in §5 is unchanged; the R4 inactives replacements (§5.2) still run.


0. **~12:05 (after the lock), re-fetch the ladders:** `dk_contest_details.py --contests $OUT/contests.json --out
   $OUT/contest-details-postlock.json`. The late swap refuses pre-lock ("Upcoming") details, because entries and paid
   places are only final after the lock. Pass this file as `--details` below.
1. ~14:30 **(operator)** the Millionaire **Export CSV** click. The script refuses (exit 3) without it, and the
   entries stand.
2. ~14:35 `live_dk_points.py --date 20261004 --out $OUT/live.json` (ESPN, ≤ 15 min old) and a fresh
   `dk_status_snapshot.py` (≤ 30 min old).
3. ~14:40:
   ```
   PYTHONPATH=$CLONE/src:src python scripts/sat_late_swap_live.py --bundle $OUT/ENTER --run-dir <T-70 run dir> \
       --details $OUT/contest-details-<date>.json --live-points $OUT/live.json --field-export <milly export>.csv \
       --snapshot $OUT/dk-status-<utc>.csv --out $OUT/late-swap-receipt.json
   scripts/sunday_swap.sh $(… its last stdout line …)
   ```
4. The watcher refills; the **operator re-uploads before 15:05**.

### 5.4 What the late swap does and does not do

- **What it does, per book row:** it re-chooses the late-game players to maximize expected tickets = Σ over the row's
  contests of P(final ≥ that contest's live line).
- **Live line:**
  - the Millionaire field's conditional final-score quantile at the contest's paid share;
  - plus a per-type strength offset (`DEFAULT_OFFSETS`, Week 3). **The offsets are refit each Monday.**
- **Only flat-payout contests** (every paid place wins the same ticket) are swapped. A row that also sits in a
  top-heavy contest (the Millionaire, the FFWC cash qualifier) stays as entered, receipted
  `skipped: in a top-heavy contest`.
- **Refusals** (exit 3, no swaps, the entries stand):
  - a ladder with no positive value (unknown);
  - a stale live feed or snapshot, or a snapshot covering < 90% of the frame;
  - a Millionaire export matching < 95% of slots.
- **Out players:** a late player who is out scores 0 in every world and is never swapped in.
- **Legality:** tokens are ordered so every intermediate lineup is legal for `apply_swaps.py`, which re-checks locks,
  the fresh DK feed and the roster.
- **Evidence:** L11 NOT SUPPORTED by the frozen rule (paired 30–32), +11.1% tickets in aggregate. The Week-3 rehearsal
  cost the one real ticket (HANDOFF 08:52 CDT 09-28). The operator chose to enter it anyway (09:04 CDT).

---

## 6. Monday/Tuesday settlement and the paper arms

1. **Standings:**
   - `$PROD_PY scripts/dk_standings_links.py --contests ~/week4-sunday/contests.json --out ~/week4-sunday/standings-links.html`;
   - the operator exports each contest by hand (the automated downloader is refused);
   - per contest, `python -m nfl_dfs.cli capture-dk-standings <file> --season 2026 --week 4 --contest-id <id>
     --contest-name "<label>" --expected-entries <field size> --confirm-settled --confirm-full-field`, first without
     `--apply`, then with it. The validator fix `8a545d64` handles identical-share rows.
   - **One convention (2026-09-29 sweep A5): `--contest-name` is the contest's `contests.json` LABEL** (Week 3 did the
     same: `milly20`, `sat13mega`, …), never the DK display name, so every Monday tool finds the same names. Week 4's
     labels come from `contests_from_entries.py` (the private `~/week4-sunday/contests.json`): `milly` = the
     Millionaire **196151357**; `sat` = the $555 satellite 196170540; `ffwc` = the FFWC qualifier satellite 196170762;
     `supersat`, `supersat2`, `supersat3` = the 23-entry 4x SUPERSats 196170703–705; `supersat4`–`supersat7` = the
     2,378-entry SUPERSats 196170706–709; `supersat8`–`supersat11` = the 594-entry 196170710–713; `supersat12`,
     `supersat13` = the 198-entry 196170714–715; `supersat14`, `supersat15` = the 118-entry 196170716–717. Read the
     label from the file, do not retype it. The scorers take the Millionaire by id: `MILLY_CONTEST_ID=196151357
     bash reports/lab-handoffs/monday_laptop_scoring.sh 4`, `cash_shadow_paper.py score … --milly-contest-id 196151357`,
     `rehearsal_two_track.py --contests ~/week4-sunday/contests.json --milly-contest-id 196151357 --details <settled>`.
2. `dk_contest_details.py` again, for the settled states.
3. **Scoring:**
   - `book_vs_field_scoreboard.py <RUN_DIR> 2026 4 <CONTEST_ID>`;
   - `bash reports/lab-handoffs/monday_laptop_scoring.sh 4` (`MILLY_CONTEST_ID` overrides the lookup);
   - `rehearsal_two_track.py --details <settled details>` for tickets at every contest's real line.
4. **The class paper arm** is a deterministic re-selection from the frozen Sunday run dir:
   `rehearsal_two_track.py --run-dir <Sunday T-70 run dir> --main-selector class --tail-selector class --class-model class_model_w4_w1w3.json …`,
   beside the entered `--main-selector mean --tail-selector mean`, at the exact ladders. It is never entered.
5. **The cash/double-up paper shadows** (production `2fdcc81c`; built by the chain from the final run dir after its
   `audit_passed` marker, never entered): `cash_shadow_paper.py score $OUT/cash-shadow-w04-A-<run tag> 2026 4`, and the
   same for `-B-`, beside the entered book's double-up share. Any `$OUT/cash-shadow-failures.txt` line goes into
   HANDOFF.
6. **Refits:**
   - the class model on Weeks 1, 3 and 4 (not the Week-2 defect week): `scripts/fit_field_class_model.py --weeks
     WEEK:CID:DG:LOCK … --map-weeks 1,3,4`, sha256-receipted, stored under `gs://…/private/week5/`;
   - the late-swap offsets: `scripts/fit_late_swap_offsets.py --layout <entered bundle>/ENTER-layout.txt --details
     <settled details> --season 2026 --week 4 --milly-contest-id <id> --out offsets-w04.json`. It computes each flat
     satellite's real line among the OTHER entrants (ours removed) minus the Millionaire's final quantile at the same
     share. Sunday passes the file with `--offsets`. On Week 3 it reproduces the defaults, except sat20 +5.8, not +6.5:
     our wins had set those lines.
7. **O1:** the Week-4 Spearman for FP (T-70 capture) and LAG (Saturday `pred_own`) against the Millionaire's realized
   ownership, counted from `contest_entries`. Record it; the decision rule applies once, after Week 7.
8. The post-mortem. Archive the entered bundle to `gs://…/private/handover/week4/enter-bundles/`.

---

## 7. Lab operations on the laptop

The operator ruled out heavy Cloud Run, so every cohort runs locally.

**The cycle for each preregistration:**
1. `PREREG-LNN.md` + `experiments/lNN_*.py` + `scripts/lNN_drive.py` + the frozen reader `scripts/lNN_report.py`, on a
   `laptop/lNN-…` branch.
2. Two smokes at 5%: `--mechanics-only` and the plain full-path smoke. Their values are not read.
3. Freeze (commit + push).
4. Run from a clean checkout of the frozen commit.
5. Read once with the frozen reader.
6. Result files and the reader output go on `laptop/lNN-results-…`. `results/` is gitignored, so use `git add -f`.
7. The result report on the integration branch, with the reader output verbatim.
8. A second agent re-runs the reader byte-identical.
9. The ledger row on lab `laptop/ledger-laptop-rows-20260924`.

**Open cohorts:**

| Cohort | What | Status | Decision it feeds |
|---|---|---|---|
| **L13** | EMAX / MEAN / plain-mean optimizer / PMO with a 50% exposure cap at p99 and p99.8; R5 (PMO vs MEAN at p89) | running since 11:06 09-28 | the deep-line sleeve selector; the operator's open contest and stake decision |
| **O1** | Fantasy Points ownership projections vs the lag model, prospective Weeks 4–7 | approved 06:05 CDT 09-28; first capture Week 4 | whether FP ownership replaces the lag model's labels (L05 cell C) |

**Closed today:**
- L11 (late swap): NOT SUPPORTED, entered by the operator's decision.
- L12 (tilt): INCONCLUSIVE; the tilt stays at 0.
- Both have ledger rows.

---

## 8. Production Cloud Build / Cloud Run

**Deploy (Wednesday):** from a clean checkout of the integration commit:
```
gcloud builds submit --config cloudbuild.week1-live.yaml --substitutions=_CODE_SHA=<full sha>,_IMAGE=<tag>
gcloud run jobs update project-slate --region us-central1 --image <repo>@sha256:<digest>
```
- Then one execution **(operator)** and the proof lines:
  `python reports/lab-handoffs/week3_proof_lines.py --execution <name> --digest sha256:<digest>`, plus
  `week3_phantom_scan.py`.
- The last deploy was 09-23 (`e457560b` → build `3a4729ac`). The effective-policy inventory v15 blocker is cleared
  (production, 09:42 CDT 09-28).
- The hourly `s-project-su` runs keep the T-70 rules off. Only the 10:36 Sunday execution turns them on.

**Refusals:** `gcloud run jobs execute` on the production project is refused to the assistant. The operator runs it, or
arms it as a timer (`T70_PROJECT=1`).

---

## 9. Open defects and risks

| # | Risk | Status / mitigation |
|---|---|---|
| 1 | **The mid-slate Millionaire export is unverified**, and the late swap depends on it | Thursday TNF dry run; without it the script refuses and the entries stand |
| 2 | **The afternoon edit upload** (fill of an edit-entries export after lock) has never been rehearsed on this chain | Thursday dry run; the watcher now runs to 15:20 CT |
| 3 | **A new generator (lev 0 + class sleeve) and a new selector (mean) on the laptop's first week as host.** S5: on Week 3 a lev-0 pool's top-144 projects 2.4–4.6 below Saturday's (HANDOFF 09-28) | Wednesday's full-size smoke; the audit and preflight fail closed; the 09:10 book is an automatic fallback |
| 4 | **The FP ownership `collect` has never loaded a row**; it needs a second FP login | Tuesday login + `inspect`; the first `collect` on Friday |
| 5 | **Vendor capture:** A–D merged 09-28, untested live | Tuesday smoke (E); Wednesday's `PAID PAGES` line (27 of 27) |
| 6 | **Contest selection and stake: TBD** (operator) | L13 and the review's §2 table are the inputs |
| 7 | `GCP_PROJECT` in the user manager is lost on reboot | now on every unit (`4df5a5b7`); the hourly loop unit sets its own |
| 8 | The `--run` preflight (`run_week_build.sh --check`) does not run the input gate | by design (inputs are not ready at arm time); the gate runs in every build |
| 9 | The cash shadows are not in the chain | paper only; Monday |
| 10 | The stored-ownership gap for identical-share slot rows (HANDOFF 19:35 CDT 09-27) | ownership is counted from `contest_entries` lineups (`field_ownership_sql`) |
| 11 | `arm()` needs bash namerefs (≥ 4.3) | the laptop has bash 5.3 |
| 12 | **The production checkout must stay clean and unchanged from arming (Saturday) until Sunday 15:30.** Every unit re-runs `check_week_runtime.py`, which refuses a dirty `~/projects/nfl-predictions`, and bash reads scripts lazily | no `git pull`, edits or untracked files there over the weekend; work in a worktree |
| 13 | The proof script's `DEPLOYED` digest constant is Week 3's | pass `--digest sha256:<Wednesday's digest>` on every proof run after the redeploy |
| 14 | **Sweep 2026-09-29:** four defects that would have stopped Sunday, found and fixed or assigned: the T-70 audit, the repeated rows, `GROUP` under systemd, the Rams `LAR`/`LA` alias | HANDOFF 09-29; production owns the audit, the repeats, vet sort, watcher filters, the Saturday self-union and the freshness sweep |

---

## 9a. After a laptop reboot, a WSL restart, or a VS Code/agent restart

What survives:
- git: everything is pushed;
- the private bucket;
- `~/week4-sunday/` (contests, details, class model);
- the vendor browser profiles (the logins);
- `.env` and the gcloud auth;
- Cloud Run executions already started (they run server-side).

What does NOT survive, and the recovery:
1. **The DK salary loop pauses until WSL starts again.** The unit is enabled, so it restarts when the user session
   starts. After any reboot: open the Ubuntu (WSL) terminal, then `systemctl --user is-active nfl-host-dk-ingest`
   (expect `active`) and `journalctl --user -u nfl-host-dk-ingest -n 5`. Recommended once (operator, needs sudo):
   `sudo loginctl enable-linger erich`, so the user services start with WSL rather than with a login shell.
2. **The Sunday timers are transient** (`systemd-run --on-calendar`): **a reboot or WSL restart after Saturday's
   arming deletes them all.** After any restart between arming and Sunday 12:00:
   - check `systemctl --user list-timers --all | grep nfl-week4`;
   - if they are gone, re-run the same arm line (dry-run first, then `--run`);
   - skip the Saturday D12800 if its run dir already exists: add `d12800sat` to `SKIP_UNITS`.
   - Keep a WSL terminal open over the weekend so the VM stays up.
3. **The agent's own reminders are session-only.** A new session reads `HANDOFF.md` (the newest entry lists them) and
   this document's §4, and re-creates them.
4. **Session scratch files** live under `/tmp`. The 09-29 copy is in `~/.cache/laptop-agent/scratch-archive-20260929/`
   (private; it contains a DK export copy, never committed).

## 10. File index (most used)

| File | What |
|---|---|
| `scripts/week_env.sh` | the single source of week facts and Week-4 defaults (pin, selectors, T-70 flags, `ENTRIES_END_UTC`) |
| `scripts/arm_week_timers.sh` | prints/arms the Sunday timers (`SKIP_UNITS`, `D*_LEV/BOOM`, `T70_MIN_PROJ_CT`, `T70_PROJECT`) |
| `scripts/run_week_build.sh`, `scripts/sunday_build_host.sh` | the timer build entrypoint (preflight → input gate → build) |
| `scripts/run_week_watchers.sh`, `sunday_after_build.sh`, `sunday_watch_dk_entries.sh`, `sunday_watch_late_inactives.py` | the watchers |
| `scripts/check_build_inputs.py`, `src/nfl_dfs/inference/build_inputs.py` | the input gate (`--min-generated-at`) |
| `scripts/sunday_swap.sh`, `scripts/apply_swaps.py`, `scripts/relayout_enter.sh` | swaps on the frozen row→contest map |
| `scripts/dk_status_snapshot.py` | the afternoon `id,status,game_start` snapshot |
| `scripts/late_inactive_swaps.py` | R4 |
| `scripts/sat_late_swap_live.py`, `scripts/live_dk_points.py` | the satellite late swap and its ESPN feed |
| `scripts/dk_contest_details.py`, `scripts/set_contest_tracks.py` | Friday ladders and tracks |
| `scripts/week_inputs.py` | push/pull `contests.json` + `chosen-dose.env` (private bucket) |
| `scripts/dk_standings_links.py`, `nfl_dfs.cli capture-dk-standings` | Monday standings |
| `scripts/book_vs_field_scoreboard.py`, `reports/lab-handoffs/monday_laptop_scoring.sh`, `reports/lab-handoffs/rehearsal_two_track.py` | Monday scoring and rehearsals |
| `scripts/fit_field_class_model.py` | the Monday class-model refit |
| `scripts/audit_build_levers.py` | the fail-loud build audit |
| `reports/lab-handoffs/t70_rules_replay.py` | the T-70 rules replay (writes nothing) |
| `src/nfl_dfs/ops/fantasy_points_ownership.py` (`fantasy-points-ownership`) | the FP ownership capture (O1) |
| lab `src/nfl2/two_track.py`, `class_selector.py`, `sat_late_swap.py`, `scripts/live_week.py` | the Week-4 lab code at 54dd512 |
