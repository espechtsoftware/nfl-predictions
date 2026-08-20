from __future__ import annotations

from itertools import combinations
import json

import numpy as np
import pandas as pd
import pytest

from nfl_dfs.research.b1_corpus_tail import (
    ENTRIES,
    FEATURE_COLUMNS,
    CorpusTailError,
    artifact_sha256,
    build_deduplicated_dataset,
    build_shadow_receipt,
    evaluate_six_week_adoption,
    historical_evaluation,
    predict_tail_score,
    select_exact80,
)


CANONICAL = "canonical-panel"


def _source(*, outcomes: bool = True, seasons=(2023, 2024, 2025)):
    player_rows = []
    candidate_rows = []
    positions = {
        "qb": ("QB", "A", "B", 6_000),
        **{f"rb{i}": ("RB", "A" if i < 3 else "C", "B" if i < 3 else "D", 4_800 + i * 50)
           for i in range(5)},
        **{f"wr{i}": ("WR", "A" if i < 4 else "B", "B" if i < 4 else "A", 4_100 + i * 70)
           for i in range(8)},
        **{f"te{i}": ("TE", "B", "A", 3_500 + i * 50) for i in range(3)},
        "dst0": ("DST", "C", "D", 2_800),
        "dst1": ("DST", "D", "C", 2_900),
    }
    roster_templates = []
    for rb in combinations([f"rb{i}" for i in range(5)], 2):
        for wr in combinations([f"wr{i}" for i in range(8)], 4):
            for te in [f"te{i}" for i in range(3)]:
                for dst in ("dst0", "dst1"):
                    roster_templates.append(("qb", *rb, *wr, te, dst))
    roster_templates = roster_templates[:130]
    for season in seasons:
        for week in (1, 2):
            for player_id, (pos, team, opp, salary) in positions.items():
                player_rows.append({
                    "season": season, "week": week, "id": player_id,
                    "pos": pos, "team": team, "opp": opp,
                    "game_id": "B@A" if {team, opp} == {"A", "B"} else "D@C",
                    "salary": salary,
                })
            for index, roster in enumerate(roster_templates):
                p = index / (len(roster_templates) - 1)
                actual = 145.0 + 75.0 * p + (week - 1) * 0.01
                salary = sum(positions[player][3] for player in roster)
                row = {
                    "panel_run_id": CANONICAL, "season": season, "week": week,
                    "cand_ix": index, "players": ",".join(roster),
                    "tag": "boom" if index % 2 else "base",
                    "selected": index < ENTRIES,
                    "selected_rank": index if index < ENTRIES else -1,
                    "salary": salary, "p_line": p,
                    "sim_mean": 140 + 40 * p, "sim_sd": 18 + 2 * p,
                    "sim_q50": 140 + 40 * p, "sim_q90": 175 + 45 * p,
                    "sim_q99": 195 + 50 * p,
                    "sim_rank_p_line": len(roster_templates) - index,
                }
                if outcomes:
                    row["actual_score"] = actual
                candidate_rows.append(row)
            alt = roster_templates[::2]
            for alt_ix, roster in enumerate(alt):
                index = roster_templates.index(roster)
                p = index / (len(roster_templates) - 1)
                salary = sum(positions[player][3] for player in roster)
                row = {
                    "panel_run_id": "alternate-panel", "season": season, "week": week,
                    "cand_ix": alt_ix, "players": ",".join(reversed(roster)),
                    "tag": "alternate", "selected": False, "selected_rank": -1,
                    "salary": salary, "p_line": min(1.0, p + 0.01),
                    "sim_mean": 141 + 40 * p, "sim_sd": 18 + 2 * p,
                    "sim_q50": 141 + 40 * p, "sim_q90": 176 + 45 * p,
                    "sim_q99": 196 + 50 * p,
                    "sim_rank_p_line": len(alt) - alt_ix,
                }
                if outcomes:
                    row["actual_score"] = 145.0 + 75.0 * p + (week - 1) * 0.01
                candidate_rows.append(row)
    return pd.DataFrame(candidate_rows), pd.DataFrame(player_rows)


def test_deduplicated_dataset_is_one_roster_per_slate_and_prelock_only():
    candidates, players = _source(outcomes=False, seasons=(2026,))
    dataset = build_deduplicated_dataset(
        candidates, players, canonical_panel=CANONICAL, include_outcomes=False,
    )

    assert len(dataset) == 260
    assert not dataset.duplicated(["season", "week", "roster_key"]).any()
    assert "actual_score" not in dataset
    assert set(FEATURE_COLUMNS) <= set(dataset)
    assert dataset.canonical_candidate.all()
    assert dataset.groupby(["season", "week"]).canonical_selected.sum().eq(80).all()
    assert dataset.appearances.max() == 2


def test_outcome_blind_builder_rejects_even_unread_outcome_columns():
    candidates, players = _source(outcomes=True, seasons=(2026,))
    with pytest.raises(CorpusTailError, match="forbidden fields"):
        build_deduplicated_dataset(
            candidates, players, canonical_panel=CANONICAL, include_outcomes=False,
        )


def test_loso_model_and_exact80_gate_use_no_winner_and_keep_production_off():
    candidates, players = _source()
    dataset = build_deduplicated_dataset(
        candidates, players, canonical_panel=CANONICAL, include_outcomes=True,
    )
    report, artifact = historical_evaluation(dataset)

    assert report["population"]["deduplicated_rosters"] == 780
    assert report["model"]["winner_fields_used"] == []
    assert report["model"]["hyperparameter_grid"] == []
    assert report["loso"]["average_precision_ge200"] > report["loso"]["prevalence_ge200"]
    assert report["exact80"]["books"]["challenger"]["mean_weekly_max"] > \
        report["exact80"]["books"]["control"]["mean_weekly_max"]
    assert report["historical_pass"] is True
    assert report["licenses"]["run_2026_shadow"] is True
    assert report["licenses"]["production"] is False
    assert artifact["artifact_sha256"] == artifact_sha256(artifact)
    scores = predict_tail_score(dataset.head(), artifact)
    assert np.isfinite(scores).all() and ((0 < scores) & (scores < 1)).all()


def test_exact80_redundancy_pass_is_deterministic_and_backfills_if_needed():
    candidates, players = _source(outcomes=False, seasons=(2026,))
    dataset = build_deduplicated_dataset(
        candidates, players, canonical_panel=CANONICAL, include_outcomes=False,
    )
    slate = dataset[dataset.week.eq(1)].assign(
        tail_score=np.linspace(1.0, 0.0, 130),
    )
    first, receipt1 = select_exact80(slate)
    second, receipt2 = select_exact80(slate.sample(frac=1, random_state=7))

    assert len(first) == len(second) == 80
    assert first.roster_key.tolist() == second.roster_key.tolist()
    assert receipt1 == receipt2
    assert receipt1["entry_budget"] == 80


def test_shadow_receipt_is_default_off_outcome_free_and_exact80():
    historical_candidates, historical_players = _source()
    historical = build_deduplicated_dataset(
        historical_candidates, historical_players,
        canonical_panel=CANONICAL, include_outcomes=True,
    )
    _, artifact = historical_evaluation(historical)
    live_candidates, live_players = _source(outcomes=False, seasons=(2026,))
    live = build_deduplicated_dataset(
        live_candidates[live_candidates.week.eq(1)],
        live_players[live_players.week.eq(1)],
        canonical_panel=CANONICAL, include_outcomes=False,
    )
    with pytest.raises(CorpusTailError, match="not enabled"):
        build_shadow_receipt(live, artifact, source_identity={"snapshot": "late"}, enabled=False)

    source_identity = {
        "snapshot_id": "late", "snapshot_at": "2026-09-13T16:20:00Z",
        "lock_at": "2026-09-13T17:00:00Z",
        "candidate_query": {"ended": "2026-09-13T16:19:00Z"},
        "player_query": {"ended": "2026-09-13T16:20:00Z"},
        "realized_outcome_columns_read": [],
    }
    receipt = build_shadow_receipt(
        live, artifact, source_identity=source_identity, enabled=True,
    )
    assert receipt["candidate_budget_control"] == receipt["candidate_budget_challenger"]
    assert len(receipt["control_entries"]) == len(receipt["challenger_entries"]) == 80
    assert receipt["uses_realized_outcomes"] is False
    assert receipt["production_licensed"] is False
    assert "actual" not in json.dumps(receipt).lower()

    for changes in (
        {"snapshot_at": "not-a-time"},
        {"snapshot_at": "2026-09-13T16:20:00"},
        {"snapshot_id": ""},
        {"snapshot_at": "2026-09-13T17:00:00Z"},
        {"realized_outcome_columns_read": ["actual_score"]},
    ):
        bad_identity = {**source_identity, **changes}
        with pytest.raises(CorpusTailError, match="snapshot|source"):
            build_shadow_receipt(
                live, artifact, source_identity=bad_identity, enabled=True,
            )


def test_six_week_gate_requires_real_tail_gain_and_never_auto_mutates_production():
    grades = pd.DataFrame({
        "season": [2026] * 6, "week": list(range(1, 7)),
        "control_max": [190, 198, 201, 205, 188, 212],
        "challenger_max": [202, 199, 203, 206, 195, 212],
        "candidate_budget_control": [500] * 6,
        "candidate_budget_challenger": [500] * 6,
        "entries_control": [80] * 6, "entries_challenger": [80] * 6,
        "frozen_before_lock": [True] * 6, "labels_complete": [True] * 6,
        "receipt_valid": [True] * 6,
    })
    result = evaluate_six_week_adoption(grades)

    assert result["prospective_gate_passed"] is True
    assert result["production_review_licensed"] is True
    assert result["automatic_production_mutation"] is False
    assert result["winner_fields_used"] == []

    for bad_value in (1, 0, "true", "false"):
        poisoned = grades.copy()
        poisoned["receipt_valid"] = poisoned["receipt_valid"].astype(object)
        poisoned.loc[0, "receipt_valid"] = bad_value
        with pytest.raises(CorpusTailError, match="exact booleans"):
            evaluate_six_week_adoption(poisoned)
