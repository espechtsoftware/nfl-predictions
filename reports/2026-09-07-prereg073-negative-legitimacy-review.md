# PREREG-073 negative-legitimacy review

**Review date:** 2026-09-07
**Experiment:** PREREG-073 / experiment 101 / JPAR-1b
**Question reviewed:** Was the recorded negative legitimate?
**Review disposition:** **The no-promotion decision is legitimate. The shorthand
“negative” is not an adequate scientific description.**

## Executive conclusion

PREREG-073 correctly failed its two frozen co-primary gates and therefore does
not authorize adoption, promotion, a same-panel relaunch, or tuning. The
execution, support census, outcome boundary, reader, arithmetic, and independent
reproduction all appear valid. I found no mechanics, identity, contamination,
or post-outcome exclusion defect that plausibly manufactured the failure.

The result does **not** show that JPAR-1b reduced scores or that participation
modeling is ineffective. Both primary point estimates were favorable. The
score endpoint was an extremely close near-miss, favorable across all banks
and leave-one-season-out contrasts despite a microscopically adverse 2022
season mean. The calibration endpoint was favorable in aggregate but weak and
season-dependent. The precise interpretation should be:

> PREREG-073 formally failed its two predeclared co-primary interval gates.
> Promotion remains `NONE`. The score axis is an unpassed near-miss, while the
> calibration benefit was not established. Close only the exact binary
> designated-player pre-allocation implementation under its frozen information
> set, proxy objective, pool, selector, budget, and common-support panel.

Do not summarize the result as “JPAR-1b was shown not to work” or “both effects
were negative.”

### Terminology correction: the decision was negative, the observed score effect was positive

In this review, “negative” applies only to the binary **promotion decision**:
the two frozen confidence gates did not both pass, so automatic promotion was
not authorized. It does **not** describe the direction of the observed scoring
effect. The raw K80 result improved by `+1.0806` points, with `16` weekly wins,
`5` losses, and `27` ties; weeks at or above 200 increased from `8` to `10`.
Those are favorable observations. Their uncertainty interval crossed zero, so
they are promising evidence rather than a demonstrated effect. The accurate
short label is therefore **favorable unpassed near-miss / no promotion**, not
“negative scoring result.” Any project summary that uses “negative” without
this distinction should be corrected.

## What PREREG-073 tested

The comparison held the sealed REDIST D800 candidate population, the three
simulation banks, the dual-law expected-max K80 selector, and all non-treatment
inputs fixed.

- `J0` was the frozen post-score P_MIX critic.
- `J1` applied the same binary designated-player participation masks inside the
  historical simulator before allocating team targets and carries.
- The score co-primary was `J1 - J0` realized K80 winner-CDF utility; favorable
  values are positive and the frozen pass rule required the lower 95% bound to
  exceed zero.
- The calibration co-primary was `J1 - J0` beneficiary-only 200–260 twCRPS;
  favorable values are negative and the frozen pass rule required the upper
  95% bound to be below zero.
- Both co-primaries had to pass. Bank, leave-one-season-out, safety, and
  current-policy-reference conditions were vetoes or downstream gates; they
  could not rescue a missed co-primary.

These rules were frozen in PREREG-071 section 7 and incorporated unchanged by
PREREG-073 sections 7–8 before the efficacy outcome read.

## Execution and provenance audit

The result is a valid efficacy result rather than a procedural failure.

1. The first efficacy attempt, r1, was correctly voided after one Cloud Run
   task failed to start. Bank 750 finished 17/18, bank 751 finished 18/18, bank
   752 was never claimed, and no r1 result body or outcome reader was opened.
2. The r2 recovery used fresh create-once prefixes while preserving the same
   estimand, arms, candidate pools, source-bank mapping, random seeds, support
   census, resource envelope, and scientific runner.
3. All three r2 banks completed 18/18 tasks with zero failures,
   cancellations, or retries. The resulting opaque cohort seal was bound only
   after terminal completion.
4. The scientific runner was frozen at SHA-256
   `ea8fcd453d7dbc70e2fe347b19f960febd67cdaf227905203bf298e837cda7fd`.
   The terminal reader was SHA-256
   `b74003ac84c3ad866436bfa084a2b14fc5ef9e094d7c32570860399520e60c67`.
   The only reader-code change from the launch binding to terminal binding was
   replacement of the cohort-seal placeholder with its exact four-field
   identity.
5. The authorized lab first read ran once from a clean detached checkout with
   an explicit import-origin guard. The committed result is 351,538 bytes,
   SHA-256
   `9f54ceef55db419ae63d3c9ce16b2dd58d0c47c5b4baac010e81599e7ec57c8a`;
   the transcript is 3,729 bytes, SHA-256
   `4c3da8e840e0d9f98dc7fcc812c31aa7140c72a449963e13119718a4106830df`.
6. Production independently invoked the same frozen reader from a fresh clean
   detached checkout and reproduced both artifacts byte-for-byte.

The score-free support census enumerated all 162 declared cells before
efficacy. It found 152 valid cells (93.827%), including 94.444%, 92.593%, and
94.444% within 2022, 2023, and 2024. This exceeded the frozen 90% overall and
85% per-season floors. Ten cells were unavailable for frozen, typed reasons:
three empty-opportunity-support cells and seven pool-not-reproduced cells.

The predeclared complete-bank intersection then retained 48 of 54 slates, or
144 analyzed cells, and discarded eight otherwise-valid cells belonging to
the six incomplete slates. Availability was determined without outcomes and
was identical for both arms. This is not evidence of cherry-picking, although
it limits generalization to the 48 common-support slates.

## Exact result and gate arithmetic

| Endpoint | J1 − J0 estimate | Frozen 95% interval | Frozen gate | Correct interpretation |
|---|---:|---:|---|---|
| K80 winner-CDF utility | `+0.0039001452` | `[-0.0000504754, +0.0083768389]` | FAIL | Favorable near-miss; improvement not established at the frozen confidence rule |
| Raw K80 realized maximum | `+1.0805556` DK points | `[-0.1262745, +2.0924444]` | Diagnostic only | Suggestive score gain, not independently conclusive |
| Beneficiary twCRPS | `-0.0000106015` | `[-0.0000492732, +0.0000129516]` | FAIL | Favorable aggregate, but uncertain and season-dependent |
| J1 vs. current PG_CTRL reference utility | `+0.0102415` | `[+0.0001240, +0.0178408]` | PASS | Context only; cannot override the failed J1-vs-J0 co-primaries |
| Inactive-lineup contamination | J0 `0.220052`; J1 `0.219965` | n/a | Safety PASS | Treatment did not worsen this safety outcome |

The decision code used the correct directions: positive for score and negative
for twCRPS. Because the score lower bound was not strictly greater than zero
and the calibration upper bound was not strictly less than zero, both
`interval_pass` values were false. The preregistered branch therefore emitted
`FAIL_BOTH_CLOSE` and `promotion: NONE`. That arithmetic is correct.

The descriptive score surface was favorable at K80:

- mean book maximum increased from `181.2697` to `182.3503`;
- mean oracle-to-book regret fell from `12.1172` to `11.0367`;
- weeks at or above 200 increased from `8` to `10`;
- weeks at or above 210 increased from `1` to `2`;
- weeks at or above 220 and 230 were unchanged at `1` each;
- all three score-bank point estimates were positive;
- all three score leave-one-season-out estimates were positive; and
- the treatment changed about 14.85% of the K80 book but captured only 24 of
  645 candidates outside J0 that retrospectively beat the J0 book maximum.

This is a favorable descriptive pattern worth preserving, but it is not a
sufficiently stable demonstration of the registered mechanism.

## Why the score result is a near-miss

The reader performs a season-clustered percentile bootstrap with 20,000 draws,
but the analyzed data contain only three season clusters. Each bootstrap draw
samples three seasons with replacement. There are only 27 ordered cluster
draws. Each specific all-one-season sequence has probability
`1/27 = 3.7037%` (all three such sequences collectively have probability
`3/27`), which is larger than either 2.5% tail of a two-sided 95% interval.
For this realized sample, the reported interval endpoints are therefore forced
to equal the worst and best observed season effects.

| Season | Score utility delta; positive favorable | Raw K80 delta | Calibration delta; negative favorable |
|---|---:|---:|---:|
| 2022 | `-0.0000504754` | `-0.1263` | `+0.0000013528` |
| 2023 | `+0.0039007793` | `+1.4142` | `+0.0000129516` |
| 2024 | `+0.0083768389` | `+2.0924` | `-0.0000492732` |

Thus the score CI missed because 2022 was microscopically adverse while 2023
and 2024 were favorable. Under the same discrete resampling law, a one-sided
95% percentile lower bound would be positive; that is useful only for
understanding conservatism and must not replace the frozen two-sided-95 rule
after outcomes were opened.

Calibration is materially weaker. Its aggregate favorable estimate is driven
by a larger 2024 improvement, while the 2022 and 2023 seasonal means are
adverse. Dropping 2024 makes calibration adverse. A different conventional
directional interval would therefore not make the required two-endpoint case
persuasive.

The 20,000 bootstrap iterations add Monte Carlo smoothness but cannot create
more than three independent season clusters. The interval is highly discrete,
and nominal small-cluster coverage is not well calibrated. There was also no
documented minimum-detectable-effect or power analysis. The decision is
contractually valid, but the experiment had low ability to distinguish a
moderate score improvement from zero.

## Winner-utility limitation

The score primary uses `winner_cdf_v1`, a smoothed pooled distribution of 48
recorded 2023–2025 winner scores. The implementation explicitly labels it
`GLOBAL_WEMAX_PROXY`, not the probability of beating the same-slate winner.
It also discloses reuse of development-era outcome information through the
shape of the utility.

The winner-registry-v2 audit had already found that the lab's 48 score labels and
production's 51 governed roster labels share 46 season/week keys but disagree
on 11 scores by as much as 30.46 points. At least four shared keys have
different nine-player rosters, and some weeks had multiple simultaneous
Millionaire contests. The registry used by PREREG-073 is therefore correctly
described as pre-adjudication.

This limits the construct and external validity of the exact winner-CDF
estimate. Applying the same frozen monotone utility to both arms preserves the
arithmetic and contractual fidelity of the declared proxy comparison, but it
does not immunize the contrast from a misspecified or pre-adjudication utility
shape. The limitation still does not justify promotion: the raw-score interval
crossed zero and the independent calibration co-primary failed.

Do not silently rescore PREREG-073 with a future registry v2 and call it the
same read. A corrected registry, different objective, or prospective 2026
grader is a new information set and requires a separately named,
pre-registered evaluation.

## Reporting and governance defects that should be corrected

These defects do not overturn the no-promotion decision, but they should not
be deferred because they will mislead future assistants.

1. **Near-miss label omitted.** `LAB_RULES.md` requires a separate
   `unpassed near-miss` classification when the point estimate and every bank
   are favorable but the bound misses. The PREREG-073 score endpoint meets
   that definition, yet the reader exposes only `pass: false` and the combined
   `FAIL_BOTH_CLOSE` label.
2. **Calibration W/L labels have the wrong semantic direction.** The shared
   `paired()` helper counts positive weekly deltas as “wins” for every
   endpoint. Positive is worse for J1-minus-J0 twCRPS, so calibration's stored
   `42 wins / 6 losses` is directionally mislabeled. Those counts do not feed
   the decision and were omitted from the calibration transcript line, so
   this is a reporting defect rather than a verdict defect.
3. **The preregistration header is stale.** Lab `origin/main` still says
   PREREG-073 is `PROPOSED` and that nothing has been frozen, launched, or
   read, despite the completed and independently reproduced closure.
4. **The required ledger row is absent.** Lab `LAB_RULES.md` requires one
   experiment, one result, and one ledger row, with negative results recorded
   as carefully as positives. Current lab `origin/main:LEDGER.md` contains no
   PREREG-073 / experiment-101 / JPAR-1b row.
5. **Support wording is ambiguous.** The transcript's `valid 144` means
   analyzed cells after complete-slate intersection. The support census
   actually had 152 valid cells. Both numbers should be named explicitly.

The lab record should be updated promptly with a closed-status header, the
exact result/transcript hashes, a sign-aware near-miss description, and the
missing ledger row. This is documentation repair only; it must not reopen,
recompute, or change the frozen decision.

## Required disposition

1. **Uphold `promotion: NONE`.** Do not adopt JPAR-1b from this result.
2. **Do not tune or rerun this exact treatment on the opened panel.** The
   frozen no-promotion rule was correctly applied.
3. **Record the score axis as `UNPASSED_NEAR_MISS`.** Retain the favorable
   `+1.0806` raw K80 signal and its uncertainty rather than flattening it into
   an adverse-result label.
4. **Describe calibration as unestablished and season-dependent.** Its
   aggregate direction is favorable, but two of three seasonal effects are
   adverse.
5. **Close only the tested implementation:** binary designated-player
   participation before allocation, under the pre-adjudication
   `winner_cdf_v1` objective, sealed REDIST D800 population, dual-law
   expected-max K80 selector, three source banks, and 48-slate common-support
   panel.
6. **Keep broader mechanisms open.** Richer role states, all-player
   participation, market-conditioned dependence, and materially different
   coherent allocation laws were not tested by PREREG-073. Any follow-up must
   be a fresh preregistration under a genuinely changed implementation,
   information set, objective, budget, or prospective 2026 clock—not a
   post-hoc amendment of 073.

## Authoritative evidence reviewed

- Lab first-read commit:
  `0619a8f76ad2c54900693d82e84527bc6d1470aa`.
- Production cross-verification commit:
  `3cddf6bd0cf333288f50876fe5126237b7e76451`.
- Frozen scientific source:
  `406b73b14a7ab9a2681c705cec49a64197b28995`.
- Immutable image:
  `sha256:367ab978aa103be97823538be9a9e42b6ad6c3709f0d7ed8999fec75c019d801`.
- Support seal: generation `1788725644157691`, SHA-256
  `932282150d627d54cc90bca13e3b3f18e61b20ca8e40355edc106444fd7bd3c4`.
- r2 cohort seal: generation `1788742361175060`, SHA-256
  `2661c6e6413678cb8709ae49cd00f8e8a916a8414fbcbf0c5ebe18ae04589d58`.
- Lab files at the first-read commit: `PREREG-073.md`, `PREREG-071.md`,
  `LAB_RULES.md`, `experiments/101_jpar1b.py`,
  `scripts/prereg073_report.py`, `src/nfl2/selectors.py`,
  `results/prereg073_read_v1.json`,
  `results/read-transcripts/prereg073-first-read-transcript.txt`, and
  `results/prereg073_first_read_receipt.json`.
- Production's local winner-registry audit:
  `reports/2026-09-01-winner-registry-v2-adjudication-status.md`.

This review did not launch cloud work, reopen raw efficacy shards, execute a
third outcome reader, rescore the panel, or change any production/lab policy.
It audited the frozen committed result, source, identities, and the existing
byte-identical independent reproduction.
