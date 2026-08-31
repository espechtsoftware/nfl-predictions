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

The launch prints one exact execution name.  After that execution reaches
terminal success, collect its receipt-only stdout without updating or
executing the job:

```bash
GENERATION_SHADOW_COLLECT_EXECUTION=generation-shadow-suite-abc12 \
GENERATION_SHADOW_SEASON=2026 \
GENERATION_SHADOW_WEEK=1 \
GENERATION_SHADOW_DRAFT_GROUP_ID=DRAFT_GROUP_ID \
GENERATION_SHADOW_SLATE_LOCK_AT=2026-09-13T17:00:00Z \
scripts/cloud_generation_shadow_suite.sh IMAGE FULL_PUSHED_CODE_SHA
```

Collection exact-describes only that execution, proves one successful task,
zero failures/cancellations/running tasks, the immutable image/code/project/
bucket/resources and exact slate arguments, then accepts exactly one matching
JSON stdout receipt.  It returns normalized generation-pinned manifest and
terminal identities for `freeze-week`.  It never describes, updates, deploys,
or executes the mutable job and never reads outcomes.

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

## 2. Publish the crossed fit/world design authority

The production operator can now create the eight explicit design-only source
documents itself, rather than depending on unspecified external artifacts.
Choose and freeze the two fit seeds and two world seeds before any outcome is
available:

```json
{
  "source_prefix": "gs://BUCKET/generation_shadow/2026/authorities/seed-design-v1",
  "target_uri": "gs://BUCKET/generation_shadow/2026/authorities/seed-crossing.json",
  "fit_seeds": {"fit0": 2026083001, "fit1": 2026083002},
  "world_seeds": {"world0": 2026083011, "world1": 2026083012},
  "must_precede": "2026-09-13T17:00:00+00:00"
}
```

Run:

```bash
nfl-dfs shadow-generation-operator publish-seed-crossing-design \
  --request /home/erich/projects/nfl-predictions/config/2026-week1-generation-shadow-seed-crossing-design.json \
  --execute
```

This writes two fit-axis documents, two world-axis documents, four crossed
design slots, then exact-reopens all eight and publishes the crossing.  Every
object explicitly says the diagnostic is `not_evaluated`; these are never
presented as fit, generation, scoring, or outcome results.

The lower-level form below remains available when eight independently
published source artifacts already exist.

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

The independent audit artifact is accepted only when its observed main-model
version, candidate-input receipt and player order match the exact paired
all-arm input authority. Its role/construction fields are retained only as
frozen-candidate provenance, because the score-only audit path does not execute
role generation or construction.

## 4. Publish the terminal-derived weekly safety receipt

After `freeze-week` publishes the exact terminal root and carrier, publish the
operational safety row from that carrier:

```json
{
  "preregistration_identity": {"uri": "...", "generation": "...", "sha256": "...", "bytes": 1},
  "target_uri": "gs://BUCKET/generation_shadow/2026/week-01/safety/receipt.json",
  "week": 1,
  "slate_id": "dk-DRAFT_GROUP_ID",
  "terminal_prelock_envelope_identity": {"uri": "...", "generation": "...", "sha256": "...", "bytes": 1}
}
```

Run:

```bash
nfl-dfs shadow-generation-operator publish-safety-week \
  --request /absolute/path/week-01-safety-request.json --execute
```

For a terminal-present run, no caller clock is authoritative: `observed_at` is
derived from the exact-reopened terminal root's GCS
creation time. If a caller supplies `observed_at`, it must equal that trusted
time exactly. Arm, book, block and prefix inventories; solve failures and
shortfalls; legality; duplicates; player exposures; and evidence identities
are all reconstructed from the terminal, suite, ledgers and frozen rosters.
The caller cannot provide any of those counts.

If the suite failed before producing a terminal, publish a durable failure row
with `terminal_prelock_envelope_identity: null` and an explicit `observed_at`.
Every non-derivable metric remains `null`, and the receipt necessarily fails;
there is no caller-supplied-zero path. Weeks 1--8 require one receipt apiece.

## 5. Publish postlock outcomes and the weekly grade

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

## 6. Publish a versioned prospective evaluation

`evaluate-season` accepts the preregistration identity, the ordered set of
post-lock publication-terminal identities, and a fresh target URI. Direct
weekly-grade identities are not accepted: each terminal and every object it
references are generation-pinned and exact-reopened, and the weekly grade is
independently rebuilt from the exact pre-lock root and outcome snapshot before
it can enter a season aggregate:

```json
{
  "preregistration_identity": {"uri": "...", "generation": "...", "sha256": "...", "bytes": 1},
  "weekly_publication_terminal_identities": [{"uri": ".../publication-terminal.json", "generation": "...", "sha256": "...", "bytes": 1}],
  "weekly_safety_receipt_identities": [{"uri": "...", "generation": "...", "sha256": "...", "bytes": 1}],
  "target_uri": "gs://BUCKET/generation_shadow/2026/evaluations/through-week-01.json"
}
```

The evaluator requires contiguous weeks beginning at Week 1. Through Week 7,
the result is accrual only. Week 8 is integrity/severe-harm only and cannot
promote an arm. Until all eight exact operational safety receipts are supplied,
its integrity status is `not_evaluated`, not a synthetic pass. Each receipt is
joined to its weekly grade by week, slate and the exact terminal-root object
identity and SHA; safety from one root cannot license a grade from another.
Week 18 is the first efficacy estimate, includes uncertainty, and still
requires a human decision. The operator never changes allocation or production
policy from any result.

The Week-18 object also executes the frozen historical-plus-2026 synthesis.
Only a complete, integrity-passing, directionally concordant primary result
with a strictly positive paired interval can become a human-review candidate.
Every other full-season result has the frozen disposition
`continue-unchanged-accrual-into-2027`; historical and prospective gains are
never pooled or added.

The versioned output preserves the complete generation-by-retrieval surface at
K20/K40/K80: all six thresholds, pool oracle, selector regret, available field
rank/duplication/payout evidence, both within-population retrieval effects,
both within-retrieval generation effects, and their slate-paired
difference-in-differences with 95% intervals. This prevents the key-secondary
mechanism from being reduced after outcomes to whichever endpoint looks most
favorable.

## Local validation

Focused operator validation currently covers:

- create-once preregistration and collision refusal;
- exact reopening of all fit/world crossing inputs;
- suite-object reopening and root-before-envelope order;
- independent-audit decoding and K20/K40/K80 base/cap calibration;
- raw-only and complete-field publication topologies;
- rejection of caller-authored/in-namespace realized-score truth;
- archived pretty-JSON DK capture receipt reopening;
- terminal-derived weekly safety, trusted GCS clock binding, failed-run rows,
  and rejection of caller-authored zero metrics or cross-root reuse;
- season evaluation with no auto-adoption;
- default-off CLI behavior and main CLI forwarding; and
- GCS absence precondition plus generation-pinned reopen calls.

No GCS object, Cloud Run job, scheduler, IAM binding, or production policy was
mutated while implementing or testing this operator.
