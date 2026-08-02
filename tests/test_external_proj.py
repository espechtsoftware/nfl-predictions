"""External projections import: loose-schema parse + diff join."""

import pandas as pd

from nfl_dfs import external_proj


def test_parse_flexible_columns_and_percent_scale():
    csv = ("Player,Pos,Projection,Ownership\n"
           "Justin Jefferson,WR,21.4,28.5%\n"
           "Bhayshul Tuten,RB,11.2,4.1%\n")
    d = external_proj.parse_csv(csv)
    assert list(d.columns) == ["name", "position", "proj", "own_pct", "ceiling"]
    assert len(d) == 2 and d.proj.iloc[0] == 21.4 and d.own_pct.iloc[1] == 4.1


def test_parse_fraction_ownership_rescaled():
    csv = "name,fpts,own\nA Player,10.0,0.22\n"
    d = external_proj.parse_csv(csv)
    assert abs(d.own_pct.iloc[0] - 22.0) < 1e-9


def test_parse_requires_name_and_proj():
    import pytest

    with pytest.raises(ValueError):
        external_proj.parse_csv("foo,bar\n1,2\n")


def test_diff_joins_on_normalized_name(monkeypatch):
    ext = pd.DataFrame({
        "source": ["etr"] * 2, "name": ["Kenneth Walker III", "A.J. Brown"],
        "ext_proj": [15.0, 20.0], "ext_own": [12.0, 25.0],
        "ext_ceiling": [30.0, 38.0]})
    monkeypatch.setattr(external_proj, "query_df", lambda *_a, **_k: ext)
    ours = pd.DataFrame({
        "display_name": ["Kenneth Walker III", "AJ Brown", "Nobody Else"],
        "position": ["RB", "WR", "TE"], "team": ["KC", "PHI", "X"],
        "salary": [6000, 7800, 3000], "proj_points": [11.0, 21.5, 5.0]})
    d = external_proj.diff(ours, 2026, 1)
    assert len(d) == 2  # punctuation-insensitive match
    assert d.iloc[0]["diff"] == -4.0  # Walker: biggest absolute diff first
