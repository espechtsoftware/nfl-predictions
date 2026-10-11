# Boom players, bust players and salary bands: what Weeks 1–4 say, and what changed in tonight's arm (2026-10-10, evening)

**For:** Erich, the laptop and the lab reviewer. Written by the outside model at the operator's request ("think about what could be
done right now to allow us to choose better boom players"), read with him before it went anywhere. Everything below is descriptive
and after the fact: four weeks of pre-lock projections, real results, the entered books and the captured contest fields. The
decisions in §6 are his.

## 1. In one page

- **The corpus holds the boom players; nothing we have says which of them will boom.** 60 of the 73 games of 25+ DraftKings
  points this season came from players in the top fifth of projections at their position. Our boom probability is calibrated but
  ranks booms no better than the plain projection (AUC 0.903 vs 0.906) and adds nothing beyond it (likelihood-ratio p 0.56–0.99).
  Of 26 pre-lock features, none survives a position control. Booms do not cluster inside games beyond chance. Game total is the one
  signal positive in all four weeks, and it is weak.
- **The paper boom block (study 38, 6z7) is betting on that residual.** On Week 4 with FP's projection it tagged 28 players; one
  reached 25 points; the fourteen at the full bonus averaged about 9. Expect a negative read Monday.
- **Width, not ranking, decided boom capture.** The Week 1–3 books (90–144 rows, 124–147 distinct skill players) held 19 of 19,
  7 of 8 and 10 of 12 in-frame booms because they held almost every top-band player. The Week 4 entered book (110 rows on 37
  players) held 6 of 19; the construction armed for Week 5, built on Week 4, holds 8 of 19.
- **The bust side has real signal.** Questionable players busted 45% of the time against 27% for everyone else and scored zero 30%
  against 9% (Weeks 1–4, n 27). Questionable with limited practice: 19 players, bust 42%, zero 26%, one boom. Since Week 5 a
  Questionable player enters the FP-sourced book at FP's full number (O-68).
- **Salary bands separate the winners from the field, in every week and both contest kinds.** Top finishers hold more $8,000+
  players, one or two under $4,000, fewer at $4,000–4,499 and fewer at $5,000–5,999; they spend the full cap; their quarterbacks
  are cheaper, and the tier they avoid most is $6,500–6,999.
- **Tonight's arm (his decisions, §6):** an operator exclusion file through the existing status path (did-not-practice and
  Questionable-plus-limited players, Jefferson included); a new row rule, at most one RB/WR/TE priced $5,300–6,000 per row; and,
  conditional on its Week 4 check and a 20:40 stop, a second row rule, quarterback under $6,500 in cells B and C.

## 2. Boom players: the model and the features

Data: the last projection batch before each Sunday's lock (our p_20_plus, projection, p90, std), actuals (no stat line = 0), skill
players only: 1,843 player-weeks, 135 at 20+, 73 at 25+, 35 at 30+.

| Question | Result |
|---|---|
| Calibration of p_20_plus | top decile predicted 0.44, realized 0.41 |
| Ranking 25+ games: AUC | p_20_plus 0.903, projection 0.906, p90 0.897, std 0.880 |
| Beyond projection + projection² | residual z: LRT p 0.99; p_20_plus p 0.94; std p 0.30; p90 p 0.34; AUC unchanged |
| The 6z7 residual on Week 4 with FP's mean | 28 players tagged, 1 of 28 at 25+; the +2 group averaged ~9 points |
| Where 25+ games come from | 60 of 73 top-20% by projection within position; the rest of the slate booms at 0.3–2% |
| Top-band 25+ rate by week | 0.24 / 0.13 / 0.11 / 0.18 (pooled 0.16) |
| 26 frame features beyond the mean, with position controls | none at p < 0.05 with a stable sign; game total + in all four weeks (p 0.30) |
| Booms clustering within games | permutation p 0.87 / 0.32 / 0.23 / 0.91 |

The arithmetic of a big lineup at a 16% top-band boom rate: eight top-band players give P(≥3 booms) 12.6% and P(≥4) 2.8%; five
top-band plus three cheap players give P(≥3) 3.3%. Realized skill points by booms held ran about 90 / 105 / 125 / 145 / 170+.

| Book | Distinct skill players | Top-20% players held | In-frame 25+ booms held |
|---|---|---|---|
| Week 1 entered (90 rows) | 124 | 69 of 69 | 19 of 19 |
| Week 2 entered (97) | 138 | 77 of 79 | 7 of 8 |
| Week 3 entered (144) | 147 | 82 of 84 | 10 of 12 |
| Week 4 entered (110) | 37 | 32 of 59 | 6 of 19 |
| Week 4, the Week-5 construction (26) | 46 | 33 of 59 | 8 of 19 |

## 3. Bust players: status

Weeks 1–4, skill players with a pre-lock projection of 5 or more, by the final report's practice status and designation:

| Status | n | Median points / projection | Bust (< half) | Zero | 25+ |
|---|---|---|---|---|---|
| No report | 641 | 0.80 | 27% | 9% | 9% |
| Full practice, no designation | 85 | 0.84 | 25% | 9% | 12% |
| Limited, no designation | 14 | 1.01 | 36% | 0% | 7% |
| Questionable, limited practice | 19 | 0.67 | 42% | 26% | 5% |
| Questionable, full practice | 5 | 0.31 | 60% | 40% | 0% |
| Did not practice, not ruled out | 8 | 0.54 | 50% | 25% | 25% |

The did-not-practice set is eight players: four busts, two zeros (Chase Week 1, Nacua Week 2), two booms (Schultz Week 2, held in 18
rows; Bowers Week 3). Week 5's set on the main slate: Jeanty (FP 18.3 Thursday, FP ownership 0.0 Saturday), McConkey, plus
Questionable-and-limited Addison, Stevenson, Tate, Kamara, Holani, Jefferson, McLaurin, Caleb Williams. Chase and Higgins practiced
in full and stay.

## 4. Salary bands of the top finishers

RB/WR/TE per lineup by salary band, top 1% against the rest, Weeks 1–4, salaries from each week's main slate. His contests =
qualifiers and satellites (42,830 entries, 407 in the top 1%); the Millionaire (1.33M entries, 13,280).

| Band | His contests, top 1% / rest | Sign by week | Millionaire, top 1% / rest | Sign by week |
|---|---|---|---|---|
| Under $3,500 | 0.61 / 0.46 | −+−+ | 0.52 / 0.43 | −+++ |
| $3,500–3,999 | 0.53 / 0.38 | +−+− | 0.57 / 0.39 | +−+− |
| $4,000–4,499 | 0.46 / 0.72 | −−−− | 0.39 / 0.52 | −−−− |
| $4,500–4,999 | 0.50 / 0.50 | mixed | 0.65 / 0.57 | mixed |
| $5,000–5,499 | 0.58 / 0.70 | −−+− | 0.38 / 0.71 | −−+− |
| $5,500–5,999 | 0.62 / 0.74 | −−−+ | 0.71 / 0.90 | −−−− |
| $6,000–6,499 | 1.02 / 1.03 | mixed | 0.96 / 0.86 | +−++ |
| $6,500–6,999 | 0.39 / 0.70 | +−−− | 0.89 / 0.90 | mixed |
| $7,000–7,499 | 0.80 / 0.55 | −+++ | 0.59 / 0.63 | mixed |
| $7,500–7,999 | 0.58 / 0.56 | mixed | 0.52 / 0.57 | mixed |
| $8,000 and up | 0.89 / 0.66 | +++− | 0.81 / 0.51 | +++− |
| Total salary | 49,907 / 49,830 | ++++ | 49,881 / 49,818 | ++++ |
| QB salary | 5,644 / 5,956 | −+−+ | 5,771 / 5,974 | −+−− |

Score against the field (sd units) and top-1% rate by count, his contests: $8,000+ none −0.26 (0.7%), one +0.14 (1.0%), two +0.38
(1.9%); $4,000–4,499 two or more: top-1% rate 0.1%; $5,300–6,000 (the band chosen tonight) zero +0.09, one +0.08, two −0.05, three
−0.22, four −0.49; under $3,500 one +0.17. Quarterback price, his contests: under $5,000 +0.32 (2.5%), $6,500–6,999 −0.06 (0.5%),
$7,000+ −0.44 (0.4%); the Millionaire: $6,500–6,999 −0.23 (0.5%), $7,000+ −0.07 (0.8%).

Where the Week-5 construction sat on Week 4's slate: $8,000+ 0.77 per row; $4,000–4,499 0.35; under $4,000 1.35 (the cheap block);
$5,300–6,000 1.31 with 13 rows holding two or three; quarterback $6,288 with 11 of 26 rows at $6,500+.

## 5. The Week 4 checks (the gate build is the baseline; every arm through the existing status-file path unless noted)

| Arm | Rows changed | $7k+ per row | Rows with 2+ | FP per row vs gate | Rules relaxed | W4 realized best / mean (skill) |
|---|---|---|---|---|---|---|
| A: status file | 4 | 1.85 | 17 | +0.15 | none | 150 / 115 |
| B: + band $5,000–6,400 removed | 26 | 2.69 | 25 | −5.23 | row rules on 2 | 197 / 125 |
| C: + band $5,500–6,900 removed | 26 | 3.08 | 26 | −5.06 | row rules 5, one-catcher 2, own cap 1 | 206 / 133 |
| D: + band $5,300–6,000 removed | 26 | 2.12 | 21 | −3.96 | none | 165 / 124 (full lineup) |
| Cap of one, $5,300–6,000 (new row rule) + status | 26 | 1.92 | 18 | −1.01 | none; every row exactly 1 | 176 / 118 |
| The rule switched off | 0 | | | 0.00 | | identical to the gate |

The realized numbers are in-sample (Week 4's outcomes were known) and did not decide; the bars were every rule applied and a
projection cost of at most 3.0 per row.

## 6. Tonight's decisions (the operator's) — ARMED 19:07–19:10 CT at 0696c9b3 (13 timers; supply 21:00 / 21:05; canary read ~23:30); the exclusion file on disk matches its pinned hash (1ac591e4)

1. The operator exclusion file through UNION_DK_STATUS (did-not-practice and Questionable-plus-limited; Jefferson stays).
2. The band cap: at most one RB/WR/TE at $5,300–6,000 per row (built from the reviewed one-hot-receiver switch; study 38 amendment
   6z8 follows it on paper).
3. The quarterback price mix: under $6,500 in cells B and C. Its Week 4 check met all three bars (RB-mate floor 4 of 4 on the
   cheaper favored pairs; nothing relaxed; FP −0.77 per full lineup); merged (ab482243) and armed.
4. Sunday pre-upload read: every book row holding a Questionable player whose game kicks off after lock.
5. Week 6: the 0.8 Questionable haircut on FP's number (O-68, a repair); a top-band coverage rule (width); the band and quarterback
   rules replayed on Weeks 1–3; the boom block's Monday read.

## 7. Sources

Scratch tables in the outside model's session (boom_calib_scored, boom_features_w1_4, calib_with_injuries, field_salary_bands_w1_4,
w4_fp_boom; the reader read_w4_arm.py); `~/rehearsals/gate-cbd1c49e-20261010T204553Z`, `dkstatus-w4-20261010T225113Z`,
`bandcap-w4-committed-20261010T232434Z`; the entered books under `~/moneygate/inputs`; `nfl_raw.contest_entries`,
`nfl_raw.injuries`, `nfl_predictions.player_projections`, `nfl_features.player_week_actuals`, `nfl_raw.fantasy_points_articles`.
