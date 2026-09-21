# CI step 2: five decisions, not 137 failures

Step 1 is done (`460b4743`): the 15 runtime-pinned corpus modules now skip with
the mismatch named, removing **184** of 365. This is the remainder, and it is
far smaller than the failure count suggests — **~137 failures collapse to about
five root causes**, because one drifted pin fails many tests at once.

Each needs the same binary decision from whoever owns the chain: **re-freeze the
manifest deliberately, or retire the chain as superseded.** Neither is ours to
take. Re-freezing someone else's chain silently is the exact failure CLAUDE.md's
frozen-chain rules exist to prevent.

| # | root cause | failures | modules |
|---|---|---|---|
| 1 | `A7 committed Cloud Build contract differs` | **40** | `test_finish_a7_select_ladder.py` (39), `test_recover_a7_v2_build_gate_preclaim.py` (1) |
| 2 | `EffectivePolicyInventoryError: frozen source SHA-256 differs` | **20** | `test_prospective_prelock_lineage_shadow_v2.py` (9), `test_corpus_legal_feasibility.py` (7), `test_corpus_parametric_snapshot.py` (4) |
| 3 | `EvidenceGraphError: artifact SHA-256 differs` | **18** | `test_evidence_knowledge_graph.py` |
| 4 | `composite executable implementation identity drifted` | **10** | `test_corpus_composite_retrieval_laws.py` |
| 5 | A7-v2 source lineage sha mismatch | **8** | `test_validate_a7_v2_source_lineage_extension.py` |

**Item 2 is the highest leverage:** one frozen source in
`effective_policy_rule_inventory` has drifted, and it fails 20 tests across
three unrelated modules. One decision clears all three.

**Item 3 is already diagnosed and needs no investigation.** Five of the 25
pinned artifacts have drifted, all live production modules, and **every pinned
version is still recoverable from git** — commits listed in
`reports/2026-09-21-reply-to-generator-arm-plan.md` §4. Our recommendation there
stands: record the commit beside each sha and resolve the pinned blob at that
commit rather than hashing the working tree, which makes the graph permanently
verifiable instead of failing on every legitimate code change. Do **not** re-pin
to head — that asserts today's code produced August's evidence.

## Not step 2: two of these were CI configuration, and are fixed

Worth separating, because they looked like chain drift and were not.

**~22 "tracked read failed" errors were a shallow clone.** Several chains prove
source identity by reading tracked git objects at pinned commits
(`git show <sha>:src/...`). `actions/checkout@v4` defaults to `fetch-depth: 1`,
where those commits do not exist, so the reads failed with exit 128. Verified:
commit `93bca249…` is present in full history and absent from a depth-1 clone.
Fixed by setting `fetch-depth: 0`.

**One chain records an absolute path to a single workstation.**
`corpus_r6_player_catalog_fixed_g0_terminal_recovery_v1.FOCUSED_TEST_COMMAND`
pins `/home/erich/projects/nfl-predictions/.venv/bin/python`. That command can
only run on one machine, so the chain is not reproducible anywhere else — a
portability defect in the frozen artifact, not in the test asserting it.
Changing it alters a recorded identity, so it is **your call**, but it should
probably be part of whichever decision you take on that chain. Flagging it
because the operator has asked that nothing depend on this particular disk.

## What is left after all of this

| bucket | count | owner |
|---|---|---|
| runtime-pinned chains | 184 | **done** — skipped with reason (step 1) |
| shallow-clone tracked reads | ~22 | **done** — `fetch-depth: 0` |
| the five decisions above | ~137 | **you** |
| real defects in non-research modules | 12 | **done** — fixed 2026-09-21 |
| research-chain assertions | ~28 | you, once the five above stop masking them |
| other | 4 | individual |

After your five decisions, CI should report roughly 30 failures instead of 365 —
and a *new* one would finally be visible, which is the entire point. The way
`test_bq_load.py` sat silently broken for a day is that a genuine regression had
363 other failures to hide behind.

---

## CORRECTION (same day): do not take these decisions until CI has run once with `fetch-depth: 0`

The five-item table above over-assigns work to you. Two of those chains read
tracked git objects, so some of their failures are the shallow-clone artifact —
already fixed — rather than drift.

**Confirmed a clone artifact: item 5, `validate_a7_v2_source_lineage_extension`
(8 failures).** It conflates "cannot read" with "does not match":

```python
def _git_blob(root, commit, relative):
    result = _git(root, "show", f"{commit}:{relative}")
    if result.returncode == 0:
        return result.stdout
    return None                      # <- shallow miss becomes None ...
```

…and the caller then reports a **sha mismatch**. Likewise `_require_ancestry`
raises `"A7 lineage ancestry differs"` when `merge-base` merely fails, which in
a depth-1 clone it always does. So in CI this chain reported *differs* for what
was actually *absent*. Nothing had drifted.

That is a real diagnostic defect in the chain, independent of CI: a check that
names the wrong cause sends the reader to re-freeze a manifest that was never
wrong. `_resolve_commit` in the same file gets it right — it says *"exact commit
is unavailable"* — so the honest wording already exists a few lines up.

**Uncertain: item 1, `finish_a7_select_ladder` (39 failures).** Its `_git_blob`
uses `check=True` and `_git_archive_sha` raises `"archive cannot be
reconstructed"`, so a clone miss surfaces honestly there. But the observed
message is `"A7 committed Cloud Build contract differs"`, which is a different
comparison. Some of those 39 may be genuine. Not claiming either way without
evidence.

**Unaffected, still genuinely yours:** items 2 (`effective_policy_rule_inventory`,
20), 3 (evidence graph, 18) and 4 (`corpus_composite_retrieval_laws`, 10) — none
of those three shells out to git; they hash working-tree files, so their drift
is real.

### Practical recommendation

**Let one CI run complete on `fetch-depth: 0` before deciding anything.** At
least 8 of the 137 disappear, plausibly up to 47, and re-freezing a manifest
that was never drifted would be worse than leaving it: it would bake a CI
configuration artifact into a frozen identity permanently.

The verified mechanism, reproduced locally:

```
depth-1 clone : git show 93bca249…:src/… -> FAILED exit 128   (matches CI exactly)
full clone    : git show 93bca249…:src/… -> SUCCEEDED
```
