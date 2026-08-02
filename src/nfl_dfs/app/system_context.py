"""Curated system knowledge for the chat assistant.

The chat's job includes reasoning about how a piece of player news
interacts with what the system ALREADY prices -- especially when
suggesting how to convert a watchlist note into a usage-note multiplier.
This module is the compact, maintained source of that knowledge (the
full documents are available via the read_doc tool; these sections are
written to be loaded into a tool result and reasoned over directly).

Update this file when the modeling changes -- it is documentation the
chat treats as ground truth.
"""

from __future__ import annotations

SECTIONS: dict[str, str] = {

    "overview": """\
Pipeline: BigQuery raw data -> point-in-time features (one row per
player-week; a week-W row only contains what was knowable before
kickoff) -> LightGBM component models (targets, carries, catch rate,
yards-per, TDs -- trained walk-forward, recency-weighted, 2014-2025) ->
Monte Carlo simulator (10,000 correlated worlds per week; possession
engine gives each game/team mean-preserving factors) -> MILP optimizer
(salary cap, roster rules, validated tournament constraints: mandatory
bring-back, sub-$4k punt, RB-vs-DST ban, chalk fade) -> greedy
tail-coverage selection of 40 entries maximizing P(best entry >= the
winning line). Everything is validated by deterministic season replays;
the shipping baseline is measured across six seasons (2019-2025).""",

    "notes_and_adjustments": """\
Two distinct note systems:
1. WATCH NOTES (watchlist.py): free text attached to a player. Affect
   NOTHING numerically. Shown on generated lineups and the Watchlist
   page. Stage one of: watch -> maybe convert.
2. USAGE NOTES (notes.py): a real adjustment. `mult` scales the
   player's OPPORTUNITY components only -- targets, carries, pass
   attempts -- NOT efficiency (yards per touch, TD rate stay modeled).
   Clamped to [0.6, 1.4]. Applied at full strength in week 1, decaying
   LINEARLY TO ZERO BY WEEK 6 -- by then actual snaps/usage flow into
   the trailing features and speak for themselves. Applied at live
   inference only, never in replays (forward-looking by construction).
Conversion (convert_watch_note) creates the usage note and stamps the
watch note converted, preserving provenance.""",

    "conversion_guide": """\
How to suggest a mult when converting a watch note. First diagnose the
note's ARCHETYPE, because each interacts differently with what the
system already prices:

A. OFFSEASON DEPARTURE / DEPTH-CHART VACANCY (trade or free agency
   opened the role -- e.g. "starter left, player X now atop depth
   chart"). The team_vacated_* features DO NOT see this: they read
   weekly INJURY REPORTS only, not departures. What does adapt:
   depth_rank (updates from depth charts) and cold-start role priors.
   The trailing usage features still reflect the old backup role for
   ~4 weeks. => This archetype deserves a REAL mult: +10-20% (1.10-
   1.20) for a clean, uncontested inheritance; +5-10% if the backfield/
   room is crowded. Check the depth chart first (get_player_form /
   explain_player) -- notes like "team also added two other backs"
   should cap the suggestion low.

B. NEW TEAM, CLEAR ROLE (veteran traded/signed into a bigger role).
   The system's WEAKEST spot and usage notes' BEST use: trailing
   features carry OLD-team usage (misleading), and veterans aren't
   cold-started (their history exists). => +10-25% depending on role
   clarity and target competition on the new team. The strongest case
   is a proven player whose old-team share was suppressed.

C. NEW COACH / SCHEME FIT ("zone scheme suits him", "new OC throws
   more"). Weakest evidence class; scheme features (neutral pass rate,
   pace) only learn from games played. => +5-10% at most, or advise
   keeping it as a watch note until September practice reports firm it
   up.

D. IN-SEASON INJURY VACANCY (starter on the injury report as Out).
   ALREADY PRICED: team_vacated_target/carry_share and depth_rank
   capture this the same week. => usually NO note needed (0-5%);
   adding one double-counts.

E. TALENT/EFFICIENCY TAKES ("fastest 40 time", "looked explosive").
   Usage notes scale OPPORTUNITY, not efficiency -- a speed note only
   converts if it implies MORE TOUCHES. Alone => keep as watch note.

Global dampeners to mention when suggesting:
- The props-market blend already prices all PUBLIC news within days;
  the mult should express edge beyond market consensus, which argues
  for the low end of each range.
- Multiple notes on one player MULTIPLY -- check list_usage_notes
  before stacking.
- Decay: full effect week 1 -> zero by week 6; a note added mid-season
  still decays on the same weekly schedule.
Protocol: read the note, call get_player_form/explain_player to check
the CURRENT depth chart and competition, classify the archetype, state
the suggested mult WITH the archetype reasoning and double-count
warnings, get the user's confirmation, then convert.

CAMP-SIGNAL CORROBORATION (convert-or-wait rule for August/September
notes): count independent corroborations in the note and any follow-ups
-- (1) first-team reps in MULTIPLE practices, (2) first-team/starter
usage in a PRESEASON GAME, (3) coach or teammate quotes naming the
role, (4) a depth-chart or beat-writer confirmation. 0-1 corroborations
=> keep as watch note, do not convert. 2 => convert at the LOW end of
the archetype range. 3+ => the archetype range as written. Camp hype
with zero usage evidence never converts.

SCHEME-CHANGE YEAR (2026): roughly 10 new head coaches and ~20 new
offensive playcallers this season -- an unusually large turnover. For
players on a team with a NEW PLAYCALLER, the trailing team features
(neutral pass rate, pace, target concentration) carry the OLD scheme
for the first ~4-6 weeks, so (a) last-year usage arguments are weaker
than normal there, (b) credible camp-role notes are MORE valuable than
in a normal year and may justify the upper half of the archetype range
when corroboration is 3+, and (c) the props blend is the fastest
adapter -- if the market has already moved a player's props, much of
the scheme story is priced. Ask the user (or check the note) whether
the team changed playcallers rather than assuming.""",

    "already_priced": """\
Signals the model already carries (adding a note for these
double-counts): trailing usage shares and trends (targets/carries/
snaps, last 4 weeks), red-zone and end-zone usage, depth chart rank,
draft capital and rookie flags, cold-start role priors, THIS-WEEK
injury-report vacancies (team_vacated_*), opponent defense quality
including CB coverage and top-CB-out, Vegas lines (spread, totals,
implied team total), weather, referee crew tendency, neutral-script
pass rate, QB CPOE (throw quality), salary and week-over-week salary
change, and the prop-market blend (sportsbook player props folded into
projections). NOT carried: offseason departures/trades (archetype A/B
above), scheme projection, camp reports.""",
}


def get_section(topic: str) -> str:
    t = (topic or "").strip().lower()
    if t in SECTIONS:
        return SECTIONS[t]
    return ("unknown topic; available: " + ", ".join(SECTIONS) +
            "\n\n" + SECTIONS["overview"])


def read_doc(name: str) -> str:
    """Full project documents, when the curated sections aren't enough.
    Reads from the container WORKDIR (Dockerfile copies them) with a
    repo-checkout fallback."""
    from pathlib import Path

    docs = {
        "model-primer": ["reports/model-primer.md"],
        "claude-md": ["CLAUDE.md"],
        "readme": ["README.md"],
    }
    rel = docs.get((name or "").strip().lower())
    if not rel:
        return "unknown doc; available: " + ", ".join(docs)
    for base in (Path.cwd(), Path(__file__).resolve().parents[3]):
        p = base / rel[0]
        if p.is_file():
            text = p.read_text()
            return text[:60_000] + ("\n...[truncated]" if len(text) > 60_000 else "")
    return f"{rel[0]} not found in this deployment"
