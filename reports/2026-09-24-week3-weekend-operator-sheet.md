# Week 3 weekend — the operator's commands (Sat 09-26 / Sun 09-27 / Mon 09-28)

Written 2026-09-24 by production for the operator. **Final entries (operator, 2026-09-25): 44 contests, 202 entries** — adds the $20 Millionaire (row 1) and three $13 satellites to a $4444 MEGA Millionaire (rows 1, 2, 3). The Week-3 changes since the Week-2 sheet:
- the **head** entry layout with the **fewest-LOW** order;
- **clean protected ranks** (the top rows and every single-entry contest);
- a **live-status re-layout** after the Sunday inactives (refinement 1, on your go);
- **frozen-map swaps**;
- two **paper** arms (refinement 2's capped book, and the R1 comparison), which are never uploaded.

Every command runs in the integration checkout:

    cd /home/erich/projects/.nfl-predictions-worktrees/week3-readiness-20260921

## Saturday 09-26

| CT | who | what |
|---|---|---|
| 09:30 | scheduler | props pull (`s-props`), automatic |
| **09:45** | **you** | the projection refresh, in this order: the three lines in the box below |
| **09:50** | assistant (you, if no session is running) | stop the L05 replay if it is still running, so the build has the CPU: `kill -- -$(ps -o pgid= -p $(cat /home/erich/l05-panel/drive.pid) | tr -d ' ')`. Finished slates are kept |
| ~10:15 | assistant | checks that the `project-slate` log says `market blend source: props` and runs the proof lines (`reports/lab-handoffs/week3_proof_lines.py`) |
| ~10:15 | you or assistant | the ownership sets file (below) |
| **before 10:30** | **you** | arm the timers (below) |
| 10:30 → ~20:30 | timers | the D12800 build (the entry); the D6400 fallback at 10:35 |
| ~10:30 | assistant | Kalshi snapshot (R5, capture only): `scripts/kalshi_capture.py --season 2026 --week 3 --label sat-build --out ~/week3-sunday/kalshi --upload`. If the create-once upload is refused by the session's safety check, it captures locally and the operator runs the upload line |
| evening | assistant | reads the TODAY file, the exposure sheet and the paper bundles; tells you what to check |
| evening, before lock | assistant | the two paper cash shadows from the D12800 paid run dir (entered nowhere): arm A `PYTHONPATH=$CLONE/src:$PROD/src $LAB_PY reports/lab-handoffs/cash_shadow_paper.py build <run dir> $OUT/cash-shadow-w03-A --n 20`; arm B (the L03 market conversion) from `/home/erich/projects/.nfl-predictions-worktrees/cash-arm-b-5fdefadc`: `... cash_shadow_paper.py build-b <run dir> $OUT/cash-shadow-w03-B --n 20` |

**09:45 refresh:**

    gcloud run jobs execute build-features --project nfl-predictions-503414 --region us-central1 --wait
    gcloud run jobs execute tabpfn-gen --project nfl-predictions-503414 --region us-central1 --update-env-vars TABPFN_UPCOMING=2026:3 --wait
    gcloud run jobs execute project-slate --project nfl-predictions-503414 --region us-central1 --wait

**Sets file** (the fewest-LOW order reads it; the arming preflight refuses without it):

    PYTHONPATH=src /home/erich/projects/nfl-predictions/.venv/bin/python scripts/ownership_sets.py sets --week 3 --group 153769 --out /home/erich/week3-sunday/ownership_sets.csv

**Arm** (the preflight prints every contest's ranks: check that the wildcats show 1-2 / 3-4 and the nineteen sat20s show
ranks 1 to 19, one each):

    ENTER_LAYOUT=head ENTER_ORDER=fewest-low OWNERSHIP_SETS=/home/erich/week3-sunday/ownership_sets.csv \
      PROMOTE_FIRST_ENTRY=1 RUN_WEEK3_SHADOW=1 scripts/arm_week_timers.sh 3 --run

- `PROMOTE_FIRST_ENTRY=1` is the Week-2 mean promotion (row 1 becomes the highest-mean clean row among the first 30).
  Use 0 to skip it.
- `RUN_WEEK3_SHADOW=1` is the selection-only shadow on the Saturday D12800 build: paper only, never uploaded.
- `HOST_INGEST` stays unset, because the host DraftKings loop is already running.
- **FLEX latest starter (2026-09-25):** the lab pin is now `65305f5a`, and `week_env` defaults `LIVE_FLEX_LATEST=1`, so every lineup's FLEX holds its position group's latest starter (rehearsed: 144/144, full path OK, post-lock FLEX swap OK). Rollback: add `LIVE_FLEX_LATEST=0` to the arm line.

## Sunday 09-27

| CT | who | what |
|---|---|---|
| 09:12 | timer | watchers start. Assistant checks that all three processes are up (the 09-20 lesson) |
| **10:30** | NFL | early-game inactives |
| ~10:35 | assistant | `scripts/sunday_live_relayout.sh --dry-run`: DK status snapshot, and which rows move into or out of the protected ranks |
| ~10:40 | **your go** | assistant publishes `scripts/sunday_live_relayout.sh`. It must run **before any swap**, and refuses after one |
| ~10:45 | assistant, on your confirmation of each OUT | `scripts/sunday_swap.sh ROW:OUT_DD:IN_DD [...]` per scratch. Only confirmed OUT/IR is removed; a Questionable player who is active stays |
| ~10:50 | assistant | Kalshi snapshot, `--label t70` |
| **by 11:15** | **you** | upload `DKEntries-FILLED-keepers-first.csv` (the watcher refills it after every publish) in the DraftKings site |
| after the upload | assistant | R1(c) paper shadow (never uploaded): `scripts/r1c_sunday_reselect.py --saturday-run <D12800 run> --t70-run <T-70 run> --k 144 --out $OUT/paper-r1c --dk-status $OUT/dk-status-<utc>.csv`, then `scripts/paper_layout_capped_book.py --capped-book $OUT/paper-r1c/r1c_book.csv --run-dir <T-70 run> ... --out $OUT/paper-r1c/bundle` |
| ~13:35 / ~13:55 | NFL | late-game inactives (about 90 minutes before the 15:05 / 15:25 kickoffs) |
| then | assistant + you | `scripts/sunday_swap.sh` for late scratches. Swaps after the noon lock are allowed only for players whose game has not started; the tool refuses the rest. **Please be reachable.** |
| after 12:00 | assistant | L06 (qbvar) panel on this machine: clean detached clone at nfl2 `a476862c`; the gate `experiments/l06_qbvar_replay.py --bank 9006 --season 2023 --week 1 --scale 0.05 --mechanics-only` must give `frame_sha256 a0d2a373…2854`, 160/160, 0 infeasible; then `scripts/l06_drive.py --banks 1150,1151,1152,1153 --workers 14 --out ~/l06-panel/out` (~32 h) |

Nothing is ever uploaded from `paper-r2-*` or `paper-r1` directories (they carry a PAPER-ONLY marker). If the live
re-layout or a swap fails, `ENTER/` is unchanged and the previous bundle stays the upload.

## Monday 09-28

- **You:** download every entered contest's full standings and the contest entry-history export into
  `/home/erich/week3-sunday/ENTERED/standings/` (DraftKings purges them after about 4 days).
- **Assistant:** loads them (`capture-dk-standings`), runs the scoreboard, posts the Monday inputs for the laptop's paper
  scoring by 12:00, and writes the week's evidence record. The inputs are the entered bundle, the R1 and R2 paper bundles
  and the run frame.
- **Laptop:** the paper triple, the SLEEVE_L2 arm, and the R1/R2 bundles scored per contest type; the Route read; the L05 read.

## Deadlines that are not this weekend

- **Tue 09-29:** the laptop cutover (`reports/2026-09-24-production-moves-to-the-laptop.md` §3). The DK loop moves first.
- **Wed 10-07:** resume the three SIS pass-tail schedulers after the Week-5 SIS acquisition
  (`reports/2026-09-22-sis-pass-tail-2026-pass-bar.md`; Weeks 3–4 are deliberate no-runs).
