# PREREG-074 R7 tail-regime read

Date: 2026-09-08 America/Chicago (read completed 2026-09-09 UTC)

## Disposition

`NO_NOMINATION`; `promotion: NONE`.

Deterministic tail-regime medoid scheduling (`SCHED_MEDOID_V1`) did not improve
the frozen K80 expected-maximum proxy relative to total-ordered scheduling
(`SCHED_TOTAL_V1`). This is not a new production baseline.

## Bound evidence

- Run: `102b740r7-20260909T023807Z`
- Source: `5aecdf0f1979133985a174da926159aef8178b39`
- Generation execution: `lab-run-6rxqk`, terminal 36/0/0/0
- Replay execution: `lab-run-7msxb`, terminal 36/0/0/0
- Seal:
  `seals/PREREG-074/102b740r7-20260909T023807Z.json|1788924568418671|30025|1dbeb6b2979ea64ebbae810ed128abec3c46ae6dfcf1b320fd83b4d6c0836343`
- Pins:
  `pins/PREREG-074/102b740r7-20260909T023807Z.json|1788924666481456|701|8f4b5a08824228ad99702557bcc766a198c2c095e12aac1badc42f4465199140`
- Release:
  `releases/PREREG-074/102b740r7-20260909T023807Z.json|1788924748051521|568|79313ede33c388e0b7d389156db0eb27a0f34c14a44096c237e58dc2e6568374`
- Reader SHA-256:
  `9e2eeb1d0ea3068eb7fa510dad18b29bb7da3a0fe433156639e592c47d972ea4`

## Frozen read

Primary and fixed-count reference were identical:

- metric: `k80_natural.wemax_proxy.K80 (fixed-work)`
- delta: `-0.005507943358211698`
- interval: `[-0.024396807824810393, 0.013380921108386996]`
- wins/losses/ties: `13 / 19 / 4`, 36 slates
- 2023 delta: `-0.02439680782481039`
- 2024 delta: `+0.013380921108386996`

Realized pool-oracle mean:

- `SCHED_TOTAL_V1`: `188.78833333333336`
- `SCHED_MEDOID_V1`: `188.05666666666667`

Threshold coverage:

| Surface | Schedule | >=194 | >=200 | >=210 | >=220 | >=230 |
|---|---|---:|---:|---:|---:|---:|
| Pool oracle | total | 12 | 9 | 3 | 1 | 0 |
| Pool oracle | medoid | 12 | 9 | 2 | 1 | 0 |
| Natural K80 | total | 6 | 4 | 3 | 1 | 0 |
| Natural K80 | medoid | 4 | 3 | 2 | 1 | 0 |
| Fixed-count K80 | total | 6 | 4 | 3 | 1 | 0 |
| Fixed-count K80 | medoid | 4 | 3 | 2 | 1 | 0 |

All first four nomination conditions were false; only the no-loss condition at
the 220/230 oracle thresholds was true. The evidence therefore rejects this
specific medoid scheduling arm for nomination. It does not reject other
generation or retrieval changes, especially PREREG-076's fresh-judge
retrieval crossing.

## Operational note

The first reader attempt was locally refused by production's 4 GiB virtual
memory cap after opening the released read; it emitted no score output and
changed no repository state. The same exact pinned reader completed under an
8 GiB virtual cap, with observed RSS below 1 GiB and ample host memory. This
was an execution-envelope correction, not a scientific rerun or changed read.
