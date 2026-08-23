# Review of the external reviewer briefing

Date: 2026-08-15. Target under review:
`reports/2026-08-15-external-reviewer-briefing.md` (untracked at time of
review). Every claim below was checked against the code, `HANDOFF.md`, the
frozen reports, or a live BigQuery query. Verification method is stated for
each item.

Second question answered in §5: whether the Fantasy Points and SIS data are
being used effectively.

---

## 0. Verdict

The briefing is well-conceived and the framing is right — the "what not to
read" section and the four-channel table are genuinely the two most useful
things an outside reviewer could be handed, and the mechanical note about
TabPFN coverage versus LightGBM ranks is correct and non-obvious.

It is not yet safe to send. Five claims would actively mislead a reviewer, and
one of them (§4) is the claim the briefing tells the reviewer should govern the
entire review. Three of the five are cases of the briefing doing exactly what
its own §2 warns against: citing a report without checking whether a later
document corrected it.

Fix the five items in §1 below and the document is strong.

---

## 1. Blocking corrections

### B1. The §4 forensic numbers are provisional, and the briefing presents them as settled

**This is the most serious item.** §4 states the H/P/C/S gaps (3.58 / 78.99 /
5.01), the 44-of-54 first-failed-layer count, the salary-floor conclusion, and
the +42.6 recourse ceiling as established fact, and then instructs the reviewer
that this "should govern the whole review."

`HANDOFF.md` (current state, 2026-08-15 05:24 CDT) records that a post-forensic
review found a **material scope defect** in exactly that attribution:

> the frozen oracle required only QB+1 and no bring-back, while every
> production candidate was generated under QB+2 plus one opponent bring-back.
> A read-only audit of the retained repair4 warehouse shows 49/54 published
> CBWU P rosters violate QB+2, 36/54 violate the bring-back and 51/54 violate
> at least one production stack rule. The published 78.994-point P-C gap and
> associated threshold/first-failed-layer counts are therefore provisional.

So the P layer was solved under looser constraints than C was generated under,
which inflates P−C by an unknown amount. The correction is *in flight right
now*: `reports/2026-08-15-post-forensic-exact-stack-addendum-protocol.md`,
implemented at `src/nfl_dfs/research/post_forensic_construction.py`, with
replacement build `3b875c6f-53c3-44ce-817b-8b3dca5b67f1` submitted and the
handoff's exact next action being "poll the build, harvest its immutable digest
and then run the correction once on Cloud Run."

Two downstream claims in §4 inherit the same defect:

- **Salary floor.** HANDOFF records SHA `7619517…` as adding "the exact-stack
  no-floor recheck so the salary-floor conclusion is not inherited from the
  loose oracle." §4's "the $49,000 minimum-salary floor costs nothing" is
  therefore also pending recomputation.
- **Recourse ceiling.** HANDOFF: "the published perfect-information recourse
  ceiling also inherited QB+1/no-bring-back… The original +42.62 recourse
  number is provisional." §4 quotes +42.6 with a caveat about hindsight but not
  about validity.

The §3 channel table also depends on this: "Generation — **where the loss is**
(§4)" is the provisional conclusion, not a measured one.

**Fix.** Do not delete the numbers — the qualitative ordering (construction ≫
selection) is very likely to survive, since C−S = 5.01 is computed under
production constraints on both sides and is unaffected. State it as: the gap
ordering is robust; the magnitude 78.99 is provisional pending the exact-stack
addendum; a reviewer should treat "construction dominates selection" as the
finding and "79 points" as an upper-biased estimate. If the addendum lands
before you send this, use its numbers instead.

### B2. SIS pass-tail is listed as rejected; it passed both of its gates

§2 lists under mechanisms that are "**not** in production" and closed:

> SIS: team context, QB line, RB run defense, **pass-tail marginal**, run-tail
> Boom/Bust, team pass-defense coverage schema

Four of those six are correct. The pass-tail marginal is not. It is the single
vendor-data mechanism in the project's history that has cleared a gate:

- `reports/2026-08-13-sis-pass-tail-final-served-result.md` — "**Pass.** The
  three-feature SIS opponent pass-tail marginal arm passed every registered
  final-served calibration gate" (pinball ratio 0.99503, QB and TE improving,
  max row-mean change 7.11e-15).
- `reports/2026-08-14-sis-pass-tail-exact80-result.md` — five-seed exact-80
  tail grid `+2/+2/+3/+1` at 220/210/200/194; the frozen tail-first rule
  "selects **treatment** at the first differing threshold, 220."
- `reports/2026-08-14-final-preseason-forensic-result.md` — "remains a valid
  selected historical research result… It is not part of the K=1 money policy
  because its cache and schedules were never tested in that composition."
- `reports/2026-08-15-prospective-sis-pass-tail-finite-k-protocol.md` — a
  frozen prospective shadow, and item **4** of the forensic report's binding
  next program.

Not-in-production and rejected are different states, and the briefing collapses
them. This one is *selected, unadopted, and scheduled*.

Consequently §3's marginal-channel status — "**exhausted** — ~12 arms, all
failed" — is also wrong as written. The honest version is: ~12 arms, one
selected and awaiting a prospective shadow, the rest failed.

### B3. The ownership chalk fade is in production; the briefing says fade objectives were rejected

§2 lists as not in production:

> Ownership "fade" objectives (`OWN_MODEL=fade`, `milly_fade`)

The code says otherwise. `src/nfl_dfs/backtest/replay.py:58-70`:

> `OWN_MODEL` env, normalized. Default `""` ADOPTED 2026-08-05 (Addenda
> 77/80/84): **the chalk fade STAYS** (its true deletion cost ~2 tails in both
> builds) but runs on NAIVE ownership — the trained booster added nothing in
> the fade… falsy spellings mean **naive-fade**

`ADOPTED_CLASSIC_POLICY` pins `OWN_MODEL: ""`
(`src/nfl_dfs/inference/production_policy.py:165`), which is precisely the
naive-fade path. What was rejected is the *booster ownership estimate inside*
the fade and the field sampler, not the fade objective.

A reviewer reading §2 will conclude the optimizer has no contrarian term at
all. §5's production description reinforces that error — it lists the selector,
floor, stacking, blend and generator mix, but never mentions the chalk fade,
`LEVERAGE_PENALTY`, or `lev_scale` at all, even though `contest_entry_policy`
in the same production module caps leverage by contest size (0.70 / 0.80 / 0.90
/ 1.00). That is a real, live piece of the objective function that is currently
invisible to the reviewer and mislabeled as dead.

(Related, worth fixing in code rather than the briefing: `replay.py:941` still
carries the stale comment "OWN_MODEL default 'fade' ADOPTED 2026-08-04", which
contradicts the `own_mode()` docstring 880 lines above it.)

### B4. The world count is wrong

§3 says "Possession simulator → **30,000** correlated worlds"; §5 repeats
"30,000 worlds."

The adopted policy is CBWU multi-seed with five registered seed pairs and
`multiseed_worlds_per_block = 10_000`
(`src/nfl_dfs/inference/production_policy.py:105-112`). `public_identity()` at
line 326-328 computes `selection_worlds = 5 × 10,000 = 50,000`. The inner
per-seed build is called with `n_sims=worlds_per_block`
(`live_lineups.py:507`), and `live_lineups.py:478-482` **hard-fails** if
`n_sims` disagrees with the block size.

`LIVE_SIMS=30000` in the policy env is real but applies to the projections job
(`run_projections.py:266`), not to the lineup book. The correct statement is:
five candidate/world blocks of 10,000 possession-simulated worlds each, 50,000
worlds of selection evidence; the projections table is generated at 30,000.

A reviewer reasoning about simulation cost, world-coverage saturation, or
selector variance from "30,000 worlds" will get the structure wrong — and the
five-block structure is exactly the sort of thing an outside reader might have
useful opinions about.

### B5. §6 omits the work that is actually in flight

§6 lists three things and says "Historical experimentation is **closed**." The
statement about closure is right, but the list is missing the items the
forensic report itself designated binding:

| in flight / frozen | status | in §6? |
|---|---|---|
| Post-forensic exact-stack addendum | build `3b875c6f…` submitted, run pending | no |
| SIS pass-tail finite-K 2026 shadow | protocol frozen 2026-08-15 | no |
| Structural-archetype budget-neutral CBWU shadow | `CBWU_ARCHETYPE_SHADOW` implemented in production_policy | no |
| Latent role-state shadow | protocol frozen | yes |
| Construction + recourse program | frozen | yes |
| Delete isolated forensic warehouse before first 2026 build | required, not done | no |
| Week 1 UI→DK CSV dress rehearsal | required, not done | no |

The first row matters most: a reviewer who spends effort re-deriving the
construction gap should know it is being recomputed this week.

---

## 2. Smaller factual corrections

| # | claim | actual | source |
|---|---|---|---|
| C1 | "roughly **200** documents in `reports/`" | 240 top-level `.md`, 245 including subdirectories, 316 entries total | `find reports -name '*.md'` |
| C2 | `replay_candidates` "~301k candidate lineups over 14 panels" | **420,713** rows over **20** distinct `panel_run_id` | live BQ query |
| C3 | `slate_player_features` "~1.9M player snapshots" | **3,319,831** | live BQ query |
| C4 | §7 dataset table | omits `nfl_backups` (5 datasets exist) | `bq ls` |
| C5 | §4 uses "54 slates" | never introduced; §1 sets the panel at 107. The forensic decomposition runs on the 54 comparable 2023–2025 slates | forensic report §"Current exact-80 baseline" |
| C6 | §5 "Generator mix: role 12 / boom 40" | also `N_QB_VARIANTS=4`, `N_GAMESTACK=4`, `N_DARKGAME=10`, `CAND_MULT=2`, `GEN_TOTAL_BUDGET=52` | `production_policy.py:169-187` |
| C7 | §2 lists `CLAUDE.md` in the authoritative set with no caveat | `CLAUDE.md:69-268` embeds a "Handoff state (2026-08-05)" block that describes a **superseded** stack — `MODEL_ENSEMBLE=3` (production is K=1), a 27/107 headline, and the pre-CBWU policy | `CLAUDE.md` vs `production_policy.py` |

C2/C3 are not important in themselves, but they suggest the briefing was
drafted against an older snapshot, which is worth knowing before trusting its
other numbers.

C7 is worth handling explicitly. The briefing's central instruction is "don't
infer current behaviour from stale documents," and then it points the reviewer
at a file whose second half is a stale handoff. Either add "read `CLAUDE.md`
only through the end of the Rules section" or trim that block out of
`CLAUDE.md` — it has been superseded by `HANDOFF.md` for ten days and it is the
single most likely source of reviewer confusion in the repository.

Note on C2's panel count: the forensic report's "14 complete 107-slate panels"
is a different quantity from 20 distinct `panel_run_id` values (some are
54-slate arms or smokes). If the briefing wants to give a reviewer a number to
query against, give both and say which is which.

---

## 3. Claims verified correct

Recorded so you know what was checked and passed, and so a reviewer challenging
these can be answered quickly.

- **TabPFN marginal coverage is 100%.** Verified directly, not taken on faith.
  For salary-listed QB/RB/WR/TE rows, coverage is 100.00% in every panel season
  (2019: 6,226/6,226; 2021: 6,922/6,922; 2022: 13,246; 2023: 13,084; 2024:
  13,132; 2025: 12,845) and 0% in 2016–2018 and 2020, which are outside the
  panel. The §3 mechanical argument therefore holds exactly as stated.
- **The shaping mechanism.** `_tabpfn_marginals` (`replay.py:551+`) rank-remaps
  each player's draws onto cached per-player quantiles with linear tail
  extrapolation beyond q01/q99, leaving the copula untouched — as §3 describes.
  One subtlety worth adding: rows *without* a cached prediction keep their raw
  widened draws and do **not** fall back to `_empirical_marginals` (the fallback
  is all-or-nothing at the table level, `replay.py:366-372`). Irrelevant at 100%
  coverage, but it becomes a live train/serve concern the moment a 2026 week
  ships with a partial cache.
- **~250 candidates/slate.** Measured 252.7–254.6 per slate across recent
  panels.
- **The dependence table (§5).** All six values match the repaired-path
  sources: QB→WR 2.418 sim vs 3.323 realized, multiplicity ≥3 2.377 vs 1.835,
  ≥4 6.175 vs 2.333 (`2026-08-14-td-ledger-closure-agreement-and-scorecard-invalidation.md`,
  `-reconciliation.md`). The direction claim (hub under-coupled, multiplicity
  over-produced, no single global parameter fixes both) is correct and is the
  G2 result.
- **The pre-repair warning.** `26e73c5` is real, dated 2026-08-13, "Repair
  season replay usage allocation units," and it did move QB→WR from 1.064 to
  2.418. The instruction to distrust pre-08-13 reports citing ≈1.05 is correct
  and is one of the most valuable lines in the briefing.
- **Production policy details.** Policy id, K=1 / `tail_k1`, tail line 194, 80
  entries, $49,000 floor, 45/55 blend, position scales
  QB 0.970 / RB 1.005 / TE 0.940 / WR 1.070, Dirichlet K = 28.154043586960896 —
  all match `production_policy.py` and the code constants.
- **Route share rejected in both channels.** Confirmed by disposition:
  `route-rank-dependence-i1-fails`, `route-rank-dependence-r2-fails`,
  `tabpfn-route-channel-final-served-fails`.
- **Forensic gap arithmetic.** 3.583 / 78.994 / 5.007 and the 44/3/0/7 counts
  match the frozen report exactly (subject to B1's validity caveat).

---

## 4. What the briefing should add

These are omissions rather than errors, ordered by how much reviewer effort
they would save.

1. **The decision rule.** §1 says the objective is "the single best score among
   the 80 entries," which is directionally right but is not the rule actually
   used. The frozen rule is a tail-count grid at 187/194/200/210/220/230/240
   compared **highest threshold first**, with mean as a secondary diagnostic.
   That is why CBWU was adopted while *losing* a ≥194 crossing. Without this, a
   reviewer cannot understand a single adoption decision in the repository —
   and §8's warning about "the mean as objective" doesn't tell them what
   replaced it.
2. **The measurement noise floor.** The forensic report puts arm identity at
   4.71% of weekly-max variance, with a minimum detectable paired difference of
   ≈3.865 mean points, ≈9.2 weeks at ≥200 and ≈6.33 weeks at ≥210. A reviewer
   who doesn't know this will propose mechanisms that cannot be measured on this
   panel even if they work. This belongs in §8 next to the validation law; it is
   arguably the single most important constraint on what a useful suggestion
   looks like.
3. **How a proposal actually gets run.** Preregistered protocol → frozen
   success criterion → immutable image digest → single Cloud Run execution →
   frozen report + GCS artifact. §8 states the law but not the machinery, so a
   reviewer can't calibrate how expensive their suggestion is to test.
4. **Contest structure.** §1's "~160,000-entry contest" is one contest. The
   code supports entry caps 1–150 with four leverage profiles, and the forensic
   report shows a prefix of the 80-entry book is materially worse than a
   purpose-built small book (20 entries: 165.9 mean / 5 at ≥194, vs 80 entries:
   176.1 / 8). Low-max contest selection is an open, unsolved, clearly-scoped
   problem — a good candidate for outside input, and currently invisible.
5. **The ownership/leverage term** (see B3) — it is part of the objective and
   should appear in §5's production list.
6. **A freshness stamp.** Give §5 and §7 a "verified as of <date> against
   <commit>" line, and mark §4's numbers provisional. The repository's own
   discipline is that a number without provenance is not citable; the briefing
   should hold itself to it.

---

## 5. Are the Fantasy Points and SIS data being used effectively?

Short answer: **no, and the reason is structural rather than a modelling
failure.** Every vendor arm to date has been fired into the channel with the
least measured headroom, and the one arm that worked is the one the briefing
mislabels as rejected.

### 5.1 What is actually there

| source | tables | coverage | wired into feature SQL? | in production model? |
|---|---|---|---|---|
| Fantasy Points ($200 Data Suite, 2026-08-10) | 13 in `nfl_raw` | route share 27,305 rows, **2022–2025 only** | **1 of 13** (`fantasy_points_route_share` → `017k` → `player_week_fp_route`) | no |
| SIS (DataHub Pro NFL, activated 2026-08-13) | 3 in `nfl_raw` | team context / run context 3,230 rows **2019–2025**; alignment attempts 4,077 rows **2022–2025** | **1 of 3** (`sis_team_run_context_game`) | no |

The other 12 FP tables and 2 SIS tables are reachable only from Python research
modules. That is a legitimate research pattern, but it means any adoption
carries an unbudgeted cost — new feature SQL plus a `features/leakage.py`
family — that is currently invisible when an arm is greenlit. Price it into the
arm decision before the arm runs, not after it passes.

Credit where due: the vendor columns in `player_week_training` carry
`fp_route_source_season`, `fp_route_source_week`, `fp_route_source_sha256`,
`fp_route_prior_observations` and `fp_route_fallback`. That provenance design
is better than most of what these features have been used for.

### 5.2 Finding 1 — the arms are diluted before they start

This is measurable and I think under-appreciated. For salary-listed WR/TE rows
across the six panel seasons:

| season | rows | `fp_route_share_l4` non-null | % |
|---:|---:|---:|---:|
| 2019 | 3,813 | 0 | **0.0** |
| 2021 | 4,316 | 0 | **0.0** |
| 2022 | 8,230 | 5,230 | 63.5 |
| 2023 | 8,132 | 6,348 | 78.1 |
| 2024 | 8,282 | 6,778 | 81.8 |
| 2025 | 7,959 | 6,502 | 81.7 |

**24,858 of 40,732 rows — 61.0% panel-wide, and structurally zero on two of six
seasons.** A six-season panel arm on an FP route feature is therefore an arm
whose treatment is inert on a third of the evidence, evaluated against a
detection floor of ≈3.865 mean points and a LOSO rule of ≥4-of-6 seasons with
≤1 negative — a rule that two guaranteed-null seasons make close to unpassable
on merit. SIS alignment (2022–2025) has the same shape.

I would not read the FP failures as "route share carries no signal." I would
read them as "the panel design cannot resolve a signal that is absent on 39% of
rows." Those are different conclusions with different next actions.

**Recommendation.** For any vendor-sourced arm, preregister the **2022–2025
subpanel as the primary evaluation window**, with the six-season panel reported
as secondary. This is not panel mining — the restriction is a data-availability
fact fixable in advance and is falsifiable exactly as before. It should be
written into the validation law as a named exception, so that it is a rule
rather than a per-arm judgment call.

Worth noting: SIS *team context* covers 2019–2025 in full, so SIS team-level
features do not have this problem. That is one more reason the pass-tail result
(the SIS arm that passed) may not be a coincidence.

### 5.3 Finding 2 — every vendor arm was fired into the wrong channel

Place the vendor arms in the briefing's own four-channel frame:

| vendor arm | channel | outcome |
|---|---|---|
| FP route share (marginal) | marginal | fail |
| FP route rank i1, r2 | copula, per-player rank | fail |
| FP advanced prior, coverage fit, same-season coverage, route shape, QB shell, defense PROE | marginal | fail |
| SIS team context, QB line, RB run defense, run-tail | marginal | fail |
| SIS team pass-defense coverage schema | acquisition gate | fail |
| **SIS pass-tail** | marginal | **pass, unadopted** |

Not one vendor arm has ever acted in the **generation** channel. Per the
project's own decomposition, generation is where ~79 of ~88 lost points live
(provisional per B1, but the ordering is not in doubt). The vendor data has been
spent almost entirely on the channel the briefing itself labels exhausted.

The rank-channel arms are the near-miss: they moved the copula, but only through
a per-player feature in LightGBM, which reorders individuals. They never touched
**structure** — who is on the field together, in what personnel grouping,
against what coverage shell.

### 5.4 Finding 3 — the untried use is the one that matches the known defect

The measured dependence error is specific and unusual: the QB hub is
**under**-coupled (2.42 vs 3.32) while multiplicity ≥3 and ≥4 are
**over**-produced (2.38 vs 1.84; 6.18 vs 2.33). G2 proved a shared global factor
cannot fix both, because anything that raises QB→WR also raises WR–WR.

That is a *structural* mismatch, and structure is exactly what the vendor
subscriptions sell and what nflverse does not have. The SIS inventory
(`2026-08-13-sis-nfl-subscription-inventory.md`) lists splits by offensive
personnel, formation, coverage shell, route, target alignment, pressure, play
action, RPO and motion, for 2015–2025. FP carries alignment (player and team
`_l4`) and route shape. None of it is used for dependence.

Three concrete proposals, each in the copula or generation channel, each
falsifiable under the existing law:

**(a) Personnel-conditioned allocation — attacks the multiplicity overshoot.**
Today the within-team allocation is a single fitted Dirichlet with global
K = 28.154. One concentration parameter for all game states is precisely the
mechanism that makes every pass-catcher co-boom, which is the ≥4 overshoot
(6.18 vs 2.33). Condition K — or the Dirichlet's mean vector — on the team's
strictly-prior personnel/formation mix from SIS or FP alignment. 11-personnel
shootout states genuinely spread targets; 12-personnel grind states genuinely
concentrate them. Falsification: the existing G0 co-exceedance harness,
pre-registered on multiplicity ≥3 and ≥4 moving toward realized without
degrading QB→WR. Channel: copula. New data: no — `sis_team_context_game` and
`fantasy_points_alignment_team_l4` are already ingested.

**(b) Pairwise QB→receiver coupling — attacks the under-coupled hub.** G2 closed
the *shared-factor* family, not the *pairwise* family. SIS route × target
alignment × coverage-shell splits support a receiver-specific coupling: a
boundary X against man is a different QB-hub partner than a slot receiver
against zone. A pairwise coupling can raise QB→WR₁ without dragging WR₂ along,
which is the exact shape a shared factor mathematically cannot produce.
Falsification: same harness, pre-registered on QB→WR rising toward 3.32 with
WR–WR and multiplicity ≥3 not rising. Channel: copula. New data: SIS acquisition
of route/alignment splits at player-week grain — which is where the acquisition
budget should go.

**(c) Football-structural archetypes for the budget-neutral allocator.** The
forensic report found high-scoring candidates concentrate in lineup-embedding
space (7.81× local enrichment, modularity 0.479 vs 0.180) and the archetype
allocator is already built (`CBWU_ARCHETYPE_SHADOW`). Its archetypes are derived
from *lineup* structure. Vendor alignment and personnel data would let
archetypes be defined by *football* structure — "12-personnel play-action
game-script stack," "condensed-formation deep-shot stack" — which is portable
across seasons in a way historical player communities explicitly are not.
Channel: generation, the one with the headroom. New data: no.

### 5.5 Finding 4 — acquisition breadth is the SIS bottleneck, and it is being spent on the wrong fields

The SIS paid UI returns at most 200 rows per query, the guarded exporter works
under a hard 10-request ceiling, and the pass-defense schema arm consumed 9 of
10 requests to produce a **fail**. Under that constraint, acquisition order is
the highest-leverage decision in the whole SIS program, and so far it has gone
to per-player marginal fields feeding the exhausted channel.

**Recommendation.** Re-prioritize the SIS acquisition queue around §5.4(b) —
route, target alignment, coverage shell at player-week grain — and treat
per-player pass/rush *value* metrics as second priority. The one SIS arm that
passed was a defense-side team-level tail feature with full 2019–2025 coverage;
that is a hint about where this vendor's usable signal actually lives.

### 5.6 Bottom line on vendor spend

- Money committed: $200 FP Data Suite plus an active SIS DataHub Pro NFL
  subscription.
- Production adoption to date: **zero features from either vendor.**
- Selected-but-unadopted: one (SIS pass-tail), currently mislabeled as rejected
  in the document under review.
- Root causes, in order of size: (1) arms fired into the exhausted marginal
  channel; (2) six-season panels diluted to 61% treatment coverage by a
  2022–2025 data window; (3) SIS acquisition budget spent on marginal fields.

None of that argues for dropping the subscriptions. It argues that the vendor
data has never yet been used for the thing it is uniquely good at — structure —
and that the structure channel is where the forensic result says the points are.
I would set an explicit, preregistered renewal review date tied to (i) the 2026
SIS pass-tail shadow and (ii) at least one of the §5.4 dependence or generation
arms actually running.

---

## 6. Suggested edit list

Blocking:

1. §4 — mark the H/P/C/S magnitudes, the salary-floor conclusion and the +42.6
   recourse ceiling as provisional pending the exact-stack addendum; keep the
   gap *ordering* as the finding.
2. §2 — move SIS pass-tail out of the rejected list into a new "selected but not
   in production" row; fix §3's marginal-channel status accordingly.
3. §2 / §5 — correct the ownership entry to "booster ownership inside the fade
   rejected; naive chalk fade is in production," and add the fade and the
   contest leverage caps to §5's production list.
4. §3 / §5 — correct the world count to five blocks × 10,000 = 50,000 selection
   worlds; note `LIVE_SIMS=30000` applies to the projections job.
5. §6 — add the in-flight addendum, the SIS pass-tail shadow, the archetype
   shadow, and the two pre-2026 obligations (delete the forensic warehouse,
   Week 1 CSV rehearsal).

Non-blocking: C1–C7 in §2 above; the six additions in §4 above, of which the
decision rule and the noise floor are the two that most change what a reviewer
can usefully produce.
