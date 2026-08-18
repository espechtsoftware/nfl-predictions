# The biggest challenges to achieving high scores — an honest assessment

**Date:** 2026-08-18
**Author:** Claude (Fable 5), orchestrating
**Purpose:** operator-requested. This is the ranked list of what actually
stands between the current system and consistently high weekly maxima, with
the evidence for each, what is being done, and — critically — the residual
risk that the current plan does not cover. Everything cited is from the
frozen forensic/calibration/census results or the experiment ledger; no
number here is aspirational.

**The frame:** production selects 80 (now 100) lineups per Sunday main
slate; the objective is the maximum realized score among them. Current
measured state on the 54-slate 2023-25 corpus: selected-book mean weekly
max **176.06** (17/8/7/6/3/1/0 at 187-240); best generated candidate
**181.07**; best candidate in the union of everything ever generated
**198.10**; hindsight pool-player optimum ≈ **250**. Winning Milly lines
run ~194-240.

---

## Challenge 1 — The simulator cannot produce the worlds where tournaments
are won (missing joint co-boom mass)

**This is the most consequential defect because it poisons everything
downstream: generation, selection, and every experimental gate.**

The evidence triangulates from independent directions:

- The frozen selected-book calibration audit: at 210+, reality produced
  **6 clears where the simulator expected 2.76** — under-prediction by
  2.2x — while 194 is *over*-predicted (8 vs 10.26). The sim's tail has
  the wrong shape, not the wrong scale.
- Player marginals are, if anything, too wide (TabPFN walk-forward q90
  exceedance 7.37% vs nominal 10%). Wide singles + thin book tail has
  exactly one arithmetic explanation: **players don't boom together
  enough in the simulated worlds.**
- Three verified structural holes supply the mechanism: (a) **DST scores
  are constant across all 30,000-50,000 worlds** — one of nine roster
  slots contributes zero variance (`draw_idx=-1`, production
  `DST_CORR_DRAWS=""`); (b) **overtime does not exist as a shared
  mechanism** — measured +23.77 concentrated skill DK points per OT game,
  ~47% of 12-game slates contain one, and the marginals carry OT mass
  individually while the joint spike is absent; (c) **cross-team coupling
  is nearly independent** in the possession engine (factor corr ~0.1-0.2).
- The dependence diagnostic independently found an under-coupled QB hub
  with over-produced high multiplicity — the same signature.

**Why it caps high scores:** 220+ weeks are, by construction, worlds where
a game or two detonated and correlated stacks rode it. If the simulator
almost never manufactures those worlds, then (i) the boom generator never
solves for them, (ii) the selector never selects coverage of them, and
(iii) any mechanism that WOULD capture them fails our own simulated gates.
The one construction mechanism that ever worked (CBWU-OI) moved 194-210
and left 220/230/240 exactly unchanged — consistent with the pool simply
not containing enough extreme-joint candidates to admit.

**What is being done:** the D-lane (DST event model, gated on a paired
outcome-based sizing step), the approved S2 OT dependence-only mixture
draft, the production-law dependence scorecard (unblocks tonight when the
coherent chain completes), S4 attribution audit, with acceptance defined
as the calibration audit's 194/210 shape improving.

**Residual risk the plan does not cover:** dependence repairs at fixed
marginals are zero-sum — adding OT/DST co-boom mass *thins* other co-boom
mass. The net effect on max-of-80 is genuinely two-sided, the DST prior
is tested-twice-negative in an older stack, and no one has demonstrated
that a better-calibrated tail produces a better realized book. This lane
is the right bet, and it is still a bet.

---

## Challenge 2 — The double measurement bind: neither instrument can see
ordinary-sized improvements

Two instruments exist to judge any idea, and both are weak:

- **Simulated gates:** candidate-level sim/realized correlation ~0.16-0.24;
  held-out AUC 0.6255; book-level calibration Brier skills with CIs
  crossing zero. Six mechanisms passed simulated gates and then produced
  nothing real (Schaake, three Gumbel variants, CE, fast-role).
- **Realized panels:** 54-107 slates. Binomial sd on a clear-count is ~4,
  so effects below roughly ±8 slates are invisible; the six "failures"
  include nulls (26v27) the panel could never have adjudicated. Worse, the
  informative statistic for paired arms (discordant pairs, McNemar) was
  never recorded by any arm report — a gap only identified today.

**Why it caps high scores:** the system cannot cheaply find improvements
(sim can't rank them) and cannot cheaply prove them (panel can't resolve
them). Everything must therefore be either large (CBWU-OI's +5.66 is the
only member of that class), structural (justified without any panel), or
prospective (2026 data) — which is a brutally narrow funnel, and it is the
correct explanation for 489 commits with zero adoptions, not process
failure.

**What is being done:** the McNemar reanalysis of all closed arms (top
analytical item — the registered data supports it); instrument repair
(Challenge 1); the S1 null floor to calibrate what P-C is winnable;
prospective collection wired before Week 1.

**Residual risk:** the McNemar recomputation may reveal the closed arms
were even *less* informative than believed — which sharpens honesty but
shrinks the usable evidence base further. And the 2026 season itself is
only ~18 graded slates: the prospective instrument is also low-power, so
even CBWU-OI's live year may end ambiguous.

---

## Challenge 3 — The construction gap is huge, but nobody knows how much
of it is winnable (P-C = 68.91, floor unmeasured)

The hindsight pool-player optimum sits ~69 points above the best generated
candidate, and the exact-P census shows the winner is typically ~5 player
swaps from everything we build. But P is a max over an astronomically
larger lineup space evaluated on one realized draw — a large P-C gap would
exist even under *perfect* beliefs, purely from order statistics. Today's
B1 census made this concrete: the candidate ceiling grows ~+3.5 points per
doubling of independent books with no saturation through 51 books —
order-statistic growth, with cross-arm "idea diversity" worth only ~+0.4.

**Why it caps high scores:** the 194-mean target requires a pool whose C
is roughly 196+. If most of the 69 points is order-statistic noise, no
finite generator reaches it by being smarter, only by being luckier or
bigger — and bigger pools are proven to damage the *selected* book under
the current signal (Addendum 117). The whole construction program's
expected value hinges on a number (the self-law floor) that has never been
measured.

**What is being done:** S1 (approved, protocol next) measures exactly that
floor using held-out same-law worlds and the seed-block-disjoint rule;
B2' (running tonight) tests whether OI-style admission converts volume
into fixed-budget realized C; residual-world columns — the only generator
that prices lineups by marginal contribution to uncovered tail states —
awaits its S1-gated slot.

**Residual risk:** if S1 says the floor is ~55 of the 69 points, the
honest conclusion is that construction is close to its practical ceiling
and the remaining points live in Challenges 1 and 4 — a result that would
invalidate much of the intuitive appeal of "just build better lineups."

---

## Challenge 4 — Selection is simultaneously near-perfect and mistargeted

The selector captures 100% of what the pool offers at 220+ and loses only
~5 mean points overall — yet those 5 points are real, and the C-S gap is
a *mean* gap with almost no threshold gap: the fingerprint of an objective
(cover worlds >= 194) that is indifferent among lineups once a world is
covered. Meanwhile book identity is partly selector noise (disjoint-half
overlap 61-66/80), and five selector redesigns produced nothing real,
closing selection on current signals by preregistered rule.

**Why it caps high scores:** with the pool fixed, the only selection
headroom is +5 mean; with the pool grown, weak signal turns extra volume
into dilution. Selection cannot be the engine of high scores — but a
mistargeted objective can quietly tax every other improvement.

**What is being done:** the authorized one-shot A1 family (E[u(max)]
portfolio-marginal greedy under the operator's frozen sparse-ladder
utility with a hard 210+ no-decline guard); A3 (exact-vs-greedy audit) to
close the algorithm question permanently; S6 stability work score-free;
and the legitimate reopening path — an adopted dependence repair — runs
through Challenge 1.

**Residual risk:** A1's in-sim gains transfer through the same ~0.2
signal as everything else; expected realized value is ~+1-2 mean at best,
and the family is one shot by design. If it nulls, selection is finished
as a lever until the law improves.

---

## Challenge 5 — The rare-boom information ceiling (the misses no model
can currently see)

33 of 612 Milly-winner roster slots were players absent from *every*
candidate — overwhelmingly thin-history WR/TEs (breakout/vacancy types,
+15.55 mean surprise). The static feature set demonstrably cannot rank
these players in time; the fast-role model that tried was validly
rejected; the exact-P census shows this is a meaningful slice of what
separates generated books from winners.

**Why it caps high scores:** a winning lineup usually contains one or two
of exactly these players. No amount of construction or selection fixes a
belief system that assigns them near-zero boom probability pre-lock.

**What is being done:** tracking-traits shadow features on thin-history
players (the gate is defined; the crosswalk exists), multi-book prop
collection starting now (the one-book dispersion null was measured on data
that could not support the question), the S8 surprise ledger to classify
every future miss, activated evidence, and the September news/persona
pipelines — all prospective 2026 paths.

**Residual risk:** these are collection bets with no historical
provability at all — their value cannot be known before mid-season, and
they compete for the same weekly operational attention as everything else.

---

## Challenge 6 — The historical record is nearly exhausted as an
evidence source

Every 2019-2025 outcome has been viewed at panel level. The standing laws
(correctly) forbid retrospective tuning on these slates; the reopening
conditions are narrow; the operator's one-shot family is, by design, close
to the last clean read these 54 slates can give. Meanwhile retrospective
success has repeatedly failed to transfer (the transfer record is the
reason the promotion gate demands prospective evidence).

**Why it caps high scores:** from here, genuinely new knowledge about
scoring higher arrives almost exclusively through the 2026 season — ~18
Sunday slates, one shadow grade, 100 entries a week. The system's learning
bandwidth is about to drop from "any panel we can afford" to "what one
season can teach," and anything not wired to collect before Week 1
forfeits a year (the CBWU-OI shadow existed for zero of the mechanisms
that came before it).

**What is being done:** Week 1 operational lane (collectors, shadow fleet,
the OI top-20 export, contest-fill capture); the surprise ledger; the
discipline of preregistered gates so season evidence is admissible.

**Residual risk:** a single season is a weak judge (Challenge 2 applies
to it too), and in-season operational load competes with research
attention on the same operator and the same fragile local machine.

---

## Challenge 7 — Execution fragility taxes everything (the compounding
overhead)

Today alone: three frozen-artifact contract defects (a census key name, a
comma-split command, newline-contaminated manifest values — the last
making a strict gate unpassable *by construction* on its first-ever
complete run), a build timeout from +11k lines of accumulated tests, and
one cross-file test pin. The ATLAS era burned six grid attempts on the
same class. All were fail-closed (correctness held), all were
offline-detectable, and each cost minutes-to-hours that used to cost days.

**Why it caps high scores:** indirectly but relentlessly — every heavy
experiment slot lost to mechanical failure is a construction or law
result not obtained, and the season deadline does not move. The local
machine's crash-under-load constraint and the one-heavy-chain lease make
serial time the scarcest resource the project has.

**What is being done:** the contract-test layer (21 offline tests shipped
with the C runner alone), canary-first launches, spec lint, durable
watchers/recovery runbooks, and repair notes measured in minutes.

**Residual risk:** the frozen-artifact web keeps growing; each new frozen
protocol adds surface for the next contract mismatch. The discipline
holds correctness; it spends calendar.

---

## How the challenges compound — and what has to be true for 194+

These are not independent. The law's missing co-boom mass (1) is why the
sim signal is weak (2), which is why bigger pools dilute (3, 4), which is
why the extreme tail never grows, which is why only prospective data (5,
6) can adjudicate anything — under an execution regime (7) that taxes
every attempt. Conversely, one real dependence repair pays four ways: a
truer tail, a sharper gate signal, a legitimate selector reopening, and a
boom generator that finally solves for detonation worlds.

For a ~194 mean weekly max to be achievable, the following must all break
favorably: S1 shows a meaningful winnable construction share; the
dependence repairs move the 210 calibration shape without destroying
shoulder coverage; residual columns or B2'-class admission convert that
into realized C at fixed budget; and the 2026 season is long enough to
prove any of it. Each step is genuinely uncertain. The honest statement
is that the system currently earns ~176 against a ~181 pool on a ~250
hindsight universe, every cheap route between those numbers has been
measured or closed, and the remaining routes are the hard ones now funded
in priority order.

---

# Part II — Where the largest opportunities are

Ranked by expected value against the challenges above, with the honest
size class of each.

## O1. The dependence repair is the one move that pays four ways

Every other opportunity improves one layer; a real joint-co-boom repair
(OT mixture, DST events, cross-team/QB-hub coupling) simultaneously (i)
puts detonation worlds into the pool the boom generator solves, (ii)
sharpens the selector's coverage signal, (iii) legitimately reopens
selector evaluation under the preregistered condition, and (iv) fixes the
gate instrument every future experiment is judged with. It is also the
only lane aimed at 220+, where selection is already perfect and the money
is. Size class: unknown but structurally unique — the 2.2x under-
prediction at 210 says the missing mass is real. S2's base-rate OT
mixture is the cheapest first shot because it requires no prediction
skill at all.

## O2. The admission/distillation class — the only mechanism family with
a proven realized gain

CBWU-OI: +5.66 mean C at exactly fixed budget, the single positive
construction result in the project's history — now live as a paired
shadow with 20 real entries. Tonight's B2' answers whether the same
admission law scales with book volume toward the 198 union ceiling. If
even a third of the k=5-to-k=51 pool growth survives admission at fixed
budget, that is the largest near-term realized-C gain available from
existing data, and its prospective vehicle (the shadow pattern) already
exists. Size class: +2-6 mean C if it scales; a clean closure if not.

## O3. Residual-world columns — the only generator aimed at the operator's
actual utility

Everything else generates candidates by proxy objectives and hopes; the
residual-column machine prices each new lineup by its marginal
contribution to uncovered tail states across the exact thresholds the
operator is paid on. It is implemented, score-free green through its
proof chain, and S1's floor tells us how much room it has. Size class:
the remainder of whatever S1 says is winnable — potentially the largest
single number in the program, or nearly nothing; that is exactly why S1
runs first.

## O4. The selection objective fix (A1 family) — small, cheap, and already
authorized

The C-S gap is a mean gap because the selector's objective stops caring
above its line. Retargeting the same greedy machinery at the operator's
sparse-ladder utility is a laptop-scale one-shot with a plausible +1-2
realized mean and the 210+ guard frozen in. Not transformative; nearly
free; the definition of picking up a dropped coin.

## O5. Prospective information on thin-history players — the only path to
the 33 missed winner slots

Tracking traits (data in hand, gate defined), multi-book prop dispersion
(collection starting; the old null was measured on data that could not
support the question), the surprise ledger (approved), news/evidence
activation. None is provable offline; together they attack the one loss
category no construction or selection change can reach. Size class per
winning lineup: one to two roster slots — which at Milly lines is often
the whole difference.

## O6. Entry scaling and operational excellence — the guaranteed capture

Max-of-N grows with N with certainty, not with model skill. The 80-to-100
move (money book + OI top-20) is already decided; every additional entry,
every collector running by Week 1, every Sunday the shadow fleet actually
fires is expected value that requires nothing to be discovered. Addendum
95 named more entries as one of exactly two guaranteed capture paths, and
it remains the only lever with zero scientific risk.

## O7. The meta-instruments — cheap measurements that keep the season's
scarce slots honest

S1 (winnable-gap floor), A3 (selector-algorithm closure), the McNemar
reanalysis (what the closed arms actually proved), S4 (marginal-vs-
dependence attribution). None scores a point; each one redirects heavy
slots away from unwinnable territory. Their combined cost is days; the
slots they protect are the offseason. The B1 census already demonstrated
the pattern: one query killed an entire tempting-but-empty program (B2
diversity admission) before it spent a heavy slot.

## The portfolio view

O1 is the bet that changes the game; O2/O3 are the funded construction
bets with the only proven precedent; O4 is loose change worth taking; O5
is the only answer to the hardest loss category; O6 is certain and
boring; O7 keeps everything else honest. The program as now sequenced
spends its next slots in exactly that order of leverage — and the
2026 season, with collectors live and preregistered gates, is the first
season where a positive result anywhere in this portfolio can actually
be promoted rather than merely admired.
