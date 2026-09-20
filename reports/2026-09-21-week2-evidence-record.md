# Week-2 evidence record (2026-09-20 Sunday main slate) — scaffold written before outcomes

Per `2026-09-19-in-season-adoption-track.md` section 3. Everything below the "Realized" heading is TODO until the
operator's Monday exports are captured and the accepted proper-score reader (`review/2026-09-prospective-proper-score`
@ 1c95dd68, protocol `2026-09-19-prospective-proper-score-protocol.md`) has run. Monitoring is not inference: this
record is descriptive; no sequential rule is declared for any candidate this week.

## Pre-outcome facts (frozen 2026-09-20)

* Entered book: K97, dose D12800 (lev 2560 / boom 10240), lab release 2dc116c, run `20260919T153008787414Z-2dc116c`
  (archive `gs://nfl-2-506823-lab/research/week2-input-release-20260919/archives/20260919T153008787414Z-2dc116c-d12800/`),
  contests.json ordered by top payout: milly 1, flea 23, huddle 1, nickel 5, pylon 1, satellite 2, supersat1a/b/c 10
  each, supersat25a 16, supersat25b 16, ffwcsat 2 (12 contests, 97 entries).
* Chain: the 09:12 CT watchers timer's transient service killed its detached children (defect recorded); relaunched by
  hand 14:35:00Z; chain completed 14:35:46Z (49 replacements, exclusion set 42, final book sha 529d4f2a...).
* Class E, first-entry promotion (operator authorization 2026-09-19, rule sha 36ffcbce..., consumer v1.2, runner v2.1):
  eligible delivered ranks 1-30 minus 27 and 28 (material); promoted delivered rank 7 (candidate 2123, pooled selection
  mean 144.30886994419097 vs 139.8871983938217 for the delivered rank 1, candidate 12413) to row 1; ranks 1-6 shifted
  to 2-7; 31+ untouched. Lab's outcome-blind screen reproduced the choice (MEAN and P230 pick rank 7; P220 keeps rank 1)
  and recorded the displaced ranks 2-24 block cost: -0.4771 simulated mean-max, -0.290 pp P220, -0.150 pp P230.
* Regeneration 15:49Z after Tua Tagovailoa (rows 39/40/76/89/93) went OUT: chain once-mode tag `-1048`, 52 replacements,
  exclusion set 50 (all dk:OUT additions), final book sha 8eb7c0a9..., promotion re-applied identically (rank 7 -> 1,
  same lineup), promoted book sha 77eaf797...; first 30 delivered rows unchanged, 44 rows changed at ranks 31+.
* Upload verified from the operator's 10:56 CT DraftKings export: 97/97 entries equal to the regenerated promoted book,
  Millionaire entry = promoted row 1. Late-game check 13:57 CT: no late-game player Out; McConkey active (DK cleared
  the Q tag at 13:40 CT).
* Entered-book simulated diagnostics (lab exposure diagnostic on the exact regenerated promoted book, equal-mass
  20,000 worlds): max-mean 200.577, P220 18.70%, P230 9.65%, P240 4.765%. Leading exposures: Jefferson 55 rows,
  Bijan Robinson 45, 49ers DST 39, Javonte Williams 28, McConkey 28 (Q; rows 27 and 28 in the Nickel; no props),
  London 26, Patriots DST 24, Schultz 21.
* Construction facts: stack depth 87 rows at 2 same-team WR/TE, 8 at 3, 2 at 4; every row carries a non-DST player
  projected under 12 (median weakest 8.1); soft flags only (McConkey Q x28; Olave and Burrow Q cleared by kickoff).
* Shadows: none paired this week (Route Share and SIS pass-tail schedulers were paused by design; Week 3 is the first
  graded week). Outcome-blind reads available for pairing after settlement: the promotion counterfactual (delivered
  rank-1 candidate 12413 vs promoted candidate 2123), the un-promoted rollback upload (chain bundle), and the
  stack-depth / floor / ladder registered-arm books produced by the Week-3 runner rehearsal on this pool (REHEARSAL
  label; descriptive only).

## Realized (TODO after Monday settlement)

| item | value | source |
|---|---|---|
| served projections vs realized: CRPS by position, mean bias, squared error, median MAE, p10/p50/p90 coverage, upper-tail pinball | TODO | proper-score reader |
| simulator components vs realized (incumbent, hsim, pooled): player marginals, fixed lineup totals, fixed-book maxima; realized vs simulated P(>=200 / >=220) over the delivered pool | TODO | proper-score reader extensions |
| entered book: realized best, count >= 187 / 194 / 200 / 220 | TODO | outcomes builder + reader |
| contest results: rank, payout per contest, fees vs winnings (the operator's ROI baseline) | TODO | standings exports |
| class E: realized points of promoted row 1 (2123) vs delivered rank-1 (12413); flea-block realized max with vs without the displacement | TODO | outcomes + rollback upload |
| McConkey (28 rows): realized points; rows' realized max with him | TODO | outcomes |
| Tua replacement: realized points of the five replaced rows vs the five removed rows (removed rows scored as entered) | TODO | outcomes |
| ordering-shadow descriptive read: mean / P220 / P230 / winner-proxy orderings' realized row-1 and prefix maxima | TODO | outcomes + ordering screen |

Record author: workstation assistant; realized fields to be filled once, from the settled tables, and never edited after.
