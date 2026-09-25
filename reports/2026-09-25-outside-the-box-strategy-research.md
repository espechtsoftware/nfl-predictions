# Outside-the-box research: untried levers, new evidence, and a ranked plan

**Date:** 2026-09-25 (Friday before the Week-3 lock). **Author:** Claude, in a remote session on branch
`claude/draftkings-lineup-strategies-cjlxo0` (both repositories). **Asked for by the operator:** review everything both teams
have tried; do deep thinking and web research on cutting-edge strategies that have not been tried; think outside the box
about how predictions are made; then write the suggestions up.

**Status:** nominations only. Nothing here changes the money path, adopts a lever, or reads a frozen cohort. Each item is
written as a candidate package for the in-season adoption track (`reports/2026-09-19-in-season-adoption-track.md`, classes
R/C/S/E), so it can become a preregistration without re-deriving it.

**New evidence.** Nine small analyses were run for this document (§2). They use public data (nflverse releases, Fantasy
Football Calculator ADP) plus LineStar's public `GetSalariesV5` endpoint, called with the same conventions as
`src/nfl_dfs/ingest/linestar_backfill.py`: one pass, 1.2 s between calls. The scripts are in
`reports/lab-handoffs/2026-09-25-outside-the-box/`. No third-party data is committed; only aggregate statistics appear here.
Nothing touched BigQuery, Cloud Run, the lab lanes or any 2026 outcome beyond public box scores.

**What was read before proposing anything:**
- the lab: all 197 `LEDGER.md` rows and every `PREREG-*.md`;
- production: the 120-addendum system study and the September syntheses;
- about 430 idea items catalogued from both repositories' memos, reviews and handoffs, each checked against the ledgers;
- production's projection code at `d5705e9` and the lab's money-path code at `60b7109`, plus the pin `9b341d77` deltas
  listed in production's README;
- the first ~2,500 lines of `HANDOFF.md`, the move document, `OPEN-DEFECTS.md` and the Week 1–2 post-mortems;
- four web research passes (about 200 searches), on:
  - the DFS portfolio literature;
  - predictive modeling;
  - market-implied distributions;
  - cross-domain analogues.

Appendix A maps each suggestion to the closest item already in the ledgers and states what is different. That was the
test every idea had to pass.

---

## 0. The short version

**Where the programme is.** Candidate generation, selection and dose have been tested more thoroughly than almost any
public DFS work I found.
- Selection is closed for the current simulator.
- Dose saturates at D3200.
- The finish objective, the learned selectors and late-swap chasing all failed their frozen reads.

The ledger's verdict, "the gap is belief, not search", is right. The remaining edge must come from three places:
- **better information at the moment of lock;**
- **lineups built the way winners are built;**
- **a simulator that is right where winners live, with a selector that does not amplify its errors.**

The literature agrees on where profit comes from. Hunter, Vielma and Zaman made money only in contests where their
lineups' *mean* beat the field's (arXiv 1604.01455). Production's own target is the same idea: move the pool mean from
the 49th to the 65th+ field percentile.

**Nine new facts (§2):**
1. **There is no slate-wide scoring factor in real football.** Across 4,049 Sunday main-slate games (2006–2025), game
   totals' misses against the closing line are uncorrelated within a week (ICC −0.002, permutation p = 0.67). The spread
   of weekly slate totals matches independent games exactly (45.3 vs 45.3). The simulator's "level" misses must be fixed
   elsewhere.
2. **Opponents' *fantasy* output is coupled; their scores are not.** Given the market's team totals, opposing teams'
   skill-position DK totals correlate **+0.21** (3,663 games). Their scoreboard points correlate +0.007 and their play
   counts **−0.41**. The coupling runs through game script, not through shared volume, which is how the incumbent law
   builds it.
3. **Same-team pass catchers are almost independent.** WR1–WR2 residuals correlate +0.016 (±0.05); the QB is the hub
   (+0.29 to +0.38 with his pass catchers, +0.24 with the opposing QB). The law that *generates* candidates has
   WR1–WR2 at +0.277.
4. **The crowd is informed except when it chases last week's box score.** Over 74 Millionaire slates (2022–26):
   - The part of ownership explained by last week's surprise is large, systematic, predictable before lock, and carries
     **zero** outcome information: ρ +0.015, t 1.3.
   - Everything else in the crowd's excess ownership predicts outcomes strongly: ρ +0.176, t 15.4, positive in 67/69
     slates.
   - This defines which chalk to follow and which to fade.
5. **The simulator cannot produce the games that win tournaments.** Each player's draws are capped at
   q99 + 0.25·(q99 − q95). Real main slates average **0.93 skill games of 40+ DK and 0.31 of 45+**. WRs projected 15–20
   reach 45+ in 0.9% of games.
6. **Lead RBs leave games early in 4.8% of starts**, and their backup's chance of 20+ points then rises from 3.5% to
   14.2%. Neither law has an in-game exit process.
7. **Crowd signals are a *game-theory* lever, not a projection lever.** Blended into a projection before lock, they move
   accuracy only about +0.005 r. The large crowd edge is late information.
8. **Preseason ADP carries a weak early-season signal** beyond a good public projection (ρ +0.06, Weeks 1–2 and 5–8).
9. **Kalshi now lists NFL player fantasy-point markets** (checked this week): thresholds for skill players, **D/ST** and
   kickers, plus per-player scalar ladders that pay $0.01 per PPR point, so their price is the market's *mean*.

**The recommendations, ranked:**

| # | Suggestion | Class | Earliest | Cost | Why it ranks here |
|---|---|---|---|---|---|
| 1 | **Enter a book selected on Sunday information.** Keep the Saturday D12800 pool; re-simulate both banks after the 10:30 CT inactives and re-select (plus a small Sunday boom batch) | S | Week 4 shadow, Week 5 entry | small | Saturday vs Sunday projections correlate only 0.82 (mean \|Δ\| 1.07 pts). The staleness buys dose above D3200, where no significant gain has been measured |
| 2 | **Fade only the crowd's recency-chasing; follow the rest.** A recency-aware chalk predictor feeds a successor to L02 | C + S | Week 4 (predictor), Week 5 (sleeve) | small | New evidence §2.4; it is the "better chalk predictor" L02 named as its reopening mechanism |
| 3 | **Give the simulator a real upper tail** (a generalized-Pareto tail above q97–q99), paired with #7 | C | Week 5 | small–medium | Winners carry 3.4 players at 30+ (ours 1.8). No simulated world contains a 45-point game |
| 4 | **Clean the market inputs:** 8–10 books at the same credit cost, de-vigging chosen per market family, and **reconciling player props with team totals (MinT)** so unpriced players get market-consistent means | C | Week 5 | medium | 55% of the mean rests on 2 books and 6 markets, and 57% of rows lack ≥ 2 markets |
| 5 | **Capture Kalshi fantasy-point, D/ST and yardage ladders** as a new market | C | capture now; grade by Week 6 | small | The first direct market on fantasy points; DST is constant in every world today |
| 6 | **Market-consistent worlds by per-game entropy pooling**, replacing the additive recentring | C | Week 6+ | medium | The principled fix for recentring floors and shape; licensed per game by fact 1 |
| 7 | **A third, empirical critic and disagreement-aware selection** | S | Week 6+ panel | medium | DUAL_EMAX (two critics) is the only selection change that ever passed; the optimizer's curse is the open objection |
| 8 | **Calibrate the generation law's dependence** to the public card (facts 2–3) | C | Week 6+ | medium | The incumbent generates every candidate with the wrong receiver and cross-team structure |
| 9 | **Cross-season player state** (dynamic priors, ADP) | C | 2027 Weeks 1–5 (and Weeks 4–6 now) | medium | 100% of Week-1 rows and 55% of Week-2 rows are cold-start |
| 10 | **Measure edge every week with information coefficients** (Grinold–Kahn) | eval | Week 3 settlement | small | An IC of 0.10 is detectable in about 6 weeks; a 2× win-rate edge needs about 4,000 weeks of first-place finishes |
| 11 | **Late window by news and field state**, not by chasing; flex the latest-starting player | S/E | Week 4 shadow | small | The crowd's late edge (ρ +0.096 late vs +0.035 early) is news; chasing is closed |
| 12 | Duplication-aware payoff, **only once chalk cores enter the book** | S | with #2 | small | Duplication is ~0 for today's books; it becomes real with chalk |
| 13 | Contest economics: rake and field composition | money | now | small | The $20 Millionaire's rake was 13.2%, the $5's 15.9% |
| 14–19 | Exploratory: an LLM news agent, in-game exits, betting splits for ownership, an inverse-optimization field model, wind and referees, Kalshi as a hedge | — | — | — | §3.4 |

**What not to do** is in §4. It includes: adding a slate factor, dropping bring-backs because scoreboard points are
independent, fading total ownership, and raising the dose further while the entry is built on Saturday.

---

## 1. Diagnosis: where the points are lost, in the programme's own numbers

**The book does not look like winning lineups.** From the winner-anatomy reports (09-22) and the Week 1–2 fields:

| | winners / field top | our lineups |
|---|---|---|
| "Chalk core": ≤ 2 players under 5% owned and ≥ 1 at 20%+ | 85–87% of the top 0.1%; 74% of 69 historical winners | 7.2% of the Week-2 pool |
| 3 or more players under 5% owned | 20% of winners | 90% of the pool |
| salary ≥ $49.5k | 95–98% of top finishers | 62% |
| players at 30+ DK | 3.4 per winner | 1.8 per book-best |
| stack depth | 1–2; only 12% legal under our house rules | QB + 2 + bring-back forced |

A 72-slate replay with pre-lock predicted ownership put the cost of 3+ sub-5% players against 0–1 at **8.19 points per
lineup** (se 1.57).

**Why the supply looks like that.** The boom family is the exact best lineup in each simulated world (in effect, Thompson
sampling). Every property of that world shapes the pool:
- **Hard-capped tails** (`nfl2/src/nfl2/core/draw_shape.py:315-316`). A world almost never contains one player's 45-point
  eruption, so plausibly its optimum spreads the "luck" across several cheap, low-owned players instead.
- **Over-correlated same-team receivers** (+0.277 vs +0.02 to +0.04 real). Team-wide booms are over-represented, so
  double-receiver stacks are over-supplied.
- **A constant DST.** The DST pick is decided by salary; the 49ers were in 61% of the Week-2 pool.
- **At the D800 dose, the worlds visited are the top 6.4% by slate total** (640 of 10,000, visited in order;
  `pipeline.py:264-266, 468-473`). With no real slate factor (§2.1), those worlds are coincidences of independent games.
  At D12800 almost every world is visited.

The ledger already says 0 of 51 real winners were a world optimum.

**Why selection cannot fix it.** DEMAX optimises a simulator whose book-level tails run 1.5–5× too optimistic (SD-A;
LEDGER 036). "Optimizing harder against the same law overfits the simulator" is the lab's own lesson 5, and it is
Smith & Winkler's *optimizer's curse* (Management Science 2006). The one selection change that passed was adding a
*second, different* critic (DUAL_EMAX, +1.39).

**Why the information lags.**
- The entered book is the **Saturday 10:30 CT D12800 build**. Sunday news reaches it only through manual OUT removals
  (move document §2, table "the entry").
- The crowd builds until noon CT. Its informative ownership predicts our residuals, and three times more strongly for
  late games (external review §3.1).

**The one strong external result that fits all of this.** Haugh & Singal (Management Science 2021) estimate, within
their model, that knowing the field's realized ownership is worth about +20% in top-heavy contests. What matters is not points in isolation, but
points relative to what the rest of the field holds.

---

## 2. New evidence produced for this document

All scripts: `reports/lab-handoffs/2026-09-25-outside-the-box/` (a README gives the commands). ρ below is the
within-slate Spearman correlation averaged over slates; t is across slates.

### 2.1 No slate-wide scoring factor (`a_slate_factor.py`)
- **Data:** nflverse schedules with closing lines; regular-season Sunday games kicking off 1:00–4:45 pm ET.
- **Residual:** final total points minus the closing total.
- **Results:**

| panel | games | weeks | residual SD/game | within-week ICC | permutation p | weekly slate-sum SD (observed vs independent) |
|---|---:|---:|---:|---:|---:|---|
| main slate 2006–25 | 4,049 | 343 | 13.26 | −0.0018 | 0.67 | 45.3 vs 45.3 |
| main slate 2014–25 | 2,384 | 208 | 13.15 | −0.0065 | 0.88 | 43.0 vs 44.2 |
| all regular season 2006–25 | 5,199 | 345 | 13.30 | −0.0021 | 0.66 | 51.0 vs 51.6 |

- **2026 in context:** Week 1 ran +70 total points over the lines (+4.4 per game) and Week 2 −75. Each is about 1.3–1.4 SD
  of a 16-game sum under independence: ordinary.
- **Meaning:** week-to-week "level" swings are the sum of independent game misses. The fixes that follow are:
  - game-level variance: target a total SD of about 13.2 around the close and a team SD of about 9.4 around the implied
    team total;
  - the pool's concentration in a few games (`MAX_PER_GAME=4` limits it);
  - player-level projection bias.

  None of them is a shared football factor. If pool-level misses persist after those fixes, the remaining candidate is
  a projection error shared across players in a week, as when the Week-2 availability defects moved many projections at
  once. That is a model problem to fix at the source, not a factor to simulate.
- **This answers** question 2 of the 09-22 state-of-the-problem document. It also settles the external review's "add a
  slate factor *if needed*": **not needed**.
- **It also contradicts** production's own reading of the star-tail misses. HANDOFF 2026-09-22 (late) called them "the
  slate LEVEL factor, not marginal width". The football has no such factor, so that attribution needs revisiting.
- **Wind** (recorded, not forecast): totals ran −1.6 under at 15–20 mph against +1.3 over in calm (n 326 / 769), a
  small under-adjustment by the market.

### 2.2 Opponents' fantasy output is coupled through game script (`b_cross_team_fantasy_coupling.py`)
- **Data:** 3,663 games, 2012–25. Each team's QB+RB+WR+TE DK total is regressed on its own and its opponent's implied
  totals; the residual SD is 23.1 (CV 0.26).
- **Correlation of the two teams' residuals:**
  - skill-position DK: **+0.212**;
  - offensive plays: **−0.408**;
  - scoreboard points (§2.1 data): **+0.007**.
- **Reading:** when one side over-performs, the other side's *fantasy* output rises with it, through trailing-team pass
  volume and shared big-play conditions. Plays trade off (possession), and the scoreboard does not co-move. Bring-backs
  *are* supported.
- **The incumbent law has the right net sign for the wrong reason.** Its two teams' volume factors correlate about
  +0.16 (`core/game_sim.py:286-328`; the simulator review's replica), so it couples *volume*, which reality couples
  *negatively*. This is the target for the built-but-never-tested `SCRIPT_FEEDBACK` (catalog C03) and the hybrid
  game-factor idea (C02).

### 2.3 A residual correlation card (`d_residual_correlation_card.py`)
- **Method:** actual DK minus LineStar's pre-game projection, 74 main slates. Roles are assigned by salary rank within
  team and position; 95% CI about ±0.05.

| same team | ρ | opponents | ρ |
|---|---:|---|---:|
| QB–WR1 | +0.383 | QB–opp QB | **+0.235** |
| QB–WR2 | +0.356 | QB–opp WR1 | +0.088 |
| QB–TE1 | +0.287 | WR1–opp WR1 | +0.057 |
| QB–RB1 | +0.072 | RB1–opp QB | +0.068 |
| **WR1–WR2** | **+0.016** | RB1–opp RB1 | −0.080 |
| WR1–TE1 | +0.014 | | |
| RB1–RB2 | +0.040 | | |

- **Reading:** the QB is the hub. Pass catchers correlate with him but not with each other, because target competition
  cancels shared volume. This is consistent with the lab's own measurement (LEDGER: incumbent +0.277 vs realized
  +0.041).
- **What is new:** one card, conditioned on a market-informed projection, with confidence intervals. Any law repair can
  use it as an outcome-free gate.
- **An independent check** by the market web pass on nflverse yardage found QB–WR1 at 0.48, WR1–WR2 at about 0, and
  QB–lead-RB rushing at −0.11. The blog figure of 0.65–0.75 for QB–WR1 is overstated.

### 2.4 The crowd: information vs recency-chasing (`c1`–`c7` scripts)
**Panel.** 74 Sunday main slates, 2022 to 2026 Week 2. Each has LineStar's pre-game projection (PP), its projected
ownership, the actual ownership of the slate's largest Millionaire, and actual DK points. The analysis covers skill players
with PP ≥ 4: 9,505 rows, of which 97% recorded a box-score line; the outcome tests use those.
- **No sign of look-ahead** in PP: accuracy r is 0.50–0.54 each season, the same as our replay model (0.495).
- **Caveat carried from HANDOFF (2026-09-22):** LineStar's historical periods were last updated the Monday after each
  slate, so their pre-lock status cannot be proven. The definitive re-run uses the team's own point-in-time replay
  projections and `contest_ownership` (§3.1 R2, test (a)).

| test | result |
|---|---|
| excess *actual* ownership (beyond PP, salary, value, position) → residual | ρ **+0.170** (t 17.0, 72/74); quintiles −1.95, −0.52, −0.07, +0.78, +1.72 |
| early games / late games | +0.161 (t 12.3) / **+0.194** (t 10.4) |
| excess *projected* ownership (LineStar's model beyond its own PP) → residual | +0.096 (t 10.6, 69/74) |
| drift = actual beyond projected ownership → residual | +0.054 overall; early +0.035, **late +0.096** (t 5.1); late-game drift quintiles −1.46 → +1.06 pts |
| drift → the player actually played (availability) | +0.091 (t 8.4) |
| **last week's surprise → excess actual ownership (does the crowd chase?)** | **+0.226 (t 18.9, 69/69 slates; 17/17 in every season)** |
| last week's surprise → this week's residual | +0.015 (t 1.3): no information |
| **recency-driven part of excess ownership → residual** | **+0.015 (t 1.3, 41/69)**; per season +0.013, +0.034, +0.011, +0.000 |
| **everything else in excess ownership → residual** | **+0.176 (t 15.4, 67/69)**; quintiles −2.02 → +1.74; every season +0.15 to +0.20 |
| elasticity | +10 pts of last-week surprise → **×1.35** ownership beyond projection, salary and value (median slope) |
| by last-week band | bust ≤ −8: owned **0.77×** fair, residual −0.19; boom ≥ 8: owned **1.57×** fair, residual +0.23 |
| LineStar's own ownership projection under-predicts the chase | drift vs surprise +0.145 (t 10.8); last week's boomers: actual 10.1% vs projected 8.6% |
| walk-forward ownership model, adding surprise and its positive part to projected ownership | within-slate Spearman 0.769→0.780 (2023), 0.800→0.808 (2024), 0.758→0.757 (2025); **bias on last week's boomers −4.5 / −4.8 / −3.6 pp → +0.2 / −0.4 / +0.2 pp** |

- **Top-15 chalk per slate, split by recency lift:**
  - Recency chalk and informed chalk carry the same projection (16.1 vs 16.2).
  - Recency chalk is **~10% more owned** (21.7% vs 19.8%) and does no better: residual +0.81 vs +1.48, paired −0.65
    (t −1.0); P(≥25) 21.7% vs 23.2%.
  - Both chalk groups beat PP, so the crowd is informed about chalk too.
- **As a pre-lock *mean* adjustment the crowd is worth little.** A walk-forward model of PP plus excess projected ownership
  moves r +0.010 / +0.006 / +0.002 (2023/24/25) with MAE flat.
- **What this means:**
  - The crowd's big edge is late information: the drift, late games, and availability.
  - The exploitable error is a behavioural one: chasing last week. It inflates ownership 1.3–1.6× with no detectable change in
    the outcome distribution, which is the textbook definition of negative leverage.
  - This is the missing distinction behind two findings:
    - the naive fade's crossed signs;
    - the external review's warning not to "fade crowd information".

### 2.5 Eruptions vs the simulator's tail cap (`g_eruptions.py`)
- **Frequency:** 0.93 skill games of 40+ DK per main slate, and 0.31 of 45+.
- **By projection band** (LineStar PP, 2022–26):

  | position | PP band | P(≥40) | P(≥45) | P(≥50) | empirical q99 |
  |---|---|---:|---:|---:|---:|
  | WR | 15–20 | 2.9% | 0.9% | 0.2% | 44.6 |
  | RB | 15–20 | 1.7% | 0.56% | 0.37% | 42.3 |
  | RB | 20–30 | 3.2% | 1.6% | 1.6% | 50.0 |
  | QB | 20–30 | 2.2% | 1.1% | 0.37% | 45.3 |

- **Tail shape:** above 35 points the tail is roughly exponential, with a mean excess of 4.5–5.2 for QB, RB and WR.
- **The simulator:** the lab law's cap, q99 + 0.25·(q99 − q95), holds each player about 2–3 points above his q99. So
  45–55-point games appear only for the few players whose q99 is already near 45, and never far beyond it. This agrees with
  the lab's SD-C ("player upper tails are too light") and LEDGER 108 (WR ≥ 40 under-predicted 2×).

### 2.6 In-game lead collapse (`e_ingame_lead_collapse.py`)
nflverse snap counts, 2018–25. The lead player is the one with the top snap share over his prior three games. A game
counts as a collapse when he is active but plays fewer than 50% of his usual snaps and fewer than 40% overall.

| position | collapse rate | lead's DK (normal → collapse) | top backup's DK | backup's P(≥20) |
|---|---:|---|---|---|
| RB | **4.8%** | 16.4 → 4.7 | 5.5 → 12.0 | 3.5% → **14.2%** |
| QB | ~8% (biased sample) | 18.2 → 2.1 | 2.1 → 13.4 | 1.0% → 23.5% |

- For RBs, 17% of backups' 20+ games came in collapse games.
- Production already identified QB early-exit busts and a missing TE zero mass (TE at 0 points: 0.2% simulated vs
  7.7% realized) in catalog A28 (`reports/2026-09-23-wr-bust-gap-sizing.md`). **The RB backup-boom joint structure is
  new.** Second-order for lineups, but real.

### 2.7 Preseason ADP (`f_preseason_adp.py`; Fantasy Football Calculator API, free, 2022–25)
Excess preseason value (ADP beyond LineStar's weekly projection and salary) predicts the residual:

| weeks | ρ | t | slates positive |
|---|---:|---:|---|
| 1–2 | +0.059 | 2.0 | 7/8 |
| 3–4 | +0.035 | 1.2 | — |
| 5–8 | +0.061 | 2.5 | 12/16 |
| 9–18 | +0.015 | 1.0 | — |

The signal is weak against a *good* public projection. The team's own model is 100% cold-start in Week 1 (§3.2 R9), so
the relevant test is against it. The catalog lists "best-ball ADP role belief" as never tested.

### 2.8 Kalshi fantasy markets exist and are free to read (checked 2026-09-25 against Kalshi's public API)
- **Markets:**
  - `KXNFLFFPTS`: "Matthew Stafford: Over 16 fantasy points", "LA Rams D/ST: Over 6.8 fantasy points", kickers.
  - `KXNFLFFPTSLADDER`: scalar contracts paying $0.01 per PPR point (capped at $1), so the price is the market mean.
  - `KXNFLRECYDS` and siblings: yardage ladders from 5+ to 135+ per player.
- **Scoring:** Sleeper full-PPR. It differs from DK in two ways:
  - no 100/300-yard bonuses;
  - −2 per fumble lost.
- **History:** receiving-yards ladders run from 2025-10-06 to 2026-02-08 (10,254 markets, median volume about 400
  contracts), which gives a timestamped calibration set.
- **Liquidity:** the scalar and fantasy markets are thin.
- **Access:** The Odds API's `us_ex` region lists Kalshi; whether it carries these NFL player markets is unverified.

---

## 3. The suggestions in detail

**Format.** Each item gives:
- **Mechanism** — why it should add points or finish;
- **Evidence** — what supports it;
- **Change** — exactly what to modify;
- **Test** — what must pass before entry, as the adoption track requires;
- **Kill** — the result that retires it;
- **Prior** — the closest item already in the ledgers, and why this is different.

**Code references.** Lab line numbers are for nfl2 `main` at `60b7109`. The money-path pin `9b341d77` is not in this
clone and differs in the four ways production's README lists (centring on `proj_points`, Doubtful exclusion,
`MAX_PER_GAME`, the passing-TD market).

### 3.1 Tier 1: small, can start this week or next

**R1. Enter a book selected on Sunday information ("pool on Saturday, select on Sunday").** *Class S; shadow from Week 4,
entry from Week 5; small cost.*
- **Mechanism.**
  - The entered Week-3 book is the Saturday 10:30 CT D12800 build. It knows Friday's injury report and Saturday
    morning's props.
  - The crowd builds until noon Sunday, with the 10:30 CT inactives, game-time decisions, weather and closing lines.
  - Selection is cheap and the pool is expensive. So keep the Saturday pool, but choose the book on Sunday's worlds.
- **Evidence.**
  - HANDOFF 2026-09-23 13:10: Saturday (15:30Z) and Sunday pre-lock (16:02Z) projections correlate **0.82**, mean |Δ|
    **1.07 pts**.
  - The ownership model tracks the crowd at 0.64 on Saturday projections vs 0.78 on Sunday projections. The field is
    built on the Sunday picture.
  - Late information is where the crowd's edge lives: drift ρ +0.096 in late games vs +0.035 early (§2.4); the external
    review found +0.275 in late games.
  - The dose the Saturday timing buys has no significant measured value above D3200:
    - D6400 was a near miss (PREREG-097);
    - at D12800 the 220+ supply doubled with no detectable K80 gain (PREREG-099, read second-hand from HANDOFF);
    - `lev` never produced a 220+ lineup in either live week.
- **Change.** A script that reuses the machinery `scripts/exposure_cap_book.py` already has (re-selection on a delivered
  pool from emitted world banks):
  1. Take the Saturday D12800 pool (`candidates.parquet`) and the Sunday T-70 D800 pool.
  2. Drop every lineup holding a player who is OUT/IR, Doubtful or inactive on the 11:0x pull.
  3. Re-run `dual_emax` on the **T-70 run's banks**, built on the post-inactives frame, to the same K and slices. Join
     the players on `dk_player_id`.
  4. Vet, emit, upload by ~11:15 CT as today.
  5. Optional: a Sunday boom batch on the post-inactives worlds for the news-affected games only.
  6. Keep the Saturday book as the fallback. Nothing else in the chain changes.
- **Test before entry.**
  - (a) Fixed-pool replay on Weeks 2–3, where a Sunday run exists: re-select each archived Saturday pool on the Sunday
    frame's banks and score
    both books on official points. Compare book mean vs field, book best, finish share above best and exposure IC
    (R10).
  - (b) Player level: MAE/CRPS of the Saturday vs Sunday served projections, Weeks 1–3.
  - (c) A paired, prelock-frozen paper shadow in Week 4 (class S), settled on Monday's scoreboard.
- **Kill.** Sunday re-selection is no better than the Saturday book on (a) and (c) over 3–4 weeks, *and* (b) shows no
  accuracy gain.
- **Prior.**
  - The T-70 rebuild exists, but at D800 and as a separate book. The Week-1 learned re-selection re-selected at the
    same information time.
  - No catalog item re-selects a high-dose pool on later information (checked against the 271 production and ~160
    lab items).

**R2. Follow the crowd's information and fade only its recency-chasing.** *Class C (predictor) + S (sleeve and fade);
predictor Week 4, sleeve preregistration Week 4–5; small cost.*
- **Mechanism (Benter's second stage, in DFS form).**
  - Benter's horse-racing model was worst exactly where it disagreed with the public. The fix was to combine the model
    with the public before computing any edge (Benter 1994, Tables 3–4).
  - The external review's §3.4 attributes PREREG-098's 9–44 loss to the same failure: P(top-N) selection against a
    modelled field chose against informed crowd picks. That is a hypothesis, testable on 098's books.
  - §2.4 shows the crowd has one systematic, measurable error: chasing last week. That component raises ownership
    1.3–1.6× with no outcome information. Fading it is *information-free leverage*: equal projection, less
    duplication, the same boom odds.
- **Evidence.** §2.4, 74 slates:
  - The recency component is uninformative in every season.
  - The rest of the crowd's excess ownership is informative in every season.
  - A recency-aware ownership model removes a −4 pp bias on last week's boomers out of sample.
  - The literature agrees: PFF (2020) found QB ownership chases prior-week passing TDs that don't repeat; Losak,
    Weinbach & Paul found the MLB field chasing a non-existent hot hand while winners faded it.
  - The web passes found no peer-reviewed NFL test, so §2.4 appears to be the first one.
- **Change.**
  1. **Predictor.** Add `surprise_prev` and its positive part to `scripts/ownership_sets.py`, which already carries the
     aligned lag features `own_prev`, `own_prev_l3` and `sal_delta`.
     - `surprise_prev` is last week's DK minus last week's projection: the point-in-time replay projection in training,
       the served projection live.
     - Check the train/serve alignment the way the lag-feature review did.
  2. **Decompose** each player's predicted ownership into a recency lift r_i: predicted ownership with the true
     surprise, minus predicted ownership with surprise set to 0.
  3. **Sleeve successor to L02 ("L05").** Keep L02's SLEEVE_L2 envelope: 25% of boom solves, ≤ 2 LOW-owned players,
     ≥ 1 top-15 chalk, salary ≥ $49,500. But:
     - define CHALK and LOW from the recency-aware predictor;
     - require the chalk anchor to be informed chalk (recency lift below the slate median);
     - prefer recency-deflated players for the LOW slots: last week's busts with intact projections, owned about 0.77×
       fair.
  4. **Fade (optional third arm).** The penalty applies to r_i only, never to total ownership.
- **Test.**
  - (a) **Definitive replication on our own data first.** Re-run `c2`–`c4` with the point-in-time replay projections
    (`slate_player_features`) and `contest_ownership` (72 weeks). This takes about an hour with the external review's
    `crowd_and_gap.py` scaffold.
  - (b) Walk-forward validation of the predictor (the `validate()` harness).
  - (c) PREREG-L05 on L02's substrate: 72 slate-banks, the real-ownership field sampler, finish share above best as
    primary.
  - (d) The Week 4–5 paper triple.
- **Kill.**
  - (a) shows the recency component predicting outcomes: the crowd is right about recency with our projection too.
  - Or L05 is not flip-eligible and its co-reported counts do not move.
- **Prior.**
  - L01/L02 chalk sleeves treat all chalk alike.
  - The naive fade (value-based `own_est`, never fired in 2026) fades noise.
  - The external review said "don't fade crowd information" without separating the parts.
  - The aligned lag model uses last week's *ownership*, not last week's *surprise*.
  - L02's own reopening rule names "a better chalk predictor" as the admissible new mechanism.

**R3. Give the simulator a real upper tail.** *Class C; Week 5; small–medium cost. Pair with R7 so selection does not
over-exploit it.*
- **Mechanism.**
  - Tournaments are won by lineups with one or two eruptions. Winners average 3.4 players at 30+; our book-best
    averages 1.8.
  - Every lab world caps each player at q99 + 0.25·(q99−q95): linear extrapolation from the top TabPFN quantile,
    `core/draw_shape.py:315-316`.
  - So per-world optima are almost never built around a 45–55-point game. Plausibly, the "luck" in each world spreads
    across cheap, low-owned players instead. That is one candidate reason the pool holds 3+ sub-5% players in 90% of
    lineups (winners: 20%).
- **Evidence.**
  - §2.5: 0.93 games of 40+ and 0.31 of 45+ per real slate; the tail above 35 is roughly exponential (mean excess
    about 5).
  - Lab SD-C: player upper tails too light.
  - LEDGER 108: WR ≥ 40 under-predicted 2×.
  - Real outcomes already exceed the simulator's q99 only 0.7% (incumbent) to 0.97% (hsim) of the time (briefing §6.1).
    So the frequency of exceedance is roughly right. What is wrong is **how far** exceedances go.
- **Change.**
  - Replace the linear piece above the top quantile with a generalized-Pareto tail. Keep P(X > q99) = 1%, the same
    rank structure, and the same body.
  - Set its scale from the q95–q99 spacing, and its shape ξ by position/role, fitted walk-forward on 2014–25 exceedances
    of the served q99.
  - Truncate at a physical cap (about 70 DK).
  - As a challenger for the body, try EasyUQ / isotonic distributional regression on the blended mean (Walz, Henzi,
    Ziegel & Gneiting, *SIAM Review* 2024), a tuning-free calibrated distribution.
- **Test.**
  - Outcome-blind first: count 40+ and 45+ games per simulated world against 0.93 and 0.31 per real slate.
  - Walk-forward exceedance calibration by position × projection band (the §2.5 table), scored with threshold-weighted
    CRPS at 30+ (Gneiting & Ranjan 2011; Allen, Ginsbourger & Ziegel 2023).
  - Then an L0x panel with the new tail in both generation and judging, co-reported with book-level PIT, since
    selection optimism is the risk.
- **Kill.**
  - Exceedance calibration gets worse.
  - Or book-level optimism rises (SD-A) with no finish gain.
- **Prior.**
  - EW widening (adopted), BIGPLAY/SHAPE_MIX (declined), breakout-mixture marginals (negative: they *replaced* draws),
    ALT_CEIL (retired).
  - None changes only the part above q99 while leaving P(>q99) fixed.

**R4. Clean the market inputs, and reconcile props with team totals.** *Class C; Week 5; medium cost.*
- **Mechanism.** For every priced player the props supply 55% of the served mean, through:
  - **2 books** (DraftKings, FanDuel) and 6 markets (`ingest/oddsapi_import.py:35-36, :215, :398`);
  - one flat 15% anytime-TD hold;
  - partial market sums treated as complete (`prop_market.py:315-319`);
  - props-or-nothing coverage (about 43% of live rows have ≥ 2 markets, and only 7.9% of players ≤ $4k are priced
    historically).

  The cheap slots that win GPPs are almost all unpriced and fall back to a model that is cold-start early in the season.
- **Change.**
  - (a) **8–10 US books at no extra credit cost.** The Odds API bills per market × region, and up to 10 bookmakers are
    one region (Odds API v4 docs, per the projection review). Take the median line and a de-vigged price; down-weight books that copy each other. There is no single
    sharp prop book: Establish The Run names Caesars and FanDuel as originators; Pinnacle and Circa post thin, late
    sheets.
  - (b) **De-vig chosen per market family** by walk-forward log loss (additive = Shin for two-way markets; power or a
    learned logit correction for one-sided TD and "X+" quotes). The constraint that matters is P(Y > line) = de-vigged
    P(over), not "line = mean". L03, running now, handles the median and bonus conversion; this adds the pricing side.
  - (c) **New: MinT reconciliation of the prop hierarchy** (Wickramasuriya, Athanasopoulos & Hyndman, *JASA* 2019).
    The team-level identities:
    - QB passing yards = Σ receivers' receiving yards (+ the unpriced remainder);
    - QB completions (a shadow market already collected) = Σ receptions;
    - QB passing TDs = Σ receiving TDs;
    - team offensive TDs ≈ f(implied team total) = Σ player TD rates.

    Base forecasts are the market where priced and the model everywhere. Reconciliation returns coherent means for
    priced players *and market-consistent remainders for unpriced ones*, weighted by the historical error covariance
    of each source.
  - (d) Where no market exists, add free public projections (RotoWire via Sleeper's endpoint and ESPN, both archived
    2018–25) as base forecasts. Their errors correlate 0.956 with each other, so they add little *for priced players*.
- **Test.** Walk-forward player-level MAE/CRPS on 2023–25 (prop history exists), split by priced and unpriced rows, then
  the L04 lineup gate.
- **Kill.** No CRPS gain on unpriced rows *and* no lineup-gate change.
- **Prior.**
  - B09 (Odds API expansion: collection only), B03 (dispersion null with only 2 books), B12 (median and bonus: L03).
  - C06 ("reconciliation identities" inside the *simulator*; only the TD ledger was ever tried).
  - Nothing reconciles the *market inputs* or gives unpriced players market-consistent means.

**R5. Capture Kalshi's fantasy-point, D/ST and yardage markets now.** *Class C; capture starts Week 3–4; grade from
Week 6; small cost.*
- **Mechanism.** These are the first markets priced *directly* on fantasy points:
  - the scalar ladders' price is the market **mean** of PPR points;
  - the threshold ladders give quantiles;
  - they cover **D/ST**, which is constant in every lab world today and has a rank skill of about 0.16;
  - weekly "fantasy leader" markets price the chance a player is the top scorer at his position, a direct boom
    probability.
- **Evidence.** §2.8.
  - Player-prop thresholds are liquid enough to read: a median of about 1,000 contracts in 2026, and up to about 170k
    on the top markets.
  - The fantasy-point and scalar markets are much thinner.
- **Change.**
  - Snapshot `KXNFLFFPTS`, `KXNFLFFPTSLADDER`, the yardage/TD/receptions ladders and the leader markets at the build
    times (Saturday build, T-70), append-only with timestamps. Use the public API and pace requests (it rate-limits
    with 429s).
  - Convert Sleeper PPR to DK by adding the 100/300 bonus expectations from the yardage ladders and correcting fumbles
    (−2 on Sleeper vs −1 on DK). Map D/ST scoring separately.
  - Use as a third, precision-weighted market component (by spread and volume), and as the check on L03's conversion:
    the scalar *is* a mean.
- **Test.** The weekly evidence record: MAE/CRPS vs served projections and vs the sportsbook-implied mean, on identical
  rows. Also use the 2025-10 → 2026-02 yardage-ladder archive as an outcome-timestamped calibration set for the
  yardage distribution shapes.
- **Kill.** After 4 graded weeks, it adds nothing beyond the sportsbook component on matched rows.
- **Prior.** B11 collected pick'em lines (operator-set medians, not priced markets) and never consumed them. Kalshi
  fantasy markets are new this season and appear nowhere in either repository.

### 3.2 Tier 2: principled rebuilds for October

**R6. Market-consistent worlds by per-game entropy pooling.** *Class C; Week 6+; medium cost.*
- **Mechanism.**
  - The current bridge from market to worlds is an additive shift of every draw (`live_week.py:113-130`). It ignores
    shape, gives stars impossible floors (external review §5.3), and moves each player without moving his teammates.
  - Production's rank-preserving *marginal* remap (09-22) changed little. What differs here is coherence: correlated
    teammates move together, toward per-slate market views.
  - Entropy pooling (Meucci, *Risk* 2008) instead *reweights* the worlds, using the smallest change in KL divergence
    that makes them agree with every market view:
    - each player's P(over line) and ladder rungs;
    - P(anytime TD);
    - team totals and spread.

    The joint structure carries each view to the correlated players, so a higher WR ceiling lifts his QB in the same
    worlds.
  - The ECB applied the same device to forecasts. Clark & Mertens (WP 3284, 2026) tilted simulated scenarios to
    published histograms, and the gains *spread to untargeted variables*. Matching medians alone fell short; medians
    plus the 15th/85th percentiles came close.
- **Why now.** Weight degeneracy is the known failure: the worlds needed grow exponentially with the number of views.
  §2.1 shows games are independent, so the problem **factorises by game**:
  - reweight each game's worlds against that game's views only;
  - resample each game to equal weights;
  - recombine games independently into slate worlds.
- **Change.**
  - Solve the dual (one variable per view) with soft views, where confidence is learned on past seasons.
  - Gate on effective sample size (Kish, or Meucci's effective number of scenarios, per game).
  - If a gate fails, adjust the simulator's parameters and redraw rather than force the weights (Montes-Galdón et al.,
    ECB WP 3200).
  - Select on one set of reweighted worlds and score on fresh draws.
  - Combine model and market quantiles by *quantile averaging* with CRPS-fitted weights (Lichtendahl, Grushka-Cockayne &
    Winkler 2013), never by averaging probabilities, which over-disperses (Gneiting & Ranjan 2013).
- **Test.**
  - Threshold calibration and PIT on 2023–25 props.
  - Joint calibration with the energy and variogram scores already built (catalog C30).
  - Fixed-pool re-selection, then an L0x panel.
- **Kill.** No calibration gain at the final consumer, or ESS gates fail on most games.
- **Prior.**
  - PREREG-101 (reweighting worlds to *historical tail frequencies*; withdrawn over selection optimism).
  - C14 (ECC / minimum-KL tilting toward *pooled* dependence; failed the screen).
  - T1 (market-implied dependence; feasibility-gated).
  - This instead targets *per-slate forward-looking market views*, per game, with ESS gates and fresh-draw scoring.

**R7. A third, empirical critic and disagreement-aware selection (the optimizer's curse).** *Class S; Week 6+ panel;
medium cost.*
- **Mechanism.**
  - Picking the best-scoring candidates under a model systematically picks the model's errors. Smith & Winkler
    (*Management Science* 2006) show the best of 10 equal options with N(0,1) errors disappoints by 1.54σ.
  - The cross-domain pass simulated DFS-like selection (synthetic data, not ours): naive top-150-of-10,000 overstated
    tail events **4.6×** and drew
    67% of its picks from the noisiest third. Shrink-then-select delivered +25% true tail events with a nearly
    calibrated estimate.
  - The programme's own numbers match: book tails 1.5–5× optimistic (SD-A), the lab's lesson 5, and Haugh & Singal's
    "bias that results from optimizing within a model".
  - The one selection change that passed added a second *different* critic (DUAL_EMAX +1.39).
- **Change.**
  - (a) A **third critic bank** from a genuinely different law. It carries the real joint structure within games (QB
    hub, receiver competition, script coupling, in-game exits, TD clustering) without a parametric copula. Games are
    independent (§2.1). The empirical residual bootstrap:
    - For each historical team-game (2012–25), compute each role's standardized residual against our point-in-time
      projection: QB, RB1–2, WR1–3, TE1, DST, for both teams.
    - For each current game, draw a historical game from the same total and spread band.
    - Apply its residual vector: X_i = μ_i + σ_i·z_role(i).
  - (b) **Disagreement-aware greedy.** Replace each candidate's marginal E[max] gain with its mean across critics minus
    κ × its spread across critics, or with the across-critic minimum (a distributionally robust max; Liu, Liu & Teo,
    *POM* 2023).
- **Test.** An L0x panel (72 slate-banks) with arms DUAL (control), TRIAD and TRIAD-skeptical, and the finish endpoint
  primary.
- **Kill.** TRIAD ≤ DUAL on both proxy and finish.
- **Prior.**
  - C31 (factor-stress robust selection: null; the TRI *supply* parliament: negative).
  - Lab idea #5 ("a third critic, never tested").
  - Memo ideas "skeptical book utility" and "proposer–critic pessimism" (never built).
  - This supplies a concrete, empirically anchored third law and a named selection rule.

**R8. Calibrate the *generation* law's dependence to a public target card.** *Class C; Week 6+; medium cost.*
- **Mechanism.**
  - Every candidate comes from the incumbent law. Its WR1–WR2 correlation is +0.277 against +0.016 real (§2.3), which
    over-supplies double-receiver stacks.
  - Its cross-team coupling runs through volume, which is negative in reality (§2.2).
  - Its TDs are independent Poisson draws, not tied between QB and receiver (`simulate.py:419-429`).
  - hsim gets much of this right (Dirichlet shares, QB = Σ receiving), but it only *judges*.
- **Change.**
  - Target the card in §2.2–2.3 directly: share competition within a team, cross-team coupling through script
    (`SCRIPT_FEEDBACK`, built and off; the hybrid factor C02), and a QB–receiver TD link.
  - Use the card, with its intervals, as an **outcome-free gate** before any panel.
- **Test.** The card gate, then an L0x panel.
- **Kill.** The card cannot be met without breaking the marginals, or the panel is flat.
- **Prior.**
  - The dependence rewrites that failed (Schaake, learned templates, coherent member worlds, A2a).
  - Those replaced the law or failed shape gates. This is targeted parameter correction against measured targets with
    CIs, a gate the ledger never had in one place.

**R9. Cross-season player state for the early weeks.** *Class C; for Weeks 4–6 of this season and Weeks 1–5 of 2027;
medium cost.*
- **Mechanism.** Feature windows reset every season: `PARTITION BY gsis_id, season` in
  `sql/features/014_player_week_usage.sql:138-140`, and the same in 015/015a/017a. So Week 1 is 100% cold-start, and
  55% of Week-2 skill rows were cold-start this year.
- **Change.**
  - A dynamic Bayesian usage state: a Kalman or beta-binomial filter on target share, carry share and route
    participation.
  - Variance is inflated at season boundaries and on team, QB or coordinator changes, with changepoint detection for
    role shifts. DARKO's Kalman approach in the NBA is the practitioner template.
  - Priors come from last season, preseason ADP (§2.7; free; 2022–25 checked) and depth charts.
- **Test.** Walk-forward MAE and CRPS by week of season, 2019–25. The gain must concentrate in Weeks 1–5.
- **Prior.**
  - H1/A12 (proposed in the 09-21 audit; not done).
  - Draft-capital priors (null; a much weaker signal).
  - Best-ball ADP role belief (never tested).

### 3.3 Tier 3: measure faster, and the money side

**R10. Measure edge weekly with information coefficients (Grinold–Kahn).** *Evaluation; from Week-3 settlement; small
cost.*
- **Why.** A book-max endpoint is one draw a week. The cross-domain pass estimates that detecting a 2× edge from
  first-place finishes takes about 4,000 weeks.
- **The identity.** Book mean − field mean = Σᵢ aᵢ·pᵢ, where aᵢ = our exposure − field ownership (the "active weight")
  and pᵢ = realized points. That is exactly the scoreboard production already built.
- **The weekly statistics.**
  - **IC:** the Spearman correlation of aᵢ with pᵢ − μᵢ over about 150–250 players. Its standard error is about 0.07 a
    week, so an IC of 0.10 reaches t ≈ 2.6 in about 6 weeks (the cross-domain pass's estimate, allowing for week-to-week
    variation).
  - **Projection IC:** of our own tilts against the crowd-implied value.
  - **Transfer coefficient:** the correlation between the exposures we *wanted* and the ones the constraints, dose and
    selector *delivered*.
  - **Active share.**
- **What it gives.** Every lever becomes a "view" whose IC can be graded weekly: recency fades, chalk cores, a Sunday
  re-selection. Grinold's fundamental law (IR ≈ IC·√breadth) says where to invest: information (IC) or expression (TC).
- **Prior.** The C5 tilt analysis is one IC computation. This makes it the standing weekly metric, with its
  decomposition.

**R11. The late window, played on news and field state rather than score-chasing.** *Class S/E; Week 4 shadow; small
cost.*
- **Mechanism.** Two cheap parts:
  - Re-project late-game players at about 13:40 CT, after the late inactives, and move lineups *into* the beneficiaries
    (external review §6.3).
  - For lineups still in contention, choose late swaps to maximise P(top-k | the field's revealed state), not our own
    pace.
- **What DraftKings shows.** DK hides opponents' players whose games have not started (help centre, updated about June
  2026), so late-game ownership is **not** revealed at noon. But the full contest CSV can be downloaded during the
  contest, and the early parts of opponents' lineups are visible. Opponents' remaining salary and open slots narrow
  their hidden picks, like reading a poker range; this is unverified.
- **Zero-cost part now.** Flex the latest-starting eligible player at upload, to keep swap options open.
- **Evidence.**
  - Drift ρ +0.096 late vs +0.035 early (§2.4).
  - Haugh & Singal value knowing realized ownership at about +20% in top-heavy contests.
  - Every closed late-swap test chased *scores* (009 invalid; 023 −1.23; 024 −0.42; swap220 +0.75).
- **Test.**
  - Sunday check: what the live CSV exposes before the 3:05 CT kickoffs.
  - A paper shadow of the news re-projection for 3–4 weeks.
  - Replay of the field-state swap on the two archived full fields, with late players masked.
- **Prior.** H06, H07, H08 and H09 in the catalog were all proposed and never run.

**R12. Duplication-aware payoff, only when chalk cores enter the book.** *Class S; alongside R2.*
- **Why now, not before.** Add18 found duplication risk around zero for today's books, which are full of sub-5%
  players. A chalk-core sleeve changes that.
- **The cases.**
  - The 2022 W17 Millionaire (about 170k entries) was split two ways with only 77% total ownership.
  - A Showdown Milly winner was duplicated 231 times (vendor anecdote).
- **Change.** Score a candidate's contribution in each world as its prize share, not its points. With D ~ Poisson(λ)
  copies, the expected share of first is (1−e^{−λ})/λ, and λ comes from the IPF field sampler, never from a product of
  ownerships, which undercounts stacked lineups. Add this to R2's L05 arms.
- **Prior.** G08 (never).

**R13. Contest economics.** *Money; operator's decision.*
- **Rake** (computed from the posted prizes):
  - the $5 Week-1 Millionaire: **15.9%** ($3.5M paid on 832,342 × $5);
  - the $20 Week-2 Millionaire: **13.2%**.
- **Recommendations.**
  - Capture payout tables (J11) so ROI is computable in the warehouse.
  - Measure each contest's heavy-user share from the standings (G12).
  - Hunter et al. made money only where their mean beat the field's.
  - A vendor figure from *bracket pools* (PoolGenius; unverified) puts the edge multiplier at 3.7× in 100–250-entry
    pools against 1.3× at 10,000+. With edge, smaller fields multiply it; without edge they only return rake more slowly.

### 3.4 Tier 4: exploratory, cheap probes or long shots

- **R14. An LLM news agent: fact extractor, not forecaster.**
  - **Evidence.**
    - Prediction-market arenas show markets overtaking LLMs as resolution nears (Prophet Arena).
    - Web access improves LLM Brier scores by about 0.02.
    - Date filters leak post-cutoff news in up to 71% of questions (El Lahib et al. 2026).
    - So the value is not forecasting. It is *structured facts the markets have not priced*: role and snap statements
      for cheap unpriced players, game-time-decision leanings, weather changes.
  - **Design.**
    - Saturday 18:00 and Sunday 10:15 CT runs.
    - Output: a table of (player, claim, source URL, timestamp, direction, confidence).
    - Strictly prospective and append-only.
    - Graded weekly for 4–6 weeks on whether it predicts residuals against the served projection, before any money use.
  - **Prior.** K02: scaffolded, "not a 2026 item". This reduces it to a logging job.
- **R15. In-game exits in the worlds (§2.6).**
  - With probability about 5% (RB) and about 8% (QB), the lead leaves early and his share transfers to his backup.
  - Second-order for lineups. It complements catalog A28: QB early-exit busts identified, and TE zero mass at 0.2%
    simulated vs 7.7% real.
- **R16. Public betting splits as an ownership feature.**
  - DK Network publishes per-game prop splits (e.g. ATL–GB, 72–82% on the overs).
  - Hypothesis only: public betting attention may predict public DFS ownership, especially recency chalk.
- **R17. An inverse-optimisation field model** (G07: "data-gated; the data now exists").
  - Fit a random-utility model to the 1.3M captured lineups.
  - This recovers the crowd's implied values *and* stacking beliefs, and extends §2.4 from marginals to combinations.
- **R18. Wind and referees.**
  - Historical *forecast* weather is available (Open-Meteo Historical Forecast / Previous Runs APIs), which corrects
    catalog J13's "impossible for weather".
  - Observed wind of 15–19 mph ran 2.3 ± 1.0 points under closing totals (2015–25); §2.1 gives −1.6 at 15–20 mph.
  - Referee crews show nothing (season-to-season r −0.09). Test forecast wind as a passing-volume feature only.
- **R19. Kalshi as a hedge.**
  - A concentrated player exposure can be partly hedged on Kalshi. This lowers variance, not expected value, and costs
    the spread.
  - Listed only because it is genuinely new. Jurisdiction and terms are the operator's to check.

---

## 4. What this research says *not* to do

- **Don't add a slate-wide scoring factor.** Real games are independent within a week (§2.1). Look at game-level
  variance, pool concentration and player bias instead.
- **Don't drop bring-backs because scoreboard points are independent.** Fantasy output *is* coupled across opponents
  (+0.21, §2.2). Change *how* the law couples them (script, not volume) instead.
- **Don't fade total ownership.** The crowd is informed (§2.4). Fade only the recency component (R2).
- **Don't expect a pre-lock crowd blend to move the mean much** (+0.002 to +0.010 r). Its value is leverage and late
  information.
- **Don't stack more public projections** for priced players: their errors correlate 0.956 with each other.
- **Don't scrape same-game-parlay prices.** There is no API, it breaches terms, and the margin masks the correlation.
- **Don't reintroduce P(top-N) finish selection** before the information gap is closed, and then only in a set-aware,
  smooth form: Haugh & Singal's covariance-with-the-field's-top term.
- **Don't raise the dose again while the entry is built on Saturday.** No significant gain is measured above D3200, and the
  cost is a day of information.
- **Don't treat an LLM as a forecaster** or trust its date filters (R14).

---

## 5. Integrity items noticed in passing (please verify; none was acted on)

1. **Possible empty 2026 salary spine.**
   - `dk_salaries.week` is NULL on all 900,812 rows (HANDOFF, laptop check, `reports/2026-09-22-laptop-doubtful-verification.md`),
     yet `sql/features/001a_dk_salary_week.sql:37` keeps only rows where `week IS NOT NULL`.
   - For 2026 that live table is the only source (the other branch is `dk_salaries_historical`).
   - If both hold, `salary_delta_wow` is null live, and 2026 usage and training rows are missing. The Week-2 audit's "45%
     with one game of history" argues against it.
   - Check: `SELECT season, week, COUNT(*) FROM nfl_features.dk_salary_week WHERE season=2026 GROUP BY 1,2`.
2. **The DST coefficient.** `COEF_L16` is applied to a last-4 average (`inference/dst_projections.py:31-35, :157-165`).
   Check what it was fitted on.
3. **The anytime-TD feed.** It has no outcome-name filter; confirm it carries only the "Yes" side.
4. **hsim's Vegas lines.** hsim reads them from a benchmark schedule frozen on 2026-08-27 (`hsim/world.py:57-64`).
   Confirm at the pin that live lines reach it; a game with missing lines would score a whole team at zero.
5. **The hsim DST.** Points allowed are reduced by the DST's own TDs (`hsim/world.py:173-180`), which is incoherent.
6. **Declared vs live policy.** The live `--max-per-game 4` is a lab flag with no counterpart in `production_policy.py`, so
   the manifest test cannot see it. This is the laptop's cross-repo audit point (§A); the same holds for any lab-side lever.
7. **Stale defect register.** `reports/OPEN-DEFECTS.md` was last reviewed 09-18. Defects 10–29 live in §9 of the Week-2
   operating handoff.
8. **The TabPFN context.** It is `all-prior-nonnull-labels` (`scripts/tabpfn_gen/gen.py:195, :281`, manifest at `:320`), which
   includes the inactive zeros present since the 2022 panel break, while the mean model is E[points | played]. Confirm
   that the shape and the mean are meant to be different estimands (the projection review's H7).

---

## 6. A sequencing proposal (the operator decides)

| when | work | owner (suggested) |
|---|---|---|
| Week 3 settlement (Mon 09-28) | Add the IC/TC lines to the scoreboard (R10). Run the R1(a) fixed-pool replay on Weeks 2–3 and the R2(a) replication on our own point-in-time data | laptop |
| Week 4 build | R1 paper shadow. R5 Kalshi capture begins (append-only). R11 flex-latest at upload (zero cost). Sunday check of what the live CSV shows before 3:05 CT | laptop + operator |
| Week 4–5 | R2 predictor walk-forward, then PREREG-L05 frozen and run (Mon–Fri only). R4(a)(b) book widening and de-vig on history. R3 outcome-blind eruption count | laptop |
| Week 5 | Decide R1 for entry (class S decision record). R4(c) MinT player-level walk-forward. R3 player-level calibration | operator; laptop |
| Weeks 6–8 | R6 entropy pooling (per game). R7 third critic (TRIAD panel). R8 dependence card gate. R14 LLM log begins. R9 planned for 2027 | laptop / lab successor |

Nothing above needs a Cloud Run job to be created. All of it runs on the laptop or reuses registered lanes, and no
panel runs from Saturday 10:30 to Sunday 12:00 CT (move document L7).

---

## Appendix A: novelty check (each suggestion against the closest item already tried or proposed)

IDs are from the lab `LEDGER.md` / `PREREG-*`, production's system-study addenda ("SS-A"), and the idea catalogs compiled
for this review (production A–L; lab categories). "Never" means proposed somewhere with no result anywhere.

| suggestion | closest prior item(s) | status of prior | what is different here |
|---|---|---|---|
| R1 Sunday re-selection | T-70 D800 rebuild; Week-1 learned re-selection; `exposure_cap_book.py` | rebuild at low dose; re-selection only at the same information time | re-select the *high-dose* pool on *post-inactives* banks |
| R2 recency split of ownership | naive fade (SS-A80; never fired in 2026); L01/L02 chalk sleeves; aligned `own_prev` lag features; external review Finding B | fade inert; L02 a near miss; lag features accuracy-only | separates the uninformative (recency) part of ownership from the informative rest, on 74 slates; defines *which* chalk to follow or fade |
| R3 generalized-Pareto tail | EW widening (SS-A40); BIGPLAY/SHAPE_MIX; breakout mixture (LEDGER 007); ALT_CEIL (SS-A22/57); SD-C | adopted / declined / negative / retired / measured | changes only the region above q99, keeps P(>q99) at 1%, fitted to the size of real exceedances |
| R4 books, de-vig, MinT | B03, B09, B12, B13; C06 identities; props-or-nothing | 2-book null; collection only; L03 running; TD de-vig small; only the TD ledger was tried | wider consensus at no extra credit cost; per-family de-vig; *market-input* reconciliation that yields market-consistent means for unpriced players |
| R5 Kalshi | B11 pick'em (collected, unconsumed); B16 overtime market (never) | — | priced fantasy-point means, D/ST and boom-probability ("leader") markets, new this season |
| R6 per-game entropy pooling | PREREG-101; C14 minimum-KL; T1 market dependence | withdrawn; failed screen; feasibility-gated | forward-looking market views, factorised by game (licensed by §2.1), ESS gates, fresh-draw scoring |
| R7 third critic, skeptical greedy | DUAL_EMAX (adopted); C31 robust / parliament; "skeptical utility" memo | adopted; null/negative as *supply*; never built | an empirical-bootstrap law used *as a critic*, plus a named disagreement penalty |
| R8 dependence target card | LEDGER 003 co-exceedance; A2a; Schaake; learned templates; C02/C03 | measured / failed shape gate / closed / never | one card with CIs conditioned on a market-informed projection; script-not-volume mechanism (§2.2) |
| R9 cross-season state | H1/A12; draft-capital priors (SS-A21); best-ball ADP (never) | not done / null / never | dynamic state model plus ADP evidence (§2.7) |
| R10 IC/TC accounting | C5 tilt analysis; book-vs-field scoreboard | one-off / built | a standing weekly metric with the fundamental-law decomposition |
| R11 news and field-state late swap | 009, 023, 024; swap220; H05; H06–H09 | invalid / negative / closed / narrow / never | news-driven and field-state objective, not score-chasing; flex-latest at zero cost |
| R12 duplication payoff | G08; Add18 (duplication ≈ 0) | never; true for today's books | conditional on R2's chalk cores; Poisson prize share from the IPF field |
| R13 contest economics | L03, L04, L15; J11 | recommended / proposed | computed rake by contest; edge-multiplier framing |
| R14 LLM facts log | K01 persona field; K02 news-to-prior | offline pass; scaffold | extractor-only, prospective, graded before use; grounded in 2025–26 LLM-forecasting evidence |
| R15 in-game exits | A28 (QB early-exit busts; TE zero mass) | identified, unfixed | RB/backup joint structure quantified (§2.6) |
| R16 betting splits | — | — | new signal for the ownership model (hypothesis) |
| R17 inverse-optimisation field | G07 | never (data-gated; data exists now) | — |
| R18 forecast wind | A31; J13 "historical weather forecasts impossible" | never; incorrect | archived forecasts exist (Open-Meteo) |
| R19 Kalshi hedge | — | — | new; risk management only |

---

## Appendix B: sources

**DFS portfolio literature**
- Hunter, Vielma & Zaman, "Picking Winners in Daily Fantasy Sports Using Integer Programming" (arXiv
  [1604.01455](https://arxiv.org/abs/1604.01455)). Profit only in contests where the lineups' mean beat the field's.
- Haugh & Singal, "How to Play Fantasy Sports Strategically (and Win)", *Management Science* 67(1):72–92 (2021).
  - Dirichlet-multinomial opponent model.
  - The objective penalises covariance with the field's top score.
  - Realized ownership worth about +20% in top-heavy contests.
- Bergman, Cardonha, Imbrogno & Lozano, *INFORMS J. Computing* 35(2) (2023): exact E[max] for two entries.
- Decary et al. (arXiv [2407.13438](https://arxiv.org/abs/2407.13438), 2024): submodular E[max]; 100 entries gave 2.2% of a
  12,605-entry pool.
- Brill, Wyner & Barnett, *Entropy* 26 (2024) (arXiv [2308.14339](https://arxiv.org/abs/2308.14339)): optimal entry
  entropy rises with the number of entries.
- Liu, Liu & Teo, *POM* 32(9):2864–84 (2023): distributionally robust small-set selection.
- DraftKings help: [why opponents' players are hidden](https://help.draftkings.com/hc/en-us/articles/4405230074515-Why-are-some-of-my-opponent-s-players-hidden-US).
- Establish The Run: [large/medium/small-field ownership](https://establishtherun.com/draftkings-projected-ownership-large-medium-small-field/).

**Cross-domain**
- Benter, "Computer Based Horse Race Handicapping and Wagering Systems" (1994;
  [PDF](https://gwern.net/doc/statistics/decision/1994-benter.pdf)).
  - Pseudo-R²: public 0.1218, model 0.1245, combined **0.1396**.
  - The model's bias lies where it disagrees with the public.
- Smith & Winkler, "The Optimizer's Curse", *Management Science* 52(3):311–322 (2006).
- Grinold, "The fundamental law of active management", *JPM* 15(3) (1989); Grinold & Kahn, *Active Portfolio Management*.
- Baron, Mellers, Tetlock et al. (2014), extremizing aggregated forecasts; temperature scaling (Guo et al., arXiv
  1706.04599).
- Aldous, "A Prediction Tournament Paradox", *American Statistician* 75(3) (2021).
- Moskowitz, "Asset Pricing and Sports Betting", *J. Finance* 76(6) (2021).
- Ownership chasing:
  - PFF (Brown, 2020) on [QB ownership drivers](https://www.pff.com/news/fantasy-football-identifying-the-stats-that-drive-dfs-ownership-at-the-quarterback-position);
    not peer-reviewed.
  - Losak, Weinbach & Paul, *J. Sports Economics* (2023) and *American Behavioral Scientist* (2024): MLB DFS hot-hand
    chasing, faded by winning lineups.

**Distributions, markets, evaluation**
- Meucci, "Fully Flexible Views", *Risk* 21(10) (2008; arXiv [1012.2848](https://arxiv.org/abs/1012.2848)).
- ECB papers:
  - Clark & Mertens, ECB WP 3284 (2026), [entropic tilting](https://www.ecb.europa.eu/pub/pdf/scpwps/ecb.wp3284~c350fd075f.en.pdf);
  - Montes-Galdón, Paredes & Wolf, ECB WP 3200 (2026), [robust tilting](https://www.ecb.europa.eu/pub/pdf/scpwps/ecb.wp3200~11eaa17194.en.pdf).
- Wickramasuriya, Athanasopoulos & Hyndman, "Optimal forecast reconciliation … through trace minimization", *JASA*
  114(526) (2019).
- Combining and scoring predictive distributions:
  - Lichtendahl, Grushka-Cockayne & Winkler, *Management Science* 59(7) (2013): quantile averaging;
  - Gneiting & Ranjan, *EJS* (2013): linear pools over-disperse;
  - Gneiting & Ranjan, *JBES* 29(3) (2011): threshold-weighted CRPS;
  - Allen, Ginsbourger & Ziegel, *SIAM/ASA JUQ* 11(3) (2023).
- Walz, Henzi, Ziegel & Gneiting, "EasyUQ", *SIAM Review* 66(1) (2024; arXiv [2212.08376](https://arxiv.org/abs/2212.08376)).
- LLM forecasting:
  - Prophet Arena ([arXiv 2510.17638](https://arxiv.org/html/2510.17638)): markets overtake LLMs near resolution;
  - El Lahib et al. ([arXiv 2602.00758](https://arxiv.org/abs/2602.00758)): date-filter leakage.
- Kalshi public API (`api.elections.kalshi.com/trade-api/v2`; series `KXNFLFFPTS`, `KXNFLFFPTSLADDER`, `KXNFLRECYDS`).
- Sleeper projections (`api.sleeper.com/projections/nfl/{season}/{week}`; undocumented).
- Open-Meteo Historical Forecast and Previous Runs APIs.
- DK Network [prop betting splits](https://dknetwork.draftkings.com/2026/09/24/falcons-packers-player-prop-bet-splits-september-24-2026/).

**Verification tags.** The web passes tagged every claim as fetched, abstract-only or unverified. Vendor figures quoted
here are unverified: PoolGenius multiples, the 231-duplicate anecdote, and the SGP holds.

---

## Appendix C: reproduction and data handling

- **Scripts:** `reports/lab-handoffs/2026-09-25-outside-the-box/`, with a README giving the commands.
  - `fetch_public_inputs.py OUT` downloads:
    - nflverse schedules, player stats and snap counts;
    - FFC ADP;
    - 74 LineStar periods, at 1.2 s spacing as in `linestar_backfill.py`.

    It writes them to a directory *outside* the repository.
  - The analysis scripts run from that directory and print the tables in §2.
- **Third-party data:** LineStar and FFC data are never committed; only aggregates appear here. The historical LineStar
  pull happened in this remote session, not through the production warehouse.
- **Definitive re-runs** use our own point-in-time replay projections and `contest_ownership` in BigQuery:
  - §2.4 → R2 test (a);
  - §2.3 → rerun with the served projection for 2026.
