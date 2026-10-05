# Preregistration: study 15, a looser QB stack (QB + 1 pass catcher + bring-back) (FROZEN 2026-10-05)

This is the design the reviewer set on 2026-10-05 for the operator's request. It is frozen before any experiment,
driver or reader exists. Any later change is a dated deviation note appended at the end; the text above the notes is
never edited.

**The operator (10-05, verbatim):** "so at the moment we still require a QB, 2 WRs and a bring back from the other team?
If that's the case, I feel that is too much and want to change it" and "I think only a QB, 1 WR and a bring back is
sufficient for a game we expect to be a shootout".

## Why
- **The live rule** is `PRODUCTION_STACK = StackRules(qb_stack_min=2, bring_back_min=1)`: every lineup holds the QB, at
  least 2 WR/TE from his team, and at least 1 RB/WR/TE from his opponent.
- **The operator's version** relaxes the first to "at least 1". It is a MINIMUM, so the optimizer may still take two.
- **Priors** (both ledgers checked):
  - LEDGER 016 "single" tested EXACTLY one partner and NO bring-back, as a 40-of-80 sleeve, on a best-score endpoint:
    −0.68 at k150, null to negative.
  - PREREG-015 / LEDGER 043: the house rules as a package (QB+2, bring-back, RB rules, $49k floor) were worth +3.6
    against legality-only.
  - The reviewer's 09-24 note: the stack rule's per-lineup lift flips between weeks.
  - X1 step 2: the field under-owns the top-total games relative to the odds. This bears on a shootout-only relaxation.
- The operator's exact version (at least 1 partner, bring-back kept) has never been tested on its own, nor on entry
  finish.

## Arms (the same L-series harness as studies 1 and 1b; co-run; fresh banks)
- **C:** the live rule (qb_stack_min 2, bring_back_min 1).
- **S1:** qb_stack_min 1 everywhere, with bring_back_min 1.
- **S1-HT, the operator's actual hypothesis:** a per-QB minimum, linear in the solve. For each QB q, the number of
  partners is at least m_q × x_q.
  - m_q = 1 if q's game ranks in the slate's top 2 by PRE-LOCK game total (study 1's `game_ranks`: ties broken by game
    id), else 2.
  - The bring-back constraint is unchanged.
  - It is built as one optional per-team minimum on the lab's `StackRules`. When unset, the formulation stays
    byte-for-byte the production one.
  - It is built only with a unit test: an MILP check that a top-2 QB accepts 1 partner and a non-top-2 QB still needs 2.
    If it needs more than that, S1-HT is recorded as NOT BUILT and S1 runs alone.

## Fixed across arms
- K = 105, the row cap 52 and DST cap 26, MAX_PER_GAME 4, the $49k floor, ≤ 7 shared (study 1's C builder; only the
  StackRules change).
- The LAG-only ownership term at λ = 0.10.
- The Week-4 mean-track plan (147 entries), dealt by the head layout with the small-contest overlap limit, M = 5 and
  ceiling 10. Both are hard-set and asserted, never inherited.
- L13's 36 slates (2023–24), the gated field sampler (200,000), and FRESH banks 1407/1408, verified unused by the
  all-branch bank-label scan before any run. Smokes use throwaway bank 1406, discarded unread.

## Endpoints and decision rule
- **PRIMARY:** the mean dealt-entry finish percentile, arm − C, paired per slate (banks averaged).
  - Season-clustered bootstrap (slates resampled within season), B = 20,000, seed 20261005.
  - Two-sided intervals at 0.9875 each: the family is 0.975 over S1 and S1-HT (0.975 if S1 runs alone).
- **TICKET GUARD** (pre-declared; studies 1 and 1b showed that mean finish and line-crossings can move in OPPOSITE
  directions, and a stack rule acts mainly on the tail). Each is reported with its interval, at the same level:
  - tickets: the dealt entries at or above each contest's line, summed per slate, arm − C;
  - best ≥ 200: the per-slate indicator, arm − C.
- **Verdict per arm:**
  - **PASS:** the primary lower bound > 0, both season means ≥ 0, and the ticket interval NOT entirely below 0. A
    reversible Week-5 trial is offered (adoption track v2, with rollback).
  - **WORSE:** the primary upper bound < 0. Not offered.
  - **NOT OFFERED (the ticket guard):** the ticket interval lies entirely below 0, whatever the primary.
  - **NO DIFFERENCE:** otherwise. It is reported to the operator as: "no measurable effect; switching is your
    preference, reversible, with the rollback".
- **Vacuity:** the census reports, per arm, the share of rows and of dealt entries whose QB has exactly one same-team
  WR/TE. An arm dealt identically to C on more than 80% of slate-banks is a DEAD LEVER, with no verdict.
- **Secondaries:**
  - zero-ticket slates, the worst-decile slate and best ≥ 194;
  - the stack-shape distribution (1/2/3+ partners; bring-backs);
  - the book's predicted-ownership sum;
  - the maximum entry exposure.
- **Integrity:**
  - the reader is frozen and its sha recorded before any scored bank;
  - an outcome-blind support census (the vacuity counts, and how often S1-HT's relaxation is available and used);
  - a full-path smoke on bank 1406, discarded unread;
  - unit tests, including the MILP boundary test, and a mutation of the per-QB minimum that must be caught.
- **Power** (from study 1's already-read banks, a book-changing arm like G at the entry level): SE ≈ 0.0063, so the
  two-sided 0.9875 half-width is about 0.016. Only an effect of about ±1.6 percentile points or more is detectable. A
  NO DIFFERENCE is therefore likely, and the decision wording above handles it.

## Transfer (descriptive)
If an arm passes or comes out NO DIFFERENCE, the live main book needs the change in `union_reselect`'s
optimize call (`StackRules`), reviewed before any entry. On the real 2026 W1–4 pools it is checked through the
money-gate harness (as study 1's AG). It is not built before the panel reads.

---

## Deviation note 1 (2026-10-05, before any scored bank): code, reader frozen, census
**Code:** nfl2 `production/s15-qb-stack-20261005` @ 7d2bd02.
- Reader `scripts/s15_report.py`: sha256 `817574f7961e0154a0619d208ea021338b283320812a1c431df644047d18c0be`.
- Experiment `experiments/s15_qb_stack.py`: sha256 `32931536d7e58bea31bc61702c42dd5568dc594be0d8d96dca84b33ed129dfc9`.
- `src/nfl2/core/lineup.py` adds `TeamStackRules`, a subclass with `qb_stack_min_by_team`. `StackRules`, and every
  `asdict` of it, is unchanged.
- **Tests:**
  - an MILP boundary test: a relaxed team's QB takes 1 partner, any other QB still needs 2;
  - a plain StackRules gives an identical solve;
  - a bad minimum raises;
  - the arm, shape and reader rules.
  - A mutation that ignores the per-team minimum is caught.
- **Smokes (bank 1406, throwaway):** the mechanics smoke ran on 2023 W7. The full path ran on 2024 W3 with build and
  reader rc 0, and its output was deleted unread.
- **Banks:** 1407/1408. In the all-branch scan they are unused; since then, the only bank labels committed are this
  session's 1404/1405 (used) and 1406 (throwaway).

**The outcome-blind census** (banks 1407/1408, mechanics only, 72 slate-banks, no errors; verbatim in the lab at
`results/s15/CENSUS_s15.txt`):

| arm | rows with 1 catcher | dealt entries with 1 catcher | entries changed vs C | rows with a top-2-game QB |
|---|---|---|---|---|
| C | 0.000 | 0.000 | – | 0.438 |
| S1 | 0.927 (min 0.686, max 1.000) | 0.934 | 0.995 | 0.490 |
| S1HT | 0.654 (min 0.010, max 0.990) | 0.657 | 0.887 | 0.701 |

**Read before any outcome:**
- Neither arm is vacuous: S1 turns almost every row into a one-catcher stack, and S1HT concentrates on the top-2-total
  games (70% of rows against C's 44%).
- No book is short.
