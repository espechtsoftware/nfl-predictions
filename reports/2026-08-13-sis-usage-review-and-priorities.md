# SIS: usage review and priority challenge

Date: 2026-08-13. Review of the SIS DataHub acquisition, the team-context
audit, and the frozen QB line protocol. **No code was changed.**

---

## What has been done well

The acquisition discipline is the best of any data source in this project.
Specifically:

- **The 200-row cap was caught as a completeness hazard, not a nuisance.** An
  exact 200-row Week 1 pass-defense result correctly triggered "the paid cap is
  still binding and must be split rather than treated as complete." That is the
  failure mode that silently truncates a backfill.
- **The `Games=1` / Week / Opponent double check** compensates for Rates/Value
  CSVs omitting the visible `Games` column — an exporter that verifies scope
  from the API response *and* independently from the downloaded CSV.
- **The identity sidecar.** CSV exports drop `playerId`/`teamId` while the
  rendered response carries them. Retaining a secret-free identity manifest
  from the same query avoids the name-join problem that cost this project real
  time on the Fantasy Points intake.
- **The redundancy screen ran before modelling.** SIS pass-defense EPA at
  `r=0.8803` against the existing `epa_per_dropback_allowed_l6` was correctly
  refused wholesale despite being proprietary. That is exactly the discipline
  that should have applied to `cb_*` in July.

---

## The priority challenge

Tranche 1 is a **QB offensive-line bundle** — lagged pass blown-block rate plus
blocking Points Earned/play, added as team-context features. The
sign-repeatability evidence is honest and the correlations
(`r ≈ 0.04–0.06`) are reported without inflation.

But structurally this is **a seventh marginal-channel arm**, and the six before
it all ended the same way:

| arm | distributional result | tail result |
|---|---|---|
| Route Share components | MAE + CRPS better every fold | tail gate failed |
| Fast-role bundle | +2.19 pts vs matched controls, all 6 seasons | 11/107 vs 17/107 |
| Fitted-K (v1) | allocation NLL better, CI wholly favourable | exact-80 rejected |
| SCHED sync | CRPS −0.00145, MAE −0.00359 | Brier flat |
| Team-QB quality | MAE 3.63282 → 3.61681 | Brier/CRPS/pinball worse |
| G2 QB-Gumbel | joint-q90 Brier and variogram both improved, clean intervals | gate failed on WR |

G0 explained the mechanism: the terminal simulator produces a QB→WR lift of
**1.053** against a realized **3.3228**. It is very nearly teammate-independent.
A nine-player sum of near-independent components concentrates, so its extreme
tail is governed by aggregate variance — **a feature that shifts one player's
mean cannot propagate into the joint tail.**

The QB line bundle is a mean-shift feature entering that simulator and being
judged by a tail gate. I would not cancel it — the evidence is honest and the
protocol is frozen — but I would **predeclare its expected failure mode**, so a
null is read as confirmation rather than as SIS being uninformative. Write into
the protocol now: *if this fails while improving MAE/CRPS, that is the
established six-arm pattern and does not close SIS.*

---

## What SIS actually unlocks that nothing else has

### 1. Cornerback-level coverage — the one coverage hypothesis that is still open

My previous review closed the coverage family with the effect-size arithmetic:
three tested shell-fit mechanisms (prior-season fit, the union that tied on all
107 slates, same-season last-four), all failing, with a measured ceiling of
**0.04–0.09 DK points** because shell coverage is a *team-averaged, diffuse*
property. That review ended:

> "Cornerback-level matchup remains untested, because no cornerback data exists
> in any source held … it is a *separate* hypothesis with a materially better
> mechanism story and should not be considered closed by the shell results."

**SIS pass defense is that data.** Player-level coverage snaps, primary-defender
targets, catchable balls and completions allowed, deserved catch rate, rating
against, yards per coverage snap — and, critically, filters for **both defender
and receiver alignment/position**, plus route and coverage shell.

That last point matters more than the metrics. Defender-*and*-receiver alignment
filters mean you can query a specific defender's performance against receivers
at a given alignment. That is much closer to a real matchup construct than the
crossing inference I had assumed would be necessary, and it is a *concentrated,
individual* effect rather than the diffuse team average whose ceiling I measured
at 0.05 points.

Caveat to state in any protocol: SIS gives defender quality by alignment, not a
**shadow assignment**. That a specific corner covered a specific receiver
remains an inference from alignment crossing. Check it cheaply first — pull one
WR's alignment distribution and the opposing CBs' alignment distributions for a
single game and see whether the crossing is sharp or mushy. If alignment shares
are diffuse, the whole construct degrades back toward a team average and the
0.05-point ceiling reapplies.

### 2. Conditional allocation — the copula channel, not the marginal one

This is the idea I would most like to see preregistered, because it puts SIS in
the channel that is actually binding.

G0 says the missing structure is QB→receiver coupling. G2 showed a *context-free*
single factor cannot supply it for WR — the calibration selected no WR
activation because one shared factor forces WR-WR positive, which reality does
not show.

**What determines which receiver benefits when a quarterback has a big game?**
Partly the defense. If the opponent's best corner covers the alignment WR1
occupies, a QB explosion flows disproportionately to WR2, the slot and the tight
end. That is a **conditional allocation** signal — precisely the input needed to
make the Dirichlet allocation *context-dependent* instead of context-free.

Concretely: use SIS defender quality by alignment to modulate the **centering
and concentration** of the per-team target allocation for that game, rather than
to shift any player's mean. Mean-preservation can still be enforced at the team
level; only the split changes.

This is a different proposal from everything tested so far in two ways: it
targets the copula rather than the marginal, and it makes the allocation
conditional rather than global. It should be gated on the **G0/G1 dependence
scorecard** — QB→WR and QB→TE lift error, WR-WR must-not-worsen — not on a
30-point Brier.

Note it composes with, rather than competes against, the ledger-coupling arm
proposed after G2: a ledger supplies the *shared production* force, and
conditional allocation supplies the *competitive* force with the right
per-receiver weights.

### 3. Boom% and Bust% are tail statistics and have not been prioritised

Every SIS candidate evaluated so far — EPA, blown-block rate, Points
Earned/play, pressure rate — is a central-tendency quantity. The Value views
also expose **Boom% and Bust%** across passing, rushing, receiving and pass
defense.

For a tail-first objective those are the more natural inputs, and they are
vendor-computed from charting the project cannot reproduce. They belong in the
first receiver bundle, not in a later tranche.

---

## Budget and sequencing advice

The cap arithmetic deserves attention before the next tranche. Team-game grain
is 32 rows per week and safe. **Player-level pass defense at game grain is
not**: roughly 200 qualifying defenders per week means the 200-row cap binds
constantly, forcing a split by SIS team ID — 32 queries per week, per report
family, per season. Six seasons × 18 weeks × 32 teams is far beyond a 1,000
query weekly allowance for even one family.

So do not attempt a broad player-level backfill. Two adjustments:

1. **Prefer filtered views over broad ones.** The distinct content is in the
   splits — defender × receiver alignment, coverage shell, route — not in the
   unfiltered totals. A narrow filtered query answers the actual question at a
   fraction of the request cost.
2. **Restrict the first player-level pull to the seasons that carry the
   evaluation.** 2023–2025 are the held-out folds for every recent gate.
   2019/2021/2022 can follow only if the mechanism survives.

---

## Recommended order

1. Run the frozen QB line arm as written, with the expected-failure-mode note
   added to its protocol.
2. **Cheap alignment-crossing feasibility check** (one game, one WR, opposing
   CBs) before committing any request budget to the CB matchup path. This is a
   handful of queries and it decides whether §1 is viable at all.
3. If crossing is sharp: preregister the **CB matchup bundle** for WR/TE, with
   Boom%/Bust% included, gated score-free.
4. In parallel, preregister **conditional allocation** (§2) against the G0/G1
   dependence scorecard. This is the item with the best mechanism story, because
   it is the only SIS proposal aimed at the channel that six arms have shown to
   be the binding one.
5. Rushing/run-defense and blocking tranches after the pass-game path resolves.

The one-line version: **SIS's team-context columns are another marginal arm;
its player-level pass-defense splits are the first genuinely new mechanism this
project has acquired in months, and they belong in the copula.**
