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

## Realized (standings 2026-09-20; contest money settled 2026-09-21; nflverse-based items still TODO)

Release: the operator's message of 2026-09-20 evening ("We performed about as badly as we could have ... do an
extremely detailed analysis of how we did this week") is the Week-2 outcome release. Realized points below are the
DraftKings FPTS carried in the 12 standings exports (identical across all 12; saved under
`/home/erich/week2-sunday/ENTERED/standings/`, never committed). The nflverse actuals for Week 2 were not yet loaded
when this was written (`player_week_actuals` held 92 Week-2 rows), so every proper-score item stays TODO for the
Monday chain. Full analysis: `2026-09-21-week2-post-mortem.md`.

| item | value | source |
|---|---|---|
| served projections vs realized: CRPS by position, mean bias, squared error, median MAE, p10/p50/p90 coverage, upper-tail pinball | TODO (Monday, after the nflverse Week-2 load). Descriptive now: corr(proj, FPTS) 0.60 over 297 salaried players; players projected >= 15 (n = 41) averaged 18.3 projected vs 14.9 realized, 32% reached projection; top-10 QBs by projection 21.1 -> 16.9, top-10 RBs 16.8 -> 11.8, top-10 WRs 17.8 -> 18.4 | standings FPTS; proper-score reader pending |
| simulator components vs realized (incumbent, hsim, pooled): player marginals, fixed lineup totals, fixed-book maxima; realized vs simulated P(>=200 / >=220) over the delivered pool | TODO (Monday). Descriptive now: over the 12,555 delivered candidates corr(sel_mean, realized) = -0.49; realized mean by sel_mean decile falls from 109.3 (lowest decile, mean 111.5) to 69.8 (highest decile, mean 139.7); pool realized >= 150: 222 rows, >= 187: 1, >= 194: 1 (197.26), >= 200: 0 | pool-realized-12555.csv |
| entered book: realized best, count >= 187 / 194 / 200 / 220 | best 156.16 (Flea, rank 7,277 of 83,234); mean 105.0, median 103.2; counts 0 / 0 / 0 / 0. Delivered ranks 1-97 before promotion and regeneration: mean 98.4, max 157.96 | standings; our-97-results.csv |
| contest results: rank, payout per contest, fees vs winnings (the operator's ROI baseline) | **SETTLED 2026-09-21 from the DraftKings contest-history export** (`My Contests -> History -> Export Contest History`; all 97 entries matched the twelve Week-2 contest keys exactly, so the reconciliation is complete). **Fees $246.00, winnings $26.00, net -$220.00, ROI -89.4%.** Tickets won: $0.00. Only one contest returned anything: Flea Flicker $26.00 across 23 entries. The other eleven returned nothing, including the Millionaire (1 entry, $20) and all seven satellites (66 entries, $40). Best finishes: Flea 7,277/83,234 (8.7%); supersat25c 84/594 (14.1%); supersat 555 44/68; supersat-other 48/59; supersat25a 151/594; supersat25b 171/594; supersat1b 255/2,378; supersat1a 337/2,378; Nickel 3,521/9,512; Pylon 5,516/15,854; Huddle 11,996/23,781; Millionaire 56,403/172,761 (32.6%). Context: Week 1 was $399 fees / $140 winnings (-64.9%); season to date $645 / $166 = **-74.3%**, against the 2020-2026 baseline of about -83% per season. The raw export stays under `week2-sunday/ENTERED/` and is never committed. |
| class E: realized points of promoted row 1 (2123) vs delivered rank-1 (12413); flea-block realized max with vs without the displacement | promoted row 1 (candidate 2123, sel_mean 139.5, the book's highest) realized 126.62 -> Millionaire rank 56,403 (top 33%); delivered rank-1 (candidate 12413, sel_mean 131.2) realized 83.84. Flea block: delivered ranks 2-24 max 157.96 vs entered Flea block max 156.16 (the entered block also carries the 10:48 regeneration). The promotion gained +42.8 points on the one Millionaire row and cost nothing visible in the Flea block | pool-realized-12555.csv; our-97-results.csv |
| McConkey (28 rows): realized points; rows' realized max with him | 6.5 points (played with the rib injury). His 28 rows: realized max 148.26 (supersat25b rank 255), mean 98.8; distribution supersat25b 9, supersat1b 5, supersat1c 5, supersat25a 4, supersat1a 3, Nickel 2; none in the Millionaire/Flea/Huddle/Pylon | standings |
| Tua replacement: realized points of the five replaced rows vs the five removed rows (removed rows scored as entered) | the 10:48 regeneration changed 44 rows, not five (the whole-slate exclusion set was 50 players). Removed versions scored as written (Tua and other excluded players at 0): total 4,620.0 vs the entered versions 4,503.2 (-116.8, -2.7 per row); max 155.76 removed-version vs 149.52 entered-version. Per-row table: `regeneration-1048-changed-rows.csv` (reply branch receipts) | book.csv 09:36 vs 10:48; standings FPTS |
| ordering-shadow descriptive read: mean / P220 / P230 / winner-proxy orderings' realized row-1 and prefix maxima | mean ordering's row 1 = 126.62 (above). P220 / P230 / winner-proxy orderings: TODO (ordering screen outputs on the labs' side) | ordering screen |

Realized fields above were filled once from the standings exports on 2026-09-20; the TODO items are to be filled once
from the settled nflverse tables and never edited after.
