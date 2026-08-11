# Fantasy Points exact-window redundancy audit

Status: outcome-blind. This audit used only vendor process/usage fields and
the project's strictly-prior feature columns. No realized score, placement,
lineup result, projection residual, or tail label was selected or read.

## Question

Which newly proven exact-window Fantasy Points reports add information that
is not already represented by the project's point-in-time nflverse/NGS/PBP
features?

The comparison uses 2025 vendor windows Weeks 1--4 and Weeks 5--8 against the
project's target-Week 5 and target-Week 9 feature rows respectively. Those
project rows are constructed from weeks strictly before the target week.
Players were matched by normalized name and position. Correlations are
diagnostics of redundancy, not predictive tests.

## Direct-overlap result

| vendor field | existing strictly-prior field | window 1--4 Pearson / Spearman (n) | window 5--8 Pearson / Spearman (n) | disposition |
|---|---|---:|---:|---|
| Advanced Receiving target share | `target_share_l4` | 0.995 / 0.994 (245) | 0.986 / 0.986 (254) | duplicate |
| Advanced Receiving air-yard share | `air_yards_share_l4` | 0.979 / 0.974 (245) | 0.975 / 0.972 (254) | duplicate |
| Advanced Receiving aDOT | `adot_l8` | 0.894 / 0.894 (217) | 0.734 / 0.777 (230) | mostly overlapping |
| Advanced Receiving XFP/game | `xfp_l4` | 0.968 / 0.963 (156) | 0.951 / 0.943 (157) | duplicate for first-pass testing |
| Detailed Snaps total snap share | `snap_share_l4` | 0.999 / 0.998 (357) | 0.991 / 0.990 (365) | duplicate |
| Advanced Rushing YPC | `yards_per_carry_l8` | 0.978 / 0.973 (88) | 0.750 / 0.753 (88) | standard efficiency overlap |
| RB + WR Efficiency YPT | `yards_per_target_l8` | 0.944 / 0.924 (286) | 0.755 / 0.748 (298) | standard efficiency overlap |
| Advanced Passing time to throw | `qb_time_to_throw_l6` | 0.852 / 0.796 (27) | 0.598 / 0.493 (26) | partly overlapping |
| Advanced Passing CPOE | `qb_cpoe_l6` | 0.557 / 0.517 (27) | 0.722 / 0.574 (26) | partly distinct definition/window |
| Separation by Alignment overall score | NGS `separation_l4` | -0.127 / -0.130 (104) | -0.103 / -0.198 (120) | genuinely distinct vendor construct |

Median absolute differences support the same conclusion: target share and
snap share differ by only 0.004--0.010 on a 0--1 scale, while the two
separation products are not even measuring the same construct on the same
scale.

## Support result

The exact four-week coverage splits are useful but not all equally stable.
In the Weeks 1--4 sample, the 392 Separation-by-Coverage rows had median route
counts of 10 versus Man, 27 versus Zone, 7 versus Cover 2, 13 versus Cover 3,
7 versus Cover 4, and 5 versus Cover 6. Only 39/128/30/9 players had at least
20 routes against Cover 2/3/4/6 respectively. Red-zone coverage had a median
of two routes among populated players.

The broader Man/Zone blocks have enough support for a compact current-form
test. Scaling the prior full-season support rule to four games and rounding
up gives at least 50 Overall routes, 10 Man routes, and 25 Zone routes. That
rule covered 118 of 269 target-Week 5 WR/TE salary rows with prior snap data
(43.9%) and 107 of 280 target-Week 9 rows (38.2%). It was fixed without
reading outcomes.

Defense Coverage Matrix has no close existing feature. Both four-week
windows contain all 32 teams, four games per team, 119--180 defensive
dropbacks in Weeks 1--4, and complete Man/Zone and shell deployment rates.
The project's current opponent-secondary fields measure results allowed and
personnel, not defensive scheme frequency.

## Collection decision

Do not bulk-collect Basic stats, Bell Cow, Routes Run, Fantasy Points Scored,
or the overlapping portions of Advanced Receiving, Efficiency and Snaps for
model search. Keep those reports available for validation and operations.

The first incremental historical collection is limited to:

1. Receiving Man vs. Zone;
2. Receiving Separation by Coverage; and
3. Defense Coverage Matrix.

Only Man/Zone rates and separation enter the first diagnostic. Cover
2/3/4/6, alignment, route-break, individual-route, red-zone, offense-matrix,
advanced-passing, advanced-rushing and efficiency fields remain excluded.
Their availability does not license a second field search after outcomes.
