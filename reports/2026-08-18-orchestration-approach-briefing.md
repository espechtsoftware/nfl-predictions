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
