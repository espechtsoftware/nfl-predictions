# The participation gain is mostly about doubtful players; the narrower rule still has costs

A fresh independent simulation audit confirms the original full participation result: on the same 1,600-candidate pool and 97-entry book, modeled P220 rises **10.180%→12.570%**, and expected maximum rises **3.511 points**. Accounting only for doubtful players recovers most of that improvement, but performs worse than the full rule under the full participation assumptions. It does not remove the contest-level tradeoffs.

This is a model sensitivity test, not newly observed NFL performance. We did not fit a new probability map or change player forecasts, candidates, dose, threshold or contest assignment. The first delivered lineup remains identical for ordinary, full and doubtful-only selection.

## What the fresh audit found

All entries below evaluate the entire 97-lineup book under the **full participation** audit assumption. Probability changes are percentage points, not relative percentages.

| Selection rule | Expected maximum | P(220+) | Emax change from ordinary | P220 change |
|---|---:|---:|---:|---:|
| Ordinary |192.406|10.180%|—|—|
| Full participation |195.918|12.570%|+3.511|+2.390pp|
| Doubtful only |195.529|12.215%|+3.123|+2.035pp|
| Questionable only |192.532|10.205%|+0.126|+0.025pp|

For full participation versus ordinary, the paired Monte Carlo 95% intervals are **[3.390, 3.633] points** and **[2.129, 2.651] pp**. Both component simulators agree: incumbent Emax +3.705 / P220 +2.030 pp; hsim +3.318 / +2.750 pp. These intervals quantify fresh simulation noise with fixed laws and map. They do not cover real football uncertainty or probability-map error.

Doubtful-only versus full loses 0.388 expected-max points (interval [−0.464, −0.312]) and 0.355 pp P220 ([−0.518, −0.192]); both component signs agree. The questionable-only rule leaves the main doubtful exposure problem in place and gives no clear whole-book P220 gain. Its first delivered lineup is worse by 10.774 expected points in this audit, so it is not an attractive way to improve the top entry.

## Why the distinction matters

Ordinary selection includes Zay Flowers in 39 lineups and Tua Tagovailoa in 4. Both are currently designated doubtful, with the fixed prior map assigning 6.52% and 1.98% participation probabilities. Both full and doubtful-only selection reduce those exposures to zero as an optimization result; no hard doubtful-player ban is imposed. Questionable-only selection instead retains Flowers in 41 and Tagovailoa in 4.

Questionable-player treatment still contributes. Full selection has McConkey 13, Olave 4 and Burrow 2, compared with doubtful-only 23, 7 and 4. Full and doubtful-only share 81 of 97 members. These are model consequences, not instructions to remove a player from an entered lineup.

| Audit assumption | Full Emax change vs ordinary | Doubtful-only Emax change |
|---|---:|---:|
| Full participation uncertainty |+3.511|+3.123|
| Only doubtful players can miss |+2.876|+3.117|
| Only questionable players can miss |−2.350|−2.738|
| All designated players play |−2.957|−2.716|

Thus the large result depends principally on doubtful nonparticipation. The all-active cost remains substantial: full P220 falls 3.665 pp under that assumption. Saturday designation uncertainty and Sunday's confirmed-active information are different decision states. Once a player is confirmed active, keeping the Friday nonparticipation prior would be wrong; the research adapter now refuses unverified official-active overrides instead of pretending that ingestion exists.

## Contest delivery remains uneven

These are the actual **vetted delivered-order** contrasts under full participation, not raw selection order:

| Delivered region | Full Emax change | Full P220 change | Doubtful-only Emax change | Doubtful-only P220 change |
|---|---:|---:|---:|---:|
| First lineup |0|0|0|0|
| First 10 |+0.487|−0.065pp|+0.257|−0.190pp|
| First 30 |+0.357|+0.120pp|+0.026|−0.050pp|
| Rank 25 |+0.617|−0.185pp|−2.953|−0.200pp|
| Ranks 32–33 |−5.872|−0.335pp|−0.300|−0.185pp|
| Whole 97 |+3.511|+2.390pp|+3.123|+2.035pp|

Doubtful-only greatly reduces the large 32–33 expected-max loss, but introduces a larger rank 25 loss and still loses 32–33 P220. It is not a dominance fix. Full participation's first 30 Emax improvement repeats, while first 30 P220 remains inconclusive. The report retains every prefix, block, assumption and component; no favorable subset determines the conclusion.

## Recommendation and evidence

Keep **full participation-aware reselection** as the leading separately reviewable option. Do not replace it with a doubtful-only rule on these results alone: the full rule has the better whole-book result under its stated assumptions and existing historical support, while the new narrowed rule has no matching historical adoption validation. Do not claim any of these comparisons proves a better Millionaire entry or a real 220 breakthrough.

The important practical next step is applying the verified saved-artifact adapter to the completed full operating corpus with current statuses, retaining the ordinary co-run control and reporting the actual delivered contest blocks. The operating dose remains unchanged. Its “D12800” label has the already documented 12,560 attempt cap under 10,000 generation worlds, before any deduplication. This experiment remains D1600; it does not substitute for that full-corpus check. Official game-day source acquisition and operator adoption are separate requirements.

Protocol/source froze at production **97bcac0c** after a synthetic complete selection/delivery/audit smoke and real-artifact checks. The original ordinary/full selected orders reproduce exactly. Fresh incumbent/hsim audit seeds 12260919 / 13260919 are built only after exact replay of the original fitted laws; availability seed 20260919055 is also fresh. Audit construction took 51.27 seconds and the reader 24.72 seconds. All four books contain 97 unique legal lineups. No scoring outcomes or bank 991 enter any reader, model or selection.

[Protocol](2026-09-19-participation-designation-protocol.md), [full numerical result](reviews/evidence/2026-09-19-participation-designation-result.json), [fresh-bank identities](reviews/evidence/2026-09-19-participation-designation-audit.json), [original participation report](2026-09-19-participation-transfer-results.md). The portable replay reproduces all numbers and delivered orders exactly. [Published bundle identity](reviews/evidence/2026-09-19-participation-designation-publication.json); external review is pending.

Research-log qualification: during a separate official-feed discovery lookup, unrelated current-season result headlines appeared in web-search snippets. They were not ingested or used for fitting, selection, evaluation or this design. Sunday outcomes and bank 991 remain unopened. The inactive-report parsing support used a 2025 page only; it does not certify a 2026 game-day active feed.
