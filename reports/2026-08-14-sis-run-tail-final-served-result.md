# SIS RB opponent run-tail final-served result

## Disposition

`tabpfn-sis-rb-runtail-final-served-fails`

Cloud Run execution `tabpfn-sis-rb-runtail-final-served-v1-prrtg` completed
successfully in 15m41.11s. The strict harvester produced immutable report
`reports/tabpfn-sis-rb-runtail-runs/20260814-tabpfn-sis-rb-runtail-final-served-v1/report.json`
with SHA-256
`bd21734e655e18e758ace4874d6c7eca2bda12fcd39fcab6d91025ff6dd29caa`.
This is a valid score-free scientific failure, not an execution or cache
failure.

## Frozen gate

The active-RB treatment made both frozen extreme-quantile proper scores worse:

| metric | control | treatment | treatment/control |
|---|---:|---:|---:|
| q95 pinball | 0.748047 | 0.750678 | 1.003517 |
| q99 pinball | 0.230791 | 0.232606 | 1.007866 |
| equal q95/q99 mean ratio | — | — | **1.005691** |

The registered gate required the equal q95/q99 mean ratio to be strictly below
1.0. It was 1.005691, so that gate is false. Mechanical marginal preservation
passed: maximum float64 mean drift was `7.1054e-15` in both arms, below the
`1e-10` ceiling.

Supporting proper scores agree with the rejection. Treatment-minus-control
CRPS was `+0.004768` with whole-slate 95% CI `[+0.001388, +0.008147]`; q99
pinball was `+0.001815` with CI `[+0.000016, +0.003615]`. Point absolute error
did improve slightly (`-0.005170`, CI `[-0.010159, -0.000182]`), but point MAE
was explicitly secondary to the q95/q99 tail gate and cannot license the arm.

## Consequence

The preregistered five-seed exact-80 control/treatment comparison expires
without launching any lineup cells. The successful pre-result full-test image
build `0a149a8b-f1d8-4bec-b496-42fbb2f7b007` and its immutable digest are retained
as validation evidence only. No production cache or served schedule changes.
The SIS run-tail marginal mechanism is closed on this historical panel; its
source features remain available for future genuinely distinct mechanisms.
