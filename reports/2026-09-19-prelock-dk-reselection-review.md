# Reselect from the saved corpus when DraftKings confirms a player out

An ordinary-selector preview is now implemented and rehearsed. It can remove every saved candidate containing a freshly DraftKings-designated OUT/IR player and select 97 legal replacements from the remaining corpus. This addresses a practical gap between a long-running build and Sunday lock without generating a new corpus or changing the scoring objective.

The real September 19 13:22:54 UTC capture produced **the exact original 97-lineup CSV, byte for byte**: no newly excluded player was present in the 1,600-candidate rehearsal. A separate hypothetical engineering check removed candidates containing two currently doubtful players and recovered 97 unique legal lineups from 1,053 eligible candidates. That check changed statuses only in memory; the players were **not reported out**, no source capture was edited, no entry book was emitted, and no scoring gain was measured.

## What it does

The [runner](reviews/evidence/2026-09-19-prelock-dk-reselect.py) reads the public DraftKings draftables response for group 153428. It preserves the raw response, server Date, collector times, SHA256 and normalized rows. The source must be no more than ten minutes old both before reselection and before output, and every game must still be unlocked. It rejects contradictory slot variants, missing identities, changed salaries/positions/draftable IDs, unknown statuses and retained players marked disabled or unswappable.

Only DK `O`, `OUT` or `IR` excludes a player. `Q` and `D` remain eligible. No status is inferred from whether a lineup announcement is available. This is separate from participation-mixture selection and requires neither its probability map nor injury-feed agreement.

The runner authenticates the two saved player-score banks, requires a clean runtime checkout at `2dc116ce95647a776ba9c36cf194f44d022d03a4`, and exactly reconstructs the source ordinary selector and stored selection means. It then uses the same ordinary `dual_emax` greedy objective on the eligible saved candidates. Every output lineup must satisfy the existing salary, stack, bring-back and roster rules. Insufficient candidates cause refusal. All output goes to a new directory labeled `RESEARCH_PREVIEW_NOT_ENTERED`.

## Evidence

- Final runner SHA256: `a2a240aa4a44d15bc8f973246722dc986978ceda9a8af69dccd3420d7f6c82cf`.
- Final real capture: 670 unique DK players, received `2026-09-19T13:22:54.314272Z`; raw SHA256 `da90b15600a7ddb9fdecc8b2bb54eaa518922e1c9ea8937cfd8db3cb12113e7d`.
- Real result: 1,600 eligible candidates, no exclusions, 97 unique legal rows, original control exact and all 97 members unchanged. CSV SHA256 `78ebc2e01d069e9eed1602df3bda47f992a636a59adeb17f1d411ca98726090e` matches the source.
- All 20 focused tests pass on the final runner. They cover raw/normalized identity, source freshness, game lock, contradictory DK slot variants, identity changes and exclusion boundaries. The real run also exercises the added clean-runtime guard.
- The hypothetical two-player exclusion smoke used the initial runner SHA256 `5490b8ce260cd57f6cf2cbb92b2d48edad2391060d199cbf9ef163650b783c3d`, before the runtime-checkout guard was added. Its receipt is retained under that identity rather than attributed to the later source. The selector logic did not change.
- Follow-up requested by the workstation: the same hypothetical exclusion path also passes against the **final** runner SHA256 `a2a240aa…d7f6c82cf`, using a separate fresh real capture and in-memory-only hypothetical labels. It again yields 1,053 eligible candidates and 97 unique legal selections with zero excluded exposure. [Final-source smoke receipt](reviews/evidence/2026-09-19-prelock-dk-final-exclusion-smoke.json). No entry book is emitted by either smoke.

[Final capture receipt](reviews/evidence/2026-09-19-prelock-dk-final-capture.json), [final reselection receipt](reviews/evidence/2026-09-19-prelock-dk-final-reselection.json), [hypothetical exclusion receipt](reviews/evidence/2026-09-19-prelock-dk-exclusion-smoke.json), [tests](reviews/evidence/test_2026_09_19_prelock_dk_reselect.py).

## Use and limits

Run with the production environment, `GCP_PROJECT=nfl-predictions-503414`, and single-thread numerical-library limits. From this production checkout:

```bash
python reports/reviews/evidence/2026-09-19-prelock-dk-reselect.py capture /new/capture-directory
python -X cpu_count=1 reports/reviews/evidence/2026-09-19-prelock-dk-reselect.py reselect \
  --lab-checkout /clean/lab-checkout-at-2dc116c \
  --run /completed/ordinary-live-week-run \
  --capture /new/capture-directory \
  --output /new/reselection-preview
```

The run must include both A5 player-score sidecars. The scheduled full builds already request them. A synthetic capacity check of **two complete 12,800×20,000 selector passes** took **109.44 seconds total** (54.04 and 54.52 seconds), with peak RSS about 1.31 GiB. The repeated selections matched exactly. This exceeds the current 12,560 attempt count, but excludes complete artifact ingestion, network delays and delivery, and is not an actual full-corpus run. [Capacity receipt](reviews/evidence/2026-09-19-prelock-dk-capacity-smoke.json).

Selection time grows with corpus size; if the capture expires, preserve the incomplete attempt and obtain a new capture before an explicitly reconciled new run. Do not relax the freshness guard.

This is a pre-first-lock preview, not a post-lock swap tool. It does not certify official active players, redistribute an absent player's workload, update forecasts, introduce missing candidates, vet/reorder for contests or upload entries. The actual full corpus still needs its own run and delivered-book review; this rehearsal is D1600. Use this capability to prepare an auditable alternative if fresh DK exclusions occur. It does not establish better 220+ scoring by itself.
