from __future__ import annotations

from hashlib import sha256
import json

import pytest

from nfl_dfs.research import receiver_matchup_contract as contract


def _identity(uri: str, raw: bytes) -> dict[str, object]:
    return {
        "uri": uri,
        "generation": "1",
        "sha256": sha256(raw).hexdigest(),
        "bytes": len(raw),
    }


def _source_identities(family: contract.MetricFamily) -> dict[str, object]:
    return {
        role: {
            "uri": f"gs://fixture/sources/{role}.json",
            "generation": "7",
            "sha256": "c" * 64,
            "bytes": 100 + ordinal,
        }
        for ordinal, role in enumerate(family.source_roles)
    }


def _row(player_id: str, family: contract.MetricFamily, **overrides):
    values: dict[str, object] = {}
    missing: dict[str, object] = {}
    for spec in family.fields:
        if spec.name in overrides:
            values[spec.name] = overrides[spec.name]
        elif spec.field_type == "boolean":
            values[spec.name] = False if spec.nullable else True
        elif spec.field_type == "integer":
            values[spec.name] = 2
        elif spec.field_type == "percentile":
            values[spec.name] = 0.5
        elif spec.field_type == "number":
            values[spec.name] = 1.25
        else:
            values[spec.name] = None
            missing[spec.name] = "source-absent"
    for name, value in values.items():
        if value is None and name not in missing:
            missing[name] = "source-absent"
    return {"player_id": player_id, "values": values, "missing": missing}


def _build(family: contract.MetricFamily, rows):
    return contract.build_annotation_object(
        family=family,
        task_id="task-0000-2023-w01",
        slate_id="2023-w01",
        lock_time_utc="2023-09-10T17:00:00Z",
        maximum_source_time_utc="2023-09-10T13:00:00Z",
        player_catalog_identity=_identity(
            "gs://fixture/catalog.json", b"catalog"
        ),
        source_identities=_source_identities(family),
        rows=rows,
        created_at_utc="2026-08-22T18:00:00Z",
    )


def test_family_registration_rejects_outcome_smuggling_and_duplicates():
    family = contract.receiver_matchup_family_v1()
    assert family.provisional is True
    definition = family.definition_payload()
    assert definition["schema_version"] == contract.FAMILY_DEFINITION_SCHEMA
    remainder = {
        key: value for key, value in definition.items()
        if key != "family_definition_sha256"
    }
    assert contract.canonical_sha256(remainder) == (
        definition["family_definition_sha256"]
    )
    with pytest.raises(
        contract.ReceiverMatchupContractError, match="forbidden target-week"
    ):
        contract.define_metric_family(
            family_id="bad-family",
            version=1,
            provisional=True,
            source_roles=("role-a",),
            fields=(
                contract.FieldSpec(
                    "actual_points", "number", True, "smuggled outcome"
                ),
            ),
            description="bad",
        )
    with pytest.raises(
        contract.ReceiverMatchupContractError, match="unique"
    ):
        contract.define_metric_family(
            family_id="dup-family",
            version=1,
            provisional=True,
            source_roles=("role-a",),
            fields=(
                contract.FieldSpec("edge", "number", True, "x"),
                contract.FieldSpec("edge", "number", True, "y"),
            ),
            description="dup",
        )
    with pytest.raises(
        contract.ReceiverMatchupContractError, match="unregistered type"
    ):
        contract.define_metric_family(
            family_id="typed-family",
            version=1,
            provisional=True,
            source_roles=("role-a",),
            fields=(
                contract.FieldSpec("edge", "float64", True, "x"),
            ),
            description="typed",
        )


def test_annotation_roundtrip_replays_and_orders_rows():
    family = contract.receiver_matchup_family_v1(provisional=False)
    rows = [
        _row("00-0031234", family, matchup_edge_score=0.81,
             easy_coverage_v1=True),
        _row("00-0029876", family, role_label="WR1",
             role_consensus_score=0.92),
    ]
    body = _build(family, rows)
    raw = contract.canonical_json_bytes(body)
    validated = contract.validate_annotation_bytes(
        raw,
        identity=_identity("gs://fixture/annotations.json", raw),
        expected_family=family,
        require_analysis_grade=True,
    )
    assert validated["row_count"] == 2
    assert [row["player_id"] for row in validated["rows"]] == [
        "00-0029876", "00-0031234",
    ]
    assert validated["analysis_grade"] is True
    assert validated["realized_outcomes_present"] is False


def test_provisional_family_cannot_license_analysis_grade():
    provisional = contract.receiver_matchup_family_v1(provisional=True)
    body = _build(provisional, [_row("00-0031234", provisional)])
    raw = contract.canonical_json_bytes(body)
    contract.validate_annotation_bytes(
        raw, expected_family=provisional, require_analysis_grade=False
    )
    with pytest.raises(
        contract.ReceiverMatchupContractError, match="provisional"
    ):
        contract.validate_annotation_bytes(
            raw, expected_family=provisional, require_analysis_grade=True
        )
    frozen = contract.receiver_matchup_family_v1(provisional=False)
    with pytest.raises(
        contract.ReceiverMatchupContractError,
        match="family definition differs",
    ):
        contract.validate_annotation_bytes(
            raw, expected_family=frozen, require_analysis_grade=False
        )


def test_missingness_and_pit_laws_fail_closed():
    family = contract.receiver_matchup_family_v1()
    naked_null = _row("00-0031234", family)
    del naked_null["missing"][next(iter(naked_null["missing"]))]
    with pytest.raises(
        contract.ReceiverMatchupContractError, match="registered missing"
    ):
        _build(family, [naked_null])
    noisy = _row("00-0031234", family)
    noisy["missing"]["matchup_edge_score"] = "source-absent"
    with pytest.raises(
        contract.ReceiverMatchupContractError, match="non-null"
    ):
        _build(family, [noisy])
    with pytest.raises(
        contract.ReceiverMatchupContractError, match="repeats player"
    ):
        _build(family, [
            _row("00-0031234", family), _row("00-0031234", family),
        ])
    with pytest.raises(
        contract.ReceiverMatchupContractError, match="precede the slate lock"
    ):
        contract.build_annotation_object(
            family=family,
            task_id="task-0000-2023-w01",
            slate_id="2023-w01",
            lock_time_utc="2023-09-10T17:00:00Z",
            maximum_source_time_utc="2023-09-10T17:00:00Z",
            player_catalog_identity=_identity(
                "gs://fixture/catalog.json", b"catalog"
            ),
            source_identities=_source_identities(family),
            rows=[_row("00-0031234", family)],
            created_at_utc="2026-08-22T18:00:00Z",
        )
    body = _build(family, [_row("00-0031234", family)])
    raw = contract.canonical_json_bytes(body)
    tampered = bytearray(raw)
    tampered[raw.index(b"0.5")] = ord("9")
    with pytest.raises(
        contract.ReceiverMatchupContractError, match="self-hash differs"
    ):
        contract.validate_annotation_bytes(
            bytes(tampered), expected_family=family,
            require_analysis_grade=False,
        )
    parsed = json.loads(raw.decode("utf-8"))
    assert set(parsed["source_identities"]) == set(family.source_roles)
