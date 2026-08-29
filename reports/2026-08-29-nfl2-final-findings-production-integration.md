# NFL2 final findings and production-integration decision

**Date:** 2026-08-29
**Decision:** authorize `lev40/boom160` only as a paired,
production-shaped shadow after Gate D0 passes. Keep the incumbent money path
unchanged until the historical and prospective gates below pass.
**Evidence status:** strong evidence for a boom-heavy allocation in the NFL2 laboratory; no direct evidence yet for its effect under the exact production K1 system. The 360-boom extension is not robust enough to adopt.

## Executive conclusion

The NFL2 work found a strong, internally consistent signal within its observed
laboratory grid, but its two principal estimates answer two different
questions:

1. **Allocation result:** under the laboratory K3 component control, changing from `lev160/boom40` to `lev40/boom160` improved the weekly maximum at K100 by **+4.737 points**.
2. **Component result:** after both arms were already using `lev40/boom160`, K1 improved on K3 by **+2.484 points**.

These effects must **not** be added into a claimed `+7.2` production improvement. The experiment matrix never measured the missing direct cell—incumbent allocation versus boom-first allocation with both arms running K1. Interaction between allocation and component choice is therefore unknown.

The appropriate aggressive move is to wire an outcome-blind, paired
`lev40/boom160` shadow alongside an incumbent-shaped `lev160/boom40` control
shadow, then launch it as soon as D0 passes. The separate incumbent remains
the only money path.

## Production integration status

The isolated transport and production-shaped comparison are implemented in
this repository. The implementation exposes an exact `N_LEV` solve dose while
leaving the incumbent money environment unchanged, constructs independent
five-book K1/role12 CBWU arms, applies the same exact-80 coverage-194 selector,
and freezes create-only control, treatment, manifest and terminal artifacts.

Before an execution can claim completion, it now fails closed unless all ten
R0--R4 native books prove the requested leverage/boom allocation; zero solver
errors or infeasible solves; exact main and role model versions; identical
full score-blind player-input hashes; identical 50,000 player worlds across
arms; and frozen 20/40/80 memberships. Candidate deduplication may change pool
size and is reported separately from solver failure, matching the laboratory's
equal-requested-work estimand.

The cloud launcher uses the unscheduled `atlas-minimal-c-smoke` transport at
the existing Cloud Run Jobs quota. It captures that job's exact prior spec,
requires no running execution or scheduler reference, launches one task with
zero retries, restores the prior spec immediately, and verifies the restored
spec hash. A create-only cloud lease serializes cooperating launchers; durable
pre-mutation recovery and execution snapshots survive a local process loss;
and the launcher refuses to overwrite a concurrent third-party job change.
The execution's image, command, args, environment, resources, service account,
retry and timeout contract are verified before success. The image itself
embeds the full clean source commit and the runner requires it to equal the
separate full `CODE_SHA`. No scheduler and no money path are modified. A real
outcome-blind artifact smoke and the exact historical grade remain required
before any promotion claim; the external `+4.737` result has not yet been
reproduced by this production-shaped implementation.

The historical paired construction core and an injection-only replay adapter
are also implemented and fixture-tested. They cache one score-blind
projection/world source per R0--R4 seed, build both allocation arms from that
source, freeze nested memberships, and keep each target slate's outcomes
absent until a separate grader. Prior-season realized labels may legitimately
train later targets; the boundary is target-slate outcome blindness, not an
incorrect claim that historical model fitting reads no realized labels.

That adapter is a foundation, not yet a runnable or verdict-capable Gate H1
job. The remaining requirements are: an authoritative immutable panel index;
byte-verified identities for the outcome-null skill panel, prior-only labels,
common-lock market data, TabPFN cache/version, strictly-prior preprojected DST
inputs and trained main/role models; an outcome-null real-slate solver smoke;
a separately frozen, identity-complete actual-points snapshot after the books
freeze; and the missing per-seed, leave-one-seed-out, exposure/duplication and
uncertainty reporter. The current 2023--2024-only panel has just two season
clusters, so any season-cluster interval is descriptive unless the immutable
PIT panel is expanded. The adapter rejects 2025 rather than treating it as a
holdout.

## What was verified

### 1. Boom-first allocation is a strong laboratory result

PREREG-001 compared allocation C (`lev160/boom40`) with allocation B
(`lev40/boom160`). Both arms used the laboratory K3 component control, the
same 89 development slates, seed banks 10/11/12, 200 requested candidate
solves, coverage line 194, and a K100 primary book. That experiment did not
include production's separate role12 family or its five-book CBWU mechanism;
the production shadow transfers the allocation hypothesis into a richer
system rather than recreating the laboratory arm exactly.

| Measure | Control C | Boom-first B | Paired change |
|---|---:|---:|---:|
| Mean weekly maximum, K100 | 176.271 | 181.008 | **+4.737** |
| Mean weekly maximum, K80 | — | — | **+3.885** |
| Weeks at least 200, K100 | 10.33 | 15.00 | +4.67 |
| Weeks at least 210, K100 | 4.00 | 8.33 | +4.33 |
| Weeks at least 220, K100 | 1.67 | 4.00 | +2.33 |
| Pool oracle | 177.586 | 185.609 | +8.023 |
| Oracle regret | 1.315 | 4.601 | +3.286 worse |

The published season-cluster bootstrap interval was `[2.983, 6.409]`; leave-one-season-out estimates were all positive, from `+4.151` to `+5.454`. Independent checks from the raw shards also found all three seed-bank means positive: `+3.588`, `+3.526`, and `+7.097`.

Relevant sources:

- `/home/erich/projects/nfl2/PREREG-001.md:6-28`
- `/home/erich/projects/nfl2/experiments/019_prereg_stack.py:17-21,35-51`
- `/home/erich/projects/nfl2/handoffs/002-prereg001_report.json:7-24,64-80,120-145`

Interpretation: increasing the boom allocation generated substantially better top books in this laboratory design. The higher oracle regret also says retrieval did not capture all of the better pool tail; boom-first generation and retrieval improvement remain separate opportunities.

### 2. K1 beats K3 after boom-first is already fixed

PREREG-004/027 compared K3 B against K1 D with **both** arms using `lev40/boom160`.

| Measure | K3 | K1 | Paired change |
|---|---:|---:|---:|
| Mean weekly maximum, K100 | 179.689 | 182.173 | **+2.484** |
| Mean weekly maximum, K80 | — | — | **+2.111** |
| Weeks at least 200, K100 | 13.00 | 16.00 | +3.00 |
| Weeks at least 210, K100 | 7.00 | 7.33 | +0.33 |
| Weeks at least 220, K100 | 2.00 | 3.00 | +1.00 |

The published interval was `[1.846, 3.083]`; all leave-one-season-out estimates were positive, from `+2.230` to `+2.708`. Raw-shard seed-bank means were `+3.039`, `+1.840`, and `+2.572`.

Relevant sources:

- `/home/erich/projects/nfl2/PREREG-004.md:1-16`
- `/home/erich/projects/nfl2/experiments/027_k3_components.py:18-27`
- `/home/erich/projects/nfl2/handoffs/prereg004_027_k1_vs_k3.json:7-28,30-68`

Interpretation: K1 is the better component design conditional on boom-first. This supports preserving production K1; it does not estimate the allocation effect within K1.

### 3. The 360-boom extension is too fragile to adopt

PREREG-004/025 compared 200 requested solves (`lev40/boom160`) with 400 (`lev40/boom360`). Its published K100 change was only `+0.679 [0.256, 1.151]`.

The raw bank means were `-0.633`, `+0.309`, and `+2.359`; leaving out bank 62 made the aggregate estimate negative (`-0.162`). The stronger uncertainty checks crossed zero. The larger pool raised the oracle from `185.761` to `192.144`, but oracle regret nearly doubled from `5.391` to `11.096`. This is evidence of an unresolved retrieval problem, not a production case for 360 boom solves.

Decision: park `lev40/boom360` as research-only. Do not spend production compute on it until retrieval at depth is materially improved and the result survives seed-aware validation.

## Stronger uncertainty assessment

The published reporter resamples only five seasons and does not incorporate seed-bank uncertainty (`/home/erich/projects/nfl2/scripts/prereg001_report.py:20-33,36-53`). With five season clusters, the smallest attainable exact two-sided cluster sign-flip p-value is `0.0625`; the published percentile-bootstrap intervals are therefore descriptive rather than conventional confirmatory evidence.

Independent raw-shard checks produced:

| Contrast | CR1 season-cluster t interval, 4 df | Two-way bank + season bootstrap | Seed-bank assessment |
|---|---:|---:|---|
| Boom-first minus incumbent allocation, K3 | `[1.954, 7.520]` | `[2.286, 7.922]` | all 3 positive |
| K1 minus K3, boom-first fixed | `[1.518, 3.450]` | `[0.995, 4.277]` | all 3 positive |
| 360 boom minus 160 boom | `[-0.040, 1.397]` | `[-1.209, 2.725]` | one negative; leave-one-bank can reverse sign |

Thus the first two findings are consistent across the available uncertainty views; the 360-boom finding is not. Production evaluation must continue reporting both season- and seed-aware uncertainty, not only a season bootstrap.

## Outcome-leakage and panel boundaries

The audited primary result shards for experiments 019, 025, and 027 comprised 18 shards per run, exactly 89 unique development slates, and seasons `{2019, 2021, 2022, 2023, 2024}`. No 2025 realized rows appeared in those result shards, and the compared arms had complete, matched books.

However, **2025 is not a pristine system-level holdout**:

- The NFL2 manifest identifies readable 2025 R6 freezes, realized grade shards, and world artifacts: `/home/erich/projects/nfl2/benchmark/MANIFEST-v1.json:460-515,904-934,1324-1338`.
- The data layer exposes v0 worlds and R6 roots without a season guard: `/home/erich/projects/nfl2/src/nfl2/data.py:35-38,86-94`.
- The simulator embeds rates fitted through 2025 and the pipeline enables that possession mode: `/home/erich/projects/nfl2/src/nfl2/core/game_sim.py:8-10,59-68,93-96`; `/home/erich/projects/nfl2/src/nfl2/pipeline.py:30-34,102-123`.
- Lineup and feature construction contain choices informed by 2025 winner/result analysis: `/home/erich/projects/nfl2/src/nfl2/core/lineup.py:27-35,142-150,181-191,522-525`; `/home/erich/projects/nfl2/src/nfl2/core/featureset.py:82-87,149-154`.
- Alternate readable copies and broad runner permissions mean bucket sealing alone did not provide a clean outcome-access boundary.

Consequently, 2025 evidence may be reported as **descriptive, previously informed historical evidence**, never as a one-shot untouched holdout. The first genuine forward confirmation is the frozen, pre-lock 2026 paired series. This review did not open sealed 2025 outcome artifacts; the boundary conclusion comes from manifests, code paths, and access topology.

## Production decision

### Adopt now

Adopt one experimental configuration only:

- **Incumbent-shaped control shadow:** `lev160 + role12 + boom40`.
- **Treatment / shadow only:** `lev40 + role12 + boom160`.
- Each native seed book requests exactly `200` core leverage-plus-boom solves
  and 12 separate direct-role slots: 212 requested family slots per book, or
  1,060 across each five-book CBWU arm. Including the registered QB-variant,
  game-stack and dark-game auxiliary families, nominal full accounting is 266
  requested solves per native search and 1,330 per five-book arm, before
  failures, retries, infeasibility or deduplication.
- Treatment is separately labeled and cannot flow into entries.
- Books are frozen before target-slate outcome access and graded as a paired
  experiment; strictly prior labels may be used for walk-forward training.

The explicit configuration seam exists in
`src/nfl_dfs/inference/production_policy.py`, and explicit `N_LEV` resolution
exists in `src/nfl_dfs/backtest/engine.py`. Before deployment, the
configuration receipt must prove the only intended behavioral difference is
the leverage/boom allocation.

### Reject from production integration

Do not port the external lab's closed or negative ideas into the production path:

- additive shootout overlay;
- stratified boom ordering;
- anti-correlated DST law;
- breakout marginals/order tilt;
- replacement analog/copula;
- relaxed-shape sleeves;
- residual-world columns;
- 30,000-lineup selection bank;
- overlap caps or tail ladders;
- late-swap chase/fresh-ticket variants.

These ideas either failed, were null, did not replicate, or add complexity without verified scoring benefit.

### Park for separately preregistered research

- `lev40/boom360` and any larger boom depth;
- improved retrieval at depth, motivated by the boom pool's increasing oracle regret;
- field duplication and payout-aware modeling;
- corrected ownership/exposure diagnostics;
- full weekly contest standings and ownership capture;
- a complete K1 allocation factorial if the exact paired production-shaped historical run cannot answer the deployment question.

## Exact production invariants

The paired arms must be identical except for `N_LEV`, `N_BOOM`, the corresponding total-allocation receipt fields, and experiment identity. Freeze and assert all of the following:

| Invariant | Required value |
|---|---|
| Production policy | `classic-k1-role12-boom40-poscal-cbwu-v4` as the control baseline |
| Models / registry | K1, `MODEL_ENSEMBLE=1`, `tail_k1` |
| Entered book size | 80 |
| Role candidates | direct `role12`; `N_EPISTEMIC=12`, `EPISTEMIC_FAMILY=role_draws` |
| Candidate allocation, control | `N_LEV=160`, `N_BOOM=40` |
| Candidate allocation, shadow | `N_LEV=40`, `N_BOOM=160` |
| Requested allocation | per native book: 200 core leverage plus boom, plus role12; per five-book arm: 1,000 core plus 60 role |
| Unique-fill behavior | `BOOM_UNIQUE_FILL=0` |
| Selector | greedy tail coverage, coverage line 194 |
| Salary floor | 49,000 |
| Blend | 0.45 |
| Worlds | identical CBWU five frozen seed pairs, 10,000 worlds per block, identical ordering |
| Stack rules | QB stack minimum 2; bring-back minimum 1; forbid RB versus DST; forbid two same-team RBs |
| Punt setting | `PUNT_MIN=0` |
| Point-in-time inputs | identical slate snapshot, player pool, projections, availability, model and market blend |
| Output isolation | shadow cannot be entered or replace the incumbent book |

Use durable identities such as `2026-boom-first-control-v1` and `2026-boom-first-v1`. Record attempted, successful, and unique lineups by generation family. Equal requested work does not guarantee equal unique output or equal runtime, so wall time and failure counts are required diagnostics.

## Required gates

### Gate D0 — deployment and isolation

Before running any scored comparison:

1. Produce canonical resolved-environment receipts for both arms and mechanically diff them.
2. Fail closed if any value outside the allocation, derived budget, or experiment-identity allowlist differs.
3. Confirm each native book requests 200 core leverage-plus-boom solves plus
   role12 (1,060 leverage/boom/role slots per five-book arm), retains the
   270 auxiliary slots, and therefore discloses 1,330 nominal requested solves
   per arm. K1, CBWU, constraints, world ordering, selector, and exact-80 book
   size remain unchanged.
4. Verify shadow outputs use a separate namespace and have no route to entry export.
5. Log source-snapshot, model, world, seed, candidate-book, selector-book, code, image, and configuration hashes.
6. Freeze both books before slate lock or any realized-score read.

### Gate H1 — exact production-shaped historical comparison

Run the missing direct contrast: K1 incumbent allocation against K1 boom-first allocation, using identical historical point-in-time inputs and world/CBWU artifacts.

Before this gate can run, freeze and verify the authoritative panel index and
the bytes/as-of times of every score-blind component: salary eligibility,
target-outcome-null features, prior-only training labels, market snapshot,
TabPFN table/cache, preprojected DST/QB/Vegas inputs, and main/role
model-feature identities. After every book is immutable, create a separate
canonical actual-points snapshot with complete normalized skill and DST
identity coverage. A caller-provided URI/hash string without recomputing or
verifying the injected bytes is not sufficient evidence.

- Primary estimand: paired weekly maximum at **K80**, the actual production book size.
- K100: diagnostic only, and only when both arms have the same valid nested availability.
- Report thresholds at `194`, `200`, `210`, `220`, and `230`; pool oracle; selector regret; per-season and per-seed results; attempted/successful/unique candidates; exposure, duplication proxies, and runtime.
- Retain native seed books and report per-seed and leave-one-seed-out results,
  exposure/duplication diagnostics, season-cluster CR1 and a two-way season +
  seed bootstrap. Require the sign to remain positive in every seed bank or in
  all leave-one-seed-out estimates. With only 2023--2024, inferential intervals
  are descriptive because there are only two season clusters.
- Correctly label all 2025 reads as previously informed/descriptive.
- Do not tune after opening target-slate realized outcomes. Target-slate
  outcome access occurs only after immutable control and treatment books are
  frozen; earlier slates may supply strictly prior walk-forward labels.

This gate estimates the production-relevant allocation effect directly. It supersedes any temptation to add `+4.737` and `+2.484`.

### Gate P1 — 2026 prospective confirmation

For every eligible 2026 slate:

1. Freeze both 80-lineup books before lock with immutable receipts.
2. Keep the incumbent as the only money path.
3. Capture full contest standings and ownership promptly after the contest, then grade both books.
4. Evaluate the preregistered paired weekly maximum, score thresholds, duplication/economic guardrails, runtime, and reliability.
5. Do not change the treatment definition in response to interim outcomes; a changed strategy receives a new version and a new prospective series.

Promotion requires a predeclared minimum slate count, a positive paired mean, acceptable tail/duplication economics, no reliability regression, and review of every losing slate—not merely a higher historical average. If the paired mean is not higher or the economic/reliability guardrails fail, retire the shadow rather than moving it into the money path.

## Exposure diagnostic correction

The external exposure report's statement that naive ownership was unchanged is not supported. Recalculation for bank 13 gave mean ownership sums `0.3982` for the incumbent allocation and `0.4290` for boom-first. More importantly, `/home/erich/projects/nfl2/scripts/exposure_diagnostic.py:27-35` clips fractional ownership at `0.5`, which is 50%, before taking logs. The reported log-product near `-6.22` is therefore inoperative; using a 0.5% floor gave approximately `-34.156` versus `-35.327`.

The structural diversity result remains favorable and usable as a diagnostic:

- maximum player exposure: `0.6656 -> 0.5203`;
- mean pair overlap: `2.3190 -> 1.2928`;
- distinct players: `126.78 -> 145.42`.

These are not substitutes for a field duplication or payout model. Production reports should distinguish structural diversity, projected ownership, realized duplication, and payout economics.

## Provenance ledger

### Frozen summaries and benchmark

- Benchmark SHA-256: `04710846d67fb6c6d1eb06335d857846bc206dda696917a379149739851f87cf`
- PREREG-001 summary SHA-256: `92c8926c1d1442747b0d9571c7d6c1e34c4e0e9a019554380e1406daa432afe0`
- PREREG-004/025 local summary SHA-256: `d77497ccf3972c63aea090891ca37fe05ffe4011167b6dc5c5819da701e1dcf1` — local result is ignored/untracked; raw runs are the authority.
- PREREG-004/027 summary SHA-256: `49eeb81c75bf333eed39341b1d6105009b9e4c683f20dd0aee5d5c1aa087ffcd`

### Source commits

- PREREG-001: `470cecad54a97d9951cb877b5284ae3dad3e906c`
- Experiment 019 code: `1e92b8f999189edc2edcf1c247de7e060fd1becf`
- PREREG-004: `058f38693f6871c08832704cb3f283a8fec3badf`
- Experiments 025/027 code: `e3fab74adc3f5e20f5ffccdd256222488dd25a6b`

### Cloud run identities

Experiment 019 image digest: `sha256:94ae8f0df77d850e2b0575c6418892b598d1f69c5569ad59d3b188906e3a9e33`

- `019b10-20260828T173601Z` / `lab-run-dcb42`
- `019b11-20260828T173808Z` / `lab-run-6gwfh`
- `019b12-20260828T183215Z` / `lab-run-qd79r`

Experiments 025/027 image digest: `sha256:e0d664171d9f90e41c700f6fe78b26ce133f677bcd284903f4dc084a0fcd6e4d`

- `025b60-20260829T022321Z` / `lab-run-bxcf6`
- `025b61-20260829T025017Z` / `lab-run-lhbrz`
- `025b62-20260829T025943Z` / `lab-run-gwqz7`
- `027b80-20260829T040634Z` / `lab-run-tm7ql`
- `027b81-20260829T042515Z` / `lab-run-jmg6r`
- `027b82-20260829T043856Z` / `lab-run-ffdcs`

### Canonical raw shard-set hashes

Experiment 019, banks 10/11/12:

- `7a8283e527c94c30c716262d0ea5d7e88a42b3131dee9fedeece77a864014581`
- `1394369340b6d98c37e35506c8dbec598da6179c1983d6b243b54335c8a08bc5`
- `a3b08e2d6c6d9da27f361f4ff057539a8607ccb60251b285e6fb7ec2aad66bec`

Experiment 025, banks 60/61/62:

- `73ad0d1a1fd870cacbbdbeeb928baebb1d2794fb1b1a83c737f99ea7e5729ece`
- `353d955ed39dbe09eedb7c465062649edfa8389be5ce9679eee5858af4226b33`
- `1a5703472f3cbc748761f4c3ae86b29203181309fec4a49183db8e1cdf4ca50b`

Experiment 027, banks 80/81/82:

- `4dee945e24055976a7191f2f71a782d64676e1c9b51734fe8a6aba9613717bfc`
- `53a5b3ffcba4fda55743746b89ec7215df1b04b357ce95d262a6d1a1d52ae060`
- `048218f39dc0303f1e1b8339a0eb3aa0af91fe779f01b7672edb72dfb9020c0b`

### Provenance limitations

The NFL2 raw envelopes can leave `image` empty when `IMAGE_DIGEST` is unset (`/home/erich/projects/nfl2/src/nfl2/run.py:40-53`); upload is not create-only; the reporter validates arguments, a shortened code SHA, and benchmark identity rather than the full benchmark hash and image (`/home/erich/projects/nfl2/src/nfl2/tasks.py:29-51`); and the cloud-build tag is not cryptographically bound to a clean source commit (`/home/erich/projects/nfl2/scripts/lab_build.sh:5-9`, with `.git` excluded). The 025 summary is also ignored/untracked.

Accordingly, the external evidence is strong enough to authorize a paired shadow and exact replay, but not strong enough to authorize direct production promotion. The production harness must emit stronger immutable receipts and reproduce the relevant effect under the invariant envelope above.

## Final disposition

| Item | Disposition |
|---|---|
| `lev40/boom160` | **Authorize as an isolated paired shadow after D0** |
| Existing K1 production design | **Keep unchanged** |
| Incumbent `lev160/boom40` money path | **Keep until gates pass** |
| Claimed additive `+7.2` | **Reject** |
| 360-boom extension | **Park** |
| 2025 as pristine holdout | **Reject; label descriptive** |
| Exact K1 allocation historical replay | **Run as highest-priority confirmation** |
| Pre-lock 2026 paired series | **Required for promotion** |

This decision preserves the scoring opportunity while matching the strength and boundary of the evidence: integrate quickly, measure the missing production-relevant contrast directly, and promote only from frozen paired evidence.
