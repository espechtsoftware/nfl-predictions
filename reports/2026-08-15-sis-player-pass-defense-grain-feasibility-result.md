# SIS player pass-defense grain feasibility result

Date: 2026-08-15 06:47 CDT  
Protocol: `20260815-sis-player-pass-defense-grain-feasibility-v1`  
Disposition: **passes the acquisition/schema gate**

## Result

After a fresh terminal-authenticated SIS session, the frozen sample completed
on its first visible Submit and used one of its three-request hard ceiling.
The response and independently downloaded CSV contained 56 player-game rows,
8 stable player identities, and 17 played weeks for the one frozen 2025 team
(the omitted week is its bye). No performance value, fantasy outcome, lineup,
or contest result was read by the gate.

Every registered requirement passed:

- the independently recovered request matched 2025 Weeks 1--18, SIS team ID
  1, CB versus Wide WR, Pass Defense Totals, Split by Game;
- 56 rows is nonempty and below the paid 200-row cap;
- every row had `Games=1` and the correct season/team/week scope;
- the CSV and API response had the same row count;
- the export exposed both `Cov. Snaps` and `Tgts` denominators;
- every row had a stable player ID, unique at player/week grain, and the API
  identity resolved to the CSV player name; and
- the machine result reported no failures.

## Durable identities

- Retrieval time: `2026-08-15T11:46:57.995580+00:00`
- Frozen protocol SHA-256:
  `c2d869eb18777cbfdd9c1cc4adf23ebf080a63a876957e0dabb41144d2553b0e`
- Licensed CSV SHA-256:
  `d407ddea442f2766c4a8ad794f5e7ea600d1f09dd2f9d0e2abda2e08dc955388`
- Machine result SHA-256:
  `74dfd08e48ff05d1b14829d120db19d08d83a65ed21a76ff6b527364e6431f65`

Raw licensed rows, request identities, and browser state remain in the
gitignored `sis/player-pass-defense-grain-feasibility-v1/` directory.

## Interpretation and next action

This establishes that the normal SIS player-grain surface can supply the
volume denominators and identities needed for a receiver-specific defensive
context. It does not establish predictive value and cannot change the money
policy.

The pass licenses one separately frozen, bounded historical acquisition and a
score-free G0/G1 dependence protocol. That next protocol must fix the seasons,
team/alignment slices, provider-request ceiling, strictly-prior windows,
sparse-cell shrinkage, QB-WR/QB-TE/WR-WR/RB-RB and multiplicity metrics before
additional SIS values are read. A passing score-free gate may license only a
2026 paired shadow, not retrospective promotion.
