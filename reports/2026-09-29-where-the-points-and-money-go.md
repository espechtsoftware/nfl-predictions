# Where the points and money go: answers to the 35 questions (2026-09-29)

Written for the reviewer, the operator and both agents. Production researched the question list of
`reports/2026-09-29-questions-to-get-to-the-bottom-of-the-losses.md` on 2026-09-29 with seven parallel read-only
analyses (light compute; the two lab panels owned the box) plus the winners study that landed the same afternoon
(`origin/review/winners-study-20260929`, `reports/2026-09-29-winners-study-and-consistency.md`). The analysts' full
answers and scripts are under `reports/lab-handoffs/2026-09-29-questions-research/` (theme files A, B, B6, C, E, F, G;
no data files are committed: the field exports carry user names). Every answer names its evidence and information
time. No dollar figures; the stake plan is private.

## The picture in one place

Our lineups average below the field, the Millionaire is out of reach of every pool we have built, and the money sits in
contests that pay the average lineup, where our books ran at 0.8–0.9× the field mean against a break-even of
1.10–1.19×. Winners are chalkier than the field, spend on stud RB/WR, take a cheap stacked QB and a cheap TE, and lean on
late games. Projections match the market; the loss is between projection and entry. Week-to-week user persistence is
real but modest (Spearman +0.12 to +0.27) and the edge is players, not shapes. On the 36-slate panel the Weeks 1–3
selectors sit below the field's rate (EMAX 0.82×, MEAN 0.95× at p89); only the Week-4 main form clears it (1.22×), on a
32–31 paired record.

## The answers, by theme (one paragraph each; the full tables are in the theme files)

**A. Money.** At the Weeks 1–3 quality no contest class clears the rake: the entered books ran at 0.85–0.94× the field
mean in every class in Weeks 2–3 and returned −72% to −100% in every satellite class. At the armed Week-4 form, if the
panel transfers, two independent transfers agree: the 2,378- and 190-entry supersats clear break-even by +20–36% per
entry, the 594-entry supersats are about even, the 11-entry satellites, the 402-entry satellites and the FFWC qualifier
stay below. A Millionaire seat from the books actually entered was worth 0.23× its fee (no row inside the top 1,000 in
three weeks); under the Week-4 form it is 0.6–0.7× outside the top ten, a lottery ticket. `payout` is NULL on every
stored entry because the importer expects a Winnings column the export does not carry; DraftKings' public ladders for
all 60 contests fetch today and sum to the stated pools, so the fix is a ladder table and a rank-to-tier view. Two cash
lines were recorded high (W2 135.5 not 138; W3 146.4 not 149.5). Lifetime the operator's ROI is −83.5% over 1,164
entries, −96% in the 5k–40k qualifier class that is more than half of lifetime volume, smallest where the payout is
flattest and the field largest.

**B. The funnel.** In both clean weeks the largest drop is the same stage: from the top-K-by-mean book to the entered
book, −29 (W1) and −31 (W3) realized points per row, and only a quarter of it is visible in projected points. In
projected points every one of our books sits above the field's average lineup; realized, the entered rows realize 2, 16
and 10 points less relative to projection than the field's rows, while the top-mean rows realize 20 and 15 points more.
The expected-max selector picks rows that under-realize (the residual rises with ownership sum and is worst for 4-punt
and boom rows). Predictable duds cost 3.5–4.7 points per entered row and are almost entirely the p90-valued punt: the
valuation overstates every punt slot by 9–14 points, ranks punts no better than the mean, and forces a fourth punt into
leverage rows that realize 13–24 below three-punt rows. The stack mandate earns points on the mean track (field rows
with our shape +3 to +5, cash 26–27% vs 18%; given the projection, 4-game rows beat 6–7-game rows); its cost is
concentration, not mean. Expensive QBs are over-projected by 0.8–1.8 historically and stud WRs under-projected by
+0.6 (+2 to +5 this season on tiny samples).

**B6. The dumb baseline.** A plain optimizer on the props-implied projection under DraftKings' rules only, no simulator,
generator or selector, beat the book we entered in every frame (+12.5, +14.1, +12.9, +32.1 per row) and beat the
Millionaire median in both clean weeks. Top-mean selection from our own pool beat that baseline on the clean weeks
(169.7 vs 157.1; 151.2 vs 133.1). The ordering on the mean track: top-mean from our pool, then market-plain, then the
entered expected-max book, then DK points-per-game. On the three clean frames the generator, simulator and expected-max
selector cost 21–25 points per row against a plain optimizer on the same served projection with the house rules, which
themselves added +40 / +7 / +7. Historically (12 slates) the market book wins 10–11 of 12; the historical served column
carries the p90 punt valuation in `proj`, so its gap is an upper bound until the snapshot's `mean_projection` is verified.

**C. The field as a forecaster.** Over 72 slates the crowd's most-owned RB, WR and TE out-score our highest-projected by
about 2 points per player in 48–50 of 72 slates; at QB we win; as a within-slate ranker the two are at parity. The
LAG+LineStar blend hits 9.5 of the realized top 15 against the lag model's 6.0 (34 slates better, 1 worse), with the
caveat that LineStar's archive hour is unknown. The stored Thursday ownership input for Week 1 had Spearman −0.16 with
realized ownership; the same formula on the T-70 frame gives +0.82: the QB-availability defect wrecked the input, not
the formula. Our pools carry the winners' chalk-core shape 3–8% of the time against the field's 52%, and it scores +7
to +15 per row where it occurs. Duplication is not a lever (fields 90–94% unique, dilution at most 10%).

**D. Timing.** The Sunday news effect on the same rows was +23 in the defect week and −3 to −4 of noise in the clean
weeks; active players' projections move 0.26 on average with identical accuracy; the smaller Sunday pools cost 13–15
points of top-mean book in Week 3. The W1 and W3 T-70 frames were pulled before the 10:30 CT inactives. The one
exploitable post-T-70 item is the Questionable players declared active (eight in W3, under-projected by 1.7 each).
Residual availability loss is down to 0.6 projected points per entered row, one class: depth-2+ WR/TE at $2.5–3.5k with a
blank status and no prop line.

**E. The simulator.** The main book is simulator-free: the "simulated mean" it solves on equals the served projection
to 2e-6 per player. Two bank defects: the corrected-hsim bank runs +5 to +7 per lineup above the served projection in
every 2026 build (QB +9%, top quartile +7%) despite its receipt, and the incumbent bank's DST row has zero variance. The
slate level is the market's own miss (W1 +20%, W2 −17%, W3 +6%, matched by the market total) and needs no pinning;
the pace flag is mean-preserving. Tails are 2–3.5× over at 200 because of within-team coupling (WR1–WR2 +0.27 in the
incumbent bank vs +0.016 realized) and spike size; no runnable preregistered repair exists (PREREG-101 withdrawn on a
refuted monotonicity claim and an impossible gate). Dependence changes nothing a projected sum can see.

**F. Portfolios (preliminary; Q11 supersedes).** Persistence: W1→W2 +0.116, W2→W3 +0.269, W1→W3 +0.237; the
lift of being top-20% again is 1.1–1.6×, so two-thirds of last week's best fifth fall out. Nine users were top-100
twice, six of them W2↔W3 (35× chance), all but one with 150 entries. The W2 winner's 150-row book averaged the field
every week. Persistent users are chalkier (+15 to +24 ownership points per row) with a small tilt to two-deep stacks.
Heavy top-100 portfolios have the same shape as heavy mid-field ones (exposure .56 vs .58 on the top player, pairwise
overlap 1.9 vs 2.0, 93–94% unique): no cores, an optimizer with exposure targets, our own shape. Every player of every
winning lineup was in our pool all three weeks (81 of 81); the book skipped two each week (W1 Coker and the Steelers at
0 of 57; W3 Geno Smith 5%, Sadiq 3% against two busting DSTs at 35% and 33%).

**G. Process.** The objective changed three times; only the L09–L18 reads and two live weeks were decided on the current
one. Six tail-era closures deserve a mean-track read and have none: the stack mandate, the p90 punt valuation, market
weight below 0.45, status caps, the late swap's mean co-report, the ensemble-K shadows. Three live weeks detect only a
20–28-point selector gap (a 9-point tilt in six weeks); a symmetric rule is proposed (same-pool paper control, book mean
vs field primary, cumulative z with the panel's σ, adopt at +2, withdraw at −2). 43% of season-split reads disagree in
sign; the 2022 holdout flipped the armed book's level and reversed a 2× pattern. The panel's verdict labels flip in
about half of bootstrap draws (the paired-wins clause), the large-effect directions do not (PMO_X50 > MEAN positive in
98.5% of draws; X67 HARMFUL 47%, sign 95%). The ranked never-tested queue starts with the ownership term inside the
capped objective, the dumb baseline (now done), the punt valuation, status caps and the spread dealing.

**H. Data.** Historical field lineups exist only for 2026 (plus a 2021 FLEX clone); whether DraftKings exports a
non-entered or a mid-slate contest is unverified and one click each. Payout ladders are fetchable and should be loaded.
The LineStar capture proves content, not time: the hash must be pushed before lock with the lock time in the receipt.

## Immediate actions, ranked

"Entry change" items alter what is uploaded and need the operator's and the reviewer's yes before the Thursday 18:00
CDT freeze; "paper" items run beside the entered book; "process" items are bookkeeping. The armed Week-4 configuration
stands throughout.

| # | Action | Kind | Evidence | Confidence |
|---|---|---|---|---|
| 1 | Fund the 2,378- and 190-entry supersats with the armed book (594s optional); stop funding the 11-entry and 402-entry satellites and the FFWC 5,000 qualifier; one Millionaire seat as a lottery ticket | operator's allocation, Week 4 | A2 (two transfers agree), A3, the qualifier class −96% lifetime | moderate on the supersats' sign; high on the rest |
| 2 | Judge every week on the book's score against the field, not the week's dollars; size the stake for four losing weeks in five | process | winners study §1–3; G2 | high |
| 3 | Cap punts at three per row and drop 4-punt leverage rows before mean selection (pool filter, no solve); queue Q4b | entry change, reversible; rehearse on Weeks 1 and 3 | B2, B3 | medium-high |
| 4 | Build the market-only plain book every Sunday as a paper shadow and mean-track fallback | paper | B6 (4 of 4 frames) | high it costs nothing; moderate-high on the edge |
| 5 | Pull DraftKings after the 10:30 CT inactives and before the T-70 projection; Q-activation scale on; re-project nothing else | process | D1, D2 | high |
| 6 | Ownership as a positive input: the blended term inside the capped optimizer (λ 0.10, 0.20) as a paper book at T-70, inputs on the T-70 frame, graded Monday; entry no earlier than Week 5 | paper | C1, C3, winners study §4.1 | moderate; gated on provable captures |
| 7 | Exposure toward the pieces the winners share: the armed DST cap plus a rehearsed tie-breaker of ≤ 2 predicted sub-5% and ≥ 1 predicted 20%+ per row | entry change, reversible; rehearse first | F5, C4 | moderate |
| 8 | Deal each contest's rows spread across the optimizer's sequence | entry change, layout only; Week 5 unless rehearsed by Thursday noon | winners study §4.2 | moderate |
| 9 | Punt-band availability filter: depth-3+ WR and depth-2+ TE at or under $3.5k with no prop line at the T-70 pull | entry change, reversible; check false positives first | D3, B2 | medium |
| 10 | Fix the two bank defects; retire the simulator's P(≥line) from receipts and paper arms | process before any tail read | E1, L14 | high |
| 11 | Data: payout ladders and the rank-to-tier view; corrected cash lines; provable LineStar/FP captures; verify the two DraftKings exports with receipts; store `own_shadow` and grade the capture every Monday | process | A4, H1–H4, C3 | high |
| 12 | Research process: bootstrap interval and P(effect > 0) beside every verdict; the symmetric adopt/withdraw rule; re-read the six tail-era closures on the mean track; verify the historical `mean_projection`; a third season on any panel adoption | process | G1–G4, B6 | high |

**Correction to action 1 (the laptop, 17:59 CDT).** Both transfers in A2 priced the 2,378- and 190-entry supersats
with the capped optimizer's rows, and the winners study's week simulation dealt its 36-row main book to every class.
Under the armed routing those contests are not dealt those rows: the deep-line rule sends every contest paying 2% or
less of its field (25 of 2,378 and 2 of 190 both qualify) to the 85-row tail sleeve, the top-85 by projected sum from
pool plus main rows (31 of 85 optimizer rows in the Week-3 rehearsal). The mean-selected pool rows' panel rate at p99
is 1.02× the field's, below the 1.19× break-even, so action 1's +20–36% holds only if the funded supersats are routed
to the main book (`track_override: "mean"` per contest; the main book then grows to cover them; L13 supports the form
at K = 144: 1.22× at p89, 1.77× at p99). That is an entry change for the operator and the reviewer before Thursday
18:00. When L19 reads, the supersats' EV under sleeve dealing will be recomputed from the sleeve's own rate.

**Correction to actions 3 and 9 (the laptop, 18:06 CDT, outcome-blind on the Week-3 slate).** On the Week-4 form both
are near-dead levers: the capped optimizer solves on `mean_projection` and the sleeve ranks by projected sum, and in
the live frame `proj` equals `mean_projection` for every non-DST player, so neither selection sees the p90 punt
valuation (it reaches the book only through the generator's pool). The Week-4 selections hold no row with four or more
punts, and the punt-band filter touches 0 of 36 main rows and 2 of 85 sleeve rows. The B2/B3 findings were about the
expected-max books of Weeks 1–3. Actions 3 and 9 move to the generator and the lab (Q4b; the pool's universe filter),
not to Thursday's decisions.

Do not: re-arm the chalk fade; treat cores as a lever or add uniqueness constraints; pin the simulator's level to the
market total; copy named repeaters; re-project active players on Sunday; read Week 2's served books as projection
evidence; adopt anything from the panel without a paired live control from the same pool.

What would change the ranking: the first live read of the armed form (Monday 10-05); the laptop's Q11 study
(Wednesday); the L16, L19 and L07 reads this week; the first graded LineStar capture.
