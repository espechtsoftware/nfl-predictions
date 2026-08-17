from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = str(ROOT / "scripts")
if SCRIPTS not in sys.path:
    sys.path.insert(0, SCRIPTS)

from validate_stack_core_shell_scorefree_canary import (  # noqa: E402
    EXECUTION_PROTOCOL_SHA256,
    PREFIX,
    RUN_ID,
    SERVICE_ACCOUNT,
    validate,
)


def _files(tmp_path: Path) -> tuple[Path, Path, Path, Path, Path, Path]:
    validator = ROOT / "scripts/validate_stack_core_shell_scorefree_canary.py"
    image = "image@sha256:" + "b" * 64
    code = "a" * 40
    support_uri = (
        "gs://nfl-predictions-503414-raw/research/"
        "stack-core-shell-support-runs/"
        "20260816-stack-core-shell-control-support-census-v1/report.json"
    )
    manifest = tmp_path / "manifest.txt"
    manifest.write_text("\n".join([
        f"run_id={RUN_ID}", f"output_prefix={PREFIX}",
        f"execution_protocol_sha256={EXECUTION_PROTOCOL_SHA256}",
        f"canary_validator_sha256={sha256(validator.read_bytes()).hexdigest()}",
        f"code_sha={code}", f"image={image}",
        f"support_report_uri={support_uri}",
        f"support_report_sha256={'c' * 64}",
    ]) + "\n", encoding="utf-8")
    job = "stack-shell-scorefree-s2023-w1-v1"
    execution = job + "-abc12"
    uri = f"{PREFIX}/slate-2023-1.json"
    ledger = tmp_path / "executions.txt"
    ledger.write_text(
        f"2023 1 {job} {execution} {uri}\n", encoding="utf-8",
    )
    metadata = tmp_path / "execution.json"
    metadata.write_text(json.dumps({
        "metadata": {"name": execution},
        "spec": {
            "parallelism": 1, "taskCount": 1,
            "template": {"spec": {
                "maxRetries": 0, "timeoutSeconds": "14400",
                "serviceAccountName": SERVICE_ACCOUNT,
                "containers": [{
                    "image": image, "command": ["python"],
                    "args": [
                        "scripts/run_stack_core_shell_scorefree.py",
                        "--season", "2023", "--week", "1",
                        "--output-uri", uri,
                        "--support-uri", support_uri,
                        "--support-sha256", "c" * 64,
                    ],
                    "env": [
                        {"name": "CODE_SHA", "value": code},
                        {"name": "ANALYSIS_IMAGE", "value": image},
                    ],
                    "resources": {"limits": {"cpu": "4", "memory": "16Gi"}},
                }],
            }},
        },
        "status": {
            "conditions": [{"type": "Completed", "status": "True"}],
            "succeededCount": 1, "failedCount": 0,
            "completionTime": "2026-08-17T02:00:00Z",
        },
    }), encoding="utf-8")
    object_path = tmp_path / "object.json"
    object_path.write_text(
        json.dumps({"generation": "123", "size": "456"}), encoding="utf-8",
    )
    completion = tmp_path / "completion.txt"
    return manifest, ledger, metadata, object_path, validator, completion


def test_scorefree_real_path_canary_validates_exact_contract(tmp_path: Path) -> None:
    paths = _files(tmp_path)
    assert validate(*paths) is True
    completion = dict(
        line.split("=", 1)
        for line in paths[-1].read_text(encoding="utf-8").splitlines()
    )
    assert completion["status"] == "True"
    assert completion["treatment_constructed"] == "true"
    assert completion["object_content_inspected"] == "false"


def test_scorefree_real_path_canary_fails_without_object(tmp_path: Path) -> None:
    manifest, ledger, metadata, _object, validator, completion = _files(tmp_path)
    assert validate(
        manifest, ledger, metadata, None, validator, completion,
    ) is False
    assert "status=False" in completion.read_text(encoding="utf-8")
