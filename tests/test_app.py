import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient

from nfl_dfs.app import main as app_main
from nfl_dfs.app.store import InMemoryStore


def projections_frame(seed=51, n_teams=6, season=2025, week=3):
    rng = np.random.default_rng(seed)
    rows = []
    pid = 1000
    for t in range(n_teams):
        team, opp = f"T{t}", f"T{t + 1 if t % 2 == 0 else t - 1}"
        for pos, n in (("QB", 2), ("RB", 3), ("WR", 4), ("TE", 2), ("DST", 1)):
            for i in range(n):
                base = {"QB": 19, "RB": 13, "WR": 11, "TE": 8, "DST": 7}[pos]
                mu = max(1.0, base - 2.5 * i + rng.normal(0, 1.5))
                rows.append({
                    "season": season, "week": week, "slate_id": 9001,
                    "gsis_id": f"00-{pid}", "dk_player_id": pid,
                    "display_name": f"{pos}{i} {team}", "position": pos,
                    "team": team, "opponent": opp,
                    "salary": int(np.clip(2700 + mu * 330, 2500, 9500)),
                    "proj_points": mu,
                    "proj_p10": mu - 5, "proj_p50": mu, "proj_p90": mu + 7,
                    "proj_std": 5.0, "p_20_plus": 0.2,
                    "value": mu / 5.0, "model_version": "pooled/2025-W30",
                    "generated_at": "2025-09-16T14:00:00Z",
                })
                pid += 1
    return pd.DataFrame(rows)


@pytest.fixture
def client():
    frame = projections_frame()
    app_main.app.dependency_overrides[app_main.default_store] = (
        lambda: InMemoryStore(frame)
    )
    yield TestClient(app_main.app)
    app_main.app.dependency_overrides.clear()


def test_health(client):
    assert client.get("/health").json() == {"status": "ok"}


def test_slates(client):
    slates = client.get("/slates").json()
    assert slates == [{"season": 2025, "week": 3, "players": 72}]


def test_projections_sorted_and_filterable(client):
    r = client.get("/projections", params={"season": 2025, "week": 3})
    assert r.status_code == 200
    rows = r.json()
    projs = [row["proj_points"] for row in rows]
    assert projs == sorted(projs, reverse=True)

    wr = client.get("/projections",
                    params={"season": 2025, "week": 3, "position": "wr"}).json()
    assert all(row["position"] == "WR" for row in wr)

    missing = client.get("/projections", params={"season": 2025, "week": 9})
    assert missing.status_code == 404


def test_lineup_builder(client):
    r = client.post("/lineups", json={
        "season": 2025, "week": 3, "n_lineups": 3,
        "qb_stack_min": 1, "objective": "proj_p90",
        "sim": False,
    })
    assert r.status_code == 200
    body = r.json()
    assert len(body["lineups"]) == 3
    for lu in body["lineups"]:
        assert len(lu["players"]) == 9
        assert lu["salary"] <= 50_000
    assert body["dk_csv"].startswith("QB,RB,RB,WR,WR,WR,TE,FLEX,DST")
    exposures = {e["id"]: e for e in body["exposure"]}
    assert all(0 < e["exposure"] <= 1 for e in exposures.values())


def test_tail_line_scales_with_field_size(client):
    # Anchor: the Milly field reproduces the measured 194 line; smaller
    # fields win lower, monotonically, and never below the contending mean.
    assert app_main.tail_line_for_field(app_main.MILLY_FIELD) == 194.0
    q20k = app_main.tail_line_for_field(20_000)
    q5k = app_main.tail_line_for_field(5_000)
    assert q5k < q20k < 194.0
    assert q20k > 180  # sanity: a 20k qualifier is not a cakewalk

    # /contests retains the provisional estimate for comparison, but the
    # production builder uses the fixed 194 selector that was validated.
    opts = client.get("/contests").json()
    assert opts["presets"][0]["field_size"] == 20_000
    assert all(c["tail_line"] == 194.0 for c in opts["presets"])
    assert all("estimated_winning_line" in c for c in opts["presets"])

    # field_size does not silently switch away from the adopted selector.
    r = client.post("/lineups", json={
        "season": 2025, "week": 3, "n_lineups": 1, "field_size": 20_000,
        "sim": False,
    })
    assert r.status_code == 200
    assert r.json()["tail_line"] == 194.0
    # explicit tail_line overrides field_size
    r = client.post("/lineups", json={
        "season": 2025, "week": 3, "n_lineups": 1, "field_size": 20_000,
        "tail_line": 205.0,
        "sim": False,
    })
    assert r.json()["tail_line"] == 205.0


def test_lineup_builder_locks_and_csv_endpoint(client):
    frame = projections_frame()
    a_wr = int(frame[frame.position == "WR"].dk_player_id.iloc[-1])
    r = client.post("/lineups", json={
        "season": 2025, "week": 3, "n_lineups": 1, "locks": [a_wr],
        "sim": False,
    })
    ids = [p["id"] for p in r.json()["lineups"][0]["players"]]
    assert a_wr in ids

    csv_resp = client.post("/lineups.csv", json={"season": 2025, "week": 3,
                                                 "sim": False})
    assert csv_resp.status_code == 200
    assert csv_resp.headers["content-type"].startswith("text/csv")


def test_lineup_infeasible_constraints(client):
    r = client.post("/lineups", json={
        "season": 2025, "week": 3, "n_lineups": 1,
        "qb_stack_min": 3,  # only ~6 WR/TE per team projected > cap conflicts
        "bring_back_min": 2,
        "bans": list(range(1000, 1030)),
        "sim": False,
    })
    assert r.status_code in (200, 422)  # feasibility depends on pool; must not 500


def defense_frame(season=2025, weeks=6, n_teams=6, seed=9):
    rng = np.random.default_rng(seed)
    rows = []
    for t in range(n_teams):
        for pos in ("QB", "RB", "WR", "TE"):
            base = rng.uniform(15, 35)
            vals = []
            for wk in range(1, weeks + 1):
                fp = max(0.0, rng.normal(base + (2 if t == 0 else 0) * wk, 4))
                vals.append(fp)
                s = pd.Series(vals)
                rows.append({
                    "team": f"T{t}", "season": season, "week": wk,
                    "position": pos, "fp_allowed": fp,
                    "fp_allowed_l3": s.tail(3).mean(),
                    "fp_allowed_l6": s.tail(6).mean(),
                    "fp_allowed_season": s.mean(),
                    "trend": s.tail(3).mean() - s.mean(),
                })
    return pd.DataFrame(rows)


@pytest.fixture
def client_with_defense():
    app_main.app.dependency_overrides[app_main.default_store] = (
        lambda: InMemoryStore(projections_frame(), defense=defense_frame())
    )
    yield TestClient(app_main.app)
    app_main.app.dependency_overrides.clear()


def test_defense_points_against(client_with_defense):
    rows = client_with_defense.get(
        "/defense/points-against", params={"season": 2025, "position": "wr"}
    ).json()
    assert len(rows) == 6  # one snapshot per team
    assert all(r["position"] == "WR" and r["week"] == 6 for r in rows)
    # Ranked toughest-first
    seasons_avg = [r["fp_allowed_season"] for r in rows]
    assert seasons_avg == sorted(seasons_avg)


def test_defense_trends(client_with_defense):
    out = client_with_defense.get(
        "/defense/trends", params={"season": 2025, "top": 3}
    ).json()
    assert set(out) == {"QB", "RB", "WR", "TE"}
    for pos in out:
        assert len(out[pos]["improving"]) == 3
        assert len(out[pos]["fading"]) == 3
        # T0's defense worsens by construction -> it should be a top fader
        assert out[pos]["fading"][0]["team"] == "T0"


def test_defense_dashboard_html(client_with_defense):
    r = client_with_defense.get("/defense")
    assert r.status_code == 200
    assert "DK points allowed per position" in r.text
    assert "vs WR" in r.text


def test_defense_endpoints_empty_store(client):
    assert client.get("/defense/points-against").status_code == 404
    assert "No defense data" in client.get("/defense").text


def test_core_lineups(client):
    req = {"season": 2025, "week": 3, "n_lineups": 4, "core_size": 6}
    r = client.post("/lineups/core", json=req)
    assert r.status_code == 200, r.text
    out = r.json()
    core_ids = {p["id"] for p in out["core"]}
    assert 3 <= len(core_ids) <= 6
    assert len(out["lineups"]) == 4
    # Every entry contains the full core; variations differ from each other
    rosters = [frozenset(p["id"] for p in lu["players"]) for lu in out["lineups"]]
    assert all(core_ids <= roster for roster in rosters)
    assert len(set(rosters)) == len(rosters)
    assert "dk_csv" in out and "exposure" in out


def test_core_lineups_respects_bans(client):
    base = client.post("/lineups/core",
                       json={"season": 2025, "week": 3, "n_lineups": 1}).json()
    banned = base["core"][0]["id"]
    r = client.post("/lineups/core",
                    json={"season": 2025, "week": 3, "n_lineups": 2,
                          "bans": [banned]})
    assert r.status_code == 200
    for lu in r.json()["lineups"]:
        assert banned not in {p["id"] for p in lu["players"]}


def test_core_lineups_auto_sizes(client):
    r = client.post("/lineups/core", json={"season": 2025, "week": 3, "n_lineups": 3})
    r = client.post("/lineups/core", json={"season": 2025, "week": 3, "n_lineups": 3})
    assert r.status_code == 200, r.text
    out = r.json()
    core = out["core"]
    assert 2 <= len(core) <= 7  # system-chosen size
    # Conviction reported and sorted strongest-first
    convictions = [c["conviction"] for c in core]
    assert all(0 < c <= 1 for c in convictions)
    assert convictions == sorted(convictions, reverse=True)
    # Budget guard: free slots keep at least mid-tier salary each
    core_salary = sum(c["salary"] for c in core)
    assert 50_000 - core_salary >= (9 - len(core)) * 4_500
    core_ids = {c["id"] for c in core}
    for lu in out["lineups"]:
        assert core_ids <= {p["id"] for p in lu["players"]}


# --- Showdown Captain Mode endpoints -----------------------------------------


def showdown_frame(frame, gid=7001, teams=("T0", "T1"),
                   game_start="2025-09-19T00:15:00Z"):
    """Showdown salary snapshot for one game, built from the projections
    frame's players on `teams` plus a K and DST per team (no projections —
    they exercise the dk_ppg fallback)."""
    sub = frame[frame.team.isin(teams)]
    rows = [{
        "draft_group_id": gid, "dk_player_id": int(r.dk_player_id),
        "dk_draftable_id": int(r.dk_player_id) + 40_000_000,
        "dk_cpt_draftable_id": int(r.dk_player_id) + 50_000_000,
        "display_name": r.display_name, "team_abbr": r.team,
        "position": r.position, "salary": int(r.salary) + 200,
        "game_start": game_start, "status": "None", "dk_ppg": None,
    } for r in sub.itertuples()]
    extra_id = 9900
    for team in teams:
        for pos, ppg in (("K", 7.5), ("DST", 6.0)):
            rows.append({
                "draft_group_id": gid, "dk_player_id": extra_id,
                "dk_draftable_id": extra_id + 40_000_000,
                "dk_cpt_draftable_id": extra_id + 50_000_000,
                "display_name": f"{pos} {team}", "team_abbr": team,
                "position": pos, "salary": 3600,
                "game_start": game_start, "status": "None", "dk_ppg": ppg,
            })
            extra_id += 1
    return pd.DataFrame(rows)


@pytest.fixture
def showdown_client():
    frame = projections_frame()
    thu = showdown_frame(frame, gid=7001, teams=("T0", "T1"),
                         game_start="2025-09-19T00:15:00Z")   # Thu 8:15pm ET
    sun = showdown_frame(frame, gid=7002, teams=("T2", "T3"),
                         game_start="2025-09-21T17:00:00Z")   # Sunday
    mon = showdown_frame(frame, gid=7003, teams=("T4", "T5"),
                         game_start="2025-09-23T00:15:00Z")   # Mon 8:15pm ET
    store = InMemoryStore(frame, showdown=pd.concat([sun, thu, mon]))
    app_main.app.dependency_overrides[app_main.default_store] = lambda: store
    yield TestClient(app_main.app)
    app_main.app.dependency_overrides.clear()


def test_showdown_slates_default_thu_mon(showdown_client):
    slates = showdown_client.get("/showdown/slates").json()
    assert [s["draft_group_id"] for s in slates] == [7001, 7003]
    assert [s["day"] for s in slates] == ["Thursday", "Monday"]
    assert slates[0]["game"] == "T0 vs T1"

    all_days = showdown_client.get("/showdown/slates",
                                   params={"days": ""}).json()
    assert {s["draft_group_id"] for s in all_days} == {7001, 7002, 7003}


def test_showdown_slates_empty_store(client):
    assert client.get("/showdown/slates").status_code == 404


def test_showdown_lineups_defaults_to_next_prime_time_game(showdown_client):
    r = showdown_client.post("/showdown/lineups", json={
        "season": 2025, "week": 3, "n_lineups": 3,
    })
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["game"]["draft_group_id"] == 7001  # Thursday comes first
    assert body["game"]["day"] == "Thursday"
    assert len(body["lineups"]) == 3
    from nfl_dfs.optimizer.showdown import cpt_salary
    for lu in body["lineups"]:
        assert len(lu["players"]) == 6
        assert lu["salary"] <= 50_000
        cpt, flex = lu["players"][0], lu["players"][1:]
        assert cpt == lu["captain"]
        assert lu["salary"] == cpt_salary(cpt["salary"]) + sum(
            p["salary"] for p in flex)
        assert {p["team"] for p in lu["players"]} == {"T0", "T1"}
    assert body["dk_csv"].startswith("CPT,FLEX,FLEX,FLEX,FLEX,FLEX")
    # Captains differ or rosters differ across the three entries
    keys = {(lu["captain"]["id"], frozenset(p["id"] for p in lu["players"]))
            for lu in body["lineups"]}
    assert len(keys) == 3
    assert all("cpt_exposure" in e for e in body["exposure"])


def test_showdown_lineups_dk_ppg_fallback_and_selection(showdown_client):
    r = showdown_client.post("/showdown/lineups", json={
        "season": 2025, "week": 3, "draft_group_id": 7003,
        "n_lineups": 1, "locks": [9900],  # K T4, projected via dk_ppg only
    })
    assert r.status_code == 200, r.text
    lu = r.json()["lineups"][0]
    kicker = next(p for p in lu["players"] if p["id"] == 9900)
    assert kicker["proj_source"] == "dk_ppg"
    assert kicker["proj"] == 7.5
    assert all(p["proj_source"] == "model"
               for p in lu["players"] if p["pos"] not in ("K", "DST"))


def test_showdown_captain_lock_and_csv_endpoint(showdown_client):
    frame = projections_frame()
    a_qb = int(frame[(frame.team == "T0") & (frame.position == "QB")]
               .dk_player_id.iloc[0])
    r = showdown_client.post("/showdown/lineups", json={
        "season": 2025, "week": 3, "n_lineups": 1, "captain": a_qb,
    })
    assert r.json()["lineups"][0]["captain"]["id"] == a_qb

    csv_resp = showdown_client.post("/showdown/lineups.csv", json={
        "season": 2025, "week": 3, "n_lineups": 2,
    })
    assert csv_resp.status_code == 200
    assert csv_resp.headers["content-type"].startswith("text/csv")
    assert csv_resp.text.startswith("CPT,FLEX")


def test_showdown_unknown_group_404(showdown_client):
    r = showdown_client.post("/showdown/lineups", json={
        "season": 2025, "week": 3, "draft_group_id": 1234,
    })
    assert r.status_code == 404


# --- Classic slate selection --------------------------------------------------


def classic_frame(frame, gid, kickoffs, id_base):
    """Classic salary snapshot for one draft group. `kickoffs` maps team ->
    game_start; only those teams' players are in the group. Slate salaries
    run $100 over the projection frame's to prove the override."""
    sub = frame[frame.team.isin(kickoffs)]
    return pd.DataFrame([{
        "draft_group_id": gid, "dk_player_id": int(r.dk_player_id),
        "dk_draftable_id": int(r.dk_player_id) + id_base,
        "display_name": r.display_name, "team_abbr": r.team,
        "position": r.position, "salary": int(r.salary) + 100,
        "game_start": kickoffs[r.team], "status": "None",
    } for r in sub.itertuples()])


SUN_EARLY = "2025-09-21T17:00:00Z"   # Sun 1:00 PM ET
SUN_LATE = "2025-09-21T20:25:00Z"    # Sun 4:25 PM ET
THU_NIGHT = "2025-09-19T00:15:00Z"   # Thu 8:15 PM ET


@pytest.fixture
def classic_client():
    """Two classic slates over the 6-team projections frame: the Sunday
    main (T2-T5) and a Thu-Sun full slate (all teams)."""
    frame = projections_frame()
    main = classic_frame(frame, gid=8200, id_base=60_000_000, kickoffs={
        "T2": SUN_EARLY, "T3": SUN_EARLY, "T4": SUN_LATE, "T5": SUN_LATE})
    full = classic_frame(frame, gid=8100, id_base=70_000_000, kickoffs={
        "T0": THU_NIGHT, "T1": THU_NIGHT,
        "T2": SUN_EARLY, "T3": SUN_EARLY, "T4": SUN_LATE, "T5": SUN_LATE})
    store = InMemoryStore(frame, classic=pd.concat([main, full]))
    app_main.app.dependency_overrides[app_main.default_store] = lambda: store
    yield TestClient(app_main.app)
    app_main.app.dependency_overrides.clear()


def test_classic_slates_listing(classic_client):
    slates = classic_client.get("/classic/slates").json()
    assert [s["draft_group_id"] for s in slates] == [8100, 8200]  # first kickoff
    full, main = slates
    assert full["label"] == "Thu–Sun · 3 games"
    assert full["games"] == 3 and full["players"] == 72
    assert not full["main"]
    assert main["label"] == "Sun 1:00 PM–4:25 PM · 2 games"
    assert main["games"] == 2 and main["players"] == 48
    assert main["main"]  # all-Sunday group with the most games


def test_classic_slates_empty_store(client):
    assert client.get("/classic/slates").status_code == 404


def test_lineups_restricted_to_chosen_slate(classic_client):
    r = classic_client.post("/lineups", json={
        "season": 2025, "week": 3, "n_lineups": 2, "draft_group_id": 8200,
        "sim": False,
    })
    assert r.status_code == 200, r.text
    body = r.json()
    frame = projections_frame()
    salary_by_id = frame.set_index("dk_player_id").salary.to_dict()
    for lu in body["lineups"]:
        for p in lu["players"]:
            # Pool is the slate's teams only, at the slate's salaries
            assert p["team"] in {"T2", "T3", "T4", "T5"}
            assert p["salary"] == salary_by_id[p["id"]] + 100
    # Upload CSV carries the chosen slate's draftable IDs
    row = body["dk_csv"].strip().splitlines()[1]
    for p in body["lineups"][0]["players"]:
        assert f"({p['id'] + 60_000_000})" in row


def test_lineups_full_slate_keeps_all_teams_available(classic_client):
    frame = projections_frame()
    a_thu_wr = int(frame[(frame.team == "T0") & (frame.position == "WR")]
                   .dk_player_id.iloc[0])
    r = classic_client.post("/lineups", json={
        "season": 2025, "week": 3, "n_lineups": 1,
        "draft_group_id": 8100, "locks": [a_thu_wr],
        "sim": False,
    })
    assert r.status_code == 200, r.text
    lu = r.json()["lineups"][0]
    assert a_thu_wr in {p["id"] for p in lu["players"]}
    row = r.json()["dk_csv"].strip().splitlines()[1]
    assert f"({a_thu_wr + 70_000_000})" in row


def test_lineups_unknown_slate_404(classic_client):
    r = classic_client.post("/lineups", json={
        "season": 2025, "week": 3, "draft_group_id": 4321,
        "sim": False,
    })
    assert r.status_code == 404
    assert "/classic/slates" in r.json()["detail"]


def test_core_lineups_respect_slate(classic_client):
    r = classic_client.post("/lineups/core", json={
        "season": 2025, "week": 3, "n_lineups": 2, "draft_group_id": 8200,
        "sim": False,
    })
    assert r.status_code == 200, r.text
    out = r.json()
    slate_teams = {"T2", "T3", "T4", "T5"}
    assert {c["team"] for c in out["core"]} <= slate_teams
    for lu in out["lineups"]:
        assert {p["team"] for p in lu["players"]} <= slate_teams


def test_slate_label_single_kickoff():
    starts = pd.Series(["2025-09-22T00:20:00Z"])  # Sun 8:20 PM ET
    assert app_main._slate_label(starts, 1) == "Sun 8:20 PM · 1 game"


# --- DK import files: draftable IDs and DKEntries filling --------------------


@pytest.fixture
def draftable_client():
    """Classic store with a draftable-ID mapping from the latest DK pull."""
    frame = projections_frame()
    draftables = pd.DataFrame({
        "dk_player_id": frame.dk_player_id,
        "dk_draftable_id": frame.dk_player_id + 40_000_000,
    })
    store = InMemoryStore(frame, draftables=draftables)
    app_main.app.dependency_overrides[app_main.default_store] = lambda: store
    yield TestClient(app_main.app)
    app_main.app.dependency_overrides.clear()


def test_classic_csv_uses_draftable_ids(draftable_client):
    r = draftable_client.post("/lineups", json={
        "season": 2025, "week": 3, "n_lineups": 1, "sim": False,
    })
    body = r.json()
    row = body["dk_csv"].strip().splitlines()[1]
    for p in body["lineups"][0]["players"]:
        assert f"({p['id'] + 40_000_000})" in row
        assert f"({p['id']})" not in row


def test_classic_csv_falls_back_to_player_ids(client):
    """No draftable mapping in the store (e.g. pre-migration rows): the
    CSV still renders, carrying player IDs."""
    r = client.post("/lineups", json={"season": 2025, "week": 3,
                                      "n_lineups": 1, "sim": False})
    row = r.json()["dk_csv"].strip().splitlines()[1]
    ids = [p["id"] for p in r.json()["lineups"][0]["players"]]
    assert all(f"({pid})" in row for pid in ids)


def test_showdown_csv_uses_cpt_draftable_id(showdown_client):
    r = showdown_client.post("/showdown/lineups", json={
        "season": 2025, "week": 3, "n_lineups": 1,
    })
    body = r.json()
    row = body["dk_csv"].strip().splitlines()[1].split(",")
    cpt = body["lineups"][0]["captain"]
    assert row[0] == f"{cpt['name']} ({cpt['id'] + 50_000_000})"
    for cell, p in zip(row[1:], body["lineups"][0]["players"][1:]):
        assert cell == f"{p['name']} ({p['id'] + 40_000_000})"


CLASSIC_ENTRIES = (
    "Entry ID,Contest Name,Contest ID,Entry Fee,"
    "QB,RB,RB,WR,WR,WR,TE,FLEX,DST,,Instructions\n"
    "4111111,NFL $100K Flea Flicker,987,$5,,,,,,,,,,,Fill in your entries\n"
    "4111112,NFL $100K Flea Flicker,987,$5\n"
)


def test_fill_classic_entries_endpoint(draftable_client):
    r = draftable_client.post("/lineups/entries.csv", json={
        "season": 2025, "week": 3, "entries_csv": CLASSIC_ENTRIES,
        "sim": False,
    })
    assert r.status_code == 200, r.text
    assert r.headers["content-type"].startswith("text/csv")
    lines = r.text.strip().splitlines()
    assert lines[1].startswith("4111111,NFL $100K Flea Flicker,987,$5,")
    assert "(4" in lines[1] and "Fill in your entries" in lines[1]
    assert lines[2].startswith("4111112,")
    # One distinct lineup per entry row
    assert lines[1].split(",")[4:13] != lines[2].split(",")[4:13]


def test_fill_showdown_entries_endpoint(showdown_client):
    entries = (
        "Entry ID,Contest Name,Contest ID,Entry Fee,"
        "CPT,FLEX,FLEX,FLEX,FLEX,FLEX\n"
        "4222221,T0 vs T1 Showdown,55,$1\n"
    )
    r = showdown_client.post("/showdown/lineups/entries.csv", json={
        "season": 2025, "week": 3, "entries_csv": entries,
    })
    assert r.status_code == 200, r.text
    filled = r.text.strip().splitlines()[1].split(",")
    assert filled[0] == "4222221"
    assert all(cell.endswith(")") for cell in filled[4:10])


def test_fill_entries_rejects_mismatched_file(showdown_client):
    r = showdown_client.post("/showdown/lineups/entries.csv", json={
        "season": 2025, "week": 3, "entries_csv": CLASSIC_ENTRIES,
    })
    assert r.status_code == 422
    assert "mismatch" in r.json()["detail"]

    r = showdown_client.post("/showdown/lineups/entries.csv", json={
        "season": 2025, "week": 3, "entries_csv": "not,a,dk,file\n1,2,3,4\n",
    })
    assert r.status_code == 422


def test_lineups_view_page(client):
    r = client.get("/lineups/view")
    assert r.status_code == 200
    assert "Lineup builder" in r.text
    assert "DK CSV" in r.text
    # Slate dropdown offers both formats and the JS hits both builders
    assert "Classic slates" in r.text
    assert "Showdown (Captain Mode)" in r.text
    assert "/showdown/lineups" in r.text
    assert "/showdown/slates?days=" in r.text
    assert "/lineups/record" in r.text
    assert "CSV always downloads that exact preview" in r.text
    assert "setModeControls" in r.text


def test_showdown_any_game_selectable(showdown_client):
    """The UI dropdown lists every upcoming showdown game (days unfiltered),
    so a Sunday game must build once its draft group is named."""
    r = showdown_client.post("/showdown/lineups", json={
        "season": 2025, "week": 3, "draft_group_id": 7002, "n_lineups": 1,
    })
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["game"]["draft_group_id"] == 7002
    assert body["game"]["game"] == "T2 vs T3"
    assert {p["team"] for p in body["lineups"][0]["players"]} == {"T2", "T3"}


def test_season_dashboard_home(client):
    r = client.get("/")
    assert r.status_code == 200
    assert "Season tracker" in r.text


def test_swap_blocks_duplicates(client, monkeypatch):
    from nfl_dfs import notes as n

    monkeypatch.setattr(n, "entered_rosters", lambda s, w: {
        0: {"a qb", "b rb", "c wr"}, 1: {"a qb", "b rb", "d wr"}})
    monkeypatch.setattr(n, "swap_entered_player",
                        lambda *a, **k: (_ for _ in ()).throw(
                            AssertionError("must not swap")))
    # store fixture has projections for 2025 wk3; pick any real name from it
    import nfl_dfs.app.main as m
    df = m.get_store().projections(2025, 3)
    name = df.display_name.iloc[0]
    monkeypatch.setattr(n, "norm_name", lambda s: {
        name.lower(): "d wr"}.get(str(s).lower(), str(s).lower()))
    r = client.post("/entries/swap", json={
        "season": 2025, "week": 3, "lineup_ix": 0,
        "out_name": "c wr", "in_name": name})
    assert r.status_code == 409
    assert "identical" in r.json()["detail"]


def test_exports_listing_and_slate_delete(client, monkeypatch):
    from nfl_dfs import notes as n

    monkeypatch.setattr(n, "list_entered_sets", lambda s: pd.DataFrame([
        {"week": 3, "lineups": 40, "players": 360,
         "recorded_at": "2025-09-21 15:00:00+00"}]))
    r = client.get("/results/exports", params={"season": 2025})
    assert r.status_code == 200
    assert r.json() == [{"week": 3, "lineups": 40, "players": 360,
                         "recorded_at": "2025-09-21 15:00:00+00"}]

    deleted = {}

    def fake_delete(season, week):
        deleted["args"] = (season, week)
        return 27

    monkeypatch.setattr(n, "delete_entered_lineups", fake_delete)
    r = client.delete("/results/lineups",
                      params={"season": 2025, "week": 3})
    assert r.status_code == 200
    assert r.json() == {"deleted": 27}
    assert deleted["args"] == (2025, 3)


def test_season_dashboard_offers_slate_delete(client):
    r = client.get("/")
    assert r.status_code == 200
    assert "Delete recorded slate" in r.text
    assert "/results/exports" in r.text


def test_showdown_pool_trailing_fallback_order():
    """K/DST fallback: model proj > trailing actuals > dk_ppg (issue #10)."""
    import pandas as pd

    game = pd.DataFrame([
        {"dk_player_id": 1, "display_name": "Model QB", "position": "QB",
         "team_abbr": "AAA", "draft_group_id": 9, "salary": 9000,
         "dk_ppg": 20.0, "dk_draftable_id": 11, "dk_cpt_draftable_id": 12},
        {"dk_player_id": 2, "display_name": "Some Kicker", "position": "K",
         "team_abbr": "AAA", "draft_group_id": 9, "salary": 4000,
         "dk_ppg": 6.0, "dk_draftable_id": 13, "dk_cpt_draftable_id": 14},
        {"dk_player_id": 3, "display_name": "BBB DST", "position": "DST",
         "team_abbr": "BBB", "draft_group_id": 9, "salary": 3500,
         "dk_ppg": 5.0, "dk_draftable_id": 15, "dk_cpt_draftable_id": 16},
    ])
    proj = pd.DataFrame([{"dk_player_id": 1, "proj_points": 18.5,
                          "proj_p50": 17.0, "proj_p90": 26.0, "proj_std": 6.0}])
    trailing = pd.DataFrame([
        {"kind": "K", "key": "SOME KICKER", "trailing_pts": 8.4},
        {"kind": "DST", "key": "BBB", "trailing_pts": 9.1},
    ])
    pool = app_main._showdown_pool(game, proj, "proj_points", trailing=trailing)
    by_id = {p["id"]: p for p in pool}
    assert by_id[1]["proj_source"] == "model" and by_id[1]["proj"] == 18.5
    assert by_id[2]["proj_source"] == "trailing" and by_id[2]["proj"] == 8.4
    assert by_id[3]["proj_source"] == "trailing" and by_id[3]["proj"] == 9.1

    # without trailing data, dk_ppg still catches them
    pool2 = app_main._showdown_pool(game, proj, "proj_points", trailing=None)
    by_id2 = {p["id"]: p for p in pool2}
    assert by_id2[2]["proj_source"] == "dk_ppg"


def test_market_page_and_endpoints(monkeypatch):
    """Market page renders; endpoints degrade gracefully with no data."""
    import pandas as pd

    monkeypatch.setattr("nfl_dfs.bq.query_df", lambda sql, **k: pd.DataFrame())
    client = TestClient(app_main.app)
    r = client.get("/market")
    assert r.status_code == 200 and "Line movement" in r.text
    r2 = client.get("/api/line-movement")
    assert r2.status_code == 200 and r2.json() == []
    r3 = client.get("/api/market-disagreement?season=2025&week=1")
    assert r3.status_code == 200 and r3.json() == []


def test_sim_mode_is_mandatory(client, monkeypatch):
    # No silent fallback (user decision 2026-08-03): a sim failure must
    # surface a clear 503 naming the cause; sim=false is the explicit
    # escape hatch and must serve MILP lineups without touching sim.
    called = {}

    def boom(*a, **k):
        called["sim"] = True
        raise RuntimeError("no models offline")

    from nfl_dfs.inference import live_lineups

    monkeypatch.setattr(live_lineups, "build_sim_lineups", boom)
    r = client.post("/lineups", json={"season": 2025, "week": 3,
                                      "n_lineups": 2})
    assert r.status_code == 503
    assert "RuntimeError" in r.json()["detail"]
    assert "sim=false" in r.json()["detail"]
    assert called.get("sim") is True

    called.clear()
    r = client.post("/lineups", json={"season": 2025, "week": 3,
                                      "n_lineups": 2, "sim": False})
    assert r.status_code == 200 and len(r.json()["lineups"]) == 2
    assert called == {}


def test_sim_mode_receives_locks_and_bans(client, monkeypatch):
    seen = {}

    def capture(*a, **k):
        seen.update(k)
        raise RuntimeError("stop here")

    from nfl_dfs.inference import live_lineups

    monkeypatch.setattr(live_lineups, "build_sim_lineups", capture)
    client.post("/lineups", json={"season": 2025, "week": 3,
                                  "n_lineups": 2,
                                  "locks": [11], "bans": [22]})
    assert seen.get("locks") == {11} and seen.get("bans") == {22}


def test_sim_mode_receives_selected_slate_salary_snapshot(classic_client,
                                                           monkeypatch):
    """The live sim must optimize on the selected group's prices, not the
    feature query's largest-group price for an overlapping player."""
    seen = {}

    def capture(*a, **k):
        seen.update(k)
        raise RuntimeError("stop here")

    from nfl_dfs.inference import live_lineups

    monkeypatch.setattr(live_lineups, "build_sim_lineups", capture)
    r = classic_client.post("/lineups", json={
        "season": 2025, "week": 3, "n_lineups": 2,
        "draft_group_id": 8200,
    })
    assert r.status_code == 503
    frame = projections_frame()
    expected = {int(p.dk_player_id): int(p.salary) + 100
                for p in frame[frame.team.isin({"T2", "T3", "T4", "T5"})]
                .itertuples()}
    assert seen["allowed_ids"] == set(expected)
    assert seen["salary_overrides"] == expected


def test_sim_mode_notes_toggle_passthrough(client, monkeypatch):
    """apply_notes reaches the sim path; default True, UI-off -> False
    (pure algorithm, no watch-note boosts/bans)."""
    seen = {}

    def capture(*a, **k):
        seen.update(k)
        raise RuntimeError("stop here")

    from nfl_dfs.inference import live_lineups

    monkeypatch.setattr(live_lineups, "build_sim_lineups", capture)
    client.post("/lineups", json={"season": 2025, "week": 3, "n_lineups": 2})
    assert seen.get("apply_notes") is True
    seen.clear()
    client.post("/lineups", json={"season": 2025, "week": 3, "n_lineups": 2,
                                  "apply_notes": False})
    assert seen.get("apply_notes") is False


def test_sim_mode_receives_immutable_adopted_policy(client, monkeypatch):
    seen = {}

    def capture(*a, **k):
        seen.update(k)
        raise RuntimeError("stop here")

    from nfl_dfs.inference import live_lineups

    monkeypatch.setattr(live_lineups, "build_sim_lineups", capture)
    client.post("/lineups", json={"season": 2025, "week": 3})
    assert seen["n_entries"] == 80
    assert seen["model_variant"] == "tail_k1"
    assert seen["belief_model_variant"] == "tail_k1_role"
    assert seen["expected_model_k"] == 1
    env = seen["policy_env"]
    assert (env["N_CE"], env["N_EPISTEMIC"], env["N_BOOM"]) == (
        "12", "12", "28")
    assert env["EPISTEMIC_FAMILY"] == "role_draws"
    assert env["MIN_LINEUP_SALARY"] == "49000"
    assert env["BLEND_MODEL_WEIGHT"] == "0.45"
    assert env["SELECT_LSE"] == "0"


def test_role_registry_outage_uses_labeled_ce_fallback(client, monkeypatch):
    from nfl_dfs.inference import live_lineups
    from nfl_dfs.optimizer.lineup import optimize

    frame = projections_frame()
    lineup = optimize(app_main._player_pool(frame, "proj_points", None))
    assert lineup is not None
    lineup.model_version = "pooled/components__tail_k1/2026-W36"
    calls = []

    def build(*args, **kwargs):
        calls.append(kwargs)
        if len(calls) == 1:
            raise live_lineups.RoleBeliefUnavailable("missing role registry")
        return [lineup]

    monkeypatch.setattr(live_lineups, "build_sim_lineups", build)
    response = client.post("/lineups", json={
        "season": 2025, "week": 3, "n_lineups": 1})
    assert response.status_code == 200
    assert calls[0]["policy_env"]["N_EPISTEMIC"] == "12"
    assert calls[1]["policy_env"]["N_EPISTEMIC"] == "0"
    identity = response.json()["policy"]
    assert identity["fallback_used"] is True
    assert identity["effective_policy_id"] == "classic-k1-ce12-boom28-v1"


def test_all_three_classic_routes_expose_same_policy(client, monkeypatch):
    from nfl_dfs.optimizer.lineup import optimize

    frame = projections_frame()
    pool = app_main._player_pool(frame, "proj_points", None)
    lu = optimize(pool)
    assert lu is not None
    lu.model_version = "pooled/components__tail_k1/2026-W36"
    ranked = [{"lineup": lu, "confidence": 1.0,
               "proj_mean": round(lu.proj, 1)}]
    monkeypatch.setattr(app_main, "_build_classic",
                        lambda req, store: ([lu], ranked))
    monkeypatch.setattr("nfl_dfs.notes.record_entered_lineups",
                        lambda *a, **k: 1)

    req = {"season": 2025, "week": 3, "n_lineups": 1}
    preview = client.post("/lineups", json=req)
    generic = client.post("/lineups.csv", json=req)
    one_entry = CLASSIC_ENTRIES.splitlines()[0] + "\n" + \
        CLASSIC_ENTRIES.splitlines()[1] + "\n"
    entries = client.post("/lineups/entries.csv", json={
        **req, "entries_csv": one_entry})

    policy_id = "classic-k1-ce12-role12-boom28-v2"
    assert preview.json()["policy"]["policy_id"] == policy_id
    assert preview.json()["policy"]["model_ensemble"] == 1
    assert preview.json()["policy"]["portfolio_allocation"] == {
        "ce": 12, "role": 12, "boom": 28,
        "total_generation_solves": 52}
    for response in (generic, entries):
        assert response.status_code == 200
        assert response.headers["x-lineup-policy"] == policy_id
        assert response.headers["x-model-version"].endswith("2026-W36")


def test_record_preview_lineups_records_exact_client_roster(client, monkeypatch):
    """CSV recording accepts the already-reviewed `/lineups` payload; it
    must not call the optimizer a second time."""
    saved = {}

    from nfl_dfs import notes

    def capture(season, week, lineups):
        saved.update(season=season, week=week, lineups=lineups)
        return len(lineups)

    monkeypatch.setattr(notes, "record_entered_lineups", capture)
    players = []
    for r in projections_frame().head(9).itertuples():
        players.append({"id": int(r.dk_player_id), "name": r.display_name,
                        "pos": r.position, "team": r.team,
                        "salary": int(r.salary), "proj": float(r.proj_points)})
    r = client.post("/lineups/record", json={
        "season": 2025, "week": 3, "lineups": [{"players": players}]})
    assert r.status_code == 200 and r.json()["recorded"] == 1
    assert saved["season"] == 2025 and saved["week"] == 3
    assert [p["id"] for p in saved["lineups"][0].players] == [p["id"] for p in players]


def test_preference_requires_projectable_player(client, monkeypatch):
    from nfl_dfs import notes

    monkeypatch.setattr(notes, "add_pref", lambda *a: "pref-1")
    # Synthetic names differ only by digits, which the production
    # normalizer deliberately removes; retain the test's intended one-name
    # case without changing real suffix-insensitive behavior.
    monkeypatch.setattr(notes, "norm_name", lambda s: str(s).lower())
    missing = client.post("/prefs", json={"season": 2025, "week": 3,
                                            "display_name": "Not A Player",
                                            "kind": "ban"})
    assert missing.status_code == 422
    good = client.post("/prefs", json={"season": 2025, "week": 3,
                                         "display_name": "WR0 T0", "kind": "boost"})
    assert good.status_code == 200
    assert good.json()["display_name"] == "WR0 T0"
