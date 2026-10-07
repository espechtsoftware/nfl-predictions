# Preregistration: study 61, does FP's news predict what FP's projections miss? The R14 fact log, graded on paper (DRAFT 2026-10-07)

**Status: DRAFT 2026-10-07** by the reviewer, before any Week-5 game.
- Week 5's first kickoff is Thursday 10-08 at 19:15 CT (TB at DAL). The graded slate, DraftKings' Sunday Main, starts
  Sunday 10-11 at 12:00 CT. The London game (08:30 CT) is not on it.
- **The design freezes before Thursday's kickoff.** The reader is pinned by an amendment before Sunday 12:00 CT (§9).

**Units:** DK points, counts and rates only. No quote and no article text ever enters a report.

## 1. Why
- **The operator 10-07**, verbatim, relayed by the laptop: "Where in the queue is the item we discussed about collecting
  news about teams and players and considering that in our selections. For example, the trade deadline is near and
  Dallas just got a cornerback. These moves likely get considered in the fantasy points projections, but i think
  collecting fantasy points articles and doing a paper study makes sense". This is study list item 61.
- **R14 has been logging since W5** (`reports/2026-10-06-r14-fact-log-spec.md`). Before each lock the laptop extracts every
  explicit, checkable statement from the week's Fantasy Points articles, with a direction (+1 / −1 / 0).
  - W5 so far: 606 statements from 9 articles.
  - By type: availability 211, matchup 108, role_up 82, role_down 22, usage_quote 5, other 178.
  - By direction: −1 ×192, +1 ×134, 0 ×280.
- **The spec's two questions:**
  - Does a statement's direction predict how a player does against FP's projection, beyond chance?
  - Is that information FP had not priced?
- **From W5 our projections ARE FP's** (the operator 10-05). So "beyond FP's projection" means beyond our live
  projection.
- **This study adopts nothing.** Only if it reads positive does a paper arm follow, whose projections the facts nudge
  (§7). After that comes his live-trial call.

## 2. Population and the projection (outcome-blind)
- **The players:** each week, the skill players (QB, RB, WR, TE) of the ENTERED union's T-70 frame, i.e. DraftKings'
  Main slate after the 10:30 CT inactives, the players a build could roster. Each must have an FP projection in that
  union's `proj_source.csv`.
  - That `fp` value is the projection our build used.
  - A player ruled out at 10:30 is not on the frame. His news is of no use to us, because the build removes him anyway.
  - DSTs are left out: they have no gsis id, and the log is about player roles.
- **A record joins a frame player** by its written name and team.
  - The name is normalised: case, punctuation and the suffixes Jr / Sr / II–V are removed.
  - The team is mapped to DraftKings' abbreviation by an alias table fixed in the reader.
  - Failing that, the normalised name alone joins if exactly one frame player has it. Otherwise the record is unmatched
    and counted.
  - The spec's `gsis_id` / `dk_player_id`, when filled, must agree with the join. A disagreement is counted and the
    record left out.
- **A record counts when all of these hold:**
  1. It was logged (`logged_utc`) before the T-70 frame's DraftKings pull (`pulled_at`, 10:33 CT). A later record
     could not feed the build. Every Main-slate kickoff is later still, so the spec's void-after-kickoff rule is met.
  2. It survives the spec's version rule (b). Per (article, player, fact type), the records of the latest version that
     has any are kept; a statement a later version drops still counts. A record a later correction names as superseded
     does not count.
  3. Its direction is +1 or −1. Direction 0 is descriptive only (§5).
- **A player's net direction** n is the sign of the sum of his counted records' directions. A tie (n = 0) is
  descriptive only.

## 3. Outcome
- r = the player's real DK points − his FP projection (`fp`), in DK points.
  - Real points come from `nfl_features.player_week_actuals.dk_points` by gsis id: the model's own target. It covers every
    player, including those with no stat line, who score 0.
  - The reader records a content sha of the rows it used, so a stat correction shows on a re-run.
- **r′ = r − the mean r of the same position on the same week's population** (§2's players, all of them). A slate-wide
  or position-wide miss by FP is not credited to the articles.

## 4. The primary
- **Per week w:** Δ_w = the mean r′ over players with n = +1, minus the mean r′ over players with n = −1. In words: the
  players the articles were positive about, minus the players they were negative about, in DK points against FP's
  projection.
  - If the articles add nothing FP had not priced, Δ_w is 0 on average.
- **A week is valid** when both groups hold at least 10 players and the week's union, frame and projection files are
  the entered ones (content identity, §8).
- **Looks at W8 and W10**, each over the valid weeks from W5 up to it. A look needs at least 4 valid weeks; with fewer
  it reads "too few valid weeks".
  - The interval is the two-sided 90% t interval on the weekly Δ_w: each side a one-sided 95% bound, with n − 1 degrees
    of freedom, as in studies 60 and P1.
  - **Lower bound > 0:** "the articles carry information FP's projections had not priced". The paper arm follows (§7).
  - **Upper bound < 0:** "the articles point the wrong way".
  - **Otherwise:** "no information shown".
  - W10's look is the study's verdict. W8's can only start the paper arm early.
- **A limitation, stated now:** a positive Δ can also come from FP mis-projecting the kinds of players the articles
  write about (for example backups whose roles grow), not from the facts as such. Either way the practical test is the
  paper arm.

## 5. Secondary (descriptive, never ruling)
- **Δ by fact type** (availability, role_up, role_down, usage_quote, matchup, other), at the record level: each counted
  record's direction against its player's r′. Also the primary computed without "other".
- **The spec's second question:** records whose article version was published (`published_date`) before the date of FP's
  last update (`fp_last_updated` in the projection's sidecar), so FP could have priced them, against those published on
  or after it.
- **The sign rate:** how often sign(r′) = n, the spec's own form.
  - Its chance rate is not 1/2: DK points are right-skewed (the median falls below the mean), and by different amounts
    for different players.
  - That is why the primary uses points, and why this rate is descriptive.
- **Direction 0:** the mean r′ of players whose only counted records have direction 0. It is a placebo, expected near 0.
- **Counts each week:**
  - records logged, joined, voided (logged late), unmatched, superseded and counted, by fact type;
  - players per group;
  - team_change records (W6 on), if the spec amendment adds them.

## 6. Power (W4's residuals; W4 has no fact log and is settled)
- **The measure:** r = DK points − FP's projection, from FP's W4 Sunday capture, for the 333 of its 395 projected
  players found in W4's contest tables.
  - Mean +0.00, sd 5.94. For players FP projected at 3 or more: sd 7.43.
  - By position: QB 5.7, RB 8.1, WR 9.0, TE 6.1.
- **One week's Δ:** with about 50 players a side and sd 7, its standard error is about 1.4 DK points.
- **The 90% half-width** if the week-to-week spread equals that: about 1.6 points at 4 weeks (t₃ 2.35) and 1.1 at 6 weeks
  (t₅ 2.02).
- **What it means:** only an edge of more than about 1 DK point per player between good-news and bad-news players reads
  by W10. A null therefore says "less than about a point", not "nothing".
- The real group sizes come from W5's support census (§9) and are recorded before the first read.

## 7. What a reading can do
- **"Information not priced":** a PAPER arm in study 38's co-run whose projections the counted facts nudge.
  - Its dose and form are preregistered in its own amendment before its first outcome.
  - Then his live-trial call.
- **Otherwise:** no use. The logging continues only if he wants it (it is cheap).
- **The team_change fact type** proposed for W6 (a trade, signing or IR move that changes a unit, e.g. DAL's pass defense
  after a cornerback trade) names a unit, not a player.
  - It enters the primary only if the spec amendment defines, before W6's extraction, which players it applies to and
    with which direction (e.g. the opposing passing game).
  - Otherwise it is descriptive only.

## 8. Data and code
- **The log:** `~/private/r14-fact-log/2026-wNN.jsonl` (private). The extraction prompt's sha is in each record.
- **The union:** the ENTERED W-week union dir, with its `frame.parquet`, `proj_source.csv` (with its `.json` sidecar) and
  `receipt.json`. They are checked by content against the receipt's recorded shas.
- **The actuals:** `nfl_features.player_week_actuals`.
- **The reader:** `scripts/s61_r14_grade.py` (the reviewer).
  - It does the join, the alias table, the cut-offs, the version rule, Δ and the looks.
  - It prints aggregates only, never a quote.
  - Its `--census` mode reads no outcome: only the records, the frame and the projection file.

## 9. Order
1. This DRAFT.
2. **The design freeze**, before Thursday 10-08 at 19:15 CT.
3. **The reader**, its tests and a smoke.
   - The smoke uses the W5 log's records and the W5 frame once it exists, in census mode only, plus a synthetic scored
     week.
   - An amendment pins the reader's sha before Sunday 10-11 at 12:00 CT.
4. **Sunday, after the T-70 union:** the W5 support census (outcome-blind), committed before any read.
5. **Each week once the actuals load** (Tuesday at the latest): the weekly read, descriptive until W8, which the laptop
   re-runs.
6. The looks at W8 and W10.
