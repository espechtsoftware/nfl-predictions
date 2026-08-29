"""Pure catalog-wide successor for an already validated R6 outcome snapshot.

This module performs no reads.  Callers must exact-open and validate the base
snapshot and the later-source freeze before invoking it.  The successor keeps
the ordinary full-union outcome-snapshot surface so score-map consumers do not
need a second row format.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from hashlib import sha256
from typing import Final

from nfl_dfs.research import corpus_parametric_batch as batch
from nfl_dfs.research import corpus_r6_full_union_outcome_snapshot_v1 as ordinary
from nfl_dfs.research import corpus_r6_novel_roster_realized_grader_v1 as grader
from nfl_dfs.research import lr8_later_period_source as later


PROJECTION_SCHEMA: Final = "corpus-r6-catalog-wide-outcome-projection/v1"
SOURCE_SCHEMA: Final = "corpus-r6-catalog-wide-realized-source/v1"
QUERY_EVIDENCE_SCHEMA: Final = "corpus-r6-catalog-wide-query-evidence/v1"
BASE_SOURCE_SNAPSHOT_AT: Final = "2026-08-26T23:58:47.451523+00:00"
ZERO_LAW: Final = "salary-catalog-closed-world-missing-skill-zero/v1"
ZERO_LAW_SOURCE_SHA256: Final = (
    "62af83985d9a9c09315167b7d4b7c7f48c36292ac61d86c525130d0187bba8de"
)
ZERO_BRIDGE: Final = (
    "positive-salary-frozen-dk-catalog-is-salary-listed-for-settlement/v1"
)
ZERO_BRIDGE_SOURCE_SHA256: Final = (
    "becb3b7db31d7006e3f4b21584129af7ca963c86adde39a5ff4b653db33a498f"
)
_PROJECTION_FIELDS: Final = {
    "schema_version", "later_source_freeze_identity", "later_source_freeze_sha256",
    "base_outcome_snapshot_identity", "base_outcome_snapshot_sha256",
    "source_slate_count", "outcome_key_count", "outcome_keys",
    "outcome_keys_sha256", "complete", "uses_realized_outcomes",
    "outcome_key_projection_sha256",
}
_KEY_FIELDS: Final = {
    "source_ordinal", "season", "week", "slate_id", "player_id", "position",
    "team", "source_kind", "source_key",
}
_QUERY_EVIDENCE_FIELDS: Final = {
    "schema_version", "outcome_key_projection_identity",
    "outcome_key_projection_sha256", "queried_keys", "queried_key_count",
    "queried_keys_sha256", "registered_request", "query_contract",
    "query_job_receipt", "source_snapshot_at", "table_receipts_before_query",
    "table_receipts_after_query", "table_receipt_set_sha256",
    "historical_outcome_lease_before_query", "historical_outcome_lease_after_query",
    "historical_outcome_lease_sha256", "row_fields", "row_count", "rows",
    "rows_sha256", "one_exact_query", "query_cache_used",
    "table_metadata_stable_during_query",
    "historical_outcome_lease_unchanged_during_query", "complete",
    "query_evidence_sha256",
}
_REGISTERED_FIELDS: Final = {
    "season", "week", "source_kind", "source_key", "realized_score_micro",
}


class CatalogWideOutcomeSuccessorError(ValueError):
    pass


def _fail(message: str) -> None:
    raise CatalogWideOutcomeSuccessorError(message)


def canonical_bytes(value: object) -> bytes:
    try:
        return batch.canonical_json_bytes(value)
    except Exception as exc:  # batch supplies the strict JSON law
        raise CatalogWideOutcomeSuccessorError(str(exc)) from exc


def digest(value: object) -> str:
    return sha256(canonical_bytes(value)).hexdigest()


def _identity(value: object, label: str) -> dict[str, object]:
    try:
        return batch.normalize_object_identity(value, label=label)
    except batch.CorpusParametricBatchError as exc:
        raise CatalogWideOutcomeSuccessorError(str(exc)) from exc


def _json_identity(value: object, identity: object, label: str) -> dict[str, object]:
    try:
        return batch.validate_json_identity(value, identity, label=label)
    except batch.CorpusParametricBatchError as exc:
        raise CatalogWideOutcomeSuccessorError(str(exc)) from exc


def _catalog_projection(later_source: Mapping[str, object]) -> list[dict[str, object]]:
    slates = later_source.get("slates")
    if not isinstance(slates, Sequence) or isinstance(slates, (str, bytes)):
        _fail("later-source slates must be an array")
    if len(slates) != 54:
        _fail("later-source freeze must contain exactly 54 slates")
    rows: list[dict[str, object]] = []
    seen_sources: set[tuple[int, int, str, str]] = set()
    for ordinal, raw_slate in enumerate(slates):
        if not isinstance(raw_slate, Mapping):
            _fail("later-source slate must be an object")
        season, week, slate_id = (
            raw_slate.get("season"), raw_slate.get("week"), raw_slate.get("slate_id")
        )
        expected_season, expected_week = 2023 + ordinal // 18, ordinal % 18 + 1
        catalog = raw_slate.get("catalog")
        if (type(season) is not int or type(week) is not int
                or not isinstance(slate_id, str) or not slate_id
                or not isinstance(catalog, Sequence)
                or isinstance(catalog, (str, bytes))):
            _fail("later-source slate identity/catalog differs")
        if (season, week, slate_id) != (
            expected_season, expected_week, f"{expected_season}-w{expected_week:02d}"
        ):
            _fail("later-source slate ID/order differs")
        observed_ids: list[str] = []
        for raw_player in catalog:
            if not isinstance(raw_player, Mapping):
                _fail("catalog player must be an object")
            player_id, pos, team, salary = (
                raw_player.get("id"), raw_player.get("pos"),
                raw_player.get("team"), raw_player.get("salary"),
            )
            if (not isinstance(player_id, str) or not player_id
                    or not isinstance(pos, str) or not pos
                    or not isinstance(team, str) or not team
                    or type(salary) is not int or salary <= 0):
                _fail("catalog player identity/positive salary differs")
            if pos.upper() not in {"QB", "RB", "WR", "TE", "DST"}:
                _fail("catalog player position differs")
            observed_ids.append(player_id)
            kind = "dst" if pos.upper() == "DST" else "skill"
            source_key = team.upper() if kind == "dst" else player_id
            source = (season, week, kind, source_key)
            if source in seen_sources:
                _fail("catalog contains a duplicate/source collision")
            seen_sources.add(source)
            rows.append({
                "source_ordinal": ordinal, "season": season, "week": week,
                "slate_id": slate_id, "player_id": player_id,
                "position": pos.upper(), "team": team.upper(),
                "source_kind": kind, "source_key": source_key,
            })
        if observed_ids != sorted(observed_ids) or len(observed_ids) != len(set(observed_ids)):
            _fail("later-source catalog player IDs are not unique canonical order")
    return rows


def build_catalog_wide_projection_v1(
    *, later_source: Mapping[str, object], later_source_identity: Mapping[str, object],
    later_source_sha256: str, base_snapshot: Mapping[str, object],
    base_snapshot_identity: Mapping[str, object],
    base_snapshot_sha256: str,
) -> dict[str, object]:
    later_identity = _json_identity(later_source, later_source_identity, "later-source")
    try:
        retained_later = later.validate_source_freeze(
            later_source, expected_freeze_sha256=later_source_sha256
        )
    except later.LR8LaterSourceError as exc:
        raise CatalogWideOutcomeSuccessorError(str(exc)) from exc
    base_identity = _json_identity(base_snapshot, base_snapshot_identity, "base snapshot")
    if base_snapshot.get("outcome_snapshot_sha256") != base_snapshot_sha256:
        _fail("base snapshot internal hash differs")
    try:
        grader.open_outcome_snapshot_surface_v1(
            outcome_snapshot_identity=base_identity,
            read_outcome_exact=lambda _: canonical_bytes(base_snapshot),
        )
    except Exception as exc:
        raise CatalogWideOutcomeSuccessorError(str(exc)) from exc
    if (base_snapshot.get("later_source_freeze_identity") != later_identity
            or base_snapshot.get("later_source_freeze_sha256") != later_source_sha256):
        _fail("base snapshot/later-source binding differs")
    rows = _catalog_projection(retained_later)
    body: dict[str, object] = {
        "schema_version": PROJECTION_SCHEMA,
        "later_source_freeze_identity": later_identity,
        "later_source_freeze_sha256": later_source_sha256,
        "base_outcome_snapshot_identity": base_identity,
        "base_outcome_snapshot_sha256": base_snapshot_sha256,
        "source_slate_count": 54, "outcome_key_count": len(rows),
        "outcome_keys": rows, "outcome_keys_sha256": digest(rows),
        "complete": True, "uses_realized_outcomes": False,
    }
    body["outcome_key_projection_sha256"] = digest(body)
    return body


def _zero_authorized(evidence: object) -> bool:
    return isinstance(evidence, Mapping) and dict(evidence) == {
        "skill_zero_completion_law": ZERO_LAW,
        "skill_zero_law_source_sha256": ZERO_LAW_SOURCE_SHA256,
        "salary_catalog_settlement_bridge": ZERO_BRIDGE,
        "salary_catalog_bridge_source_sha256": ZERO_BRIDGE_SOURCE_SHA256,
    }


def validate_catalog_wide_projection_v1(
    value: Mapping[str, object], *, identity: Mapping[str, object],
    later_source: Mapping[str, object], later_source_identity: Mapping[str, object],
    later_source_sha256: str,
) -> tuple[dict[str, object], dict[str, object]]:
    retained = dict(value)
    retained_identity = _json_identity(retained, identity, "catalog-wide projection")
    keys = retained.get("outcome_keys")
    if (set(retained) != _PROJECTION_FIELDS
            or retained.get("schema_version") != PROJECTION_SCHEMA
            or not isinstance(keys, Sequence)
            or retained.get("source_slate_count") != 54
            or retained.get("outcome_key_count") != len(keys)
            or retained.get("outcome_keys_sha256") != digest(keys)
            or retained.get("outcome_key_projection_sha256")
            != digest({k: v for k, v in retained.items()
                       if k != "outcome_key_projection_sha256"})
            or retained.get("complete") is not True
            or retained.get("uses_realized_outcomes") is not False):
        _fail("catalog-wide projection differs")
    later_identity = _json_identity(later_source, later_source_identity, "later-source")
    try:
        retained_later = later.validate_source_freeze(
            later_source, expected_freeze_sha256=later_source_sha256
        )
    except later.LR8LaterSourceError as exc:
        raise CatalogWideOutcomeSuccessorError(str(exc)) from exc
    if (retained.get("later_source_freeze_identity") != later_identity
            or retained.get("later_source_freeze_sha256") != later_source_sha256):
        _fail("projection/later-source predecessor differs")
    if any(not isinstance(row, Mapping) or set(row) != _KEY_FIELDS for row in keys):
        _fail("catalog-wide projection key row shape differs")
    normalized_keys = _catalog_projection(retained_later)
    if keys != normalized_keys:
        _fail("catalog-wide projection key coverage/order differs")
    _identity(retained.get("later_source_freeze_identity"), "projection later source")
    _identity(retained.get("base_outcome_snapshot_identity"), "projection base snapshot")
    return retained, retained_identity


def validate_catalog_wide_realized_source_v1(
    value: Mapping[str, object], *, identity: Mapping[str, object],
    projection: Mapping[str, object], projection_identity: Mapping[str, object],
    base_snapshot: Mapping[str, object], query_evidence: Mapping[str, object],
    query_evidence_identity: Mapping[str, object],
) -> tuple[dict[str, object], dict[str, object]]:
    retained = dict(value)
    retained_identity = _json_identity(retained, identity, "catalog-wide realized source")
    rows, synthesized, delta = (
        retained.get("rows"), retained.get("synthesized_skill_keys"),
        retained.get("delta_registered_rows"),
    )
    expected_fields = {
        "schema_version", "outcome_key_projection_identity",
        "outcome_key_projection_sha256", "base_outcome_snapshot_identity",
        "base_outcome_snapshot_sha256", "later_source_freeze_identity",
        "later_source_freeze_sha256", "query_evidence_identity",
        "query_evidence_sha256", "query_provenance", "delta_registered_rows",
        "delta_registered_rows_sha256", "skill_zero_completion_law",
        "skill_zero_law_source_sha256", "salary_catalog_settlement_bridge",
        "salary_catalog_bridge_source_sha256",
        "synthesized_skill_keys", "synthesized_skill_key_count",
        "synthesized_skill_keys_sha256", "rows", "rows_sha256", "row_count",
        "realized_source_sha256",
    }
    if (set(retained) != expected_fields
            or retained.get("schema_version") != SOURCE_SCHEMA
            or retained.get("outcome_key_projection_identity") != dict(projection_identity)
            or retained.get("outcome_key_projection_sha256")
            != projection.get("outcome_key_projection_sha256")
            or not isinstance(rows, Sequence) or retained.get("row_count") != len(rows)
            or retained.get("rows_sha256") != digest(rows)
            or not isinstance(delta, Sequence)
            or retained.get("delta_registered_rows_sha256") != digest(delta)
            or not isinstance(synthesized, Sequence)
            or retained.get("synthesized_skill_key_count") != len(synthesized)
            or retained.get("synthesized_skill_keys_sha256") != digest(synthesized)
            or retained.get("realized_source_sha256")
            != digest({k: v for k, v in retained.items() if k != "realized_source_sha256"})):
        _fail("catalog-wide realized source differs")
    _, evidence_identity, evidence_rows = validate_catalog_wide_query_evidence_v1(
        query_evidence, identity=query_evidence_identity,
        projection=projection, projection_identity=projection_identity,
        base_snapshot=base_snapshot,
    )
    if (retained.get("query_evidence_identity") != evidence_identity
            or retained.get("query_evidence_sha256") != evidence_identity["sha256"]
            or list(delta) != list(evidence_rows)
            ):
        _fail("realized source/query evidence replay differs")
    expected_provenance = {
        "source_snapshot_at": query_evidence["source_snapshot_at"],
        "query_contract": query_evidence["query_contract"],
        "query_job_receipt": query_evidence["query_job_receipt"],
    }
    if retained.get("query_provenance") != expected_provenance:
        _fail("realized source query provenance differs")
    expected_row_keys = [(r["source_ordinal"], r["player_id"])
                         for r in projection["outcome_keys"]]
    snapshot_row_fields = {"source_ordinal", "season", "week", "slate_id",
                           "player_id", "realized_score_micro"}
    if any(not isinstance(r, Mapping) or set(r) != snapshot_row_fields
           or type(r["realized_score_micro"]) is not int for r in rows):
        _fail("catalog-wide realized source row shape differs")
    registered_fields = {"season", "week", "source_kind", "source_key",
                         "realized_score_micro"}
    if any(not isinstance(r, Mapping) or set(r) != registered_fields
           or type(r["realized_score_micro"]) is not int for r in delta):
        _fail("catalog-wide delta row shape differs")
    delta_tuples = [(r["season"], r["week"], r["source_kind"], r["source_key"])
                    for r in delta]
    if delta_tuples != sorted(set(delta_tuples)):
        _fail("catalog-wide delta source keys are not unique canonical order")
    observed_row_keys = [(r.get("source_ordinal"), r.get("player_id")) for r in rows]
    if observed_row_keys != expected_row_keys or len(observed_row_keys) != len(set(observed_row_keys)):
        _fail("catalog-wide realized source does not cover the full catalog")
    base_keys = {(r["source_ordinal"], r["player_id"]) for r in base_snapshot["rows"]}
    query_sources = {(r["season"], r["week"], r["source_kind"], r["source_key"])
                     for r in evidence_rows}
    expected_synthesized = [{"season": r["season"], "week": r["week"],
                             "source_kind": r["source_kind"], "source_key": r["source_key"]}
                            for r in projection["outcome_keys"]
                            if (r["source_ordinal"], r["player_id"]) not in base_keys
                            and (r["season"], r["week"], r["source_kind"], r["source_key"])
                            not in query_sources]
    if list(synthesized) != expected_synthesized:
        _fail("synthesized zero census differs from queried absent keys")
    zero_fields = (
        retained.get("skill_zero_completion_law"),
        retained.get("skill_zero_law_source_sha256"),
        retained.get("salary_catalog_settlement_bridge"),
        retained.get("salary_catalog_bridge_source_sha256"),
    )
    if synthesized and zero_fields != (
        ZERO_LAW, ZERO_LAW_SOURCE_SHA256, ZERO_BRIDGE, ZERO_BRIDGE_SOURCE_SHA256
    ):
        _fail("synthesized zero authority differs")
    if not synthesized and zero_fields not in {
        (None, None, None, None),
        (ZERO_LAW, ZERO_LAW_SOURCE_SHA256, ZERO_BRIDGE, ZERO_BRIDGE_SOURCE_SHA256),
    }:
        _fail("zero authority fields differ")
    base_scores = {(r["source_ordinal"], r["player_id"]): r["realized_score_micro"]
                   for r in base_snapshot["rows"]}
    query_scores = {(r["season"], r["week"], r["source_kind"], r["source_key"]):
                    r["realized_score_micro"] for r in evidence_rows}
    synthesized_sources = {(r["season"], r["week"], r["source_kind"], r["source_key"])
                           for r in synthesized}
    expected_scores = []
    for key in projection["outcome_keys"]:
        player_key = (key["source_ordinal"], key["player_id"])
        source_key = (key["season"], key["week"], key["source_kind"], key["source_key"])
        if player_key in base_scores:
            score = base_scores[player_key]
        elif source_key in query_scores:
            score = query_scores[source_key]
        elif source_key in synthesized_sources and key["source_kind"] == "skill":
            score = 0
        else:
            _fail("realized source score lacks an authorized predecessor")
        expected_scores.append(score)
    if [r["realized_score_micro"] for r in rows] != expected_scores:
        _fail("realized source score replay differs")
    return retained, retained_identity


def validate_catalog_wide_query_evidence_v1(
    value: Mapping[str, object], *, identity: Mapping[str, object],
    projection: Mapping[str, object], projection_identity: Mapping[str, object],
    base_snapshot: Mapping[str, object],
) -> tuple[dict[str, object], dict[str, object], list[dict[str, object]]]:
    evidence = dict(value)
    retained_identity = _json_identity(evidence, identity, "query evidence")
    rows, queried = evidence.get("rows"), evidence.get("queried_keys")
    before, after = evidence.get("table_receipts_before_query"), evidence.get("table_receipts_after_query")
    lease_before, lease_after = (evidence.get("historical_outcome_lease_before_query"),
                                 evidence.get("historical_outcome_lease_after_query"))
    contract, receipt, request = (evidence.get("query_contract"),
                                  evidence.get("query_job_receipt"), evidence.get("registered_request"))
    if (set(evidence) != _QUERY_EVIDENCE_FIELDS
            or evidence.get("schema_version") != QUERY_EVIDENCE_SCHEMA
            or evidence.get("query_evidence_sha256")
            != digest({k: v for k, v in evidence.items() if k != "query_evidence_sha256"})
            or evidence.get("outcome_key_projection_identity") != dict(projection_identity)
            or evidence.get("outcome_key_projection_sha256")
            != projection["outcome_key_projection_sha256"]
            or not isinstance(queried, list) or evidence.get("queried_key_count") != len(queried)
            or evidence.get("queried_keys_sha256") != digest(queried)
            or not isinstance(rows, list) or evidence.get("row_count") != len(rows)
            or evidence.get("rows_sha256") != digest(rows)
            or evidence.get("row_fields") != sorted(_REGISTERED_FIELDS)
            or any(not isinstance(r, Mapping) or set(r) != _REGISTERED_FIELDS
                   or type(r["realized_score_micro"]) is not int for r in rows)
            or not isinstance(request, Mapping)
            or set(request) != {"outcome_key_projection_identity",
                                "outcome_key_projection_sha256"}
            or request.get("outcome_key_projection_identity") != dict(projection_identity)
            or request.get("outcome_key_projection_sha256")
            != projection["outcome_key_projection_sha256"]
            or not isinstance(contract, Mapping)
            or set(contract) != {"query_count", "use_query_cache", "source_snapshot_at"}
            or contract.get("query_count") != 1
            or contract.get("use_query_cache") is not False
            or evidence.get("source_snapshot_at") != contract.get("source_snapshot_at")
            or evidence.get("source_snapshot_at") != BASE_SOURCE_SNAPSHOT_AT
            or not isinstance(receipt, Mapping) or set(receipt) != {"cache_hit", "complete"}
            or receipt.get("cache_hit") is not False
            or not isinstance(before, list) or not before
            or not isinstance(lease_before, Mapping) or not lease_before
            or receipt.get("complete") is not True
            or before != after or evidence.get("table_receipt_set_sha256") != digest(before)
            or lease_before != lease_after
            or evidence.get("historical_outcome_lease_sha256") != digest(lease_before)
            or evidence.get("one_exact_query") is not True
            or evidence.get("query_cache_used") is not False
            or evidence.get("table_metadata_stable_during_query") is not True
            or evidence.get("historical_outcome_lease_unchanged_during_query") is not True
            or evidence.get("complete") is not True):
        _fail("catalog-wide query evidence replay differs")
    base_keys = {(r["source_ordinal"], r["player_id"]) for r in base_snapshot["rows"]}
    expected_queried = [{k: r[k] for k in ("season", "week", "source_kind", "source_key")}
                        for r in projection["outcome_keys"]
                        if (r["source_ordinal"], r["player_id"]) not in base_keys]
    row_keys = [{k: r[k] for k in ("season", "week", "source_kind", "source_key")}
                for r in rows]
    key_names = ("season", "week", "source_kind", "source_key")
    queried_tuples = {tuple(r[k] for k in key_names) for r in queried}
    returned_tuples = [tuple(r[k] for k in key_names) for r in row_keys]
    if (queried != expected_queried or len(queried_tuples) != len(queried)
            or returned_tuples != sorted(set(returned_tuples))
            or any(key not in queried_tuples for key in returned_tuples)):
        _fail("query evidence queried-key census differs from returned rows")
    return evidence, retained_identity, [dict(row) for row in rows]


def _validate_base_again(
    *, base_snapshot: Mapping[str, object], base_snapshot_identity: object,
    base_snapshot_sha256: str, projection: Mapping[str, object],
) -> dict[str, object]:
    identity = _json_identity(base_snapshot, base_snapshot_identity, "base snapshot")
    if (base_snapshot.get("outcome_snapshot_sha256") != base_snapshot_sha256
            or identity != projection["base_outcome_snapshot_identity"]
            or base_snapshot_sha256 != projection["base_outcome_snapshot_sha256"]
            or base_snapshot.get("later_source_freeze_identity")
            != projection["later_source_freeze_identity"]
            or base_snapshot.get("later_source_freeze_sha256")
            != projection["later_source_freeze_sha256"]):
        _fail("base snapshot replay/binding differs")
    try:
        grader.open_outcome_snapshot_surface_v1(
            outcome_snapshot_identity=identity,
            read_outcome_exact=lambda _: canonical_bytes(base_snapshot),
        )
    except Exception as exc:
        raise CatalogWideOutcomeSuccessorError(str(exc)) from exc
    return identity


def build_catalog_wide_realized_source_v1(
    *, projection: Mapping[str, object], projection_identity: Mapping[str, object],
    later_source: Mapping[str, object], later_source_identity: Mapping[str, object],
    later_source_sha256: str,
    base_snapshot: Mapping[str, object], base_snapshot_identity: Mapping[str, object],
    base_snapshot_sha256: str, delta_registered_rows: Sequence[Mapping[str, object]],
    query_evidence: Mapping[str, object], query_evidence_identity: Mapping[str, object],
    query_provenance: Mapping[str, object],
    zero_evidence: object = None,
) -> dict[str, object]:
    """Build the publishable source; publication must precede snapshot creation."""
    projection, projection_identity = validate_catalog_wide_projection_v1(
        projection, identity=projection_identity, later_source=later_source,
        later_source_identity=later_source_identity,
        later_source_sha256=later_source_sha256,
    )
    _validate_base_again(
        base_snapshot=base_snapshot, base_snapshot_identity=base_snapshot_identity,
        base_snapshot_sha256=base_snapshot_sha256, projection=projection,
    )
    _, query_identity, query_rows = validate_catalog_wide_query_evidence_v1(
        query_evidence, identity=query_evidence_identity,
        projection=projection, projection_identity=projection_identity,
        base_snapshot=base_snapshot,
    )
    if list(delta_registered_rows) != list(query_rows):
        _fail("delta rows differ from persisted normalized query results")
    expected_query_provenance = {
        "source_snapshot_at": query_evidence["source_snapshot_at"],
        "query_contract": query_evidence["query_contract"],
        "query_job_receipt": query_evidence["query_job_receipt"],
    }
    if dict(query_provenance) != expected_query_provenance:
        _fail("query provenance differs from persisted evidence")
    keys = projection.get("outcome_keys")
    if (projection.get("schema_version") != PROJECTION_SCHEMA
            or not isinstance(keys, Sequence)
            or projection.get("outcome_keys_sha256") != digest(keys)
            or projection.get("outcome_key_projection_sha256")
            != digest({k: v for k, v in projection.items()
                       if k != "outcome_key_projection_sha256"})):
        _fail("catalog-wide projection differs")
    base_rows = base_snapshot.get("rows")
    panel_identity = base_snapshot.get("panel_freeze_identity")
    panel_sha256 = base_snapshot.get("panel_freeze_sha256")
    if (not isinstance(base_rows, Sequence)
            or not isinstance(panel_identity, Mapping)
            or not isinstance(panel_sha256, str)):
        _fail("base snapshot rows must be an array")
    base: dict[tuple[int, str], int] = {}
    for row in base_rows:
        if not isinstance(row, Mapping):
            _fail("base snapshot row must be an object")
        key = (row.get("source_ordinal"), row.get("player_id"))
        score = row.get("realized_score_micro")
        if (type(key[0]) is not int or not isinstance(key[1], str)
                or type(score) is not int or key in base):
            _fail("base snapshot row differs or repeats")
        base[key] = score
    projected_sources = {
        (r["season"], r["week"], r["source_kind"], r["source_key"]): r
        for r in keys
    }
    delta: dict[tuple[int, int, str, str], int] = {}
    for row in delta_registered_rows:
        if not isinstance(row, Mapping) or set(row) != {
            "season", "week", "source_kind", "source_key", "realized_score_micro"
        }:
            _fail("delta registered row fields differ")
        source = (row["season"], row["week"], row["source_kind"], row["source_key"])
        if source not in projected_sources or source in delta:
            _fail("delta contains a duplicate/non-projection source")
        projected = projected_sources[source]
        if (projected["source_ordinal"], projected["player_id"]) in base:
            _fail("delta collides with a base snapshot player")
        score = row["realized_score_micro"]
        if type(score) is not int:
            _fail("delta score must be integer micro-DK")
        delta[source] = score
    rows: list[dict[str, object]] = []
    synthesized: list[dict[str, object]] = []
    observed_skill_slates: set[tuple[int, int]] = set()
    for raw in keys:
        player_key = (raw["source_ordinal"], raw["player_id"])
        source = (raw["season"], raw["week"], raw["source_kind"], raw["source_key"])
        score = base.get(player_key, delta.get(source))
        if score is None:
            if raw["source_kind"] == "dst":
                _fail("missing DST delta is forbidden")
            if not _zero_authorized(zero_evidence):
                _fail("missing skill delta lacks exact salary-catalog zero evidence")
            score = 0
            synthesized.append({
                "season": raw["season"], "week": raw["week"],
                "source_kind": raw["source_kind"], "source_key": raw["source_key"],
            })
        elif raw["source_kind"] == "skill":
            observed_skill_slates.add((raw["season"], raw["week"]))
        rows.append({k: raw[k] for k in (
            "source_ordinal", "season", "week", "slate_id", "player_id"
        )} | {"realized_score_micro": score})
    all_skill_slates = {(r["season"], r["week"]) for r in keys if r["source_kind"] == "skill"}
    if all_skill_slates - observed_skill_slates:
        _fail("zero completion would remove every observed skill row for a slate")
    source_body = {
        "schema_version": SOURCE_SCHEMA,
        "outcome_key_projection_identity": dict(projection_identity),
        "outcome_key_projection_sha256": projection["outcome_key_projection_sha256"],
        "base_outcome_snapshot_identity": projection["base_outcome_snapshot_identity"],
        "base_outcome_snapshot_sha256": projection["base_outcome_snapshot_sha256"],
        "later_source_freeze_identity": projection["later_source_freeze_identity"],
        "later_source_freeze_sha256": projection["later_source_freeze_sha256"],
        "query_evidence_identity": query_identity,
        "query_evidence_sha256": query_identity["sha256"],
        "query_provenance": dict(query_provenance),
        "delta_registered_rows": [dict(row) for row in delta_registered_rows],
        "delta_registered_rows_sha256": digest(delta_registered_rows),
        "skill_zero_completion_law": ZERO_LAW if _zero_authorized(zero_evidence) else None,
        "skill_zero_law_source_sha256": ZERO_LAW_SOURCE_SHA256 if _zero_authorized(zero_evidence) else None,
        "salary_catalog_settlement_bridge": ZERO_BRIDGE if _zero_authorized(zero_evidence) else None,
        "salary_catalog_bridge_source_sha256": ZERO_BRIDGE_SOURCE_SHA256 if _zero_authorized(zero_evidence) else None,
        "synthesized_skill_keys": synthesized,
        "synthesized_skill_key_count": len(synthesized),
        "synthesized_skill_keys_sha256": digest(synthesized),
        "rows": rows,
        "rows_sha256": digest(rows), "row_count": len(rows),
    }
    source_body["realized_source_sha256"] = digest(source_body)
    return source_body


def build_catalog_wide_snapshot_v1(
    *, projection: Mapping[str, object], projection_identity: Mapping[str, object],
    later_source: Mapping[str, object], later_source_identity: Mapping[str, object],
    later_source_sha256: str,
    base_snapshot: Mapping[str, object], base_snapshot_identity: Mapping[str, object],
    base_snapshot_sha256: str, realized_source: Mapping[str, object],
    realized_source_identity: Mapping[str, object], query_evidence: Mapping[str, object],
    query_evidence_identity: Mapping[str, object],
) -> dict[str, object]:
    """Build an ordinary snapshot only from an actually published source."""
    projection, projection_identity = validate_catalog_wide_projection_v1(
        projection, identity=projection_identity, later_source=later_source,
        later_source_identity=later_source_identity,
        later_source_sha256=later_source_sha256,
    )
    _validate_base_again(
        base_snapshot=base_snapshot, base_snapshot_identity=base_snapshot_identity,
        base_snapshot_sha256=base_snapshot_sha256, projection=projection,
    )
    realized_source, source_identity = validate_catalog_wide_realized_source_v1(
        realized_source, identity=realized_source_identity,
        projection=projection, projection_identity=projection_identity,
        base_snapshot=base_snapshot, query_evidence=query_evidence,
        query_evidence_identity=query_evidence_identity,
    )
    rows = realized_source.get("rows")
    if not isinstance(rows, Sequence) or realized_source.get("rows_sha256") != digest(rows):
        _fail("catalog-wide realized source rows differ")
    panel_identity = base_snapshot.get("panel_freeze_identity")
    panel_sha256 = base_snapshot.get("panel_freeze_sha256")
    row_keys = [{k: row[k] for k in (
        "source_ordinal", "season", "week", "slate_id", "player_id"
    )} for row in rows]
    snapshot: dict[str, object] = {
        "schema_version": ordinary.OUTCOME_SNAPSHOT_SCHEMA,
        "outcome_key_projection_identity": dict(projection_identity),
        "outcome_key_projection_sha256": projection["outcome_key_projection_sha256"],
        "panel_freeze_identity": dict(panel_identity),
        "panel_freeze_sha256": panel_sha256,
        "later_source_freeze_identity": projection["later_source_freeze_identity"],
        "later_source_freeze_sha256": projection["later_source_freeze_sha256"],
        "realized_source_identity": source_identity,
        "realized_source_sha256": realized_source["realized_source_sha256"],
        "score_unit": "micro_dk", "micro_dk_per_point": 1_000_000,
        "row_count": len(rows), "row_keys_sha256": digest(row_keys),
        "rows_sha256": digest(rows), "rows": rows,
        "exact_union_coverage": True, "lineup_scoring_performed": False,
        "full_field_standings_included": False, "payout_ladder_included": False,
        "graph_mutation_licensed": False, "production_change_licensed": False,
        "decision_authority": False,
    }
    snapshot["outcome_snapshot_sha256"] = digest(snapshot)
    return snapshot


def validate_catalog_wide_snapshot_v1(
    value: Mapping[str, object], *, identity: Mapping[str, object],
) -> tuple[dict[str, object], dict[tuple[int, str], int]]:
    retained_identity = _json_identity(value, identity, "catalog-wide outcome snapshot")
    try:
        _, opened_identity, scores, _ = grader.open_outcome_snapshot_surface_v1(
            outcome_snapshot_identity=retained_identity,
            read_outcome_exact=lambda _: canonical_bytes(value),
        )
    except Exception as exc:
        raise CatalogWideOutcomeSuccessorError(str(exc)) from exc
    if opened_identity != retained_identity:
        _fail("novel grader retained a different snapshot identity")
    return retained_identity, scores
