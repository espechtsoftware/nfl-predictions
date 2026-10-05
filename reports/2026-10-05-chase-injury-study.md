# The Chase-injury study (Week 4): how much it hurt, and whether we should have used him differently (2026-10-05)

Written for the operator and the reviewer. The operator asked (10-04): "let's do a study about that, of how badly that is
hurting me, and if we should have been smarter about how we used him". Ja'Marr Chase left Week 4 with a concussion
during the game. He had no injury designation before the lock: `injury_snapshots` on 10-02 and 10-04 have no Chase row.

The report gives aggregates only: no entry keys and no dollar amounts. Returns are multiples of fees. The settled
standings imported 10-05 are byte-identical to the files the Sunday analysis used, so Part 1 stands as computed.

## Part 1: the exact damage
**Exposure:**
- 75 of our 154 entries held Chase (48.7%), against a field ownership of 19.5%: 2.5 times the field.
- In 51 of those 75 he was the bring-back against our Lawrence + Parker Washington stack.
- In the book's 110 distinct lineups, Chase is in 54. Only 2 of them also hold his own QB, Joe Burrow; 31 are
  Lawrence stacks.

**What he scored:** 5.7 DK points. His pre-lock projection: mean 20.6, p50 21.4, p90 40.2, p10 6.9. So 5.7 sat below
his 10th percentile.

**The counterfactual** (his 5.7 replaced; "field-adjusted" also moves the field entries that held him and recomputes
each cash line):

| If Chase had scored | Cashes (actual 3), fixed lines | Cashes, field-adjusted lines | Recovery, as a multiple of the week's fees |
|---|---|---|---|
| his projection, 20.6 | 4 | 4 | about 0.08× |
| p75, 33.2 (a proxy) | 8 | 5 | about 0.15× |
| p90, 40.2 | 12 | 7 | about 0.38× |

The book returned 0.42× of fees.

**What it means:**
- At his projection, the injury cost about one cash: a 25x super-satellite in the 594-entry field.
- Chase entries averaged 108.2 points against 122.7 for the rest. That 14.5-point gap matches his 14.9-point shortfall.
- Even at his projection, Chase lineups finished a median of about 52 points short of their cash lines. Only 1 of the
  75 was within 14.9 points of its line.
- Share of the week: Chase cost 7.3 points per entry against projection. That is 37% of the book's net −19.7 miss.
- He was the second-largest drag. Parker Washington was the largest (8.7 per entry, a volume collapse; see post-mortem
  §12), and Garrett Wilson third (6.7).

## Part 2: should we have used him differently? (HINDSIGHT; descriptive)
These are re-deals of the ENTERED book's own 110 lineups into the real Week-4 contests: only which entry gets which
lineup changes. Each is scored the same way as the money gate's replay of the entered book (`scripts/moneygate_chase_hindsight.py`,
money-gate harness branch).
- The 25 plan contests are covered: 152 entries.
- The hand-added Millionaire seat is outside the plan, so "as entered" here is 0.17×, not the week's 0.42×.

| Version | Chase's share of entries | Return (× fees) | Cashes | Mean entry finish (percentile) |
|---|---|---|---|---|
| as entered | 49% (75) | 0.17× | 2 | 44.7 |
| Chase capped at 30% | 30% (45) | 0.35× | 4 | 45.5 |
| Chase capped at 20% | 20% (30) | 0.35× | 4 | 46.1 |
| Chase only in Burrow stacks | 3% (5) | 0.43× | 5 | 52.0 |

**Read this as HINDSIGHT.**
- In a week he left injured, any version with less Chase wins by construction. That is not evidence that capping or
  steering helps.
- The forward-looking test of exactly this question was study 1b (preregistered, 36 slates, reproduced by the reviewer;
  system study Addendum 123):
  - an entry-level player cap halves the damage when a top player busts;
  - but it costs 2.4–4.3 points of average finish over many weeks, against the operator's 1.5-point limit;
  - assignment alone cannot hold the cap. Not adopted.

## What was in our control
- **Concentration, not the player.**
  - Chase was a reasonable pick at his price and projection. The injury was not foreseeable.
  - What was in our control was 2.5 times the field's exposure: one in-game event touched half the book.
  - That concentration is created by the SELECTION step (the selection-redundancy evidence, 10-05). Study 17, running
    now, tests a selector that keeps the best lineups first and reduces this redundancy
    (`reports/2026-10-05-prereg-study17-selection-redundancy.md`).
- **How he was used.**
  - Chase was mostly a bring-back against a Jaguars stack, not part of a Bengals stack (2 of 54 lineups with Burrow).
  - When he left, Cincinnati's points went to Higgins, D. Meyers and Chase Brown, and Burrow threw 54 times. A Burrow
    stack would have kept some of that value.
  - That is one week. The stack-rule question was tested separately in study 15: no measurable difference.

## Files
- **Part 1:** the Sunday-night analysis (code preserved privately in `~/private/pm-week4/pm-players/`).
- **Part 2:** `scripts/moneygate_chase_hindsight.py` (money-gate harness). Private results stay on the laptop. Dollar
  figures are not written under `~/week4-sunday/` (O-24).
