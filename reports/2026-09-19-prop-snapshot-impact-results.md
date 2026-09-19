# Odds snapshot handling: real defect, bounded current numerical effect

The current reader retains stale main-line thresholds after newer ones arrive. On the captured Week2 quotes, restricting each event/book/market/player to its coherent latest snapshot changes **119 of the185 real-prop estimates consumed by production**. Mean absolute change is **0.0566 fantasy points**; maximum absolute change is **0.8801**. This is a market-proxy difference, not an accuracy gain, actual production-projection replay or220+lineup result. No live code, job, projection or selector changed.

| Population | Paired players | Changed above1e-8 | Mean absolute proxy change | Maximum absolute change |
|---|---:|---:|---:|---:|
| All Week2 priced players | 200 | 130 | 0.05659 | 0.88013 |
| Exact472-player production skill pool | 185 | 119 | 0.05664 | 0.88013 |
| Exact post-filter CLI proof player frame | 160 | 100 | 0.05529 | 0.88013 |

Coverage is unchanged:200pricedplayers in both arms,185/472real-prop matches in both, no players gained/lost and no crossing of the whole-slate30%gate. The mean signed production-pool difference is+0.01031, which should not obscure the opposing player-level changes.

| Player in the actual proof frame | Current market proxy | Coherent latest proxy | Change |
|---|---:|---:|---:|
| Dalton Schultz | 10.2563 | 11.1365 | +0.8801 |
| Roman Wilson | 4.9119 | 5.4856 | +0.5737 |
| C.J. Stroud | 17.1420 | 16.6983 | −0.4437 |
| Lamar Jackson | 21.4540 | 21.0896 | −0.3645 |
| Rico Dowdle | 9.4654 | 9.1695 | −0.2959 |

These values precede the production blend and downstream adjustments. Do not call them changes in final projections or real scoring probabilities. The moderate effects in this particular Friday capture also do not bound what larger line movement, incomplete quotes or later pulls could do.

## What was checked

The frozen capture contains5,908standard-market rows. The current helper keeps3,145, including502rows older than a newer snapshot for the same event/book/market/player. Those rows span223groups and131rawplayernames; that131count is not an entered-slate count. CompleteOver/Underpairs do not mix timestamps in this capture, though synthetic preflight showed the existing reader permits that behavior. There are no same-snapshot multiple thresholds or conflicting identical-key prices at the newest snapshots here.

The treatment changes only the snapshot function. It retains the entire latest pre-main-lock snapshot, preserves simultaneous alternate thresholds, refuses conflicting prices and does not borrow an absent side from an older snapshot. The existing production market_points function still performs the same de-vig, conversion, alias matching, averaging and minimum-two-market requirement. Synthetic moved-line, postlock, incomplete-side, simultaneous-alternate, duplicate and conflict checks pass. Quotes/schedules are frozen; names are captured once and reused by both arms.

The first numerical run completed and saved every comparison dataframe but failed JSON rendering on an optional missing display name for a player outside the proof frame. Version2 converts those optional missing fields to JSONnull. Control, treatment, paired rows and names were compared against the original saved frames and are **exactly equal**; no estimate, treatment rule or parameter changed. Original source/log/partial JSON remain retained.

## Recommendation and boundary

Keep this defect open for a separately reviewed coherent-snapshot application fix. The current effect is much smaller than the missing-usage failure already repaired, and this comparison does not justify changing the weekend selector or silently adding a fourth production release. Before an application patch, verify historical event-identity support, declare the policy for incomplete newest snapshots and simultaneous thresholds, and test all callers and fallback paths. A future deployment needs its own explicit scope decision and rollback plan.

Odds data demonstrably enter the live projection consumer; this result concerns how to use that feed correctly, not whether the feed is unused. It does not change the separate SIS/FP evidence or renewal conclusions.

[Protocol](2026-09-19-prop-snapshot-impact-protocol.md), [support census](reviews/evidence/2026-09-19-prop-snapshot-live-census.json), [complete numerical result](reviews/evidence/2026-09-19-prop-snapshot-impact.json), [original source](reviews/evidence/2026-09-19-prop-snapshot-impact.py), [serialization-only version2](reviews/evidence/2026-09-19-prop-snapshot-impact-v2.py). Independent review requested.


The complete small input/output bundle is published at `gs://nfl-2-506823-lab/research/week2-input-release-20260919/prop-snapshot-impact-v1/manifest.json`, generation `1789801556753832`, SHA256 `28df3d976aeae371dc8c2ce43ba4b77cd3bde027a051a6975e7d5a64024457b6`. Includes quotes, schedules, names, both market estimates, paired rows, exact production-pool identities, proof frame and analysis/consumer source. All objects were downloaded and hash-verified. [Publication identities](reviews/evidence/2026-09-19-prop-snapshot-publication.json).


Historical identity **presence** checking is complete: all176,046standard-market rows across2023–2026 have nonempty event IDs, parseable snapshot timestamps, quote identities and prices. This removes the specific missing-event-ID concern for the current warehouse; it does not establish unique or correct event identity, settle incomplete-snapshot policy or establish historical performance. [Exact support query/result](reviews/evidence/2026-09-19-prop-snapshot-historical-identity-support.json), job `c8fc2906-da6e-4601-9a27-1e9559f19229`.

## Follow-up: the experimental rule is not a general repair

Workstation review `88bb876` identified two 2026 Week 1 bookmaker/market/player groups carrying multiple event IDs. A separate read-only laptop census independently reproduces the season counts, all 45 affected raw rows, and the retained-price counterexample. There are no such groups in 2023–2025 or the captured Week 2 data. Production retains the newest DraftKings anytime-TD quote for each affected player; the experimental event-specific rule retains an obsolete quote too:

| Player | Newest price retained by both | Additional old price retained by experiment |
|---|---:|---:|
| Emari Demercado | +475, September 13 | +425, August 30 |
| Kayshon Boutte | +340, September 13 | +550, August 23 |

This would give an obsolete observation an additional vote in the market average. A synthetic sequential-event-ID fixture also reproduces the failure. The original experimental source and results are preserved; no revised treatment was tested or deployed. The Week 2 effect remains valid for its frozen inputs, where adding event ID to the grouping is inert. **Do not copy this experimental snapshot function into production.** A general repair must resolve quote identity as well as snapshot coherence and incomplete-side policy.

The peer characterized the multiple IDs as re-keying of the same event. Our additional inspection does **not** establish that explanation: the affected raw rows have different team pairs and kickoff times. Demercado's old/new records name Chiefs–Broncos and Giants–Cowboys; Boutte's name Seahawks–Patriots and Texans–Bills. Provider re-keying, player movement and bad upstream association require separate source tracing. The retained-obsolete-quote counterexample does not depend on choosing among those explanations.

Review `305e325` reconciled the published numerical summaries and checked the source mechanism and serialization-only change. That is not yet an independent consumer replay from the raw bundle. Its reference to 100/160 reaching an entered book is incorrect: those are **available players in the post-filter proof frame**, with no selected-book effect measured. A future production-only consumer change also would not itself change the lab SHA; both applications still need their own caller review before deployment.

[Independent census and counterexample](reviews/evidence/2026-09-19-prop-event-identity-check.json), [separate research check](reviews/evidence/2026-09-19-prop-event-identity-check.py), [raw event metadata](reviews/evidence/2026-09-19-prop-event-identity-metadata.json).
