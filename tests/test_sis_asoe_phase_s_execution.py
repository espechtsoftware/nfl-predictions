import importlib.util
from pathlib import Path


SPEC = importlib.util.spec_from_file_location(
    "_sis_asoe_phase_s_execution",
    Path(__file__).parents[1]
    / "scripts"
    / "verify_sis_asoe_phase_s_execution.py",
)
execution_check = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(execution_check)


IMAGE = "us-central1-docker.pkg.dev/project/repository/image@sha256:abc"
CODE_SHA = "4d6f5cf"


def _execution(arm="control", replicate=3, season=2024, control_arm="k"):
    family = f"sisasoe{arm[0]}{replicate}"
    panel = f"20260813-sis-asoe-{arm}-r{replicate}-v1"
    job = f"replay-{family}-{season}"
    name = f"{job}-abcde"
    base_seed, role_seed = execution_check.SEEDS[replicate]
    values = {
        "GCP_PROJECT": execution_check.PROJECT,
        "GAME_SIM_MODE": "possession",
        "MODEL_ENSEMBLE": "1",
        "TABPFN_MARGINALS": "1",
        "TABPFN_MARGINAL_TABLE": "tabpfn_active_label_treatment_v2",
        "EPISTEMIC_FAMILY": "role_draws",
        "ROLE_BELIEF_FEATURES": execution_check.ROLE_FEATURES,
        "ROLE_BELIEF_SEED": str(role_seed),
        "REPLAY_PROJECTION_SEED": str(base_seed),
        "REPLACEMENT_SLOTS": "12",
        "N_CE": "0",
        "N_EPISTEMIC": "12",
        "N_GUMBEL": "0",
        "N_BOOM": "40",
        "SERVED_POSITION_SCALES": execution_check.POSITION_SPECS[season],
        "PANEL_RUN_ID": panel,
        "CODE_SHA": CODE_SHA,
        "CAND_LOG_TABLE": (
            f"{execution_check.PROJECT}.nfl_predictions."
            "replay_candidates_staging"
        ),
        "CAND_FEATURE_TABLE": (
            f"{execution_check.PROJECT}.nfl_predictions."
            "slate_player_features"
        ),
        "CAND_ARTIFACT_BUCKET": f"{execution_check.PROJECT}-raw",
        "CAND_ARTIFACT_PLAYER_WORLDS": "1",
        "REPLAY_LINEUPS_TABLE": (
            f"{execution_check.PROJECT}.nfl_features."
            f"replay_lineups_{family}_{season}"
        ),
    }
    if control_arm == "k":
        values.update({
            "GAME_SIM_USAGE": "dirichlet",
            "DIRICHLET_K": execution_check.FITTED_K,
        })
    if arm == "treatment":
        values.update({
            "SIS_ASOE_TARGET_ALLOCATION": "1",
            "SIS_ASOE_BETA": execution_check.FROZEN_BETA,
        })
    payload = {
        "metadata": {
            "name": name,
            "labels": {"run.googleapis.com/job": job},
        },
        "spec": {"template": {"spec": {
            "containers": [{
                "args": [
                    "replay", "--season", str(season), "--contest", "gpp",
                    "--entries", "80",
                ],
                "command": ["nfl-dfs"],
                "env": [
                    {"name": key, "value": value}
                    for key, value in values.items()
                ],
                "image": IMAGE,
                "resources": {"limits": {"cpu": "8", "memory": "32Gi"}},
            }],
            "maxRetries": 0,
            "timeoutSeconds": "14400",
        }}},
        "status": {
            "conditions": [{"type": "Completed", "status": "True"}],
            "succeededCount": 1,
        },
    }
    expected = {
        "arm": arm,
        "replicate": replicate,
        "season": season,
        "panel": panel,
        "job": job,
        "execution_name": name,
        "image": IMAGE,
        "code_sha": CODE_SHA,
        "control_arm": control_arm,
    }
    return payload, expected


def test_all_registered_cells_verify_from_their_own_execution_spec():
    for control_arm in ("mult", "k"):
        for arm in ("control", "treatment"):
            for replicate in execution_check.SEEDS:
                for season in execution_check.POSITION_SPECS:
                    payload, expected = _execution(
                        arm, replicate, season, control_arm
                    )
                    assert not execution_check.execution_failures(
                        payload, **expected
                    )


def test_seed_or_cell_substitution_fails_closed():
    payload, expected = _execution()
    for item in payload["spec"]["template"]["spec"]["containers"][0]["env"]:
        if item["name"] == "ROLE_BELIEF_SEED":
            item["value"] = "7331"
    failures = execution_check.execution_failures(payload, **expected)
    assert "execution environment ROLE_BELIEF_SEED differs" in failures


def test_wrong_ledger_execution_and_missing_treatment_flag_fail_closed():
    payload, expected = _execution("treatment", 1, 2025)
    expected["execution_name"] = "some-other-execution"
    payload["spec"]["template"]["spec"]["containers"][0]["env"] = [
        item
        for item in payload["spec"]["template"]["spec"]["containers"][0]["env"]
        if item["name"] != "SIS_ASOE_TARGET_ALLOCATION"
    ]
    failures = execution_check.execution_failures(payload, **expected)
    assert "execution name differs from ledger" in failures
    assert "treatment does not enable SIS ASOE" in failures


def test_nonterminal_execution_is_only_allowed_for_prelaunch_provenance_check():
    payload, expected = _execution()
    payload["status"] = {
        "conditions": [{"type": "Completed", "status": "Unknown"}]
    }
    assert execution_check.execution_failures(payload, **expected)
    assert not execution_check.execution_failures(
        payload, require_success=False, **expected
    )
