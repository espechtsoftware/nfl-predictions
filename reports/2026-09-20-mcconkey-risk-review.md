# K97 Ladd McConkey risk review

> **Current-artifact correction:** this review was written against the earlier
> pre-Tua refresh and reported 26 rows. The exact regenerated/uploaded book
> now contains 28 McConkey rows, including positions 27 and 28. See
> [`2026-09-20-mcconkey-first30-reconciliation.md`](2026-09-20-mcconkey-first30-reconciliation.md)
> for the byte-bound reconciliation.

## Finding

This is a real concentration risk, but it is not evidence that the K97 CSV is
corrupt or that McConkey was mistaken for a backup. The current regenerated
book contains McConkey in 28 of 97 lineups (28.9%). Every one of those rows carries the same
signals: DraftKings `Questionable`, report `Questionable`, Friday `Limited`,
and `market:no_props`.

The official Chargers injury report records DNP on Wednesday and Thursday,
limited participation Friday, and a Questionable designation. On Sunday,
Ian Rapoport reported that McConkey was pushing to play through a cracked rib,
that there was optimism he could go, and that he would wear a flak jacket if
active. The team did not elevate a receiver. Those facts make active status
more likely, but they do not establish a normal snap count or normal receiving
efficiency.

Sources: [Chargers official injury report](https://www.chargers.com/news/raiders-injury-report-ladd-mcconkey-fantasy),
[Raiders/NFL injury report](https://www.raiders.com/news/las-vegas-raiders-injury-report-2026-season),
and [Sunday report relaying Rapoport](https://www.fantasypros.com/nfl/news/609161/ladd-mcconkey-ribs-pushing-to-play-sunday.php).

## Why this is different from last week's Flowers problem

Flowers was a much stronger pregame failure signal: a large exposure to a
player carrying a Doubtful designation. McConkey is Questionable, has a
credible report that he intends to play, and has not been officially ruled out.
The current protocol correctly leaves a Q player in the book until an official
OUT/IR/inactives update. The model therefore has not made a row-identity or
backup-player error.

The exposure is still high for a Q player with two DNPs, a rib fracture, and no
matched player props. `market:no_props` is not proof that he will sit, but it
is evidence that the market did not provide a normal projection/role signal.
If he is active but limited or used as a decoy, the same 26 rows can underperform
together. This is the exact portfolio risk the current hard-OUT-only rule does
not cap.

## Contest placement

The risk vetter kept the first 26 delivered entries free of McConkey. The
promoted Millionaire row (row 1, candidate 2123, source book-rank 33) has no
McConkey flag. McConkey first appears at delivered row 27, so the highest-prize
entry is not exposed to this particular uncertainty. The current 28-row
concentration is in the lower contest blocks and is still material there; rows
27 and 28 are in the $40K Nickel block.

## Recommendation for today

Do not mass-swap him before the official inactive report solely because of the
news report or absent props. A preemptive swap would throw away the upside if
he plays his normal role, and there is no validated live rule that converts
`Q + no_props + injury` into an automatic zero. Keep him as a priority watch.

At the official inactive window:

1. Fetch fresh DraftKings status and the official inactives list.
2. If McConkey is OUT/IR, replace all 28 affected rows with the normal fresh
   vetting/replacement chain and rerun promotion. Do not hand-edit only the
   Millionaire file; the Millionaire row is not affected, while lower contest
   blocks are.
3. If he is active, retain the book for this week but record the result as a
   risk-policy observation: the current process can still leave 26/97 exposure
   to a Q/no-props player despite pushing those rows below the first 26.

The shared `apply_swaps.py v1` tool should not be the only safeguard: before
live use it needs a fail-closed check that every incoming draftable ID is
present in the fresh DraftKings response. A missing ID currently becomes an
empty status and can pass the `not O/OUT/IR/D` check.

## Follow-up experiment

For Week 3, shadow a predeclared exposure policy for `Questionable + no_props`
and `Questionable + DNP/LP` separately. Compare no cap, cap 20%, and cap 10%
using the same frozen candidate pool, with mean, P220, P230, max-of-K, and
contest-prefix costs. Treat the policy as a risk/robustness experiment until
it has prospective evidence; do not silently turn it into an automatic hard
exclusion.
