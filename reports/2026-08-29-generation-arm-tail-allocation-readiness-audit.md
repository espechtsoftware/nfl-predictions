# Generation-arm tail-allocation retrospective: readiness audit

**Date:** 2026-08-29  
**Decision:** **HOLD — the requested walk-forward allocation comparison is not
validly runnable from the artifacts currently local to this workspace.**

This is a data-availability and estimand problem, not a reason to abandon the
idea. Running it now would quietly substitute selected-book tags or overlapping
lineup ancestry for generation exposure and would produce a number that does
not answer whether solver budget should move between arms.

## What the test must observe

For an exposure-normalized generation-arm retrospective, every generated event
must be recoverable as:

`season, slate, arm/version, ordered visit, roster, solve status, realized score`

The ordered visit is necessary to replay a smaller or reallocated budget
without looking at outcomes. A deduplicated lineup may belong to several arms,
so `lineup -> set of source arms` is not a replacement for exact per-arm visit
rows. Walk-forward weights for season `S` must be fitted only on seasons before
`S` and then frozen before season `S` is evaluated.

## Local artifact audit

| Local artifact | What is complete | Why it is insufficient |
|---|---|---|
| `reports/six-season-replay-lineups.csv` | 2,139,326 bytes; SHA-256 `21c59b51e13fc2412e04a48c201b5fbe5b671a03b52735cf38bb35e31285dd6a`; exactly 4,280 selected lineups, 40 per week over 107 weeks in 2019 and 2021–2025; each selected lineup has one of `boom`, `dark`, `game`, or `lev` and a realized score. | This is the **post-selector 40-entry book**, not the generated candidate population. It contains no unselected candidates, attempted solves, visit order, or nominal arm work. Tail rates from it would measure the generator *through the old selector*, not generation yield. It also has no 2020 season. |
| `reports/entries_study/e150_lineups_2023.csv`, `...2024.csv`, `...2025.csv` | Exactly 2,700 selected lineups per season (150 per week) with tag, realized score, and selection index. | These are also post-selector books, cover only 2023–2025, and come from a different run/law than the six-season export. They cannot be pooled with that export as additional generation exposure. |
| Tracked R6 score report | `reports/r6-full-union-realized-runs/20260826-foundry-v12-r6-full-union-realized-v2/score-report.json` is a complete selector-level summary over 54 slates. | It contains strategy summaries, not the 199,244 lineup rows or the 378 ordered arm-result streams. |
| Local R6 task-0 envelope | `/tmp/r6-current-bank-task-result-00.json`; 19,417,135 bytes; SHA-256 `f865949525ea1460c04b91476ec04b2ad88e52ee4c3484fbc391f6cfc79a32e7`. It proves that task 0 can expose constraint-profile membership by block. | It is only `2023-w01`, is temporary rather than durable, contains no realized outcomes, and retains arm/block summary provenance rather than exact per-arm visit rows. |
| Local task-0 incumbent arm result | `/tmp/hard230-r6-2023-w01-p0-result.json`; 250,034 bytes; exact source SHA-256 `da82b4a3b5b759d4a2c2ddfb65ea2270d09a18bf71edf43bc466872aaa3df738`. It has the incumbent arm's ordered 1,000 visits for one slate. | It is one of the required 378 arm/slate bodies: one profile and one slate. It has no realized labels and no `boom`/`dark`/`game`/`lev` family membership. |
| Local later-source freeze | `.scratch-score-sprint/outcome-successor/later-source-freeze.json`; 4,566,802 bytes; SHA-256 `c63251a3dee0b455502a8e37d03c731c671457b9b17ff41dd9249edb0bae654a`. | It inventories the five world artifacts and incumbent candidates. It is not the seven-arm ordered generation ledger and does not attach per-arm realized scores. |

The two selected-book exports demonstrate the confounding directly. In the
six-season 40-entry file, the selected exposures are `boom=2,789`, `dark=614`,
`game=380`, and `lev=497`; the observed 200+ counts are respectively
`13, 2, 2, 3`. At 220+ and 230+, only three selected `boom` lineups appear.
Those sparse, selector-conditioned counts cannot support a stable per-arm GPD
shape estimate or a generation-budget conclusion.

## Frozen R6 bodies that exist but are not local

Only small identity summaries for the following immutable bodies are present
in this workspace:

- R6 panel freeze: generation `1787756181440564`, SHA-256
  `57844386a3da86ddf05f8b3e6b19ae19c7327afcfc1057647b210e58caec2467`,
  89,879 bytes.
- Realized grade root: generation `1787823913707002`, SHA-256
  `7e5da240f6ad3978553fa3101e12d4414c993f9547bb76cfa999cf32acdb6dfc`,
  5,480,030 bytes.
- Attribution root: generation `1787852572673874`, SHA-256
  `caaddba5ef709b1e4df8c60480e2a50a37063917ef9b8d3c788f5e107133722b`,
  114,551 bytes at
  `gs://nfl-predictions-503414-corpus-retrieval/research/corpus-r6-full-union-attributions/20260827-foundry-v12-r6-full-union-attribution-v1/attribution-release.json`.
- No-rescore funnel release: generation `1787859076719874`, SHA-256
  `782a1d88c27b3160e3f91f8c8efcf07d92ab7d5f5ef60c90bca4712449bdfcbb`,
  2,448,874 bytes at
  `gs://nfl-predictions-503414-corpus-retrieval/research/corpus-r6-no-rescore-funnels/20260827-r6-no-rescore-funnel-v1/no-rescore-funnel-release.json`.

The 54 attribution shards would provide realized score plus the set of
constraint profiles and blocks that produced each deduplicated lineup. They
would **not** by themselves close the exposure gap. Their frozen schema
deliberately declares:

- `candidate_provenance_resolution = arm-block-count-summary-only`; and
- `exact_generation_occurrence_rows_available = false`.

The lineup row contains aggregate occurrence count by block and source-arm
sets by block, but not the count or ordered visit stream for each arm. The 378
original source arm results contain the ordered visits needed to reconstruct
that stream, but 377 of those bodies are not local. This audit was explicitly
restricted from cloud reads, so they were not fetched.

## Additional scientific blockers

1. **No prior-season panel for the seven R6 profiles.** The complete R6
   realized panel is 2023–2025. It cannot implement the planned 2019–2022 fit
   followed by 2023–2025 evaluation. At best, after recovering exact visit
   rows, 2023 could train a 2024 allocation and 2023–2024 could train 2025.
2. **The arm taxonomies are not crossed.** `boom/dark/game/lev` belong to the
   legacy generator; the seven R6 arms are constraint profiles applied to one
   world scheduler. Current artifacts do not identify both dimensions for the
   same candidate population.
3. **The upper tail is too sparse for separate GPD fits.** The entire pooled R6
   corpus has only 279 lineups at 200+, 34 at 220+, and 7 at 230+. Splitting
   those overlapping rows by arm and prior-season fold is not enough support
   for defensible profile-specific shape parameters. Threshold rates with a
   predeclared hierarchical shrinkage law are more realistic; a GPD component
   must fail closed when its prior-fold support gate is not met.
4. **Full-budget unequal allocation is outside the frozen support.** Each R6
   arm has only 1,000 ordered visits per slate. At the existing 7,000-solve
   total, equal allocation already consumes all seven arms' frozen support.
   A favored arm cannot receive more than 1,000 without new generation. The
   frozen artifacts could support a lower-budget prefix experiment (for
   example 3,500 total solves with 500-per-arm control) after the 378 streams
   are staged, but not an unequal 7,000-solve comparison.

## Smallest honest route to the test

1. Exact-stage the already-frozen 54 attribution shards and all 378 source arm
   result bodies locally; this is read-only recovery, not a new outcome query
   or population run.
2. Build one deterministic occurrence sidecar keyed by
   `(season, slate_id, arm_id, visit_index, lineup_id)`, joining realized score
   only after the ordered generation rows are frozen.
3. Run a **constraint-profile-only** prefix retrospective for 2024 and 2025 at
   a total budget supported by the frozen prefixes. Freeze each allocation
   from prior seasons, compare it with equal allocation at identical total
   visits, and report 194/200/220/230 unique-yield rates and weekly corpus
   maxima. Do not call ancestry a causal arm effect.
4. Treat GPD shape as unavailable unless a predeclared prior-fold support gate
   passes. Use shrinkage-smoothed threshold yields as the primary allocation
   signal in this sparse panel.
5. Test `boom/dark/game/lev` separately only after a full legacy candidate and
   solve-exposure ledger is located or regenerated. Do not use the selected
   40/150-entry exports as that ledger.

No analyzer or score report was generated from the incomplete inputs. That is
the only result consistent with the requested no-cloud/no-new-outcome scope.
