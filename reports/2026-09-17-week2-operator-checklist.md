# Week 2 — the operator's own steps (2026-09-17)

Everything else is automated or done by the assistant. These are the steps only you can do, in order, with the exact
commands. Times are Central. All commands run in the WSL terminal unless marked Windows.

## Today (Thursday) — three commands, in this order (found 2026-09-17 10:30Z; do this first)

Both Week-2 rehearsal builds ran on fallbacks, not on the production law: (a) there are **no production projections for
Week 2 yet** — `project-slate` runs only Tuesday and Sunday morning, and Tuesday's run failed because Cloud Run could not
pull the DraftKings pool (defect 18) — so the builds centred on the lab's own blend (receipt: `production_rows 0`; Week
1's entered build had 465); (b) the TabPFN marginals cache holds Week 1 only, so the simulator fell back to empirical
marginals. Week 1's entered book had neither problem. The fix is the same three commands as the Saturday refresh; run
them now so the rest of the week's builds and shadows are on the real law (≈ 35 minutes, they must run in this order):
```
gcloud run jobs execute build-features --project nfl-predictions-503414 --region us-central1 --wait
gcloud run jobs execute tabpfn-gen --project nfl-predictions-503414 --region us-central1 --update-env-vars TABPFN_UPCOMING=2026:2 --wait
gcloud run jobs execute project-slate --project nfl-predictions-503414 --region us-central1 --wait
```
Each should end "completed successfully". Two rules learned on 2026-09-17: run them **after 05:10 CT** (the daily nflverse
roster ingest runs at 05:00 CT; a build-features that runs before it can be contradicted by DraftKings' roster and
project-slate then refuses with "stale team/position in player_week_inference"), and if project-slate does refuse, simply run
all three again — nothing is damaged. Tell the assistant when done: it re-runs the 6,400 rehearsal (2 hours) so you
get a representative book to look at before Saturday, and checks the receipt shows `production_rows` > 0 and no
marginals warning.

## Before Saturday: nothing else required

- Optional: sign off (or amend) `reports/2026-09-16-prereg-tail-calibration-DRAFT.md` (a lab study, not on the Sunday path).
- Optional: if you change your mind about entering the D12800 book, say so; the fallback switch is one line (Sunday step 2).

## Saturday 2026-09-19

**1. Before 07:30 — arm the six timers** (the assistant cannot write systemd units):
```
/home/erich/projects/.nfl-predictions-worktrees/week1-audit-adjust-20260912/scripts/arm_week_timers.sh 2 --run
systemctl --user list-timers --all | grep nfl-week2
```
Expect six `nfl-week2-*` timers: d12800-sat-build (Sat 08:30), d6400-sat-build (Sat 08:35), d6400-build (Sun 05:30),
sunday-build (Sun 09:10), t70-build (Sun 10:50), watchers (Sun 09:12). The assistant stops the PREREG-099 bank before 08:00.

**2. At 07:45 — refresh the projections** (≈ 35 min; run all three, in this order; after 05:10 CT so the day's roster ingest is in; the 08:30 timer does not wait for them, so start on time):
```
gcloud run jobs execute build-features --project nfl-predictions-503414 --region us-central1 --wait
gcloud run jobs execute tabpfn-gen --project nfl-predictions-503414 --region us-central1 --update-env-vars TABPFN_UPCOMING=2026:2 --wait
gcloud run jobs execute project-slate --project nfl-predictions-503414 --region us-central1 --wait
```
(Why the morning: the 12,800 rehearsal on this week's slate took 16 h 17 min while sharing the machine with the lab bank;
an 08:30 start finishes between 20:30 Saturday and 00:50 Sunday, leaving the night to recover if anything fails.)
Both should end with the execution "completed successfully". If either fails, tell the assistant; the builds still run on
Tuesday's projections, which is acceptable.

**3. Around 09:00 — confirm the builds started:**
```
ls -t /home/erich/week2-sunday/build-*.log | head -n 2; tail -n 2 /home/erich/week2-sunday/build-*.log
```
Two logs (D12800 and D6400) each showing a "== ... run tag ..." header line.

## Sunday 2026-09-20

**1. About 06:00 — check the overnight books:**
```
grep -h "k90=\|k90 build took\|K90 build failed\|== done" /home/erich/week2-sunday/build-*.log
```
You want a `k90=` line and a "== done" for the d12800sat tag (between 20:30 Saturday and 00:50 Sunday) and for d6400sat (≈ 10:45 Saturday). You can check Saturday evening instead of Sunday morning.

**2. Only if the D12800 build failed or you prefer the D6400 book — before 09:12:**
```
printf 'CHOSEN_LEV=1280\nCHOSEN_BOOM=5120\n' > /home/erich/week2-chosen-dose.env
```
(The file currently holds 2560/10240 = the D12800 book. The 09:12 watchers enter only the chosen dose.)

**3. 09:12 — the watchers start on their own.** By about 09:25 read your entry sheet:
```
cat /home/erich/week2-sunday/TODAY-30-LATEST.md
```
The filled entries file appears in Windows Downloads as `DKEntries-FILLED-keepers-first.csv` (built from your
`DKEntries-2026-09-16.csv`; every contest gets the vetted book's first N lineups). If you re-export entries from DraftKings
on Sunday, drop the new export in Downloads and the watcher refills it within a minute.

**4. 10:30 — inactives.** The late-inactives watcher prints any entered player marked O / OUT / IR / D
(`/home/erich/week2-sunday/watch_late_inactives.log`). Scratch protocol: remove a player only when DraftKings marks him
OUT/IR or the official inactives name him; ask the assistant for the swap (it rewrites the ENTER files; the filled CSV
regenerates automatically). Never apply a filter to the book on the day.

**5. By 11:15 — upload in the DraftKings site** (Windows): Lineups → Edit entries → Upload CSV → the
`DKEntries-FILLED-keepers-first.csv` file from Downloads. Lock is 12:00.

## Monday 2026-09-21

- Export the three contest standings and your contest-entry history from DraftKings into Downloads (as in Week 1) and tell
  the assistant; it settles every book and shadow and records the PREREG-099 read when the bank finishes.

## If something looks wrong at any point

Say so in the session. Every step above is idempotent: timers can be re-armed (`systemctl --user stop <unit>` first),
builds re-run by hand (`RUN_TAG=<tag> /home/erich/week2-sunday-build.sh` with the same `env` prefix the timer line
shows), the chosen dose changed, the watchers restarted (`/home/erich/week2-sunday-watchers.sh`).
