"""Lever-registry completeness: every score-relevant environment read in the
simulation/generation path must be registered in the immutable lever set or
explicitly exempted as infrastructure/provenance.

Motivation (2026-08-18, N5): SCRIPT_FEEDBACK and SCHAAKE_K were live sim-path
reads absent from the registry, and an audit found nine optimizer knobs with
the same gap — the defect class that made panel 20260806-universe-baseline-
81b7ff3 non-self-identifying (its lever record omitted EXTRA_FEATURES).
"""
from __future__ import annotations

import inspect
import re

from nfl_dfs.backtest import engine, replay
from nfl_dfs.models import game_sim, simulate
from nfl_dfs.optimizer import lineup
from nfl_dfs.research import schaake_diag

# Modules whose environment reads can change projections, simulation,
# candidate generation, or selection.  Extend this list when a new module
# joins the sim/generation path.
SIM_PATH_MODULES = (game_sim, simulate, replay, engine, lineup, schaake_diag)

# Receivers that denote an environment mapping in this codebase:
# os.environ / _os.environ / __import__("os").environ, plus the
# request-local mapping aliases used by production paths.
_ENV_READ = re.compile(
    r'\b(?:environ|runtime_env|env|e|source|_env)\s*\.\s*get\(\s*'
    r'"([A-Z][A-Z0-9_]*)"'
)


def _read_keys() -> set[str]:
    keys: set[str] = set()
    for module in SIM_PATH_MODULES:
        keys.update(_ENV_READ.findall(inspect.getsource(module)))
    return keys


def test_every_sim_path_env_read_is_registered_or_exempt():
    keys = _read_keys()
    assert keys, "scanner found no environment reads; the regex is broken"
    overlap = engine._lever_keys & engine._lever_exempt_keys
    assert not overlap, f"keys both registered and exempt: {sorted(overlap)}"
    unregistered = keys - set(engine._lever_keys) - engine._lever_exempt_keys
    assert not unregistered, (
        "score-relevant environment reads missing from the lever registry "
        f"(register in engine._lever_keys or, for pure infrastructure, "
        f"exempt with a justification): {sorted(unregistered)}"
    )


def test_previous_registry_gaps_stay_closed():
    # The exact keys the 2026-08-18 audit found missing.
    for key in (
        "SCRIPT_FEEDBACK", "SCHAAKE_K", "MAX_PER_GAME", "MIN_LOWOWN",
        "OWN_BARBELL_HIGH", "OWN_BARBELL_LOW", "OWN_BARBELL_NHIGH",
        "OWN_BARBELL_NLOW", "PUNT_MAX", "VALUE2_MAX", "VALUE2_MIN",
    ):
        assert key in engine._lever_keys, key


def test_boom_unique_fill_lever_is_registered():
    assert "BOOM_UNIQUE_FILL" in engine._lever_keys
    assert "OPEN_BOOM_SOLVES" in engine._lever_keys
    assert "SINGLE_STACK_BOOM_SOLVES" in engine._lever_keys


def test_exempt_keys_are_infrastructure_only():
    # The exemption list is a frozen, deliberately short partition; growing
    # it should be a conscious edit here, never a convenience.
    assert engine._lever_exempt_keys == frozenset({
        "CAND_ARTIFACT_BUCKET", "CAND_FEATURE_TABLE", "CAND_LOG_TABLE",
        "CODE_SHA", "PANEL_RUN_ID", "REPLAY_LINEUPS_TABLE", "SEEDS",
    })
