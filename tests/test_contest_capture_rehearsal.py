"""Local-only contract for the Week-1 contest-capture rehearsal."""

from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

import pandas as pd
import pytest

from nfl_dfs.ingest import contest_capture_rehearsal as rehearsal
from nfl_dfs.ingest import ownership_import


FIXTURE = Path(__file__).parent / "fixtures" / "week1_contest_capture"
TRACKED_RECEIPT = (
    Path(__file__).parents[1]
    / "reports"
    / "week1-contest-capture-rehearsal"
    / "fixture-v1"
    / "receipt.json"
)
CAPTURED_AT = "2026-09-14T23:00:00Z"
REHEARSED_AT = "2026-09-01T16:00:00Z"


def _paths(root: Path = FIXTURE) -> tuple[Path, Path]:
    return (
        root / "contest-standings-12345.csv",
        root / "contest-manifest-v2.json",
    )


def _copy_fixture(tmp_path: Path) -> Path:
    target = tmp_path / "fixture"
    shutil.copytree(FIXTURE, target)
    return target


def _run(root: Path = FIXTURE) -> dict[str, object]:
    standings, manifest = _paths(root)
    return rehearsal.rehearse_capture(
        standings_path=standings,
        manifest_path=manifest,
        captured_at=CAPTURED_AT,
        rehearsed_at=REHEARSED_AT,
        confirm_settled=True,
        confirm_full_field=True,
    )


def _rewrite_and_rehash_bound_book(
    root: Path, *, binding_index: int, mutate
) -> None:
    _, manifest_path = _paths(root)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    binding = manifest["book_bindings"][binding_index]
    artifact_path = root / binding["artifact_identity"]["uri"]
    artifact = json.loads(artifact_path.read_text(encoding="utf-8"))
    mutate(artifact)
    payload = (json.dumps(artifact, sort_keys=True, indent=2) + "\n").encode()
    artifact_path.write_bytes(payload)
    binding["artifact_identity"]["sha256"] = hashlib.sha256(payload).hexdigest()
    binding["artifact_identity"]["bytes"] = len(payload)
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")


def _rewrite_and_rehash_source(root: Path, *, source_name: str, mutate) -> None:
    _, manifest_path = _paths(root)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    identity = manifest["source_identities"][source_name]
    source_path = root / identity["uri"]
    source = json.loads(source_path.read_text(encoding="utf-8"))
    mutate(source)
    payload = (json.dumps(source, sort_keys=True, indent=2) + "\n").encode()
    source_path.write_bytes(payload)
    identity["sha256"] = hashlib.sha256(payload).hexdigest()
    identity["bytes"] = len(payload)
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")


def test_rehearsal_runs_production_validator_without_external_writes(monkeypatch):
    def unexpected(*args, **kwargs):
        raise AssertionError("local rehearsal attempted an external write")

    monkeypatch.setattr(ownership_import, "_archive_bytes_create_only", unexpected)
    monkeypatch.setattr(ownership_import, "load_dataframe", unexpected)

    receipt = _run()

    assert receipt["schema_version"] == rehearsal.RECEIPT_SCHEMA
    assert receipt["mode"] == "local-validation-only"
    assert receipt["network_or_cloud_reads_performed"] is False
    assert receipt["external_writes_performed"] is False
    assert receipt["scientific_or_production_evidence_allowed"] is False
    assert receipt["apply_eligible"] is False
    assert receipt["complete"] is True
    assert receipt["timeline"] == {
        "rehearsed_at": REHEARSED_AT,
        "representative_capture_at": CAPTURED_AT,
        "representative_capture_is_simulated": True,
    }
    capture = receipt["capture_validation"]
    assert capture["status"] == "validated-only"
    assert capture["apply_required_for_live_capture"] is True
    assert capture["contest"]["observed_entries"] == 4
    assert capture["contest"]["ownership_rows"] == 9
    assert receipt["outcome_access"] == {
        "settlement_values_read": True,
        "synthetic_outcomes_read": True,
        "live_realized_outcomes_read": False,
        "outcome_bearing_when_rehearsal_fixture_false": True,
    }
    structural = receipt["warehouse_structural_rehearsal"]
    assert structural["load_calls_performed"] == 0
    assert structural["live_destination_identity_reproduced"] is False
    assert structural["entries_payload"]["row_count"] == 4
    assert structural["ownership_payload"]["row_count"] == 9
    assert receipt["book_binding_summary"] == {
        "paid_book_count": 1,
        "shadow_book_count": 1,
        "paid_entry_count": 2,
        "all_books_frozen_before_lock": True,
    }

    supplied = receipt["receipt_sha256"]
    unhashed = dict(receipt)
    del unhashed["receipt_sha256"]
    assert supplied == rehearsal._sha256(rehearsal._canonical_bytes(unhashed))


def test_rehearsal_reconciles_winner_and_payout_ladder():
    settlement = _run()["settlement_rehearsal"]
    assert settlement["payout_reconciled"] is True
    assert settlement["scheduled_prize_pool_micro"] == 1_150_000_000
    assert settlement["observed_prize_pool_micro"] == 1_150_000_000
    assert settlement["winner_score_micropoints"] == 200_500_000
    assert settlement["winner_entry_ids"] == ["0001"]
    assert settlement["first_place_tie_count"] == 1


def test_tracked_fixture_receipt_exactly_reproduces():
    assert rehearsal.receipt_bytes(_run()) == TRACKED_RECEIPT.read_bytes()


def test_rehearsal_reconciles_a_tie_across_payout_positions(tmp_path):
    root = _copy_fixture(tmp_path)
    standings, _ = _paths(root)
    frame = pd.read_csv(standings, dtype=str)
    frame.loc[0:3, "Rank"] = ["1", "1", "3", "4"]
    frame.loc[0:3, "Points"] = ["200.0", "200.0", "180.0", "170.0"]
    frame.loc[0:3, "Winnings"] = ["$550", "$550", "$50", "$0"]
    frame.to_csv(standings, index=False)

    settlement = _run(root)["settlement_rehearsal"]

    assert settlement["payout_reconciled"] is True
    assert settlement["first_place_tie_count"] == 2
    assert settlement["winner_entry_ids"] == ["0001", "0002"]
    assert settlement["maximum_tie_rounding_residual_micro"] == 0


def test_rehearsal_rejects_payout_disagreement(tmp_path):
    root = _copy_fixture(tmp_path)
    standings, _ = _paths(root)
    frame = pd.read_csv(standings, dtype=str)
    frame.loc[0, "Winnings"] = "$999"
    frame.to_csv(standings, index=False)

    with pytest.raises(rehearsal.CaptureRehearsalError, match="split payout"):
        _run(root)


def test_rehearsal_reopens_manifest_sources_and_books_by_content(tmp_path):
    root = _copy_fixture(tmp_path)
    (root / "paid-book.json").write_text("tampered\n", encoding="utf-8")

    with pytest.raises(
        rehearsal.CaptureRehearsalError, match="content identity"
    ):
        _run(root)


def test_rehearsal_rejects_rehashed_book_with_wrong_contest(tmp_path):
    root = _copy_fixture(tmp_path)
    _rewrite_and_rehash_bound_book(
        root,
        binding_index=0,
        mutate=lambda artifact: artifact.__setitem__("contest_id", "99999"),
    )

    with pytest.raises(
        rehearsal.CaptureRehearsalError, match="semantics do not exactly match"
    ):
        _run(root)


def test_rehearsal_rejects_rehashed_source_with_wrong_contest(tmp_path):
    root = _copy_fixture(tmp_path)
    _rewrite_and_rehash_source(
        root,
        source_name="contest_metadata",
        mutate=lambda source: source.__setitem__("contest_id", "99999"),
    )

    with pytest.raises(
        rehearsal.CaptureRehearsalError,
        match="metadata evidence does not exactly match",
    ):
        _run(root)


def test_rehearsal_rejects_rehashed_book_with_wrong_lineup_count(tmp_path):
    root = _copy_fixture(tmp_path)
    _rewrite_and_rehash_bound_book(
        root,
        binding_index=0,
        mutate=lambda artifact: artifact["lineup_ids"].pop(),
    )

    with pytest.raises(
        rehearsal.CaptureRehearsalError, match="exact-count and unique"
    ):
        _run(root)


def test_rehearsal_rejects_source_mutation_between_validation_reads(
    tmp_path, monkeypatch
):
    root = _copy_fixture(tmp_path)
    standings, _ = _paths(root)
    original = ownership_import.capture_full_field

    def mutate_after_first_read(*args, **kwargs):
        result = original(*args, **kwargs)
        standings.write_bytes(standings.read_bytes() + b"\n")
        return result

    monkeypatch.setattr(
        ownership_import, "capture_full_field", mutate_after_first_read
    )
    with pytest.raises(
        rehearsal.CaptureRehearsalError, match="changed between validation reads"
    ):
        _run(root)


def test_rehearsal_rejects_postlock_book_binding(tmp_path):
    root = _copy_fixture(tmp_path)
    _, manifest_path = _paths(root)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["book_bindings"][0]["frozen_at"] = "2026-09-13T18:00:00Z"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(
        rehearsal.CaptureRehearsalError, match="book must freeze"
    ):
        _run(root)


def test_real_data_rehearsal_cannot_predate_capture(tmp_path):
    root = _copy_fixture(tmp_path)
    _, manifest_path = _paths(root)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["rehearsal_fixture"] = False
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(
        rehearsal.CaptureRehearsalError, match="cannot precede"
    ):
        _run(root)


def test_real_data_rehearsal_discloses_live_outcome_access(tmp_path):
    root = _copy_fixture(tmp_path)
    standings, manifest_path = _paths(root)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["rehearsal_fixture"] = False
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    receipt = rehearsal.rehearse_capture(
        standings_path=standings,
        manifest_path=manifest_path,
        captured_at=CAPTURED_AT,
        rehearsed_at="2026-09-15T00:00:00Z",
        confirm_settled=True,
        confirm_full_field=True,
    )

    assert receipt["outcome_access"]["live_realized_outcomes_read"] is True
    assert receipt["outcome_access"]["synthetic_outcomes_read"] is False


def test_rehearsal_requires_explicit_operator_confirmations():
    standings, manifest = _paths()
    with pytest.raises(
        rehearsal.CaptureRehearsalError, match="explicit confirm_settled"
    ):
        rehearsal.rehearse_capture(
            standings_path=standings,
            manifest_path=manifest,
            captured_at=CAPTURED_AT,
            rehearsed_at=REHEARSED_AT,
            confirm_settled=False,
            confirm_full_field=True,
        )


def test_local_receipt_is_create_only_and_retry_safe(tmp_path):
    receipt = _run()
    path = tmp_path / "receipt.json"

    assert rehearsal.write_receipt_create_only(path, receipt) == "created"
    assert rehearsal.write_receipt_create_only(path, receipt) == "already-identical"

    changed = dict(receipt)
    changed["complete"] = False
    with pytest.raises(
        rehearsal.CaptureRehearsalError, match="create-only receipt conflict"
    ):
        rehearsal.write_receipt_create_only(path, changed)
