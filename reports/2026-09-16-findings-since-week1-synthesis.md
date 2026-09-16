# What the tests since Sunday say, and what to do next (2026-09-16, Wednesday)

Written for the operator and for whichever agent runs the program next. Every number is from a frozen read or a
settled export; the source is named in each row. Nothing here changes the Week-2 money path by itself (§5 lists the
decisions that would).

## 0. In five sentences

1. The machine generates 220-point lineups at a rate that doubles with every doubling of the candidate budget, but the
   selector does not find them: the pool's best lineup rose 13 points from dose 800 to 6,400 while the 80-lineup book
   rose 1.9, and the share of weeks in which the book contains the pool's best lineup fell from 22 % to 7 %.
2. The reason is not the admission gate, not the paid data, and not the field model: with every qualifying candidate in
   front of it the selector's K20 book did not move (164.4 vs 165.1), the Fantasy Points / SIS annotations changed
   *which* lineups were picked (Jaccard 0.13–0.26) without changing what they scored, and finish-against-the-field
   selection was decisively worse than expected-max (9 wins / 44 losses).
3. Every objective that reaches further into the simulator's tail than expected-max does worse on realized outcomes,
   in order: E[max] > P(top-1,000) > P(top-100), and the simulated-q99 ordering loses 6.8 points at K30. The
   simulator's *ordering* of extreme outcomes is the binding constraint; its marginal calibration is fine.
4. Availability is the one place a measurable, unpriced error exists: Questionable players who did not practise fully
   deliver 3–6 points under projection and score zero a quarter to a half of the time, while undesignated practice
   absences deliver in full. The shipped vetting rule is null on the proxy with a positive raw prefix effect; keep it.
5. The next levers, in order of evidence: (a) contest choice where a 200-point book wins (the settled Week-1 fields say
   where that is), (b) the 12,800 supply read now running (generation exhausted or not), (c) a tail-calibration
   preregistration that reweights worlds against realized exceedance, (d) a Questionable-exposure cap. Not: more
   selectors on simulated tail probabilities, paid data renewals, deeper stacks, late swap.

## 1. The record since Sunday 2026-09-13

| when | test | question | result | verdict / consequence | source |
|---|---|---|---|---|---|
| Sun–Mon | Week-1 settlement | what did the entered 80 and every shadow score against the real fields? | entered best 196.24 (Play-Action rank 4,872 / 158,541; Millionaire 192.08, rank 34,838 / 832,342); the machine's own vetted K90 held a 226.64 that the proven-scorer rule removed; fees $399, winnings $140 | the removal rule was the costliest decision of the week; scratch protocol adopted | `2026-09-14-week1-field-winners-settlement.md` |
| Sun night | post-mortem measurements | is the simulator miscalibrated? is the selector broken? | realized perfect lineup 267 vs simulated 258 (inside range); realized outcomes exceed the simulator's q99 0.7–1.0 % of the time; P(≥200) over-predicted 3× (0.40 % vs 0.13 %); selector enriches 220s 10× vs unselected; stacks of 4–5 over-rewarded; late swap +0.7 at K30 | marginals calibrated, extreme tail optimistic; 220 is a +4 s.d. event for a fixed lineup | `2026-09-13-week1-postmortem-and-220-program.md` |
| Sun | PREREG-096 learned pool selector | does the frozen ridge score beat expected-max as the selector over real 3,200 pools? | K30 −2.83 [−10.2, +5.1]; 2022 −17.0; K80 +0.3; simulated-q99 ordering −6.77 at K30 | REVERT; learned selectors closed on this simulator | lab `PREREG-096`, `2026-09-13-prereg096-read.md` |
| Mon–Tue | PREREG-097 dose 6,400 | does the dose law continue? | D3200−D800 +0.0096 PASS (replicates 093/095); D6400−D800 +0.0146 PASS (raw +1.87; K80 weeks ≥200 10→16, ≥210 1→7, ≥220 1→1); D6400−D3200 +0.0050 near miss (32W/36L); 220-supply per slate-bank 0.45→0.89; pool oracle 204.5→207.8; best-in-book 0.069 at both | saturation at 3,200 as a paid dose; 3,200 is the Week-2 candidate; 12,800 admissible as a supply study only | lab `PREREG-097`, read 2026-09-16 |
| Mon | payout retro-test (one week, field known) | does selecting on finish pick a different, better book? | different (6–12 of 30 shared); on the one real week P(top-100)-30 found the 224.54 ($133 vs $71); raw expected payout is lottery noise | a sign, not a verdict → PREREG-098 | `2026-09-14-payout-retro-test.md` |
| Mon–Tue | PREREG-098 finish objective (53 slates, modeled field) | does P(top-N) selection against an ownership-consistent field beat expected-max on realized finish? | FIN1000_K80 − DEMAX −0.0299 [−0.048, −0.015], 9W/44L; FIN100 −0.0345, 4W/48L; every bank and LOSO negative; points −8.7 / −10.5; best-finish percentile 2.56 % (DEMAX) vs 5.55 / 6.01 % | NEGATIVE, decisive; closed at tested form; the sign did not replicate | lab `PREREG-098`, read 2026-09-16 |
| Tue | paid-source influence ladder (direct runner, 54 slates) | do Fantasy Points / SIS annotations change selection and outcomes? | selection yes (K80 Jaccard vs on-on 0.13 FP-off / 0.26 SIS-off); points null at every K; finish SIS-given-FP K20 +0.019 PASS-by-rule but 24W/14L p 0.14 and null at K40/K80; FP null to negative; admitted ceiling ~181 vs pool 202.7 in every cell | sources reshuffle without value; the admission gate discards the tail two-thirds of the time | `2026-09-15-paid-source-influence-ladder-direct.md` |
| Tue | admission-cap lever (frozen f9ed9475) | is the cap the bottleneck? do sources matter once it is lifted? | capall lifts the admitted ceiling 181→202 (36 of 54 slates hold a 194+) yet K20 164.4 vs 165.1; K80 +1.5 near miss; source-free tail200 as good or better (K20 +1.16 near miss, best finish percentile of any rule); sources at capall null at every K | nothing passes; the regret is in the selector's world model; do not renew FP/SIS | `2026-09-15-admission-cap-lever-result.md` |
| Wed | PREREG-100 practice-status vetting (216 slate-banks) | does the shipped vetting demotion help or hurt the 30-lineup prefix? which flags carry error? | V1 (as shipped) K30 proxy +0.0053 [−0.0034, +0.0142] NULL, raw +0.84, weeks ≥194 at K30 5→13; V2 hard-only NULL. Player level: Q_dnp −5.9 (zero rate 47 %), Q_limited −2.9 (25 %), doubtful −11.8; none_limited +0.4, none_dnp −1.2 with 20+ rates 1.3× / 1.2× clean | keep vet_book as shipped; a Q_dnp/Q_limited cap is the follow-up | lab `PREREG-100` |
| Wed → Thu | PREREG-099 12,800 supply rung (2 banks, running) | does the 220+ supply keep doubling? | pending | DOUBLING / SATURATING / INDETERMINATE by frozen rule | lab `PREREG-099` |

Infrastructure findings of the same days, because they gate everything above: the FTN charting ingest now tolerates an
absent season (verified on the Wednesday 10:00Z run: 2,675 rows loaded); DraftKings returns 403 to every Google Cloud
address tried (Cloud Run and Cloud Build), so the hourly salary and contest pulls run from the host loop; the full test
suite exceeds Cloud Build's 3-hour ceiling, so production builds use the focused lane (disclosed deviation).

## 2. Findings that hold together

### 2.1 Supply is manufactured on demand; conversion is not

| dose | candidates ≥ 220 per slate-bank | pool oracle | K80 raw max vs 800 | book holds the pool's best | weeks K80 ≥ 200 / ≥ 220 |
|---|---:|---:|---:|---:|---:|
| 800 | 0.10 | 194.8 | – | 21.8 % | 10 / 1 |
| 1,600 | 0.25 | 200.5 | +0.66 | 11.6 % | 10 / 1 |
| 3,200 | 0.45 | 204.5 | +0.66 | 6.9 % | 11 / 1 |
| 6,400 | 0.89 | 207.8 | +1.87 | 6.9 % | 16 / 1 |

(PREREG-097 read; six earlier banks in 093/095 gave the same shape.) Each doubling adds about 3.3 points to the pool's
best lineup and doubles the count of 220+ candidates; the K80 book keeps a fixed fraction of that. The gap between the
pool oracle and the book widens with dose: retrieval regret is now the larger half of the distance to 220.

### 2.2 The regret is in the selector's world model, and nowhere else

Three independent instruments, two code bases, the same answer:

- Lab, expected-max over 20,000 dual-law worlds: best-in-book 7 % at 3,200 and 6,400 (PREREG-097).
- Production corpus, coverage-194 over 40,000 discovery worlds: admitting everything (ceiling 181 → 202, a 194+
  candidate in front of the selector in 36 of 54 slates instead of 13) moves the K20 book by −0.7 (admission-cap read).
- Paid annotations: change the selection materially (Jaccard 0.13–0.26 vs the on-on book) and nothing downstream
  (points null at K20/40/80; finish null except one K20 cell that fails its sign test).

This is Addendum 95 ("selection is closed for the current simulator") reproduced on fresh data with fresh code. The
ledger's older negative results on selectors (LSE, sharp-LSE, dollars, decision-focused reranker, novelty, union e-max,
coverage-220) are the same phenomenon.

### 2.3 The further an objective reaches into the simulated tail, the worse the realized book

| objective (same pool, same worlds) | what it optimises | realized result vs expected-max |
|---|---|---|
| expected-max (control) | E[max over the book] — the whole distribution | – |
| P(top-1,000) against a modeled field | the simulated 0.12 % tail | finish −0.030, points −8.7 (098) |
| P(top-100) | the simulated 0.012 % tail | finish −0.035, points −10.5 (098) |
| ordering by simulated q99 | the 1 % tail per lineup | K30 −6.8 (096 descriptive) |
| learned ridge (fit on 2023–24 realized tails) | a learned tail score | K30 −2.8, 2022 −17 (096) |
| heavier QB stacks (sim q99 184 → 207 from 2 to 5 players) | simulated tail | realized ≥200 share flat or lower (post-mortem §3.3) |

Expected-max is the most robust selector tested because it integrates over the whole simulated distribution, where
the simulator is calibrated; every objective that conditions on the simulated extreme inherits its over-prediction
(3× at 200+) and its mis-ordering (deep stacks). This is the deepest result of the week: **it is a statement about the
simulator's tail ordering, not about selectors**. The post-mortem's "the simulator is calibrated" holds at the
marginal and the perfect-lineup level and fails at the level that matters for retrieval — which candidate, among
many with similar means, will realize the tail. That is the one modelling question left open by the ledger, and
Addendum 95's reopening condition allows it as an "adopted new dependence model" only under a preregistration frozen
before outcomes are seen (§4, item 3).

### 2.4 The one unpriced error is availability, and it is specific

PREREG-100's player-level look: Questionable players who did not practise fully deliver −2.9 (limited) to −5.9 (DNP)
points below projection with zero-point rates of 25 % and 47 %; Doubtful players are effectively out (99 % zero);
undesignated limited or missed practices deliver in full with *higher* 20+ rates than clean players (rest days for
studs). The shipped vetting rule demotes 54 of 80 lineups (20 of the first 30) because it treats every one of these
cells as risk; it is null on the proxy with raw +0.84 at K30 and 13 vs 5 weeks over 194 at K30. Keeping it costs
nothing measured; a narrower, stronger rule (cap exposure to Q_dnp / Q_limited, ignore none_dnp / none_limited) is
the obvious follow-up and must be tested before it touches an entered book.

### 2.5 Finish, contests and money

Week 1's settled fields give the thresholds a book must clear (official points): Millionaire top-1,000 228.2, top-100
244.8, cash 165.5; Play-Action top-1,000 213.4; the 5,000-entry qualifier top-100 205.3 and paid line 171.1. Against
history at K80 (PREREG-097, 72 weeks): the book's best clears 187 in 26–31 weeks, 194 in 20–21, 200 in 10–16, 210 in
1–7, 220 in 1. A 200-point book wins nothing in the Millionaire and finishes in the top 100 of a 5,000-entry qualifier.
Nothing measured this week moves the 220 rate; several things (dose, vetting) move the 194–210 rate. The bankroll
consequence is unchanged from the post-mortem's option 2: play where 200 pays. The operator's DK history (ROI ≈ −83 %
on large GPPs across six seasons) is the baseline any plan must beat; the finish-objective idea that would have
changed the Millionaire arithmetic is now closed (098).

## 3. What this says about the problem

A lineup fixed at lock scores 220 when five or more of its nine players have top-decile games the same week. The
machine samples the right players (perfect-lineup skill players are 84 % top-quartile projections), generates such
lineups at a known rate per solve, and cannot tell in advance which of its candidates will be the one — because the
simulator that ranks them is right about means and about the shape of the extreme, but not about *which* joint
outcome carries it. Everything measured since Sunday is consistent with that single sentence: dose works on supply and
saturates on the book; admission, vendor data, learned scores and finish objectives reshuffle the same
uninformative ordering; the only measurable player-level error is availability, which is not a tail question at all.

Two things follow. First, the points program has exactly one modelling lever left — the tail ordering of the world
model — and it must be tested as a preregistered calibration study, not as another selector. Second, the money
program does not need that lever to be positive: the book already clears 194–200 in a fifth to a quarter of weeks,
which is a paying outcome in the right contests.

## 4. Suggested next steps

1. **Week 2 (no money-path change).** Dose 3,200, expected-max K80, vet_book as shipped, scratch protocol (remove only
   DK OUT/IR or official inactives), contests as the operator chooses with the Millionaire count reduced (§2.5).
   Thursday: fill `contests.json`, rehearse on draft group 153428 at dose 3,200, arm the timers. The host DK loop
   must stay running on whichever machine is on.
2. **PREREG-099 (running).** Read Thursday. DOUBLING → generation is not the constraint and a 12,800 Sunday build is
   a cost question for a later week; SATURATING → the dose ladder is closed at every budget and the 220 program must
   change what is generated.
3. **Tail-calibration preregistration (draft for sign-off: `reports/2026-09-16-prereg-tail-calibration-DRAFT.md`).**
   Fit, walk-forward by season, a reweighting of the simulator's worlds so that the pooled lineup-level exceedance
   rates at 187/194/200/210 match realized rates on prior seasons, then select with expected-max under the weighted
   worlds. Endpoints: retrieval (does the weighted ordering rank the realized top lineups higher: AUC of realized
   ≥ 194 among candidates) and the ledger's K80 proxy. This is the one remaining modelling lever; it respects
   Addendum 95's reopening condition because the weights are fitted on earlier seasons only.
4. **Questionable-exposure cap preregistration** (from PREREG-100 look 1): cap Q_dnp / Q_limited exposure in the
   K30 prefix, drop the none_dnp / none_limited weights; test on fresh banks before any entered book.
5. **Close and do not reopen**: finish-objective selection on simulated top-N (098), learned pool selectors (096),
   paid-data renewals (ladder + cap), admission-cap changes, deeper stacks, late swap. The immutable FP×SIS chain stays
   abandoned; the direct runner is the instrument if a prospective source shadow is ever wanted.
6. **Bankroll framing.** Every proposal from here is stated in expected finish against a named field size, not in
   points; a cash-game / double-up shadow (the calibrated mean is the system's real strength: 61 % of entries above
   the Millionaire median, 25 % above the cash line) is a candidate to measure on paper for two weeks before money.
7. **Infrastructure.** Keep the DK pulls on the host (the 403 is on Google's network broadly, so Cloud NAT is not
   expected to help); the operator installs a user timer if the loop should survive reboots; the focused Cloud Build
   lane stays the production build path until the policy-drift tests are repaired.

## 5. Decisions only the operator can make

- Contest mix and entry counts for Week 2 (my advice stands: one Millionaire entry, the rest in the small fields).
- Whether to spend ≈ $250 of lab compute on PREREG-099 (launched on the "I'm interested in #3" instruction; cancel
  by killing the launcher and the two executions if not wanted).
- Sign-off on the tail-calibration preregistration before it is frozen.
- Whether the program's goal is "routinely 220+" (not reachable by any tested method at 30–80 entries) or "positive
  ROI at the entered volume" (reachable in contests where 200 pays, on this week's evidence).
