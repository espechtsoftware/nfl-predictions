# B1 generated-corpus tail model — frozen historical result

Date: 2026-08-20 CDT / 2026-08-21 UTC

Run: `20260820-b1-corpus-tail-model-v1`

Execution: `atlas-minimal-c-s2023-w1-v1-sm64k`

Disposition: `historical-gates-fail-closed`

## Result

The one frozen B1 historical challenger did not pass. The fixed leave-one-season-out
L2 logistic tail score ranked `actual_score >= 200` better than the registered
`p_line` comparator, but it did not improve the equal-budget exact-80 book and
was slightly worse than fold prevalence on Brier score.

| Registered quantity | Control | Challenger | Gate |
| --- | ---: | ---: | --- |
| Mean weekly maximum | 173.6556 | 171.3685 | fail |
| Weeks >= 194 | 12 | 12 | pass / protected |
| Weeks >= 200 | 8 | 8 | fail / no improvement |
| Weeks >= 210 | 1 | 1 | pass / noninferior |
| Weeks >= 220 | 1 | 1 | diagnostic |

Candidate and entry budgets were exactly equal on all 54 slates. The LOSO
tail model's average precision was `0.00240972` at 200 and `0.00079093` at
210, versus `p_line` at `0.00196699` and `0.00073343`. Its 200-point Brier
score was `0.001141619`, slightly worse than the registered fold-prevalence
comparator at `0.001141396`. The walk-forward companion showed the same
calibration failure (`0.000966731` versus `0.000965206`).

This control is specifically the stored ranks 0--79 from the canonical
`20260815-atlas-money-worlds-r0-v1` candidate panel, with the challenger
restricted to that same roughly 250-roster weekly pool. It is not the 176.06
money-book baseline or the 178.57 A3/A7 comparator; those use different panel,
slate, or book definitions and their means must not be compared as if they
were the B1 control.

The exact historical gates were:

- pass: equal candidate/entry budgets; 194 protection; 210 noninferiority;
  model PR above `p_line` and prevalence at 200; model PR above prevalence at
  210;
- fail: positive Brier skill; improved mean weekly maximum; improved 200+
  count.

Therefore no portable model was published. Historical retuning, a 2026 shadow,
shadow writes, and production are all literal `false`. This run is not eligible
for a retry, threshold search, feature sweep, or relaxed gate.

## Execution and evidence

Cloud Run completed strict-success at `2026-08-21T00:17:24.845961Z` with one
successful task and zero failures, cancellations, or retries. The registered
watcher generation-pinned and independently replayed the attempt and report,
then closed only the exact active outcome-lease generation.

- attempt object: generation `1787270838253869`, 1,218 bytes, SHA-256
  `1a9cbe9761b49393c5b2b27095970895b46638407798420e765362e264621b54`;
- report object: generation `1787271440125485`, 31,606 bytes, SHA-256
  `2deeaa732c5b58798237b46c32f8fd99e40a0aa7b03ff4ee6c8e89b355e925b4`;
- release-intent object: generation `1787271474897332`, SHA-256
  `725e3f0598c42d64ef57e9a3d144f557e74a6a6992f50d3aaef3b8bd8f07a39c`;
- closed lease generation: `1787270618157974`;
- `finish.sha256`: SHA-256
  `b1cf14e9eec3a1fc2a90a15f5ece48e0d1855a3e1561ff3d7d25f62648e25d96`;
- `lease-release.sha256`: SHA-256
  `a46cdff9c52a91a6cf990e242c159c14594473de9a55564bdbe0b14834052fad`.

An idempotent second `finish` and `close-lease` replay passed, all ledger
targets passed `sha256sum -c`, and the global historical-outcome lease was
verified absent.

## Scientific interpretation

The retained 127,778-roster generated corpus remains valuable as a description
of where the system has produced high scores. This test shows that a simple
linear tail classifier over the currently frozen pre-lock roster summaries is
not sufficient to choose a better 80-book from the existing roughly 250-roster
weekly pool. It does not show that the corpus is useless, and it does not
license fitting another model to the same opened outcomes.

The next adoption attempt must obtain genuinely new information or candidate
support: prospectively collected full-field/duplication data, richer pre-lock
world and allocation signals, or a separately frozen candidate-generation
mechanism with materially more ceiling than the current union. It must not be
presented as a repair of this one-shot B1 model.
