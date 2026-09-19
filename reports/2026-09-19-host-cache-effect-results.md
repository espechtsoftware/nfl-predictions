# Historical-cache sensitivity changes joint worlds, not player marginals

Both actual live CLI rehearsals passed against the refreshed warehouse. Using a freshly queried historical cache instead of the exact August 29 workstation cache leaves served player means and **each player's complete 10,000-score multiset identical**. It nevertheless changes 3,818,855 of 4,280,000 incumbent-bank cells: scores occupy different simulated worlds. The hsim bank is byte-identical.

The 32 leverage candidates are shared, but the 128 boom candidates in each run are disjoint. The ordinary selected books share only 8 of 97 lineups, with the same first lineup. This is a mechanism finding, not evidence that either book scores better. These are pre-vetting books, not entered lineups.

| Check | Result |
|---|---|
| Source, structural settings, seeds, live input hashes, projection batch, player order | All match |
| Historical key sets | Same 102,927 rows |
| Historical values | Prior comparison found 3,472 rows differing materially in baseline inputs/activity eligibility |
| Historical training row order | Different |
| Served means, incumbent per-player multisets | Exactly equal |
| Incumbent world matrix | Different |
| Hsim world matrix | Exactly equal |
| Candidate overlap | 32/160 |
| Ordinary book overlap / same first | 8/97 / yes |

The fitted component simulator supplies ranks to the TabPFN marginal remapping. That remapping can preserve every player's marginal distribution while changing which players boom together. Therefore equality of projections or marginal quantiles cannot establish full-law equivalence. The earlier frame comparison found only floating roundoff in model_points_pre (maximum 7.1e-15); that alone did not reveal the changed joint worlds.

This pair changes **both cache values and training-row order**. It does not isolate the effect of accumulated source corrections from order sensitivity. The [frozen two-run inspection](2026-09-19-host-cache-effect-protocol.md) measured marginal and roster differences; the exact world/multiset diagnostic was added after seeing the unexpected combination of identical marginal summaries and low roster overlap. Neither analysis reads current NFL outcomes or scores a proposed selection improvement.

The actual workstation cache remains unchanged. The representative host-cache proof passes and is the release gate. A future cache policy should bind source identity, schema/content and row ordering, and test downstream effects; freshness alone is not an adoption argument.

Evidence: [frozen-reader output](reviews/evidence/2026-09-19-host-cache-effect.json), [additional joint-world diagnostic](reviews/evidence/2026-09-19-host-cache-joint-diagnostic.json), [actual host-cache proof](reviews/evidence/2026-09-19-release-live-cli-host-proof.json), [fresh-cache proof](reviews/evidence/2026-09-19-release-live-cli-fresh-proof.json).
