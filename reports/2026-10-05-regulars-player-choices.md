# Which players the max-entry regulars choose, and why (2026 Weeks 1–4)

2026-10-05. Operator request: "go deeper and get into the specific players they are choosing — grouped by the user …
are they picking players that have better matchups (using our FP or SIS data), players that had a good prior week …
let's try to get deep into their strategy so we can match or beat them."

This is descriptive. Nothing here changes production. The tests it proposes are at the end, and also as study-list item 22.

## Who and how

- **The regulars.** The same 117 users as `reports/2026-10-05-max-entry-regulars.md`: 100 or more entries in each of the
  four 2026 Millionaires. They were chosen by entry volume, not results, so the cohort is not selected on outcomes. As a
  group they finish in the top 1% at 1.26–1.97% of entries every week, against 1% by chance.
- **Their tilt on a feature.** Within each week and position, every player's feature is standardised among players at
  least 0.2% owned. The tilt is the mean of that score over the regulars' picks minus the same mean over the rest of the
  field's picks. A tilt of +0.10 means their players sit 0.10 standard deviations higher on that feature than the rest
  of the field's players do. It is measured on players, not lineup shape; shape is in the earlier report.
- **What the reasons are built from.** Only facts known before lock:
  - salary, our projection, and FP's projection (Week 4 only: the FP projections capture began that week);
  - the Vegas team total and spread;
  - DK points, usage, salary change and Millionaire ownership from the previous one or two weeks;
  - the opposing defence: DK points it allowed to the position and EPA it allowed, 2026 to date from box scores, pbp
    and SIS, plus 2025;
  - FP's O-line and WR/TE coverage-matchup grades. Through Week 3 FP builds these from 2025 data; the vendor calls this
    its early-season regime.

  Realized points are kept apart and labelled as outcomes.
- **Counting.** Picks were counted in BigQuery from every Millionaire lineup: 0.81M in Week 1 and 0.14–0.16M in Weeks
  2–4. "Ours" is every entry of our book that week, across all contests.

Scripts and full output are private (`~/private/week4-monday/regulars_players*.py`, `players/`), because per-user
rows name the users.

## 1. The size of the edge: about 6 points per lineup, every week

The regulars' player choices outscore the rest of the field's choices in every week. The measure is each player's
share among the regulars minus his share in the rest of the field, times his realized DK points, summed over players.

| | W1 | W2 | W3 | W4 | mean |
|---|---|---|---|---|---|
| Regulars vs the rest of the field (points per lineup) | +4.9 | +8.4 | +6.4 | +4.7 | **+6.1** |
| Our book vs the rest of the field | +2.9 | −9.7 | −6.2 | −2.4 | **−3.8** |

- **By person.** 92% of the 117 regulars individually have a positive realized tilt.
- **By position** (mean per week):

  | | QB | RB | WR | TE | DST |
  |---|---|---|---|---|---|
  | Regulars | +0.4 | +2.3 | +0.4 | +3.0 | 0.0 |
  | Ours | −1.2 | −0.5 | **−6.7** | +3.1 | +1.5 |

- **It explains their results.** Scaled against each week's lineup-score spread (sd 24–29) and its top-1% line, an edge
  of +4.7 to +8.4 points predicts a top-1% rate of 1.6–2.4%. They achieved 1.3–2.0%. Their edge is mostly in which
  players they pick, not in having a secret shape.
- **Where we lose.** Our loss is almost entirely at WR, through a few heavy exposures that did not score. For example:
  W2 Justin Jefferson 57% of our entries vs 19% of the field (8.5 points); W4 Garrett Wilson 54% vs 12% (5.7) and
  Jordan Addison 55% vs 23% (9.1).

## 2. What they lean toward, before kickoff

Tilts are pooled over weeks and positions. The share of users column is the share of the 117 whose own tilt has the
same sign: the higher it is, the more this is a shared habit rather than a few people.

| Feature (pre-lock) | Regulars' tilt | Share of users, same sign | Ours |
|---|---|---|---|
| **Salary increase since last week** | −0.11 | 95% negative | −0.07 |
| **DK points the opponent allowed to the position, 2026 to date** (1–3 games) | −0.13 | 93% negative | −0.12 |
| **FP projection above ours (W4 only)** | +0.13 (RB +0.38) | 92% positive | −0.15 |
| FP O-line grade (rush for RB, pass otherwise) | +0.05 | 90% positive | +0.09 |
| **Last week's points above our projection** | −0.12 | 89% negative | −0.13 |
| Points per $1k (our projection) | +0.13 | 88% positive | +0.32 |
| EPA the opponent allowed, 2026 to date (pass, or rush for RB) | −0.07 | 87% negative | −0.05 |
| Questionable tag | +0.04 | 86% positive | −0.01 |
| Target or carry share last week | +0.07 | 85% positive | +0.13 |
| **DK points last week** | −0.08 | 84% negative | +0.01 |
| DK points the opponent allowed to the position, **2025** | +0.04 | 76% positive | +0.03 |
| FP WR/TE coverage-matchup grade (2025-based) | +0.03 | 74% positive | +0.08 |
| Field ownership (log) | +0.03 | 68% positive | −0.05 |
| Team implied total, game total, spread | about 0 | about 50% | |

In plain words, the shared habits are these:

1. **They sell last week's big game and buy last week's dud.** They underweight players who scored big last week, beat
   their projection, or rose in salary, and overweight good-role players coming off a bad game. The lists in §4 show
   it every week:
   - sold: Derrick Henry in W2 (after 38.3) and W4; Caleb Williams in W2 (after 37.3); Jaxon Smith-Njigba in W3
     (after 45.5); Kalif Raymond in W4 (after 21.0);
   - bought: Ja'Marr Chase in W2 (after 3.2); T.J. Hockenson in W4 (after 3.1; 30% vs 14%, scored 27.9); Chase Brown in
     W4 (after 8.9; 29% vs 15%).
2. **They distrust this season's tiny matchup samples.** A defence that gave up a lot to a position in its first one
   to three games is avoided, not chased. The rest of the field chases it. Last season's defence numbers and FP's line
   grades get a mild positive tilt instead.
3. **They buy volume and value, not points.** They favour a high target or carry share and points per dollar. Where FP
   projected more than we did, they sided with FP (Week 4, strongest at RB).
4. **They lean on cheap tight ends.** These were among their largest overweights:

   | Week | Player | Regulars | Rest of field | DK points |
   |---|---|---|---|---|
   | W1 | Michael Mayer | 40% | 27% | 9.2 |
   | W2 | Dalton Schultz | 34% | 21% | 29.0 |
   | W2 | Michael Mayer | 25% | 12% | 5.3 |
   | W3 | Hunter Henry | 8% | 3% | 1.5 |
   | W4 | T.J. Hockenson | 30% | 14% | 27.9 |

   Mark Andrews was overweighted in W2–W4. TE is their largest positional point edge (+3.0 per lineup).
5. **They do not fade chalk.** Their players are owned at about field rates or slightly more. Their differentiation
   is player choice among similar prices plus the lineup construction already reported, not low ownership.

Their realized edge shows **no** link to Vegas totals or spreads: everybody reads those.

**Holding the other features fixed.** A joint fit per position (W2–4) keeps most of this.

- For every position, last week's DK points has a negative coefficient: QB −0.15 (se 0.08), RB −0.25 (0.11),
  WR −0.14 (0.05), TE −0.20 (0.11).
- So do the salary rise (RB −0.24, se 0.07) and the 2026 DK points allowed (WR −0.21, se 0.03; RB −0.15, se 0.07).
- Points per $1k is positive (RB +0.35, TE +0.48).
- For QBs, a higher team total counts once the spread is held fixed (+0.32, se 0.15), and so does being the underdog
  at a given total (spread −0.17, se 0.09; in the frames a positive spread means the team is favoured). This is the
  "trailing QB throws more" read.

**Users differ.** The 117 are not one strategy. Across users, the realized-points tilt is the only feature strongly tied
to each user's top-1% rate (Spearman 0.56). The pre-lock tilts most associated with a higher top-1% rate are: the
coverage-matchup grade 0.41, points per $1k 0.34, the 2025 defence numbers 0.33, our projection 0.31 and slightly
higher ownership 0.29. That is four weeks of results, so it is suggestive only.

The user analysed separately earlier is the least projection-driven of the group. They lean against ownership (−0.05)
and against high game totals (−0.10). They follow the shared anti-recency habit.

## 3. Do those habits point at real misses in our projection?

The test is our pre-lock projection's miss (realized DK minus our projection) for players at least 0.5% owned, W2–4,
386–390 player-weeks. It is Spearman with each feature: + means players high on the feature beat our projection.

| Feature | All (position-standardised) | QB | RB | WR | TE |
|---|---|---|---|---|---|
| Opponent's DK points allowed, **2025** | **+0.12** | +0.15 | +0.02 | +0.12 | +0.28 |
| FP O-line grade | +0.07 | +0.14 | +0.02 | 0.00 | +0.27 |
| Opponent's DK points allowed, **2026 to date** | −0.06 | −0.18 | −0.13 | 0.00 | −0.08 |
| Opponent's EPA allowed, 2026 to date | −0.08 | −0.13 | −0.24 | +0.04 | −0.14 |
| DK points last week | −0.09 | −0.08 | −0.01 | −0.10 | −0.20 |
| Target or carry share last week | −0.12 | −0.08 | −0.11 | −0.12 | −0.08 |
| Points per $1k (ours) | −0.15 | −0.13 | −0.17 | −0.18 | −0.15 |
| Field ownership | −0.10 | −0.03 | −0.11 | −0.15 | −0.09 |

Week 4 only: FP's projection ranked realized points slightly better than ours (0.40 vs 0.38, n 125). FP's disagreement
with us pointed the right way (FP minus ours vs realized minus ours, 0.12).

**What this says.** Our projection under-rates last season's defence quality and FP's line grades. It over-rates this
season's soft-looking matchups, last week's scorers and our own best "value" plays. On four of these the regulars lean
the right way:
- last season's defence;
- the line grade;
- distrust of the 2026 samples;
- selling last week's scorers.

On value we lean the same way they do, but about 2.5 times harder (+0.32 vs +0.13). Our value calls are exactly where
our projection is most optimistic. This is consistent with the earlier finding that the book concentrates on our own
top-ranked rows.

**How much weight this bears.** Three weeks, about 390 player-weeks, and the features were chosen after looking. The
standard error of each correlation is about 0.05. This is a hypothesis list, not evidence for a change. A July addendum
(system study Addendum 6) already named "the field's recency bias" as exploitable. That finding came from winners'
lineups, which are selected on outcomes; it was never tested as a projection or selection lever. It has not been
re-verified since the July audits.

## 4. The players, week by week

The top overweights and underweights each week, with their pre-lock features, are in the private output
(`players/analysis.txt`); the patterns in §2 are drawn from those lists.

## 5. What would let us match or beat them: tests, not changes

These are recorded as study-list item 22. All are on history or in shadow, under the in-season adoption track.

1. **Projection calibration (class C), on history, the cheapest and first.** On 2022–25 out-of-sample predictions:
   does our projection's miss depend on the following? If it does, add the term as a calibration or feature.
   - last season's defence-vs-position;
   - early-season (one to three games) defence stats;
   - last week's points and the salary change;
   - the value rank.

   The endpoints must be written down before Thursday's six-season co-run, as part of the defence re-test arm
   already planned there, before its outcomes are seen.
2. **An FP blend (class C).** FP beat us in the one week we have. The DFS projections page was captured for Week 4 only. Make
   it a weekly capture first; that is not yet verified. After four captured weeks, test a fixed pre-declared blend weight on those weeks. Also check whether FP
   offers archived projections for a back-test.
3. **A Monday player-choice panel (part of scorecard item 20).** Every week, the points per lineup from player choice
   for us and for the regulars, by position, plus the anti-recency and value tilts. It is cheap, and it would have
   flagged the WR loss in Week 2.
4. **A sharp-tilt shadow (class S, later).** Fit the regulars' Weeks 1–4 tilts on pre-lock features, freeze the fit,
   and from Week 6 run a paired shadow book whose player exposures are nudged by it. The grade is the player-choice
   points per lineup. This only makes sense if test 1 does not already capture the same signal.
5. **WR concentration.** The −6.7 points per lineup at WR come from a few 54–57% exposures. That is the territory of
   studies 1b and 17 (exposure and selection redundancy); their reads come first.
