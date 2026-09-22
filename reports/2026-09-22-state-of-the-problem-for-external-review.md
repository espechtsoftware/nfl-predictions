# State of the problem, for an outside reviewer: what is hard, what we tried, what is queued

**Written for:** a model or person with no history on this project, asked to review our position
and suggest ideas. **Written by:** the laptop agent, 2026-09-22, from the tracked record (every
number cites a report or ledger row you can open). **What we want from you:** §7 lists the
specific questions. §5 lists what is already closed, so proposals don't repeat it. Please read
§1–§3 before proposing anything; this programme's most common failure is an idea that looks
new and was tested in August.

---

## 1. The system in one page

**Goal.** Enter DraftKings NFL Classic contests (the Sunday main slate) with a book of roughly
80–200 lineups, and make money. The operator's stated goal is winning.

**Two repositories.**
- **Production** (`~/projects/nfl-predictions`, this repo, public): the BigQuery warehouse,
  the projection model, the daily Cloud Run jobs and the Sunday money path.
- **Lab** (`~/projects/nfl2`): the simulator, candidate generator and selector, plus
  preregistered experiments (`PREREG-0NN.md`, `LEDGER.md`). **The lab agent became unavailable
  on 2026-09-22.** Its code remains in the money path, pinned at commit `2dc116c`.

**How a Sunday book is built.**
1. **Player projection.** LightGBM ensemble trained only on games the player played, so it is
   E[points | played], blended as 0.45 × model + 0.55 × sportsbook-prop-implied points.
2. **Simulation.** 10,000 correlated worlds per player (game, team and player dependence).
3. **Candidate pool.**
   - `lev`: MILP lineups on a tournament objective, with overlap cuts.
   - `boom`: the optimal lineup in one simulated world, repeated per world.
   - Week 2: 2,560 `lev` + 10,240 `boom` solves, 12,555 unique lineups.
4. **Selection.** A greedy expected-max selector ("DEMAX") picks K lineups, each maximising
   E[max over the book] across worlds.
5. **Construction rules.** QB + 2 same-team pass catchers + a bring-back; salary floor.
6. **Contest assignment.** Operator-chosen contest mix; since Week 2 each contest gets a
   disjoint slice of the book.

**Validation laws — non-negotiable here; read `CLAUDE.md` for the full text.**
- Walk-forward by season only.
- Preregister, freeze and read once.
- Six-season panels with a co-run control on the same build; at most one negative
  leave-one-season-out estimate.
- Audit before verdict.
- Point-in-time features: week W sees only weeks < W.
- Always compute the null. A count without an expected-if-random beside it is not a finding;
  several of our retractions came from forgetting that.

---

## 2. Where we are — the numbers

**Money** (`reports/2026-09-22-production-what-winning-requires.md` §1):

| | entries | net | entries cashed |
|---|---:|---:|---:|
| Week 1 2026 | 80 | −$259 | 18 (22.5%) |
| Week 2 2026 | 97 | −$220 | 3 (3.1%) |

Lifetime: 1,164 entries, best single entry $100, **zero entries ever returning ≥ $400**.

**Pool quality against the real field.** We hold every lineup and score from the real contests:
994,328 Week-1 and 311,664 Week-2 entries in `nfl_raw.contest_entries`.

| | our pool mean | field mean | pool mean's field percentile | book in field's top 20% |
|---|---:|---:|---:|---:|
| Week 1 | 141.1 | 142.1 | **49th** | 27.8% |
| Week 2 | 93.7 | 115.6 | **22nd** | 6.2% |

(`reports/2026-09-22-production-pool-quality-decomposition.md`)

---

## 3. The challenges

### C1. The large-field tournament is structurally out of reach
The Millionaire winner is the maximum of ~170k–830k entries; we submit about 150. Our pool's
maximum grows about 6.95 points per e-fold of candidates, and the field's winning line grows
about 6.41 per e-fold of entries. The two rise at the same rate, so volume never closes the
gap. Even adding **+40 points to every lineup we build** gives only a 7.7% chance of winning with
150 entries. Winning is **plausible in fields up to about 1,000 entries** (10–25% a week at
today's quality), but much of that comes from owning a large share of a small field, which is
not profit without edge. (`reports/2026-09-22-production-what-winning-requires.md` §2–§3)

### C2. Almost nothing replicates across our two slates, and the reason is the simulator
We hold only **two** weeks of full-field data. Lever after lever showed a strong effect on one
slate and the **opposite sign** on the other:

| lever | Week 1 | Week 2 | source |
|---|---|---|---|
| exposure caps | −2.5 to −5.0 mean | +11.3 mean | `2026-09-22-exposure-caps-do-not-replicate-out-of-sample.md` |
| chalk fade | mean −2.33 / best +6.72 | mean +2.25 / best −1.84 | `2026-09-22-laptop-fade-two-slate-synthesis.md` |
| cash-line objective | 53.3% cleared | 0 of 97 cleared | `2026-09-22-production-simulator-regime-flip.md` |
| sim-mean sort vs realized (ρ) | +0.28 | −0.16 to −0.27 | same; `2026-09-22-laptop-sort-key-study.md` |
| bring-back lineups (top-0.1% lift) | 1.99 | 0.75 | HANDOFF `b1af8137` |
| salary left ≥ $400 | lift 1.28 | lift 0.70 | same |

**The mechanism** (`reports/2026-09-22-simulator-calibration-is-the-defect.md`): the simulator
predicts a lineup mean of about 123 every week, while realized means were 141 (Week 1) and 94
(Week 2). The error is **compositional**, not a uniform shift:
- The lineups the simulator likes most are the ones it misprices most, and the sign flips:
  corr(sim mean, error) +0.14 in Week 1, −0.55 in Week 2.
- P(score ≥ 194) was 5.5× too low in Week 1 and 146× too high in Week 2.
- Expected-max selection is threshold-free and degrades gracefully.
- Every threshold-keyed objective (cash line, P(top-N), tail counts) inherits the full error.

A claim that the slate scoring environment is predictable pre-lock was **retracted** the same
day: it had fitted a 2022 data break in the training panel, where the share of inactive rows
jumps from 0.3% to 46.6%.

### C3. Availability errors poisoned the pools (now largely fixed for Week 3)
- **Doubtful players:** 0 of 13 played across two weeks. Zay Flowers (Doubtful) held 48 of our 97
  Week-2 rows and scored 0.
- **Backup QBs:** about 20% of each pool used a backup QB who never played, because the model
  serves E[points | played] and a minimum-salary backup looks like value.
- **Scale:** 47% of Week-2 candidates carried at least one player projected ≥ 5 who took zero
  snaps.
- **Week-3 fixes, all verified deployed:**
  - Doubtful players excluded from the pool before simulation (nfl2 `69f98a7`).
  - Backup-QB gate with two refinements.
  - Questionable projections × 0.80.
  - Doubtful non-QB starters trigger the next-man-up cascade (`CASCADE_DOUBTFUL=1`).
- **Retrospective check:** these rules would have removed 56 of the 57 non-playing slots from
  Week 2's entered lineups (`2026-09-22-laptop-suffix-name-join-correction.md`).
- **Limit:** this fixes the floor; it does not create edge.

### C4. The average lineup is a median DFS entry
The pool's mean sits at about the field median. Diversification costs mean, and it pays only if
the ceiling it buys can reach a winning line, which C1 says it cannot in large fields. Production
proposed replacing tail-count targets with **"move the pool mean from the 49th to the 65th+ field
percentile"**, a target the programme has never optimised directly
(`2026-09-22-production-what-winning-requires.md` §5).

### C5. Our pool's divergence from the crowd was a losing bet in Week 2
Across all 202 players, the tilt log(pool share / field ownership) correlated **−0.28**
(p < 0.001) with realized points: we overweighted the players who underperformed. It was
strongest at WR (−0.41) and TE (−0.49). **Week 1 has not been run yet**, so this may be "chalk
won in Week 2" (`2026-09-22-laptop-winning-tail-anatomy.md`).

### C6. Data limits
- Only two slates of full-field lineups. `contest_ownership` has 72 weeks (2022–2025) of
  per-player ownership but **no lineups**.
- **Payout amounts are NULL** everywhere in `contest_entries`, so cash lines must be derived.
- 2025 injury data is missing.
- `rosters_weekly` keeps only the latest pull, so any retrospective use of rosters sees after
  the game.
- The training panel has the 2022 inactive-row break.
- Full list: `README.md` → *Known gaps*.

### C7. Organisational
- The lab agent is gone, so the money path runs lab code frozen at `2dc116c`, and nobody owns
  fixes to it.
- 14 frozen lab preregistrations have **no ledger row**; for example, 051 (winner-shape supply
  at fixed compute) and 073 (awaiting a production review that never came).
- The adopted **chalk fade has never fired in 2026**: the live caller never passes ownership
  (`2026-09-22-the-chalk-fade-has-never-fired-in-2026.md`). Since it also fails to replicate
  across the two slates, it was not restored.

---

## 4. What we tried in the last ten days, with verdicts

| attempt | verdict | where |
|---|---|---|
| Finish objective: select by P(top-1,000 / top-100) against an ownership-fitted synthetic field (PREREG-098, 53 historical slates) | **negative, decisive**: best-finish percentile 5.6% vs expected-max's 2.6% | lab LEDGER; briefing §7 |
| Paid data (Fantasy Points, SIS) 2×2 ablation, 54 slates | consumed, but realized points don't move | `2026-09-15-paid-source-influence-ladder-direct.md` |
| Admission cap removed (more tail in front of the selector) | K20 null, K80 +1.5 near miss | `2026-09-15-admission-cap-lever-result.md` |
| Exposure caps | + on W2, − on W1: do not use | see C2 |
| Chalk fade (A/B on both slates) | signs crossed: does not replicate | see C2 |
| Cash-line objective | 53% W1, 0% W2: regime-dependent | see C2 |
| Direct P(30+) "ceiling" player model | worse than the mean model in 8 of 8 seasons | `2026-09-22-ceiling-model-result-negative.md` |
| Model-input ablation | only a few features clearly matter; column order alone moves MAE 0.005 (noise floor) | `2026-09-22-model-input-study.md` |
| Selection: expected-max vs caps vs random | expected-max beats random in both weeks on the best lineup; caps add nothing | HANDOFF `bba50744` |
| Sort order across contests | no key ranks the book in both weeks, not even post-lock oracles; the simulator sort is the projection sort | `2026-09-22-laptop-sort-key-study.md` |
| Generator batches | all Week-2 top-1% lineups are `boom`; `lev` never reaches 220+ in either week | `2026-09-22-laptop-generator-batches.md`, HANDOFF `b1af8137` |
| Field shapes (QB stack / bring-back) | QB+2+ is best per lineup both weeks; naked QB worst; the bring-back flips | HANDOFF `b1af8137` |
| Cascade double count (injury redistribution) | the carry side over-projects RBs (−0.68 residual, 3/3 seasons); default-off fix on a branch | `2026-09-22-laptop-cascade-double-count.md` |
| Cash/double-up shadow | the Week-2 book would have cashed 11–24% against a ~50% break-even | `2026-09-22-laptop-cash-shadow-first-measurement.md` |
| Tail calibration (PREREG-101) | frozen, then **withdrawn**: selection-optimism objection unresolved; do not launch | HANDOFF 2026-09-22 11:28 |

## 5. Already closed — please don't re-propose without a new mechanism

From the lab ledger (`nfl2/LEDGER.md`) and the briefing's §3
(`reports/2026-09-14-project-briefing-for-a-new-model.md`):
- **Alternative generators:** GFlowNet, Gumbel, hierarchical Gumbel, cross-entropy, Schaake,
  TD coupling, role-belief.
- **Dependence rewrites:** learned conditional templates, coherent member worlds.
- **Selection alternatives:** LSE, sharp LSE, QB concentration, dollars objective,
  decision-focused reranker, novelty ladder, union e-max, coverage-194/220, P(top-N) finish
  selection, learned lineup scores.
- **Other levers:** 24 within-book orderings, skill-salary floors, late swap, deeper stacks,
  player filters, a no-bring-back sleeve at the current dose (PREREG-055), and minimum-concentration
  or retention sleeves (PREREG-057).
- **Dose** was the only monotone lever: 3,200 candidates passed against 800 twice; 6,400 over 3,200 was only a near miss (PREREG-097: saturation at 3,200).

## 6. What is queued

| when | item | owner |
|---|---|---|
| Thu 09-24 | Week-3 rosters land → run the availability dry run (`reports/lab-handoffs/week3_availability_dry_run.py`) | laptop |
| Sat 09-26 | props + injury report → re-run the dry run; prop-match preflight | laptop / production |
| **Sun 09-27** | **Week-3 build**: 198 entries across 40 contests, sequential layout, 12,800 solves (2,560 lev + 10,240 boom), all four availability rules live | production + operator |
| operator decision | enable the carry-side cascade fix (`laptop/cascade-priced-carries-20260922`) | operator |
| after Sunday | all-`boom` vs live-generator panel (design, not frozen: `2026-09-22-laptop-lev-to-boom-panel-design.md`) | production / operator |
| after Sunday | Week-1 replication of the field-tilt result (C5) | production |
| after Sunday | Python 3.14 re-freeze of the pinned runtime | production |
| ongoing | cash/double-up shadow, on paper beside the tournament book | laptop |

## 7. Questions for the reviewer

1. **Learning with two slates.** Every live verdict has n = 2, and most flip. What evaluation
   design would let us learn faster without panel-mining? Material to design with:
   - 72 historical weeks of per-player ownership, but no lineups.
   - An IPF field sampler gated at 0.987 against a real field (PREREG-098).
   - Two real full fields.
   - Replays back to 2014.
2. **Calibrating the simulator's level and composition.** The error is compositional and flips
   sign by week. With two weeks of lineup-level simulated-vs-realized pairs, plus historical
   player outcomes, what recalibration is identifiable? Is anything fittable pre-lock, given
   that the environment-prediction claim was retracted?
3. **Raising pool mean quality (49th → 65th percentile).** Players' projections come 55% from
   sportsbook props. What have we missed that would raise the average lineup rather than the
   tail?
   - Evidence exists but is unused for practice-participation level.
   - The 0.45 model / 0.55 market weight is fixed.
   - The field-relative concentration gap is +10 points on the field's top-40 players.
4. **Which contests to play.**
   - The winnable frontier says small fields (≤ 1,000).
   - The lifetime record says ROI is best in the largest fields and worst in fields under 100.
   - Top-heavy payouts returned −100% over 85 entries.
   How should contest selection be evaluated with no payout amounts in the data?
5. **Construction relative to the field (C5).** If the Week-1 replication confirms the negative
   tilt, what is the right way to pull the pool's player distribution toward the field's without
   losing the differentiation a tournament needs (duplicated lineups split prizes)?
6. **Anything structural we are blind to.** For example: the model trains on
   E[points | played] and availability is bolted on afterwards in four places; the sim ranks
   by a mean that equals the projection sum; a large, fragile research apparatus rests on a
   two-slate live record.

## 8. Where to read further

| topic | file |
|---|---|
| current work record (newest first) | `HANDOFF.md` |
| operating handoff for Week 3 | `reports/2026-09-22-laptop-agent-handover.md` |
| background, validation culture, science to 09-14 | `reports/2026-09-14-project-briefing-for-a-new-model.md` |
| synthesis after Week 1 | `reports/2026-09-16-findings-since-week1-synthesis.md` |
| experiment ledger (read the last 15 addenda; several verdicts were retracted) | `reports/2026-07-25-system-study.md`; `nfl2/LEDGER.md` |
| unturned stones audit (with its corrections) | `reports/2026-09-22-laptop-research-audit-unturned-stones.md` |
| known data gaps | `README.md` → *Known gaps* |

**Standing constraints for anyone acting on this:**
- This repo is public. Never commit credentials, DraftKings entry keys, entries exports, the
  stake plan (`contests.json`) or licensed vendor data.
- Money-path changes need a validation trail and the operator's approval.
- Never touch an entered book with an untested rule.
