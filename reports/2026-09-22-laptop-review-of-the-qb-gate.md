# Review: the backup-QB gate works — 89.6% precision, 87.8% recall, 28:1 on points

Second-party review of the QB availability gate merged at `b76f5cd9`. **Verdict: ship it.**
I tested it against outcome data it was not built on, and it holds. Two findings follow,
one of them evidenced and cheap.

## The gate, scored against what actually happened

Production's committed live-frame evidence (83 QBs in, 48 gated), joined to Week-2
`snap_counts` — an outcome the gate never sees:

| | zeroed | kept |
|---|---:|---:|
| **took no snaps** | **43** | 6 |
| took snaps | 5 | 29 |

- **Precision 89.6%** — 43 of the 48 zeroed QBs never took an offensive snap.
- **Recall 87.8%** — it caught 43 of the 49 QBs who never played.
- **364.3 projection points removed. Those 48 QBs scored 13.1 points in total.** A 28:1
  ratio of phantom projection to reality.

The five "false positives" are mop-up duty, not starts: Mariota 32 snaps (8.74 pts against
a 12.21 projection), Bagent 10 (2.16), Mac Jones 8 (−0.20), Pickett 4 (−0.40), Rudolph 3
(0.30). **The gate's mistakes cost 13 points of upside to remove 364 points of fiction.**

Tests are real, not decorative: 13 pass, and mutating the ambiguity guard to a no-op fails
**4** of them.

## Finding 1 — the ambiguity rule leaves the most dangerous case untouched, and it is the
gate's single most expensive miss

The rule: *"A Doubtful or Questionable primary makes the team ambiguous — nothing is gated."*

Atlanta in Week 2: depth-1 **Michael Penix Jr. was Out**, so the primary became depth-2
**Tua Tagovailoa, who was Doubtful**. Ambiguity rule fires, nothing is gated, and Tua keeps
a **17.47** projection at $4,700.

**He took zero snaps and scored zero.** He is the largest single miss in the whole frame.

**The evidence says the default is backwards.** My Doubtful cohort work
(`a4378fdd`) measured **13 Doubtful player-weeks in 2026: zero snaps, zero points, all 13**,
at the highest mean salary of any status cohort. A Doubtful player is not an ambiguous
signal — in this feed he is a near-certain absence. "Doubtful primary → do nothing" is the
one branch where doing nothing is most expensive.

**Questionable is genuinely ambiguous and should keep the current treatment** — 124 Q
player-weeks, **77.4% played**, and better value per dollar than unflagged players. The rule
is right for Q and wrong for D, because it treats them as one class.

**Cheapest correct version:** a Doubtful QB cannot *be* the primary. Promote the next
non-out, non-doubtful QB and gate behind him. That is one predicate change and it aligns this
layer with nfl2, which already denylists `D` at eligibility.

## Finding 2 — the two layers disagree about Doubtful, and only one of them is right

`cascade_adjust.OUT_STATUSES = {"O","OUT","IR"}` (nfl-predictions) against
`live.DK_INACTIVE_STATUSES = {"O","OUT","IR","D"}` (nfl2, since `69f98a7`).

The module comment explains the exclusion: *"most doubtful players sit, but zeroing them
would erase real late-swap decisions; their depressed practice features already carry the
signal."*

**"Their depressed practice features already carry the signal" is empirically false.** Zay
Flowers was served **22.57** and Tua **17.47** — both Doubtful, both zero. The features did
not depress those projections at all.

The money path is currently saved by nfl2's eligibility denylist removing `D` before any
solve. But **anything reading `player_projections` directly gets the inflated number** — the
exposure sheet, `div_shadow`, and every retrospective analysis. The layers should agree, and
the evidence says they should agree on nfl2's side.

## The residual the gate cannot reach, by construction

Two of the six misses are **depth-1 QBs with no status at all** who did not play: Jaxson
Dart (NYG, $5,800, proj 18.86) and Matthew Stafford (LA, $6,000, proj 17.41) — **36.3 points
of phantom projection between them**. Both played in Week 1 (69 and 51 snaps), so these are
real absences, not a join artifact.

A *backup* gate cannot catch a *primary*. That is a different defect — inactive/roster data
arriving too late, or a depth chart that was wrong — and it is the larger remaining slice of
the QB problem now that the backups are handled.

## What I checked and did not find

No interaction with the roster invariant: gated QBs keep their rows with a zero projection,
so team row counts are unchanged and `apply_roster_status_invariant` cannot be tripped by
this. No failure mode where a team loses every QB: the primary is never gated. The
`QB_BACKUP_GATE=0` escape hatch works without a redeploy, which is the right shape for a
money-path gate shipped mid-week.
