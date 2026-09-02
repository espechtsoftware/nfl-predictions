# Opportunity-lineage v1 — production interface review

**Date:** 2026-09-02

**Scope:** interface compatibility only

**Disposition:** **GO for one shadow-only 084 release; NO-GO for an exact-production-settlement claim until the interface corrections below are made.**

No experiment, pipeline, scoring process, or Cloud Run execution needs to stop. The sidecar is useful now for natural-arm mechanics and selection diagnostics. Neo4j should remain a read-only projection of immutable artifacts.

The lab's focused opportunity-lineage suite passes (`21 passed`). The review below concerns what the contract proves, not whether its current code executes.

## Direct production answers

### Candidate-trace freeze point

For a future exact trace, freeze a separate create-once provider object **after generation, admission, and selection have completed, but before the outcome reader or any outcome-bearing branch opens**. The object must carry the complete candidate identities and selector decisions rather than being reconstructed later. For a live contest, it must also predate the authoritative slate-lock time.

The existing 084 artifact may be used as a `local-mechanics-shadow`. It must not be relabelled as exact pre-lock evidence after the fact. Current count-match reference membership and ranks remain explicitly unobserved.

### Ranks and selector marginal values

- `selected_rank` is safe for the current 084 natural arms because the frozen selector trace contains it.
- `actual_field_rank` and `counterfactual_field_rank` are safe only in settlement, after an exact complete DraftKings standings capture has been mapped through the validated production field bridge.
- `predicted_marginal_utility` must remain null for current 084. It may be included in a future trace only if the selector emits the value at each greedy step before outcomes, together with the objective/law identifier, units, and baseline.
- A distinct `submitted_entry_slot` is not presently evidenced by the filled DKEntries file. Either define it explicitly as a derived confirmation ordinal, or require an immutable upload/Entry History receipt. Do not represent prepared row order as an independently observed submission order.

## Flag 1 — conflicting identifiers or schema

### 1.1 Exact roster-hash settlement join is not yet compatible

The lab and production hashes are intentionally different:

- Lab 084: SHA-256 of comma-joined sorted lab player IDs (`nfl2/src/nfl2/kg/candidate_trace.py`).
- Production: SHA-256 of canonical JSON containing nine sorted production player IDs (`src/nfl_dfs/inference/generation_exposure.py`).
- Raw standings warehouse: a third, display-name-based digest. It must never be joined directly to either of the above.

The current opportunity candidate retains only the lab digest. A digest is non-invertible, so production cannot map it through the player-identity bridge or recompute the production digest.

**Required correction:** freeze either:

1. the nine sorted source player IDs, their namespace, and the exact generation-pinned identity-bridge object; or
2. a separate create-once roster-members bridge keyed by the lab digest, containing the source roster and recomputed production identity.

Every join must compare a complete identity tuple: hash algorithm, canonicalization, player-ID namespace, and digest. Digest-string equality alone is invalid.

### 1.2 Score units are inconsistent

The sidecar accepts floating `realized_score` and `winner_score`; production's exact authority uses integer micro-points (`realized_score_micro`).

**Required correction:** use integer `realized_score_micro` and `winner_score_micro` throughout exact settlement, or add an explicit scale/unit plus a lossless conversion rule. Do not round-trip exact authority through binary floats.

### 1.3 “Observed in field” is not the same as “our submitted entry”

Production's existing field bridge marks a roster as entered when *any* field entry matches it. That may be another participant's duplicate roster. It does not establish that production submitted that roster or earned that payout.

**Required correction:** keep these claims separate:

- `roster_observed_in_field` and matching field Entry IDs; and
- `our_submission_confirmed`, which requires the exact prepared DraftKings Entry ID to match the settled standings Entry ID and roster.

Only the second can attribute an actual payout to the production book.

### 1.4 Exact research-book cardinality is under-specified

The generic validator currently permits fewer selected rows than `research_book_size` so long as ranks are contiguous and do not exceed it.

**Required correction:** if `research_book_size` means actual K, require exactly K selected decisions. Otherwise rename it to `research_book_capacity`. This does not invalidate current 084, whose experiment-specific mechanics produce K80.

### 1.5 Version identity is not yet durable

At review time the opportunity-lineage schema, implementation, tests, and interface documents are untracked in the lab worktree. They therefore lack an immutable source commit identity.

**Required correction:** commit and freeze the reviewed interface before any cross-repository adapter claims compatibility. This is not a reason to interrupt 084.

## Flag 2 — fields that cannot yet be emitted safely

### 2.1 Contest facts are not derived from or content-bound to their source objects

The settlement CLI accepts an arbitrary local `contest-facts.json`. The validator requires source-object role names, but does not reopen those objects and prove that their bytes produced the emitted entry IDs, ranks, payouts, field membership, or winner score.

**Required correction:** the production adapter should generation-exact reopen the source objects, validate them with the production parsers, derive the contest facts, and bind the derived artifact's semantic/content digest to those exact source identities. Prefer adapting production's already validated field-bridge artifact over accepting free-form contest facts.

### 2.2 Winner adjudication is only shape-checked

The reduced winner object is not passed through production's `validate_adjudication_receipt`; its receipt hash/object, contest identity, and official score are not proven to match the sidecar claim.

**Required correction:** reopen the full receipt bytes, run the registry-v2 validator against the frozen ledger and policy, and require receipt contest ID and official score to equal the settlement contest fields. Until then, emit `observed-unadjudicated` or `unavailable`.

### 2.3 Prepared-entry facts require a durable filled artifact

The paid-book exporter validates the fill, Entry IDs, row order, legality, and exact book, but its normal application endpoint returns bytes rather than durably archiving the filled DKEntries file and row-level Entry-ID-to-candidate mapping.

**Required correction:** add an off-critical-path create-once archive of the exact filled bytes and receipt before outcomes. Without it, leave prepared/submitted deployment unobserved.

### 2.4 `contest_entry_limit` is not a paid-fill fact

The filled DKEntries receipt proves the targeted rows, not the contest's maximum entry limit.

**Required correction:** source the limit from the exact pre-lock `dk-contest-manifest/v2` contest metadata object, and bind that object into preparation authority. Otherwise omit the field.

### 2.5 Arbitrary feature objects weaken the no-outcome claim

The `beliefs` and `features` objects are open-ended and outcome rejection is denylist-based. A new outcome field with an unrecognized name could pass.

**Required correction:** exact provider traces need a versioned allowlist of permitted pre-lock fields. The current known mechanics adapter is safe for shadow use.

## Flag 3 — pre-lock/settlement boundary violations

The schema records artifact times but does not bind an authoritative slate-lock time or contest manifest. Settlement compares provider creation times to a caller-supplied `outcome_branch_opened_at_utc`; that scalar is not itself an exact access receipt. Consequently, the current generic contract could label a post-lock artifact exact-prelock or move the claimed outcome-opening time.

**Required correction:**

1. bind the exact contest/slate manifest and `slate_lock_at` to the pre-lock package;
2. require candidate trace and filled-entry provider objects to predate that lock for live use;
3. derive or content-bind `outcome_branch_opened_at_utc` to the canonical outcome-reader/access receipt; and
4. require settlement recording to occur at or after that access marker.

For historical experiments, separately record the feature `as_of`/point-in-time boundary; artifact creation time alone does not prove historical feature availability.

This limitation does **not** block the explicitly labelled current 084 shadow.

## Flag 4 — simpler authoritative production sources

| Requested fact | Authoritative source | Production interpretation |
|---|---|---|
| Prepared entries | Create-once filled DKEntries CSV plus `paid_classic_book_v2` export receipt | Exact pre-lock Entry ID, row, roster, and source-book mapping. The returned bytes must first be durably archived. |
| Contest entry limit and lock | Pre-lock `dk-contest-manifest/v2` | Do not infer either value from DKEntries rows. |
| Actual field entries | Create-once, complete post-settlement DraftKings standings CSV and capture receipt | Exact Entry ID plus roster. Raw object is authority; warehouse rows are a derived query surface. |
| Final points and ranks | Same complete standings object, validated by the production full-field parser | Competition ranks should be reproduced from exact integer micro-scores. |
| Payouts | Same complete standings object plus validated payout reconciliation | Attribute payout to production only through the prepared Entry ID; roster-only matches are field observations. |
| Winning score for a newly captured contest | Rank-1 points from the same complete standings object | Registry v2 is the acceptance/correction layer, not an independent unsourced number. |
| Historical adjudicated winner | Accepted winner-registry-v2 receipt and its exact evidence objects | Until a receipt is accepted, use `observed-unadjudicated` or `unavailable`. |
| Observed generated/admitted population | Complete provider-frozen generator trace for the exact run/slate/bank/arm | This is the useful near-term lineage universe. |
| Literal full DK-legal lineup universe | No current authoritative artifact | A future exhaustive enumerator must bind salary slate, roster rules, and legality-contract version. Do not describe the observed 084 pool as the full legal universe. |

## Minimal acceptance gate for exact production settlement

An exact adapter is ready when it proves all of the following without changing the live selection path:

1. source roster membership can be mapped and target hashes recomputed under an immutable identity bridge;
2. scores use exact, explicit units;
3. every contest fact is derived from and bound to the exact provider bytes named as its authority;
4. prepared Entry IDs are frozen before outcomes and field confirmation joins by Entry ID plus roster;
5. contest lock/limit come from the frozen manifest and outcome opening comes from an exact access marker; and
6. an adjudicated winner is accepted by the full production registry-v2 validator.

Until then, run the requested first use as a clearly labelled shadow. That gives useful generation/admission/selection-loss intelligence now without making claims the current evidence cannot support.
