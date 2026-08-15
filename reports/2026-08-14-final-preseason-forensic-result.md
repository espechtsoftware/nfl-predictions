# Final preseason forensic result

> **Corrective addendum (2026-08-15):** The H/P and perfect-information
> recourse solvers described below used QB+1/no bring-back rather than the
> production QB+2/one-bring-back contract. The production candidates,
> selected lineups, baseline and all adoption decisions were unaffected.
> Corrected diagnostic quantities and interpretation are in
> `reports/2026-08-15-post-forensic-exact-stack-addendum-result.md`; its exact
> H-P/P-C/C-S means are 4.057/68.914/5.007 and its corrected hindsight
> recourse mean gain is 37.807. Treat the superseded H/P and recourse numbers
> retained in this original report as historical provenance only.

Date: 2026-08-14 CDT. This report closes the frozen historical arm program and
defines what its result does, and does not, license. The full machine-readable
evidence remains in the create-only GCS output prefix and the isolated BigQuery
forensic dataset described below.

## Executive conclusion

The corrected final forensic execution completed successfully. The current
exact-80 production policy remains
`classic-k1-role12-boom40-poscal-cbwu-v4`. Across the 54 comparable 2023–2025
slates it produced 17 weekly maxima at or above 187, 8 at or above 194, 7 at or
above 200, 6 at or above 210, 3 at or above 220, and 1 at or above 230.

The apparent decline to eight >=194 weeks is not evidence that the current
policy is worse for the operator's objective. Against its pre-CBWU component
baseline, it traded away one >=194 crossing while adding two >=200, five >=210,
two >=220, and one >=230 crossing. Mean weekly maximum also increased by 3.395
points. This is the intended trade: less emphasis on the average or a moderate
cash line in exchange for more genuinely exceptional weeks.

The most important forensic finding is that the final selector is not the main
constraint. The best generated candidate is, on average, 78.994 points below
the best legal lineup supported by the candidate player union, whereas the
selector leaves only 5.007 points between the best generated candidate and the
best selected lineup. At the 210 threshold, construction is the first failed
layer on 44 of 54 slates and selection is the first failed layer on none. The
next scoring program therefore targets candidate construction and the shape of
the decision, not another selector sweep.

No additional retrospective arm is licensed. This is not a conclusion that
there is nothing left to improve. It is a boundary: new mechanisms must be
frozen and evaluated on outcome-unseen 2026 slates rather than mined from the
same historical outcomes again.

## Durable execution receipt

- Execution: `final-preseason-forensic-v1-gqssz`
- Status: succeeded, one successful task and no failed task
- Start: `2026-08-15T03:18:49.798795Z`
- Completion: `2026-08-15T04:05:51.446124Z`
- Runtime: 47 minutes 1.64 seconds
- Analysis code: `1e4f7f4c81a07100b522975a8d2f352a911c3d5b`
- Immutable image: `us-central1-docker.pkg.dev/nfl-predictions-503414/nfl-dfs/nfl-dfs@sha256:313e762be343dada9ee9f386818af176cdb1e4ff09b84912e4a683841cf9aa4d`
- Manifest: `reports/final-forensic-runs/20260814-final-preseason-forensic-v1/freeze_manifest_repair4.json`
- Internal manifest SHA-256: `51edbe124846dc936ade71c4e5a9a07e252bcf6c7d7872b979715ccd1f6bab02`
- Manifest file SHA-256: `565cdcfaffad6e131449c991dda64dc171cad2d23ec0b3dc55ae0a53c9ef94e3`
- GCS output root: `gs://nfl-predictions-503414-raw/research/final-forensic-runs/20260814-final-preseason-forensic-v1/outputs-repair4`

The run wrote all nine contracted JSON objects. Every object parses, every
required top-level contract is present, and the combined size is approximately
35.37 MiB. The opportunity decomposition contains all 215 required
slate-scope rows: 107 component, 54 position-calibrated, and 54 CBWU.

The isolated BigQuery warehouse contains the four exact write-once repair4
tables:

| table | rows |
|---|---:|
| `final_forensic_20260814_player_corpus_repair4` | 111,191 |
| `final_forensic_20260814_candidate_corpus_repair4` | 54,430 |
| `final_forensic_20260814_actual_selections_repair4` | 17,200 |
| `final_forensic_20260814_oracle_rosters_repair4` | 1,075 |

Their schemas exactly match the manifest, their labels and descriptions carry
the manifest identity, and their common expiry is
`2026-11-13T04:05:17.429Z`. They must remain available for independent review
for now, but must be deleted and verified absent before the first 2026
production build. Production does not read this isolated dataset.

## Current exact-80 baseline

The current CBWU policy's aggregate weekly-maximum score is 176.063. Mean is a
secondary diagnostic; the tail grid is the decision-aligned result.

| season | slates | mean weekly max | best | >=187 | >=194 | >=200 | >=210 | >=220 | >=230 | >=240 |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 2023 | 18 | 181.833 | 235.60 | 6 | 3 | 2 | 2 | 2 | 1 | 0 |
| 2024 | 18 | 178.268 | 225.28 | 7 | 3 | 3 | 2 | 1 | 0 | 0 |
| 2025 | 18 | 168.088 | 217.34 | 4 | 2 | 2 | 2 | 0 | 0 | 0 |
| total | 54 | 176.063 | 235.60 | 17 | 8 | 7 | 6 | 3 | 1 | 0 |

The weekly maxima are:

- 2023: 173.64, 187.28, 235.60, 167.72, 173.98, 171.34, 168.16,
  180.28, 224.20, 194.72, 166.98, 162.62, 171.08, 193.28, 188.84,
  169.02, 173.06, 171.20.
- 2024: 170.48, 160.72, 225.28, 153.90, 185.22, 177.90, 144.20,
  166.80, 158.52, 149.72, 192.48, 179.20, 146.94, 218.48, 193.72,
  189.46, 207.26, 188.54.
- 2025: 136.18, 217.20, 168.14, 156.46, 163.86, 170.74, 158.54,
  156.98, 189.10, 167.50, 160.42, 217.34, 151.76, 148.64, 188.80,
  163.62, 161.34, 148.96.

### Why CBWU remains the baseline

Against the pre-CBWU component baseline on the same 54 slates, CBWU improved
30 slates and worsened 24. It increased mean weekly maximum by 3.395 points and
changed the tail counts by `+3/-1/+2/+5/+2/+1/0` at
187/194/200/210/220/230/240. Its largest single-slate gain was 61.22 points and
its largest loss was 42.16 points.

Against the position-calibrated comparison, CBWU improved 27 slates and
worsened 27, added one >=200, five >=210, two >=220, and one >=230 crossing,
and lost three >=194 crossings. Its mean gain was 3.017 points with a
slate-bootstrap 95% interval of -1.87 to 7.96. That interval and the exact
50/50 improved/worsened split are important uncertainty disclosures, but they
do not reverse the frozen tail-first adoption decision.

## Entry-count implications

The first 20, first 40, and all 80 entries of the current selected book yielded:

| entries | mean weekly max | >=187 | >=194 | >=200 | >=210 | >=220 | >=230 | >=240 |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 20 | 165.916 | 11 | 5 | 3 | 3 | 2 | 0 | 0 |
| 40 | 172.729 | 16 | 8 | 4 | 4 | 2 | 1 | 0 |
| 80 | 176.063 | 17 | 8 | 7 | 6 | 3 | 1 | 0 |

This supports retaining the 80-entry objective as the primary strategy. It also
supports the UI's separate 1–20 entry mode: simply taking a short prefix of the
80-entry book leaves material tail coverage on the table, so lower-entry
contests need their own contest-size-aware selection policy.

## Where the score is being lost

For each slate, the frozen decomposition is:

- **H:** best legal hindsight lineup from the complete authoritative slate
  universe under the frozen construction constraints.
- **P:** best legal hindsight lineup from the union of players appearing in any
  generated candidate.
- **C:** best actually generated candidate.
- **S:** best selected entry in the exact-80 book.

For current CBWU, the H/P/C/S threshold counts are:

| layer | >=200 | >=210 | >=220 | >=230 | >=240 |
|---|---:|---:|---:|---:|---:|
| H | 54 | 53 | 51 | 49 | 46 |
| P | 52 | 50 | 50 | 47 | 44 |
| C | 8 | 6 | 3 | 1 | 0 |
| S | 7 | 6 | 3 | 1 | 0 |

The average player-support gap H-P is 3.583 points, the construction gap P-C is
78.994, and the selection gap C-S is 5.007. Median player-support and selection
gaps are both zero; median construction gap is 76.02.

At the 210 threshold, the first failed layer is construction on 44 slates,
player support on 3, no failure on 7, and selection on 0. At 220 the counts are
47/1/6/0; at 230 they are 46/2/6/0; at 240 they are 44/2/8/0. Therefore:

1. More selector tuning is low priority.
2. Merely admitting more players is not enough; the union already supports a
   high-scoring legal lineup on almost every slate.
3. The generator must place supported players together in a much more diverse
   and tail-relevant set of legal candidate compositions.

## Salary-floor and paid-data findings

Removing only the production minimum-salary floor, while preserving every
other construction constraint, produced a positive hindsight difference on
18 of 54 CBWU slates, with mean 0.534, median zero, and maximum 4.60 points. It
created zero new threshold-reaching slates at every line from 187 through 240.
The salary floor should not be loosened on this evidence.

The frozen route-share admission rule admitted 565 absent WR/TE players, an
average of 10.46 per slate, while recovering only 2 of 17 omitted winner slots.
It is too indiscriminate for direct adoption. If retained at all, it must be a
budget-neutral 2026 shadow that replaces an equal number of low-yield
candidates; it may not simply enlarge the candidate budget.

The finite-K SIS pass-tail treatment remains a valid selected historical
research result, with `+2/+2/+3/+1` at 220/210/200/194 across its five seed
books. It is not part of the K=1 money policy because its cache and schedules
were never tested in that composition. The correct next use is a separately
labeled 2026 shadow, not an untested silent merge.

## Experiment noise and why repeated arm mining must stop

Across the 14 complete 107-slate panels, the arm identity explains only 4.71%
of arm-plus-residual weekly-maximum variance, 2.34% of >=200 variance, and
2.14% of >=210 variance. The minimum detectable paired mean difference is
approximately 3.865 weekly-max points; the corresponding tail-count scales are
about 9.2 >=200 weeks and 6.33 >=210 weeks.

Most plausible arm effects are smaller than this, while individual slate
gains and losses are large. Repeatedly choosing among small historical deltas
would increasingly select noise. The 56-entry arm ledger and 13-family
exhaustion certificate therefore close the registered historical search.

## Corpus-understanding leads

These findings are explicitly outcome-viewed and cannot alter a historical
scorecard. They are leads for prospective construction:

- A shallow held-out LightGBM model of candidate >=200 outcomes was weak but
  above chance: ROC AUC 0.6255 and average precision 0.00614 against prevalence
  0.00367. This is insufficient for production prediction but indicates some
  learnable construction signal.
- Candidate tail outcomes were most associated with simulated q99, ownership
  sum, salary, simulated median/mean/standard deviation, `p_line`, and lineup
  structure. The strongest interactions included ownership with simulated
  q99/median and q99 with simulated mean/median.
- The historical subgroup `largest_team_block=3`, high simulated q99, and high
  `p_line` had a 2.26x >=200 lift with large support. Related block-three plus
  bring-back/two-QB-stack strata were near 2x. These are hypotheses, not
  historical adoption rules.
- High-scoring candidates are locally concentrated in lineup-embedding space:
  7.81x local enrichment and 0.88 centroid separation in the deterministic
  sparse SVD view.
- The high-score co-selection graph has materially stronger community
  structure than the full candidate graph (modularity 0.479 versus 0.180).
  Specific historical player communities are not portable, but allocating
  candidate budget across structural archetype communities is testable.

These results motivate an outcome-unseen, budget-neutral archetype generator.
They do not justify training a production selector on the forensic labels.

## Late-swap opportunity

The perfect-hindsight late-swap ceiling improved 53 of 54 CBWU slates, with a
mean gain of 42.62, median 39.32, and maximum 103.72 points. It created 32 new
>=200, 30 new >=210, 24 new >=220, 18 new >=230, and 12 new >=240 slates.

This is an upper bound that uses realized late-player outcomes, not an expected
policy gain. The numeric gain must never be advertised as achievable. It does,
however, establish that late-game flexibility has far more potential than
another small marginal or selector adjustment. A realistic recourse policy
must use only information available at each lock stage and be evaluated
prospectively.

## Winner and ROI limitations

Against known first-place scores on the 52 matched Phase-S weeks, the current
selected weekly maximum trails by 55.842 points on average, beats the winner on
zero weeks, comes within 20 points twice, within 30 six times, and within 40
nine times.

The retained contest data contain first-place rosters but not complete places
2–5, field lineups, payout ladders, and duplication counts across the historical
evaluation window. Exact historical ROI is therefore not identifiable and no
precise ROI estimate should be reported. The 69 known first-place rosters have
median salary $50,000, mean salary $49,911, and mean ownership sum 120.23, but
known salary mismatches and older FLEX limitations make those descriptive only.

Complete standings, payouts, ownership, and contest metadata must be retained
for each 2026 contest so ROI, duplication, contest choice, and places 2–5 can be
measured honestly.

## Binding next program

Priority now becomes:

1. Keep the current K=1 CBWU exact-80 policy as the money baseline.
2. Operate the integrated, budget-neutral structural-archetype allocator only
   through its separately labeled 2026 outcome-unseen CBWU shadow. Keep the
   selector, entry count, simulation inputs, source-seed quotas, and candidate
   budget fixed.
3. Build a realistic recourse-aware late-swap shadow and an operator-safe
   rehearsal. Do not use the hindsight ceiling as an expected effect.
4. Run the already-defined finite-K SIS pass-tail shadow separately; do not
   transfer it silently into K=1.
5. Integrate live projected ownership and expanded market distributions as
   separately calibrated prospective inputs when available.
6. Retain route admission and latent role-state generation as lower-priority,
   explicitly prospective mechanisms.
7. Complete the Week 1 UI-to-DraftKings CSV dress rehearsal and delete the
   isolated forensic warehouse before the first production build.

The accompanying prospective program document defines the adoption boundaries
for the first two new construction mechanisms.
