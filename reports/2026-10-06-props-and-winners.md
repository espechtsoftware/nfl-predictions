# Prop bets, our projection and the winners (2026 Weeks 1–4): a descriptive read

2026-10-06, the laptop; reviewed by the reviewer before the operator. **Descriptive, four weeks: patterns, not
verdicts.** Aggregates only; player rows, usernames and Fantasy Points' licensed values stay private
(`~/private/props-analysis/`).

**The operator's question (10-06, verbatim):** "I would also like to do some analysis of how the winners picks align with
our usage of data points such as prop bets. Does it appear they are using that data? Is it helping or hurting us? Do we
need to change the blend of how much we rely on props? Or is it giving us an edge they don't have, which would be nice?"

## Data
- **Pre-lock inputs:** each week's T-70 frame carries our model's points (`model_points_pre`), the prop-market points
  (`market_points`) and the served projection (`mean_projection`). Fantasy Points' projections exist for Week 4 only
  (the newest capture before the T-70 build).
- **Outcomes:** the Millionaire's DraftKings points per player; players who did not play on game day are excluded (O-32).
- **Fallback rows removed:** a "market" value equal to DraftKings' points-per-game is the old fallback, not props
  (README deficiency log, 2026-09-17). That was 3 rows (Week 1: 2, Week 2: 1); every other row is real props.
- **Population:** the skill players with a real prop line and an outcome: 165 / 184 / 190 / 183 a week. That is the
  prop-covered half of the skill rows (47–49%), the higher-usage players.
- **Groups for the winners' question:** the 117 regulars (at least 100 Millionaire entries in every one of the four
  weeks: defined by volume, not by results), and each week's top 1% of Millionaire lineups by points (defined by
  results: labelled as such). The field is all Millionaire entries.

## 1. Are props helping or hurting our projection?

| players with props | our model | props | what we served | 45/55 blend of the two |
|---|---|---|---|---|
| average miss (points) | 5.88 | **5.31** | 5.50 | 5.46 |
| average bias (points) | −1.71 | −0.97 | −0.30 | −1.30 |

- **Props are the better half of the blend.** They beat our model at every position and in every week. What we served
  missed by 0.38 points less than the model alone, but by 0.19 points more than props alone (both outside the
  game-resampling range).
- **The best weight for our model is zero.** Fitted on the four weeks, the blend that misses least puts 0% on the
  model (90% range 0–10%). Leaving each week out in turn and fitting on the other three also gives 0% every time.
- **On these players our model adds nothing to the props.** Our model also projects too low (bias −1.7 points).
- **From Week 5, Fantasy Points' numbers pick the lineups**, so the live question is FP against FP + props. Week 4,
  on the prop-covered players only: FP missed by 5.85, props by 5.71, and a 50/50 FP + props blend by 5.76. The blend
  beat FP by 0.09 points, in 98% of the game resamples. **That is one week.**
- This is a different population from the frozen weekly check (FP 5.54 vs ours 5.58 in Week 4). That check covers
  every skill player either source projects at 3 or more; this one covers only players with prop lines. The two are not
  contradictory.

## 2. Do the winners use prop-like information? (exploratory)
How much more (or less) a group used a player than the field did, per one standard deviation of a "props signal",
holding salary and ownership fixed (percentage points of lineups; game-clustered 95% intervals):

| props signal | the regulars (all positions) | the week's top 1% (outcome-selected) |
|---|---|---|
| props above what the salary implies | **+1.28** (+0.99 to +1.57) | +0.35 (−0.88 to +1.58) |
| props above our model | **+1.22** (+0.79 to +1.64) | +0.98 (−0.03 to +1.99) |
| props above what the ownership implies | **+1.59** (+1.29 to +1.89) | +0.85 (−0.28 to +1.97) |
| props above FP (Week 4 only) | −0.08 (−0.43 to +0.26) | −0.50 (−1.76 to +0.76) |

- **The regulars lean toward players the props like** more than salary, ownership or our model would suggest, at every
  position (the per-position results are in the private report).
- **But not beyond what Fantasy Points already says.** In Week 4, once FP's projection is known, the regulars' picks
  show no extra lean toward props. They look like they read FP-style projections, which already contain the props.
- The top 1% is noisier: mostly no clear lean (running backs are the exception).

## 3. An edge the field doesn't have? (exploratory)
- **Against our model, yes.** When props disagree with our model, the actual points move with the props almost
  point for point (slope +1.11, 95% range +0.87 to +1.36; positive at every position, Weeks 1–4). Props carry
  information our model lacks.
- **Against Fantasy Points, no sign yet.** Week 4's slope is +0.24, with a range from −0.86 to +1.35. **One week
  can't tell.** The regulars' picks track props only as far as FP already does.
- Players the props liked well above our model *and* the field under-owned: only 12 player-weeks. They scored 8.7
  points more than our model expected, relative to everyone else, but 12 is too few to lean on.
- **52 tests** were fitted in parts 2–3, all reported. About 3 would cross zero by chance; the regulars' lean on props
  is well beyond that.

## What it means
1. **Change the blend?** Our own blend should lean much harder on props: on players with lines, props alone beat our
   45/55 mix every week. From Week 5, though, the lineups are picked from Fantasy Points' numbers, so the question that
   matters is FP vs FP + props.
2. **FP + props:** Week 4 suggests a 50/50 blend on prop-covered players beats FP alone, by 0.09 points. That is one
   week. A weekly paired check is preregistered from Week 5 (`reports/2026-10-06-prereg-fp-props-weekly-check.md`).
3. **An edge?** Props correct our model; there is no sign yet that they add anything beyond what Fantasy Points (and
   the field reading it) already has.
