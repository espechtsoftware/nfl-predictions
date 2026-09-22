# The pool cannot reach the winning line — and Week 2's loss was a floor failure

Production's reply to the laptop's supply-versus-retrieval work, plus the Week-1
replication it asked for. Four findings, in descending order of how much they should
change what we do. All of it is retrospective diagnostics on Weeks 1–2; none of it is
a gate, and nothing here has been applied to the Week-3 money path.

---

## 1. The Week-1 replication (requested)

Ran `reports/lab-handoffs/supply_vs_retrieval.py` **verbatim** against the archived
Week-1 run. Validated the shim first by reproducing the laptop's Week-2 numbers exactly
— 197.26 / 157.96 / gap 39.30 / edit distance 5 of 9 / Kamara as the sole never-rostered
player. Byte-for-byte agreement, so the Week-1 run below uses the same instrument.

| | Week 1 | Week 2 |
|---|---:|---:|
| candidates | 3,200 | 12,555 |
| entered | 90 | 97 |
| pool oracle | 236.28 | 197.26 |
| book best | 218.40 | 157.96 |
| **retrieval gap** | **17.88** | **39.30** |
| min edit distance to pool best | 4 of 9 | 5 of 9 |

The shape replicates. The magnitude does not: 17.88 versus 39.30.

## 2. But the retrieval framing does not survive a base-rate check

"We generated thirty lineups at 170 or better and entered none of them" is only
evidence of a retrieval failure if a book drawn **at random** would have entered some.
It would not. Thirty qualifying rows in 12,555, drawn 97 times, is an expectation of
0.23 rows — and a random book enters zero of them **79.2% of the time**.

Hypergeometric expectation for a random K-row book, against what the selector actually
entered:

| | ≥150 | ≥170 | ≥194 | ≥200 |
|---|---:|---:|---:|---:|
| **W1** selector lift vs random | 1.14× | 1.55× | 2.74× | **4.01×** |
| **W2** selector lift vs random | 1.75× | — | — | — |
| W1 P(random book enters zero) | 0.0% | 0.0% | 4.9% | 16.8% |
| W2 P(random book enters zero) | 17.6% | **79.2%** | 99.2% | — |

The selector converts **above** the pool base rate at every threshold where it entered
anything, in both weeks, and its edge *grows* with the threshold in Week 1 (4.01× at
200). Week 1's "6 at ≥220, entered none" is likewise the majority outcome for a random
book (84.3%).

So the two headline lines are not evidence the selector mis-ranks. The real evidence
for that is separate and it is strong — pool `corr(sim_mean, realized)` is **−0.332** in
Week 2 — but the "generated N, entered none" statistic is not part of it. I would drop
that line before this hardens into the programme's central fact.

## 3. What actually binds: the pool ceiling is ~35 points below the winning line

The 150/170/194 thresholds are arbitrary. The line that pays first place is not. Joining
the applied Week-1/Week-2 standings:

| contest | entries | winning line | pool oracle − win | book best − win |
|---|---:|---:|---:|---:|
| W1 $3.5M Millionaire | 831,028 | 273.98 | **−37.70** | −55.58 |
| W1 $400K Play-Action | 158,302 | 263.84 | −27.56 | −45.44 |
| W2 $3M Millionaire | 172,692 | 232.38 | **−35.12** | −74.42 |
| W2 $350K Flea Flicker | 83,200 | 235.48 | −38.22 | −77.52 |
| W2 $100K Huddle | 23,758 | 223.00 | −25.74 | −65.04 |
| W2 SUPERSat (68 entries) | 68 | 182.06 | **+15.20** | −24.10 |
| W2 FFWC SUPERSat (59) | 59 | 183.84 | **+13.42** | −25.88 |

**Our entire pool could not win any contest above 68 entries, in either week.** Perfect
retrieval — entering the single best of all 12,555 candidates — still loses the
Millionaire by ~35 points. The margin is remarkably stable across two very different
slates, and it matches the earlier winning-line join (median −36.5 across 34 historical
slates, 0/34 wins from the whole pool).

This reframes supply-versus-retrieval. Measured against 170, retrieval looks binding.
Measured against the line that pays, **the ceiling binds on both slates** and retrieval
is a second-order concern for first place. Perfecting selection over this pool converts
a large loss into a smaller one.

## 4. Week 2's actual loss was a floor failure, not a ceiling failure

| | book mean | field median (Millionaire) | gap |
|---|---:|---:|---:|
| Week 1 | 149.31 | 141.74 | **+7.57** |
| Week 2 | 98.40 | 113.82 | **−15.42** |

In Week 2 the *typical lineup we entered was worse than the typical lineup the field
entered*. That is a different failure from the one the programme has been chasing, it is
the one that actually cost the week, and unlike the ceiling it is addressable with
correctness work rather than new signal.

### The largest identified contributor: availability is not in the projections

Six of the 97 entered Week-2 rows contained a player who recorded zero DK points —
five of them Tua Tagovailoa, served at DK status **"D" (Doubtful)**. Those six rows
averaged **77.45** against 99.78 for the rest.

Across both weeks, restricted to players the generator could actually use, the served
status field is **monotone** in residual (realized − projection), and separately so in
each week:

| status | n | play rate | mean residual | W1 | W2 |
|---|---:|---:|---:|---:|---:|
| (none) | 732 | 93.4% | −1.02 | −0.58 | −1.41 |
| Q | 14 | 85.7% | −5.50 | −4.75 | −6.07 |
| **D** | **5** | 80.0% | **−12.32** | −6.19 | −16.41 |

**All five Doubtful players across both weeks scored exactly 0.00 DK points**, against a
mean projection of 12.32. Verified against two independent authorities: nflverse
`weekly_stats` has no Week-2 row for any of them, and the one cross-checkable case (Zay
Flowers, Week 1) agrees to the DK 100-yard bonus — `contest_ownership` 29.0 versus
nflverse PPR 26.0. The mechanism is already on the books: projections are
E[points | played] and are never conditioned on availability, the same defect class as
the backup-QB contract issue. 17.7% of the Week-2 pool contains a never-played player,
against 1.1% in Week 1.

### Isolated A/B, and its null test

Re-ran the exact dual expected-max selection with Doubtful players removed from the
selectable universe (pre-lock information only):

| | Week 1 | Week 2 |
|---|---:|---:|
| rows changed | **0 of 90** | 57 of 97 |
| best | +0.00 | +26.58 |
| mean | +0.00 | **+7.26** |

Then the null: 120 draws excluding three *random* players matched on pool usage.

- **best — P(null ≥ +26.58) = 53.3%.** Random triples give +14.39 ± 13.07. The rule sits
  at the 47th percentile. **Its effect on best is indistinguishable from excluding
  arbitrary players** and must not be claimed.
- **mean — P(null ≥ +7.26) = 0.0%.** Random triples give +1.63 ± 1.97. Roughly 2.9 sd
  out, unreached by any of 120 draws. **Real.**

That the *best* moves +14.39 on average when you exclude any three well-used players is
itself a finding: the book is over-concentrated on the selector's favourites.

**Two corrections to my own earlier claims.** I retracted the exposure caps on an
out-of-sample mean failure, then said the retraction was wrong because "GPPs pay the
max" and the caps gained +26.58 on best. The null test says that best-gain was noise, so
that second claim was also wrong — the mean effect is the defensible one here. And the
+26.58 is not attributable to the Doubtful rule specifically.

**What I would propose for Week 3 — operator's call, not applied:** exclude DK-Doubtful
from the selectable universe. It is an eligibility correctness fix, not the variance
trade the caps were; it uses only pre-lock data; it was a provable no-op in Week 1, so
its downside is bounded to slates where a Doubtful player would otherwise be selected;
and it targets the book mean, which is the statistic that actually failed in Week 2. The
evidence is n=5 players — thin, but the effect is total and the mechanism is understood.
The Questionable tier shows the same effect at lower magnitude and is **not** included;
capping Q is a variance trade with weaker support and should be treated separately.

---

## Data deficiency

`nfl_raw.contest_entries.payout` is **NULL for all 1,305,992 rows** across both weeks
(`payout_raw` empty throughout), so realized ROI per contest cannot be computed from the
warehouse. Field score distributions are complete (Millionaire ranks 1–172,692), so cash
*lines* are recoverable but prize *amounts* are not. Logged to README's deficiency table.

## What this does not say

Two slates. The ceiling result is the most robust claim here because it agrees with the
34-slate historical winning-line join. The status finding rests on five players. The
base-rate correction is arithmetic and does not depend on sample size.
