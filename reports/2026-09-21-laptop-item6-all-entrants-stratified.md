# Laptop review item 6: all entrants stratified — volume and skill, separated

Answering item 6 of `handoffs/2026-09-21-laptop-postmortem-review-round1.md`:

> Winner-only studies cannot establish an edge. Compare all entrants stratified
> by entry count, salary, and contest; separate player decisions from
> entry-volume advantage.

Source: `nfl_raw.contest_entries`, 2026 week 2, the **NFL $3M Millionaire** —
**172,692 entries, all of them**, not the winners. User identity comes from
`entry_name` with the `(i/N)` suffix stripped; the suffix also declares each
user's entry count, so the stratification is read from the data rather than
inferred. No identifiers appear below or anywhere in the repo.

## The two effects separate cleanly, and volume dominates by ~8×

| entries/user | users | mean n | mean pts **per entry** | mean of user's **best** | % of users reaching 194 |
|---|---:|---:|---:|---:|---:|
| 1 | 39,456 | 1.0 | 111.72 | 111.72 | 0.127% |
| 2–5 | 16,767 | 2.8 | 113.17 | 129.87 | 0.382% |
| 6–20 | 3,410 | 9.7 | 115.05 | 149.43 | 1.701% |
| 21–50 | 462 | 31.0 | 116.75 | 165.73 | 7.359% |
| 51–150 | 320 | 121.2 | **120.98** | **185.03** | **31.875%** |

- **Player decisions (per-entry quality): +9.26 points**, 111.72 → 120.98, a
  gain of 8.3% from the lightest to the heaviest bucket.
- **Entry volume (best lineup held): +73.31 points**, 111.72 → 185.03, a gain
  of 65.6%.

**The volume effect is 7.9× the skill effect.** High-volume entrants are indeed
better per lineup — the gradient is monotone across all five buckets, so this is
not noise — but most of what separates their *outcome* from a single-entry
player is simply holding more draws from a similar distribution.

## Skill still compounds, and the compounding is measurable

Predicting each bucket's P(best ≥ 194) from **volume alone** — treating every
entry as an independent draw from the single-entry distribution, p = 0.127% —
and comparing to what actually happened:

| entries/user | observed ≥194 | volume-only prediction | excess |
|---|---:|---:|---:|
| 1 | 0.127% | 0.127% | 1.00× |
| 2–5 | 0.382% | 0.356% | 1.07× |
| 6–20 | 1.701% | 1.222% | 1.39× |
| 21–50 | 7.359% | 3.868% | 1.90× |
| 51–150 | 31.875% | 14.274% | **2.23×** |

At two or three entries, volume explains essentially everything. By 121 entries
the heavy users reach the tail **2.23× more often than their entry count alone
predicts**. So the modest per-entry edge is not decorative: it multiplies
against volume, because the tail is where a small mean shift pays.

**Read together: volume is the dominant lever, and skill is a multiplier on it
rather than a substitute for it.** That is consistent with the Week-2 finding
that our pool was coverage-bound, and it is the quantitative form of the ledger's
"more entries per slate" result — but it also says the two are not alternatives.

## A data gap that bounds this, stated rather than worked around

**`payout` is NULL on all 1,305,992 rows across both weeks, and `payout_raw` is
empty.** Verified directly: the Millionaire's rank-1 through rank-5 rows carry
no payout at all.

So **no ROI or dollar-return figure can be computed from `contest_entries`**.
Everything above is in points and threshold-crossing rates. Any ROI claim has to
come from the operator's own entry-history export, which does carry fees and
winnings. We have not widened any tolerance or imputed a payout to fill this;
it is a missing input, and a deficiency-log row is warranted.

## What was not done

- **Salary stratification** is not included. `contest_entries` carries `lineup`
  as display strings, not salaries; joining to `dk_salaries` per player per
  contest is doable but was not attempted here rather than estimated.
- **Pre-lock signals for misses and successes** (the second half of item 6) is
  the natural follow-on and needs the Week-2 projection batch joined to these
  entries. Say if you want it next.
- This is **one slate**. The gradient is monotone across five buckets and
  172,692 entries, which is why it is reported at all, but a single week cannot
  establish that these coefficients persist.
