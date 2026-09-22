# The exposure cap does not replicate out of sample. Do not enter a capped book.

Operator asked whether any experiment could still improve scores this week. I ran one
today. **It came back negative, and it closes a lever rather than opening one.**

## What I claimed on Week 2

Isolated properly — same pool, statuses, K, contest assignment and objective, cap the only
change — a 25% cap was worth **+11.3 realized mean and +26.6 realized best**, at a cost of
0.8% of the selector's own E[max]. The sign was uniform across all seven cap levels and
both objectives.

I hedged that correctly at the time ("one slate", "not claimed: that caps help in general")
but the tool went into the Sunday build and the direction of travel was positive.

## Week 1, same design, opposite answer

Archived run `20260912T204921889774Z-e7255e9` (LEV 640 / BOOM 2560, 3,200 candidates,
K=90). Both world banks sha256-verified against the receipt; `sel_mean` reproduces to
3.1e-5; **the greedy returns all 90 delivered lineups in exact delivered order**, so the
gate that makes the arms comparable passed before any cap was applied.

| cap | max exposure | sim E[max] | realized mean | best | ≥150 | ≥170 |
|---|---:|---:|---:|---:|---:|---:|
| **none (delivered)** | 68 | 191.12 | **149.31** | **218.40** | **39** | **22** |
| 40% | 36 | 190.65 | 146.85 (−2.46) | 218.40 | 35 | 20 |
| 35% | 31 | 190.49 | 146.30 (−3.01) | 218.40 | 35 | 20 |
| 30% | 27 | 190.35 | 144.30 (−5.01) | 217.34 | 35 | 18 |
| 25% | 22 | 190.03 | 142.55 (**−6.76**) | 217.34 | 35 | 16 |
| 20% | 18 | 189.54 | 143.60 (−5.71) | 217.34 | 37 | 17 |

**Every cap level is worse.** Mean falls monotonically to −6.76, best falls or stays flat,
rows ≥150 drop 39→35, rows ≥170 drop 22→16. On Week 2 the same sweep moved mean +11.3 and
best +26.6 in the *other* direction.

## What that means, stated carefully

**The cap is a variance trade, not an edge.** It does not buy cheap insurance; it pays out
when the book's concentration is on players who bust and it costs when the concentration is
right. Week 2 concentrated on Jefferson, Bijan and the 49ers DST, who busted. Week 1
concentrated on players who hit.

The two slates were also very different in supply: Week 1's pool oracle was **236.28 with
104 candidates ≥194 and 1,215 ≥150**; Week 2's was **197.26 with exactly one ≥194**. The
cap helped on the starved slate and hurt on the rich one, which is the opposite of a robust
lever.

**Caveat I am not hiding:** the two runs differ in dose as well as slate — Week 1 selects 90
from 3,200 (2.8%), Week 2 selects 97 from 12,555 (0.8%). A cap bites differently at
different selection ratios, so "slate" and "dose" are confounded here and I cannot separate
them with two runs. But every way of reading it argues against deploying: either the effect
is slate-specific, or it is dose-specific, and this week's dose is Week 2's while the slate
is neither.

## Decision

**No capped book is entered for Week 3.** I had already decided that on a weaker argument —
protecting the prospective shadows — and I was right for the wrong reason. This is the real
reason.

`scripts/exposure_cap_book.py` **stays wired and stays reporting**. The exposure sheet is
worth reading before upload, and the status rules it carries (Doubtful → 0) are unaffected:
those are an availability control, a different thing entirely, and they replicate 13/13.

## What this does not touch

The Doubtful exclusion stands. It rests on 13 player-weeks, zero played, zero snaps, at the
highest mean salary of any cohort — measured across both weeks, not one.

Reproduce: `reports/cap-out-of-sample/` — `build_w1.py` (hash-gated rebuild), `sweep_w1.py`
(gate + sweep), `w1_cap_sweep.csv`.
