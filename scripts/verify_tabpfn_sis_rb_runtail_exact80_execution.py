#!/usr/bin/env python
"""Fail closed unless a SIS RB run-tail execution is its registered cell."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from nfl_dfs.research import tabpfn_sis_rb_runtail_lineup_v1 as experiment  # noqa: E402
from nfl_dfs.research.served_tail_lineup import ROLE_FEATURES  # noqa: E402


PROJECT = "nfl-predictions-503414"


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
    control_schedules: dict[int, str], treatment_schedules: dict[int, str],
    require_success: bool = True,
) -> list[str]:
    failures: list[str] = []
    family = f"sisrt{arm[0]}{replicate}"
    expected_panel = experiment.panel_id(arm, replicate)
    expected_job = f"replay-{family}-{season}"
    if panel != expected_panel:
        failures.append(f"ledger panel {panel} != registered {expected_panel}")
    if job != expected_job:
        failures.append(f"ledger job {job} != registered {expected_job}")
    metadata = execution.get("metadata", {})
    if metadata.get("name") != execution_name:
        failures.append("execution name differs from ledger")
    if metadata.get("labels", {}).get("run.googleapis.com/job") != job:
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
    if container.get("args") != [
        "replay", "--season", str(season), "--contest", "gpp",
        "--entries", "80",
    ]:
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
    base_seed, role_seed = experiment.SEEDS[replicate]
    table = (experiment.CONTROL_TABLE if arm == "control"
             else experiment.TREATMENT_TABLE)
    schedules = control_schedules if arm == "control" else treatment_schedules
    try:
        experiment.validate_schedule_specs(schedules)
        schedule = schedules[season]
    except (KeyError, ValueError) as exc:
        return failures + [str(exc)]
    expected_env = {
        "GCP_PROJECT": PROJECT,
        "GAME_SIM_MODE": "possession",
        "MODEL_ENSEMBLE": "1",
        "TABPFN_MARGINALS": "1",
        "TABPFN_MARGINAL_TABLE": table,
        "EPISTEMIC_FAMILY": "role_draws",
        "ROLE_BELIEF_FEATURES": ROLE_FEATURES,
        "ROLE_BELIEF_SEED": str(role_seed),
        "REPLAY_PROJECTION_SEED": str(base_seed),
        "REPLACEMENT_SLOTS": "12",
        "N_CE": "0",
        "N_EPISTEMIC": "12",
        "N_GUMBEL": "0",
        "N_BOOM": "40",
        "SERVED_POSITION_SCALES": schedule,
        "GAME_SIM_USAGE": "dirichlet",
        "DIRICHLET_K": experiment.FITTED_K,
        "PANEL_RUN_ID": panel,
        "CODE_SHA": code_sha,
        "CAND_LOG_TABLE": f"{PROJECT}.nfl_predictions.replay_candidates_staging",
        "CAND_FEATURE_TABLE": f"{PROJECT}.nfl_predictions.slate_player_features",
        "CAND_ARTIFACT_BUCKET": f"{PROJECT}-raw",
        "CAND_ARTIFACT_PLAYER_WORLDS": "1",
        "REPLAY_LINEUPS_TABLE": (
            f"{PROJECT}.nfl_features.replay_lineups_{family}_{season}"
        ),
    }
    for name, value in expected_env.items():
        if env.get(name) != value:
            failures.append(f"execution environment {name} differs")
    for name in experiment.FORBIDDEN_COMPOSITION_LEVERS:
        if name in env:
            failures.append(f"execution unexpectedly composes {name}")
    if require_success:
        status = execution.get("status", {})
        if _completed_status(execution) != "True":
            failures.append("execution is not a clean terminal success")
        if int(status.get("succeededCount", 0) or 0) != 1:
            failures.append("execution succeededCount differs from one")
        if int(status.get("failedCount", 0) or 0) != 0:
            failures.append("execution failedCount differs from zero")
    return failures


def _schedule_argument(value: str) -> dict[int, str]:
    payload = json.loads(value)
    return {int(season): str(spec) for season, spec in payload.items()}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--arm", choices=("control", "treatment"), required=True)
    parser.add_argument("--replicate", type=int, choices=experiment.SEEDS, required=True)
    parser.add_argument("--season", type=int, choices=experiment.SEASONS, required=True)
    parser.add_argument("--panel", required=True)
    parser.add_argument("--job", required=True)
    parser.add_argument("--execution", required=True)
    parser.add_argument("--image", required=True)
    parser.add_argument("--code-sha", required=True)
    parser.add_argument("--control-schedules-json", required=True)
    parser.add_argument("--treatment-schedules-json", required=True)
    parser.add_argument("--allow-nonterminal", action="store_true")
    args = parser.parse_args()
    failures = execution_failures(
        json.load(sys.stdin), arm=args.arm, replicate=args.replicate,
        season=args.season, panel=args.panel, job=args.job,
        execution_name=args.execution, image=args.image,
        code_sha=args.code_sha,
        control_schedules=_schedule_argument(args.control_schedules_json),
        treatment_schedules=_schedule_argument(args.treatment_schedules_json),
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
