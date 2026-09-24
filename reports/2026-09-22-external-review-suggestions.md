# External review: where the scoring gap is, and what to change

**2026-09-22.** This answers `reports/2026-09-22-state-of-the-problem-for-external-review.md` (its §7
questions), written by a reviewer with no prior history on the project. Every number below was computed
today from the warehouse, the archived Week-2 run, or LineStar's public API. The scripts are in
`reports/lab-handoffs/2026-09-22-external-review/`, and §9 has the commands. Nothing touched the money
path. Nothing here is a ledger row.

The Week-2 backup-QB, Doubtful and DK-PPG-stand-in defects are already fixed, and I treat them as fixed.
Where they would contaminate a measurement I remove them from the data, so every finding below is about
what is left.

---

## 1. Summary

| | finding | where | confidence |
|---|---|---|---|
| A | **Week 2's "compositional error" and "regime flip" came from the defects you have already fixed.** Zero the players who did not play, restore the four projections the DK-PPG stand-in inflated, and every compositional statistic of the Week-2 pool sits inside the simulator's own world distribution. What remains is a low-scoring slate. | §2 | high for Week 2; Week 1 not run (the run is not on this host) |
| B | **Historically, the field knew more than our replay projections.** Ownership that our projection, salary and position do not explain predicts our residual in 69 of 71 slates (2022–25), in every season, for healthy players, and beyond the prop market. The replay books' players who played trailed the field's picks by **11.0 points per lineup** against our own projection. | §3.1–3.2 | high, for the replay projection |
| C | **The live Sunday projection is much closer to the crowd** (ρ +0.09 in Week 1, +0.02 in Week 2, against +0.17 historically). The exception may be late games, which the live build cannot see by construction. | §3.3 | medium (two weeks) |
| D | **A free pre-game crowd signal is already one API call away.** The LineStar payload that `linestar_backfill.py` fetches, and mostly discards, carries a projection and per-slate projected ownership. The projected ownership tracks actual Millionaire ownership at 0.78 within a slate; the replay's `own_est` manages 0.10. Blending the projection cut MAE out of sample in 2024 and 2025. | §4 | high on availability and historical value; live value unmeasured |
| E | **Three money-path items:** <br>• The validated participation mixture (PREREG-054, "the program's strongest measured result") is not in the Week-2/3 path. <br>• The Questionable ×0.80 haircut also hits players whom the 90-minute inactives have already cleared. <br>• Early in the season, the lab's additive recentering gives stars impossible floors: Ja'Marr Chase's simulated 1st percentile in Week 2 was 8.4 DK points, and Bijan Robinson's 8.6. | §5 | high (code and data verified) |

**Recommended order** (details in §6):

1. **Start the book-vs-field scoreboard on Monday of Week 3** (§6.1). It is one query, and it splits every week's gap into availability, information and construction.
2. **Condition the Questionable haircut on the inactives** (§5.2). This refines a rule introduced this week. If the operator can't validate the change before Sunday, keep ×0.80 for Week 3 and fix it for Week 4.
3. **Shadow a late-news late swap in Week 3** (§6.3). Late games are where the crowd's historical edge concentrates, and the live build cannot see them.
4. **Test LineStar's projection and a real ownership model** at player level, then on the replay books (§6.2).
5. **Bring the replay projection up to what the crowd knew before re-testing any field-relative lever.** That covers finish objectives, fades and contest-sim. Their historical verdicts were decided against a field that knew more than our worlds (§3.4).
6. **Put P_MIX back in the comparison set, and build the cross-repo consumption test** (§5.1).

**Stop doing:**

- Don't build a compositional recalibration of the simulator from Week 2.
- Don't restore the chalk fade with a real ownership projection before the projection has absorbed the crowd's information.
- Don't read two-slate sign flips as mechanisms without first computing the simulator's own null.

---

## 2. Finding A: Week 2 was the defects, not a regime

C2 compares Week 1 with Week 2 and has no null between them. The null is already on disk: each of a
run's 10,000 worlds is a slate the simulator considers possible. If Week 2's realized statistics look
like one of those worlds, the simulator was not wrong about Week 2's composition; the slate was one draw.

**Method.** `slate_ppc.py` ranks each realized pool statistic among the world values of the archived
Week-2 D12800 run: 12,555 candidates, the incumbent selection bank, and the corrected-hsim bank
separately. A world-rank of 0.5 is typical; below 0.025 is outside the simulator's range.

**Result** (incumbent bank; hsim world-ranks in brackets):

| statistic | raw: realized, rank | non-players zeroed | + DK-PPG stand-in removed |
|---|---|---|---|
| simulated pool mean | 125.0 | 114.1 | 109.9 |
| realized pool mean 93.7 | rank 0.0003 [0.0001] | 0.016 [0.002] | 0.049 [0.010] |
| corr(simulated mean, error) across the pool | −0.69, 0.0000 [0.0003] | −0.28, 0.004 [0.022] | **−0.09, 0.145 [0.277]** |
| corr(simulated mean, realized score) | −0.49, 0.0000 [0.0003] | +0.15, 0.001 [0.008] | **+0.34, 0.104 [0.236]** |
| top- minus bottom-decile error | −67.7, 0.0000 [0.0003] | −29.1, 0.0002 [0.008] | **−7.3, 0.126 [0.227]** |
| book mean 98.4 | rank 0.0008 [0.0000] | 0.022 [0.001] | 0.067 [0.006] |

The two corrections were:

- **"Non-players zeroed":** in every world, zero the 31 skill players projected ≥ 5 who recorded no box-score line. That covers Flowers, Tua, Pittman, Bowers and the backup QBs; half of the pool held one of them.
- **"DK-PPG stand-in removed":** restore the four projections that the deleted stand-in inflated. Jefferson goes 25.3 → 17.3, Flowers 22.6 → 14.7, McConkey 17.2 → 14.8, and Bech 9.4 → 7.1.

**What follows.**

- **The stated mechanism of the flip is the defects.** `2026-09-22-simulator-calibration-is-the-defect.md` rests on the −0.55 mispricing correlation and the −50.7 decile spread. My raw run on the two banks combined reproduces both exactly (−0.554, −50.67). They are the dead players plus four inflated projections. Remove them, and the simulator's ranking of the Week-2 lineups is ordinary in both banks.
- **The Week-2 half of C2's table is defect evidence.** The caps (+11.3), the fade A/B, the cash objective (0 of 97), the sort-key correlation and the bring-back lift were all measured on a book dominated by these defects. None of them is evidence of a regime.
- **What remains is a level, and it goes both ways.** Week 2 was a low-scoring slate for our pool (world-rank 0.01–0.05). Week 1 went the other way: the simulator predicted 121 against a realized 141. Production's ceiling diagnostic puts Week 1's pool best at a height reached in only 2–14% of worlds, and has Week 2's exceeded in 88–95%. Two slates at opposite ends suggest a slate-wide scoring factor the simulator lacks. Expected-max and field-relative objectives are nearly immune to such a factor, because the field moves with it. Absolute thresholds are not, which fits the cash-line objective's swing.
- **Next steps.** Run `slate_ppc.py <week-1 run> 1 <inputs>` on the Week-1 run; production holds it, and it takes about 5 minutes. Then run it on 20–30 replay slates to see whether realized levels are over-dispersed relative to the worlds (§6.7). Nothing compositional needs recalibrating on this evidence.

---

## 3. Finding B: the field knew more than our replay projections

### 3.1 Crowd information over 72 slates

**Data.** For 2022–2025 I joined each week's Sunday Millionaire ownership (`contest_ownership`) to the
point-in-time replay projections: `slate_player_features`, panel `20260811-pitclean-e80-k1-a12ab31`. I
kept skill players who played (a box-score row) with a projection of at least 5.

**Test, slate by slate.** Does "excess ownership" predict the part of the outcome our projection missed
(actual − projection)? Excess ownership is the part of log ownership that our projection, salary and
position do not explain. Ownership is post-lock, so this measures information; it is not a live input.

| specification | mean within-slate ρ | slates positive | top- minus bottom-quintile residual |
|---|---:|---:|---:|
| baseline | **+0.169** (t 15.6) | 69/71 | +3.7 DK points |
| + quadratic terms and implied team total | +0.163 | 70/71 | +3.5 |
| healthy players only (not on the injury report) | +0.162 | 67/71 | +3.5 |
| prop-covered 2023–25, with market and model components also controlled | +0.076 (t 4.6) | 35/54 | +1.5 |
| early games (1 pm ET) | +0.094 | 55/71 | +1.9 |
| **late games (4 pm ET)** | **+0.275** (t 13.0) | **64/68** | **+5.5** |
| each season, 2022 / 23 / 24 / 25 | +0.17 / +0.17 / +0.16 / +0.19 | 17/17, 17/18, 17/18, 18/18 | +3.6 to +3.9 |

Three things this effect is not:

- **It is not the injury channel.** The healthy-only specification barely moves.
- **It is not a blend-weight problem.** Market-minus-model disagreement is uncorrelated with our residual (ρ −0.002 on the same rows), and controlling for both components leaves the effect standing.
- **It is not evenly spread in time.** It is three times stronger for late-game players. That is information arriving after the early lock: late inactives, late news, and the crowd's own late swaps.

### 3.2 What it cost the replay books

I compared the replay books (80 entries per slate, `replay_lineups_pitk1`, 72 slates) with the field's
average lineup, over the eight skill slots. The average lineup is the ownership-weighted sum over players,
which is exactly the mean over field lineups.

| per lineup, 8 skill slots | replay book | field's average lineup | book − field |
|---|---:|---:|---:|
| projected by our replay model | 109.7 | 107.7 | +2.1 (book lower in 36/72) |
| realized | 107.5 | 120.7 | **−13.3** (t −7.2; book lower in 64/72) |
| skill slots that did not play | 0.50 | 0.05 | the availability gap, since fixed |
| realized − projection, players who played | +2.4 | +13.4 | **−11.0** (t −9.6; book lower in 60/72) |

**The gap is broad.** Per slot, among players who played, the field's picks beat our projection by
+0.9 (QB), +2.3 (RB), +1.8 (WR) and +0.9 (TE). Our picks managed −0.1, +0.4, +0.4 and +0.4. The pattern
is the same in every salary tier.

Two readings follow:

- **The construction assumes a mean edge we did not have.** Our own model rated the books only +2.1 points above the field's average lineup; the tournament construction spends almost all of the projected mean edge on shape (per-world optima, forced stacks). That trade is sensible only if the projection is ahead of the field. Historically it was behind.
- **This is C4 and C5 with 72 slates of power.** The pool sits at or below the field median because the players we choose, relative to the ones the field chooses, underperform our own numbers.

### 3.3 The live projection is much closer to the crowd

Here is the same test against the last served projection before each 2026 lock (the 11:0x CT run, after
the 10:30 inactives):

| | players | ρ | top − bottom quintile |
|---|---:|---:|---:|
| 2026 Week 1 | 186 | +0.087 | +0.7 |
| 2026 Week 2 | 188 | +0.014 | +1.2 |

*Corrected 2026-09-22 (evening): 2026 standings carry one ownership row per roster slot, and the first
version took the MAX per player (the laptop agent's grain find). Re-run with the slot rows summed; the
original values were +0.086 / +0.5 and +0.017 / +1.2, so nothing below changes.*

**Reading.** Both weeks sit at the low end of the historical distribution. The per-slate standard
deviation is about 0.09, so two slates this low have roughly a 1% chance under it. The Sunday-morning
live build (inactives, hourly re-projection, props near lock) has closed most of the replay projection's
gap, at least for early games.

**Late games can't be measured yet.** Each week has only 53–63 late-game players, so the uncertainty is
about ±0.26.

**On production's Week-1 verdict.** Production called the C5 tilt "slate noise" after Week 1, and these
two live numbers agree with that. My disagreement is only about scope. The 72-slate evidence says the gap
is real and systematic for the projection the historical panel uses, and that matters for the next
section.

### 3.4 Consequences

1. **Every historical verdict on a field-relative lever was decided against a field that knew more than our worlds.** PREREG-098 built its synthetic field from *real* ownership, then asked our simulator which lineups beat that field. In our worlds the crowd's informed choices look like mistakes, so P(top-N) selection leans against them, and it lost 9 slates to 44. Production's contest-sim negative (real field, simulated worlds) has the same structure. The ledger does not record this as a mechanism for either negative. It is testable now on 098's existing books: its FIN arms should hold players with lower excess ownership than DEMAX's.
2. **Fix the replay projection before re-testing anything that reads the field.** That covers finish, payout, leverage, fades and contest-sim. The replay projection needs the crowd's pre-game information first; the cheapest proxy is §4.
3. **The chalk fade needs care.** Its historical +2 was measured with *naive* ownership, which is a function of our own value, so it acted as shrinkage. Restored with a *real* ownership projection, it would fade crowd information: historically, the top quintile of excess ownership beat the bottom quintile by 3.7 DK points per player, relative to our projection. Test it only on the finish endpoint, and only with an informed projection.
4. **`own_est` is not an ownership estimate.** In the replay panel, the naive value softmax has a within-slate Spearman of **0.10** with actual Millionaire ownership. Our own points-per-dollar reaches 0.41. Anything that consumed `own_est` as ownership consumed noise.

---

## 4. Finding D: LineStar already has a pre-game crowd signal

`src/nfl_dfs/ingest/linestar_backfill.py` reads `GetSalariesV5` for salaries and actual contest
ownership. The same payload also carries, per player, LineStar's pre-game projection (`PP`, `Ceil`,
`Floor`). It also carries **projected ownership per slate** under `Ownership.Projected`, keyed by slate
id; the Sunday slate is the one with `SlateName == "Main"`.

I pulled all 72 weeks of 2022–2025 in one pass: 72 weekly calls, 1.2 s apart, with the backfill's
User-Agent. The data is stored outside the repo.

| test (players who played, projection ≥ 5, 2022–25) | result |
|---|---|
| accuracy: correlation with actual / MAE | ours 0.495 / 5.861; LineStar 0.506 / 5.863. Similar skill, and no sign of look-ahead. |
| walk-forward blend (weight fit on earlier seasons) | Weight 0.47–0.48. MAE: 2023 5.799 → 5.808; 2024 5.915 → 5.879; **2025 5.769 → 5.688**. |
| LineStar projected ownership vs actual (within-slate Spearman) | **0.784**, against 0.105 for the replay's `own_est` |
| excess of LineStar projected ownership → our residual | ρ +0.105, positive in 65/71 slates, top − bottom +2.2 |
| excess of LineStar's projection → our residual | ρ +0.099, 62/71, +2.0. Early games +0.049; late games +0.160. |
| actual-ownership excess left after both LineStar controls | ρ +0.120, down from +0.168. LineStar carries roughly a third of the crowd's edge. |
| replay books vs the field: LineStar minus ours, players who played | book +3.1, field +9.1 per lineup (field higher in 70/72). At the 0.48 weight that is about 27% of the −11.0 gap. |

**Caveats:**

- **Third-party data.** LineStar is a third-party service. The backfill already relies on its public endpoint, but its data must stay out of this public repo.
- **Late-game timing.** Its late-game projections may be updated after the early lock. That is legitimate for late swap, but not for the noon lock. Check its timestamp fields (`ProjectionChanges`, the period's `PU`/`OU`) before any historical late-game use.
- **Smaller live gain.** The live projection is already closer to the crowd (§3.3), so the gain there will be smaller than on the replays. It needs its own prospective read.

---

## 5. Finding E: money-path items

### 5.1 P_MIX is not in the Week-2/3 money path

**What the ledger says.** PREREG-054: "BOTH ARMS PASS — the program's strongest measured result … P_MIX
dominates P_ELIG on every endpoint." Its proxy was +0.0055, with every bank and all four LOSO seasons
positive, and a raw effect of +1.4.

**What the Week-3 path contains.** The path is `live_week.py --selector dual_emax` at nfl2 `69f98a7`.
None of the money-path code contains any participation logic:

- `live_week.py`, `live.py`, `pipeline.py`, `selectors.py` and `core/lineup.py`
- the Sunday scripts `sunday_build_host.sh`, `sunday_after_build.sh`, `sunday_runbook.sh` and `week_env.sh`

P_MIX appears only in research scripts.

**What replaced it.** The four live availability rules took its place:

- The Doubtful exclusion is a subset of P_ELIG, the weaker validated arm.
- The ×0.80 haircut and the cascade have no lineup-level panel.

I found no record of a decision to retire P_MIX. Together with the chalk fade, that makes two validated
levers lost at the repository boundary. The laptop's cross-repo consumption test (§A of its audit) would
have caught both.

### 5.2 The Questionable haircut hits players the inactives have already cleared

**The mechanism.** `find_questionable_players` selects on DK status **or** `injury_status ==
"QUESTIONABLE"`, and the Friday report status does not change when a player is declared active. So at the
final build (the 11:0x CT run after the 10:30 inactives), every active noon-game Questionable player
still gets ×0.80.

**The haircut's own evidence says that is too much for them.** The haircut commit reports a ratio of
Questionable to healthy players of 0.77–0.91 across 2018–24, 0.86 pooled. The 2022–24 seasons, which
include the zeros of players who sat, run 0.77–0.83. So the earlier seasons, when the panel held almost
no inactive rows, must have run higher.

**Proposal:**

- Apply ×0.80 only while a player's status is unresolved (late games at build time).
- Once he is active, apply the active-only ratio (measure it; it looks like about 0.9), or a practice-level adjustment.
- Once he is ruled out, remove him.

On a 15-point player the current rule over-discounts by roughly 1–1.5 points. This is the operator's
call; the Thursday dry run can list who it affects.

### 5.3 Additive recentering gives stars impossible floors early in the season

**The mechanism.** `finish_bank` shifts each lab draw row by (served mean − lab model mean). Early in the
season the lab component model is thin on usage windows (the 2026-09-12 note says it can "collapse to a
per-position constant"). So the shift is large for exactly the players the book leans on.

**The size in Week 2.** In the selection bank:

- 25% of skill players projected ≥ 5 had a simulated 1st percentile of at least 3 DK points, and 11% at least 5.
- Chase's 1st percentile was 8.4 (served 17.8, lab model 8.8) and Bijan's 8.6, where a real WR1 or RB1 scores under 5 points in roughly one game in ten. Flowers' (13.7) and Jefferson's (12.6) were worse still, compounded by the now-deleted DK-PPG stand-in.

**DST.** DST is a constant in the same bank. That is a known limitation, and PREREG-002's DST law did not
replicate on points. It is why one DST, the 49ers, sat in 61% of the Week-2 pool.

**Fix.** Replace the shift with a rank-preserving map onto production's own served distribution;
production already publishes p10/p50/p90/std. That keeps the lab's dependence structure and removes the
floors. The hsim bank calibrates upstream and has neither problem.

---

## 6. Recommendations

### 6.1 A weekly book-vs-field scoreboard (Monday, one query)

**What to compute.** For the entered book and for the pool: projected, realized, skill slots that did not
play, and realized − projection among players who played. Compare each against two benchmarks:

- (a) the Millionaire field's average lineup;
- (b) the average lineup of the 51–150-entry users.

The laptop's stratification gives the Week-2 reference points: 121.0 per entry for heavy users, 111.7
for single-entry users, and 98.4 for our book.

**Why it's worth it:**

- It separates availability (fixed), information and construction, every week, from standings alone.
- It is the quantity the "what winning requires" §5 target actually needs.

**Backfill.** Do Weeks 1 and 2 of 2026 now. The historical version is §3.2.

### 6.2 Put the crowd's pre-game information into the projection

There are two inputs to try:

1. **LineStar `PP` as a blend component** beside the props. Fit the weights walk-forward and per position. Props-or-nothing stays.
2. **A real pre-lock ownership model.** Inputs: LineStar projected ownership, salary, our projection and Vegas lines. Target: the 72 weeks of Sunday Millionaire ownership. Its excess over our projection enters the projected mean as a feature.

Test in three stages:

- **Player level first**, walk-forward by season, with slate-clustered inference (thousands of rows per season).
- **Then on the replay books**, with the §3.2 decomposition as the endpoint.
- **Then prospectively.**

The primary endpoint is the book-vs-field gap among players who played, not MAE. The gain lives in which
players the optimizer prefers.

### 6.3 Late swap as information, not as chasing

**Why this is a new mechanism.** The closed late-swap work re-chose late slots on early-game *scores*.
That covers ledger rows 023 and 024/PREREG-003, and the post-mortem's late-swap study. None of it used
late *news*:

- the late inactives, about 90 minutes before the 3:05/3:25 CT kickoffs;
- late role reports;
- fresh late-game projections.

The crowd's historical edge is concentrated exactly there (ρ +0.275 late against +0.094 early), and the
live build cannot see it by construction.

**Proposal.** At about 13:40 CT:

- re-run `project-slate` (the cascade already redistributes a late scratch's usage);
- pull LineStar's late-game projections;
- re-optimize each entered lineup's late slots.

That includes moving *into* the beneficiaries of a late scratch, which the current rule (remove only OUT
or inactive players) never does.

**Shadow first,** as the money-path rules require. Record the proposed swaps and settle them for three or
four weeks.

**Historical proxy.** Re-optimize the replay books' late slots on a blend of our projection and
LineStar's late `PP`, after confirming LineStar's timestamps.

**Size.** Unknown for the live system. Historically, the crowd's late-game excess separated the top and
bottom quintiles by 5.5 points per player.

### 6.4 The money-path items in §5

- Condition the Questionable haircut on resolution.
- Re-run P_MIX against the four live rules on the historical panel, with the same pools and judge-only arms.
- Add the cross-repo lever-consumption test.
- For weeks when the lab model is thin, replace the additive recentering with a marginal map, and test it on the dual bank.

### 6.5 Validate the synthetic field on Week 2

The PREREG-098 IPF sampler was gated on Week 1 only, because Week 2 did not exist yet. Before any finish
endpoint is used again, re-run its gate against Week 2's 172,692-entry field: cutoff correlation,
realized cutoffs and the ownership error.

### 6.6 Market conversion (a cheap check)

**The concern.** `prop_line_to_mean` treats yardage lines as the mean of a symmetric normal (σ = 0.3 ×
line). `market_points` also omits parts of DK scoring:

- the +3 bonuses at 100 rushing or receiving yards and at 300 passing yards;
- interceptions (−1);
- fumbles.

**Expected direction.** The market should under-project high-volume WRs and RBs by roughly 0.5–1.5
points. For QBs it should be roughly neutral, because the bonus and the interceptions offset.

**Why it matters, and the check.** The blend has no intercept, so it cannot absorb a bias like this. One
query settles it: mean(actual − market_points) by position and line band, 2023–25. This is untested here.

### 6.7 Simulator: settle the slate factor on history, then choose objectives

- **Measure it.** Run `slate_ppc.py` over 20–30 replay slates.
- **Add a factor only if needed.** If realized pool levels are over-dispersed relative to the worlds, add a slate-wide factor fitted to that dispersion.
- **Either way, drop absolute thresholds as objectives** (P(≥ 194), the cash line). Expected-max and field-relative objectives are insensitive to the slate level.

### 6.8 Contests and money

- **"Winning a large field is closed" is another way of saying "no edge".** At parity, P(win) is the share of the field you hold, and every contest returns minus the rake. The same per-lineup edge multiplies P(win) in every field size, so contest choice cannot create edge.
- **Make ROI computable from the warehouse.** Capture every entered contest's payout table (the `contests/v1/contests/<id>` endpoint used in the Week-1 A5 capture) and join it to standings.
- **Measure how soft each field is, from standings.** Compute the share of entries from 51–150-entry users and their mean percentile. Prefer contests where that share is low (single-entry, 3-max).
- **Consider volume.** Until the scoreboard shows our book ahead of the heavy-user cohort for several weeks, fewer entries is the cheapest edge available. That is the operator's call.

---

## 7. Answers to the §7 questions

1. **Learning with two slates.**
   - Compute the simulator's null (§2) before reading any live comparison; here it turned C2's flips into defects.
   - Ask questions at the player level over 72 slates, with slate-clustered inference, wherever the question allows it (§3.1: t = 15).
   - Use the book-vs-field decomposition as the field-relative endpoint, on replays and live (§6.1). It needs no field lineups.
   - Validate the IPF sampler on Week 2 (§6.5).
   - Treat 2026 weeks as preregistered confirmations, not discovery.
2. **Calibration.**
   - Composition: nothing to fit from Week 2 (§2).
   - Level: plausibly a missing slate factor. It is not forecastable (the retraction stands), so model it as variance fitted on history, and avoid threshold objectives.
   - The early-season floors (§5.3) are a real marginal defect worth fixing.
3. **Pool mean.**
   - First, information (§3, §4, §6.2, §6.3).
   - Then the haircut timing and P_MIX (§5).
   - Then the market-conversion check (§6.6).
   - Practice level is still a good candidate, but it is not what drives the crowd effect: the healthy-only result is unchanged.
4. **Contests.** See §6.8.
5. **Construction relative to the field.** Work through the projection, not through exposure rules. Correct the means with the crowd's information, then let expected-max and any field-aware objective work on corrected means. Duplication is second-order in large fields; the information loss is first-order.
6. **Blind spots.**
   - The historical panel's projection is informationally behind both the crowd and the live build, so field-relative verdicts drawn from it are suspect (§3.4).
   - Validated levers disappear at the repository boundary: P_MIX and the fade (§5.1).
   - `own_est` is not an ownership estimate.
   - The lab's early-season marginals have artificial floors (§5.3).
   - The research effort sits almost entirely downstream of the projection, while the largest gap this review measured is at the information layer.

---

## 8. Limits of this review

- **One live week.** The slate check covers Week 2 only; the Week-1 run is not on this host.
- **One replay configuration.** §3.1–3.2 use projections from one panel run (pitclean K=1, 2026-08-11) and books from `replay_lineups_pitk1`, an August configuration with 80 entries, older than D12800/dual_emax. The same per-slot pattern across every position and salary tier points to a projection-level effect, but its size for today's books is unmeasured.
- **"Played" means a box-score row.** A player who dressed without a touch counts as not playing, on both sides of every comparison.
- **Timing caveats.** Ownership is post-lock. LineStar's late-game timing is unverified.
- **No preregistered reads.** I did not re-run any preregistered reader. Everything here nominates; nothing adopts.

---

## 9. Reproduction

```bash
cd reports/lab-handoffs/2026-09-22-external-review
OUT=~/.cache/nfl-dfs-external-review          # outside the repo: DK ownership and vendor data
PY=~/projects/nfl-predictions/.venv/bin/python
$PY pull_inputs.py $OUT                         # BigQuery + one polite LineStar pass
$PY crowd_and_gap.py $OUT                       # §3, §4 and the own_est check
$PY slate_ppc.py <week-2 run dir> 2 $OUT --dual # §2 raw column (--dual adds the combined bank: -0.554, -50.67)
$PY slate_ppc.py <week-2 run dir> 2 $OUT --condition-availability     # §2 middle column
$PY slate_ppc.py <week-2 run dir> 2 $OUT --condition-availability \
    --override "Justin Jefferson=17.27" --override "Zay Flowers=14.70" \
    --override "Ladd McConkey=14.82" --override "Jack Bech=7.11"      # §2 right-hand column
```

The Week-2 run used here is the archived D12800 run
(`review-evidence/overnight-20260918/d12800-archive-20260920`, built 2026-09-19 15:30Z, nfl2 `2dc116c`).
