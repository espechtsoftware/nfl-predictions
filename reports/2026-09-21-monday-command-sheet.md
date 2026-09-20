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
