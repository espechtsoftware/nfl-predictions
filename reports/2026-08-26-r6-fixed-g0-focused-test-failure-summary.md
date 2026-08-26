# R6 fixed-G0 focused-test failure summary

Date: 2026-08-26

## Invocation

Exactly one independently licensed offline invocation was run:

```text
.venv/bin/python -m pytest -q tests/test_corpus_r6_player_catalog_fixed_g0_adapter_v1.py
```

It exited `1`. The command made no cloud call, created no real-artifact smoke
attempt or receipt, and read no result, matrix, acceptance, effect, lineup, or
realized-outcome body.

The candidate identities at invocation were:

- source SHA-256
  `9878c3db99f1ab62bc2d1e143131c37470719854d7a58788f687a376c28f094e`,
  213,447 bytes;
- test SHA-256
  `446a36be64c1b368ef5f574cc1043e80c658ec451b65f99cb60d554ec04d484f`,
  123,862 bytes.

## Failure class

Pytest listed 27 failed nodes. Every listed failure converged on the same
exception and boundary:

```text
CorpusR6FixedG0AdapterV1Error: task evidence[0] carrier differs
```

The exception arose in
`_reopen_task_acceptance_and_carrier_v1`, called by
`_derive_pinned_projection_inputs_v1`. It affected the shared fixture path
used by task-0 smoke, final-lock, full 54-member replay, projection
publication/resume, and receipt-reopen tests. This is one common
fixture/validator mismatch until diagnosis proves otherwise; it is not
evidence of 27 distinct production defects.

The tool truncated the raw pytest output, so no exact collected/passed count
or complete raw-output hash is claimed. The durable facts are exit code 1,
the 27 listed failed nodes, and their common exact exception above.

## Consequence

The focused invocation is consumed. No second invocation is authorized under
the reviewed bytes. A bounded correction must sweep the complete carrier
binding class, record this failed history in an additive correction, freeze
new source/test identities, and pass fresh independent static review before
at most one post-fix focused invocation. The task-0 real-artifact smoke and
all catalog publication remain unauthorized meanwhile.
