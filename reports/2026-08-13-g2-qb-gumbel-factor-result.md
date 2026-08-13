# G2 QB-rooted Gumbel factor result

Date: 2026-08-13

## Decision

The frozen G2 score-free dependence gate **failed cleanly**. The result is
scientifically valid, but it does not license an exact-80 lineup comparison.
Production remains on the accepted finite-usage law and unchanged incumbent
dependence model.

- Disposition: `g2-dependence-gate-fails`
- Exact-80 licensed: `false`
- Selected calibration cell: `theta_WR=1.0`, `theta_TE=1.05`
- Sole failed mandatory gate: separate QB-WR absolute-log-error improvement

The selected cell is active because it changes TE ranks, but `theta_WR=1.0`
is the identity link for WRs. Consequently the treatment leaves the held-out
QB-WR miss unchanged and cannot satisfy the registered requirement that both
QB-WR and QB-TE improve separately.

## Frozen execution and transport

- Execution: `g2-qb-gumbel-factor-v3-75thv`
- Code commit: `47ff083`
- Image digest:
  `sha256:c81abd2a3887593c35445f0f2b965da0dfc2293496084af770e9e0d64d984342`
- Cloud Build: `29f0c714-8125-48da-8f60-8da1f0adb4ca`
- Terminal status: successful
- Machine report:
  `reports/g2-qb-gumbel-runs/20260812-g2-qb-gumbel-factor-v3/report.json`
- Machine-report SHA-256:
  `aff43f6be30b66178a753938f6324b408789bf1c2ec1ccae5b4dfc9853945dbd`

The harvester reconstructed the checksummed calibration and terminal report
from chunked Cloud Logging transport. The recomputed calibration matched the
opaque V2 calibration JSON hash
`e387a6983df58a18f7f70200c574453e3cc7819ef12b0ce591b222e426f14f69`
exactly, and its fit/historical sections matched the terminal report exactly.
This establishes that the V3 operational repairs did not change the frozen
calibration result.

## Held-out 2023--2025 result

The treatment improved the two primary proper scores across 54 held-out
slates, with both paired whole-slate bootstrap intervals excluding zero:

| Metric | Control | Treatment | Treatment - control | Paired 95% interval |
|---|---:|---:|---:|---:|
| Joint-q90 Brier | 0.018490246 | 0.018467120 | -0.000023125 | [-0.000040320, -0.000007171] |
| Variogram p=0.5 | 1.434919238 | 1.433817879 | -0.001101359 | [-0.001836918, -0.000366275] |

The registered dependence-error summaries also improved:

| Metric | Control | Treatment | Change |
|---|---:|---:|---:|
| Supported G0 absolute-log-error sum | 3.312852 | 2.747302 | -0.565550 |
| G1 weighted absolute-log-error sum | 6.944177 | 5.965699 | -0.978478 |
| QB-TE absolute log error | 0.787420 | 0.307184 | -0.480236 |
| QB-WR absolute log error | 1.138373 | 1.138373 | 0.000000 |

For QB-TE, simulated co-exceedance lift rose from `1.0788` to `1.7438`
against realized `2.3709`, a material reduction in the miss. For QB-WR,
simulated lift remained `1.0644` against realized `3.3228`. The central
QB-WR deficiency therefore remains unresolved.

## Integrity and scope

All registered invariants passed:

- exact sorted marginal draw multisets;
- unchanged non-receivers;
- deterministic finite output;
- historical/control reproduction;
- maximum mean drift `3.55e-15` on held-out treatment rows.

The treatment changed 3,464 eligible receiver-rank rows, skipped 99 ambiguous
and six unsupported QB team-weeks, and evaluated 7,848 active rows / 34,038
registered pairs across 54 slates. No lineup scores were queried by this gate.

## Interpretation and next action

This is useful negative evidence, not a reason to stop dependence research.
A single context-free Gumbel strength per receiver position can partially
repair TE dependence, but score-free calibration selects no WR activation and
therefore cannot repair the much larger, season-stable QB-WR miss. Do not tune
the theta grid, link family or gate on this held-out result, and do not run a
TE-only exact-80 panel: both would violate the frozen protocol.

Because G2 did not change the accepted dependence law, run the registered
portfolio effective-rank/tail-overlap diagnostic on the unchanged incumbent.
Then continue the distinct G3 participation-conditioned allocation hierarchy,
using accepted finite `K=28.154043586960896` as its frozen global center and
control. Any future QB-WR dependence mechanism must be a newly motivated,
separately preregistered conditional mechanism rather than a post-result G2
retune.
