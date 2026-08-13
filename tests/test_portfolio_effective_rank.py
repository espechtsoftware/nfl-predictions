from __future__ import annotations

import hashlib
import importlib.util
import io
from pathlib import Path
import sys

import numpy as np
import pandas as pd
import pytest

from nfl_dfs.research.portfolio_effective_rank import (
    analyze_selected_book,
    decode_score_artifact,
)


def _payload(totals: np.ndarray) -> tuple[bytes, str]:
    buffer = io.BytesIO()
    np.savez_compressed(
        buffer,
        cand_ix=np.arange(len(totals), dtype=np.int32),
        totals=np.asarray(totals, dtype=np.float32),
        tail_line=np.float32(194.0),
    )
    value = buffer.getvalue()
    return value, hashlib.sha256(value).hexdigest()


def _rows(totals: np.ndarray, selected: int) -> pd.DataFrame:
    count, worlds = totals.shape
    rows = []
    for cand_ix in range(count):
        rows.append({
            "season": 2025,
            "week": 1,
            "cand_ix": cand_ix,
            "players": ",".join(
                f"p{cand_ix}_{slot}" for slot in range(9)),
            "selected": cand_ix < selected,
            "selected_rank": cand_ix if cand_ix < selected else -1,
            "n_worlds": worlds,
            "tail_line": 194.0,
            "sim_mean": float(totals[cand_ix].mean()),
        })
    return pd.DataFrame(rows)


def test_decodes_only_exact_checksummed_artifact():
    totals = np.arange(60, dtype=np.float32).reshape(6, 10)
    payload, digest = _payload(totals)
    artifact = decode_score_artifact(payload, digest)
    assert artifact["totals"].shape == (6, 10)
    with pytest.raises(ValueError, match="sha256 differs"):
        decode_score_artifact(payload, "0" * 64)


def test_identical_selected_entries_have_effective_rank_one():
    rng = np.random.default_rng(7331)
    one = rng.normal(190, 20, size=5000)
    totals = np.vstack([one, one, one, rng.normal(180, 10, size=5000)])
    payload, digest = _payload(totals)
    report = analyze_selected_book(
        _rows(totals, 3), decode_score_artifact(payload, digest),
        lines=(194,), book_sizes=(3,),
    )
    assert report["covariance"]["participation_ratio"] == pytest.approx(1.0)
    assert report["correlation"]["participation_ratio"] == pytest.approx(1.0)
    assert report["after_first_pc_deflation"]["status"] == \
        "degenerate-after-first-pc"
    assert report["nested_books"]["3"]["tails"][0][
        "pair_joint_lift_ratio_of_sums"] > 1


def test_independent_book_has_high_rank_and_nested_tail_disclosure():
    rng = np.random.default_rng(42)
    totals = rng.normal(194, 18, size=(80, 10000))
    payload, digest = _payload(totals)
    report = analyze_selected_book(
        _rows(totals, 80), decode_score_artifact(payload, digest),
    )
    assert report["correlation"]["participation_ratio"] > 78
    assert set(report["nested_books"]) == {"20", "40", "80"}
    for size in ("20", "40", "80"):
        assert len(report["nested_books"][size]["tails"]) == 7
    covered = [
        report["nested_books"][size]["tails"][1]["covered_world_rate"]
        for size in ("20", "40", "80")
    ]
    assert covered == sorted(covered)
    assert len(report["leading_factor_top_players"]) == 12
    assert report["after_first_pc_deflation"]["status"] == "valid"
    assert report["same_world_controls"]["random_books"]["books"] == 20
    assert report["same_world_controls"]["top_sim_mean"]["tails"][0][
        "worlds_with_any_event"] > 0
    assert report["nested_books"]["80"]["tails"][-1]["pair_cells"] == 3160


def test_rejects_incomplete_selected_ranks_and_artifact_universe():
    rng = np.random.default_rng(9)
    totals = rng.normal(size=(5, 100))
    payload, digest = _payload(totals)
    artifact = decode_score_artifact(payload, digest)
    rows = _rows(totals, 3)
    rows.loc[rows.cand_ix.eq(1), "selected_rank"] = 2
    with pytest.raises(ValueError, match="selected ranks"):
        analyze_selected_book(rows, artifact)
    with pytest.raises(ValueError, match="row count"):
        analyze_selected_book(_rows(totals[:4], 3), artifact)


def test_selected_diversification_exceeds_same_pool_controls():
    rng = np.random.default_rng(100)
    common = rng.normal(0, 12, size=4000)
    independent = rng.normal(0, 5, size=(100, 4000))
    totals = 195 + common + independent
    payload, digest = _payload(totals)
    rows = _rows(totals, 80)
    report = analyze_selected_book(
        rows, decode_score_artifact(payload, digest),
        lines=(194,), book_sizes=(80,),
    )
    assert report["after_first_pc_deflation"]["correlation"][
        "participation_ratio"] > report["correlation"]["participation_ratio"]
    random_summary = report["same_world_controls"]["random_books"][
        "deflated_correlation_participation_ratio"]
    assert random_summary["mean"] > 70


def test_main_image_contains_effective_rank_analyzer():
    dockerfile = (Path(__file__).parents[1] / "Dockerfile").read_text(
        encoding="utf-8")
    assert "COPY scripts/analyze_portfolio_effective_rank.py " \
        "./scripts/analyze_portfolio_effective_rank.py" in dockerfile
    analyzer = (Path(__file__).parents[1] /
                "scripts/analyze_portfolio_effective_rank.py").read_text(
                    encoding="utf-8")
    assert 'META_PREFIX = "PORTFOLIO_EFFECTIVE_RANK_META="' in analyzer
    assert 'CHUNK_PREFIX = "PORTFOLIO_EFFECTIVE_RANK_CHUNK="' in analyzer
    assert "encode_report_transport(report)" in analyzer


def _load_analyzer_module():
    path = Path(__file__).parents[1] / \
        "scripts/analyze_portfolio_effective_rank.py"
    spec = importlib.util.spec_from_file_location(
        "test_portfolio_effective_rank_analyzer", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_analyzer_composes_terminal_incumbent_by_frozen_seasons(
        monkeypatch, capsys):
    module = _load_analyzer_module()
    historical = "historical-panel"
    evaluation = "evaluation-panel"
    rows = []
    for season in (2019, 2021, 2022, 2023, 2024, 2025):
        source = historical if season <= 2022 else evaluation
        rows.append({
            "panel_run_id": source,
            "season": season,
            "week": 1,
            "cand_ix": 0,
            "players": "a,b,c,d,e,f,g,h,i",
            "selected": True,
            "selected_rank": 0,
            "n_worlds": 10000,
            "tail_line": 194.0,
            "sim_mean": 180.0,
            "score_artifact_uri": f"gs://bucket/{season}",
            "score_artifact_sha256": str(season),
        })
    frame = pd.DataFrame(rows)
    captured = {}

    monkeypatch.setattr(module, "query_df", lambda *args, **kwargs: frame)
    monkeypatch.setattr(module, "_download", lambda uri: b"artifact")
    monkeypatch.setattr(
        module, "decode_score_artifact", lambda payload, digest: {})
    monkeypatch.setattr(
        module,
        "analyze_selected_book",
        lambda group, artifact: {
            "season": int(group.season.iloc[0]),
            "week": int(group.week.iloc[0]),
        },
    )

    def encode(report):
        captured.update(report)
        return {"chunks": 1}, ["payload"]

    monkeypatch.setattr(module, "encode_report_transport", encode)
    monkeypatch.setattr(sys, "argv", [
        "analyze_portfolio_effective_rank.py",
        "--historical-panel", historical,
        "--selected-eval-panel", evaluation,
        "--source", "promoted",
    ])
    assert module.main() == 0
    assert captured["version"] == "v2"
    assert captured["slate_count"] == 6
    assert captured["historical_panel"] == historical
    assert captured["selected_eval_panel"] == evaluation
    by_season = {row["season"]: row["source_panel"]
                 for row in captured["slates"]}
    assert by_season == {
        2019: historical,
        2021: historical,
        2022: historical,
        2023: evaluation,
        2024: evaluation,
        2025: evaluation,
    }
    assert "PORTFOLIO_EFFECTIVE_RANK_META=" in capsys.readouterr().out


def test_effective_rank_v2_scripts_bind_composite_scope():
    root = Path(__file__).parents[1]
    launcher = (root / "scripts/cloud_portfolio_effective_rank_v2.sh").read_text(
        encoding="utf-8")
    finisher = (
        root / "scripts/cloud_finish_portfolio_effective_rank_v2.sh"
    ).read_text(encoding="utf-8")
    assert "--historical-panel,$HISTORICAL_PANEL" in launcher
    assert "--selected-eval-panel,$EVAL_PANEL" in launcher
    assert 'report.get("slate_count") != 107' in finisher
    assert 'row.get("source_panel") != expected_panel' in finisher
