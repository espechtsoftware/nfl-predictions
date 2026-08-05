"""Contest comparator (2026-08-04): curve interpolation + endpoint."""
import os

import pytest
from fastapi.testclient import TestClient

from nfl_dfs.models.entries_curve import p_reach


@pytest.fixture()
def client():
    os.environ.setdefault("APP_NO_AUTH", "1")
    from nfl_dfs.app.main import app

    with TestClient(app) as c:
        yield c


def test_p_reach_monotone_in_n_and_line():
    assert p_reach(40, 187) > p_reach(10, 187) > p_reach(2, 187)
    assert p_reach(40, 187) > p_reach(40, 194) > p_reach(40, 205)
    assert 0 < p_reach(4, 199) < 0.1
    assert p_reach(150, 180) <= 0.95


def test_endpoint_ranks_by_ev_per_dollar(client):
    r = client.post("/api/contest-compare", json={"contests": [
        {"name": "A", "entry_fee": 5, "field_size": 832000,
         "top_prize": 1000000, "n_entries": 4},
        {"name": "B", "entry_fee": 20, "field_size": 100000,
         "top_prize": 200000, "n_entries": 4}]})
    assert r.status_code == 200
    j = r.json()
    assert j["verdict"] == "A"
    evs = {c["name"]: c["ev_per_dollar"] for c in j["contests"]}
    assert evs["A"] > evs["B"]


def test_endpoint_validates(client):
    r = client.post("/api/contest-compare", json={"contests": [
        {"name": "A", "entry_fee": 5, "field_size": 832000,
         "top_prize": 1000000, "n_entries": 4}]})
    assert r.status_code == 422
