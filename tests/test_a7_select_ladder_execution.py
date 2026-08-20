from __future__ import annotations

import importlib
from hashlib import sha256
import json
from pathlib import Path
import sys
from types import SimpleNamespace

import pandas as pd
import numpy as np
import pytest

from nfl_dfs.research import a7_select_ladder as science


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
runner = importlib.import_module("run_a7_select_ladder")


def test_candidate_protocol_hash_and_phase_s_identity_are_literal():
    assert sha256((ROOT / runner.PROTOCOL_PATH).read_bytes()).hexdigest() == (
        runner.PROTOCOL_SHA256
    )
    assert runner.RUN_ID == "20260820-a7-select-ladder-phase-s-incumbent-v1"
    assert runner.FROZEN_CHOICES["simulation_law"] == (
        "phase-s-finite-k-plus-sis-asoe"
    )


def _identity(season: int, week: int, index: int) -> list[str]:
    return [f"{season}-{week}-{index}-p{slot}" for slot in range(9)]


def _row(season: int, week: int) -> dict:
    control = [_identity(season, week, index) for index in range(80)]
    treatment = list(reversed(control))
    scorefree = {
        "selection_order_sha256": "1" * 64,
        "total_ladder_utility": 100,
        "ladder_utility_by_block": [20] * 5,
        "realism": {
            quantile: {
                "utility_by_extreme_player_count": [90, 0, 0, 10, 0, 0, 0, 0, 0, 0],
                "utility_by_extreme_player_count_by_block": [
                    [18, 0, 0, 2, 0, 0, 0, 0, 0, 0] for _ in range(5)
                ],
                "positive_gain_events_by_extreme_player_count_by_block": [
                    [18, 0, 0, 2, 0, 0, 0, 0, 0, 0] for _ in range(5)
                ],
            }
            for quantile in ("0.99", "0.995")
        },
    }
    return {
        "season": season,
        "week": week,
        "uses_realized_outcomes": False,
        "candidate_budget": 80,
        "world_count": 50_000,
        "candidate_identities": control,
        "candidate_identities_sha256": "0" * 64,
        "candidate_tags_sha256": "5" * 64,
        "combined_input_receipts": {
            "candidate_totals": {"dtype": "<f4", "shape": [80, 50_000],
                                 "sha256": "2" * 64},
            "player_draws": {"dtype": "<f4", "shape": [9, 50_000],
                             "sha256": "3" * 64},
            "player_ids_sha256": "4" * 64,
        },
        "candidate_pool_shared_across_arms": True,
        "control_source_reproduced": True,
        "control": {"identities": control, "scorefree": scorefree},
        "treatment": {"identities": treatment, "scorefree": scorefree},
    }


def _patch_sources(
    monkeypatch, *, scorefree_passes: bool = True,
    mechanics_passes: bool = True, realism_supported: bool = True,
    realism_noninferior: bool = True,
):
    slates = [(season, week) for season in (2023, 2024, 2025)
              for week in range(1, 19)]
    expected = {(season, week): {"season": season, "week": week}
                for season, week in slates}
    artifacts = [
        {
            "panel_run_id": panel, "season": season, "week": week,
            "uri": f"gs://bucket/{panel}/{season}-{week}",
            "sha256": "9" * 64, "source_rows": 80,
            "generation": "1", "bytes": 1,
        }
        for season, week in slates for panel in runner.SOURCE_PANEL_IDS
    ]
    artifact_map = {
        (row["panel_run_id"], row["season"], row["week"]): row
        for row in artifacts
    }
    queries = []
    source = pd.DataFrame([{
        "panel_run_id": row["panel_run_id"],
        "season": row["season"], "week": row["week"], "cand_ix": 0,
        "tag": "lev", "all_tags": ["lev"],
        "players": ",".join(f"p{index}" for index in range(9)),
        "score_artifact_uri": row["uri"],
        "score_artifact_sha256": row["sha256"],
    } for row in artifacts], columns=runner.SOURCE_QUERY_COLUMNS)
    players = pd.DataFrame([{
        "manifest_sha256": runner.FORENSIC_MANIFEST_SHA256,
        "season": 2023, "week": 1, "player_id": "p0",
        "player_name": "Player", "position": "QB", "team": "A",
        "opponent": "B", "game_id": "g", "salary": 5000,
        "mean_projection": 20.0,
    }], columns=runner.PLAYER_QUERY_COLUMNS)
    actuals = source[[
        "panel_run_id", "season", "week", "cand_ix", "players",
    ]].copy()
    actuals["actual_score"] = 200.0
    actuals = actuals[list(runner.ACTUAL_QUERY_COLUMNS)]

    monkeypatch.setattr(runner, "verify_local_sha256", lambda value: {
        key: {"sha256": digest} for key, (_, digest) in value.items()
    })
    monkeypatch.setattr(runner, "validate_scorefree_queries", lambda: None)
    monkeypatch.setattr(runner, "_validate_smoke_source_identity", lambda value: None)
    monkeypatch.setattr(
        runner, "_source_report", lambda: (expected, artifact_map, {}),
    )
    monkeypatch.setattr(runner, "_validate_baseline", lambda value: (
        176.06, {"187": 17, "194": 8, "200": 7, "210": 6,
                 "220": 3, "230": 1, "240": 0},
    ))
    monkeypatch.setattr(runner.bigquery, "Client", lambda project: object())
    monkeypatch.setattr(runner.storage, "Client", lambda project: object())

    def query(client, sql, params=None):
        queries.append(sql)
        if sql == runner.SOURCE_SQL:
            return source
        if sql == runner.PLAYER_SQL:
            return players
        return actuals

    monkeypatch.setattr(runner, "_query", query)
    monkeypatch.setattr(runner, "resolve_panel_artifacts", lambda *args, **kwargs: {
        "panel_ids": list(runner.SOURCE_PANEL_IDS),
        "slates": [list(value) for value in slates],
        "slate_count": 54,
        "artifact_count": 270,
        "artifacts": [
            {key: row[key] for key in (
                "panel_run_id", "season", "week", "uri", "sha256", "source_rows",
            )}
            for row in artifacts
        ],
    })
    monkeypatch.setattr(runner, "_prepare_slate", lambda **kwargs: (
        _row(int(kwargs["season"]), int(kwargs["week"])),
        [{
            "panel_run_id": panel, "season": int(kwargs["season"]),
            "week": int(kwargs["week"]),
            "uri": f"gs://bucket/{panel}/{kwargs['season']}-{kwargs['week']}",
            "sha256": "9" * 64, "generation": "1", "bytes": 1,
            "candidate_rows": 80, "metageneration": "1",
            "md5_hash": "", "crc32c": "", "seed": index,
        } for index, panel in enumerate(runner.SOURCE_PANEL_IDS)],
    ))
    monkeypatch.setattr(runner, "aggregate_scorefree", lambda rows: {
        "passes": scorefree_passes,
        "mechanics_passes": mechanics_passes,
        "uses_realized_outcomes": False,
        "conditions": {
            "realism_r3_supported": realism_supported,
            "realism_r3_noninferior": realism_noninferior,
        },
    })
    support = {
        "version": "a7-r3-support-census-v1", "passes": realism_supported,
        "uses_realized_outcomes": False,
    }
    monkeypatch.setattr(runner, "build_support_census", lambda rows: support)
    query_receipts = {
        "candidate_source": runner._query_content_receipt(
            source, runner.SOURCE_QUERY_COLUMNS,
        ),
        "player_source": runner._query_content_receipt(
            players, runner.PLAYER_QUERY_COLUMNS,
        ),
    }
    monkeypatch.setattr(runner, "_preflight_receipt", lambda report: "frozen-support")
    monkeypatch.setattr(runner, "_load_freeze_evidence", lambda *args, **kwargs: {
        "manifest": {
            "query_content_receipts": query_receipts,
            "image": {"uri": "registry.invalid/image@sha256:" + "b" * 64},
            "implementation_sha256": {"finisher": "6" * 64},
        },
        "manifest_object": {
            "uri": runner.FREEZE_MANIFEST_URI, "generation": "3",
            "sha256": "8" * 64, "bytes": 1, "metageneration": "1",
        },
        "smoke_receipt": {}, "smoke_object": {},
        "support_receipt": "frozen-support", "support_object": {},
        "source_artifact_lock_sha256": "7" * 64,
        "implementation_sha256": {},
    })
    monkeypatch.setattr(
        runner, "_attach_in_image_science_replay",
        lambda report, **kwargs: report.__setitem__(
            "in_image_science_replay", {
                "version": "a7-in-image-science-replay-v1",
                "image": "registry.invalid/image@sha256:" + "b" * 64,
                "finisher_sha256": "6" * 64,
                "receipt": {"version": "a7-strict-science-replay-v1"},
                "receipt_sha256": "7" * 64,
            },
        ),
    )
    baseline_vector = {
        (season, week): 79.0 for season, week in slates
    }
    monkeypatch.setattr(runner, "_baseline_vector", lambda: baseline_vector)
    monkeypatch.setattr(runner, "validate_control_baseline", lambda *args, **kwargs: {
        "reproduced": True, "weekly_vector_reproduced": True,
    })
    return queries, slates, actuals


def test_prepare_slate_integrates_explicit_arms_order_tags_and_hashes(
    monkeypatch,
):
    rng = np.random.default_rng(20_260_820)
    player_ids = [f"player-{index:03d}" for index in range(88)]
    player_draws = rng.normal(
        20.0, 5.0, size=(len(player_ids), 50_000),
    ).astype("<f4")
    roster_rows = [list(range(8)) + [8 + index] for index in range(80)]
    rosters = [frozenset(player_ids[index] for index in rows)
               for rows in roster_rows]
    candidates = [SimpleNamespace(ids=roster) for roster in rosters]
    totals = np.stack([
        player_draws[rows].sum(axis=0, dtype="float32")
        for rows in roster_rows
    ])
    tags = {
        roster: ("boom", f"candidate_seed:R{index % 5}")
        for index, roster in enumerate(rosters)
    }
    combined = SimpleNamespace(
        candidates=candidates,
        candidate_totals=totals,
        player_ids=player_ids,
        row_draws=player_draws,
        all_tags=tags,
    )
    canonical_identities = [sorted(roster) for roster in rosters]
    expected_control = science.select_books(totals)["control"]
    expected_control_ids = [canonical_identities[index]
                            for index in expected_control]

    source_rows = []
    source_map = {}
    for panel in runner.SOURCE_PANEL_IDS:
        source_rows.append({
            "panel_run_id": panel, "season": 2023, "week": 1,
        })
        source_map[(panel, 2023, 1)] = {
            "uri": f"gs://bucket/{panel}", "sha256": "9" * 64,
            "generation": "1", "bytes": 1, "source_rows": 80,
        }
    sources = pd.DataFrame(source_rows)
    players = pd.DataFrame([{"season": 2023, "week": 1}])
    monkeypatch.setattr(runner, "_download_artifact_pinned", lambda *a, **k: (
        {}, {
            "uri": str(a[1]), "sha256": str(a[2]), "generation": "1",
            "metageneration": "1", "bytes": 1, "md5_hash": "",
            "crc32c": "",
        },
    ))
    monkeypatch.setattr(runner, "_candidate_batch", lambda *a, **k: object())
    monkeypatch.setattr(runner, "combine_cbwu_books", lambda *a, **k: combined)
    monkeypatch.setattr(runner, "_is_production_legal", lambda lineup: True)

    calls = []
    real_selector = science.select_tail_entries

    def capture_selector(matrix, count, line, env=None):
        calls.append((int(count), float(line), dict(env or {})))
        return real_selector(matrix, count, line, env=env)

    monkeypatch.setattr(science, "select_tail_entries", capture_selector)
    row, artifacts = runner._prepare_slate(
        season=2023,
        week=1,
        sources=sources,
        players=players,
        source_map=source_map,
        expected={
            "order_invariant": True,
            "control": {"identities": expected_control_ids},
        },
        gcs=object(),
    )
    assert calls == [
        (80, 194.0, science.CONTROL_ENV),
        (4, 194.0, science.CONTROL_ENV),
        (14, 194.0, science.CONTROL_ENV),
        (80, 194.0, science.TREATMENT_ENV),
        (4, 194.0, science.TREATMENT_ENV),
        (14, 194.0, science.TREATMENT_ENV),
    ]
    assert row["control"]["identities"] == expected_control_ids
    assert row["control"]["selector_env"] == science.CONTROL_ENV
    assert row["treatment"]["selector_env"] == science.TREATMENT_ENV
    assert row["candidate_identities_sha256"] == sha256(json.dumps(
        canonical_identities, sort_keys=True, separators=(",", ":"),
    ).encode()).hexdigest()
    assert len(row["control"]["selected_source_tags"]) == 80
    assert len(row["treatment"]["selected_source_tags"]) == 80
    assert all(
        len([tag for tag in values if tag.startswith("candidate_seed:")]) == 1
        for values in row["treatment"]["selected_source_tags"]
    )
    assert len(artifacts) == 5

    with pytest.raises(RuntimeError, match="control exact-80 source reproduction"):
        runner._prepare_slate(
            season=2023,
            week=1,
            sources=sources,
            players=players,
            source_map=source_map,
            expected={
                "order_invariant": True,
                "control": {"identities": list(reversed(expected_control_ids))},
            },
            gcs=object(),
        )


def test_smoke_never_formats_or_executes_actual_query(monkeypatch):
    queries, _, _ = _patch_sources(monkeypatch)
    monkeypatch.setenv("CODE_SHA", "a" * 40)
    monkeypatch.setattr(
        runner, "_actual_sql",
        lambda: pytest.fail("smoke crossed the historical outcome boundary"),
    )
    report = runner.run(output_uri=None, smoke=True)
    assert len(queries) == 2
    assert report["smoke"] is True
    assert report["support_census"] is False
    assert report["uses_realized_outcomes"] is False
    assert report["actual_score_query_executed"] is False
    assert len(report["slates"]) == 1
    assert "output" not in report


def test_support_census_is_all_54_and_never_crosses_outcome_boundary(monkeypatch):
    queries, _, _ = _patch_sources(monkeypatch)
    monkeypatch.setenv("CODE_SHA", "a" * 40)
    monkeypatch.setattr(
        runner, "_actual_sql",
        lambda: pytest.fail("support census crossed the historical boundary"),
    )
    report = runner.run(output_uri=None, smoke=False, support_census=True)
    assert len(queries) == 2
    assert report["smoke"] is False
    assert report["support_census"] is True
    assert report["uses_realized_outcomes"] is False
    assert report["actual_score_query_executed"] is False
    assert len(report["slates"]) == 54
    assert report["support"]["passes"] is True
    assert "scorefree" not in report


def test_unsupported_census_is_durable_but_cannot_reach_full_outcomes(monkeypatch):
    queries, _, _ = _patch_sources(monkeypatch, realism_supported=False)
    monkeypatch.setenv("CODE_SHA", "a" * 40)
    monkeypatch.setattr(
        runner, "_actual_sql",
        lambda: pytest.fail("unsupported census crossed the historical boundary"),
    )
    report = runner.run(output_uri=None, smoke=False, support_census=True)
    assert report["support"]["passes"] is False
    assert len(queries) == 2

    monkeypatch.setattr(runner, "validate_execution_identity", lambda *args: None)
    monkeypatch.setenv(
        "ANALYSIS_IMAGE", "registry.invalid/image@sha256:" + "b" * 64,
    )
    with pytest.raises(RuntimeError, match="support disappeared"):
        runner.run(output_uri=runner.OUTPUT_URI, smoke=False)
    assert len(queries) == 4


def test_full_run_fails_before_actual_query_when_scorefree_gate_fails(
    monkeypatch,
):
    queries, _, _ = _patch_sources(monkeypatch, mechanics_passes=False)
    monkeypatch.setattr(runner, "validate_execution_identity", lambda *args: None)
    monkeypatch.setenv("CODE_SHA", "a" * 40)
    monkeypatch.setenv(
        "ANALYSIS_IMAGE", "registry.invalid/image@sha256:" + "b" * 64,
    )
    monkeypatch.setattr(
        runner, "_actual_sql",
        lambda: pytest.fail("failed score-free gate queried outcomes"),
    )
    with pytest.raises(RuntimeError, match="score-free mechanism"):
        runner.run(output_uri=runner.OUTPUT_URI, smoke=False)
    assert len(queries) == 2


def test_full_run_queries_actuals_only_after_all_54_scorefree_rows(
    monkeypatch,
):
    queries, slates, actuals = _patch_sources(monkeypatch)
    monkeypatch.setattr(runner, "validate_execution_identity", lambda *args: None)
    monkeypatch.setenv("CODE_SHA", "a" * 40)
    monkeypatch.setenv(
        "ANALYSIS_IMAGE", "registry.invalid/image@sha256:" + "b" * 64,
    )
    actual_maps = {
        (season, week): {
            tuple(identity): float(index)
            for index, identity in enumerate(_row(season, week)[
                "candidate_identities"
            ])
        }
        for season, week in slates
    }
    monkeypatch.setattr(runner, "_actual_maps", lambda sources, actuals: actual_maps)
    aggregate_kwargs = {}

    def aggregate(rows, **kwargs):
        aggregate_kwargs.update(kwargs)
        return {
            "disposition": "historical-positive-phase-s",
            "production_law_scorefree_transfer_licensed": True,
            "prospective_shadow_licensed": False,
        }

    monkeypatch.setattr(runner, "aggregate_outcomes", aggregate)
    monkeypatch.setattr(runner, "_upload_create_only", lambda client, uri, payload: {
        "uri": uri, "generation": "1", "sha256": "c" * 64,
        "bytes": len(payload), "create_only": True,
    })
    report = runner.run(output_uri=runner.OUTPUT_URI, smoke=False)
    assert len(queries) == 3
    assert "actual_score" in queries[2]
    assert len(report["slates"]) == 54
    assert report["actual_score_query_executed"] is True
    assert len(report["actual_query_rows"]) == len(actuals)
    assert report["actual_query_content_receipt"]["columns"] == list(
        runner.ACTUAL_QUERY_COLUMNS
    )
    assert all(
        len(row["candidate_actual_scores"]) == len(row["candidate_identities"])
        for row in report["slates"]
    )
    assert report["prospective_shadow_licensed"] is False
    assert report["production_law_scorefree_transfer_licensed"] is True
    assert report["production_change_licensed"] is False
    assert report["in_image_science_replay"]["version"] == (
        "a7-in-image-science-replay-v1"
    )
    assert report["output"]["create_only"] is True
    assert len(aggregate_kwargs["baseline_vector"]) == 54
    assert report["freeze_manifest_uri"] == runner.FREEZE_MANIFEST_URI


def test_supported_realism_failure_closes_outcome_blind(monkeypatch):
    queries, _, _ = _patch_sources(monkeypatch, realism_noninferior=False)
    monkeypatch.setattr(runner, "validate_execution_identity", lambda *args: None)
    monkeypatch.setenv("CODE_SHA", "a" * 40)
    monkeypatch.setenv(
        "ANALYSIS_IMAGE", "registry.invalid/image@sha256:" + "b" * 64,
    )
    monkeypatch.setattr(
        runner, "_actual_sql",
        lambda: pytest.fail("tail-artifact closure queried outcomes"),
    )
    monkeypatch.setattr(runner, "_upload_create_only", lambda client, uri, payload: {
        "uri": uri, "generation": "1", "sha256": "c" * 64,
        "bytes": len(payload), "create_only": True,
    })
    report = runner.run(output_uri=runner.OUTPUT_URI, smoke=False)
    assert len(queries) == 2
    assert report["disposition"] == "tail-artifact-risk-phase-s"
    assert report["uses_realized_outcomes"] is False
    assert report["prospective_shadow_licensed"] is False
    assert "in_image_science_replay" in report


def test_full_source_query_content_must_match_freeze(monkeypatch):
    queries, _, _ = _patch_sources(monkeypatch)
    monkeypatch.setattr(runner, "validate_execution_identity", lambda *args: None)
    monkeypatch.setenv("CODE_SHA", "a" * 40)
    monkeypatch.setenv(
        "ANALYSIS_IMAGE", "registry.invalid/image@sha256:" + "b" * 64,
    )
    monkeypatch.setattr(runner, "_load_freeze_evidence", lambda *args, **kwargs: {
        "manifest": {"query_content_receipts": {"poison": True}},
    })
    with pytest.raises(RuntimeError, match="query content differs"):
        runner.run(output_uri=runner.OUTPUT_URI, smoke=False)
    assert len(queries) == 2


def test_actual_map_requires_exact_keys_and_duplicate_score_parity():
    rows = [
        {"panel_run_id": "p0", "season": season, "week": week, "cand_ix": 0,
         "players": ",".join(f"x{season}-{week}-{index}" for index in range(9))}
        for season in (2023, 2024, 2025) for week in range(1, 19)
    ]
    # A second panel supplies the same first-slate roster; its score must agree.
    rows.append({**rows[0], "panel_run_id": "p1"})
    sources = pd.DataFrame(rows)
    actuals = sources.copy()
    actuals["actual_score"] = 200.0
    result = runner._actual_maps(sources, actuals)
    expected = tuple(f"x2023-1-{index}" for index in range(9))
    assert result[(2023, 1)][expected] == 200

    actuals.loc[len(actuals) - 1, "actual_score"] = 201.0
    with pytest.raises(RuntimeError, match="outcomes disagree"):
        runner._actual_maps(sources, actuals)
    with pytest.raises(RuntimeError, match="source candidate keys"):
        runner._actual_maps(sources, actuals.iloc[:1])


def test_retained_native_actual_query_is_complete_finite_and_sql_ordered():
    rows = [{
        "panel_run_id": panel,
        "season": 2023,
        "week": 1,
        "cand_ix": cand_ix,
        "players": ",".join(f"{panel}-{cand_ix}-p{slot}" for slot in range(9)),
        "actual_score": float(100 + cand_ix),
    } for panel, cand_ix in ((runner.SOURCE_PANEL_IDS[1], 2),
                             (runner.SOURCE_PANEL_IDS[0], 10),
                             (runner.SOURCE_PANEL_IDS[0], 1))]
    frame = pd.DataFrame(list(reversed(rows)), columns=runner.ACTUAL_QUERY_COLUMNS)
    retained, receipt = runner._retained_actual_query(frame)
    assert [
        (row["panel_run_id"], row["season"], row["week"], row["cand_ix"])
        for row in retained
    ] == sorted(
        (row["panel_run_id"], row["season"], row["week"], row["cand_ix"])
        for row in rows
    )
    assert receipt == runner._query_rows_content_receipt(
        retained, runner.ACTUAL_QUERY_COLUMNS, require_encoded_order=False,
    )
    poisoned = frame.copy()
    poisoned.loc[0, "actual_score"] = np.nan
    with pytest.raises(RuntimeError, match="retained actual-query row"):
        runner._retained_actual_query(poisoned)
    with pytest.raises(RuntimeError, match="schema"):
        runner._retained_actual_query(frame.drop(columns=["actual_score"]))


def test_in_image_replay_is_independent_hash_bound_and_pristine(monkeypatch):
    calls = {}
    expected_receipt = {
        "version": "a7-strict-science-replay-v1",
        "run_id": runner.RUN_ID,
        "outcome_replayed": False,
    }

    class Reader:
        def load(self, uri, generation):
            return {"uri": uri, "generation": generation}, b"raw"

    def replay(report, manifest, query_loader, object_loader):
        calls["report"] = dict(report)
        calls["manifest"] = manifest
        calls["queries"] = query_loader()
        calls["object"] = object_loader("gs://bucket/object", "7")
        return expected_receipt

    monkeypatch.setattr(runner.a7_transport, "_StorageReader", Reader)
    monkeypatch.setattr(runner.a7_transport, "_replay_science", replay)
    report = {"version": runner.VERSION, "uses_realized_outcomes": False}
    manifest = {
        "image": {"uri": "registry.invalid/a@sha256:" + "1" * 64},
        "implementation_sha256": {"finisher": "2" * 64},
    }
    sources, players = object(), object()
    runner._attach_in_image_science_replay(
        report, manifest=manifest, sources=sources, players=players,
    )
    block = report["in_image_science_replay"]
    expected_raw = (json.dumps(
        expected_receipt, sort_keys=True, separators=(",", ":"),
        allow_nan=False,
    ) + "\n").encode()
    assert block == {
        "version": "a7-in-image-science-replay-v1",
        "image": manifest["image"]["uri"],
        "finisher_sha256": "2" * 64,
        "receipt": expected_receipt,
        "receipt_sha256": sha256(expected_raw).hexdigest(),
    }
    assert calls["report"] == {
        "version": runner.VERSION, "uses_realized_outcomes": False,
    }
    assert calls["queries"] == (sources, players)
    assert calls["object"][0]["generation"] == "7"
    with pytest.raises(RuntimeError, match="not pristine"):
        runner._attach_in_image_science_replay(
            report, manifest=manifest, sources=sources, players=players,
        )


def test_baseline_labels_and_counts_are_literal():
    baseline = {
        "money_book": {
            "label": "registered production 80-entry book, realized weekly best",
            "mean_weekly_best": 176.06,
            "slates": 54,
            "at_or_above": {
                "187": 17, "194": 8, "200": 7, "210": 6,
                "220": 3, "230": 1, "240": 0,
            },
        },
    }
    assert runner._validate_baseline(baseline)[0] == 176.06
    baseline["money_book"]["slates"] = 53
    with pytest.raises(RuntimeError, match="baseline differs"):
        runner._validate_baseline(baseline)


def test_compact_preflight_receipt_binds_inputs_without_roster_bodies():
    row = _row(2023, 1)
    report = {
        "code_sha": "a" * 40,
        "image": "registry.invalid/a@sha256:" + "b" * 64,
        "protocol_sha256": "c" * 64,
        "source_report_sha256": "d" * 64,
        "baseline_sha256": "e" * 64,
        "baseline_vector_sha256": "6" * 64,
        "forensic_manifest_sha256": "f" * 64,
        "local_source_receipts": {"protocol": "c" * 64},
        "implementation_receipts": {"runner": "1" * 64},
        "query_content_receipts": {
            "candidate_source": {"rows": 1, "sha256": "7" * 64},
            "player_source": {"rows": 1, "sha256": "8" * 64},
        },
        "source_panels": list(runner.SOURCE_PANEL_IDS),
        "source_preflight": {"slate_count": 54, "artifact_count": 270},
        "source_artifacts": [{
            "panel_run_id": runner.SOURCE_PANEL_IDS[0],
            "season": 2023, "week": 1, "uri": "gs://bucket/a",
            "sha256": "9" * 64, "generation": "1", "bytes": 1,
            "candidate_rows": 80,
        }],
        "smoke": True,
        "slates": [row],
        "uses_realized_outcomes": False,
        "actual_score_query_executed": False,
        "production_change_licensed": False,
        "production_law_scorefree_transfer_licensed": False,
        "prospective_shadow_licensed": False,
    }
    receipt = runner._preflight_receipt(report)
    assert receipt["mode"] == "real-artifact-smoke"
    assert receipt["source_artifact_count"] == 1
    assert receipt["slates"][0]["combined_input_receipts"] == row[
        "combined_input_receipts"
    ]
    assert receipt["slates"][0]["candidate_tags_sha256"] == "5" * 64
    assert "candidate_identities" not in receipt["slates"][0]
    assert "2023-1-0-p0" not in str(receipt)
    assert receipt["uses_realized_outcomes"] is False


def test_source_artifact_download_is_generation_pinned(monkeypatch):
    raw = b"immutable-artifact"
    digest = __import__("hashlib").sha256(raw).hexdigest()

    class Blob:
        generation = 17
        metageneration = 1
        size = len(raw)
        md5_hash = "md5"
        crc32c = "crc"

        def __init__(self, pinned=None):
            self.pinned = pinned

        def reload(self, **kwargs):
            if self.pinned is not None:
                assert kwargs == {"if_generation_match": 17}

        def download_as_bytes(self, **kwargs):
            assert self.pinned == 17
            assert kwargs == {"if_generation_match": 17}
            return raw

    class Bucket:
        def blob(self, name, generation=None):
            assert name == "object"
            return Blob(generation)

    class Client:
        def bucket(self, name):
            assert name == "bucket"
            return Bucket()

    monkeypatch.setattr(runner, "decode_score_artifact", lambda value, sha: {
        "cand_ix": [], "totals": [], "player_ids": [], "player_draws": [],
    })
    _, receipt = runner._download_artifact_pinned(
        Client(), "gs://bucket/object", digest, generation="17",
        expected_bytes=len(raw),
    )
    assert receipt["generation"] == "17"
    assert receipt["metageneration"] == "1"
    assert receipt["bytes"] == len(raw)
