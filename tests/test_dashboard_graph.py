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
    ids = SLATE.set_index("display_name").dk_player_id
    assert {p["dk_player_id"] for p in b["players"]} == {r["dk_player_id"] for r in b["contains"]}
    assert all(isinstance(p["dk_player_id"], int) and p["name"] for p in b["players"])
    qa = next(p for p in b["players"] if p["dk_player_id"] == ids["qa"])
    assert (qa["name"], qa["team"], qa["position"]) == ("qa", "BUF", "QB")
    assert len(b["owned_in"]) == len({r["dk_player_id"] for r in b["contains"]})
    kinds = {r["kind"] for r in b["stacked_with"]}
    assert kinds == {"teammate", "opponent"}
    pair = next(r for r in b["stacked_with"] if (r["a"], r["b"]) == (ids["qa"], ids["wa1"]))
    assert pair["count"] == 2 and pair["kind"] == "teammate"
    for r in b["stacked_with"]:
        assert r["a"] < r["b"]                       # each pair stored once


def test_loaded_rows_carry_no_licensed_fields_and_names_only_on_users():
    users = set(top_rows().username)
    for name, rows in batches().items():
        for row in rows:
            assert not any(m in k.lower() for k in row for m in G.FORBIDDEN_FIELD_MARKERS), name
            assert "entry_name" not in row and "username" not in row
            if name not in ("users", "entered"):         # a user name is never a property elsewhere
                assert not users & {v for v in row.values() if isinstance(v, str)}, name


def test_user_names_survive_the_loader():
    b = batches()
    assert b["users"] == [{"name": "user_a"}, {"name": "user_b"}]
    assert sorted((r["lineup_key"], r["name"]) for r in b["entered"]) == [
        ("k1", "user_a"), ("k2", "user_b"), ("k3", "user_a")]
    drv = FakeDriver()
    sent = G.apply_batches(drv, "neo4j", b)
    assert sent["users"] == 2 and sent["entered"] == 3
    writes = [(q, p) for q, p, _ in drv.calls if p]
    order = [next(k for k, s in G.STATEMENTS.items() if s == q) for q, _ in writes]
    assert order.index("users") < order.index("entered") and order.index("lineups") < order.index("entered")
    entered = next(p["rows"] for q, p in writes if q == G.STATEMENTS["entered"])
    assert {r["name"] for r in entered} == {"user_a", "user_b"}
    assert "MERGE (u:User {name: row.name})" in G.STATEMENTS["users"]
    assert "MERGE (u)-[:ENTERED]->(l)" in G.STATEMENTS["entered"]


def test_blank_or_missing_user_names_are_not_loaded():
    top = top_rows()
    top.loc[0, "username"] = None
    top.loc[1, "username"] = "  "
    b = G.build_graph_batches(contests(), lines(), top, SLATE, GAMES, OWN)
    assert b["users"] == [{"name": "user_a"}] and [r["lineup_key"] for r in b["entered"]] == ["k3"]
    b = G.build_graph_batches(contests(), lines(), top_rows().drop(columns="username"), SLATE, GAMES, OWN)
    assert b["users"] == [] and b["entered"] == [] and len(b["lineups"]) == 3


def test_repeat_finishers_panel():
    class Rec(dict):
        def data(self):
            return dict(self)
    keys = ["user", "top_1pct_weeks", "top_1pct_lineups", "best_rank", "loaded"]
    drv = FakeDriver({"MATCH (u:User)-[:ENTERED]->(l:Lineup)": (
        [Rec(user="user_a", top_1pct_weeks=1, top_1pct_lineups=2, best_rank=1, loaded=2)], keys)})
    out = G.run_panel(drv, "neo4j")
    assert out["repeat_finishers"].iloc[0].user == "user_a"
    assert list(out["repeat_finishers"].columns) == keys


def test_saved_cypher_file_is_in_step_with_the_module():
    from pathlib import Path
    text = (Path(__file__).resolve().parents[1] / "cypher" / "milly_insights.cypher").read_text()
    norm = lambda q: " ".join(q.split())  # noqa: E731
    saved = norm(text)
    for name, q in {**G.PANEL_QUERIES, **G.INSIGHT_QUERIES}.items():
        assert norm(q) + ";" in saved, name


def test_browser_queries_are_saved_and_never_run_by_the_panel():
    """The parameterised Browser queries (operator 10-06, --users-file portfolios) are in the saved file and are not
    part of run_panel (which passes no parameters)."""
    from pathlib import Path
    text = " ".join((Path(__file__).resolve().parents[1] / "cypher" / "milly_insights.cypher").read_text().split())
    for name, q in G.BROWSER_QUERIES.items():
        assert " ".join(q.split()) + ";" in text, name
        assert "$user" in q and "$week_key" in q, name
    assert not set(G.BROWSER_QUERIES) & (set(G.PANEL_QUERIES) | set(G.INSIGHT_QUERIES))


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
    assert schema == list(G.load_schema())
    first_write = next(i for i, (_, p, _) in enumerate(drv.calls) if p)
    assert all(q.startswith("CREATE CONSTRAINT") for q, _, _ in drv.calls[:len(schema)])
    assert first_write == len(schema)                  # constraints before the first batch
    writes = [(q, p) for q, p, _ in drv.calls if p]
    assert sum(len(p["rows"]) for q, p in writes if "CONTAINS {slot" in q) == 27
    assert max(len(p["rows"]) for _, p in writes) <= 10
    for q, _ in writes:                                # idempotent: MERGE, never CREATE
        assert "MERGE" in q and not re.search(r"(?<!ON )\bCREATE\b", q)
    order = [next(k for k, s in G.STATEMENTS.items() if s == q) for q, _ in writes]
    assert order.index("players") < order.index("contains") < order.index("stacked_with")


def test_fp_rows_are_opt_in():
    b = batches()
    fp_proj = pd.DataFrame({"week": [5, 5], "name": ["qa", "qa"], "team": ["BUF", "KC"],
                            "fantasy_points": [21.0, 9.0]})
    fp_own = pd.DataFrame({"week": [5], "name": ["qa"], "team": ["BUF"], "projected_ownership_pct": [18.0]})
    rows = G.fp_batch(b["players"], fp_proj, fp_own, 2026)
    assert rows == [{"dk_player_id": 1001, "week_key": "2026-05", "fp_proj": 21.0, "fp_own": 18.0}]
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


class CountingDriver(FakeDriver):
    def __init__(self, nodes: int, rels: int):
        super().__init__()
        self.nodes, self.rels = nodes, rels

    def execute_query(self, query, parameters=None, database_=None, **kw):
        self.calls.append((query, parameters, database_))
        if query.startswith("MATCH (n) RETURN count(n)"):
            return [{"n": self.nodes}], None, ["n"]
        if query.startswith("MATCH ()-[r]->() RETURN count(r)"):
            return [{"n": self.rels}], None, ["n"]
        if parameters and "rows" in parameters:
            self.rels += len(parameters["rows"])
        return [], None, []


def test_estimate_additions_is_an_upper_bound():
    b = batches()
    nodes, rels = G.estimate_additions(b)
    assert nodes == 1 + 1 + 2 + 4 + len(b["players"]) + 3 + 2          # + 2 users
    assert rels >= len(b["contains"]) + len(b["lineups"]) + len(b["stacked_with"]) + len(b["entered"])
    assert G.estimate_additions({**b, "entered": []})[1] == rels - 3


def test_capacity_guard_refuses_past_90_percent_and_writes_nothing():
    drv = CountingDriver(nodes=179_990, rels=1_000)
    logs = []
    with pytest.raises(G.CapacityError, match="nodes"):
        G.guarded_load(drv, "neo4j", batches(), log=logs.append)
    assert not any(p for _, p, _ in drv.calls)               # no write was sent
    assert "graph before" in logs[0]
    with pytest.raises(G.CapacityError, match="relationships"):
        G.check_capacity((0, 359_990), (0, 100), rel_limit=400_000)
    G.check_capacity((0, 0), (1000, 1000))                   # ample headroom: no error


def test_guarded_load_counts_before_and_after():
    drv = CountingDriver(nodes=10, rels=20)
    logs = []
    res = G.guarded_load(drv, "neo4j", batches(), log=logs.append)
    assert res["before"] == (10, 20) and res["after"][1] > 20
    assert any("graph after" in line for line in logs)


def test_keepalive_reads_once_and_reports_failure():
    import importlib.util
    from pathlib import Path
    path = Path(__file__).resolve().parents[1] / "scripts" / "neo4j_keepalive.py"
    spec = importlib.util.spec_from_file_location("neo4j_keepalive", path)
    ka = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(ka)
    env = {G.URI_ENV: "neo4j+s://example.invalid", G.USERNAME_ENV: "u", G.PASSWORD_ENV: "p"}
    drv = FakeDriver({"RETURN 1": ([{"ok": 1}], ["ok"])})
    assert ka.main(env, connect=lambda cfg: drv) == 0
    assert [q for q, _, _ in drv.calls] == ["RETURN 1 AS ok"] and drv.closed

    def boom(cfg):
        raise OSError("connection refused")
    assert ka.main(env, connect=boom) == 1
    assert ka.main({}, connect=boom) == 2


def test_schema_covers_every_merged_label_and_key():
    schema = G.load_schema()
    for label, key in G.MERGED_KEYS.items():
        assert any(f"FOR (n:{label}) REQUIRE n.{key} IS UNIQUE" in st for st in schema), label
    merged = set()
    for q in G.STATEMENTS.values():
        merged |= set(re.findall(r"MERGE \((?:\w+):(\w+) \{(\w+):", q))
    assert merged <= set(G.MERGED_KEYS.items())
    assert ("Player", "dk_player_id") in merged          # never the display name


def test_collisions_are_reported_and_not_loaded():
    slate = pd.concat([SLATE, pd.DataFrame([
        {"display_name": "Twin Name", "team": "BUF", "position": "WR", "salary": 4000, "season": 2026,
         "week": 5, "contest_id": "c1", "dk_player_id": 2001},
        {"display_name": "Twin Name", "team": "KC", "position": "WR", "salary": 3900, "season": 2026,
         "week": 5, "contest_id": "c1", "dk_player_id": 2002}])], ignore_index=True)
    top = top_rows()
    top.loc[0, "lineup_slots_json"] = top.loc[0, "lineup_slots_json"].replace('"wb1"', '"Twin Name"')
    rep = G.resolution_report(top, slate)
    assert rep["unresolved_slots"] == 1 and rep["unresolved_names"] == ["Twin Name"]
    assert sorted(rep["collisions"].dk_player_id) == [2001, 2002]
    b = G.build_graph_batches(contests(), lines(), top, slate, GAMES, OWN)
    ids = {p["dk_player_id"] for p in b["players"]}
    assert 2001 not in ids and 2002 not in ids and len(b["contains"]) == 26


def test_loaded_share_is_recorded_on_the_contest():
    b = batches()
    c = b["contests"][0]
    assert c["loaded_lineups"] == 3 and c["loaded_share"] == pytest.approx(3 / 300)
    assert G.loaded_share(top_rows()) == {"c1": (3, pytest.approx(0.01))}
    assert "c.loaded_share = row.loaded_share" in G.STATEMENTS["contests"]


def test_browser_week_key_example_matches_the_graph():
    """Reviewer R1 (10-06): the Browser example said '2026-w04' while Week keys are '2026-04', so every query following
    it would return nothing, silently."""
    from pathlib import Path
    assert G.week_key(2026, 4) == "2026-04"
    assert f"week_key => '{G.week_key(2026, 4)}'" in G.BROWSER_PARAMS
    assert G.BROWSER_PARAMS in (Path(__file__).resolve().parents[1] / "cypher" / "milly_insights.cypher").read_text()
    assert batches()["lineups"][0]["week_key"] == G.week_key(2026, 5)


def test_users_file_lineups_never_change_the_panel_figures():
    """Reviewer R2 (10-06): a listed user's lineup ranked between top_n and 1% of the field must not count as a top-1%
    lineup, in STACKED_WITH or in the loaded share; it is loaded with source 'users_file' and its rank fact kept."""
    top = top_rows().assign(n_entries=1000)                      # 1% of 1,000 = rank 10; the top set is ranks 1-3
    extra = top.iloc[[1]].assign(lineup_key="k7", rank=7, points=200.0, username="user_c")
    only = G.build_graph_batches(contests(), lines(), top.assign(source="top"), SLATE, GAMES, OWN)
    both = G.build_graph_batches(contests(), lines(),
                                 pd.concat([top.assign(source="top"), extra.assign(source="users_file")], ignore_index=True),
                                 SLATE, GAMES, OWN)
    assert both["stacked_with"] == only["stacked_with"]
    assert both["contests"][0]["loaded_lineups"] == only["contests"][0]["loaded_lineups"] == 3
    k7 = next(r for r in both["lineups"] if r["key"] == "k7")
    assert k7["source"] == "users_file" and k7["top_1pct"] is False and k7["rank_top_1pct"] is True
    assert all(r["source"] == "top" and r["top_1pct"] for r in only["lineups"])
    assert {"name": "user_c", "lineup_key": "k7"} in both["entered"]
