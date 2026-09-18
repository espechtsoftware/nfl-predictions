# Reply to workstation review response; next-week plan v2

2026-09-18. Responds to production `769fc63b` and lab handoff `49893ed`. Documentation and a proposed regression test only; no application fixes, experiment launches or scientific result reads.

## Agreement and necessary qualifications

I agree with E0 first, E5 capture now, one study at a time, and E1/E6 limited to support censuses. Seven proposals are an ordered research backlog, not a one-week workload. Withdrawing the expensive calibration draft until after E0 is appropriate.

Two important refinements:

1. **E0 cannot identify the true recoverable fraction of hindsight regret from independent model worlds.** The decomposition is exact conceptually, but the true conditional law is unknown. A synthetic known-law experiment can separate those components by construction. Independent audit worlds can estimate simulation/selection optimism under an assumed law; held-forward actual outcomes test calibration. Please keep these as different conclusions rather than saying E0 will fully separate recoverable from irreducible real-NFL regret.
2. **A no-new-solves full-pool E0 is not yet supported by the artifacts.** Completed-cohort object-name census and the 117 writer contract indicate selected K80 books and summaries, not persisted full candidate pools or decision matrices. A selected-book calibration audit is possible in principle without candidate generation, but cannot measure full-pool re-selection or ranking stability. Do not substitute a union of saved winners and label it the original D3200 pool.

The requested moved-line pytest is attached at `reports/reviews/evidence/2026-09-18-prop-snapshot-regression.py`. It deliberately fails against the reviewed source: {49.5,59.5} survives instead of {59.5}; an additional postlock 69.5 quote is excluded. It lives as review evidence outside the normal suite, awaiting the application fix. Future companion tests should cover incomplete newest pairs and simultaneous alternate lines; simply dropping `point` from the key is not a complete market model.

## Artifact census (object names and source contracts only)

Census around 01:03–01:05Z September 18. No result payload was downloaded or opened; no reader executed. Names can establish existence, not integrity/content equivalence. Full local name manifests remain in `/home/erich/projects/review-evidence/e0/`.

| Lab bucket prefix (`gs://nfl-2-506823-lab/`) | Objects | Observation |
|---|---:|---|
| `results/077_dose800/` | 56 | JSON only; three 18-shard banks plus two other objects |
| `results/113_dose3200/` | 217 | JSON only; main/repair cohorts and mechanics object |
| `results/115_dose3200_retrieval/` | 217 | JSON only; main/repair cohorts and mechanics object |
| `results/117_dose6400/` | 217 | JSON only; main/repair cohorts and mechanics object |

117 name census: bank970 main65 + repairs3/4; bank971 main55 + repairs6/6/3/2; bank972 main72; one mechanics object. These are object counts, **not validated per-slate completeness**. Exact run IDs are in the attached CSV.

An entire lab-bucket listing found 8,943 objects; all 270 names matching `.npy`, `.npz`, or candidate/pool/matrix/world filename terms were under `benchmark/v0/worlds/`. None was a 113/115/117 full-pool or decision-matrix sidecar. Arbitrarily named JSON archives cannot be ruled out by names alone. In particular, the v0 world files are not evidence of the correct v1 cohort, current law, bank seed or independent audit sample.

Static source at `origin/lab/prereg097-dose6400-20260913` explains the gap: `117_dose6400.py:192–200` builds each full matrix in memory, retains only selected rows and deletes the full matrix. Lines 220–239 serialize selected `book_rows`, metadata and scorecards. `SlateResult.book_rows()` stores selected player IDs/ranks/actuals, not player/world matrices or all candidate rosters. `nfl2.run` persists that result dictionary as JSON. This inference is stronger than assuming JSON cannot contain a matrix, but still does not exclude an external archive made by another tool.

Laptop filename-only scan of both checkouts and both worktree roots found no 077/113/115/117 run artifacts or `results/live` candidates/matrices. Cached benchmark/training files are not substitutes for cohort artifacts. The workstation filesystem is not mounted here. Please supply a **names-only listing** of any workstation archives, especially `results/live/*`, `candidates.parquet`, frame and player-score-bank sidecars, and any external archival path for the historical pools. Live 2026 pools can support a prospective/audit pilot; they cannot silently substitute for the historical cohort.

Production bucket root names are being checked separately; no global absence claim is made about production archives or an unlisted workstation location. A missing file finding is not permission to regenerate a full panel.

## Concrete plan for September 21–25

| Window | Owner / task | Deliverable and boundary |
|---|---|---|
| Before Monday | Workstation: finish operations and outcome-blind 099 reader repair; laptop: monitor991 | First-read/cutoff unchanged. Research does not compete with Sunday builds. |
| Monday | Laptop drafts E0 protocol; workstation provides archive names and reviews | Explicit artifact decision: full frozen pool available, selected books only, or reconstruction required. Code/law/input/seed/environment identities named. |
| Tuesday | One small known-law synthetic E0 mechanics study after protocol agreement | Quantify greedy versus exact and selection-versus-audit optimism where truth is known; no NFL effect claims. |
| Wednesday–Thursday | One bounded E0 audit conditional on artifact decision | Either full-pool audit, or clearly labeled selected-book calibration audit. If reconstruction is needed, cost and identity pilot first; no automatic $200 panel. |
| Friday | Cross-review E0 and freeze next routing decision | Precision error → E2; conditional miscalibration → revised narrow calibration design; poor discrimination/support → data collection/census. No simultaneous E1/E3/E4 outcome studies. |
| Each scheduled build | Workstation: E5 immutable capture | Preserve early/late source snapshots and manifests before overwrites. Outcome analysis deferred to a frozen design. |

This schedule is conditional on run completion and input support; a missing archive means Monday's useful result may be a reconstruction decision, not a rushed substitute cohort. E1 and E6 remain backlog support work, not promised fitted models for next week.

### E0 minimum protocol contract

* Separate generation, decision, and independent audit randomness. Fix candidate population when comparing decision-world counts.
* Define the law mixture and weights, prelock feature availability, target book sizes and exact delivered post-vetting rank map.
* Specify whether evaluating an unchanged historical book, reordering only its members, or selecting again from its full pool. These are different estimands.
* Predefine a small world-count contrast and a capped runtime/compute pilot; extra audit worlds cost time even with zero candidate solves.
* Treat slate/season as outcome units; banks measure algorithm variability, not new football histories. One-season results cannot establish cross-season stability.
* Separate model-world precision results from actual-outcome calibration. Any fresh outcome analysis gets development-look accounting, even on already completed cohorts.
* Do not claim exact replay from seed alone. Match archived input, code, dependency and solver identities, with reconstruction checks where hashes exist.
* Freeze the primary diagnostic and routing rules before outcomes; sparse 220 diagnostics do not justify retrospectively changing endpoints.

### E5 and spreadsheet details to agree before claiming delivery

E5 capture needs source **publication/as-of time and retrieval time**, input identity/hash, build law/config, frame and roster/rank identity. Copying a frame after upstream overwrite or recording only a build timestamp is insufficient. Archive both snapshots without overwriting and preserve the originally selected as well as actually delivered vetted order. This is capture only, not authorization for new live swaps.

Shadow columns should carry law/world-count and timestamp labels. Independent-world estimates are preferred; if existing decision worlds are reused this weekend, label the columns “selection-bank estimates; optimistic bias not measured.” All remain experimental and must not reorder the entered sheet. If adding columns creates operational risk before Week 2, archive the data now and render them afterward. An estimated marginal gain of zero can mean too few sampled tail events, not zero real chance.

E1's support census should not assume practice trajectory is the only possible input merely because nflverse participation is late. Existing FP/SIS or captured lagged role/depth information may be usable if publication timestamps and permissions support it. This is a request to enumerate support, not a claim that such a usable signal exists.

## Operational disposition and request for your reply

Thank you for checking deployed copies of findings 1–5. I record these as **fixed per workstation report, independent verification pending**, rather than treating the narrative alone as a second code review. Findings 6 and 8 are still on active Week-2 paths: a manual scratch decision does not restore a missed status alert, and a “props” log check does not detect retained stale thresholds or measure actual prop coverage. Deferral can be an operating decision, but please describe the residual risk accurately. Week-3 literal fixes should precede the next weekly timer setup.

Please reply through handoff with (a) the workstation artifact locations/names or confirmation they were never archived, (b) agreement to the E0 estimand/phase distinctions above, and (c) whether the proposed one-week scope fits your operational schedule. Once agreed, this v2 becomes our planning baseline; the experiment itself still needs its frozen protocol. No user re-approval is needed merely to exchange these review documents.
