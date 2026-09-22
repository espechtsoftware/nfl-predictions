# The lab's open decisions, taken over and ruled on

The lab agent became unavailable on 2026-09-22 (the operator lost access to that model).
Everything that was waiting on it now has one owner. This closes
`2026-09-21-decisions-requested-from-lab.md` and
`2026-09-22-questions-for-lab-exposure-caps.md`: nothing from either is still "open with
the lab", because there is no lab.

Week 3 locks **Sunday 2026-09-27**. Rulings are ordered by whether they can still affect
that build.

---

## What changed structurally, and the one thing that needs the operator

**nfl2 is still in the money path.** `sunday_build_host.sh` runs
`$CLONE/scripts/live_week.py` with `$LAB_PY` from the clone
`.nfl2-worktrees/week2-release-2dc116c`. So lab *code* remains production-critical even
though the lab *agent* is gone. Two standing rules were built around a second party that
no longer exists:

- "Nothing in nfl2 is modified by us; fixes go as a patch plus a failing test."
- "The release worktree stays CLEAN at `2dc116c`."

Both were correct arrangements. With no counterparty, the first now means *nobody* fixes
nfl2, and the second means the money path is frozen at whatever nfl2 was on 2026-09-19.
**That is the operator's call, not mine, and it is the one thing I have not acted on.**
It matters this week because of decision 5 below.

---

## 1. Python 3.14 — re-freeze, but not this week

**Ruling: re-freeze the contracts against `3.14.4-1ubuntu0.2`, scheduled after Week 3
settles.**

The earlier recommendation was re-freeze, with one caveat: hold instead if a live panel
must stay bit-comparable. That caveat now resolves — PREREG-101 must not launch, PREREG-099
is read and closed, and bank 991 is complete but deliberately unread. No chain is
generating results that must be bit-comparable to a recorded panel. The preserved debs (in
`gs://…/pinned-runtime/`, round-trip verified to reproduce sha `b8d8288f…`) keep every
historical re-validation reproducible.

**Deliberately not done now.** Re-freezing touches the pinned interpreter identity that the
whole verification chain rests on. Doing that in the five days before a money build, to fix
a problem that costs nothing until the next apt update, is the wrong order. It is scheduled,
not skipped.

## 2. TabPFN sufficiency — **DONE** (`2748e666`)

The floor is derived from the slate's skill-player count, not a constant. Re-run against
the live warehouse: the old gate passed this week's cache, the new one fails it — *51 rows
for week 3 against a 633-skill-player slate (floor 506)*. Sufficiency that cannot be
computed fails closed rather than reverting to presence-only.

Found while measuring: **`dk_salaries.week` is NULL on every row**, so a slate can only be
located by draft group — recorded in the README deficiency log. And **2026 week 2's TabPFN
rows are gone**; the bad run truncated them as documented, so there is no in-season history
left, only 2025.

## 3. CI framing — **my call, and I am taking the recommendation**

Point `ci.yml` at `scripts/test_lanes.sh`, which already classifies KNOWN vs NEW and exits
non-zero only on NEW. Line 24 currently runs bare `pytest`, so a CI failure email carries no
signal. The `requires_pinned_runtime` marker half is already in (`460b4743`). **Queued
behind the Week-3 items**; it changes no production behaviour, only whether the alarm means
anything.

## 4. Evidence graph — **ruling: resolve pins at the recorded commit**

`build_graph` hashes the working tree, so it fails on every legitimate code change. Record
the commit beside each sha and resolve the pinned blob at that commit. Additive, and it
makes the graph permanently verifiable. **No artifact has been re-pinned** — re-pinning to
head would assert that today's code produced August's evidence, which is false. Queued
behind the Week-3 items.

## 5. Quarterback availability — **this is the Week-3 decision, and it needs the operator**

The recommendation was to exclude at generation input. Investigating it properly turned up
something better and simpler, and adjacent to it the biggest single miss of Week 2.

`nfl2/src/nfl2/live.py` already has the right function —
`apply_dk_status_invariant`, "remove DraftKings-inactive rows **before any simulation or
candidate solve**". Its denylist is `{"O", "OUT", "IR"}` and its receipt reads
`retained_designations: {"Q": 10, "D": 3}`. **Doubtful is retained deliberately and treated
exactly like a healthy player by every downstream stage.**

Week 2: **Zay Flowers was Doubtful at build time, held 48 of 97 rows including the
Millionaire entry, and scored 0.0.** All three Doubtful players scored zero; none played.
51 of 97 rows carried one.

The fix is one token — adding `"D"` to that frozenset. It is an *availability* rule, not a
valuation or exposure one: the objective, the draws and the construction rules are
untouched; the pool simply never contains a player who is not expected to play, exactly as
it never contains an OUT player. **Questionable is not included and should not be** — Q rows
averaged 98.3 against 98.4, and the two Q players with posted props were among the better
outcomes.

**Blocked, not decided by me:** it is an nfl2 edit to the clone that must stay clean at
`2dc116c`. Patch, evidence and a failing test are ready in
`reports/lab-handoffs/2026-09-22-doubtful-eligibility-patch.md`. The clone is untouched.

The original "minimum ask" — flagged-QB counts in the receipt — is satisfied
production-side: `scripts/exposure_cap_book.py` reads `report_status` and its sheet lists
every flagged player with delivered and capped row counts.

## 6. Exploration sleeve — **parked, with the fix already specified**

Three fail-open paths (a nine-player lineup containing a kicker is accepted; `qb_safe_ids=None`
silently disables the QB gate; a DST row without `opp` skips the RB-versus-DST rule). All
three are in `research/exploration-sleeve-20260921`, which is **research-only and not in the
money path**, and nobody is now running it. Same nfl2 ownership question as decision 5, but
without the urgency. Parked deliberately; if the sleeve is ever armed, these land first.

---

## The exposure-cap questions I had put to the lab

**The gate question — ruling: do not upload the capped book for Week 3.**

`ordering_shadows.py` and the other pre-lock captures run against `$K90_DIR`, the selector's
book. Uploading a different book would leave every prospective gate grading a book we did
not enter. Weighed against that: the cap's measured benefit is one slate, and item 3 was
explicit that the *sign* is established and the *level* is not. A multi-week instrument is
worth more than a one-slate edge, so the shadows stay aimed and the capped book stays a
report. The sheet still emits every Sunday (step 6 of the build) and the operator reads it.

This ruling is about the **exposure caps**. It is not an argument against decision 5, which
is a different kind of change: an availability exclusion applies before generation, so the
selector, the book and the shadows all move together and stay mutually consistent. That is
precisely why the eligibility route is better than capping.

**Caps inside the selector — no**, for now. Same nfl2 constraint.

**The per-contest level — 50%, as shipped.** Deliberately weak; the Week-3 preflight showed
the global 30% cap does the work at this entry spread anyway (peak exposure 59 rows at both
50% and 34%, because 30% of 198 is 59).

---

## Also closed while taking this over

**`min_book_entries = 90`** (the operator's unanswered question (a)): the floor was a volume
test wearing a data-quality test's clothes. The operator states he typically will not exceed
90, so it sat exactly on his normal volume and an 89-entry week would have failed closed on
Sunday morning with nothing wrong. Defaulted to 1; every genuine malformation — absent file,
zero entries, missing `contest_id` or `name`, non-integer entries — still fails, and the
parameter remains so a floor can be imposed deliberately.

## Still open, and honestly so

- **Laptop review item 1** needs a re-run at the serving commit, and item 2's per-bug
  consolidation is unwritten. Both are reporting, not repair.
- **Laptop review item 2's per-bug consolidation** is unwritten. Reporting, not repair.

## `sis-pass-tail-2026` — DONE, ruled dormant

Not a contract declaration in the end. The registry entry's own note recorded that **no
frozen gate document exists**: the week-5 start was derived from a last-four-weeks context
inside the module, not from anything preregistered. A paired job with a scheduler but no
written gate cannot be graded, so the entry could only ever warn — which it did, every hour
for two days.

The note offered two exits: write the gate, or move to DORMANT with a reason. **Writing it
now would mean choosing what it adjudicates after two weeks of 2026 outcomes are visible,
which is retrospective design and is forbidden by the ledger.** So the three schedulers move
to `DORMANT` carrying that reasoning in the registry itself, not just in this report, and a
test pins it so the pair cannot be quietly re-silenced or revived without a gate. All three
were already PAUSED and no live feature, model or inference path reads the SIS pass-tail
tables. Re-open only with a gate frozen *before* the weeks it grades.

**Two tests had to be repaired to do this, and the repair is the interesting part.**
`test_upcoming_gate_warns_but_does_not_fail` and `test_gate_outside_its_window_is_not_an_error`
both reached into the real `sis-pass-tail-2026` row to find a gate at the right distance —
so they were testing a registry entry rather than the lookahead mechanism, and a legitimate
registry change broke them. Both now inject their own synthetic gate and test the behaviour.

**Operator note: the hourly host check's expected output is now stale.** It says to expect
"four sis-pass-tail WARNs"; the audit is now clean, with one `ok` line. A future check
should treat the *reappearance* of those warnings as the departure.
