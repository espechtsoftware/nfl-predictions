# Project status, open challenges, and what has been tried (2026-10-06)

Written 2026-10-06 (Tuesday of Week 5) by the laptop agent, for another AI agent joining or advising the project. It is
self-contained: no prior context is assumed. It summarises; the records it cites are authoritative, and anything here
that conflicts with them is wrong. This is a public repository: no dollar amounts, DraftKings user names or stake plans
appear here (they exist only in the operator's private files).

---

## 1. What the project is

- **A DraftKings NFL daily-fantasy (DFS) system** run by one operator (Erich), who decides everything about money and
  adoption. Agents build, test, run and report. Code: this repository (`nfl-predictions`, "production") and a research
  repository (`nfl2`, "the lab").
- **The pipeline:**
  1. Public and licensed data land in BigQuery: nflverse, DraftKings salaries and contests, odds, weather, Fantasy
     Points (FP) and Sports Info Solutions (SIS) pages.
  2. Point-in-time features: week W only sees weeks before W, enforced by leakage checks.
  3. Per-position projection models; correlated game simulations.
  4. A large candidate pool of lineups (the lab's `live_week.py`).
  5. A selection step that picks the entered book (production's `scripts/union_reselect.py`).
  6. Vetting (injury/status checks, replacements).
  7. A layout that deals lineups to contests.
  8. Upload files the operator submits by hand on DraftKings.
- **Weekly rhythm:** data and research Monday–Friday. Saturday the agent arms timers (`scripts/arm_week5_saturday.sh`).
  Sunday morning the builds run, with a final rebuild at T−70 minutes after the 10:30 CT inactives. The operator uploads
  by about 11:15 CT; lock is 12:00 CT. Monday is settlement and scoring.
- **The operator's goal, in his words (10-05):** "If i could win one 333, 555 or 4444 or $500 in the milly, the week is
  a success and i wouldnt care if i lost all the $20 milly tickets."
  - So the target is **the chance of at least one big win per week**: first place in a satellite qualifier, a 25-seat
    super-satellite seat, or a $500+ finish in the Millionaire (a ~160,000-entry tournament).
  - It is not average return.
- **Urgency:** he has said the project ends if it is not working within one to two weeks, and that things may change
  mid-season.

## 2. Where we are (Week 5 preparation, 2026-10-06)

### Results so far (2026 Weeks 1–4)
- **Money:** a faithful replay of the current system over Weeks 1–4 returns **about 0.48× of entry fees** (95% range
  0.36–0.67). By week: 0.85× / 0.65× / 0.00× / 0.17×. Week 4 as actually settled: about 0.42× counting tickets at face.
  Source: `briefings/2026-week-04/2026-10-05-week5-money-gate-result.md`.
- **Selection vs chance:** our selection step is about **as good as random picks from our own candidate pool**. Over
  Weeks 1–4, the entered book sits at the **52nd percentile** of 1,000 random books drawn under the same caps and
  dealing. It was far above chance in Weeks 1–2 and below in Weeks 3–4.
  - The pool itself beats fully random legal lineups clearly, so the value we add is in the pool, not the selection.
- **Player picks vs the field:** our lineups average **3.8 points below** the rest of the Millionaire field per lineup
  (2026 W1–4). A fixed cohort of 117 max-entry "regulars" averages **6.1 points above** it.
  - The gap is pre-lock knowledge (better projections and news), not visible construction habits (study 34).
- **Projections:** the betting market's numbers beat our served projections (mean absolute error 5.28 vs 5.43,
  preliminary), and our model alone is worse than the market every week.
  - A data leak was found in one training feature (`xfp_l4`; Addendum 121); every verdict that used it is void. The
    retrain with the fix is pending (register item O-22).
- **Week 4 in one line:** one game decided the slate and we had no player from it. Four heavily used players busted
  together (one to an in-game concussion). The book was much chalkier than the field (ownership sum 152% vs 110%) and
  concentrated in three games. Source: `briefings/2026-week-04/2026-10-05-week4-post-mortem.md`.

### What is armed for Week 5 (Sunday 10-11), all operator-approved
- **Projection source:** Fantasy Points' projections replace ours in selection. A Week-4 replay held. It is unproven
  live; a weekly ours / FP / blend check runs.
- **Book shape ("MIXT"):** a portfolio of four stack shapes at the rates the winners use ("the winners' mix"), plus an
  ownership term.
  - The ownership term adds +0.20 × FP's projected ownership to each player's value, i.e. it leans toward popular
    players, which history supported.
- **Caps:** no quarterback in more than 5 of the 26 book lineups (study 35); no other player in more than 13; no
  defense in more than 6.
- **The contest plan:** 29 contests, 53 entries, 26 distinct lineups. The super-satellites take lineups 1–26 (the
  operator's change, 10-06), dealt by the "head" layout.
- **Arming and checks:**
  - Saturday's fail-stop arming script.
  - Its 10:30 Saturday build is a canary: receipt and audit checked by 11:00.
  - Rehearsals run Wednesday and again Friday on the merged code.
- **Nothing else changes for Week 5.** Each of these choices is a preference with no measured cost, not a proven gain
  (see §4).

## 3. The challenges

1. **No measurable edge yet.** The system loses money in replay. Our player picks trail the field, and selection adds
   nothing over random picks from the pool. Every change tested in Weeks 4–5 reads "no difference" at its frozen rule.
2. **Projection quality is the binding constraint.** The regulars beat the field by knowing more before lock, not by
   building differently.
   - We switched to Fantasy Points' projections for Week 5 (the operator's decision) and are fixing our own model's leak.
   - Whether FP closes the gap is measured weekly from Week 5 (the picks-vs-field line, `scripts/weekly_picks_vs_field.py`).
3. **Concentration and bust risk.** Our books hold about ten players at the cap (13 of 26 lineups) and few quarterbacks.
   One bust takes half the book with it.
   - Spreading the book has so far cost projected points under our own ratings (studies 1b, 36, 37), so it has not been
     adopted.
4. **Evaluation power is thin.**
   - One slate per week. The operator's utility (at least one big win) is a rare event.
   - Historical data (2023–24) lack FP, SIS and props, so the historical simulation panels cannot judge anything that
     depends on them. The operator has ruled that six-season panels never gate; test on 2026 full-data weeks.
   - The historical harness prices every lineup with OUR projections, so it cannot credit an approach whose value comes
     from better information (the "transfer caveat").
   - Most results therefore land in a wide "no difference" band.
5. **Choosing among lineups.** With one entry in a big contest, no ranking rule beats a random pick from the book
   (study 32). With 2–3 entries, choosing them together for joint coverage helps a little (about +7 points of cash
   chance at three entries); this is offered, not automatic.
6. **Operational reliability.** Vendor data revise after publication (FP's Week-4 Route Share changed on Tuesday). Vendor
   sessions expire (SIS). Alerts were noisy, and frozen research chains are fragile.
   - Each known problem is in `reports/OPEN-DEFECTS.md` with an impact, a deadline and a definition of "resolved".
   - Several fixes await this week's rehearsals.

## 4. What has been tried

Every study below was preregistered (frozen design and decision rule), run on 36 historical slates (2023–24) averaged
over six sets of simulated fields, read by a frozen reader, and reproduced byte-identically by a second agent before
being recorded.
- "NO DIFFERENCE" means the 95% interval for the change in the chance of at least one big win per week spans zero.
- "Guards" protect average finish and expected big seats.
- Details: `reports/2026-07-25-system-study.md`, Addenda 121–142, and the lab's `LEDGER.md`.

### Lineup shape and stacking

| Study | Idea | Result | Status |
|---|---|---|---|
| 15 | A looser quarterback stack rule | No difference | Not adopted |
| 18 / 18b | Within-game "WS" shape | Passed on tickets (+42%), then no difference on his goal and real plan | Not adopted |
| 26 | One-game shootout build | No difference; first consistent ceiling signal | Not adopted |
| 28 | The winners' shape mix vs our house shape | No difference, every season positive, guards intact (the closest result) | Adopted as his preference |
| 31 | Shape × ownership term together | Shapes tied; the term helped on both | MIXT armed |

### Popularity (ownership)

| Study | Idea | Result | Status |
|---|---|---|---|
| 29 | Ownership term on the winners' mix | No difference, leaning negative | Reversed by 31 |
| 31 | The same term in a larger co-run | Helped on both shapes (+6 to +10 percentage points of big-win chance) | ON at 0.20 |
| 34 | Copy the regulars' visible habits | No difference: their edge is information | Closed |

### Concentration and caps

| Study | Idea | Result | Status |
|---|---|---|---|
| 1 | Cap how much of the book one game takes | No difference | Not adopted |
| 1b | Cap any player at ~30% of entries | Halves the single-bust damage; costs 2.4–4.3 points of average finish | Not adopted |
| 16 / 16c | The operator's thesis portfolio (core games plus alternatives) | No difference; average finish far below margin | Closed |
| 17 | Selection redundancy | No difference | Closed |
| 24 | A per-game quarterback cap | No difference; failed his tolerance (−22% expected big seats) | Not offered |
| 35 | A per-quarterback cap at the regulars' level (5 of 26) | No difference, leaning positive everywhere | Adopted |
| 36 | A stricter cap on every player (9 of 26) | No difference; measured cost to average finish | Not adopted |
| 37 | The regulars' structure: ~11 quarterbacks and a steep player curve | No difference but leaning worse; both guards breached | Not adopted (see 38) |

### Other questions

| Study | Idea | Result | Status |
|---|---|---|---|
| 32 | How to choose the best few lineups | One entry: random is as good; 2–3 entries: choose jointly | Offered |
| 33 | Late-window injury calibration | No difference; production already removes Doubtful players at T−70 | Closed |
| P1 | Is any contest type +EV for us? | No measurable edge anywhere | Informs staking (his decision) |
| Overlay back-test | Contests the field fails to fill | No usable overlays on the classic slate | Closed |

### What the winners do (descriptive, 2026-10-06)

Source: `briefings/2026-week-05/2026-10-06-how-the-winners-spread.md`.
- **Their spread is construction, not volume.** Cut to our size (26 lineups), a regular's portfolio still has only about
  2 players in more than 40% of lineups, 53 distinct non-quarterback players and 11 quarterbacks. Our book has about
  10, 25 and 7. Real players entering only 20–40 lineups look like the regulars.
- **Nobody swaps within the same game.** When a portfolio leaves out its most-used player, the replacement comes from
  another game about 95% of the time, at the slate's base rate. The winners' replacement is 2.4–3.2 projected points
  cheaper (by our projections); ours is 0.7 cheaper.
- **The top receiver is the usual partner, not a rule.** A quarterback's lineups hold his team's top receiver about 60%
  of the time, ours included.

### What is running next
- **Study 38, a paper co-run under FP projections on live weeks W5–W8** (operator: "I want to exhaust all reasonable
  options").
  - Each Sunday, the regulars' structure and the current book are built on paper from the same pre-lock inputs. They
    are never entered, and are scored Mondays against the real contest results.
  - The rule is frozen before the Week-5 lock. It needs the structure ahead in all four weeks, within his seat tolerance.
  - This is the fair test of study 37's idea, because it uses the projections we actually play.
- **The projection retrain** with the leak fix (O-22), after Week 5.
- **The weekly evidence record from Week 5:** picks-vs-field, the random-book benchmark, projection accuracy
  (ours / FP / FP + props), and the paired scorer for choosing big-contest entries.

## 5. Open questions an outside agent could help with

1. **Better pre-lock information.** The regulars' edge is information. Which sources or signals (news, practice
   reports, props, sharper projections) would move our picks-vs-field line, and how do we test them on only a few 2026
   weeks?
2. **Evaluation with little data.** How do we judge a construction rule with 4–8 live slates, when the target event (a
   big win) is rare? Study 38 uses a paired weekly finish rule as the workable proxy; is there a better one?
3. **Concentration without paying for it.** Spreading costs projected points under our ratings, but the winners spread
   and win. Is there a way to spread that keeps projected value? For example, spreading across more quarterback stacks
   while keeping the cheap-fill trade the winners make.
4. **Contest selection and staking** while no edge is measurable: overlays, rake differences, satellite structures.

## 6. How work is done here (so advice fits the process)

- **The operator decides all money and adoption questions.** Agents recommend in plain words and implement what he
  approves. Two agent roles work together: a laptop agent (production operations and builds) and a reviewer (study
  design and code review). Every finding travels as a committed file.
- **Validity laws:**
  - Point-in-time features only.
  - Walk-forward validation.
  - Preregister the decision rule before outcomes are seen.
  - An outcome-blind "census" of how each arm builds, before scoring.
  - Fresh random seeds ("banks"), scanned for prior use.
  - A frozen reader, re-run byte-identically by the other agent.
  - Never tune on already-read slates.
  - A change in a downstream stage voids a verdict's transfer.
  - Integrity failures stop release.
- **The money path is changed only through tested, reviewed code.** It is rehearsed on archived inputs, armed by a
  fail-stop script, and every guard fails closed. The repository is public, so private data stays in the operator's
  private files.

## 7. Where to look

| What | Where |
|---|---|
| Current state, newest first | `HANDOFF.md` |
| Rules for agents | `CLAUDE.md` |
| Known unfixed problems | `reports/OPEN-DEFECTS.md` |
| Every experiment's verdict | `reports/2026-07-25-system-study.md` (addenda) and the lab's `LEDGER.md` |
| The study list (his questions, the status of each) | `reports/2026-10-04-post-week4-study-list.md` |
| This week's decisions and arming | `briefings/2026-week-05/2026-10-05-week5-decision-sheet.md`, `reports/2026-10-06-week5-arming-checklist.md` |
| Week-4 post-mortem and the money test | `briefings/2026-week-04/` |
| The operator's documents index | `briefings/README.md` |
| Older background (architecture, science through mid-September) | `reports/2026-09-14-project-briefing-for-a-new-model.md`, `docs/design-guide.md`, `README.md` |
