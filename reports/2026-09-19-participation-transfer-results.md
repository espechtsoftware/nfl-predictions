# Participation-aware selection improves this modeled book, with a clear tradeoff

The fixed current-snapshot test found a selection improvement **if the prior-season participation probabilities describe the designated players**. On the unchanged 1,600-candidate pool, the 97-lineup book's independently simulated chance of 220+ rises from **10.360% to 12.710%**, and expected maximum rises **3.409 points**. Both component simulators improve. This is a credible mechanism to prepare for the weekend; it is not evidence of an observed NFL scoring gain.

The existing vetting step already moves the risky first lineup down. Therefore **the first delivered lineup is identical** in both arms. The main improvement changes membership later in the book, where moving a risky lineup down does not remove its entry.

| Evaluation assumption, whole 97 | Ordinary selection | Participation-aware | Change |
|---|---:|---:|---:|
| Participation mixture: expected maximum |192.483|195.892|+3.409|
| Participation mixture: P(220+) |10.360%|12.710%|+2.350 percentage points|
| Participation mixture: winner-CDF proxy |0.103525|0.119725|+0.016200|
| All designated players play: expected maximum |199.900|196.800|−3.099|
| All designated players play: P(220+) |17.195%|13.485%|−3.710 percentage points|
| Model-implied fraction of lineups with an inactive |47.922%|6.582%|−41.340 percentage points|

The last row is a model expectation, not an observed inactive rate. The all-active loss is substantial and is reported alongside the gain. Ordinary selection assumes designated players' existing score distributions without explicit participation sampling; the treatment gives them zero in the worlds where the map says they do not play. These different assumptions, not Monte Carlo precision, dominate the decision.

Under the participation audit, incumbent and hsim expected-max deltas are respectively **+3.585 and +3.233**; P220 deltas are **+2.060 and +2.640 percentage points**. The equal-mixture paired Monte Carlo 95% intervals are [3.289,3.529] points and [2.092,2.608] percentage points. These narrow intervals quantify simulation noise for fixed assumptions, not uncertainty about the map or football predictions.

## What changes in selection and delivery

Both arms use exactly the same 1,600 candidates and exactly 97 unique legal lineups. No candidate was removed by the current eligibility check. They share 51 selected rosters; 46 change per side. Under the fixed map, Zay Flowers (Doubtful/Limited) has 6.52% participation probability, and Tua Tagovailoa (Doubtful/DNP) has 1.98%. Flowers exposure falls 39→0 and Tagovailoa 4→0. Questionable players are still selected: Ladd McConkey 22→13, Chris Olave 6→4 and Joe Burrow 4→2. These are consequences of expected-max selection, not a hard ban on Q/D players.

The unchanged vetting helper marks 60 ordinary lineups and 19 participation-aware lineups as material risk, with zero hard flags in either. It promotes ordinary rank 10 to the first delivered slot, which is already the treatment's raw first. Both first delivered rosters contain C.J. Stroud, Bijan Robinson, Javonte Williams, Ja'Marr Chase, Justin Jefferson, Kendrick Bourne, Xavier Hutchinson, Dalton Schultz and San Francisco DST. This names a research comparison, not a recommendation to enter that roster.

After vetting, prefix 30 expected maximum improves 0.441 points and its P220 changes +0.105 percentage points (interval crosses zero). Prefix 10 expected maximum improves 0.601 but P220 changes −0.070 percentage points (also inconclusive). The first slot changes by exactly zero. Whole-book results are unaffected by reordering. Every declared prefix and contest-block result is retained in the full output; there was no selection of a favorable prefix for the headline.

## Evidence, limits and next concrete step

The protocol and source froze at production `91fff1ed`. Original control ordering reproduces exactly. Synthetic all-active identity, deterministic masks, real-input support and full offline selection/vetting checks pass. A separate legality check finds zero DraftKings or house-strategy violations in all four raw/delivered books. A portable replay independently reopens the same bytes and reproduces every numerical result, exposure, mask, selected roster and delivered order exactly on this laptop. External independent review is requested, not yet completed.

The source map and September 10 K80/D800 rehearsal are real and pass their production validators; the peer independently checked their object identities and corrected its earlier claims. This does not establish prior entered use or current D12800/K97 certification. The new snapshot is 11:50:49.748032UTC, with 10:03 injury and 11:41 DK collector times. Provider `date_modified` is NULL, so the report claims collector-time provenance only. The initial raw-DK week query returned no rows because its `week` field is NULL; the retained repair uses exact draft group 153428 and asserted Sunday-main game dates.

The base forecast audit banks were used in earlier experiments; availability masks are fresh and independent of selection. No current football outcomes, bank991 or new historical fit were opened. Production components train on played outcomes, which supports treating participation separately, but blended means and shaped marginals may still embed some injury information. That limitation needs continued validation.

My recommendation is to prepare participation-aware reselection as a concrete, separately reviewable weekend option. The current build already saves both required player score banks, so it can be tested on its completed full corpus without rerunning candidate generation or changing the timer's build source. Before proposing adoption, demonstrate exact control replay and legal K97 delivery from those ordinary saved artifacts, enforce fresh status inputs, and handle **confirmed-active players** correctly. A stale Questionable label must not continue to assign nonparticipation probability after official active information is known. Saturday's conditional benefit must not be presented as Sunday's final-book benefit before that transfer is checked.

[Frozen protocol](2026-09-19-participation-transfer-protocol.md). [Full result](reviews/evidence/2026-09-19-participation-transfer-result.json). [Portable artifact identity](reviews/evidence/2026-09-19-participation-publication.json). No live policy or entry file has been changed.
