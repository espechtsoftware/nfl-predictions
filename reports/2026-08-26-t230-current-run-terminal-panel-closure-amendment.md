# T230 current-run terminal panel-closure amendment

Date frozen: 2026-08-26, after the sole ordinal-6 replacement became
terminal and before any result, acceptance, realized outcome, effect, score,
or lineup body was opened.

Status: pre-publication law for independent review; authorizes no execution.

## Why this is the correct next step

Run `20260825-foundry-t230-production-v2` cannot reach an accepted 54-member
panel. Lane A consumed its ordinary ordinal-6 worker and the one exceptional
replacement permitted by the ordinal-6 amendment. The replacement ended with
a nonzero application exit, so the amendment makes ordinal 6, Lane A, and the
full panel terminal-invalid and forbids another replacement.

Lane B independently stopped after the ordinal-35 worker succeeded and its
ordinary verifier suffered the exact contradictory Cloud Run code-13
platform signature. No verifier replacement was launched. A draft recovery
law existed but never passed independent review and granted no execution
authority. Recovering Lane B now would spend another long execution chain
without any possibility of making the already-invalid panel accepted.

This amendment therefore closes the current run truthfully and quickly. It
publishes one Lane-B terminal receipt and one combined terminal panel index.
It never converts partial work into acceptance, never launches compute, and
never reads science or outcome bodies.

The separately accepted 54-member Foundry v12 G0 from
`20260823-foundry-production-v12` is independent of this T230 run. Its R6-v2
player-catalog path may continue under its own two-lock law; this negative
T230 closure neither licenses nor blocks that path.

## Frozen run state

- Project: `nfl-predictions-503414`
- Region: `us-central1`
- Run: `20260825-foundry-t230-production-v2`
- Output prefix:
  `gs://nfl-predictions-503414-corpus-parametric/research/corpus-parametric-research/t230/20260825-foundry-t230-production-v2/`
- Immutable image:
  `us-central1-docker.pkg.dev/nfl-predictions-503414/nfl-dfs/nfl-dfs@sha256:ed7da003c80ad47118c3c9242ec2e9047a24f489134bfdc0f534a6769d622fee`
- Lane A accepted ordinals: exactly `0..5`, six of 28.
- Lane B accepted ordinals: exactly `28..34`, seven of 26.
- Full-panel accepted count: exactly 13 of 54.
- No canonical Lane-A ledger, Lane-B ledger, finish-panel request, canonical
  panel release, T230 G0 authority, R6 authority, or scoring authority exists.

The closure must derive the accepted sets from exact worker/verifier stage
and acceptance metadata identities. The integers above are assertions to
validate, not substitutes for replay.

## Lane-A terminal dependency

This amendment does not duplicate ordinal-6 closure logic. It depends on the
generation-pinned terminal artifacts created under
`2026-08-26-t230-ordinal6-replacement-terminal-closure-amendment.md`:

1. the attempt-1 execution terminal at
   `transport/platform-replacements/run-slate/06/attempt-01/execution-terminal-v1.json`;
2. the supplemental Lane-A terminal-invalid root at
   `transport/platform-replacements/lanes/lane-0-ordinal-06-amendment-v1.json`.

The Lane-A root must report six accepted members, ordinals 6 through 27
incomplete, both consumed ordinal-6 executions, no bridge verifier, and every
authority false. Missing, unequal, ambiguous, or non-terminal Lane-A evidence
prevents the combined index from being published.

## Lane-B terminal evidence

The Lane-B closer must exact-replay, by content identity, all accepted
ordinal-28 through ordinal-34 worker/verifier stages and acceptances in
strict order. It must also bind the ordinal-35 stopped chain:

- successful worker execution `atlas-cbc-32g-full-2023-w8-v1-bg5kv`;
- worker start generation `1787714234063439`, SHA-256
  `8769408869bbdfe940033a7f27cf5fa42fc4fc92416ca61e30447438ed87f73b`,
  3,600 bytes;
- worker runtime generation `1787714321300536`, SHA-256
  `09dafa50c03f8e6cd60a1cacb9f5b4a889f443fa4c3da8065ce27486e93bab8a`,
  13,520 bytes;
- result metadata only, generation `1787715331922729`, SHA-256
  `b9e8e344bb3e6043a84654e2a277a0137c406f6c67f76d5911293b3df1d517f6`,
  15,352,504 bytes, with `content_inspected=false`;
- worker stage generation `1787715332909235`, SHA-256
  `6065524e64d669864b9646e71347b54025a21a9318333095081f1ffcf516d387`,
  2,054 bytes;
- consumed verifier request generation `1787715358516177`, SHA-256
  `8d42167a91afa4d4bcd01f6c8bcc60f5e7a751ea482b6db7c1ae68cb8c360efa`,
  2,533 bytes, plus its exact publication intent/completion identities;
- verifier start generation `1787715526710581`, SHA-256
  `2bd29614608c18a0d5f5bd6e8d9c814c03ed080da9288ee8c1bb0e64d6c75f0d`,
  3,611 bytes;
- verifier runtime generation `1787715612475399`, SHA-256
  `bb477a4a2b8be8aaf211bf4ab6c3b60166eacd9b3f96af3ce92f03741c3aa03a`,
  13,647 bytes; and
- failed verifier execution `atlas-cbc-32g-full-2023-w8-v1-sqs7z`, whose
  exact execution/task projections carry `Completed=False`, code 13,
  `Internal error.`, and the contradictory execution-level exit-code-zero
  message described in the superseded recovery draft.

The ordinal-35 acceptance and canonical verifier stage must both still be
absent. Every ordinal-36 through ordinal-53 request, start, runtime, result,
stage, and acceptance surface must remain absent. A presence, changed
identity, or ambiguous metadata response fails closed.

## No verifier-35 replacement

The unreviewed draft
`2026-08-26-t230-ordinal35-verifier-bounded-platform-replacement-amendment.md`
is superseded before launch. Consequently:

- no attempt-1 verifier intent or request may be created;
- no Cloud Run verifier or ordinal-36 boundary execution may be submitted;
- the consumed attempt-0 verifier request may never be reused;
- no canonical or supplemental accepted Lane-B ledger may be fabricated; and
- no later equal-existing object may be interpreted as authority to resume.

This is an abandonment of an unnecessary recovery path, not a classification
of the ordinal-35 science result and not evidence against the tested strategy.

## Lane-B terminal receipt

After exact replay and two exact-name metadata-only absence passes, the
first-creator closer may publish one create-once object at:

```text
transport/terminal-closures/lanes/lane-1-verifier-35-v1.json
```

Its schema is `foundry-t230-terminal-invalid-lane-receipt/v1`. It must bind:

- the transport contract, execution authority, execution manifest, compute
  release, immutable image, and exact run/output-prefix identities;
- seven ordered accepted member records for ordinals 28 through 34, each
  carrying worker stage, verifier stage, and acceptance metadata identity;
- the complete ordinal-35 worker and failed-verifier mechanics listed above;
- `lane_ordinal=1`, `required_count=26`, `accepted_count=7`,
  `accepted_ordinals=[28,29,30,31,32,33,34]`,
  `first_incomplete_ordinal=35`, and `incomplete_ordinals=[35..53]`;
- `terminal=true`, `accepted=false`, `terminal_invalid=true`,
  `verifier_replacement_abandoned=true`, and
  `additional_execution_allowed=false`;
- `result_bodies_inspected=false`, `acceptance_bodies_inspected=false`,
  `realized_outcomes_accessed=false`, and
  `support_rank_book_effect_fields_withheld=true`; and
- false values for G0, panel, R6, scoring, fill, selection, graph, promotion,
  decision, deployment, and production authority.

The object is create-once. Equal-existing is resolve-only. Unequal collision,
publication ambiguity, or failure to generation-pin the created bytes leaves
Lane B terminal-invalid and permits no substitute URI or execution.

## Combined terminal panel index

Only after both generation-pinned negative lane roots exist may the closer
publish one create-once combined terminal index at:

```text
transport/terminal-closures/panel/t230-terminal-invalid-v1.json
```

Its schema is `foundry-t230-terminal-invalid-panel-index/v1`. It must bind
both exact lane-root identities and rederive, without opening acceptance
bodies, the disjoint ordered accepted set:

```text
[0,1,2,3,4,5,28,29,30,31,32,33,34]
```

It records `required_count=54`, `accepted_count=13`,
`incomplete_count=41`, `terminal=true`, `accepted=false`,
`g0_passed=false`, `panel_release_allowed=false`, and
`current_t230_run_reusable_for_scoring=false`. It explicitly distinguishes
this failed T230 experiment from the independently accepted August-23 v12 G0
source so downstream automation cannot confuse their run IDs or authorities.

The canonical `foundry-t230-panel-release-v1.json`, finish-panel request,
finalizer start/runtime/stage, and every accepted/supplemental panel root must
remain absent. This terminal index is the combined panel disposition requested
for auditability; it is not a G0 acceptance receipt.

## Minimal implementation and review sequence

The implementation must be isolated in new terminal-closure files. It may
reuse pure content-identity and create-once helpers but may not modify frozen
transport, ordinal-6 replacement, worker, verifier, or scoring code.

1. Freeze this amendment plus new module/controller/focused-test identities
   in a preliminary tracked review lock.
2. Obtain independent static P0/P1/P2 disposition.
3. Run exactly one focused offline test invocation if and only if licensed.
4. Run exactly one reviewed real-artifact preflight. It may exact-read
   mechanics receipts and exact-name metadata, but may not read result,
   acceptance, effect, lineup, world, or outcome bodies and may create no
   cloud object or execution.
5. Bind the test and preflight receipts in a final tracked-clean lock and
   obtain independent publication approval.
6. Publish the Lane-B receipt once, exact-reopen it, then publish the combined
   terminal index once and exact-reopen it. Mirror the final JSON bytes and
   identities under the tracked T230 run directory and update `HANDOFF.md`.

The focused suite must adversarially cover accepted-count/order drift,
overlapping lanes, ordinal-35 acceptance/stage presence, any ordinal-36+
surface presence, result-body reader injection, empty/two task rows, terminal
literal drift, attempted execution/submission, unequal create races,
ambiguous creates, index-before-both-lanes, accepted/G0 authority flips, and
cross-run confusion with the independent August-23 G0.

## Consequence boundary

This amendment grants zero Cloud Run, result, outcome, R6, or scoring
authority. Its sole purpose is to make the exhausted current T230 state
durable and machine-readable. The immediate analytical path proceeds against
the separately accepted `20260823-foundry-production-v12` G0 only after that
R6 adapter's own review, smoke, and final lock pass.
