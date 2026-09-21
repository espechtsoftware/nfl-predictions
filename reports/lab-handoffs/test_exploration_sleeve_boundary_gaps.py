"""Three fail-open paths in `validate_lineup`, each currently ACCEPTED.

Written by the production side 2026-09-21 against
`lab/workstation-reply-bank991-20260918` @ 40735a60, because the sleeve's own
handoff records that pytest could not be run on that workstation, so there was
no way to verify either the defects or a fix.

All three fail today. They should pass once the validator is corrected; no
other test in tests/test_exploration_sleeve.py changes behaviour.
"""

import pytest

from nfl2.core.lineup import Lineup
from nfl2.exploration_sleeve import validate_lineup


def _players():
    players = [
        {"id": "qb", "pos": "QB", "team": "A", "opp": "B", "salary": 7000},
        {"id": "rb1", "pos": "RB", "team": "A", "opp": "B", "salary": 6000},
        {"id": "rb2", "pos": "RB", "team": "B", "opp": "A", "salary": 5500},
        {"id": "w1", "pos": "WR", "team": "C", "opp": "D", "salary": 6000},
        {"id": "w2", "pos": "WR", "team": "D", "opp": "C", "salary": 5500},
        {"id": "w3", "pos": "WR", "team": "E", "opp": "F", "salary": 5000},
        {"id": "te", "pos": "TE", "team": "F", "opp": "E", "salary": 5000},
        {"id": "flex", "pos": "TE", "team": "G", "opp": "H", "salary": 4500},
        {"id": "dst", "pos": "DST", "team": "H", "opp": "Z", "salary": 4500},
    ]
    for i, player in enumerate(players):
        player["game_id"] = str(i // 2)
    return players


def test_rejects_a_roster_spot_it_never_classified():
    """QB1 + RB2 + WR3 + TE1 + DST1 = 8 counted, nine players present.

    The five position counts are never asserted to sum to 9, so any `pos`
    outside the five literals rides along: a kicker, a null, a lowercase
    "wr", or a source-schema spelling drift. `K` is real in DK data (7,636
    rows in 2026) though only on showdown slates.
    """
    players = _players()
    players[7]["pos"] = "K"
    with pytest.raises(ValueError):
        validate_lineup(Lineup(players), qb_safe_ids={"qb"})


def test_explicit_none_cannot_silently_disable_the_quarterback_gate():
    """The sleeve's own handoff says the caller MUST supply `qb_safe_ids`.

    Making it a required keyword was the right half. The remaining half is the
    `is not None` guard: a caller threading an unset config through passes
    None, the gate is skipped, and the lineup is accepted with no quarterback
    check at all -- voiding the contract the handoff states.
    """
    players = _players()
    players[0]["id"] = "backup"
    with pytest.raises((ValueError, TypeError)):
        validate_lineup(Lineup(players), qb_safe_ids=None)


def test_rb_versus_dst_rule_fails_closed_when_the_dst_row_lacks_opp():
    """Same lineup is correctly rejected when `opp` is present.

    With `opp` absent, `dst_opp` is None, no real team equals None, and the
    rule passes. DST rows are exactly where opponent fields have gone missing
    or wrong before.
    """
    players = _players()
    players[1]["team"] = "Z"          # RB on the defence's real opponent
    players[8].pop("opp")             # ...but the DST row no longer says so
    with pytest.raises(ValueError):
        validate_lineup(Lineup(players), qb_safe_ids={"qb"})
