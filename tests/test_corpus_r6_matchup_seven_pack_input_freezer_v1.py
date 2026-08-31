from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import importlib.util
import json
from pathlib import Path

import pytest

from nfl_dfs.research import corpus_r6_matchup_seven_pack_input_freezer_v1 as freezer
from nfl_dfs.research import corpus_r6_matchup_seven_pack_capture_v1 as capture
from nfl_dfs.research import corpus_r6_matchup_source_v2 as source
from nfl_dfs.research import corpus_r6_paid_source_normalized_snapshot_v1 as snapshot
from nfl_dfs.research import (
    corpus_r6_fixed_g0_candidate_authority_release_v2 as candidate_v2,
)


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
CLI_PATH = REPOSITORY_ROOT / "scripts/freeze_corpus_r6_matchup_seven_pack_inputs_v1.py"


def _identity(uri: str, label: str) -> dict[str, object]:
    raw = label.encode()
    return {
        "uri": uri,
        "generation": str(int(sha256(raw).hexdigest()[:12], 16) + 1),
        "sha256": sha256(raw).hexdigest(),
        "bytes": len(raw),
    }


def _candidate_identity() -> dict[str, object]:
    return _identity(
        f"gs://{candidate_v2.OUTPUT_BUCKET}/{candidate_v2.OUTPUT_NAMESPACE}/"
        f"fixture-run/{candidate_v2.ROOT_FILENAME}",
        "candidate-v2",
    )


def _terminal_identity() -> dict[str, object]:
    return _identity(
        f"{snapshot.OUTPUT_PREFIX}/fixture-run/snapshot-terminal.json",
        "normalized-terminal",
    )


def _spec() -> dict[str, object]:
    return {
        "schema_version": freezer.FREEZE_SPEC_SCHEMA,
        "run_id": "sevenpack-input-freeze-test",
        "candidate_authority_v2_root_identity": _candidate_identity(),
        "normalized_snapshot_terminal_identity": _terminal_identity(),
    }


def _load_cli() -> object:
    spec = importlib.util.spec_from_file_location("seven_pack_input_freezer_cli", CLI_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_freeze_builds_terminal_bound_request_without_loose_manifests() -> None:
    result = freezer.freeze_seven_pack_inputs_v1(spec_value=_spec())
    receipt = result["receipt"]
    assert receipt["complete"] is True
    assert receipt["external_read_count"] == 0
    assert receipt["artifact_manifest_identities_accepted_from_caller"] is False
    assert receipt["normalized_snapshot_deep_reopen_required"] is True
    assert receipt["warehouse_query_pack_ids"] == list(capture.WAREHOUSE_PACK_IDS)
    assert receipt["artifact_pack_ids"] == list(capture.ARTIFACT_PACK_IDS)
    request = json.loads(result["files"]["seven-pack-request.json"])
    assert request["candidate_authority_v2_root_identity"] == _candidate_identity()
    assert request["normalized_snapshot_terminal_identity"] == _terminal_identity()
    assert "artifact_manifest_identities" not in request
    assert set(result["files"]) == {
        "seven-pack-request.json", "seven-pack-request.identity.json",
        "freeze-receipt.json",
    }


def test_missing_terminal_identity_fails_explicitly() -> None:
    spec = _spec()
    del spec["normalized_snapshot_terminal_identity"]
    with pytest.raises(
        freezer.CorpusR6MatchupSevenPackInputFreezerV1Error,
        match="freeze spec fields differ",
    ):
        freezer.freeze_seven_pack_inputs_v1(spec_value=spec)


def test_candidate_must_be_v2_terminal_namespace() -> None:
    spec = deepcopy(_spec())
    spec["candidate_authority_v2_root_identity"]["uri"] = (
        "gs://wrong-bucket/candidate-authority-release-v2.json"
    )
    with pytest.raises(
        freezer.CorpusR6MatchupSevenPackInputFreezerV1Error,
        match="candidate-authority v2 root URI differs",
    ):
        freezer.freeze_seven_pack_inputs_v1(spec_value=spec)


def test_cli_is_default_off_and_writes_only_new_explicit_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    cli = _load_cli()
    spec_path = (tmp_path / "spec.json").resolve()
    output = (tmp_path / "frozen").resolve()
    spec_path.write_bytes(source.canonical_json_bytes(_spec()))
    argv = [
        "--spec", str(spec_path),
        "--output-directory", str(output),
        "--confirm-freeze",
    ]
    monkeypatch.delenv(freezer.FREEZE_ENABLE_ENV, raising=False)
    with pytest.raises(cli.SevenPackInputFreezerCliError, match="freeze is disabled"):
        cli.run(argv)
    assert not output.exists()
    monkeypatch.setenv(freezer.FREEZE_ENABLE_ENV, freezer.ENABLE_VALUE)
    receipt = cli.run(argv)
    assert receipt["complete"] is True
    assert (output / "seven-pack-request.json").is_file()
    assert (output / "freeze-receipt.json").is_file()
    with pytest.raises(
        cli.SevenPackInputFreezerCliError,
        match="output directory must be one absent path",
    ):
        cli.run(argv)
