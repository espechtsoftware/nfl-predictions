# ATLAS repair4 terminal census result

Date: 2026-08-16
Run ID: `20260816-atlas-matched-diversity-mvp-v1-repair4`

## Disposition

Repair4 is a terminal mechanical non-result. All 54 exact execution identities
are terminal failed and the repair4 output prefix contains zero objects. No
score-free ATLAS effect, candidate result or historical score exists for this
run, and historical scoring is not licensed.

No shard or effect field was opened during the census.

## Terminal census

- 54 terminal executions;
- 0 succeeded;
- 54 failed;
- 47 explicit operator-cancellation states after the grid had become
  irrecoverably invalid;
- 1 natural configured-memory-limit failure: 2023 Week 8 execution
  `atlas-md-s2023-w8-r4-6rn7r`; and
- 6 terminal `Internal error running task` states.

The cost-control cancellations were frozen only after the natural Week 8
failure made repair4's all-54-success contract permanently unattainable. They
released capacity for the separately frozen exact 8-CPU/32-GiB full-cell
preflight. No repair4 output may be reused by repair5.

## Durable evidence

- Terminal census SHA-256:
  `fae0f421a7b79225436c6361a89baaa83699245d6cafca191aa7b00804d8d4b0`.
- Terminal census completion SHA-256:
  `31735ea72b5ed789974d4fff80826318222a6410fb0e1dc494081235e0dd6291`.
- Exact 54-record execution-metadata ledger SHA-256:
  `50dd20196d817f290751c031b0745980186a07098b861943e5510e9d4313b65f`.
- Empty object-inventory file SHA-256:
  `e3b0c44298fc1c149afbf4befc8996fb92427ae41e4649b934ca495991b7852b855`.
- Object-inventory hash-ledger SHA-256:
  `f9e112c28081e20b6b8e529e442a50d68e94fc58ce5efec3774595bef4c1d955`.

## Next action

Poll and strictly harvest exact preflight execution
`atlas-cbc-32g-full-2023-w8-v1-lbzjd`. It began running after repair4 capacity
was released. Only a terminal successful exact-full-cell receipt licenses the
already-frozen complete resource-only repair5 grid at 8 CPU/32 GiB.
