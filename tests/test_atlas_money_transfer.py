import json
from pathlib import Path

import pytest

from nfl_dfs.inference.production_policy import ADOPTED_CLASSIC_POLICY
from nfl_dfs.research import atlas_money_transfer as transfer


CODE_SHA = "a" * 40
PROJECT = "nfl-predictions-503414"
ROOT = Path(__file__).resolve().parents[1]


def test_canonical_receipt_is_the_public_production_multinomial_law():
    receipt = transfer.canonical_policy_receipt()
    public = ADOPTED_CLASSIC_POLICY.public_identity()
    assert receipt["policy_id"] == public["policy_id"]
    assert receipt["engine_environment_sha256"] == (
        public["engine_environment_receipt"]["sha256"]
    )
    assert receipt["simulation_law"]["usage_allocation"] == (
        "production-multinomial"
    )


@pytest.mark.parametrize("block", range(5))
@pytest.mark.parametrize("season", (2023, 2024, 2025))
def test_acquisition_environment_changes_only_single_block_plumbing(
    block, season,
):
    env = transfer.acquisition_environment(
        block=block, season=season, code_sha=CODE_SHA, project=PROJECT,
    )
    projection_seed, role_seed = transfer.SEED_PAIRS[block]
    assert env["GAME_SIM_MODE"] == "possession"
    assert env["GAME_SIM_TEAM_FACTORS"] == "1"
    assert env["GAME_SIM_USAGE"] == ""
    assert "DIRICHLET_K" not in env
    assert env["TD_LEDGER"] == ""
    assert env["TABPFN_MARGINAL_TABLE"] == ""
    assert env["SERVED_POSITION_SCALES"] == (
        "QB:0.970,RB:1.005,TE:0.940,WR:1.070"
    )
    assert env["CAND_ARTIFACT_PLAYER_WORLDS"] == "1"
    assert env["PANEL_RUN_ID"] == transfer.panel_id(block)
    assert env["REPLAY_PROJECTION_SEED"] == str(projection_seed)
    assert env["ROLE_BELIEF_SEED"] == str(role_seed)
    assert env["MULTISEED_PORTFOLIO"] == ""
    assert env["MULTISEED_SEED_PAIRS"] == ""
    assert env["MULTISEED_WORLDS_PER_BLOCK"] == ""
    assert env["MULTISEED_CANDIDATE_ENTRY_BASIS"] == ""


def test_environment_receipt_and_gcloud_serialization_are_stable():
    env = transfer.acquisition_environment(
        block=2, season=2024, code_sha=CODE_SHA, project=PROJECT,
    )
    first = transfer.environment_receipt(env)
    second = transfer.environment_receipt(dict(reversed(list(env.items()))))
    assert first == second
    assert json.loads(json.dumps(first))["values"] == env
    text = transfer.gcloud_environment(env)
    assert text.startswith("BLEND_MODEL_WEIGHT=0.45|")
    assert "|GAME_SIM_USAGE=|" in f"|{text}|"
    with pytest.raises(ValueError, match="safely"):
        transfer.gcloud_environment({"BAD": "a|b"})


@pytest.mark.parametrize("block", (-1, 5))
def test_invalid_block_is_rejected(block):
    with pytest.raises(ValueError, match="block"):
        transfer.acquisition_environment(
            block=block, season=2024, code_sha=CODE_SHA, project=PROJECT,
        )


def test_cloud_launcher_is_create_only_scorefree_and_policy_bound():
    text = (ROOT / "scripts/cloud_atlas_money_worlds.sh").read_text()
    assert "strict Phase S ATLAS harvest must complete first" in text
    assert "policy_environment_sha256=$POLICY_SHA" in text
    assert "CAND_ARTIFACT_PLAYER_WORLDS" not in text
    assert "atlas_money_world_env.py" in text
    assert "uses_realized_outcomes=false" in text
    assert "usage_allocation=production-multinomial" in text
    assert "--memory 16Gi" in text
    assert "--max-retries 0" in text
    assert "--task-timeout 4h" in text
    assert "COUNT(*) AS n" in text
