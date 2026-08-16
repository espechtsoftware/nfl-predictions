"""Frozen R3/2025 source-repair contract for the ATLAS MVP.

The original acquisition uploaded the complete Week 1 player/candidate world
artifact but its ancillary candidate-table write received a BigQuery 429.
Part B needs roster identities and tags, so it replays the exact original
container while changing only the two create-only storage destinations below.
"""

from __future__ import annotations

from hashlib import sha256
import json
from typing import Any, Mapping


VERSION = "atlas-mvp-source-repair-r3-2025-v1"
RUN_ID = "20260816-atlas-mvp-source-repair-r3-2025-v1"
ORIGINAL_EXECUTION = "replay-atlasmoney-r3-2025-htrch"
ORIGINAL_EXECUTION_SHA256 = (
    "60173988c785b88253052e40d73cfe396f9947c44f84f4bfe279be781db07ca9"
)
ORIGINAL_ENVIRONMENT_SHA256 = (
    "f0807cc2045d59b89fd7cd856e8633b88c105250fdfc09ffe91efbfe13ca6f03"
)
ORIGINAL_IMAGE = (
    "us-central1-docker.pkg.dev/nfl-predictions-503414/nfl-dfs/"
    "nfl-dfs@sha256:ad4604d86f1b1f7938136650f3d3940c9f1d6edd6a3427d618e6f943822602c8"
)
ORIGINAL_CODE_SHA = "545ddae1b8e1256fde8e345683e0004aa5463b5e"
ORIGINAL_PANEL = "20260815-atlas-money-worlds-r3-v1"
ORIGINAL_LINEUPS_TABLE = (
    "nfl-predictions-503414.nfl_features.replay_lineups_atlasmoney_r3_2025"
)
REPAIR_PANEL = "20260816-atlas-mvp-repair-r3-2025-v1"
REPAIR_LINEUPS_TABLE = (
    "nfl-predictions-503414.nfl_features."
    "replay_lineups_atlas_mvp_repair_r3_2025"
)
ORIGINAL_ARTIFACT_URI = (
    "gs://nfl-predictions-503414-raw/cand_scores/"
    "20260815-atlas-money-worlds-r3-v1/2025_w1_0590227023eb.npz"
)
ORIGINAL_ARTIFACT_SHA256 = (
    "7eaef50c890150f6cdc329e80e4d68f08b4a8d2aac402fa5a51ba9ce4f860805"
)
EXPECTED_ARGS = (
    "replay", "--season", "2025", "--contest", "gpp", "--entries", "80",
)
EXPECTED_RESOURCES = {"cpu": "4", "memory": "16Gi"}
EXPECTED_SERVICE_ACCOUNT = (
    "817589974517-compute@developer.gserviceaccount.com"
)
EXPECTED_TIMEOUT_SECONDS = 14_400


def environment_sha256(values: Mapping[str, str]) -> str:
    """Stable digest used by the original acquisition receipt."""
    normalized = dict(sorted((str(k), str(v)) for k, v in values.items()))
    payload = json.dumps(
        normalized, sort_keys=True, separators=(",", ":"),
    ).encode()
    return sha256(payload).hexdigest()


def repair_environment(original: Mapping[str, str]) -> dict[str, str]:
    """Validate the immutable source env and change only storage identity."""
    values = dict(sorted((str(k), str(v)) for k, v in original.items()))
    if environment_sha256(values) != ORIGINAL_ENVIRONMENT_SHA256:
        raise ValueError("ATLAS MVP repair original environment differs")
    required = {
        "CODE_SHA": ORIGINAL_CODE_SHA,
        "PANEL_RUN_ID": ORIGINAL_PANEL,
        "REPLAY_LINEUPS_TABLE": ORIGINAL_LINEUPS_TABLE,
        "CAND_ARTIFACT_PLAYER_WORLDS": "1",
        "REPLAY_PROJECTION_SEED": "253722715",
        "ROLE_BELIEF_SEED": "3374646876",
        "N_BOOM": "40",
    }
    if any(values.get(key) != value for key, value in required.items()):
        raise ValueError("ATLAS MVP repair source identity differs")
    values["PANEL_RUN_ID"] = REPAIR_PANEL
    values["REPLAY_LINEUPS_TABLE"] = REPAIR_LINEUPS_TABLE
    return dict(sorted(values.items()))


def environment_differences(
    original: Mapping[str, str], repair: Mapping[str, str],
) -> dict[str, tuple[str | None, str | None]]:
    """Return every changed key for the human/machine receipt."""
    left = {str(k): str(v) for k, v in original.items()}
    right = {str(k): str(v) for k, v in repair.items()}
    return {
        key: (left.get(key), right.get(key))
        for key in sorted(set(left) | set(right))
        if left.get(key) != right.get(key)
    }


def validate_repair_execution(
    execution: Mapping[str, Any], *, execution_name: str,
    expected_environment: Mapping[str, str], terminal: bool,
) -> dict[str, Any]:
    """Validate the complete immutable Cloud Run execution receipt."""
    if execution.get("metadata", {}).get("name") != execution_name:
        raise ValueError("ATLAS MVP repair execution name differs")
    spec = execution.get("spec", {})
    template = spec.get("template", {}).get("spec", {})
    containers = template.get("containers", [])
    if spec.get("parallelism") != 1 or spec.get("taskCount") != 1 or \
            len(containers) != 1:
        raise ValueError("ATLAS MVP repair task shape differs")
    container = containers[0]
    if container.get("image") != ORIGINAL_IMAGE or \
            container.get("command") != ["nfl-dfs"] or \
            container.get("args") != list(EXPECTED_ARGS):
        raise ValueError("ATLAS MVP repair image or command differs")
    actual_environment = {
        str(row.get("name")): str(row.get("value", ""))
        for row in container.get("env", [])
    }
    expected = {str(k): str(v) for k, v in expected_environment.items()}
    if actual_environment != expected:
        raise ValueError("ATLAS MVP repair execution environment differs")
    if container.get("resources", {}).get("limits") != EXPECTED_RESOURCES or \
            template.get("maxRetries") != 0 or \
            int(template.get("timeoutSeconds") or 0) != EXPECTED_TIMEOUT_SECONDS or \
            template.get("serviceAccountName") != EXPECTED_SERVICE_ACCOUNT:
        raise ValueError("ATLAS MVP repair compute contract differs")
    if terminal:
        status = execution.get("status", {})
        completed = [
            row for row in status.get("conditions", [])
            if row.get("type") == "Completed"
        ]
        if len(completed) != 1 or completed[0].get("status") != "True" or \
                int(status.get("succeededCount") or 0) != 1 or \
                int(status.get("failedCount") or 0) != 0 or \
                not status.get("completionTime"):
            raise ValueError("ATLAS MVP repair is not terminal successful")
    return {
        "execution": execution_name,
        "image": ORIGINAL_IMAGE,
        "environment_sha256": environment_sha256(expected),
        "environment_differences": environment_differences(
            {**expected,
             "PANEL_RUN_ID": ORIGINAL_PANEL,
             "REPLAY_LINEUPS_TABLE": ORIGINAL_LINEUPS_TABLE},
            expected,
        ),
    }
