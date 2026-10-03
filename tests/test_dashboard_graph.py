"""Milly Neo4j loader and panel against a fake driver (no neo4j package
needed, nothing leaves the process)."""
from __future__ import annotations

import re
import sys

import pandas as pd
import pytest

from nfl_dfs.dashboard import milly_graph as G

sys.path.insert(0, __file__.rsplit("/", 1)[0])
from test_dashboard_milly import GAMES, OWN, SLATE, top_rows  # noqa: E402


class FakeDriver:
    """Records every execute_query; returns canned (records, summary, keys)."""

    def __init__(self, results: dict | None = None):
        self.calls: list[tuple[str, dict | None, str | None]] = []
        self.results = results or {}
        self.closed = False

    def execute_query(self, query, parameters=None, database_=None, **kw):
        self.calls.append((query, parameters, database_))
        for marker, (records, keys) in self.results.items():
            if marker in query:
                return records, None, keys
        return [], None, []

    def close(self):
        self.closed = True


def contests():
    return pd.DataFrame([{"season": 2026, "week": 5, "contest_id": "c1", "contest_name": "Synthetic Milly",
                          "draft_group_id": 1, "start_time": pd.Timestamp("2026-10-11T17:00Z"),
                          "field_size": 300, "n_entries": 300}])


def lines():
    return pd.DataFrame([{"season": 2026, "week": 5, "contest_id": "c1", "contest_name": "Synthetic Milly",
                          "n_entries": 300, "winning_score": 250.0, "top_01pct_line": 250.0,
                          "top_1pct_line": 240.0, "cash_line": None, "median_score": 120.0}])


def batches():
    return G.build_graph_batches(contests(), lines(), top_rows(), SLATE, GAMES, OWN)


def test_build_graph_batches_shapes():
    b = batches()
    assert set(b) == set(G.STATEMENTS)
    assert b["weeks"] == [{"key": "2026-05", "season": 2026, "week": 5}]
    assert b["contests"][0]["contest_id"] == "c1" and b["contests"][0]["winning_score"] == 250.0
    assert len(b["games"]) == 2 and {g["home"] for g in b["games"]} == {"BUF", "KC"}
    assert len(b["lineups"]) == 3 and len(b["contains"]) == 27
    win = next(r for r in b["lineups"] if r["rank"] == 1)
    assert win["stack_label"] == "QB+2+2" and win["top_1pct"] is True
    assert {p["name"] for p in b["players"]} == {r["player"] for r in b["contains"]}
    assert len(b["owned_in"]) == len({r["player"] for r in b["contains"]})
    kinds = {r["kind"] for r in b["stacked_with"]}
    assert kinds == {"teammate", "opponent"}
    pair = next(r for r in b["stacked_with"] if (r["a"], r["b"]) == ("qa", "wa1"))
    assert pair["count"] == 2 and pair["kind"] == "teammate"
    for r in b["stacked_with"]:
        assert r["a"] < r["b"]                       # each pair stored once


def test_loaded_rows_carry_no_licensed_fields_and_no_entry_names():
    for name, rows in batches().items():
        for row in rows:
            assert not any(m in k.lower() for k in row for m in G.FORBIDDEN_FIELD_MARKERS), name
            assert "entry_name" not in row and "username" not in row


def test_vendor_fields_are_refused():
    b = batches()
    b["players"][0]["fp_own"] = 12.0
    with pytest.raises(ValueError):
        G.assert_no_vendor_fields(b)
    with pytest.raises(ValueError):
        G.apply_batches(FakeDriver(), "neo4j", b)


def test_apply_batches_merges_in_order_and_chunks():
    drv = FakeDriver()
    sent = G.apply_batches(drv, "milly", batches(), chunk=10)
    assert sent["contains"] == 27
    assert all(db == "milly" for _, _, db in drv.calls)
    schema = [q for q, _, _ in drv.calls if q.startswith("CREATE CONSTRAINT")]
    assert len(schema) == len(G.SCHEMA)
    writes = [(q, p) for q, p, _ in drv.calls if p]
    assert sum(len(p["rows"]) for q, p in writes if "CONTAINS {slot" in q) == 27
    assert max(len(p["rows"]) for _, p in writes) <= 10
    for q, _ in writes:                                # idempotent: MERGE, never CREATE
        assert "MERGE" in q and not re.search(r"(?<!ON )\bCREATE\b", q)
    order = [next(k for k, s in G.STATEMENTS.items() if s == q) for q, _ in writes]
    assert order.index("players") < order.index("contains") < order.index("stacked_with")


def test_fp_rows_are_opt_in():
    b = batches()
    fp_proj = pd.DataFrame({"week": [5], "name": ["qa"], "fantasy_points": [21.0]})
    fp_own = pd.DataFrame({"week": [5], "name": ["qa"], "projected_ownership_pct": [18.0]})
    rows = G.fp_batch(b["players"], fp_proj, fp_own, 2026)
    assert rows == [{"name": "qa", "week_key": "2026-05", "fp_proj": 21.0, "fp_own": 18.0}]
    drv = FakeDriver()
    sent = G.apply_batches(drv, "neo4j", b, fp_rows=rows)
    assert sent["fp_projected"] == 1
    assert any("FP_PROJECTED" in q for q, _, _ in drv.calls)
    drv2 = FakeDriver()
    G.apply_batches(drv2, "neo4j", b)
    assert not any("FP_PROJECTED" in q for q, _, _ in drv2.calls)


def test_graph_config_from_env():
    assert G.GraphConfig.from_env({}) is None
    assert G.GraphConfig.from_env({G.URI_ENV: "neo4j+s://x", G.USERNAME_ENV: "u"}) is None
    cfg = G.GraphConfig.from_env({G.URI_ENV: "neo4j+s://x", G.USERNAME_ENV: "u", G.PASSWORD_ENV: "p"})
    assert cfg.database == "neo4j"


def test_run_panel_shapes_frames():
    class Rec(dict):
        def data(self):
            return dict(self)
    drv = FakeDriver({"STACKED_WITH]->(b:Player)\nWHERE r.kind = 'teammate'": (
        [Rec(player_a="qa", player_b="wa1", top_1pct_lineups=2, lineups=2, weeks=1)],
        ["player_a", "player_b", "top_1pct_lineups", "lineups", "weeks"])})
    out = G.run_panel(drv, "neo4j")
    assert set(G.PANEL_QUERIES) | set(G.INSIGHT_QUERIES) == set(out)
    assert out["stack_pairs"].iloc[0].player_b == "wa1"
    assert out["winning_shapes"].empty


def test_neo4j_is_imported_lazily():
    import importlib
    mod = importlib.reload(G)
    assert "neo4j" not in mod.__dict__
