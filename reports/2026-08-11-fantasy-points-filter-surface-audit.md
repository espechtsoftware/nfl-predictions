# Fantasy Points historical-filter surface audit

Audited against the authenticated live Data Suite catalog and report pages on
2026-08-10 CDT. This is an availability and redundancy review only. It does
not license a new outcome join, model feature, candidate arm, or live policy.

## Material finding

The historical surface is broader than the original full-season exports
suggested. Every standard descriptive report inspected exposes both `Season`
and `Week(s)` filters. The exceptions are the three upcoming-matchup tools:
QB Coverage Matchup and WR Coverage Matchup have `Week(s)` plus a target
`Schedule Week` but no historical `Season`; OL/DL Matchups has `Week(s)` but
no historical `Season`.

Two controlled exports establish the shared week widget's semantics:

- 2025 Advanced Receiving Weeks 1--4 returned 285 player rows with `G<=4`;
  Weeks 5--8 returned 299 with `G<=4`. All 259 overlapping players changed
  on at least one of `G/RTE/TGT/YDS/FP`. Jaxon Smith-Njigba was `G=4,RTE=93`
  in the first window and `G=3,RTE=92` in the second. The exports are exact
  selected-window aggregates, not automatic season-to-date totals.
- 2025 Defense Coverage Matrix Weeks 1--4 and Weeks 5--8 each returned all
  32 defenses with `G=4`, distinct hashes, and materially different shell
  rates. This report also honors exact selected windows.

The successful ignored run manifests are
`20260811T033115Z__advanced-receiving-window-semantics-v1` and
`20260811T033342Z__coverage-matrix-window-semantics-v1`. Their licensed CSVs
remain outside Git.

The broader high-priority audit then verified seven additional report pairs.
Every pair was distinct and every populated `G` was at most four:

| report | player/team rows, Weeks 1--4 / 5--8 | columns |
|---|---:|---:|
| Advanced Passing | 52 / 52 | 59 |
| Advanced Rushing | 101 / 104 | 42 |
| Receiving Man-vs-Zone | 285 / 299 | 26 |
| Separation by Coverage | 392 / 404 | 38 |
| Separation by Alignment | 392 / 404 | 41 |
| RB + WR Efficiency | 344 / 357 | 51 |
| Detailed Snaps | 415 / 430 | 26 |
| Offense Coverage Matrix | 32 / 32 | 22 |

The first bulk attempt exposed an automation hazard: clicking an already
active context tab after choosing weeks reset the page and produced
full-season data. The downloader now selects or verifies context first,
chooses filters second, presses `Apply`, and reopens the Week(s) widget to
assert the exact set before export. The corrected evidence is in ignored run
`20260811T034933Z__high-priority-window-semantics-v1`; its final Offense
Coverage navigation readiness failure was repaired and independently
completed in `20260811T035458Z__coverage-matrix-offense-window-semantics-v1`.
The earlier reset exports are rejected audit artifacts and are not inputs.

## Catalog disposition

| report family | historical filters | incremental value | disposition |
|---|---|---|---|
| Advanced Receiving | Season + Week(s) | recent routes, first reads, air-yard share, XFP and alignment | highest priority; exact-window contract proven |
| Defense Coverage Matrix | Season + Week(s) | recent opponent shell usage; distinct from receiver traits | highest priority; exact-window contract proven |
| Advanced Passing | Season + Week(s) | recent QB process and efficiency beyond mean projection | high-priority schema/window sample, then frozen diagnostic |
| Advanced Rushing | Season + Week(s) | recent contact, concept and explosive-rush process | high-priority schema/window sample, then frozen diagnostic |
| Receiving Man-vs-Zone | Season + Week(s) | same-season receiver scheme performance | high priority paired with defensive shells; require route/dropback support |
| Separation by Coverage | Season + Week(s) | recent receiver performance by shell | high priority paired with defensive shells; sparse cells require support |
| Separation by Alignment | Season + Week(s) | recent slot/wide/inline/backfield effectiveness | medium-high; test only as a complete preregistered family |
| RB + WR Efficiency | Season + Week(s) | recent missed tackles, YAC and explosive-touch rates | medium-high; first remove overlap with Advanced/PBP fields |
| Detailed Snaps | Season + Week(s) | play-type/field-position usage not present in simple share | medium; audit against nflverse before modeling |
| Offense Coverage Matrix | Season + Week(s) | schemes recently faced by an offense | medium; likely secondary to player traits plus opposing defense |
| Passing Depth of Target | Season + Week(s) | recent QB depth distribution | medium-low because PBP/aDOT already cover much of it |
| Separation by Routes / Route Breaks | Season + Week(s) | granular receiver skill by route shape | medium-low; sparse samples, no post-outcome route subset selection |
| Run/Pass Report | Season + Week(s) | situational play-calling | low because PBP and PROE can derive most fields |
| Fantasy Points Allowed | Season + Week(s) | defense-vs-position production allowed | low; mostly derivable from authoritative scoring/PBP |
| Basic Passing/Rushing/Receiving | Season + Week(s) | standard box/PBP production | do not collect; redundant with nflverse |
| Bell Cow / Routes Run | Season + Week(s) | consolidated usage and alignment | do not collect routinely; overlaps rush/target/snap/route inputs |
| Fantasy Points Scored / Weekly FPTS | Season + Week(s) | outcome labels | audit only; never use as a predictor for the same week |
| Weekly Route/Target/Snap Share and PROE | Season + Week(s) | explicit player/team week rows | keep evidence-selected families; lag rows in code rather than exporting many aggregate windows |
| QB/WR Coverage Matchup | no historical Season | vendor current-week matchup grade | prospective pre-lock snapshot only; cannot backtest from this UI |
| OL/DL Matchups | no historical Season | vendor current-week line matchup | prospective pre-lock snapshot only; cannot backtest from this UI |

## Safe next sequence

1. The listed high-priority two-window samples are complete. Before bulk
   collection, freeze the reports and fields that survive outcome-blind
   redundancy/support review; do not equate availability with usefulness.
2. Freeze one window policy before outcomes. The current default candidate is
   last four completed weeks, with explicit minimum-sample shrinkage to the
   season-N-1 prior and no same-week data.
3. Run outcome-blind redundancy/coverage audits against existing nflverse and
   vendor weekly inputs. Do not pay the multiple-testing cost of modeling
   fields that merely reproduce existing data.
4. Preregister one compact diagnostic family at a time. Same-season coverage
   should combine receiver Man/Zone or separation traits with the opposing
   Defense Matrix derived from the project's schedule, never the vendor `OPP`
   field.
5. Treat Week 1 as prior-season only. Treat Weeks 2--4 as small samples with
   frozen shrinkage; never use target-week results in a target-week feature.

This audit expands the plausible value of the purchased data, but it does not
imply that every report deserves weekly operation. The useful distinction is
same-season point-in-time process and scheme information, not the number of
available CSVs.
