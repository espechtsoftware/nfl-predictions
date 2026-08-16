"""Frozen environment contract for ATLAS production-law world acquisition."""

from __future__ import annotations

from hashlib import sha256
import json
import re
from typing import Mapping

from nfl_dfs.inference.production_policy import ADOPTED_CLASSIC_POLICY


VERSION = "atlas-current-money-worlds-v1"
RUN_ID = "20260815-atlas-current-money-worlds-v1"
SEED_PAIRS = (
    (0, 7331),
    (1137260708, 2690847602),
    (2875959182, 1630284992),
    (253722715, 3374646876),
    (1643280042, 3977633467),
)
PROTOCOL_PATH = "reports/2026-08-15-atlas-current-money-transfer-protocol.md"


def panel_id(block: int) -> str:
    """Return the immutable source-panel identity for one registered block."""
    if not 0 <= int(block) < len(SEED_PAIRS):
        raise ValueError("ATLAS money block must be in 0..4")
    return f"20260815-atlas-money-worlds-r{int(block)}-v1"


def canonical_policy_receipt() -> dict:
    """Return and validate the exact public money-policy environment receipt."""
    identity = ADOPTED_CLASSIC_POLICY.public_identity()
    law = identity["simulation_law"]
    expected_law = {
        "game_mode": "possession",
        "team_factors": True,
        "usage_allocation": "production-multinomial",
        "game_sim_usage_env": "",
        "dirichlet_k": None,
        "td_ledger": False,
    }
    if law != expected_law:
        raise RuntimeError("ATLAS money transfer policy law differs")
    receipt = identity["engine_environment_receipt"]
    env = receipt["values"]
    if env.get("GAME_SIM_USAGE") or env.get("TD_LEDGER") or \
            "DIRICHLET_K" in env or env.get("TABPFN_MARGINAL_TABLE") or \
            env.get("SIS_ASOE_TARGET_ALLOCATION"):
        raise RuntimeError("ATLAS money transfer policy has research leakage")
    return {
        "policy_id": identity["policy_id"],
        "simulation_law": law,
        "engine_environment_sha256": receipt["sha256"],
        "engine_environment": dict(env),
    }


def acquisition_environment(
    *, block: int, season: int, code_sha: str, project: str,
) -> dict[str, str]:
    """Build one exact, single-block replay environment.

    Production's multi-block wrapper is disabled because each immutable
    artifact must represent exactly one registered random block. No player-
    world law is changed by that diagnostic-only override.
    """
    block = int(block)
    season = int(season)
    if season not in {2023, 2024, 2025}:
        raise ValueError("ATLAS money acquisition season must be 2023..2025")
    if not re.fullmatch(r"[0-9a-f]{40}", str(code_sha)):
        raise ValueError("ATLAS money acquisition needs a full code SHA")
    if not re.fullmatch(r"[a-z][a-z0-9-]{4,62}", str(project)):
        raise ValueError("ATLAS money acquisition project is invalid")
    panel = panel_id(block)
    projection_seed, role_seed = SEED_PAIRS[block]
    base = {
        "GCP_PROJECT": project,
        "CAND_LOG_TABLE": f"{project}.nfl_predictions.replay_candidates_staging",
        "CAND_ARTIFACT_BUCKET": f"{project}-raw",
        "CAND_ARTIFACT_PLAYER_WORLDS": "1",
        "PANEL_RUN_ID": panel,
        "CODE_SHA": str(code_sha),
        "SEEDS": (
            f"REPLAY_PROJECTION_SEED={projection_seed};"
            f"ROLE_BELIEF_SEED={role_seed}"
        ),
    }
    env = ADOPTED_CLASSIC_POLICY.engine_environment(base)
    env.update({
        "MULTISEED_PORTFOLIO": "",
        "MULTISEED_SEED_PAIRS": "",
        "MULTISEED_WORLDS_PER_BLOCK": "",
        "MULTISEED_CANDIDATE_ENTRY_BASIS": "",
        "REPLAY_PROJECTION_SEED": str(projection_seed),
        "ROLE_BELIEF_SEED": str(role_seed),
        "CAND_FEATURE_TABLE": (
            f"{project}.nfl_predictions.slate_player_features"
        ),
        "REPLAY_LINEUPS_TABLE": (
            f"{project}.nfl_features.replay_lineups_atlasmoney_"
            f"r{block}_{season}"
        ),
    })
    forbidden_active = {
        "GAME_SIM_USAGE", "DIRICHLET_K", "TD_LEDGER",
        "SIS_ASOE_BETA", "SIS_ASOE_TARGET_ALLOCATION",
    }
    active = {
        key for key in forbidden_active
        if str(env.get(key, "")).strip()
    }
    if active:
        raise RuntimeError(
            "ATLAS money acquisition has active research levers: "
            + ", ".join(sorted(active))
        )
    return dict(sorted((key, str(value)) for key, value in env.items()))


def environment_receipt(env: Mapping[str, str]) -> dict:
    """Return a stable receipt for one full Cloud Run environment."""
    values = dict(sorted((str(key), str(value)) for key, value in env.items()))
    payload = json.dumps(values, sort_keys=True, separators=(",", ":")).encode()
    return {"sha256": sha256(payload).hexdigest(), "values": values}


def gcloud_environment(env: Mapping[str, str], delimiter: str = "|") -> str:
    """Serialize a validated environment for gcloud's alternate delimiter."""
    if len(delimiter) != 1 or delimiter in "=\n\r":
        raise ValueError("ATLAS gcloud delimiter is invalid")
    values = dict(sorted((str(key), str(value)) for key, value in env.items()))
    if any(delimiter in key or delimiter in value or "\n" in value
           or "\r" in value for key, value in values.items()):
        raise ValueError("ATLAS environment cannot be serialized safely")
    return delimiter.join(f"{key}={value}" for key, value in values.items())


def parse_logged_lever_environment(text: str) -> dict[str, str]:
    """Parse the candidate logger's comma-delimited scientific receipt.

    Some values themselves contain commas, so separators are recognized only
    when followed by another uppercase environment key.
    """
    raw = str(text)
    parts = re.split(r",(?=[A-Z][A-Z0-9_]*=)", raw) if raw else []
    result: dict[str, str] = {}
    for part in parts:
        key, marker, value = part.partition("=")
        if not marker or not re.fullmatch(r"[A-Z][A-Z0-9_]*", key) or \
                key in result:
            raise ValueError("ATLAS logged lever environment is malformed")
        result[key] = value
    return result


def expected_logged_source_environment(block: int) -> dict[str, str]:
    """Return the required score-facing lever subset for one source block."""
    block = int(block)
    panel_id(block)
    projection_seed, role_seed = SEED_PAIRS[block]
    return {
        "CAND_ARTIFACT_PLAYER_WORLDS": "1",
        "EPISTEMIC_FAMILY": "role_draws",
        "GAME_SIM_MODE": "possession",
        "GAME_SIM_TEAM_FACTORS": "1",
        "GAME_SIM_USAGE": "",
        "MODEL_ENSEMBLE": "1",
        "MODEL_REGISTRY_VARIANT": "tail_k1",
        "MULTISEED_CANDIDATE_ENTRY_BASIS": "",
        "MULTISEED_PORTFOLIO": "",
        "MULTISEED_SEED_PAIRS": "",
        "MULTISEED_WORLDS_PER_BLOCK": "",
        "REPLAY_PROJECTION_SEED": str(projection_seed),
        "ROLE_BELIEF_SEED": str(role_seed),
        "SERVED_POSITION_SCALES": (
            "QB:0.970,RB:1.005,TE:0.940,WR:1.070"
        ),
        "SIM_WIDEN_DRAWS": "fitted",
        "TABPFN_MARGINALS": "1",
        "TABPFN_MARGINAL_TABLE": "",
        "TD_LEDGER": "",
    }


def source_environment_lever_text(
    environment: Mapping[str, str], block: int,
) -> str:
    """Create a labeled lever receipt from a verified execution environment."""
    expected = expected_logged_source_environment(block)
    values = {str(key): str(value) for key, value in environment.items()}
    if any(values.get(key) != value for key, value in expected.items()):
        raise ValueError("ATLAS execution source environment differs")
    return ",".join(f"{key}={expected[key]}" for key in sorted(expected))


def validate_logged_source_environment(text: str, block: int) -> dict[str, str]:
    """Verify score-facing source levers against the frozen money contract."""
    block = int(block)
    values = parse_logged_lever_environment(text)
    expected = expected_logged_source_environment(block)
    differences = {
        key: (values.get(key), value)
        for key, value in expected.items()
        if values.get(key) != value
    }
    forbidden = {
        key: value for key, value in values.items()
        if key in {
            "DIRICHLET_K", "SIS_ASOE_BETA",
            "SIS_ASOE_TARGET_ALLOCATION",
        } and str(value).strip()
    }
    if differences or forbidden:
        raise ValueError("ATLAS logged source environment differs")
    return values
