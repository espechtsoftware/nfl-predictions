# CP-4 efficacy branch review

Date: 2026-09-08 America/Chicago  
Candidate: `nfl2` branch `lab/cp4-efficacy-prep` at
`538f8b74682a206e5bda58275dd8a2da0717df31`

## Disposition

**HOLD before build or cloud launch.** The branch now executes its focused
tests safely, but the score-free cohort receipt does not preserve the selector
or fixed-count memberships computed by the accepted mechanics path. A reader
could produce plausible numbers from those receipts, but they would not be the
declared CP-4 estimands.

## What passed

- `tests/test_cp4_efficacy_prep.py`: 49/49 under a 4 GiB virtual-memory cap.
- The former runaway test was correctly repaired. The global
  `argparse.ArgumentParser` monkeypatch recursed and was the direct cause of
  the approximately 22 GiB local process; the replacement reads the parser's
  own help output and completes quickly.
- The real composed generation path is now explicit opt-in via
  `--execute-composed`, preventing a default unit-test invocation from running
  the expensive scientific workload.
- Outcome authentication, release shape, canonical roster identity, complete
  cell-set seal validation, and slate-level bank averaging have materially
  improved from the earlier candidate.

## P0: cohort memberships are not the accepted memberships

`scripts/cp4_efficacy_cohort.py::composed_cell_receipt` computes the accepted
mechanics object, including `composed["evidence"]`, but never consumes that
evidence. Instead it sets, for each arm:

```python
hashes = [c["roster_sha256"] for c in serialized["candidates"]]
arm_record(serialized, hashes, hashes[:E.K_NATURAL], hashes, hashes)
```

This means:

- `admitted` is every delivered candidate, so an admission loss is impossible;
- `k80_selection` is the first 80 candidates in generator order, not the
  audited `select_expected_max` result already computed in
  `composed["evidence"][arm]["k80_natural"]`;
- `fixed_count_selection` is the entire natural pool, not the fixed-count K80
  selection; and
- the later `fixed_count_max` is therefore a pool oracle, not a K80 book max.

Consequently selected-book turnover, representation, treatment-only retention,
first-loss attribution, realized delta, winner utility, and the
supply/admission/retrieval decomposition are all mislabelled downstream.

The validator does not catch this. It only caps `k80_selection` at 80; it does
not require `fixed_count_selection` to contain 80 members or bind either list
to the persisted selector evidence.

### Required repair

Build both selection lists from the exact indices and roster hashes already in
`composed["evidence"]`, preserving their selection order. Bind the candidate
matrix and selector identities from that evidence. Define `admitted` from the
actual D800 admission boundary; if this mechanics path contains no distinct
admission stage, say so explicitly and do not invent one. The pool-oracle
universe should remain the declared eligible candidate set, separately named.

Add a behavioral regression with deliberately non-prefix selector indices and
unequal natural/fixed membership. It must fail if the receipt substitutes the
first 80 candidates or the full pool for either selected book. Also require
both selected books to contain exactly K when their evidence reports `ok`.

## P0: no frozen provider cohort launch/seal path yet

The launch contract remains `DRAFT` and the branch contains only a local
one-cell CLI plus a seal that reads arbitrary local directories and prints JSON
to stdout. There is no bound immutable image, run authority, registered
three-bank launcher, create-once per-cell object namespace, exact-generation
terminal census, or provider-published cohort seal/release chain.

That is acceptable for implementation preparation but not sufficient for a
162-cell cloud efficacy cohort. The next candidate needs a complete score-free
provider path with exact source/image/runtime bindings, typed unavailable cells,
zero retries, terminal 162-cell census, and a create-once seal. The score reader
must remain a separate post-release action.

## Scope of the repair

Keep CP-4's scientific law fixed: control 160 leverage + 640 boom, treatment
160 contextual + the identical 640 boom, D800 work budget, banks 740--742,
Sunday-main 2022--2024 panel, K80, judge, and outcome authority. This review
does not authorize a new arm or a score read. It asks only that the intended
memberships and execution identities survive from the accepted mechanics path
to the sealed receipts.

