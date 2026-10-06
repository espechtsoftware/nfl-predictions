# R14: the LLM fact log (spec, 2026-10-06)

Source: `reports/2026-10-04-different-approaches.md` (R14, pick 1: "start the logging now"). This is the operator's 10-06
expedited plan, `briefings/2026-week-05/2026-10-06-expedited-test-plan.md`. **Logging only.** Nothing on the money path
reads the log until it has been graded over 4–6 weeks and a preregistered use passes.

## What is logged

For each Fantasy Points article collected before a week's lock (`nfl_raw.fantasy_points_articles`, season/week, text),
an LLM (the laptop agent) extracts **explicit, checkable statements** about a player's role or availability for that
week. It extracts no forecasts and no opinions about points. Each statement becomes one record:

| field | meaning |
|---|---|
| `logged_utc` | when the record was written (always before the player's kickoff; a record written after it is void) |
| `season`, `week`, `article_id`, `source_sha256`, `retrieved_at`, `published_date` | the source, by content identity |
| `player`, `team`, `position` | as written; `gsis_id` / `dk_player_id` filled by a later join, never by the extractor |
| `fact_type` | one of `availability` (injury, practice, status), `role_up` / `role_down` (snaps, routes, carries, targets, depth chart), `usage_quote` (a coach or beat quote about usage), `matchup` (a named defensive weakness or strength), `other` |
| `direction` | +1 / −1 / 0: the statement's implication for the player's DK points against a normal week, as the article states it |
| `magnitude` | a number only when the article states one (e.g. "70% of snaps"), else null |
| `quote` | the supporting sentence, at most 200 characters |
| `extractor` | model id and prompt sha256 |

## Rules

- **Prospective only.** Week 5 is the first logged week. Weeks 1–4 are not logged, because their outcomes are known.
- **Append-only.** One JSONL file per week. A correction is a new record that names the one it supersedes.
- **Private.** The records quote licensed vendor text. They live in `~/private/r14-fact-log/<season>-w<NN>.jsonl`, never in
  git. Only counts and graded aggregates may enter reports.
- **No use before grading.** The grading (4–6 weeks, preregistered first) asks two questions. Does `direction` predict the
  sign of (DK points − FP projection) beyond chance? Does it predict it for the facts FP's own projection could have
  priced, i.e. is it new information?

## The weekly step

After the Wednesday vendor run (articles collected), and again after any pre-lock refresh: extract → validate the schema →
append → record the counts in HANDOFF.
