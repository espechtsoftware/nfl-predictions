# Review #6: mine these results for optimization (2026-08-05)

You are reviewing a DraftKings NFL DFS system at the close of a
six-week program. Five prior review rounds (Gemini x4, GPT-5.6/Sol
with code access) have been triaged; every actionable finding was
implemented and panel-tested within hours. This package is different:
it is a **data dump with fresh analysis**, and the ask is narrow —
**find optimization opportunities in these numbers.**

Constraints on your answers: free data only; solo operator; six-season
walk-forward replay panels with same-image co-run controls and a LOSO
rule (positive in >=4 of 6 seasons, <=1 negative) are the only accepted
evidence; BigQuery + Cloud Run (GPU available). Answer with numbered
findings: claim, mechanism, the concrete code-level test, and the
falsification condition. Do not propose anything in §6 (graveyard)
without attacking the specific burial.

---

## 1. The system in one paragraph

40 lineups/week into large-field NFL tournaments (Milly Maker ~150k
entries; qualifiers ~20k). Per-component LightGBM ensembles (3 seeded
members) + TabPFN quantile marginals + de-vigged prop-market blend →
possession-Markov correlated game simulator (~2,000 worlds/slate) →
MILP candidate generators (per-world argmax "boom", mean-objective
"lev", game-stack, dark-game, QB-variant) → greedy max-coverage
selection on P(best-of-40 >= 194). Hard rules: QB + 2 pass-catchers +
opponent bring-back; $49k salary floor; p90 ceiling valuation of
punt-priced players; chalk fade on our objective using naive
ownership.

**Shipping baseline: 27/107 weeks where best-of-40 >= 194** (the
MINIMUM winning Milly line in our data; the AVERAGE winning line is
~237). Mean best-of-40 = 179.5, sd 19.6, median contest percentile
14.2%.

## 2. Every week's best-of-40 score (the raw material)

| Season | Week-by-week best-of-40 | Mean | Max |
|---|---|---|---|
| 2019 | 171,169,195,192,**271**,200,186,210,163,180,171,183,165,176,177,212,167 | 187.5 | 271.1 |
| 2021 | 188,181,173,171,202,191,180,167,140,156,203,190,177,189,143,176,**218**,171 | 178.6 | 218.1 |
| 2022 | 177,199,168,200,172,150,190,188,160,155,157,188,157,**205**,181,172,175,153 | 175.0 | 205.3 |
| 2023 | 177,164,199,195,194,156,181,178,**200**,180,159,174,174,162,176,186,180,174 | 178.3 | 199.9 |
| 2024 | 152,151,184,165,201,163,173,165,164,173,**206**,179,195,189,197,197,199,178 | 179.6 | 206.5 |
| 2025 | 166,158,156,196,175,180,**222**,162,203,185,202,218,149,168,179,163,174,150 | 178.2 | 221.8 |

Distribution: q10 155.6 · q25 165.4 · **median 177.1** · q75 191.5 ·
q90 201.8 · q95 208.8. Weeks >=187 (qualifier line): 35/107. Weeks
>=194: 26-27/107. Weeks >=200: 14/107. Weeks >=237: 1/107.

## 3. NEW ANALYSIS — the candidate-oracle decomposition (the best lead we have)

We instrumented the generator to log, every week, the best ACTUAL
score achievable by ANY candidate in the pool (the "candidate
oracle"), versus what selection actually took. 107 weeks:

| segment | n | mean gap | mean oracle | oracle's sim-rank | pool size |
|---|---|---|---|---|---|
| oracle misses line, we miss | 77 | 6.4 | 175.6 | 65 | 167 |
| **oracle clears, we MISS** | **8** | **22.0** | **203.9** | **99** | **169** |
| oracle clears, we hit | 22 | 3.1 | 214.3 | **52** | 168 |

Key numbers:
- The pool clears the line in **30/107 weeks**; selection converts
  only **22**. Eight weeks are *recoverable without any new
  generator*.
- In those 8 recoverable weeks the winning candidate sat at **median
  sim-rank 92 of 168** — deep in the pool. In the 22 captured weeks
  it sat at median rank 30.
- **corr(oracle sim-rank, oracle-minus-selected gap) = +0.428.** The
  worse the simulator ranks the true best candidate, the more we
  lose. That is a quantified target for any reranker.
- The oracle was already inside our 40 in only **47.7%** of weeks.
- Mean capture of the candidate oracle = 96.3% overall, but **89.2%
  in the recoverable weeks**.

**The generator-attribution twist**: which batch produced the oracle
lineup, and its mean actual score:

| generator | weeks it produced the oracle | mean oracle score |
|---|---|---|
| boom (per-world argmax) | 55 | 181.6 |
| lev (mean-objective diversity) | 24 | 191.7 |
| dark (low-ranked game stacks) | 12 | 179.0 |
| qbvar (QB variants) | 10 | **198.5** |
| game (top game stacks) | 6 | 190.2 |

And in the **8 recoverable weeks specifically**, the oracle came from
`lev` (4), `qbvar` (3), `game` (1) — **never from the boom batch**,
which produces 55 of 107 oracles overall. The weeks we lose are weeks
where a NON-boom candidate wins and the simulator ranks it deep.

## 4. Other measured facts (all six-season unless noted)

- **Selection is instrument-blind, three ways**: log-sum-exp depth
  objective (25 vs 25, both pre-registered falsifications
  triggered), sharp-alpha conditional-peak "glass cannon" (26),
  QB-capped and 4-entry concentrated variants (worse). The weekly-MAX
  lineup was byte-identical across selectors in all six seasons.
- **Assembly overlap is below its random null for every
  construction**: incumbent best-entry overlap with the hindsight
  optimal 2.00 vs null 2.38; alternate architecture 1.56 vs 2.37;
  LSE 1.78 vs 2.30. Pool-hit (optimal players present anywhere) is
  77.8-81.2%.
- **Winner anatomy (74 real contests, full per-entry standings, up to
  470k entries)**: ONLY the winner stratum is contrarian
  (ownership-sum ~235 vs 245-254 for every other stratum including
  2nd-10th) and unique (~85% duplicated vs ~97%). Near-winners are
  chalk mirrors.
- **Field co-ownership**: real fields co-roster popular pairs at a
  median **0.87x** the independence estimate (p90 1.08; max chalk-pair
  inflation 1.7x for RB+own-DST) — cap substitution dominates, so
  independence is mildly CONSERVATIVE, not naive-optimistic. (2021
  showdown-format archive; classic re-measure pending.)
- **Our Gaussian difficulty diagnostics under-predict us**: summing
  per-week Gaussian-implied P(clear 194) predicts 17.9 clears; we
  produce 26-27. The portfolio's right tail is manufactured by the
  boom generator and is not normal.
- **Environment gating**: cleared weeks have entry-score mean 131 /
  sd 28.4; missed weeks 122 / 22.9. The slate booming matters more
  than the picks.
- **Simplification wins**: deleting the trained-ownership fade input,
  the mandatory punt slot, and the punt archetype boost took the
  baseline 25 -> 27 (the p90 punt VALUATION, salary floor, stack
  mandate all tested load-bearing and kept).

## 5. What we already built and gated (do not re-propose; extend if you see a flaw)

Built this week under `src/nfl_dfs/research/`: run-context + candidate
schemas + a config manifest (zero-drift invariant); a role-weighted
variogram dependence instrument; a **conditional GFlowNet** lineup
generator (legal-by-construction, trajectory balance) — **gated out**
because its own cheap-diversity baselines beat it at equal candidate
count (world-argmax +7.9 frontier gain, Gumbel-MILP +6.8, GFlowNet
+5.4); **SBI** parameter inference (2 of 3 simulator parameters
identifiable synthetically); **online conformal** calibration with
risk control; an **evidence-to-prior** pipeline (schema, extractor
contract, effect model) awaiting live news; **tracking traits** from
Big Data Bowl 2026 (1,384 players, 96.3% high-confidence gsis
crosswalk) awaiting a shadow-feature evaluation.

## 6. Graveyard (attack a burial or move on)

Selection: LSE (25), sharp-LSE (26), expected-dollars at 4 entries
(null), peak-slice (21), QB-cap (held). Generation: q99
ceiling-injection (23), boom-dose N=100 (25), **Gumbel-perturbed MILP
batch (26 vs 27 — the GFlowNet gate's own winner nulled on real
slates)**, manufactured collinear p98 game worlds (24), loosened
stacks (17,17), no-stack batch (0 survivors), vacancy-boost (21),
value-tier (26, noise). Simulator: **parametric TD event ledger,
correctly grouped and mean-preserving: 19 vs 27** — hand-specified
joint coupling reduced tails; learned game sim (failed rollout gate).
Models: heterogeneous ensemble member (21), TabPFN mean-swap (null),
ensemble size 5 (no gain over 3). Ops: legal late-swap (+0.9, null).
Architecture: from-scratch per-world-argmax + beat-the-field-bar
rebuild = exact parity (25 vs 25, then 27-equivalent).

Standing laws: post-ensemble and post-selection verdicts don't
transfer across a changed downstream stage; byte-identical arms mean
the lever never fired; **three arms this week were INVALID (env-name
typo, mislabeled deletion, season-pooled TD grouping) and were caught
by code audit, never by the panel number.**

## 7. Questions

1. **The 8 recoverable weeks.** The winning candidate exists in the
   pool but sits at median sim-rank 92/168, and it is never a boom
   candidate. What ranking signal — computable pre-lock, orthogonal
   to the simulator that already failed to rank it — would surface
   it? Be concrete about features and the training target, given we
   now persist every candidate with actuals.
2. **The generator-attribution asymmetry**: `qbvar` produces the
   highest-scoring oracles (mean 198.5) from only 10 weeks, while
   `boom` produces 55 oracles at mean 181.6. Does that argue for
   re-weighting the candidate mix, and how would you test it without
   simply re-running the dose arms that already nulled?
3. **Distribution shape**: our weekly bests are median 177, q90 202,
   with exactly one 237+ week in 107. Winning the average Milly
   requires ~237. Is chasing 237 rational at 40 entries, or is the
   correct objective explicitly the ~194 qualifier-and-min-line
   band? What does the data say about which target maximizes
   expected dollars?
4. **Simplification kept winning** (three deletions, +2 net). What
   else in §1's construction would you now suspect, and what is the
   cheapest decisive test?
5. **Anything in these numbers we have not noticed.** The per-week
   scores, the segment table, the tag attribution, and the
   sim-rank/gap correlation are all fresh. Mine them.
