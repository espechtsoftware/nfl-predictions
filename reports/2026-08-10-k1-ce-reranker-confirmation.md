# K=1 CE true-80 fixed-pool reranker confirmation

Status: complete; the valid structure-only reranker failed the frozen
tail-first and negative-control gates and is not adopted.

## Why this arm is eligible

The accepted panel `20260809-e80-k1-ce12-c616390` has six recoverable 194+
pool weeks across four seasons and four recoverable 200+ weeks. Canonical
acceptance therefore passes the original decision gate for one low-capacity
reranker evaluation. Candidate generation is now materially better; this arm
asks only whether pre-lock structure can improve which 80 candidates are
submitted from that fixed pool.

The earlier reranker result used a superseded 40-entry/K=3 universe. Its
structure-only arm was the sole directional lead, while adding disagreement
and ownership features degraded results. This confirmation therefore has one
adoptable arm—structure/provenance only—and does not reopen a feature search.

## Frozen source, model, and serving contract

- Source: promoted 107-slate panel `20260809-e80-k1-ce12-c616390`; exactly 80
  entries, line 194, and its immutable score artifacts.
- Candidate pool is fixed. No generation, projection, world, salary, stack,
  ownership, CE, or candidate-count setting changes. Pool oracle must be
  identical by construction.
- Target: `actual_score - sim_mean` on training candidates only.
- Model: `StandardScaler` plus ridge regression, `alpha=10`, candidate shifts
  clipped to `[-15,+15]`. These are the original preregistered settings; no
  hyperparameter is chosen from this panel.
- Each slate receives equal total training weight, rescaled to mean candidate
  weight one. Training for season S uses only seasons `< S`. The first season,
  2019, is an explicit unchanged-baseline cold start.
- Features: simulated mean/SD/q50/q90/q99/p-line, salary/leftover, complete
  generator tags, stack-mate count, bring-back count, max players from a game,
  and number of games. All are pre-lock and immutable. No ownership,
  market/model disagreement, player identity, team identity, actual score, or
  future season enters the serve matrix.
- Integration: add the predicted residual shift to every simulated total for
  that candidate, recompute the 194 clear mask/probability/mean, then call the
  unchanged 80-entry greedy coverage selector.
- Negative control: deterministically permute the same predicted shifts within
  each served slate using seed `314159 + season*100 + week`, then rerun the
  same selector.

## Frozen gate

The arm passes only if all mechanism checks are valid and:

- selected weekly maxima gain at least two 200+ weeks versus the accepted CE
  source;
- selected 210+ weeks do not worsen;
- the fixed-pool oracle at 200+ does not worsen;
- the primary book lexicographically beats the shuffled control on 200+, then
  210+, 220+, 194+, and finally mean weekly maximum.

Report the complete 187/194/200/210/220/230/240 grid, mean, median, training
manifest, selected-slot movement, and season attribution. Season signs and
mean are diagnostics under the operator's tail-first utility, not vetoes.

A failure closes this structure-only reranker on the known historical panel.
Do not tune alpha, shift cap, line, feature set, weighting, negative-control
seed, or add the previously negative ownership/disagreement arms after seeing
the result.

## Outcome

Full Cloud Build `44264eea-f58b-419a-a9b6-a77f13d60dff` passed 707 tests with
2 skipped and produced immutable digest
`sha256:09a7ed659928afef1e720b40fc55e2aec8ca643e706c720dee21047aa5d0dd9f`.
Execution `evaluate-k1-ce-reranker-vhg99` completed with zero mechanism
failures and returned `reject`:

| Weekly maximum metric | Accepted CE | Primary A1 | Shuffled control |
|---|---:|---:|---:|
| >=187 | 40 | 42 | 39 |
| >=194 | 26 | 26 | 26 |
| >=200 | 18 | 18 | 19 |
| >=210 | 11 | 12 | 11 |
| >=220 | 5 | 5 | 5 |
| >=230 | 2 | 2 | 2 |
| >=240 | 1 | 1 | 1 |
| Mean | 181.12 | 181.40 | 180.57 |
| Median | 178.64 | 179.20 | 177.00 |

The evaluator verified all 90 served-season artifacts, retained an unchanged
2019 cold start, served every season only from earlier-season training, kept
all shifts within the frozen cap, and moved 1,449 selected slots. Candidate
pool and oracle metrics are identical by construction.

The primary model adds no 200+ week (required +2) and loses the preregistered
lexicographic comparison to the shuffled control, which adds one 200+ week by
chance. Its extra 210+ week and modest mean/median gains are diagnostics, not
permission to weaken the gate. Close this reranker family on the known panel;
do not try A2/A3, another alpha/cap, or a different shuffle seed.
