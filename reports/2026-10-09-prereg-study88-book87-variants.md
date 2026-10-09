# Preregistration: study 88, his study-87 book on a fresh draw, with a cheaper QB, with a TE allowed in the flex, and both, in the harness (DRAFT 2026-10-09)

**Status: DRAFT 2026-10-09 (09:29 CDT; the reviewer's RUN with conditions folded in)** by the outside reviewer — **THE DESIGN IS COMMITTED BEFORE STUDY 87'S READ** (study 87
is running on the same slates). The code follows (committed before 87's READ, the reviewer's timing rule); the reviewer
reviews, runs the binding census and FREEZES; the laptop acks.
- **Banks and seed:** **1737–1742, seed 20261133** (the reviewer's RUN, pending the laptop's scan of them and the derived bases
  1787–1792 / 2437–2442).
- **Target:** after study 87.

**Units:** probabilities, counts and rates only. Dollars stay in BigQuery and private files.

## 1. Why — his request
- **The operator, 10-09 (during study 87's run, before its read; in full, his typing kept; recorded verbatim with his typos in
  production HANDOFF `d8fd5461`):** "My suspicion is we are going to find that the last test we set up - with the QB from on of the top 4 point total
  games, a lower priced tight end, a cheaper defense, at least 1 wr <=4500, top receiver from same team as QB and WR or RB in flex
  is going to outperform everything else. Premature to say, but that looks more like the way I believe winners are structured.
  Please consider other options along those lines - perhaps with a slightly cheaper QB - that you think are good to test based on
  what you see in historic results"
- **What the 2026 W1–4 Millionaires show** (the outside reviewer's scan4, top 1% vs the field, weeks equally weighted, per week;
  aggregates only; `~/private/winner-shapes-2026/scan4.py`):

| Per lineup | Top 1% (W1 / W2 / W3 / W4) | Field | Top below the field in | His W5-style book |
|---|---|---|---|---|
| a QB priced ≥ $7,000 | 0.03 (.07 / .02 / .00 / .03) | 0.09 | 3 of 4 weeks | 0.15 |
| a TE priced ≥ $5,000 | 0.12 (.09 / .04 / .07 / .29) | 0.28 | 4 of 4 | 0.42 |
| a DST priced ≥ $3,000 | 0.36 (.52 / .32 / .20 / .39) | 0.45 | 3 of 4 | 0.50 |
| a TE in the flex | 0.37 (.16 / .38 / .55 / .40) | 0.28 | **above** in 3 of 4 | 0.54 |
| QB + 2 pass catchers | 0.44 | 0.30 | above in 3 of 4 | 0.46 |
| no bring-back | 0.41 | 0.57 | below in 3 of 4 | 0.42 |

  - **The cheaper QB is supported** (the top avoids $7,000+ QBs); **the cheap TE is the strongest pattern**; the cheap DST mildly.
  - **The "no TE in the flex" rule is NOT supported** — the top 1% used a TE in the flex MORE than the field. The data support a
    cheap TE, not keeping TEs out of the flex. Hence the TE-flex arms below.
  - QB + 2 and bring-backs: his book is already at the top's rates; nothing to change.
- **Study 87's own read is not seen** (this design comes first); study 84's caution applies: one read moves several points
  across bank sets, so **BOOK87 itself is re-read here on a fresh draw** — the forward rule's second read.
- **The prior:** NO DIFFERENCE for each variant against BOOK87 (the in-study comparisons on the same banks).

## 2. Arms (`experiments/s88_book87_variants.py`)
**The book and the rules:** study 87's frozen module (`s87_qb_price_book.py`, sha-asserted; its `qb_price_rules`, `rule_sets`,
`arm_rules` imported, never copied), the same harness, his live book with the cheap +2 block, Rev6.
- **All arms but LIVE_CB are built WITHOUT the usage caps** (his 87 amendment: the QB cap 5, the player cap 13, the DST cap 6
  removed; the overlap limit 4 kept), so the variants compare with BOOK87 on equal terms.
- **THE ARMS:**
  - **LIVE_CB** — the reference, with the caps;
  - **NOCAP** — his live book without the caps;
  - **BOOK87** — study 87's book (a top-4-game QB with his top WR, TE ≤ $5,000, DST ≤ $3,000, at least one WR ≤ $4,500, no TE in
    the flex) on this fresh draw;
  - **CHEAPQB** — BOOK87 + every pool QB priced **≥ $7,000** banned ("a slightly cheaper QB"; the scan's threshold);
  - **TEFLEX** — BOOK87 **without** the no-TE-in-flex rule (a TE ≤ $5,000 may be the flex);
  - **CHEAPQB_TEFLEX** — both changes.
- One combined solve per book solve (bans, constraints, the top-WR floor), infeasible → the cell's own rules, recorded; spares
  never — study 87's mechanics exactly.

## 3. The read (the reader `scripts/s88_report.py`)
- Study 63's frozen reader for the statistics, study 83's `his_rule` printed for reference.
- **Each arm − LIVE_CB** (his live book) and **each variant − BOOK87** (the change alone, same banks), on P(≥ 1 big seat) per
  slate, the 2023–24 read (36 slates, two-sided 0.95, B 20,000) and the 2022 check; NOCAP − LIVE_CB; expected big seats, P(≥ 2),
  l02, the projection cost, the concentration (the top QB's rows and share).
- **Information for his decision.** BOOK87 here + study 87's BOOK87 are the two reads the forward rule asks for; both are
  reported side by side with their difference before any option is built.
- Plainly: study 84's bank-to-bank finding applies; under no true effect a version is "not negative" on both 2023–24 and 2022
  about one time in four; the slates are the ones studies 78–87 read; picking the best of several variants on the same slates
  flatters it.
- **The BOOK87 replication (the reviewer's condition):** the reader prints BOOK87 − LIVE_CB in exactly study 87's form (the same
  decision-arm block), so the Addendum sets the two reads (two disjoint bank sets) side by side with their difference.

## 4. What the harness can and cannot say
- **The real-book checks** (the laptop's, outcome-blind, W4, OFF `a4ab2839`): the cheaper-QB ban's extra cost on top of
  BOOK87's bans (the dk-status route; uncapped), and how many top-4-game QBs are priced under $7,000 on W4.
- **Feasibility:** the top-4 games' QBs priced under $7,000 can be few (the high-total games often hold the elite QBs); the census
  reports the QBs allowed per slate-bank (minimum), infeasible solves per arm and per slate, and the concentration.
  - **If the fallback fires on more than 5% of an arm's ruled solves (CHEAPQB most likely), the reviewer is told before the
    freeze** (the reviewer's condition): a diluted arm reads toward LIVE_CB, and it is noted, not read as a result.
  - **Concentration:** the CONCENTRATION lines of study 87 for every uncapped arm; with fewer cheap top-4 QBs, CHEAPQB can
    concentrate harder than BOOK87 — flagged in the smoke and the census.
- Without the caps one QB can take most of the book (study 87's smoke: up to 15 of 26 rows); a live version would also lift
  production's caps (a large money-path change).
- The simulator's mean, not FP's; closing lines.

## 5. Production
- None unless he decides; any live version is a fresh build with parity against the frozen wrappers, its format agreed with the
  laptop first; the forward rule (two reads) is met by study 87 + this study for BOOK87, and only by this study's single read for
  each variant.

## 6. Smoke, census and integrity
- Bank 1406 only, **after the laptop's calibration run has finished** (the laptop's machine order, 10-09: 87's READ and its
  reproduction, the calibration run, then this smoke): the unit tests, the mechanics smoke, the binding census, the full-path
  smoke (reader exit and line count only). Any code change the smoke forces is a new commit with its diff disclosed.
- **Code:** nfl2 `production/s88-book87-variants-20261009` @ `49db37c6` (committed 09:34:25, BEFORE study 87's READ — 87's scored
  run was still going; branched from study 87's `01869883`):
  - `experiments/s88_book87_variants.py` `a387b349…` (pins s87 `85adf47b…`; its `rule_sets`, `arm_rules`, `qb_price_rules`
    imported; `run()` is 87's with only the listed edits, a test asserts it);
  - `scripts/s88_drive.py` `badc6fb8…`; `scripts/s88_census.py` `b7aacdc7…` (+ each variant's identity to BOOK87);
  - **`scripts/s88_report.py` (the reader) `be54fc38…`** (seed 20261133); `tests/test_s88_book87_variants.py` `4c453d13…` (9 tests;
    the text-parity ones pass; the importing ones wait for a machine gap).
