# Core v1 score transaction v2 amendment

**Date:** 2026-08-25
**Status:** prospectively frozen and outcome-blind; execution waits for the
accepted T230 v2 panel release

## Purpose

Supersede only the unexecuted operational binding of the first Core v1 score
transaction. The prior `*-v1` run identifiers were prospectively bound to
source `37447b53c5ac71bf36d5323443566ecfac8f9c04` and candidate build
`80963d40-24c5-4da8-af24-c490e33a4ed7`. That image lineage was superseded
before any Core catalog, historical-outcome read, grade, or score artifact was
created. It must never be silently paired with the repaired T230 v2 release.

This amendment does not change Core v1 science, strategies, budgets, slates,
contrasts, score arithmetic, outcome query law, or reporter. It creates a new
transaction incarnation whose names are fixed before the candidate result or
any historical score is observed.

## Frozen upstream binding

- Foundry source panel: the accepted 54-member G0 panel at
  `gs://nfl-predictions-503414-corpus-parametric/research/corpus-parametric-research/panels/20260823-foundry-production-v12/foundry-v12-combined-panel-index-v1.json`,
  generation `1787663639938214`, SHA-256
  `4d41acd9277e525cd8521071b62390281c442d6324db1e3f5812bf59920c16f9`.
- T230 run: `20260825-foundry-t230-production-v2`.
- Image source S2:
  `501b68a4f7b842de1f59d55358540c9a615b6e40`.
- Candidate build:
  `56d64cbe-2d77-4f51-adf8-21b65dbe7b7c`.
- Runtime image: exactly the future digest D2 produced and successfully
  Rule-1-smoked by that candidate, then released without rebuilding from the
  same S2. A failed candidate, different digest, rebuilt release, or later
  source commit cannot satisfy this binding.
- T230 panel release URI:
  `gs://nfl-predictions-503414-corpus-parametric/research/corpus-parametric-research/t230/20260825-foundry-t230-production-v2/foundry-t230-panel-release-v1.json`.
- Reused score-chain job: `atlas-minimal-c-s2023-w1-v1` in `us-central1`.
- Runtime service account:
  `817589974517-compute@developer.gserviceaccount.com`.

## Frozen Core transaction identifiers

- Chain run ID: `20260825-core-v1-score-chain-v2`.
- Catalog ID: `20260825-core-v1-score-catalog-v2`.
- Catalog prefix:
  `gs://nfl-predictions-503414-corpus-retrieval/research/corpus-core-v1/catalogs/20260825-core-v1-score-catalog-v2/`.
- Catalog logical-byte ceiling: `100000000`.
- Outcome run ID: `20260825-core-v1-realized-score-v2`.
- Outcome prefix:
  `gs://nfl-predictions-503414-corpus-retrieval/research/corpus-core-v1-realized/20260825-core-v1-realized-score-v2/`.
- Grade run ID: `20260825-core-v1-realized-grade-v2`.
- Grade prefix:
  `gs://nfl-predictions-503414-corpus-retrieval/research/corpus-core-v1-grades/20260825-core-v1-realized-grade-v2/`.
- Grade logical-byte ceiling: `200000000`.

The retained catalog remains exactly 12 strategies by three budgets
`4/14/80` by 54 slates, or 1,944 immutable book cells. All frozen contrasts
and the `r194:incumbent` baseline remain unchanged.

## Acceptance sequence

1. Candidate build and real Rule-1 smoke close successfully and identify D2.
2. A same-S2, same-D2 release publishes the v2 transport contract.
3. T230 prepare, ordinal-zero benchmark, fixed panel, verifier pass, and final
   panel release close without historical outcomes.
4. Core catalog v2 exact-reads the G0 and T230 v2 release and freezes all
   1,944 books before any outcome access.
5. One historical-outcome lease and one fixed query create/reopen the v2
   player/DST snapshot.
6. The Core v1 grader scores every shared-union roster once, projects all
   books, publishes all 54 grade shards and contrast summaries, and publishes
   terminal `completion.json` last.
7. Only the completed grade may be reported as evidence of realized scoring
   improvement; the candidate smoke and benchmark remain outcome-blind.

The old `*-v1` Core transaction names remain unused historical declarations.
They are not aliases, fallbacks, recovery targets, or valid inputs to v2.

## Terminal operational disposition

Candidate build `56d64cbe-2d77-4f51-adf8-21b65dbe7b7c` failed before the
image-build and Rule-1-smoke steps. It produced no D2 and can never satisfy the
frozen upstream binding above. Consequently these Core `*-v2` transaction
identifiers are also unused terminal declarations and must never be launched,
rebound, aliased, or recovered. A fresh prospective Core transaction
incarnation must bind the successor T230 candidate before its outcome is
known.
