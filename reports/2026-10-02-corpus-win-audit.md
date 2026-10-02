# Can our corpus win a major contest? (audit, 2026-10-02)

**Asked by the operator (2026-10-02, early morning):** "do a thorough audit of the corpus to make sure it contains
lineups that can win major contests."

**Scope.**
- **The corpus** is the candidate pool a build produces: the lev lineups (projection-maximising) plus the boom lineups
  (one optimal lineup per simulated world). In Week 4 it is the Saturday/Sunday-early D12800 supply plus the T-70 pool,
  joined by the union.
- **"Major contests"** are the Millionaire, the FFWC qualifiers and the $555 satellites: the contests our 5-row tail
  sleeve enters.

**Method.**
- Weeks 1 and 3 of 2026 are measured in hindsight against the real fields (Week 2, the projection-defect week, is left
  out).
- Week 4 is measured outcome-blind on the full-size smoke build of 2026-10-02.

**Scripts and data.**
- Scripts: `reports/lab-handoffs/2026-10-02-corpus-win-audit/`.
- Data: private only (standings carry user names), in `~/corpus-audit` on the laptop.
- Sources:
  - `nfl_raw.contest_entries` and `nfl_raw.contest_ownership`;
  - `nfl_raw.dk_salaries`;
  - the archived run dirs in `gs://nfl-predictions-503414-raw/private/rehearsal/`.

## 0. The answer

**This audit is about the POOL. In Week 4 no entered row comes from the pool:** the 105 main rows are the capped
optimizer's (PMO_X50) solved on the T-70 frame with the ownership term, and the 5 tail-sleeve rows come from the field
sample (§2). So the pool's numbers below are not a forecast of Sunday.

- **The pool, Weeks 1 and 3, was below the field at every line** (W3: 0.62× at the top 20%, 0.39× at the top 1%, 0.08×
  at the top 0.1%). It never came within one player of a real top-0.1% lineup; an equally large slice of the field held
  7% of them exactly. Inside our own model it holds a lineup within 17 points of a week's best in only 3–5% of weeks.
- **The entered design is a different thing.** The reviewer rebuilt this week's entered design (K 105, cap 52, DST 26,
  per-game 4, >= $49k, the lag term at 0.10) on each week's archived frame and scored it on DK points against the real
  Millionaire field (`review/ownership-term-20260929` @ 4f279caf, `14_entered_design_2026.py`). The results, in
  hindsight on three draws:

  | | top 20% | top 10% | top 1% |
  |---|---:|---:|---:|
  | W1 | 2.43× | 4.00× | 8.57× |
  | W2 | 1.67× | 2.10× | 1.90× |
  | W3 | 1.48× | 1.52× | 2.86× |

  The only cell below 1× is W3 at the top 5% (0.76×). That is consistent with L13/L20/L21/L24.
- **What changed for the major contests:** the operator moved the Millionaire / FFWC / $555 rows (the sleeve) from the
  pool to a field-like sample (§2), the one place this audit's finding reaches an entered row.

## 1. Weeks 1 and 3, in hindsight

### 1.1 The pool against the real lines

| | W1 pool (800, entered) | W3 pool (12,559, entered) | W3 replay, Week-4 design (12,854) |
|---|---:|---:|---:|
| Millionaire winner | 274.0 | 239.8 | 239.8 |
| Millionaire top-0.1% / top-1% line | 229.6 / 209.0 | 205.6 / 188.2 | 205.6 / 188.2 |
| pool's best lineup (realized) | 228.5 | 207.1 | 207.1 |
| where the pool's best would have finished | 961st of 831,028 | 129th of 161,682 | 129th |
| pool lineups ≥ top-0.1% line (the field's rate would give) | 0 (0.8) | 1 (12.6) | 1 (12.9) |
| pool lineups ≥ top-1% line (the field's rate would give) | 7 (8) | 49 (126) | 50 (129) |
| pool average vs field average | 140.2 vs 142.1 | 120.4 vs 128.5 | 120.8 vs 128.5 |

The pool's rate at each line, as a multiple of the field's rate:

| line (field's top …) | 50% | 20% | 10% | 5% | 1% | 0.1% |
|---|---:|---:|---:|---:|---:|---:|
| W1 pool | 0.97 | 0.87 | 0.76 | 0.68 | 0.88 | 0 |
| W3 pool | 0.77 | 0.62 | 0.52 | 0.45 | 0.39 | 0.08 |
| W3 replay (Week-4 design) | 0.78 | 0.63 | 0.54 | 0.46 | 0.39 | 0.08 |

**Reading.** In both weeks the corpus as a whole held *worse* lineups than the crowd, at every line. Week 3 was
badly below; the Week-4 design (union with the T-70 pool) changes nothing at the corpus level.

### 1.2 Could the corpus have held the winners? Nearest pool lineup to each real top-0.1% lineup

For every Millionaire lineup in the top 0.1%, the most players any pool lineup shares with it (9 = the pool holds that
exact lineup). Each pool is compared with a random slice of the field of the same size.

| | exact (9/9) | 8/9 | 7/9 | ≤ 6/9 |
|---|---:|---:|---:|---:|
| W1 pool (800) | 0% | 0% | 1.4% | 98.6% |
| W1, random field slice of 800 | 0.2% | 0.1% | 3.7% | 96% |
| W3 pool (12,559) | 0% | 0% | 5.6% | 94.4% |
| W3, random field slice of 12,559 | **6.8%** | 3.1% | 34.6% | 55.6% |

The W3 pool came within one player of none of the 162 top lineups. An equally large slice of the crowd held 7% of them
exactly and 10% within one player. (Part of the crowd's advantage is duplication: popular winning builds are entered
many times. That is also what winning a Millionaire takes.)

### 1.3 Not the rules, and not the player universe

- **No winning lineup used a player our build excluded** (min projection, injury and roster filters). In both weeks
  every player of every top-0.1% lineup was in our universe.
- **The best lineup in hindsight was buildable.** W3: the best DK-legal lineup (256.8) also satisfies every house rule.
  W1: 292.1 DK-legal, 277.1 under the house rules; the winner had 274.0.
- **The house rules favour winners overall.** Only 23% (W1) and 33% (W3) of top-0.1% lineups satisfy every rule, but
  only 10–11% of the whole field does: winners are 2.3× and 3.0× more likely to be rule-legal than a random entry.
  - The stack rule and the bring-back are *enriched* among winners: they break them at 0.3–0.8× the field's rate.
  - **One rule cuts against winners: at most 4 players from one game** (adopted for Week 3). 15% (W1) and 31% (W3) of
    top-0.1% lineups have 5+ from one game, 1.8× and 4.3× the field's rate. The W3 winner (239.8) did.
  - Against this stands the lab's panel: the cap raised the pool oracle in 3 of 3 seasons (HANDOFF, L01 read), and
    MAXGAME5 was not supported (L10). Two 2026 weeks do not overturn that. This is a Week-5 question, not a Sunday
    change.

### 1.4 Why: the corpus is narrow where winners are made

- **Inside our own model the corpus almost never holds a winning-calibre lineup.** In 300 simulated worlds (the
  independent selection bank stored with each run), the pool's best lineup is typically 30–38 points below that world's
  best house-legal lineup. The real winners finished 3.1 (W1) and 17.0 (W3) points below the real best lineup.

  | | gap median | pool within 3 of the world's best | within 10 | within 17 |
  |---|---:|---:|---:|---:|
  | W1 pool (800) | 38.4 | 0% | 0% | 3.0% |
  | W3 replay (12,854) | 30.4 | 0.3% | 0.7% | 5.3% |

  Each boom lineup is the best lineup of *one* generation world. A new world's best lineup is a different nine. Ten
  thousand worlds do not cover a 160,000–830,000-entry field's reach.
- **The simulator's player tails are not too thin.** Realized scores above the simulated p99: 0.3–0.6% of skill
  players (1% if calibrated). The realized week's best lineup sat at the 79th (W3) and 99th (W1) percentile of the
  simulated worlds' bests. The W3 pool's realized best (207.1) sat at the 41st percentile of its simulated bests.
  The model's spread is not the problem.
- **DST has no variance in any build bank** (`live_week.py` `finish_bank`: every DST row = its projection in all 10,000
  draws). So a boom lineup picks its DST by projection and salary alone, and the corpus piles onto one DST:

  | | pool's top DST | its share of the top-0.1% lineups |
  |---|---|---:|
  | W1 | Jaguars, 73% of the pool | 25% (Steelers 22%, Jets 15%) |
  | W3 | Seahawks, 45% of the pool | not in the top six; Titans 35% of winners vs 9.5% of the pool |

  - This is known: HANDOFF calls it "the only verified structural omission".
  - **Adding DST variance was tested twice for selection and lost** (system study: `DST_CORR_DRAWS` closed,
    "constant DST projections in entry selection are not a deficiency").
  - Its effect on the corpus's composition has not been tested on its own. A Week-5 candidate, not a Sunday change.
- **The pool's exposures drift from the field's where the winners were made.** Most-used players in the top-0.1%
  lineups:

  | week | player | share of top-0.1% | share of our pool | field ownership |
  |---|---|---:|---:|---:|
  | W1 | Jahmyr Gibbs | 82% | 40% | 43% |
  | W1 | Jalen Coker | 76% | 4% | 7% |
  | W1 | Chris Olave | 63% | 17% | 25% |
  | W1 | Jaguars DST | 25% | 73% | 18% |
  | W3 | Jahmyr Gibbs | 94% | 38% | 27% |
  | W3 | Garrett Wilson | 88% | 9% | 28% |
  | W3 | Kenyon Sadiq | 72% | 3% | 6% |
  | W3 | Geno Smith | 65% | 4% | 8% |
  | W3 | Kenneth Walker III | 32% | 20% | 44% |

  Several of the week-makers were popular *and* well ranked by our projection (Olave 3rd WR, Garrett Wilson 7th WR), yet
  the pool held them at a third or less of the field's rate.

## 2. Week 4 (outcome-blind, the 2026-10-02 full-size smoke on pin 32cdb61)

**The supply that fed the smoke's union** (8 threads, 2 h 35 min): 12,403 candidates (lev 2,560, boom 4,999, class
4,844); 12,276 joined the T-70 pool's 4,758.

**The sleeve, chosen by the operator on the 36-slate panel** (`06_`/`07_`; 5 rows per slate, 12 seeds, scored against a
200k field from each slate's real ownership):

| arm | own source | z | top 1% | top 0.1% |
|---|---|---:|---:|---:|
| projection sleeve (as built before) | n/a | −0.03 | 2.22× | 0 hits |
| field, house rules, ≤ 5/game (`top`, ENTERED) | blend | +0.02 | 1.44× | 0.93× |
| field, house rules, ≤ 5/game (`top`, ENTERED) | lag | 0.00 | 1.62× | 3.24× |
| field, no house rules (`free`) | blend | +0.12 | 1.99× | 1.39× |
| field, no house rules (`free`) | lag | +0.04 | 1.25× | 1.39× |

- The field sleeve trades the top 1% for the top 0.1%. The top-0.1% figures rest on a handful of hits.
- **The Week-4 smoke** (field sleeve, today's real slate, end to end):
  - 2,817 rule-passing rows of 200k; pick ranks 0, 1, 14, 337, 364.
  - The audit passed.
  - Rows: Millionaire = 106; $555 sat = 107–108; FFWC = 109–110.

## 3. What this means for Sunday, and for Week 5

1. **Sunday:**
   - The main book is the tested capped optimizer with the ownership term. It does not come from the pool.
   - The major-contest rows come from the field sample. That gives a better chance at the top 0.1% (the Millionaire)
     and a lower rate at the top 1%.
   - The reviewer's open question is whether the $555 / FFWC rows (one ticket per ~72 entries, a top ~1.4% line) should
     keep the projection sleeve. That is the operator's decision (HANDOFF).
2. **Week 5, the pool itself:**
   - DST variance in the generation bank. Selection was tested negative twice; the corpus composition was never tested.
   - The per-game cap for boom solves (winners use 5+ at 1.8–4.3× the field's rate; the lab panel favoured the cap).
   - Exposure drift from the field on the week-makers.
   - Each needs a preregistered panel before entry.

## 4. Limits

- Two clean weeks, one Millionaire each; top-0.1% lineups within a week are correlated, so the "162 lineups" of W3 are
  a few dozen distinct builds.
- W1's pool is one of the twelve `e7255e9` builds (the archived one), not their union.
- Realized points come from the Millionaire's ownership table. A pool player nobody drafted counts 0; these are
  low-projection punts, so the pool's numbers could be a fraction of a point low.
- The simulated-world statistics use our own model (independent selection bank, not the generation bank). They show
  what the corpus can reach if the model were right, not what the field does.
