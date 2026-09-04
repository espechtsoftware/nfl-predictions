"""End-to-end OFFLINE smoke of the live sim build chain (2026-08-04
readiness check): synthetic slate through the REAL build_sim_lineups —
cold-start fill, ensemble component models, correlated sims, draw
shaping (TabPFN cache empty -> empirical fallback), fade (booster
unavailable -> naive fallback), tilts, candidate generation, and
tail-coverage selection. This is the week-1 'first click' path with
every BigQuery/registry touchpoint mocked."""
import numpy as np
import pandas as pd
import pytest


def test_props_first_market_keeps_per_player_dk_ppg_fallback():
    from nfl_dfs.inference.run_projections import (
        _props_first_market_with_dk_fallback,
    )

    fallback = np.array([10.0, 20.0, 30.0, 40.0, 50.0])
    props = np.array([101.0, np.nan, 303.0, np.nan, np.nan])

    market, prop_mask = _props_first_market_with_dk_fallback(
        fallback, props,
    )

    assert market == pytest.approx([101.0, 20.0, 303.0, 40.0, 50.0])
    assert prop_mask.tolist() == [True, False, True, False, False]


def test_props_first_market_uses_full_dk_ppg_below_coverage_gate():
    from nfl_dfs.inference.run_projections import (
        _props_first_market_with_dk_fallback,
    )

    fallback = np.array([10.0, 20.0, 30.0, 40.0, 50.0])
    props = np.array([101.0, np.nan, np.nan, np.nan, np.nan])

    market, prop_mask = _props_first_market_with_dk_fallback(
        fallback, props,
    )

    assert market == pytest.approx(fallback)
    assert not prop_mask.any()


def test_dst_projection_joins_dk_and_schedule_team_aliases():
    from nfl_dfs.inference.dst_projections import build_rows

    slate = pd.DataFrame({
        "dk_player_id": [343], "display_name": ["Rams"],
        "team_abbr": ["LAR"], "salary": [3000],
        "draft_group_id": [151307],
    })
    trailing = pd.DataFrame({"team": ["LA"], "dst_l4": [7.5]})
    opponents = pd.DataFrame({
        "team": ["LA"], "opponent": ["HOU"], "opp_implied": [20.0],
    })
    qb = pd.DataFrame({"team": ["HOU"], "career_starts": [40]})

    row = build_rows(slate, trailing, opponents, qb, 2026, 1, "vtest").iloc[0]

    assert row.team == "LAR"
    assert row.opponent == "HOU"
    assert row.proj_points != 6.0


def test_combined_projection_write_has_one_batch_timestamp():
    from datetime import datetime, timezone

    from nfl_dfs.inference.run_projections import _stamp_projection_batch

    frame = pd.DataFrame({
        "position": ["WR", "DST"],
        "generated_at": [
            "2026-09-04T08:49:38Z",
            "2026-09-04T08:49:45Z",
        ],
    })
    batch_at = datetime(2026, 9, 4, 9, 0, tzinfo=timezone.utc)

    stamped = _stamp_projection_batch(frame, batch_at)

    assert stamped.generated_at.nunique() == 1
    assert stamped.generated_at.iloc[0] == batch_at
    assert frame.generated_at.nunique() == 2


def test_projection_accepts_none_policy_env_and_uses_dk_ppg(monkeypatch):
    from types import SimpleNamespace

    from nfl_dfs import notes
    from nfl_dfs.inference import run_projections
    from nfl_dfs.models import prop_market

    feats = pd.DataFrame({
        "gsis_id": ["p1", "p2"],
        "display_name": ["One", "Two"],
        "position": ["WR", "RB"],
        "team": ["A", "B"],
        "opponent": ["B", "A"],
        "salary": [6_000, 5_000],
        "dk_player_id": [1, 2],
        "dk_ppg": [20.0, 8.0],
    })
    summary = pd.DataFrame({
        "proj_points": [10.0, 12.0],
        "proj_p10": [5.0, 6.0],
        "proj_p50": [10.0, 12.0],
        "proj_p90": [20.0, 22.0],
        "proj_std": [4.0, 5.0],
        "p_20_plus": [0.2, 0.3],
    })
    seen: dict[str, object] = {}

    class FakeModel:
        def predict_components(self, frame):
            assert frame.gsis_id.tolist() == ["p1", "p2"]
            return object()

    monkeypatch.setattr(
        run_projections.coldstart,
        "fill_cold_start_features",
        lambda frame: frame.copy(),
    )
    monkeypatch.setattr(
        run_projections.coldstart,
        "widen_cold_start_quantiles",
        lambda frame, _flags: frame,
    )
    monkeypatch.setattr(notes, "apply_notes", lambda comps, *args: comps)

    def fake_simulate(comps, **kwargs):
        seen["env"] = kwargs.get("env")
        return SimpleNamespace(summary=summary.copy())

    monkeypatch.setattr(run_projections.simulate, "simulate", fake_simulate)
    monkeypatch.setattr(
        run_projections.calibration,
        "apply_widen",
        lambda frame, _positions: frame.copy(),
    )
    monkeypatch.setattr(
        prop_market,
        "market_points",
        lambda _seasons: pd.DataFrame(
            columns=["season", "week", "gsis_id", "market_points"]
        ),
    )
    monkeypatch.setattr(
        run_projections.cascade_adjust,
        "zero_out_projections",
        lambda frame, _out_ids: frame,
    )
    monkeypatch.delenv("BLEND_MODEL_WEIGHT", raising=False)

    out = run_projections.project(
        feats,
        FakeModel(),
        "test-model",
        2026,
        1,
        n_sims=10,
        policy_env=None,
    )

    assert seen["env"] is None
    assert out.proj_points.to_numpy() == pytest.approx([
        0.45 * 10.0 + 0.55 * 20.0,
        0.45 * 12.0 + 0.55 * 8.0,
    ])


@pytest.fixture()
def live_slate(panel):
    season = int(panel.season.max())
    rows = panel[(panel.season == season) & (panel.week == 3)].head(60).copy()
    rows = rows.reset_index(drop=True)
    rows["dk_player_id"] = np.arange(100, 100 + len(rows))
    rows["display_name"] = ["P" + str(i) for i in range(len(rows))]
    rows["dk_position"] = rows.position
    rows["salary"] = np.clip(3000 + (np.arange(len(rows)) % 40) * 130,
                             3000, 8100)
    # Balance every position across teams. Assigning team by raw row index
    # makes each synthetic team accidentally contain only one position
    # because the panel alternates QB/RB/WR/TE.
    seen = {p: 0 for p in ("QB", "RB", "WR", "TE")}
    teams = []
    for pos in rows.position:
        teams.append(f"T{seen[pos] % 8}")
        seen[pos] += 1
    rows["team"] = teams
    team_ix = [int(t[1:]) for t in teams]
    rows["opponent"] = [f"T{i ^ 1}" for i in team_ix]
    rows["game_id"] = [f"g{i // 2}" for i in team_ix]
    rows["game_total"] = 45.0
    rows["status"] = None
    return rows


def test_live_build_chain_offline(monkeypatch, panel, live_slate):
    from nfl_dfs.inference import live_lineups
    from nfl_dfs.models import components
    from nfl_dfs.optimizer.lineup import StackRules

    season = int(panel.season.max())
    monkeypatch.setenv("MODEL_ENSEMBLE", "2")  # exercise ensemble path, fast
    cm = components.train(panel, target_season=season, num_boost_round=15)
    monkeypatch.setattr(
        "nfl_dfs.models.train_job.load_latest_component_models",
        lambda: (cm, "test/components/w1"))
    monkeypatch.setattr(
        "nfl_dfs.inference.run_projections.upcoming_slate_features",
        lambda s, w: live_slate)
    # BQ touchpoints -> empty (tabpfn cache missing, notes absent)
    import nfl_dfs.bq as bqmod
    monkeypatch.setattr(bqmod, "query_df",
                        lambda sql, **k: pd.DataFrame())
    # market blend -> no market rows; dst -> none; booster -> unavailable
    monkeypatch.setattr("nfl_dfs.models.blend.market_projection_frame",
                        lambda df: pd.Series(np.nan, index=df.index))
    from nfl_dfs.backtest import replay as rp
    monkeypatch.setattr(rp, "_ownership_booster", lambda s: None)
    monkeypatch.setattr(rp, "punt_boom_flags_live",
                        lambda s, w: set(), raising=False)
    import nfl_dfs.inference.dst_projections as dstm
    dst = pd.DataFrame({
        "dk_player_id": [900, 901, 902, 903],
        "display_name": ["D0", "D1", "D2", "D3"],
        "team": ["T0", "T2", "T4", "T6"],
        "opponent": ["T1", "T3", "T5", "T7"],
        "salary": [2800, 3000, 3200, 3400],
        "proj_points": [6.0, 5.5, 7.0, 6.5]})
    monkeypatch.setattr(dstm, "project_dst",
                        lambda s, w, model_version=None: dst,
                        raising=False)

    lineups = live_lineups.build_sim_lineups(
        season, 3, n_entries=4, stack=None, tail_line=150.0,
        n_sims=300, seed=7)
    assert len(lineups) == 4
    for lu in lineups:
        assert len(lu.players) == 9
        assert lu.salary <= 50_000
        ids = [p["id"] for p in lu.players]
        assert len(ids) == len(set(ids))

    # A selected classic draft group can price an overlapping player
    # differently from the largest-group row used to source live features.
    # The exact chosen snapshot must win before salary-sensitive tilts.
    slate, _ = live_lineups.build_slate_with_draws(
        season, 3, n_sims=20, seed=7, salary_overrides={100: 4321})
    assert int(slate.loc[slate.id == 100, "salary"].iloc[0]) == 4321

    # The stored projection path retains known inactive rows at zero, but the
    # live simulator must exclude them before component sampling.  A selected
    # DK slate still lists O/IR players, so allowed_ids cannot be the gate.
    out_index = live_slate.index[live_slate.position.eq("WR")][0]
    out_id = int(live_slate.loc[out_index, "dk_player_id"])
    live_slate.loc[out_index, "status"] = "O"
    active_skill = len(live_slate) - 1
    inactive_slate, inactive_draws = live_lineups.build_slate_with_draws(
        season, 3, n_sims=20, seed=7,
        allowed_ids=set(live_slate.dk_player_id.astype(int)) | {out_id},
    )
    assert out_id not in set(inactive_slate.id)
    assert inactive_draws.shape == (active_skill, 20)


def test_live_inactive_policy_redistributes_once_then_excludes(monkeypatch):
    from nfl_dfs.inference import live_lineups, run_projections

    skill = pd.DataFrame({
        "gsis_id": ["out-player", "active-player"],
        "display_name": ["Out", "Active"],
        "dk_position": ["WR", "WR"],
        "team": ["A", "A"],
        "status": ["O", None],
        "target_share_l4": [0.30, 0.20],
    })
    calls = []

    def fake_adjust(frame):
        calls.append(tuple(frame.gsis_id))
        adjusted = frame.copy()
        adjusted.loc[adjusted.gsis_id.eq("active-player"),
                     "target_share_l4"] += 0.10
        return adjusted, ["out-player"]

    monkeypatch.setattr(
        run_projections, "_cascade_adjuster", lambda season: fake_adjust
    )
    active, out_ids = live_lineups._apply_live_inactive_policy(skill, 2026)

    assert calls == [("out-player", "active-player")]
    assert out_ids == ("out-player",)
    assert active.gsis_id.tolist() == ["active-player"]
    assert active.target_share_l4.tolist() == pytest.approx([0.30])


def test_adopted_policy_builds_true80_dk_csv(monkeypatch, panel, live_slate):
    """Pre-season gate: exact adopted policy through the real live builder
    and generic DK export, with only external registry/BQ inputs mocked."""
    from nfl_dfs.inference import live_lineups
    from nfl_dfs.inference.production_policy import ADOPTED_CLASSIC_POLICY
    from nfl_dfs.models import components
    from nfl_dfs.optimizer.export import to_dk_csv
    from nfl_dfs.optimizer.lineup import StackRules

    season = int(panel.season.max())
    monkeypatch.setenv("MODEL_ENSEMBLE", "1")
    cm = components.train(panel, target_season=season, num_boost_round=12)
    monkeypatch.setenv(
        "EXTRA_FEATURES", ADOPTED_CLASSIC_POLICY.role_features)
    cm_role = components.train(
        panel, target_season=season, num_boost_round=12)
    monkeypatch.delenv("EXTRA_FEATURES")
    monkeypatch.setattr(
        "nfl_dfs.models.train_job.load_latest_component_models",
        lambda variant=None: (
            (cm_role, "pooled/components__tail_k1_role/2026-W36")
            if variant == "tail_k1_role"
            else (cm, "pooled/components__tail_k1/2026-W36")))
    monkeypatch.setattr(
        "nfl_dfs.inference.run_projections.upcoming_slate_features",
        lambda s, w: live_slate)
    import nfl_dfs.bq as bqmod
    monkeypatch.setattr(bqmod, "query_df", lambda sql, **k: pd.DataFrame())
    monkeypatch.setattr("nfl_dfs.models.blend.market_projection_frame",
                        lambda df: pd.Series(np.nan, index=df.index))
    from nfl_dfs.backtest import replay as rp
    monkeypatch.setattr(rp, "_ownership_booster", lambda s: None)
    import nfl_dfs.inference.dst_projections as dstm
    dst = pd.DataFrame({
        "dk_player_id": [900, 901, 902, 903],
        "display_name": ["D0", "D1", "D2", "D3"],
        "team": ["T0", "T2", "T4", "T6"],
        "opponent": ["T1", "T3", "T5", "T7"],
        "salary": [2800, 3000, 3200, 3400],
        "proj_points": [6.0, 5.5, 7.0, 6.5]})
    monkeypatch.setattr(dstm, "project_dst",
                        lambda s, w, model_version=None: dst)

    policy = ADOPTED_CLASSIC_POLICY
    policy_env = policy.engine_environment()
    # Keep the full five-search/five-world orchestration while using compact
    # world blocks in this offline integration test.
    policy_env["MULTISEED_WORLDS_PER_BLOCK"] = "300"
    lineups = live_lineups.build_sim_lineups(
        season, 3, n_entries=policy.default_entries,
        stack=StackRules(qb_stack_min=2, bring_back_min=1),
        tail_line=policy.tail_line, n_sims=300, seed=7,
        apply_notes=False, model_variant=policy.model_variant,
        belief_model_variant=policy.role_model_variant,
        expected_model_k=policy.model_ensemble,
        policy_env=policy_env)
    assert len(lineups) == 80
    assert all(lu.salary >= 49_000 for lu in lineups)
    assert all(getattr(lu, "model_version", "").endswith("2026-W36")
               for lu in lineups)
    csv_text = to_dk_csv(lineups)
    assert len(csv_text.strip().splitlines()) == 81
