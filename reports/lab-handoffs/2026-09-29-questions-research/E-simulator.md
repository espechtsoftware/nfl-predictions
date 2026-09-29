# THEME E — The simulator: what is it still buying us? (2026-09-29)

Scope: E1–E4 of `QUESTIONS.md`. Read-only on every repository; light compute only (single thread, no simulation — the
only arithmetic on worlds is a column permutation of persisted banks, an independence counterfactual). Scripts and
raw output: `E/e_compute.py`, `E/e_results.json`.

**Inputs and their information time**
- Code read: production `scripts/union_reselect.py`, `scripts/sunday_build_host.sh`, `scripts/week_env.sh`
  (worktree `week3-readiness-20260921`); lab `scripts/live_week.py`, `src/nfl2/two_track.py`, `src/nfl2/pipeline.py`
  (`generate_candidates`, `proj_tourney_production`, `world_order`), `src/nfl2/core/simulate.py`,
  `src/nfl2/core/draw_shape.py` (clone `week4-live-center-54dd512`); `src/nfl_dfs/inference/production_policy.py`.
- Pre-lock artifacts (players x 10,000 worlds, `incumbent_player_scores.npy` + `corrected_hsim_player_scores.npy`,
  `frame.parquet`, `candidates.parquet`), each stamped by its build time: W1 `20260913T141023Z` (K80 D800) and
  `20260913T160405Z` (the K90 paid build named in the class-gates evidence); W2 `20260919T153008Z` (the entered
  D12800, clone `week2-release-2dc116c`; the generator-batches script names it) plus the Wednesday `20260916T165251Z`
  D12800 as a second look; W3 `20260926T153408Z` (entered D12800, Saturday) and `20260927T155027Z` (T-70 D800).
- Post-lock ground truth: `nfl_raw.contest_ownership.fpts` for the Millionaire contest of each week (DK's own
  scoring, imported the Monday after; a player absent from the contest file is scored 0), and
  `nfl_raw.schedules` home/away scores for the slate's games. Realized points therefore include every player the
  frame projected but who did not play (the W2 availability defects show up as they were entered).
- Ledger: L09/L13/L14 (2023–24, 36 slates x 2 banks), PREREG-036 seal (DUAL_EMAX), the sealed-2025 holdout
  (boom-first), the 2019/2021 calibration scripts in `reports/lab-handoffs/`, PREREG-101 and its retraction, the
  2026-09-22 calibration reports and their same-day addenda, the 2026-09-25 outside-the-box review §2.1–2.3, R3, R8.

---

## E1. Which decisions still use the simulator, what each is worth, and what removing it would change

**First fact, settled in code and in the banks.** The "simulated mean" the mean track selects on and the PMO main
solves on IS the served projection: `live_week.py` shifts every skill row of every bank to `mean_projection`
(`shift_draws_to_means`) and pins DST to its prior, and the receipt says so
("mean_rank: sum of the served mean_projection (== selection-bank mean: banks are shifted to it)"). Measured on the
four builds: max |bank mean − mean_projection| = 2e-6 per player; pool sim mean = projected sum to two decimals in
every build (119.40 = 119.40, 125.04 = 125.04, 118.07 = 118.07, 119.21 = 119.21). `union_reselect.py --main pmo_x50`
reads `fr.mean_projection` only; it never touches a bank. The served projection is production's `player_projections`
(`NFL2_LIVE_CENTER=production`), already market-blended.

**Second fact, not in any receipt.** The "corrected hsim" bank is *not* self-calibrated to the served means at the
player level: QB +9% (7.51 vs 6.90), top projection quartile +7% (14.84 vs 13.91), so its lineup sums run
**+5 to +7 above the served projection** in every build (pool: 124.6 vs 119.4; 126.4 vs 125.0; 123.8 vs 118.1; 125.4
vs 119.2). On dual_emax-selected rows the gap is +9 to +12 (W2 book 141.5 hsim vs 132.8 projected) — the selector's
optimism on the bank it selected on. And the incumbent bank's DST row is a constant (zero variance; DST p90 = mean),
while hsim's DST has a p90 of 12.4 on a mean of 6.2. Any tool that concatenates the two banks (dual_emax, `p_tail`
receipts) mixes a level offset and a DST with no tail.

### The inventory (current armed path, operating handoff 2026-09-28 §2)

| # | Decision | Where | Simulator input | Measured value (objective, source) | If the simulator were removed |
|---|---|---|---|---|---|
| 1 | **Main book = PMO_X50** (K sequential plain-mean solves, ≤7 shared, 50% player cap, DST cap) | `union_reselect.py --main pmo_x50` | **none** | +27.7% tickets at p89 vs MEAN-from-pool, both seasons, paired 32–31, SUPPORTED; +6.3 realized/row (129.2 vs 123.0) (L13) | nothing changes |
| 2 | Fallback main = top-K by projected sum from the union pool | `select_top_mean` | none in the *selection*; the *pool* is simulator-made (row 4/5) | MEAN vs EMAX +13.3% tickets (not confirmed, paired 30–32; L09), L10 replicated +20.8%; live W1 +23, W3 +31/row | the pool would have to be projection-made (PMO rows) |
| 3 | **Tail sleeve = top-T by projected sum** from the union pool (+ PMO rows) | `--tail-sleeve-selector mean` | none in selection; `p_tail` on inc+hsim worlds is **receipt only** | mean sleeve at exact ladders: W3 23 vs 20 paid, W1 40 vs 31 (rehearsal, hindsight). The world-based forms it replaced: pline chose 128/110/137-point rows in W3; SIMP99 −6.2% (paired 11–18), SIMP998 −22.2% (1–6) vs MEAN (L14); EMAX −11.7% tickets vs MEAN at p89 but better tail share (0.0183 vs 0.0221 field-above-best, L09); DUAL_EMAX +1.39 at K80 on the old best-of-K objective (PREREG-036 seal) | the sleeve needs a pool; PMO rows K+1..K+T under the overlap cap is the projection-only form (`--sleeve-includes-main` already admits them) |
| 4 | **Boom generation**: the exact optimum of each simulated world, worlds visited in descending slate total ("total" order: at D800 the top 6.4% of worlds, at D12800 nearly all) | `generate_candidates._boom` on the generation bank | whole world (marginals + dependence) | boom-first allocation +7.563 at K100 on the sealed-2025 holdout [+3.33, +11.94], 12W/6L; +4.737 K100 external; PREREG-024 +3.39 at K80 — **all on the best-of-K maximum objective**. On the mean track the pool's realized mean is 122–123 (L09/L13 MEAN) and a projection-only optimizer beats it (row 1) | the supply for rows 2/3/5 disappears; replacement = capped projection solves (row 1's mechanism) |
| 5 | **Class sleeve**: every 2nd boom visit solved under the field-class shape (QB salary cap, two TEs, salary floor, projection band) | `boom_sleeve` kwargs on a world's `proj_sim` | the world's draws as objective; the constraints are projection-compatible | W1 (out of sample): 3.54% of sleeve rows ≥193 vs 1.00% plain boom, mean 138.0 vs 133.0; W3 circular (138.4 vs 116.0) | the same kwargs on `objective_col="proj"` with banned lineups — untested |
| 6 | **Lev generation**: `optimize_many` on `proj_tourney` = mean, except salary ≤4000 players valued at max(mean, generation-bank p90), minus the fade | `proj_tourney_production` | one marginal quantile per cheap player | kept on the old objective ("true-deletion tests cost tails"); **no read under the mean track** (B3/Q4b). W3: lev rows realized 137 vs boom 116 | value cheap players at the mean (Q4b's spirit); a paper read is cheap |
| 7 | min-proj universe pruning, projection-level gate (naive top lineup ≥135), DST cap, overlap cap | `live_week.py`, `two_track.py` | none | Q4b: 399 boom rows held a non-player (W3) | nothing changes |
| 8 | `p_line` in receipts, `sel_p194`/`aud_p194` in candidates | `tail_probability` on inc+hsim | worlds | the simulator's P(≥line) loses to MEAN at every line (L14); the empirical Gaussian on projected sum (EMPP99) +3.9%, NOT SUPPORTED but never below SIMP | replace with EMPP sigma (L14 `emp_sigma` ≈ 25.5) |
| 9 | dual_emax, pline, cov194, class *selector* | retired / paper | worlds | class selector: W3 30 vs 20, W1 8 vs 31 (withdrawn) | already off |

**What would change if the simulator left the money path.** The main book: nothing — it is already projection-only
(row 1), and the one adoption with a two-season SUPPORTED read is precisely the arm that dropped the worlds. The
sleeve and the fallback main lose their supply (rows 4/5), which is replaceable by PMO rows and class-constrained
projection solves; the p90 punt valuation reverts to the mean (unread); receipts lose `p_line`, which L14 says was
the worst of the available estimates. What is lost that was measured: +7.6 (sealed) on the best-of-K maximum and
+1.39 (DUAL_EMAX) on the same objective — an objective the book cannot currently win (pool ceiling 30–40 short of the
Millionaire line, Q picture item 2) — plus the class sleeve's shape supply (one out-of-sample week). Build time
falls by the three 10,000-world banks and the boom solves; L13 timed the projection-only main at under a minute for
144 rows. Level replacement (market total): not needed — see E2, the served mean already carries the market.

Confidence: high on the code facts (read directly, and the bank identity reproduces to 2e-6); high that the mean
track is simulator-free; medium on the replacement suggestions (untested).

---

## E2. Slate-level calibration, week by week and by season; can the level be pinned to the market total?

Per build (incumbent bank; hsim in parentheses). "World rank" = share of the 10,000 per-world pool means at or below
the realized pool mean (0.5 = perfectly centred; <0.05 or >0.95 = outside the simulator's 90% band).

| Build (pre-lock time) | Sim pool mean = projected sum | (hsim) | Realized pool mean | World rank inc (hsim) | Market total → realized points, slate games | Top-50 by projection: proj → real |
|---|---:|---:|---:|---:|---:|---:|
| W1 D800 K80, 09-13 14:10Z | 119.4 | (124.6) | **140.9** | **0.98** (0.95) | 537 → 645, **×1.20**, per-game r 0.63 | 862 → 1008 (×1.17) |
| W1 D800 K90 paid, 09-13 16:04Z | 120.5 | (126.5) | 140.2 | 0.97 (0.91) | same | 869 → 1008 |
| W2 D12800 entered, 09-19 15:30Z | 125.0 | (126.4) | **93.4** | **0.0002** (0.0001) | 575.5 → 478, **×0.83**, r −0.01 | 886 → 700 (×0.79) |
| W2 D12800 Wednesday, 09-16 16:53Z | 112.2 | (119.6) | 98.7 | 0.15 (0.004) | same | 825 → 733 |
| W3 D12800 entered (Sat), 09-26 15:34Z | 118.1 | (123.8) | 120.4 | 0.60 (0.35) | 582.5 → 617, ×1.06, r 0.39 | 867 → 893 (×1.03) |
| W3 D800 T-70, 09-27 15:50Z | 119.2 | (125.4) | 122.2 | 0.62 (0.37) | 583.5 → 617, ×1.06 | 868 → 893 |

Reading.
1. "Sim mean ≈123 every week" is the served projection level (119–125), which is where a market-blended mean sits
   every week. The realized level is the scoreboard: the DK-points miss tracks the market's own miss almost exactly
   (W1 scoreboard +20%, DK top-50 +17%; W2 −17% / −21%; W3 +6% / +3%). **The market total missed by the same amount
   the simulator did.** Pinning the level to the market total pins it to a number that was itself wrong by 2 sd in
   each of the first two weeks: the outside-the-box review §2.1 measured that weekly slate totals' misses are
   uncorrelated within a week (ICC −0.002) and spread exactly as independent games (45.3 vs 45.3), i.e. ≈8% of a
   13-game slate. The incumbent bank's level sd is 9.6–11.3 points on a ~120 level (≈8–9%). Its dispersion is
   the market's dispersion; there is no pre-lock information that would have moved it.
2. W2's rank of 0.0002 is defect-inflated: the entered build carried the availability defects (QB slots projected
   18.1, realized 10.8). The 2026-09-22 Addendum 2 puts the corrected W2 level near rank 0.05; the Wednesday build
   (fewer non-players) sits at 0.15. W1 at 0.97–0.98 is a genuine outer-3% draw on a build with 383/391 players
   matched.
3. Seasons (lab-handoff scripts, incumbent law, `NFL2_CENTER=mean`): 2021, 18 slates — ranks 0.044–0.749, 6% in the
   outer 10% (nominal 10%), KS p 0.18, sim level sd 11.2 vs realized 8.9, runs slightly high (121 vs 116). 2019 — outer
   share 0.12, KS p 0.46, sd 11.2 vs 11.3. **The level is calibrated across seasons and, if anything, slightly
   over-dispersed.** 2026 W1–3 (ranks 0.98 / ~0.05–0.15 / 0.60) are two extreme draws and one centred — consistent
   with the market's own two 2-sd weeks, not with a level bias.
4. The hsim bank's level is *not* calibrated to the served mean (+5–7, E1 second fact). Anything reading hsim worlds
   for a level or a threshold inherits a +5% optimism before any draw is taken.

**The pace flag.** `GAME_SIM_PACE=vegas` (`nfl2/core/simulate.py:278–295`) is reachable: both the lab
`PRODUCTION_ENV` and `production_policy.py` run `GAME_SIM_MODE=possession` with `GAME_SIM_PACE=""`, so it is one
env var and has simply never been executed (Q10). What it does: conditions each game's DRIVE COUNT on its Vegas total
relative to the slate mean, mean-preserving by construction ("the only strength channel that survives a
mean-preserving factor"). It changes the *between-game* dispersion of worlds (high-total games get more drives,
more variance, more co-movement), **not the slate level** — the level is fixed by the served means regardless. So it
cannot pin the level; the level is already pinned to the market through the projection. If it is ever run, it is an
outcome-blind dispersion/dependence check (E4), not a level fix.

Verdict: pinning the level to the market total is feasible in one line and worth nothing — the mean already carries
the market and the market missed. Confidence high (four builds, three seasons of level ranks, the market check
computed directly).

---

## E3. Player and lineup tails; the single best preregistered fix; why PREREG-101 was withdrawn

Pool-level simulated vs realized (incumbent bank; `sim_vs_real_P_ge` in `e_results.json`):

| Build | P(≥150) sim → real | P(≥200) sim → real | Share of rows realized above their own sim p99 (nominal 1%) | Sim within-row sd vs realized cross-row sd |
|---|---:|---:|---:|---:|
| W1 D800 K80 | 0.107 → **0.369** | 0.0019 → **0.0138** (7× under) | **5.6%** | 23.1 vs 27.0 |
| W2 D12800 entered | 0.179 → 0.018 | 0.0077 → 0 (∞ over) | 0.04% | 26.1 vs 24.9 |
| W3 D12800 Sat | 0.113 → 0.118 | 0.0024 → 0.0007 (3.4× over) | 0.54% | 25.0 vs 24.4 |
| W3 D800 T-70 | 0.122 → 0.128 | 0.0028 → 0.0013 (2.2× over) | 0.50% | 25.2 vs 23.3 |
| dual_emax book rows | W1 0.135 → 0.475; W2 0.260 → 0.031; W3 0.172 → 0.097 | W1 0.0037 → 0.025; W2 0.0178 → 0; W3 0.0059 → 0 | W1 7.5%, W2 0, W3 0 | — |

Reading.
1. Within-row dispersion is right (sim 23–26 vs realized 24–27). The tail error is the **level draw** applied to a
   threshold: W1's whole pool shifted +20 and 5.6% of rows broke their p99; W2's shifted −30 and none came near.
   Pooled over the three slates the P(≥200) errors nearly cancel (0.0040 sim vs 0.0048 real, all of it W1); excluding
   W1 the simulator is 2–3.5× over at 200 and the book rows 3× or more — matching the historical 3× (W1 post-mortem
   §3.1: 0.40% vs 0.13% on 57,531 candidates) and the season dependence the 2019/2021 scripts found (lineups above
   p99: 0.35% in 2021, 1.79% in 2019; per-player above p99 0.60% vs 1.75%).
2. **Selection amplifies it** (PREREG-101 §2a, 216 slate-banks): pool max real/sim at 220 = 0.84, book max = 0.44
   (per bank 0.33/0.49/0.49). The "2.8× over" figure is the withdrawn draft's single-bank number; the authoritative
   ratio is ≈2.3× on 8 events over 6 slates and "must not be cited as a magnitude". Here: the dual_emax book's hsim
   mean sits +9 to +12 above its projected sum (winner's curse on the selection bank).
3. **Never-realized spikes** (winner anatomy §C): 49/51 deep-world optima carry a player above his three-season
   realized maximum, +19.3 points of never-realized excess per optimum vs +5.8 for the winners' own rosters in the
   same worlds. Frequency of exceedance is right (0.7–1.0% above q99), size is wrong — the tail above the top TabPFN
   quantile is a linear extrapolation (`draw_shape.py:312–316`). That is R3's target.

**Which single fix has a preregistered test.** Three candidates exist; only one has been preregistered *and* run:
- **L14 (run, read 09-29):** replace the simulator's P(≥line) by a Gaussian on projected sum with an empirical sigma.
  EMPP99 +3.9% at p99 vs MEAN (NOT SUPPORTED, not killed), EMPP998 +11.1% (paired 4–2, NOT SUPPORTED); SIMP99 −6.2%
  and SIMP998 −22.2% — the simulator's own tail probability loses at every line. On the money path this is already
  the outcome: the sleeve selects by mean, and `p_line` survives only in receipts. **This is the best preregistered
  fix, and it is a removal, not a repair.**
- **PREREG-101** (world reweighting, frozen 09-18, withdrawn the same day): see below — not runnable as written.
- **R3** (generalized-Pareto tail above q99, keep P(X>q99)=1%, fit ξ by position walk-forward on 2014–25 exceedances,
  physical cap): the best-specified simulator repair, class C, no preregistration yet, and it only matters for the
  tail sleeve (the mean track cannot see it). If it is written, its gate must be the §9.1 independence probe 101
  lacked (freeze a book on decision worlds, evaluate on an independent bank from the same law, repeat selection seeds
  at fixed pools) — otherwise the winner's-curse objection that sank 101 sinks it too.

**Why 101 was withdrawn** (lab commit `7f7900b`, 2026-09-18; production retraction 09-22):
1. §8 retracted: winner's curse imposes no monotonicity law on a threshold-probability ratio under greedy expected-max
   selection — the optimized quantity is an expected maximum, the diagnostic a threshold event. The reviewer's
   counterexample reproduces at 400,000 trials (a correctly specified law whose optimism is entirely selection, where
   enlarging the pool moves the ratio from 0.300 to 1.000). The selection-optimism objection is UNRESOLVED, which is
   the stated reason readiness was withdrawn.
2. §2a pairing-variance claim retracted: shared pools raise covariance but do not make Var(A−C) small by construction;
   a minimum detectable effect needs a predeclared pilot.
3. Unimplementable as written: clipping raw weights to [0.2, 2.0] and then normalizing to mean 1 cannot satisfy a gate
   requiring final weights in [0.2, 2.0] (90% at 0.2 and 10% at 2.0 → 0.526 and 5.263); a gate asks a new-bank book to
   reproduce an old-bank roster; FLAT10 and routing rules undefined.
4. Its motivating magnitude was overstated (bank 970 only, 0.63/0.36 → 0.84/0.44 across three banks).
   Consequence narrowed to implementation scope: a failure would close this reweighting at this information set and
   objective, not law work generally.

Confidence: high on the direction (over-predicted tail outside high-level slates; selection amplifies), medium on any
magnitude (three 2026 slates, 8 historical book events), high that no runnable preregistered simulator *repair*
exists today.

---

## E4. Cross-team dependence: does the card change the MEAN track, or only the tail?

Measured in the persisted banks (per game: correlation across worlds of the two teams' skill-position sums; per team:
top-2 WR by salary; QB vs WR1), against the residual card (outside-the-box §2.2–2.3, 74 slates / 3,663 games):

| Pair | Real (card) | Incumbent bank, W1 / W2 / W3 | hsim bank, W1 / W2 / W3 |
|---|---:|---:|---:|
| Opponents' skill DK totals | **+0.21** | +0.13 / +0.13 / +0.13 | +0.20 / +0.20 / +0.20 |
| WR1–WR2 same team | **+0.016** | **+0.27 / +0.25 / +0.27** | −0.02 (W3; NaN where a WR row is constant) |
| QB–WR1 same team | +0.38 | +0.35 / +0.35 / +0.34 | +0.34 / +0.37 / +0.37 |

So the question's premise ("~0 simulated") is not what the banks show: the incumbent couples opponents at +0.13 —
right sign, wrong mechanism (through shared volume, which reality couples at −0.41 in plays and +0.21 in fantasy
through game script, §2.2) — and hsim at +0.20, on target. The WR1–WR2 over-coupling (+0.27 vs +0.02) is real in
every incumbent bank and absent in hsim. QB–receiver is right in both.

**Independence counterfactual** (each player's worlds permuted independently; marginals and level identical;
destroys correct and wrong dependence alike, so it is a lower bound on the tail):

| Build, incumbent bank | Pool mean: with → without dependence | P(≥200) pool | P(≥150) pool | Sim level sd | Mean per-world pool max |
|---|---:|---:|---:|---:|---:|
| W1 D800 K80 | 119.395 → 119.395 | 0.0019 → 0.0003 (6×) | 0.107 → 0.075 | 9.6 → 6.5 | 191.1 → 183.1 |
| W2 D12800 entered | 125.039 → 125.039 | 0.0077 → 0.0027 (2.8×) | 0.179 → 0.150 | 11.3 → 8.3 | 221.2 → 212.5 |
| W3 D12800 Sat | 118.067 → 118.067 | 0.0024 → 0.0007 (3.6×) | 0.113 → 0.087 | 10.3 → 7.1 | 211.4 → 205.0 |
| W3 T-70 (hsim, for contrast) | 125.406 → 125.406 | 0.0049 → 0.0026 (1.9×) | 0.166 → 0.154 | 8.9 → 8.5 | 205.8 → 200.3 |

Answer.
- **Mean track: nothing, exactly.** A projected sum is a sum of means; dependence cannot move it, and the shuffle
  confirms it to three decimals on every build. Neither the PMO main, the mean fallback, the mean sleeve, min-proj,
  the DST cap nor the overlap cap reads a joint distribution. R8 (dependence card as an outcome-free gate on the
  generation law) has no mean-track consequence.
- **Tail and boom worlds: it is most of the simulated tail.** Removing dependence cuts the incumbent's P(≥200) by
  2.8–6× and the per-world pool maximum by 6–9 points; the whole historical over-prediction is ≈3× — the same size.
  Since QB–receiver and cross-team coupling are roughly right, the excess is attributable to the WR1–WR2 channel
  (+0.27 vs +0.02) and, per §C, to spike size — which is why double-receiver stacks are over-supplied in boom and why
  simulator-tail objectives lost at every line (L14, the "simulated-tail objectives lose" rule). About 30% of the
  incumbent's slate-level variance also comes from the coupling (sd 9.6–11.3 → 6.5–8.3 without it); hsim's level
  variance does not (8.9 → 8.5), so hsim gets its dispersion from a different, team-level channel.
- **A cheaper move than R8** exists for the tail supply: hsim already has WR1–WR2 ≈ 0 and cross-team +0.20; after
  its level offset is fixed (E1 second fact) it is a better generation law by the card than the incumbent. Untested;
  a boom-from-hsim arm is a same-image, same-pool-count comparison, not a law rewrite.

Confidence: high on the bank correlations (three builds, identical to two decimals) and on the mean-track null;
medium on attributing the tail excess to WR1–WR2 (the shuffle removes everything at once; no realized 2026 cross-team
correlation was computed — 38 games is too few).

---

## Immediate actions (evidence → action → confidence)

1. **Leave the main book alone; record that it is simulator-free.** Evidence: code (`--main pmo_x50` reads
   `mean_projection` only), bank mean = projection to 2e-6, L13 SUPPORTED both seasons. Confidence high.
2. **Fix two bank defects before any tail or sleeve read cites `p_line`:** (a) the hsim bank runs +5–7 per lineup
   above the served mean (QB +9%, top quartile +7%) although the receipt calls it self-calibrated; (b) the incumbent
   DST row has zero variance. Both are visible in four consecutive builds. Until fixed, `p_line`, `sel_p194`,
   `aud_p194` and any dual-bank concatenation are biased upward. Confidence high.
3. **Retire the simulator's P(≥line) from receipts and paper arms; carry the L14 empirical sigma (~25.5 on projected
   sum) instead.** Evidence: SIMP99 −6.2% (11–18), SIMP998 −22.2% (1–6); EMPP never below SIMP; the pline sleeve chose
   110–137-point rows. Confidence high that SIMP loses; low that EMPP adds anything (NOT SUPPORTED).
4. **Do not pin the level to the market total, and do not run GAME_SIM_PACE=vegas as a level fix.** Evidence: the
   market missed W1 +20%, W2 −17%, W3 +6% — the same misses as the DK level; the sim level sd (≈8–9%) equals the
   market-miss sd (≈8%); the 2019/2021 level ranks are calibrated; the flag is mean-preserving by construction and
   only reshapes between-game dispersion. If run at all, run it as an outcome-blind dependence/dispersion check
   (it is one env var: production law is already `GAME_SIM_MODE=possession`). Confidence high.
5. **Sleeve supply paper arm (one Monday read, no compute at lock):** sleeve = PMO rows K+1..K+T under the overlap cap
   vs the union-pool mean sleeve, scored at exact ladders. Evidence: the sleeve is the only entered rows whose supply
   still comes from the worlds; PMO rows "project highest" (L13); the mean sleeve's own rehearsal edge is hindsight.
   Confidence medium.
6. **Lev p90 punt valuation → mean, as a paper read (B3/Q4b).** Evidence: the only simulator input to lev is a
   marginal p90 on cheap players, kept on the old objective; unread on the mean track. Confidence medium.
7. **Tail repair only if the tail sleeve stays entered:** write R3 (GPD tail above q99, exceedance frequency held at
   1% — matching the measured 0.5–1.0% — size fitted walk-forward) with PREREG-101's §9.1 independence probe as its
   gate and a predeclared pilot for MDE; do not revive 101 as written. Alternatively test boom-from-hsim (card-correct
   WR1–WR2) after action 2. Confidence medium-low that either moves paid tickets; the Millionaire line is 30–40 above
   the pool ceiling regardless.

## Unknowns
- Three 2026 slates; W1's pool is 800 rows; W2's entered build carries the availability defects, so its level and tail
  misses overstate the simulator's share of the error (Addendum 2 corrections bring corr(sim, real) from −0.49 to +0.34).
- Realized points are DK's contest file; a frame player absent from it scores 0 (non-players are counted as entered).
- The independence shuffle is a lower bound (it removes the correct QB–receiver and cross-team coupling as well).
- No 2026 realized cross-team correlation (too few games); the +0.21 is the 3,663-game card.
- Which W1 build was entered is inferred (the class-gates evidence names `20260913T160405Z` as the paid K90 build;
  the K80 build at 14:10Z gives the same level and tail numbers within noise).
