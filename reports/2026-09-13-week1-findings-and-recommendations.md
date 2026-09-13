# Week 1 (2026-09-13): findings and recommendations

Written for the operator at the end of Week-1 Sunday. Everything here is backed by a measurement made today; the
detailed reports are linked at the end. Short version: the lineup machine is calibrated and does what a points-optimal
system does; that system sits 36–49 points below the Millionaire winner in a typical week; no lever on the points axis
closes that; the contest pays finish, not points, and finish has never been the objective. The recommendation is to
re-decide on the finish objective, not to keep chasing a score.

## 1. What happened

- 80 unique entries went live (Millionaire 57, Play-Action 20, FFWC Q6 3) after DraftKings offered no withdrawals on the
  full contests. The entered file was the "proven-scorer" variant (v6b); its best lineup scored about 188–190.
- The plain book (scratch swaps only, v4b) would have scored about 216 and 206: the proven-scorer rule removed Jalen
  Coker (36.8) from exactly the lineups that cleared 200. That rule was applied at the operator's request without a
  historical test; tested tonight, it costs 10–15 points at K30. Standing rule: no filter touches an entered book
  without a 72-slate test first.
- A 216 today paid about $30. In 10 of the 35 matched historical weeks the same 216 is a top-10 finish or the win.

## 2. What the measurements say

1. **The simulator is calibrated, including at the extreme.** Its per-world perfect lineup (max over all legal lineups
   on simulated points) averages 258; the realized perfect lineup averages 267 over 72 slates, always inside the
   simulated range. Real outcomes exceed the simulator's own 99th percentile 0.7–1.0% of the time; it over-predicts 200+
   by 3×. There is no hidden tail.
2. **The selector works; the ceiling is structural.** Selected lineups reach 220 ten times as often as unselected ones
   from the same pool (0.10% per lineup), which is one 220 per 80-lineup book every ~12 weeks — the historical 5 of 72.
3. **Perfect lineups are four 30-point games from the top quarter of projections, unstacked.** 84% of their players are
   top-quartile projections (97% top half); 18% of their slots are "unproven" players (no big game in the prior year),
   and 47% of their sub-$4,000 players are. Who booms is predictable; when is not.
4. **Deeper stacks hurt; late swap does not reach 220; learned selectors fail; player filters fail.** Stack size 4–5 has
   higher simulated ceilings and lower realized exceedance. Late swap (re-optimising late slots on early results) is
   +0.7 at K30 with 220-weeks unchanged. The learned pool selector was −2.8 at K30 on real pools. "Every player proven"
   costs 10–15 points; "at most one unproven" −0.9; "at most two" +0.2.
5. **Dose is the one monotone lever on supply.** Candidates at 220+ per slate: 0.14 (800) → 0.25 (1600) → 0.50 (3200);
   pool oracle 195 → 199 → 204; the 3200 rung passed against 800 in two cohorts (093, 095). The 6,400 rung (PREREG-097)
   is running on the lab lanes.
6. **The duds.** Of the two weak players per lineup: one stud with a practice red flag (Chase, did not practice Friday,
   22 lineups; historically such players flop 36% vs 24%), several healthy players who had nothing (no signal exists),
   and several low-frequency boomers at $4,000–5,300 (Tucker 6%, Harrison 9%, Jones 9%) — the same profile as Coker,
   who won the day. None of their big games were injury-driven (6.4% of all big games are).
7. **The gap to the winner.** Millionaire winners 2023–24: mean 230, range 178–296, correlated 0.7 with our own best.
   Our K80 best: 182 (gap 49); our 800-candidate pool oracle: 195 (gap 36). Our book beat the winner in 1 week of 35;
   our pool held a winner-beating lineup in 1 of 35. 2025 winners average 4.2 sub-10%-owned players and a QB owned
   under 9%.

## 3. What follows

- **Points is the wrong axis for this contest.** Nothing on it moves the book more than ~2 (the dose moves the pool
  ~8), against a gap of 36–49. Continuing to optimise points cannot change the outcome.
- **Finish is the right axis, and it has never been evaluated.** Every gate in the ledger scores points. The Millionaire
  pays rank against a field whose top end is made of ownership: a contrarian 205 in a chalk-bust week wins; a chalky
  216 in a shootout week is $30. The August ownership model passed calibration and its lineup arm was then dropped by
  a points gate — the "wrong question" the August strategy review named.
- **The data to decide exists.** 72 weeks of actual DraftKings ownership per contest (2022–2025), winners' rosters
  2019/2023/2024/2025, and the weekly standings exports the operator can download Monday/Tuesday.

## 4. Recommendations

1. **Re-decide on the finish objective before stopping or scaling.** Build the field model from real ownership; score
   our historical books by finish rank against the actual weekly field (win-week rate, top-1,000 rate, EV under the
   Millionaire's payout curve) instead of points; test contrarian construction (low-owned QB, 3–5 sub-10% players)
   under that objective on history. Two to three weeks. If it does not lift the win-week rate off 1-in-35 or produce a
   positive measured EV, stop with a clean answer.
2. **Play minimum stakes or none meanwhile.** The Week-1 shadows settle regardless.
3. **Keep the two cheap structural gains.** The 3200 dose for the paid book (two passing cohorts); the practice-status
   exposure cap in vetting (Friday DNP = material regardless of props, ≤10% of the book; DNP + Questionable = hard).
4. **Contest choice as a lever.** The book reaches 200 in 15–18% of weeks at K80; where 200 pays (5k-entry qualifiers,
   3-max GPPs), the existing machine is already competitive. This is a bankroll decision, not a model change.
5. **Runbook fixes for Week 2** (recorded): reserved entries are edited only through DraftKings' entries export, so the
   keepers-first fill goes into the Sunday script; withdrawals cannot be assumed; the 10:50 CT build must pull salaries
   after the 10:30 inactives; the scratch-swap tool stays live from 11:00 CT through the late window; no untested filter
   on an entered book.

## 5. Monday / Tuesday, when the exports arrive

- Settle the entered book (v6b) and the counterfactual (v4b) against DraftKings' exact scores; settle every shadow
  (paid P_MIX/K90, learned, union, orderings).
- Winners' analysis: profile the Millionaire's top 100 the same way as the duds (big-game rate, practice status, salary,
  ownership) and compare with our book. This is the first finish-axis measurement.
- Read PREREG-097 when its banks land; re-arm its launcher first (see HANDOFF).

## Detailed reports

- `reports/2026-09-13-week1-morning-decision.md` — the day's decisions, §2–§5 (ordering shadows, learned score,
  PREREG-093/095/096 reads, entry mechanics, post-lock record).
- `reports/2026-09-13-week1-postmortem-and-220-program.md` — the ledger audit and the 220 arithmetic.
- `reports/2026-09-13-week1-dud-analysis.md` — today's duds, their history, the practice-status test, the filter tests.
- `reports/2026-09-13-audit-winner-gap.md` — week-by-week gap to the Millionaire winner.
- `reports/2026-09-13-audit-perfect-lineup-gap.md`, `reports/2026-09-13-audit-late-swap-and-anatomy.md`,
  `reports/2026-09-13-pool-level-learned-selection.md`, `reports/2026-09-13-prereg096-read.md`.
