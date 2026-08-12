# Review: the marginal-arm pattern, G0's explanation, and one adoption risk

Date: 2026-08-12. Review of work through `a58cd61`. **No code was changed.**

---

## 1. G0 explains six failed arms at once

G0 (`g0-final-served-dependence-v2-7fsx6`) measured the terminal served
simulator against realized outcomes on 7,848 supported player-weeks:

| cell | realized | **simulated** | 95% interval on log(sim/real) |
|---|---:|---:|---|
| QB → WR conditional lift | 3.321 | **1.053** | [−1.346, −0.938] |
| QB → TE conditional lift | 2.359 | **1.048** | [−1.140, −0.414] |
| team ≥3 q90 exceeders / independence | 1.835 | **1.013** | [−0.840, −0.281] |
| team ≥2 q90 exceeders / independence | 1.148 | **1.003** | [−0.266, −0.001] |

**The simulated lifts are ~1.00–1.05. The terminal simulator is very nearly
teammate-independent.** Reality has a 3.3× QB→WR hub; the simulator has
essentially none. Every interval is wholly on one side of zero.

This is the missing explanation for a pattern that now has six instances:

| arm | distributional evidence | tail/lineup outcome |
|---|---|---|
| Route Share components | MAE and CRPS better in **every** fold | tail gate failed |
| Fast-role bundle | +2.19 DK pts vs matched controls, positive in all 6 seasons | 11/107 vs 17/107 |
| Fitted-K (v1 panel) | held-out allocation NLL better, CI wholly favourable | exact-80 rejected |
| SCHED sync | CRPS −0.00145, point MAE −0.00359 | 30-pt Brier flat, CI spans zero |
| Team-QB quality | point MAE 3.63282 → 3.61681 | Brier, CRPS, pinball all worse |
| `depth_rank_delta`, `team_ol_out` | plausible | −4.6, −8.7 mean best |

**Mechanism.** A lineup score is a sum of nine players. Under near-independence
the sum concentrates — its extreme upper tail is governed by aggregate variance,
not by any single player's marginal. Improving one player's mean or sharpening
his distribution moves the *centre* of the nine-player sum and barely touches
its 99.9th percentile. Under strong positive dependence the opposite holds: one
player's boom drags his stack-mates with him and the sum's tail fattens
sharply.

So the marginal queue did not fail because the features were worthless. **It
failed because the dependence structure downstream of the marginals is too weak
to propagate a marginal improvement into the joint tail.** Six independent
mechanisms produced the same signature, and G0 now supplies the reason.

This also retires a claim I made earlier — that "the marginal layer is
exhausted." It is more accurate to say the marginal layer was **tested under a
mis-specified dependence structure**.

## 2. Predeclare the post-G2 re-ask now, before G2's result

The project's own validation law already covers this:

> "post-ensemble AND post-selection law: verdicts don't transfer across a
> changed downstream stage."

G2 would change the dependence stage, which sits downstream of the marginals in
the pipeline. Under that law, marginal verdicts obtained against a near-
independent copula **do not transfer** to a properly-coupled one. This is not
reopening closed arms; it is the standing law operating as designed.

**Recommendation: freeze the re-ask list now, while G2's result is unknown.**
Deciding afterwards which arms to revisit would be exactly the post-hoc
selection the project forbids. A small, pre-committed set — I would nominate
**team-QB quality first**, because the QB is the measured hub and coupling is
precisely the thing that would let a better QB marginal reach his receivers,
followed by SCHED — with the same frozen gates as before, conditional on G2
passing and on nothing else.

If G2 fails, the list is discarded unused and costs nothing. If G2 passes and
the list was not frozen beforehand, any re-ask is contaminated.

## 3. One adoption carries more risk than its threshold count suggests

The fitted-usage exact-80 v2 was adopted on the tail-first law. The full grid:

| threshold | 240 | 230 | 220 | 210 | 200 | 194 | 187 | mean |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| control | 2 | 2 | 3 | 5 | 14 | 26 | 37 | 177.95 |
| fitted-K | **3** | **3** | 3 | **6** | **11** | **19** | 34 | 177.36 |

Evaluation-only 2023–2025: `0/0/1/1/6/11/13 → 1/1/1/2/3/4/10`, mean
`173.05 → 171.88`.

The law was applied correctly by its letter — the first non-zero difference from
240 down is positive. Three observations about what that letter is buying here.

**The decision rests on one or two Bernoulli events.** Control counts at 240 and
230 are 2 and 2 on the full panel, and **0 and 0** on the evaluation panel. On
the eval panel the entire adoption is one week crossing 240 and one crossing 230
— possibly the same week. Earlier in this same program I proposed a guardrail:
no promotion on a threshold whose control count is below ~5 unless the paired
weekly-maximum comparison is also favourable. That guardrail was not adopted,
and this is the case it was written for.

**The middle is degraded substantially and consistently.** −3 at 200, −7 at 194,
−3 at 187, and mean −0.59 on the full panel; −3 and −7 on the eval panel. These
are not noise-scale movements — the 194 loss is larger in absolute count than
every tail gain combined.

**The 240 week probably does not win anything.** The one recorded contest
data point is the 2025-10-05 Millionaire: first place **246.82**, min-cash
**169.34**. A week that reaches 240 does not win that contest; weeks at 194 are
comfortably above min-cash and pay. So the trade is roughly *seven likely cashes
for one week that gets closer to a prize it still does not reach.*

**Recommended, and cheap:** before this law promotes anything else, score both
books against a stylised top-heavy payout curve — DraftKings' published
Millionaire structure is public and needs no new data — and report expected
dollars alongside the threshold grid as a **mandatory diagnostic, not a veto**.
That does not change the operator's stated objective; it makes visible what each
tail-first adoption costs. Right now the grid cannot distinguish a trade that is
worth making from one that is not.

Also worth recording per-week detail for this arm: which specific week crossed
240, and whether that week's winning construction is a class the book would
reproduce or a single fortunate roster.

## 4. Corrections to my own earlier claims

- **My WR–WR prediction was wrong.** I predicted the simulator would over-couple
  same-position teammates relative to a realized ≈0.99. G0 found WR–WR
  inconclusive and the direction did not hold. My 0.99 came from
  `slate_player_features.proj_p90` — the *widened summary*, not the served
  draws — and G0's terminal measurement supersedes it. Two of three predictions
  held (QB–WR and ≥4 under-prediction); the third did not.
- **Realized QB→WR is larger than I measured**: 3.321 on the served path versus
  the 2.34 I reported from the summary quantiles. The correction moves in the
  direction of a stronger effect, which strengthens rather than weakens the G1/G2
  case.

## 5. G1 notes

The ambiguous-QB repair is handled correctly: excluding the 169 ambiguous
team-weeks from QB-source pairs, rather than choosing a primary by projection or
depth chart, preserves G0's exact rule and avoids a post-hoc selection that
would have been very hard to unwind later. Retaining their non-QB pairs is the
right scope.

Two things worth ensuring in the G1 output, given what G2 will be gated on:

1. **Report the QB-hub lift per held-out season, not only pooled.** The G2
   license depends on the hub being *stable*, and pooled cells can hide a
   single-season effect. The protocol requires two supported folds; make the
   per-fold values visible in the report rather than only the stability verdict.
2. **Expect thin archetype cells and let the broad relationship cells carry the
   verdict.** The effect G0 measured is large (log gap −1.149) and unambiguous
   at the relationship level. Subdividing by archetype pair will produce many
   inconclusive cells by construction; that should not be read as weakening the
   relationship-level finding.

---

## Summary

The most important thing to come out of this stretch is not a rejection — it is
that **G0 gave a single mechanical explanation for six independent failures**,
and that explanation says the marginal work was mis-timed rather than
misguided. The immediate actions are to freeze the post-G2 re-ask list before
G2's result exists, and to add expected-dollars as a mandatory diagnostic beside
the threshold grid so tail-first adoptions can be seen for what they cost.
