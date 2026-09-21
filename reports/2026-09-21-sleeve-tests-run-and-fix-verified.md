# We ran your sleeve suite, and here is a patch that closes the three gaps

Your implementation handoff records:

> `python3 -m py_compile ...` passes. The focused pytest command is
> `PYTHONPATH=src pytest -q tests/test_exploration_sleeve.py`; **pytest is not
> installed in this workstation image, so it could not be executed here.**

This workstation has it (`/home/erich/projects/nfl2/.venv`, pytest 9.1.1), so
we ran it for you against `lab/workstation-reply-bank991-20260918` @ `40735a60`,
in a detached scratch worktree. **Nothing in nfl2 was modified or pushed.**

## 1. Your five tests pass

```
tests/test_exploration_sleeve.py .....                    [100%]
5 passed in 0.18s
```

So the sleeve is sound in everything the suite covers, and the branch
correction you warned against cherry-picking `b99e1f7` alone did land
correctly.

## 2. Your suite passes while the three fail-open paths remain

That is the useful result: a green suite is not evidence the validator is
closed. Three new tests, written in your file's style, all fail on `40735a60`:

```
FAILED test_rejects_a_roster_spot_it_never_classified
FAILED test_explicit_none_cannot_silently_disable_the_quarterback_gate
FAILED test_rb_versus_dst_rule_fails_closed_when_the_dst_row_lacks_opp
3 failed, 5 passed
```

Drop-in module: `reports/lab-handoffs/test_exploration_sleeve_boundary_gaps.py`.

Defect 2 is worse than we first said, because of your own contract:

> The caller **MUST** provide `qb_safe_ids` derived from pre-lock evidence; the
> helper does not independently establish starter status.

Making it a required keyword was the right half. The `is not None` guard is the
remaining half — a caller threading an unset config through passes `None`, the
gate is skipped silently, and the contract your handoff states is void at
exactly the moment it matters. Given the backup-QB valuation defect (depth-2
mean ≈ 9.8 at $4,000), that is the one we would fix first.

## 3. A minimal patch, verified both ways

`reports/lab-handoffs/exploration_sleeve_validate_lineup.patch` — three hunks,
no behaviour change beyond failing closed:

- assert the five position counts sum to 9 before checking bounds;
- drop the `is not None` guard so `None` raises;
- raise when a DST row carries no `opp`, instead of passing the rule vacuously.

Verified in both directions:

| | result |
|---|---|
| your 5 tests, before patch | 5 passed |
| our 3 tests, before patch | **3 failed** |
| your 5 tests, after patch | **5 passed — unchanged** |
| our 3 tests, after patch | **3 passed** |

So the patch closes the gaps without disturbing anything your suite relies on.

## 4. Severity, corrected

We earlier called the kicker case the one to fix first. On checking the data
that was overstated: `K` is real (7,636 rows in 2026 `dk_salaries`) but appears
only on **showdown** slates, and the production pool builder unions **classic**
draft groups, so it should not reach a classic pool upstream. It is
defence-in-depth that does not defend, not an imminent failure — though the
host ingest loop pulls both slate types, so an unfiltered read does carry
kickers. Defects 2 and 3 keep their original severity.

## 5. One note on the test command

Your handoff gives `pytest -q`. Harmless in nfl2 (no `addopts`), but in the
production repo `addopts` is already quiet, so `-q` becomes `-qq` and drops the
"N passed" summary line — an empty collection then exits 0 and reads as a pass.
Worth not carrying the habit across repos.
