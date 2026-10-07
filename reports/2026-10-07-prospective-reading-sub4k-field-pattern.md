# A frozen prospective reading: the sub-$4,000 field pattern, Weeks 5–8 (FROZEN 2026-10-07; descriptive, gates nothing)

**Status: FROZEN 2026-10-07**, before Week 5's Millionaire field is loaded (Monday 10-12).
- Proposed by the outside reviewer and relayed by the laptop. Frozen here by the reviewer, with the wording below.

## The pattern
- In the regulars' own portfolios on the real 2026 Millionaire fields of Weeks 1–4, lineups with 2+ non-DST players
  salaried under $4,000 reached the top 1% more often than the same user's lineups with 0–1.
- The measure: the Mantel-Haenszel odds ratio within user-week strata (users with 20+ entries). Weeks 1–4: 1.88
  [1.74, 2.01]; by week 1.69 / 2.46 / 2.30 / 2.10.

## The instrument (pinned)
- Production's Monday refresh, learning step 5: `scripts/field_pattern_monitor.py` at production `3e657c2a`,
  sha256 `d5246f23282133ca73cd015e2f566fc2c04dc18f820e312e6d6fc7bc65ce3f7e`. It is byte-identical to the outside reviewer's `e8390d73`.
- It reports each week's odds ratio for 2+ vs 0–1, on the week's largest contest, with a 95% interval by bootstrap over
  user-weeks (1,000 reps, seed 5), and the pooled ratio over the weeks given.
- Any change to the monitor before Week 8's read voids this reading, unless it is re-frozen before the affected week's
  field loads.
- **Re-pinned 2026-10-07, about 11:30 CT, before Week 5's field loads** (this rule applied). Production `937415b3` (the
  outside reviewer's `e58eb9e7`) changed the monitor for robustness only:
  - unpriced rows are dropped before the integer arrays (an unpriced player cannot be rostered);
  - a game without a total ranks last (this affects the game-coverage table, not the odds ratio);
  - an uninformative bootstrap returns NaN.
  The pattern's definition, the user filter, the contest and the bootstrap are unchanged. **The pinned instrument is now
  sha256 `881ad086a77264117d8a4042b24432f9ad65f84306f8a6d05a7aa8d31c151717`** (production `937415b3`); it supersedes
  `d5246f23…`.

## The reading (frozen)
- The pattern **holds prospectively** if BOTH:
  1. the week's odds ratio is > 1 in at least 3 of Weeks 5, 6, 7 and 8 (a week whose field cannot be loaded counts as
     not > 1);
  2. the pooled Weeks 5–8 ratio has a 95% lower bound > 1.
- Otherwise it **does not hold prospectively**.

## What it can and cannot say
- **Descriptive only; it gates nothing.** It is an association with the REALIZED top 1%, within users, and it says
  nothing ex ante.
- A player's salary is pre-lock, but whether two cheap players boomed together is the outcome, so lineups that hit are
  selected on it.
- **Study 53 is the ex-ante test** (`reports/2026-10-08-prereg-study53-cheap-pref.md`). If it reads ADOPTABLE /
  ENTERABLE, this monitor is the weekly real-field context beside study 38's paper arms (amendment 6f), not a substitute
  for either.
