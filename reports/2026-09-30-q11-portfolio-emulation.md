# Q11: emulating the top users' portfolios, small-book cores, and week-to-week variation

Production (workstation), 2026-09-30. Delegated by the laptop at `c3dc040f` (the design is its); supersedes the
"remaining Q11" line of `reports/lab-handoffs/2026-09-29-questions-research/F-portfolios.md`. **Descriptive hindsight on
the 2026 Millionaire fields (W1–W3). It changes nothing in Week 4**; the Week-5 candidates at the end go through a frozen
panel as usual. No user names appear here.

**Information time of every input.**
- Pools and projections: pre-lock. The W1 union of the twelve `e7255e9` builds (7,219 rows), the W2 Wednesday 12,559
  build (5,701 rows survive the T-70 frame) and the W3 Saturday D12800 pool (12,555 rows). Every lineup mean is the
  sum of the Sunday T-70 frame's `proj`.
- Predicted ownership: pre-lock where it exists. W3 uses the Saturday lag-model file. For W1 the stored `own_shadow`
  turned out to be a within-position share (each position sums to 1), so it is used only after rescaling by roster
  slots, as a sensitivity run. The primary W1 source is **LineStar's recorded projection** (its archive: published
  before lock, but not provably the pre-lock copy). Every source is rescaled to a 900% slate total, the scale of the
  F3 target (130–140 per row).
- Realized scores and realized Millionaire ownership: post-lock. They are used only to score finished books and as
  the chalk covariate; ownership is fixed at lock, so it carries no outcome.

Scripts: `reports/lab-handoffs/2026-09-30-q11-portfolio/` (`q11_emulation.py`, with `--ablation`;
`q11_small_books.py`; `q11_single_row.py`; `q11_week_to_week.py`). The inputs and outputs are private (the field holds
user names) and stay outside the repository.

## 1. Emulation: a book built to the top users' profile, from our own pool

Three 150-row books per week from the same pool:
- **(a) top-mean** with ≤ 7 shared;
- **(b) exposure-target**: greedy by mean under a per-player cap, a 25% QB cap, a 30% DST cap, a max-shared limit and
  an optional band on predicted ownership. The setting is picked from a 36-cell grid by distance to the F3 targets,
  computed from pre-lock quantities only; the chosen setting was cap 55%, ≤ 6 shared, no band;
- **(c) top-mean with the ownership term**: mean + 0.20 × predicted ownership sum, the armed Week-4 form.

| Week (ownership source) | Book | Top player | Top-3 | Distinct players | Overlap | Pairs ≥ 6 | Modal QB | Distance to targets | Mean vs field | Cash share | Top-1% share |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| W1 (LineStar) | (a) top-mean | 0.98 | 0.90 | 66 | 4.88 | 30% | 0.77 | 45.6 | **+24.1** | **49%** | 0.7% |
| | (c) + term | 0.97 | 0.89 | 66 | 4.84 | 29% | 0.67 | 42.7 | +19.9 | 39% | 0.7% |
| | (b) exposure-target | 0.55 | 0.51 | 125 | 2.00 | 2.8% | 0.25 | 2.5 | +11.9 | 33% | 1.3% |
| W3 (lag file) | (a) top-mean | 0.92 | 0.71 | 87 | 3.17 | 11% | 0.49 | 20.1 | **+19.9** | **47%** | **4.0%** |
| | (c) + term | 0.96 | 0.84 | 101 | 3.17 | 7% | 0.30 | 16.6 | +14.1 | 33% | 3.3% |
| | (b) exposure-target | 0.55 | 0.54 | 107 | 2.02 | 1.8% | 0.25 | **0.9** | +3.2 | 26% | 2.7% |

Targets (F3): top player 0.50–0.60, top-3 0.45–0.50, ~8 players ≥ 25%, 90–115 distinct, overlap 1.8–2.4, pairs
sharing ≥ 6 ≤ 3%, modal QB ≤ 25%, predicted ownership 130–140. Field means: 142.1 (W1), 128.5 (W3). The top-100 heavy
users' benchmark is +12.6 mean, 35% cash and 4.9% top-1%.

**Sensitivity.**
- (c) moves with the ownership source: in W3 it is +22.2 / 49% cash with LineStar against +14.1 with the lag file; in
  W1 it is +22.0 with the slot-rescaled shadow. (a) and (b) do not use ownership.
- (b) is identical across sources: the ownership band was never selected, and its predicted ownership landed at
  118–130 on its own.

**Which of (b)'s constraints costs the points** (each alone on top of (a); realized mean vs field; projected mean in
brackets):

| Constraint | W1 | W3 |
|---|---:|---:|
| none, (a) | +24.1 (130.4) | +19.9 (130.2) |
| player cap 55% | +17.2 (128.0) | +10.7 (129.6) |
| QB cap 25% | +15.7 (129.2) | +14.8 (130.1) |
| DST cap 30% | +23.2 | +19.9 |
| ≤ 6 shared | +21.5 | +13.7 |
| ≤ 5 shared | +16.3 | +3.8 |
| all of (b) | +11.9 (126.3) | +3.2 (129.0) |

**Reading.**
- **(b) matches the top users' shape almost exactly** (distance 0.9 in W3) **and loses to plain top-mean selection
  from the same pool by 12–17 points of mean and 16–21 points of cash share, in both weeks.** At the top-1% line it is
  mixed: W1 two rows against one, W3 four against six.
- So the laptop's test comes out the second way: shape is not the lever, and emulating it costs.
- Top-mean from our pool already sits above the top-100 heavy-user class on mean (+20 to +24 against +12.6) without
  any emulation, in these two weeks.
- **The cost is concentration: our top-projected players hit in both weeks.** The projected means barely move (0–4
  points) while realized drops by 3–16 per constraint. That is two weeks of hindsight, not a rule.
- The frozen 36-slate panels are the evidence for the main book's cap: L17 (looser cap) read HARMFUL and L18 (tighter
  cap, 40%) NEUTRAL. They say the armed 50% cap is safe. This read adds only that an even tighter shape target, the top
  users' 50–60% top player with ≤ 6 shared and 25% QBs, did not pay in W1 or W3.

## 2. Small books (users with 2–10 entries): cores vs diversified

108,231 user-weeks across the three fields. Core = the players common to every row. Tiers: DUP (all rows identical),
CORE5 (≥ 5 common), PART (2–4) and DIVERSE (0–1).

| Entries | DIVERSE | PART | CORE5 | DUP |
|---|---:|---:|---:|---:|
| 2–3 | 32,809 | 27,613 | **6,968** | 2,999 |
| 4–5 | 17,784 | 2,918 | 371 | 298 |
| 6–10 | 15,033 | 1,095 | 145 | 198 |

Cores are a 2–3-entry habit: 10% CORE5 and 39% PART. From 4 entries up they are rare (1–2% CORE5).

**Raw, core books look better, and all of that is chalk.** Linear fits with week × entry-count fixed effects and HC1
errors, relative to DIVERSE:

| Outcome | CORE5, no chalk control | CORE5, chalk controlled | PART, controlled | DUP, controlled | Per +10 ownership points |
|---|---:|---:|---:|---:|---:|
| Portfolio mean vs field | +3.78 (±0.29) | −0.29 (±0.29) | −0.44 (±0.15) | −1.03 (±0.47) | **+1.83** (±0.02) |
| P(best row ≥ top-1% line) | −0.2 pp (±0.2) | **−1.1 pp** (±0.2) | −0.6 pp (±0.1) | −1.6 pp (±0.2) | +0.4 pp |
| Cash share | +2.9 pp (±0.4) | −1.1 pp (±0.4) | −0.7 pp (±0.2) | −1.3 pp (±0.6) | +1.8 pp |

- At the same chalk level, **a core book has no mean advantage and a lower chance of a top-1% row**: −1.1 pp against a
  base of 1.7–7%, depending on entry count. Duplicated rows are worst. Diversified books at 6–10 entries reach the top 1%
  in 7.0% of user-weeks against 2.8% for CORE5.
- **Chalk is the lever in both outcomes.** By chalk tercile, the high-chalk third beats the low third by 9–14
  points of mean in every tier. This is three weeks of fields in which chalk did well; the winners study said the same.
- **For our 2–5-entry contests:** hold chalk where the book already holds it and deal rows that do not share a core.
  Top-mean head rows under ≤ 7 shared can overlap heavily (overlap 3.2–4.9 in the books above), which is the spread
  layout's case.

**Single-entry row: top-mean or chalk-core?** This is pre-lock-computable: in our pool, the top-mean row against the
row with the most predicted ownership within 2 or 4 projected points of it.

| Week (source) | Top-mean row: field percentile | Chalk row within 2: pct | Within 4: pct | Top-200 rows: Spearman(predicted ownership, realized) |
|---|---:|---:|---:|---:|
| W1 (LineStar) | 61 | 79 | 79 | −0.14 |
| W2 (LineStar) | 85 | 53 | 53 | +0.67 |
| W3 (lag file) | 51 | 69 | 38 | −0.13 |
| W3 (LineStar) | 51 | 95 | 93 | +0.09 |

**No stable answer.** Each is a single draw, and within the top 200 the ownership–outcome sign flips week to week.
Keep top-mean as the single-entry default. A chalk-core single row is a panel question (the frozen harness, 36 slates),
not a three-week one.

## 3. Week-to-week variation of the heavy users

Users with ≥ 20 entries in at least two weeks (917 / 822 / 803 user-weeks). "Persistent" = the top 20% by mean finish
in both weeks of a pair (31 / 45 / 37 users; the F1 counts were 33 / 40 / 35).

Spearman across users, week A vs week B, all heavy users (persistent users in brackets):

| Statistic | W1→W2 | W2→W3 | W1→W3 | Median absolute change (W2→W3) |
|---|---:|---:|---:|---:|
| top player's exposure | 0.56 (0.65) | 0.64 (0.64) | 0.55 (0.64) | 0.10 |
| top-3 exposure | 0.64 (0.76) | 0.72 (0.78) | 0.62 (0.68) | 0.07 |
| distinct QBs per row | 0.53 (0.68) | 0.80 (0.74) | 0.55 (0.72) | 0.04 |
| modal QB share | 0.49 (0.67) | 0.58 (0.64) | 0.51 (0.80) | 0.05 |
| mean pairwise overlap | 0.71 (0.83) | 0.77 (0.84) | 0.68 (0.80) | 0.29 |
| pairs sharing ≥ 6 | 0.75 (0.89) | 0.73 (0.87) | 0.71 (0.90) | 0.005 |
| chalk (ownership sum) | 0.60 (0.38) | 0.65 (0.73) | 0.54 (0.54) | 9.9 |

- **A user's construction style is a stable trait:** overlap and the ≥ 6-shared rate correlate 0.7–0.9 week to week,
  and exposure concentration and QB count 0.5–0.8. The persistent users are the most stable. F3's targets are
  therefore a coherent style that users hold, and one we could aim at.
- **Their players do not carry.** For players on both weeks' lists, the median Spearman between a user's exposure in
  week A and in week B is −0.09 to +0.02. It is lower than the field's week-A ownership against the user's week-B
  exposure (+0.05 to +0.11), and only 18–21% of users are better predicted by their own last week than by the field.
  They re-pick every week from the slate in front of them.
- Levels (medians): the top-20% users in a week run more concentrated and chalkier portfolios than the rest (top player
  0.70–0.78 vs 0.54–0.59, overlap 2.4–2.6 vs 1.8–1.9, +13 to +21 ownership). That selects on the same week's outcome,
  which concentrated chalk books hit when chalk scores. It is not evidence of skill (F1.4's caveat), and F2's top-100
  vs matched-mid comparison found no shape difference.

## What this settles, and the Week-5 candidates

1. **Shape emulation is closed as a lever for the main book.** The top users' profile is reachable from our pool (part
   1, distance 0.9), costs mean and cash in both weeks, and is mixed at the top 1%. The style is stable per user (part
   3) but carries no player information. Their edge is which players they pick each week, as F2 and the winners study
   concluded.
2. **For 2–5-entry contests, do not build cores.** At equal chalk they cost top-1% probability with no mean gain (part
   2, 108k user-weeks). **Week-5 candidate:** a frozen panel of the small-contest dealing: head rows as today vs rows
   drawn from the top-mean rows under a pairwise-overlap limit (≤ 4 shared) at the same chalk (the spread layout's
   small-contest case).
3. **Chalk level is the one construction variable that moved outcomes** in all three parts. The armed ownership term is
   the tested form of it (L20 SUPPORTED on 36 slates × fresh banks). Its two-week hindsight here is mixed: −4 to −6 with
   one source, +2 with another. That does not outweigh the panel.
4. The single-entry chalk-core row is undecided (part 2b): a panel question if the operator wants it; top-mean stays.

**Confidence.** Parts 2 and 3 are large-sample descriptive (108k and ~2,500 user-weeks) and hold in each week
separately. Part 1 is two weeks of hindsight: the direction (the shape costs) is the same in both weeks and under every
ownership source, but the magnitude is inflated by two weeks in which our top projections hit. W1's pre-lock ownership
is LineStar's recorded copy, not a proven pre-lock one.
