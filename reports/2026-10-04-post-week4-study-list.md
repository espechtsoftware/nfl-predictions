# Post-Week-4 study list (operator requests, 2026-10-04)

**For:** the operator (priorities) and the reviewer (designs). **Standing rule (operator 10-04):** "anything that I say I
want added to the list" goes here without confirmation. Nothing on this list changes the money path until it is
preregistered, run, and the operator adopts it (adoption track v2; money-path rule: tested before an entered book).
Detail and the reviewer's binding design notes live in the HANDOFF entries cited.

| # | Study | Operator's words (abridged) | Key facts so far | Design notes | HANDOFF |
|---|---|---|---|---|---|
| 1 | **Entry-level player exposure cap** | "the percentage of lineups we have for a player… consider restricting that further" | Cap is 50% of 105 book rows; the head layout's repeats push entries higher (Chase 74/152, JAX stack ~61%) | Two arms: assignment cap vs entry-weighted book constraint; measure the downside (worst decile, zero-cash week, one-player-bust), not only EV; term fixed; L25/L26 harness, 107 books | abae10d8, db12a754 |
| 2 | **Use quality: spend capped exposure on a player's best uses** | "a preference of the way that they're used so that ideal uses are taken over just any random use" | Today: a sequential best-first fill | Arm 1 = joint MILP with the same objective (no new scoring); arm 2 = frozen-weight use score; ≤ 2×2 with study 1 | 6121d759, a3792215 |
| 2a | — how Millionaire leaders use popular players | "how those players are selected by the winners or the leaders in the major contests" | 2026 Milly fields in BigQuery (with user names) | Descriptive; defines arm 2's score only; never fitted and tested on the same weeks | 27c8ef65 |
| 2b | — position/environment/ceiling selection (RBs, cheap enablers) | Skattebo "never really puts up points"; Wicks "another mediocre player… be pickier… if a game is going to be a shootout" | Skattebo 28/110 rows (steady ~12, p90 ~28); Wicks 34/110 (a $4,300 enabler); neither from a shootout | Environment and ceiling inside arm 2, all positions | d5dec828, 4d7b5f98 |
| 3 | **Injury risk** (active-Q players; injury-prone players) | "if a player is injury prone… listed as questionable… we discount them somewhat" | Flowers: Q haircut kept him out of every large pool (0 of ~24k), 14.5 at T-70; FP 17.0 | Calibration first; DIFFERENTIAL risk only (average risk is already in the projections); the injury lock-filter (O-22) fixed before the feature SQL | 6121d759, a3792215, 37ce0842, 9bbcb766 |
| 4 | **Chase-injury study** (this week only) | "how badly that is hurting me, and if we should have been smarter about how we used him" | 75/154 entries carry Chase (concussion, in-game) | Exact damage plus hindsight-labelled paper rebuilds; the decision basis stays study 1/2 | b6962b19, 580300f6 (Mon 13:47) |
| 5 | **Shootout calibration** | "be critical of the games that we're calling a shootout, whether they actually turn out to be shootouts" | — | Totals and spreads vs realized points (nflverse history + 2026); the hit rate of "shootout" calls | d5dec828 |
| 6 | **Odds-feed trust** | "whether we can trust the odds data that we're being provided" | Props are 55% of every projection | PROPS FIRST (coverage, book/line type, staleness, ruled-out players, mapping); game lines vs our snapshot at matched times | d5dec828, c00ab62d |
| 7 | **Defense (DST) projections and exposure** | "the Bears' defense is once again doing quite well… why we weren't considering them" | DST projections 2026 W1–3: corr 0.27, MAE 4.3, bias −0.5; MIN under by 7/wk, LV 5.3, CIN 3.8; Bears 6.8/6.7/6.2 vs 6/7/12 (7th this week, 6 rows) | Candidate inputs (pressure, opp QB turnover rate, opp OL injuries, opp implied total, weather), scored the usual way; DST exposure spread vs concentration (ties to study 1). **Prior evidence (reviewer):** the served DST projection's rank skill on the panel is Spearman 0.32, positive on 36/36 slates, and the "flat DST valuation" lead is CLOSED (`reports/2026-09-29-review-of-the-35-answers-and-the-week4-actions.md` §3; `lab-handoffs/2026-09-29-ownership-term/09_dst_rank_skill.py`). New inputs are tested against that 0.32 baseline; never re-propose flattening. 2026 W1–3's 0.27 (3 slates) is within the panel spread, not evidence of a decline | 79155b31 |
| 8 | **DraftKings opponent rank (OPRK)** | "DraftKings opposing rankings and how well those predict the outcome of the game. It seems we go contrary to that sometimes" | Week-3 post-mortem: OPRK's correlation with our residual was −0.05 to −0.14 by position (one slate); OPRK is NOT ingested anywhere (the DK client drops it) | Start capturing OPRK pre-lock each week (the DK draftables attribute, point in time; history only from capture onward). Measure: OPRK vs realized points; OPRK vs OUR residual (does it add information beyond our projection?); how often and where we contradict it, and who was right. A candidate feature only after a support census and a preregistered test. Capturing it changes the DK ingest client, so it gets a review before going live; point-in-time history starts at the first capture (plus any pre-lock draftables snapshots already on disk, e.g. Week 3's 10:51) | c4431677 |
| 9 | **What predicted booms and busts** (residual attribution) | "when a player does well, what data points predicted it, and when they didn't do well, which data points predicted it… put together the correlations that are more important" | Prior: the Week-3 vendor-signals audit (`reports/2026-09-27-week3-vendor-signals-audit.md` §2) screened vendor columns against residual = fpts − proj on ONE slate: hits only marginally above a permutation null (P = 0.048), all in the WR/TE per-route-efficiency cluster (e.g. 2025 YPRR vs cover-6, partial ρ 0.30) | Extend to every 2026 week (and the historical panel where the inputs exist): targets = the residual vs our projection and boom/bust labels (top/bottom decile vs projection, by position). Point-in-time inputs only, EXCLUDING the O-21/O-22 leaky features until fixed. Multiple-testing control (permutation null, as in the audit), walk-forward by season, and hold-out confirmation before anything counts. Output: a ranked, validated list of inputs that predict over/under-performance; the survivors become preregistered feature candidates. It feeds studies 2b, 3, 7 and 8. **Operator addition:** "I don't only mean the data points that we currently use. I want the data points that we capture… we're not using all the fantasy points, SIS data." So the candidate set is EVERY captured source, not only model features: all FP tables (Data Suite advanced receiving/rushing/QB/OL/defense, route share, PROE, XFP, weighted opportunity, bell cow, coverage matchups, rankings, DFS projections and ownership, article mentions) and all SIS tables (team pass/rush defense, pass rush, busts, alignment, receiver copula, team run context), plus Odds API props and OPRK once captured. The B4/D1 map (`reports/2026-10-03-b4-audit-d1-overlap-map.md`) is the inventory: FP's own XFP/Bell Cow/weighted opportunity/PROE and all SIS tables are captured but read by nothing, so this study is where they earn a place or not. The SIS week-1 value-metric revisions (all 32 rows changed within 3 days) must be handled point in time. **Reviewer's guard (binding):** (a) explore on one block of weeks, then a frozen short-list (at most 5 fields, chosen by a rule written beforehand) confirmed on DIFFERENT weeks or the historical seasons where the field exists; (b) report the exploration with a Benjamini–Hochberg false-discovery adjustment and the count of fields tried; (c) only a confirmed field becomes a feature candidate, which then goes through the six-season test; pre-lock values only (post-lock vendor revisions are the leak class just found) | e805e08e, 3e78db9d |
| 10 | **Field-behaviour model** (learn how the field builds lineups) | "Are we training any models using the data from this season… to analyze stuff that we can't get from other sources?" → "Yes." | About 1.49M real contest lineups (nfl_raw.contest_entries, W1–3, growing weekly) train nothing. Models that do use 2026 weekly: the projection model (retrained with each week), the lag ownership model (prior weeks' realized Milly ownership), TabPFN ownership (2026 rows; now unreachable without LineStar), the class model (W1/W3 cashing patterns) | Learn, point in time, how the field constructs lineups for a slate: player ownership, stack/pair frequencies by game environment, salary left, duplication rates, reaction to news and price. Validate week-ahead (train on weeks < W, predict W). Uses: the ownership term, the field sleeve, P8's duplication-aware EV, study 2a. Outcome-blind where it is about construction (it needs only lineups, not scores) | this commit |

**Agent-proposed studies (10-04, at the operator's request):** see `reports/2026-10-04-agent-proposed-studies.md`.
- **P1:** contest-type edge vs stake.
- **P2:** market vs model blend, plus pick'em coverage.
- **P3:** a weekly simple-baseline benchmark.
- **P4:** spread dealing.
- **P5:** quantile calibration by position and tier.
- **P6:** simulator coupling repair.
- **P7:** market-anchored Q at T-70 (folds into 3).
- **P8:** field/duplication-aware EV.
- **P9:** E0 recoverable regret.
- **Audits:** A1–A4.


**Completely different approaches (operator 10-04: "think completely outside of the box…"):** see
`reports/2026-10-04-different-approaches.md`.
- It builds on the 09-25 round (R1–R19): sponsor R17 as study 10; start the R14 LLM fact log; keep R6/R7/R12.
- **New:**
  - X1 scenario arbitrage;
  - X2 field-softness index;
  - X3 a method portfolio with online allocation;
  - X4 the operator-signal log;
  - X5 frequent-pattern mining of winning combinations;
  - X6 a public-attention ownership signal;
  - X7 an LLM lineup critic (long shot);
  - X8 a GNN (long shot);
  - X9 a scenario-spanning corpus (conditional on X1).


## Approved plan (operator 10-04: "Lets plan on all of that")
This covers the operator's studies 1–9 and the agent's revised proposals (`reports/2026-10-04-agent-proposed-studies.md`
@ df811723). Every item is preregistered with the reviewer before outcomes are read, and nothing touches the money path
without a test and the operator's adoption.

| When | Work |
|---|---|
| Mon 10-05 | The Monday order (O1/A3/B2 readers, the unchanged comparison, the dashboard publisher dry run); the Chase study (4) |
| Tue 10-06 | LineStar revision check (then retired). **A2** OPEN-DEFECTS register review (close or re-date with evidence). **A4** Week-5 deadlines (O-3 pass-tail schedulers; plan for the O-22 retrain) |
| Wed 10-07 | **P1** contest-type edge: payout-ladder table, then the power analysis first (Add. 95 item 5). **P3** simple-baseline benchmark: paper toggles on `union_paper_rebuild.sh`, scored on tickets and line hits by contest class |
| Thu–Fri 10-08/09 | The O-22 feature fix (as-of), the leakage checks, the retrain, the six-season co-run; the lock-filter item first (top_cb_out, team_ol_out). **A1** DST/11-01 audit. **A3** weekly ownership grading storage |
| Week 5 Mon 10-12 | O1 interim; first P3 weekly read; Week 5 shadow B (no-cpoe/neutral-pass paper) |
| Week 5–6 | Preregister: study 1 (+ the P4 offset-dealing arm, built first) with study 2 (≤ 2×2); study 3 + P7; the P2 prelim re-run on the retrained model (a conditional bias correction only if the asymmetry survives); studies 5–6 (shootout calibration; odds trust, props first) |
| Week 6–8 | Studies 7 (DST inputs vs the 0.32 baseline), 8 (OPRK capture, after review), 9 (boom/bust attribution with the BH guard), P5 (quantile calibration), P9 (E0); automation phase 1 (week manifest) |
| Later | P8 (field/duplication-aware EV, priced outcome-blind first) |
| Closed | P6 (simulator coupling: three prior families null/negative; facts recorded) |

**Already scheduled (not studies):** Monday 10-05 (O1/A3/B2 readers, the unchanged comparison, the dashboard publisher
dry run); Tuesday 10-06 (LineStar revision check, then LineStar retired); O-21/O-22 fixes (features, leakage checks,
Addendum-32 re-run); the build automation design (phases from Week 6).
