# Model input study: which of the 35 features earn their place

Operator request: check that every input to the trained projection model helps.
Walk-forward by season, 2019–2025 held out, model fit on **active** rows exactly as
production fits it (`active_training_rows`), scored on MAE, Spearman and ceiling AUC
(30+ points). Every feature dropped singly; Vegas, production-trail, salary and defense
dropped as families.

## The noise floor was the finding

My first pass used a 3-seed noise floor (0.0017 MAE) and flagged four features as
harmful. It was **about 3× too tight**. Re-running the *identical* feature set in six
random **column orders** — no information changed — moves mean MAE by up to **0.0052**,
per-season sd 0.009. Under the first-pass rule, **a third of pure reorderings would have
read as "harmful" and a third as "helpful."** LightGBM's split tie-breaking depends on
column order (the ledger's "order luck"); dropping a column shifts every later index, so
any drop carries it. (A first control that inserted constant columns was invalid —
LightGBM discards constants before training, so it never shifted anything; it returned
exactly 0.0.) Dropping all four "harmful" features together made MAE slightly *worse*
(+0.0014, improved in only 3/7 seasons, per-season swings ±0.015).

**Corrected floor: 0.0052 MAE** (largest order-only shift). Verdicts below use it.

## Clearly helpful — removing them hurts, beyond order luck

| input | ΔMAE if removed | seasons worse |
|---|---:|---:|
| **`qb_cpoe_l6`** | **+0.0418** | **7/7** |
| Vegas family (implied total, spread, total, script) | +0.0314 | 7/7 |
| `depth_rank` | +0.0267 | 7/7 |
| `snap_share_l4` | +0.0197 | 6/7 |
| `carry_share_l4` | +0.0137 | 6/7 |
| production-trail family (`dk_points_l4/std/vol`) | +0.0113 | 5/7 |
| `game_total` | +0.0079 | 5/7 |
| `ref_flags_prior` | +0.0068 | 5/7 |
| `salary_delta_wow` | +0.0067 | 5/7 |
| `team_vacated_target_share` | +0.0060 | 6/7 |

`qb_cpoe_l6` is worth more than the entire Vegas family on its own.

**Salary** is ambiguous on MAE (+0.0103, 4/7) but dropping the family costs the **largest
ranking loss of anything tested** — Spearman −0.0083, ceiling AUC −0.0048. Ranking is
what construction consumes. Keep it.

## Everything else — indistinguishable from order luck

The remaining ~24 inputs (including `wopr_l4`, `target_share_l4`, `spread`, the defense
family at +0.0053, `separation_l4`, `stacked_box_l4`, `gl3_carries_smoothed`,
`neutral_pass_rate_l6`) move MAE by less than column order alone does. **No feature is
demonstrably harmful.** Several are individually redundant with correlated partners
(e.g. `target_share_l4` with `wopr_l4`), which a single drop cannot resolve.

Two are also sparse: `separation_l4` is 0% populated in 2014 and ~25–31% after;
`stacked_box_l4` 0% then ~10%. Low coverage limits what they could contribute.

## What this does and does not license

**Does:** confirms the core inputs, and says there is no player-level case for removing
anything. **Does not:** delete anything — a player-level null is not a lineup-level null
(the `depth_rank_delta` lesson: neutral here, −4.6 mean-best in replay).

**One check worth doing, flagged not asserted:** given today's discovery that
`rosters_weekly` carries post-game look-ahead, `depth_rank`'s 7/7 strength should be
confirmed point-in-time in the historical panel. A depth feature that leaked who actually
started would look exactly this strong.

**Method lesson:** any ablation noise floor here must include **column-order
perturbation**, not only seeds.
