# 2026 Route Share prospective shadow gate

Status: frozen on 2026-08-11 before any 2026 Route Share observation,
prediction or outcome was available. This is independent prospective evidence;
it does not re-adjudicate the closed historical Route component arm.

## Isolated comparison

Beginning with target Week 2, freeze two player-distribution forecasts before
the shared Sunday-main lock:

- control: the then-live K=1 component model and production inputs;
- treatment: the identical fit/simulation path with exactly
  `fp_route_share_last`, `fp_route_share_l4`, `fp_route_share_jump`, and
  `fp_route_cross_season` added.

Both use the same training cutoff, player universe, component definitions,
seeds, simulator, marginal shaper and market blend. The Route model receives
only the manifest-locked source Week W-1 rows available before target Week W.
Every nonnull target record must preserve its exact Route source season/week,
and the mechanical source-order assertion must pass. Missing or unresolved
Route values stay null and use the labeled incumbent fallback. No global
`EXTRA_FEATURES` deployment variable may leak into production.

Persist pre-lock control/treatment player keys, means, draws or reproducible
draw artifact, component predictions, model/data cutoffs, source manifest/hash,
coverage and fallback counts. Score them only after authoritative actuals land.

### Frozen operating identities

The then-live lineup policy is the promoted CE/role expanded policy, so the
paired shadow must compare that complete policy rather than a boom-only
surrogate:

- control base registry `tail_k1` and role registry `tail_k1_role`;
- treatment base registry `tail_k1_route` and role registry
  `tail_k1_route_role`;
- all four registries use one fitted member and the same training rows,
  component laws and cutoff;
- the treatment base adds exactly the four registered Route fields, while the
  treatment role registry adds those same four fields to the control role
  registry's exact six role fields; and
- both arms use the identical `12 CE / 12 role / 28 boom`, seeds, worlds,
  market blend, salary/stack rules, selector and 80-entry count.

The existing `shadow-k1-roleunion` command is the paired control. New command
`shadow-k1-route-roleunion` is the treatment. They freeze at the same early
and late schedule times. The treatment must fail closed if either Route
registry is missing or if a fitted booster does not contain its exact expected
feature contract. No process-global Route feature flag may be added to the
app, ordinary projection job, control registry or control shadow.

Before candidate generation, each arm writes a create-only, hash-addressed
player artifact containing the ordered skill-player keys, final served draws,
all eleven component means, the pre/post-market means, source season/week and
the four Route fields. Its URI/hash and the arm/registry identities are also
stored on the immutable player snapshot rows. A successful shadow execution
therefore proves both the exact-80 book and the player-distribution evidence
needed by this gate were durably frozen before lock.

Week 1 may use only strict prior-season values already present in the historical
Route table and must label them cross-season. Beginning Week 2, a treatment
execution also requires that the target week's manifest-locked Week W-1 import
has completed before training; missing or unresolved players still use the
explicit row-level fallback.

## Minimum evidence and resolution

Do not adjudicate early. A 2026 result is gradeable only after all available
Sunday-main Weeks 2--18 are frozen and scored, with at least 12 complete paired
slates, 2,500 covered RB/WR/TE player-weeks and 40 realized 30-point events.
If those floors are not reached, retain the shadow into 2027; insufficient
support is not a failure.

For every paired proper-loss difference, report row count, event count, mean,
SD, standard error and a 95% interval clustered by slate week. Report the
two-sided 95% minimum detectable absolute difference as `1.96 * SE` and its
percentage of the control loss before assigning a disposition. The interval
and MDE diagnose fragility; they do not silently replace the frozen utility
gate.

## Player-distribution gate

On all covered RB/WR/TE rows, treatment may have its independently frozen
exact-80 lineup shadow adjudicated only if every mechanical guard and all of
these prospective criteria pass:

1. empirical CRPS improves by at least 0.5% (`treatment/control <= 0.995`);
2. the equal-weight mean of q95 and q99 pinball-loss ratios is at most 1.000;
3. absolute q99 exceedance-calibration error does not worsen by more than
   0.10 percentage point;
4. point MAE does not worsen by more than 1%; and
5. 20- and 30-point Brier losses are reported and neither worsens by more than
   1%.

Report every metric by position and week as diagnostics. No segment, window,
feature, support floor or model may be selected from 2026 outcomes. Failure
keeps the incumbent; it does not license a retry.

## Exact-80 scoring gate

Beginning in Week 2, freeze one paired lineup shadow at the same pre-lock time
as the player forecasts so an entire season can be evaluated without hindsight.
Use the then-live exact-80 policy, same entry count, salary/stack/overlap rules,
candidate budgets and selector; change only the Route player distribution.
Never reconstruct an earlier 2026 lineup after its outcome is known. The books
may be stored and mechanically validated each week, but they have no adoption
interpretation unless the player-distribution gate passes first.

At the end of the gradeable prospective sample, compare selected weekly maxima
at 240, 230, 220, 210 and 200 in that order. At the first difference,
treatment passes only when its count is higher, and it must improve at least one
200+ threshold. Exact standings-derived ranks, cashes and payout ROI are
mandatory when the operator's captured contest file supports them, but missing
standings do not fabricate a payout estimate. Means, medians, pool oracle,
weekly wins/ties/losses, coverage and lower score thresholds are diagnostics.

Only a player-distribution pass followed by this future-only exact-80 pass can
license production/UI adoption. Until then Route Share is visible as a shadow
and the incumbent remains the submitted book.

## Amendment 1 (2026-09-19, operator directive) — v2, corrected on the lab's review

Recorded before any 2026 week is graded (Week 2 was forfeited; Week 3 is the
first). v1 of this amendment (same day) proposed interim reads after 6 and 10
graded weeks at a "200+ threshold"; it is withdrawn: the primary above is
lexicographic 240/230/220/210/200, not 200 alone; six complete weeks from
Week 3 would first allow a read at Week 9 and ten at Week 13; and the 12-week,
2,500-row and 40-event floors above would make such interim reads unpassable.

**Unchanged:** the final scientific read after all available Sunday-main Weeks
2-18, with this document's primary, guards and floors, governs permanent
adoption.

**Added:** a separately named **weekly in-season decision record**, one row
per complete paired week from the first (Week 3), reporting the paired
treatment-minus-control result on this document's primary and its guards for
the weeks then available, with the available support (weeks, rows, events)
stated explicitly against the floors — which are never silently waived. The
record is descriptive monitoring, not the scientific adjudication; bounded
in-season use of the treatment may be considered from it under
`reports/2026-09-19-in-season-adoption-track.md` §1 (a candidate-specific
decision record with its uncertainty, control, material-harm criteria and
rollback), and only after the original exact-80 consumer and historical
generation contract are shown to transfer to the current lab K97 / dose. The
frozen contract of this gate (12 CE / 12 role / 28 boom / exact-80) is never
changed in place: a versioned current-policy companion (O-2) states every
generation / env / registry / K / selector setting under which the paired
weeks are actually produced. The checker's `adjudicates` / `in_season_value`
fields for this gate are updated to cite this amendment, with a test (O-13).

## Amendment 2 (2026-10-04, operator decision (a) on O-2/O-25) — companion-v1 contract, graded Weeks 5–18

Recorded before any Week-5 outcome exists: the Week-5 Sunday main locks 2026-10-11. No paired week of this gate has
produced a book or a distribution under any contract since Week 2.

**What happened.**
- **Week 2** was forfeited under the original contract (Amendment 1).
- **Weeks 3 and 4 were lost to failure.** On 09-21 the two jobs' env moved to the current money-path generation
  (N_BOOM=160, N_LEV=40). The image's frozen-settings guard still demanded N_BOOM=28, so all eight executions in
  Weeks 3–4 failed before building anything (`RuntimeError: role-union shadow has incorrect frozen settings`;
  OPEN-DEFECTS O-25). The checker saw scheduler state and env, not run outcomes, so the loss went unnoticed for two
  weeks.
- **The operator chose (a) on 2026-10-04:** run the pair under one declared current-policy contract from Week 5, rather
  than reverting to the August generation (b) or stopping the reads (c).

**Changed (this amendment):**
1. **Contract.** Executions must declare `ROUTE_SHARE_CONTRACT`. Live 2026 runs from Week 5 must declare
   `companion-v1`. Its settings are derived from `ClassicProductionPolicy.engine_environment()` and pinned by tests:
   - GEN_TOTAL_BUDGET=172, N_LEV=40, N_CE=0, N_EPISTEMIC=12, N_BOOM=160, N_GUMBEL=0, REPLACEMENT_SLOTS=12,
     BOOM_UNIQUE_FILL=0;
   - EPISTEMIC_FAMILY=role_draws, with ROLE_BELIEF_FEATURES = the six role features (target/carry/snap share last and
     jump);
   - ROLE_BELIEF_SEED=7331, CE_SEED=1701, BLEND_MODEL_WEIGHT=0.45, LIVE_SIMS=30000, GAME_SIM_MODE=possession;
   - SERVED_POSITION_SCALES=QB:0.970,RB:1.005,TE:0.940,WR:1.070, MODEL_ENSEMBLE=1, MIN_LINEUP_SALARY=49000;
   - a single seed (MULTISEED_* unset), the adopted construction preset, and an exact-80 book.

   Settings identity, sha256 over the canonical serialization in `src/nfl_dfs/inference/tail_shadow.py::check_route_share_contract()` (`sha256(json.dumps(dict(sorted(settings.items())), sort_keys=True, separators=(",", ":")))`, all values strings, contract name not hashed; branch `production/o25-route-share-companion-20261005` @ `4572d6ad`; pinned by `test_contract_settings_sha256_is_the_published_identity`; every receipt carries it as `route_share_contract_settings_sha256`): companion-v1 `76c3994a0d9d4bb4bc852a60569c535a8306458b5be7a2a9c254a7d851f96ee8` (18 keys);
   frozen-2026-08 `345d3ca925564663490f20c5809be104c8171d86cd2c85990681cc874888fd91` (10 keys). The two arms differ only in MODEL_REGISTRY_VARIANT (`tail_k1` vs `tail_k1_route`).
   The image guard refuses any one-key deviation, and the checker's `fp-route-share-2026-companion-v1` registry entry
   requires the same set. `frozen-2026-08` is refused for live runs from Week 5; it remains available only for dry
   runs and replays, flagged as such.
2. **Position scales.** The companion serves position-scaled distributions in both arms, as production does. Every
   earlier pair, and this gate's original contract, used UNSCALED draws (SERVED_POSITION_SCALES was never set on the
   shadow jobs). Weeks 5+ are therefore not comparable to any earlier pair and are never pooled with them.
3. **Graded weeks and floor.**
   - The graded sample is the Sunday-main Weeks 5–18: 14 possible weeks. The 12-week floor is unchanged, so two
     misses are allowed.
   - A third missed week ends the 2026 read as **insufficient**, which is not a pass or a fail. Per §"Minimum evidence"
     the shadow is then retained into 2027.
   - The 2,500 covered player-week and 40 thirty-point-event floors are unchanged.

**Unchanged:**
- the player-distribution gate (criteria 1–5);
- the exact-80 scoring gate (lexicographic 240/230/220/210/200, at least one 200+ improvement);
- the order (the distribution gate first, then the exact-80 gate);
- "failure keeps the incumbent and does not license a retry";
- the no-selection-from-2026-outcomes rule;
- Amendment 1's weekly in-season decision record.

**What the weekly record grades (reviewer, 2026-10-04):** player DISTRIBUTIONS under the companion-v1 generation (the
CRPS of draws, Route Share vs not). Its result informs the projection layer that every consumer reads: the K80
generation, the lab K110 union and the five-seed CBWU book. It is not a claim about any entered book.

**The weekly pair reader:** `nfl-dfs freeze-route-share-pair --slot early|late` freezes both arms' books under one policy version naming the contract (`route-share-pair-companion-v1-v1`). It refuses arms built under different contracts, or arms that differ in anything except the registry variant. It is not scheduled; the weekly record runs it by hand after each freeze.

**Retired:** the checker key `fp-route-share-2026` is marked SUPERSEDED from Week 5 (with this reason) and keeps its
W2–W4 history; the companion key alone audits the four schedulers from Week 5.

**Operational proof required before the Week-5 freeze** (Sun 2026-10-11 10:20 CT):
1. One outcome-blind dry-run execution of each job under companion-v1. It runs in the separate `dryrun-live-shadow-…`
   namespace, with `run_type=live_shadow_dryrun`, so graded readers never see it.
2. Both dry runs complete within the job timeout.
3. `check_prospective_gates.py --week 5` passes, including the new last-execution-success check.

If the dry run cannot finish within the job's timeout, the remedy is a longer timeout or more CPU on the EXISTING job
(the operator decides; Cloud Run cost). Fewer sims or booms would change this contract.
