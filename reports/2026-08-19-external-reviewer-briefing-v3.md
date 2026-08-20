# External reviewer briefing v3 — state, in-flight work, and the question needing a second opinion

**Date:** 2026-08-19 (evening, CDT). **Role of this document:** a
self-contained temporary handoff and second-opinion briefing. It is
current as of this writing; [`HANDOFF.md`](../HANDOFF.md) remains the
standing record and supersedes this file as work moves.

## 1. Document map (authority order)

| Document | Authority |
|---|---|
| [`HANDOFF.md`](../HANDOFF.md) | The tracked current-state record. Read first when resuming |
| [`CLAUDE.md`](../CLAUDE.md) | Binding working rules: validation laws, frozen-chain lessons, machine constraints |
| [`README.md`](../README.md) | Entry point: architecture, setup, orchestration model, CLI; hosts the append-only data-deficiency log |
| [`docs/design-guide.md`](../docs/design-guide.md) | The original §0–§14 design guide (reference, not current state) |
| [`reports/2026-08-19-preseason-test-queue.md`](2026-08-19-preseason-test-queue.md) | THE single ordered experiment queue with gates and statuses |
| [`reports/current-baseline.json`](current-baseline.json) | Canonical baseline numbers, updated only from committed receipts |
| `reports/` generally | Protocols, receipts, results. **Not uniformly adopted** — proposals and superseded analyses live here too; on any conflict, code and HANDOFF win |

The operator-facing dashboard is `bash scripts/chain_status.sh`
(`--watch` for the live app; `--baseline`, `--experiments`,
`--result <substr>`, `-b/-e <id|latest>` for logs). Every
score-affecting run commits its result JSON under `reports/*-runs/`.

## 2. The program and its baseline

DraftKings NFL Millionaire-Maker system optimizing the **weekly best
realized score of an 80-lineup book**; operator target ≈194 mean.
Current verified baseline (54-slate Sunday-main corpus, 2023–2025 — the
full VALID history):

- **Money book 176.06 mean weekly best** (≥187/194/210: 17/8/6 slates).
- Arm-comparator reconstruction 178.57 (53 slates); registered pool
  ceiling C 187.58; exact-stack gap chain H−P 4.06, P−C 68.91, C−S 5.01.
- Historical headlines implying higher means (the "27/107" era) were
  measured on a structurally broken replay universe (mixed slates,
  dropped DST salary rows, wrong DST scoring) and are formally
  retracted. Two older seasons (2019, 2021) are rebuildable with the
  already-fixed pipeline; 2020/2022 lack salary data entirely.

## 3. What today established (all frozen one-shots, receipts committed)

Chronologically compressed; each item links to its result document.

1. **Winner-audit series** (`2026-08-19-winner-world-optima-and-field-null-results.md`):
   the N1 "law can't produce winning scores" headline died to a
   field-max selection-effect null (a correct law reproduces the
   observed percentile extremity with a ~9.5k-roster field); and no
   Milly winner is EVER its best world's optimum (0/51; median 47.4
   points below, 4/9 overlap). Only surviving law-deficit evidence at
   winner scale: the book-tail factor-of-two.
2. **Winner anatomy** (`2026-08-19-winner-anatomy-results.md`): pool
   proximity to winners is exactly CHANCE (max-overlap minus
   exposure-null median 0.00); winners are chalk-core + ~4 sub-10%
   pieces; deep-world optima carry ~3× the winners' never-realized
   draw mass.
3. **Structure census** (`2026-08-19-winner-structure-census-results.md`):
   production's stack/bring-back mandates confine 100% of generated
   volume to a shape region holding **16% of real winners** (22% of
   winners are naked-QB; 61% have no bring-back; 69% concentrate ≤3 in
   any game). For the 8 rule-compliant winners the blocker is worlds +
   law preference, not player coverage.
4. **All-boom C then S** (`2026-08-19-all-boom-and-dependence-results.md`,
   `2026-08-19-all-boom-selection-s-results.md`): replacing the lev
   batch with boom depth raised the POOL ceiling +9.06 (43/54, p≈0) at
   exact budget — and the SELECTED book captured +1.34 of it, p=0.49,
   19/18/16 — **null**. The winner-overlap instrument shows the boom
   book aims WORSE than the incumbent. Reallocation closed for the
   money path; the C−S harvest gap (5→17 points, growing with pool
   depth) is now the largest measured unclaimed prize.
5. **Dependence remeasurement** (same results doc): the simulator
   over-couples generic teammate co-booms (≈5× at 4-plus, ≈4× RB–RB
   and TE–TE) and UNDER-couples QB→WR (−0.26 log-ratio) — the one
   pairing tournaments are won with. First law defect with a measured
   direction. Repair design: `2026-08-19-dependence-repair-design.md`.

Convergent diagnosis across five independent audits: the simulator
misallocates co-boom mass toward whole-team pile-ups, construction
mandates force shapes the law doesn't reward, and the field wins with
less stacking and more game spread than we can even generate.

## 4. In flight right now

- **A3 stack-relaxation carve** (`20260819-stack-relaxation-carve-v1`,
  protocol frozen at `2026-08-19-stack-relaxation-carve-protocol.md`):
  operator approved relaxing the construction mandates; k=8 open solves
  per seed (delegated sizing; rationale recorded — the modest dose
  deliberately limits expression of the law's measured generic-coupling
  bias). Outcome-blind smoke already showed the unchanged selector
  voluntarily takes 11/80 open-shape lineups into the book. Cloud
  build → canary → 54 cells → aggregate running; log
  `~/nfl-panels/stack-carve-chain.log`.
- **B1 volume shadow** (build in progress, deploy before Week 1): the
  retrospective B2-prime result (selected book 178.38→181.13 at fixed
  budget as admitted books rise 5→51) expressed as a weekly prospective
  mechanism — twenty frozen seed books' candidates admitted at the
  registered budget on the registered world blocks. Core combine +
  policy env + live dispatch are implemented and tested (provably
  identical to the incumbent admission at k=5); remaining: CLI
  subcommand, schedule entry, frozen grading spec.

## 5. The question for the second opinion

The operator asked whether the validation rules are suppressing the
baseline. The honest framing:

- **Boom:** no rule withheld anything — the S test showed the +9 pool
  gain does not reach the book (p=0.49) and aims worse. The two-stage
  rule (pool numbers license nothing; book numbers decide) caught a
  false adoption within twelve hours.
- **B2-prime volume admission:** the one place a rule IS delaying a
  measured book-level gain (+2.0–2.75 mean on the corpus). It is
  unadopted because the k-curve was read against outcomes on the same
  54 slates (selection/mining risk), and the program's base rate for
  corpus-positives surviving independent confirmation is poor (CE,
  Gumbel, fast-role, boom-S all failed it). The standing rule routes it
  through a prospective shadow: collect from Week 1, grade weeks 4–6
  (paired weekly-max co-primary), adopt mid-season if it clears.

Options presented to the operator (decision open):
1. Status quo — shadow, grade, adopt if real (~6-week latency; zero
   mining risk). **Recommended.**
2. Real-money split — e.g., 20 of 80 entries from the volume book from
   Week 1 (bounded exposure, faster evidence; money-mix is operator
   territory).
3. Full early adoption at Week 1 (argued against: the k was chosen by
   reading the curve).

A reviewer should pressure-test: (a) is the no-retrospective-adoption
rule correctly applied to B2-prime, or over-cautious given the
monotone dose-response across k? (b) is the entry-split option sound or
does it contaminate the money record? (c) the queue ordering in
`2026-08-19-preseason-test-queue.md`, especially selection-lane
priority (SELECT_LADDER vs regret-targeting vs S1 floor) after the
boom-S null.

## 6. How orchestration works (mechanics a reviewer can verify)

- **Frozen chain pattern** (every scored arm): implement + offline
  tests → outcome-blind reality smoke on real artifacts → freeze a
  protocol doc with pinned SHAs and a preregistered reading → clean-
  archive Cloud Build from the exact commit (`git archive | gcloud
  builds submit`, image tag binds code) → **reuse** one Cloud Run job
  via `gcloud run jobs deploy` + per-execution `--args` (us-central1
  sits at the JobsPerProject quota; job creation is forbidden) → canary
  cell first, halt-and-disposition on failure → 53-cell fan-out with a
  polling chain script writing a durable log in `~/nfl-panels/` →
  create-only GCS receipts per cell → aggregate committed to
  `reports/*-runs/<run-id>/`.
- **Cross-run binding:** arms re-derive their comparators and fail
  closed unless C and S reproduce prior frozen receipts to 1e-6 — three
  independent runs currently share one provable truth.
- **Governance:** one active historical-outcome experiment at a time
  (durable GCS lease with generation-matched acquire/release/abandon);
  fixed budgets and exact pairing; every score-relevant env lever
  registered in `backtest.engine._lever_keys` (test-enforced); no
  production change from any historical diagnostic.
- **Observability:** `chain_status.sh` renders processes (bound to
  their logs via /proc fd), builds, executions, grids, lease, baseline,
  and a live/history-separated event feed; `-b`/`-e` stream build/
  execution logs by polling Cloud Logging (the `gcloud builds log`
  stream reads only the GCS copy, which is empty until completion);
  `--experiments` browses every retained result JSON. A background
  Monitor watches `~/nfl-panels/*.log` and wakes the assistant on
  non-heartbeat transitions.

## 7. Pending operator decisions

1. B2-prime adoption path (the §5 options).
2. SELECT_LADDER utility freeze + one-shot selector amendment (A7).
3. S1 null-gap floor freeze + fresh-seed world block (A6).
4. Deep-history rebuild go/no-go — 2019/2021 (A10).
5. September cadence ownership: Mon/Tue standings downloads are
   LOAD-BEARING (`contest_entries` has never received a row; DK purges
   in ~4 days; they feed the field model and top-N winner sets).
