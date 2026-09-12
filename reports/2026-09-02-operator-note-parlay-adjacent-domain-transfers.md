# Operator-side note: what parlay-adjacent domains know that we can use

**Date:** 2026-09-02
**Author:** operator-side assistant (outside review; neither a production nor a lab document; no queue
authority)
**Audience:** operator, lab experiment team, production implementation team
**Purpose:** the operator asked: a DFS lineup is a set of individual outcomes combined into one ticket,
somewhat like a parlay — what do *other* domains with that structure (wagering and not) do to score or win,
and what transfers? Three parallel literature/practitioner sweeps were run (betting markets; contest pools
and power-law portfolios; quantitative best-of-batch methods outside gambling). This note reports the
findings deduplicated against `LEDGER.md`, the untried-ideas closure inventory, and the knowledge frontier,
ranked by transfer value. Standing posture unchanged: nothing here interrupts 088/089/085, historical panels
remain screening data, prospective 2026 settlement is the adoption authority.

**Domains examined:** same-game parlays and correlated betting; horse-racing exotics (Pick 6 / Benter);
lottery and parimutuel pool economics; March Madness bracket pools (rich academic literature); NFL survivor
pools; Kaggle final-submission strategy; venture capital power-law portfolios; poker MTT/ICM; batch Bayesian
optimization; dispersion trading / implied correlation; rainbow (best-of) options; catastrophe reinsurance;
speedrun reset theory; oil-exploration prospect portfolios.

---

## 1. The seven transplants worth acting on (ranked)

### T1. Market-implied dependence targets — the parlay market already prices our co-boom problem

**What the domains know.** Sportsbooks price same-game parlays by *joint simulation* (DraftKings
engineering blog; the SportCast/OpenBet BetBuilder engine) and charge a measurable "correlation tax" (SGP
hold ~15% vs 4–5% on singles). Practitioners routinely **extract the implied dependence**: de-vig each leg,
de-vig the quoted SGP, and the gap between the quoted joint and the independence product is the correlation
the book is charging (documented practitioner practice; e.g. Wizard of Odds "The Mathematics of
Correlation"; OddsIndex; PropsBot tooling). Separately, options desks compute **implied equicorrelation** by
reconciling basket variance with component variances — ρ_imp = (σ_I² − Σw_i²σ_i²)/(2Σ_{i<j}w_i w_j σ_i σ_j),
the CBOE COR3M construction — and trade the implied-vs-realized gap (documented correlation risk premium:
implied ~39–47% vs realized ~29–36% in equities).

**Transfer.** The dependence-repair ladder's weakest point — production flagged it — is sparse calibration
targets (~89 slates of rare co-exceedance events). The market offers two dense, pre-lock, external sources:

- **Reconciliation route (existing data):** the frozen `raw_prop_lines` table already holds 371,997 rows,
  60.8% alternate-ladder, plus hourly `odds_snapshots` with game/team totals. Applying the COR3M identity to
  *team-total ladder variance vs the sum of player-prop ladder variances* yields a per-team, per-week
  market-implied intra-team dependence read — no new capture required. (It is a reconciliation constraint on
  fantasy-relevant co-movement, not an exact copula; label it that way.)
- **Direct route (new capture):** quoting two-leg SGP combos (QB yards × WR yards, player × team total)
  through the existing odds infrastructure and de-vigging gives pair-level implied dependence exactly where
  exp 003/003-recal measured the deficit.

**Why it clears the bar.** This is a *market-based genuinely new pre-lock signal* — the preregistered
reopening class — and it converts the ladder's noisy historical targets into weekly market-sourced ones.
First step is instrument-only: compute implied dependence walk-forward, compare against the incumbent law's
co-exceedance and against realized, and report the three-way gap as a standing meter (the dispersion-desk
discipline). No outcome is opened. **Status: new; feeds 089/regime-overlay targets directly.**

### T2. CLV-style grading — a process instrument ~100× more sample-efficient than weekly outcomes

**What the domain knows.** Sharp bettors grade *process* by closing line value, not results: per-bet CLV has
SD ≈ 0.1 vs ≈ 1.0 for outcome P&L, so skill separates in ~50 bets instead of thousands; Buchdahl validated
expected-from-CLV 4.0% vs realized 3.4% across ~20,000 bets. Known caveat: CLV only grades information the
market eventually incorporates — a genuine originator with private signal shows no CLV.

**Transfer.** The program's binding statistical constraint is 72–107 weekly outcomes per season of panel.
Grading **lock-time beliefs against closing lines** — marginal projections vs closing prop ladders, and
(with T1) pair-dependence beliefs vs closing implied dependence — gives a weekly, player-level calibration
instrument with orders of magnitude more observations than slate outcomes. The hourly `odds_snapshots` path
already makes closes derivable. This complements `div_shadow` (which collects divergence but grades against
outcomes). Use it as one instrument among several, never a kill-gate, because of the originator caveat.
**Status: new instrument; zero outcome risk; cheap.**

### T3. The √(1−ρ) law and a book-level implied-correlation receipt

**What the domains know.** For best-of options (Stulz 1982 / Johnson 1987), value is monotonically
*decreasing* in pairwise correlation among basket components. Exact Gaussian form: for n equicorrelated
assets, E[max] ≈ μ + σ·√(1−ρ)·E[max of n iid N(0,1)] — **the entire extreme-value growth term scales by
√(1−ρ)**. Desk rule: adding a component highly correlated with an existing one adds almost nothing to the
max.

**Transfer.** Two standing receipts, no experiment:

- Report each selected book's *effective inter-entry correlation* and its σ√(1−ρ̄) decomposition under the
  law — how much max-premium the book actually bought, and where adding an entry stopped paying. This turns
  overlap intuitions into a priced quantity and gives 088/retention arms a mechanism readout.
- Combine with T1 at the book level: implied (market) vs simulated vs realized inter-entry correlation —
  the dispersion-trading triad — as the standing alarm on the joint law.

Also from reinsurance: report the **full exceedance curve of the simulated book-max** per slate (their OEP
curve of the per-year maximum), not only its mean/threshold counts — cheap, and it is the shape 088-style
reads argue about. **Status: new receipts; measurement only.**

### T4. Selection robustness from the batch-optimization literature: sample and bag, don't just argmax

**What the domain knows.** In batch Bayesian optimization (the literal expected-best-of-batch acquisition
problem), greedy marginal selection with a submodularity guarantee is near-optimal — joint optimization ties
greedy-with-conditioning within noise (Hartmann-6D benchmark). The measured wins come from *robustness*
devices, not cleverer argmaxes: sampling batches from a quality×diversity determinantal distribution hedges
surrogate miscalibration (Kathuria et al., NeurIPS 2016); Thompson batches draw one *model perturbation* per
slot and let each perturbation pick its favorite (Kandasamy 2018; Hernández-Lobato 2017); Caruana-style
ensemble selection fixes selection-set overfitting by **bagging the selection process itself** (ICML 2004).

**Transfer, deduplicated.** With explicit 10k-world matrices, exact greedy marginal E[max] is already
computable — so the fantasy/qEI machinery per se adds little (and confirms the DEMAX greedy is the right
shape; see §2). What transfers is the robustness pair, both aimed at measured failure modes:

- **Bagged selection:** run the frozen selector on bootstrap resamples of the worlds and pick the book by
  aggregate membership. The program's own reads keep dying to bank luck at ±1 effect sizes (VX14, AB,
  BX120; PREREG-049→052); bagging the selection is the direct, outcome-free countermeasure, and composes
  with the already-suggested stratified/antithetic banks (untried-ideas 1.6).
- **Thompson-from-law-uncertainty:** allocate some book slots by drawing a *dependence-knob perturbation*
  per slot (from the walk-forward-calibrated knob posterior of the repair ladder) and letting each draw
  select its slots. Diversity then comes from model uncertainty — the thing actually broken — rather than
  from outcome-space coverage. Distinct from the closed ensemble member-sample worlds arm (Addendum 112: a
  single alternative world mode for the whole book) and from closed plain-DPP descriptors.

**Status: new bounded selector-robustness arms; run only per the ±1 discipline (cheap screens, after the
dependence ladder gives the perturbation posterior).**

### T5. Spine-contrarian book structure: deviate where the crowd is chalky AND the payoff is top-weighted

**What the domains know (this is the most cross-confirmed finding of the sweep).**

- Metrick (1996, ~24k real entries): favorites are systematically overbacked; contrarian value scales with
  pool size.
- Clair & Letscher (OR 2007): optimizing EV *against an opponent-behavior model* beats optimizing expected
  score "often by orders of magnitude," and the crowd misallocates by picking upsets early and going
  conservative at the champion slot — so the right deviation is **"boring early, strange at the top-weighted
  slot."**
- Decary, Bergman et al. (2024, "The Madness of Multiple Entries"): E[max] is submodular; the best single
  entry is often *not* in the optimal set; optimal multi-entry sets **repeat the same champion across
  entries while varying middle rounds** — diversification emerges as a consequence of the probabilities,
  never as a goal; their PROP+ per-round thresholds go risk-averse early / arbitrarily aggressive late.
- Crist's ABC exotic-ticket canon: tier legs by conviction, **press singles** (concentrate) on conviction
  legs to fund spread on uncertain legs; pick-6 syndicates add "separator" legs whose only job is making the
  winning ticket unique.

**Transfer.** The DFS book analog of the champion slot is the game-environment/QB-stack **spine**; the flex
slots are the early rounds. The convergent prescription: measure where the *field* concentrates (ownership
and stack-shape data — Week-1 capture makes this real) and place the book's contrarianism at the
top-leverage spine exactly where the field is chalky, while staying "boring" (high-probability) in
low-leverage slots — and be willing to *repeat* a conviction spine across many entries with varied
completions rather than maximizing spine variety. This is testable as a structural retention/allocation
policy in the KG family (it sharpens, not duplicates, 088's minimum-concentration arm), and the
"separator" framing gives the lev family a defensible payout-space identity distinct from its (weak)
raw-tail identity. Note the tension worth measuring rather than assuming: current guidance keeps rosters
globally distinct; Decary's repeat-the-champion result and ABC press-singles both suggest conviction-weighted
duplication can beat uniqueness under top-heavy payouts. That question is A5/field-model material
(payout-space, tie-aware), not a raw-max panel question. **Status: structural hypothesis with strong external
precedent; needs the field/ownership data lane; routes into KG/A5, no new family.**

### T6. Late swap as reset theory and two-stage optionality

**What the domains know.** Speedrunners formalized "many attempts, keep the max, under a time budget":
continue a run iff conditional record-rate ≥ your long-run record-rate (record-density policy iteration —
semi-formal but validated; koenbres04/ResetOptimization). Oil explorers formalize portfolios where *drilling
one prospect reveals the shared factor* and the second-stage plan adapts (two-stage stochastic programming);
survivor-pool optimization (Bergman & Imbrogno, OR 2017) proved planning-horizon re-planning beats
full-season precommitment.

**Transfer.** The knowledge frontier already lists "standings/payout-aware late-swap policy" as an open
program. These give it its math: (a) the swap rule is a reset rule — swap remaining slots when conditional
P(final ≥ target | early-game pace) drops below the book's standing rate; (b) more interesting and earlier
in the pipeline: **swap-optionality-aware selection** — late-game player slots are decision points that get
re-optimized after early games reveal the slate factor, so entries carrying late-game flexibility are worth
more than their frozen E[max], computable as a two-stage program on the existing worlds (condition worlds on
early-game outcomes; value the recourse). **Status: new formalization for an already-open program item;
panel-screenable outcome-blind (the recourse value is computed under the sim, graded prospectively).**

### T7. The operator layer: contest-curvature variance targets, overlay states, and the optimism haircut

Three A5-adjacent items with quantified external precedent:

- **Payout-curvature variance targeting (poker ICM):** solver-quantified bubble factors show
  winner-take-all structures collapse to pure chip-EV (maximum variance-seeking) while flatter structures
  demand survival — steep structures also need ~45% more bankroll at equal EV. DFS analog: assign
  per-contest lineup variance targets (qualifier ≈ winner-take-all → maximum-variance builds; Milly's
  deep-but-steep curve → slightly tempered), rather than one book profile for all contests.
- **Overlay hunting (the Cash WinFall lesson, legalized):** the syndicates' edge was recognizing and
  concentrating volume into temporary positive-pool states (rolldowns; carryover > takeout). The DFS analog
  is contest overlay and soft-field states — late-week underfilled contests and weak-field qualifiers —
  plus across-week allocation: the survivor-pool result says keep option value and re-plan, i.e., don't
  precommit the season's entry budget uniformly; concentrate entries in weeks/contests where the measured
  edge (T1 gap wide, injuries/uncertainty high, overlay present) is largest.
- **The 26% optimism haircut (Adams, NESSIS):** a real 100-entry bracket portfolio realized +53%/yr against
  a 72% simulated estimate — ~26% optimism when your own simulator scores your own portfolio. The program
  has its own versions of this (regret growing 8.5→13.1; the +1.9 phantom). Budget a standing haircut on
  any simulated live-performance projection used for bankroll or entry decisions.

---

## 2. External confirmations of things the ledger already settled (useful as ammunition, not work)

- **More entries beats better selection under power-law tails.** AngelList (10,665 portfolios): median IRR
  rises ~9bp per additional company; under α<2 tails fewer than 10% of skilled pickers beat the index.
  Matches the measured ~9.3 points per ln(k) entry curve — the ledger's largest lever — and the repeated
  finding that selector cleverness caps near ±1.
- **Greedy coverage/E-max selection is near-optimal in class.** qEI is submodular (1−1/e guarantee); joint
  batch optimization ties greedy-with-conditioning on benchmarks; Decary et al. prove submodularity of the
  E[max] entry problem. The selector's *shape* was never the problem — consistent with 087 FLAT.
- **Diversity as a goal is the wrong target.** Decary: optimal sets repeat champions; diversification is a
  consequence of correct probabilities. Matches the closed diversity/DPP/overlap-cap family and the
  anti-consensus caution.
- **Co-run controls on identical trial years** are industrial practice in reinsurance (marginal contract
  value = portfolio YLT with/without, same event years) — the program's same-bank co-run law independently
  reinvented.
- **Shakeup is mostly noise (Roelofs, NeurIPS 2019):** Kaggle private-LB shakeups trace to test noise, not
  adaptive overfitting — spend portfolio variance on genuine model diversity (the dual-law direction), not
  on hedging evaluation artifacts.
- **Benter's blend:** the combined logit c_i ∝ exp(α·ln f_i + β·ln π_i) — model shrunk toward the public —
  sustained a decade on ΔR² = 0.0178. External precedent for the adopted 45/55 market blend being the only
  info lever that moved the book; the log-space ML-fitted weights are a minor refinement worth one line in
  the market-ladder work, not an arm. His Harville corrections (power-dampened conditionals, γ=0.81,
  δ=0.65 — dependence *weakens* deeper into the order) are a compact functional form the dependence ladder
  can borrow for rank-conditional damping.

## 3. Screened and not recommended (the ledger already answers them)

- **Lottery wheels / covering designs:** wheels provably reshape the hit distribution without changing EV,
  and the lab's covering-array generation attack already failed — closed family.
- **Plain diversity selectors** (DPP-as-descriptor, overlap caps, Hunter-style max-correlation
  construction): closed (008/PREREG-016; production's quality-weighted DPP challenger stands).
- **Betting SGPs themselves** as a side income: the correlation tax (~15% hold) eats the documented edges;
  the value of the SGP market to us is its *prices* (T1), not its bets.
- **Ziemba's unpopular-numbers result** is the formal ancestor of the adopted chalk-fade and needs no new
  work — but carry his companion warning (MacLean–Ziemba): +EV with a catastrophic hit-rate profile is
  unusable without bankroll math; keep tail-probability primary, payout-EV secondary.
- **Manufacturing the +EV state** (MIT's forced rolldown): no DFS analog beyond overlay hunting (T7);
  noted for completeness.

## 4. Suggested entry points, in standing-law order

1. **Instrument-only, this month:** T1 reconciliation meter from existing `raw_prop_lines` +
   `odds_snapshots`; T2 CLV grading harness; T3 book receipts (√(1−ρ̄) decomposition, book-max exceedance
   curves). None opens an outcome; all three make 088/089 reads more interpretable.
2. **Into the existing dependence-repair ladder:** T1's implied-dependence series as calibration targets
   alongside realized co-exceedance (prior-fold fitting unchanged); Benter-style rank-damping as one
   candidate functional form.
3. **After the ladder yields a knob posterior:** T4's two bounded robustness screens (bagged selection;
   Thompson-from-law-uncertainty slots).
4. **KG/A5 lanes:** T5 spine-contrarian retention as a sharpening of the queued structural work once
   Week-1 ownership/field capture lands; T6 two-stage swap-optionality valuation for the open late-swap
   program; T7 operator decisions with the A5 memo.

## 5. Sources (as gathered by the three research sweeps)

Betting markets: DraftKings Engineering (Dorward) on simulation-priced markets; Wizard of Odds
"Same-Game Parlays: The Mathematics of Correlation"; OddsIndex SGP guides; USPTO 11657680/12002332;
Stanford Wong (BJ21) on correlated parlays; Buchdahl on CLV (Pinnacle Odds Dropper); Benter 1994 (incl.
Harville/Lo–Bacon-Shone corrections); Crist, *Exotic Betting*; Meadow, *Money Secrets at the Racetrack*;
Ziemba (JEP 1988; LSE working papers); MA Inspector General / HuffPost Highline on Cash WinFall; arXiv
2408.06857 (Mandel).
Pools/portfolios: Metrick 1996 (JEBO); Clair & Letscher (OR 2007); Niemi et al. (CHANCE 2008); Brill,
Wyner & Barnett (arXiv 2308.14339 / Entropy 26:615); Decary et al. (arXiv 2407.13438); Adams (NESSIS);
Bergman & Imbrogno (OR 2017); PoolGenius survivor practice; Roelofs et al. (NeurIPS 2019); Blum & Hardt
(ICML 2015); Caruana et al. (ICML 2004); AngelList Koh & Othman; Nanda & Rhodes-Kropf (JFE); Correlation
Ventures / Horsley Bridge base rates; GTO Wizard ICM payout-structure analysis.
Quant methods: Chevalier & Ginsbourger 2013 (exact qEI); BoTorch (NeurIPS 2020); Ginsbourger et al.
(Kriging Believer/Constant Liar); arXiv 2605.18819 (conditioning analysis); González et al. (AISTATS 2016);
GIBBON (arXiv 2102.03324); Kathuria et al. (NeurIPS 2016); Kandasamy et al. (AISTATS 2018); CBOE COR3M
white paper; Driessen, Maenhout & Vilkov (JF 2009); Quantpedia dispersion; Stulz 1982 / Johnson 1987;
Verisk cat-modeling primers; QuPARA (arXiv 1308.3615); arXiv 2504.16530 (reinsurance optimization);
arXiv 1304.0057 (tail importance sampling); koenbres04/ResetOptimization; SPE-147062 and arXiv 2605.26493
(exploration portfolios).
