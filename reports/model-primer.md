# How This System Actually Works: A Plain-English Primer on the Models and Training

*Written 2026-08-01 for Erich. No prior machine-learning knowledge assumed.
Every concept is illustrated with the real component in this repo and, where
possible, the real measured numbers from our own experiments.*

---

## The Overview: One Paragraph, Then One Page

In one paragraph: **this system reads years of NFL history, learns patterns
that connect a player's situation to how many fantasy points he scores,
imagines each upcoming week thousands of times, and then picks lineups that
win specifically in the imagined worlds where scores go crazy — because
crazy weeks are what win tournaments.**

The one-page version. The system is a pipeline with six stages, and each
stage is a chapter below:

1. **Data** (`ingest/`): raw facts land in BigQuery — every play since 2014,
   every salary, injury report, depth chart, Vegas line, and (as of this
   week) every contest's real ownership.
2. **Features** (`sql/features/`): raw facts are compressed into one row per
   player per week — "his last 4 weeks of targets," "his team's vacated
   carries," "the referee's flag tendency" — with a sacred rule: a row for
   week 10 may only contain things knowable *before* week 10 kicked off.
3. **Models** (`models/components.py`): a machine-learning method called
   gradient-boosted trees learns, from ~52,000 historical player-weeks, how
   those features relate to what actually happened.
4. **Simulation** (`models/simulate.py` + `game_sim.py`): predictions are
   turned into 10,000 imagined versions of the week, with players in the
   same game rising and falling together, the way real football works.
5. **Optimization** (`optimizer/`): an exact mathematical solver builds
   lineups under DraftKings' rules, then a selection step picks the 40
   entries that cover the most winning worlds.
6. **Validation** (`backtest/`): the whole thing is re-run against past
   seasons it never saw, so every claim in this document has a number
   attached instead of a vibe.

Now the lessons.

---

## Chapter 1: What "a Model" Is

Strip away the mystique: a model is a **function** — something that takes
inputs and produces an output. A thermostat is a model: input temperature,
output on/off. The difference with *machine-learned* models is that nobody
writes the rules by hand. Instead, you show the computer thousands of
historical examples where you know both the inputs *and* the answer, and an
algorithm finds rules that connect them.

Our central example: for a given player in a given week, the inputs are
about 40 numbers describing his situation (recent usage, his team's
situation, the opponent, the weather, his salary). The output we want is
what he'll do on Sunday. We have ~52,000 historical examples where we know
both sides — that's the training table, `player_week_training`.

Two vocabulary words you'll see everywhere:

- **Features** — the input numbers. "Targets over his last 4 games" is a
  feature.
- **Labels** (or **targets**, confusingly) — the answer we're trying to
  predict. "Receptions he actually got that week" is a label.

Training is the process of finding rules that map features to labels well.
Prediction is applying those rules to a new row where the label hasn't
happened yet.

**The single most important idea in this whole document**: a model is only
as honest as its training examples. Everything else in this primer —
point-in-time discipline, walk-forward validation, leakage checks — exists
to keep the examples honest.

---

## Chapter 2: The Training Data, and the Golden Rule

Open `player_week_training` and each row reads like a scouting card frozen
in time: *Player X, 2023 week 10 — averaged 7.2 targets over his last 4
games, his team lost its WR2 to injury this week, opponent allows the 4th
most yards to slot receivers, wind forecast 6 mph, salary $5,400.* And then
the labels: what he actually did in that week's game.

### The Golden Rule: no peeking

A week-10 row may only contain information that existed **before week 10's
games kicked off**. His "last 4 weeks of targets" means weeks 6–9, never
week 10 itself. This sounds obvious and is shockingly easy to violate by
accident — one SQL window written as "including the current row" instead of
"up to the previous row" and your model gets to peek at the answer.

Why is peeking so poisonous? Because the model will happily learn from the
leak, look *amazing* in testing, and then collapse in real life where the
future isn't available. It's the difference between a student who studied
and one who saw the answer key: identical exam scores, very different
futures.

Our defenses, in the code:

- Every rolling window in the feature SQL ends at `1 PRECEDING` — SQL for
  "up to but not including this week."
- `features/leakage.py` runs automated checks on every feature build that
  recompute windows independently and compare. The project rule (in
  CLAUDE.md) says these may never be weakened to make a build pass.
- Some features are *legitimately* same-week: the injury report, the depth
  chart, the referee assignment, salaries. Those are published before
  kickoff, so knowing them isn't peeking — the test is always "was this
  knowable Saturday night?", not "is this from the same week?"

### Walk-forward: the Golden Rule applied to testing

When we *evaluate* a model, the same rule applies at a bigger scale: to
test on 2023, train only on 2014–2022. Never shuffle all years together
and split randomly — random splits let the model train on December 2023
and be tested on October 2023, which smuggles the future in through the
back door (it learns that season's scoring environment, injuries, etc.).
Every replay in this repo trains on strictly-earlier seasons. This is
called **walk-forward validation** and it's non-negotiable here.

### What the audit taught us about data

This week's audit found the training table had 9 duplicate rows (players
traded mid-week appeared twice) and that three seasons of salaries were
missing entirely. Small data flaws are normal; the lesson is that you find
them by *auditing systematically*, and the deterministic testing setup
(Chapter 10) turned out to be the tool that proved one "harmless" flaw was
actually costing measurable performance.

---

## Chapter 3: Gradient-Boosted Trees, in Plain English

Our models use **LightGBM**, an implementation of *gradient-boosted
decision trees*. Let's build that up from nothing.

### A decision tree

A decision tree is a flowchart of yes/no questions:

```
Was his target share last month over 20%?
├── yes → Was the opponent bottom-10 defending WRs?
│         ├── yes → predict 8.1 targets
│         └── no  → predict 6.9 targets
└── no  → Was a teammate ruled Out this week?
          ├── yes → predict 4.4 targets
          └── no  → predict 2.7 targets
```

Training a tree means letting an algorithm choose which questions to ask,
and where to split, so that the examples landing in each leaf are as
similar as possible. One tree is crude — it can only express a handful of
rules.

### Boosting: a committee of specialists in each other's mistakes

Gradient boosting builds trees **in sequence, each one trained on the
errors of the committee so far**. Tree #1 makes rough predictions. Tree #2
is trained to predict *where tree #1 was wrong*, and its output nudges the
predictions toward the truth. Tree #3 corrects the remaining errors. Repeat
a few hundred times, with each tree's correction scaled down by a
**learning rate** (small steps, so no single tree overcommits).

That's the whole trick. Our training call uses `num_boost_round=400` — a
committee of 400 small trees, each contributing a modest correction.

### Why trees, and not a neural network?

For data that lives in a table — rows of players, columns of numbers —
boosted trees are the reigning champion, and it isn't close. Three reasons
that matter for us:

1. **They find thresholds and interactions on their own.** Nobody told the
   model "wind matters only above 15 mph" — a tree can discover that split
   itself. (This is why, when a strategy article said "you need a
   nonlinear wind term," the answer was: trees already do that.)
2. **They handle missing values natively.** Our blitz-rate feature only
   exists from 2022; earlier rows are simply blank, and LightGBM routes
   blanks down whichever branch worked best in training. No fake filler
   values needed.
3. **They're fast and reproducible** — which is what makes our exact-A/B
   testing culture possible.

### What can go wrong: the overfitting idea

A model with enough capacity can *memorize* its training examples instead
of learning general patterns — like a student who memorizes past exams and
fails on new questions. The fix is never to trust training-set performance;
only held-out, walk-forward performance counts. You'll see this theme
reach its dramatic conclusion in Chapter 10.

---

## Chapter 4: Why We Predict Components, Not Fantasy Points

A naive design predicts fantasy points directly. Ours predicts the
**ingredients** — separate models for targets, catch rate, yards per
reception, receiving TDs, carries, yards per carry, rushing TDs, pass
attempts, and so on (`models/components.py`) — and computes fantasy points
from the ingredients.

Why go to the trouble?

1. **Each ingredient is more learnable.** Targets are driven by role and
   game script; yards-per-reception by player style and depth of target;
   touchdowns by red-zone usage. One mashed-together number blurs signals
   that are cleaner separately.
2. **The simulator needs ingredients.** To imagine a week realistically
   (Chapter 5) we need to roll dice for "how many targets" separately from
   "how long was each catch" — you can't roll dice on a pre-mixed
   fantasy-point number and get realistic variance.
3. **DraftKings scoring is just arithmetic on ingredients** (a catch is 1
   point, a yard is 0.1, a TD is 6...), so the conversion is exact
   (`models/scoring.py`).

---

## Chapter 5: From One Number to Ten Thousand Worlds

Here's the problem with a single prediction: "Player X will score 14.2" is
almost useless for tournaments. Two players can both average 14.2 where
one scores 12–16 every week and the other alternates between 4 and 30.
For cash games you want the first; for the Milly Maker you want the
second — tournaments are won by the *tail* of the distribution, not the
average.

So `simulate.py` plays each week 10,000 times ("sims" or "draws"):

- **Counting stats get counting dice.** How many targets in a sim is drawn
  from a Poisson distribution — the natural distribution for "how many
  events happen in a window" (the same math that models phone calls per
  hour). It's built from the model's predicted average but produces a
  different integer every sim.
- **Whether each target is caught** is a Binomial draw — a weighted coin
  flip per target using the predicted catch rate.
- **Yardage per catch** is drawn from a Gamma distribution — right-skewed,
  meaning mostly modest values with occasional long ones, which is exactly
  how receptions look in real life (lots of 8-yarders, the occasional 65).

Run all players through all 10,000 worlds and you get, per player, a full
distribution: their floor (p10 = the value they beat 90% of the time),
median (p50), ceiling (p90), and — crucially — a *joint* record of who
boomed together in which worlds.

**Is the imagination honest?** We measure it. Across replays, actual
scores land above our p90 about 9% of the time — a 90th percentile should
be exceeded 10% of the time, so the ceiling estimates are essentially
truthful. (The floor is currently too pessimistic — actuals beat p10 more
often than they should — but nothing in tournament play consumes floors,
so it's a cosmetic debt, on record.)

---

## Chapter 6: Correlation — the Soul of the Simulator

If every player's dice were rolled independently, the simulator would
believe a 5-player stack from one game boom-boom-boom-boom-booming
together is astronomically unlikely. But Milly winners routinely take
50–80% of their points from one game. Real players are correlated:
a shootout lifts everyone in the building.

### Version 1: the shared dial

The original mechanism: each game, each sim, draw one multiplier (say
0.85 or 1.20) and scale every player in that game by it. Games run hot or
cold as a unit. Crude but effective — and *mean-preserving*, an idea worth
pausing on: the multiplier averages exactly 1.0, so nobody's average
projection changes; only the *spread* of outcomes widens and narrows
together. We use this trick everywhere: change the shape of the
distribution, never the center, so improvements to correlation can't
silently corrupt projections.

### Version 2: the possession engine (this week's flagship)

`game_sim.py` replaces the arbitrary dial with a miniature football game:
each team gets ~10 drives, each drive starts in a field-position zone and
ends in a touchdown, field goal, punt, or turnover with probabilities
**fitted from 48,528 real drives (2018–2025)** — for example, drives
starting in the opponent's red zone score a TD 57.6% of the time. Summing
simulated drive outcomes yields each team's score, and each team's
multiplier is its own score relative to its own average.

Why this matters beyond elegance: we *measured* reality on the way. Real
cross-team scoring correlation is 0.016 — essentially zero — and real
opposing-QB fantasy correlation is 0.19. The old shared dial forced
correlation = 1.0 between teams; the possession engine's team-level
factors land near the measured truth. When A/B-tested over the 2025
season, the fitted engine matched-or-beat the old dial (and won the most
tail weeks of any configuration), so it was adopted into production.

### A hard-won lesson about correlations and folklore

Strategy articles trade in correlation numbers ("QB and opposing QB
correlate at .58!"). When we measured 4,432 real QB pairings, it was 0.19.
Most published stack correlations failed replication in our data — but
here's the subtle part: **weak average correlation doesn't mean weak tail
correlation.** The bring-back rule (always roster someone from the
opponent) shows a measly 0.10 linear correlation, yet when we *removed*
the rule and re-ran the season, winning weeks fell from 8 to 4. Averages
and tails are different animals, and tournaments live in the tails. This
is why we simulate whole worlds instead of trusting pairwise numbers.

---

## Chapter 7: Cold Starts, Priors, and the Market

Three supporting systems handle what the main model can't see.

**Cold start** (`models/coldstart.py`): a rookie or a backup thrust into a
starting job has no usable history — his "last 4 weeks" are blanks. The
system fills those from **role-based priors**: what does a typical player
*in this role* (depth-chart rank, position) do? A prior is just a
starting belief you fall back on when specific evidence is missing.

**Next-man-up** (`team_vacated_*` features + the graph): when a starter is
ruled Out, his targets don't vanish — they're inherited. The features
quantify vacated opportunity, and a small in-memory graph of who-competes-
with-whom routes it. Our punt-boom study (Addendum 24) found this catches
about a third of winning cheap-player booms; most of the rest were simply
cheap *starters* — knowledge that reshaped how we think about punts.

**The market blend** (`prop_lines`, `models/prop_market.py`): sportsbook
player props are predictions backed by money, and they're sharp. We
convert prop lines into implied fantasy points (after removing the
bookmaker's built-in margin, called *de-vigging*) and blend them with our
model. The blend weights were tuned by replay: roughly half model, half
market performs best. When our model and the market disagree hard, that's
either our edge or our bug — the new `/market` page in the app lists the
week's biggest disagreements for exactly that reason.

---

## Chapter 8: The Optimizer — Turning Beliefs into Lineups

Given 400 players with projections and salaries, how many legal DraftKings
lineups exist? Roughly 10²¹. You cannot check them all. Enter **MILP**
(mixed-integer linear programming, `optimizer/lineup.py`): a solver that
treats each player as a yes/no variable and finds the *provably best*
lineup under the constraints — salary cap ≤ $50,000, exactly one QB, the
roster shape, and our tournament rules. Not "a pretty good lineup" —
mathematically, the best one for the stated objective.

The rules it enforces aren't vibes anymore. This week we causally audited
every construction rule by deleting each one and re-running the season:

| Rule | What happens if you remove it |
|---|---|
| Must roster an opponent of your QB ("bring-back") | Winning weeks halve, 8 → 4 |
| Must include a sub-$4k punt | −4.4 points, −3 winning weeks |
| Never RB against opposing DST | −4.2 points, −3 winning weeks |
| Fade high-ownership players (chalk penalty) | −2.0 points, −2 winning weeks |

Every rule earns its slot. That table is the difference between a system
built on folklore and one built on evidence — the rules *came from*
folklore, but they *stay* because of measurements.

---

## Chapter 9: Picking 40 Entries — Expected Points Is the Wrong Goal

Here's a tournament truth that feels wrong until it clicks: **the lineup
with the highest average score is usually a bad tournament entry, and 40
copies of the best lineup is a terrible portfolio.**

Why: a Milly Maker pays meaningfully only near the very top. What matters
is the probability that *at least one* of your 40 entries clears the
winning line (~194 points historically). Forty similar entries boom in
the same worlds and bust in the same worlds — they're redundant. The
right portfolio *covers* different boom-worlds.

The machinery (`select_tail_entries` + the generators):

1. Generate hundreds of candidate lineups from different philosophies —
   the leverage objective, "dark game" stacks from overlooked games (a
   generator that our data validated twice over: 10 of 17 winning-week
   stacks came from games ranked 11th or lower by Vegas), and **boom
   solves**: take the 40 highest-scoring simulated worlds and ask the
   optimizer "if the week goes exactly like *this*, what's the perfect
   lineup?" — which bakes correlation in automatically.
2. Score every candidate across all 10,000 worlds.
3. Greedily pick entries to maximize the number of worlds where at least
   one entry clears the line. Each pick is chosen for the worlds *not yet
   covered* — the mathematical formalization of "don't buy 40 tickets to
   the same outcome." (This greedy approach carries a proof that it gets
   within ~63% of the theoretical optimum; in practice it's far closer.)

---

## Chapter 10: How We Know Any of This Works

This is the chapter that separates the system from a betting blog.

### Replays

`nfl-dfs replay --season 2023` re-lives a season honestly: train on
2014–2022 only, project each week, build 40 entries with real salaries,
score them with real results, simulate a real-sized field of opponents,
and report — average best entry, weeks over the winning line, percentile
finishes. Six seasons are replayable (2019, 2021–2025) since this week's
salary backfill.

Always alongside: the **naive baseline** — just predict every player's
trailing average. Our model beats it by 5–11% depending on season. Any
model too fancy to beat "last month's average" is decoration; always
demand the boring comparison.

### The accidental superpower: determinism

We assumed replay results wobbled run-to-run, so differences under ~5
points were shrugged off as noise. Then, on a whim, we ran the same
replay three times: **identical to the decimal.** The pipeline is fully
deterministic — same inputs, same output, always.

That changed everything. Every A/B comparison became *exact*: change one
thing, re-run, and the difference is entirely caused by your change. No
statistics, no repeats, no hedging. It also retroactively overturned a
verdict: a feature judged "neutral, within noise" was actually costing
4.6 points — there was no noise for it to be within. It was removed the
same hour.

### The feature law (a cautionary tale in five acts)

Armed with exact measurement, we tested five plausible new model features
in two days: depth-chart promotions, offensive-line injuries, referee
pace, opponent blitz rate, target concentration. **All five hurt**, with
the same signature: slightly better *typical* weeks, meaningfully worse
*best* weeks. The interpretation: features that make a model more
accurate on average tame exactly the extreme projections that tail-driven
lineup construction feeds on. Meanwhile the construction *rules* (Chapter
8) all validated. The law we wrote down: in this system, **the edge lives
in construction, not in feature accumulation** — and every proposed
feature is guilty until its own replay proves otherwise.

### The final trap: overfitting the test itself

Late in the week, richer training data moved our headline 2025 number
*down* from 189.5 to 185.1. Painful, but diagnosable: we had spent a week
adopting whatever measured best *on the 2025 replay* — so some of that
189.5 was 2025-specific luck, not durable skill. Selecting on a
measurement contaminates the measurement. The cure is the multi-season
panel (all six seasons, one config, judged together) that is being built
as this document is written. Remember this the first time an in-season
tweak looks great for one week.

---

## Chapter 11: The Ownership Model — Predicting Humans Instead of Football

Everything so far predicts *football*. The newest model predicts *the
crowd*: what percentage of tournament entries will roster each player?

Why it matters: tournaments are zero-sum against other people. A player
projected for 20 at 40% ownership is a worse tournament play than one
projected for 18 at 5% — if the popular one hits, you split the prize
pool with everyone; if the unpopular one hits, the prize is yours.

Thanks to this week's data windfall (103,556 real ownership records from
1,258 actual DraftKings contests, 2022–2025), this model trains on truth:

- **Features**: salary, recent production (deliberately the *public's*
  expectation — trailing points — because that's what drives chalk, not
  our model's opinion), value rank at the position, min-price flags.
- **Label**: the real percentage drafted.
- **The test that matters**: trained on 2022–24 and evaluated on 2025
  contests it never saw, it correlates 0.727 with real ownership, versus
  0.548 for the naive salary-based guess. That out-of-sample gap is the
  entire justification for its existence.

Its first production use is subtle and important: it powers the *simulated
field* — the imaginary opponents in replays now roster players the way
real crowds actually do. When we switched it on, our lineups' scores
didn't change but their percentile finishes got ~7 points worse. That's
not failure; that's the yardstick getting honest. A better opponent model
makes every future measurement mean more.

---

## Chapter 12: The Weekly Lifecycle (Ops in Sixty Seconds)

In-season, Tuesdays: nflverse data refreshes → features rebuild (leakage
checks must pass) → models retrain on all completed weeks (never the
in-progress season's own games for evaluation) → projections regenerate.
Salaries, odds, props, and weather refresh on their own schedules. A daily
freshness check emails if any feed silently stops (a lesson bought with
three real silent failures), and the app's System Status button shows
every feed's pulse. Every experiment lives behind an environment switch
(`GAME_SIM_MODE`, `OWN_MODEL`, `EXTRA_FEATURES`...), defaulting to the
validated configuration — so trying an idea never risks the shipping
system, and any idea is one 35-minute exact replay from a verdict.

---

## Glossary

- **Feature**: an input number the model learns from.
- **Label / target**: the answer being predicted during training.
- **Training**: fitting rules that map features to labels using history.
- **Leakage**: future information contaminating training rows. Fatal.
- **Walk-forward**: testing only on periods after the training period.
- **Gradient boosting**: many small decision trees, each correcting the
  previous ones' errors.
- **Prior**: a fallback belief used when specific evidence is missing.
- **Monte Carlo simulation**: playing out a scenario thousands of times
  with dice to see the distribution of outcomes.
- **Poisson / Binomial / Gamma**: dice shaped for counts, coin flips, and
  right-skewed sizes, respectively.
- **Mean-preserving**: changing a distribution's spread without moving
  its average.
- **Correlation**: the tendency of two quantities to move together.
- **MILP**: a solver that finds the provably best combination under
  constraints.
- **Chalk**: heavily-owned players. **Leverage**: benefiting when chalk
  fails. **Bring-back**: rostering an opponent of your stacked QB.
- **MAE**: mean absolute error — average size of prediction misses.
- **Coverage / calibration**: whether stated probabilities match observed
  frequencies (our p90 says 90%, reality says ~91% — calibrated).
- **Overfitting**: learning the quirks of your examples (or your test!)
  instead of durable patterns.
- **A/B test**: change one thing, measure both versions, compare.
- **Determinism**: same inputs always produce the same outputs — which
  makes every A/B here exact rather than statistical.

---

*The best way to use this document: pick any chapter, open the file it
names, and read the code's own comments — they were written to be read.
The study report (`2026-07-25-system-study.md`, 29 addenda) is the lab
notebook where every number above was born.*
