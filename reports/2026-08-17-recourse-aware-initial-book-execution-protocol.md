# Recourse-aware initial-book execution protocol

Date frozen: 2026-08-17, before any cloud image, shard, score-free result,
aggregate report, realized outcome, or treatment effect existed.

Execution ID: `20260817-recourse-aware-initial-book-scorefree-v1`.

Scientific protocol: `reports/2026-08-17-recourse-aware-initial-book-scorefree-protocol.md`
with SHA-256
`0085b5f77b4e859982fc4f664161cdafe2bb6ec07ea0351fb618ddf58319c077`.

## Immutable inputs

The runner must validate and bind all of the following before it loads a slate:

- the scientific protocol and this execution protocol;
- passed CBWU-OI repair report SHA-256
  `556adeca6e0bf2855ad82296b1e708041a20446dc27e2c988c1d11e8c5bd4d33`;
- forensic manifest SHA-256
  `51edbe124846dc936ade71c4e5a9a07e252bcf6c7d7872b979715ccd1f6bab02`;
- the exact R0--R4 source panels
  `20260813-sis-asoe-treatment-r0-v1` through
  `20260813-sis-asoe-treatment-r4-v1`; and
- all five immutable player-world artifact URI/SHA receipts for the slate.

The only BigQuery fields admitted are the existing candidate identity, roster,
tag and score-artifact receipt fields plus the pre-lock player catalog fields
ID, name, position, team, opponent, game, salary, mean projection and exact
kickoff time. The SQL and emitted payload must not contain actual/final score,
actual ownership, historical selected membership/rank, contest rank, payout,
ROI, or an effect/result from another mechanism.

## Shard grid and resource envelope

- Run exactly 54 independent Sunday-main slate shards: seasons 2023--2025,
  Weeks 1--18.
- Each shard evaluates all five train-four/test-one folds and emits one
  create-only JSON object only after all five folds complete.
- The intended Cloud Run envelope is 4 CPU, 16 GiB memory, 4-hour task timeout,
  one task, parallelism one and `maxRetries=0`.
- A shard may print only identity, validation and fold-completion metadata while
  running. It must not print or upload a partial fold, tail count, treatment
  selection, effect or disposition.
- The aggregate job may run only after the strict harvester validates exactly
  54 final objects, 270 unique folds, 270 exact artifact receipts and a common
  immutable source/code/image identity.

The mechanism is queued behind strict terminal closure of the active ATLAS
repair5 family. It must not compete with that family for historical research
compute. This score-free family does not acquire the historical-outcome lease,
but it may not be used to bypass the one-heavy-experiment compute rule.

## Actual final-path canary

Only 2023 Week 1 may run initially. It must use the same immutable image,
entrypoint, resource envelope, source loader, five-fold evaluator, create-only
upload and strict validation code intended for the other 53 slates. A synthetic
or reduced-workload smoke is not sufficient.

The other 53 shards may be released only after the canary is terminal success
and a validator, without opening tail/effect fields, confirms:

1. the expected create-only object exists and its object generation is fixed;
2. all source, code, image, protocol and run identities match;
3. five unique R0--R4 fold records exist and every fold is mechanically valid;
4. five distinct artifact receipts exist and bind the expected R0--R4 panels;
5. the payload and serialized field names contain no forbidden outcome/effect
   field; and
6. no other shard object exists before the release marker is written.

The canary object is retained as the authoritative 2023 Week 1 shard and is not
rerun after release.

## Retry and failure policy

A substantive code, data, schema, identity, scientific, resource-exhaustion,
timeout or ambiguous failure is terminal for this execution ID. It requires a
new pre-result amendment and new run ID before any retry.

One unchanged external replacement is permitted only when Cloud Run reports a
literal platform failure before the container starts and the expected GCS
object provably does not exist. The replacement must use the same image digest,
arguments, environment, resources and destination. Both execution identities
must be retained in the attempt ledger. No other retry is allowed.

## Strict harvest and disclosure

The harvester validates all 54 final objects before importing the six-condition
gate from the scientific protocol. It writes one create-only aggregate report
and a source manifest. It must reject duplicates, missing slates/folds,
unexpected object generations, mismatched source receipts or any forbidden
field. It must never infer a missing shard from logs.

No score-free treatment result may be inspected or summarized before strict
harvest completes. The aggregate is outcome-free and cannot change production.
Only the frozen disposition may license the separately frozen historical
policy diagnostic described in the scientific protocol.
