"""Shared synthetic data for model/optimizer/backtest tests.

The generator produces a plausible player-week panel with real signal
(usage drives production) so models have something to learn, plus a noisy
market projection so market-comparison code paths run.
"""

import functools
import os

import numpy as np
import pandas as pd
import pytest

POSITIONS = ["QB", "RB", "WR", "TE"]


def synthetic_panel(n_players=120, seasons=range(2018, 2025), seed=11) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    rows = []
    for p in range(n_players):
        pos = POSITIONS[p % 4]
        skill = rng.normal(0, 1)
        for season in seasons:
            team_total = rng.uniform(17, 30)
            usage = np.clip(rng.normal(0.15 + 0.05 * skill, 0.05), 0.01, 0.4)
            for week in range(1, 18):
                usage = np.clip(usage + rng.normal(0, 0.01), 0.01, 0.45)
                implied = team_total + rng.normal(0, 2)
                # True expectation: usage x game environment
                mu = 4 + 40 * usage + 0.35 * (implied - 22) + 2 * skill
                dk = max(0.0, rng.normal(mu, 6))
                rows.append({
                    "gsis_id": f"00-{p:07d}",
                    "season": season, "week": week,
                    "team": f"T{p % 32}", "opponent": f"T{(p + 7) % 32}",
                    "game_id": f"{season}_{week:02d}_T{p % 32}",
                    "position": pos,
                    "target_share_l4": usage if pos in ("WR", "TE") else usage / 3,
                    "carry_share_l4": usage if pos == "RB" else usage / 5,
                    "wopr_l4": 1.5 * usage,
                    "rz20_targets_smoothed": usage * 4,
                    "gl3_carries_smoothed": usage * (2 if pos == "RB" else 0.2),
                    "snap_share_l4": np.clip(usage * 2.2, 0, 1),
                    "dk_points_l4": mu + rng.normal(0, 2),
                    "dk_points_std": mu + rng.normal(0, 1.5),
                    "dk_points_vol": 6.0,
                    "implied_team_total": implied,
                    "spread": rng.normal(0, 5),
                    "game_total": implied * 2 + rng.normal(0, 2),
                    "expected_game_script": rng.normal(0, 4),
                    "games_played_prior": week - 1 + 17 * 2,
                    "is_home": float(rng.random() < 0.5),
                    "is_dome": float(rng.random() < 0.3),
                    "is_cold_start": 0.0,
                    "salary": int(np.clip(3000 + 320 * mu + rng.normal(0, 400), 2500, 9800)),
                    "salary_delta_wow": float(rng.normal(0, 200)),
                    # Market is a good but imperfect projection
                    "dk_ppg": mu + rng.normal(0, 2.0),
                    "injury_status": None,
                    # Role + next-man-up features (021/023). Deterministic —
                    # consuming rng draws here would shift every label below.
                    "depth_rank": (p // 4) % 3 + 1,
                    "is_rookie": False,
                    "draft_round": p % 7 + 1,
                    "team_vacated_target_share":
                        0.2 if (week % 9 == 0 and p % 5 == 0) else 0.0,
                    "ez_targets_l4": usage * 1.5,
                    "deep_targets_l4": usage * 2.0,
                    "separation_l4": 2.5 + (p % 5) * 0.2,
                    "stacked_box_l4": 20.0 + (p % 7) * 2.0,
                    "team_vacated_carry_share":
                        0.35 if (week % 11 == 0 and p % 4 == 1) else 0.0,
                    # Component labels, roughly consistent with dk points
                    "y_targets": rng.poisson(9 * usage) if pos != "QB" else 0,
                    "y_receptions": rng.poisson(6 * usage) if pos != "QB" else 0,
                    "y_rec_yards": max(0, rng.normal(70 * usage, 20)) if pos != "QB" else 0,
                    "y_rec_tds": rng.binomial(1, min(0.6, usage)) if pos != "QB" else 0,
                    "y_carries": rng.poisson(18 * usage) if pos == "RB" else 0,
                    "y_rush_yards": max(0, rng.normal(80 * usage, 25)) if pos == "RB" else 0,
                    "y_rush_tds": rng.binomial(1, min(0.5, usage * 0.8)) if pos == "RB" else 0,
                    "y_pass_attempts": rng.poisson(33) if pos == "QB" else 0,
                    "y_pass_yards": max(0, rng.normal(240, 60)) if pos == "QB" else 0,
                    "y_pass_tds": rng.poisson(1.6) if pos == "QB" else 0,
                    "y_interceptions": rng.poisson(0.7) if pos == "QB" else 0,
                    "y_dk_points": dk,
                })
    return pd.DataFrame(rows)


@pytest.fixture(scope="session")
def panel() -> pd.DataFrame:
    return synthetic_panel()


@pytest.fixture(scope="session")
def small_panel() -> pd.DataFrame:
    return synthetic_panel(n_players=60, seasons=range(2019, 2023), seed=5)


@pytest.fixture(autouse=True)
def _no_warehouse_writes_from_offline_tests(monkeypatch, request):
    """The suite is offline. On 2026-09-21 the live-lineups smoke wrote 1,558 synthetic rows into
    nfl_predictions.market_source_log (creating it) and 502 into own_shadow through the best-effort monitor writers,
    because the workstation has warehouse credentials and only ``query_df`` was stubbed. Every ``nfl_dfs.bq.load_dataframe``
    call made through the module attribute is recorded instead of executed; tests that need the real function (there
    are none offline) must opt out explicitly."""
    import nfl_dfs.bq as _bq

    recorded: list[tuple] = []

    def _record(df, table, *args, **kwargs):
        recorded.append((table, len(df) if hasattr(df, "__len__") else None))

    if request.node.get_closest_marker("real_load_dataframe"):
        # The guard's original claim that no offline test needs the real
        # function was wrong: tests/test_bq_load.py exercises load_dataframe
        # itself against a fake BigQuery client, so stubbing it there tested
        # the stub and the three assertions could never fail for a real reason.
        # The marker is the explicit opt-out this docstring already promised.
        return recorded
    monkeypatch.setattr(_bq, "load_dataframe", _record)
    return recorded


def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        "real_load_dataframe: run against the real nfl_dfs.bq.load_dataframe "
        "instead of the offline no-warehouse-writes recorder.",
    )
    config.addinivalue_line(
        "markers",
        "requires_pinned_runtime: frozen numerical chain that validates an exact "
        "interpreter/NumPy/CPU identity; skipped, with the mismatch named, on any "
        "machine that is not the pinned runtime.",
    )


@functools.lru_cache(maxsize=1)
def _pinned_runtime_mismatches() -> tuple[str, ...]:
    """Which parts of the frozen numerical runtime this machine does not match.

    The frozen corpus chains assert bit-identical numerical behaviour, which
    genuinely requires an identical runtime: the interpreter binary, the NumPy
    core binary, and the host CPU feature flags all change floating-point
    results. GitHub Actions runs Python 3.11 with ``numpy>=1.26`` on variable
    runner hardware, so those chains were never capable of passing in CI -- on
    2026-09-21 they were 184 of 365 failures, drowning the ~12 real ones.

    They are SKIPPED rather than xfailed or quarantined, and the reason names
    the exact mismatch, so this can never read as "these passed". Constants and
    live evidence both come from the contract module itself, so this check
    cannot drift away from what the chains actually assert.
    """
    try:
        from nfl_dfs.research import (
            corpus_retrieval_v2_implementation_contract as _contract,
        )
        runtime, _ = _contract._runtime_evidence()
    except Exception as exc:                      # unimportable, or no CPU evidence
        return (f"runtime evidence unavailable: {type(exc).__name__}",)

    expected = {
        "python_implementation": _contract._PYTHON_IMPLEMENTATION,
        "python_version": _contract._PYTHON_VERSION,
        "python_executable_bytes": _contract._PYTHON_EXECUTABLE_BYTES,
        "python_executable_sha256": _contract._PYTHON_EXECUTABLE_SHA256,
        "numpy_version": _contract._NUMPY_VERSION,
        "numpy_core_binary_bytes": _contract._NUMPY_CORE_BYTES,
        "numpy_core_binary_sha256": _contract._NUMPY_CORE_SHA256,
        "numpy_cpu_features_true": list(_contract._CPU_FEATURES_TRUE),
    }

    def _short(value):
        text = str(value)
        return text[:12] + "\u2026" if len(text) > 16 else text

    return tuple(
        f"{key} (pinned {_short(want)} != live {_short(runtime.get(key))})"
        for key, want in expected.items()
        if runtime.get(key) != want
    )


def pytest_collection_modifyitems(config, items):
    """Skip frozen-runtime chains when this machine is not the pinned runtime.

    Only a runtime MISMATCH skips. If the runtime matches, the chains run and a
    genuine failure still fails -- the guard narrows what CI reports, it does
    not excuse these modules from being correct.
    """
    if os.environ.get("NFL_DFS_RUN_PINNED_RUNTIME_TESTS"):
        # Deliberate override: run them anyway, e.g. under the preserved
        # interpreter (see reports/2026-09-21-portability-of-local-artifacts.md)
        # or to inspect what else in these modules is broken. It can only make
        # MORE tests run, never turn a failure into a pass.
        return
    mismatches = _pinned_runtime_mismatches()
    if not mismatches:
        return
    reason = "pinned numerical runtime not present: " + "; ".join(mismatches)
    skip = pytest.mark.skip(reason=reason)
    for item in items:
        if item.get_closest_marker("requires_pinned_runtime"):
            item.add_marker(skip)
