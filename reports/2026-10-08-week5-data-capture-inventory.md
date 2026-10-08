# Week 5 data capture: what we collect, when, and who does it (2026-10-08)

The operator (10-08): "please make sure that we're getting all the necessary data from the paid services and other vendors
not only for the live processes this week but also what is needed for the neo4j build and the paper shadows we're running
so we don't lose a week of good data again."

This is the inventory, checked on 10-08 against the code, the warehouse and the live schedulers. **Perishable** means the
data can only be captured in a window. A missed capture is lost for good.

## 1. What runs by itself

These are Cloud Scheduler jobs, verified ENABLED on 10-08. Times are CT.

| Data | Job | When | Week 5 status (10-08) |
|---|---|---|---|
| nflverse (play-by-play, rosters, injuries, depth-chart snapshots, stats) | s-nflverse | daily 05:00 | injuries and rosters current; game data after the games (actuals by Tue 10-13) |
| Game lines (The Odds API) | s-odds | Wed–Sun 09:00, 15:00 | current |
| Player props (The Odds API) | s-props | Wed–Sun 09:30 | 3,874 Week-5 rows (09:33); props guard passes (34.5%) |
| US DFS props and lines | s-us-dfs / s-us-dfs-sun | Wed–Sat 10:30; Sun 06:30, 08:30, 10:30, 11:30 | 1,416 rows (10:32) |
| Weather | s-weather | Fri–Sun 08:00 | starts Friday |
| Features, projections, training | s-features*, s-project*, s-train* | Tue / Thu / Sun | W5 projections written 10-08 (498 players) |
| SIS pass-tail caches | s-tabpfn-sis-pass-tail-* | Thu 09:15, 09:20 | 884 W5 rows each (W1–W4 SIS) |
| The paired shadows | s-shadow-* | Sun: SIS 06:00, cbwu-oi 09:45 / 10:45, Route Share 10:20 / 11:10 | dry runs on 10-08 |
| Freshness check | s-freshness | daily 08:30 | CFB dropped 10-08; weather bar fixed (next image) |

Paused by design:
- `s-dk`, `s-contests`, `s-contests-sun`: DraftKings blocks Cloud Run, and the laptop loop below replaces them.
- CFB (retired).
- The retired shadows.

**On the laptop:**
- **DraftKings salaries and lobby fills:** the host loop `scripts/host_ingest_dk_loop.sh` (running since 10-04). The
  Sunday slate has 84 salary pulls so far.
- **Saturday's armed timers:**
  - the Saturday supply build and the Sunday T-70 build (10:50);
  - the 10:33 post-inactives DraftKings pull;
  - **FP's projection pages** at arming, Sunday 10:40 and Sunday 10:46.

## 2. What the laptop agent captures by hand

Every step is dated in the Week-5 checklist, section "Week 5 data capture".

| Data | Who needs it | When | Perishable |
|---|---|---|---|
| FP weekly pages: route share, alignment, PROE, matchups, SIS | the Route Share shadow; the frames' vendor columns; the graph | Wed vendor run; re-run Thu 10-08 | yes (FP serves the current week; it also revises in place, and we take the latest) |
| FP projection pages (dfs, weekly, rankings) | the live build (FP's projections); study 38; the weekly accuracy check | collected Thu 10-08; then the timers above | yes |
| **FP projected ownership** | study 38's ownership arms; the Monday ownership line (22a); the graph | **Fri 12:30 and 16:30; Sat after arming; Sun 09:15**; plus the Sunday snapshot | **yes** |
| FP live matchups (QB coverage, WR coverage, line matchups) | the matchup research tables | QB coverage retried Fri and Sat; the other two archived 10-07 | yes |
| FP articles and the R14 fact log | study 61 | Sat sweep, before Sunday 10:33 | yes |
| DraftKings draftables (opponent rank) | study 8 (OPRK) | Thu 10-08 done; Sat and Sun ~10:45 | yes (DK revises after the games) |
| Our Sunday build (T-70 and union dirs, FP files) | study 38; studies 60 and 61; P1 / P3; the graph; every Monday reader | Sun after the T-70 upload: the study-38 snapshot, the copies into `~/moneygate/inputs`, `weeks.json` | yes (the pre-lock state) |
| **Paper shadow B** (projections with two features dropped) | O-22's paper check | **Sun ~06:45** (smoke first) | yes (pre-lock serve rows) |

## 3. What only the operator can do (perishable)

**Monday 10-12, by Tuesday 10-13 at the latest:**
- **Export the full standings CSV for every contest entered on Sunday.** DraftKings purges standings exports about 4 days
  after a contest, and the Monday scorer needs one file per contest entered that Sunday. The laptop writes the links page
  and adds any contest from the entry history that is not in the plan.
- **Download the refreshed DraftKings contest entry history.** The file on disk ends 10-04. The laptop pins its new sha.

## 4. Gaps found on 10-08, and what was done

1. **FP projected ownership had one collector, the Sunday snapshot.** At ownership tilt 0 the build does not collect it.
   - Fix: four extra captures this week (FP posted Week 4's by Friday 12:23); the timers do it from Week 6 (O-56).
   - A capture on 10-08 (its log closed 11:25:32 CT) found nothing posted yet.
2. **The FP vendor run crashed on a vendor revision** (the alignment import was fatal). Fixed (non-fatal, merged
   `2bbdcedb`). The skipped projection pages were collected the same morning.
3. **FP revised two stored datasets.** Both were replaced with the latest (the operator 10-08), with backups.
4. **FP's QB coverage matchup page omits two teams' QBs** (ATL, WAS), so the matchup loader cannot stage the week.
   - The other two pages are archived.
   - The QB page is retried Friday and Saturday.
   - A loader rule for a page missing teams is in O-57.
5. **Paper shadow B never ran.** Fix: a smoke run before Sunday and the real run Sunday 06:45. Its Monday reader arm is
   in O-56.
6. **The standings links page lists only the plan's contests.** Fix: Monday adds the entry history's contests; code in
   O-56.
7. **The Monday graph refresh runs before Week 5's actuals load**, so its result facts would be missing. Fix: a Tuesday
   facts re-run.
8. **The graph monitors fall back silently to the largest imported contest** if the Millionaire import is missing. Fix:
   check the import before Monday's refresh; make them refuse in O-56.
9. **Week-specific files** (the priority-contest type mapping, the prior-top file builder, `tier_edges`' paths) need
   their Week 6 versions before Monday 10-19 (O-56).
10. **The daily freshness alarm** had failed every morning on retired CFB, and every Wednesday and Thursday on weather.
    Fixed 10-08.
