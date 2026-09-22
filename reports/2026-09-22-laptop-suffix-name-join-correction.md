# Correction: a name-suffix join bug inflated today's "phantom" figures — what changes and what does not

**`snap_counts` lists players without generational suffixes ("Aaron Jones"); `dk_salaries` keeps
them ("Aaron Jones Sr.").** My name normalisation stripped only non-letters, so every suffixed
player who *played* read as zero snaps and was counted as a non-player. Verified directly: Aaron
Jones, Luther Burden, Travis Etienne, Deebo Samuel, Chris Godwin and Kyle Pitts all logged 26–56
offensive snaps in Week 2. Fixed by stripping `jr/sr/ii–v` as whole tokens;
`reports/lab-handoffs/phantom_contamination.py` is corrected.

## Changed (Week 2)

| figure | reported | **corrected** |
|---|---:|---:|
| genuine phantoms (proj ≥ 5, zero snaps) | 38 | **28** (22 QB) |
| pool share carrying ≥ 1 | 63.8% (`b8e41660`) | **47.3%** |
| zero-phantom control group | 4,543 | **6,614** |
| Spearman(sel_mean, realized) on clean candidates | −0.345 | **−0.366** |
| availability share of the −0.49 inversion | ~30% | **~25%** |
| Questionable (never D/OUT) play rate | 77.4% | **83.9%** |
| Questionable PPR per $1k (vs never-designated) | 1.274 vs 1.003 | **1.290 vs 1.026** |

## Unchanged — rechecked with the fix

| figure | value |
|---|---:|
| **Doubtful player-weeks that played** | **0 of 13** — the Doubtful exclusion's evidence stands |
| backup-QB snap rate | 10.1% → 10.7% (immaterial) |
| QB gate precision / recall (pre-lock frame) | **89.6% / 87.8%** |
| frame QBs with zero snaps; pool with a dead QB | 37 of 69; 19.7% |
| QB gate pool-mean effect | **+2.8** |
| Week-2 inversion, all candidates | −0.4908 |

The Questionable changes run the same direction as before and **strengthen** the case for keeping
Questionable players in the pool: 84% of them played, and they returned about 26% more per dollar.

## New, with corrected names — the Sunday-relevant result

Across the 97 entered Week-2 lineups there were **57 slots holding a player projected ≥ 5 who never
took a snap.** Under the rules now deployed for Week 3 — DK Doubtful/Out/IR denylisted before any
solve (nfl2 `69f98a7`) plus the backup-QB gate with both refinements (`98efdfa6`):

| player | pos | entered rows | caught by |
|---|---|---:|---|
| Zay Flowers | WR | 48 | Doubtful at build → denylist |
| Tua Tagovailoa | QB | 5 | gate + Out |
| J.J. McCarthy | QB | 1 | backup-QB gate |
| Aidan O'Connell | QB | 1 | gate + Out |
| Michael Pittman Jr. | WR | 1 | Out pre-lock |
| RJ Harvey | RB | 1 | **not caught** (Questionable) |

**56 of 57 (98%).** The Week-3 rules would have removed essentially every non-playing player from
the book that was actually entered. The one miss was Questionable, and that designation is now
handled by the 0.80 haircut rather than by exclusion, which is correct given that 84% of
Questionable players play.

Caveat: "flagged Doubtful/Out at a pre-lock pull" assumes the flag was present at the pull the
build used; Flowers was Doubtful at the Week-2 build, and Pittman's Out needs the T-70 rebuild on
the post-inactives pull, as the standing money-path rule requires.

**Also superseded:** the draft figures "55% of the gap to the field median closed" and "64 of 97
entered rows" that I computed before finding the bug and did not push. Corrected: **45%** and
**51 of 97**.
