# Monday 2026-09-21 command sheet (Week-2 settlement, Week-3 gates)

## 1. Operator: exports (DraftKings web, into Windows Downloads, as in Week 1)

1. Contest standings CSV for every entered contest (12 contests; the Millionaire, Flea Flicker, Huddle, Nickel, Pylon,
   Satellite, the three $1/$0.25 supersatellites, the two $25 supersatellites, the FFWC qualifier).
2. Contest entry history CSV.
3. Tell the assistant the files are in Downloads. They stay under `/home/erich/week2-sunday/ENTERED/`; never in a
   repository or handoff package.

## 2. Assistant: settlement (in this order; each step prints and stops on mismatch)

1. `nfl-dfs capture-dk-standings` validation on the exports (expected entries per contest vs contests.json), then the
   explicit settlement/full-field confirmations, then `--apply` (append-only into `nfl_raw.contest_entries` /
   `contest_ownership`).
2. Confirm every Week-2 game is final by the settlement rule (schedules + last pbp row "end game").
3. `scripts/week3_shadow_outcomes.py --run <run dir> --season 2026 --week 2 --out <OUT>/outcomes-w02
   --i-confirm-outcomes-released --settlement-receipt <path>` (the builder on the labs' wiring branch, once merged), then
   `scripts/week3_shadow_reader.py` on the entered book and the pre-outcome shadow books listed in the evidence record.
4. Accepted proper-score reader (`review/2026-09-prospective-proper-score` @ 1c95dd68) on the served projections and
   the simulator components; fill the Realized table of `2026-09-21-week2-evidence-record.md` exactly once.
5. PREREG-099 host-bank read remains CLOSED (bank 990 read 2026-09-18; bank 991 deliberately unread pending the
   amendment-5 reader decision, which is the operator's).

### 2a. Week-2 standings capture: what was found on Sunday evening (2026-09-20, workstation)

The operator downloaded all 12 contest standings on Sunday evening; the zips and their CSVs are under
`/home/erich/week2-sunday/ENTERED/standings/` (raw exports stay out of git). Findings:

- **The `nfl-dfs` CLI in the operational worktree runs pre-2026-09-14 capture code** (this worktree's venv is an
  editable install of `production/test-lanes-and-factorial-drift-20260911`); it rejects all 12 files on blank-lineup
  counting, single-precision score ties and the classic-mass check. The laptop's 2026-09-14 hardening (blank-lineup
  rows counted toward the field, ranks reproduced from 2-dp points, chunked archive upload) is on `origin/main` and on
  the wiring tip `5f8f61a5`. **Run the capture from a main-tip checkout**, e.g. `PYTHONPATH=<main-tip>/src python -m
  nfl_dfs.cli capture-dk-standings ...`.
- With the main-tip code (`handoffs/receipts/2026-09-21-week2-post-mortem/capture-validate-main-tip.log` on the reply
  branch): **6 of 12 validate** (195660198, 195660199, 195660200, 195660202 supersats; 195661365 Nickel; 195661380
  Pylon). **6 fail** on DraftKings' own ownership summary, not on the entry block:
  - Millionaire 195648007, Flea 195661344, Huddle 195661326, supersat 195660201: `pct_mismatch` on players owned by
    0.01-0.05% of the field (e.g. Millionaire "Mike Washington Jr." 0.04% derived from 69 lineups vs 0.02% in DK's
    summary = 31 entries' worth; Huddle Turpin/Iosivas/Moreau; Flea Spann-Ford/Mitchell). DK's summary shows roughly
    half the lineup-derived share for these near-zero players; the 09-14 tolerance (<= 2 entries' worth AND < 1%) is
    too tight for large fields.
  - 68-entry satellite 195660061 and 59-entry FFWC qualifier 195660229: `ownership mass 895.43 / 894.52 vs 900` with
    zero blank lineups and zero empty slots; DK's summary is short by exactly one entry for several players held by two
    entries (1.47% shown vs 2.94% derived; Goedert 3.39 vs 6.78). Same phenomenon as the Week-1 qualifier, but above the
    1% clause.
  - Proposed tolerance (laptop owns `ownership_import.py`): express both checks in entries, not percent: per-player gap
    <= max(2 entries, 50% of the derived share) when the derived share is below 0.1% of the field, and <= 2 entries'
    worth at any level; mass gap <= 6 entries' worth of a roster slot. Record every tolerated gap in the receipt as
    today. Do not edit the CSVs.
- Expected entries per contest = the export's entry rows including blank lineups (Millionaire 172,761 with 69 blank;
  Flea 83,234 with 34; Huddle 23,781 with 23; Pylon 15,854 with 16; Nickel 9,512; supersats 2,378 / 2,378 / 594 x 3;
  satellite 68; FFWC 59). Check them against the DK contest pages before `--confirm-full-field`.
- Apply only after the DK contest page shows the contest completed after scoring review (Monday). Commands for the six
  that validate today (season 2026, week 2; names exactly as in the entries export):

```bash
MT=<main-tip checkout>; E=/home/erich/week2-sunday/ENTERED/standings
for spec in "195660198|NFL SUPERSat to \$20 NFL Fantasy Football Millionaire [25x]|2378" \
            "195660199|NFL SUPERSat to \$20 NFL Fantasy Football Millionaire [25x]|2378" \
            "195660200|NFL SUPERSat to \$20 NFL Fantasy Football Millionaire [25x]|594" \
            "195660202|NFL SUPERSat to \$20 NFL Fantasy Football Millionaire [25x]|594" \
            "195661365|NFL \$40K Nickel [5 Entry Max]|9512" \
            "195661380|NFL \$40K Pylon [Single Entry]|15854"; do
  IFS='|' read -r cid name n <<< "$spec"
  PYTHONPATH=$MT/src python -m nfl_dfs.cli capture-dk-standings $E/contest-standings-$cid.csv --season 2026 --week 2 \
    --contest-id $cid --contest-name "$name" --expected-entries $n --confirm-settled --confirm-full-field --apply
done
```

- The remaining six (Millionaire, Flea, Huddle, supersat 195660201, satellite, FFWC) wait for the tolerance change;
  the Millionaire and Flea are the two that matter for field calibration, so this is the first Monday item for the
  laptop.
- Winnings: the standings export carries no payout column. Export **My Contests -> History -> Export Contest History**
  for the fees-vs-winnings line of the evidence record (fees are $246.00 over 97 entries from the entries export).

## 3. Operator: the cloud commands the assistant is not permitted to run (Week 3 = first graded Route Share week)

The two Route Share jobs still carry `N_BOOM=28` (read-only describe 2026-09-20) against the adopted boom-first policy;
their four schedulers are PAUSED. Resume only after the update, and only on Monday or later (never before Week-2
settlement):

    gcloud run jobs update shadow-k1-roleunion --project nfl-predictions-503414 --region us-central1 --update-env-vars N_BOOM=160,N_LEV=40
    gcloud run jobs update shadow-k1-route-roleunion --project nfl-predictions-503414 --region us-central1 --update-env-vars N_BOOM=160,N_LEV=40
    gcloud scheduler jobs resume s-shadow-k1-roleunion-early --project nfl-predictions-503414 --location us-central1
    gcloud scheduler jobs resume s-shadow-k1-roleunion-late --project nfl-predictions-503414 --location us-central1
    gcloud scheduler jobs resume s-shadow-k1-route-roleunion-early --project nfl-predictions-503414 --location us-central1
    gcloud scheduler jobs resume s-shadow-k1-route-roleunion-late --project nfl-predictions-503414 --location us-central1

Then the assistant runs `scripts/check_prospective_gates.py --week 3` and expects the three `fp-route-share-2026` FAILs
to clear. The schedulers fire Sunday 10:20 and 11:10 CT (control and treatment, early and late snapshots).

SIS pass-tail pair (`s-shadow-sis-pass-tail-paired` Sun 06:00, `s-tabpfn-sis-pass-tail-control` Thu 09:15,
`s-tabpfn-sis-pass-tail-treatment` Thu 09:20; all PAUSED): resume only after the gate document
`2026-09-21-sis-pass-tail-2026-prospective-gate.md` is accepted by the lab and registered in the checker, and before
the Thursday of the first week whose caches the shadow needs (first target week 5; the four-week context means the
Thursday caches must exist from Week 1 of the context window, so the operator decision is due by Thursday 2026-09-24
if the caches cannot be backfilled; the lab confirms which).

    gcloud scheduler jobs resume s-tabpfn-sis-pass-tail-control --project nfl-predictions-503414 --location us-central1
    gcloud scheduler jobs resume s-tabpfn-sis-pass-tail-treatment --project nfl-predictions-503414 --location us-central1
    gcloud scheduler jobs resume s-shadow-sis-pass-tail-paired --project nfl-predictions-503414 --location us-central1

## 4. Week-3 inputs due before Saturday 2026-09-26 10:30 CT (operator)

`/home/erich/week3-sunday/contests.json` (real reservations), `/home/erich/week3-sunday/chosen-dose.env`, the approved
clean Week-3 lab release (export `CLONE`/`EXPECT_SHA`), the Wednesday vendor run (`nfl-weekly-data`), Saturday 09:30 CT
props pull then `build-features` -> `tabpfn-gen` (`TABPFN_UPCOMING=2026:3`) -> `project-slate`, and the three enable
decisions (`PROMOTE_FIRST_ENTRY`, `RUN_WEEK3_SHADOW`, `HOST_INGEST`). `arm_week_timers.sh 3 --run` preflights all of it.
