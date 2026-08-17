"""Strict score-blind source binding for the ATLAS historical v3 scorer."""

from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
import re
from typing import Any, Mapping, Sequence


UPSTREAM_RUN_ID = "20260816-atlas-matched-diversity-mvp-v1-repair5"
HISTORICAL_RUN_ID = "20260816-atlas-historical-score-diagnostic-v3"
UPSTREAM_PREFIX = (
    "gs://nfl-predictions-503414-raw/research/atlas-matched-diversity-runs/"
    + UPSTREAM_RUN_ID
)
HISTORICAL_PREFIX = (
    "gs://nfl-predictions-503414-raw/research/atlas-historical-score-runs/"
    + HISTORICAL_RUN_ID
)
UPSTREAM_CODE_SHA = "60f296fdad769b30c0bb7334118698f156e462b9"
UPSTREAM_IMAGE = (
    "us-central1-docker.pkg.dev/nfl-predictions-503414/nfl-dfs/nfl-dfs@"
    "sha256:ce03feb739e51aabedd7cea79f46e13a06a097a7f85e9a5817f38184b67f4fcb"
)
SERVICE_ACCOUNT = "817589974517-compute@developer.gserviceaccount.com"
CANARY_EXECUTION = "atlas-md-s2023-w1-r5-45nvf"
UPSTREAM_MANIFEST_SHA256 = (
    "a2812964c3bec8779c7ed8ce4aac8e74d84ea74548f611b87658d4f13371e400"
)
PRIMARY_LEDGER_SHA256 = (
    "1d9493c5608fc00abba7adb3436117c29f07c8167025dbb1ba1de97b45c12b50"
)
CANARY_COMPLETION_SHA256 = (
    "454e3648f3a9cfeafafad1f5183cbae73908de4831313055ad150689fa7ee28e"
)
GRID_RELEASE_SHA256 = (
    "436bd49f413b9e84282c9765344b0cb23ca264c8eb172940cd5f63b6639c0f13"
)
CANARY_ATTEMPT0_RECEIPT_SHA256 = (
    "0a07b0cf77c2f67f61090c8be100885b4cf690340759b9068ddf8121b341066e"
)

EXPECTED_SOURCE_HASHES = {
    "reports/2026-08-17-atlas-historical-score-v3-execution-protocol.md": (
        "2a4b0ed6c6a2c4b15c052968248aefd0d8a1ff519c5ec2bce5c72bfb50020e7b"
    ),
    "reports/2026-08-16-atlas-historical-score-diagnostic-protocol.md": (
        "4b618b5f8b8b8ed61dc5518e5b8b1cb8d5941e92f088ddb0a53af05d37f4239e"
    ),
    "reports/2026-08-16-atlas-historical-score-source-parity-amendment.md": (
        "6e3997e4e81ffe20063fdf76aff7c3655cdd1424aea350a5e29a681a1cd1832e"
    ),
    "reports/2026-08-16-atlas-historical-score-sharded-upstream-amendment.md": (
        "ce32274be00678cdef24b3d174578a2e2ce212164166da2a712a9df1562fcd5d"
    ),
    "reports/2026-08-16-atlas-historical-score-repair4-upstream-amendment.md": (
        "32bb95916d53b0a95472adad6d0aebcb6f7fd1631b07b3c29b1cf31950dffd17"
    ),
    "reports/2026-08-16-atlas-historical-score-repair5-upstream-amendment.md": (
        "f5b43fd7a6c76c2296727152d55a9d87fb75809ac09367f31d3fc573879b0f11"
    ),
    "reports/2026-08-16-atlas-historical-score-attempt-binding-amendment.md": (
        "8fa4f7111d99070fc040eaa62ad4f5ade0817fe835244825d8ff0410e3cf35d3"
    ),
    "reports/2026-08-16-atlas-historical-score-repair5-canary-binding-amendment.md": (
        "c893d958b300484e0468d84763267ee89211178127bf84fc664a9bbc8170ee1e"
    ),
    "reports/2026-08-16-atlas-historical-high-tail-guard-amendment.md": (
        "b98227830aed550a3f024b85695a3c0bbf7195834320370c41cf3c3e5ca5693d"
    ),
    "reports/2026-08-17-atlas-historical-score-canary-validator-repair-binding-amendment.md": (
        "f986238a0919879944d4bddbb76855676fd5b96b5e20064f9797476cc20e5477"
    ),
    "reports/2026-08-16-atlas-mvp-resource-only-repair5.md": (
        "5acc93c2b3a59931aa17dbc67d98fca81d3a6ac047011cfe1a9a81aa1ee8550e"
    ),
    "reports/2026-08-16-atlas-repair5-bounded-platform-retry-amendment.md": (
        "d464660b72e669d261d7f6d4800b3e59d55726b56e7003c5e3e806f38fa987a0"
    ),
    "reports/2026-08-16-atlas-repair5-real-path-canary-amendment.md": (
        "b2d0e32dabeb87bb1a67bee58c01f00c4c0d97e3fac9d1f7181bfcee50abc242"
    ),
    "reports/2026-08-17-atlas-repair5-canary-validator-quoting-repair.md": (
        "3929c805db67b0d9d66500f6b4d14c6ea4011d8c3723dd2b86535ea9a4e69d94"
    ),
    "scripts/cloud_wait_atlas_repair5_canary.sh": (
        "e1c82612f231976563f0df12ffbe9f5e2db1aebfae636f61b723ad8699ae1411"
    ),
    "scripts/cloud_atlas_matched_diversity_repair5.sh": (
        "3c8092c2bc3e40840a16867621f2f3ffe231f571d3f621818feab61dbefbe330"
    ),
    "scripts/cloud_prepare_atlas_matched_diversity_repair5_attempts.sh": (
        "705b65e5164b775361a2efe1440059f76978c3701c192179a40d85f4b0c27093"
    ),
    "scripts/cloud_finish_atlas_matched_diversity_repair5.sh": (
        "fe7a069e42bfece580ff4f312bc2990bd31339932713d834c2c123bbc431cdd9"
    ),
    "scripts/atlas_repair5_validator_bin/awk": (
        "42e0c74654f5e7ecb70e164aa1b28bc188f6279bde1273aa45093c51e5871b7a"
    ),
    "scripts/resume_atlas_repair5_after_canary_validator_quoting.sh": (
        "a2a00c559d74a38610736ccb93f695568993da6f65bc7ce7d82b2ecca527bb48"
    ),
    "scripts/run_atlas_matched_diversity_mvp.py": (
        "0548e26e26d7e81b20c6837adcc8925bc2317f9b7c8586fba084787581cac740"
    ),
    "scripts/render_atlas_matched_diversity_repair4_command.py": (
        "69d0ed1187bf59176a857e0bc822f65bd9aea2ffd211ffc247312796bfaeb671"
    ),
}

EXPECTED_CELLS = tuple(
    (season, week) for season in (2023, 2024, 2025) for week in range(1, 19)
)


def file_sha(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def canonical_json(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()


def load_json(path: Path) -> Any:
    return loads_json(path.read_text(encoding="utf-8"))


def loads_json(raw: str) -> Any:
    def reject(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise RuntimeError(f"duplicate JSON key: {key}")
            result[key] = value
        return result

    return json.loads(raw, object_pairs_hook=reject)


def parse_kv(path: Path) -> dict[str, str]:
    rows = [line.split("=", 1) for line in path.read_text(encoding="utf-8").splitlines()
            if "=" in line]
    if len(rows) != len({key for key, _ in rows}):
        raise RuntimeError(f"duplicate receipt key: {path}")
    return dict(rows)


def parse_primary_rows(path: Path) -> list[list[str]]:
    rows = [line.split() for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()]
    if len(rows) != 54 or any(len(row) != 5 for row in rows):
        raise RuntimeError("ATLAS historical v3 execution ledger is not exact 54")
    if {(int(row[0]), int(row[1])) for row in rows} != set(EXPECTED_CELLS) or \
            len({row[3] for row in rows}) != 54:
        raise RuntimeError("ATLAS historical v3 execution grid differs")
    for season, week, job, execution, uri in rows:
        expected_job = f"atlas-md-s{season}-w{week}-r5"
        if job != expected_job or not execution.startswith(expected_job + "-") or \
                uri != f"{UPSTREAM_PREFIX}/slate-{season}-{week}.json":
            raise RuntimeError("ATLAS historical v3 execution identity differs")
    return rows


def validate_execution_contract(
    value: Mapping[str, Any], row: Sequence[str], grid_command: str,
) -> None:
    season, week, job, execution, uri = row
    if value.get("metadata", {}).get("name") != execution:
        raise RuntimeError("ATLAS historical v3 execution name differs")
    spec = value.get("spec", {})
    task = spec.get("template", {}).get("spec", {})
    containers = task.get("containers", [])
    if spec.get("parallelism") != 1 or spec.get("taskCount") != 1 or \
            len(containers) != 1:
        raise RuntimeError("ATLAS historical v3 task shape differs")
    container = containers[0]
    env = {item.get("name"): str(item.get("value", ""))
           for item in container.get("env", [])}
    if container.get("image") != UPSTREAM_IMAGE or \
            container.get("command") != ["python"] or \
            container.get("args") != [
                "-c", grid_command, "--season", season, "--week", week,
                "--output-uri", uri,
            ] or env != {
                "CODE_SHA": UPSTREAM_CODE_SHA, "ANALYSIS_IMAGE": UPSTREAM_IMAGE,
            } or container.get("resources", {}).get("limits") != {
                "cpu": "8", "memory": "32Gi",
            } or task.get("maxRetries") != 0 or \
            str(task.get("timeoutSeconds")) != "43200" or \
            task.get("serviceAccountName") != SERVICE_ACCOUNT:
        raise RuntimeError("ATLAS historical v3 execution contract differs")


def validate_execution(
    value: Mapping[str, Any], row: Sequence[str], grid_command: str,
) -> None:
    validate_execution_contract(value, row, grid_command)
    status = value.get("status", {})
    completed = [item for item in status.get("conditions", [])
                 if item.get("type") == "Completed"]
    if len(completed) != 1 or completed[0].get("status") != "True" or \
            int(status.get("succeededCount") or 0) != 1 or \
            int(status.get("failedCount") or 0) != 0 or not status.get("completionTime"):
        raise RuntimeError("ATLAS historical v3 execution was not successful")


def parse_retry_rows(path: Path) -> list[list[str]]:
    rows = [line.split() for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()]
    if any(len(row) != 6 for row in rows) or \
            len({(row[0], row[1]) for row in rows}) != len(rows) or \
            len({row[4] for row in rows}) != len(rows):
        raise RuntimeError("ATLAS historical v3 retry execution ledger differs")
    expected_cells = {(str(season), str(week)) for season, week in EXPECTED_CELLS}
    for season, week, job, primary, replacement, uri in rows:
        expected_job = f"atlas-md-s{season}-w{week}-r5"
        if (season, week) not in expected_cells or job != expected_job or \
                not primary.startswith(expected_job + "-") or \
                not replacement.startswith(expected_job + "-") or \
                primary == replacement or \
                uri != f"{UPSTREAM_PREFIX}/slate-{season}-{week}.json":
            raise RuntimeError("ATLAS historical v3 retry identity differs")
    return rows


def verify_sha256_ledger(
    *, root: Path, ledger: Path, expected_relatives: Sequence[str],
) -> None:
    """Validate both the population and every digest in a sha256sum ledger."""
    root = root.resolve()
    parsed: dict[str, str] = {}
    for raw in ledger.read_text(encoding="utf-8").splitlines():
        match = re.fullmatch(r"([0-9a-f]{64})\s+(.+)", raw)
        if match is None:
            raise RuntimeError(f"ATLAS historical v3 malformed hash ledger: {ledger}")
        digest, name = match.groups()
        path = Path(name)
        resolved = path.resolve() if path.is_absolute() else (root / path).resolve()
        try:
            relative = resolved.relative_to(root).as_posix()
        except ValueError as exc:
            raise RuntimeError("ATLAS historical v3 hash ledger leaves repository") from exc
        if relative in parsed:
            raise RuntimeError("ATLAS historical v3 duplicate hash-ledger path")
        parsed[relative] = digest
    expected = set(expected_relatives)
    if set(parsed) != expected:
        raise RuntimeError(f"ATLAS historical v3 hash-ledger population differs: {ledger}")
    for relative, digest in parsed.items():
        path = root / relative
        if not path.is_file() or file_sha(path) != digest:
            raise RuntimeError(f"ATLAS historical v3 hashed artifact differs: {relative}")


def _validate_object(value: Mapping[str, Any], uri: str) -> None:
    if value.get("uri") != uri or not str(value.get("generation", "")).isdigit() or \
            int(value.get("bytes") or 0) <= 0 or \
            not re.fullmatch(r"[0-9a-f]{64}", str(value.get("sha256", ""))):
        raise RuntimeError("ATLAS historical v3 object receipt differs")


def validate_receipt(receipt: Mapping[str, Any], grid_command: str) -> dict[str, Any]:
    """Validate one self-contained immutable v3 upstream source receipt."""
    fixed = {
        "version": "atlas-historical-upstream-receipt-v5",
        "historical_run_id": HISTORICAL_RUN_ID,
        "upstream_run_id": UPSTREAM_RUN_ID,
        "upstream_prefix": UPSTREAM_PREFIX,
        "upstream_code_sha": UPSTREAM_CODE_SHA,
        "upstream_image": UPSTREAM_IMAGE,
        "upstream_manifest_sha256": UPSTREAM_MANIFEST_SHA256,
        "primary_execution_ledger_sha256": PRIMARY_LEDGER_SHA256,
        "uses_realized_outcomes": False,
        "effect_fields_inspected": False,
        "canary_rerun": False,
    }
    if any(receipt.get(key) != value for key, value in fixed.items()) or \
            receipt.get("source_hashes") != EXPECTED_SOURCE_HASHES:
        raise RuntimeError("ATLAS historical v3 source receipt identity differs")
    primary = receipt.get("primary_execution_rows", [])
    accepted = receipt.get("accepted_execution_rows", [])
    retries = receipt.get("retry_execution_rows", [])
    if not isinstance(primary, list) or not isinstance(accepted, list) or \
            not isinstance(retries, list):
        raise RuntimeError("ATLAS historical v3 ledger payload differs")
    primary_rows = [[str(field) for field in row] for row in primary]
    accepted_rows = [[str(field) for field in row] for row in accepted]
    retry_rows = [[str(field) for field in row] for row in retries]
    for rows in (primary_rows, accepted_rows):
        if len(rows) != 54 or any(len(row) != 5 for row in rows) or \
                {(int(row[0]), int(row[1])) for row in rows} != set(EXPECTED_CELLS) or \
                len({row[3] for row in rows}) != 54:
            raise RuntimeError("ATLAS historical v3 embedded ledger differs")
        for season, week, job, execution, uri in rows:
            expected_job = f"atlas-md-s{season}-w{week}-r5"
            if job != expected_job or not execution.startswith(expected_job + "-") or \
                    uri != f"{UPSTREAM_PREFIX}/slate-{season}-{week}.json":
                raise RuntimeError("ATLAS historical v3 embedded identity differs")
    primary_by_cell = {(row[0], row[1]): row for row in primary_rows}
    accepted_by_cell = {(row[0], row[1]): row for row in accepted_rows}
    retry_by_cell: dict[tuple[str, str], list[str]] = {}
    if any(len(row) != 6 for row in retry_rows) or \
            len({(row[0], row[1]) for row in retry_rows}) != len(retry_rows) or \
            len({row[4] for row in retry_rows}) != len(retry_rows):
        raise RuntimeError("ATLAS historical v3 embedded retry ledger differs")
    for row in retry_rows:
        cell = (row[0], row[1])
        primary_row = primary_by_cell.get(cell)
        if primary_row is None or row[:4] != primary_row[:4] or \
                row[5] != primary_row[4] or row[4] == row[3] or \
                not row[4].startswith(row[2] + "-"):
            raise RuntimeError("ATLAS historical v3 retry-primary binding differs")
        retry_by_cell[cell] = row
    for cell, row in primary_by_cell.items():
        accepted_row = accepted_by_cell[cell]
        retry = retry_by_cell.get(cell)
        expected_execution = row[3] if retry is None else retry[4]
        if accepted_row[:3] != row[:3] or accepted_row[3] != expected_execution or \
                accepted_row[4] != row[4]:
            raise RuntimeError("ATLAS historical v3 accepted ledger binding differs")
    if primary_by_cell[("2023", "1")][3] != CANARY_EXECUTION or \
            accepted_by_cell[("2023", "1")][3] != CANARY_EXECUTION:
        raise RuntimeError("ATLAS historical v3 canary execution differs")
    if receipt.get("canary_job_executions") != [CANARY_EXECUTION]:
        raise RuntimeError("ATLAS historical v3 canary execution population differs")
    job_executions = receipt.get("job_execution_names", {})
    expected_job_keys = {row[2] for row in primary_rows}
    if set(job_executions) != expected_job_keys:
        raise RuntimeError("ATLAS historical v3 job-execution population differs")
    for cell, primary_row in primary_by_cell.items():
        retry = retry_by_cell.get(cell)
        expected_names = [primary_row[3]]
        if retry is not None:
            expected_names.append(retry[4])
        actual_names = job_executions.get(primary_row[2])
        if not isinstance(actual_names, list) or sorted(map(str, actual_names)) != \
                sorted(expected_names):
            raise RuntimeError("ATLAS historical v3 has an unreceipted execution")

    executions = receipt.get("accepted_execution_metadata", {})
    primary_metadata = receipt.get("primary_execution_metadata", {})
    expected_keys = {f"{season}-{week}" for season, week in EXPECTED_CELLS}
    if set(executions) != expected_keys or set(primary_metadata) != expected_keys:
        raise RuntimeError("ATLAS historical v3 execution metadata grid differs")
    for cell, row in accepted_by_cell.items():
        validate_execution(executions[f"{cell[0]}-{cell[1]}"], row, grid_command)
    for cell, row in primary_by_cell.items():
        value = primary_metadata[f"{cell[0]}-{cell[1]}"]
        # A replaced primary may be terminal False; its exact failure is bound by
        # the attempt classifier, so validate its immutable command separately.
        if row[3] == accepted_by_cell[cell][3]:
            validate_execution(value, row, grid_command)
        else:
            validate_execution_contract(value, row, grid_command)
            status = value.get("status", {})
            completed = [item for item in status.get("conditions", [])
                         if item.get("type") == "Completed"]
            if len(completed) != 1 or completed[0].get("status") != "False" or \
                    int(status.get("succeededCount") or 0) != 0 or \
                    int(status.get("failedCount") or 0) != 1 or \
                    not status.get("completionTime"):
                raise RuntimeError("ATLAS historical v3 replaced primary differs")

    strict = receipt.get("strict_harvest", {})
    required_strict = {
        "completion_sha256", "report_sha256", "season_reports_sha256",
        "shards_sha256", "execution_metadata_sha256",
        "primary_execution_metadata_sha256", "primary_object_inventory_sha256",
        "primary_attempt_classification_sha256", "retry_execution_ledger_sha256",
        "accepted_execution_ledger_sha256", "attempt_resolution_sha256",
        "attempt_artifacts_sha256", "canary_completion_sha256",
        "canary_execution_metadata_sha256", "canary_object_metadata_sha256",
        "canary_sha256", "grid_release_sha256", "validator_repair_sha256",
        "canary_attempt0_receipt_sha256", "canary_attempt0_metadata_sha256",
        "canary_attempt0_attempt_sha256",
    }
    if set(strict) != required_strict or any(
        not re.fullmatch(r"[0-9a-f]{64}", str(value)) for value in strict.values()
    ) or strict["canary_completion_sha256"] != CANARY_COMPLETION_SHA256 or \
            strict["grid_release_sha256"] != GRID_RELEASE_SHA256 or \
            strict["canary_attempt0_receipt_sha256"] != \
            CANARY_ATTEMPT0_RECEIPT_SHA256:
        raise RuntimeError("ATLAS historical v3 strict-harvest receipt differs")

    attempt = receipt.get("attempt", {})
    resolution = attempt.get("resolution", {})
    classification = attempt.get("classification", {})
    if resolution.get("version") != "atlas-repair5-attempt-resolution-v1" or \
            resolution.get("disposition") not in {
                "accepted-primary-population", "accepted-population-with-platform-replacements",
            } or resolution.get("uses_realized_outcomes") is not False or \
            resolution.get("effect_fields_inspected") is not False or \
            resolution.get("task_max_retries") != 0 or \
            resolution.get("max_replacement_executions_per_cell") != 1 or \
            resolution.get("primary_executions") != 54 or \
            resolution.get("accepted_executions") != 54 or \
            resolution.get("retry_executions") != len(retry_rows) or \
            classification.get("version") != \
            "atlas-repair5-primary-attempt-classification-v1" or \
            classification.get("uses_realized_outcomes") is not False or \
            classification.get("effect_fields_inspected") is not False or \
            classification.get("task_max_retries") != 0 or \
            classification.get("max_replacement_executions_per_cell") != 1 or \
            classification.get("primary_executions") != 54 or \
            classification.get("ineligible_failures") != 0 or \
            classification.get("eligible_replacements") != len(retry_rows):
        raise RuntimeError("ATLAS historical v3 attempt receipt differs")
    expected_resolution = (
        "accepted-primary-population" if not retry_rows
        else "accepted-population-with-platform-replacements"
    )
    expected_classification = (
        "all-primary-success" if not retry_rows else "replacement-required"
    )
    if resolution.get("disposition") != expected_resolution or \
            classification.get("disposition") != expected_classification:
        raise RuntimeError("ATLAS historical v3 attempt disposition differs")
    if resolution.get("classification_sha256") != \
            strict["primary_attempt_classification_sha256"] or \
            resolution.get("primary_execution_ledger_sha256") != \
            PRIMARY_LEDGER_SHA256 or \
            resolution.get("retry_execution_ledger_sha256") != \
            strict["retry_execution_ledger_sha256"] or \
            resolution.get("accepted_execution_ledger_sha256") != \
            strict["accepted_execution_ledger_sha256"] or \
            resolution.get("canary_completion_sha256") != \
            CANARY_COMPLETION_SHA256 or \
            resolution.get("grid_release_sha256") != GRID_RELEASE_SHA256 or \
            classification.get("primary_execution_ledger_sha256") != \
            PRIMARY_LEDGER_SHA256 or \
            classification.get("primary_object_inventory_sha256") != \
            strict["primary_object_inventory_sha256"] or \
            classification.get("canary_completion_sha256") != \
            CANARY_COMPLETION_SHA256 or \
            classification.get("grid_release_sha256") != GRID_RELEASE_SHA256:
        raise RuntimeError("ATLAS historical v3 attempt hash binding differs")
    cells = classification.get("cells", [])
    if not isinstance(cells, list) or len(cells) != 54 or \
            {(str(row.get("season")), str(row.get("week"))) for row in cells} != \
            {(str(season), str(week)) for season, week in EXPECTED_CELLS}:
        raise RuntimeError("ATLAS historical v3 attempt classification grid differs")
    for cell_row in cells:
        cell = (str(cell_row.get("season")), str(cell_row.get("week")))
        primary_row = primary_by_cell[cell]
        retry = retry_by_cell.get(cell)
        expected_eligibility = (
            "primary-success" if retry is None else "eligible-platform-replacement"
        )
        if cell_row.get("job") != primary_row[2] or \
                cell_row.get("primary_execution") != primary_row[3] or \
                cell_row.get("uri") != primary_row[4] or \
                cell_row.get("eligibility") != expected_eligibility or \
                bool(cell_row.get("object_present")) is not (retry is None):
            raise RuntimeError("ATLAS historical v3 attempt classification differs")

    objects = receipt.get("objects", {})
    if set(objects) != {"report", "season-2023", "season-2024", "season-2025"}:
        raise RuntimeError("ATLAS historical v3 aggregate object population differs")
    for key, value in objects.items():
        name = "report.json" if key == "report" else f"{key}.json"
        _validate_object(value, f"{UPSTREAM_PREFIX}/{name}")
    shards = receipt.get("shards", {})
    if set(shards) != expected_keys:
        raise RuntimeError("ATLAS historical v3 shard object population differs")
    for season, week in EXPECTED_CELLS:
        _validate_object(
            shards[f"{season}-{week}"],
            f"{UPSTREAM_PREFIX}/slate-{season}-{week}.json",
        )
    return {
        "accepted_rows": accepted_rows,
        "retry_rows": retry_rows,
        "execution_names": {
            f"{row[0]}-{row[1]}": row[3] for row in accepted_rows
        },
        "objects": objects,
        "strict_harvest": strict,
    }


def _local_object_receipt(
    *, uri: str, local: Path, metadata: Mapping[str, Any],
) -> dict[str, Any]:
    value = {
        "uri": uri,
        "generation": str(metadata.get("generation", "")),
        "bytes": local.stat().st_size,
        "sha256": file_sha(local),
        "md5_hash": str(metadata.get("md5_hash") or metadata.get("md5Hash") or ""),
        "crc32c": str(metadata.get("crc32c") or ""),
        "updated": str(metadata.get("updated") or ""),
    }
    if int(metadata.get("size") or 0) != value["bytes"]:
        raise RuntimeError("ATLAS historical v3 local/GCS object size differs")
    _validate_object(value, uri)
    return value


def build_receipt(
    *, root: Path, object_metadata: Mapping[str, Mapping[str, Any]],
    job_execution_names: Mapping[str, Sequence[str]], grid_command: str,
) -> dict[str, Any]:
    """Build the deterministic receipt without parsing any ATLAS effect file."""
    for relative, digest in EXPECTED_SOURCE_HASHES.items():
        path = root / relative
        if not path.is_file() or file_sha(path) != digest:
            raise RuntimeError(f"ATLAS historical v3 frozen source differs: {relative}")
    upstream = root / "reports/atlas-matched-diversity-runs" / UPSTREAM_RUN_ID
    required = [
        "manifest.txt", "executions.txt", "accepted-executions.txt",
        "retry-executions.txt", "attempt-resolution.json",
        "primary-attempt-classification.json", "completion.txt", "report.json",
        "season-2023.json", "season-2024.json", "season-2025.json",
        "completion.sha256", "report.sha256", "season-reports.sha256",
        "shards.sha256", "execution-metadata.sha256",
        "primary-execution-metadata.sha256", "primary-object-inventory.txt",
        "primary-object-inventory.sha256",
        "primary-attempt-classification.sha256", "attempt-resolution.sha256",
        "attempt-artifacts.sha256", "canary-completion.txt",
        "canary-execution-metadata.json", "canary-object-metadata.json",
        "canary.sha256", "grid-release.txt", "validator-repair.sha256",
        "canary-validator-attempt0/receipt.txt",
        "canary-validator-attempt0/metadata.sha256",
        "canary-validator-attempt0/attempt.sha256",
    ]
    for relative in required:
        if not (upstream / relative).is_file():
            raise RuntimeError(f"ATLAS historical v3 upstream lacks {relative}")
    if file_sha(upstream / "manifest.txt") != UPSTREAM_MANIFEST_SHA256 or \
            file_sha(upstream / "executions.txt") != PRIMARY_LEDGER_SHA256 or \
            file_sha(upstream / "canary-completion.txt") != CANARY_COMPLETION_SHA256 or \
            file_sha(upstream / "grid-release.txt") != GRID_RELEASE_SHA256 or \
            file_sha(upstream / "canary-validator-attempt0/receipt.txt") != \
            CANARY_ATTEMPT0_RECEIPT_SHA256:
        raise RuntimeError("ATLAS historical v3 fixed upstream receipt differs")
    completion = parse_kv(upstream / "completion.txt")
    if completion.get("primary_executions") != "54" or \
            completion.get("accepted_executions") != "54" or \
            completion.get("slates") != "54" or \
            completion.get("real_path_canary") != "passed" or \
            completion.get("released_after_canary") != "53" or \
            completion.get("uses_realized_outcomes") != "false" or \
            completion.get("production_change_licensed") != "false":
        raise RuntimeError("ATLAS historical v3 upstream completion differs")
    release = parse_kv(upstream / "grid-release.txt")
    if release.get("primary_executions") != "54" or \
            release.get("released_after_canary") != "53" or \
            release.get("canary_rerun") != "false" or \
            release.get("object_content_inspected") != "false" or \
            release.get("effect_fields_inspected") != "false" or \
            release.get("canary_completion_sha256") != CANARY_COMPLETION_SHA256 or \
            release.get("canary_validator_attempt0_receipt_sha256") != \
            CANARY_ATTEMPT0_RECEIPT_SHA256:
        raise RuntimeError("ATLAS historical v3 grid release differs")
    expected_repair_release = {
        "original_canary_validator_sha256": (
            "e1c82612f231976563f0df12ffbe9f5e2db1aebfae636f61b723ad8699ae1411"
        ),
        "canary_validator_repair_protocol_sha256": (
            "3929c805db67b0d9d66500f6b4d14c6ea4011d8c3723dd2b86535ea9a4e69d94"
        ),
        "canary_validator_awk_wrapper_sha256": (
            "42e0c74654f5e7ecb70e164aa1b28bc188f6279bde1273aa45093c51e5871b7a"
        ),
        "canary_validator_resume_sha256": (
            "a2a00c559d74a38610736ccb93f695568993da6f65bc7ce7d82b2ecca527bb48"
        ),
    }
    if any(release.get(key) != value for key, value in expected_repair_release.items()):
        raise RuntimeError("ATLAS historical v3 validator-repair release differs")
    canary = parse_kv(upstream / "canary-completion.txt")
    if canary.get("execution") != CANARY_EXECUTION or \
            canary.get("status") != "True" or \
            canary.get("disposition") != "real-path-canary-passes" or \
            canary.get("cell") != "2023-1" or \
            canary.get("remaining_cells_released") != "false" or \
            canary.get("object_content_inspected") != "false":
        raise RuntimeError("ATLAS historical v3 canary completion differs")
    attempt0 = parse_kv(upstream / "canary-validator-attempt0/receipt.txt")
    if attempt0.get("execution") != CANARY_EXECUTION or \
            attempt0.get("cloud_execution_terminal_success") != "true" or \
            attempt0.get("canary_rerun") != "false" or \
            attempt0.get("object_content_inspected") != "false" or \
            attempt0.get("effect_fields_inspected") != "false":
        raise RuntimeError("ATLAS historical v3 canary attempt0 receipt differs")

    primary_rows = parse_primary_rows(upstream / "executions.txt")
    accepted_rows = parse_primary_rows(upstream / "accepted-executions.txt")
    retry_rows = parse_retry_rows(upstream / "retry-executions.txt")
    base = upstream.relative_to(root).as_posix()
    accepted_names = [row[3] for row in accepted_rows]
    ledger_populations = {
        "completion.sha256": [f"{base}/completion.txt"],
        "report.sha256": [f"{base}/report.json"],
        "season-reports.sha256": [
            f"{base}/season-{season}.json" for season in (2023, 2024, 2025)
        ],
        "shards.sha256": [
            f"{base}/shards/slate-{season}-{week}.json"
            for season, week in EXPECTED_CELLS
        ],
        "execution-metadata.sha256": [
            f"{base}/execution-metadata/{name}.json" for name in accepted_names
        ],
        "primary-execution-metadata.sha256": [
            f"{base}/primary-execution-metadata/season-{season}-week-{week}.json"
            for season, week in EXPECTED_CELLS
        ],
        "primary-object-inventory.sha256": [
            f"{base}/primary-object-inventory.txt"
        ],
        "primary-attempt-classification.sha256": [
            f"{base}/primary-attempt-classification.json"
        ],
        "attempt-resolution.sha256": [
            f"{base}/{name}" for name in (
                "executions.txt", "retry-executions.txt", "accepted-executions.txt",
                "attempt-resolution.json",
            )
        ],
        "attempt-artifacts.sha256": [
            f"{base}/{name}" for name in (
                "executions.txt", "retry-executions.txt", "accepted-executions.txt",
                "attempt-resolution.json", "primary-attempt-classification.json",
                "primary-execution-metadata.sha256", "canary-completion.txt",
                "canary-execution-metadata.json", "canary-object-metadata.json",
                "grid-release.txt",
            )
        ],
        "canary.sha256": [
            f"{base}/{name}" for name in (
                "canary-execution-metadata.json", "canary-completion.txt",
                "canary-object-metadata.json",
            )
        ],
        "canary-validator-attempt0/metadata.sha256": [
            f"{base}/canary-validator-attempt0/{name}" for name in (
                "canary-execution-metadata.json", "canary-object-metadata.json",
            )
        ],
        "canary-validator-attempt0/attempt.sha256": [
            f"{base}/canary-validator-attempt0/{name}" for name in (
                "metadata.sha256", "receipt.txt",
            )
        ],
        "validator-repair.sha256": [
            "reports/2026-08-17-atlas-repair5-canary-validator-quoting-repair.md",
            "scripts/atlas_repair5_validator_bin/awk",
            "scripts/resume_atlas_repair5_after_canary_validator_quoting.sh",
            f"{base}/canary-validator-attempt0/attempt.sha256",
            f"{base}/canary-completion.txt",
            f"{base}/grid-release.txt",
        ],
    }
    for ledger, population in ledger_populations.items():
        verify_sha256_ledger(
            root=root, ledger=upstream / ledger, expected_relatives=population,
        )
    primary_by_cell = {(row[0], row[1]): row for row in primary_rows}
    accepted_by_cell = {(row[0], row[1]): row for row in accepted_rows}
    primary_metadata: dict[str, Any] = {}
    accepted_metadata: dict[str, Any] = {}
    for season, week in EXPECTED_CELLS:
        key = f"{season}-{week}"
        primary_path = upstream / "primary-execution-metadata" / (
            f"season-{season}-week-{week}.json"
        )
        accepted_path = upstream / "execution-metadata" / (
            f"{accepted_by_cell[(str(season), str(week))][3]}.json"
        )
        if not primary_path.is_file() or not accepted_path.is_file():
            raise RuntimeError("ATLAS historical v3 execution metadata is missing")
        primary_metadata[key] = load_json(primary_path)
        accepted_metadata[key] = load_json(accepted_path)
        validate_execution(
            accepted_metadata[key], accepted_by_cell[(str(season), str(week))],
            grid_command,
        )
        if primary_metadata[key].get("metadata", {}).get("name") != \
                primary_by_cell[(str(season), str(week))][3]:
            raise RuntimeError("ATLAS historical v3 primary metadata identity differs")

    objects: dict[str, Any] = {}
    for key, name in (
        ("report", "report.json"), ("season-2023", "season-2023.json"),
        ("season-2024", "season-2024.json"),
        ("season-2025", "season-2025.json"),
    ):
        uri = f"{UPSTREAM_PREFIX}/{name}"
        objects[key] = _local_object_receipt(
            uri=uri, local=upstream / name, metadata=object_metadata[uri],
        )
    shards = {}
    for season, week in EXPECTED_CELLS:
        key = f"{season}-{week}"
        uri = f"{UPSTREAM_PREFIX}/slate-{season}-{week}.json"
        shards[key] = _local_object_receipt(
            uri=uri, local=upstream / "shards" / f"slate-{season}-{week}.json",
            metadata=object_metadata[uri],
        )

    strict_paths = {
        "completion_sha256": "completion.txt",
        "report_sha256": "report.json",
        "season_reports_sha256": "season-reports.sha256",
        "shards_sha256": "shards.sha256",
        "execution_metadata_sha256": "execution-metadata.sha256",
        "primary_execution_metadata_sha256": "primary-execution-metadata.sha256",
        "primary_object_inventory_sha256": "primary-object-inventory.txt",
        "primary_attempt_classification_sha256": "primary-attempt-classification.json",
        "retry_execution_ledger_sha256": "retry-executions.txt",
        "accepted_execution_ledger_sha256": "accepted-executions.txt",
        "attempt_resolution_sha256": "attempt-resolution.json",
        "attempt_artifacts_sha256": "attempt-artifacts.sha256",
        "canary_completion_sha256": "canary-completion.txt",
        "canary_execution_metadata_sha256": "canary-execution-metadata.json",
        "canary_object_metadata_sha256": "canary-object-metadata.json",
        "canary_sha256": "canary.sha256",
        "grid_release_sha256": "grid-release.txt",
        "validator_repair_sha256": "validator-repair.sha256",
        "canary_attempt0_receipt_sha256": "canary-validator-attempt0/receipt.txt",
        "canary_attempt0_metadata_sha256": "canary-validator-attempt0/metadata.sha256",
        "canary_attempt0_attempt_sha256": "canary-validator-attempt0/attempt.sha256",
    }
    receipt = {
        "version": "atlas-historical-upstream-receipt-v5",
        "historical_run_id": HISTORICAL_RUN_ID,
        "upstream_run_id": UPSTREAM_RUN_ID,
        "upstream_prefix": UPSTREAM_PREFIX,
        "upstream_code_sha": UPSTREAM_CODE_SHA,
        "upstream_image": UPSTREAM_IMAGE,
        "upstream_manifest_sha256": UPSTREAM_MANIFEST_SHA256,
        "primary_execution_ledger_sha256": PRIMARY_LEDGER_SHA256,
        "uses_realized_outcomes": False,
        "effect_fields_inspected": False,
        "canary_rerun": False,
        "source_hashes": dict(EXPECTED_SOURCE_HASHES),
        "primary_execution_rows": primary_rows,
        "retry_execution_rows": retry_rows,
        "accepted_execution_rows": accepted_rows,
        "primary_execution_metadata": primary_metadata,
        "accepted_execution_metadata": accepted_metadata,
        "canary_job_executions": list(job_execution_names.get(
            "atlas-md-s2023-w1-r5", [],
        )),
        "job_execution_names": {
            str(job): list(names) for job, names in job_execution_names.items()
        },
        "strict_harvest": {
            key: file_sha(upstream / relative) for key, relative in strict_paths.items()
        },
        "attempt": {
            "classification": load_json(upstream / "primary-attempt-classification.json"),
            "resolution": load_json(upstream / "attempt-resolution.json"),
        },
        "objects": objects,
        "shards": shards,
    }
    validate_receipt(receipt, grid_command)
    return receipt
