# Orchestration takeover and handover review

Date: 2026-08-18
Author: Claude (Fable 5), orchestrating from this date
Reviewed document: `reports/2026-08-18-handover-state-and-proposed-direction.md`

## 1. Verification of the handover's claims

Verified against code and ledger before accepting the takeover:

- DST zero-variance: CONFIRMED (`live_lineups.py:334` `draw_idx=-1`;
  `production_policy.py:176` `DST_CORR_DRAWS=""`; `_row_draws` docstring).
- Minimal ATLAS C-test target: CONFIRMED
  (`engine.py:1067` `boom_order = np.argsort(rd.sum(axis=0))[::-1]`).
- ATLAS circularity argument: sound; disposition record consistent.
- HANDOFF.md was stale at review time (last touched `eed48f8`; the
  contest-fills deploy `46cc871` and gate-5 finding `0ac819d` were not
  reflected). Corrected in the 13:20 update.

## 2. Material omission found

The handover presents DST zero-variance as "the only verified structural
omission" without citing the ledger's `DST_CORR_DRAWS` record (system-study,
2026-08-01 cycle): **tested twice, negative both times**, including a refit
to measured moments (corr -0.491, rel-sd 0.93, 4,390 team-games 2018-25) at
186.5/5-17 versus comparator 189.5/8-17, with the recorded verdict "constant
DST projections in entry selection are not a deficiency." Old universe / old
law, so the verdict does not transfer and the lane is reopenable — but the
prior is materially worse than the handover stated, and any D-series
protocol must engage this record explicitly.

## 3. Answers to the handover's §8

1. **DST lane (§7.2(1)):** not as scoped. Outcome-based sizing step first
   (DST points-above-projection inside the existing H/P hindsight solves,
   54-slate corpus, no simulator trust required). If sized worthwhile,
   acceptance = improvement in the frozen tail-calibration audit's
   194-over/210-under shape, never simulated coverage; fit to upstream
   co-movement moments, never to the 54 realized book-tail counts. Note the
   DST fix and the QB-hub coupling repair are the same lane: both thin the
   simulated extreme tail and both predict the observed 210-under shape.
2. **Weak surrogate vs six bad ideas:** the dichotomy under-describes the
   situation because the realized gate is also underpowered (binomial sd ~4
   on 107-slate clear counts). Record re-read: 2-3 clear negatives
   (fast-role 11v17, fixed-budget Gumbel 20v27, hierarchical 23v27), one
   measured-worse (Schaake), two nulls (plain Gumbel and CE at 26v27).
   Either horn yields the same program: simulated deltas cannot license
   adoption, realized deltas under ~8 slates cannot either; the escapes are
   structural corrections, prospective data, and effects large enough for a
   low-power gate (CBWU-OI's 11->18 at >=194 is the only member so far).
3. **Tail-calibration lane:** real under tight scope — every gate runs
   through the instrument and its shape error is twice-independently
   confirmed. Guardrails: structural/upstream-moment repairs only; accept on
   the frozen calibration audit; timebox — if the QB-hub repair does not
   move the 210 shape, do not iterate into an open-ended program.
4. **Process diagnosis:** split verdict. Governance is not the pathology
   (it caught three invalid arms; zero adoptions is honesty at this power).
   The pathology is execution engineering: 4 of 6 ATLAS attempts died to
   mechanical causes. Remedy adopted: mandatory cheap preflight (single-cell
   canary, config/spec lint, memory headroom) before any multi-cell grid,
   and an infra-vs-science retry distinction that preserves the zero-retry
   science contract. On ATLAS specifically, the deeper miss was that the
   sort-key/eval-metric tautology was identifiable at protocol-freeze time,
   before any compute; a tautology audit joins the preflight checklist.

## 4. Operator decisions (recorded 2026-08-18)

1. D0 gate 3: bounded-mismatch acceptance; components fitting; freeze
   before treatment effects.
2. DST lane: sizing step first.
3. Minimal ATLAS C test: run it, through preflight canary.
4. Coherent-market-state: release now.

## 5. Actions taken at takeover

See HANDOFF.md 2026-08-18 13:20 for the full record: coherent chain
released (parity launched from pinned worktree `/tmp/nfl-parity-fa90ff7` at
`fa90ff7`, census key repair frozen at
`reports/2026-08-18-atlas-parity-census-key-repair.md`), both dead watchers
restarted, pytest collection defect fixed (`pythonpath = ["."]`).

Post-reboot recovery commands (state files resume; safe to rerun):

```bash
setsid nohup bash ~/nfl-panels/parity-finish-driver.sh \
  > ~/nfl-panels/parity-finish-driver.log 2>&1 &
cd /tmp/nfl-coherent-cde9c60 && setsid nohup bash \
  scripts/watch_coherent_market_state_queue.sh \
  74f048df-1b8a-4b96-962b-f642deacb606 \
  cde9c600d4d33e4d9bceae442af09b137fb4588a \
  us-central1-docker.pkg.dev/nfl-predictions-503414/nfl-dfs/nfl-dfs:coherent-market-state-cde9c60 \
  > ~/nfl-panels/coherent-scorefree-watcher-20260818.log 2>&1 &
cd /home/erich/projects/nfl-predictions && setsid nohup bash \
  scripts/watch_coherent_market_state_historical_score_queue.sh \
  4ce80f20-a976-436c-9276-1e45c306aff9 \
  ae9780b3d52037b014031c7982912afb204d265d \
  us-central1-docker.pkg.dev/nfl-predictions-503414/nfl-dfs/nfl-dfs:coherent-market-historical-ae9780b \
  > ~/nfl-panels/coherent-historical-watcher-20260818.log 2>&1 &
```

If either worktree is missing after a reboot: recreate with
`git worktree add --detach /tmp/nfl-parity-fa90ff7 fa90ff7…` /
`git worktree add --detach /tmp/nfl-coherent-cde9c60 cde9c60…`, re-symlink
`.venv` and the live run dirs to the main checkout (parity worktree
additionally needs the two repaired scripts copied from `main` — SHAs in the
census-key repair note), then rerun the commands above.
