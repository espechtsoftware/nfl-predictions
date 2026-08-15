# Realistic recourse point-in-time scoring reconciliation

Date: 2026-08-15  
Status: implementation prerequisite; **no recourse outcome run licensed yet**

## Purpose

The historical executable-policy estimate needs the DraftKings points that
were knowable at one late-swap decision time. Full-game labels leak the rest
of an in-progress game, while assigning every started player zero discards
information that really was available. `src/nfl_dfs/research/recourse_scoring.py`
now reconstructs skill-player and DST points from timestamped nflverse PBP and
stops at an exact timezone-aware instant.

The scorer mirrors the production full-game definitions in:

- `sql/features/013_player_week_actuals.sql` for skill players; and
- `sql/features/024_team_defense_week.sql` for DSTs, including points-allowed
  exclusions, recoveries, return touchdowns, blocks, safeties and defensive
  conversions.

It also handles pass and rush two-point conversions, passing/rushing/receiving
bonuses, primary and lateral yardage, offensive-category fumbles, blocked-kick
touchdowns and onside-kick recovery touchdowns.

## PIT contract

`points_information_as_of` enforces three disjoint states:

1. **Not started:** zero points. Eventual PBP and final labels are not read for
   the returned score.
2. **In progress:** only PBP rows whose event timestamp is at or before the
   decision instant are scored.
3. **Final as of the decision:** the authoritative full-game label is used,
   but only when the caller explicitly supplies the game in the as-of final
   set. A game cannot be declared final before kickoff.

The output uses the exact status schema already required by
`prospective-recourse-policy-v1`. It records the point source for every row and
declares that no unstarted or in-progress final outcome was used.

## Real-data reconciliation

Read-only validation covered all 2023--2025 regular-season PBP currently in
BigQuery:

- 141,125 PBP rows;
- 54,419 authoritative player-week rows;
- zero scoring-relevant rows with an unavailable wall-clock timestamp; and
- exact reproduction of 2025 Week 1 for every skill player and all 32 DSTs.

Across the full three seasons, the raw structured-PBP skill scorer exactly
matches 54,407 of 54,419 player-week labels (99.978%). The 12 differences are
all rare, multi-lateral end-of-game plays for which nflverse stores only one
lateral-player identity and an aggregate lateral-yard value. Their maximum
absolute difference is 1.7 DK points. The residual identities and differences
are:

| Season-week | Player ID | PBP minus authoritative |
|---|---|---:|
| 2024-03 | 00-0033576 | -1.7 |
| 2024-09 | 00-0036988 | -0.9 |
| 2025-18 | 00-0036252 | +0.9 |
| 2024-04 | 00-0036196 | +0.7 |
| 2024-09 | 00-0039915 | +0.6 |
| 2024-03 | 00-0036261 | -0.5 |
| 2025-15 | 00-0034827 | -0.4 |
| 2023-09 | 00-0036985 | +0.3 |
| 2024-03 | 00-0039351 | +0.3 |
| 2023-16 | 00-0033699 | +0.2 |
| 2024-05 | 00-0039896 | +0.2 |
| 2024-03 | 00-0037525 | -0.1 |

The raw PBP DST scorer matches 1,619 of 1,632 authoritative team-weeks. All 13
exceptions are in 2025, where `team_defense_week` deliberately replaces its
PBP-computed score with the exact historical DraftKings salary-feed label when
one is available. The largest exact-label difference is 8 points. This is why
completed games use the authoritative label rather than pretending that the
PBP approximation is exact.

## Disposition

The implementation is sufficient to represent the information boundary, but
it does not yet license the historical policy estimate. Before that one run:

1. freeze the single decision instant and independently derived final-game
   set;
2. audit whether any of the 12 structurally unresolvable lateral plays occurs
   before the decision time in an in-progress target game and intersects a
   retained candidate identity;
3. verify every completed target game receives an authoritative player and
   DST label, with no fallback;
4. reconstruct the exact retained entry book, player worlds and candidate set
   by checksum; and
5. run the already frozen recourse policy without changing its tail ladder,
   alternative cap, ordering or tie breaks.

The result will remain a descriptive policy-sizing estimate, not unbiased ROI
and not retrospective promotion evidence.
