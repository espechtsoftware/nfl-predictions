from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

import pytest

from scripts import publish_week1_operating_book as runner


SOURCE_IDENTITY = {
    "uri": "gs://example-bucket/week1/terminal-envelope.json",
    "generation": "123",
    "sha256": "a" * 64,
    "bytes": 1234,
}
OUTPUT_IDENTITY = {
    "uri": "gs://example-bucket/week1/operating-book-k80.json",
    "generation": "456",
    "sha256": "b" * 64,
    "bytes": 5678,
}
MATERIALIZATION_SHA = "c" * 64
SELECTED_SHA = "d" * 64
PUBLICATION_SHA = "e" * 64
ROOT = Path(__file__).resolve().parents[1]


def _arguments(*, apply: bool = True, confirmation: str | None = None) -> list[str]:
    values = [
        "--confirm",
        runner.CONFIRMATION_PHRASE if confirmation is None else confirmation,
        "--terminal-envelope-uri",
        str(SOURCE_IDENTITY["uri"]),
        "--terminal-envelope-generation",
        str(SOURCE_IDENTITY["generation"]),
        "--terminal-envelope-sha256",
        str(SOURCE_IDENTITY["sha256"]),
        "--terminal-envelope-bytes",
        str(SOURCE_IDENTITY["bytes"]),
        "--output-uri",
        str(OUTPUT_IDENTITY["uri"]),
        "--k",
        "80",
    ]
    return (["--apply"] if apply else []) + values


def _publication() -> dict[str, object]:
    return {
        "complete": True,
        "k": 80,
        "materialization_identity": deepcopy(OUTPUT_IDENTITY),
        "materialization_sha256": MATERIALIZATION_SHA,
        "publication_receipt_sha256": PUBLICATION_SHA,
        "create_once": True,
        "independent_exact_reopen": True,
    }


def _reopened() -> dict[str, object]:
    return {
        "identity": deepcopy(OUTPUT_IDENTITY),
        "storage_created_at": "2026-09-13T15:00:00+00:00",
        "materialization": {
            "k": 80,
            "materialization_sha256": MATERIALIZATION_SHA,
            "selected_lineup_ids_sha256": SELECTED_SHA,
            "cap4_used": False,
            "tier3_used": False,
            "uses_realized_outcomes": False,
        },
    }


@pytest.mark.parametrize(
    ("apply", "confirmation"),
    ((False, None), (True, "wrong-confirmation")),
)
def test_command_defaults_off_before_store_or_publication(
    monkeypatch, capsys, apply: bool, confirmation: str | None
) -> None:
    called: list[str] = []
    monkeypatch.setattr(
        runner,
        "publish_week1_operating_book_v1",
        lambda **_kwargs: called.append("publish"),
    )

    result = runner.main(
        _arguments(apply=apply, confirmation=confirmation),
        store_factory=lambda: called.append("store"),
    )

    captured = capsys.readouterr()
    assert result == 2
    assert called == []
    assert captured.out == ""
    assert "disabled" in captured.err
    assert "WEEK1_OPERATING_BOOK_URI" not in captured.err


def test_success_emits_exact_app_identity_only_after_second_read(
    monkeypatch, capsys
) -> None:
    events: list[tuple[str, object]] = []
    store = object()

    def fake_publish(**kwargs):
        events.append(("publish", kwargs))
        return _publication()

    def fake_read(**kwargs):
        events.append(("read", kwargs))
        return _reopened()

    monkeypatch.setattr(runner, "publish_week1_operating_book_v1", fake_publish)
    monkeypatch.setattr(runner, "read_week1_operating_book_v1", fake_read)

    result = runner.main(_arguments(), store_factory=lambda: store)

    captured = capsys.readouterr()
    assert result == 0
    assert captured.err == ""
    report = json.loads(captured.out)
    assert [event[0] for event in events] == ["publish", "read"]
    assert events[0][1] == {
        "store": store,
        "terminal_prelock_envelope_identity": SOURCE_IDENTITY,
        "target_uri": OUTPUT_IDENTITY["uri"],
        "k": 80,
    }
    assert events[1][1] == {
        "store": store,
        "materialization_identity": OUTPUT_IDENTITY,
    }
    assert report["complete"] is True
    assert report["independent_exact_reopen"] is True
    assert report["deployment_mutation_performed"] is False
    assert report["uses_realized_outcomes"] is False
    assert report["app_environment"] == {
        "WEEK1_OPERATING_BOOK_URI": OUTPUT_IDENTITY["uri"],
        "WEEK1_OPERATING_BOOK_GENERATION": OUTPUT_IDENTITY["generation"],
        "WEEK1_OPERATING_BOOK_SHA256": OUTPUT_IDENTITY["sha256"],
        "WEEK1_OPERATING_BOOK_BYTES": str(OUTPUT_IDENTITY["bytes"]),
    }


@pytest.mark.parametrize(
    "mutation",
    ("identity", "materialization_sha", "cap4", "tier3", "outcome"),
)
def test_independent_reopen_drift_emits_no_configuration(
    monkeypatch, capsys, mutation: str
) -> None:
    reopened = _reopened()
    if mutation == "identity":
        reopened["identity"]["generation"] = "999"
    elif mutation == "materialization_sha":
        reopened["materialization"]["materialization_sha256"] = "f" * 64
    elif mutation == "cap4":
        reopened["materialization"]["cap4_used"] = True
    elif mutation == "tier3":
        reopened["materialization"]["tier3_used"] = True
    else:
        reopened["materialization"]["uses_realized_outcomes"] = True
    monkeypatch.setattr(
        runner, "publish_week1_operating_book_v1", lambda **_kwargs: _publication()
    )
    monkeypatch.setattr(
        runner, "read_week1_operating_book_v1", lambda **_kwargs: reopened
    )

    result = runner.main(_arguments(), store_factory=object)

    captured = capsys.readouterr()
    assert result == 2
    assert captured.out == ""
    assert "failed closed" in captured.err
    assert "WEEK1_OPERATING_BOOK_URI" not in captured.err


def test_publication_failure_emits_no_configuration(monkeypatch, capsys) -> None:
    def fail(**_kwargs):
        raise RuntimeError("create-once collision")

    monkeypatch.setattr(runner, "publish_week1_operating_book_v1", fail)
    monkeypatch.setattr(
        runner,
        "read_week1_operating_book_v1",
        lambda **_kwargs: pytest.fail("read must not follow a failed publication"),
    )

    result = runner.main(_arguments(), store_factory=object)

    captured = capsys.readouterr()
    assert result == 2
    assert captured.out == ""
    assert "failed closed" in captured.err
    assert "WEEK1_OPERATING_BOOK_URI" not in captured.err


def test_output_uri_cannot_reuse_source_object(monkeypatch, capsys) -> None:
    arguments = _arguments()
    output_index = arguments.index("--output-uri") + 1
    arguments[output_index] = str(SOURCE_IDENTITY["uri"])
    monkeypatch.setattr(
        runner,
        "publish_week1_operating_book_v1",
        lambda **_kwargs: pytest.fail("collision must fail before publication"),
    )

    result = runner.main(arguments, store_factory=object)

    captured = capsys.readouterr()
    assert result == 2
    assert captured.out == ""
    assert "output URI" in captured.err


def test_production_image_copies_and_smokes_the_operator_command() -> None:
    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    cloudbuild = (ROOT / "cloudbuild.yaml").read_text(encoding="utf-8")
    path = "scripts/publish_week1_operating_book.py"
    assert f"COPY {path} ./scripts/publish_week1_operating_book.py" in dockerfile
    assert f"python {path} --help" in cloudbuild
