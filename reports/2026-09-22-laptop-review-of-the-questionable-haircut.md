# Review: the Questionable haircut is safely off — and if enabled, the evidence says ~0.80, not 0.86

Second-party review of `dfefbc55` on the shipping branch (added after my `654202e6` review) and
the image it replaced mine with.

## Deployed state — verified, safe

| link | evidence |
|---|---|
| shipping tip | `dfefbc5548649c6c3baef55ce8e074ccc8004156` (one commit past the reviewed `25a159df`) |
| Cloud Build `fe88fb38` | **SUCCESS**, `_CODE_SHA` = that full commit |
| build digest | `sha256:98efdfa6…7c27df9` |
| `project-slate` job | **same digest**, pinned, updated 19:57 UTC; **no `Q_HAIRCUT` env var set** |

The only diff from the image I reviewed is the haircut (six files), so **the QB gate is carried
forward unchanged**. With `Q_HAIRCUT` unset the default is 1.0, and
`apply_questionable_haircut` returns the frame untouched when `h == 1.0` — **a true no-op.**
Only `proj_points` and `value` are ever scaled, which is right: the money path reads
`proj_points` alone.

**One operational note:** an invalid `Q_HAIRCUT` (outside (0, 1], or non-numeric) raises and
**stops the whole `project-slate` run.** That is deliberate fail-closed design, but it means a
typo in that one env var blocks Sunday's projections. Worth knowing before anyone sets it.

## The magnitude, if it is ever enabled

The code comment and HANDOFF cite a pooled walk-forward relative ratio of **0.86** (2018–2024)
and note **0.77–0.83 in 2022–24**. The walk-forward correctly counts non-players as zeros — the
right target for a haircut on an `E[points | played]` projection. But the panel it runs on has
the **2022 inactive-row break** (`6e487bb8`):

| season | Questionable rows | **recorded as played** |
|---|---:|---:|
| 2018 | 246 | **100.0%** |
| 2019 | 240 | **100.0%** |
| 2020 | 278 | **100.0%** |
| 2021 | 309 | **100.0%** |
| 2022 | 471 | 68.4% |
| 2023 | 502 | 63.3% |
| 2024 | 421 | 60.8% |

**Before 2022 a Questionable player who sat is simply absent from the panel**, so the 2018–21
seasons measure *performance given that he played* and cannot see the weeks he did not. Only
2022–24 measure what the haircut is for: **sits plus slumps**. The pooled 0.86 averages the two
and **understates the haircut.**

**The evidence-based multiplier is the 2022–24 range, 0.77–0.83 — call it ~0.80** — which also
sits closer to the served-2026 figures production quotes (0.45× and 0.63× of healthy, with the
market blend in between).

"Questionable under-ran healthy in 7 of 7 seasons" remains true — both halves are negative — but
it is two different effects: **4 seasons of performance-only, 3 of performance-plus-availability.**

## How this squares with my own Questionable numbers

Earlier today I reported that Questionable players were the **best value per dollar** on the board
in 2026 Weeks 1–2 (77.4% played, 1.274 PPR per $1k against 1.003 unflagged) and warned that a
blanket **exposure cap** on Q would destroy value. That is not in conflict with a haircut:

- A **cap** removes Q players regardless of price. That throws away the value.
- A **haircut** corrects their projection to what they actually deliver, and leaves the optimizer
  free to keep them wherever the discounted price still makes them good value — which my numbers
  suggest it often will, because DraftKings discounts Q salaries by more than they under-deliver.

So a correctly-sized haircut is the right tool and a cap is the wrong one. The decision to enable
remains the operator's; this is input to it, not a recommendation to enable before Sunday.
