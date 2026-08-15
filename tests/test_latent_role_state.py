import hashlib
import json

import numpy as np
import pandas as pd
import pytest

from nfl_dfs.research.latent_role_state import (
    MODEL_FEATURES,
    STATES,
    TRANSITION_SOURCE_SQL,
    LatentRoleStateError,
    add_previous_state,
    apply_sampled_role_states,
    classify_realized_states,
    compute_role_state_emissions,
    decode_role_transition_artifact,
    encode_role_transition_artifact,
    empirical_transition_probabilities,
    expanding_role_audit,
    fit_role_transition,
    multiclass_scores,
    persist_role_transition_artifact,
    predict_role_transition_artifact,
    prepare_transition_frame,
    transition_frame_sha256,
    validate_team_role_share_caps,
)


def test_frozen_role_state_boundaries_and_unavailable_snap():
    rows = pd.DataFrame({
        "position": ["WR", "WR", "TE", "RB", "RB", "WR", "RB"],
        "was_active": [False, True, True, True, True, True, True],
        "snap_share": [np.nan, 0.20, 0.70, 0.70, 0.70, np.nan, 0.50],
        "target_share": [np.nan, 0.07, 0.14, 0.10, 0.10, 0.30, np.nan],
        "carry_share": [np.nan, 0.00, 0.00, 0.20, 0.30, 0.00, np.nan],
    })
    out = classify_realized_states(rows)
    assert out.iloc[:5].tolist() == [
        "inactive", "dormant", "rotation", "secondary", "primary",
    ]
    assert pd.isna(out.iloc[5])
    assert pd.isna(out.iloc[6])


def test_role_state_rejects_unregistered_positions():
    rows = pd.DataFrame({
        "position": ["QB"], "was_active": [True], "snap_share": [1.0],
        "target_share": [0.0], "carry_share": [0.0],
    })
    with pytest.raises(LatentRoleStateError, match="unsupported"):
        classify_realized_states(rows)


def test_previous_state_is_strict_prior_within_player_season():
    rows = pd.DataFrame({
        "gsis_id": ["a", "a", "a", "a"],
        "season": [2026, 2025, 2025, 2025],
        "week": [1, 3, 1, 2],
        "realized_state": ["primary", "secondary", "dormant", "rotation"],
    })
    out = add_previous_state(rows).sort_values(["season", "week"])
    assert out.previous_state.tolist() == [
        "unknown", "dormant", "rotation", "unknown",
    ]


def _transition_rows(n_per_state: int = 8) -> pd.DataFrame:
    rows = []
    for state_index, state in enumerate(STATES):
        for repeat in range(n_per_state):
            level = state_index / (len(STATES) - 1)
            rows.append({
                "position": ("RB", "WR", "TE")[repeat % 3],
                "previous_state": STATES[(state_index + repeat) % len(STATES)],
                "injury_status": None if repeat == 0 else "Questionable",
                "target_share_last": level * 0.30,
                "target_share_l4": level * 0.25,
                "carry_share_last": level * 0.35,
                "carry_share_l4": level * 0.30,
                "snap_share_last": 0.05 + level * 0.90,
                "snap_share_l4": 0.05 + level * 0.80,
                "target_share_jump": level * 0.10,
                "carry_share_jump": level * 0.10,
                "snap_share_jump": level * 0.15,
                "games_played_prior": repeat + 1,
                "practice_level": None if repeat == 0 else float(repeat % 3),
                "team_vacated_target_share": (
                    None if repeat == 0 else level * 0.20
                ),
                "team_vacated_carry_share": (
                    None if repeat == 0 else level * 0.25
                ),
                "realized_state": state,
            })
    return pd.DataFrame(rows)


def test_transition_input_denies_outcomes_and_builds_missing_flags():
    rows = _transition_rows()
    prepared = prepare_transition_frame(rows)
    assert list(prepared.columns) == [*MODEL_FEATURES, "realized_state"]
    assert prepared.injury_status_missing.sum() == len(STATES)
    assert prepared.practice_level_missing.sum() == len(STATES)
    assert prepared.vacated_target_missing.sum() == len(STATES)
    assert prepared.vacated_carry_missing.sum() == len(STATES)

    unsafe = rows.assign(dk_points=100.0)
    with pytest.raises(LatentRoleStateError, match="forbidden outcomes"):
        prepare_transition_frame(unsafe)

    with pytest.raises(LatentRoleStateError, match="unsupported transition"):
        prepare_transition_frame(rows.assign(position="QB"))


def test_frozen_transition_fit_is_deterministic_and_predicts_canonical_states():
    rows = _transition_rows()
    first = fit_role_transition(rows)
    second = fit_role_transition(rows)
    assert first.n_rows == len(rows)
    assert set(first.classes) == set(STATES)

    live = rows.drop(columns="realized_state").iloc[:7]
    p1 = first.predict_proba(live)
    p2 = second.predict_proba(live)
    assert list(p1.columns) == list(STATES)
    assert np.allclose(p1, p2)
    assert np.allclose(p1.sum(axis=1), 1.0)

    baseline = empirical_transition_probabilities(rows, rows.iloc[:7])
    assert list(baseline.columns) == list(STATES)
    assert np.allclose(baseline.sum(axis=1), 1.0)


def test_source_query_is_score_denying_and_expanding_audit_is_walk_forward():
    lower = TRANSITION_SOURCE_SQL.lower()
    for forbidden in (
        "fantasy_points", "dk_points", "lineup_score", "winner_score",
        "winnings", "payout",
    ):
        assert forbidden not in lower
    assert "t.season between 2018 and 2025" in lower
    assert "t.position in ('rb', 'wr', 'te')" in lower

    frames = []
    for season in (2021, 2022, 2023):
        frame = _transition_rows().copy()
        frame["season"] = season
        frames.append(frame)
    audit = expanding_role_audit(
        pd.concat(frames, ignore_index=True), evaluation_seasons=(2023,),
    )
    assert audit.season.tolist() == [2023]
    assert audit.n_train.tolist() == [80]
    assert audit.n_test.tolist() == [40]
    for column in (
        "model_log_loss", "model_multiclass_brier",
        "baseline_log_loss", "baseline_multiclass_brier",
    ):
        assert np.isfinite(audit[column]).all()


def test_role_calibration_metrics_use_only_state_labels():
    truth = pd.Series(list(STATES), index=range(len(STATES)), dtype="string")
    values = np.full((len(STATES), len(STATES)), 0.025)
    np.fill_diagonal(values, 0.90)
    probabilities = pd.DataFrame(values, columns=STATES, index=truth.index)
    scores = multiclass_scores(truth, probabilities)
    assert 0 < scores["log_loss"] < 0.2
    assert 0 < scores["multiclass_brier"] < 0.02

    with pytest.raises(LatentRoleStateError, match="canonical"):
        multiclass_scores(truth, probabilities[list(reversed(STATES))])


def _keyed_transition_rows() -> pd.DataFrame:
    rows = _transition_rows().copy()
    rows["gsis_id"] = [f"player-{index:03d}" for index in range(len(rows))]
    rows["season"] = 2025
    rows["week"] = (np.arange(len(rows)) % 18) + 1
    shares = {
        "inactive": (np.nan, np.nan, np.nan),
        "dormant": (0.06, 0.05, 0.20),
        "rotation": (0.12, 0.12, 0.50),
        "secondary": (0.20, 0.20, 0.70),
        "primary": (0.30, 0.30, 0.85),
    }
    rows[["target_share", "carry_share", "snap_share"]] = [
        shares[state] for state in rows["realized_state"]
    ]
    return rows


def test_transition_artifact_is_byte_stable_and_portable_prediction_matches():
    rows = _keyed_transition_rows()
    fitted = fit_role_transition(rows)
    code_sha = "a" * 40
    first, receipt = encode_role_transition_artifact(
        fitted, rows, code_sha=code_sha,
    )
    second, second_receipt = encode_role_transition_artifact(
        fitted, rows.sample(frac=1, random_state=99), code_sha=code_sha,
    )
    assert first == second
    assert receipt == second_receipt
    assert transition_frame_sha256(rows) == transition_frame_sha256(
        rows.sample(frac=1, random_state=11)
    )

    artifact = decode_role_transition_artifact(first, receipt["sha256"])
    assert artifact["state_emissions"]["RB"]["inactive"] == {
        "carry_share": 0.0, "snap_share": 0.0, "target_share": 0.0,
    }
    assert artifact["state_emissions"]["WR"]["primary"] == {
        "carry_share": 0.3, "snap_share": 0.85, "target_share": 0.3,
    }
    live = rows.drop(columns="realized_state").iloc[:12]
    expected = fitted.predict_proba(live)
    portable = predict_role_transition_artifact(artifact, live)
    assert np.allclose(portable, expected, atol=1e-12)
    assert not receipt["uses_fantasy_or_lineup_outcomes"]

    with pytest.raises(LatentRoleStateError, match="sha256 differs"):
        decode_role_transition_artifact(first + b" ", receipt["sha256"])
    changed = json.loads(first)
    changed["uses_fantasy_or_lineup_outcomes"] = True
    unsafe = json.dumps(
        changed, allow_nan=False, separators=(",", ":"), sort_keys=True,
    ).encode()
    with pytest.raises(LatentRoleStateError, match="outcome boundary"):
        decode_role_transition_artifact(
            unsafe, hashlib.sha256(unsafe).hexdigest(),
        )


class _FakeBlob:
    def __init__(self):
        self.calls = []

    def upload_from_string(self, payload, **kwargs):
        self.calls.append((payload, kwargs))


class _FakeBucket:
    def __init__(self):
        self.blobs = {}

    def blob(self, name):
        return self.blobs.setdefault(name, _FakeBlob())


class _FakeStorage:
    def __init__(self):
        self.buckets = {}

    def bucket(self, name):
        return self.buckets.setdefault(name, _FakeBucket())


def test_transition_artifact_persistence_is_create_only():
    rows = _keyed_transition_rows()
    storage = _FakeStorage()
    receipt = persist_role_transition_artifact(
        fit_role_transition(rows), rows, code_sha="b" * 40,
        bucket_name="evidence-bucket", object_name="role/v1/model.json",
        storage_client=storage,
    )
    call = storage.buckets["evidence-bucket"].blobs[
        "role/v1/model.json"
    ].calls
    assert len(call) == 1
    payload, kwargs = call[0]
    assert kwargs == {
        "content_type": "application/json", "if_generation_match": 0,
    }
    assert hashlib.sha256(payload).hexdigest() == receipt["sha256"]
    assert receipt["uri"] == "gs://evidence-bucket/role/v1/model.json"
    assert receipt["create_only"]


def test_role_emissions_require_every_active_position_state_cell():
    rows = _keyed_transition_rows()
    emissions = compute_role_state_emissions(rows)
    assert list(emissions) == ["RB", "WR", "TE"]
    assert emissions["TE"]["inactive"] == {
        "target_share": 0.0, "carry_share": 0.0, "snap_share": 0.0,
    }
    assert emissions["TE"]["secondary"]["target_share"] == 0.20

    missing = rows[
        ~(
            rows.position.eq("TE")
            & rows.realized_state.eq("secondary")
        )
    ]
    with pytest.raises(LatentRoleStateError, match="TE/secondary"):
        compute_role_state_emissions(missing)


def test_conditional_role_frame_replaces_only_registered_role_fields():
    training = _keyed_transition_rows()
    fitted = fit_role_transition(training)
    payload, receipt = encode_role_transition_artifact(
        fitted, training, code_sha="c" * 40,
    )
    artifact = decode_role_transition_artifact(payload, receipt["sha256"])
    live = training.drop(columns=[
        "realized_state", "target_share", "carry_share", "snap_share",
    ]).iloc[:3].copy()
    live.index = pd.Index([10, 20, 30])
    live["team"] = ["A", "A", "B"]
    live["injury_status"] = ["Questionable", "Out", None]
    live["unrelated_market_mean"] = [12.0, 13.0, 14.0]
    states = pd.Series(["primary", "inactive", "rotation"], index=live.index)

    conditional = apply_sampled_role_states(artifact, live, states)
    for field in ("target_share", "carry_share", "snap_share"):
        expected = [
            artifact["state_emissions"][position][state][field]
            for position, state in zip(live.position, states, strict=True)
        ]
        assert conditional[f"{field}_last"].tolist() == expected
        assert np.allclose(
            conditional[f"{field}_jump"],
            np.asarray(expected) - live[f"{field}_l4"],
        )
        assert conditional[f"{field}_l4"].equals(live[f"{field}_l4"])
    assert conditional.sampled_role_state.tolist() == states.tolist()
    assert conditional.unrelated_market_mean.equals(live.unrelated_market_mean)
    assert conditional.injury_status.equals(live.injury_status)

    bad_out = states.copy()
    bad_out.loc[20] = "rotation"
    with pytest.raises(LatentRoleStateError, match="listed Out"):
        apply_sampled_role_states(artifact, live, bad_out)
    with pytest.raises(LatentRoleStateError, match="exactly aligned"):
        apply_sampled_role_states(artifact, live, states.reset_index(drop=True))


def test_conditional_role_frame_rejects_team_share_cap_breach():
    training = _keyed_transition_rows()
    payload, receipt = encode_role_transition_artifact(
        fit_role_transition(training), training, code_sha="d" * 40,
    )
    artifact = decode_role_transition_artifact(payload, receipt["sha256"])
    live = training.drop(columns=[
        "realized_state", "target_share", "carry_share", "snap_share",
    ]).iloc[:4].copy()
    live["position"] = ["RB", "WR", "TE", "WR"]
    live["team"] = "A"
    live["injury_status"] = "Questionable"
    states = pd.Series("primary", index=live.index)
    with pytest.raises(LatentRoleStateError, match="team-share cap"):
        apply_sampled_role_states(artifact, live, states)

    allowed = live.iloc[:3].copy()
    totals = validate_team_role_share_caps(
        apply_sampled_role_states(artifact, allowed, states.loc[allowed.index])
    )
    assert totals["A"]["target_share"] == pytest.approx(0.9)
    assert totals["A"]["carry_share"] == pytest.approx(0.9)
