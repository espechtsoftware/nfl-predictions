# Six decisions we need from you

Each of these is yours by ownership, not by preference — they touch frozen
research chains, your instruments, or a protocol you set. Each has my
recommendation and the evidence behind it, so a one-line answer is enough. If
any is genuinely not yours, say so and it goes back to the operator.

Two are new; four have been open since earlier today.

---

## 1. NEW — Python 3.14: hold the package, or re-freeze the contracts against it?

Open since 2026-09-12. apt moved `python3.14` from `3.14.4-1ubuntu0.1` to
`0.2` on 2026-09-09. `corpus_retrieval_v2_implementation_contract` pins the
interpreter binary's sha256 and byte count, so every chain validating that
contract now fails closed.

**Status changed today:** the `1ubuntu0.1` debs existed only in
`/var/cache/apt/archives`, one `apt clean` from permanent loss. They are now
copied to `/home/erich/pinned-runtime/`, and I verified by extraction that they
reproduce the contract literals exactly (7,481,192 bytes, sha256
`b8d8288f…`). So the decision is no longer time-critical — both options remain
genuinely available.

**My recommendation: re-freeze against `0.2`.** Holding a superseded system
interpreter indefinitely accrues cost with every future apt update, and the
preserved debs already guarantee the old runtime is reproducible for any
historical re-validation. But if any chain's results must remain
bit-comparable to an already-recorded panel, hold instead — that argument
beats mine and only you know which panels are still live.

## 2. NEW — the TabPFN gate has no sufficiency check

`assess_tabpfn` in `src/nfl_dfs/inference/build_inputs.py` tests only
`rows_for_week <= 0`. Demonstrated today: a `tabpfn-gen` run made before
`build-features` wrote **51** rows for week 3 (against 813 DK classic players)
and **the gate went green**. `assess_files`, ten lines below, already carries
`min_book_entries: int = 90`, so the pattern exists.

**My recommendation: derive the threshold from the DK classic slate's
skill-player count rather than a constant** — a constant becomes the next
`N_BOOM=40`. Flagged, not changed; tell us if you would rather own it.

## 3. Quarantine framing — these chains cannot pass in GitHub CI at all

`corpus_retrieval_v2_implementation_contract` pins a *numerical runtime
identity*: interpreter binary sha256 and bytes, numpy core binary sha256, and
the host **CPU feature flags** (AVX2, FMA3, BMI2, …). `ci.yml` runs **Python
3.11** with `numpy>=1.26` on variable runner hardware.

So quarantining them would record a permanent KNOWN failure for tests that were
never capable of passing there — which is how a real regression gets lost,
exactly as your quarantine header warns.

**My recommendation: a `requires_pinned_runtime` marker that deselects them in
CI with a stated reason, while `scripts/test_lanes.sh full` keeps running them
on the pinned workstation**, where the assertion is meaningful. And point
`ci.yml` at the lanes script — it already classifies KNOWN vs NEW and exits
non-zero only on NEW; line 24 currently runs bare `pytest` and never invokes
it. Until something changes, a CI failure email carries no signal.
Detail: `reports/2026-09-21-ci-quarantine-addendum.md`.

## 4. Evidence graph — how should the pins be resolved?

5 of the 25 artifacts in `reports/evidence-graph/20260821-v1/bootstrap.json`
have drifted, all live production modules. `build_graph` hashes the **working
tree**, so it fails on every legitimate code change.

**No evidence is lost** — every pinned version is still recoverable from git
(commits in `reports/2026-09-21-reply-to-generator-arm-plan.md` §4).

**My recommendation: record the commit beside each sha and resolve the pinned
blob at that commit instead of reading the working tree.** Additive, and it
makes the graph permanently verifiable. **I have deliberately not re-pinned
anything** — re-pinning to head would assert that today's code produced
August's evidence, which is false.

## 5. The quarterback availability gate — three options, still open

Backup QBs carry `E[points | played]` as an unconditional projection (depth-2
mean ≈ 9.8 at $4,000); 12 of 97 D6400 rows sat on a flagged QB in Week 2.

**My recommendation is unchanged: exclude at generation input (option 3).**
Today's review of your exploration sleeve strengthens it. `EXPLORATION_ENV`
sets `MIN_LOWOWN=0`, `OWN_BARBELL=""`, `MAX_PER_GAME=0` — correctly, that is
the arm's purpose — but those were the constraints incidentally capping
exposure to this mispricing. An allow-list of approved QB ids is an
*availability* control, not a *valuation* one: a backup who is active and
cleared passes it while still priced as though his start were certain.

**Minimum ask regardless of which option wins: put a flagged-QB row count in
each arm's receipt**, or a coverage gain and a valuation artefact will be
indistinguishable.

## 6. Exploration sleeve — three fail-open paths, all reproduced

From `reports/2026-09-21-review-exploration-sleeve-validate-lineup.md`, against
`research/exploration-sleeve-20260921` @ `c2b4be6`:

1. **A nine-player lineup containing a kicker is ACCEPTED** — the five position
   counts are never asserted to sum to 9, so `QB 1 + RB 2 + WR 3 + TE 1 +
   DST 1 = 8` satisfies every bound with one unclassified roster spot.
2. **`qb_safe_ids=None` silently disables the quarterback gate.**
3. **A DST row without `opp` silently skips the RB-versus-DST rule** — the
   identical lineup is correctly rejected when `opp` is present.

These need no decision, only your fix — but item 1 in particular should land
before the arm generates candidates, since a relaxed-construction arm is the
most likely thing to meet an unexpected `pos` value. Nothing in nfl2 was
modified by us.

---

**If any of these is not yours to answer, say which and it goes back to the
operator rather than sitting open.**
