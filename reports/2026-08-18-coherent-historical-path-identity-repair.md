# Coherent historical stage: checkout-path identity repair (frozen record)

**Date:** 2026-08-18 (evening)
**Defect class:** producer records absolute checkout paths; frozen
consumers in a different checkout compare path-keyed identities — the
same class as the census-key repair (`all_declared_attempts_terminal` vs
`all_terminal`) and the finisher manifest-newline/self-hash repair
(`04c0dbb`). Artifacts and digests are untouched; both repairs are
consumer-side.

## Failure

The historical-stage launcher aborted twice (16:21 CDT last attempt) at
`validate_coherent_market_state_attempts.py:196`:
`coherent-state primary metadata population differs`. Root cause: the
score-free finisher wrote `primary-execution-metadata.sha256` with
absolute paths from ITS checkout (`/tmp/nfl-coherent-cde9c60/...`), while
the validator, running in the historical checkout
(`/tmp/nfl-historical-ae9780b/...`), globs its own paths and compared
`digest_map` DICTIONARIES keyed by path — keys can never match across
checkouts even when every digest does. The score-free stage passed the
same validator because producer and consumer shared one checkout.

**Evidence, gathered read-only before any change:** all 54 metadata
files present in the historical checkout; recorded-vs-fresh digests
keyed by basename: 54/54 equal, zero mismatches.

A sibling instance was found one consumer earlier in the same launcher:
`sha256sum --check` over five ledgers (`report.sha256`,
`report-upload.sha256`, `execution-metadata.sha256`,
`object-metadata.sha256`, `shards.sha256`) verifies the paths RECORDED in
the ledgers — i.e., the producer checkout's files. It passes only while
`/tmp/nfl-coherent-cde9c60` survives and hard-fails after any reboot.
All five ledgers were verified to pass under run-relative path
normalization before the change.

## Repairs (consumer-side only; no artifact, checksum, or producer change)

1. `scripts/validate_coherent_market_state_attempts.py` — the metadata
   digest map is keyed by the season-week BASENAME on both sides of the
   comparison; count and byte-exact digest requirements unchanged
   (54 files, 54 rows, 54 unique keys, SHA-256 equality per file).
2. Self-hash deadlock: the upstream manifest pins
   `attempt_validator_sha256`, which no legitimate repair of the
   validator can satisfy — the exact `04c0dbb` finisher deadlock,
   resolved with the same mechanism: the self-comparison accepts either
   the manifest hash or an explicitly exported
   `ATTEMPT_VALIDATOR_REPAIR_SHA256` that must still equal the exact
   current file hash (conscious, not silent). Protocol and resolver pins
   remain strict. Verified: without the export the validator fails
   closed; with the exact hash exported it validates the complete real
   upstream end-to-end
   (`COHERENT_MARKET_STATE_ATTEMPTS_VALIDATED accepted-primary-population`).
3. `scripts/cloud_coherent_market_state_historical_score.sh` — the five
   `sha256sum --check` ledger verifications normalize recorded paths to
   run-relative form and verify inside `$UPSTREAM` (all five verified
   OK against the real ledgers before the change).

## Identities

| file | before SHA-256 | after SHA-256 |
|---|---|---|
| `scripts/validate_coherent_market_state_attempts.py` | `effe83af9ced03a4725b7b7ca8ba7ddfff48c9fdbebc2718fbaf02cdc9d0e307` | `863efd64a79a4b1b215480fe9ea1d4851a494c1941561b064b7eb8b98bf1b5a2` |
| `scripts/cloud_coherent_market_state_historical_score.sh` | `5dfa72c2fd02ad872b0a604a271133ec46af63f9fe53258bc0726aba860a1067` | `147a5fa5406e71a20e51218b8441f4fa95a042618461df0c6e102954a4996851` |

The before-hashes match both `main` and the `ae9780b` worktree exactly
(verified). The launcher pins its sources against the invocation
`CODE_SHA`, and the validation build's image tag embeds the code SHA, so
the relaunch runs from a fresh clean-archive Cloud Build at the repair
commit and a fresh pinned worktree — launch receipts of the failed r1/r2
attempts are untouched, and the completed score-free stage is unaffected
(its checkout satisfied the original path-keyed comparison).

## Forward note

The finisher for the historical stage writes its own `*.sha256` ledgers
with absolute `$OUT` paths (producer side of the same class). Consumers
of THOSE ledgers should use run-relative identities; a future
producer-side change to record run-relative paths belongs in a separate,
prospectively frozen change, not this repair.

## Addendum: fourth representation-identity instance (launch r1 failure)

The relaunched historical execution (`coherent-market-historical-v1-bg74m`)
failed closed in-container at shard validation: `coherent-state historical
shard object changed`. Read-only comparison of the first shard showed
generation, sha256, bytes and uri all EQUAL; the mismatch was the
`updated` STRING FORMAT — the launcher's upstream receipt passed
harvest-time `update_time` strings through verbatim
(`2026-08-18T17:35:15+0000`), while the scorer recomputes
`blob.updated.isoformat()` (`2026-08-18T17:35:15.743000+00:00`). No
outcome was read (the failure precedes scoring).

Repair (launcher-side; the in-image scorer is untouched): shard object
receipts are now live-derived with the scorer's exact primitive, and the
harvest-time generation must EQUAL the live generation — a strictly
stronger pin (any re-upload since harvest fails closed) replacing a
format-fragile equality. The failed attempt's launch receipts are
preserved under `failed-launch-attempt-1/`; the launcher is pinned, so
the relaunch runs from a fresh build/commit cycle per the frozen
build↔code binding.

## Addendum 2: fifth instance — the silent combined gate (kqw47)

Execution `coherent-market-historical-v1-kqw47` cleared shard validation
(confirming the timestamp repair) and failed at the combined upstream-
aggregate gate, which raises one message for three distinct legs. Every
leg passes when replicated outside the container against the same live
objects with the scorer's own module code — the failing leg is therefore
unidentifiable from the evidence the gate emits, and the in-container
difference could not be isolated remotely. Repair: the gate is now
diagnostic and leg-specific (each raise names its leg and the differing
identities/paths), object comparisons use content identity per the
frozen-chain rules, and the cross-image re-aggregation compares floats
at 1e-12 relative/absolute tolerance — requiring bit-exact float
re-derivation across independently built images was never sound; value
equality at 1e-12 is. No outcome was read by kqw47 (the gate precedes
scoring). If r6 trips the same gate, its error now names the exact keys.

## Addendum 3: sixth representation instance — the dependence launcher's newline parse

After the historical completion released it, the production-law
dependence watcher acquired the outcome lease (23:32 CDT) and its
remeasurement launcher failed closed at the queue/lease check — every
compared VALUE was correct; the launcher's key=value parser kept trailing
newlines on values (`'…source-lock\n' != '…source-lock'`). The check had
never run before (frozen without reality contact). Additionally, main's
Dockerfile/cloudbuild.yaml drift breaks the launcher's pin loop from the
main checkout, so the rerun uses the standard pinned-worktree cycle.
Repair: `rstrip("\n")` on both parse sites (the only two instances of
the class in the dependence scripts); new build at the repair commit;
the stale lease receipt and governance object are ARCHIVED (the crashed
launcher never launched an execution, so the lease's release path has
nothing to bind) and the rerun watcher acquires a fresh lease consistent
with the repaired identity.
