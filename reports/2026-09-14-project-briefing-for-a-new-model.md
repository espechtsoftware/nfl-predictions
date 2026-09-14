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

**The next test (proposed to the operator 2026-09-14, awaiting go):** for each of our 3,200 Week-1 candidates and
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

## 8. Operational state right now (2026-09-14 11:30Z)

- Cloud: PREREG-097 (6,400 rung) banks 970/971/972 launching on the lab lanes via the finish launcher (host script
  `/home/erich/week1-sunday/queue_117_finish.sh`, registered; the original launcher died with the workstation
  shutdown and its registry receipt was adjudicated); read this evening with `scripts/prereg097_report.py`
  (repairs: `/home/erich/week1-sunday/repair_bank.sh`).
- Warehouse: Week-1 full fields loaded; Week-1 player stats arrive with the nflverse job (which still 404s on FTN
  after loading rosters/injuries — fix the tolerance).
- Branches, all pushed and clean: production `production/week1-audit-adjust-20260912`; lab
  `lab/prereg097-dose6400-20260913`, `lab/prereg096-learned-pool-20260913`, `lab/prereg090-amend4-20260912`
  (LEDGER rows for 093/095/096 with transcripts).
- Host artifacts (untracked): `/home/erich/week1-sunday/` (tools, ENTER/, ENTERED/ with the operator's entry export
  — entry keys, never commit), `results/2026-09-13/` (the standings exports).
- Runbook fixes queued for Week 2: reserved-entry fill in the Sunday script; withdrawals not assumed; T-70 salary pull
  after the 10:30 inactives; scratch-swap tool live 11:00 CT → late window; practice-status cap in vetting; no
  untested filter on an entered book.

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
- `reports/2026-07-25-system-study.md` — the 120-addendum ledger; read the last fifteen before proposing anything.
- Lab: `PREREG-093/094/095/096/097.md` and `LEDGER.md` on the branches above.
- Memory notes for the assistant (not project truth): operator working style, lab launch lessons, tail target
  supply-bound, learned lineup score, operator DK history, Week-1 resume state.
