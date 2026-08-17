# Impact/equivalence certificate protocol

Date frozen: 2026-08-17, before any certificate output exists.

## Purpose and boundary

This protocol implements the already accepted recommendation in
`2026-08-15-independent-tail-scoring-reconciliation-and-queue.md`: an upstream
change should force revalidation only when it can change the exact downstream
treatment/control contrast. The burden of proof remains on transfer.

The certificate is governance-only and outcome-free. It cannot adopt, reject,
rank or score a mechanism; waive a prospectively required test; change the
money policy or UI; or treat semantic similarity as equivalence. A positive
certificate may only establish that an already valid prior verdict need not be
recomputed because every object that verdict reads is byte-identical under the
same population, treatment, control, gate and terminal context.

## Registered stages and channels

Every context declares one stage:

- `player_marginal`
- `rank_dependence`
- `candidate_generation`
- `portfolio_selection`
- `objective_contest`

The only registered impact channels are:

- `player_marginals`
- `rank_dependence`
- `candidate_membership`
- `candidate_order`
- `world_masks`
- `selected_identities`
- `objective_contest`

The conservative propagation law is fixed before implementation:

| changed channel | downstream channels potentially affected |
|---|---|
| player marginals | all seven |
| rank/dependence | rank/dependence, candidate membership/order, world masks, selected identities, objective/contest |
| candidate membership | candidate membership/order, world masks, selected identities, objective/contest |
| candidate order | candidate order, selected identities, objective/contest |
| world masks | world masks, selected identities, objective/contest |
| selected identities | selected identities, objective/contest |
| objective/contest | objective/contest |

This impact closure is diagnostic. Disjoint declared impact is never enough to
earn transfer without the byte-equivalence proof below.

## Context manifest

Both the prior and proposed contexts must provide a canonical JSON manifest
with:

1. version `impact-equivalence-context-v1`;
2. the same nonempty `mechanism_id`;
3. one registered `stage`;
4. `contains_outcome_values=false` and
   `candidate_or_lineup_scores_read=false`;
5. five 64-character SHA-256 semantic identities:
   `terminal_context_sha256`, `population_sha256`, `control_sha256`,
   `treatment_sha256` and `metric_gate_sha256`;
6. a sorted, unique, nonempty `required_channels` list; and
7. `channels`, mapping channel names to nonempty receipt lists.

Each receipt contains exactly `logical_id`, `role`, `sha256` and `bytes`.
`role` is one of `shared`, `control` or `treatment`; `sha256` is a full digest;
`bytes` is positive; and `(logical_id, role)` is unique within a channel.
Receipt ordering has no meaning and is canonicalized. Every required channel
must exist and be nonempty. Extra registered channels are permitted only as
diagnostic context.

The manifest contains hashes and provenance identities, never player outcomes,
lineup scores, ranks, ownership, payouts or treatment effects. The producer of
a context manifest is responsible for binding its receipts to immutable source
objects; this certificate does not trust a manually asserted prose claim in
place of a receipt.

## Transfer decision

`transfer-equivalent-no-revalidation` requires all of the following:

1. both manifests are valid and name the same mechanism;
2. stage and required-channel sets are identical;
3. all five semantic identities are identical; and
4. the complete canonical receipt list is identical in every required channel.

Any failed condition yields `revalidation-required`. Differences confined to
an optional channel are disclosed but do not defeat transfer if every required
channel and semantic identity is exact. Missing receipts, unknown channels,
malformed hashes, duplicate identities or outcome-value flags fail closed as
invalid input rather than producing a certificate.

The output records canonical hashes of both manifests, every identity/channel
comparison, changed and propagated-impact channels, and these immutable
consequences:

- `uses_realized_outcomes=false`
- `scientific_verdict_issued=false`
- `production_change_licensed=false`

The output itself must be create-only. A certificate never makes an invalid or
prospective-only verdict transferable; it can only prevent unnecessary
recomputation of a verdict that was independently valid in its original
context.
