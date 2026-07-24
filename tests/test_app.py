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
