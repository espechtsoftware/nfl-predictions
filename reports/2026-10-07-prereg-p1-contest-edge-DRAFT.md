# Preregistration DRAFT: P1, the prospective contest-class edge record and its lower-confidence-bound stake rule (2026-10-07)

**Status: DRAFT** by the laptop, for the reviewer to edit and freeze (the operator's approved-plan item P1; his
Wed 10-07 directive). Week 5 locks Sunday 10-11. Nothing here has read any Week-5 outcome. The freeze must come before
Week 5's standings load (Monday 10-12).

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
- **Primary (finish level, the 10-05 method):**
  - Each entered row's z against the SAME week's Millionaire field: (row points − the field's mean) / the field's sd. The
    class's edge is the mean z minus the class's break-even z.
  - The break-even z is FROZEN here from the 10-05 latent model, which was calibrated on W1–4 and placed each class's
    exact ladder and entries: +0.12 to +0.22 sd. **The reviewer fixes one value per class before the freeze** (the
    10-05 scratch, recomputed from `v_dk_payout_structure`).
- **Secondary (money):**
  - The realized multiple per class (tie-split payouts), its ticket/cash rate against the break-even rate (the flat
    ladders: 1 / the pool ratio × the field's paid rate), and the 10-05 clustered model interval (a common weekly
    slate shock; ICC 0.062, with 0.15 / 0.25 as sensitivity).
  - The monkey percentile beside every line (the money gate's rule 3).
- **Beside them (P3's prereg):** the paper arms per class at each contest's own line.

## 5. The stake rule (Addendum 95 item 5; fixed now)
- **What is computed:** per class, the one-sided 95% lower confidence bound of the prospective finish-level edge (mean
  z − the class's break-even z). The week is the cluster, W5 onward only. It is reported each Monday from Week 8 (four
  prospective weeks).
- **The rule:** a class carries **"stake supported"** only while its LCB is above 0. Otherwise it reads **"no evidence
  for stake"**.
  - Realized money never turns the flag on: its power within a season is close to zero (§1).
  - The flag is advice. Contest choice and stakes stay the operator's.

## 6. Power, stated before any outcome
Fourteen prospective weeks (W5–W18), the 10-05 model (total sd 0.95, week ICC 0.062):

| Rows a week in the class | SE of the mean z | LCB margin (one-sided 95%) | True edge above break-even for 80% power |
|---|---|---|---|
| 26 (the whole book) | 0.080 sd | 0.131 sd | 0.198 sd |
| 12 | 0.095 | 0.156 | 0.236 |
| 4 | 0.138 | 0.227 | 0.344 |
| 2 (the Millionaire) | 0.185 | 0.304 | 0.460 |

- **The bar this sets:** a class turns "stake supported" this season only if its rows run about 0.2–0.5 sd ABOVE their
  break-even.
- **Against the W1–4 record:** our rows ran −0.15 sd against the Millionaire field, with break-even at +0.12 to
  +0.22. A flag this season needs a large real improvement, not a modest one.
- **Fewer weeks are weaker still:** the margins above scale by about √(14 / weeks).

## 7. Review points
- **Weekly (Monday, with settlement):** the record, as data only.
- **After W8 and W12:** the reviewer reads the record against §5. Anything beyond the frozen rule is exploratory.
- **Season end:** the full record and the flags.

## 8. What it can and cannot do
- **It can say, before the fact,** which classes show a finish-level edge large enough to see in this season's weeks.
- **It cannot confirm a small edge** (1.15×) in money in any class this season. In top-heavy contests a losing season is
  the likely outcome even with a real edge (the 10-05 table: 82–99% for GPPs and the Millionaire).
- **It changes nothing on the money path** without the operator.

## 9. Open points for the reviewer before the freeze
1. **One break-even z per class** (§4): recompute from the views and the 10-05 model, or keep the 10-05 values.
2. **The z reference:** the same-week Millionaire field (the 10-05 method, one yardstick for every class), or each
   contest's own field? The latter is noisier for small satellites.
3. **Unequal rows a week:** classes have different row counts each week. Weight weeks equally, or by rows?
4. **The paper arms (P3):** in this record, or kept in P3's own ledger?
