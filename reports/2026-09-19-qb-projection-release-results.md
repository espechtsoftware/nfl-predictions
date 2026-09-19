# QB projection trial released and independently checked

The authorized projection-only trial is deployed. The new 505-row batch at **2026-09-19 20:56:54.107443 UTC** zeros all seven projection fields for the **47 intended backup QBs**. Player identities, model version, salaries and DST projections match the current-input control. Production independently confirmed gate membership and the small non-gated changes in shared handoff `3cd6f64`.

This verifies the release's behavior, not an improvement in realized NFL scoring. The current lab consumer still preserves dispersion when shifting its own draws to zero means. The separately reviewed v4.3 replacement step remains necessary for final admission; production will install it after the running D12800 build completes. See the [full review](2026-09-19-production-qb-replacement-review.md).

## Exact release identities

| Item | Identity |
|---|---|
| Reviewed runtime | production QB branch `8dd7abc954d63567aff956a46db0b1a1d772e1c2` |
| Built source | `f06a192cd9b0aacf798d8f36432a26cac03df206` (adds the cascade test module to Cloud Build) |
| Cloud Build | `d7089008-a38d-4df5-87b2-4121b7119260`, SUCCESS; all boundary/build/smoke steps passed |
| Installed image | `us-central1-docker.pkg.dev/nfl-predictions-503414/nfl-dfs/nfl-dfs@sha256:0993ee01d6d617ed2fa88c51335616c6d473508952fb226201f3cc383db75758` |
| Matched-input control | `project-slate-m9psm`, succeeded; batch `20:53:54.750101Z`; gate disabled only for this execution |
| Gated execution | `project-slate-tspcf`, succeeded at `20:57:00.820745Z`; batch `20:56:54.107443Z` |
| Authorization | Operator “Tonight” after the projection-only limitation was explained; shared `81d809f` |

Only the job image changed. Other task settings, resource limits, command/args, service account, environment and secret references remain as captured. The read-only final template check passed. No schedules or running lab sources changed. The canonical `project-slate` registry lane was released at 20:57:15Z; the validation process's nonzero exit is explained below, not hidden as a successful strict comparison.

## What was verified

- Both final executions succeeded with the exact image and intended execution-level gate setting. Both batches have 505 unique DK identities, valid finite ordered forecasts and the same model/identity/salary fields.
- The captured identity/depth/status rows are exactly equal before control, before treatment and after treatment. ETags of the five tracked input tables are unchanged across this pair. These checks cover the named captures, not every possible upstream source.
- The classifier's exact 47-ID set has zero `proj_points`, `proj_p10`, `proj_p50`, `proj_p90`, `proj_std`, `p_20_plus` and `value`. Production independently distinguishes these 47 newly zeroed QBs from the three QBs already zero under the existing OUT rule.
- Applying the actual zeroing helper to the saved control output leaves every non-gated cell exactly unchanged on common upstream values. The deterministic DST output is also exactly unchanged across the two live runs.

The live sampler uses `seed=None` and draws 30,000 new worlds each execution. Consequently, separate runs are not a common-random-number comparison. The **original 1e-6 equality requirement fails**; that failure and its source are retained. It would be incorrect to label the live batches numerically identical or infer that every observed difference is caused by the QB gate.

| Non-gated forecast field | Maximum absolute difference | Median absolute difference |
|---|---:|---:|
| Mean points | 0.069419 | 0.008009 |
| p10 | 0.484442 | 0.005537 |
| p50 | 0.211246 | 0.016740 |
| p90 | 0.570564 | 0.053310 |
| Standard deviation | 0.223463 | 0.026389 |
| P20 | 0.008233 | 0.000200 |
| Value | 0.020191 | 0.002234 |

All non-gated mean differences are below the previously declared **0.75-point operational alert**. The largest absolute mean difference divided by its conservative two-run Monte Carlo standard error is 1.5713, using reported widened standard deviations and ignoring blend shrinkage. This is a diagnostic consistent with sampling variation, **not an equivalence test**. Quantile differences are reported descriptively.

The supplemental method was recorded in shared `b374180` before any treated output was read. That note's “execution not started” statement was stale: the asynchronous driver had already requested treatment at 20:54:14Z. Shared `44c9e47` corrects the timing. The separate [functional verifier](reviews/evidence/2026-09-19-qb-functional-verification.py) was committed at `72a87c7e` before its data read; four behavioral tests pass. Its [result and artifact hashes](reviews/evidence/2026-09-19-qb-functional-verification.json) explicitly record `original_strict_comparison_passed: false` and `paired_random_draws: false`. The unchanged original comparison's seven tests also pass.

## First attempt and retained evidence

The first control `project-slate-rwkvt` succeeded, but a 20:44:10Z DK refresh changed Flowers from Doubtful to OUT and Cooper from OUT to IR during its run. The driver stopped before treatment, preserving the result. Table ETags did not change, so checking row contents caught real drift that metadata alone missed. A new control/treatment pair was run after exact provider reconciliation; no ambiguous mutation was retried.

Private raw captures/configurations and execution claims remain in:

- `/home/erich/projects/review-evidence/overnight-20260918/qb-projection-release-20260919/`
- `/home/erich/projects/review-evidence/overnight-20260918/qb-projection-release-20260919-pair2/`

No current-week outcomes were queried or decoded by this review. The archive includes forecast values and allowlisted input-only feature columns.

## Operational follow-through and rollback

The new gated batch is available for the next host build; the already-running D12800 build retains its earlier frozen inputs. Production acknowledged exact v4.3 host-tool hashes and owns installation plus a fresh final-book rehearsal when that build ends. Keep final Q/D risk flags visible; do not reinstate the unrequested blanket Q/D candidate ban. A complete eligibility decision propagated through generation and both banks remains a separate lab follow-up.

Rollback must restore the previous image **and run a new projection execution**, so the newest batch is restored too:

`us-central1-docker.pkg.dev/nfl-predictions-503414/nfl-dfs/nfl-dfs@sha256:f630fc8c88ed1625fa7873d959e0dcc217a55bd4d95b4e0edb9c1386fb3d5f5d`

Use the same canonical launcher lane, preserve other job settings and verify the fresh complete batch. Alternatively, record `QB_BACKUP_GATE=0` and re-execute to disable the policy. An image/config change without a new execution does not replace a published projection batch.
