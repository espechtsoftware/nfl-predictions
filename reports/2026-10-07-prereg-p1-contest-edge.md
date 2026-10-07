# Preregistration: P1, the prospective contest-class edge record and its lower-confidence-bound stake rule (FROZEN 2026-10-07; amendments 1 and 2 before any Week-5 outcome)

**Status: FROZEN 2026-10-07** by the reviewer, before any Week-5 outcome.
- Drafted by the laptop: v1 `5e6fffdd`, v2 `a9736719`. The reviewer's four decisions are folded in (§9).
- The operator's approved-plan item P1 (his Wed 10-07 directive).
- It holds from Week 5. Week 5 locks Sunday 10-11, and its standings load Monday 10-12, after this freeze.
- **AMENDMENT 1 (2026-10-07, before any Week-5 outcome; a disclosed drafting error, found by the laptop while building
  the reader).**
  - §4's yardstick read z = (points − the field's mean) / the field's sd and called it the 10-05 method. It was not. The
    10-05 analysis, and the break-even values and power table calibrated on it, use the latent normal score of the
    finish position.
  - §4 now states that score. Nothing else changes: the break-even table, the classes, the week weighting, the t bound,
    and the power table, whose total sd 0.95 and ICC 0.062 were measured on this latent z.

**Units:** multiples of the fee, rates and z-scores only. Dollars stay in BigQuery and private files.

## 1. Why
- **P1 has already answered the question on W1–4.** The analysis ran 10-04/05, reviewer-checked:
  `briefings/2026-week-04/2026-10-05-p1-contest-type-edge.md`.
  - No contest type can be shown +EV.
  - Money cannot confirm a 1.15× edge within a season in any type. Satellites need about 170–1,200 weeks; the
    Millionaire about 0.3–3 million.
  - The 2026 satellite and supersat books ran below break-even: 0.12×, robust up to a week correlation of 0.15.
  - The finish-level yardstick (rows against the field, in sd) is more efficient, but still needs about 100–250 weeks.
- **What is still open:**
  - (a) A weekly record per contest class, fixed BEFORE the outcomes, so the season's evidence accumulates honestly.
  - (b) The stake rule written down as a rule: Addendum 95 item 5, a lower-confidence-bound rule. A lucky week must
    never read as an edge.
- **This study adopts nothing.** Contest choice and stakes are the operator's (R6 / R7). It supplies the evidence each
  Monday.

## 2. Data (existing pipelines; nothing new collected)
- **The payout ladders:** `nfl_raw.dk_payout_ladders` and its views (sql/raw/011; built 10-07).
  - The plan's contests are loaded each week from the pre-lock contest-details capture; any contest missing a capture is
    fetched after settlement (public API, no login).
  - Realized payouts use `v_dk_entry_tier.split_payout_multiple`: DraftKings' tie split. Never the reported-rank
    `payout_multiple`.
- **Our entered books' settled results:** the DK entry history (private) and the standings import (`contest_entries`).
- **The fields:** `contest_entries`, post-settlement.

## 3. Contest classes (fixed now; assigned from the ladder BEFORE the result)
Each contest's class comes from `v_dk_payout_structure` and its name:
1. **Flat ticket ladders** (satellites and supersats: kind 'ticket', every paid position equal), split by capacity into
   ≤ 600 and > 600.
2. **The Millionaire.**
3. **Other large cash GPPs** (kind 'cash', capacity ≥ 10,000).
4. **Qualifiers** (kind 'mixed': a seat plus cash, e.g. the FFWC).
5. **Everything else:** reported, never ruled on.

## 4. Measures, per class, per week from W5 (W1–4 reported as the baseline, never pooled into the decision)
- **Primary (finish level; the 10-05 method; the reviewer's decisions 2 and 3):**
  - **The yardstick** (AMENDMENT 1, 2026-10-07): each entered row's z against the SAME week's Millionaire field is the
    10-05 latent score z = Φ⁻¹(1 − p).
    - p = (position − 0.5) / N; position = 1 + the number of the field's entries (ours removed) strictly above the row;
      N = that field's size.
    - The break-even values below were calibrated on this scale.
    - Own fields are too small and noisy for the satellites.
  - **The unit is the week, weighted equally.** Per class: the week's mean z over the class's entered rows; the class's
    edge = the mean over weeks of (the week mean − the class's break-even z).
  - **Beside it, descriptive:** each contest's own-field finish percentile.
  - **A limitation, stated now:** satellite fields are probably sharper than the Millionaire's, so a satellite's true
    break-even z is probably HIGHER than the value below. The flag (§5) is, if anything, generous there.
- **The break-even z per class, FROZEN here** (the reviewer's decision 1):
  - Each value is the 10-05 latent model's calibrated μ at an expected multiple of exactly 1.00. Total sd 0.95, week
    ICC 0.062, each type's actual ladder and entries (scripts and CSVs: the laptop's 10-04 P1 scratch,
    `power.py` / `power_by_type.csv`).
  - Where a class holds several 10-05 types, the value is their mean weighted by the Week-5 plan's entries. A class the
    Week-5 plan does not use takes its 10-05 plan's types.
  - **No later re-freeze:** if a class's ladders change materially later in the season, the record reports it and the
    value stays.

  | Class | Break-even z | Computed on (10-05 types: their plan and entries) |
  |---|---|---|
  | Flat ticket ladders, capacity ≤ 600 | **0.158** | The W5 plan's 28 contests, 51 entries: SAT_402 0.164 (W4 plan: 1 contest), SAT_OTHER 0.152 (W4: 3 contests, 6 entries), SS25_594 0.162 (W4: 4, 40), SS25_198 0.159 (W4: 2, 10), SS25_118 0.159 (W4: 2, 6) |
  | Flat ticket ladders, capacity > 600 | **0.175** | SS25_2378 0.175 (W4 plan: 4 contests, 80 entries); not in the W5 plan |
  | The Millionaire | **0.216** | MILLY 0.216 (W4 plan: 1 contest, 2 entries; the W1 57-entry plan gave 0.224) |
  | Other large cash GPPs (capacity ≥ 10,000) | **0.199** | GPP_LARGE 0.202 (W2 plan: 1 contest, 23 entries), GPP_MID 0.187 (W2: 3, 7), weighted by those entries; not in the W5 plan |
  | Qualifiers (a seat plus cash) | **0.207** | FFWC_QUAL 0.207 (W3 plan: 1 contest, 2 entries); not in the W5 plan |
  | Everything else | — | reported, never ruled on |

- **Secondary (money):** per class, the realized multiple from tie-split payouts (`v_dk_entry_tier.split_payout_multiple`)
  and the ticket/cash rate against the break-even rate (the flat ladders: 1 / the pool ratio × the field's paid rate).
  The 10-05 clustered model interval goes beside it: a common weekly slate shock at ICC 0.062, with 0.15 / 0.25 as
  sensitivity.
- **The paper arms (the reviewer's decision 4):** kept in P3's own record, never in this one. P1 is our ENTERED rows
  against break-even, for stakes; mixing in paper arms would blur the stake rule. The Monday report prints the two side
  by side.
- **Weeks:**
  - A week with a standings-import failure is skipped and recorded.
  - A week entered under an operator override counts as entered.
- **The W1–4 baseline note:** W4 had 1 contest (196305080) excluded from the money gate for lack of a pre-lock ladder;
  its ladder was fetched 10-07 after settlement. From W5, every plan contest's ladder is captured pre-lock, or fetched
  after settlement under this rule.

## 5. The stake rule (Addendum 95 item 5; fixed now)
- **The bound:** per class, the one-sided 95% t lower bound on its week means (model-free; the week is the unit),
  i.e. the mean over weeks of (week mean − break-even z) − t(0.95, n − 1) × sd / √n.
  - It is computed from W8 on, and only for a class with at least 4 prospective weeks.
  - With fewer weeks, the class carries no flag.
  - The 10-05 clustered-model interval is reported beside it.
- **The rule:** a class carries **"stake supported"** only while that bound is above 0. Otherwise it reads **"no
  evidence for stake"**.
  - Realized money never turns the flag on: its power within a season is close to zero (§1).
  - The flag is advice. Contest choice and stakes stay the operator's (R6 / R7).

## 6. Power, stated before any outcome
Fourteen prospective weeks (W5–W18), the 10-05 model (total sd 0.95, week ICC 0.062), normal approximation:

| Rows a week in the class | SE of the mean z | LCB margin (one-sided 95%) | True edge above break-even for 80% power |
|---|---|---|---|
| 26 (the whole book) | 0.080 sd | 0.131 sd | 0.198 sd |
| 12 | 0.095 | 0.156 | 0.236 |
| 4 | 0.138 | 0.227 | 0.344 |
| 2 (the Millionaire) | 0.185 | 0.304 | 0.460 |

- **The t bound is wider with few weeks.** t(0.95, 3) = 2.35 at 4 weeks against 1.645, so a flag at W8 needs about 1.4×
  the margins above, before the √(14 / weeks) factor.
- **The bar this sets:** a class turns "stake supported" this season only if its rows run about 0.2–0.5 sd ABOVE their
  break-even.
- **Against the W1–4 record:** our rows ran −0.15 sd against the Millionaire field, with break-even at +0.16 to +0.22.

## 7. Review points
- **Weekly (Monday, with settlement):** the record, as data only.
- **After W8 and W12:** the reviewer reads the record against §5. Anything beyond the frozen rule is exploratory.
- **Season end:** the full record and the flags.

## 8. What it can and cannot do
- **It can say, before the fact,** which classes show a finish-level edge large enough to see in this season's weeks.
- **It cannot confirm a small edge** (1.15×) in money in any class this season. In top-heavy contests a losing season is
  the likely outcome even with a real edge (the 10-05 table: 82–99% for GPPs and the Millionaire).
- **It changes nothing on the money path** without the operator.

## 9. The reviewer's decisions (10-07), folded in
1. One break-even z per class, the 10-05 values (§4 table); no later re-freeze.
2. The yardstick is the same-week Millionaire field, with the satellite limitation stated and own-field percentiles
   beside it.
3. Equal week weights, the week as the unit; the one-sided t bound from W8 with at least 4 weeks; the clustered
   interval beside it.
4. P3's arms stay in P3's own record.
Also added: standings-import failures are skipped and recorded; operator-override weeks count as entered; the W4
exclusion note.
