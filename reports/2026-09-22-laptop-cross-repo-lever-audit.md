# Cross-repo lever audit: 75 adopted levers traced to the money path

Assignment from `3c05dcad`. Deliverables: a verdict per lever with proof, restoration cost
for anything dead, and a money-lane test that fails closed when an adopted lever is
declared-but-ignored across the repository boundary. **Nothing was fixed**, per instruction.

Artifacts: `tests/adopted_lever_consumers.json` (the verdicts),
`tests/test_adopted_levers_are_consumed_across_repos.py` (the guard, wired into
`MONEY_TESTS`).

## The structural answer first

`nfl2`'s money path takes its configuration from **three independent sources, none of which
is the adopted policy**:

1. `PRODUCTION_ENV` in `nfl2/src/nfl2/pipeline.py` — a hardcoded dict of **five keys**
   against the policy's **75**;
2. `os.environ` reads scattered through `core/lineup.py`, `core/game_sim.py` and
   `live_week.py`;
3. **CLI arguments** — dose is `a.lev` / `a.boom` from `live_week.py`, not `N_LEV` / `N_BOOM`.

There is no import, no shared constant and no assertion linking the two repositories.
`config_manifest.py` cannot see any of this: it inspects six `nfl_dfs` modules and contains
the string `nfl2` zero times.

## Verdicts

| status | n | meaning |
|---|---:|---|
| `off` | 21 | declared `0`; the family is disabled, so a downstream gap cannot change a lineup |
| **`dead`** | **20** | **declared here, not consumed by the money path** |
| `consumed` | 16 | nfl2 reads the key |
| `shadowed` | 6 | nfl2 implements the same concept with its **own literal**; equal today, unguarded |
| `production_side` | 6 | consumed in `nfl-predictions` before nfl2 runs |
| `needs_production_confirmation` | 6 | declared `""`, unread by nfl2; only production knows if `""` is inert |

### The dead ones that are non-zero, which is where the money is

`N_QB_VARIANTS=4`, `N_GAMESTACK=4`, `N_DARKGAME=10`, `N_EPISTEMIC=12`,
`REPLACEMENT_SLOTS=12`, plus `OWN_MODEL` (the chalk fade, already proven).

**Proof, by call-path trace rather than grep.** `generate_candidates`
(`pipeline.py:463–478`) builds exactly two families: `lev` via
`optimize_many(..., objective_col="proj_tourney")` and `boom` via per-world
`optimize(..., objective_col="proj_sim")`, plus optional `extra_profiles`. The money path's
call is `live_week.py:218` with `extra_profiles=_profiles`, and `_profiles` is `None` unless
the `--nobb-sleeve` research flag is set. **There is no QB-variant, gamestack, darkgame,
epistemic or replacement-slot construction anywhere in nfl2.**

`N_QB_VARIANTS` is named in CLAUDE.md's adopted stack. It has never run on the money path.

### `shadowed` is the category I would watch

`MAX_OVERLAP`, `MIN_GAMES`, `SERVED_POSITION_SCALES`, `GAME_SIM_MODE`, `TABPFN_MARGINALS`,
`SIM_WIDEN_DRAWS`. Each is declared in the policy **and** hardcoded independently in nfl2,
and **every one is equal today** — I compared them literal-for-literal rather than assuming.
They are not bugs; they are unguarded coincidences that will diverge the first time someone
changes one side.

**`MAX_OVERLAP` nearly became a false finding.** The policy declares `7`; `optimize()` at
`core/lineup.py:279` defaults `8`, which looked like a live divergence. It is not:
`optimize_many` at `:506` — the LEV family — defaults `7`, and the boom loop passes no
banned lineups, so the `:279` constraint is inert. Checked before reporting.

## Restoration cost for the dead non-zero levers

| lever | cost | note |
|---|---|---|
| `OWN_MODEL` | **low** | one argument at `live_week.py:191`, plus the port; equivalence harness already proven bit-exact (`1057e9e6`). **But the two-slate A/B says do not ship it** (`8dd64a78`). |
| `N_QB_VARIANTS` | **high** | no construction exists in nfl2; this is a new generation family, not a wiring fix |
| `N_GAMESTACK`, `N_DARKGAME` | **high** | same — families that exist in `nfl_dfs` and were never ported |
| `N_EPISTEMIC`, `REPLACEMENT_SLOTS` | **high** | same |

The honest summary: **only one dead lever is cheap to restore, and the evidence says not to.**
The rest are unported generation families. Whether they are worth porting is a research
question — several were measured in the `nfl_dfs` replay era, and the ledger's own conclusion
is that no lever moved the book more than ~2 points.

## The guard

`test_adopted_levers_are_consumed_across_repos.py`, three tests, in `MONEY_TESTS`:

1. **every** adopted lever has a reviewed status — fails closed on a new lever;
2. every status is well-formed and carries a proof string ("a status without proof is folklore");
3. when nfl2 is reachable, recorded statuses are re-verified against the live source.

**Mutation-tested, and one mutation exposed a real flaw in my own design.** The first version
filtered to levers with non-zero declared values, reasoning that an inert lever cannot change
a lineup. **Mutation M1 — deleting `OWN_MODEL`'s entry — passed**, because `OWN_MODEL` is
declared `""`, and `""` *selects the naive fade* rather than disabling it. The guard would
have skipped the exact defect it was written for. Now every lever needs a status and `off` is
a claim someone made, not an inference from a literal.

| mutation | first version | shipped version |
|---|---|---|
| M1 drop `OWN_MODEL` entry | **survived** | caught |
| M2 call a dead lever consumed | caught | caught |
| M3 empty proof string | caught | caught |
| M4 drop an `off` lever entry | n/a | caught |

Test 3 also needed correcting: a bare substring match called `N_LEV`, `N_BOOM` and
`N_DARKGAME` "consumed" when they appear only as local constants in a research script and
inside a **comment**. It now strips comments and matches actual `environ.get("KEY")` /
`env["KEY"]` reads. That is the same "a grep is a hypothesis" lesson applied to the guard
itself.

## Six questions only production can answer

`DST_CORR_DRAWS`, `EMP_POS`, `GEN_POOL_CAP_MAP`, `PUNT_BOOM_WR`, `ROOKIE_WIDEN`,
`TABPFN_MARGINAL_TABLE` are declared `""` and unread by nfl2. Whether `""` is inert or
selects a default is production-side semantics I cannot determine from nfl2 — and `OWN_MODEL`
proves `""` can mean "apply the fade". They are marked `needs_production_confirmation` so
they cannot be quietly assumed either way.
