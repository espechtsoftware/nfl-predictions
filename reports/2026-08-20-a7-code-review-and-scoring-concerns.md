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

---

## Addendum 2 (2026-08-20): review of the A2a rank-factor-split census

Reviewed `0b43a07` (`research/a2a_rank_factor_split.py`, its runner, two
test suites, protocol `20260820-a2a-rank-factor-split-scorefree-v2`) and
the committed real-artifact smoke receipt. All A2a tests pass. This is
the lane I recommended prioritizing, and the mechanism is well chosen.

### What is right

The transform is a **rank remapping**: each player's new world-ordering
is computed from a residualized priority, then that player's own sorted
draws are reassigned along it (`out[row, order] = np.sort(values[row])`).
Because the result is a permutation of the player's own values, the
marginal distribution is preserved *exactly* — the smoke confirms
`exact_sorted_marginals=True` and `exact_q90_boom_counts=True`, with
`deterministic_repeat_exact=True`. Only the copula moves, which is
precisely the defect being repaired. Half-residualizing against the team
factor targets the generic over-coupling, and the one-hot QB→WR
allocation targets the under-coupled cell. Single frozen dose, no grid:
protocol-compliant.

### Concern A — undisclosed coverage gap (should be fixed before the remeasurement)

The transform only runs on groups with **exactly one QB and at least two
WRs**; everything else hits `continue` and keeps the unrepaired law. The
smoke shows the scale: **161 of 221 eligible rows transformed across 22
groups**. Twenty-two of those unchanged rows are QBs (skipped by design,
they are the anchor), which leaves roughly forty non-QB eligible rows
sitting in groups that received no repair at all.

The receipt reports `eligible_groups`, `eligible_rows`,
`transformed_rows` — but **no count of skipped groups and no skip
reason**. That matters because DraftKings routinely lists a backup QB,
so `len(qbs) != 1` is not a rare edge case; it may systematically
exclude particular teams every week.

Scientifically this is the risk: the remeasurement compares *aggregate*
co-boom cells. If ~15% of teams retain the over-coupled law, any real
improvement is diluted toward the null, and a failed gate could not be
distinguished from a coverage artifact.

**Recommendation:** add a skipped-group census (count plus reason —
`qb_count != 1`, `wr_count < 2`) to the receipt, and disclose the
covered fraction, *before* the outcome-bearing remeasurement is read.
This is an accounting addition, not a mechanism change, so it does not
disturb the frozen scientific law.

### Concern B — the one-hot rule concentrates on the already-hot WR

`competitive_wr_assignment` selects `argmax` of the canonical WR ranks,
so the QB-linked boost goes to the WR who was *already* highest in that
world. Directionally this is right twice over: it raises QB–WR (measured
under-coupled at −0.261) and, because only one WR is boosted per world,
it should lower WR–WR (measured over-coupled at +0.691).

The risk is overshoot. Amplifying the already-leading WR is a
concentrating rather than redistributing rule, and with
`QB_WR_ALLOCATION = 1.0` applied to a centered rank it is not a small
nudge. **Recommendation:** pre-commit that crossing QB–WR *past* its
realized target (over-coupling a previously under-coupled cell) is
recorded as a miss, not a pass. Otherwise a treatment that lands at, say,
+0.30 could be read as "moved in the right direction" when it has simply
traded one mis-specification for its mirror image.

### Concern C — dose sufficiency, and what to do if it undershoots

`GENERIC_ATTENUATION = 0.5` removes half the team factor from the
priority. The defects it must move are large: RB–RB +1.49, TE–TE +1.34,
multiplicity ≥4 +1.65. Whether half-residualization moves log-ratios of
that size into a ±0.14 equivalence band is genuinely unknown, and the
census is the right way to find out.

The important part is the response to an undershoot: it must be a **new
frozen protocol**, never a dose bump re-run against the same corpus.
Worth stating that in the protocol now, while no result has been seen.

### Concern D — TE and RB get only the generic term

The mechanism has a QB-specific term for WRs only. TEs and RBs receive
attenuation but no re-coupling, so QB–TE (currently "inconclusive",
+0.239) and QB–RB (+1.167) are repaired only by removing generic mass.
That is a defensible first dose and I would not add terms now — but the
result document should say so explicitly, so a partial success is not
read as a full law repair.

### Summary for this lane

No defect found; the mechanism, the marginal-preservation proof, and the
determinism checks are all sound. Concern A is the one I would act on
before the remeasurement, because it is cheap, it is pure accounting,
and without it a null is ambiguous between "mechanism too weak" and
"mechanism never touched enough of the slate."

---

## Addendum 3 (2026-08-20): A2a census result — direction passed, magnitude did not

The A2a score-free census completed
(`a2a-scorefree-mechanism-passes`, `historical_remeasurement_licensed=true`,
result `86f72b40…`, 54x5 grid complete, all mechanical invariants exact:
marginals preserved, QB rows bit-exact, deterministic repeat, one-hot
exact). The mechanism is real and non-vacuous: 35,855 rows transformed
across 5,205 groups.

**Every one of the nine cells moved in the correct direction, and the
gate checks direction only.** Its sixteen conditions are all of the form
`*_no_greater`, `*_strictly_less`, `*_strictly_greater`. None constrains
*how far* a cell moves. On magnitude the picture is materially worse.

### Where the treatment law lands

Combining each cell's census movement with its prior remeasurement
position (both use the same `_conditional_lift` functional; multiplicity
cells use the same rate):

| Cell | prior log(sim/real) | census Δlog | implied new | band | status |
|---|---|---|---|---|---|
| multiplicity ≥2 | +0.259 | −0.008 | +0.251 | 0.095 | barely moved |
| multiplicity ≥3 | +0.744 | −0.705 | **+0.038** | 0.140 | fixed |
| multiplicity ≥4 | +1.648 | −1.520 | **+0.128** | 0.223 | fixed |
| QB–WR | −0.261 | +0.245 | **−0.016** | 0.140 | fixed, no overshoot |
| QB–RB | +1.167 | −1.036 | **+0.131** | 0.140 | fixed |
| RB–RB | +1.488 | −0.784 | +0.704 | 0.140 | still off |
| TE–TE | +1.343 | −0.639 | +0.704 | 0.140 | still off |
| **QB–TE** | +0.239 | −1.153 | **−0.913** | 0.140 | **OVERSHOOT** |
| **WR–WR** | +0.691 | −1.842 | **−1.150** | 0.140 | **OVERSHOOT** |

Four cells land in band — including QB–WR, the cell the whole repair was
aimed at, which lands almost exactly on target (−0.016). That is a
genuine success and the mechanism deserves credit for it.

But two cells cross into the mirror-image defect:

- **WR–WR** was over-coupled at +0.691 and is now under-coupled at about
  **−1.150** — the absolute defect is *larger than before the repair*.
- **QB–TE** was the one cell the remeasurement classified
  **inconclusive** (+0.239, nearest to acceptable). It is now roughly
  **−0.913**, a large material miss that the repair created.

This is the overshoot I flagged in Addendum 2, Concern B. The one-hot
rule boosts the single already-highest WR per world, which mechanically
anti-correlates every other WR on the team; a −1.84 log-unit swing
against a +0.69 defect is far past the target. Concern D also played
out: TEs receive only generic attenuation, so TE–TE stayed off while
QB–TE lost its group factor with nothing re-coupling it.

**Caveat, stated plainly:** "implied new" adds a census movement measured
on the pre-lock Phase-S artifacts (with A2a's eligibility and flag rules)
to a prior measured on the final-served book. Same functional, different
populations, so these positions are indicative rather than exact — the
remeasurement produces the authoritative number. That said, the WR–WR
swing is so much larger than its target that overshoot is near-certain
regardless of population alignment.

### The recommendation, and why it is not panel mining

**Do not spend the outcome-bearing remeasurement on this dose.** It
consumes the historical-outcome lease and a one-shot to measure a law
that has traded two defects for two mirror-image defects, one of which
it manufactured in a previously acceptable cell.

The important point: **the score-free census is exactly where dose
iteration is legitimate.** No outcomes are read, no lease is held, and
no realized score is exposed — so adjusting `GENERIC_ATTENUATION` and
`QB_WR_ALLOCATION` against *this* instrument carries none of the
panel-mining risk that forbids dose sweeps on scored corpora. The
standing prohibition is on tuning against outcomes; it does not and
should not prevent tuning a mechanism against a score-free mechanical
census.

Concretely I would suggest, before any outcome-bearing step:

1. Add **magnitude conditions** to the gate — each cell's implied
   position must move toward its band without crossing it — and treat
   crossing as a fail rather than a pass.
2. **Soften the one-hot allocation.** A partial or rank-weighted
   allocation across WRs (rather than winner-take-all on the argmax)
   would raise QB–WR while doing far less violence to WR–WR. QB–WR
   currently lands at −0.016, so there is ample room to reduce the dose
   and still fix that cell.
3. **Protect QB–TE explicitly.** It was the healthiest cell and the
   repair broke it; it belongs in a protected set that must not be
   pushed past its band.
4. Consider a **position-specific attenuation** so RB–RB and TE–TE
   (+0.70 remaining) get more, while pairs already in band get less.

Only once the census shows all nine cells moving toward band without
crossings should the historical remeasurement be spent.

---

## Addendum 4 (2026-08-20, URGENT): the predicted watcher defect fired and the lease is stranded

The A2a outcome-bearing remeasurement launched
(`atlas-minimal-c-s2023-w1-v1-8cnxz`) and its watcher then died with:

```
A2A_REMEASUREMENT_OUTCOME state=Malformed execution=atlas-minimal-c-s2023-w1-v1-8cnxz
ERROR: A2a execution metadata malformed; lease held
```

**This is exactly the false failure diagnosed in Addendum 1, in the
sibling consumer, with the consequence I flagged there.** I verified the
facts rather than inferring them:

- The execution is **healthy and still running**: one `Completed`
  condition with `status=Unknown`, `runningCount=1`, and it is actively
  emitting `A2A_REMEASUREMENT_ARTIFACT_COMPLETE` lines (2023 W14/W15
  across blocks R0/R2/R4 as of this writing). Nothing is wrong with the
  work.
- The **historical-outcome lease is HELD** by the dead watcher
  (`acquired_at 2026-08-20T21:52:42Z`, run_id `20260820-a2a-…`,
  job `atlas-minimal-c-s2023-w1-v1`).

So the job will very likely run to completion and write its result,
while no watcher is left to harvest it, and the lease blocks every
subsequent scored arm until someone releases it by hand.

### Why this happened

Addendum 1 identified the parse at
`scripts/watch_a7_select_ladder_queue.sh:250` and
`scripts/cloud_a7_select_ladder.sh:349`:

```python
print(rows[0].get("status", "") if len(rows) == 1 else "Malformed")
```

An execution that has not yet published its `conditions` array yields
`len(rows) == 0` → `Malformed` → fatal. The A2a chain carries the same
pattern. `CLAUDE.md` frozen-chain rule 4 exists for precisely this: when
a fail-closed gate trips, sweep the entire defect class across sibling
consumers before rebuilding. The class was identified and published
before this launch; the sweep did not reach the A2a watcher.

### Remediation, in order (owning agent's call — I have changed nothing)

1. **Do not kill the execution.** It is healthy; let it finish and write
   its result object.
2. **Re-attach or hand-harvest** the result when the execution reaches
   terminal success, then release the lease through the normal
   `historical_outcome_lease.py release` path with the execution and
   completion receipts, so the release is receipted rather than
   abandoned.
3. If the execution instead ends non-terminal or the receipts do not
   validate, use the generation-matched `abandon` path (added
   2026-08-19) so the stale lease is archived with evidence rather than
   deleted.
4. **Then apply the Addendum-1 fix to every consumer**, not just A7:
   treat empty conditions as "not ready" and reserve `Malformed` for a
   genuine multi-row contradiction. Grep for the literal
   `len(rows) == 1 else "Malformed"` to find them all.

### Standing concern, restated

The remeasurement launched on the **unchanged dose**
(`GENERIC_ATTENUATION = 0.5`, `QB_WR_ALLOCATION = 1.0`), so Addendum 3
stands: this outcome-bearing run is being spent on a law whose census
shows WR–WR and QB–TE crossing into mirror-image defects. If the run
completes and is harvested, I would read the WR–WR and QB–TE cells
first: if they land materially negative as the census projects, the
correct disposition is that the dose is wrong, not that the mechanism
family is closed — and the re-dose belongs on the score-free census,
where iteration costs no outcome exposure.

---

## Addendum 5 (2026-08-20): the A2a realized-law result, and a finding worth acting on

The remeasurement completed and was harvested cleanly
(`f2b7cf9`, disposition **`dependence-premise-miss`**). The lease was
released. Result:

| Cell | before repair | after repair | class now |
|---|---|---|---|
| multiplicity ≥2 | +0.259 | +0.251 | material miss |
| multiplicity ≥3 | +0.744 | **+0.038** | inconclusive |
| multiplicity ≥4 | +1.648 | **+0.128** | inconclusive |
| QB–RB | +1.167 | **+0.131** | inconclusive |
| QB–WR | −0.261 | **−0.016** | inconclusive |
| TE–TE | +1.343 | +0.704 | inconclusive |
| RB–RB | +1.488 | +0.704 | material miss |
| **QB–TE** | +0.239 *(inconclusive)* | **−0.913** | **material miss** |
| **WR–WR** | +0.691 | **−1.150** | **material miss** |

**Balanced read.** Material misses fell from eight to four, and the
targeted cell landed almost perfectly (QB–WR −0.016). That is real
progress and the mechanism works. But the repair *manufactured* a
material miss in QB–TE — the one cell previously classified
inconclusive — and drove WR–WR to a larger absolute defect than it had
before (+0.691 → −1.150). The law is better on count and worse in two
specific places, which is why the disposition is still
`dependence-premise-miss`.

### The finding: the free census predicted this exactly

Addendum 3 projected the post-repair position of every cell from the
score-free census, with an explicit caveat that different populations
made the numbers "indicative rather than exact." Comparing that
projection against the measured result:

| Cell | projected | measured |
|---|---|---|
| multiplicity ≥2 / ≥3 / ≥4 | +0.251 / +0.038 / +0.128 | +0.251 / +0.038 / +0.128 |
| QB–WR / QB–RB / QB–TE | −0.016 / +0.131 / −0.913 | −0.016 / +0.131 / −0.913 |
| WR–WR / RB–RB / TE–TE | −1.150 / +0.704 / +0.704 | −1.150 / +0.704 / +0.704 |

**All nine cells match to three decimals.** My caveat was unnecessary;
the populations align exactly.

That has a concrete consequence worth adopting: for *dose evaluation*,
the outcome-bearing remeasurement added **no information** beyond what
the score-free census already contained. The census movement plus the
prior position determines the post-repair position deterministically.

**Recommendation:** evaluate future doses entirely on the score-free
census, and spend the outcome-bearing remeasurement only to CONFIRM a
dose that the census already shows landing every cell in band. This is
not a corner-cut — it is the same arithmetic, computed without holding
the historical-outcome lease, without consuming a one-shot, and without
the watcher/lease incident risk that this run demonstrated. It also
makes dose iteration cheap enough that the overshoot in WR–WR and QB–TE
can be fixed properly rather than accepted.

### Standing recommendation for the next dose

Unchanged from Addendum 3, now with measured targets rather than
projections. QB–WR needs almost none of its current allocation
(−0.016 means the one-hot dose could be cut substantially and still
clear), and that same reduction is what would relieve WR–WR. QB–TE needs
protection, and RB–RB / multiplicity ≥2 need more attenuation than 0.5
delivers. A position-aware dose evaluated on the census should be able
to land all nine cells without another outcome-bearing run — and the
evidence above says the census will tell you whether it has, before you
spend anything.

---

## Addendum 6 (2026-08-20): the Malformed sweep is incomplete — A7 still carries it

Good news first: the two watchers written since the incident
(`watch_b1_corpus_tail_queue.sh:169`,
`watch_a2a_production_law_dependence_queue.sh:161`) now carry exactly the
recommended parse, with an extra hardening I did not ask for and like:

```python
if not rows:
    print("Unknown")                      # not yet published -> retry
elif len(rows) == 1 and rows[0].get("status") in {"Unknown", "True", "False"}:
    print(rows[0]["status"])              # known-good status only
else:
    print("Malformed")                    # genuinely contradictory
```

Validating the status against an allow-list closes a second hole (an
unexpected status string can no longer be forwarded as if it were
meaningful). That is the right fix.

**But the original two sites are unchanged:**

- `scripts/cloud_a7_select_ladder.sh:349`
- `scripts/watch_a7_select_ladder_queue.sh:250`

both still read:

```python
print(rows[0].get("status", "") if len(rows) == 1 else "Malformed")
```

The fix went forward into new code but not backward into the code that
first exhibited the defect. `CLAUDE.md` frozen-chain rule 4 is explicit
that the whole class must be swept across sibling consumers, precisely
because point-wise fixes made the same class recur — which is what
happened between the A7 smoke (Addendum 1) and the A2a lease incident
(Addendum 4).

**Why this is not academic.** A7 is a queued, frozen, ready-to-run
experiment. When it launches, its launcher can still abort a healthy
preflight, and its watcher can still die on a transient with the message
`"A7 execution metadata malformed; lease held"` — the exact incident
already paid for once tonight, in the one consumer whose failure strands
the historical-outcome lease.

**Recommendation:** port the corrected parse (including the status
allow-list) to both A7 sites before A7 is launched, and add the
regression cases from Addendum 1 — `{"status": {}}`,
`{"status": {"conditions": []}}`, an unexpected status string, and a
two-`Completed`-row fixture — so the class cannot silently return in the
next chain either. A one-line `grep` for
`len(rows) == 1 else "Malformed"` is sufficient to confirm the sweep is
complete.
