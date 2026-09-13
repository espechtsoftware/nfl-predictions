# Week-1 morning decision — 2026-09-13 (lock 12:00 CT)

**Status:** draft written 2026-09-12 ~19:00Z with the decision rule frozen; the PREREG-090 read fills §2
when the three r2 banks complete (expected ~21:00–22:00Z). Nothing here opens a 2026 outcome.

## 1. What is fixed regardless of the read

- **Paid book = corrected centering.** Every Week-1 book is built with `NFL2_LIVE_CENTER=production` from
  `/home/erich/projects/.nfl2-worktrees/week1-live-center-e7255e9` (skill AND DST centred on production's
  served projections; level gate on; receipts record `naive_top_lineup_projection` ≈145–160, `matched_skill`
  ≈362, `dst_matched` 24). The uncorrected lab level (RB/WR ≈ 8 pts, salary-ranked DST) is not an option.
- **Paid policy = P_MIX on the D800 pair** through the governed publisher (P_CTRL fallback), unless §2
  moves the dose.
- **Entry layout:** 90 unique lineups (Milly 1–57, Play-Action 58–77, FFWC-Q6 78–80, FFWC-Q5 81–90) from
  the K90 build; the alternative 57-unique + duplicated top ranks is inferior for a weekly-max objective
  (audit §3.4). The K90 book's ranks 1–80 are identical to the K80 paid book (verified), so P_MIX's K80 and
  the K90 layout compose: Milly gets P_MIX ranks 1–57; the other three contests take K90 ranks 58–90 of the
  same-seed build (P_CTRL-equivalent rows, since P_MIX is defined on K80 only).
- **Shadows (frozen, never entered):** D400_DEMAX, D800_WEMAX, direct-tail, DT-union, spread-4, NOBB sleeve,
  D1600 and D3200 (PREREG-090 did not move the dose; PREREG-091 read 01:15Z: spread-4 UNRESOLVED, column
  pricing FAIL vs its dose reference; PREREG-092 read 03:58Z: scenario reduction UNRESOLVED both arms;
  PREREG-094 read 06:30Z: dose × novelty retrieval UNRESOLVED/near-miss — no adoption, no sleeve from any of
  the four; PREREG-093 (3200) reads ~11:15Z and cannot select 3200 unless its own D1600 − D800 replication
  passes).

## 2. The dose decision (fill from the frozen reader)

PREREG-090 consequence 1: `D1600_DEMAX` **PASS** on the r2 cohort **and** the live D1600 receipts not worse
than D800's under both laws (already true: 178.6 vs 177.7 incumbent, 199.0 vs 198.4 hsim, P≥220 .021 vs
.018 / .141 vs .133) → the Milly book becomes the corrected **D1600 DEMAX K90** (lev 320 / boom 1280) via
the run-dir upload path (P_CTRL-equivalent; the governed P_MIX publisher only accepts the 160/640 pair), and
the P_MIX D800 K80 book is frozen as the primary shadow. Any other verdict → the D800 P_MIX plan above.

**Live receipts (outcome-blind, built Saturday on `e7255e9`, all three books scored under the D800 build's
own two banks; `score_book_under_bank.py`) — the live-receipt conditions of PREREG-090 consequence 1 and
PREREG-093's ladder are satisfied: every line is monotone in dose.**

| live book (K80) | law | E[max] | P(≥194) | P(≥210) | P(≥220) | pool P(≥220) |
|---|---|---:|---:|---:|---:|---:|
| D800 `…192221336726Z` | incumbent | 179.5 | .209 | .062 | .023 | .054 |
| D1600 `…203440469470Z` | incumbent | 180.6 | .225 | .069 | .026 | .082 |
| D3200 `…194342612416Z` | incumbent | 181.1 | .237 | .072 | .027 | .114 |
| D800 | corrected-hsim | 196.4 | .516 | .227 | .115 | .210 |
| D1600 | corrected-hsim | 197.0 | .529 | .235 | .118 | .285 |
| D3200 | corrected-hsim | 198.3 | .552 | .259 | .138 | .369 |

Build cost on this workstation: D800 5 min, D1600 14 min, **D3200 51 min** (3,040 s). A D3200 K90 with
sidecars was built Saturday 20:49–21:39Z as the Sunday fallback for the 3200 dose: run dir `…/week1-live-center-e7255e9/results/live/2026-w01/20260912T204921…-e7255e9` (salary pull 20:04Z; 90 unique rosters, its own K80 nested), upload CSVs `/home/erich/week1-sunday/upload-FALLBACK-D3200-K90-20260912T204921-e7255e9-{milly-193028206-ranks-1-57, playaction-193028208-ranks-58-77, ffwc-q6-194478066-ranks-78-80, ffwc-q5-194478065-ranks-81-90}.csv` — usable only if the read selects 3200 AND the Sunday D3200 build cannot finish before ~10:45 CT; re-check DK inactives against its rosters first.

**Read procedure (PREREG-090 amendment 4):** Cloud Run lost 13 r2 tasks to platform "Internal error"; the
registered finish launcher re-runs exactly those slates on the same image. Read from the amend4 worktree:
`cd /home/erich/projects/.nfl2-worktrees/prereg090-amend4 && PYTHONPATH=src /home/erich/projects/nfl2/.venv/bin/python
scripts/prereg090_report.py 110b900r2-20260912T191557Z 110b901r2-20260912T191821Z <110b902r2 run id>
--repair <each 110b9NNr2rep<season> run id>` (run ids: cohort worktree `results/queue_110_launches.log` and
`results/queue_110_finish_launches.log`).

**Read 2026-09-12 23:27Z** (amendment-4 reader `3ec0d8b`, transcript sha256 `c515d696…`, repaired slates listed in
the transcript header). **No treatment passed — the paid dose stays 800 (D800 P_MIX plan); `/home/erich/week1-dose.env`
is NOT written.**

| reader line | value |
|---|---|
| `D1600_DEMAX − D800_DEMAX` | proxy −0.00061 fam[−0.00773, +0.00693], banks +.0067 / −.0095 / +.0010, W/L/T 26/43/3, LOSO +/−/−/+, **UNRESOLVED**; raw K80 −0.739 [−3.05, +1.05] |
| `D800_DT_DEMAX − D800_DEMAX` | proxy −0.00235 fam[−0.01244, +0.00709], banks +/−/+, W/L 33/39, **UNRESOLVED**; raw −0.645 |
| `D1600_HALFDT_DEMAX − D800_DEMAX` | proxy +0.00238 fam[−0.00380, +0.00867], banks +/−/+, W/L 34/37, **UNRESOLVED**; raw +0.449 [−0.44, +1.19]; count-matched reference +0.00198 (≈ the full D1600) |
| threshold events (weeks of 72 ≥200/210/220/230) | D800 8/2/1/0 · D1600 9/4/1/0 · DT 12/3/0/0 · HALFDT 11/3/1/0 |
| supply per slate-bank ≥200/≥210/≥220/≥230 | D800 1.04/.37/.08/.04 · **D1600 2.28/.77/.19/.06** · DT 1.17/.40/.10/.02 · HALFDT 2.13/.77/.18/.06; pool oracle 194.9 → 198.8 (D1600); best-in-book .204 → .102 |

Reading: the 1600 rung doubles the tail supply and the book does not convert it — retrieval, not supply,
binds above 800 with the DEMAX selector. PREREG-093's 3200 rung would test the same mechanism again; see
HANDOFF for the redirect decision.

## 2b. Operator decision 2026-09-13 (04:30 CT): 30 entries instead of 90, same four contests

Reason given: no book has beaten a Milly winner yet and scoring still has to improve; keep all four contests so
the leaderboard captures continue. **Layout:** ranks 1–30 of the same nested book (the selector is greedy, so ranks
1–30 of the K90 are exactly its optimal 30-lineup book) — Milly ranks 1–19 (`193028206`), Play-Action 20–26
(`193028208`), FFWC Q6 27 (`194478066`), FFWC Q5 28–30 (`194478065`). The Sunday script now emits these
`k30-*` slices beside the 90-entry ones; the P_MIX publisher step uses `--ranks 1-19` for the Milly file. Withdraw
the surplus placeholder entries in the DK UI first, then bulk-edit the kept 30.

Historical cost of 30 vs 80 (D800_DEMAX control books, 72 slates × 3 banks, PREREG-094 cohort, descriptive):
weekly max K30 172.8 vs K57 178.5 vs K80 181.4; weeks ≥200 3 / 9 / 14 of 72; ≥220 0 / 2 / 2. Rank order is a
diversification order, not a quality order (mean realized score flat from 120.5 at ranks 1–10 to 116.6 at
58–80; the slate's best lineup sits at median rank 38, in the top 30 only 41% of the time).

## 2c. Ordering shadows (frozen before lock, graded Monday) — the only legitimate "sort better" experiment

Descriptive read of the opened PREREG-083 books (72 K80 books with per-lineup simulated stats): no simulator
ordering beats the greedy order — top-30 max: greedy 171.1, sim-mean 171.0, P≥220 170.8, q99 169.9, random
169.5; the realized best lands at position 33–38 under every ordering (random 40.5); within-book Spearman of
realized score with the simulated mean +0.22, falling to +0.10 for P≥230. Sorting on the current simulator is not
a lever; only new pre-lock information could be. Prospective test: `scripts/week1_ordering_shadows.py` freezes
the top-30 sets of ten orderings (greedy = the entered layout, inc/hsim mean, inc/hsim q99, inc P≥200, hsim
P≥220, PREREG-060 novelty ladder over the book, broad phenotype, seeded random) on the Sunday K90 (the Sunday
script writes `/home/erich/week1-sunday/ordering_shadows-<run>-k30.json`); Monday each set's realized maximum
is compared with the entered 30. Tonight's outcome-blind placeholder on the DST-fixed D800 book:
`reports/week1-ordering-shadows/placeholder-D800K80-20260912T1922Z-e7255e9-k30.json` (greedy top-30 has the
highest simulated E[max] under the incumbent law, 172.6 vs 167.6–171.8; NOV ladder highest under hsim, 188.5).

**Additional ordering families (added 10:30Z, frozen the same way):** structural — salary desc, distinct teams desc,
max-per-team asc, 3-RB first, concentrated (control); player-level — prior-season DK points per game sum (the
"proven performers" heuristic), per-player P(≥25) sums under each law, cross-law agreement, player-novelty greedy;
reverse-greedy and random as controls. Descriptive hints on the 72 opened PREREG-083 books (hypothesis only):
top-30 max broad 172.4, salary desc 172.4, max-team asc 172.4, teams desc 171.9, spread 171.5, 3-RB 171.1, greedy
171.1, sim-mean 171.0; concentrated 169.6, 4-WR first 169.6, 2-TE first 169.4, reverse greedy 169.2, salary asc
166.6; random 169.4. Within-book Spearman with realized score ≈ 0 for every structural feature (salary .02, games
.03, teams .04) vs +.22 for the simulated mean. Tool: `scripts/week1_ordering_shadows.py` v2 (20 orderings).

## 2d. Optional real-entry trial offered to the operator: `D1600_NOV` on the non-Milly entries

The only overnight mechanism that scaled with supply (PREREG-094 interaction, near-miss) can be entered as a
live arm: D1600 K80 pool → PREREG-060's frozen novelty-ladder selector (`scripts/week1_nov_book.py`; selector
sha `2fb435e6…`). Against the paid policy it measured flat (D1600_NOV − D800_DEMAX −0.004, UNRESOLVED) — not
expected to be worse, upside unproven. Offered split: **Milly 19 = P_MIX ranks 1–19 (validated), Play-Action 7 +
FFWC Q6 1 + FFWC Q5 3 = D1600_NOV ranks 1–11**; or all 30 on NOV; or none (default). Opt in by creating
`/home/erich/week1-nov.env` before the 09:10 CT build: the Sunday script then builds the D1600 (14 min), the NOV
book (2 min) and emits `upload-<run>-nov-d1600-*` CSVs (ranks 1–7 / 8 / 9–11, plus 1–19 and 1–30). Placeholder
from Saturday's D1600 pool: `/home/erich/week1-sunday/nov-placeholder-D1600/` (overlap with the DEMAX book 55/80;
sim E[max] 179.4 vs 180.5 incumbent, 198.8 vs 198.4 hsim). Graded Monday as its own book either way.

## 2e. Front-30 hybrid offered for the entered set (operator's choice; hypothesis-level, replicated on two opened samples)

Rule: keep the selector's greedy core (ranks 1–15) and fill the remaining 15 with the broadest lineups of ranks
16–90 (most distinct games, then fewest from any one game, then greedy rank). Mean top-30 realized max vs plain
greedy-30: **+2.38** on the 72 PREREG-083 books (wins 35% / losses 22%), **+1.45** on the 216 fresh PREREG-094
control books (32% / 26%); core-20 +1.63 / +0.54; broad-alone +0.72 / +0.13. Direction matches the Neo4j census
(broad 200+ lineups under-selected). Not preregistered — an informed tie-break, not proof. Tool
`scripts/week1_hybrid30.py`; the Sunday build emits `hybrid15-*` slices (Milly 1–19, Play-Action 20–26, Q6 27,
Q5 28–30, plus all-30) beside the plain `k30-*` slices from the same K90; the operator picks one set. The hybrid is
built on the run-dir (P_CTRL) K90; with no Q/D/O designations on this slate P_MIX ≈ P_CTRL. Every variant is
settled Monday against the entered set.

## 2f. Additional approaches armed 11:10Z (operator asked for more than tie-breaks)

1. **T-70 rebuild with final inactives (10:50 CT = 15:50Z, armed as a session task):** `week1-sunday-build.sh`
   runs again with run tag `…-t70-e7255e9` after the 10:30 CT inactives are announced and DK marks them, so the
   entered set can be the later build (fresh salary pull with statuses applied, latest projections). Upload the
   `-t70-` CSVs by ~11:30 CT; the 09:10 set is the fallback. This is the largest legitimate information gain of
   the day — the 09:10 book cannot know who is inactive.
2. **Line-movement ordering / veto (`scripts/week1_market_move.py`):** Saturday→Sunday change in DK-implied
   points from `nfl_raw.prop_lines` (mean across books; yards, receptions, pass TDs, anytime-TD probability),
   summed over each lineup's skill players; lineups carrying a player whose lines VANISHED from the market are
   veto candidates. Frozen as a shadow right after the 09:00 CT props fetch; the ledger's reopening condition
   (market movement) — no evidence yet, so shadow/veto only unless the operator chooses otherwise.
3. **Objective-aligned coverage orderings** (`cov220_hsim`, `cov220_inc`, `cov200_dual`) — the 30 that maximise
   the simulated probability that at least one lineup scores 220+ (200+) under each law — and **world-leader**
   (how many simulated worlds each lineup wins among the book). Placeholder receipts: cov220_hsim lifts the
   top-30's hsim P(≥220) from .065 (greedy) to .077, cov220_inc lifts the incumbent P(≥220) from .013 to .019
   at the cost of the other law; historically P(≥220)-descending orderings did not beat greedy, so these stay
   shadows (v3 of the ordering tool, 24 orderings).

## 2g. Post-selection vetting pass (operator request, implemented 12:30Z; runs inside both Sunday builds)

`scripts/week1_vet_book.py` (host copy `/home/erich/week1-sunday/tools/vet_book.py`) runs after selection and ordering:
every player in every lineup is checked against live signals — DK feed status, `nfl_raw.injuries` (designation,
practice status + injury), `player_week_inference` (injury status, practice level, depth rank, games missed), prop
lines (player pulled from the market since the previous fetch; no props at all for a ≥$5k player), placeholder
salary. Tiers: **hard** (OUT/IR, market-vanished, placeholder salary) → vetoed to the back of the book; **material**
(risk ≥ 1.0: Questionable/Doubtful, injury-DNP with a silent market, no props) → demoted behind every clean lineup;
**soft** (limited practice, DNP with props posted, depth ≥ 3, rest-day DNP) → reported only; otherwise the selector's
order is kept. Output: emitter-compatible vetted book (`vetted-<run>/book.csv`), `vetting_report.md` (flagged
players with reasons; every lineup's tier and move), `vetting.json`, and upload CSVs `upload-<run>-vetted-{milly
1-19, playaction 20-26, ffwc-q6 27, ffwc-q5 28-30, all30, all90}`. Placeholder run on Saturday's K90 with live
Sunday signals: 7 players flagged (Odunze, Love Questionable + limited; Chase knee DNP but props posted → soft;
Pierce, Croskey-Merritt limited; Waller, Gadsden depth 3); ranks 13 and 22 demoted out of the top 30, 31 and 32 in.

## 2h. Post-selection player-scoring resort (operator request, implemented 12:15Z; runs after vetting in both builds)

`scripts/week1_player_score.py`: every player in the book gets an independent projected score — within-position
z-scores of production `proj_points` (.20), `proj_p90` (.15), `p_20_plus` (.20), market-implied points from the latest
prop fetch (.20), Sunday-vs-Saturday market movement (.05), the corrected-hsim (.10) and incumbent (.05) player q99
from this run's banks, prior-season DK ppg (.05), minus the vetting risk weight (hard flags exclude the lineup from
the top); lineup score = sum over the nine slots; the book is re-sorted on it (frozen weights v1). Outputs:
`composite-<run>/{book.csv, player_scores.csv, lineup_scores.csv, composite_receipt.json}` and upload CSVs
`upload-<run>-composite-{milly 1-19, playaction 20-26, ffwc-q6 27, ffwc-q5 28-30, all30, all90}`. Placeholder run on
Saturday's D800 book with today's data: top players Chase 2.22, St. Brown 2.18, Gibbs 1.98, McBride 1.85, Jaguars
1.52; the composite top-30 overlaps the greedy top-30 in 13 lineups (17 promoted from ranks 31–73). Prospective
rule: this is one more frozen ordering graded Monday; if it beats the entered set over the coming weeks, the
operator widens the entry count so more of its top bubbles into the paid book.

## 2i. Lineup-creation review (operator question, 12:55Z) and the skill-salary-floor shadow

- The $200 players were a historical-feed artifact (two player-weeks in five seasons; README deficiency row); the
  live DK feed enforces position minimums (QB/RB $4,000, WR $3,000, TE $2,500, DST $2,000) and today's book has
  nothing below them — its cheapest slots are DSTs (18 of 26 sub-$3k slots) and TEs (8); every lineup is at
  $49.0–50.0k. Panel hygiene (drop skill players below DK's position minimum in historical frames) is a Week-2
  preregistration amendment for the next cohort.
- Construction per slate: 160 "lev" lineups (repeated MILP on a tournament-valued projection, ≥2 players different
  from every previous one) + 640 "boom" lineups (the optimal lineup of each of the 640 highest-total simulated
  worlds); QB+2 pass-catchers + bring-back and the $49k–50k salary band in every solve; no punt mandate
  (`PUNT_MIN = 0`); selection = greedy expected-max over 10,000 fresh worlds × two laws.
- Shadow arm frozen today: **skill-salary floor $3,500** (QB/RB/WR/TE below $3,500 removed from the pool before
  generation; DST untouched) — `live_week.py --min-skill-salary 3500` on branch
  `lab/shadow-skill-salary-floor-20260913` (`f26b7dc`, from the paid-path commit `e7255e9`), D800 K80, fresh Sunday
  projections; graded Monday with the other shadows. Panel evidence for the direction: sub-$4k skill slots average
  6.8 points with 17% zeros; production's "punt valuation" was kept because its deletion cost tails, so this is a
  shadow, not a change to the paid book.

**Skill-salary floor, tested for today (13:10Z):** live shadow built (`…/shadow-salary-floor-20260913/results/live/2026-w01/20260913T122747041835Z-f26b7dc`,
fresh 12:03Z projections): a $3,500 floor removed 134 skill players including $3.0–3.4k starting TEs (Waller,
Schultz, Njoku, Hockenson, Kmet); simulated receipts slightly lower than the paid D800 under both laws (incumbent
E[max] 178.4 vs 179.5, hsim 195.4 vs 196.4). Selection-time version on the 216 opened books (skip lineups whose
cheapest skill player is below the floor, next ranks fill in): floor $3,000 −0.70 (wins 4% / losses 12%), $3,500
−1.00 (21/28), $4,000 −0.15 (28/29), position-specific TE≥3,000/WR≥3,500/RB≥4,000 −1.13; lineups' realized scores
are flat across cheapest-skill-salary tiers (116.8–118.2; share ≥187 ≈ 1% in every tier). **Not applied today**;
the shadow is graded Monday; a generation-time floor would need a cloud cohort (Week 2 if the shadow surprises).

## 3. Sunday sequence (times CT)

| time | step |
|---|---|
| 08:30 | confirm `s-nflverse`, `s-features-sun` and the 09:00 `project-slate` execution succeed |
| 09:10 | `/home/erich/week1-sunday-build.sh` (runbook build + preflight, K90, upload CSVs; add `/home/erich/week1-dose.env` first if §2 fired: `PAID_LEV=320 PAID_BOOM=1280` for 1600, `PAID_LEV=640 PAID_BOOM=2560` for 3200 — the 3200 build takes ~51 min, so the dose book lands ≈10:15; if it is late, upload Saturday night's D3200 K90 fallback CSVs from `/home/erich/week1-sunday/` after re-checking inactives) |
| 09:30 | publish once: runbook step 4a (`publish_week1_a5_books.py … --execute`, run id from the build log) |
| 09:35 | emit P_MIX ranks 1–19 from the published book (runbook 4b, `--book-id P_MIX --ranks 1-19`; 1–57 if the 90-entry layout is restored); take ranks 20–30 (58–90 for 90 entries) from the K90 run-dir `k30-*` / `k90-*` CSVs |
| 09:45–11:15 | upload the four contest files in the DK UI (operator-only) |
| 11:20 | re-check DK inactives; if a paid-book player is ruled out, rebuild with a new run id and re-upload (DK edits allowed until lock) |
| 12:00 | lock |

Fallbacks: corrected P_CTRL run-dir CSVs (`/home/erich/week1-sunday/upload-*`) → the DST-fixed placeholder files
emitted Saturday 19:41Z (`/home/erich/week1-upload-CORRECTED-DST-20260912T1922Z-e7255e9-*` for K80 ranks and
`…-CORRECTED-DST-K90-20260912T1933Z-e7255e9-*` for ranks 58–90; the older `…-3df1b0c-*` files are Chargers-centred
and superseded) → production app export.

## 4. Monday/Tuesday

Standings capture for all four contests (`nfl-dfs capture-dk-standings`, validation first, then
`--confirm-settled --confirm-full-field --apply`); settle every frozen run dir (`scripts/settle_live.py`),
including the shadow arms; write the tail-ledger row; append the LEDGER rows for PREREG-090/091/092.

## §2j — Learned lineup score: book re-sort and pool-level selection (13:00Z)

**Question answered:** can a learned "what a good lineup looks like" score be applied to the *entire* candidate corpus at
selection time, not only to re-sort the 90 already selected? **Yes, and historically it is the strongest ordering/selection
signal measured today** — with one live caveat (concentration) that the historical corpus could not show.

Model (frozen, `reports/2026-09-13-learned-ordering-v1.json`): ridge on 66 within-book-standardised lineup features
(sums/min/max of projection, p10/p90/std, market points, usage windows, game total, spread, implied total, depth, cold start,
salary; games/teams/stack structure) fitted to realized score on the 216 opened D800 books (2021–2024). What it says a good
lineup is: **market-backed, high-floor, high-usage players in high-total, close games**; it penalises the sum of p90, the
spread and single-player volatility — roughly the opposite of what the boom-world optimiser rewards, which is why it adds
information on top of the expected-max order.

Book re-sort (LOSO on the 216 books, top-30 realized max vs greedy order): 2021 −2.4 (no prop market that season),
2022 −0.5, 2023 +1.7, 2024 +5.2 (corr .10 → .32 as the feature set fills in). Hypothesis-level.

Pool-level (LOSO models applied to all 200 candidates per slate-arm of the Neo4j PREREG-083 corpus, 2023–2024, 72 slate-arms;
realized max of the chosen K vs the DEMAX book; full table in `reports/2026-09-13-pool-level-learned-selection.md`):

| rule | K=30 Δ | K=30 wins/losses | 2023 / 2024 | K=80 Δ | K=80 wins/losses | 2023 / 2024 |
|---|---:|---|---|---:|---|---|
| LEARNED_POOL (top-K by learned) | +5.11 | .57 / .24 | +1.1 / +9.1 | +1.31 | .36 / .25 | −0.1 / +2.7 |
| LEARNED_DIV5 (greedy, overlap ≤ 5) | +5.65 | .58 / .22 | +2.3 / +9.0 | +2.66 | .39 / .17 | +1.6 / +3.7 |
| BLEND_Q99 (z learned + z sim q99) | +2.51 | .40 / .29 | +1.2 / +3.8 | +2.00 | .31 / .11 | +1.9 / +2.1 |
| BLEND_DIV5 | +3.65 | .44 / .25 | +2.0 / +5.4 | +2.72 | .35 / .10 | +3.1 / +2.3 |
| UNION (DEMAX K/2 + learned K/2) | +3.08 | .38 / .19 | +1.6 / +4.6 | +1.92 | .29 / .14 | +1.9 / +1.9 |
| RESORT (DEMAX-80 re-sorted) | +2.01 | .38 / .25 | −0.4 / +4.4 | 0 (same set) | | |
| Q99 alone (simulator only) | −1.35 | | | −2.13 | | |

Slate-arms whose K=30 max reached 200+: DEMAX 6 → LEARNED_DIV5 12 (194+: 7 → 19). Caveats: two seasons, 36 slates (the
two arms share slates), 200-candidate pools of the 40-lev/160-boom era, no preregistration — hypothesis-level, but out of
season and larger than any other Sunday ordering effect.

**Live caveat.** On the 2026-W1 K90 run (3200-candidate pool) the unconstrained pool rules collapse onto one core: top-30
mean pairwise overlap 5.4 (paid book 1.3), one player in 97–100% of lineups, 43 distinct players. The overlap-capped rules
bring pairwise overlap to 3.3 but single-player exposure stays 87–97%. The historical corpus never showed this (overlap 1.5).
The UNION book (half DEMAX) is the hedge: exposure 70%, overlap 2.7.

**Implemented (post-build, applies to the whole corpus, emitter-compatible, all outcome-blind):**
`scripts/week1_learned_score_live.py` scores every candidate of a run dir and writes six books — `learned-book` (paid K90
re-sorted), `learned-pool`, `learned-div5`, `blend-q99`, `blend-div5`, `union` — with concentration receipts; the host chain
`scripts/week1_learned_after_build.sh` (running) applies it to every new live run (the 14:10Z build's K80 and K90 runs and
the T-70 rebuild), emits `upload-K90-<stamp>-<book>.csv` and per-book lineup sheets under `/home/erich/week1-sunday/`, and
adds `pos_learned_book / pos_learned_pool / pos_blend_q99 / pos_union` columns to the paid sheet. Everything is settled
Monday against the standings. Week-2: the same computation as a selector law inside `live_week.py` behind a preregistered
lab cohort (PREREG-096 candidate: learned-div5 vs DEMAX on the 72-slate panel at 800 and 3200, nested LOSO fit).

### §2j.1 — Adopted for today (operator decision 13:10Z: "I would like to use this today")

Exposure cap tested on the same corpus before adoption (overlap ≤ 5 plus single-player exposure ≤ 40%): K=30 **+6.07**
(2023 +3.0 / 2024 +9.1, wins .58 / losses .21), K=80 **+3.17** (losses .14) — the best rule at both sizes, and it binds
hard on the live pool (exposure 97% → 40%, 90 distinct players in 30 lineups, pairwise overlap 1.6 vs paid 1.3).

**Today's product** (`scripts/week1_learned_after_build.sh`, running; `once RUN TAG` processes any run by hand): for
every new live run → learned scorer over the whole pool → vet the 30 (`week1_vet_book.py`: DK O/IR/OUT, placeholder
salary, vanished prop line = HARD) → HARD players excluded and the 30 re-selected (≤ 3 passes) → `upload-<tag>-today-30.csv`
(30 rows) and `upload-<tag>-today-90.csv` (the same 30 first, then the paid remainder in expected-max order) → sheet +
exposure table → `/home/erich/week1-sunday/TODAY-30-LATEST.md` names the newest set. Placeholder run (last night's K90):
one HARD exclusion (Jalen McMillan, doubtful, prop line vanished), exposure capped at 12/30 for Chase, Robinson, Gibbs,
Shough, Olave, JAX DST. The paid P_MIX/K90 books remain the frozen primary shadow; the today-30 is the entered book;
both settle Monday. Simulated q99 of the entered 30 is lower than the paid top-30 (180 vs 189) by construction.

### §2j.2 — Pre-lock historic test of today's rule at the paid dose (PREREG-096, launched 14:02Z)

The operator asked whether the current algorithm can be run through a historic test before kickoff. A full 3200-dose
replay cannot finish before lock, but one 72-slate bank at the paid dose (D800, 160 lev / 640 boom) can: experiment 116 on
a dedicated lab job (`lab-run-fast`, image `prereg09v-552b0f01b659`, execution `lab-run-fast-fbmwf`, run
`116b960r1-20260913T140230Z`, 72 tasks, parallelism 36, `maxRetries 3`), untouched PREREG-093/095 lanes. Frozen before
launch (`reports/2026-09-13-prereg096-learned-pool-paid-dose.md`): primary = paired K30 realized max, today's rule
(learned score, overlap ≤ 5, exposure ≤ 40%, LOSO coefficients per season) vs the expected-max book's first 30; consequence
limited to today — KEEP the learned today-30 iff mean delta > 0 and ≥ 3 of 4 seasons ≥ 0, else REVERT to the vetted paid
top-30. The watcher (`/home/erich/week1-sunday/watch_116.sh`) reads the bank when it completes (or at 16:10Z on the
complete shards), writes `prereg096_verdict.env`, and re-processes the newest live run so `TODAY-30-LATEST.md` reflects
the verdict; the chain applies the same verdict to the T-70 rebuild. Read expected ~14:40–15:00Z.

### §2j.3 — PREREG-096 read (14:26Z): **REVERT** — the learned rule does not beat expected-max on real 800-candidate pools

Bank 960 completed 72/72 (execution `lab-run-fast-fbmwf`, 23 min). Frozen primary, K30 realized max of today's rule vs the
expected-max book's first 30: **−2.83** [−10.21, +5.11] (season-clustered 90%), wins .40 / losses .47; by season
2021 −3.4, 2022 −17.0, 2023 −3.4, **2024 +12.5**. K80: +0.34 (flat). 2021–2022 (untouched by rule selection): −10.2.
Threshold events at K30: 194+ 12 vs 12, 200+ 4 vs 6, 220+ 1 vs 4. Every descriptive variant is also ≤ 0 except the two
that keep the expected-max order (UNION +0.5, RESORT +0.6). Full read: `reports/2026-09-13-prereg096-read.md`.

Reading: the 200-candidate Neo4j result (+6 at K30, two seasons) **did not transfer** to 800-candidate pools — 2024 still
carries a large positive effect, 2022 a large negative one, and the mean is negative. The learned score is not a
selector; at most it is a re-sort of the expected-max book (RESORT/UNION ≈ +0.5, hypothesis-level). Consequence applied as
frozen: `TODAY-30-LATEST.md` now names the **vetted paid top-30** (`upload-K90-<stamp>-paid-vetted-30.csv`); the learned
books stay as shadows for Monday's settlement. Lesson for the ledger: a pool-level selector must be tested at the
generator's real dose before adoption; the small-pool corpus over-stated it by ~9 points at K30.

## §2k — PREREG-093 first read (14:35Z): the 3200 rung passes both contrasts; the Sunday dose ladder still says 800

Amended reader (amendment 1, repair shards unioned; bank 931 repaired with rep2021 + rep2022), three complete banks.
GLOBAL_WEMAX_PROXY, family level 0.9833: **D1600 − D800 +0.00242** [−0.00527, +0.00789], bank 931 negative →
UNRESOLVED (replicates PREREG-090's null on the 1600 rung); **D3200 − D800 +0.00898** [+0.00169, +0.01707], every bank
and every LOSO positive → **PASS**; **D3200 − D1600 +0.00655** [+0.00171, +0.00997], every bank and LOSO positive →
**PASS**. Frozen ladder: 3200 requires the 1600 rung to pass (in 090 or here) — it did not — so the paid dose stays
**800** today (no dose env written; the T-70 rebuild runs the P_MIX D800 K80 path). Consequence 5 already holds: the
K90 nested book IS the live D3200 stream, so the entered vetted paid top-30 comes from the 3200 pool and the D3200 book
is in the Week-1 shadow set. The 3200 rung is the first dose above 800 to pass both its contrasts; it becomes the Week-2
dose candidate, decided by prospective settlement plus PREREG-095 (running: 3200 × {DEMAX, NOV}). Transcript on the
amend4 branch (`results/read-transcripts/prereg093-first-read-transcript.txt`).
