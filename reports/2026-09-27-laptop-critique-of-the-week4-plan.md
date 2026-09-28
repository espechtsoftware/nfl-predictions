# A critique of the Week-4 plan, with evidence from the full fields

Laptop agent, 2026-09-27 evening, for production. The operator's words were: "Please be critical of what is being
proposed. If you see a better way to win these contests let the other agent know."

Evidence used here:
- the three 2026 Millionaire fields: 1,160,834 matched entries, from `contest_entries` and `contest_ownership`, with
  our pre-lock `player_projections`;
- the Week 2–3 satellite fields;
- lab PREREG-L09, which is running now.

The script `reports/lab-handoffs/milly_shape_lift.py` reproduces every field table below. It is read-only.

Throughout, **"lift"** means the rate at which a group of lineups finished in the top 1% (or top 10%), divided by
the base rate. A lift of 2 means twice as often as a random entry. These are conditional rates over the whole field,
not a description of the winners, which would be survivorship-biased.

## 1. The satellite evidence was measured against the wrong line

The rehearsal and the post-mortem count lineups "above cash" at 149.5, the Millionaire's min-cash. A satellite pays
its tickets to roughly its top 9–11%, and satellite fields are *stronger* than the Millionaire field.

| Field percentile, 2026 Week 3 | p50 | p89 | p91 |
|---|---|---|---|
| Millionaire | 127.0 | 159.9 | 163.0 |
| $2 11-entry satellites (19) | 133.5 | 162.6 | 169.4 |
| SuperSat ×12 (190 entries) | 132.1 | 165.8 | 167.9 |
| $13 mega (402) | 138.0 | 169.8 | 174.3 |
| SuperSat 594 | 131.7 | 164.2 | 167.0 |
| SuperSat 2,378 | 129.4 | 162.1 | 164.7 |
| $18 qualifier (5,000) | 134.6 | 166.4 | 169.5 |

Week 2 shows the same pattern: the SuperSats' p89 was 150–160 against the Millionaire's 149.3.

A Week-3 satellite ticket needed roughly **162–174 points, not 149.5**. The "74 of 147 above cash" and "50% above
cash" figures therefore overstate the satellite result by a wide margin. Please re-score the rehearsal per contest at
that contest's real ticket line. Production holds `contests.json`, so tickets = prize pool ÷ ticket value, and the
line is the score of the last paid rank.

## 2. Mean is the wrong objective for a satellite; P(score ≥ the ticket line) is the right one

**If a user may cash several tickets from one satellite,** expected tickets = Σ over rows of P(row ≥ line). The line
sits 30–40 points above the field median, and our rows' projected means run about 120–135. At that distance a row's
variance matters as much as its mean, and correlated rows (stacks, game concentration) are worth more.

**If only one ticket per user counts,** overlap between winning rows is waste, and coverage of worlds at the line is
the objective.

**PREREG-L09** (lab `laptop/l09-satellite-objective-20260927` @ `b96f47e`) is running on the laptop now, with no
Cloud Run cost.
- **Panel:** 36 slates × 2 banks, at the live construction (D3200, `MAX_PER_GAME=4`, dual-law worlds).
- **Arms, all from the same pool:** EMAX, MEAN (the proposal), P(≥160), P(≥170), P(≥ simulated field p89), and
  coverage at the field p89.
- **Primary outcome:** rows ≥ the realized field p89 at K = 144.
- **Decision rule, frozen before any outcome:** a challenger replaces MEAN only with ≥ 5% more tickets, ≥ MEAN in each
  season, and more paired wins than losses.
- The reader output follows in HANDOFF tonight, at about 00:30 CT. The selector functions already exist in `two_track.py`.

**Operator question (asked separately):** does DraftKings let one user win and use several tickets from one
satellite? The answer decides between P(≥line) and coverage.

## 3. What the full Millionaire fields say, three weeks, 1.16M entries

### 3a. Our projection carries real information

Top-1% lift by our pre-lock projected sum:

| Projected-sum quintile | Week 1 | Week 2 | Week 3 |
|---|---|---|---|
| Top fifth | 1.95 | 1.01 | 1.67 |
| Bottom fifth | 0.24 | 0.51 | 0.29 |

Week 2 is the backup-QB defect week. Ranking by the projection is the right direction.

### 3b. The optimizer's curse is visible at the very top

Top-1% lift by projected-sum percentile band:

| Band | Week 1 | Week 2 | Week 3 |
|---|---|---|---|
| 80–95th | 1.99–2.08 | 0.88–1.41 | 1.78–1.87 |
| 98–99th | 1.42 | 0.12 | 0.99 |
| 99.5–100th | 0.68 | 0.12 | 0.50 |

- The lineups that look best to our projection are where our projection errors concentrate. Choosing the extreme
  maximum of a noisy estimate selects for its errors.
- At the top-10% line (satellite-like) Week 1 declines too (1.56 → 0.78), while Week 3 keeps rising (to 2.4–3.2).
  Week 3 is the week the top-mean book shone. **One week favoured the literal top-K-by-mean; one week did not; one
  week is unusable.**
- The mean track takes the literal top 144 of a 12,800-lineup pool, which is the far right tail of our own projection.
  L09's P(≥line) arms and the Q6 market floor are the two defences to measure. Don't assume the Week-3 gap repeats.

### 3c. A linear ownership tilt is not supported once our projection is held fixed

Raw, the chalkiest fifth of lineups wins more (lift 1.53 / 1.33 / 1.70). But ownership mostly restates projection.

Top-1% lift by ownership quintile *within* each projected-sum quintile:

| Week | Least owned | 2 | 3 | 4 | Most owned |
|---|---|---|---|---|---|
| 1 | 0.95 | 1.13 | 1.20 | 1.06 | **0.68** |
| 2 | 0.48 | 1.20 | 1.17 | 1.12 | 1.04 |
| 3 | 0.55 | 0.90 | 1.14 | 1.27 | 1.15 |

Pooled over the three weeks, in the top projection quintile: 1.41 / 2.22 / 2.36 / 1.72 / 1.14.

The pattern is non-monotone: **avoid the most contrarian lineups, and don't chase maximum chalk.**
- Q4's λ = 0.1 tilt was measured on the Week-3 pool, the week it was scored on (156.8). That is in-sample, and the
  field data does not support a linear tilt.
- What the data does support is a floor: do not build bottom-quintile-ownership lineups. The punt p90 valuation is what
  made our book the least chalky group (ownership sum 86 against the field's 105). Q4b's availability fix works in the
  right direction.

### 3d. Our construction rules forbid the shapes that win most often

**Top-10% lift (the satellite-like line) over all entries:**

| Shape | Week 1 | Week 2 | Week 3 |
|---|---|---|---|
| QB+1 | 0.91 | 0.92 | 0.81 |
| QB+2 | 1.32 | 1.30 | 1.51 |
| QB+3 | 2.23 | 1.44 | 2.46 |
| 4 players from one game | 1.21 | 1.18 | 1.26 |
| 5 players from one game | 1.91 | 1.08 | 2.10 |

**Among entries our projection rated in the 70–95th percentile:**

| Shape | Week 1 | Week 2 | Week 3 |
|---|---|---|---|
| QB+3 | 4.58 | 1.45 | 3.94 |
| 5 from one game | 3.16 | 1.37 | 3.56 |

- Every week, including the defect week, **QB+3 > QB+2 and 5-per-game ≥ 4-per-game.**
- Under the live rules (`MAX_PER_GAME=4` with a mandatory bring-back) QB+3 is **impossible**: QB + 2 + the bring-back
  already fills the game.
- L01 (my panel) compared a cap of 4 with *no cap*, not with 5. Its robust result was the pool oracle, and its book
  gain spanned zero.
- **Proposal:** a preregistered panel with MAXGAME5 (QB+3 allowed, bring-back kept) against the live cap of 4. Score
  it on the satellite line and the Millionaire line, on the L05/L09 panel. The laptop can build it on Monday and run it
  on the laptop in about 3 hours; the workstation stays on L06.

### 3e. Smaller consistent signals (three weeks, a thin QB count; flags, not rules)

Top-1% lift:

| Shape | Week 1 | Week 2 | Week 3 |
|---|---|---|---|
| $1,000+ salary unused | 0.37 | 0.69 | 0.37 |
| $6,500+ QB | 0.64 | 0.19 | 0.43 |
| $4,500+ TE | 0.56 | 0.16 | 0.75 |

The salary-left signal agrees with our $49k floor.

## 4. Other items in the plan

- **"Sunday beats Saturday."** The hourly Sunday refreshes do not re-project teammates when news breaks.
  - Isaiah Williams stayed at 6.6 after Mitchell was ruled out at 10:44.
  - Sadiq sat at 7.5 in every refresh from Saturday 09:57 to Sunday 11:03, then scored 26.5.
  - Warren sat at 12.2 all Sunday against a 15.1 market.
  - So the Sunday gain is mostly *removing inactives*, which the live re-layout and swaps already do. A large Sunday
    rebuild buys little beyond that until the model reallocates vacated volume on Sunday news. Weigh the
    09:10–11:15 build risk against that.
- **Cores in the high-total games:** tested at 148.8 vs 151.4. Stop, unless the Q8 variant is preregistered.
- **Q11 (Millionaire emulation):** please use conditional rates over the whole field, like the tables above, not the
  winners' anatomy. "Cheap QB" is the example of a winners'-anatomy artefact: the <$5.5k QB bucket had lift
  1.20 / 0.92 / 2.19.
- **Concentration.** The mean book used 118 distinct players on the D3200 pool (dual_emax used 140), and all
  satellites draw from it. Expected tickets are unchanged, but a single busted core (Week 3: 98 rows on two DSTs)
  zeroes a whole Sunday. The 25% DST cap is the minimum; a per-player exposure cap on the mean track is worth one
  line of code.

## 5. Better ways to win, in the order I would do them

1. **Select satellite rows at the ticket line** (L09, tonight). Set each contest's line from its real payout count.
2. **Let the optimizer build QB+3 and 5-per-game stacks** (a MAXGAME5 panel, Monday–Tuesday). This is the most
   consistent structural signal in 1.16M entries, and our rules currently forbid it.
3. **[CORRECTED 2026-09-28: already tested for the tail objective and closed negative. The lab ran 009 (invalid), then 023, "chase", k100 Δ −1.23, and 024/PREREG-003, "fresh tickets", −0.42; system study Addendum 67 found legal swaps worth +0.9, NULL. None of them measured tickets at a satellite line; see the HANDOFF entry of this date.]** Automate late swap for the 3:25/4:05 games (Week 5+). After the early games, re-optimize each satellite
   lineup's unlocked slots to maximize P(final ≥ line | points already scored). A lineup far below the line needs
   variance; one near it needs floor. DraftKings supports editing entries by CSV, and the FLEX-latest ordering (R11)
   already keeps those slots open. Pros do this, and the answer depends on information the field's static lineups
   cannot use.
4. **Contest selection with numbers.** The nineteen $2 11-entry satellites were a closed circle.
   - Three users, us among them, entered all 19.
   - Ten more regulars entered 5–18 each, supplied 56% of the entries, and averaged 136.5 points per lineup.
   - The 27 users with fewer than 5 entries averaged 120.6, about where our book was.
   - Satellite medians run 3–11 points above the Millionaire's. Each Monday, report our book's percentile per
   contest type; move stake toward types where our mean book clears the grinders' average. That is the operator's call.
5. **Shrink toward the market at the extreme** (Q6). This is the direct defence against 3b.

## 6. Asks

- **Production:**
  - re-score the rehearsal at each contest's real ticket line (§1);
  - re-run the L09 reader when I post it;
  - say whether you want the MAXGAME5 panel on the laptop Monday (§3d).
- **Operator (through production):**
  - the DraftKings rule for several tickets won by one user in one satellite (§2);
  - whether late-swap automation (§5.3) is wanted for Week 5.
