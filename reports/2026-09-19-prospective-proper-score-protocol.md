# Prospective proper-score protocol: which law is better calibrated on the Sunday-main slate

**Frozen 2026-09-19, before the Week-2 lock (2026-09-20 17:00Z) and before any Week-2 outcome exists.**
Requested by the laptop agent in `2026-09-19-laptop-prospective-scoring-task-and-runtime.md`. Workstation agent owns
the protocol and the reader; the laptop reviews the source and supplies the portable bundle.

## 1. What this measures, and what it is not

The control chain and the salary-repaired chain embody two different predictive laws. On the Week-2 book they
disagree: at `prefix97` the two equal mixtures differ by 0.733 points of expected maximum on the **identical** control
book. That disagreement is about DK points, a physically realized quantity, so realized Sunday-main scores can say which
law was closer — **on whatever book is entered, with no counterfactual book required.**

**This protocol scores predictive laws. It does not compare books, does not adjudicate the salary repair's selection
effect, and cannot nominate a live rule.** One slate is one draw. The output is a measurement to be accumulated
weekly; a single week's result is reported with its uncertainty and nothing is adopted from it. Explicitly, per the
laptop's instruction: *do not treat 428 players or 97 overlapping lineups as independent replications, and do not
nominate a live rule from one slate.*

## 2. Pre-registered quantities

Scored with **CRPS** (continuous ranked probability score, lower is better), the strictly proper score for a full
predictive distribution, computed as the score of the **issued empirical distribution** (denominator `n*n`).

**This is deliberately not the "fair" ensemble estimator `n*(n-1)`.** The banks *are* the forecast, not a finite
sample drawn from some underlying forecast, so the fair correction does not apply — and applying it to a
deterministic stratified concatenation breaks convexity outright. Exact counterexample (the laptop's, in review of
v1): components `[0,2]` and `[0,2]` with outcome `1` score 0 each under the fair estimator while their pooled
duplicate `[0,0,2,2]` scores 1/3, a mixture "gain" of −1/3 for two *identical* forecasts. Under the
issued-distribution estimator both score 0.5 and the gain is exactly 0. See Ferro (2013) on the distinction.

Each law's prediction for a player is its **audit** bank row — 10,000 draws, independent of the bank used for
selection, so selection-on-noise cannot flatter a law.

**Laws (six, all reported):**

| id | predictive sample |
|---|---|
| `control_I`, `control_H` | control arm, `I_audit` / `H_audit` |
| `salaryfix_I`, `salaryfix_H` | repaired arm, `I_audit` / `H_audit` |
| `control_mixture`, `salaryfix_mixture` | **pooled** 20,000 draws (10,000 from each component) |

**The mixture is scored on the pooled sample, not as the mean of its components' scores.** With the
issued-distribution estimator the pooled empirical CDF is exactly `½F₁+½F₂`, and CRPS is convex in the distribution,
so `CRPS(½F₁+½F₂) ≤ ½CRPS(F₁)+½CRPS(F₂)` with equality for identical components. Averaging component scores measures
"pick one law at random"; the pooled sample measures the mixture that `dual_emax`'s equal-mass concatenation actually
is. Both are emitted so the gap is visible. **Equal component widths are asserted**, since unequal widths would make
the pooled sample an unequal-weight mixture.

**Primary:** mean CRPS per law over the common-key player universe, and the paired per-player difference
`salaryfix_mixture − control_mixture`.

**Strata (pre-specified, all reported, none selected after the fact):**
- overall;
- by position — QB, RB, WR, TE, DST;
- the **prior-eligible group** (the target-prior work's eligible players), supplied as an explicit id list in the
  bundle. Absent list ⇒ the stratum is reported as unavailable, never silently skipped.

**Secondary, descriptive only, no interval:** per-lineup total CRPS and the predicted book-maximum distribution
against the realized maximum, for **each saved book under every law**, as in the existing cross-audits — not each
book only under its own arm's law. The lineups share players heavily and the maximum is a single number; both are
descriptive rows carrying no inferential claim. Books are labelled **prospective shadow books** unless the bundle
manifest declares an entered-book identity. Lineup totals are aggregated in float64, which does **not** reproduce the
build's preserved float32 summation order; the disclosure is emitted with the rows.

## 3. Uncertainty

Players within a game share weather, pace, game script and each other's usage. **Clusters are games**, keyed
`min(team,opp)-max(team,opp)` from the frame, giving ~13–14 clusters on a Sunday main slate.

Uncertainty on the paired mean difference is a **cluster bootstrap over games**, B = 10,000, resampling whole games
with replacement. Reported as the 2.5/97.5 percentiles alongside the point estimate and the cluster count.

**With ~13 clusters this interval is wide, and that is the honest answer, not a defect to be tuned away.** The reader
**refuses to emit an interval below 8 clusters** and says so. No per-player independence is assumed anywhere.

## 4. Decision rule

**None.** There is no gate, threshold or adoption trigger in this protocol. The deliverable is a committed row per
week. A law comparison becomes actionable only after a pre-registered number of slates, which is a separate protocol
that must be frozen before those slates are read.

## 5. Outcome gate and anti-peeking

The reader is fail-closed three ways and cannot run early:

1. it refuses unless `now > 2026-09-21 02:00:00Z`, **after the Sunday-main slate settles** — not merely after the
   17:00Z lock. Week-2 Thursday labels already exist, so a lock-time gate is not sufficient. **The clock is injected
   by tests and has no CLI override**; v1 exposed a `--now` flag that let any caller walk past the gate.
2. it requires a pinned **actuals manifest** (its sha256 passed on the command line) which must declare
   `season 2026`, `week 2`, `draft_group 153428`, `slate sunday_main`, `scoring dk_classic_v1`, a named source, and
   every listed game `FINAL` with `all_games_final: true`. The manifest in turn pins the data file's sha256.
   **A hash establishes which bytes, never which slate** — identity is the manifest's job.
3. the manifest's game set must be **unique and exactly equal to the bundle's frozen Sunday-main slate**, taken from
   the already-pinned `hsim_game_inputs` receipt. A manifest naming one unrelated finished game would otherwise
   satisfy every field above. Each actuals row must additionally carry its own `season`, `week` and `game_id`, and
   every row's game must lie inside that frozen set.
4. it writes its output **write-once** (`open(...,'x')`) and records its own source sha256, so a result cannot be
   silently regenerated under changed code.

Every bundle input is sha-verified against a manifest before use. Banks must be 2-D with a non-trivial draw width
matching across components; saved lineups must hold nine unique ids with no duplicate memberships, and a supplied
book **must** declare `expected_book_size`. Null ids and non-finite points are refused.

**Each actual row is bound to the player's own forecast fixture**: the row's `game_id` must equal the unique frozen
game whose two sides are that player's team and opponent, and a frame `game_id` column must agree with it. Checking
that the row's game is on the slate, and separately that the player's sides are on the slate, does not stop an
on-slate row being joined to the wrong fixture. The binding covers players present in only one arm, since those can
still be scored descriptively in that arm's book.

**Cross-arm metadata is validated on the complete shared player universe, before outcomes narrow it** — checking only
the scored players would let a frame disagreement hide behind a missing outcome. Every shared player's position, team
and opponent must agree across arms, and every player's `{team, opp}` pair must correspond to a game in the frozen
slate, so a player from outside the forecast cannot be scored. Players missing from either arm, or without a
finalized outcome, are reported by identity and **excluded from the common-key comparison — never zero-imputed**.

Implementation and its tests use **synthetic fixtures only**. No Week-2 actuals are queried or materialized while this
is being built, per the laptop's instruction.

## 6. Artifacts

| | |
|---|---|
| protocol | this file, frozen before lock |
| reader | `reports/reviews/evidence/2026-09-19-prospective-proper-score-reader.py` |
| tests | `tests/test_prospective_proper_score.py`, 52 tests, synthetic fixtures only |
| bundle | supplied by the laptop; saved paired frames, audit banks, book orders, prior-eligible ids, manifest |
| output | `2026-09-19-prospective-proper-score.json`, write-once |

## 7. Known limitations, stated before the result

- **One slate.** n is 13-ish games, not 428 players. The interval will be wide.
- **CRPS rewards whole-distribution calibration**, not tail accuracy specifically. A law can win on CRPS and still be
  wrong about the 220+ tail we actually care about. Tail-specific scoring is a separate question and is deliberately
  not smuggled in here.
- **The audit banks are conditional** on each arm's calibration and inputs; this compares the laws as they were
  frozen, not the best version of either.
- **Lineup aggregation is float64**, so descriptive book rows do not reproduce the build's float32 summation order.
- **Only the entered book's players are observed in situ**; the common-key universe is the frame, so most scored
  players were never entered. That is intended — it is what gives the comparison more than 97 points of contact — but
  it means the score is about the law's general calibration, not about the entered lineups specifically.
