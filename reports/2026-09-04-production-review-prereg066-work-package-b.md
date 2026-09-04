# Production review: PREREG-066 Work Package B

Date: 2026-09-04 UTC

Scope: outcome-blind review of the lab's beneficiary rescue-relevance
implementation at lab `main` commit
`26ba113654cbf17fac9645b61cd42a1547f56360`.

This review does not amend or interrupt experiment 095. The efficacy cohort
remains sealed while its Cloud Run banks execute. Work Package B must not run
until the 095 first-read transcript is sealed and the eligibility condition in
the adopted production plan is satisfied.

## Result

The scientific core is aligned with the adopted plan:

- the cohort is every unselected `REDIST_DEMAX` candidate, without
  outcome-based row selection;
- the target is whether the candidate beats its same-slate `REDIST_DEMAX`
  book maximum;
- beneficiary status is the pre-lock binary feature;
- the reader validates the full candidate settlement with a one-to-one exact
  `(slate_id, roster_sha256)` join before Work Package B receives the frame;
- the co-signed binary support rule, season-clustered bootstrap, sign-flip,
  LOSO cuts, and three-route disposition are present;
- the seal guard rejects a missing transcript or a supplied transcript hash
  that differs from the local bytes.

Independent focused validation on the exact lab tip passed:

- `tests/test_prereg066_rescue_relevance.py` and
  `tests/test_prereg066_reader.py`: **7 passed**;
- Ruff on the Work Package B implementation and tests: **clean**.

The implementation should not execute yet. Three bounded repairs are needed
before its one permitted post-seal run.

## Required pre-execution repairs

### 1. Prove the sealed input and analysis implementation identities

The module says it requires a *committed* first-read transcript, but currently
checks only that a file exists at the expected path and that its bytes equal a
caller-supplied SHA-256. An untracked or locally modified transcript can pass.
It also imports the current `scripts/prereg066_report.py` and current
`nfl2.scorecard._sign_flip_p` without binding their bytes.

Before execution, require and receipt:

- transcript path tracked at `HEAD`;
- working-tree transcript bytes exactly equal the `HEAD` blob;
- transcript SHA-256 supplied on the command line and equal to those bytes;
- exact PREREG-066 reader SHA-256 (currently bound for the efficacy release as
  `e7d725b07ef2405644b5f398004e7a1f59774d7ecb9bf54f183dcfd96b987875`),
  or a separately reviewed post-seal reader identity if that file must change;
- exact analysis source commit and Work Package B script SHA-256;
- exact scorecard/sign-flip implementation identity, or a local frozen
  implementation with behavioral equivalence tests.

The output receipt should contain those identities plus all three frozen run
IDs. This is an analysis-boundary repair, not a request to change any 095
runner, artifact, arm, or reader.

### 2. Enforce the declared exactly-once output

The default output currently uses `Path.write_text`, so a second invocation can
silently replace the first result. Publish create-once: fail if the target
exists, write through an exclusive-create or atomic no-clobber path, reopen the
published bytes, and report their SHA-256. A failed attempt must not leave a
partial file that can be mistaken for the terminal artifact.

The command should also fail closed unless a separately recorded post-seal
release says Work Package B is eligible under section B1 of the adopted plan.
The existence of any sealed 095 transcript alone is not proof of that routing
decision. A small immutable release receipt binding the transcript SHA and the
three run IDs is sufficient; do not parse an informal sentence from the
transcript.

### 3. Route on raw statistics and emit the promised denominators

The implementation rounds `mean_within_slate_rho` and every LOSO estimate to
four decimals, stores only those rounded values, and then uses the rounded
values for `RESCUE_ELIGIBLE`. The frozen rule is based on the mathematical
sign, so routing must use the unrounded mean and unrounded LOSO values. Rounding
belongs only in the presentation fields. Add a boundary regression in which a
small positive value rounds to zero but remains positive for routing.

The adopted plan also asks that conditional rates carry candidate and slate
denominators. The current `rates` output includes candidate counts but no slate
counts. Add, at minimum, the distinct `(season, week)` count for every overall,
bank, and season cell, and preferably the distinct-slate counts supporting B=1,
B=0, and rescue events. These are descriptive additions and must not change
the inferential cohort or routing rule.

## Non-issues confirmed

- The settlement dictionary inside `cohort_rows` does not silently weaken the
  join because frozen `_load` has already called `reader_settlement_join`,
  which rejects duplicate, missing, and extra settlement keys and reconciles
  the complete generated population.
- Pooling banks within `(season, week)` is the already co-signed unit for this
  bounded diagnostic.
- Undefined binary slates are explicitly excluded with reasons and are never
  coerced to zero.
- The requested repairs do not justify opening 095 outcomes, changing its
  frozen files, or delaying the running efficacy cohort.

## Requested lab disposition

Land only the three repairs above plus focused behavioral tests while 095 runs.
Do not execute Work Package B. After the 095 first read is sealed, production
will independently verify the transcript and eligibility-release identities;
then Work Package B may run exactly once if and only if the adopted B1 route is
eligible. Experiment 091 remains held.
