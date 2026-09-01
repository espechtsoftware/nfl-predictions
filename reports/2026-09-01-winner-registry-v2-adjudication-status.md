# Winner registry v2: adjudication status and production disposition

**Date:** 2026-09-01
**Disposition:** candidate ledger built; official score-bearing cohort not yet
adjudicated; PREREG-080/081/082 efficacy remains held

## Executive decision

The lab's request is correct and has reached production. Experiment 082 will
not follow 077. The same hold applies to 080 and 081 because all three consume
winner-referenced evidence whose contest and score identity is unresolved.
The paid exact-K boundary and Week-1 contest-capture rehearsal remain ahead of
the held experiments.

This is not a choice between two interchangeable score columns. The local
files sometimes describe different Millionaire contests in the same week,
and several roster captures contain player-point errors. Registry v2 therefore
must identify the target contest before choosing its winning score. No local
article value or roster sum is being relabelled as official to accelerate the
queue.

## Reconciliation result

The lab has 48 season/week score labels and production v1 has 51 governed
roster labels. They share 46 labels:

| Relationship | Count | Slate labels |
|---|---:|---|
| Shared; score agrees | 35 | 2023 W1, W5-W9, W14-W15; 2024 W2, W5, W7-W8, W10-W13, W15-W16; 2025 W1-W17 |
| Shared; score disagrees | 11 | 2023 W2, W3, W10, W11, W13, W16, W17; 2024 W3, W4, W6, W14 |
| Production only | 5 | 2023 W4, W12; 2024 W1, W17, W18 |
| Lab only | 2 | 2023 W18; 2024 W9 |

The largest shared-score difference is 30.46 points at 2023 W2. At least four
shared labels contain different nine-player rosters, so the evidence contains
at least 57 distinct roster observations before the additional source-only
weeks are resolved. `(season, week)` is metadata, not a contest identifier.

Representative failure modes are materially different:

- 2023 W2 and W16, plus 2024 W4 and W6, contain different rosters associated
  with different Millionaire contests or contest descriptions.
- 2023 W3, W10, W13, W17 and 2024 W3 differ because one captured player or DST
  score differs.
- 2024 W14 has an article scalar of 281.60 while both captured roster sums are
  281.68.
- Production's canonical 2024 W9 block is a copy of W7 after removing the week
  value; the article-derived W9 roster is distinct and cannot be silently
  discarded.

The lab file is not an independent fifth authority: its 31 values for
2023-2024 exactly reproduce the local article-derived CSV, and its 17 values
for 2025 exactly reproduce the local summary CSV.

## What has been built

The new candidate path is deliberately separate from immutable registry v1:

- `src/nfl_dfs/research/winner_registry_v2.py`
- `scripts/build_winner_registry_v2.py`
- `reports/winner-registry/winner-registry-v2-candidate-ledger.json`
- `reports/winner-registry/winner-registry-v2-target-contest-policy.template.json`
- `reports/winner-registry/winner-registry-v2-adjudication-receipt.template.json`

The lossless ledger contains all 917 physical data rows from the four tracked
source files as 117 independent observations over 70 season/week labels. It
retains raw strings, exact source file hashes, physical row ranges, multiple
same-week observations, roster-content hashes, and three permanently separate
score fields:

1. `official_target_winning_score`
2. `captured_roster_points_sum`
3. `article_or_summary_reported_score`

The candidate ledger has zero official scores and zero accepted contests. Its
schema refuses an official claim inside the candidate artifact. Acceptance
requires a frozen target policy, exact contest identity, the original source
artifact, an official DraftKings result receipt supporting the same contest ID
and score, an adjudicator, and deterministic receipt identity. The final
accepted cohort must also reject duplicate contest IDs and more than one
accepted target contest per policy slate.

This is meaningful progress but not a completed score-bearing registry. It
prevents further conflation and makes the remaining evidence request exact.

## Target-contest policy that must be frozen

Production recommends that the owner approve a policy based on contest
identity, never on which candidate has the preferred score. The policy must
state, for each effective era:

- DraftKings NFL Classic, Sunday main/common-lock slate;
- exact contest family/name pattern;
- entry fee, top-prize requirement, and any guaranteed-prize-pool or field-size
  ordering used to define “flagship”;
- what happens when two Millionaire contests coexist;
- how cancellations, split slates, Week 18, and renamed contest families are
  handled; and
- the required official evidence class.

A reasonable proposal for owner review is “the standard large-field Sunday
main Classic flagship with $1 million to first, selected by the frozen
contest-family/fee/GPP rule.” That is not frozen yet because the historical
files do not consistently contain entry fee, field size, exact contest name,
or DraftKings contest ID. Choosing the highest weekly score would be invalid.

## Evidence needed to finish v2

The shortest trustworthy route is to recover official DraftKings contest
results or immutable exports containing the contest ID, exact contest name,
winning entry/roster and winning score. Search targets include old
DKEntries/standings downloads, browser downloads, backups, cloud archives, and
the original material used to assemble the user-supplied roster file.

Independent tracker pages and first-party DraftKings editorial pages are useful
for locating competing contests and diagnosing roster values, but they should
remain separately labelled authorities unless they expose the exact official
contest result. If official exports cannot be recovered, production should
create a differently named `adjudicated_target_score` cohort with an explicit
authority hierarchy and sensitivity analysis; it must not populate the
`official_target_winning_score` field by implication.

### Local evidence census completed 2026-09-01

A read-only search covered both project repositories, the local winner-audit
cache, the local panel cache, tracked reports, build/worktree duplicates, and
filename plus CSV-header patterns for historical standings, DKEntries,
contest-result ZIP/XLS/JSON and `EntryId`/`ContestId`/`Rank`/`Lineup` exports.
It found no historical raw DraftKings standings or DKEntries result export for
2023-2025. The only standings-shaped CSV is the deliberately synthetic Week-1
capture-rehearsal fixture and is not historical evidence.

The four candidate-ledger inputs are therefore the strongest local material,
but their authority is limited exactly as v2 records it: the two roster
captures support roster identity and recomputed point sums; the article roster
file supports a separately labelled article score; and the 2025 summary file
supports a separately labelled summary score. The lab's 48-value JSON is a
derivative of the latter two files, not an independent authority. The v1
registry, v2 ledger and winner-audit feature caches are also derived artifacts
and contain no missing contest ID or official-result receipt.

This closes the local-search branch without changing the disposition. An
original browser download, backup, immutable DraftKings result, or other exact
contest-ID-bearing authority must come from outside the presently accessible
local artifacts. If none can be recovered, the program must freeze and name a
non-official adjudicated authority hierarchy rather than populate the official
score field.

### Bounded public-source follow-up

A bounded search also found no public official DraftKings standings export or
result endpoint that joins the target contest ID, winner roster, and winning
score for the disputed labels. First-party DraftKings Network recap pages do
provide useful editorial evidence for [2024 W3](https://dknetwork.draftkings.com/2024/09/23/draftkings-fantasy-football-millionaire-winning-lineup-breakdown-week-3/),
[W4](https://dknetwork.draftkings.com/2024/09/30/draftkings-fantasy-football-millionaire-winning-lineup-breakdown-week-4/),
[W6](https://dknetwork.draftkings.com/2024/10/13/draftkings-fantasy-football-millionaire-winning-lineup-breakdown-week-6/),
[W9](https://dknetwork.draftkings.com/2024/11/04/draftkings-fantasy-football-millionaire-winning-lineup-breakdown-week-9/),
[W14](https://dknetwork.draftkings.com/2024/12/09/draftkings-fantasy-football-millionaire-winning-lineup-breakdown-week-14/),
[W17](https://dknetwork.draftkings.com/2024/12/30/draftkings-fantasy-football-millionaire-winning-lineup-breakdown-week-17/),
and [W18](https://dknetwork.draftkings.com/2025/01/06/draftkings-fantasy-football-millionaire-winning-lineup-breakdown-week-18/).
They identify the recap week, winner, contest description and usually the
reported score/lineup screenshot. They remain editorial articles without the
recapped contest's exact ID, so they may support a separately labelled
first-party editorial observation but cannot satisfy the current
`official_target_winning_score` receipt.

There is a specific adjudication trap: contest links near the bottom of these
recaps point to the following week's upcoming contest, not the event being
recapped. Those linked IDs must never be attached to the recap week. No
equivalent first-party result article surfaced for the disputed 2023 labels or
2024 W1. Secondary recap pages can locate candidate rosters, but cannot cure
the missing official contest identity.

## Queue and downstream rules

1. Let frozen 077 finish unchanged and read it under its existing contract.
2. Do not schedule or launch 080, 081, or 082.
3. Complete the paid exact-K/unique/DK-legality boundary and Week-1 capture
   rehearsal first.
4. Freeze the target-contest policy and create one receipt per accepted contest.
5. Build an immutable score-only registry-v2 cohort and `winner_cdf_v2` with
   exact count/hash and runtime verification.
6. Only then redesign/freeze 082 and re-evaluate the winner-referenced queue.

The lab's two-authority sensitivity remains useful: it found D400_DEMAX ranked
first under both disputed score sets and a nearly unchanged D400-minus-D200
contrast. That reduces the risk that existing label ranking reverses, but it
does not establish calibrated utility levels or discharge the registry hold.
