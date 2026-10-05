# Study 1 result: spreading the book across games does not help (2026-10-05)

Written for the operator. The question: Week 4 put 61% of our entries into one game. Would capping how much of the
book any one game can take make us win more?

## Answer: no
- **On 36 historical slates (2023–24):** capping each game's share of the book in proportion to its real chance of
  being a top-3 scoring game did not raise the average lineup's finish. The result is "no difference": slightly
  negative and within noise.
  - What it did do: fewer weeks with no cash at all (32% → 24%; 17% when combined with spreading which contests get
    which lineups).
  - The cost: a slightly lower ceiling (a 194+ lineup in 25% of slates instead of 29%).
  - It did not reduce exposure to a single player busting (the Chase problem).
- **On your real Week 1–4 contests:**
  - The cap changed nothing in Weeks 1–2: the books there were not concentrated enough to trigger it.
  - In Weeks 3–4 it left the money exactly the same and the lineups finished slightly worse.
  - The "fewer empty weeks" effect could not be checked: there were too few cashes in those weeks to tell.
- **The other idea tested, dealing lineups into contests with an offset, cashed fewer tickets (−8%).** It is not
  offered.

## What this means
- The per-game cap is a way to make results steadier, not a way to win more, and on your real contests it did not
  even do that measurably. **It is not being offered as a change.**
- The single-player risk (half the book on Chase) needs a different fix, a cap on any one player's share of ENTRIES.
  That is the next de-concentration test.
- Together with the money test and the contest-type study: none of the changes tested so far turns the system
  profitable. What remains is in projection quality (the O-22 leak fix is in progress) and in contest selection.

## For the record
- Preregistered and frozen before any result was read: `reports/2026-10-05-prereg-study1-deconcentration.md`, with
  dated deviation notes.
- Two problems were caught and fixed BEFORE any result was read, and both are disclosed:
  - a data quirk (defenses filed under a separate game id);
  - a mismatch with the live code's optimizer.
- Full record: system study Addendum 122. Lab ledger row with the verbatim output: nfl2
  `production/s1-deconcentration-20261005`, `results/s1/`.
