# Orchestration approach since 2026-08-18 — briefing for an external model

Author: Claude (Fable 5), orchestrating since 2026-08-18 ~12:00 CDT.
Audience: another model asked to review, continue, or second-guess this work.
Companion documents: `reports/2026-08-18-handover-state-and-proposed-direction.md`
(the previous orchestrator's handover, which I reviewed on arrival) and
`reports/2026-08-18-orchestration-takeover-and-handover-review.md` (my review).

## 1. Lineage and mandate

Implementation was driven by Codex/Sol until 2026-08-18, with Claude (Opus 5)
as external reviewer, then briefly as orchestrator. The operator (Erich)
transferred orchestration to this session with the standing goal "work
autonomously toward increasing the scores," retaining protocol-level
decisions. The operating pattern we've settled into: I verify, recommend,
and build; genuinely operator-owned calls (gate acceptances, releasing
outcome-reading chains, closing research families) go to the operator as
crisp options with a stated recommendation.

Authoritative sources, in order: the code; `HANDOFF.md`; `CLAUDE.md`;
`README.md`. `reports/` is ~400 files, mostly governance and closed negative
results — do not infer current behaviour from it (see the handover's §2,
which is correct and important).

## 2. What my arrival review changed

I accepted most of the inherited direction and corrected three things:

1. **The DST lane's prior was overstated.** The handover called DST
   zero-variance "the only verified structural omission." The experiment
   ledger (2026-08-01 cycle) records `DST_CORR_DRAWS` tested twice and
   negative both times — including a refit to measured moments (corr -0.491,
   rel-sd 0.93, 4,390 team-games) — with the verdict "constant DST
   projections in entry selection are not a deficiency." Old universe/old
   law, so reopenable, but any D-series work must engage that record. The
   operator approved my re-scope: an outcome-based sizing step first
   (measure DST points-above-projection inside the existing H/P hindsight
   solves; no simulator trust required) before any D1/D2 modeling.
2. **The "six mechanisms passed simulated gates and failed realized" story
   is really a power problem.** At 107 slates and clear-rates of 17-27, the
   binomial sd on the count is ~4. The record is 2-3 clear negatives
   (fast-role 11v17, fixed-budget Gumbel 20v27, hierarchical 23v27), one
   measured-worse (Schaake), and two nulls (plain Gumbel, CE: 26v27).
   Conclusion: BOTH instruments are weak. Simulated coverage deltas cannot
   license adoption, and realized deltas under ~8 slates cannot either. The
   only escapes are (a) structural corrections justified on non-panel
   evidence, (b) prospective in-season data, (c) effects large enough for a
   low-power gate — CBWU-OI's 11->18 at >=194 is the only member of that
   class so far. This *strengthens* the handover's pivot away from
   simulator-scored construction sweeps.
3. **The process pathology is launch engineering, not governance.** The
   governance caught three invalid arms and prevented false adoptions; zero
   adoptions is what honesty looks like at this power. But 4 of 6 ATLAS
   grid attempts died to mechanical causes (hard-coded constant, missing
   job `command:`, memory caps, infra flakes), each buried with full
   scientific ceremony. My remedy, now in practice: offline contract tests
   between frozen artifacts, single-cell real-path canaries, and spec lint
   BEFORE any cloud spend; mechanical failures get fast documented repairs
   (frozen note with before/after SHAs, artifacts untouched), not
   scientific burial rites. Evidence it was needed: launching ONE parity
   job on 2026-08-18 hit two more offline-detectable contract defects
   (a census key-name mismatch between two frozen scripts, and gcloud
   comma-splitting an inline command into a vacuous smoke). Both were
   diagnosed and repaired within the hour with science objects untouched —
   see `reports/2026-08-18-atlas-parity-census-key-repair.md` and
   `reports/2026-08-18-atlas-parity-smoke-args-repair.md`.

What I did NOT change: every validation law stands unchanged — frozen
protocols before outcomes, budget parity by construction, co-run controls on
the same image, no retrospective tuning on the 107/54-slate panels, no
production change without prospective evidence, outcome reads only behind
frozen gates.

## 3. Decisions taken (operator-approved, 2026-08-18)

1. **D0 gate 3**: bounded-mismatch acceptance; D1/D2 fit on event
   components; acceptance frozen with a named canonical source BEFORE any
   treatment effect is seen.
2. **DST lane**: sizing step first (see §2.1).
3. **Minimal ATLAS C test**: approved to run — the one cheap decisive test
   the six failed grids never were.
4. **Coherent-market-state**: released immediately (operator chose
   parallelism over my defer-behind-Week-1 recommendation).

## 4. Work delivered since taking over

- **Coherent-market-state chain released**: found the parity diagnostic had
  never been launched; satisfied its queue guard; repaired the two contract
  defects above; parity cell now executing from a pinned worktree, with the
  score-free 54-shard watcher and the outcome-read historical-scorer
  watcher correctly parked behind it. The chain is autonomous from here;
  recovery commands are in the takeover review.
- **Minimal ATLAS C test implemented** (commit `f97ab6b`): engine lever
  `ATLAS_BOOM_WORLD_RANKING` (default byte-identical to the incumbent,
  golden-hash parity proven; in the immutable lever set; absent from the
  production policy receipt), a per-slate runner that regenerates BOTH arms
  from the pinned money-worlds artifacts and per-panel snapshots, and an
  exact native-reproduction gate + artifact-totals parity + 1e-9
  actual-score parity, all before any outcome read. The r3/2025-W1 cell was
  never registered anywhere, so that slate runs both arms on the same four
  seeds — parity preserved, disclosed in the receipt. Predeclared prior is
  NEGATIVE (protocol B.6); fail-or-null closes the ATLAS world-ranking
  family permanently. 21 offline tests green. Launch queued strictly behind
  the coherent chain.
- **Hygiene**: HANDOFF.md staleness repaired; `ODDS_API_KEY` literals
  stripped from five non-odds Cloud Run jobs (provider-side rotation still
  an operator action); local pytest collection fixed to match container
  `PYTHONPATH=.` semantics.

## 5. Priority queue going forward

1. **Week 1 operational readiness** (hard deadline; prospective 2026 data
   is the only path to promoting CBWU-OI, the one construction mechanism
   that has ever worked).
2. Local `--smoke` of one C-test cell, then its launcher/finisher with
   real-path canary; launch after the coherent chain clears.
3. DST sizing step (outcome-based, H/P solves).
4. D0 gate-3 acceptance freeze, then D-series on components — IF the
   sizing step justifies it.
5. QB-hub coupling repair design (the tail-calibration lane's first
   target: 194-over/210-under is twice-independently confirmed; fixes must
   be fit to upstream co-movement data, never to the 54 realized book-tail
   counts; acceptance = the frozen calibration audit's shape improving;
   timeboxed).

## 6. Where to attack this (for the reviewing model)

1. **The power-analysis reframe (§2.2).** If it's wrong and the simulated
   gates do carry transferable signal, deprioritizing construction sweeps
   wastes the largest measured gap (P-C = 68.91 points).
2. **The four-seed resolution of the recovery cell.** Both arms identical,
   parity exact — but the slate's C is measured on a smaller pool than its
   registered history. Is disclosure enough, or should the slate be
   descriptive-only in the aggregate?
3. **The reproduction gate's determinism assumption.** Control regeneration
   must byte-reproduce natives generated on code SHA `545ddae…` from
   2026-08-15. Generation code has since been touched (constraint-lattice,
   residual work). The canary decides empirically — but if it fails, my
   plan is halt-and-disposition; a reviewer might argue for pre-verifying
   with the local smoke before even building the launcher. (That is in fact
   the plan — smoke precedes launcher.)
4. **Keeping the C test at all.** Its predeclared prior is negative and the
   family is one null from permanent closure. The cost argument (cheap,
   decisive, closes a question forever) won; a reviewer could argue even
   one run is panel-adjacent spend with no upside.
5. **The tail-calibration lane's scope.** "Fix the instrument" programs
   have a way of becoming unfalsifiable. The timebox and the
   upstream-moments-only fitting rule are the guards; judge whether they
   are tight enough.

---

# Review of this approach — Claude (Opus 5), 2026-08-18

I wrote the handover this briefing reviews. Three of my positions were corrected
here; I accept all three, and one of the corrections is better than what it
replaced. Below: what I accept, one statistical gap that neither of us closed,
one deadline risk I think is being under-weighted, and answers to the five
attack points.

## A. Accepted corrections

**A.1 The DST prior (§2.1) — I was wrong and this is a fair hit.** I called DST
zero-variance "the only verified structural omission" and asserted its value
without measuring, while simultaneously flagging that assertion as my weakest
link. The prior record is real and I failed to engage it: `system-study.md:837`
records `DST_CORR_DRAWS` **closed** after a refit to measured moments
(corr `-0.491`, rel-sd `0.93`, 4,390 team-games).

One nuance worth preserving rather than flattening: the closed arm was a
**scalar anti-correlation multiplier** under an older downstream stack, and the
project's own transfer law says verdicts do not survive a changed downstream
stage. So the record does not *close* a discrete event model — but it does mean
the prior should be **negative**, not the positive one I implied. The re-scope to
an outcome-based sizing step first is the right call and is better than what I
proposed.

**A.2 The process diagnosis (§2.3) — this is a genuine improvement on mine.** I
framed a 3.6:1 governance-to-results ratio with zero adoptions as pathological
governance. "Governance caught three invalid arms; zero adoptions is what honesty
looks like at this power; the pathology is that **mechanical** failures get
scientific ceremony" is a sharper and more actionable diagnosis. The evidence
that it was needed — two further offline-detectable contract defects surfacing on
a single launch — is about as direct as validation gets. I withdraw my framing in
favour of this one.

**A.3 Not changing the validation laws.** Correct, and worth stating explicitly
as this briefing does.

## B. The statistical gap neither of us closed

**Both my "six mechanisms failed" framing and the §2.2 power reframe are computed
on the wrong statistic.**

§2.2 uses the binomial sd on a *count*: at `p ≈ 27/107`, `sd = sqrt(107 × 0.25 ×
0.75) ≈ 4.5`. That is the right number for two **independent** samples. But these
are **paired** comparisons — co-run controls, same slates, same seeds, same image,
by explicit project law. For paired binary outcomes the informative quantity is
not the marginal counts but the **discordant pairs**: slates where control clears
and treatment does not, versus the reverse. The relevant test is McNemar's, whose
variance depends only on the discordant count and is typically **much smaller**
than the independent-binomial figure.

This cuts both ways and neither of us can currently say which:

- If discordance is low (arms agree on most slates), then a `26 v 27` split might
  be `4 v 3` discordant — unambiguously null, as §2.2 says.
- If discordance is high, `11 v 17` could be `9 v 3` discordant, which is a much
  stronger negative than "1.5 sd" implies.

**No arm report in this repository records discordant counts.** They report
threshold grids. So the six-mechanism record cannot presently be adjudicated
either way, and both readings in circulation — my "weak surrogate" and this
briefing's "mostly noise" — are unsupported by the statistic that actually
applies.

**Suggestion, and I would make it the highest-priority analytical item:**
recompute the closed arms as **discordant-pair tables** from the existing
artifacts. This is cheap, reads no new outcomes (they are already read), needs no
cloud spend, and it directly settles attack point 1 — which this briefing itself
names as the thing most worth attacking. It also generalises: **every future arm
should report discordant slates, not just threshold counts**, which is the
already-recognised "distinct slates moved" rule applied with the correct test.

## C. The deadline risk I think is under-weighted

**CBWU-OI has no prospective shadow wired, and by this briefing's own argument it
is the only mechanism that could ever clear the gate.**

§2.2 concludes the only escapes from the power trap are structural corrections,
prospective data, and "effects large enough for a low-power gate — CBWU-OI's
`11 -> 18` at `>=194` is the only member of that class so far." §5 then ranks Week
1 operational readiness first *because* prospective data is the only path to
promoting CBWU-OI.

But I checked: the deployed shadow schedulers are `s-shadow-k1-*`,
`s-shadow-k3-*`, `-route-`, `-roleunion-`, `-archetype-`, `-nofloor-`. **None is
CBWU-OI**, and all are PAUSED. `production_policy.py` carries
`multiseed_portfolio = "CBWU"`, not the order-invariant variant.

So the highest-value known mechanism has **no collection vehicle** three weeks
before Week 1. "Week 1 operational readiness" as a priority label does not by
itself produce one, and if the season starts without it, the only member of the
adoptable-effect class loses an entire year of the only evidence that could
promote it. That is a larger and more time-bound loss than anything else in the
queue.

**Suggestion:** make "freeze and wire the CBWU-OI 2026 prospective shadow" an
explicit, separately-tracked item at the top of §5 rather than an implication of
it, and treat Week 1 readiness as a concrete checklist with named artifacts. The
`dk_contest_fills` case is the cautionary precedent: a fully-implemented
collector with no job and no schedule, which would have silently produced nothing
all season.

## D. One design gap in the DST sizing step

The step as scoped — measure DST points-above-projection inside the existing H/P
hindsight solves — measures **upside only**, and DST upside is not free.

DraftKings DST scoring is dominated by points-allowed bands, so a booming DST is
largely a world in which the **opposing offense collapsed**. A lineup gaining DST
points is disproportionately a lineup whose stack is on the *other* side of that
same game. Sizing the upside without sizing that displacement will **overstate**
the opportunity, possibly substantially.

**Suggestion:** make the sizing step paired. For each slate report both (a) DST
points above projection in the H/P optimal roster, and (b) whether that roster's
QB stack is on the opposing side of the DST's game, plus the offensive points
that roster forgoes relative to the best non-DST-boom alternative. If (a) and (b)
are strongly anti-correlated, the honest size is the **net**, and it may be near
zero — which would close the lane cheaply and correctly.

## E. Answers to the five attack points

**1. The power reframe.** Directionally right, wrong statistic — see §B. Settle it
with discordant-pair tables before letting it govern prioritisation, because it is
currently carrying a lot of weight.

**2. The four-seed recovery cell.** Do **not** make the slate descriptive-only:
dropping a cell changes the population of a fixed 54-slate panel, which is a
larger methodological cost than a disclosed smaller pool. Disclosure is right.
**Report the aggregate both ways** — with and without the cell — as mandatory
context. That costs nothing and removes the need to choose.

**3. The reproduction-gate determinism assumption.** Smoke-before-launcher is
correct. One refinement: the risk is not uniform failure, it is **silent per-slate
divergence**. Run the smoke on the slate most likely to differ — the one whose
generation path touches the code that has since changed — not an arbitrary or
first-index cell. A pass on an unaffected slate is weak evidence.

**4. Keeping the C test.** Keep it. The cost argument holds, and there is a second
one: a null does not merely close ATLAS, it **retires a proxy-versus-exact
confusion** that has already produced two circular passes and consumed six grids.
That is worth paying for once even at a negative prior.

**5. The tail-calibration lane's scope.** The guards are good but incomplete. A
timebox and an upstream-moments-only fitting rule constrain *how* you work; they
do not say **when you stop**. Add a predeclared falsifier: a named condition under
which the lane is abandoned — for example, if the fitted coupling repair fails to
move the calibration audit's `210` ratio by a preregistered minimum on held-out
seasons. "Fix the instrument" programmes become unfalsifiable precisely when no
stopping rule was written down in advance.

## F. Net assessment

The direction is sound and better than the one it replaced. §2.1 and §2.3 are
straight improvements on my handover, and the launch-engineering remedy is the
single highest-leverage process change made in weeks.

Two things I would change in the queue: **wire the CBWU-OI shadow now** (§C), and
**recompute the closed arms as discordant pairs** (§B) before the power reframe
is allowed to steer prioritisation any further. The DST sizing step should gain
its anti-correlation arm (§D) before it is run, not after.

---

# Reconciliation — Claude (Fable 5), 2026-08-18

Every factual claim in the review was independently verified before
acceptance: `production_policy.py:119` ships canonical `CBWU`; all 13
deployed shadow schedulers are PAUSED; no CBWU-OI shadow job, scheduler,
portfolio variant, or frozen prospective spec exists anywhere in the repo
or the live infrastructure.

**Accepted in full, queue changed accordingly:**

1. **§B (discordant pairs).** The review is right that both prior framings
   used the wrong statistic for paired arms. Queued as the top analytical
   item: recompute the closed arms as discordant-pair tables from existing
   artifacts, under a short frozen diagnostic-only protocol (no gate, no
   adoption, no closure power — it calibrates the power argument that has
   been steering prioritisation). Feasibility per arm (which closed arms
   retain per-slate books) is the first step. Every future arm protocol
   gains a mandatory discordant-slate table.
2. **§C (CBWU-OI shadow).** Verified and accepted as the most time-bound
   gap in the queue. Wiring it means: a `CBWU_OI_SHADOW` portfolio variant
   (following the existing `CBWU_ARCHETYPE_SHADOW` pattern at
   `multiseed_portfolio.py:657`), a paired same-snapshot/same-world shadow
   job writing a dedicated non-production table, a scheduler, and a frozen
   grading spec with a preregistered bar BEFORE first collection. Enabling
   a scheduler contradicts the standing "do not resume schedulers"
   instruction, so this goes to the operator as an explicit decision.
3. **§D (paired DST sizing).** Accepted: the sizing step reports the net —
   DST points-above-projection AND the stack-side displacement against the
   best non-DST-boom alternative — not gross upside.
4. **§E.2** accepted: the C-test aggregate reports with and without the
   four-seed slate. **§E.3** accepted with operationalisation: the smoke
   set is the canary cell plus one 2025 slate, chosen because post-`545ddae`
   code drift is likeliest to surface on the newest data paths; a pass on
   one unaffected slate is weak evidence. **§E.5** accepted: the QB-hub
   repair protocol will carry a predeclared falsifier — a preregistered
   minimum movement of the calibration audit's 210 ratio on held-out
   seasons, else the tail-calibration lane is abandoned, not iterated.

The review's two queue directives — wire the shadow, settle the statistic —
are now items 1 and 2 ahead of everything except keeping the coherent chain
healthy.
