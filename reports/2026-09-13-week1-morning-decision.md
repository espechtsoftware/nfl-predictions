# Week-1 morning decision — 2026-09-13 (lock 12:00 CT)

**Status:** draft written 2026-09-12 ~19:00Z with the decision rule frozen; the PREREG-090 read fills §2
when the three r2 banks complete (expected ~21:00–22:00Z). Nothing here opens a 2026 outcome.

## 1. What is fixed regardless of the read

- **Paid book = corrected centering.** Every Week-1 book is built with `NFL2_LIVE_CENTER=production` from
  `/home/erich/projects/.nfl2-worktrees/week1-live-center-e7255e9` (skill AND DST centred on production's
  served projections; level gate on; receipts record `naive_top_lineup_projection` ≈145–160, `matched_skill`
  ≈362, `dst_matched` 24). The uncorrected lab level (RB/WR ≈ 8 pts, salary-ranked DST) is not an option.
- **Paid policy = P_MIX on the D800 pair** through the governed publisher (P_CTRL fallback), unless §2
  moves the dose.
- **Entry layout:** 90 unique lineups (Milly 1–57, Play-Action 58–77, FFWC-Q6 78–80, FFWC-Q5 81–90) from
  the K90 build; the alternative 57-unique + duplicated top ranks is inferior for a weekly-max objective
  (audit §3.4). The K90 book's ranks 1–80 are identical to the K80 paid book (verified), so P_MIX's K80 and
  the K90 layout compose: Milly gets P_MIX ranks 1–57; the other three contests take K90 ranks 58–90 of the
  same-seed build (P_CTRL-equivalent rows, since P_MIX is defined on K80 only).
- **Shadows (frozen, never entered):** D400_DEMAX, D800_WEMAX, direct-tail, DT-union, spread-4, NOBB sleeve,
  and — if PREREG-090 does not move the dose — D1600.

## 2. The dose decision (fill from the frozen reader)

PREREG-090 consequence 1: `D1600_DEMAX` **PASS** on the r2 cohort **and** the live D1600 receipts not worse
than D800's under both laws (already true: 178.6 vs 177.7 incumbent, 199.0 vs 198.4 hsim, P≥220 .021 vs
.018 / .141 vs .133) → the Milly book becomes the corrected **D1600 DEMAX K90** (lev 320 / boom 1280) via
the run-dir upload path (P_CTRL-equivalent; the governed P_MIX publisher only accepts the 160/640 pair), and
the P_MIX D800 K80 book is frozen as the primary shadow. Any other verdict → the D800 P_MIX plan above.

**Live receipts (outcome-blind, built Saturday on `e7255e9`, all three books scored under the D800 build's
own two banks; `score_book_under_bank.py`) — the live-receipt conditions of PREREG-090 consequence 1 and
PREREG-093's ladder are satisfied: every line is monotone in dose.**

| live book (K80) | law | E[max] | P(≥194) | P(≥210) | P(≥220) | pool P(≥220) |
|---|---|---:|---:|---:|---:|---:|
| D800 `…192221336726Z` | incumbent | 179.5 | .209 | .062 | .023 | .054 |
| D1600 `…203440469470Z` | incumbent | 180.6 | .225 | .069 | .026 | .082 |
| D3200 `…194342612416Z` | incumbent | 181.1 | .237 | .072 | .027 | .114 |
| D800 | corrected-hsim | 196.4 | .516 | .227 | .115 | .210 |
| D1600 | corrected-hsim | 197.0 | .529 | .235 | .118 | .285 |
| D3200 | corrected-hsim | 198.3 | .552 | .259 | .138 | .369 |

Build cost on this workstation: D800 5 min, D1600 14 min, **D3200 51 min** (3,040 s). A D3200 K90 with
sidecars was built Saturday 20:49–21:39Z as the Sunday fallback for the 3200 dose: run dir `…/week1-live-center-e7255e9/results/live/2026-w01/20260912T204921…-e7255e9` (salary pull 20:04Z; 90 unique rosters, its own K80 nested), upload CSVs `/home/erich/week1-sunday/upload-FALLBACK-D3200-K90-20260912T204921-e7255e9-{milly-193028206-ranks-1-57, playaction-193028208-ranks-58-77, ffwc-q6-194478066-ranks-78-80, ffwc-q5-194478065-ranks-81-90}.csv` — usable only if the read selects 3200 AND the Sunday D3200 build cannot finish before ~10:45 CT; re-check DK inactives against its rosters first.

**Read procedure (PREREG-090 amendment 4):** Cloud Run lost 13 r2 tasks to platform "Internal error"; the
registered finish launcher re-runs exactly those slates on the same image. Read from the amend4 worktree:
`cd /home/erich/projects/.nfl2-worktrees/prereg090-amend4 && PYTHONPATH=src /home/erich/projects/nfl2/.venv/bin/python
scripts/prereg090_report.py 110b900r2-20260912T191557Z 110b901r2-20260912T191821Z <110b902r2 run id>
--repair <each 110b9NNr2rep<season> run id>` (run ids: cohort worktree `results/queue_110_launches.log` and
`results/queue_110_finish_launches.log`).

| reader line | value |
|---|---|
| `D1600_DEMAX − D800_DEMAX` proxy, family interval, banks, LOSO, verdict | *pending* |
| `D800_DT_DEMAX − D800_DEMAX` | *pending* |
| `D1600_HALFDT_DEMAX − D800_DEMAX` | *pending* |
| threshold events 200/210/220/230 per arm | *pending* |
| supply counts ≥220/≥230 per pool | *pending* |

## 3. Sunday sequence (times CT)

| time | step |
|---|---|
| 08:30 | confirm `s-nflverse`, `s-features-sun` and the 09:00 `project-slate` execution succeed |
| 09:10 | `/home/erich/week1-sunday-build.sh` (runbook build + preflight, K90, upload CSVs; add `/home/erich/week1-dose.env` first if §2 fired: `PAID_LEV=320 PAID_BOOM=1280` for 1600, `PAID_LEV=640 PAID_BOOM=2560` for 3200 — the 3200 build takes ~51 min, so the dose book lands ≈10:15; if it is late, upload Saturday night's D3200 K90 fallback CSVs from `/home/erich/week1-sunday/` after re-checking inactives) |
| 09:30 | publish once: runbook step 4a (`publish_week1_a5_books.py … --execute`, run id from the build log) |
| 09:35 | emit P_MIX ranks 1–57 from the published book (runbook 4b, `--book-id P_MIX --ranks 1-57`); take ranks 58–90 from the K90 (or D1600 K90) run-dir CSVs |
| 09:45–11:15 | upload the four contest files in the DK UI (operator-only) |
| 11:20 | re-check DK inactives; if a paid-book player is ruled out, rebuild with a new run id and re-upload (DK edits allowed until lock) |
| 12:00 | lock |

Fallbacks: corrected P_CTRL run-dir CSVs (`/home/erich/week1-sunday/upload-*`) → the DST-fixed placeholder files
emitted Saturday 19:41Z (`/home/erich/week1-upload-CORRECTED-DST-20260912T1922Z-e7255e9-*` for K80 ranks and
`…-CORRECTED-DST-K90-20260912T1933Z-e7255e9-*` for ranks 58–90; the older `…-3df1b0c-*` files are Chargers-centred
and superseded) → production app export.

## 4. Monday/Tuesday

Standings capture for all four contests (`nfl-dfs capture-dk-standings`, validation first, then
`--confirm-settled --confirm-full-field --apply`); settle every frozen run dir (`scripts/settle_live.py`),
including the shadow arms; write the tail-ledger row; append the LEDGER rows for PREREG-090/091/092.
