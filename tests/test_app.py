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
    r = client_with_defense.get("/")
    assert r.status_code == 200
    assert "DK points allowed per position" in r.text
    assert "vs WR" in r.text


def test_defense_endpoints_empty_store(client):
    assert client.get("/defense/points-against").status_code == 404
    assert "No defense data" in client.get("/").text


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
