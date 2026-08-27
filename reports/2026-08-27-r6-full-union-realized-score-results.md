# R6 full-union realized score results

**Run:** `20260826-foundry-v12-r6-full-union-realized-v2`

**Panel:** 54 historical slates

**Freeze:** 2,592 immutable rank-80 books; 7,776 immutable 4/14/80 prefixes

**Report schema:** `corpus-r6-full-union-score-report/v1`

## Result

The full-union score release is valid and complete for its frozen scope. The
strict finisher exact-replayed the grade, deleted historical-outcome lease
generation `1787782649649091`, and produced a generation-bound release intent
and receipt. The post-finish status check reports `lease_released=true`.

The bounded reporter then exact-opened only the generation-pinned grade
completion, persisted root, and 54 grade shards. It emitted all eight frozen
strategies, six fit scopes, and three entry counts: 144 complete aggregate
cells and 1,008 threshold observations. It did not open the outcome source,
BigQuery, or the historical-outcome lease, and it emitted no lineup IDs,
rosters, or row-level realized scores.

Canonical score report:

- path: `reports/r6-full-union-realized-runs/20260826-foundry-v12-r6-full-union-realized-v2/score-report.json`
- bytes: `350520`
- exact file SHA-256:
  `b0ccc59416b61c46b586a4b477639d95664870db1d2c466c390b88c1af62395d`
- internal report SHA-256:
  `bebe8688f73bcd5a497c2617aaee642e33c378830586c89d36444bc29cac3638`

## Intended final-fit books at 80 entries

The all-block final fit is the intended final book: its selectors were fitted
against all five simulated-world blocks before the outcome source was opened.
Counts below are across 54 historical slates. `Lineups >=200` measures depth
across all 4,320 selected lineup occurrences; the threshold-week columns
measure whether a strategy found at least one qualifying lineup that week.

| Strategy | Mean weekly max | Median weekly max | Weeks >=200 | >=210 | >=220 | >=230 | >=240 | Lineups >=200 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `coverage-194-v1` | 176.882 | 171.520 | 6 | 4 | 3 | 1 | 1 | 9 |
| `strict-200-coverage-v1` | 176.359 | 170.170 | 6 | 5 | 3 | 2 | 2 | 10 |
| `tail-ladder-200-210-220-v1` | **178.435** | 177.820 | 6 | **5** | **4** | **2** | **2** | **13** |
| `mean-score-v1` | 176.003 | 172.080 | 6 | 3 | 2 | 1 | 1 | **22** |
| `expected-max-v1` | 176.537 | 171.520 | 6 | 5 | 3 | 2 | 2 | 13 |
| `block-supported-tail-ladder-v1` | **178.435** | 177.820 | 6 | **5** | **4** | **2** | **2** | **13** |
| `regime-robust-ladder-v1` | 177.103 | 175.630 | **7** | 4 | **4** | **2** | **2** | 12 |
| `strict-230-coverage-v1` | 177.462 | **178.300** | **7** | **5** | **4** | 1 | 1 | **13** |

The leading final-fit mean weekly maximum is 178.435, shared by the ordinary
and block-supported tail ladders. That is +1.553 points relative to the frozen
coverage-194 strategy on this exact panel. It is also numerically above the
rough 176 benchmark cited during development, but that historical benchmark
used a different panel and must not be presented as a paired improvement.

## Entry-count behavior

No strategy is uniformly best at every portfolio size or under every tail
utility.

| Entries | Highest mean weekly maximum | Mean | Most useful tail observation |
|---:|---|---:|---|
| 4 | `expected-max-v1` | 148.543 | `mean-score-v1` found 200+ in two weeks and 230+ in one; expected-max found 200+ in one and no 210+ week. |
| 14 | `coverage-194-v1` | 163.197 | `mean-score-v1` found 200+ in three weeks and 240+ in one, despite a lower 159.814 mean maximum. |
| 80 | `tail-ladder-200-210-220-v1` and `block-supported-tail-ladder-v1` | 178.435 | `regime-robust-ladder-v1` and T230 each covered seven 200+ weeks, while the tail ladders covered six but won mean maximum and had two 230+/240+ weeks. |

This is evidence for entry-count-specific retrieval presets. Expected-max is
the strongest four-entry default by average maximum; coverage-194 is strongest
at 14 by that metric; and the tail-ladder family is strongest at 80. A single
global selector would discard real signal visible in the frozen results.

## Rotated-scope robustness at 80 entries

The five holdout scopes were fitted without one simulated-world block apiece.
Their realized results are diagnostics for sensitivity to the simulated-world
fit, not separately deployable outcome-tuned alternatives.

| Strategy | Final-fit mean | Mean over five holdout fits | Holdout range |
|---|---:|---:|---:|
| `coverage-194-v1` | 176.882 | 178.225 | 177.761-178.569 |
| `strict-200-coverage-v1` | 176.359 | 177.817 | 177.425-178.306 |
| `tail-ladder-200-210-220-v1` | **178.435** | **178.628** | 177.714-179.629 |
| `mean-score-v1` | 176.003 | 177.548 | 176.051-178.087 |
| `expected-max-v1` | 176.537 | 177.719 | 177.045-179.441 |
| `block-supported-tail-ladder-v1` | **178.435** | 178.551 | 177.714-179.629 |
| `regime-robust-ladder-v1` | 177.103 | 178.550 | 176.869-179.773 |
| `strict-230-coverage-v1` | 177.462 | 178.463 | 176.915-179.753 |

The tail-ladder conclusion is not an isolated final-fit accident: the ordinary
tail ladder also has the highest mean across the five rotated fits. Regime
robustness and T230 remain plausible threshold-coverage sleeves rather than
replacements for the tail ladder.

## Interpretation

1. **The tail ladder is the current 80-entry retrieval leader.** It has the
   strongest average weekly maximum, four 220+ weeks, and two 230+/240+ weeks.
   Its block-supported variant ties every displayed weekly-maximum result but
   has a slightly different selected-lineup score mean, so the two books are
   not assumed identical.

2. **T230 does not validate its literal name as a realized 230 optimizer.** It
   covers seven 200+ weeks and has the highest median weekly maximum, but only
   one realized 230+/240+ week versus two for five other strategies. Strict
   simulated >230 coverage is therefore useful but not well enough calibrated
   to serve as the sole retrieval law.

3. **Mean score creates depth, not broad weekly tail coverage.** Its 22 total
   200+ lineup occurrences are the most by a wide margin, but they occur in
   only six weeks and its average weekly maximum is the lowest of the eight at
   80 entries. High individual-lineup expectation is clustering redundant
   realized tail outcomes rather than covering more slates.

4. **Average maximum and threshold coverage encode different objectives.** At
   80 entries, the tail ladders win average maximum, while regime robust and
   T230 find a 200+ lineup in one additional week. A production portfolio can
   use a dominant tail-ladder core plus a preregistered, bounded robustness
   sleeve instead of pretending one scalar ranking answers both objectives.

## What this release does not establish

- Contest rank, duplication, ties, payout, and ROI are unavailable because a
  complete field and payout-settlement source was not supplied.
- The seven corpus-fill arms were pooled before retrieval. These results
  compare selectors over the pooled union; they do not isolate which fill arm
  is best.
- Current selectors used simulated scores and diversification only. Boom,
  ownership, leverage, matchup, Fantasy Points coverage, SIS, and winner
  likeness were not selection inputs.
- The bounded report intentionally omits lineup/player identities and
  per-slate rows. It cannot by itself explain which pre-lock player traits
  produced the successful selections.
- The result grants no historical retune, retry, promotion, decision, graph,
  or production authority.

## Next analysis release

The next artifact should join the already frozen candidate/book lineage to the
already published grade shards without regenerating candidates or rescoring:

`(slate, lineup_id) -> fill/world provenance -> selector/rank -> realized score -> point-in-time traits`

That attribution release should first quantify corpus-ceiling capture,
selector regret, rank of each high scorer, exclusive versus multi-arm origin,
and selected-player contribution. Corrected ownership, boom, odds, role, and
matchup features can then be attached under their own point-in-time source
identities and evaluated through matched controls and ablations.

The older canonical matchup-inclusive R6-v2 experiment remains separate and
unfinished. Its newer source-v2 modules are offline contracts and reducers,
not an executable/publishing source. Completing that experiment requires a
fixed-G0 candidate-authority binding, exact upstream provenance bodies, an
outcome-blind 54-slate source publication, and a versioned successor R6
consumer before any matchup-versus-neutral outcome comparison.
