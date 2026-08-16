# ATLAS continuous-interaction real-slate parity protocol

Date frozen: 2026-08-16, while the exact binary-interaction 32-GiB full-cell
preflight was nonterminal and before any continuous-interaction cloud result.
Protocol ID: `20260816-atlas-interaction-parity-v1`

## Purpose and queue position

The ATLAS pair/triple product auxiliary is mathematically integral whenever
the roster variables are binary, even when the auxiliary is declared
continuous on `[0,1]`. The proof and focused synthetic parity test are already
recorded in `reports/2026-08-16-atlas-interaction-integrality-proof.md`.

This protocol adds the requested hard real-slate roster-parity gate. It is a
conditional fallback, not a change to the running experiment:

- do not run it concurrently with the live 32-GiB binary full-cell preflight;
- if that preflight succeeds, the already-frozen binary repair5 grid retains
  priority and this diagnostic remains deferred until repair5 releases the
  research capacity;
- if that preflight fails, this becomes the next ATLAS solver diagnostic; and
- no binary repair4/repair5 result may be mixed with a future continuous grid.

## Immutable implementation

- Candidate image source commit:
  `06797314a0ed423b9f5783fc926b269c1fb24371`.
- Candidate validation build:
  `85aace06-7f36-4307-acfa-194c4648ef6d`.
- Only the unique immutable digest emitted if that build's complete test suite,
  image build and existing ATLAS runner smokes succeed may be used.
- Frozen MVP runner SHA-256:
  `0548e26e26d7e81b20c6837adcc8925bc2317f9b7c8586fba084787581cac740`.
- Continuous optimizer source SHA-256:
  `ba5ac3a7c9eb5d436fa6b319e13104b10281fee640c64377904d56c93db65de6`.
- Diagnostic source:
  `scripts/run_atlas_interaction_parity_diagnostic.py`, SHA-256
  `f8b5b54ce3aab95be36d32bdb3825f2c0b34ed9552c7ebaf0085f0e5f0fb1d2d`.
- The launcher must inject that exact diagnostic source into the immutable
  image without changing the installed runner or optimizer and must bind all
  hashes in a create-only manifest.

## Fixed calculation

Use only 2024 Week 15 and native source seed R0. This is the isolated real cell
whose old binary R0 calculation already completed under the strict CBC
resource diagnostic. Load all five books so leave-one-seed-out interaction
pricing and complete non-boom coverage remain identical to the frozen MVP.

Compute the common top-40 attainable worlds, their exact legal optima and the
eight structural clusters once. Then run the complete 40-lineup R0
matched-diversity enumeration twice with identical inputs, ordering, bans,
98% floor, tuple weights, stack rules and salary floor:

1. force only `interaction_*` auxiliaries back to the old binary category;
2. use the proved continuous `[0,1]` category from the candidate optimizer.

All nine roster variables remain binary in both calculations. No returned
lineup identity may be persisted. The create-only receipt may contain only
fixed provenance, counts, category instrumentation, ordered-roster and
proposal-path hashes, and Boolean parity fields.

Run one Cloud Run task at 8 CPU/32 GiB, zero retries and a 12-hour timeout.
Realized player scores, selected historical books, contest results, ownership
and payouts are forbidden.

## Frozen parity gate

The diagnostic passes only if all of these hold:

1. both enumerations produce exactly 40 unique additions;
2. at least one interaction auxiliary is constructed in both arms;
3. instrumentation proves the installed formulation declared those
   auxiliaries continuous, the control forced them binary and the treatment
   retained them continuous;
4. the complete ordered list of 40 roster identities is byte-identical after
   canonicalization; and
5. the canonical proposal-path signature, including accepted/rejected path,
   source world, cluster and coverage-count fields, is byte-identical.

Any missing source, timeout, solver failure, category discrepancy or parity
failure is terminally invalid/negative. Do not relax to unordered equality or
select another slate.

## Consequence

A pass confirms real-slate formulation parity but licenses no historical score,
production change or ATLAS effect. If the binary 32-GiB preflight failed, a
pass licenses freezing one continuous-interaction exact-full-cell preflight on
the same failed 2023 Week 8 cell. Only that later full-cell success could
license a complete all-new continuous repair grid.

A failure closes this continuous formulation for the current ATLAS MVP. No
outcome may be queried to reinterpret it.
