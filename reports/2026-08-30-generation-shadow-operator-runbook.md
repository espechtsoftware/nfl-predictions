# Generation-shadow immutable operator runbook

Date: 2026-08-30
Status: implementation complete locally; no cloud publication or job mutation
has been performed from this work.

## Purpose

The five-arm generation-shadow suite now has one bounded operational path from
the pre-Week-1 decision rule through weekly realized grades. The operator does
not alter production lineups, allocate entries, adopt a treatment, install a
scheduler, inspect IAM, or modify a money job. It publishes evidence only.

The executable is:

```bash
nfl-dfs shadow-generation-operator <subcommand> ...
```

Every subcommand that writes GCS requires the literal `--execute` flag. Without
it, the command fails before constructing a cloud client.

The generation suite itself has no automatic “upcoming slate” mode. An
operator must supply exact season, week, draft group and the lock timestamp
from the frozen slate authority:

```bash
nfl-dfs shadow-generation-suite \
  --season 2026 --week 1 --draft-group-id DRAFT_GROUP_ID \
  --slate-lock-at 2026-09-13T17:00:00+00:00
```

An accidental execution of the installed job without those values fails
before candidate or outcome access.

## Immutable object law

All operator outputs use `if_generation_match=0`. A pre-existing object is a
collision even when its bytes are identical; the operator refuses to overwrite
or accept it. After a partial failure, use a fresh run URI. Do not retry into
the same namespace.

Every input is reopened by all four content coordinates:

- exact `gs://` URI;
- exact object generation;
- exact byte count; and
- exact SHA-256.

The GCS `time_created` value is the clock authority. Prelock objects must be
strictly before slate lock. Outcome/field objects must be strictly after lock,
and the capture receipt may not predate its source CSV.

## 0. Build and install the isolated job

After the release cohort is committed and pushed, build only from that exact
commit archive. Unrelated local worktree files never enter the context:

```bash
scripts/build_generation_shadow_suite_image.sh --execute FULL_PUSHED_CODE_SHA
```

Record the returned Cloud Build ID and digest-pinned `IMAGE`. Install the
dedicated unscheduled job without running a slate:

```bash
GENERATION_SHADOW_ALLOW_CREATE=1 GENERATION_SHADOW_EXECUTE=0 \
  scripts/cloud_generation_shadow_suite.sh IMAGE FULL_PUSHED_CODE_SHA
```

Subsequent installs update that one predeclared job and do not need
`GENERATION_SHADOW_ALLOW_CREATE=1`. To run a frozen slate later, explicit
season/week/draft-group/lock environment values and
`GENERATION_SHADOW_EXECUTE=1` are all required. No scheduler is installed.

## 1. Publish the pre-Week-1 family rule

Publish this once before the Week 1 Sunday-main lock:

```bash
nfl-dfs shadow-generation-operator preregister \
  --target-uri gs://BUCKET/generation_shadow/2026/authorities/preregistration.json \
  --registered-at 2026-08-30T12:00:00+00:00 \
  --week1-lock-at 2026-09-13T17:00:00+00:00 \
  --operational-k 80 \
  --execute
```

The preregistration fixes the five-arm order, K20/K40/K80 reporting,
194/200/210/220/230/240 thresholds, the eight-week integrity-only read, the
18-week first efficacy read, the single family decision rule, and no automatic
adoption.

## 2. Publish the crossed fit/world authority

`publish-seed-crossing` accepts a JSON request with:

```json
{
  "target_uri": "gs://BUCKET/generation_shadow/2026/authorities/seed-crossing.json",
  "fit_seed_identities": {"fit0": {"uri": "...", "generation": "...", "sha256": "...", "bytes": 1}, "fit1": {"uri": "...", "generation": "...", "sha256": "...", "bytes": 1}},
  "world_seed_identities": {"world0": {"uri": "...", "generation": "...", "sha256": "...", "bytes": 1}, "world1": {"uri": "...", "generation": "...", "sha256": "...", "bytes": 1}},
  "crossed_slot_identities": {"fit0--world0": {"uri": "...", "generation": "...", "sha256": "...", "bytes": 1}, "fit0--world1": {"uri": "...", "generation": "...", "sha256": "...", "bytes": 1}, "fit1--world0": {"uri": "...", "generation": "...", "sha256": "...", "bytes": 1}, "fit1--world1": {"uri": "...", "generation": "...", "sha256": "...", "bytes": 1}},
  "must_precede": "2026-09-13T17:00:00+00:00"
}
```

Run:

```bash
nfl-dfs shadow-generation-operator publish-seed-crossing \
  --request /absolute/path/seed-crossing-request.json --execute
```

All eight source artifacts are exact-reopened before the crossing object is
written. This freezes a design lattice only. Its receipt says execution
`not_evaluated` and semantic outputs unverified until a successor binds the
actual four crossed generation/scoring results.

## 3. Adapt one completed suite run into the evaluation authority

The suite itself publishes its manifest, terminal, five arm NPZ bundles, five
cross-law discovery banks, and independent audit bank before lock. Once that
terminal exists, `freeze-week` accepts:

```json
{
  "preregistration_identity": {"uri": "...", "generation": "...", "sha256": "...", "bytes": 1},
  "seed_crossing_identity": {"uri": "...", "generation": "...", "sha256": "...", "bytes": 1},
  "suite_manifest_identity": {"uri": "...", "generation": "...", "sha256": "...", "bytes": 1},
  "suite_terminal_identity": {"uri": "...", "generation": "...", "sha256": "...", "bytes": 1},
  "terminal_root_uri": "gs://BUCKET/generation_shadow/2026/week-01/evaluation/terminal-root.json",
  "terminal_envelope_uri": "gs://BUCKET/generation_shadow/2026/week-01/evaluation/terminal-envelope.json",
  "slate_id": "dk-DRAFT_GROUP_ID"
}
```

The adapter exact-reopens every declared suite object, compares external GCS
creation times with the suite's internal receipts, checksum-decodes all five
arm bundles, invokes the evaluator's real suite adapter, publishes the terminal
root, and publishes its envelope second. No caller can substitute books,
candidates, score maps, thresholds, or arm labels.

## 4. Publish postlock outcomes and the weekly grade

`grade-week` accepts the frozen envelope identity, a generation-pinned score
artifact already published outside the grader namespace by an independent
scorer, its postlock capture timestamp, and a fresh output prefix:

```json
{
  "terminal_prelock_envelope_identity": {"uri": "...", "generation": "...", "sha256": "...", "bytes": 1},
  "captured_at": "2026-09-14T12:00:00+00:00",
  "realized_score_source_identity": {"uri": "gs://BUCKET/independent-scorer/2026/week-01/realized-scores.json", "generation": "...", "sha256": "...", "bytes": 1},
  "output_prefix_uri": "gs://BUCKET/generation_shadow/2026/week-01/postlock/run-001",
  "field_inputs": null
}
```

The independent artifact must use
`prospective-generation-realized-score-source/v1`, exactly cover every frozen
lineup ID with integer micro-points, carry no arm/treatment/root binding, and
have a trusted creation time after lock and at or after its `captured_at`.
The operator exact-reopens and validates it; it does not mint a score map and
rejects a score artifact inside its own output prefix.

With `field_inputs: null`, the operator deliberately emits a
`raw-score-only-no-contest-ev` bridge. It still publishes and grades every
frozen lineup, but rank, duplicates, payout, contest EV, and allocation advice
remain unavailable.

A complete field request instead supplies exactly:

- `capture_manifest_identity` for the applied `capture-dk-standings` receipt;
- `capture_source_identity` for the archived full DK CSV;
- `entry_fee_micro`;
- exact payout-table rows;
- point-in-time participant-strength rows covering every entry; and
- player-identity rows covering the complete captured field.

The operator generation-reopens the receipt and CSV, reruns the existing full
field validator on those exact bytes, publishes six derived components, and
then binds the complete bridge. An archived capture receipt is recognized as
applied only when its own declared `receipt_uri` equals the exact object being
reopened; the capture code writes that receipt only after both deterministic
warehouse loads finish.

Raw-score mode creates five objects: bridge, outcome source, outcome snapshot,
weekly grade, and publication terminal. Complete-field mode creates those five
plus six field components. The independently published score source is an
input, never one of the grader's writes. The publication terminal is last.

## 5. Publish a versioned prospective evaluation

`evaluate-season` accepts the preregistration identity, the ordered set of
weekly-grade identities, and a fresh target URI:

```json
{
  "preregistration_identity": {"uri": "...", "generation": "...", "sha256": "...", "bytes": 1},
  "weekly_grade_identities": [{"uri": "...", "generation": "...", "sha256": "...", "bytes": 1}],
  "target_uri": "gs://BUCKET/generation_shadow/2026/evaluations/through-week-01.json"
}
```

The evaluator requires contiguous weeks beginning at Week 1. Through Week 7,
the result is accrual only. Week 8 is integrity/severe-harm only and cannot
promote an arm. Until explicit operational safety receipts are supplied, its
integrity status is `not_evaluated`, not a synthetic pass. Week 18 is the first
efficacy estimate, includes uncertainty, and still requires a human decision.
The operator never changes allocation or production policy from any result.

## Local validation

Focused operator validation currently covers:

- create-once preregistration and collision refusal;
- exact reopening of all fit/world crossing inputs;
- suite-object reopening and root-before-envelope order;
- independent-audit decoding and K20/K40/K80 base/cap calibration;
- raw-only and complete-field publication topologies;
- rejection of caller-authored/in-namespace realized-score truth;
- archived pretty-JSON DK capture receipt reopening;
- season evaluation with no auto-adoption;
- default-off CLI behavior and main CLI forwarding; and
- GCS absence precondition plus generation-pinned reopen calls.

No GCS object, Cloud Run job, scheduler, IAM binding, or production policy was
mutated while implementing or testing this operator.
