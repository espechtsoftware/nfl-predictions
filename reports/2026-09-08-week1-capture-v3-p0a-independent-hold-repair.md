# Week-1 capture-v3 P0-A independent-HOLD repair candidate

Date: 2026-09-08

Branch: `codex/week1-capture-v3-p0a-review-repair-20260908`

Reviewed candidate tip:
`47183b0cc442735579f401284fb93facf022c935`

Independent HOLD tip:
`36e573d8fdb4c0b5f7b55e432b128b8b909f5ee0`

Controlling review:
`reports/2026-09-08-week1-capture-v3-p0a-independent-review.md`

## Disposition

**BOUNDED CODE/TEST REPAIR READY FOR FRESH INDEPENDENT REVIEW. LIVE
ACQUISITION, PROVIDER PUBLICATION, INFRASTRUCTURE CHANGES, DRAFTKINGS CONTACT,
PAID ENTRY, AND OUTCOME CONTACT REMAIN ON HOLD.**

The repair addresses all three P0 defect classes and the P1 authority-interface
finding without enabling a call site or populating an activation pin. The
generic `week1_a5_capture_contracts.py` P2 implementation and the legacy-v2
compatibility implementation are unchanged, so their existing serialized
artifact bytes and behavior are preserved.

## P0-1: complete direct bucket governance

The previous governance adapter projected a short role list and therefore
discarded a direct `roles/storage.objectUser` grant. The repaired adapter:

1. Retains the complete direct bucket IAM binding set, including conditions,
   rather than retaining only recognized writer/viewer projections.
2. Binds provider IAM policy version, provider ETag, canonical full bindings,
   and a digest over all three.
3. Derives the direct object-mutator and viewer member sets from those exact
   bindings and rejects any mismatch between the projections and full policy.
4. Includes `roles/storage.objectUser` and the legacy object-writing roles in
   the direct mutator set.
5. Fails closed on any custom, new, or otherwise unreviewed bucket role. The
   collector does not guess that an unknown role is read-only.
6. Requires the full policy facts as separate activation pins. All remain
   absent, so the live path still fails before constructing a provider client.

Adversaries now cover an unexpected `roles/storage.objectUser` member, a
custom object-writer role, public access, and the concrete GCS policy adapter's
retention of an object-user binding. A second direct writer can no longer be
hidden by role projection.

This code-side census deliberately does not claim to derive inherited
project/folder/organization roles, service-account impersonators, or Cloud Run
job updaters. Those effective-authority facts require the separately reviewed
P0-B provider attestation and remain an activation blocker. The direct bucket
must also be reduced to the small reviewed role vocabulary; custom roles are
not accepted merely because their name looks harmless.

## P0-2: root-last ledger is cutoff- and phase-bound

The production authority implementation is now constructed with one immutable
repository-owned read boundary:

- exact acquisition profile set;
- pre-lock or post-lock phase;
- exact `publish_by` text and timestamp; and
- the applicable Week-1 lock boundary.

Every authority read requires:

```text
observation <= raw/trace <= receipt <= ledger <= publish_by
```

A pre-lock ledger must be strictly before the Week-1 lock. A final-field ledger
must be strictly after it. The authority exact-reopens the sole ledger
generation once before dependent evidence and again at the end, requiring the
same `{uri, generation, sha256, bytes}`, provider creation time, and bytes.

The fixed live publisher builds the generic P2 artifact only through that
boundary, publishes it create-once under the same cutoff, and then requires
the provider-returned capture creation time to be no earlier than each exact
ledger generation used by that build. The exact ledger identity/time is held
by the private live authority for this publication check; the existing P2/v2
semantic artifact shape is not silently changed.

The reproduced attack now fails: a receipt/raw/trace from September 13 paired
with a root-last ledger created September 14 cannot authenticate a pre-lock
provider capture. A derived-capture provider generation dated before its
ledger also fails.

## P0-3: redirect validation precedes contact

The fixed requests adapter no longer uses automatic redirects. It now:

1. Validates the initial scheme, hostname, implicit/explicit port, and path
   family before constructing provider traffic.
2. Sends every request with `allow_redirects=False`.
3. Rejects any response object that reports an internally followed history.
4. Validates the response URL and requires it to equal the requested hop.
5. Resolves and validates each `Location` target before the next request.
6. Permits only 301/302/303/307/308 redirects, caps the chain at five, and
   rejects loops before another request.
7. Restricts HTTPS locator families to port 443 (implicit or explicit).

The new fake-session adversaries prove that an off-family redirect target is
never called, a non-443 initial locator is rejected before session-state
access, and a self-loop is rejected before a second request. The existing
post-transport chain/ledger validation remains in place as a second boundary.

## P1: live authority construction semantics

The exported `ProductionDraftKingsAcquisitionAuthority` class and public
authority-returning factory were removed. Python underscore/token privacy is
no longer described or tested as a security boundary.

The fixed live provider-capture functions create the private implementation
from repository-owned policy, GCS stores, runtime service-account check,
phase, profile set, and cutoff. Their signatures still accept no authority,
store, locator, transport, project, bucket, service account, or session path.
An explicitly private `_authority_from_reviewed_ports` seam remains for
offline adversarial tests and requires the same phase/profile/cutoff boundary;
no production call site uses it.

## Validation

All pytest commands began only after a separate exact global process census
showed no `python ... -m pytest` process. Tests ran serially.

- Repaired P0-A suite: **21/21 passed** in 0.78 seconds, 138,876 KiB maximum
  RSS.
- Existing P2 suite: **42/42 passed** in 16.43 seconds, 139,584 KiB maximum
  RSS.
- Legacy-v2 compatibility suite: **15/15 passed** in 1.02 seconds, 145,908
  KiB maximum RSS.
- Python byte compilation: passed for both collector modules and the focused
  test module.
- Ruff: passed for both collector modules and the focused test module.
- `git diff --check`: passed.
- `src/nfl_dfs/ingest/week1_a5_capture_contracts.py` and
  `tests/test_week1_a5_capture_contracts.py` remain byte-identical to exact
  production parent `0391390ca82df6bcc0661e84e2c179f20e2975b6`.

No broad suite or local simulation ran. No network, provider, DraftKings,
cloud, deployment, GCS publication, paid-entry, scoring, selection,
generation, or outcome operation occurred.

## Residual activation gates

This repair is source-only. A fresh independent CODE PASS is required before
P0-B. P0-B must still establish and bind, without guessing:

1. the immutable source archive, image digest, runtime job/revision and
   provider-authenticated service accounts;
2. complete inherited effective IAM, service-account impersonation and job-
   update authority in addition to the now-complete direct bucket policy;
3. the dedicated bucket's real retention/versioning/metageneration facts;
4. the authenticated active-entry request locator and every permitted
   redirect/effective family;
5. real response media/disposition/session behavior and settled response
   shapes; and
6. the D832342 full-field rehearsal and separately reviewed live publication
   call graph.

All activation pins remain `None`, and repository search must continue to show
no non-test caller. A reviewer should rerun the late-ledger, complete-policy,
off-family pre-contact, explicit-port, redirect-loop and public-interface
adversaries before granting any next gate.
