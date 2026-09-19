# Prospective proper-score protocol: which law is better calibrated on a real slate

**Frozen 2026-09-19, before the Week-2 lock (2026-09-20 17:00Z) and before any Week-2 outcome exists.**
Requested by the laptop agent in `2026-09-19-laptop-prospective-scoring-task-and-runtime.md`. Workstation agent owns
the protocol and the reader; the laptop reviews the source and supplies the portable bundle.

## 1. What this measures, and what it is not

The control chain and the salary-repaired chain embody two different predictive laws. On the Week-2 book they
disagree: at `prefix97` the two equal mixtures differ by 0.733 points of expected maximum on the **identical** control
book. That disagreement is about DK points, a physically realized quantity, so realized Week-2 scores can say which
law was closer — **on whatever book is entered, with no counterfactual book required.**

**This protocol scores predictive laws. It does not compare books, does not adjudicate the salary repair's selection
effect, and cannot nominate a live rule.** One slate is one draw. The output is a measurement to be accumulated
weekly; a single week's result is reported with its uncertainty and nothing is adopted from it. Explicitly, per the
laptop's instruction: *do not treat 428 players or 97 overlapping lineups as independent replications, and do not
nominate a live rule from one slate.*

## 2. Pre-registered quantities

Scored with **CRPS** (continuous ranked probability score, lower is better), the strictly proper score for a full
predictive distribution. Each law's prediction for a player is its **audit** bank row — 10,000 draws, independent of
the bank used for selection, so selection-on-noise cannot flatter a law.

**Laws (six, all reported):**

| id | predictive sample |
|---|---|
| `control_I`, `control_H` | control arm, `I_audit` / `H_audit` |
| `salaryfix_I`, `salaryfix_H` | repaired arm, `I_audit` / `H_audit` |
| `control_mixture`, `salaryfix_mixture` | **pooled** 20,000 draws (10,000 from each component) |

**The mixture is scored on the pooled sample, not as the mean of its components' scores.** CRPS is convex in the
predictive distribution, so `CRPS(½F₁+½F₂) ≤ ½CRPS(F₁)+½CRPS(F₂)`; averaging component scores measures "pick one law
at random", while the pooled sample measures the mixture distribution that `dual_emax`'s equal-mass concatenation
actually is. These are different numbers and only the second answers the question. Both are emitted so the gap is
visible.

**Primary:** mean CRPS per law over the common-key player universe, and the paired per-player difference
`salaryfix_mixture − control_mixture`.

**Strata (pre-specified, all reported, none selected after the fact):**
- overall;
- by position — QB, RB, WR, TE, DST;
- the **prior-eligible group** (the target-prior work's eligible players), supplied as an explicit id list in the
  bundle. Absent list ⇒ the stratum is reported as unavailable, never silently skipped.

**Secondary, descriptive only, no interval:** per-lineup total CRPS over the entered lineups, and the predicted
book-maximum distribution against the realized maximum. The 97 lineups share players heavily and the maximum is a
single number; both are reported as descriptive rows and carry no inferential claim.

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

1. it refuses unless `now > 2026-09-20 17:00:00Z` (lock), so no pre-lock peek is possible;
2. it requires an actuals artifact whose **sha256 is passed on the command line and must match**, so the outcome set
   is pinned and cannot drift between runs;
3. it writes its output **write-once** (`open(...,'x')`) and records its own source sha256, so a result cannot be
   silently regenerated under changed code.

Every bundle input is sha-verified against a manifest before use. Players missing from either arm are reported by
identity in a support table and **excluded from the common-key comparison — never zero-imputed**.

Implementation and its tests use **synthetic fixtures only**. No Week-2 actuals are queried or materialized while this
is being built, per the laptop's instruction.

## 6. Artifacts

| | |
|---|---|
| protocol | this file, frozen before lock |
| reader | `reports/reviews/evidence/2026-09-19-prospective-proper-score-reader.py` |
| tests | `tests/test_prospective_proper_score.py`, synthetic fixtures only |
| bundle | supplied by the laptop; saved paired frames, audit banks, book orders, prior-eligible ids, manifest |
| output | `2026-09-19-prospective-proper-score.json`, write-once |

## 7. Known limitations, stated before the result

- **One slate.** n is 13-ish games, not 428 players. The interval will be wide.
- **CRPS rewards whole-distribution calibration**, not tail accuracy specifically. A law can win on CRPS and still be
  wrong about the 220+ tail we actually care about. Tail-specific scoring is a separate question and is deliberately
  not smuggled in here.
- **The audit banks are conditional** on each arm's calibration and inputs; this compares the laws as they were
  frozen, not the best version of either.
- **Only the entered book's players are observed in situ**; the common-key universe is the frame, so most scored
  players were never entered. That is intended — it is what gives the comparison more than 97 points of contact — but
  it means the score is about the law's general calibration, not about the entered lineups specifically.
