# Exact-P corrected-identity source repair

Date: 2026-08-15 16:24 CDT  
Parent protocol: `20260815-exact-p-generator-constraint-census-v1`  
Evidence class: operational source repair for an outcome-viewed descriptive census

## Failure and scope

Execution `exact-p-generator-constraint-census-v1-kwqdb` failed before it
produced a census result. Its independent legality audit found `qb-stack` on a
roster read from repair4 layer P. No native-candidate membership, family
distance, loss-stage count or disposition was emitted, and the create-only
census target remains absent.

The failure exposed a source-identity error in the parent protocol and runner.
`final_forensic_20260814_oracle_rosters_repair4` contains the published loose
QB+1/no-bring-back P identities. The later immutable exact-stack addendum
recomputed P under the production QB+2/one-bring-back contract and verified its
scores, but its create-only result retained only the corrected scores and
structural summaries, not the corrected P roster IDs. The parent protocol
therefore names a corrected identity source that does not exist.

This is not a scientific result and does not permit substituting the loose P,
lowering the legality audit, or inferring a corrected roster from candidate
membership.

## Sole repair

Create one identity-only corrected-P artifact before rerunning the census:

1. Bind the same repair4 manifest
   `51edbe124846dc936ade71c4e5a9a07e252bcf6c7d7872b979715ccd1f6bab02`,
   scope `phase-s-cbwu-54`, 54 slate keys and the exact three repair4 source
   tables used by the exact-stack addendum.
2. Bind the immutable exact-stack result at generation
   `1786794534795445` and SHA-256
   `1d9e6b1f8d4e6174ae4aa717acf62fe657f0f3fbfd9271289a36b4a58664e7f3`.
3. Re-run only the deterministic corrected P solve on the repair4 candidate
   player support with the unchanged $49,000--$50,000 salary range, QB+2,
   one opponent bring-back, no same-team two-RB, no RB against DST, minimum
   two games and the existing stable tie-break.
4. Require all 54 corrected P scores to reproduce the immutable addendum to
   `1e-6`, require its registered exact-P tail counts to reproduce, and run the
   independent production-contract legality audit on every reconstructed
   roster.
5. Write exactly one create-only identity artifact containing only receipt
   metadata plus `season`, `week` and nine canonical player IDs per slate. It
   must not contain player scores, candidate scores, ranks, ownership,
   selection membership or payouts. Record explicitly that the identities are
   outcome-derived even though the persisted artifact is identity-only.

The create-only target is:

`gs://nfl-predictions-503414-raw/research/final-forensic-runs/20260814-final-preseason-forensic-v1/post-forensic-addenda/20260815-exact-p-corrected-identities-v1/result.json`

The materializer may read realized player outcomes only to reproduce the
already-published exact-stack oracle. It may not read native seed books,
candidate tags, candidate scores, selected membership or any generator-census
result. Its output cannot itself classify a generator loss or change
production.

## Census retry

Only after the identity artifact is strictly harvested and hash-pinned may the
parent census runner be repaired to read that identity-only object instead of
repair4 layer P. The repaired runner must:

- verify the artifact URI, generation, SHA-256, source manifest, exact-stack
  parent generation/SHA, 54 unique slate keys and 486 unique roster slots;
- construct an input frame containing only `season`, `week` and `players`;
- retain every original outcome/rank/ownership/payout denial, prelock check,
  candidate/CBWU reproduction check and frozen disposition threshold; and
- write to the unchanged, still-absent parent census target under a new
  operational execution identity.

No scientific parameter, candidate population, family definition, threshold
or consequence changes. If source materialization or exact reproduction
fails, the census remains invalid/inconclusive and no further retry is
licensed without a new recorded mechanical cause.

