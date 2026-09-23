# Production response to the winner-anatomy review (`dd529ddc`)

Reviewed: `reports/2026-09-22-winner-anatomy-and-follow-up-review.md` on
`review/external-suggestions-20260922`. Every production number below was recomputed here from the
warehouse and the archived live runs; scripts are in production's session scratchpad, results only.

## 1. Verified

- **The corpus shape (§2.2) reproduces exactly** on the Week-2 12,555-candidate pool with slot-summed
  Millionaire ownership (mass 899.4%): 3+ skill players under 5% **89.9%**, 0–1 under 5% **1.4%**, no
  20%+ player **36.3%**, chalk core **7.2%**, ≥ $500 salary left **44.0%**.
- **Chalk-core selection moves the book the way §2.4 predicts — where the pool has the supply.** Same
  archived pools, live dual expected-max selector, live availability rules, pre-lock *predicted*
  ownership (production's reduced version of the §2.4 model: no `proj_p90`, which the live frame lacks;
  within-slate Spearman on the 2026 live frames **0.684 (W1), 0.618 (W2)**):

| week | arm | eligible | book best | units | top 1% | cashed | book mean |
|---|---|---:|---:|---:|---:|---:|---:|
| 1 | live | 3,126 | 232.1 | 42.4 | 3 | 27 | 149.8 |
| 1 | chalk ≤2 sub-5%, ≥1 at 20%+ | 670 | 218.4 | 48.0 | 2 | 32 | 152.5 |
| 1 | chalk ≤1 | 312 | 218.4 | **66.0** | 2 | **44** | **163.3** |
| 1 | chalk ≤2 + salary ≥ $49,500 | 528 | 218.4 | 58.5 | 2 | 39 | 156.5 |
| 2 | live | 8,249 | 184.5 | 18.0 | 1 | 12 | 106.7 |
| 2 | chalk ≤2 / ≤1 / ≤2+sal | **96 / 7 / 67** | — | — | — | — | — |

  Week 1: book mean +2.7 to +13.5, cashes 27 → 32–44, units up in every chalk arm; the best lineup falls
  (232.1 → 218.4) because the pool's chalk candidates top out at 218–221. Week 2: the pool holds too few
  chalk-core candidates to fill 97 entries at all.

## 2. What this changes in §4

**A selection-only chalk-core shadow from the live pool (§4 row 1) is not feasible on a Week-2-like
pool.** The generator must produce the shape: the §2.7 item 1 **chalk-core boom sleeve** (constraints
in predicted-ownership space inside the per-world solves) is the only form that can be built. It is a
generation change in the nfl2 live path, so for Week 3 it can be a **paper shadow only**: a default-off
flag plus a separate shadow build Saturday, scored Monday with the scoreboard.

## 3. Corrections to the review

- **`own_shadow` is not uniformly broken.** For 2026 Week 1, `pred_own` (the naive column) has
  Spearman **−0.18** with actual slot-summed Millionaire ownership (the review's −0.11 is the same
  finding), but the trained **`booster_own` column has +0.63**. The review's conclusion applies to the naive
  column; the booster is usable, if weaker than the §2.4 model.
- **Live ownership prediction is weaker than the historical gate suggests.** The reduced model scores
  0.62–0.68 on the 2026 live frames against the review's 0.75–0.81 walk-forward on the replay panel. A
  Spearman ≥ 0.7 gate on 2025 actuals may pass a model that is below 0.7 live; gate on the 2026 weeks too.
- **"12% of winners legal under the house rules" contradicts the August anatomy's 43 of 51.** That needs
  a reconciliation before it is cited: it decides whether the stack mandate excludes most winners.

## 4. Accepted

- **"Too small to change which lineups win" was measured at the wrong unit** (player MAE, salary-blind
  top-k). Withdrawn as a general statement; the lineup-level effect above is the right unit.
- **Market bias is a ranking bias for a salary-constrained optimizer** (studs vs value). Test at lineup
  level: re-optimize with a bonus-aware conversion and score with the scoreboard decomposition.
- **P_MIX cannot be decided on two live weeks.** For the record, the two-week illustration: live rules
  beat P_MIX in Week 2 (18.0 vs 12.0 units; contamination 7.2% vs 9.3%) and tie in Week 1. The decision
  belongs on the historical panel against the four live availability rules.
- **`MAX_PER_GAME=4` is adopted on thin evidence**, with L01 as the check (production's end-to-end sweep:
  neutral across seeds; +1 first-place-level lineup in one Week-1 run).
- **Route Share weekly reads need a declared stopping rule** before Week 3 is read. Production will
  propose one in the handoff before Sunday.
- **The Questionable factor for a Saturday build that is followed by Sunday replacement is closer to 0.89
  than 0.80.** Small; the operator's call.
- **The scoreboard gains the heavy-user (51–150-entry) benchmark and the §2.2 corpus shares.**

## 5. Production's own finding this review overturns

Production's QB+3 test (two weeks, one seed) raised the pool's best lineup in both weeks (253.5, 214.5)
and a 50/50 QB+3 mix gained +4/+3 units. §2.6 has 3+ stack depth in 2% of 69 historical winners. The
two-week gain is not evidence against 69 slates: **QB+3 is dropped**; a relaxed stack inside the chalk
envelope (§2.7 item 3) is the stack test worth running.

## 6. Proposed Week-3 actions (paper only; nothing enters the money path)

1. Production: fit the pre-lock ownership model on the Week-3 frame once projections exist; publish
   predicted ownership to the build host; report its 2026-weeks Spearman.
2. Laptop (nfl2, light CPU): a default-off **chalk-core boom sleeve** flag (≤1 and ≤2 sub-5% predicted,
   ≥1 at 20%+, salary ≥ $49,500) with tests; a Saturday **paper shadow** build beside the entered build.
3. Monday: scoreboard with corpus shares + heavy-user benchmark; chalk shadow vs entered book.
4. Next lab slot: the §4 replay-panel test, frozen before any read.
