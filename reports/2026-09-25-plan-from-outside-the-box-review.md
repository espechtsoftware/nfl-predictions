# Plan from the outside-the-box review (2026-09-25): what we do, in what order, who does it

**Source:** `reports/2026-09-25-outside-the-box-strategy-research.md`, 19 nominations and 8 integrity items. It is now merged
into the integration branch from `claude/draftkings-lineup-strategies-cjlxo0` @ `d2820b1e`; the nfl2 pointer is at `ef4f7b9`.
**Written by** production, for the laptop agent, which does the work, and for the operator, who decides adoption.
Nothing here changes the Week-3 entry. The Week-3 path is frozen from Saturday 10:30 CT.

**Naming.** The review calls its recency-aware sleeve "PREREG-L05", but L05 is the lag-label sleeve panel already running.
The recency successor is **PREREG-L07**. L06 is qbvar.

## 0. Integrity items (§5): checked or assigned before anything else

| # | item | status |
|---|---|---|
| 5.1 | the 2026 salary spine empty? | **Checked 2026-09-24 21:30: not a defect.** `dk_raw.dk_salaries.week` is NULL on every row, but `nfl_features.dk_salary_week` derives the week and holds 2026 W1/W2/W3 = 863/773/775 rows. W3 `salary_delta_wow` is non-null for 771/935 |
| 5.4 | hsim reads a frozen schedule's Vegas lines | **Checked: not on the money path.** At the pin `9b341d7`, `live_week.py:231` passes `game_inputs=live_games` and records `hsim_game_inputs` in the receipt. Only the historical benchmark path reads `raw_schedules` |
| 5.3 | the anytime-TD feed is filtered to the "Yes" side? | laptop, by Mon 09-28 (read `prop_market.py` / the ingest; one query on `odds_player_props`) |
| 5.2 | the DST `COEF_L16` is applied to a last-4 average | laptop, by Mon 09-28 (what was it fitted on?) |
| 5.5 | the hsim DST's points allowed are reduced by its own TDs | laptop, lab note. Second critic only; Week-4+ fix if confirmed |
| 5.6 | `MAX_PER_GAME` is invisible to the policy manifest | laptop: add lab-side live levers to the cross-repo manifest check (Week 4) |
| 5.7 | `OPEN-DEFECTS.md` is stale | production, at the Tuesday cutover: fold defects 10–29 in from the Week-2 operating handoff §9 |
| 5.8 | the TabPFN context mixes estimands (inactive zeros vs E[pts \| played]) | laptop: write down the intended estimand in the TabPFN gen README; a test only if it is unintended |

## 1. Monday 09-28 (Week-3 settlement): cheap measurement, no new code on the money path

| id | work | owner | output |
|---|---|---|---|
| **R10** | **Information coefficients in the scoreboard:** IC (active weight vs realized minus projected), projection IC, transfer coefficient, active share, per week | laptop | a scoreboard section, graded from Week 3 on |
| **R2(a)** | **Replicate §2.4 on our own data:** the point-in-time replay projections (`slate_player_features`) + `contest_ownership` (72 weeks). Is the recency part of excess ownership uninformative, and the rest informative? | laptop | a report. **The kill test for R2** |
| **R1(a)** | **Fixed-pool replay:** re-select the archived Saturday pools of Weeks 2 and 3 on the Sunday frames' banks, and score both books on official points | laptop (after L05 and L06 are read) | a report. First evidence for R1 |
| R1(b) | player level: MAE/CRPS of Saturday vs Sunday served projections, Weeks 1–3 | production | the weekly evidence record |

## 2. Week 4 (build Sat 10-03; the laptop is the only host from Tue 09-29)

| id | work | owner | gate |
|---|---|---|---|
| **R1(c)** | **Sunday re-selection as a paper shadow.** Keep the Saturday pool; drop lineups with OUT/IR/Doubtful/inactive players after the 10:30 inactives; re-run `dual_emax` on the T-70 run's banks; paper only, settled Monday | laptop | frozen pre-lock; **first confirm the laptop can build T-70 + re-select inside 10:30–11:15** |
| **R5** | **Kalshi capture begins:** `KXNFLFFPTS`, `KXNFLFFPTSLADDER`, the yardage/TD ladders and the leader markets, snapshotted at the Saturday build and at T-70, append-only, paced (the API returns 429 when rushed). **Operator approval requested** (public API, no account) | laptop | capture only; graded from Week 6 |
| **R11** | Zero-cost part: confirm whether the lab's `book.csv` slot order puts the **latest-starting** eligible player in FLEX. If not, a default-off fix, tested. Operator: the Sunday check of what the live contest CSV shows before the 15:05 kickoffs | laptop; operator | the flex fix enters only after a tested rehearsal |
| **R2(b)** | **The recency-aware predictor:** `surprise_prev` plus its positive part added to `ownership_sets.py`, with train/serve alignment checked like the lag features; walk-forward `validate()` | laptop | only if R2(a) holds |
| **R3** | **Outcome-blind count:** 40+/45+ skill games per simulated world vs 0.93/0.31 per real slate, at the pin | laptop | a report |
| **R4(a)(b)** | **Odds API:** 8–10 books at the same credit cost, and de-vig chosen per market family, walk-forward on history | laptop | player-level MAE/CRPS; no live change yet |

## 3. Week 5 and later: decisions and panels (Mon–Fri only; no panel Sat 10:30 – Sun 12:00)

| when | work | owner |
|---|---|---|
| Week 5 | **Decide R1 for entry** (class-S decision record, from R1(a)(c)). **PREREG-L07** (the R2 sleeve successor: informed-chalk anchor, recency-deflated LOW slots, optional recency-only fade arm, R12 duplication co-arm), frozen after the L05 read. R3 walk-forward exceedance calibration (tw-CRPS at 30+). R4(c) MinT reconciliation, player level | operator; laptop |
| Weeks 6–8 | R6 per-game entropy pooling; R7 third critic and TRIAD panel; R8 dependence card gate (the card in §2.3 as the outcome-free gate); R14 LLM facts log (prospective, graded 4–6 weeks before any use) | laptop |
| 2027 | R9 cross-season player state (Weeks 1–5), with the ADP prior (§2.7) | — |

## 4. Not adopted, or the operator's call

- **R13 contest economics:** for the operator. Rake: the $5 Millionaire 15.9%, the $20 13.2%. Capture the payout tables
  (J11) so ROI is computable.
- **R19 Kalshi as a hedge:** not recommended (it lowers variance, not EV, and costs the spread). Listed only for completeness.
- **R15–R18** (in-game exits, betting splits, inverse-optimisation field, forecast wind): logged; each would need a
  sponsor. R15 is second-order; it goes on the simulator backlog with A28 (TE zero mass, QB early exits).
- **The review's "do not do" list (§4) is adopted as standing guidance.** It includes "don't raise the dose while the
  entry is built on Saturday" (Week 3 holds D12800, the operator's 09-21 decision) and "don't fade total ownership".

## 5. Laptop queue, in order (it is also the production host from Tue 09-29)

1. **Now through Fri 09-25:** L04 (finishes ~08:30); L05 bank 1143 (Fri ~13:00); the L06 smokes and freeze (by Sun 10:00); the
   Saturday paper triple.
2. **Sun after the 12:00 lock:** the workstation runs L06 (production).
3. **Mon 09-28:** the L05 read (at least banks 1140–1142); R10; R2(a); the §5.2/§5.3 checks; the Week-3 Monday scoring.
4. **Tue 09-29:** the cutover (move document §3). The L04 read; the L06 read when complete.
5. **Week 4:** R1(a)(c), R5, R11, R2(b), R3 count, R4(a)(b), in that priority. PREREG-L07 is drafted once R2(a) and L05 are in.
