# ATLAS CBC child-process and cgroup resource diagnostic result

Date harvested: 2026-08-16
Protocol: `20260816-atlas-cbc-resource-diagnostic-v1`
Outcome access: none
Mechanical disposition: `sigkill-without-cgroup-oom-confirmation`
Frozen resource decision: `resource-pressure-supported-use-16GiB`

## Strict harvest

All three immutable executions and their exact image/source/protocol bindings,
resource envelopes, terminal receipts, artifacts and score firewall passed the
strict finisher. Summary SHA-256:
`c467332d78b09589680e9354ef9454d6c3f14a0193d4db15b559dde55af1472a`.
Completion receipt SHA-256:
`2412fa80e01e98633ded7224f544f2b5f19ff47c04971d8fc6e99d0413777ff1`.

| cell | status | child | peak bytes | peak / 4 GiB |
|---|---|---:|---:|---:|
| 2024 Week 7 | CBC failure | `-9` / `SIGKILL` | 3,618,242,560 | 84.24% |
| 2024 Week 15 | R0 complete | `0` | 3,526,561,792 | 82.11% |
| 2024 Week 16 | CBC failure | `-9` / `SIGKILL` | 3,623,886,848 | 84.38% |

Every cgroup read was available. Cloud Run exposed the cgroup-v1 compatibility
path, whose event field is `failcnt`; it did not expose an `oom_kill` counter.
The recorded OOM-kill deltas are therefore zero and do **not** directly prove
an OOM kill. The two failures are exact SIGKILL evidence.

## Frozen interpretation

The mechanical summary correctly uses the protocol's higher-precedence label
`sigkill-without-cgroup-oom-confirmation`: SIGKILL without a positive
`oom_kill` increment is not definitive OOM proof.

That label does not negate the separately frozen pressure boundary. The
protocol states that a successful isolated R0 run with peak/cap at least 0.80
remains resource-pressure evidence. Week 15 completed but peaked at 0.8211,
and the two SIGKILL cells peaked still higher at approximately 0.843. Resource
pressure is therefore supported under the prospectively frozen rule even
though the narrower cause `cgroup OOM kill` remains unconfirmed.

The native diagnostic is consistent: the identical Week 16 MPS parses with
zero errors, enters branch-and-bound, and its 4,096-byte log ends abruptly
mid-pass. No deterministic parser/model/numerical defect was identified.

## Decision

The resource protocol's repair branch is licensed: repair3 should preserve the
old-binary repair2 image, model, sources, solver options and scientific logic,
change only the Cloud Run envelope to four CPUs and 16 GiB, use new run/job/
execution/object identities, and rerun all 54 cells. The independent fixed-cell
16-GiB preflight remains the go/no-go check for that envelope before launching
the full grid.

No ATLAS effect, historical score conclusion or production change is licensed
by this resource diagnostic itself.

