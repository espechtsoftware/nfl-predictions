# Review: `exploration_sleeve.validate_lineup` has three fail-open paths

Reviewing nfl2 `research/exploration-sleeve-20260921` @ `c2b4be6`
(`src/nfl2/exploration_sleeve.py`).

The design is right. Keeping the sleeve outside `pipeline.run_slate`, relaxing
only concentration preferences while the optimizer still enforces DK roster and
salary rules, and adding a second cheap boundary check before a sidecar is
written — all correct, and `forbid_rb_vs_dst=True` with
`forbid_two_rb_same_team=False` is the right split between "football-invalid"
and "concentration choice".

The problem is in `validate_lineup`, which the docstring describes as the check
that makes a lineup "upload-safe". Three of its rules can pass without ever
testing anything. All three are reproduced below against `c2b4be6`.

## 1. A lineup with an unrecognized position is accepted (most serious)

```python
counts = {pos: sum(p.get("pos") == pos for p in players)
          for pos in ("QB", "RB", "WR", "TE", "DST")}
```

Nothing asserts that these five counts sum to 9. With
`QB 1 + RB 2 + WR 3 + TE 1 + DST 1 = 8`, every bound is satisfied while one
roster spot holds a player the check never classified.

Reproduced: a nine-player lineup of
`QB, RB, RB, WR, WR, WR, TE, DST, K` — legal salary, two games, one QB, one
DST — is **ACCEPTED**.

Any `pos` value outside the five literals does this: a kicker, a null, a
lowercase `"wr"`, or a source-schema spelling drift. Position is the one field
a relaxed-construction arm is most likely to meet in an unexpected form.

Minimal fix:
```python
if sum(counts.values()) != 9:
    raise ValueError(f"unclassified roster position present: {counts}")
```

Related, and worth a comment even though it is currently correct: the
`counts != {...}` comparison compares `RB`/`WR`/`TE` to themselves, so it tests
only QB and DST. That is what the message says, but it reads as though it tests
all five and will mislead the next editor.

## 2. `qb_safe_ids=None` silently disables the quarterback gate

```python
if qb_safe_ids is not None and str(qbs[0].get("id")) not in {...}:
```

`qb_safe_ids` is a required keyword, so it cannot be *omitted* — good. But an
explicit `None`, which is what a caller threading an unset config through will
pass, turns the gate off and returns success.

Reproduced: the same lineup with `qb_safe_ids=None` is **ACCEPTED** with no
quarterback check performed.

This is the operator's standing no-silent-fallbacks rule (2026-09-20): a step
works as designed or the run stops. Suggested: drop the `is not None` guard and
let `None` raise, or raise explicitly.

This gate matters more than it looks — see §4.

## 3. A DST row with no `opp` silently skips the RB-versus-DST rule

```python
dst_opp = dst.get("opp")
if any(p.get("pos") == "RB" and p.get("team") == dst_opp for p in players):
```

When `opp` is absent, `dst_opp` is `None`, no real team equals `None`, and the
rule passes.

Reproduced, same lineup both times, RB genuinely on the defense's opponent:

| DST row | result |
|---|---|
| `opp="Q"` present | rejected — "running back opposes selected defense" |
| `opp` missing | **ACCEPTED** |

This one has history: DST rows are exactly where opponent fields have gone
missing or wrong before. The adjacent-Thursday LineStar DST rows carried the
prior source week, and DST salary rows had to be made to match schedule
team+opponent+week with duplicates hard-failing. A missing `opp` should be an
error, not a pass.

Minor, same class: `inactive_ids` defaults to `()`, so a caller that forgets it
falls back to `_inactive(row)` alone, which returns `False` when the row simply
has no status field.

## 4. An interaction the safety set does not cover

`EXPLORATION_ENV` sets `MIN_LOWOWN=0` and `OWN_BARBELL=""` and
`MAX_PER_GAME=0`. That is the point of the arm. But it removes the constraints
that were incidentally limiting exposure to a known valuation defect: backup
quarterbacks currently carry `E[points | played]` as an unconditional
projection — depth-2 mean about 9.8 at $4,000. In Week 2, 12 of 97 D6400 rows
sat on a flagged quarterback.

An allow-list of *approved* quarterback ids is an availability control, not a
valuation control. A backup who is active and cleared is in the safety set,
while still being priced as though his start were certain. With ownership and
concentration limits relaxed, the sleeve will find that cheap quarterback
attractive and build a large share of its candidates around him — and it will
look like coverage.

This does not block the arm. It means the per-arm receipt should carry a
flagged-QB row count so the coverage result can be read net of it, otherwise a
coverage gain and a valuation artefact are indistinguishable.

## Not raised as defects

`generate_candidates(extra_profiles=...)` with a deterministic `start` offset
for the reserved world slice is a clean way to keep the arm's draws
reproducible and disjoint. The two-game check correctly fails closed when every
`game_id` is missing. `validate_all` returning a count for the sidecar manifest
is the right shape.

## Note

I have not modified anything in nfl2. These are reproductions against your
commit, with suggested minimal fixes for you to accept or reject.
