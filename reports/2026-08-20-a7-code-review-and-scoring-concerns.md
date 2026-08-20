# Code review: A7 tail-ladder experiment, plus scoring-goal concerns

**Date:** 2026-08-20. **Reviewer role:** code review only (no code
changes made). **Reviewed:** commit `c1dcf4f` "Add proof-gated A7 tail
ladder experiment" (~14k lines across the ladder module, runner, freeze,
cloud chain, finisher, five test files, plus two production files) and
the frozen protocol
`reports/2026-08-20-a7-select-ladder-incumbent-pool-protocol.md`.

## Verdict up front

The engineering is strong and the protocol is the most rigorous in the
repository. All A7 test suites pass on my machine, as do the production
parity guards (`test_lever_registry`, `test_sbi` golden hashes,
`test_select_ladder`). I found **no correctness defect** in the
production-path changes and **no outcome-leakage path** in the
preregistration. My concerns are about *what the arm can prove* and
*what a null would mean*, plus two robustness items.

Concerns are ordered by how much they should change what the other
agent does next.

---

## 1. Arithmetic ceiling: selection alone cannot reach 194 (highest)

This is the most important thing in this review and it is not an
opinion.

`S` (selected-book best) is bounded above by `C` (best candidate in the
pool). On the incumbent pool the registered means are:

| Quantity | Mean |
|---|---|
| Selected book, control (S) | 178.57 |
| Pool ceiling, control (C) | 187.58 |
| Operator target | **194** |

A **perfect** selector — one that always picked the pool's best lineup —
would score 187.58. That is **6.4 points short of the target**, and it
is an unreachable upper bound, not a plan. The entire remaining
selection lane, A7 included, is competing for at most **+9.0 mean**, and
realistically a small fraction of it.

**Implication for planning:** A7 is worth running, but it cannot close
the gap to 194 and should not be described as the path there. Reaching
194 requires the *pool* to change — better candidates or a better
simulation law — not a better selection rule on the current pool. I
would state this explicitly in the A7 result document, whatever the
outcome, so a positive result does not get over-read as progress toward
the target.

## 2. The frozen ladder is shoulder-heavy, not tail-aggressive

The frozen spec is `170:10,180:10,187:7,194:7,200:6,210:10`, with
cumulative utility 10/20/27/34/40/50 and a hard cap at 210.

| Region | Utility units | Share |
|---|---|---|
| Up to 194 | 34 | **68%** |
| 194 → 210 | 16 | 32% |
| Above 210 | 0 | 0% |

The motivating diagnosis was that binary coverage at 194 under-values
the extreme tail. This ladder puts **68% of its utility at or below
194** and adds two entirely new rungs (170/180 = 40% of total utility)
in a region the incumbent ignores. It is a conservative reweighting, and
in the low rungs it rewards *breadth at scores that cannot win*.

For a maximum-of-book objective, covering an additional world at 170
contributes essentially nothing to the outcome we care about; for the
actual Millionaire deployment (four entries) it contributes even less.
There is a plausible mechanism by which the low rungs actively pull the
book away from the top end. The protocol's 194/200 non-inferiority
guards are exactly the right protection against that, and I am glad they
are there.

To be clear about my own position: the **cap at 210 is correct** — I
recommended it, because 230/240 are ~1 and ~0 events in 54 slates and
weighting them would be fitting to the region where the simulation law
is least trustworthy. My concern is the *bottom* of the ladder, not the
top.

**Recommendation (no protocol change):** do not amend the frozen spec —
that would be post-hoc tuning. Instead, pre-commit in writing to the
narrow reading of a null: *"this specific shoulder-heavy dose did not
help"*, **not** "objective alignment is closed." The distinction matters
because a null here would otherwise close the most promising remaining
selection idea on the basis of a dose that never strongly expressed it.

## 3. N4/N14 are non-gating, but N4 is what we actually enter

The protocol reports the `[:4]` and `[:14]` prefixes and states they
"can never rescue, veto, reweight, or change the S80 disposition."
Scientifically this is defensible — they are prefixes of an 80-optimized
order, not optimized books.

Operationally there is a hazard. The standing entry mix in `CLAUDE.md`
is **4 Millionaire entries + 3 qualifiers × 14**. An arm that improves
the max of 80 while degrading the max of 4 would be recorded as
`historical-positive-phase-s` and would be operationally harmful in the
contest we actually enter.

**Recommendation (respects the frozen gates):** keep N4/N14 non-gating
for the disposition, but pre-commit that a positive S80 combined with a
negative N4 direction (a) is flagged prominently in the result document,
and (b) blocks the downstream selector-transfer test until reconciled.
That adds no gate to this arm and prevents an operationally misleading
"win" from propagating.

## 4. Evaluation-path complexity is a real risk here

`scripts/finish_a7_select_ladder.py` is **5,016 lines with 100
functions**, backed by 41 tests. The tests are thorough on failure modes
(unknown fields, inventory binding, replay rejection), which is good.

The specific risk is this repository's own history: the fade mislabel,
the GREEN2 env typo, and the TDLEDGER season-pooling defect were all
caught by *instrument audit*, never by the panel number — and all three
lived in evaluation/analysis code, not generation code. A 5,000-line
finisher is a large surface for exactly that failure mode, and its
output is the thing that decides the arm.

**Recommendations, in order of value:**
1. **Known-answer end-to-end fixture.** I could not find a test that
   drives the finisher over a synthetic corpus whose disposition is
   known by construction (e.g. a fabricated 54-slate set where the
   treatment is designed to be exactly `+2` slates at 194 and the
   expected branch is `historical-positive-phase-s`). Failure-mode tests
   confirm it rejects bad input; a known-answer test confirms it
   computes the *right* number from good input.
2. **Independent recomputation of the two co-primaries.** Recompute the
   paired mean delta and the threshold grid from the raw per-slate
   receipts with a ~30-line script that shares no code with the
   finisher, and require exact agreement before the disposition is
   recorded. This is cheap and would have caught every one of the three
   historical defects named above.

## 5. Smaller notes

- **Production changes are good.** `SELECT_LADDER: ""` pinned in
  `engine_environment`, mutual exclusion with `SELECT_LSE`, NaN/inf
  rejection, duplicate-threshold and repeated-mean detection, and the
  negative-totals guard on the mean term are all correct hardening. The
  golden-hash parity tests still pass, so the money path is unchanged.
- **Integer-exact R3 comparison** via cross-multiplication rather than
  float division is the right call and worth keeping as a pattern.
- **The R3 realism falsifier answers my earlier review note** about
  needing a realism guard alongside score, and the support floor being
  frozen independently of the observed difference is correctly done.
- **Verify the ladder gain function against the utility definition once
  more before launch.** `_world_ladder_gain` credits
  `weight * (candidate >= t) & (previous < t)`, which equals
  `u(max(prev, cand)) - u(prev)` only because the ladder is a
  non-decreasing step function; that is true here, but the invariant is
  implicit. A single test asserting
  `gain == u(max(prev,cand)) - u(prev)` over random inputs would pin it.

## 6. On the scoring goal, plainly

Recent completed arms: boom-deep supply **null** at the book (+1.34,
p=0.49); selector algorithm **closed** (greedy within 0.134% of exact);
stack relaxation **negative** (−0.98); ownership template **blocked**
(own_est has 10.2% precision on chalk). A7 is competing for a slice of a
9-point ceiling.

The honest read of the evidence set is that the binding constraint is
the **simulation law**, not selection or construction: it over-couples
generic teammate booms up to five-fold and under-couples QB→WR, its deep
world optima carry ~3× the never-realized mass of real winning rosters,
and the stack-relaxation negative is most parsimoniously explained by
the mandates hand-correcting that defect. I would prioritize the
dependence repair ahead of further selection work, and treat A7 as a
cheap parallel probe rather than the main line.

None of this argues against running A7 — it is built, frozen, and
scientifically clean. It argues against expecting it to move the
program's headline number.

---

## Addendum (2026-08-20, same day): the A7 smoke failure is a false failure

The A7 preflight smoke died with
`ERROR: A7 smoke execution metadata malformed` (execution
`atlas-minimal-c-s2023-w1-v1-6qfpk`,
log `~/nfl-panels/a7-select-ladder-smoke.log`). I reviewed it rather
than touching it. **The execution was not malformed and nothing was
actually wrong with the run.**

### Diagnosis

Both the launcher and the watcher parse execution state with the same
line:

```python
rows = [row for row in value.get("status", {}).get("conditions", [])
        if row.get("type") == "Completed"]
print(rows[0].get("status", "") if len(rows) == 1 else "Malformed")
```

- `scripts/cloud_a7_select_ladder.sh:349`
- `scripts/watch_a7_select_ladder_queue.sh:250`

A freshly created Cloud Run execution does not immediately publish its
`conditions` array. In that window `len(rows) == 0`, the parser emits
`Malformed`, and the caller's `*)` branch treats it as fatal. Polling
the same execution now returns exactly one `Completed` row with
`status=Unknown` — i.e. healthy and still running. The gate fired on a
transient absence, not a defect.

`len(rows) == 0` (not yet published) and `len(rows) > 1` (genuinely
contradictory metadata) are different conditions and must not share a
branch. Only the second is malformation.

### Why this matters beyond the smoke

This is the frozen-chain defect class from `CLAUDE.md` — a fail-closed
gate tripping on a *representation* rather than a content defect — and
rule 4 requires sweeping the whole class rather than fixing one site.
Both consumers carry the identical pattern, and the watcher's failure is
worse than the launcher's: its message is
`"A7 execution metadata malformed; lease held"`, so the same transient
would **strand the historical-outcome lease** and block every subsequent
scored arm until someone abandons it by hand. On a 54-cell grid the
chance of hitting one unpopulated poll is not small.

### Suggested fix (for the owning agent — I made no code change)

Treat empty conditions as "not ready" and reserve `Malformed` for real
contradictions, at both sites:

```python
rows = [row for row in value.get("status", {}).get("conditions", [])
        if row.get("type") == "Completed"]
if not rows:
    print("")          # not yet published -> existing Unknown|"" retry branch
elif len(rows) == 1:
    print(rows[0].get("status", ""))
else:
    print("Malformed")  # contradictory metadata: genuinely fatal
```

Worth adding a regression test that feeds `{"status": {}}` and
`{"status": {"conditions": []}}` and asserts the retry branch, plus a
two-`Completed`-row fixture that asserts the fatal branch. The existing
suites did not catch this because they exercise well-formed metadata.

### One process note

The smoke did its job: it failed before the real grid, and it cost
nothing. That is the rule-1 reality smoke working as designed. The
concern is only that the failure mode would have recurred mid-grid with
the lease held.

---

## Correction after terminal state (2026-08-20 10:11 CDT)

The addendum above was correct about the **first poll** but wrong about the
eventual execution result. The empty `conditions` array was a transient
polling/parser defect. The same execution later became terminal with exactly
one `Completed=False` condition and `failedCount=1`; it therefore must not be
harvested as a successful smoke or relaunched.

The terminal traceback is a separate, outcome-blind input-contract failure:

```text
RuntimeError: A7 source query contains a non-finite value
```

It occurred while constructing the canonical `player_source` query receipt.
An independent read-only census of the frozen `phase-s-cbwu-54` player corpus
found 30,044 rows, including 439 SQL `NULL` values in `mean_projection`, no
non-null NaN/Inf projections, and no null salary/name/position/team/opponent/
game fields. Pandas represents those SQL nulls as NaN, while the downstream
CBWU lineup reconstruction already maps a non-finite projection to `0.0`.
The A7 receipt rejected that representation before reaching the reconstruction.

Cloud evidence at the terminal boundary:

- execution `atlas-minimal-c-s2023-w1-v1-6qfpk`, completion
  `2026-08-20T15:00:41.442723Z`;
- exact task result: zero successes, one failure, zero retries by the frozen
  `maxRetries=0` contract;
- the A7 prefix contains only the 1,026-byte create-once job claim—no smoke,
  support, freeze, or historical-result object;
- the historical-outcome lease is absent; no realized-score query or
  historical look occurred.

Accordingly, v1 is `invalid-outcome-blind-preflight-closed-no-retry`. The
polling parser should be fixed before a future cloud arm, but that fix cannot
rescue this execution. Normalizing the player-source query would change a
bound input receipt and would require a fresh A7 protocol/run/build/preflight.
That repair is not the current priority: the dependence-law mechanism and the
prepared exact-one stack arm are closer to the winner-structure question.
