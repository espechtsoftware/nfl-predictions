# Exact-one QB partner at k=8 under A2a — protocol draft

**Protocol ID:** `20260820-single-stack-k8-under-a2a-v1`

**Status:** `READY-AWAITING-A2A` — not frozen, not licensed, not launched

**Scope:** one causal lever only

This is the prepared successor to the negative A3 open-stack carve. It asks
whether replacing the same eight deterministic boom visits per seed with an
exactly-one QB--WR/TE stack improves the exact-80 weekly maximum after the
separate A2a dependence law has passed its realized-law gate. It does not
change or test bring-backs, salary, RB/DST restrictions, game spread,
ownership, selector utility, world count, seed count, or candidate budget.

Nothing in this draft authorizes an outcome query, BigQuery or GCS access, a
historical lease, a build, a Cloud Run update or execution, a shadow, or a
production change. Source and protocol hashes are deliberately not pinned
while status is `READY-AWAITING-A2A`.

## 1. Hard prerequisite

The protocol may advance to an outcome-blind real-artifact smoke only if the
strictly harvested A2a realized-law result has all of the following literal
values and a generation/size/SHA-pinned content identity:

```text
passes = true
disposition = a2a-law-shape-passes-single-stack-protocol-licensed
licenses.single_stack_protocol_licensed = true
licenses.candidate_or_lineup_scores_read = false
licenses.single_stack_arm_licensed = false
licenses.exact80_scoring_licensed = false
licenses.prospective_shadow_licensed = false
licenses.production_change_licensed = false
```

Any other A2a disposition closes this draft without a smoke or historical
read. A2a's exact transform and dose must be common to both construction arms;
the construction experiment cannot alter, refit, or selectively apply it.

## 2. Exact contrast

- **Control:** A2a-transformed R0--R4 player worlds, incumbent production
  construction, `OPEN_BOOM_SOLVES=0`, `SINGLE_STACK_BOOM_SOLVES=0`.
- **Treatment:** byte-identical sources, A2a-transformed worlds, seeds,
  objectives and environment except
  `SINGLE_STACK_BOOM_SOLVES=8`.
- The existing seam replaces eight deterministic boom visits. It never adds
  visits or candidates. Each carved solve requires exactly one same-team QB
  WR/TE partner (`qb_stack_min=1`, `qb_stack_max=1`) while retaining the
  incumbent `bring_back_min`, salary band, RB/DST prohibitions and game rules.
  The primary family remains `boom`; the secondary tag is `single_stack`.
- `OPEN_BOOM_SOLVES` and every other research lever remain fixed. No combined
  arm is allowed.

The fixed population is the same 54 Sunday-main 2023--2025 slate lattice and
five money-world blocks used by A3. R3/2025 Week 1 remains the registered
four-block recovery cell and is mechanism-only. Therefore there are exactly
269 seed/slate blocks, 2,152 carved additions, and 53 paired exact-80 scoring
slates.

## 3. Outcome-blind support and mechanism gates

Before this document can be frozen, one real-artifact `2023 Week 1` smoke must
exercise the exact reconstruction, A2a transform, both generations, equal
budget accounting, exact-80 selection and receipt serialization without
selecting or reading an actual, actual score, winner, ownership outcome,
contest rank or payout. The smoke is not allowed before the A2a prerequisite
passes.

The eventual full one-shot arm fails closed unless every condition below is
true:

1. The cell lattice is exactly 54 ordered slates; block population is exactly
   269; both arms use the same content-pinned source and A2a draw identity in
   every block.
2. Candidate counts are equal within every paired block.
3. Every block records exactly 8 carved attempts, 8 distinct carved roster
   identities and 8 distinct additions, with no infeasibility, duplicate or
   refill shortfall. Aggregate carved additions must equal 2,152.
4. All 2,152 carved candidates have exactly one same-team QB WR/TE partner,
   at least one incumbent bring-back, zero protected-constraint violations,
   eight primary `boom` tags and eight secondary `single_stack` tags per
   block.
5. Both arms contain exactly 80 unique entries on each of the 53 scored
   slates. The recovery cell claims neither an exact-80 book nor an outcome.
6. Every selected `single_stack` roster independently reproduces the same
   exact-one and bring-back census. On at least one slate, one reaches the
   treatment book and that same treatment book differs from control. If not,
   disposition is
   `single-stack-outcome-blind-selector-vacuity`, and historical scoring is
   not scientifically informative.

The pure accounting implementation is
`src/nfl_dfs/research/single_stack_k8_arm.py`; the local-only scaffold is
`scripts/run_single_stack_k8_arm.py`. The script accepts only canonical local
JSON and optionally writes one create-only local report. It contains no data,
optimizer, BigQuery, GCS, cloud, lease, launch or scoring body.

## 4. Outcome boundary

Only after the A2a pass, a successful real-artifact smoke, a frozen protocol
and exact code/input hashes, a successful exact-source build, a free shared
historical-outcome lease, an empty create-only output prefix and independent
launch review may one immutable historical execution be considered.

For each of the 53 scored slates, both exact-80 roster books and all simulated
accounting must be locked before one actual-player-score source is read.
Actual-score reconstruction must match the registered canonical candidate
scores within absolute tolerance `1e-9`. Outcome data may only compute:

- control and treatment candidate-pool weekly maxima;
- control and treatment exact-80 weekly maxima;
- the complete `187/194/200/210/220/230/240` count grid;
- mean and median weekly maximum; and
- the standing paired-weekly-max report.

No outcome may choose a roster, tune k, alter A2a, change a threshold, repair a
cell, or choose a fallback. Partial bodies are never inspected.

## 5. Frozen historical gate

Subject to every support/mechanism gate, the result is historically positive
only if all of these exact conditions pass:

1. treatment mean exact-80 weekly maximum is strictly greater than control;
2. treatment adds at least two exact-80 weeks at or above 200;
3. treatment exact-80 counts are noninferior at 194, 210, 220, 230 and 240;
4. treatment candidate-pool weeks at or above 200 are noninferior; and
5. on at least one slate, an exact-one treatment roster reached the selected
   book and that same exact-80 book changed.

The complete grid and paired statistics are reported even when a gate fails;
they cannot override it.

## 6. Exhaustive dispositions

- Any A2a result other than the sole pass: `closed-prerequisite-a2a-miss`.
- Any support/identity/budget/structure failure: `mechanically-invalid` with
  no outcome verdict and no retry under this protocol.
- Exact candidates exist but none reach a changed book:
  `single-stack-outcome-blind-selector-vacuity`; no historical claim.
- Every historical gate passes:
  `single-stack-historical-positive-shadow-design-licensed`.
- Otherwise: `single-stack-historical-not-supported-closed-at-k8`.

A historical pass licenses only writing a separate default-off prospective
shadow design. It does not license the shadow run, production, a deployment,
another historical look, a k sweep, bring-back removal, or any other variant.
Production adoption still requires a separately frozen unseen-2026 shadow
gate. A miss closes k=8 under this A2a law; it may not be converted into a dose
sweep on the same outcomes.

## 7. Work deliberately deferred

The transport is not implemented in this preparation step. After A2a passes,
the next bounded action is one outcome-blind real-artifact smoke using the
existing A3 reconstruction and exact selector patterns with the A2a transform
inserted identically in both arms. Only then may the protocol and transport
bytes be reviewed and frozen. Cloud transport must reuse an idle unscheduled
research job, use `maxRetries=0`, honor the shared lease and create-only
prefix, and be made visible to `scripts/chain_status.sh`; those shared-file and
cloud changes are outside this draft.
