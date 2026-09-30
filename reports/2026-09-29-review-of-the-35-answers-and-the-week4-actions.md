# Review of "Where the points and money go" and of the Week-4 actions since it

Reviewer, 2026-09-29 20:10 CDT. Branch `review/ownership-term-20260929`. Asked by the operator: "review the report and
the actions taken since; tell me where I would do something different; we need unique ways to score higher."

Read: `reports/2026-09-29-where-the-points-and-money-go.md` at integration `69fe23f7`, its seven theme files under
`reports/lab-handoffs/2026-09-29-questions-research/`, the HANDOFF entries from 17:55 to 19:29 CDT, the lab ledger
through PREREG-L20, and the operator's 18:40 decisions. Three of the report's leads were checked on the 36-slate
panel tonight (§3); the scripts are in `reports/lab-handoffs/2026-09-29-ownership-term/` (08–10).

## 0. The short version

| | |
|---|---|
| The report | Sound. Its main claims hold up where I could check them. Two of its supporting statements are weaker than the text (§1). |
| The actions since | Right, and in the right order. Two changes: the spread dealing needs the per-contest offset before it is rehearsed again (addendum §3), and nothing else should be added to Week 4 (§2). |
| Where I would do something different | Not this week. From Week 5: put the research effort where the ceiling is (§4), and stop spending it on the three leads I closed tonight (§3). |
| "Revolutionary" | The honest answer is that the remaining edge is in three places, and they are not glamorous: a better ownership predictor (twice the term's current effect), a late swap that uses the real standings, and where the entries go. Everything else measured this week is noise-sized. |

## 1. The report: what holds and what is thinner than it reads

**Holds.** The funnel (the expected-max selector was the leak; fixed by the capped optimizer). The field as a
forecaster (the ownership term, now replicated on fresh banks by L20: +33% tickets at p89, 47–17, both seasons). The
simulator's defects (the main book no longer uses it). The portfolio anatomy (winners are our shape with better
player choice; the term is the mechanism that buys their choices). The money table (no class cleared the rake at
Weeks 1–3 quality). The process findings (season splits disagree 43% of the time; verdict labels flip in half of
bootstrap draws; the large directions do not).

**Thinner than it reads.**

1. **"The house rules added +40 / +7 / +7" and "the market projection beats the served" (B6).** These come from
   36-row books that share seven players with their first row, so each is close to one lineup. Week 1's served
   book held two busts in every row; that is one draw, not a measurement. The historical part of B6 is contaminated
   by the p90 punt valuation in the snapshot's `proj`, as B6 itself says. At the player level the served projection
   and the market are the same thing at the top of the slate (§3.1). Action 4 (the market-only plain book as a paper
   shadow) costs nothing and is fine; it is not evidence that the projection is where the points go.
2. **"DST projections carry no rank skill" (A, quoting the 09-22 decomposition).** On the 36 panel slates the DST
   projection ranks DSTs with Spearman 0.32, positive in 36 of 36 (§3.2). The 25% DST cap is a concentration control,
   not a correction of a skill-less projection, and it should be described that way.
3. **Action 6's "entry no earlier than Week 5"** is superseded by L20 and the operator's decision; the report should
   say so where it lists the actions.

## 2. The actions since 17:55, and my verdict on each

| Action | State | Verdict |
|---|---|---|
| Ownership term at 0.20 on the main book | patch merged, chain wired, audit check in, L20 SUPPORTED; gates: smoke, refusal path, Saturday lag file | **Arm.** Nothing to add. |
| Deep-line supersats held on the main book | operator: yes; `--hold-on-main` built | **Yes** (addendum §2). The term holds at 100 rows. |
| Spread dealing (`ENTER_LAYOUT=spread`) | built; rehearsed on Weeks 1 and 3 (+2 / 0 paid); production says Week 5 | **Not as built.** Equal-size contests take identical rows: 37 distinct lineups of 100. With one offset per contest, empty weeks fall from 25–30% to 11–21% at the same expected tickets (addendum §3). Rehearse that version; Thursday noon or Week 5. |
| Late swap on flat-payout contests | operator entered it; L11 was +11% in both seasons, paired 30–32 | Stands as the operator's choice. Two follow-ups in §4. |
| Actions 3 and 9 (punt cap, punt-band filter) demoted | laptop's dead-lever check on the Week-4 form | Agree. |
| Action 7 (chalk-core tie-breaker) deferred | overlaps the term | Agree; grade the term first. |
| Action 1 (contest mix) declined | operator: "keep my current mix" | The operator's call. One sentence for the record: the classes at the top of his priority list are the ones the evidence prices lowest (a Millionaire seat at 0.6–0.7× its fee ex-jackpot; qualifiers −96% lifetime), and the classes the evidence prices best sit at the bottom of it. Keeping the list is fine; sizing within it is the lever. |
| L16, L19 reads pending | tonight / Wednesday | Read them before touching the sleeve; with the routing the sleeve is five rows, so their reach this week is small. |
| Process items (2, 10, 11, 12) | queued | Agree. One addition in §4.5. |

**What I would not do this week:** add anything else that changes an upload. Week 4 already carries the laptop's
first week as host, a new main-book objective, the routing, and the late swap. Each of Weeks 1–3 lost money to a chain
defect, not to a research question. The smoke on Wednesday and the dry run on Thursday are the week's most valuable
hours.

## 3. Three leads checked tonight and closed

All on the 36 panel slates of 2023–24 with the same books as the arming report. Scripts 08–10.

### 3.1 A heavier market weight in the objective: not a lever

Priced skill players projected ≥ 8 (62 per slate):

| | Served projection (0.45 model / 0.55 market) | Market alone |
|---|---:|---:|
| Mean absolute error | 6.29 | 6.32 |
| Bias (realized − projected) | +0.84 | +1.13 |
| Residual of each source's own top 25 | +0.70 | +0.74 |
| Slates where the market's error is lower | 20 of 36 | |

The two are the same forecaster at the top of the slate (correlation 0.96). L04 already showed that a lighter market
weight loses; a heavier one has nothing to gain. B6's live gaps were single frames with specific misses.

### 3.2 A flat DST valuation (spend the DST salary on skill players): not a lever

| | |
|---|---:|
| Spearman of the DST projection with realized points, mean of 36 slates | 0.32 (positive in 36 of 36) |
| The three highest-projected DSTs, realized | 9.4 points at $3,513 |
| The three cheapest DSTs, realized | 4.3 points at $2,317 |

Five points for $1,200 is a better rate than any skill tier pays. The projection earns its DST salary.

### 3.3 Cash games as income: not with this book

| Book | Rows at or above the field's median | Double-up return per entry |
|---|---:|---:|
| plain, K 36 | 52–54% | −17% |
| with the term, K 36 | 58–62% | −8% to 0% |
| plain / with the term, K 100 | 51–54% / 58–60% | −18% / −8% to −3% |

The book's edge is in its upper rows, not at the median. The cash-shadow paper arms will show the same on Monday.

## 4. Where the remaining edge is, in order

### 4.1 The ownership predictor (the largest ceiling on the table)

L20's diagnostic arm says what the term is worth with perfect ownership: +72% tickets at p89 against +33% with the
blend. The predictor, not the term, is the bottleneck, as L05's cell C said in September.

- Now: O1 grades LineStar, FP, LAG and the two blends every Monday from Week 4.
- Week 5–6: a stacked predictor fitted walk-forward on LAG, LineStar, FP, salary, projection and value, with the
  blend as its baseline; it enters the term only through a frozen panel, as the blend did.
- Also test on the panel: λ by position (the term is skill-only and uniform now), and the "excess ownership" form
  (ownership above what salary and projection imply), which C found predicts the residual on its own.

### 4.2 A late swap that uses the real standings

After the early games, DraftKings shows every entry in the contest with its lineup and points. That is information
the pre-lock field did not have and most of it does not use. L11's chase policy re-solved late slots against a
simulated conditional field and gained +11% in both seasons (paired 30–32). A policy that reads the actual entries
above and below each of our rows, and their late-game exposures, can target the ticket line directly: move with the
entries it must pass when it is close, take variance when it is far. It cannot be replayed on the historical panel
(no historical field lineups), so it is built and graded live, on paper first, from the Week-4 standings.

### 4.3 Construction for optionality

Only rows with late-game players can be swapped; in L11 about half the rows had any. A row-level requirement of at
least two skill players from the 4:05 and 4:25 ET games makes every row swappable at a small cost in projected sum.
The pinned lab optimizer already supports it (`member_bounds`). Test on L11's harness: mean rows with and without the
requirement, swap vs keep, on the lab's 36 slates.

### 4.4 Where the entries go

The only lever with a lifetime-scale effect. The report's A2 and the winners study's §5 agree on the ordering of the
classes; the operator has chosen to keep his list. Within the list, the size of each class is still his to set every
week, and it is the one decision that moves the weekly expectation by more than any objective change.

### 4.5 Two process items to add

1. **Extend the panel.** Every verdict since L09 rests on the same 36 slates. The deep-line reads are a dozen events.
   The lag-only arms need no props archive, so 2022 and 2025 slates can carry the provably pre-lock arms at K = 36 and
   K = 100; the blend arms stay on 2023–24 until a props archive exists for the other seasons.
2. **A lineup model trained on the fields' own lineups**, once six weeks of 2026 fields exist. Three weeks were
   enough to show the shape effect (the Week-3 review's class model) and not enough to select on; six weeks may be.

## 5. What I would not spend time on

The market weight, a flat DST valuation, cash games (§3); duplication and uniqueness constraints (C5: fields are
90–94% unique); the simulator's P(≥ line) in any form until the two bank defects are fixed (E, L14); copying named
repeaters (F); a fourth objective change this season (G).

## 6. Reproduction

`reports/lab-handoffs/2026-09-29-ownership-term/08_projection_vs_market.py`, `09_dst_rank_skill.py`,
`10_double_up_read.py`; the README names the environment variables. No data files are committed.
