# O-62b probe: does the flipped `spread` change the lab's live draws and pool? (design, written before any run, 2026-10-08)

**Status:** design committed BEFORE the first run. The reviewer drafted it (10-08); the laptop amended §4's pool line
before any run (the reason is given there). Nothing here changes the live center, a pin or the money path.

**Units:** DK points, ratios, shares.

## 1. The question
The lab live center (`scripts/live_week.py`, week5-live-center @ `f69598b`) predicts the lab components on the live
frame's rows. Those rows carry the live sign of `spread` (POSITIVE = favoured), while the components were trained on
`player_week_training` (NEGATIVE = favoured). Production's centring sets the means, but each modeled skill player's draw
SHAPE comes from the components, and the draws feed the T-70 pool (O-62b in `reports/OPEN-DEFECTS.md`). How large is the
effect?

## 2. Arms
The same frame, the same inputs, and the same seed. Only the components' `spread` input differs:
- **LIVE:** as served now.
- **TRAIN:** `spread` = game_total − 2 × implied_team_total, the training sign. It is set on the rows passed to
  `predict_components`, after `fill_cold_start_features`.
- **LIVE_SEED (the noise reference, the laptop's amendment):** LIVE at generation seed 2027 instead of 2026. It shows
  how much a different seed alone moves the same measures.

Everything else stays identical, including production's `expected_game_script` and the centring.
**Assertion:** for LIVE and TRAIN, the rows passed to `predict_components` are dumped, and every column other than
`spread` must be byte-identical. Otherwise the probe stops.

## 3. How it runs
- **Code:** `live_week.py` itself, from a separate probe worktree. The pinned live center is never touched. The worktree
  is nfl2 at `f69598b`, plus env-gated blocks committed on `production/o62b-probe-20261008` (`b8f7bc9` after the pre-run amendment).
  - `O62B_PROBE_SPREAD=train` rebuilds `spread` on the component rows.
  - `O62B_PROBE_DUMP=<path>` writes those rows.
  - With neither set, the code is byte-identical in behaviour to `f69598b`.
- **W4 (tonight, after the study-65 run):** the W4 T-70 receipt's configuration (run `20261004T155026918221Z-32cdb61`),
  with `NFL2_LIVE_CENTER=production`, draft group 154078, and these settings:

  | Setting | Value |
  |---|---|
  | `--selector` | `mean` |
  | `--lev` | 0 |
  | `--boom` | 4800 |
  | `--sims` | 10000 |
  | `--k` | 1 |
  | `--seed` | 2026 (LIVE_SEED 2027) |
  | `--entries` | 105 |
  | `--max-per-game` | 4 |
  | `--tail-sleeve` | 5, `--tail-line 210`, `--tail-sleeve-selector mean` |
  | `--class-sleeve-every` | 2, `--class-model ~/week4-sunday/class_model.json` (`92cec733`) |
  | `--mean-max-shared` | 7 |
  | `--mean-dst-cap` | 0.25 |

  - The inputs are today's warehouse reads for W4. They are identical across the three arms, but not byte-equal to the
    T-70 run's. That is disclosed: the comparison is between arms, not against the T-70 run.
- **W5 (Friday):** the same three arms under A3's settings and A3's draft group.

## 4. Measures and the pre-stated line
**Measures,** by position over the modeled skill players. The draws are each run's `incumbent_player_scores.npy`: the
selection bank, after centring.
- the per-player draw sd ratio TRAIN / LIVE: the median, and the share outside ±5%;
- the p90 and p99 differences (TRAIN − LIVE), in points: median and max |diff|;
- the within-team correlation of each QB's draws with his team's WR1 / TE1 (by mean projection), TRAIN vs LIVE. If the
  components only set per-player marginals, it is reported as such;
- the T-70 pool (`candidates.parquet`):
  - the Jaccard overlap of the candidate lineups, all and by tag (`boom`, `boom:class`);
  - the top-30 players' exposure changes (absolute share-point change).

Every pool measure is also given for LIVE vs LIVE_SEED.

**The line for bringing it to the operator before Saturday's arming.** It is a stop rule only.

It is crossed if EITHER:
- **(a)** the median |sd ratio − 1| > 5% at any position; OR
- **(b)** the TRAIN / LIVE pool Jaccard is < 0.70 AND below the LIVE / LIVE_SEED Jaccard.

*Amendment, written before any run:* lineup solves can be sensitive to small draw changes, so the 0.70 bar alone could
trip on noise. Requiring the sign to move the pool MORE than a seed change does is what separates an effect from noise.

- **Below both:** it is recorded as small, and fixed after Week 5 together with O-62.
- **Above either, the operator gets two options:**
  - (a) Week 5 as is, the pin unchanged;
  - (b) the TRAIN sign. This would come only after a Friday rehearsal on A3's frame, per the money-path rule "never enter
    an untested rule".

**Pre-run amendments (2026-10-08, before any run; neither changes an arm, a measure or the line):**
1. `live_week.py` asserts that the lock is still ahead, so a Week-4 replay cannot run. The probe branch adds
   `O62B_PROBE_ALLOW_PAST_LOCK=1`, which skips only that assertion. It is set on all three W4 arms and unset for W5.
   Because the warehouse reads happen after the games, the W4 inputs are post-lock (statuses included). They are still
   identical across the arms.
2. The reviewer asked that the report print the LIVE / LIVE_SEED Jaccard beside the TRAIN / LIVE Jaccard, by tag. This
   adds one print line.

3. **(after the first W4 attempt, before any measured run) W4 is infeasible; W5 runs tonight instead.**
   - The W4 LIVE arm stopped inside `predict_components` with zero component rows. The live frame takes its features
     from production's inference table, which holds only the upcoming week (W5 now), so every W4 player has
     `has_features` false. Nothing was measured; the failed arm's log is kept in `~/private/o62b-probe/w04/`.
   - The three arms run on **W5 tonight**, with W5's lock still ahead, so the past-lock switch is unset.
   - The settings are the W5 arm's: group 154468, `--selector mean`, `--lev 0 --boom 4800`, `--sims 10000 --k 1`,
     `--seed 2026` (LIVE_SEED 2027), `--entries 26` (Rev6 head; tail sleeve 0), `--emit-a5-sidecars`,
     `--max-per-game 4`, `--class-sleeve-every 2 --class-model ~/week5-sunday/class_model.json` (`92cec733`),
     `--min-proj 1.0` and `--mean-dst-cap 0.25`.
   - The inputs are tonight's warehouse reads, identical across the arms. Friday's A3-frame run becomes optional: it is
     repeated only if tonight's result sits near a line.
   - Measures, lines and verdict are unchanged.

**Reporting:** W4 first, then W5 Friday, with the probe patch's commit and the measurement script's sha256
(`reports/2026-10-08-o62b-probe/probe_measure.py`).

## 5. Result, W5 (2026-10-08 evening): SMALL; fixed after Week 5 with O-62

- **Verbatim output:** `reports/2026-10-08-o62b-probe/REPORT-w05.txt`, from the measures `5c267fb0`. The lab probe is
  `b8f7bc9`, and the run dirs are under the probe worktree. The private copies are in `~/private/o62b-probe/w05/`.
- **One operational re-run, disclosed.** The first LIVE arm read the 19:59:45 UTC DraftKings pull, while TRAIN and
  LIVE_SEED read the 20:59:45 pull (11 statuses changed). The design's assertion stopped the measures, so nothing was
  measured. LIVE was re-run at once on the 20:59:45 pull. All three arms' component rows are then identical but for
  `spread`, LIVE and LIVE_SEED are byte-identical, and the frames are identical on 139 input columns. The first LIVE
  run is kept privately (`first-LIVE-19z/`).
- **(a) The draw shape: no change at all.**
  - Every modeled skill player's TRAIN draws are the SAME multiset of values as his LIVE draws: the sorted draws are
    identical, while only 11.9% of draws sit in the same world.
  - The served draw shape is a rank-preserving TabPFN quantile remap (`core/draw_shape.py`), shifted to production's
    mean. The components' `spread` therefore reaches only the ORDER of the worlds (which players score high
    together), never a player's marginal.
  - So the sd ratio is 1.0000 and the p90 / p99 differences are 0.000 at every position. (LIVE_SEED's marginals differ
    slightly, as a reseed should.)
- **The joint shape** (the mean QB–WR1 / QB–TE1 correlation over 22 teams):

  | Arm | QB–WR1 | QB–TE1 |
  |---|---|---|
  | LIVE | 0.3582 | 0.3189 |
  | TRAIN | 0.3589 | 0.3153 |
  | LIVE_SEED | 0.3596 | 0.3168 |

  TRAIN sits inside the seed noise.
- **(b) The pool:**
  - Any change to the draws rebuilds the 4,800-solve pool almost entirely: Jaccard TRAIN / LIVE 0.006, against
    LIVE / LIVE_SEED 0.005.
  - The sign moves the top-30 exposures LESS than a reseed does: median 0.0025 vs 0.0033, max 0.0089 vs 0.0139.
- **The verdict by the pre-stated line:** both lines are below, so the effect is SMALL. O-62b stays open and is fixed
  with O-62's frame decision after Week 5. Week 5 runs the pin unchanged. Friday's A3 repeat is not needed: no
  number is near a line.
