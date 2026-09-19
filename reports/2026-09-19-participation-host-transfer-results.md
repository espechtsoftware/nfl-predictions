# Participation selection improves again on the actual deployed inputs

Using the overnight deployed projections and the workstation's unchanged historical cache, full participation-aware selection raises the modeled chance of at least one 220+ lineup in the 97-entry book from **10.730% to 13.155%**, with expected maximum **193.010→196.408**. Both component simulators agree on the whole-book improvement. This closes the previous research-input lineage gap on the fixed 1,600-candidate pool; the actual operating full corpus and later morning refresh remain untested.

The first delivered lineup now changes, unlike the earlier research-input comparison. Its expected score rises **133.329→148.504**, but the component simulators disagree on its P220 change. This is a promising ordering observation, not proof of a better Millionaire winner.

## Fixed comparison and source reconstruction

The actual deployed D160 proof saved a 428-player frame and both selection banks at clean lab `2dc116c`, using the exact workstation cache `8aaa5daf…672b072b7` and production batch `2026-09-19T06:29:00.515884Z`. Its ordinary selected order and stored selection means reproduce exactly. We borrowed the original D1600 candidate pool without generating or adding candidates. Every one of those 1,600 candidates remains legal and scoreable on the actual frame. Michael Carter is absent from the new universe but was in none of the candidates.

The original incumbent bank and original hsim bank each reproduce **bit for bit** from their saved fitted components/calibration and authenticated historical inputs. Fresh audit seeds are incumbent 14260919 and hsim 15260919. Full-rule participation masks use the fixed prior map, selection seed 20260919054 and new audit seed 20260919056. The provider-bound 12:42:10 UTC status capture is replayed as of its recorded cutoff; it is not represented as a fresh collection.

The [version 2 protocol](2026-09-19-participation-host-transfer-v2-protocol.md) and [input manifest](reviews/evidence/2026-09-19-participation-host-transfer-v2-inputs.json) froze at **46961b8b** before the real comparison. The first synthetic rehearsal failed because the smaller player universe changed the vetter's exact query parameters. Version 2 derives authenticated subsets of the old captures, removing only Carter, and retains their original provenance. It passed a complete synthetic selection/delivery smoke. The failed version 1 artifacts remain preserved; no real comparison was read before the repair.

## Independent simulation audit

Whole-book full minus ordinary under participation uncertainty:

| Audit | Expected-max change | P220 change |
|---|---:|---:|
| Incumbent |+3.863|+2.450pp|
| Hsim |+2.933|+2.400pp|
| Equal mixture |**+3.398**|**+2.425pp**|

Mixture Monte Carlo 95% intervals are **[3.274, 3.522] points** and **[2.164, 2.686] pp**. These describe simulation noise for fixed model assumptions, not real football uncertainty or participation-map error. The books share 51 of 97 members. Flowers exposure falls 38→0 and Tagovailoa 4→0 through optimization rather than hard bans; material-risk lineups fall 59→17. Both books have zero hard-vetted rows.

The all-active cost remains: full minus ordinary is **−3.029 expected-max points and −3.405 pp P220** if all designated players play. Confirmed-active Sunday information cannot be replaced by Saturday nonparticipation priors.

## Actual delivered regions

All changes below use the unchanged vetter's delivered order under full participation uncertainty. Probability changes are percentage points.

| Region | Expected-max change | P220 change |
|---|---:|---:|
| First lineup |+15.175|+0.665pp|
| First 10 |+0.913|+0.305pp|
| First 30 |+0.535|+0.195pp|
| Ranks 2–24 |−0.042|−0.305pp|
| Rank 25 |+6.231|+0.095pp|
| Ranks 26–30 |+1.712|+0.240pp|
| Rank 31 |+4.857|0|
| Ranks 32–33 |+0.488|+0.030pp|
| Ranks 34–43 |+2.030|−0.495pp|
| Ranks 44–53 |+9.784|+0.620pp|
| Ranks 54–63 |+9.185|+0.720pp|
| Ranks 64–79 |+13.444|+1.500pp|
| Ranks 80–95 |+5.832|+1.775pp|
| Ranks 96–97 |+10.249|+0.210pp|

First-30 mixture P220 now has a positive Monte Carlo interval, **[+0.014, +0.376] pp**, although each component's individual interval includes zero. The first-lineup P220 change is **−0.060 pp incumbent versus +1.390 pp hsim**; its positive mixture should not hide that disagreement. Ranks 32–33 also have opposite expected-max component signs despite the positive mixture. Losses in ranks 2–24 and 34–43 remain on the record.

The full first lineup is the Stroud/Bijan/Javonte/Chase/Jefferson/Bourne/Hutchinson/Schultz/49ers roster. It already appears **second** in the ordinary vetted book. Ordinary's first is the Mayfield/Irving/Javonte/Watson/Egbuka/Jefferson/Otton/Fannin/49ers roster. This illustrates a separate ordering issue: after risk demotion, retaining portfolio-greedy order does not guarantee the strongest standalone lineup comes first. Any general head-ordering change needs its own frozen rule and all affected contest-block comparisons; this report does not choose a row swap after inspecting the audit.

## Recommendation

Full participation-aware reselection remains the strongest tested candidate for portfolio review. Keep ordinary as the co-run control, use current Sunday availability, and repeat on the completed full operating corpus. Separately retain the [ordinary DK-confirmed-out reselector](2026-09-19-prelock-dk-reselection-review.md), which can replace affected candidates without generating another corpus or changing the selection objective.

The main real transfer run took 20.81 seconds. A portable local replay regenerated both audit banks and reproduced every selection, delivery order and numerical result exactly. [Full result](reviews/evidence/2026-09-19-participation-host-transfer-result.json), [published and download-verified bundle](reviews/evidence/2026-09-19-participation-host-transfer-publication.json). Independent workstation replay is requested. No entry, timer, model or warehouse change follows from this diagnostic, and no current scoring outcome or bank 991 is an input.

Operational follow-up: [adapter version3](2026-09-19-participation-reselection-use-time-review.md) adds clean runtime selection and repeats availability checks at the real output clock. It leaves these frozen as-of numerical results unchanged. Availability masks also leave teammate workload and forecasts unchanged; that remains a model limitation.
