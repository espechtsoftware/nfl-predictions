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


def test_lineup_builder_locks_and_csv_endpoint(client):
    frame = projections_frame()
    a_wr = int(frame[frame.position == "WR"].dk_player_id.iloc[-1])
    r = client.post("/lineups", json={
        "season": 2025, "week": 3, "n_lineups": 1, "locks": [a_wr],
    })
    ids = [p["id"] for p in r.json()["lineups"][0]["players"]]
    assert a_wr in ids

    csv_resp = client.post("/lineups.csv", json={"season": 2025, "week": 3})
    assert csv_resp.status_code == 200
    assert csv_resp.headers["content-type"].startswith("text/csv")


def test_lineup_infeasible_constraints(client):
    r = client.post("/lineups", json={
        "season": 2025, "week": 3, "n_lineups": 1,
        "qb_stack_min": 3,  # only ~6 WR/TE per team projected > cap conflicts
        "bring_back_min": 2,
        "bans": list(range(1000, 1030)),
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
        "season": 2025, "week": 3, "n_lineups": 1,
    })
    body = r.json()
    row = body["dk_csv"].strip().splitlines()[1]
    for p in body["lineups"][0]["players"]:
        assert f"({p['id'] + 40_000_000})" in row
        assert f"({p['id']})" not in row


def test_classic_csv_falls_back_to_player_ids(client):
    """No draftable mapping in the store (e.g. pre-migration rows): the
    CSV still renders, carrying player IDs."""
    r = client.post("/lineups", json={"season": 2025, "week": 3, "n_lineups": 1})
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


def test_season_dashboard_home(client):
    r = client.get("/")
    assert r.status_code == 200
    assert "Season tracker" in r.text
