from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = str(ROOT / "scripts")
if SCRIPTS not in sys.path:
    sys.path.insert(0, SCRIPTS)

from validate_stack_core_shell_lock_canary import (  # noqa: E402
    EXECUTION_PROTOCOL_SHA256,
    PREFIX,
    RUN_ID,
    SERVICE_ACCOUNT,
    validate,
)


def test_lock_real_path_canary_validates_exact_outcome_free_contract(
    tmp_path: Path,
) -> None:
    validator = ROOT / "scripts/validate_stack_core_shell_lock_canary.py"
    image = "image@sha256:" + "b" * 64
    code = "a" * 40
    manifest = tmp_path / "manifest.txt"
    manifest.write_text("\n".join([
        f"run_id={RUN_ID}", f"output_prefix={PREFIX}",
        f"execution_protocol_sha256={EXECUTION_PROTOCOL_SHA256}",
        f"canary_validator_sha256={sha256(validator.read_bytes()).hexdigest()}",
        f"code_sha={code}", f"image={image}",
        f"scorefree_report_sha256={'c' * 64}",
        f"scorefree_completion_sha256={'d' * 64}",
    ]) + "\n", encoding="utf-8")
    job = "stack-shell-lock-s2023-w1-v1"
    execution = job + "-abc12"
    uri = f"{PREFIX}/slate-2023-1.json"
    ledger = tmp_path / "executions.txt"
    ledger.write_text(
        f"2023 1 {job} {execution} {uri}\n", encoding="utf-8",
    )
    metadata = tmp_path / "execution.json"
    metadata.write_text(json.dumps({
        "metadata": {"name": execution},
        "spec": {"parallelism": 1, "taskCount": 1, "template": {"spec": {
            "maxRetries": 0, "timeoutSeconds": "7200",
            "serviceAccountName": SERVICE_ACCOUNT,
            "containers": [{
                "image": image, "command": ["python"],
                "args": [
                    "scripts/run_stack_core_shell_production_lock.py",
                    "--season", "2023", "--week", "1", "--output-uri", uri,
                    "--scorefree-report-sha256", "c" * 64,
                    "--scorefree-completion-sha256", "d" * 64,
                ],
                "env": [
                    {"name": "CODE_SHA", "value": code},
                    {"name": "ANALYSIS_IMAGE", "value": image},
                ],
                "resources": {"limits": {"cpu": "4", "memory": "16Gi"}},
            }],
        }}},
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
    assert validate(
        manifest, ledger, metadata, object_path, validator, completion,
    ) is True
    text = completion.read_text(encoding="utf-8")
    assert "actual_scores_queried=false" in text
    assert "object_content_inspected=false" in text
