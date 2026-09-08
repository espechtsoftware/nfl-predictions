# Canonical-v3 paid/deployment bounded R4 independent review

Date: 2026-09-08

Reviewed candidate: `9dfc767f141053efd29e6471519c711bce3a86f6`

Candidate tree: `9b3a3fc70bfc0481d77926a1a14b0f0a288cd558`

Candidate branch: `origin/codex/canonical-v3-paid-r4-repair-20260908`

Exact parent / reviewed R3: `999204cc42602a43b8f94df12bbeb590db37ff40`

R3 HOLD authority: report
`reports/2026-09-08-canonical-v3-paid-deployment-r3-independent-review.md`
on branch `origin/codex/canonical-v3-paid-r3-independent-review-20260908`.

Review branch: `codex/canonical-v3-paid-r4-independent-review-20260908`

Disposition: **PASS for bounded integration; the R3 create-once blocker is
closed. This is not by itself a Cloud Build, deployment, traffic, activation,
or paid-output authorization.**

## Findings, ordered by severity

### Release blockers

None found.

The exact R4 tip implements every item in the bounded R3 HOLD contract. The
fixed final-activation URI is no longer authorized by whichever object happens
to be current. Both deployment and runtime require a fully consumed exact-name
inventory across live, all-version/noncurrent, and soft-deleted views. The
publisher requires empty history, retains the generation returned by a
normally completed conditional create, exact-reopens that generation, binds
its URI/generation/bytes/SHA-256, and proves the same sole-generation census
again. Runtime requires exactly one live generation and no noncurrent or
soft-deleted generation before and after its exact semantic read.

Accordingly, the R3 reproduction no longer works: after deletion/recreation,
the recreated live generation is accompanied by either a prior noncurrent or
soft-deleted generation and runtime closes before it reads final bytes. A
soft-deleted-only object, two live/versioned generations, a provider-list
error, partial iterator failure, category overlap, or census/read drift also
closes output.

### Required pre-deployment provider check, non-code-blocking

The authority bucket and the runtime/deployment service identities must
support all three provider queries used by the reviewed law, including
`soft_deleted=True`, and exact-generation reload/download. The installed
`google-cloud-storage` 3.13.1 API exposes the reviewed `soft_deleted` argument
and documents that the query succeeds only when the bucket has a soft-delete
policy. The implementation fully consumes every returned iterator and converts
permission, policy, pagination, transport, or representation uncertainty into
a closed gate.

Before live cutover, run one outcome-blind provider-reality authentication from
the exact release image/service identity against the intended authority prefix.
It must prove the soft-delete policy/query and required list/get permissions.
This is an operational readiness check, not a reason to redesign or add a new
arm; the early deployment census is already ordered before the first Cloud Run
mutation and will fail closed if the provider contract is unavailable.

### Operational observation, non-blocking

The final companion publication receipt is written locally after the GCS
conditional create and exact reopen. A local filesystem failure at that last
write could therefore leave a valid, unique final gate active without the
local companion file. This does not bypass or weaken the runtime money law:
the immutable final object still contains the authenticated R3 authority and
runtime independently recenses and validates it. If the wrapper returns
nonzero after provider publication, however, the operator must reconcile the
exact provider generation and must not blindly retry. Retaining or remotely
archiving the companion receipt can be future operational hardening; it is not
part of the R3 security blocker and should not delay integration.

Paid-v2 and the legacy Week-1 route remain outside the paid-v3 authority. They
must continue to be described as legacy routes unless separately retired or
denied at ingress. R4 did not widen that pre-existing boundary.

## Requirement-by-requirement adjudication

1. **All-generation and soft-delete absence law: PASS.**
   `read_paid_classic_final_generation_census_v3` materializes live,
   `versions=True`, and `soft_deleted=True` iterators; exact-name filtering
   excludes the adjacent traffic archive. Closed-schema normalization rejects
   missing categories, noncanonical generations, duplicates, overlaps, and
   provider-view disagreement. The first absence check precedes every Cloud
   Run mutation.
2. **Repeated prepublication inventory plus atomic create: PASS.** The wrapper
   repeats the complete absence check after final-authority construction. The
   provider publisher repeats it immediately before
   `upload_from_string(..., if_generation_match=0)` and treats any exception,
   including an ambiguous/collision return, as failure without a creator
   receipt.
3. **Provider-returned generation and exact reopen: PASS.** Only the generation
   returned on the successfully completed blob upload is accepted. It must be
   the sole live and historical generation, is reloaded/downloaded by exact
   generation, and must reproduce the already authenticated bytes. Its exact
   URI/generation/bytes/SHA-256 and the stable census are bound into the closed
   publication receipt and shell transcript.
4. **Runtime unique-generation law: PASS.** Runtime uses the same census reader
   and validator, requires one live generation with no noncurrent or
   soft-deleted history, exact-reads that generation, applies the retained R3
   semantic/cross-binding validator, and recensuses before returning authority.
5. **Adversarial coverage: PASS.** Tests cover soft-delete only; soft-delete
   plus recreated live; live plus noncurrent; exact-name/prefix neighbors;
   permission and late-page failures; malformed, duplicated, overlapping, and
   noncanonical census fields; conditional-create collision; an immediate
   second generation; exact provider-generation reopen; and runtime census
   drift. The real-shell traffic-success plus final-attestation-and-rollback-
   failure adversary remains in the exact release gate.
6. **Scope retention: PASS.** The candidate is a single direct child of R3.
   Its product delta is limited to the deploy wrapper, final-authority module,
   and a Week-1 reader type annotation. No scoring, generation, selection,
   objective, money-policy constant, frozen v1/v2, graph, or experiment-default
   module changed.

## Accepted R3 laws retained

The following R3 functions have identical normalized AST hashes between R3
and R4:

- `validate_paid_classic_build_evidence_v3`:
  `100071960a27e3305a2502e21c41d20090861273876ccd55ed7838e9b0341cf4`;
- `attest_paid_classic_deployment_v3`:
  `6df3891ea445000e78224bddc96319412faf246c35a1dea34ccbf5c3741c28a7`;
- `validate_paid_classic_deployment_attestation_v3`:
  `216002fca40fa9fa7b14af90da24c0b7f4d861a29288be97a7e2a9d420fe056f`;
- `validate_paid_classic_final_activation_authority_v3`:
  `75c7a864f456be37345f3570457cc9c8426d490fa798896523fbd5ed34461b46`;
- `create_paid_classic_final_activation_authority_v3`:
  `49d9d74ffdd9eb98dfb28fc52ba73db1198d2944937cea953d3223482a4e4cf3`.

The paid-v3 book, application router, and Cloud Build contract retain their
exact R3 Git blob identities:

```text
src/nfl_dfs/optimizer/paid_classic_book_v3.py  1ca363b7d800de7aa32f302f15b5044bec5cb541
src/nfl_dfs/app/main.py                         a4f2dcf5cb9b3d1a1ffba9db94e5598758065a62
cloudbuild.paid-boundary-v3.yaml               87b8bdb9a64f466632376cc90d940882b5b0d846
```

Independent shell-order inspection confirms strict ordering of initial
historical absence, first Cloud Run mutation, traffic mutation, final traffic
attestation, final-authority construction, repeated absence, rollback disarm,
and provider publication. The existing rollback remains armed through all
posttraffic authentication and final-authority construction. If traffic moves
and final attestation and rollback both fail, no final money gate is written.

## Independent validation

The remote branch reproduced the requested exact commit and tree and was clean.
Static checks passed:

- direct-child ancestry (`9dfc767f...` -> `999204cc...`);
- `git diff --check`;
- `bash -n` for both paid build/deploy wrappers;
- Python compilation of every changed Python/test module;
- winner-registry-v2 check (117 observations, four source artifacts, zero
  official target scores, expected `candidate_only_unadjudicated` status);
- installed GCS client signature/documentation inspection; and
- exact changed-surface and retained-function/blob comparisons above.

The globally prioritized PREREG-074 R23 suite released the serial lane before
R4 validation. A fresh machine-wide census immediately before each invocation
found no other `python -m pytest` process. Both commands were serial, used the
shared production virtual environment, disabled repository addopts and cache,
and wrote no bytecode:

```text
focused R4 surface:              148 passed in 8.03s
exact Cloud Build release gate:  298 passed in 21.61s
```

No Cloud Build, deployment, Cloud Run/GCS mutation, traffic change, graph
load, score, outcome read, contest entry, or paid action occurred.

## Exact next action

Integrate the exact R4 candidate through the production review path. Before
any live cutover, authenticate the provider-list/soft-delete contract from the
exact release identity, retain the build/deployment/publication receipts, and
stop if the early historical census is not clean. Do not treat this code PASS
as independent authorization to build, deploy, change traffic, activate paid
output, or use a legacy route as paid-v3.
