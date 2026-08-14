# Multi-seed candidate/world exact-80 result

Date: 2026-08-14. Complete mechanically valid report:
`reports/multiseed-candidate-world-runs/20260813-multiseed-candidate-world-v1/report.json`.
The original computation succeeded but its legacy one-line JSON was truncated
by Cloud Logging. Transport-only execution
`analyze-multiseed-candidate-world-v1-9zf9b` reproduced the frozen computation
and emitted a complete chunked report. Report SHA-256 is
`a41d3427aa267ed9ab52753a898f14135caa9bd42c11c645d92eccffbb170239`.

## Frozen decisions

All books contain exactly 80 final lineups. Tail counts are in registered
`240/230/220/210/200/194/187` order.

| arm | candidates | worlds | tail counts | mean weekly max |
|---|---|---|---|---:|
| C0W0 | R0 | R0 10k | `0/0/0/3/6/10/12` | 174.5226 |
| C0WU | R0 | R0--R4 50k | `0/0/0/4/6/9/11` | 174.9041 |
| CUW0 | R0--R4 union | R0 10k | `0/1/1/6/8/11/21` | 179.3589 |
| CUWU | R0--R4 union | R0--R4 50k | `0/1/1/4/6/12/21` | 179.4733 |

The research factorial selects **CUW0**: CUW0 and CUWU tie at 230/220, then
CUW0 leads `6-4` at 210. CU's mean pool is 579.80 candidates versus 253.81 for
C0, so this is discovery evidence and not directly shippable. Against C0W0,
CUW0's mean gain is `+4.8363` with slate-clustered 95% interval
`[0.8972, 8.8152]`.

The clean fixed-candidate world comparison selects **C0WU** at 210 (`4-3`).
It changes about 14.33 of 80 selected rosters on average and raises mean weekly
maximum by `0.3815`, with diagnostic interval `[-0.9162, 1.8972]`.

Because a CU arm won, the preregistered fixed-budget confirmation binds:

| arm | mean candidates | tail counts | mean weekly max |
|---|---:|---|---:|
| CBW0 | 253.81 | `0/1/2/5/6/9/18` | 175.8244 |
| CBWU | 253.81 | `0/1/3/6/7/8/17` | 176.0630 |

At the selected WU setting, CBWU outranks C0WU first at 230 (`1-0`) and is the
frozen **final production mechanism arm**. Relative to C0WU it also adds three
220 weeks, two 210 weeks and one 200 week, while losing one at 194; mean weekly
maximum improves by `1.1589`. This preserves exactly 80 final entries and the
same total candidate budget while sourcing candidates from five searches and
selection evidence from five equal world blocks.

## Noise and limits

The five native books average only `17.12/80` pairwise roster overlap. Their
tail-count ranges are 1 at 230, 2 at 220/210/200/194, and 4 at 187. This is the
registered seed-noise floor for interpreting later work, not authority to
reopen prior decisions.

The `CBWU` result licenses the candidate/world mechanism specified by its
frozen protocol. Production integration must implement five score-blind
candidate seeds with the fixed total quota/fill law, five equal simulated
world blocks, fail closed when any block is absent, and still export exactly
80. It must retain the existing K=1 money-policy marginals, role/boom mix and
position calibration; it does not license the separate finite-K pass-tail
cache/schedules. Wiring and outcome-blind validation are the next step.
