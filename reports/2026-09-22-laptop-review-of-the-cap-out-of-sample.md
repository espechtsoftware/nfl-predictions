# Laptop → production: I agree with the decision, cannot reproduce the result, and
# have one question about how the arms are scored

Review of `1aa42101`. **The decision — no capped book for Week 3 — I support, and nothing
below argues against it.** The review is about the evidence's strength and its
reproducibility, which are separate from whether the call is right.

## What is well done, said first because it is most of it

- **Hash-gated inputs.** `build_w1.py` verifies both archived bank sha256 values against
  `receipt.json` before using them. That is comparison by content identity, as the rules
  require.
- **The comparability gate runs before any arm.** Requiring the greedy to return all 90
  delivered lineups *in exact delivered order*, and stopping if it does not, is the right
  gate and is the thing that makes the capped arms mean anything.
- **The confound is disclosed rather than buried** — Week 1 selects 90 from 3,200 (2.8%),
  Week 2 selects 97 from 12,555 (0.8%), so slate and dose are entangled and two runs cannot
  separate them. Stating that, and then arguing that every reading still counsels against
  deploying, is the right shape of argument.
- Retracting a positive lever on out-of-sample evidence is the behaviour this project's
  ledger rules exist to produce.

## Finding: neither reproduction script can run anywhere but your host

Both embed absolute host paths:

```
sweep_w1.py:  sys.path.insert(0, "/home/erich/projects/.nfl-predictions-worktrees/week3-readiness-20260921/src")
build_w1.py:  R = Path("/home/erich/projects/.nfl2-worktrees/week1-live-center-e7255e9/results/live/...")
```

**Both are absent on this machine** (nearest local equivalents: `week3-readiness` without
the date suffix, and no `week1-live-center-*` worktree at all). `sweep_w1.py` also reads
five files — `T_inc.npy`, `T_hs.npy`, `rix.npy`, `frame.parquet`, `cands.parquet` — from an
unstated working directory.

This is the standing frozen-chain rule almost verbatim: *"A chain whose validators embed
the current commit, an absolute host path or a contest-specific constant will fail at the
next commit, host or week. Prefer content identities, repository-relative paths…"*

The practical cost is the protocol: **the second party re-runs the reader before the result
is relied on, and I cannot.** So this result currently rests on one execution on one host,
which is exactly what "reproduce:" in the report offers and does not yet deliver.

Cheap fix, not made by me: take the run directory as an argument (defaulting to an env
var), resolve `src` repository-relatively from `__file__`, and document the working
directory. The sha256 gate already gives the content identity, so the path only needs to be
*a* copy of the right bank, not *that* path.

## Question: are the arms scored symmetrically?

`sweep_w1.py` scores realized points from `contest_ownership`, and a slate player with no
row there becomes **0.0**:

```python
pa = np.array([lut.get(n, np.nan) for n in names], float)
pa0 = np.nan_to_num(pa, nan=0.0)
```

That conflates *played and scored nothing* with *absent from the standings export* — the
same conflation that made my first Doubtful pass wrong this morning, when `weekly_stats`
omitted players who suited up and recorded nothing.

Why it could matter **here specifically**: a cap's entire mechanism is spreading exposure
across **more distinct players**, and the players it spreads into are the ones the
unconstrained book declined. If those are systematically more likely to be missing from the
export, then tighter caps mechanically accrue more default zeros, and the monotone decline
(−2.46 → −6.76 as caps tighten) is partly an artifact of scoring rather than of the lever.

**I am not claiming this is happening.** I tried to probe it from the warehouse and the
result was inconclusive — missing-row rates by salary band came out 28.8% / 13.9% / 27.2%
(high / mid / low), with no gradient supporting the hypothesis. I could not test it properly
because the books themselves are behind the host paths above.

The decisive check is cheap and you can run it: **for each arm in the sweep, count the
roster slots referencing a player with no standings row.** If that count is flat across
caps, the concern is dead and the result stands as measured. If it rises as caps tighten,
part of the decline is measurement. `sweep_w1.py` already computes `miss` and prints it —
the report does not carry the number, and per-arm it is the number that settles this.

## Net

Decision: agreed, and it would still be my recommendation if the concern above resolves in
your favour — the dose/slate confound alone justifies not deploying a lever this week.
Evidence: one host, one execution, not independently reproduced, with one open question
about symmetric scoring. Those are different claims and worth keeping apart in the ledger.
