# Project briefing for a new model: NFL DFS on DraftKings, state after Week 1 of 2026

Written 2026-09-14 (Monday after Week 1) for a model joining the project cold. It covers what the system is, how work
is validated here, where the science stands, what happened in Week 1, what was measured afterwards, and the one test
that is open. Everything quantitative below is from a committed report or a frozen ledger entry; paths are given so the
claims can be re-derived. Read `HANDOFF.md` (newest entries at the top of the recent block) before doing any work: it
is the authoritative record and this document does not replace it.

---

## 1. What the project is

**Goal.** Enter DraftKings NFL Classic tournaments (the Sunday main slate, 12:00 CT lock) with a small book of lineups
and produce, most weeks, at least one lineup near the top of the field. The operator's stated target during Week 1 was
"one lineup scoring 220–230"; this document explains why that target is now understood to be the wrong axis (§7).

**Two repositories, two GCP projects.**

- **Production** (`~/projects/nfl-predictions`, GCP `nfl-predictions-503414`): the data warehouse (BigQuery datasets
  `nfl_raw`, `nfl_features`, `nfl_predictions`), daily Cloud Run jobs (`ingest-nflverse`, `ingest-dk`,
  `build-features`, `project-slate`, …, on `s-*` schedulers), the point-in-time feature panel
  (`nfl_features.player_week_training`, windows end at `1 PRECEDING`; the leakage checks in `features/leakage.py`
  must pass on every build), the projection models, the FastAPI app (`nfl-dfs-app` on Cloud Run, behind IAP), and the
  research ledger `reports/2026-07-25-system-study.md` (120 addenda) plus one report per experiment under `reports/`.
- **Lab** (`~/projects/nfl2`, GCP `nfl-2-506823`): a fast experimentation repo with its own simulator/optimizer
  pipeline, `PREREG-0NN.md` preregistrations, a `LEDGER.md` (rows only with the frozen reader's verbatim output), and
  two shared Cloud Run jobs (`lab-run`, `lab-run-slow`) driven by registered host launchers. The Week-1 money path
  (`scripts/live_week.py`) lives here; production centres its projections (`NFL2_LIVE_CENTER=production`).

Work happens in git worktrees, one per task or cohort, e.g. `~/projects/.nfl-predictions-worktrees/week1-audit-adjust-20260912`
(production, branch `production/week1-audit-adjust-20260912`) and `~/projects/.nfl2-worktrees/prereg097-dose6400-20260913`
(lab). Never commit to a lab cohort branch while its launcher is armed: launchers pin `CODE_SHA == HEAD`.

**Data.** nflverse (rosters, injuries, schedules, weekly stats; the daily job currently errors on a missing FTN 2026
file after rosters/injuries load), DraftKings public endpoints (draft groups, salaries, statuses, lobby), prop lines
from sportsbooks (`nfl_raw.prop_lines`, pulled several times a day; DK-implied points per player are the "market"
signal), Fantasy Points Data Suite exports (route data; the ownership product is NOT in the operator's plan), SIS
charting (operator subscribes; in-season pulls start at week 5), the operator's own contest history, and — as of this
morning — DraftKings' full contest standings (every entry's lineup and points, plus per-player ownership), loaded for
the first time into `nfl_raw.contest_entries` (831,028 + 158,302 + 4,998 entries) and `nfl_raw.contest_ownership`
(which also holds 2022–2025 per-player ownership for 72 weeks, without lineups).

**How a Sunday book is built (the adopted policy).** Per slate: a player frame (salaries, statuses, features, market
points, production projection as the centre) → two simulated banks of 10,000 worlds per player under two laws (the
incumbent simulator and a corrected "hsim" law; the simulator is a calibrated ensemble with game/team/player
dependence) → candidate generation: 160 "lev" lineups (MILP on the tournament projection with overlap cuts) plus 640
"boom" lineups (the optimal lineup in each of 640 simulated worlds) = the **D800 pool** → scoring of every candidate on
the identical dual decision matrix → greedy **expected-max** selection (`select_expected_max`, "DEMAX") of an exact
K=80 (or K=90 nested) book: each pick maximises E[max over the book] across worlds, which makes the order a
diversification order (the realized best lineup sits at median rank ~38, not 1). Construction rules: QB + 2 same-team
pass catchers + 1 bring-back, salary floor 49,000, cap 50,000, DK roster shape. A governed publisher
(`publish_week1_a5_books.py`, create-once) records the paid P_MIX/P_CTRL D800 K80 books; the K90 nested book (ranks
1–80 = the paid K80) is the operator's upload set.

---

## 2. How work is validated here (read before proposing anything)

The ledger has a strong culture, learned expensively:

- **Preregister, freeze, read once.** Every lab cohort has a `PREREG-0NN.md` frozen before launch: construction, arms,
  primary endpoint (the paired GLOBAL_WEMAX_PROXY, a winner-cdf utility of the bank-averaged weekly K80 maximum),
  decision rule (season-clustered bootstrap, family level 1−0.05/k, PASS iff the interval's lower bound > 0, every bank
  ≥ 0, ≤ 1 negative leave-one-season-out estimate), consequences, mechanics gate. Three banks (random seeds) of 72
  development slates (2021–2024, 18 per season). Readers run once; rows enter `LEDGER.md` with verbatim output.
- **Walk-forward only, never random splits; six-season or 72-slate panels; co-run controls on the same image.**
- **Audit before verdict.** Several early "results" were retracted after code/instrument audits (a mislabelled fade, an
  env typo, season pooling). Before accepting a negative: prove the lever moved, is not inverted, and aims at the
  functional the gate scores.
- **220+/230+ counts are reported and never a pass.** The tail is too rare to gate on.
- **Point-in-time is sacred.** Never weaken a leakage check to make a build green.
- **Never touch an entered book with an untested rule** (added 2026-09-13 after it cost the week; §5).
- **Cloud Run discipline.** us-central1 production sits at the jobs quota: reuse jobs, never create per-run jobs.
  Lab launchers go through `scripts/launcher_registry.sh` (single-writer lanes); ≤ 2 non-terminal executions across
  the two lab jobs; `maxRetries 3` because the platform loses ~5–10% of tasks with "Internal error"; repairs re-run
  exactly the missing slates and readers union main + repair shards (the `--repair` pattern).
- **The classifier in this harness refuses some actions** (create-once publishes with `--execute`, systemd unit
  writes, some greps): hand the operator the one-line command instead of retrying.

---

## 3. Where the science stands (the ledger, condensed)

Adopted and replicated: the D800 dose over D400 (+1.2 points, PREREG-047); a naive-ownership chalk fade in the
objective (+2, twice); QB+2+bring-back construction; the $49k salary floor; tournament-only "proj_tourney" objective;
dual-law scoring; the greedy expected-max selector (solves its objective to within 0.13%).

Closed after preregistered tests (each ≤ +2 points or negative): every alternative generator family (GFlowNet, Gumbel,
hierarchical Gumbel, cross-entropy, Schaake, TD coupling, role-belief); dependence rewrites (learned conditional
templates, coherent member worlds — better average dependence, worse joint tail); selection alternatives (LSE, sharp
LSE, QB concentration, dollars objective, decision-focused reranker, novelty ladder, union e-max, coverage-194/220);
the 1600 dose (null/unresolved in three cohorts); within-book orderings (24 shadows, ±1.7); skill-salary floors;
learned lineup scores as selector (PREREG-096, §6.5); late swap (§6.6); deeper stacks (§6.3); player filters (§6.7).

The one monotone lever: **dose**. Candidates at 220+ per slate-bank: 0.14 (800) → 0.25 (1600) → 0.50 (3200); pool
oracle 195 → 199 → 204; K80 weeks with a 220+: 0 → 0 → 2 of 72. The 3200 rung passed the family gate against 800 in two
cohorts (PREREG-093 +0.00898, PREREG-095 +0.01041); the 6,400 rung (PREREG-097) is running now (gate passed
2026-09-14 04:31Z; banks launched 11:20Z).

Verdicts to internalise: *selection is closed for the current simulator and static feature set* (Addendum 95); *the
tail target is supply-bound*; *the live capture paths are more entries and genuinely new information*.

---

## 4. Week 1 timeline (2026-09-12/13), including the mistakes

- **Saturday.** Overnight cohorts (090–092, 094) read: no adoption; retrieval binds above 800. A production defect was
  found and fixed: `upcoming_slate_features` selected the DK draft group by `MAX(game_start)` and pulled a stale
  full-week group, so 57 already-played-team players entered the pool; fixed to `MIN`, regression test added,
  image deployed. Historical fact: $200 placeholder salaries existed in two player-weeks (deficiency logged).
- **Sunday morning.** Operator decision: play 30 entries instead of 90, across the same four contests (Millionaire
  $5, Play-Action $5, two FFWC qualifiers $18/$5), by importing 90 and withdrawing 60. A day of ordering
  experiments (§6.4) at the operator's request; a learned lineup score (ridge on 66 lineup features, LOSO) looked
  strong on a 200-candidate Neo4j corpus (+6 at K30) and the operator chose to use it; a same-morning cloud test at the
  real dose (PREREG-096, one bank, 72 slates) came back **−2.8 at K30**, so the entry reverted to the machine's
  vetted top-30. Lesson: a pool-level selector must be tested at the generator's real dose.
- **Reserved entries.** DraftKings edits reserved entries only through its own entries export (Entry ID, Contest ID,
  QB…DST); no authenticated API exists in the system (the September-9 "capture" was a one-shot DevTools read through
  the operator's browser). Tooling now fills that export positionally (`scripts/week1_fill_dk_entries.py`) and a
  watcher re-fills it when the lineups change. Withdrawal was impossible on the two full contests, so 80 entries went
  live (Millionaire 57, Play-Action 20, qualifier 3).
- **The 10:50 CT rebuild ("T-70") used a 10:04 CT salary pull and missed the 10:30 inactives** (77 newly OUT players,
  24 of them in the pool). A final build on the 11:02 pull replaced it at 11:04. Runbook fix recorded. (The original
  T-70 task had also survived a process scan that said it was dead, so two identical builds ran concurrently; no
  harm, identical books.)
- **Pre-lock scratches** (Bateman, Downs, Warren, Wicks) and one late-window scratch (McCaffrey) were swapped on
  request with the best-projected active same-position player fitting the lineup's salary.
- **The decisive mistake.** The operator asked for a "proven scorer" rule (drop RB/WR/TE without a 20+ DK game in
  the prior year); I built it as an optional file with a caveat instead of testing it first, and the operator entered
  it. It removed Jalen Coker from the lineups that would have cleared 200. Tested afterwards on 72 slates: −10 to −15
  points at K30. Standing rule now: no filter on an entered book without the 72-slate test.

---

## 5. Week 1 results, official (DraftKings exports, loaded 2026-09-14)

| contest | entries | winner | top-100 cut | top-1,000 cut | cash line | our best (rank) |
|---|---:|---:|---:|---:|---:|---|
| Millionaire | 832,342 | 273.98 | 244.8 | 228.2 | 165.5 (top 20.8%) | 192.08 (34,838) |
| Play-Action | 158,541 | 263.84 | 232.2 | 213.4 | 168.1 | 196.24 (4,872) |
| FFWC Qualifier 7 | 5,000 | 260.00 | 205.3 | 171.1 | 260 paid | 153.72 (2,093) |

Fees $399, winnings $140, 18 of 80 entries min-cashed. Every book and shadow scored on official player points
(`reports/2026-09-14-week1-field-winners-settlement.md`):

| book | best | best of first 30 | ≥ 200 |
|---|---:|---:|---:|
| entered (proven-scorer rule) | 196.24 | 182.0 | 0 |
| the same book without the rule | 224.54 | 203.8 | 2 |
| **the machine's vetted top-30, both builds** | **226.64** | **226.64** | 2 |
| learned-div5 / blend-div5 shadows | 228.5–228.8 | up to 228.8 | 3–6 |

The system's own book contained a lineup at about rank 1,100 of 832,342; the entered version did not. The winner
(Steelers DST, Swift, Love, Gibbs, Henry, Goedert, Watson, DJ Moore, Coker) is four top-quartile studs at 30+ and a 7%-
owned receiver from the 59–37 Chicago–Carolina game — precisely the perfect-lineup anatomy of §6.2.

The operator's own history, from the same export: 1,063 NFL entries since 2020, $8,704 in fees, $1,456 won, ROI about
−83% every season, all in top-heavy tournaments. Any proposal must be framed against that baseline in expected ROI,
never in points.

---

## 6. What the post-mortem measured (all on 2026-09-13/14; reports listed in §9)

1. **The simulator is calibrated, including at the extreme.** Its per-world perfect lineup (max over all legal
   lineups on simulated points) averages 258; the realized perfect lineup averages 267 over 72 slates (200–331),
   always inside the simulated range. Real outcomes exceed the simulator's own 99th percentile 0.70% (incumbent law)
   / 0.97% (hsim) of the time; it over-predicts P(≥200) by 3×. There is no hidden fat tail to model.
2. **What a 220+ lineup is.** Perfect lineups have 4.2 players at 30+, 6.6 at 25+, are barely stacked (QB stack
   0.8), spread over 6.7 games, use $49,283. 84% of their players are top-quartile projections within position, 97%
   top half; 90% of the 30-point games come from top-quartile players; 18% of slots are players with no big game in
   the prior year (47% of their sub-$4,000 players). Who booms is predictable; when is not.
3. **Deeper stacks hurt.** Stack size 2 → 5: simulated q99 184 → 207, realized exceedance 0.83% → 0%. The simulator
   over-rewards stacks relative to reality.
4. **Selection works and is still not enough.** Selected lineups reach 220 at 0.10% per lineup vs 0.01% unselected;
   that is one 220 per 80-lineup book every ~12 weeks. 220 is +4.1 s.d. for a lineup fixed at lock (within-slate s.d.
   24.8 around a mean of 118).
5. **Learned lineup scores.** A ridge on lineup features (market points, usage, projection floor, game total positive;
   summed p90, spread, implied total negative) re-sorts the book at +0.6 [−4.5, +6.0] (2024 only) and fails as a pool
   selector (−2.8 at K30 on real 800-pools; +5.7 on a 200-candidate corpus — the transfer failed). Live 3200-pools
   also collapse onto one core under such a score (one player in 97% of lineups) unless exposure-capped.
6. **Late swap does not reach 220.** Re-choosing late slots on the early games' results: +0.7 at K30, +0.2 at K80,
   220-weeks unchanged; only 13 of 80 lineups are "alive" at 3:00 CT.
7. **Player filters fail.** "Every player proven" −10 to −15 at K30 (drops 4 of 5 lineups); "≤ 1 unproven" −0.9;
   "≤ 2" +0.2. The book already carries fewer unproven slots (9–16%) than perfect lineups (18%). None of Week 1's
   duds had injury-borrowed big games (6.4% of all big games are).
8. **The one pre-lock signal with teeth: practice status.** Established players who did not practice Friday, had no
   game designation and then played delivered 82% of their trailing mean with a 36% flop rate (24% baseline); with a
   Questionable tag, 69% and a halved big-game rate. Week 1: Chase (DNP, knee) in 22 of 80 lineups, scored 3.2; the
   winners' top 100 held zero DNP players. Recommended: DNP = material in vetting regardless of posted props, ≤ 10%
   of the book; DNP + Questionable = hard. Not yet implemented; test on the historical books first.
9. **The gap to the winner.** Millionaire winners 2023–24 average 230 (178–296), correlated 0.7 with our own best;
   our K80 best averages 182 (gap 49), our 800-pool oracle 195 (gap 36); our book beat the winner in 1 week of 35.
   The target is the field's weekly maximum, not a fixed score.
10. **The winners' profile (Week 1 Millionaire top 100 vs our book).** Chalkier than us (highest-owned slot 36% vs
    24%; mean ownership 12.9% vs 9.5%), 96% top-quartile projections (ours 91%), same salary, 1.65 stack mates, zero
    DNP players, and three or four low-owned booms (Coker in 92 of 100 at 7%, Swift 8%, Young 3%, Goedert 8%, Henry
    8%). Contrarianism per se was not the edge; the right game and the right cheap receiver in it were.

11. **The manual removals and the cheap slots, scored on official points** (`reports/2026-09-14-week1-swaps-and-cheap-players.md`).
    Removing Bateman (inactive), Downs and Warren (diminished) with the projection-based replacement rule was worth
    +124 points across the book (Vele 19.9, Irving 21.3, Hubbard 23.7, McConkey 19.2). Removing Wicks, who was never
    flagged and scored 15.3, cost −44; the proven-scorer rule cost −130 across the book and 28 on the best lineup.
    Cheap slots (skill players ≤ $5,000): three of 287 scored 20+ on Sunday (Coker 36.8 at 7.5% owned, Goedert 23.7,
    Kincaid 21.0); the plain book held all three, the entered book two. On 27,550 historical cheap player-weeks the
    big-game rate is 1.5% and is strongly predictable from the signals the optimizer already uses — projection top
    quartile 5.0% vs 0.1%, market-points top quartile 8.7% vs 0.3%, starters 7.5% vs 1.3% for third-stringers; a
    leave-one-season-out model reaches AUC 0.84–0.87 with a top decile hitting 12.8% against a 2.7% base (Coker was
    in that decile) — and from nothing else: game total and implied team total carry no lift for cheap players.
    Cheap booms are the projection/market top decile hitting at about one in eight, not "unproven" players getting
    lucky. Protocol from here: a player is removed only when DraftKings marks him OUT/IR or the inactives list names
    him ("replace X" is answered with his live status first); cheap-player risk is controlled by exposure (no single
    cheap player above ~15% of the book), never by history filters; the replacement rule stays.

---

## 7. The structural conclusion and the open question

Points is the wrong axis for this contest. A points-optimal system with 30–80 entries sits 36–49 points below the
Millionaire winner in a typical week and reaches the winner about once in 35 weeks; no lever in the ledger moves the
book by more than ~2 points and dose moves the pool by ~8. That part is measured and closed.

The contest pays *finish*: a lineup's value is its rank in a field whose top end is built from chalk. Every gate ever
run here scored points; the August ownership model passed its calibration and its lineup arm was then dropped by a
points gate ("the money path asks the selector the wrong question" — `reports/2026-08-19-large-field-tournament-
winning-strategy-plan.md`). The finish objective has never been evaluated, and as of this morning the data exists to
evaluate it on a real field.

**The payout retro-test (run 2026-09-14 on the operator's go; `reports/2026-09-14-payout-retro-test.md`).** Selecting
by an estimable finish objective — P(top-1,000) or P(top-100) against the real 831,028-lineup field under the
simulator — picks a materially different book from expected-max (6–12 of 30 lineups in common; 32–37 of 80), with
25–70% higher simulated top-N probabilities, and on the one real week it earned more ($133 vs $71 at K=30 by finding
the 224.54 lineup; $250–274 vs $211 at K=80). Raw expected payout is a lottery objective (the top candidate's $202
comes from 2 worlds in 10,000) and must never be selected on. One week, field known after the fact: a sign, not a
verdict. The historical version needs an ownership-consistent field sampler on the 54 development slates with real
ownership (PREREG-098, built and frozen the same afternoon — next paragraph).

**PREREG-098, the historical finish-objective cohort (frozen 2026-09-14; lab branch
`lab/prereg098-finish-objective-20260914` at 7e8126b; `PREREG-098.md` is the contract).** The question: over the 53
development slates from 2022–2024 whose Sunday Millionaire per-player ownership record joins the lab frame with ≥ 800
of ~900 ownership mass, does choosing the book by P(top-1,000) or P(top-100) against a *modeled* field beat
expected-max on realized finish? Construction, per slate: the D800 pool on the dual decision matrix (as in the money
path), plus a synthetic field of 200,000 lineups drawn by an ownership-consistent sampler (`experiments/
prereg098_field_sampler.py`: roster shape, $50k cap, salary floor drawn in [48,500, 50,000], 0.70 QB-stack
propensity, six rounds of iterative proportional fitting so the sampled field reproduces the week's real ownership).
Per-world cutoffs are the field's scores at the top-100 / top-1,000 / cash *fractions* of an 832,342-entry Millionaire,
so the objective is field-size invariant. Seven arms: DEMAX K80 (control; its first 30 is the K30 control), top-K by
P(top-1,000), by P(top-100), by P(cash), each at K30 and K80. Primary endpoint: the share of the field (scored on
realized points) above the book's best lineup, lower is better, paired weekly and bank-averaged, season-clustered
bootstrap at family level 0.975, PASS iff the interval clears zero with every bank ≥ 0 and ≤ 1 negative LOSO. The
ledger's points proxy runs as a secondary so the result stays comparable with every earlier row. Three banks
(980/981/982), 53 tasks each, launched by `scripts/queue_118.sh` through the launcher registry once PREREG-097
has left both lab lanes (`scripts/arm_118_after_117.sh` waits for that); reader `scripts/prereg098_report.py`.

Findings from the build itself, before any bank has run:

1. *Real ownership joins the lab frame cleanly.* 54 of the 72 development slates have a Sunday Millionaire ownership
   record (2022–2024); matched mass averages 861.7 of ~900 (the remainder is players outside the lab's player
   universe); 2022 Week 16 did not join and is excluded by the frozen ≥ 800 rule, leaving 53.
2. *An IPF-fitted sampler reproduces a real field's cutoff structure.* Gated on the one real field we hold (Week 1):
   per-world top-1,000 cutoffs of the sampled field correlate 0.987 with the real field's across 10,000 worlds; the
   sampled field's realized-points cutoffs land at 226.0 / 163.5 against the real 228.2 / 165.5; ownership error
   sum 0.29 of ~9. The first setting (stack 0.55, floor 47k) was 3.6 points soft at the top; raising the salary floor
   band and the stack propensity closed it (four variants, all recorded in `PREREG-098.md` §Gate; the adopted one
   against the frozen bars):

   | criterion | bar | adopted (stack 0.70, floor 48,500–50,000) |
   |---|---|---|
   | top-1,000 cutoff correlation across 10,000 worlds | > 0.95 | 0.987 |
   | top-1,000 mean absolute cutoff difference | < 3 | 2.63 |
   | realized top-1,000 / cash cutoffs vs real 228.2 / 165.5 | within 5 | 226.0 / 163.5 |
   | ownership error sum | < 0.5 | 0.291 |

   A residual one-signed
   bias of about −2.4 points remains: real lineups are optimizer-built and projection-correlated, so a field that
   matches ownership marginals is still slightly less sharp than the real thing. Because the arms *rank* candidates,
   a uniform shift does not change what is selected; absolute finish probabilities read slightly optimistic.
3. *The finish objective is cheap.* Sampling 200,000 lineups takes ~4 s vectorised (the first Python-loop version
   did not finish in 12 minutes); scoring the field over 10,000 worlds ~65 s. The whole cohort is dominated by the
   800 solves per slate, as every other cohort is.
4. *The K30 and K80 books disagree with DEMAX to the degree the retro-test showed.* In the outcome-blind smoke on
   2023 W1 (80 candidates at 0.1 scale), top-30 by P(top-1,000) shared 20 of 30 with DEMAX's first 30 and carried
   1.6× the DEMAX K80 book's mean simulated P(top-1,000); the same shape as on the real Week-1 field.

What the cohort will not settle: the *live* field must be modeled from projected ownership before lock (the August
contest-aware ownership model is the candidate; its lineup arm was never scored on finish). PREREG-098's
consequences clause therefore nominates the finish objective for Week 2 only as a shadow book plus a projected-
ownership field, never as a straight swap of the paid selector.

**The test as originally proposed:** for each of our 3,200 Week-1 candidates and
each of the 10,000 simulated worlds, score the entire 831,028-lineup Millionaire field in that world, read off the
world's top-100 / top-1,000 / cash cutoffs, convert each candidate's world score to a payout under the Millionaire's
actual table, and build the 30- and 80-lineup books that maximise expected payout. Compare with the expected-max
books on lineup overlap and on what they actually earned. If the books coincide, the finish-objective idea dies
cleanly and the points ceiling is the ceiling; if they differ and would have earned more, the same machinery runs
on the 2022–2025 ownership history with a field model. Two smaller tests ride along: the practice-status exposure
cap on the 72 historical books; whether the Chicago–Carolina explosion was visible pre-lock.

Also on the table, as bankroll decisions rather than model changes: contests where 200 wins (the book reaches 200 in
15–18% of weeks at K80; the same 80 entries would have cashed 61% in a double-up field vs 25% in the Millionaire), and
volume (P(220) scales nearly linearly in entries).

---

## 8. Operational state right now (2026-09-14 14:30Z; superseded by `reports/2026-09-15-week2-operating-handoff.md`, which is the live take-over document)

- Cloud: PREREG-097 (6,400 rung) banks 970/971/972 launching on the lab lanes via the finish launcher (host script
  `/home/erich/week1-sunday/queue_117_finish.sh`, registered; the original launcher died with the workstation
  shutdown and its registry receipt was adjudicated); read this evening with `scripts/prereg097_report.py`
  (repairs: `/home/erich/week1-sunday/repair_bank.sh`).
- Cloud, queued behind 097: PREREG-098 (the finish objective). Image built: tag `prereg09s-7e8126b9b4c1`, digest
  `sha256:d8a02797…` (full line in the 098 worktree's untracked `results/prereg09s_image.txt`). The sequencer
  `scripts/arm_118_after_117.sh` is RUNNING on the host (pid 69162, log `results/arm_118_sequencer.log` in
  `/home/erich/projects/.nfl2-worktrees/prereg098-finish-20260914`): it waits for the 097 finish launcher's
  `action=completed` line in the registry log and for both lanes to be idle, updates both jobs to the 09s image with
  `CODE_SHA` = 7e8126b, and arms `scripts/queue_118.sh` through the registry (mechanics execution `118m980r1` →
  `scripts/prereg098_mechanics_gate.py` must PASS, or the launcher dies → banks 980/981 → 982, 53 tasks each; launcher
  log `results/queue_118_launcher.log`). Read once with `scripts/prereg098_report.py RUN980 RUN981 RUN982`; the LEDGER
  row carries the reader's verbatim output; then update §7 here and `reports/2026-09-14-payout-retro-test.md`.
  Do not commit to the 098 branch while the launcher is armed (the `CODE_SHA == HEAD` guard). If the workstation is
  shut down before 097 finishes, both the 097 launcher and this sequencer die: adjudicate the 097 receipt as before,
  then restart the sequencer with the tag and digest from `results/prereg09s_image.txt`.
- Warehouse: Week-1 full fields loaded; Week-1 player stats arrive with the nflverse job (which still 404s on FTN
  after loading rosters/injuries — fix the tolerance).
- Branches, all pushed and clean: production `production/week1-audit-adjust-20260912`; lab
  `lab/prereg098-finish-objective-20260914`, `lab/prereg097-dose6400-20260913`, `lab/prereg096-learned-pool-20260913`, `lab/prereg090-amend4-20260912`
  (LEDGER rows for 093/095/096 with transcripts).
- Host artifacts (untracked): `/home/erich/week1-sunday/` (tools, ENTER/, ENTERED/ with the operator's entry export
  — entry keys, never commit), `results/2026-09-13/` (the standings exports).
- What follows, in order: (1) 097 banks terminal → `scripts/prereg097_report.py` from the 097 worktree, LEDGER row;
  (2) 098 banks terminal → `scripts/prereg098_report.py`, LEDGER row, §7 update; its consequences clause nominates the
  finish objective for Week 2 only as a shadow book with a projected-ownership field, never as a straight swap of
  the paid selector; (3) the Week-2 runbook and vetting items below.
- Runbook fixes queued for Week 2: reserved-entry fill in the Sunday script; withdrawals not assumed; T-70 salary pull
  after the 10:30 inactives; scratch-swap tool live 11:00 CT → late window; practice-status cap in vetting; no
  untested filter on an entered book.

---

## 10. The build process (how a week is produced, end to end)

### 10.1 Production cadence (Cloud Run jobs on `s-*` schedulers, `nfl-predictions-503414`, us-central1)

| when (CT) | scheduler → job | what it does |
|---|---|---|
| daily 08:00 | `s-freshness` → `check-freshness` | feed freshness receipts; the app's status reads these |
| daily (after nflverse publishes) | `ingest-nflverse` | rosters, injuries, schedules, weekly stats; currently exits non-zero on the missing 2026 FTN charting file *after* rosters/injuries load — weekly stats for the just-played week must be verified on Monday/Tuesday |
| Tue 06:30 | `s-features` → `build-features` | the point-in-time panel `nfl_features.player_week_training` (+ leakage checks, must pass) |
| Tue 08:00 | `s-score` | scores last week's projections |
| Tue 08:30/08:45 | `s-train-k1`, `s-train-k1-role` (PAUSED) | weekly model retrain (paused; the adopted models are frozen) |
| Wed 11:00 | `s-trends` | trend tables |
| Wed–Sat 10:00 | `s-contests` → `ingest-contests` | lobby contest list, fill/overlay snapshots (`nfl_raw.dk_contest_fills`) |
| Sun 05:30–10:30 hourly | `s-features-sun` → `build-features` | refreshes the panel with the latest injuries/rosters |
| Sun 06:00–11:00 hourly | `s-contests-sun` → `ingest-contests`; `ingest-dk` (salaries, DK statuses, draft groups) and `project-slate` also run hourly on Sunday morning (07:00–11:00 CT executions observed: 12:00Z … 16:00Z) | the 11:00 CT `ingest-dk` is the first pull that carries the 10:30 CT inactives; the 11:00 CT `project-slate` regenerates projections on it (~4 min) |
| Sun ~09:45/10:45 | `s-shadow-cbwu-oi-paired-*` (ENABLED), other `s-shadow-*` (PAUSED) | outcome-blind shadow books for settlement |

`project-slate` writes `nfl_predictions.player_projections` (proj_points, p10, p90, std, ownership placeholder) keyed
by `generated_at`; every consumer reads the latest `generated_at`. Its slate selection is the DK draft group whose
*earliest* game has not started (`MIN(game_start)`; the Week-1 fix — `MAX` picked a stale full-week group).

**Deploying a production job.** `gcloud builds submit` from a clean worktree with the repo's `cloudbuild.yaml` (a
contract regex checks the config), image `us-central1-docker.pkg.dev/nfl-predictions-503414/nfl-dfs/nfl-dfs:<tag>`
(Week-1 tag form `week1-live-<sha12>`), then `gcloud run jobs update <job> --image <tag@digest>`; record the job
generation and digest in HANDOFF. Never create per-run jobs (the project sits at the 1,000-job quota; the job list is
full of frozen analysis jobs). The app (`nfl-dfs-app`, IAP) runs its own older digest and reads the warehouse live.

### 10.2 The Sunday money path (host workstation, armed by `nfl-week1-sunday-build.timer` at 09:10 CT; T-70 at 10:50 CT)

`/home/erich/week1-sunday-build.sh` (tracked copy: production `scripts/week1_*`; lab money path in
`~/projects/.nfl2-worktrees/week1-live-center-e7255e9`, commit e7255e9, `NFL2_LIVE_CENTER=production`):

1. **Runbook pair** — `scripts/week1_sunday_runbook.sh --run-id <tag>` builds the governed D800 paid book (lev 160 /
   boom 640, K80) and the D400 shadow through `live_week.py`, runs the publisher **preflight** (four distinct book
   hashes, P_MIX turnover ≥ 1) and prints the operator's 4a/4b commands. ~7 min per build.
2. **K90 nested book** — `live_week.py --season 2026 --week 1 --group <draft group> --selector dual_emax --lev 160
   --boom 640 --sims 10000 --k 1 --seed 2026 --entries 90 --emit-a5-sidecars` (ranks 1–80 equal the paid K80).
   Each build writes an immutable run dir `results/live/2026-w01/<UTC stamp>-<sha7>/` and a `LATEST` marker:
   `book.csv` (DK slot order, dk_player_id), `book.json`, `book_wemax.*`, `candidates.parquet` (the whole pool with
   tags, sim stats, book ranks), `frame.parquet` (the player frame, 140 columns), `incumbent_player_scores.npy` and
   `corrected_hsim_player_scores.npy` (players × 10,000 worlds, float32), `exposure_ledger.json`,
   `universe_ledger.parquet`, `receipt.json` (identity, inputs, DK-status and roster invariants, config, hashes).
   Any RNG-affecting change to the universe re-bases every draw: a rebuild on a different player pool yields a
   different book, not a patched one.
3. **Ordering shadows** (`tools/ordering_shadows.py`, 24 within-book orderings, outcome-blind), **line movement /
   vanished-line veto** (`market_move.py`), **vetting** (`vet_book.py`: DK O/IR/OUT, placeholder salary, vanished
   prop line = HARD; DNP/Limited/Q/D tiers; writes a re-ordered book + `vetting.json`), **composite**
   (`player_score.py`), **hybrid15** (`hybrid30.py`), per-contest draftable-id CSVs via
   `scripts/emit_dk_upload_csv_v1.py --source run-dir --run-dir <dir> --ranks a-b --output <csv>` (create-only
   outputs; never upload a `book.csv`).
4. **Post-build chain** (`learned_after_build.sh`, polling `LATEST`): learned scorer over the whole pool
   (`learned_score_live.py` → shadow books), vetting of the entered 30, `ENTER/` folder with the reserved-entry layout
   (keepers first per contest), `TODAY-30-LATEST.md`; `watch_dk_entries.sh` fills DraftKings' entries export the
   moment it appears in the Windows Downloads folder; `watch_late_inactives.py` polls DK statuses for late-game
   scratches. A scratch swap = best-projected active same-position player fitting the lineup's salary, stack bonus.
5. **Operator steps** — 4a: `publish_week1_a5_books.py … --execute` (create-once per run id; the harness classifier
   refuses to run it, the operator runs the printed line); 4b: emit P_MIX upload files from the published books;
   upload in the DK UI by ~11:15 CT; lock 12:00 CT.

Inputs the build depends on, and when they are fresh: DK salaries/statuses (`nfl_raw.dk_salaries`, hourly on Sunday;
the T-70 build must use the pull *after* 10:30 CT inactives), production projections (`player_projections`, hourly),
props (`nfl_raw.prop_lines`, ~2-hourly; last Week-1 pull 09:33 CT), injuries (`nfl_raw.injuries`, practice status),
`player_week_inference` (depth rank, practice level, usage windows — empty in Week 1), TabPFN marginals.

### 10.3 The lab cohort pipeline (`nfl-2-506823`)

1. Freeze `PREREG-0NN.md` + runner `experiments/NNN_*.py` + reader `scripts/preregNNN_report.py` + gate
   `scripts/preregNNN_mechanics_gate.py` + launcher `scripts/queue_NNN.sh` on a branch off the current cohort commit.
2. Local smoke: `NFL2_UPLOAD=0 PYTHONPATH=<worktree>/src python -m nfl2.run experiments/NNN.py --bank=N
   --mechanics-only --smoke --season=2023 --weeks=1` (0.1 scale), then a full-path `--smoke` when the outcome path
   is new.
3. Image: lean `Dockerfile.prereg0NN` (base pinned by digest, `requirements.lock`, `src`, the experiment file(s),
   benchmark/data, frozen JSON receipts) + `cloudbuild.prereg0NN.yaml`; `gcloud builds submit --project nfl-2-506823
   --config cloudbuild.prereg0NN.yaml --substitutions _IMAGE_TAG=us-central1-docker.pkg.dev/nfl-2-506823/lab/nfl2:prereg0NN-<sha12> .`
   (~3 min). `.gcloudignore` excludes `results/**` except listed files — add an exception for any new frozen receipt.
4. Jobs: `gcloud run jobs update lab-run|lab-run-slow --image <tag> --update-env-vars CODE_SHA=<sha>,IMAGE_DIGEST=<digest>
   --parallelism 36 --tasks 72 --task-timeout <s>` (2 vCPU / 8 GiB; `maxRetries 3`). Only when both lanes are idle.
5. Launch through the registry: `scripts/launcher_registry.sh run --root <worktree> --state-root
   ~/.local/state/nfl-dfs/lab-launcher-registry --lane nfl2-lab-jobs --owner production --target-prefixes … -- <launcher>`
   (detached with `setsid nohup`). The launcher checks `CODE_SHA == HEAD` and a pushed branch, runs the gate
   (1 task, `--mechanics-only --verify-prefix`), then banks 72 tasks each under the ≤ 2-execution ceiling; a
   registered owner that dies leaves a receipt that must be adjudicated by hand (move it to
   `adjudicated-launcher-receipts/…orphaned-<stamp>.json` after confirming no surviving child work).
6. Results: `gs://nfl-2-506823-lab/results/<experiment>/<RUN_ID>/result-tNN.json` (envelope: experiment, run_id,
   code_sha, benchmark, image, args, seconds, task_index, result{params, slates, books, …}). Lost tasks: repair with
   `/home/erich/week1-sunday/repair_bank.sh <experiment> <result dir> <prefix> <bank> <code sha>` (registered; one
   execution per season with `--season/--weeks`), read with the reader's `--repair` union.
7. Read once; paste the verbatim output into `LEDGER.md` with the transcript's sha256; consequences as frozen.

Capacity: 100 instances / 200 vCPU per region; two 72-task banks at parallelism 36 fit; the 3200 stream takes up to
4,752 s on the largest slate (2023-W1, 773 players), the 6,400 stream roughly double, so task timeouts must follow.

### 10.4 The DraftKings side (no API; all through the logged-in desktop site)

- Entries are reserved by entering a placeholder lineup N times; DraftKings edits reserved entries only through
  **Lineups → Upload Lineups → download entries** (`DKEntries.csv`: Entry ID, Contest Name, Contest ID, Entry Fee,
  QB…DST, then the player pool). Fill it positionally (`scripts/week1_fill_dk_entries.py`), upload on the same page.
  Withdrawals are not available on full contests.
- Late swap: the same upload works during live contests for players whose games have not started.
- After the games: the contest entry history export (own entries' official points/places/winnings) and the full
  standings `https://www.draftkings.com/contest/exportfullstandingscsv/<contestId>` (zip; every entry's lineup and
  points plus %Drafted/FPTS per player; purged after ~4 days). Validate and load with
  `nfl-dfs capture-dk-standings <csv> --season --week --contest-id --contest-name --expected-entries N --apply
  --confirm-settled --confirm-full-field` (create-once archive + `nfl_raw.contest_entries` / `contest_ownership`).
  Real exports contain blank-lineup entries, single-precision scores and occasional one-entry ownership gaps; the
  validator handles all three as of 2026-09-14.

### 10.5 Local development traps

- Two venvs: production `~/projects/nfl-predictions/.venv` (Python 3.14; BigQuery, storage, pandas, pulp) and lab
  `~/projects/nfl2/.venv` (no `neo4j`, no `sklearn`, no BigQuery client in some paths). Always run lab code with
  `PYTHONPATH=<worktree>/src`: the editable install resolves `import nfl2` to the main checkout otherwise.
- `pytest` runs offline (synthetic panel in `conftest.py`); never pass `-q` (the commit gate reads the "N passed"
  line). Targeted modules only; one heavy local process at a time; heavy compute goes to Cloud Run.
- `results/` is git-ignored in both repos: `git add -f` for transcripts/receipts that must be tracked.
- The harness classifier refuses create-once publishes, systemd unit writes and some `grep`s in auto mode: hand the
  operator the one-line command.
- Background host processes must be `setsid nohup … &`-detached and named so `pgrep -f "^bash /path"` finds them;
  `pkill -f` on a substring kills the caller's own shell (happened twice). A process scan is not proof a timer task
  is dead: the "dead" T-70 task ran anyway.
- Windows files are visible at `/mnt/c/Users/Erich/…`; the operator sees the Linux tree at
  `\\wsl.localhost\Ubuntu\home\erich\…`. Give paths in that form when the operator must open them.

---

## 9. Where to read the evidence

- `HANDOFF.md` — authoritative, newest entries above "Exact next actions".
- `reports/2026-09-13-week1-findings-and-recommendations.md` — the operator-facing summary and recommendation.
- `reports/2026-09-13-week1-morning-decision.md` — the day's decisions §2–§6 (ordering shadows, learned score,
  cohort reads, entry mechanics, post-lock record, official result).
- `reports/2026-09-13-week1-postmortem-and-220-program.md` — the ledger audit and the 220 arithmetic.
- `reports/2026-09-13-week1-dud-analysis.md` — the duds, their history, the practice-status test, the filter tests.
- `reports/2026-09-13-audit-winner-gap.md`, `-perfect-lineup-gap.md`, `-late-swap-and-anatomy.md`,
  `reports/2026-09-13-pool-level-learned-selection.md`, `reports/2026-09-13-prereg096-read.md`.
- `reports/2026-09-14-week1-field-winners-settlement.md` — the fields, every book settled, the winners' profile.
- `reports/2026-09-14-week1-swaps-and-cheap-players.md` — every manual removal scored, the cheap slots, cheap-boom predictability.
- `reports/2026-09-14-payout-retro-test.md` — finish-objective selection against the real field (P(top-N) vs expected-max).
- `reports/2026-07-25-system-study.md` — the 120-addendum ledger; read the last fifteen before proposing anything.
- Lab: `PREREG-093/094/095/096/097/098.md` and `LEDGER.md` on the branches above. `PREREG-098.md` §Gate holds the
  sampler gate table (four variants); the host gate scripts and per-variant JSON are under
  `/home/erich/week1-sunday/payout/` (`sampler_gate_variant.py`, `sampler_gate_week1_*.json`, `variants.log`).
- Memory notes for the assistant (not project truth): operator working style, lab launch lessons, tail target
  supply-bound, learned lineup score, operator DK history, Week-1 resume state.
