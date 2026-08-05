"""Shared name normalization (2026-08-04 readiness)."""
from nfl_dfs.names import initial_key, match_map, norm_name, resolve


def test_suffixes_stripped():
    assert norm_name("Odell Beckham Jr.") == "odell beckham"
    assert norm_name("Kenneth Walker III") == "kenneth walker"
    assert norm_name("Marvin Harrison Jr") == "marvin harrison"
    # short names never stripped to nothing
    assert norm_name("Ja'Marr Chase") == "jamarr chase"


def test_diminutive_fallback_when_unambiguous():
    lookup = match_map({"Cam Ward": "g1", "Justin Jefferson": "g2"})
    assert resolve("Cameron Ward", lookup) == "g1"
    assert resolve("J. Jefferson", lookup) == "g2"


def test_ambiguous_initials_never_guess():
    lookup = match_map({"Josh Jones": "g1", "Jalen Jones": "g2"})
    assert resolve("J. Jones", lookup) is None
    assert resolve("Josh Jones", lookup) == "g1"


def test_prefs_match_suffix_variants():
    from nfl_dfs.notes import norm_name as pref_norm

    assert pref_norm("odell beckham") == pref_norm("Odell Beckham Jr.")
