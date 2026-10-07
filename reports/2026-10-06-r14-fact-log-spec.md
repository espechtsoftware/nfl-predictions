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
| `fact_type` | one of `availability` (injury, practice, status), `role_up` / `role_down` (snaps, routes, carries, targets, depth chart), `usage_quote` (a coach or beat quote about usage), `matchup` (a named defensive weakness or strength), `other`; from W6 also `team_change` (the amendment below) |
| `direction` | +1 / −1 / 0: the statement's implication for the player's DK points against a normal week, as the article states it |
| `magnitude` | a number only when the article states one (e.g. "70% of snaps"), else null |
| `quote` | the supporting sentence, at most 200 characters |
| `extractor` | model id and prompt sha256 |

## Rules

- **Prospective only.** Week 5 is the first logged week. Weeks 1–4 are not logged, because their outcomes are known.
- **Append-only.** One JSONL file per week. A correction is a new record that names the one it supersedes.
- **Article versions** (added 2026-10-07, before any grading; the reviewer's rules, after FP republished the W5 Game Hub):
  - **(a)** A logged article may take a later VERSION: a new `source_sha256` whose `published_date` AND `retrieved_at` are
    both strictly later than every logged version's; otherwise the append is refused. Its records carry `version_of` (the
    latest logged version's sha), and statements already logged (same article, player, fact type, quote) are skipped. The
    void-after-kickoff rule applies per record, unchanged.
  - **(b) Grading rule, preregistered now:** per (article_id, player, fact_type), the record from the LATEST version
    published before that player's kickoff counts. A statement a later version drops still counts (it was made and never
    retracted); a changed direction or magnitude in a later version is the later record.
  - **(c)** HANDOFF records the counts per version (new records, deduplicated records). The frozen extraction prompt is the
    same for every version.
- **Private.** The records quote licensed vendor text. They live in `~/private/r14-fact-log/<season>-w<NN>.jsonl`, never in
  git. Only counts and graded aggregates may enter reports.
- **No use before grading.** The grading (4–6 weeks, preregistered first) asks two questions. Does `direction` predict the
  sign of (DK points − FP projection) beyond chance? Does it predict it for the facts FP's own projection could have
  priced, i.e. is it new information?

## The weekly step

After the Wednesday vendor run (articles collected), and again after any pre-lock refresh: extract → validate the schema →
append → record the counts in HANDOFF.

## Amendment (2026-10-07, before Week 6's extraction): team moves, the Saturday sweep, one prompt per week

The operator 10-07 (study list 61, step 2: "the trade deadline is near and Dallas just got a cornerback"). The reviewer
named the record form 10-07. Study 61's prereg §7 requires the player mapping to be defined before W6's extraction.

- **`team_change`, a seventh fact type from W6.** A trade, signing, release or injured-reserve move (or a return from IR)
  that the article says changes a team's unit. It is logged only when the article states BOTH the move AND what it does
  to the unit.

  | field | for `team_change` |
  |---|---|
  | `player` | the moved player, as written; he may be a defender or a lineman who is never on the frame |
  | `team` | the team whose unit changes, as written (required); the reader aliases it |
  | `direction` | always 0: written as 0 when absent, and ±1 is refused. It is a unit record, not a player statement |
  | `unit` | one of `pass_defense`, `run_defense`, `pass_rush`, `offensive_line`, `receiving_corps`, `backfield` |
  | `unit_effect` | +1 stronger, −1 weaker, 0 unclear, in the article's own words |
  | `quote` | as for every record, at most 200 characters |

  - `unit` and `unit_effect` are required on `team_change` and refused on the other six types, so neither can leak.
  - A moved skill player's own role or availability, when the article states it, is a separate record of the other
    types.
- **The player mapping**, defined now and applied only by study 61's reader amendment 3, on its own descriptive line.
  It never enters study 61's primary through W10 (the W8 and W10 reads).
  - `pass_defense` or `pass_rush`: the opponent's QB, WR and TE on the frame; derived direction = −`unit_effect`.
  - `run_defense`: the opponent's RBs; −`unit_effect`.
  - `offensive_line`: the team's own QB and RBs; +`unit_effect`.
  - `receiving_corps` and `backfield`: no derived players, a count only. Who gains stays the article's `role_up` /
    `role_down` on named teammates.
  - The opponent comes from the frame's `opp`. A team not on the Main slate gets no derived players and is counted.
- **One prompt per week.**
  - v1 (`PROMPT.md`, sha256 `ee7a1310b7bddf0ff17f517fb22f8383568a17fdb90e08c330aca65ee15b820d`, frozen) serves W5,
    its Saturday sweep included.
  - v2 (`PROMPT-v2.md`, sha256 `0ff953775f06b63ff656493ffdbd1185f64234fa01e729dff8c475ff9811c183`: v1 plus
    `team_change`) serves W6's extraction on.
  - The appender picks the prompt by week. It refuses an append to a week whose log holds records of another prompt.
- **The Saturday sweep, a standing step from W5:**
  - Run it on Saturday, outside any build window, before Sunday's T-70 DraftKings pull (10:33 CT).
  - Collect the week's articles again: `python -m nfl_dfs.ops.fantasy_points_articles collect --week W`.
  - Extract only the new articles and the new versions (rule (a)), append, and record the sweep's counts in HANDOFF.
  - Records logged before the T-70 pull count (study 61 §2); later ones are void.
  - Late-week news, the trade deadline included, is then logged before lock.
- **The appender** (private, beside the log): `r14_append.py` sha256 `721e74c2d01424b00221ff6931487d502ca32b79908a1430beb5b4a70f8c42e1`.
  Its private test passes 17 checks (`test_r14_append.py` `bb770ad14ea0807d1ecfa9233c12339aa70597009befd9a70d68b3d70a188837`):
  - the version rule and supersedes (7);
  - `team_change`'s required and refused fields, direction forced 0, the prompt by week, the one-prompt rule, the counts;
  - the real W5 log (606 records) still validating.
