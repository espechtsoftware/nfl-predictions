# Pre-forensic exhaustion review: what is closed, and what is not

Date: 2026-08-14. A check, before the arm program closes, on whether the
scoring opportunities and the three paid data sources have actually been
exhausted. **No code was changed. No new outcome was queried.**

---

## Verdict

**Two of three paid sources are not exhausted, and one designed mechanism was
invalidated rather than adjudicated.** Everything else is genuinely closed.

Critically, most of what remains **does not require another historical arm**.
Data acquisition and prospective wiring can proceed in parallel with the
forensic program without violating the closure sequencing. Only one item — the
TD-ledger repair — is a candidate for one more arm, and it is a repair of an
existing test rather than a new idea.

---

## 1. Genuinely exhausted

| area | evidence |
|---|---|
| **Fantasy Points** | Route share tested in **both** channels — marginal (`tabpfn-route-channel-final-served-fails`) and rank (`route-rank-dependence-i1-fails`, then `route-rank-dependence-r2-fails`, the last actively harmful at a 2.07 loss ratio). Advanced prior failed. Coverage families closed under the grain bind. Same-season `Week(s)` window reconstruction was collected and its Advanced Receiving arm failed. Weekly Target/Snap/PROE correctly closed as redundant. |
| **Selector** | Closed five-plus ways; selected equals pool oracle at 220/230/240; resampling diagnostic run (historical R0-only 54.28/80 disjoint-half overlap; superseded for standing use by the width-qualified `reports/2026-08-16-simulation-law-ledger.md`, plus 1.28pp coverage optimism); bagging refuted algebraically. |
| **Marginal feature channel** | Nine-plus arms across four families. |
| **Shared-factor copula** | G2 closed it for WR mathematically — one factor cannot give QB↗WR with WR⊥WR. |

Fantasy Points in particular is done. I would not spend anything further on it
beyond the licensed 2026 prospective shadow.

---

## 2. The TD ledger was invalidated, not adjudicated — highest-value remaining item

`td-ledger-final-served-v2` returned `td-ledger-invalid-or-inconclusive`. The
reason is **not scientific**: all substantive gates and material-regression
guards passed, sorted draw multisets were exactly equal, and player-mean drift
was `7.1e-15`. It failed only because the *control* no longer reproduced the
frozen G1 variogram values within `1e-12` — the 13 relationship variograms moved
by `2.8e-10` to `1.28e-8`, an expected consequence of changing the incumbent's
shared floating-point transform.

So the mechanism was never actually measured.

This matters more than an ordinary inconclusive result, because of what the
ledger *is*. G0 measured QB→WR at 1.053 simulated against 3.3228 realized. G2
then established that a shared factor **cannot** close that gap: any θ that
makes both QB→WR correlations positive forces WR–WR positive, and reality shows
WR–WR near independence. A **shared production ledger with competitive
allocation** is the one mechanism class that produces the observed pattern —
shared volume lifts QB→every receiver, competitive allocation cancels the
WR–WR side effect.

It is the only remaining candidate that matches the measured structure, and its
test was lost to floating point.

The result document already specifies the correct repair: leave the incumbent
pipeline byte-for-byte unchanged, take world ranks from the existing
`TD_LEDGER=1` simulation, and permute each unchanged final-served marginal by
those ranks. That makes exact marginal preservation true by construction and
avoids the production-wide numeric change that invalidated v2.

**Recommendation:** run this one. It is score-free, it is a repair of an
existing design rather than a new mechanism, and closing the arm program with
the best-motivated hypothesis unadjudicated would be the wrong place to stop.

---

## 3. Odds API — the largest unexploited paid surface

Current state, measured:

- **10 markets stored** of roughly 25 the API exposes: six base
  (`player_pass_yds`, `player_pass_tds`, `player_rush_yds`,
  `player_reception_yds`, `player_receptions`, `player_anytime_td`) plus four
  alternate ladders.
- **2 bookmakers** (DraftKings, FanDuel) against a documented allowance of up to
  10 counting as one region.
- **2023–2025 only** — three of six panel seasons.

The Priority-3 expansion list in `2026-08-09-data-acquisition-priorities.md` has
sat unexecuted since it was written. Nothing from it has been added.

### 3.1 The item I would prioritise: alternate team totals

This is the best-motivated data acquisition remaining in the project, and it was
not on my earlier lists.

The copula's binding deficiency is the **shared team-level factor** — the latent
that lifts a quarterback and his receivers together. The system currently
consumes `implied_team_total`, a *point estimate* derived from spread and total.

**Alternate team-total ladders give the market's implied *distribution* of team
points** — P(team scores ≥ X) across a range of X — pre-lock, per game, priced
by professionals. That is precisely the object the possession simulator's shared
factor approximates, and it can be used to calibrate that factor per game rather
than leaving it context-free.

This is the same idea as the same-game-parlay proposal but far more practical:
alternate team totals are a **standard market the existing subscription already
serves**, whereas SGP prices are computed on demand and probably unobtainable.
Add alternate game totals alongside for the game-level envelope.

Cost is affordable and bounded: 10 credits per market per event per region, so
roughly 8,160 credits per market across 2023–2025, or about 16,000 for both
ladders — inside the 20,000-credit ceiling the roadmap already set.

### 3.2 Second: volume markets

`pass attempts`, `completions`, `rush attempts` are opportunity **denominators**
— market-implied usage, available pre-lock. The system infers usage from lagged
play-by-play; the market prices it directly. This is the one remaining source of
opportunity information that is neither stale nor derived.

### 3.3 Already closed, do not revisit

Cross-book dispersion and line movement were tested and returned NULL
(Addendum 96). Expanding to ten bookmakers for *dispersion* is closed. Expanding
for *coverage and de-vigging quality* is a different and untested question, but
low priority.

---

## 4. SIS — acquisition incomplete against its own plan

From the coverage-gap audit, unchanged since:

**In the warehouse, untested:**
- **Boom%/Bust%** (`rush_`, `rdef_`, `pdef_`) — the only *tail-shape* fields
  acquired, and every SIS arm tested a central-tendency metric instead. The RB
  arm used `rdef_points_saved_per_play` while `rdef_boom_rate` sat unused in the
  same table. **Screened 2026-08-14 and confirmed non-redundant — see §4.1.**
- **Pass rush, 18 columns** — never used, despite the outcome-blind screen
  identifying SIS pressure rate as the **most distinct** team column
  (`r = 0.4573`) against pass-defense EPA at `r = 0.8803`, which was correctly
  rejected as redundant.
- `pass_on_target`, `pass_catchable` — charting judgments with no nflverse
  equivalent, never used.

**Never retrieved:**
- **Receiving family, entirely** — and it is named in the account's own
  acquisition priority 1 alongside the four families that *were* pulled. WR and
  TE are 23 of the 36 omitted Millionaire-winner slots; the position group where
  the misses concentrate has zero SIS coverage.
- **All player grain** — including the coverage snaps whose absence closed the
  team schema path.
- Three of four priority-1 filtered views.

ASOE was adopted, which vindicates having narrowed that closure. The rest of the
plan remains unexecuted.

### 4.1 Boom/bust redundancy screen — run 2026-08-14, outcome-blind

The single strongest untested candidate against currently available data. This
screen used only strictly-prior last-four-game SIS windows and existing
strictly-prior features. **No realized outcome, projection residual or lineup
score was read.** 3,038 team-weeks.

| SIS field (lagged l4) | nearest existing strictly-prior feature | r |
|---|---|---:|
| `rdef_boom_rate` | `rb_fp_allowed_adj_l6` | **0.1922** |
| `rdef_bust_rate` | `rb_fp_allowed_adj_l6` | **−0.0827** |
| `rdef_boom_rate` | `epa_per_dropback_allowed_l6` | **0.0755** |
| `rdef_boom_rate` | `epa_per_rush_allowed_l6` | 0.5150 |

Read against the project's own established benchmarks:

| reference | r | disposition it received |
|---|---:|---|
| SIS pass-defense EPA | 0.8803 | correctly rejected as redundant |
| SIS pressure rate | 0.4573 | flagged "**most distinct** team column"; never tested |
| **`rdef_boom_rate`** | **0.1922** | never tested |
| **`rdef_bust_rate`** | **−0.0827** | never tested |

**Boom and bust are substantially more distinct than the field the project
already identified as its most distinct candidate**, and bust is effectively
orthogonal to the nearest existing feature.

That is mechanically coherent rather than surprising: fantasy points allowed and
EPA are **mean** quantities, while boom rate is a **tail frequency**. They
measure different things. Even the 0.5150 against `epa_per_rush_allowed_l6` —
the closest conceptual match, both describing run defense — leaves roughly 73%
of variance unexplained.

So boom/bust is simultaneously: already paid for, already in BigQuery,
demonstrably non-redundant, the only tail-shape family acquired, and untested —
while every SIS arm that *did* run tested a central-tendency metric and failed.

This screen is a redundancy audit, not a preregistered diagnostic. It
establishes that an arm is *warranted*; a formal protocol would still need to
freeze support counts, per-season stability, the exact feature block and the
gate before any outcome is joined.

---

## 5. Other opportunities still open

- **The field/payout objective.** Unbuilt, gated on 2026 standings. Still the
  largest single item in the project and the only one that changes what is being
  optimised rather than what is believed.
- **Per-contest portfolio slicing.** Prospective, never implemented; the
  entries curve exists to price it.
- **Marginal × copula factorial.** The running multi-seed factorial is
  candidate × world, which is a different question. A marginal-channel feature
  crossed with a dependence mechanism has still never been run — and after the
  ledger repair would be the natural place for it.

---

## 5a. Does acquisition contaminate the repaired ledger arm?

Substantially no — but the boundary needs stating explicitly, because it is not
where the phrase "acquisition/prospective work" naturally lands.

**Safe: raw ingestion.** Writing new tables into `nfl_raw` is inert with respect
to the ledger arm. Nothing it reads — `player_week_training`,
`player_week_inference`, the frozen incumbent caches, the final-served
marginals — is touched by the presence of a new raw table.

**Not safe: a feature rebuild.** The ledger repair's entire premise is *"leave
the incumbent pipeline byte-for-byte unchanged."* A `build-features` run
re-executes every SQL file against upstream sources that may have been revised
since the incumbent caches were built — nflverse revises routinely — and the
project's own PIT repairs demonstrated that rebuilds move real values (3,625
red-zone smoother rows changed on the position-prior fix alone).

This is not a hypothetical risk. **v2 was invalidated by variogram drift of
`2.8e-10` to `1.28e-8`.** A feature rebuild could move things orders of
magnitude beyond that, and the frozen protocol cannot waive it after the fact.

**Also watch: capacity.** Phase S reached a 67% infrastructure failure rate at
30 concurrent cells. Acquisition jobs should not compete for the ledger arm's
execution slots.

**Rule to adopt:** ingest freely; **do not run `build-features` until the
ledger arm has a terminal disposition**; keep acquisition off the ledger arm's
capacity.

One further clarification worth making, because it affects what can start
immediately: **an outcome-blind redundancy or support screen is an audit, not an
arm.** Screens like §4.1 read only strictly-prior features and existing
columns, run as BigQuery queries rather than Cloud Run panels, and consume
neither sequencing nor capacity. They can proceed now. What must queue behind
the ledger is any score-free *model* arm built on their results.

## 6. Recommended sequencing, respecting the closure

**Does not require an arm — start now, in parallel with forensics:**

1. Ingest **alternate team totals and alternate game totals** (§3.1). Feeds the
   2026 prospective copula work and the winning-line model.
2. Ingest **volume markets** (§3.2).
3. Retrieve **SIS team Receiving** (§4) — 32 rows per week, in the account's own
   priority 1.
4. Cost one **player-grain filtered SIS query** to replace the budget assumption
   with a number.
5. **Formalise the boom/bust screen** (§4.1) with support counts, per-season
   stability and the pass-rush and `pass_on_target`/`pass_catchable`
   equivalents. Audits only — no outcome join, no capacity conflict.

**One more arm, and I would make the case for it:**

6. The **TD-ledger rank-coupling repair** (§2), score-free, frozen before
   output. It is the only unadjudicated mechanism that matches the measured
   dependence structure.

**Candidate for a second arm, if §4.1's formal screen holds:**

7. A **boom/bust tail-shape arm**. It is the one place where currently-available
   data, a measured distinctness advantage over the project's own best
   candidate, and the tail objective all line up — and every SIS arm that failed
   tested the wrong class of field. Queue it behind the ledger; it competes for
   the same capacity.

**Then close, and carry into forensics:**

8. Enter every un-acquired and untested item above into the **opportunity
   register as an explicit row**, so the 2026 charter inherits them rather than
   rediscovering them. The register's `prereq` field exists for exactly this.

The forensic program is the right next step. The risk is not that it starts too
early — it is that it starts while three specific data gaps are undocumented,
and a register built without them will look more complete than it is.
