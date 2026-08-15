from __future__ import annotations

import base64
from hashlib import sha256
import json

import pytest

from nfl_dfs.analysis import sis_receiver_copula as gate
from nfl_dfs.analysis import sis_receiver_copula_calibration as calibration
from nfl_dfs.analysis import sis_receiver_copula_heldout as heldout


def _reference() -> dict:
    return {
        "version": "sis-receiver-copula-reference-attestation-v1",
        "historical_panel": gate.REFERENCE_HISTORICAL_PANEL,
        "evaluation_panel": gate.REFERENCE_EVALUATION_PANEL,
        "disposition": "sis-receiver-copula-reference-passes",
        "heldout_treatment_licensed": True,
        "report_sha256": "a" * 64,
        "manifest_sha256": "b" * 64,
        "score_sha256": "c" * 64,
        "frame_sha256": "d" * 64,
        "draws_sha256": "e" * 64,
        "terminal_sha256": "f" * 64,
    }


def _calibration() -> dict:
    return {
        "version": "sis-receiver-copula-calibration-attestation-v1",
        "panel": gate.REFERENCE_HISTORICAL_PANEL,
        "disposition": "sis-receiver-copula-calibration-passes",
        "heldout_evaluation_licensed": True,
        "protocols": {
            "parent_protocol_sha256": calibration.PARENT_PROTOCOL_SHA256,
            "calibration_amendment_sha256": calibration.AMENDMENT_SHA256,
        },
        "selected": {"strength": 0.75, "required_support": True},
        "report_sha256": "1" * 64,
        "manifest_sha256": "2" * 64,
    }


def test_attestation_decoder_requires_exact_content_hash(monkeypatch):
    value = _reference()
    content = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    monkeypatch.setenv(
        "SIS_RECEIVER_COPULA_REFERENCE_ATTESTATION_B64",
        base64.b64encode(content).decode(),
    )
    monkeypatch.setenv(
        "SIS_RECEIVER_COPULA_REFERENCE_ATTESTATION_SHA256",
        sha256(content).hexdigest(),
    )

    assert heldout._attestation("REFERENCE") == value

    monkeypatch.setenv(
        "SIS_RECEIVER_COPULA_REFERENCE_ATTESTATION_SHA256", "0" * 64,
    )
    with pytest.raises(ValueError, match="hash differs"):
        heldout._attestation("REFERENCE")


def test_attestations_license_only_the_frozen_selected_strength():
    assert heldout._validate_attestations(
        _reference(), _calibration(), gate.REFERENCE_HISTORICAL_PANEL,
    ) == 0.75

    invalid = _calibration()
    invalid["selected"] = {"strength": 0.6, "required_support": True}
    with pytest.raises(ValueError, match="calibration attestation differs"):
        heldout._validate_attestations(
            _reference(), invalid, gate.REFERENCE_HISTORICAL_PANEL,
        )
