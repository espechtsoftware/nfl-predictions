# Review: ATLAS CBC invalidation, integrality repair and historical-score protocol

Date: 2026-08-16. **No code was changed. No outcome was queried.**

Covers the changes since the deployment evidence index: the repair2 CBC
invalidation, the native-CBC diagnostic protocol, the interaction-integrality
proof and its commit `bba24a7`, the pair-reach amendment, and the historical
realized-score diagnostic protocol.

**One material concern (§1), one protocol asymmetry (§4), and two
confirmations.**

---

## 1. The OOM hypothesis was dismissed on evidence that does not support the dismissal

This is the item I would act on before launching the CBC diagnostic.

[2026-08-16-atlas-repair2-cbc-invalidation.md](reports/2026-08-16-atlas-repair2-cbc-invalidation.md)
states: *"Cloud Monitoring does not support an OOM explanation. One-minute p99
memory utilization for the failed Week 15 and Week 16 jobs peaked at
approximately 0.660 and 0.740 of the 4 GiB allocation."*

Three things argue the opposite way.

**1.1 The failures are coincident with an 8× memory reduction.**

| job | CPU | memory | source |
|---|---:|---:|---|
| unsharded MVP | 8 | **32 GiB** | [cloud_atlas_matched_diversity_mvp.sh:78](scripts/cloud_atlas_matched_diversity_mvp.sh#L78) |
| **sharded repair2 grid** | **1** | **4 GiB** | [cloud_atlas_matched_diversity_shards.sh:86](scripts/cloud_atlas_matched_diversity_shards.sh#L86) |
| money worlds | 4 | 16 GiB | [cloud_atlas_money_worlds.sh:79](scripts/cloud_atlas_money_worlds.sh#L79) |
| money transfer / world ranking | 8 | 32 GiB | [cloud_atlas_money_transfer.sh:77](scripts/cloud_atlas_money_transfer.sh#L77) |

The repair2 image is code `60f296f` — *"Shard ATLAS MVP by slate"*, the commit
that introduced the shard runner. **repair2 is the first ATLAS grid to run
interaction-heavy MILPs at 4 GiB**, and it is the first to throw
`PulpSolverError`. Every ATLAS job that has completed ran at 16–32 GiB.

This is also the project's own documented failure mode: per CLAUDE.md, expanded
panels hit the 12 GiB cap and `scripts/baseline_panel.sh` was raised to 16 GiB
for exactly this reason.

**1.2 p99 at 0.740 of the cap is evidence *for* memory pressure, not against
it.** Cloud Monitoring samples at one-minute granularity. CBC's branch-and-bound
tree grows in bursts as it stores active nodes; a sub-minute allocation spike
from 74% to the cap is entirely invisible at that resolution. A job sitting at
three-quarters of its limit is near the edge, not comfortably clear of it.

**1.3 The described symptom is the classic cgroup OOM-kill signature.** The
document notes *"the Python container itself remained alive long enough to raise
and log the child CBC process's nonzero return"* as though it argued against
OOM. It is the opposite: the cgroup OOM killer selects the largest process — the
CBC child — and the parent survives to observe a nonzero exit. A parent that
survives while its child dies is precisely what OOM looks like from inside the
container.

**1.4 Week 7 remains unexplained and is excluded.** Week 7 failed near 0.240
utilization, and its retry was cancelled mid-flight. The diagnostic runs only
Weeks 15 and 16. If Week 7's cause differs, a clean two-cell result does not
cover it.

**Suggestion:** treat memory as the leading hypothesis, not a ruled-out one, and
say so in the diagnostic's decision rule.

## 2. The diagnostic as written cannot distinguish OOM from a model defect

This follows directly and is the cheapest fix in this review.

[run_atlas_cbc_failure_diagnostic.py:86-87](scripts/run_atlas_cbc_failure_diagnostic.py#L86-L87)
persists only `exception_type` and `exception_message`. PuLP raises
`PulpSolverError` with a message of the form *"Pulp: Error while executing
&lt;path to cbc&gt;"* — **it does not carry the child's return code.** So an
OOM-killed CBC (`returncode == -9`, SIGKILL) and a model/parser defect produce
an identical receipt.

Worse, `keepFiles=True` + `logPath` does not rescue this: a SIGKILL'd CBC never
flushes its final log lines, so the diagnostic would find a truncated or empty
native log and land in the *"evidence is missing or inconsistent →
inconclusive"* branch — burning the run and leaving the cause unknown.

**Suggestion — add three mechanical fields, all score-free and all within the
protocol's permitted receipt class (identity, terminal status, exception,
artifact metadata):**

1. **the CBC child's return code and terminating signal** — `-9` settles it
   immediately;
2. **`/sys/fs/cgroup/memory.events`, specifically the `oom_kill` counter**, read
   before and after each solve. A nonzero increment is definitive proof of an
   OOM kill regardless of what one-minute p99 reported. Cloud Run gen2 exposes
   cgroup v2;
3. **`memory.peak`** (or `memory.max_usage_in_bytes`), which gives the true
   high-water mark rather than a sampled percentile.

None of these touch lineups, candidates, selector output or outcomes.

## 3. The decision rule can misclassify a resource failure as transient

The protocol's second branch is: *"If both diagnostics complete R0 successfully,
classify repair2 as a transient child-process reliability failure and freeze
repair3 with one predeclared mechanical retry per cell."*

Memory pressure is **load-dependent and nondeterministic**. Two cells rerun in
isolation, with no neighbours competing for the node, may well succeed — and
that success would be read as "transient." repair3 would then launch all 54
slates at 4 GiB with one retry per cell, and fail again at scale, costing
another full grid.

**Suggestion:** make the branch conditional on the memory evidence from §2. If
`oom_kill` is zero and peak memory is well clear of the cap, "transient" is a
sound reading. If either indicator shows pressure, the correct repair3 is a
resource change — which is also the cheapest possible repair and requires no new
science. Given every completed ATLAS job ran at 16–32 GiB, raising the shards to
16 GiB is defensible on precedent alone.

## 4. The historical-score signal rule is not tail-first, and it is asymmetric

The rule in
[2026-08-16-atlas-historical-score-diagnostic-protocol.md](reports/2026-08-16-atlas-historical-score-diagnostic-protocol.md)
is titled *"Frozen tail-first signal rule"*, but it is not the standing law.

| | standing law | this protocol |
|---|---|---|
| thresholds examined | `240,230,220,210,200,194,187` | anchored at **200** |
| decision | first nonzero difference | +2 slates at 200 |
| 210 | decision threshold | non-decline guard |
| **220 / 230 / 240** | **decision thresholds** | **"authoritative context"** — no decision role |

**The asymmetry is the concrete defect.** Condition 1 requires +2 slates at 200;
condition 2 protects 210; condition 3 protects `C` at 200. **Nothing protects
220, 230 or 240.** As written, ATLAS could **lose a 230-point slate** and still
record `historical-tail-signal-positive` — under an objective whose entire
premise is maximizing the single best score.

To be fair to the change: the standing law has a real pathology that this rule
was clearly written to fix. On 54 slates with control counts of 0 at 240 and 1
at 230, "first nonzero difference" lets a single lucky slate decide everything.
The protocol's `single-event-extreme-tail` label is a genuine improvement and
should be kept.

**Suggestion:** keep the 200 anchor and the single-event label, but **add a
symmetric guard — no decline at 220 or above.** It costs nothing if ATLAS is
neutral up there, which is the predeclared expectation given CBWU-OI moved
194–210 and left 220+ exactly tied. It only binds in the case that should
actually block a positive verdict.

One further note on framing. The threshold anchor was chosen **after** CBWU-OI
established on these same 54 slates that gains sit at 194–210 and vanish above
220. The protocol is properly frozen before *ATLAS's* result, so this is not
post-hoc tuning — but it is decision-rule selection informed by prior results on
the same panel, and the deviation from the standing law should be stated and
justified in the protocol rather than carried under a heading that says
"tail-first."

## 5. Confirmed: the integrality proof is correct

I verified this rather than taking it on the argument, because it changes a
shared optimizer.

- The lower-bound constraint **is present** —
  [lineup.py:171-173](src/nfl_dfs/optimizer/lineup.py#L171-L173) adds
  `y >= sum(x_i) - (|T|-1)` alongside the `y <= x_i` upper bounds. With both
  families, `y` is uniquely determined at every integer `x`: all members
  selected forces `y = 1`, any member absent forces `y = 0`. Integrality is
  redundant. The proof holds.
- Weights are validated finite and non-negative at
  [lineup.py:149-150](src/nfl_dfs/optimizer/lineup.py#L149-L150), so the
  argument does not depend on sign.
- **No code reads `y`'s solved value.**
  [`_interaction_value`](src/nfl_dfs/analysis/atlas_matched_diversity.py#L378)
  recomputes interaction weight from the roster set, so a continuous `0.999…`
  cannot leak into a comparison. This was my main practical worry and it does
  not apply.
- **Tie-breaking is safe**, which was my second worry. Stage two's exact integer
  optimum is unchanged by the proof, and stage three re-solves against a
  deterministic `stable_identity_objective` under that floor
  ([atlas_matched_diversity.py:514-525](src/nfl_dfs/analysis/atlas_matched_diversity.py#L514-L525)).
  A different stage-two argmax under ties therefore cannot propagate.

The boundary is also right: interactions are used only by
`atlas_matched_diversity.py`, so with `interaction_maps` empty no `y` variables
are created and the production path is genuinely untouched.

**One caution.** Fewer integer variables shrinks the branch-and-bound tree, so
this will *reduce* memory — which means adopting it as repair3 might make the
CBC failures disappear **without the cause ever being identified.** If §1 is
right, that is a mask, not a fix, and the same wall returns on the next
interaction-heavier grid. Settle the memory question first; the requirement to
*"validate exact roster parity where the old solver completes"* should be a hard
gate either way.

## 6. Confirmed: the pair-reach floor and the parity amendment

- **Pair-reach floor** — the amendment adopts the breadth floor and states the
  prior explicitly. The aggregate-mean form (`mean R2 >= mean R1`) rather than
  per-slate is the right call for the reason given: slate-size variation
  shouldn't read as a feasibility failure. Naming the Boolean
  `candidate_pair_reach_retains_100pct` and requiring it in the strict finisher
  closes the usual gap where a gate is computed but not enforced.
- **Source parity** — the `72,520 → 68,199` row correction is exactly the class
  of defect that has invalidated arms here before, caught by two independent
  sources. The `1e-9` tolerance against a `5.68e-14` observed maximum is sound
  for `FLOAT` re-association.
- **Pricing is clean.** The MVP prices tuples by leave-one-seed-out robust
  support, explicitly excluding realized outcomes and the priced seed's own
  block. No outcome leakage.

---

## 7. Summary

| # | item | priority |
|---|---|---|
| 1 | **Capture CBC child return code + cgroup `oom_kill` and `memory.peak`** in the diagnostic — as written it cannot tell OOM from a model defect, and a SIGKILL'd CBC yields an empty log and an "inconclusive" verdict | **highest — before launch** |
| 2 | **Treat memory as the leading hypothesis.** repair2 is the first ATLAS grid at 4 GiB (down from 32 GiB) and the first to fail; p99 0.740 and a surviving parent both point toward OOM, not away | **high** |
| 3 | **Gate the "transient" branch on that evidence**, or repair3 relaunches 54 slates into the same wall | high |
| 4 | **Add a no-decline guard at 220+** to the historical signal rule; as written a lost 230 slate still scores positive. Keep the 200 anchor and the single-event label, but state the deviation from the standing law | high |
| 5 | Include **Week 7** in the diagnostic or record why its 0.240 profile is out of scope | medium |
| 6 | Integrality proof **verified correct**; adopt only after the memory question is settled, with roster parity as a hard gate | — |

Nothing here blocks the running MVP repair. Items 1–3 are worth settling before
the CBC diagnostic launches, since that run is the one chance to observe the
failure cheaply.
