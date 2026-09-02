from __future__ import annotations

import importlib.util
import json
import os
from hashlib import sha256
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/run_corpus_r6_historical_realized_summary_v1.py"
SPEC = importlib.util.spec_from_file_location("historical_realized_runner", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
runner = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(runner)


def _identity(uri: str, *, marker: str = "") -> dict[str, object]:
    return {
        "uri": uri,
        "generation": str(int.from_bytes(sha256((uri + marker).encode()).digest()[:4])),
        "sha256": sha256((marker + uri).encode()).hexdigest(),
        "bytes": 2,
    }


def _manifests() -> tuple[dict[str, object], dict[str, object], dict[str, object]]:
    candidate_rows: list[dict[str, object]] = []
    catalog_rows: list[dict[str, object]] = []
    attribution_rows: list[dict[str, object]] = []
    for ordinal in range(runner.EXPECTED_SLATE_COUNT):
        season = 2023 + ordinal // 18
        week = ordinal % 18 + 1
        slate = f"{season}-w{week:02d}"
        candidate_rows.extend(
            (
                {
                    "role": "candidate_artifact",
                    "source_task_ordinal": ordinal,
                    "identity": _identity(
                        f"gs://fixture/source-task-{ordinal:02d}-{slate}/"
                        "accepted-candidates.json"
                    ),
                },
                {
                    "role": "exact_occurrence_lineage_sidecar",
                    "source_task_ordinal": ordinal,
                    "identity": _identity(
                        f"gs://fixture/source-task-{ordinal:02d}-{slate}/"
                        "exact-occurrence-lineage.json"
                    ),
                },
            )
        )
        catalog_rows.append(
            {
                "role": "player_catalog",
                "source_task_ordinal": ordinal,
                "identity": _identity(
                    f"gs://fixture/tasks/{ordinal:04d}-{slate}/player-catalog.json"
                ),
            }
        )
        attribution_rows.append(_identity(f"gs://fixture/{ordinal:02d}-{slate}.json"))
    return (
        {"non_root_publication_manifest": list(reversed(candidate_rows))},
        {"inner_object_manifest": list(reversed(catalog_rows))},
        {
            "predecessors": {
                "attribution_shard_identities": list(reversed(attribution_rows))
            }
        },
    )


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n")


def _staging_fixture(tmp_path: Path) -> tuple[Path, Path, Path, Path]:
    staging = tmp_path / "staging"
    staging.mkdir()
    candidate, catalog, funnel = _manifests()
    candidate_identity = _identity("gs://fixture/candidate-root.json")
    catalog_identity = _identity("gs://fixture/catalog-root.json")
    funnel_identity = _identity("gs://fixture/funnel-root.json")
    candidate["catalog_recovery_outer_identity"] = catalog_identity
    _write_json(staging / "candidate-authority-release-v2.json", candidate)
    _write_json(staging / "fixed-g0-catalog-recovery-attestation-v2.json", catalog)
    _write_json(staging / "no-rescore-funnel-release.json", funnel)
    candidate_identity_path = tmp_path / "candidate-identity.json"
    funnel_reopen_path = tmp_path / "funnel-reopen.json"
    receipt_path = tmp_path / "accepted-receipt.json"
    _write_json(candidate_identity_path, candidate_identity)
    _write_json(funnel_reopen_path, {"funnel_release_identity": funnel_identity})
    _write_json(receipt_path, {"fixture": True})

    roles, _ = runner._manifest_descriptors(
        candidate_root=candidate,
        catalog_root=catalog,
        funnel_root=funnel,
    )
    for role, directory_name in runner._ROLE_DIRECTORIES.items():
        directory = staging / directory_name
        directory.mkdir()
        for _, filename in roles[role].values():
            (directory / filename).write_text("{}")
    return staging, candidate_identity_path, funnel_reopen_path, receipt_path


def test_manifest_mapping_is_coordinate_derived_not_positionally_zipped() -> None:
    candidate, catalog, funnel = _manifests()
    roles, slates = runner._manifest_descriptors(
        candidate_root=candidate,
        catalog_root=catalog,
        funnel_root=funnel,
    )
    assert set(slates) == set(range(54))
    assert slates[0] == "2023-w01"
    assert slates[53] == "2025-w18"
    assert roles["candidate_artifact"][7][1] == "7.json"
    assert roles["exact_occurrence_lineage_sidecar"][7][1] == "7.json"
    assert roles["player_catalog"][7][1] == "7.json"
    assert roles["attribution_shard"][7][1] == "07-2023-w08.json"


def test_prepare_bundle_requires_exact_219_file_coordinate_grid(
    tmp_path: Path,
) -> None:
    staging, candidate_identity, funnel_reopen, receipt = _staging_fixture(tmp_path)
    exact, *_ = runner._prepare_bundle(
        staging_dir=staging,
        candidate_root_identity_path=candidate_identity,
        funnel_reopen_summary_path=funnel_reopen,
        accepted_e0_receipt_path=receipt,
    )
    assert len(exact) == 219
    assert len({item.path for item in exact}) == 219
    assert exact[0].path.name == "candidate-authority-release-v2.json"
    assert exact[-1].path.name == "53-2025-w18.json"


def test_role_directory_rejects_missing_and_extra_entries(tmp_path: Path) -> None:
    staging, candidate_identity, funnel_reopen, receipt = _staging_fixture(tmp_path)
    role_dir = staging / "candidate-artifacts"
    (role_dir / "0.json").unlink()
    (role_dir / "unexpected.json").write_text("{}")
    with pytest.raises(
        runner.HistoricalRealizedSummaryRunnerError,
        match=r"missing=.*0\.json.*extra=.*unexpected\.json",
    ):
        runner._prepare_bundle(
            staging_dir=staging,
            candidate_root_identity_path=candidate_identity,
            funnel_reopen_summary_path=funnel_reopen,
            accepted_e0_receipt_path=receipt,
        )


@pytest.mark.parametrize("kind", ["symlink", "hardlink"])
def test_input_registry_rejects_file_aliases(tmp_path: Path, kind: str) -> None:
    source = tmp_path / "source.json"
    alias = tmp_path / "alias.json"
    source.write_text("{}")
    if kind == "symlink":
        alias.symlink_to(source)
    else:
        os.link(source, alias)
    registry = runner._InputFileRegistry()
    with pytest.raises(
        runner.HistoricalRealizedSummaryRunnerError,
        match="symlink|hard-linked",
    ):
        registry.file(alias if kind == "symlink" else source, label="fixture")


def test_manifest_rejects_unsafe_or_duplicate_coordinates() -> None:
    candidate, catalog, funnel = _manifests()
    candidate["non_root_publication_manifest"][0]["identity"]["uri"] = (
        "gs://fixture/source-task-53-2025-w18/../accepted-candidates.json"
    )
    with pytest.raises(
        runner.HistoricalRealizedSummaryRunnerError,
        match="URI coordinate is unsafe or differs",
    ):
        runner._manifest_descriptors(
            candidate_root=candidate,
            catalog_root=catalog,
            funnel_root=funnel,
        )


def test_create_once_output_is_canonical_lf_and_outside_staging(
    tmp_path: Path,
) -> None:
    staging = tmp_path / "staging"
    staging.mkdir()
    with pytest.raises(
        runner.HistoricalRealizedSummaryRunnerError,
        match="outside",
    ):
        runner._output_path(staging / "summary.json", staging_dir=staging)
    output = runner._output_path(tmp_path / "summary.json", staging_dir=staging)
    runner._write_create_once(output, {"complete": True, "value": 1})
    assert output.read_bytes() == b'{"complete":true,"value":1}\n'
    with pytest.raises(
        runner.HistoricalRealizedSummaryRunnerError,
        match="overwrite",
    ):
        runner._write_create_once(output, {"complete": True})


def test_runner_source_has_only_fixed_local_interface() -> None:
    source = SCRIPT.read_text()
    for required in (
        'parser.add_argument("--staging-dir"',
        'parser.add_argument("--candidate-root-identity"',
        'parser.add_argument("--funnel-reopen-summary"',
        'parser.add_argument("--accepted-e0-receipt"',
        'parser.add_argument("--output"',
        'path.open("xb")',
    ):
        assert required in source
    for forbidden in (
        "glob(",
        "rglob(",
        "google.cloud",
        "requests.",
        "import neo4j",
        "nfl_dfs.scoring",
        "--threshold",
        "--project",
        "--bucket",
    ):
        assert forbidden not in source
