"""The Milly graph's fact layer (study list item 44; reports/2026-10-06-neo4j-winner-likeness-inputs.md): pre_ facts
come from the frame and prior games only, out_ facts from the week's results, a same-week outcome is refused under a
pre_ name, vendor columns stay out unless opted in, and the game / lineup facts compute as documented. Offline."""
import pandas as pd
import pytest

from nfl_dfs.dashboard import milly_graph_facts as F


def _frame():
    rows = []
    for i, (team, opp, game, spread) in enumerate((("BUF", "NE", "g1", -7.0), ("NE", "BUF", "g1", 7.0),
                                                   ("KC", "LV", "g2", -3.0), ("LV", "KC", "g2", 3.0))):
        for pos, sal in (("QB", 7000), ("RB", 6000), ("WR", 5000), ("WR", 3500), ("TE", 4000), ("DST", 3000)):
            k = len(rows)
            rows.append({"id": f"00-{k:04d}", "dk_player_id": 100 + k, "team": team, "opp": opp, "pos": pos,
                         "game_id": game, "salary": sal, "spread": spread, "game_total": 50.0 if game == "g1" else 44.0,
                         "implied_team_total": 28.5 if spread < 0 else 21.5, "game_start": "2026-10-04 17:00:00+00:00",
                         "rz20_targets_l4": 1.0 + k, "gl3_carries_l4": 0.5, "targets_l4": 6.0, "mean_projection": 10.0 + k,
                         "fp_route_share_l4": 0.8, "pace_l4": 60.0, "proe_l4": 0.02,
                         "team_vacated_target_share": 0.1, "team_vacated_carry_share": 0.0})
    return pd.DataFrame(rows)


def test_pre_and_out_are_separate_and_carry_provenance():
    fr = _frame()
    lag = pd.DataFrame({"gsis_id": ["00-0000"], "tds_l4": [3], "tds_l8": [5], "pass_tds_l4": [6], "pass_tds_l8": [11],
                        "pass_att_l4": [34.5], "games_prior_l8": [8]})
    out = pd.DataFrame({"gsis_id": ["00-0000"], "targets": [0], "rush_tds": [1], "pass_tds": [2], "dk_points": [24.3]})
    pbp = pd.DataFrame({"gsis_id": ["00-0000"], "rz20_targets": [0], "rz20_carries": [2], "gl5_carries": [1],
                        "ez_targets": [0], "rz_tds": [1]})
    rows = F.player_week_rows(fr, "2026-04", "run sha", "2026-10-04T15:50Z", lag, out, pbp)
    qb = next(r for r in rows if r["dk_player_id"] == 100)
    p = qb["props"]
    assert qb["key"] == "100|2026-04"
    assert p["pre_rz20_targets_l4"] == 1.0 and p["pre_tds_l4"] == 3 and p["pre_pass_att_l4"] == 34.5
    assert p["out_pass_tds"] == 2 and p["out_dk_points"] == 24.3 and p["out_gl5_carries"] == 1 and p["out_rz_tds"] == 1
    assert p["pre_source"] == "run sha" and p["pre_as_of"] == "2026-10-04T15:50Z"
    assert not any(k.startswith("pre_") and k[4:] in F.OUTCOME_NAMES for k in p)
    assert "pre_fp_route_share_l4" not in p                                   # vendor column: opt-in only
    with_fp = F.player_week_rows(fr, "2026-04", "s", "t", include_vendor=True)
    assert with_fp[0]["props"]["pre_fp_route_share_l4"] == 0.8
    assert len(rows) == len(fr)


def test_a_same_week_outcome_under_a_pre_name_is_refused():
    with pytest.raises(ValueError, match="same-week outcome under a pre_ name"):
        F.assert_point_in_time([{"props": {"pre_dk_points": 30.0}}])
    with pytest.raises(ValueError, match="neither the pre_ nor the out_ group"):
        F.assert_point_in_time([{"props": {"targets": 5}}])
    F.assert_point_in_time([{"props": {"pre_targets_l4": 5, "out_targets": 7, "pre_source": "x"}}])


def test_team_and_game_facts():
    fr = _frame()
    tw = {r["team"]: r["props"] for r in F.team_week_rows(fr, "2026-04", "s", "t")}
    assert tw["BUF"]["pre_favourite"] is True and tw["NE"]["pre_favourite"] is False and tw["BUF"]["pre_implied_total"] == 28.5
    sch = pd.DataFrame({"game_id": ["g1", "g2"], "home_team": ["BUF", "KC"], "away_team": ["NE", "LV"],
                        "home_score": [10, 31], "away_score": [7, 28], "week": [4, 4]})
    g = {r["game_id"]: r["props"] for r in F.game_fact_rows(fr, sch, "s", "t")}
    assert g["g1"]["pre_total"] == 50.0 and g["g1"]["out_total"] == 17 and g["g1"]["out_top_game_rank"] == 2
    assert g["g2"]["out_top_game_rank"] == 1 and g["g1"]["pre_kickoff"] == "early" and g["g1"]["pre_spread_home"] == -7.0
    assert F.kickoff_window("2026-10-05 00:20:00+00:00") == "night" and F.kickoff_window("2026-10-06 00:15:00+00:00") == "other day"


def test_lineup_labels_and_tiers():
    fr = _frame()
    ids = list(fr.dk_player_id)
    # BUF QB + 2 BUF pass-catchers + NE WR bring-back + NE RB + KC RB + KC WR + LV TE + BUF DST
    picks = [(ids[0], "QB"), (ids[2], "WR"), (ids[3], "WR"), (ids[8], "WR"), (ids[7], "RB"), (ids[13], "RB"),
             (ids[14], "FLEX"), (ids[22], "TE"), (ids[5], "DST")]
    contains = [{"lineup_key": "L1", "dk_player_id": p, "slot": s} for p, s in picks]
    own = {("c", p): (3.0 if i % 2 else 20.0) for i, p in enumerate(ids)}
    own.update({("other", p): 99.0 for p in ids})                    # another contest's ownership is never used
    rows = F.lineup_label_rows([{"key": "L1", "contest_id": "c", "rank": 1, "points": 230.0}], contains, fr, own,
                               {"c": 160_000}, {"c": 230.0})
    p = rows[0]["props"]
    assert p["lbl_games"] == 2 and p["lbl_qb_game_rank"] == 1 and p["lbl_qb_favourite"] is True
    assert p["lbl_top_game_players"] == 6 and p["lbl_cheap_players"] == 1 and p["lbl_flex_pos"] == "WR"
    assert p["lbl_dual_stack"] is True and p["lbl_salary_left"] == 50_000 - sum(fr.set_index("dk_player_id").salary[[x for x, _ in picks]])
    assert p["out_tier_winner"] and p["out_tier_top01pct"] and p["out_tier_within10"]
    assert p["out_own_under5_realized"] == sum(own[("c", x)] < 5 for x, _ in picks) and p["out_own_max_realized"] == 20.0
    assert not any(k.startswith("lbl_") and "own" in k for k in p)       # realized ownership is never a pre-lock label
    with pytest.raises(ValueError, match="realized"):
        F.assert_point_in_time([{"props": {"lbl_own_max": 20.0}}])


def test_the_td_price_prior_top_and_starters_out_are_pre_lock_facts():
    """10-07 (the outside reviewer's facts-layer review): the market's anytime-TD price (yes side, mean implied
    probability over books), the prior real weeks' top-1% share by dk id, and depth-chart starters missing from the
    frame's active pool, all under pre_ names."""
    fr = _frame(); fr["display_name"] = [f"Player {chr(65 + k)}{chr(65 + k)} Jr." for k in range(len(fr))]
    props = pd.DataFrame({"player": ["Player AA Jr.", "Player AA Jr.", "Player BB"], "bookmaker": ["a", "b", "a"],
                          "price": [150, -120, 400], "outcome_name": ["Yes", "Yes", "No"]})
    td = F.td_probabilities(props)
    assert list(td.key) == ["player aa"] and td.books.iloc[0] == 2
    assert abs(td.td_prob.iloc[0] - (100 / 250 + 120 / 220) / 2) < 1e-12
    pt = pd.DataFrame({"dk_player_id": [100, 101], "prior_top": [0.21, 0.0], "weeks": [3, 1]})
    rows = {r["dk_player_id"]: r["props"] for r in F.player_week_rows(fr, "2026-05", "s", "t", td=td, prior_top=pt, prior_top_source="f sha x")}
    assert rows[100]["pre_anytime_td_prob"] == td.td_prob.iloc[0] and rows[100]["pre_prior_top1_share"] == 0.21
    assert rows[100]["pre_prior_top1_source"] == "f sha x" and "pre_anytime_td_prob" not in rows[101]
    st = pd.DataFrame({"team": ["BUF", "BUF", "NE"], "gsis_id": ["00-0000", "00-9999", "00-0006"], "pos_abb": ["QB", "WR", "QB"]})
    tw = {r["team"]: r["props"] for r in F.team_week_rows(fr, "2026-05", "s", "t", starters=st)}
    assert tw["BUF"]["pre_starters_out"] == 1 and tw["BUF"]["pre_starters_out_pos"] == "WR" and tw["NE"]["pre_starters_out"] == 0
    assert "pre_starters_out" not in tw["KC"]
    assert F.team_code("LAR") == "LA" and F.canon_name("Amon-Ra St. Brown") == "amon ra st brown"
