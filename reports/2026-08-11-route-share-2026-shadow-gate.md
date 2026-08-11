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
