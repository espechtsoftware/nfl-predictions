# Overlay back-test, Week 4 (2026-10-05): no usable overlay on the classic main slate

Written for the operator, under the reviewer's three notes. It tests path-to-winning item 1: are there DraftKings
contests where the guarantee exceeds the fees, so that an average lineup is +EV?

- **Tool:** `scripts/overlay_monitor.py` (read-only; it flags only).
- **Snapshots:** the hourly `nfl_raw.dk_contest_fills`.
- **Final entries:** fetched after lock from the public contest API.
- **Pool ratio:** prize pool / (entries × fee), which is already net of rake. Above 1.0 means an average entrant is
  +EV.

## Result

- **At the latest snapshot, 2,251 guaranteed NFL contests looked overlaid.** Most were freshly spawned copies with one
  entry, which fill before kickoff.
- **The window that matters is 15–60 minutes before lock**, when the operator could still enter. 456 sampled contests
  had a snapshot there:
  - **Original contests:** 86 flagged; **1 held** at lock. That one was a single-game Showdown $5 double-up, at a final
    ratio of 1.18.
  - **Spawned copies:** 370 flagged; 32 held (8.6%). **All 32 were single-game Showdown contests**: satellites,
    double-ups and one GPP. Final ratios were 1.10–1.36, median about 1.11.
- **By fee (window flags; held / flagged):**

  | Fee | Originals | Spawned copies |
  |---|---|---|
  | under $1 | 0 / 8 | 3 / 53 |
  | $1–4 | 0 / 21 | 17 / 162 |
  | $5–25 | 1 / 36 | 6 / 103 |
  | over $25 | 0 / 21 | 6 / 52 |

  The median FINAL ratio of flagged contests was 0.84–0.91: they filled.
- **Against our skill** (P1):
  - Our lineups sit about 0.15 sd below the Millionaire field. In a double-up (top ~44% paid) that means clearing the
    line about 85% as often as an average entry, so an overlay helps us only above a pool ratio of about 1.18. In
    satellites our measured rate is far lower, so the bar is higher still.
  - **No classic main-slate contest held an overlay above 1.18.** The held Showdown overlays (1.10–1.36) are a
    different game format that the system does not build, and our skill there is unmeasured.

## Reading

- **Overlay hunting gives no edge on the classic main slate** in Week 4. Early overlays are an artefact of hourly
  snapshots taken before contests fill.
- **Showdown copies do hold small overlays.** Using them would need a Showdown (captain-format) builder and a measured
  skill estimate in that format. That is a separate idea, recorded here and not proposed.
- **The monitor stays as a cheap weekly log:** run `flag` about T−45 and `finalize` after lock. Over the coming weeks
  that tells us whether Week 4 is typical.

**Files** (scratch, not tracked): `overlay/w4_sample_flags-final.csv`, `overlay/w4_overlay_backtest.csv`. Sample: all
1,524 flags that were at least 50% full within 120 minutes of lock, plus a random 150 of the rest.
