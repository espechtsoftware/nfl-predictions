# T230 production v2 restart amendment

Date: 2026-08-25
Status: **outcome-blind transport restart; v1 compute is terminally refused**

## Decision

Restart the T230 production transport under the new run incarnation
`20260825-foundry-t230-production-v2` and build a fresh immutable image from
the repaired exact source. Reuse the already-frozen 54-slate Foundry v12 G0
panel without regenerating either source lane. Do not relaunch or use the v1
transport for prepare, benchmark, panel execution, scoring, or decision work.

This amendment changes transport serialization and run identity only. It does
not change the source panel, four T230 laws, support-switch law, matrices,
worlds, folds, final-fit books, 4/14/80 prefixes, lane split, compute limits,
verification law, false-authority law, or outcome boundary.

## Terminal v1 disposition

The accepted v1 image was
`us-central1-docker.pkg.dev/nfl-predictions-503414/nfl-dfs/nfl-dfs@sha256:90fd3e09d6d8a5a081f7903fa522223309d466d31d7aa163e0ea47da2a15c5a2`.
Its same-D release and transport contract are valid evidence of build, real
smoke, and release integrity. They are not compute authority after the first
prepare request became terminal.

Prepare execution `atlas-minimal-c-s2023-w1-v1-zxnbb` completed false at
`2026-08-25T18:48:12.042398Z`, with one failed task, exit code 2 and
`maxRetries=0`. The exact Cloud Run execution envelope contains three
container arguments:

1. `-ceu`;
2. the runtime script truncated after `[[ "$T230_PRED_COUNT" =`; and
3. the remainder beginning ` ^[0-2]$ ]] || exit 2`.

The v1 operator encoded the two intended arguments with gcloud's alternate
list delimiter `~` while the Bash payload itself contained the `=~` regex
operator. Gcloud therefore split one script into two arguments. Bash reported
an incomplete conditional and exited before invoking the assembled
`run-stage` command.

Exact known-name checks found no prepare stage-start, prepare stage receipt,
panel execution manifest, or execution authority. Only generation-pinned
image-evidence materialization could run, on the execution's ephemeral
in-memory volume. Consequently v1 performed:

- zero prepare/science stages;
- zero T230 slate or verifier computations;
- zero benchmark computations;
- zero historical-outcome reads; and
- zero realized-score computations.

The durable v1 prepare launch request explicitly sets
`automatic_retry_licensed=false`, `relaunch_allowed=false`, attempt zero, and
consumption even when the execution response is ambiguous or failed. The
operator correctly refused to launch again. V1 remains retained as terminal
failure evidence and must not be modified.

## V2 repair and identity

V2 uses:

- run ID `20260825-foundry-t230-production-v2`;
- output prefix
  `gs://nfl-predictions-503414-corpus-parametric/research/corpus-parametric-research/t230/20260825-foundry-t230-production-v2/`;
- prefreeze prefix
  `gs://nfl-predictions-503414-corpus-parametric/research/corpus-parametric-research/t230-prefreeze/20260825-foundry-t230-production-v2/`; and
- image tag family
  `foundry-t230-production-v2-<source-commit>-<candidate-build-id>`.

V2 removes dynamic delimiter encoding from both the runtime argument list and
the environment dictionary. It writes one mode-0600 temporary JSON
`--flags-file` whose typed values are exactly
`{"--args":["-ceu",<complete payload>],"--update-env-vars":{...}}`.
Gcloud therefore receives the list and dictionary as typed values rather than
reparsing punctuation in either one. Environment keys are syntax-checked and
duplicate keys fail locally. The file is removed immediately after the gcloud
call. A focused regression invokes the production builder, requires exact
argument bytes and the complete environment map—including hostile `~`, comma,
pipe, `@sha256:`, embedded `=` and newline values—and proves the literal `=~`
survives. It also demonstrates that the old v1 encoding yields three
arguments.

Because the run ID, prefixes, launcher, source snapshot, source commit, image
evidence, release gate and transport contract are mutually bound, v2 requires
a fresh candidate D. Reusing the v1 digest or gate would violate the transport
contract even though the scientific laws are unchanged.

## Required execution sequence

1. Focused-validate the repaired source, exact G0 replay and argument
   round-trip law.
2. Commit and push one exact source S2.
3. Build a fresh candidate D2 from S2 and require its own real outcome-blind
   Rule-1 smoke and terminal candidate success.
4. Release the same D2 without rebuilding it; require v2 image evidence,
   prefreeze gate and transport contract.
5. Bootstrap into a new empty local v2 run directory.
6. Configure the same two fixed jobs and launch v2 prepare exactly once.
7. Exact-describe that execution and require two arguments, successful
   completion and the durable execution authority.
8. Run the ordinal-zero benchmark. Reuse its worker if the compute release
   permits the fixed two-lane panel.
9. Complete and finalize all 54 slates before freezing the downstream Core
   catalog.
10. Only after the complete outcome-blind catalog closes may the separately
    governed historical outcome lease and one-read score path begin.

No IAM census, source-lane rebuild, Neo4j/UI work, or realized-outcome access
is part of this restart.
