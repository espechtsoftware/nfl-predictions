# Data sources: what we ingest, what the model uses, and which ones have proven helpful

Operator question (2026-09-20, 14:55 CT): "a comparison of the data sources we have (more than what we use) and which
ones have been helpful." Built from a read-only survey of the production checkout (56 sources traced from ingestion to
consumer; file-path index at the end), the experiment ledger's verdicts, the 2026-09-15 paid-source ladder read, and the
labs' Week-3 experiment plan. No current-week outcomes were opened.

## 1. The short answer

Of 56 ingested, captured or referenced sources, **17 feed the live model or the live pipeline, and every one of those has
an ablation or gate result behind it.** The paid vendors (Fantasy Points, SIS) are captured in depth, have been tested in
eleven frozen experiments, and **none of them is in the live model**: nine Fantasy Points families and three SIS
mechanisms failed their frozen gates; the two survivors (Route Share, SIS pass-tail) sit in paused 2026 prospective
shadows whose first graded week is Week 3. The ledger's paid-source ladder (54 slates, 2023-2025) found no paid source
clearing its preregistered gate. The one paid input that demonstrably helps is The Odds API player props, through the
45/55 market blend. **The most valuable unused asset is not a vendor feed but the full-field contest standings we now
capture** (994,328 Week-1 entries), and the one strong source never tested as a model input is the ETR projection file,
which the operator already buys and which the contract confines to a display-only flag.

## 2. Sources that carry proven weight (live today)

| Source | Provider / cost | What it feeds | Evidence |
|---|---|---|---|
| Play-by-play, weekly stats, snap counts | nflverse, free | usage shares, red-zone, labels (`dk_points`) | core of every panel; never ablated as a block |
| Schedules (Vegas spread/total, rest, roof) | nflverse, free | implied total, spread, game script, SCHED pair | SCHED adopted (+6 tail weeks, Addendum 49); Vegas-first DST adopted (Addendum 12); minus-Vegas ablation costs accuracy (ledger table) |
| Next Gen Stats passing | NFL, free | `qb_cpoe_l6` | adopted: tail weeks 18 -> 23 of 101 (Addendum 32) |
| Next Gen Stats receiving/rushing | NFL, free | separation, stacked box | in the live matrix; `qb_time_to_throw` rejected (Addendum 33) |
| PFR advanced defense | free | CB/DB yards-per-target, top CB out | drop-ablation retained all four (2026-08-13 result) |
| Depth charts, rosters, injuries | nflverse, free | `depth_rank`, vacated shares, top CB out | live; `depth_rank_delta` and `team_ol_out` removed after exact-replay losses |
| Officials | nflverse, free | `ref_flags_prior` | adopted, but NULL live until midweek crews are sourced (a live-path hole) |
| DraftKings salaries | free | salary, week-over-week delta | live |
| Historical salaries + ownership | LineStar, RotoGuru, DiscoveryLab (2025 paid tier) | replay pricing, ownership booster | LineStar ownership corr 0.727 vs 0.548 naive (Addendum 29); chalk fade +2 twice proven |
| Player props | The Odds API, about $30/month | 45/55 blend, market-implied quantiles (flag) | blend MAE 4.664 vs 4.909 model-only, best tail (Addendum 14); q90 arrives calibrated (Addendum 45) |
| Weather | Open-Meteo, free | `is_dome` only | wind and temperature are carried but never entered the model (untested) |
| TabPFN marginals | derived, GPU job | per-player quantile marginals | adopted default-on (Addendum 50) |

## 3. Paid vendors: captured deeply, never in the live model

| Vendor | Families captured | Frozen results | Where it stands |
|---|---|---|---|
| Fantasy Points Data Suite | Route Share (2022-25 + 2026 weekly), Coverage Matrix (prior and same season), Advanced passing/rushing/receiving, PROE, alignment, route shape, QB shell, live matchup tools | Route Share final-served: calibration tie (no improvement); component arm fails; coverage union ties on 107/107 slates; PROE, same-season coverage, same-season passing, route shape, QB shell, prior-season receiving: all `*-fails` | Route Share only, as four `CANDIDATE_FEATURES` in the paused `tail_k1_route` registry; the 2026 prospective gate (`shadow-k1-route-roleunion`, paused) is graded from Week 3 |
| SIS DataHub | team pass defense / pass rush / blocking, run context, alignment (ASOE), receiver copula | pass-tail trio passes the player gate and selects treatment at 220 in the exact-80 test (mean-max 173.90 -> 173.48); ASOE passes score-free to final-served; QB line and RB run defense fail; receiver copula procedurally closed | prospective 2026 pass-tail shadow (`s-shadow-sis-pass-tail-paired`, paused; no frozen gate document yet, must be written or moved to DORMANT before Week 5) |
| Both together | paid-source ladder, 54 slates 2023-2025, FP x SIS 2x2 | points: FP given SIS +0.64 [-3.71, +5.44]; SIS given FP +1.20 [-1.13, +4.00]; finish: SIS given FP +0.019 [+0.003, +0.040]; FP given SIS -0.012 [-0.014, -0.008]; no cell clears the co-primary gate | the retrieval-only 2x2 (`fp-sis-retrieval-only-cross-v1`) exists in code and is parked; `source_value_established = false` |
| ETR projections | weekly CSV, paid pass | never tested as an input; contract: "a disagreement FLAG, not an input" | display-only on the market page |
| Fantasy Points projected ownership | site surface only | not ingested | auth bootstrap exists, no collector frozen |

The ledger's own framing (2026-09-12 retrieval-lever report): the bottleneck is the world model's ability to identify
good candidates, not the rule that orders them; a paid source is worth testing only as an improvement to the world model.
That is the design the labs scheduled for Week 3 (section 6).

## 4. Free sources tested and rejected (do not re-run without a new mechanism)

Chronos time-series foundation model (baselines win, Addendum 88); Big Data Bowl tracking traits v0 (no residual gain on
thin-history players, Addendum 96b); odds movement (close absorbs the news, Addendum 17); cross-book dispersion (fails
with two books, Addendum 96); FTN blitz rate, pace, target concentration (five consecutive single-feature failures,
Addendum 28); NGS time-to-throw (Addendum 33); draft-capital cold-start priors (Addendum 21); `depth_rank_delta`,
`team_ol_out` (exact-replay losses).

## 5. Captured but consumed by nothing

| Item | State | Suggested disposition |
|---|---|---|
| Full-field contest standings (`contest_entries`, 994,328 Week-1 rows; the checkout's README still says zero) | landed 2026-09-13 after the checkout; consumers exist (ownership model, field calibration, winner anatomy) but have not been rerun on it | highest-value free asset: field calibration and the ownership booster after 2-3 weeks, plus construction studies like today's stack-depth read |
| Odds API shadow prop markets (`prop_lines_shadow`) | collection-only by design | keep collecting; candidate for the world-model test once props-first has a graded baseline |
| Weather wind / temperature | carried in training tables, not in the model | cheap candidate-feature arm (never tested) |
| Referee crew assignments | live NULL in an adopted feature | source midweek crews (free) to close a hole in a feature that already earned its place |
| Combine, CFB salaries, contest fills, showdown salaries, Odds API quota audit | orphans or scaffolds | no cost; no action |
| FP live matchup tools | GCS archive only, contract forbids consumption in 2026 | research only |
| Nine FP families and SIS run context / copula | closed with frozen `*-fails` dispositions | do not retest |
| Prop-divergence shadow (`div_shadow`), ownership shadow, live candidates | 2 weeks of 2026 data; grading bar is 4 of the first 6 graded weeks on 25+ players | grade automatically at week 4-6 |
| Beat-writer news / LLM evidence | scaffold, data-gated | no fetcher; not a 2026 item |
| Odds API `us_dfs` region (pick'em lines) | proposal only; a live scheduler named `s-us-dfs-sun` is reported but has no repo counterpart | resolve the scheduler mystery before anything else |

## 6. What answers the operator's question prospectively

1. **The labs' Week-3 paid-source incremental-value shadow** (their experiment plan, item 3): on the first fresh slate
   where SIS, Fantasy Points and Odds API snapshots are all complete and point-in-time bound, one common candidate
   universe and four frozen score inputs: free stack, +Odds, +SIS, +Fantasy Points, and all three; record whether each
   source changes served means, tails, candidate membership, selected membership and order; realized max-of-K and
   200+/210+ clears as the read. This is the direct measurement the ledger has never had. It depends on the operator's
   Wednesday vendor run landing all three feeds.
2. **Turn the two paused prospective gates on for Week 3** (Route Share pair, SIS pass-tail pair), as already planned;
   write the SIS gate document before Week 5.
3. **Add one arm the plan lacks: ETR as a world-model center.** The operator already pays for it, it is the strongest
   external projection available, and it has never been tested as anything but a flag. A paired shadow that generates
   candidates from an ETR-centered projection (blend or replace) on the same pool would test the ledger's own claim that
   the world model is the bottleneck. Contract change required; operator's call.
4. **Use the captured field.** Rerun field calibration and the ownership booster on the Week-1/Week-2 full fields; they
   are free, already ingested, and the ledger's chalk-fade result says ownership accuracy pays.

## 7. Sources for this note

Inventory: `src/nfl_dfs/ingest/*` (32 modules), `src/nfl_dfs/models/featureset.py` (`NUMERIC_FEATURES`,
`CANDIDATE_FEATURES`), `src/nfl_dfs/features/build.py`, `deploy/deploy_jobs.sh`, `sql/features/*.sql`,
`sql/research/*.sql`, `src/nfl_dfs/research/paid_source_ablation_registry_v1.py`. Verdicts:
`reports/2026-07-25-system-study.md` addenda 12, 14, 17, 21, 28, 29, 32, 33, 45, 49, 50, 82, 88, 96, 96b;
`reports/2026-08-10-*` and `2026-08-11-*` Fantasy Points protocols and results; `reports/2026-08-13-*` and
`2026-08-14-*` SIS results; `reports/2026-08-15-prospective-sis-pass-tail-finite-k-protocol.md`;
`reports/2026-09-10-neo4j-fantasy-points-sis-influence-review.md`; `reports/paid-source-ladder-direct-20260915/read.txt`;
`reports/2026-09-12-retrieval-lever-measured-on-realized-scores.md`; `reports/2026-09-20-week3-experiment-start-plan.md`
(research branch). BigQuery row counts read on 2026-09-20: `nfl_raw.contest_entries` 994,328 (2026 W1, 3 contests);
`nfl_predictions.div_shadow` 4,535 rows over 2 weeks.

## Addendum (21:50Z): the labs' full SIS / Fantasy Points value-surface review

The labs' `reports/2026-09-20-sis-fantasy-points-full-value-review.md` (research `220faa59`) adds two readings this map
should carry. First, Fantasy Points Route Share is the one paid field with demonstrated signal: at matched projections,
high prior route share ran about +0.6 to +1.0 DK points above projection, clearest in the 10-14 projection band, and
it is far less collinear with snap share for tight ends (r about 0.90) than for wide receivers (r about 0.97); the
coverage families failed narrow gates (prior-season edges weak and unstable; same-season windows short of support;
shell-fit worse on Brier), which does not test defender-level coverage, red-zone route participation, or coverage x
role interactions. Second, the paid-source ladder's null is a retrieval finding: every cell admitted a ceiling near 181
while the pool held 202.7, because mean-edge admission discards the tail regardless of vendor. Their proposed tests
(a coverage/role incremental forecast test led by route share and red-zone routes, an SIS player-coverage matchup test
with shrinkage and support floors, and a tail-aware re-run of the 2x2 ablation) are the right next reads; the
recommendation is to keep the subscriptions long enough to run them, not to renew on faith or cancel on the marginal
tests so far. Section 3 of this map stands; "in nothing live" remains true today.
