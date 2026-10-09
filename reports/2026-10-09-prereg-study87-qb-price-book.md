# Preregistration: study 87, his whole book with a top-4-game QB stacked with his top receiver, plus the price rules (TE ≤ $5,000, DST ≤ $3,000, at least one WR ≤ $4,500, no TE in the flex), in the harness (DRAFT 2026-10-09)

**Status: DRAFT 2026-10-09 (07:08 CDT)** by the outside reviewer — **THE DESIGN IS COMMITTED BEFORE STUDIES 85'S AND 86'S READS**
(the same slates). The code and its shas follow; the reviewer reviews, runs the binding census and FREEZES; the laptop acks.
- **Banks and seed:** the reviewer assigns them (proposed 1731–1736, seed 20261132; the laptop scans them and the derived bases
  1781–1786 / 2431–2436 first).
- **Target:** after studies 85 and 86.

**Units:** probabilities, counts and rates only. Dollars stay in BigQuery and private files.

## 1. Why — his request
- **The operator, 10-09, in the outside reviewer's session (after study 84's read, before 85's and 86's; the laptop records it
  verbatim):** "Let's queue up an experiment with this. / QB from one of top 4 point total games / TE <= 5000 / D <= 3000 / 1 WR
  <= 4500 / Top receiver same team as QB / WR or RB in Flex" — and, right after: "In this case at least 1 wr <= 4500 can be
  more."
- **Use:** an experiment — information for his decision (the outside reviewer's reading, as for 85 / 86).
- **What was tested before (the prior):** forcing the QB's game or side and his top pass catcher read at or below his book —
  study 73's TOPG5_QB1 (the favourite's QB + top pass catcher in the top-5 games) −0.036; study 74's STACK4_B −0.029; study
  80's top-4-game QBs (−0.004 underdog, −0.038 favourite). The price pieces: study 84's TE ban alone −0.012 on its banks (+0.047
  on 81's). **Prior: NO DIFFERENCE or negative.**
- **THE NOISE FINDING (study 84, disclosed here as a fact, not a rule change):** the same rule read +0.047 on banks 1689–1694 and
  −0.012 on 1713–1718 (study 81's NOTE5K_ALL = study 84's TE_ONLY, call for call), and study 83's COMBO −0.019 vs +0.010 in 84.
  The intervals resample slates; they do not include the bank-to-bank variation of the simulations and the field draws, so
  they understate the uncertainty. Leans of a few points are within that variation.

## 2. Arms (`experiments/s87_qb_price_book.py`)
**The book:** study 48's harness through study 85's module (sha-asserted; study 84 / 81 / 80 / 73 underneath), plus study 70's
frozen `top_wr` (`s70_topwr.py` `d622a211…`, the same top receiver as production's `top_receivers`). LIVE = 48d's 41 rows with
the cheap +2 block, on Rev6 (`plan-week5-rev6-s24.json` `ac10ddf6…`).
- **THE RULES, on EVERY BOOK solve (j < 26; spares never), whatever the cell:**
  - **QBTOP4:** "top 4 point total games" = study 73's `game_order` (the games with a QB in the pool, by game_total
    descending, ties by game id), the top 4; every pool QB outside them (either side) is banned;
  - **TOPREC:** the lineup holds its QB's team's top receiver — study 70's `top_wr`: **the highest-SALARIED WR of the team in
    the pool (WRs only; ties: the higher projection, then the id). A TE is never the "top receiver" under it** (if he meant a
    WR or TE, that is his to say before the freeze). The lab optimizer's interaction floor over the pairs (QB, his team's top
    WR), weight 1, floor 1;
  - **TE5000:** every pool TE priced > $5,000 banned (a TE at $5,000 allowed);
  - **DST3000:** every pool DST priced > $3,000 banned;
  - **WR1PLUS:** at least one WR priced ≤ $4,500 (set_constraints [(those WRs, ">=", 1)]; more allowed — his clarification);
  - **FLEXNOTE:** at most one TE (the flex is a WR or an RB).
  - The rules that apply are ONE solve (the bans, the constraints and the floor); an infeasible one is re-solved at the cell's
    own rules with none of them and recorded once (studies 81–85's fallback). The cells, their quotas and stacking rules, the
    cheap block, the caps and the dealing are his live book's.
- **THE ARMS:** **LIVE_CB**; **BOOK87** (all six rules); **PRICE87** (TE5000 + DST3000 + WR1PLUS + FLEXNOTE); **QBTOP87** (QBTOP4 +
  TOPREC). The two parts on the same banks show which half drives BOOK87.

## 3. The read (the reader `scripts/s87_report.py`)
- Study 63's frozen reader for the statistics, study 83's `his_rule` printed for reference; each arm − LIVE_CB on P(≥ 1 big
  seat), the 2023–24 read (36 slates, two-sided 0.95, B 20,000) and the 2022 check, the guards, expected big seats, P(≥ 2), l02,
  the projection cost.
- **NO AUTOMATIC DECISION:** information for his decision. Under no true effect an arm is "not negative" on both 2023–24 and
  2022 about one time in four; with study 84's bank-to-bank finding, a lean of a few points is not a result.

## 4. What the harness can and cannot say
- **The real-book check first** (the laptop's, outcome-blind, W4, OFF `a4ab2839`): how many of his rows break each rule today;
  the parts the dk-status route can emulate (the QB and price bans) and their FP cost; the floor and the WR / flex rules cannot
  be emulated that way.
- Infeasibility: a QB from the top 4 games whose top receiver is out of the pool, with the price rules, may leave few lineups;
  the census reports infeasible solves by arm (above 5% goes to the reviewer before the freeze).
- Path dependence; the simulator's mean; closing lines.

## 5. Production
- None unless he decides to use it; a production version would be a fresh build (bans, an own-team top-receiver floor, the
  constraints) with parity against this study's frozen wrapper, its format agreed with the laptop first.

- **BEFORE HE ACTS ON ANY ARM (the reviewer's forward rule, 10-09):** it is first re-read on a second, disjoint bank set (the same code and reader, new banks and seed), and both reads and their difference are reported before any option is built.

## 6. Smoke, census and integrity
- Bank 1406 only, when the machine is free: the mechanics smoke, the binding census, the full-path smoke (reader exit and line
  count only). Shas in the next commit.
- **Code:** nfl2 `production/s87-qb-price-book-20261009` (to branch from study 85's).
