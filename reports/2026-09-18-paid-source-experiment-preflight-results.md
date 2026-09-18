# Paid-source experiments: first-stage results

September 18, 2026. Erich authorized the staged experiments after reading the renewal review.
Scope was fixed in [the first-stage plan](2026-09-18-paid-source-experiment-plan.md) at `8ce2ffd9`.
This is an outcome-free source/mechanics study, not a treatment-value or adoption result.

**The SIS pass-tail shadow becomes eligible FROM Week 5, not THROUGH Week 5. Its potential value remains
unresolved. However, deployed SIS and Route shadow schedules are currently paused: existing code does not
mean fresh prospective evidence is being collected.**

## Completed checks

### Registered model artifacts

Inspected serialized feature headers and matching registry metadata for 33 actual models: 11 components
in each of `tail_k1`, `tail_k1_role`, and `tail_k1_route`. Recorded GCS generations and content hashes;
no predictions or validation metrics were exposed.

| Registry | Latest observed ISO week | Features per component | Licensed vendor features |
|---|---|---:|---|
| tail_k1 | 2026-W32 | 36 | none with fp_/sis_ prefixes |
| tail_k1_role | 2026-W33 | 42 | none with fp_/sis_ prefixes |
| tail_k1_route | 2026-W33 | 40 | all four registered fp_route fields |

The base-model metadata and serialized models list the same feature sets in different order. This is
not evidence of a prediction bug: `components._matrix_for_model` uses the fitted model's feature names/order.
The role and Route metadata agree in order as well. The operating briefing says the adopted models are
frozen and retraining paused; the old ISO-week labels alone do not establish a missed retrain.

This strengthens the earlier source/configuration conclusion. It is still not a replay of a specific
Sunday artifact: that requires its exact loaded model/cache identities and inputs, not just today's
latest registry objects. Learned historical influences cannot be ruled out solely by feature prefixes.

### Synthetic Odds-consumer checks

These call the existing production functions with invented players and quotes, without network queries
for odds or actual outcomes.

| Check | Observed behavior | Interpretation |
|---|---|---|
| Standard main line moves 49.5 → 59.5 before lock | Both lines survive; postlock 69.5 is excluded | Confirms stale main-line retention even though lock filtering works |
| Over quote at 16:00Z, Under at 09:00Z, same point | Both sides survive | Pairing can combine different observation times |
| Prop coverage increases from 2/10 to 3/10 | True-prop mask jumps 0→3; an already-covered player's market value jumps from PPG 20 to prop 10 | Reproduces the intentional whole-slate gate discontinuity, not a new coding error |
| Receiving yards plus receptions, no TD market | Player is accepted by minimum_markets=2 | Count-based completeness does not guarantee a whole-player fantasy expectation |

The first two require a coherent snapshot contract before an efficacy study. The latter two require
an explicit fallback/completeness design, not invented missing prices. No source correction was deployed.

### Warehouse support census

Enumerated the actual FP/SIS raw-table schemas and queried four support summaries, using a 100 MB
maximum-bytes limit per query. No treatment scores, player outcomes, lineup outcomes or vendor calls.

| Source table | Current support |
|---|---|
| fantasy_points_route_share | 265 rows for 2026 Week 1; all have route_share; imported Sept 17 |
| fantasy_points_advanced_receiving_windows | Historical 2022–2025 target Weeks 5–18; first-read-rate field exists; no 2026 rows |
| fantasy_points_alignment_player_l4 | Historical 2022–2025 target Weeks 5–18; no 2026 rows |
| sis_team_context_game | Historical 2019 and 2021–2025; no 2026 rows |

These are row/non-null counts, not claims of complete player coverage, distinct-player counts or
information novelty. The advanced-receiving table includes multiple window types, so its row count is
not an independent sample size. No 2026 SIS/alignment rows at Week 2 is consistent with the planned
Week-5 acquisition; it is not by itself a missing-data incident.

The schema establishes a real historical first-read-rate field and distinguishes it from a merely
proposed red-zone route feature. A new role-change study still needs prelock current-season captures,
a documented field definition, eligible changes and a redundancy audit. The 265 route rows alone do
not supply a fresh 2026 first-read/red-zone treatment.

### Shadow readiness

All eight inspected SIS/Route Cloud Scheduler entries are **PAUSED**, including the SIS control/treatment
cache schedules and paired-book schedule, Route feature/train schedules and both Route book schedules.
Provider execution listing returned no retained executions for `shadow-sis-pass-tail-paired` or
`shadow-k1-route-roleunion`. This is not proof no manually produced or historical artifacts exist elsewhere.
It establishes that these named scheduled jobs are not currently collecting evidence.

The current briefing explicitly lists other research shadows as paused; the operating handoff says not
to restart them casually. Their older frozen policies differ from today's live DEMAX path. I have asked
the workstation agent whether a newer paired replacement exists and for the reason/disposition of these
pauses. Restarting an old research policy would not establish current-money transfer.

## Experiment routing and next steps

1. **Odds integrity first:** fix the snapshot-selection contract in a separately reviewed change; require
   moved-line and mismatched-side cases to behave correctly while genuine same-snapshot alternate ladders
   remain intact. Compare corrected versus current proxies on retained prelock snapshots before model effects.
2. **Finish the current-build source audit:** bind the exact existing live run, model/cache identities and
   inputs, then distinguish prop removal from PPG substitution. The registered-feature census above completes
   only its model-input portion, not the full candidate/book byte-ablation.
3. **FP role-change research:** support census confirms route data is current but the proposed richer
   same-season fields are not yet in these tables. Define the smallest prospective capture and field/role
   cohort, check timely incremental information before fitting, and avoid rerunning the failed generic Route arms.
4. **SIS:** retain the question as open. Reconcile existing shadow ownership/policy and prepare the Week-5
   acquisition/cache/book chain; only a supported comparison under a defined policy can establish value.
   Do not reinterpret the old insufficient-support copula run as a failed mechanism.

The user has authorized this research sequence. No additional permission is needed for its ordinary
read-only/mechanics work. No subscription purchase/cancellation, schedule change, production model change,
or money-lineup adoption has been made. Future outcomes cannot be supplied now; prospective studies need
prelock artifacts and subsequent games, with their original minimum-support/reading rules respected.
The known-law E0 → existing-pool independent-world pilot sequence remains agreed separately.

## Reproducibility and limitations

Evidence and runnable probes:

- [Preflight script](reviews/evidence/2026-09-18-paid-source-preflight.py) and
  [captured evidence](reviews/evidence/2026-09-18-paid-source-preflight.json).
- [Support follow-up script](reviews/evidence/2026-09-18-paid-source-support.py) and
  [captured support](reviews/evidence/2026-09-18-paid-source-support.json).

Scripts ran with the production virtual environment, this worktree's `src` on PYTHONPATH, and numerical
thread caps of one. The initial support query was refused because `rows` was used as an unquoted reserved
alias (job `3fdbc801-707f-4353-8e9a-16400d37325c`); changing it to `n_rows` was a syntax-only repair before
any result. Final query IDs/processed bytes and artifact hashes are retained. No benchmarks or hypothesis
tests on outcomes were run, and no 990/991 results were opened.
