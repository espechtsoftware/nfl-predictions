# Forensic analyzer: correctness review

Date: 2026-08-14. Code review of `research/final_forensic*.py` while the
forensic run is in flight, to establish whether the result can be trusted.
**No code was changed. No outcome was queried.**

---

## Verdict

The code is careful and I would trust the result. One change is worth making —
it is additive, does not invalidate anything already computed, and can be
applied mid-run — plus one interpretation caveat for the output.

---

## 1. What is correct

### 1.1 The oracle MILP constraint set

`_solve_oracle` enforces:

```
count(QB)  == 1
count(DST) == 1
count(RB)  in [2, 3]
count(WR)  in [3, 4]
count(TE)  in [1, 2]
total      == 9
salary     <= 50,000
```

That is exactly DraftKings Classic — QB 1, RB 2, WR 3, TE 1, FLEX (RB/WR/TE) 1,
DST 1 — with the FLEX represented implicitly by the upper bounds. This is the
single constraint set whose failure would silently inflate every L1 bound and
make the whole decomposition unusable. It is right.

### 1.2 The recourse FLEX-lock arithmetic

When an early-core player occupies the FLEX slot, the positional bounds are
adjusted:

```
count(RB) >= 2 + rb_flex_locked
count(RB) <= 3 - wr_flex_locked - te_flex_locked
```

and symmetrically for WR and TE. This prevents a locked FLEX player from being
double-counted against his own position's bounds. It is subtle, easy to get
wrong, and the failure mode would be plausible-looking but illegal lineups
inflating the recourse ceiling. It is correct.

The protocol also validates that a declared FLEX lock actually appears in its
early core (`recourse FLEX lock is absent from its early core`) and rejects
ineligible FLEX positions, so a malformed lock fails closed rather than
silently.

### 1.3 The recourse bound relaxes the floor but enforces the cap

Both the ceiling solve (line 1091) and the per-stage solves (line 1128) pass
`min_salary=0` while retaining `salary_expr <= salary_cap`.

That is the right pair of choices. A *bound* should not inherit a production
policy constraint, and cap legality must hold at swap time or the bound is not
achievable. This addresses the design note raised when the ceiling was being
implemented.

### 1.4 Deterministic tie handling

Both the candidate and selected maxima are taken via
`sort_values(["actual_score", "roster_key"], ascending=[False, True],
kind="stable")`. Ties resolve on a stable key rather than on frame order, so the
decomposition is exactly reproducible — which matters for a deterministic
pipeline whose entire validation law rests on exact reproduction.

### 1.5 Fail-closed structural checks

`selected roster is absent from the candidate pool`, `selected book is not
exact-{expected_entries}`, `oracle player support is empty`, and the duplicate
check on selected keys all raise rather than degrade. The analyzer cannot
quietly produce a decomposition over a malformed book.

---

## 2. The change worth making: L1 inherits the salary floor

`full_oracle` — the H layer, the full-universe bound — is solved with the
default `min_salary=49_000`:

```python
full_oracle = _solve_oracle(frame, min_salary=min_salary, salary_cap=salary_cap)
```

**The $49,000 floor is a production policy, not a DraftKings rule.** DK imposes
no minimum salary.

So L1 currently measures *"the best legal lineup **under our salary policy**"*
rather than *"the best legal lineup."* The decomposition therefore attributes
nothing to the policy itself, and cannot.

### Why this is a live question rather than a hypothetical

The omitted winning player-slots averaged **$4,128** — cheap players — and the
route-share measurements found cheap high-participation players clearing 20
points at roughly ten times the rate of cheap low-participation players at the
same salary. A floor that forces spending is precisely the kind of constraint
that would exclude that population.

As written, **if the salary floor is costing winners, L1 cannot detect it**,
because the oracle is bound by the same rule as the generator it is meant to
bound. The layer designed to answer "how far short is the universe" is silently
answering "how far short is the universe we allowed ourselves."

### The fix

One additional solve: compute `full_oracle` **both with and without** the
floor, and report the difference as an explicit layer.

- It is **additive** — nothing already computed changes or is invalidated.
- The plumbing exists — the recourse path already passes `min_salary=0`.
- It can be applied mid-run without disturbing the frozen manifest, provided
  the new field is recorded as an addition rather than a redefinition.
- The output is a directly useful number that is otherwise invisible: **the
  realized cost of the salary-floor policy across 107 slates.**

That number matters beyond this analysis. The floor was adopted on one-shot
evidence, and the recourse framing independently predicts it may be optimal for
the wrong problem — unspent salary is a call option on an expensive late-game
player. Measuring its cost directly is cheaper than any arm and settles a
question two separate lines of reasoning now raise.

---

## 3. Interpretation caveat for the output

`support_oracle` is solved over the union of players appearing in **any**
candidate on the slate. The resulting split is:

- **H → P**: value lost to players the generator never touched at all;
- **P → C**: value lost to combinations it never assembled from players it did
  touch.

Both are real and the split is meaningful, but it is sensitive to how support is
defined. A player appearing in **exactly one** of ~250 candidates counts as
fully available to the P layer, even though the generator plainly had no
meaningful propensity to build him.

**Recommendation:** state this in the output, and consider reporting a
support-count distribution alongside — how many players in the support set
appear in fewer than, say, five candidates. Otherwise P reads as "the generator
had a fair shot at this," when for the thinly-represented tail it did not, and
the H→P versus P→C attribution will be over-read.

---

## Summary

The analyzer is trustworthy: the legality constraints are exactly right, the
recourse locks are handled correctly, ties are deterministic, and malformed
inputs fail closed.

One additive change — **solve the full-universe oracle with and without the
$49,000 floor** — converts an unmeasurable policy assumption into a reported
number, and can be made without disturbing the run. One caveat — **the support
set includes barely-represented players** — should be stated so the H→P and
P→C layers are not over-attributed.
