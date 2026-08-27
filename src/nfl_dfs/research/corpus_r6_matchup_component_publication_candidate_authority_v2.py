"""Candidate-authority-rooted R6 matchup component publication.

The v1 publication boundary accepts an accepted-candidate release body and
identity from its caller.  This successor removes that authority seam.  Its
public publisher accepts only the terminal fixed-G0 candidate-authority root
identity, exact-reopens all published candidate objects, and replays all 54
accepted Foundry predecessors before passing the derived release body and
identity into the unchanged v1 root-last component publisher.

The bounded v2 receipt records the candidate root, candidate release, and
catalog-replay bindings used by the component publication.  It grants no
source, scoring, fill, retrieval, graph, promotion, decision, publication, or
production authority.  Structural validation alone is explicitly
non-authoritative; downstream consumers can invoke the exact validator to
reopen the candidate root again.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from hashlib import sha256
import json
from pathlib import Path
import re
from typing import Final

from nfl_dfs.research import (
    corpus_r6_fixed_g0_candidate_authority_release_v1 as candidate_authority,
)
from nfl_dfs.research import (
    corpus_r6_matchup_component_publication_v1 as publication_v1,
)
from nfl_dfs.research import corpus_r6_matchup_component_producer_v1 as producer
from nfl_dfs.research import corpus_r6_matchup_source_v2 as source


PUBLICATION_RECEIPT_SCHEMA: Final = (
    "corpus-r6-matchup-component-publication-candidate-authority/v2"
)
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_ROOT_URI = re.compile(
    rf"^gs://{re.escape(candidate_authority.OUTPUT_BUCKET)}/"
    rf"{re.escape(candidate_authority.OUTPUT_NAMESPACE)}/"
    r"[a-z0-9][a-z0-9-]{7,80}/"
    rf"{re.escape(candidate_authority.ROOT_FILENAME)}$"
)
_RECEIPT_FIELDS: Final = frozenset({
    "schema_version",
    "candidate_authority_root_identity",
    "candidate_authority_root_sha256",
    "accepted_candidate_release_identity",
    "accepted_candidate_release_sha256",
    "catalog_replay_receipt_identity",
    "catalog_replay_receipt_sha256",
    "catalog_release_identity",
    "catalog_release_sha256",
    "candidate_authority_exact_reopened",
    "complete_candidate_population_binding_verified",
    "exact_occurrence_provenance_binding_verified",
    "caller_candidate_release_body_allowed",
    "caller_candidate_release_identity_allowed",
    "candidate_authority_exact_reopen_required",
    "candidate_authority_structure_only_authority",
    "legacy_v1_publication_path_authoritative",
    "authoritative_consumer_requires_full_v2_result",
    "component_publication_receipt",
    "component_publication_receipt_sha256",
    "producer_release_identity",
    "producer_release_sha256",
    "outcome_columns_read",
    "uses_realized_outcomes",
    *source.FALSE_AUTHORITY_FIELDS,
    "candidate_authority_component_publication_receipt_sha256",
})

ReadExact = candidate_authority.ReadExact
GitHead = candidate_authority.GitHead
GitBlob = candidate_authority.GitBlob
GitStatus = candidate_authority.GitStatus
PublishCreateOnce = publication_v1.PublishCreateOnce


class CorpusR6MatchupComponentPublicationCandidateAuthorityV2Error(ValueError):
    """The candidate-rooted component publication failed closed."""


def _fail(message: str) -> None:
    raise CorpusR6MatchupComponentPublicationCandidateAuthorityV2Error(message)


def canonical_json_bytes(value: object) -> bytes:
    return source.canonical_json_bytes(value)


def canonical_sha256(value: object) -> str:
    return source.canonical_sha256(value)


def _mapping(value: object, *, label: str) -> dict[str, object]:
    if not isinstance(value, Mapping) or any(type(key) is not str for key in value):
        _fail(f"{label} must be a string-keyed object")
    return dict(value)


def _identity(value: object, *, label: str) -> dict[str, object]:
    try:
        return source.normalize_object_identity_v2(value, label=label)
    except source.CorpusR6MatchupSourceV2Error as exc:
        raise CorpusR6MatchupComponentPublicationCandidateAuthorityV2Error(
            str(exc)
        ) from exc


def _digest(value: object, *, label: str) -> str:
    if type(value) is not str or _SHA256.fullmatch(value) is None:
        _fail(f"{label} must be lowercase 64-hex")
    return value


def _policy() -> dict[str, object]:
    return {
        "outcome_columns_read": [],
        "uses_realized_outcomes": False,
        **{field: False for field in source.FALSE_AUTHORITY_FIELDS},
    }


def _candidate_binding(
    reopened: candidate_authority.ReopenedFixedG0CandidateAuthorityV1,
    *,
    expected_root_identity: object,
    expected_catalog_replay_receipt_identity: object | None = None,
    expected_catalog_replay_receipt_sha256: object | None = None,
    expected_catalog_release_identity: object | None = None,
    expected_catalog_release_sha256: object | None = None,
    expected_candidate_release_identity: object | None = None,
    expected_candidate_release_sha256: object | None = None,
) -> dict[str, object]:
    root = _mapping(reopened.root, label="reopened candidate-authority root")
    root_identity = _identity(
        reopened.root_identity, label="reopened candidate-authority root"
    )
    retained_root_identity = _identity(
        expected_root_identity, label="candidate-authority root identity"
    )
    candidate_release = _mapping(
        reopened.candidate_release, label="reopened accepted candidate release"
    )
    candidate_release_identity = _identity(
        reopened.candidate_release_identity,
        label="reopened accepted candidate release",
    )
    root_sha = _digest(
        root.get("candidate_authority_release_sha256"),
        label="candidate-authority root SHA",
    )
    candidate_release_sha = _digest(
        candidate_release.get("accepted_candidate_release_sha256"),
        label="accepted candidate release SHA",
    )
    catalog_identity = _identity(
        root.get("catalog_replay_receipt_identity"),
        label="candidate root catalog replay receipt",
    )
    catalog_sha = _digest(
        root.get("catalog_replay_receipt_sha256"),
        label="candidate root catalog replay receipt SHA",
    )
    authority_bundle = _mapping(
        reopened.authority_bundle, label="reopened candidate authority bundle"
    )
    panel = _mapping(
        authority_bundle.get("panel_derivation_receipt"),
        label="reopened candidate panel derivation receipt",
    )
    catalog_release_identity = _identity(
        panel.get("catalog_release_identity"),
        label="candidate panel catalog release",
    )
    catalog_release_sha = _digest(
        panel.get("catalog_release_sha256"),
        label="candidate panel catalog release SHA",
    )
    if (
        root_identity != retained_root_identity
        or _ROOT_URI.fullmatch(str(root_identity["uri"])) is None
        or root.get("target_uri") != root_identity["uri"]
        or root.get("candidate_release_identity") != candidate_release_identity
        or root.get("candidate_release_sha256") != candidate_release_sha
        or root.get("candidate_population_authority") is not True
        or root.get("exact_occurrence_provenance_authority") is not True
        or root.get("authoritative_reopen_required") is not True
        or root.get("structure_only_validation_authority") is not False
        or root.get("complete") is not True
        or panel.get("catalog_replay_receipt_identity") != catalog_identity
        or panel.get("catalog_replay_receipt_sha256") != catalog_sha
        or panel.get("candidate_release_sha256") != candidate_release_sha
    ):
        _fail("reopened candidate-authority root binding differs")
    comparisons = (
        (
            expected_catalog_replay_receipt_identity,
            catalog_identity,
            "catalog replay receipt identity",
            _identity,
        ),
        (
            expected_candidate_release_identity,
            candidate_release_identity,
            "accepted candidate release identity",
            _identity,
        ),
        (
            expected_catalog_release_identity,
            catalog_release_identity,
            "catalog release identity",
            _identity,
        ),
    )
    for expected, actual, label, normalizer in comparisons:
        if expected is not None and normalizer(expected, label=label) != actual:
            _fail(f"candidate authority {label} differs")
    digest_comparisons = (
        (
            expected_catalog_replay_receipt_sha256,
            catalog_sha,
            "catalog replay receipt SHA",
        ),
        (
            expected_candidate_release_sha256,
            candidate_release_sha,
            "accepted candidate release SHA",
        ),
        (
            expected_catalog_release_sha256,
            catalog_release_sha,
            "catalog release SHA",
        ),
    )
    for expected, actual, label in digest_comparisons:
        if expected is not None and _digest(expected, label=label) != actual:
            _fail(f"candidate authority {label} differs")
    return {
        "candidate_authority_root_identity": root_identity,
        "candidate_authority_root_sha256": root_sha,
        "accepted_candidate_release_identity": candidate_release_identity,
        "accepted_candidate_release_sha256": candidate_release_sha,
        "catalog_replay_receipt_identity": catalog_identity,
        "catalog_replay_receipt_sha256": catalog_sha,
        "catalog_release_identity": catalog_release_identity,
        "catalog_release_sha256": catalog_release_sha,
    }


def _validate_publication_result(
    result: object,
    *,
    reopened: candidate_authority.ReopenedFixedG0CandidateAuthorityV1,
    binding: Mapping[str, object],
    supplied_catalog_release_identity: object,
) -> tuple[dict[str, object], dict[str, object], dict[str, object]]:
    item = _mapping(result, label="v1 component publication result")
    if set(item) != {"publication_receipt", "offline_panel"}:
        _fail("v1 component publication result fields differ")
    try:
        v1_receipt = publication_v1.validate_component_publication_receipt_v1(
            item["publication_receipt"]
        )
    except publication_v1.CorpusR6MatchupComponentPublicationV1Error as exc:
        raise CorpusR6MatchupComponentPublicationCandidateAuthorityV2Error(
            str(exc)
        ) from exc
    panel = _mapping(item["offline_panel"], label="v1 offline panel")
    catalog_release_identity = _identity(
        supplied_catalog_release_identity, label="catalog release identity"
    )
    if (
        v1_receipt.get("fixed_g0_replay_receipt_identity")
        != binding["catalog_replay_receipt_identity"]
        or v1_receipt.get("catalog_release_identity")
        != catalog_release_identity
        or v1_receipt.get("accepted_candidate_release_identity")
        != binding["accepted_candidate_release_identity"]
        or panel.get("fixed_g0_replay_receipt_identity")
        != binding["catalog_replay_receipt_identity"]
        or panel.get("catalog_release_identity") != catalog_release_identity
        or panel.get("accepted_candidate_release_identity")
        != binding["accepted_candidate_release_identity"]
        or panel.get("accepted_candidate_release") != reopened.candidate_release
    ):
        _fail("v1 component publication differs from candidate authority")
    return item, v1_receipt, panel


def _build_receipt(
    *,
    binding: Mapping[str, object],
    v1_receipt: Mapping[str, object],
) -> dict[str, object]:
    body: dict[str, object] = {
        "schema_version": PUBLICATION_RECEIPT_SCHEMA,
        **dict(binding),
        "candidate_authority_exact_reopened": True,
        "complete_candidate_population_binding_verified": True,
        "exact_occurrence_provenance_binding_verified": True,
        "caller_candidate_release_body_allowed": False,
        "caller_candidate_release_identity_allowed": False,
        "candidate_authority_exact_reopen_required": True,
        "candidate_authority_structure_only_authority": False,
        "legacy_v1_publication_path_authoritative": False,
        "authoritative_consumer_requires_full_v2_result": True,
        "component_publication_receipt": dict(v1_receipt),
        "component_publication_receipt_sha256": v1_receipt[
            "component_publication_receipt_sha256"
        ],
        "producer_release_identity": v1_receipt["producer_release_identity"],
        "producer_release_sha256": v1_receipt["producer_release_sha256"],
        **_policy(),
    }
    body["candidate_authority_component_publication_receipt_sha256"] = (
        canonical_sha256(body)
    )
    return validate_component_publication_candidate_authority_receipt_v2(body)


def validate_component_publication_candidate_authority_receipt_v2(
    value: object,
) -> dict[str, object]:
    """Validate bounded receipt structure without granting root authority."""
    item = _mapping(value, label="candidate-authority publication receipt")
    if set(item) != set(_RECEIPT_FIELDS):
        _fail("candidate-authority publication receipt fields differ")
    retained = _digest(
        item.get("candidate_authority_component_publication_receipt_sha256"),
        label="candidate-authority publication receipt self-hash",
    )
    unhashed = {
        key: nested
        for key, nested in item.items()
        if key != "candidate_authority_component_publication_receipt_sha256"
    }
    if canonical_sha256(unhashed) != retained:
        _fail("candidate-authority publication receipt self-hash differs")
    for field, expected in _policy().items():
        if item.get(field) != expected:
            _fail("candidate-authority publication receipt claims authority")
    root_identity = _identity(
        item.get("candidate_authority_root_identity"),
        label="candidate-authority root identity",
    )
    candidate_identity = _identity(
        item.get("accepted_candidate_release_identity"),
        label="accepted candidate release identity",
    )
    catalog_identity = _identity(
        item.get("catalog_replay_receipt_identity"),
        label="catalog replay receipt identity",
    )
    catalog_release_identity = _identity(
        item.get("catalog_release_identity"),
        label="catalog release identity",
    )
    root_sha = _digest(
        item.get("candidate_authority_root_sha256"),
        label="candidate-authority root SHA",
    )
    candidate_sha = _digest(
        item.get("accepted_candidate_release_sha256"),
        label="accepted candidate release SHA",
    )
    catalog_sha = _digest(
        item.get("catalog_replay_receipt_sha256"),
        label="catalog replay receipt SHA",
    )
    catalog_release_sha = _digest(
        item.get("catalog_release_sha256"),
        label="catalog release SHA",
    )
    try:
        v1_receipt = publication_v1.validate_component_publication_receipt_v1(
            item.get("component_publication_receipt")
        )
    except publication_v1.CorpusR6MatchupComponentPublicationV1Error as exc:
        raise CorpusR6MatchupComponentPublicationCandidateAuthorityV2Error(
            str(exc)
        ) from exc
    prefix = str(root_identity["uri"]).removesuffix(
        candidate_authority.ROOT_FILENAME
    )
    if (
        item.get("schema_version") != PUBLICATION_RECEIPT_SCHEMA
        or _ROOT_URI.fullmatch(str(root_identity["uri"])) is None
        or candidate_identity["uri"]
        != f"{prefix}{candidate_authority.CANDIDATE_RELEASE_FILENAME}"
        or v1_receipt["fixed_g0_replay_receipt_identity"] != catalog_identity
        or v1_receipt["catalog_release_identity"] != catalog_release_identity
        or v1_receipt["accepted_candidate_release_identity"] != candidate_identity
        or item.get("component_publication_receipt_sha256")
        != v1_receipt["component_publication_receipt_sha256"]
        or item.get("producer_release_identity")
        != v1_receipt["producer_release_identity"]
        or item.get("producer_release_sha256")
        != v1_receipt["producer_release_sha256"]
        or item.get("candidate_authority_exact_reopened") is not True
        or item.get("complete_candidate_population_binding_verified") is not True
        or item.get("exact_occurrence_provenance_binding_verified") is not True
        or item.get("caller_candidate_release_body_allowed") is not False
        or item.get("caller_candidate_release_identity_allowed") is not False
        or item.get("candidate_authority_exact_reopen_required") is not True
        or item.get("candidate_authority_structure_only_authority") is not False
        or item.get("legacy_v1_publication_path_authoritative") is not False
        or item.get("authoritative_consumer_requires_full_v2_result") is not True
    ):
        _fail("candidate-authority publication receipt fixed law differs")
    normalized = dict(item)
    normalized.update({
        "candidate_authority_root_identity": root_identity,
        "candidate_authority_root_sha256": root_sha,
        "accepted_candidate_release_identity": candidate_identity,
        "accepted_candidate_release_sha256": candidate_sha,
        "catalog_replay_receipt_identity": catalog_identity,
        "catalog_replay_receipt_sha256": catalog_sha,
        "catalog_release_identity": catalog_release_identity,
        "catalog_release_sha256": catalog_release_sha,
        "component_publication_receipt": v1_receipt,
        "candidate_authority_component_publication_receipt_sha256": retained,
    })
    if canonical_json_bytes(normalized) != canonical_json_bytes(item):
        _fail("candidate-authority publication receipt canonical replay differs")
    return normalized


def publish_all_54_component_release_candidate_authority_v2(
    *,
    producer_id: str,
    producer_release_id: str,
    producer_namespace: str,
    fixed_g0_replay_receipt: Mapping[str, object],
    fixed_g0_replay_receipt_identity: Mapping[str, object],
    catalog_release: Mapping[str, object],
    catalog_release_identity: Mapping[str, object],
    structural_catalogs: Sequence[Mapping[str, object]],
    candidate_authority_root_identity: Mapping[str, object],
    repository_root: Path,
    git_head: GitHead,
    git_blob: GitBlob,
    git_status: GitStatus,
    upstream_source_release: Mapping[str, object],
    upstream_source_release_identity: Mapping[str, object],
    upstream_pack_row_objects: Sequence[Mapping[str, object]],
    producer_code_identity: Mapping[str, object],
    publish_create_once: PublishCreateOnce,
    read_exact: ReadExact,
) -> dict[str, object]:
    """Publish all components after authoritative candidate-root replay."""
    try:
        reopened = candidate_authority.reopen_fixed_g0_candidate_authority_release_v1(
            candidate_authority_root_identity,
            repository_root=repository_root,
            read_exact=read_exact,
            git_head=git_head,
            git_blob=git_blob,
            git_status=git_status,
        )
    except Exception as exc:
        raise CorpusR6MatchupComponentPublicationCandidateAuthorityV2Error(
            f"candidate-authority exact reopen failed: {exc}"
        ) from exc
    fixed_identity = _identity(
        fixed_g0_replay_receipt_identity,
        label="supplied fixed-G0 replay receipt identity",
    )
    fixed_sha = _digest(
        fixed_g0_replay_receipt.get("replay_receipt_sha256"),
        label="supplied fixed-G0 replay receipt SHA",
    )
    supplied_catalog_release_identity = _identity(
        catalog_release_identity, label="supplied catalog release identity"
    )
    supplied_catalog_release_sha = _digest(
        catalog_release.get("release_sha256"),
        label="supplied catalog release SHA",
    )
    binding = _candidate_binding(
        reopened,
        expected_root_identity=candidate_authority_root_identity,
        expected_catalog_replay_receipt_identity=fixed_identity,
        expected_catalog_replay_receipt_sha256=fixed_sha,
        expected_catalog_release_identity=supplied_catalog_release_identity,
        expected_catalog_release_sha256=supplied_catalog_release_sha,
    )
    try:
        result = publication_v1.publish_all_54_component_release_v1(
            producer_id=producer_id,
            producer_release_id=producer_release_id,
            producer_namespace=producer_namespace,
            fixed_g0_replay_receipt=fixed_g0_replay_receipt,
            fixed_g0_replay_receipt_identity=fixed_identity,
            catalog_release=catalog_release,
            catalog_release_identity=supplied_catalog_release_identity,
            structural_catalogs=structural_catalogs,
            accepted_candidate_release=reopened.candidate_release,
            accepted_candidate_release_identity=(
                reopened.candidate_release_identity
            ),
            upstream_source_release=upstream_source_release,
            upstream_source_release_identity=upstream_source_release_identity,
            upstream_pack_row_objects=upstream_pack_row_objects,
            producer_code_identity=producer_code_identity,
            publish_create_once=publish_create_once,
            read_exact=read_exact,
        )
    except publication_v1.CorpusR6MatchupComponentPublicationV1Error as exc:
        raise CorpusR6MatchupComponentPublicationCandidateAuthorityV2Error(
            str(exc)
        ) from exc
    _normalized_result, v1_receipt, panel = _validate_publication_result(
        result,
        reopened=reopened,
        binding=binding,
        supplied_catalog_release_identity=supplied_catalog_release_identity,
    )
    receipt = _build_receipt(binding=binding, v1_receipt=v1_receipt)
    return {
        "publication_receipt": receipt,
        "component_publication_result": {
            "publication_receipt": v1_receipt,
            "offline_panel": panel,
        },
    }


_OFFLINE_PANEL_FIELDS: Final = frozenset({
    "schema_version",
    "producer_id",
    "producer_namespace",
    "fixed_g0_replay_receipt",
    "fixed_g0_replay_receipt_identity",
    "catalog_release_identity",
    "accepted_candidate_release",
    "accepted_candidate_release_identity",
    "upstream_source_release_identity",
    "producer_code_identity",
    "family_registry",
    "family_registry_sha256",
    "task_count",
    "entries",
    "entry_manifest_sha256",
    "input_bundles",
    "input_bundle_identities",
    "input_bundle_identity_manifest_sha256",
    "producer_receipts",
    "producer_receipt_identities",
    "producer_receipt_identity_manifest_sha256",
    "all_54_support_census",
    "all_54_support_census_sha256",
    "producer_release",
    "producer_release_identity",
    "outcome_columns_read",
    "uses_realized_outcomes",
    *source.FALSE_AUTHORITY_FIELDS,
    "offline_panel_result_sha256",
})


def _sequence(value: object, *, label: str) -> list[object]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        _fail(f"{label} must be an array")
    return list(value)


def _exact_canonical_object(
    identity_value: object,
    *,
    read_exact: ReadExact,
    label: str,
) -> tuple[dict[str, object], object]:
    identity = _identity(identity_value, label=f"{label} identity")
    try:
        raw = read_exact(identity)
    except Exception as exc:
        raise CorpusR6MatchupComponentPublicationCandidateAuthorityV2Error(
            f"{label} exact reopen failed"
        ) from exc
    if (
        type(raw) is not bytes
        or len(raw) != identity["bytes"]
        or sha256(raw).hexdigest() != identity["sha256"]
    ):
        _fail(f"{label} exact content identity differs")
    try:
        parsed = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        raise CorpusR6MatchupComponentPublicationCandidateAuthorityV2Error(
            f"{label} must be canonical JSON"
        ) from exc
    body = parsed
    if canonical_json_bytes(body) != raw:
        _fail(f"{label} canonical bytes differ")
    try:
        publication_v1._reject_outcome_carriers(body, label=label)
    except publication_v1.CorpusR6MatchupComponentPublicationV1Error as exc:
        raise CorpusR6MatchupComponentPublicationCandidateAuthorityV2Error(
            str(exc)
        ) from exc
    return identity, body


def _validate_offline_panel_structure(
    value: object,
) -> dict[str, object]:
    panel = _mapping(value, label="component publication offline panel")
    if set(panel) != set(_OFFLINE_PANEL_FIELDS):
        _fail("component publication offline panel fields differ")
    retained = _digest(
        panel.get("offline_panel_result_sha256"),
        label="offline panel self-hash",
    )
    unhashed = {
        key: nested
        for key, nested in panel.items()
        if key != "offline_panel_result_sha256"
    }
    if canonical_sha256(unhashed) != retained:
        _fail("component publication offline panel self-hash differs")
    for field, expected in _policy().items():
        if panel.get(field) != expected:
            _fail("component publication offline panel claims authority")
    entries = _sequence(panel.get("entries"), label="offline panel entries")
    bundles = _sequence(
        panel.get("input_bundles"), label="offline panel input bundles"
    )
    bundle_ids = [
        _identity(value, label=f"offline panel input bundle[{ordinal}]")
        for ordinal, value in enumerate(_sequence(
            panel.get("input_bundle_identities"),
            label="offline panel input bundle identities",
        ))
    ]
    receipts = _sequence(
        panel.get("producer_receipts"), label="offline panel producer receipts"
    )
    receipt_ids = [
        _identity(value, label=f"offline panel producer receipt[{ordinal}]")
        for ordinal, value in enumerate(_sequence(
            panel.get("producer_receipt_identities"),
            label="offline panel producer receipt identities",
        ))
    ]
    if (
        panel.get("schema_version") != producer.OFFLINE_PANEL_RESULT_SCHEMA
        or panel.get("task_count") != source.TASK_COUNT
        or any(
            len(rows) != source.TASK_COUNT
            for rows in (entries, bundles, bundle_ids, receipts, receipt_ids)
        )
        or panel.get("entry_manifest_sha256") != canonical_sha256(entries)
        or panel.get("input_bundle_identity_manifest_sha256")
        != canonical_sha256(bundle_ids)
        or panel.get("producer_receipt_identity_manifest_sha256")
        != canonical_sha256(receipt_ids)
    ):
        _fail("component publication offline panel 54-task lattice differs")
    normalized = dict(panel)
    normalized.update({
        "fixed_g0_replay_receipt_identity": _identity(
            panel.get("fixed_g0_replay_receipt_identity"),
            label="offline panel fixed-G0 replay receipt",
        ),
        "catalog_release_identity": _identity(
            panel.get("catalog_release_identity"),
            label="offline panel catalog release",
        ),
        "accepted_candidate_release_identity": _identity(
            panel.get("accepted_candidate_release_identity"),
            label="offline panel accepted candidate release",
        ),
        "upstream_source_release_identity": _identity(
            panel.get("upstream_source_release_identity"),
            label="offline panel upstream source release",
        ),
        "input_bundle_identities": bundle_ids,
        "producer_receipt_identities": receipt_ids,
        "producer_release_identity": _identity(
            panel.get("producer_release_identity"),
            label="offline panel producer release",
        ),
    })
    if canonical_json_bytes(normalized) != canonical_json_bytes(panel):
        _fail("component publication offline panel canonical replay differs")
    return normalized


def _durable_validate_full_result(
    *,
    receipt: Mapping[str, object],
    component_result: Mapping[str, object],
    read_exact: ReadExact,
) -> dict[str, object]:
    if set(component_result) != {"publication_receipt", "offline_panel"}:
        _fail("nested v1 component publication result fields differ")
    try:
        v1_receipt = publication_v1.validate_component_publication_receipt_v1(
            component_result["publication_receipt"]
        )
    except publication_v1.CorpusR6MatchupComponentPublicationV1Error as exc:
        raise CorpusR6MatchupComponentPublicationCandidateAuthorityV2Error(
            f"nested v1 publication receipt replay failed: {exc}"
        ) from exc
    if v1_receipt != receipt["component_publication_receipt"]:
        _fail("nested v1 publication receipt differs from v2 binding")
    panel = _validate_offline_panel_structure(component_result["offline_panel"])

    cache: dict[tuple[str, str, str, int], object] = {}

    def reopen(identity_value: object, label: str) -> object:
        identity = _identity(identity_value, label=f"{label} identity")
        key = (
            str(identity["uri"]),
            str(identity["generation"]),
            str(identity["sha256"]),
            int(identity["bytes"]),
        )
        if key not in cache:
            _, cache[key] = _exact_canonical_object(
                identity, read_exact=read_exact, label=label
            )
        return cache[key]

    replay = _mapping(reopen(
        receipt["catalog_replay_receipt_identity"], "fixed-G0 replay receipt"
    ), label="fixed-G0 replay receipt")
    catalog_release = _mapping(reopen(
        receipt["catalog_release_identity"], "catalog release"
    ), label="catalog release")
    candidate_release = _mapping(reopen(
        receipt["accepted_candidate_release_identity"],
        "accepted candidate release",
    ), label="accepted candidate release")
    upstream_release = _mapping(reopen(
        v1_receipt["upstream_source_release_identity"], "upstream source release"
    ), label="upstream source release")
    if panel["upstream_source_release_identity"] != v1_receipt[
        "upstream_source_release_identity"
    ]:
        _fail("v1 receipt upstream source root differs from offline panel")
    if (
        replay != panel["fixed_g0_replay_receipt"]
        or panel["fixed_g0_replay_receipt_identity"]
        != receipt["catalog_replay_receipt_identity"]
        or panel["catalog_release_identity"]
        != receipt["catalog_release_identity"]
        or panel["accepted_candidate_release_identity"]
        != receipt["accepted_candidate_release_identity"]
        or candidate_release != panel["accepted_candidate_release"]
        or replay.get("replay_receipt_sha256")
        != receipt["catalog_replay_receipt_sha256"]
        or catalog_release.get("release_sha256")
        != receipt["catalog_release_sha256"]
        or candidate_release.get("accepted_candidate_release_sha256")
        != receipt["accepted_candidate_release_sha256"]
    ):
        _fail("reopened v1 upstream roots differ from panel/authority")

    catalog_entries = _sequence(
        catalog_release.get("entries"), label="catalog release entries"
    )
    candidate_entries = _sequence(
        candidate_release.get("entries"), label="candidate release entries"
    )
    upstream_packs = _sequence(
        upstream_release.get("packs"), label="upstream release packs"
    )
    if (
        len(catalog_entries) != source.TASK_COUNT
        or len(candidate_entries) != source.TASK_COUNT
        or len(upstream_packs) != len(source.PACK_IDS)
    ):
        _fail("reopened v1 upstream lattice differs")
    catalogs = [
        _mapping(reopen(
            _mapping(entry, label=f"catalog entry[{ordinal}]").get(
                "catalog_identity"
            ),
            f"structural catalog[{ordinal}]",
        ), label=f"structural catalog[{ordinal}]")
        for ordinal, entry in enumerate(catalog_entries)
    ]
    for ordinal, entry_value in enumerate(candidate_entries):
        entry = _mapping(entry_value, label=f"candidate entry[{ordinal}]")
        artifact = reopen(
            entry.get("candidate_artifact_identity"),
            f"candidate artifact[{ordinal}]",
        )
        if artifact != entry.get("candidate_artifact"):
            _fail(f"candidate artifact[{ordinal}] body binding differs")
    pack_rows: list[dict[str, object]] = []
    expected_provenance = [
        _identity(
            upstream_release.get("fixed_source_root_identity"),
            label="upstream fixed source root",
        )
    ]
    reopen(expected_provenance[0], "upstream fixed source root")
    for ordinal, pack_value in enumerate(upstream_packs):
        pack = _mapping(pack_value, label=f"upstream pack[{ordinal}]")
        pack_rows.append(_mapping(reopen(
            pack.get("exact_rows_identity"), f"upstream pack rows[{ordinal}]"
        ), label=f"upstream pack rows[{ordinal}]"))
        query = pack.get("warehouse_query_receipt_identity")
        manifests = _sequence(
            pack.get("frozen_artifact_manifest_identities"),
            label=f"upstream pack[{ordinal}] artifact manifests",
        )
        provenance_values = ([] if query is None else [query]) + manifests
        for provenance_ordinal, provenance_value in enumerate(provenance_values):
            identity = _identity(
                provenance_value,
                label=f"upstream provenance[{ordinal}:{provenance_ordinal}]",
            )
            expected_provenance.append(identity)
            reopen(identity, f"upstream provenance[{ordinal}:{provenance_ordinal}]")
    if expected_provenance != v1_receipt["upstream_provenance_identities"]:
        _fail("v1 upstream provenance manifest differs from reopened release")

    materialized_ids = v1_receipt["materialized_object_identities"]
    materialized_bodies = {
        str(identity["uri"]): reopen(identity, f"materialized object[{ordinal}]")
        for ordinal, identity in enumerate(materialized_ids)
    }
    bundle_ids = panel["input_bundle_identities"]
    receipt_ids = panel["producer_receipt_identities"]
    producer_root_identity = panel["producer_release_identity"]
    expected_materialized: list[dict[str, object]] = []
    expected_leaf_bodies: dict[str, object] = {}

    def retain(identity_value: object, body: object, *, label: str) -> None:
        identity = _identity(identity_value, label=label)
        uri = str(identity["uri"])
        previous = expected_leaf_bodies.get(uri)
        if previous is not None and previous != body:
            _fail(f"{label} repeats a URI with different bytes")
        if previous is None:
            expected_materialized.append(identity)
            expected_leaf_bodies[uri] = body

    for ordinal, (bundle, bundle_identity, producer_receipt,
                  producer_receipt_identity) in enumerate(zip(
        panel["input_bundles"], bundle_ids,
        panel["producer_receipts"], receipt_ids, strict=True
    )):
        target_spine = _mapping(
            bundle.get("target_spine"), label=f"bundle target spine[{ordinal}]"
        )
        retain(
            target_spine.get("schedule_slice_identity"),
            target_spine.get("games"),
            label=f"schedule slice[{ordinal}]",
        )
        for slice_ordinal, slice_value in enumerate(_sequence(
            bundle.get("source_slices"),
            label=f"bundle source slices[{ordinal}]",
        )):
            slice_entry = _mapping(
                slice_value,
                label=f"bundle source slice[{ordinal}:{slice_ordinal}]",
            )
            retain(
                slice_entry.get("exact_slice_identity"),
                slice_entry.get("rows"),
                label=f"period slice[{ordinal}:{slice_ordinal}]",
            )
        admission = _mapping(
            producer_receipt.get("admission_support_census"),
            label=f"producer admission census[{ordinal}]",
        )
        retain(
            admission.get("candidate_support_rows_identity"),
            admission.get("candidate_support_rows"),
            label=f"candidate support rows[{ordinal}]",
        )
        retain(bundle_identity, bundle, label=f"input bundle[{ordinal}]")
        retain(
            producer_receipt_identity,
            producer_receipt,
            label=f"producer receipt[{ordinal}]",
        )
    retain(producer_root_identity, panel["producer_release"], label="producer root")
    if materialized_ids != expected_materialized:
        _fail("v1 materialized manifest differs from complete nested leaf manifest")
    for uri, expected_body in expected_leaf_bodies.items():
        if materialized_bodies[uri] != expected_body:
            _fail("nested materialized leaf bytes differ from parent metadata")
    for ordinal, (body, identity) in enumerate(zip(
        panel["input_bundles"], bundle_ids, strict=True
    )):
        if materialized_bodies[str(identity["uri"])] != body:
            _fail(f"offline panel input bundle[{ordinal}] bytes differ")
    for ordinal, (body, identity) in enumerate(zip(
        panel["producer_receipts"], receipt_ids, strict=True
    )):
        if materialized_bodies[str(identity["uri"])] != body:
            _fail(f"offline panel producer receipt[{ordinal}] bytes differ")
    producer_release = _mapping(
        materialized_bodies[str(producer_root_identity["uri"])],
        label="producer release",
    )
    if (
        producer_release != panel["producer_release"]
        or panel["producer_id"] != v1_receipt["producer_id"]
        or panel["producer_namespace"] != v1_receipt["producer_namespace"]
        or panel["all_54_support_census"]
        != producer_release.get("all_54_support_census")
        or panel["all_54_support_census_sha256"]
        != producer_release.get("all_54_support_census_sha256")
        or producer_root_identity != v1_receipt["producer_release_identity"]
        or producer_release.get("producer_release_sha256")
        != v1_receipt["producer_release_sha256"]
        or v1_receipt["producer_release_object_sha256"]
        != producer_root_identity["sha256"]
        or materialized_ids[-1] != producer_root_identity
    ):
        _fail("v1 receipt producer root differs from exact offline panel")
    release_entries = _sequence(
        producer_release.get("entries"), label="producer release entries"
    )
    if len(release_entries) != source.TASK_COUNT:
        _fail("producer release does not contain 54 entries")
    for ordinal, entry_value in enumerate(release_entries):
        entry = _mapping(entry_value, label=f"producer release entry[{ordinal}]")
        panel_entry = _mapping(
            panel["entries"][ordinal], label=f"offline panel entry[{ordinal}]"
        )
        bundle = panel["input_bundles"][ordinal]
        producer_receipt = panel["producer_receipts"][ordinal]
        admission = _mapping(
            producer_receipt.get("admission_support_census"),
            label=f"producer admission census[{ordinal}]",
        )
        deletion = _mapping(
            producer_receipt.get("target_or_later_deletion_proof"),
            label=f"producer deletion proof[{ordinal}]",
        )
        if (
            entry.get("input_bundle_identity") != bundle_ids[ordinal]
            or entry.get("producer_receipt_identity") != receipt_ids[ordinal]
            or panel_entry.get("source_task_ordinal") != ordinal
            or panel_entry.get("input_bundle_identity") != bundle_ids[ordinal]
            or panel_entry.get("producer_receipt_identity") != receipt_ids[ordinal]
            or panel_entry.get("slate") != producer_receipt.get("slate")
            or panel_entry.get("slate") != entry.get("slate")
            or panel_entry.get("catalog_identity")
            != producer_receipt.get("catalog_identity")
            or panel_entry.get("catalog_identity") != entry.get("catalog_identity")
            or panel_entry.get("support_preflight_passed")
            is not producer_receipt.get("support_preflight_passed")
            or panel_entry.get("support_preflight_passed")
            is not entry.get("support_preflight_passed")
            or panel_entry.get("qualifying_candidate_count")
            != admission.get("qualifying_candidate_count")
            or panel_entry.get("qualifying_candidate_count")
            != entry.get("qualifying_candidate_count")
            or panel_entry.get("deletion_proof_sha256")
            != deletion.get("deletion_proof_sha256")
            or producer_receipt.get("family_registry") != panel["family_registry"]
            or producer_receipt.get("family_registry_sha256")
            != panel["family_registry_sha256"]
            or bundle.get("family_registry") != panel["family_registry"]
            or bundle.get("family_registry_sha256")
            != panel["family_registry_sha256"]
        ):
            _fail(f"producer release entry[{ordinal}] output identities differ")

    frozen_family = source.frozen_family_registry_v1()
    if (
        panel["family_registry"] != frozen_family
        or panel["family_registry_sha256"]
        != frozen_family["family_registry_sha256"]
        or producer_release.get("family_registry") != frozen_family
        or producer_release.get("family_registry_sha256")
        != frozen_family["family_registry_sha256"]
    ):
        _fail("offline panel family registry differs from frozen producer evidence")

    try:
        source.validate_producer_release_v1(
            producer_release,
            catalog_release=catalog_release,
            accepted_candidate_release=candidate_release,
            upstream_source_release=upstream_release,
            upstream_pack_row_objects=pack_rows,
            producer_receipts=panel["producer_receipts"],
            input_bundles=panel["input_bundles"],
            structural_catalogs=catalogs,
            expected_catalog_release_identity=receipt["catalog_release_identity"],
            expected_catalog_replay_receipt_identity=receipt[
                "catalog_replay_receipt_identity"
            ],
            expected_candidate_release_identity=receipt[
                "accepted_candidate_release_identity"
            ],
            expected_upstream_source_release_identity=v1_receipt[
                "upstream_source_release_identity"
            ],
            expected_producer_code_identity=panel["producer_code_identity"],
            expected_namespace=str(panel["producer_namespace"]),
        )
    except source.CorpusR6MatchupSourceV2Error as exc:
        raise CorpusR6MatchupComponentPublicationCandidateAuthorityV2Error(
            f"producer release deep replay failed: {exc}"
        ) from exc
    return panel


def validate_component_publication_against_candidate_authority_v2(
    value: object,
    *,
    repository_root: Path,
    read_exact: ReadExact,
    git_head: GitHead,
    git_blob: GitBlob,
    git_status: GitStatus,
) -> dict[str, object]:
    """Replay the full v2 result, every v1 object, and candidate authority."""
    result = _mapping(value, label="candidate-authority component result")
    if set(result) != {"publication_receipt", "component_publication_result"}:
        _fail("candidate-authority component result fields differ")
    receipt = validate_component_publication_candidate_authority_receipt_v2(
        result["publication_receipt"]
    )
    component_result = _mapping(
        result["component_publication_result"],
        label="nested v1 component publication result",
    )
    try:
        reopened = candidate_authority.reopen_fixed_g0_candidate_authority_release_v1(
            receipt["candidate_authority_root_identity"],
            repository_root=repository_root,
            read_exact=read_exact,
            git_head=git_head,
            git_blob=git_blob,
            git_status=git_status,
        )
    except Exception as exc:
        raise CorpusR6MatchupComponentPublicationCandidateAuthorityV2Error(
            f"candidate-authority exact reopen failed: {exc}"
        ) from exc
    binding = _candidate_binding(
        reopened,
        expected_root_identity=receipt["candidate_authority_root_identity"],
        expected_catalog_replay_receipt_identity=receipt[
            "catalog_replay_receipt_identity"
        ],
        expected_catalog_replay_receipt_sha256=receipt[
            "catalog_replay_receipt_sha256"
        ],
        expected_catalog_release_identity=receipt["catalog_release_identity"],
        expected_catalog_release_sha256=receipt["catalog_release_sha256"],
        expected_candidate_release_identity=receipt[
            "accepted_candidate_release_identity"
        ],
        expected_candidate_release_sha256=receipt[
            "accepted_candidate_release_sha256"
        ],
    )
    if any(receipt[field] != binding[field] for field in binding):
        _fail("candidate-authority publication receipt exact binding differs")
    panel = _durable_validate_full_result(
        receipt=receipt,
        component_result=component_result,
        read_exact=read_exact,
    )
    return {
        "publication_receipt": receipt,
        "component_publication_result": {
            "publication_receipt": receipt["component_publication_receipt"],
            "offline_panel": panel,
        },
    }


__all__ = [
    "CorpusR6MatchupComponentPublicationCandidateAuthorityV2Error",
    "PUBLICATION_RECEIPT_SCHEMA",
    "publish_all_54_component_release_candidate_authority_v2",
    "validate_component_publication_against_candidate_authority_v2",
    "validate_component_publication_candidate_authority_receipt_v2",
]
