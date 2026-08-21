#!/usr/bin/env python3
"""Close A7-v1 after its outcome-blind preflight execution failed.

This operator-side closer has one narrow cloud write: a create-only logical
release object.  It cannot deploy, execute, retry, cancel, delete, query
BigQuery, read logs, acquire the historical lease, or read any A7 scientific
artifact body.
"""

from __future__ import annotations

import argparse
from collections.abc import Callable, Mapping
from datetime import datetime, timezone
from hashlib import sha256
import json
import math
from pathlib import Path
import re
import subprocess
from typing import Any, Final

from google.api_core.exceptions import NotFound, PreconditionFailed
from google.cloud import storage


ROOT: Final = Path(__file__).resolve().parents[1]
PROJECT: Final = "nfl-predictions-503414"
REGION: Final = "us-central1"
RUN_ID: Final = "20260820-a7-select-ladder-phase-s-incumbent-v1"
NEXT_RUN_ID: Final = "20260820-a7-select-ladder-phase-s-incumbent-v2"
JOB: Final = "atlas-minimal-c-s2023-w1-v1"
JOB_UID: Final = "d6e4b8c1-5950-46b7-8869-7e34dbf29ad2"
EXECUTION: Final = "atlas-minimal-c-s2023-w1-v1-6qfpk"
EXECUTION_UID: Final = "168674b0-4f13-48fb-9ff9-6a6e1e5ce49e"
CODE_SHA: Final = "96f4487bdefa297f66d03e4aca896728581540b2"
BUILD_ID: Final = "3503c493-60d5-4fe6-a853-583679c8e33d"
GIT_SOURCE_URL: Final = "https://github.com/espechtsoftware/nfl-predictions.git"
IMAGE_TAG: Final = (
    "us-central1-docker.pkg.dev/nfl-predictions-503414/nfl-dfs/"
    "nfl-dfs:a7-96f4487-20260820"
)
IMAGE: Final = (
    "us-central1-docker.pkg.dev/nfl-predictions-503414/nfl-dfs/nfl-dfs@"
    "sha256:9956f2b4444bc60255c29a1844c23a1f772d6b0c85ae1a532e032ece975e86ed"
)
PROTOCOL_PATH: Final = (
    "reports/2026-08-20-a7-select-ladder-incumbent-pool-protocol.md"
)
PROTOCOL_SHA256: Final = (
    "987ad3eb8bd141427ce201348de165b9b337c1184de1fc8bdd32987bd1373cce"
)
CLOSURE_PROTOCOL_PATH: Final = (
    "reports/2026-08-20-a7-v1-failed-preflight-logical-release-protocol.md"
)
CLOSURE_PROTOCOL_SHA256: Final = (
    "b399dbcbafc92926eee6c4c50474422858d748d005a2acffb95fa87b0dffe69a"
)
DISPOSITION_REPORT_PATH: Final = (
    "reports/2026-08-20-a7-outcome-blind-smoke-failure-and-queue-disposition.md"
)
DISPOSITION_REPORT_SHA256: Final = (
    "52b7d52afc3f3fdcb21129c9071eb10f294ca596e4f02d423dc824d2aaedcdff"
)
DISPOSITION: Final = "invalid-outcome-blind-preflight-closed-no-retry"
COMPLETION_TIME: Final = "2026-08-20T15:00:41.442723Z"
CLAIMED_JOB_GENERATION: Final = "8"
EXECUTION_JOB_GENERATION: Final = "9"
CLAIMED_JOB_SPEC_SHA256: Final = (
    "e0739de9c90d29d95bf1fc616373c0799ec033958c6bf7a5257eb66204d585f4"
)
EXECUTION_JOB_SPEC_SHA256: Final = (
    "466f6a3c492d9687dca6cc38fa57584d8c63b20b39e7bca7953b05e48c73861e"
)

PREFIX: Final = (
    "gs://nfl-predictions-503414-raw/research/a7-select-ladder-runs/"
    f"{RUN_ID}"
)
JOB_CLAIM_URI: Final = f"{PREFIX}/preflight/job-claim.json"
SMOKE_URI: Final = f"{PREFIX}/preflight/real-artifact-smoke.json"
SMOKE_TERMINAL_URI: Final = (
    f"{PREFIX}/preflight/real-artifact-smoke-terminal.json"
)
SUPPORT_URI: Final = f"{PREFIX}/preflight/support-census.json"
SUPPORT_TERMINAL_URI: Final = f"{PREFIX}/preflight/support-census-terminal.json"
FREEZE_URI: Final = f"{PREFIX}/preflight/freeze-manifest.json"
RESULT_URI: Final = f"{PREFIX}/result.json"
RELEASE_URI: Final = f"{PREFIX}/preflight/failed-preflight-logical-release.json"
LEASE_URI: Final = (
    "gs://nfl-predictions-503414-raw/research-governance/"
    "historical-outcome-active-v1.json"
)
REQUIRED_NOT_FOUND_URIS: Final = (
    SMOKE_URI,
    SMOKE_TERMINAL_URI,
    SUPPORT_URI,
    SUPPORT_TERMINAL_URI,
    FREEZE_URI,
    RESULT_URI,
)

DEFAULT_OUT: Final = (
    ROOT / "reports/a7-select-ladder-preflight-runs" / RUN_ID
)
DEFAULT_RELEASE: Final = DEFAULT_OUT / "failed-preflight-logical-release.json"
DEFAULT_RELEASE_OBJECT: Final = (
    DEFAULT_OUT / "failed-preflight-logical-release-object.json"
)
TERMINAL_RECEIPT_NAME: Final = "failed-preflight-terminal-execution.json"
INVENTORY_RECEIPT_NAME: Final = "failed-preflight-prefix-inventory.json"
ABSENCE_RECEIPT_NAME: Final = "failed-preflight-absence-receipt.json"

RELEASE_VERSION: Final = "a7-select-ladder-failed-preflight-logical-release-v1"
OBJECT_RECEIPT_VERSION: Final = (
    "a7-select-ladder-failed-preflight-logical-release-object-receipt-v1"
)
INVENTORY_VERSION: Final = "a7-select-ladder-failed-preflight-prefix-inventory-v1"
ABSENCE_VERSION: Final = "a7-select-ladder-failed-preflight-absence-v1"

V1_SOURCE_SHA256: Final = {
    PROTOCOL_PATH: PROTOCOL_SHA256,
    "src/nfl_dfs/research/a7_select_ladder.py": (
        "cfe4ff5faea3db2b7c8d07adbcc92e747a2a52c1e14c453b8bfd8c456abfe1a0"
    ),
    "scripts/run_a7_select_ladder.py": (
        "e20e1dadcb94136b74727e77b0c30c2a61975aaef459269186d690640bde196a"
    ),
    "scripts/cloud_a7_select_ladder.sh": (
        "d4b30c6784ef4d786cfe70d9a097d0c453d5f4cdc861ddf6d89893357e756c9a"
    ),
    "scripts/watch_a7_select_ladder_queue.sh": (
        "fefc5764f676c9e19c7103f9d43dd79628cff91d3e2d7eca40902a4c8e6097a1"
    ),
    "scripts/finish_a7_select_ladder.py": (
        "00c96db3e0063dfdf8fa3750a8766a10feb9819afd45f5dafc87598128e2b8fc"
    ),
    "cloudbuild.yaml": (
        "799f498b358660aebc5f7948b2bb50fadc2623a3027f1d138392feb253896c6d"
    ),
}

INPUT_SHA256: Final = {
    "build-metadata.json": (
        "945deeb954980bf8cdd141df7af25fd0f082a43741820a4f52dbf58412284961"
    ),
    "a3-logical-release.json": (
        "77c4979bc8b39b7980fe6c6f65c46dc37c964696d1d21a9931923bc75075ce9e"
    ),
    "job-at-claim.json": (
        "37f14089c44b4d6a00908f2d4bdded3f5d5ce85b63e83b742467bbb3548d4692"
    ),
    "job-claim-receipt.json": (
        "11d1fcfcab41bc616fa1213d97523574706f15f0934b076f3136f8992e9d0b48"
    ),
    "prepared.sha256": (
        "711058997adbfab22015e061ff5af529bff800acb5a7265a230a46a3ddca7e1c"
    ),
    "smoke/manifest.json": (
        "289f736d32c30f2df379c340a5e1b21b98ffa1ab9286f50fd38d7cbec1c5a202"
    ),
    "smoke/build-metadata.json": (
        "945deeb954980bf8cdd141df7af25fd0f082a43741820a4f52dbf58412284961"
    ),
    "smoke/a3-logical-release.json": (
        "77c4979bc8b39b7980fe6c6f65c46dc37c964696d1d21a9931923bc75075ce9e"
    ),
    "smoke/job-claim-receipt.json": (
        "11d1fcfcab41bc616fa1213d97523574706f15f0934b076f3136f8992e9d0b48"
    ),
    "smoke/job-before.json": (
        "37f14089c44b4d6a00908f2d4bdded3f5d5ce85b63e83b742467bbb3548d4692"
    ),
    "smoke/job-after.json": (
        "bad0ac28c417a3870dbfe2d187fd230442a769ab7811a28e3184155d681133fb"
    ),
    "smoke/prepared.sha256": (
        "cfadc79a70efe2f54a43ed6621e12fc7fd82ec162b2b12cab9fc127afacfba19"
    ),
    "smoke/launch.sha256": (
        "7f07aac040a8be762d2765bc9fa14bcc330842d718ac66daa30da579e94d3c02"
    ),
    "smoke/executions.txt": (
        "bd8873394660a1558bbd0a5fe5714fe9b4d4d2696fc10a7e79eeaf5bb1cf478b"
    ),
    "smoke/.execution-poll.json": (
        "f97eff90169efa21c8ae2acb2fc7124f438e696dc8b88abf3b9279c68623d91c"
    ),
}


def _reject_constant(value: str) -> None:
    raise ValueError(f"non-finite JSON constant is forbidden: {value}")


def _strict_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key is forbidden: {key}")
        result[key] = value
    return result


def _strict_json_bytes(raw: bytes, *, label: str) -> Any:
    try:
        value = json.loads(
            raw,
            object_pairs_hook=_strict_object,
            parse_constant=_reject_constant,
        )
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        raise RuntimeError(f"A7-v1 closure {label} is not strict JSON") from exc

    def walk(item: Any) -> None:
        if isinstance(item, float) and not math.isfinite(item):
            raise RuntimeError(f"A7-v1 closure {label} contains non-finite JSON")
        if isinstance(item, dict):
            for child in item.values():
                walk(child)
        elif isinstance(item, list):
            for child in item:
                walk(child)

    walk(value)
    return value


def _canonical_json(value: Any) -> bytes:
    return (
        json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)
        + "\n"
    ).encode("utf-8")


def _sha_bytes(raw: bytes) -> str:
    return sha256(raw).hexdigest()


def _sha(path: Path) -> str:
    return _sha_bytes(path.read_bytes())


def _load_json(path: Path, *, label: str) -> Any:
    if path.is_symlink() or not path.is_file():
        raise RuntimeError(f"A7-v1 closure {label} is absent")
    return _strict_json_bytes(path.read_bytes(), label=label)


def _hex(value: object, *, length: int, label: str) -> str:
    text = str(value)
    if re.fullmatch(rf"[0-9a-f]{{{length}}}", text) is None:
        raise RuntimeError(f"A7-v1 closure {label} differs")
    return text


def _nonnegative_int(value: object, *, label: str) -> int:
    if type(value) is not int or value < 0:
        raise RuntimeError(f"A7-v1 closure {label} differs")
    return value


def _positive_int(value: object, *, label: str) -> int:
    result = _nonnegative_int(value, label=label)
    if result == 0:
        raise RuntimeError(f"A7-v1 closure {label} differs")
    return result


def _utc(value: object, *, label: str) -> str:
    text = str(value)
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise RuntimeError(f"A7-v1 closure {label} differs") from exc
    if parsed.tzinfo is None or parsed.utcoffset() != timezone.utc.utcoffset(parsed):
        raise RuntimeError(f"A7-v1 closure {label} differs")
    return text


def _gcs_parts(uri: str) -> tuple[str, str]:
    match = re.fullmatch(r"gs://([^/]+)/(.+)", uri)
    if match is None or ".." in match.group(2).split("/"):
        raise RuntimeError("A7-v1 closure GCS URI differs")
    return match.group(1), match.group(2)


def _repo_relative(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError as exc:
        raise RuntimeError("A7-v1 closure evidence escaped repository") from exc


def _write_once_or_equal(path: Path, raw: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("xb") as handle:
            handle.write(raw)
    except FileExistsError:
        if path.is_symlink() or not path.is_file() or path.read_bytes() != raw:
            raise RuntimeError(f"A7-v1 immutable local evidence differs: {path}")


def _git_blob(root: Path, code_sha: str, relative: str) -> bytes:
    return subprocess.run(
        ["git", "-C", str(root), "show", f"{code_sha}:{relative}"],
        check=True,
        capture_output=True,
    ).stdout


def _reference(path: Path, root: Path) -> dict[str, str]:
    return {"path": _repo_relative(path, root), "sha256": _sha(path)}


def _validate_reference(
    value: object, *, path: str | None = None, sha256_value: str | None = None,
    label: str,
) -> dict[str, str]:
    if not isinstance(value, dict) or set(value) != {"path", "sha256"}:
        raise RuntimeError(f"A7-v1 closure {label} reference differs")
    result = {
        "path": str(value.get("path", "")),
        "sha256": _hex(value.get("sha256"), length=64, label=f"{label} SHA"),
    }
    if path is not None and result["path"] != path:
        raise RuntimeError(f"A7-v1 closure {label} path differs")
    if sha256_value is not None and result["sha256"] != sha256_value:
        raise RuntimeError(f"A7-v1 closure {label} SHA differs")
    return result


def _validate_object_identity(
    value: object, *, uri: str, create_only: bool = True, label: str,
) -> dict[str, Any]:
    keys = {"uri", "generation", "metageneration", "bytes", "sha256"}
    if create_only:
        keys.add("create_only")
    if not isinstance(value, dict) or set(value) != keys or value.get("uri") != uri:
        raise RuntimeError(f"A7-v1 closure {label} object fields differ")
    generation = str(value.get("generation", ""))
    metageneration = str(value.get("metageneration", ""))
    if re.fullmatch(r"[1-9][0-9]*", generation) is None or metageneration != "1":
        raise RuntimeError(f"A7-v1 closure {label} object identity differs")
    result: dict[str, Any] = {
        "uri": uri,
        "generation": generation,
        "metageneration": metageneration,
        "bytes": _positive_int(value.get("bytes"), label=f"{label} bytes"),
        "sha256": _hex(value.get("sha256"), length=64, label=f"{label} SHA"),
    }
    if create_only:
        if value.get("create_only") is not True:
            raise RuntimeError(f"A7-v1 closure {label} is not create-only")
        result["create_only"] = True
    return result


def _job_spec_sha(job: Mapping[str, Any]) -> str:
    return _sha_bytes(_canonical_json(job.get("spec")))


def _validate_sha_ledger(path: Path, expected_names: set[str]) -> None:
    if path.is_symlink() or not path.is_file():
        raise RuntimeError(f"A7-v1 closure ledger is absent: {path}")
    rows: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        match = re.fullmatch(r"([0-9a-f]{64})  ([A-Za-z0-9_.-]+)", line)
        if match is None or match.group(2) in rows:
            raise RuntimeError(f"A7-v1 closure ledger is malformed: {path}")
        rows[match.group(2)] = match.group(1)
    if set(rows) != expected_names:
        raise RuntimeError(f"A7-v1 closure ledger population differs: {path}")
    for name, expected in rows.items():
        target = path.parent / name
        if target.is_symlink() or not target.is_file() or _sha(target) != expected:
            raise RuntimeError(f"A7-v1 closure ledger target differs: {target}")


def _expected_execution_contract() -> dict[str, Any]:
    return {
        "parallelism": 1,
        "taskCount": 1,
        "template": {"spec": {
            "containers": [{
                "args": [
                    "scripts/run_a7_select_ladder.py",
                    "--smoke",
                    "--preflight-receipt-uri",
                    SMOKE_URI,
                ],
                "command": ["python"],
                "env": [
                    {"name": "CODE_SHA", "value": CODE_SHA},
                    {"name": "ANALYSIS_IMAGE", "value": IMAGE},
                ],
                "image": IMAGE,
                "resources": {"limits": {"cpu": "4", "memory": "16Gi"}},
            }],
            "maxRetries": 0,
            "serviceAccountName": (
                "817589974517-compute@developer.gserviceaccount.com"
            ),
            "timeoutSeconds": "7200",
        }},
    }


def _validate_execution_contract(value: object, *, label: str) -> None:
    if _canonical_json(value) != _canonical_json(_expected_execution_contract()):
        raise RuntimeError(f"A7-v1 closure {label} contract differs")


def _validate_execution_identity(value: Mapping[str, Any], *, label: str) -> None:
    metadata = value.get("metadata")
    if not isinstance(metadata, dict) or metadata.get("name") != EXECUTION or \
            metadata.get("uid") != EXECUTION_UID or metadata.get("generation") != 1:
        raise RuntimeError(f"A7-v1 closure {label} execution identity differs")
    labels = metadata.get("labels")
    if not isinstance(labels, dict) or labels.get("run.googleapis.com/job") != JOB or \
            labels.get("run.googleapis.com/jobUid") != JOB_UID or \
            str(labels.get("run.googleapis.com/jobGeneration")) != \
            EXECUTION_JOB_GENERATION:
        raise RuntimeError(f"A7-v1 closure {label} job binding differs")
    _validate_execution_contract(value.get("spec"), label=label)


def _validate_first_poll(value: object) -> dict[str, Any]:
    if not isinstance(value, dict) or value.get("apiVersion") != \
            "run.googleapis.com/v1" or value.get("kind") != "Execution":
        raise RuntimeError("A7-v1 closure first-poll envelope differs")
    _validate_execution_identity(value, label="first poll")
    status = value.get("status")
    if not isinstance(status, dict) or set(status) != {"logUri"} or \
            not str(status.get("logUri", "")).startswith("https://"):
        raise RuntimeError("A7-v1 closure retained first poll is not preterminal")
    return value


def _counter(status: Mapping[str, Any], name: str) -> int:
    value = status.get(name, 0)
    return _nonnegative_int(value, label=f"terminal {name}")


def _validate_terminal_execution(value: object) -> dict[str, Any]:
    if not isinstance(value, dict) or value.get("apiVersion") != \
            "run.googleapis.com/v1" or value.get("kind") != "Execution":
        raise RuntimeError("A7-v1 closure terminal envelope differs")
    _validate_execution_identity(value, label="terminal")
    status = value.get("status")
    if not isinstance(status, dict) or status.get("completionTime") != \
            COMPLETION_TIME or status.get("observedGeneration") != 1:
        raise RuntimeError("A7-v1 closure terminal status identity differs")
    completed = [
        row for row in status.get("conditions", [])
        if isinstance(row, dict) and row.get("type") == "Completed"
    ]
    if len(completed) != 1 or completed[0].get("status") != "False":
        raise RuntimeError("A7-v1 closure terminal condition differs")
    counters = {
        "succeeded": _counter(status, "succeededCount"),
        "failed": _counter(status, "failedCount"),
        "cancelled": _counter(status, "cancelledCount"),
        "retried": _counter(status, "retriedCount"),
    }
    if counters != {"succeeded": 0, "failed": 1, "cancelled": 0, "retried": 0}:
        raise RuntimeError("A7-v1 closure terminal counters differ")
    return value


GitLoader = Callable[[Path, str, str], bytes]


def _validate_local_evidence(
    out: Path, *, root: Path = ROOT, git_loader: GitLoader = _git_blob,
) -> dict[str, Any]:
    if out.is_symlink() or not out.is_dir():
        raise RuntimeError("A7-v1 retained preflight directory is absent")
    for relative, expected in INPUT_SHA256.items():
        target = out / relative
        if target.is_symlink() or not target.is_file() or _sha(target) != expected:
            raise RuntimeError(f"A7-v1 retained evidence differs: {relative}")

    protocol = root / PROTOCOL_PATH
    closure_protocol = root / CLOSURE_PROTOCOL_PATH
    disposition = root / DISPOSITION_REPORT_PATH
    for path, expected, label in (
        (protocol, PROTOCOL_SHA256, "v1 protocol"),
        (closure_protocol, CLOSURE_PROTOCOL_SHA256, "closure protocol"),
        (disposition, DISPOSITION_REPORT_SHA256, "disposition report"),
    ):
        if path.is_symlink() or not path.is_file() or _sha(path) != expected:
            raise RuntimeError(f"A7-v1 closure {label} differs")

    for relative, expected in V1_SOURCE_SHA256.items():
        if _sha_bytes(git_loader(root, CODE_SHA, relative)) != expected:
            raise RuntimeError(f"A7-v1 committed source differs: {relative}")

    _validate_sha_ledger(
        out / "prepared.sha256",
        {"build-metadata.json", "a3-logical-release.json", "job-at-claim.json",
         "job-claim-receipt.json"},
    )
    _validate_sha_ledger(
        out / "smoke/prepared.sha256",
        {"manifest.json", "build-metadata.json", "a3-logical-release.json",
         "job-claim-receipt.json", "job-before.json", "job-after.json"},
    )
    _validate_sha_ledger(
        out / "smoke/launch.sha256",
        {"manifest.json", "prepared.sha256", "executions.txt"},
    )

    if (out / "build-metadata.json").read_bytes() != \
            (out / "smoke/build-metadata.json").read_bytes() or \
            (out / "a3-logical-release.json").read_bytes() != \
            (out / "smoke/a3-logical-release.json").read_bytes() or \
            (out / "job-claim-receipt.json").read_bytes() != \
            (out / "smoke/job-claim-receipt.json").read_bytes() or \
            (out / "job-at-claim.json").read_bytes() != \
            (out / "smoke/job-before.json").read_bytes():
        raise RuntimeError("A7-v1 duplicated retained evidence differs")

    build = _load_json(out / "build-metadata.json", label="build metadata")
    source = {"url": GIT_SOURCE_URL, "revision": CODE_SHA}
    results = build.get("results") if isinstance(build, dict) else None
    build_images = results.get("images") if isinstance(results, dict) else None
    if not isinstance(build, dict) or build.get("id") != BUILD_ID or \
            build.get("status") != "SUCCESS" or \
            build.get("source") != {"gitSource": source} or \
            build.get("sourceProvenance") != {"resolvedGitSource": source} or \
            build.get("images") != [IMAGE_TAG] or \
            not isinstance(build_images, list) or len(build_images) != 1 or \
            not isinstance(build_images[0], dict) or \
            build_images[0].get("name") != IMAGE_TAG or \
            build_images[0].get("digest") != IMAGE.rsplit("@", 1)[1]:
        raise RuntimeError("A7-v1 successful build identity differs")
    steps = build.get("steps")
    if not isinstance(steps, list) or len(steps) != 3 or \
            any(not isinstance(step, dict) or step.get("status") != "SUCCESS"
                for step in steps):
        raise RuntimeError("A7-v1 build steps differ")

    job_before = _load_json(out / "job-at-claim.json", label="job at claim")
    job_after = _load_json(out / "smoke/job-after.json", label="job after update")
    for job, generation, spec_sha, label in (
        (job_before, CLAIMED_JOB_GENERATION, CLAIMED_JOB_SPEC_SHA256, "claimed"),
        (job_after, EXECUTION_JOB_GENERATION, EXECUTION_JOB_SPEC_SHA256, "updated"),
    ):
        metadata = job.get("metadata") if isinstance(job, dict) else None
        if not isinstance(metadata, dict) or metadata.get("name") != JOB or \
                metadata.get("uid") != JOB_UID or str(metadata.get("generation")) != \
                generation or _job_spec_sha(job) != spec_sha:
            raise RuntimeError(f"A7-v1 {label} job differs")
    # A Cloud Run Job nests the future Execution spec at
    # job.spec.template.spec.  That whole value (parallelism/taskCount/task
    # template), not the inner task spec, must equal the launched execution.
    future_execution_spec = (
        job_after.get("spec", {}).get("template", {}).get("spec")
    )
    _validate_execution_contract(future_execution_spec, label="updated job")

    claim_receipt = _load_json(
        out / "job-claim-receipt.json", label="job claim receipt",
    )
    if not isinstance(claim_receipt, dict) or set(claim_receipt) != \
            {"claim", "object"}:
        raise RuntimeError("A7-v1 job claim receipt fields differ")
    claim = claim_receipt["claim"]
    expected_claim = {
        "version": "a7-select-ladder-job-claim-v1",
        "run_id": RUN_ID,
        "protocol_id": RUN_ID,
        "protocol_sha256": PROTOCOL_SHA256,
        "code_sha": CODE_SHA,
        "image": IMAGE,
        "job": JOB,
        "job_uid": JOB_UID,
        "job_generation": CLAIMED_JOB_GENERATION,
        "job_spec_sha256": CLAIMED_JOB_SPEC_SHA256,
        "claimant_phase": "smoke-support-freeze-historical",
        "a3_logical_release_sha256": INPUT_SHA256["a3-logical-release.json"],
        "actual_score_query_executed": False,
        "uses_realized_outcomes": False,
        "production_law_scorefree_transfer_licensed": False,
        "prospective_shadow_licensed": False,
        "production_change_licensed": False,
        "claimed_at": claim.get("claimed_at") if isinstance(claim, dict) else None,
    }
    if not isinstance(claim, dict) or claim != expected_claim:
        raise RuntimeError("A7-v1 job claim body differs")
    _utc(claim["claimed_at"], label="claim time")
    claim_object = _validate_object_identity(
        claim_receipt["object"], uri=JOB_CLAIM_URI, label="job claim",
    )
    claim_raw = _canonical_json(claim)
    if claim_object != {
        "uri": JOB_CLAIM_URI,
        "generation": "1787237723143509",
        "metageneration": "1",
        "bytes": len(claim_raw),
        "sha256": _sha_bytes(claim_raw),
        "create_only": True,
    }:
        raise RuntimeError("A7-v1 job claim object identity differs")

    manifest = _load_json(out / "smoke/manifest.json", label="launch manifest")
    required_manifest = {
        "version": "a7-select-ladder-preflight-launch-manifest-v1",
        "run_id": RUN_ID,
        "protocol_id": RUN_ID,
        "protocol_sha256": PROTOCOL_SHA256,
        "code_sha": CODE_SHA,
        "build_id": BUILD_ID,
        "image": IMAGE,
        "job": JOB,
        "job_uid": JOB_UID,
        "prior_job_generation": CLAIMED_JOB_GENERATION,
        "prior_job_spec_sha256": CLAIMED_JOB_SPEC_SHA256,
        "job_generation": EXECUTION_JOB_GENERATION,
        "job_spec_sha256": EXECUTION_JOB_SPEC_SHA256,
        "output_uri": SMOKE_URI,
        "max_retries": 0,
        "uses_realized_outcomes": False,
        "actual_score_query_executed": False,
        "production_law_scorefree_transfer_licensed": False,
        "prospective_shadow_licensed": False,
        "production_change_licensed": False,
    }
    if not isinstance(manifest, dict) or any(
        manifest.get(key) != expected for key, expected in required_manifest.items()
    ) or manifest.get("job_claim") != claim_receipt or \
            manifest.get("job_claim_receipt_sha256") != \
            INPUT_SHA256["job-claim-receipt.json"]:
        raise RuntimeError("A7-v1 preflight launch manifest differs")

    ledger = (out / "smoke/executions.txt").read_text(encoding="utf-8")
    expected_ledger = f"{JOB} {EXECUTION} {SMOKE_URI}\n"
    if ledger != expected_ledger:
        raise RuntimeError("A7-v1 execution ledger differs")
    first_poll = _validate_first_poll(_load_json(
        out / "smoke/.execution-poll.json", label="retained first poll",
    ))
    return {
        "build": build,
        "job_after": job_after,
        "claim_receipt": claim_receipt,
        "first_poll": first_poll,
    }


def _describe_execution() -> dict[str, Any]:
    process = subprocess.run(
        [
            "gcloud", "run", "jobs", "executions", "describe", EXECUTION,
            "--project", PROJECT, "--region", REGION, "--format=json",
        ],
        check=True,
        capture_output=True,
    )
    value = _strict_json_bytes(process.stdout, label="live execution metadata")
    if not isinstance(value, dict):
        raise RuntimeError("A7-v1 live execution metadata is not an object")
    return value


def _blob_text(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)


def _pinned_blob(
    client: storage.Client, *, uri: str, generation: str,
) -> tuple[dict[str, Any], bytes]:
    if re.fullmatch(r"[1-9][0-9]*", generation) is None:
        raise RuntimeError("A7-v1 generation-pinned read lacks generation")
    bucket_name, name = _gcs_parts(uri)
    blob = client.bucket(bucket_name).blob(name, generation=int(generation))
    blob.reload()
    raw = blob.download_as_bytes(if_generation_match=int(generation))
    identity = {
        "uri": uri,
        "generation": str(blob.generation or ""),
        "metageneration": str(blob.metageneration or ""),
        "bytes": len(raw),
        "sha256": _sha_bytes(raw),
        "md5_hash": _blob_text(blob.md5_hash),
        "crc32c": _blob_text(blob.crc32c),
        "etag": _blob_text(blob.etag),
        "time_created": _blob_text(blob.time_created),
        "updated": _blob_text(blob.updated),
    }
    if identity["generation"] != generation or identity["metageneration"] != "1" or \
            int(blob.size or 0) != len(raw):
        raise RuntimeError(f"A7-v1 generation-pinned object changed: {uri}")
    return identity, raw


def _require_not_found(client: storage.Client, uri: str) -> None:
    bucket_name, name = _gcs_parts(uri)
    try:
        client.bucket(bucket_name).blob(name).reload()
    except NotFound:
        return
    raise RuntimeError(f"A7-v1 object required absent is present: {uri}")


def _capture_remote_boundary(
    client: storage.Client, *, claim_receipt: Mapping[str, Any], checked_at: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    bucket_name, prefix_name = _gcs_parts(PREFIX + "/")
    listed = list(client.list_blobs(bucket_name, prefix=prefix_name))
    if len(listed) != 1:
        raise RuntimeError("A7-v1 pre-release prefix inventory is not singleton")
    listed_uri = f"gs://{bucket_name}/{listed[0].name}"
    generation = str(listed[0].generation or "")
    if listed_uri != JOB_CLAIM_URI:
        raise RuntimeError("A7-v1 pre-release prefix contains a non-claim object")
    identity, raw = _pinned_blob(
        client, uri=listed_uri, generation=generation,
    )
    expected_object = _validate_object_identity(
        claim_receipt.get("object"), uri=JOB_CLAIM_URI, label="local job claim",
    )
    compact_identity = {
        key: identity[key]
        for key in ("uri", "generation", "metageneration", "bytes", "sha256")
    }
    if compact_identity != {key: expected_object[key] for key in compact_identity} or \
            raw != _canonical_json(claim_receipt.get("claim")):
        raise RuntimeError("A7-v1 generation-pinned job claim differs")

    for uri in REQUIRED_NOT_FOUND_URIS:
        _require_not_found(client, uri)
    _require_not_found(client, LEASE_URI)

    inventory = {
        "version": INVENTORY_VERSION,
        "run_id": RUN_ID,
        "prefix": PREFIX,
        "captured_at": checked_at,
        "objects": [identity],
        "exact_uris": [JOB_CLAIM_URI],
        "job_claim_generation_pinned_reopened": True,
    }
    absence = {
        "version": ABSENCE_VERSION,
        "run_id": RUN_ID,
        "checked_at": checked_at,
        "not_found_uris": list(REQUIRED_NOT_FOUND_URIS),
        "historical_outcome_lease": {"uri": LEASE_URI, "state": "absent"},
        "authentication_or_network_errors_count_as_absent": False,
    }
    return inventory, absence


def _validate_inventory(value: object) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != {
        "version", "run_id", "prefix", "captured_at", "objects",
        "exact_uris", "job_claim_generation_pinned_reopened",
    } or value.get("version") != INVENTORY_VERSION or value.get("run_id") != \
            RUN_ID or value.get("prefix") != PREFIX or value.get("exact_uris") != \
            [JOB_CLAIM_URI] or value.get("job_claim_generation_pinned_reopened") \
            is not True:
        raise RuntimeError("A7-v1 prefix-inventory receipt differs")
    _utc(value.get("captured_at"), label="inventory capture time")
    objects = value.get("objects")
    if not isinstance(objects, list) or len(objects) != 1:
        raise RuntimeError("A7-v1 prefix-inventory population differs")
    row = objects[0]
    if not isinstance(row, dict) or set(row) != {
        "uri", "generation", "metageneration", "bytes", "sha256",
        "md5_hash", "crc32c", "etag", "time_created", "updated",
    }:
        raise RuntimeError("A7-v1 prefix-inventory object fields differ")
    _validate_object_identity(
        {key: row[key] for key in (
            "uri", "generation", "metageneration", "bytes", "sha256"
        )},
        uri=JOB_CLAIM_URI,
        create_only=False,
        label="inventory job claim",
    )
    if str(row["generation"]) != "1787237723143509" or \
            row["sha256"] != \
            "3a8d4a25868d2c450b2a4059b50028f2262d9315b6ca439054fd6cee9eaabb8c" or \
            row["bytes"] != 1026:
        raise RuntimeError("A7-v1 inventory job-claim identity differs")
    return value


def _validate_absence(value: object) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != {
        "version", "run_id", "checked_at", "not_found_uris",
        "historical_outcome_lease",
        "authentication_or_network_errors_count_as_absent",
    } or value.get("version") != ABSENCE_VERSION or value.get("run_id") != \
            RUN_ID or value.get("not_found_uris") != list(REQUIRED_NOT_FOUND_URIS) or \
            value.get("historical_outcome_lease") != \
            {"uri": LEASE_URI, "state": "absent"} or \
            value.get("authentication_or_network_errors_count_as_absent") is not False:
        raise RuntimeError("A7-v1 absence receipt differs")
    _utc(value.get("checked_at"), label="absence check time")
    return value


def _persist_capture(
    path: Path, value: dict[str, Any], *, validator: Callable[[object], dict[str, Any]],
    timestamp_key: str | None = None,
) -> dict[str, Any]:
    if path.exists():
        existing = validator(_load_json(path, label=path.name))
        left = dict(existing)
        right = dict(value)
        if timestamp_key is not None:
            left.pop(timestamp_key, None)
            right.pop(timestamp_key, None)
        if left != right:
            raise RuntimeError(f"A7-v1 retained capture changed: {path}")
        return existing
    _write_once_or_equal(path, _canonical_json(value))
    return validator(value)


def _make_release(
    *, root: Path, out: Path, terminal_path: Path, inventory_path: Path,
    absence_path: Path, inventory: Mapping[str, Any], absence: Mapping[str, Any],
    claim_receipt: Mapping[str, Any],
) -> dict[str, Any]:
    return {
        "version": RELEASE_VERSION,
        "run_id": RUN_ID,
        "status": "released-after-invalid-outcome-blind-preflight",
        "disposition": DISPOSITION,
        "next_run_id": NEXT_RUN_ID,
        "released_at": str(absence["checked_at"]),
        "closure_protocol": {
            "path": CLOSURE_PROTOCOL_PATH,
            "sha256": CLOSURE_PROTOCOL_SHA256,
        },
        "disposition_report": {
            "path": DISPOSITION_REPORT_PATH,
            "sha256": DISPOSITION_REPORT_SHA256,
        },
        "source": {
            "commit_sha": CODE_SHA,
            "git_source_url": GIT_SOURCE_URL,
            "committed_build_source": True,
            "implementation_sha256": dict(V1_SOURCE_SHA256),
        },
        "build": {
            "id": BUILD_ID,
            "status": "SUCCESS",
            "image": IMAGE,
            "metadata": _reference(out / "build-metadata.json", root),
        },
        "job_claim": {
            "job": JOB,
            "job_uid": JOB_UID,
            "claimed_generation": CLAIMED_JOB_GENERATION,
            "execution_generation": EXECUTION_JOB_GENERATION,
            "receipt": _reference(out / "job-claim-receipt.json", root),
            "object": dict(claim_receipt["object"]),
            "logically_released": True,
        },
        "preflight": {
            "prepared_ledger": _reference(out / "prepared.sha256", root),
            "smoke_prepared_ledger": _reference(
                out / "smoke/prepared.sha256", root,
            ),
            "launch_ledger": _reference(out / "smoke/launch.sha256", root),
            "launch_manifest": _reference(out / "smoke/manifest.json", root),
            "execution_ledger": _reference(out / "smoke/executions.txt", root),
            "first_poll": _reference(out / "smoke/.execution-poll.json", root),
        },
        "terminal_execution": {
            "name": EXECUTION,
            "uid": EXECUTION_UID,
            "completion_time": COMPLETION_TIME,
            "completed_condition": False,
            "counters": {
                "succeeded": 0, "failed": 1, "cancelled": 0, "retried": 0,
            },
            "max_retries": 0,
            "receipt": _reference(terminal_path, root),
        },
        "pre_release_prefix": {
            "uri": PREFIX,
            "exact_uris": [JOB_CLAIM_URI],
            "inventory_receipt": _reference(inventory_path, root),
            "job_claim_generation_pinned_reopened": bool(
                inventory["job_claim_generation_pinned_reopened"]
            ),
        },
        "absence": {
            "receipt": _reference(absence_path, root),
            "required_not_found_uris": list(REQUIRED_NOT_FOUND_URIS),
            "historical_outcome_lease_uri": LEASE_URI,
            "historical_outcome_lease_state": "absent",
            "authentication_or_network_errors_count_as_absent": False,
        },
        "outcome_boundary": {
            "uses_realized_outcomes": False,
            "actual_score_query_executed": False,
            "realized_score_query_executed": False,
            "scientific_artifact_body_read": False,
            "historical_outcome_lease_acquired": False,
            "historical_look_consumed": False,
        },
        "licenses": {
            "preflight_retry_licensed": False,
            "historical_retest_licensed": False,
            "historical_scoring_licensed": False,
            "prospective_shadow_licensed": False,
            "production_law_scorefree_transfer_licensed": False,
            "production_change_licensed": False,
        },
        "lane_release": {
            "shared_job_claim_released": True,
            "v1_prefix_closed": True,
            "v1_prefix_reuse_licensed": False,
            "success_finisher_licensed": False,
            "next_run_id": NEXT_RUN_ID,
        },
    }


def validate_failure_logical_release(
    value: object, *, require_next_run_id: str = NEXT_RUN_ID,
) -> dict[str, Any]:
    keys = {
        "version", "run_id", "status", "disposition", "next_run_id",
        "released_at", "closure_protocol", "disposition_report", "source",
        "build", "job_claim", "preflight", "terminal_execution",
        "pre_release_prefix", "absence", "outcome_boundary", "licenses",
        "lane_release",
    }
    if not isinstance(value, dict) or set(value) != keys or \
            value.get("version") != RELEASE_VERSION or value.get("run_id") != \
            RUN_ID or value.get("status") != \
            "released-after-invalid-outcome-blind-preflight" or \
            value.get("disposition") != DISPOSITION or \
            value.get("next_run_id") != require_next_run_id:
        raise RuntimeError("A7-v1 failure logical release fields differ")
    _utc(value["released_at"], label="release time")
    _validate_reference(
        value["closure_protocol"], path=CLOSURE_PROTOCOL_PATH,
        sha256_value=CLOSURE_PROTOCOL_SHA256, label="closure protocol",
    )
    _validate_reference(
        value["disposition_report"], path=DISPOSITION_REPORT_PATH,
        sha256_value=DISPOSITION_REPORT_SHA256, label="disposition report",
    )
    if value["source"] != {
        "commit_sha": CODE_SHA,
        "git_source_url": GIT_SOURCE_URL,
        "committed_build_source": True,
        "implementation_sha256": dict(V1_SOURCE_SHA256),
    }:
        raise RuntimeError("A7-v1 release source binding differs")
    build = value["build"]
    if not isinstance(build, dict) or set(build) != {
        "id", "status", "image", "metadata",
    } or build.get("id") != BUILD_ID or build.get("status") != "SUCCESS" or \
            build.get("image") != IMAGE:
        raise RuntimeError("A7-v1 release build binding differs")
    _validate_reference(
        build["metadata"],
        path=f"reports/a7-select-ladder-preflight-runs/{RUN_ID}/build-metadata.json",
        sha256_value=INPUT_SHA256["build-metadata.json"], label="build metadata",
    )
    claim = value["job_claim"]
    if not isinstance(claim, dict) or set(claim) != {
        "job", "job_uid", "claimed_generation", "execution_generation",
        "receipt", "object", "logically_released",
    } or claim.get("job") != JOB or claim.get("job_uid") != JOB_UID or \
            claim.get("claimed_generation") != CLAIMED_JOB_GENERATION or \
            claim.get("execution_generation") != EXECUTION_JOB_GENERATION or \
            claim.get("logically_released") is not True:
        raise RuntimeError("A7-v1 release job claim differs")
    _validate_reference(
        claim["receipt"],
        path=f"reports/a7-select-ladder-preflight-runs/{RUN_ID}/job-claim-receipt.json",
        sha256_value=INPUT_SHA256["job-claim-receipt.json"], label="job claim",
    )
    _validate_object_identity(
        claim["object"], uri=JOB_CLAIM_URI, label="release job claim",
    )
    preflight = value["preflight"]
    expected_preflight = {
        "prepared_ledger": ("prepared.sha256", INPUT_SHA256["prepared.sha256"]),
        "smoke_prepared_ledger": (
            "smoke/prepared.sha256", INPUT_SHA256["smoke/prepared.sha256"],
        ),
        "launch_ledger": (
            "smoke/launch.sha256", INPUT_SHA256["smoke/launch.sha256"],
        ),
        "launch_manifest": (
            "smoke/manifest.json", INPUT_SHA256["smoke/manifest.json"],
        ),
        "execution_ledger": (
            "smoke/executions.txt", INPUT_SHA256["smoke/executions.txt"],
        ),
        "first_poll": (
            "smoke/.execution-poll.json",
            INPUT_SHA256["smoke/.execution-poll.json"],
        ),
    }
    if not isinstance(preflight, dict) or set(preflight) != set(expected_preflight):
        raise RuntimeError("A7-v1 release preflight fields differ")
    base = f"reports/a7-select-ladder-preflight-runs/{RUN_ID}/"
    for key, (relative, digest) in expected_preflight.items():
        _validate_reference(
            preflight[key], path=base + relative, sha256_value=digest,
            label=f"preflight {key}",
        )
    terminal = value["terminal_execution"]
    if not isinstance(terminal, dict) or set(terminal) != {
        "name", "uid", "completion_time", "completed_condition", "counters",
        "max_retries", "receipt",
    } or terminal.get("name") != EXECUTION or terminal.get("uid") != \
            EXECUTION_UID or terminal.get("completion_time") != COMPLETION_TIME or \
            terminal.get("completed_condition") is not False or \
            terminal.get("counters") != {
                "succeeded": 0, "failed": 1, "cancelled": 0, "retried": 0,
            } or terminal.get("max_retries") != 0:
        raise RuntimeError("A7-v1 release terminal execution differs")
    _validate_reference(
        terminal["receipt"], path=base + TERMINAL_RECEIPT_NAME,
        label="terminal execution",
    )
    prefix = value["pre_release_prefix"]
    if not isinstance(prefix, dict) or set(prefix) != {
        "uri", "exact_uris", "inventory_receipt",
        "job_claim_generation_pinned_reopened",
    } or prefix.get("uri") != PREFIX or prefix.get("exact_uris") != \
            [JOB_CLAIM_URI] or prefix.get("job_claim_generation_pinned_reopened") \
            is not True:
        raise RuntimeError("A7-v1 release prefix binding differs")
    _validate_reference(
        prefix["inventory_receipt"], path=base + INVENTORY_RECEIPT_NAME,
        label="prefix inventory",
    )
    absence = value["absence"]
    if not isinstance(absence, dict) or set(absence) != {
        "receipt", "required_not_found_uris", "historical_outcome_lease_uri",
        "historical_outcome_lease_state",
        "authentication_or_network_errors_count_as_absent",
    } or absence.get("required_not_found_uris") != \
            list(REQUIRED_NOT_FOUND_URIS) or \
            absence.get("historical_outcome_lease_uri") != LEASE_URI or \
            absence.get("historical_outcome_lease_state") != "absent" or \
            absence.get("authentication_or_network_errors_count_as_absent") is not False:
        raise RuntimeError("A7-v1 release absence binding differs")
    _validate_reference(
        absence["receipt"], path=base + ABSENCE_RECEIPT_NAME,
        label="absence receipt",
    )
    if value["outcome_boundary"] != {
        "uses_realized_outcomes": False,
        "actual_score_query_executed": False,
        "realized_score_query_executed": False,
        "scientific_artifact_body_read": False,
        "historical_outcome_lease_acquired": False,
        "historical_look_consumed": False,
    }:
        raise RuntimeError("A7-v1 release outcome boundary differs")
    if value["licenses"] != {
        "preflight_retry_licensed": False,
        "historical_retest_licensed": False,
        "historical_scoring_licensed": False,
        "prospective_shadow_licensed": False,
        "production_law_scorefree_transfer_licensed": False,
        "production_change_licensed": False,
    }:
        raise RuntimeError("A7-v1 release licenses differ")
    if value["lane_release"] != {
        "shared_job_claim_released": True,
        "v1_prefix_closed": True,
        "v1_prefix_reuse_licensed": False,
        "success_finisher_licensed": False,
        "next_run_id": require_next_run_id,
    }:
        raise RuntimeError("A7-v1 release lane binding differs")
    return value


def validate_failure_release_object_receipt(
    value: object, *, release_raw: bytes,
) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != {
        "version", "run_id", "release_sha256", "object",
    } or value.get("version") != OBJECT_RECEIPT_VERSION or \
            value.get("run_id") != RUN_ID or value.get("release_sha256") != \
            _sha_bytes(release_raw):
        raise RuntimeError("A7-v1 release object receipt fields differ")
    identity = _validate_object_identity(
        value["object"], uri=RELEASE_URI, label="logical release",
    )
    if identity["sha256"] != _sha_bytes(release_raw) or \
            identity["bytes"] != len(release_raw):
        raise RuntimeError("A7-v1 published release body identity differs")
    return value


def validate_failure_release_files(
    release_path: Path,
    object_receipt_path: Path,
    *,
    require_next_run_id: str = NEXT_RUN_ID,
) -> tuple[dict[str, Any], dict[str, Any]]:
    release_raw = release_path.read_bytes()
    release = validate_failure_logical_release(
        _strict_json_bytes(release_raw, label="failure logical release"),
        require_next_run_id=require_next_run_id,
    )
    receipt = validate_failure_release_object_receipt(
        _load_json(object_receipt_path, label="release object receipt"),
        release_raw=release_raw,
    )
    return release, receipt


def _publish_create_once(
    client: storage.Client, raw: bytes,
) -> dict[str, Any]:
    bucket_name, name = _gcs_parts(RELEASE_URI)
    blob = client.bucket(bucket_name).blob(name)
    try:
        blob.upload_from_string(
            raw, content_type="application/json", if_generation_match=0,
        )
    except PreconditionFailed as exc:
        raise RuntimeError("A7-v1 logical release URI is already occupied") from exc
    blob.reload()
    generation = str(blob.generation or "")
    audit, reopened = _pinned_blob(client, uri=RELEASE_URI, generation=generation)
    if reopened != raw:
        raise RuntimeError("A7-v1 create-once logical release reopen differs")
    return _validate_object_identity(
        {
            "uri": RELEASE_URI,
            "generation": audit["generation"],
            "metageneration": audit["metageneration"],
            "bytes": audit["bytes"],
            "sha256": audit["sha256"],
            "create_only": True,
        },
        uri=RELEASE_URI,
        label="published logical release",
    )


def _verify_publication(
    client: storage.Client, *, raw: bytes, receipt: Mapping[str, Any],
) -> None:
    identity = _validate_object_identity(
        receipt.get("object"), uri=RELEASE_URI, label="recorded logical release",
    )
    observed, reopened = _pinned_blob(
        client, uri=RELEASE_URI, generation=identity["generation"],
    )
    compact = {
        key: observed[key]
        for key in ("uri", "generation", "metageneration", "bytes", "sha256")
    }
    if compact != {key: identity[key] for key in compact} or reopened != raw:
        raise RuntimeError("A7-v1 recorded logical release changed")


def _validate_local_release_bundle(
    *, root: Path, out: Path,
) -> tuple[dict[str, Any], bytes]:
    raw = (out / DEFAULT_RELEASE.name).read_bytes()
    release = validate_failure_logical_release(
        _strict_json_bytes(raw, label="local logical release"),
    )
    references = [
        release["terminal_execution"]["receipt"],
        release["pre_release_prefix"]["inventory_receipt"],
        release["absence"]["receipt"],
    ]
    for reference in references:
        path = root / reference["path"]
        if path.is_symlink() or not path.is_file() or _sha(path) != \
                reference["sha256"]:
            raise RuntimeError("A7-v1 release evidence reference differs")
    _validate_terminal_execution(_load_json(
        root / release["terminal_execution"]["receipt"]["path"],
        label="retained terminal execution",
    ))
    _validate_inventory(_load_json(
        root / release["pre_release_prefix"]["inventory_receipt"]["path"],
        label="retained prefix inventory",
    ))
    _validate_absence(_load_json(
        root / release["absence"]["receipt"]["path"],
        label="retained absence evidence",
    ))
    return release, raw


def close(
    *,
    root: Path = ROOT,
    out: Path | None = None,
    client: storage.Client | None = None,
    execution_loader: Callable[[], Mapping[str, Any]] = _describe_execution,
    now: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
    git_loader: GitLoader = _git_blob,
) -> dict[str, Any]:
    target = root / "reports/a7-select-ladder-preflight-runs" / RUN_ID \
        if out is None else out
    release_path = target / DEFAULT_RELEASE.name
    object_path = target / DEFAULT_RELEASE_OBJECT.name
    gcs = storage.Client(project=PROJECT) if client is None else client

    if object_path.exists():
        if not release_path.is_file():
            raise RuntimeError("A7-v1 release object receipt lacks local body")
        release, receipt = validate_failure_release_files(release_path, object_path)
        _verify_publication(gcs, raw=release_path.read_bytes(), receipt=receipt)
        return {"status": "already-released", "release": release, "object": receipt}

    if release_path.exists():
        release, raw = _validate_local_release_bundle(root=root, out=target)
        bucket_name, name = _gcs_parts(RELEASE_URI)
        existing = gcs.bucket(bucket_name).blob(name)
        try:
            existing.reload()
        except NotFound:
            identity = _publish_create_once(gcs, raw)
        else:
            generation = str(existing.generation or "")
            observed, reopened = _pinned_blob(
                gcs, uri=RELEASE_URI, generation=generation,
            )
            if reopened != raw:
                raise RuntimeError("A7-v1 occupied release URI body differs")
            identity = _validate_object_identity(
                {
                    "uri": RELEASE_URI,
                    "generation": observed["generation"],
                    "metageneration": observed["metageneration"],
                    "bytes": observed["bytes"],
                    "sha256": observed["sha256"],
                    "create_only": True,
                },
                uri=RELEASE_URI,
                label="recovered logical release",
            )
        receipt = {
            "version": OBJECT_RECEIPT_VERSION,
            "run_id": RUN_ID,
            "release_sha256": _sha_bytes(raw),
            "object": identity,
        }
        _write_once_or_equal(object_path, _canonical_json(receipt))
        return {"status": "released", "release": release, "object": receipt}

    local = _validate_local_evidence(
        target, root=root, git_loader=git_loader,
    )
    terminal = _validate_terminal_execution(dict(execution_loader()))
    checked_at = now().astimezone(timezone.utc).isoformat()
    inventory, absence = _capture_remote_boundary(
        gcs,
        claim_receipt=local["claim_receipt"],
        checked_at=checked_at,
    )

    terminal_path = target / TERMINAL_RECEIPT_NAME
    inventory_path = target / INVENTORY_RECEIPT_NAME
    absence_path = target / ABSENCE_RECEIPT_NAME
    _write_once_or_equal(terminal_path, _canonical_json(terminal))
    inventory = _persist_capture(
        inventory_path, inventory, validator=_validate_inventory,
        timestamp_key="captured_at",
    )
    absence = _persist_capture(
        absence_path, absence, validator=_validate_absence,
        timestamp_key="checked_at",
    )

    release = _make_release(
        root=root,
        out=target,
        terminal_path=terminal_path,
        inventory_path=inventory_path,
        absence_path=absence_path,
        inventory=inventory,
        absence=absence,
        claim_receipt=local["claim_receipt"],
    )
    validate_failure_logical_release(release)
    release_raw = _canonical_json(release)
    _write_once_or_equal(release_path, release_raw)
    identity = _publish_create_once(gcs, release_raw)
    receipt = {
        "version": OBJECT_RECEIPT_VERSION,
        "run_id": RUN_ID,
        "release_sha256": _sha_bytes(release_raw),
        "object": identity,
    }
    validate_failure_release_object_receipt(receipt, release_raw=release_raw)
    _write_once_or_equal(object_path, _canonical_json(receipt))
    return {"status": "released", "release": release, "object": receipt}


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Close exact A7-v1 failed preflight after read-only evidence checks; "
            "publish only its create-once logical release"
        ),
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=DEFAULT_OUT,
        help="retained A7-v1 preflight directory",
    )
    args = parser.parse_args()
    result = close(root=ROOT, out=args.out)
    print(json.dumps(result, sort_keys=True, separators=(",", ":")))


if __name__ == "__main__":
    main()
