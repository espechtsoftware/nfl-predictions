#!/usr/bin/env python
"""Fail closed unless a Phase S execution describes its registered cell."""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any


PROJECT = "nfl-predictions-503414"
SEEDS = {
    0: (0, 7331),
    1: (1137260708, 2690847602),
    2: (2875959182, 1630284992),
    3: (253722715, 3374646876),
    4: (1643280042, 3977633467),
}
POSITION_SPECS = {
    2023: "QB:0.965,RB:0.99,TE:0.945,WR:1.03",
    2024: "QB:0.905,RB:0.97,TE:0.95,WR:1.06",
    2025: "QB:0.925,RB:0.96,TE:0.94,WR:1.04",
}
ROLE_FEATURES = (
    "target_share_last,carry_share_last,snap_share_last,"
    "target_share_jump,carry_share_jump,snap_share_jump"
)
FITTED_K = "28.154043586960896"
FROZEN_BETA = "0.07771181538347656"


def _environment(container: dict[str, Any]) -> tuple[dict[str, str], list[str]]:
    values: dict[str, str] = {}
    failures: list[str] = []
    for item in container.get("env", []):
        name = str(item.get("name", ""))
        if not name:
            failures.append("execution has an unnamed environment variable")
        elif name in values:
            failures.append(f"execution repeats environment variable {name}")
        elif "value" not in item:
            failures.append(f"execution environment variable {name} has no value")
        else:
            values[name] = str(item["value"])
    return values, failures


def _completed_status(execution: dict[str, Any]) -> str:
    for condition in execution.get("status", {}).get("conditions", []):
        if condition.get("type") == "Completed":
            return str(condition.get("status", ""))
    return ""


def execution_failures(
    execution: dict[str, Any], *, arm: str, replicate: int, season: int,
    panel: str, job: str, execution_name: str, image: str, code_sha: str,
    control_arm: str, require_success: bool = True,
) -> list[str]:
    """Return every provenance/status mismatch for one registered cell."""
    failures: list[str] = []
    expected_panel = f"20260813-sis-asoe-{arm}-r{replicate}-v1"
    family = f"sisasoe{arm[0]}{replicate}"
    expected_job = f"replay-{family}-{season}"
    if panel != expected_panel:
        failures.append(f"ledger panel {panel} != registered {expected_panel}")
    if job != expected_job:
        failures.append(f"ledger job {job} != registered {expected_job}")

    metadata = execution.get("metadata", {})
    if metadata.get("name") != execution_name:
        failures.append("execution name differs from ledger")
    labels = metadata.get("labels", {})
    if labels.get("run.googleapis.com/job") != job:
        failures.append("execution-owned job differs from ledger")

    try:
        template = execution["spec"]["template"]["spec"]
        containers = template["containers"]
        container = containers[0]
    except (KeyError, IndexError, TypeError):
        return failures + ["execution container specification is missing"]
    if len(containers) != 1:
        failures.append("execution does not contain exactly one container")
    if container.get("image") != image:
        failures.append("execution image digest differs from manifest")
    if container.get("command") != ["nfl-dfs"]:
        failures.append("execution command differs")
    expected_args = [
        "replay", "--season", str(season), "--contest", "gpp",
        "--entries", "80",
    ]
    if container.get("args") != expected_args:
        failures.append("execution replay arguments differ")
    limits = container.get("resources", {}).get("limits", {})
    if str(limits.get("cpu", "")) != "8" or limits.get("memory") != "32Gi":
        failures.append("execution resource shape differs from 8 CPU / 32 GiB")
    if int(template.get("maxRetries", -1)) != 0:
        failures.append("execution maxRetries differs from zero")
    if str(template.get("timeoutSeconds", "")) != "14400":
        failures.append("execution timeout differs from 14400 seconds")

    env, env_failures = _environment(container)
    failures.extend(env_failures)
    base_seed, role_seed = SEEDS[replicate]
    expected_env = {
        "GCP_PROJECT": PROJECT,
        "GAME_SIM_MODE": "possession",
        "MODEL_ENSEMBLE": "1",
        "TABPFN_MARGINALS": "1",
        "TABPFN_MARGINAL_TABLE": "tabpfn_active_label_treatment_v2",
        "EPISTEMIC_FAMILY": "role_draws",
        "ROLE_BELIEF_FEATURES": ROLE_FEATURES,
        "ROLE_BELIEF_SEED": str(role_seed),
        "REPLAY_PROJECTION_SEED": str(base_seed),
        "REPLACEMENT_SLOTS": "12",
        "N_CE": "0",
        "N_EPISTEMIC": "12",
        "N_GUMBEL": "0",
        "N_BOOM": "40",
        "SERVED_POSITION_SCALES": POSITION_SPECS[season],
        "PANEL_RUN_ID": panel,
        "CODE_SHA": code_sha,
        "CAND_LOG_TABLE": (
            f"{PROJECT}.nfl_predictions.replay_candidates_staging"
        ),
        "CAND_FEATURE_TABLE": (
            f"{PROJECT}.nfl_predictions.slate_player_features"
        ),
        "CAND_ARTIFACT_BUCKET": f"{PROJECT}-raw",
        "CAND_ARTIFACT_PLAYER_WORLDS": "1",
        "REPLAY_LINEUPS_TABLE": (
            f"{PROJECT}.nfl_features.replay_lineups_{family}_{season}"
        ),
    }
    if control_arm == "k":
        expected_env.update({
            "GAME_SIM_USAGE": "dirichlet", "DIRICHLET_K": FITTED_K,
        })
    for name, value in expected_env.items():
        if env.get(name) != value:
            failures.append(f"execution environment {name} differs")
    if control_arm == "mult":
        for name in ("GAME_SIM_USAGE", "DIRICHLET_K"):
            if name in env:
                failures.append(f"multinomial execution unexpectedly sets {name}")
    if arm == "treatment":
        if env.get("SIS_ASOE_TARGET_ALLOCATION") != "1":
            failures.append("treatment does not enable SIS ASOE")
        if env.get("SIS_ASOE_BETA") != FROZEN_BETA:
            failures.append("treatment SIS ASOE beta differs")
    else:
        for name in ("SIS_ASOE_TARGET_ALLOCATION", "SIS_ASOE_BETA"):
            if name in env:
                failures.append(f"control unexpectedly sets {name}")

    if require_success:
        status = execution.get("status", {})
        if _completed_status(execution) != "True":
            failures.append("execution is not a clean terminal success")
        if int(status.get("succeededCount", 0) or 0) != 1:
            failures.append("execution succeededCount differs from one")
        if int(status.get("failedCount", 0) or 0) != 0:
            failures.append("execution failedCount differs from zero")
    return failures


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--arm", choices=("control", "treatment"), required=True)
    parser.add_argument("--replicate", type=int, choices=SEEDS, required=True)
    parser.add_argument("--season", type=int, choices=POSITION_SPECS, required=True)
    parser.add_argument("--panel", required=True)
    parser.add_argument("--job", required=True)
    parser.add_argument("--execution", required=True)
    parser.add_argument("--image", required=True)
    parser.add_argument("--code-sha", required=True)
    parser.add_argument("--control-arm", choices=("mult", "k"), required=True)
    parser.add_argument("--allow-nonterminal", action="store_true")
    args = parser.parse_args()
    execution = json.load(sys.stdin)
    failures = execution_failures(
        execution, arm=args.arm, replicate=args.replicate,
        season=args.season, panel=args.panel, job=args.job,
        execution_name=args.execution, image=args.image,
        code_sha=args.code_sha, control_arm=args.control_arm,
        require_success=not args.allow_nonterminal,
    )
    if failures:
        for failure in failures:
            print(f"EXECUTION_PROVENANCE_FAILURE {failure}", file=sys.stderr)
        return 2
    print(
        "EXECUTION_PROVENANCE_VERIFIED "
        f"{args.arm} R{args.replicate} {args.season} {args.execution}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
