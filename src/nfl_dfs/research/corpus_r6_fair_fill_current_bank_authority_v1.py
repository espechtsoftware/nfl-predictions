"""Sealed current-bank authority loader for fair fill/selector retests.

This module deliberately separates three capabilities:

* manifest inspection creates the 54 x 5 recipe lattice without opening any
  referenced object;
* selection preparation may open the projection, one fold process budget and
  the later-source catalog, but never a world-artifact body;
* matrix materialization may open exactly the four budgeted training blocks.

The fifth block is not accepted by either selection function.  A subsequent
evaluator must receive an already frozen selection identity before it can ask
for the held-out body.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from hashlib import sha256
import json
from typing import Final

import numpy as np

from nfl_dfs.research import corpus_r6_current_bank_crossed_screen_contract_v1 as contract
from nfl_dfs.research import corpus_r6_current_bank_crossed_screen_task_manifest_v1 as tasks


ReadExact = Callable[[Mapping[str, object]], bytes]
HEADER_SCHEMA: Final = "corpus-r6-fair-fill-current-bank-54x5-header/v1"
SELECTION_PACKAGE_SCHEMA: Final = "corpus-r6-fair-fill-current-bank-selection-package/v1"
EVALUATION_GATE_SCHEMA: Final = "corpus-r6-fair-fill-current-bank-evaluation-gate/v1"
LOCAL_SELECTION_PREFIX: Final = contract.OUTPUT_NAMESPACE + "fair-fill-local-selection/v1/"


class CorpusR6FairFillCurrentBankAuthorityV1Error(ValueError):
    """A sealed authority or capability boundary differed."""


def _fail(message: str) -> None:
    raise CorpusR6FairFillCurrentBankAuthorityV1Error(message)


def _strict_json(raw: bytes, *, label: str) -> dict[str, object]:
    try:
        value = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CorpusR6FairFillCurrentBankAuthorityV1Error(
            f"{label} is not strict JSON"
        ) from exc
    if not isinstance(value, Mapping):
        _fail(f"{label} must be an object")
    return dict(value)


def _identity(value: object, *, label: str) -> dict[str, object]:
    try:
        return contract._safe_object_identity(value, label=label)
    except contract.CorpusR6CurrentBankCrossedScreenContractV1Error as exc:
        raise CorpusR6FairFillCurrentBankAuthorityV1Error(str(exc)) from exc


def _read_bound_json(
    identity: object, *, read_exact: ReadExact, label: str,
) -> tuple[dict[str, object], dict[str, object]]:
    retained = _identity(identity, label=label)
    raw = read_exact(retained)
    if not isinstance(raw, bytes):
        _fail(f"{label} reader must return bytes")
    body = _strict_json(raw, label=label)
    try:
        contract._bind_canonical_body_to_identity_v1(body, retained, label=label)
    except contract.CorpusR6CurrentBankCrossedScreenContractV1Error as exc:
        raise CorpusR6FairFillCurrentBankAuthorityV1Error(str(exc)) from exc
    return body, retained


def _read_bound_bytes(
    identity: object, *, read_exact: ReadExact, label: str,
) -> tuple[bytes, dict[str, object]]:
    retained = _identity(identity, label=label)
    raw = read_exact(retained)
    if (
        not isinstance(raw, bytes)
        or len(raw) != retained["bytes"]
        or sha256(raw).hexdigest() != retained["sha256"]
    ):
        _fail(f"{label} body differs from its sealed identity")
    return raw, retained


def validate_54x5_manifest_headers_v1(value: object) -> dict[str, object]:
    """Validate the sealed manifest and compile 270 byte-free fold recipes."""
    try:
        manifest = tasks.validate_task_manifest_v1(value)
    except tasks.CorpusR6CurrentBankCrossedScreenTaskManifestV1Error as exc:
        raise CorpusR6FairFillCurrentBankAuthorityV1Error(str(exc)) from exc
    if (
        manifest["layer_id"] != "broad-selection-receipt"
        or manifest["phase"] != contract.BROAD_SCREEN_PHASE
        or manifest["task_count"] != contract.PANEL_SLATE_COUNT
        or len(manifest["task_bindings"]) != contract.PANEL_SLATE_COUNT
    ):
        _fail("manifest is not the sealed 54-slate broad selection panel")
    recipes: list[dict[str, object]] = []
    for source, binding in enumerate(manifest["task_bindings"]):
        request = binding["request"]
        budgets = request["worker_process_budget_identities"]
        if (
            binding["source_ordinal"] != source
            or request["source_ordinal"] != source
            or len(budgets) != contract.FOLDS_PER_SLATE
        ):
            _fail(f"task {source} source/fold lattice differs")
        for fold, block in enumerate(contract.WORLD_BLOCKS):
            recipes.append({
                "source_ordinal": source,
                "fold_ordinal": fold,
                "heldout_block_label_only": block,
                "projection_bundle_identity": request["projection_bundle_identity"],
                "process_budget_identity": budgets[fold],
                "world_artifact_body_opened": False,
            })
    body = {
        "schema_version": HEADER_SCHEMA,
        "manifest_sha256": manifest["task_manifest_sha256"],
        "source_count": contract.PANEL_SLATE_COUNT,
        "folds_per_source": contract.FOLDS_PER_SLATE,
        "recipe_count": len(recipes),
        "recipes": recipes,
        "object_body_open_count": 0,
        "heldout_world_body_open_count": 0,
    }
    body["header_sha256"] = contract.canonical_sha256_v1(body)
    return body


def prepare_selection_package_v1(
    manifest_value: object, *, source_ordinal: int, fold_ordinal: int,
    read_exact: ReadExact,
) -> dict[str, object]:
    """Open only projection, fold budget, and source catalog authorities."""
    header = validate_54x5_manifest_headers_v1(manifest_value)
    if (
        type(source_ordinal) is not int
        or type(fold_ordinal) is not int
        or not 0 <= source_ordinal < contract.PANEL_SLATE_COUNT
        or not 0 <= fold_ordinal < contract.FOLDS_PER_SLATE
    ):
        _fail("source/fold ordinal differs")
    manifest = tasks.validate_task_manifest_v1(manifest_value)
    request = manifest["task_bindings"][source_ordinal]["request"]
    topology_body, topology_identity = _read_bound_json(
        request["topology_identity"], read_exact=read_exact, label="topology",
    )
    bundle_body, bundle_identity = _read_bound_json(
        request["projection_bundle_identity"], read_exact=read_exact,
        label="projection bundle",
    )
    try:
        bundle = contract.validate_projection_bundle_authority_v1(
            bundle_body, publication_identity=bundle_identity,
            topology=topology_body, topology_identity=topology_identity,
        )
    except contract.CorpusR6CurrentBankCrossedScreenContractV1Error as exc:
        raise CorpusR6FairFillCurrentBankAuthorityV1Error(str(exc)) from exc
    if bundle["source_ordinal"] != source_ordinal:
        _fail("projection source differs from manifest recipe")
    projection = bundle["fold_projections"][fold_ordinal]
    budget_body, budget_identity = _read_bound_json(
        request["worker_process_budget_identities"][fold_ordinal],
        read_exact=read_exact, label="fold process budget",
    )
    try:
        budget = contract.validate_process_budget_v1(budget_body)
    except contract.CorpusR6CurrentBankCrossedScreenContractV1Error as exc:
        raise CorpusR6FairFillCurrentBankAuthorityV1Error(str(exc)) from exc
    if (
        budget["source_ordinal"] != source_ordinal
        or budget["process_ordinal"] != source_ordinal * 5 + fold_ordinal
        or budget["projection_bundle_identity"] != bundle_identity
    ):
        _fail("fold budget does not bind the selected projection recipe")
    reads = {str(row["role"]): row["identity"] for row in budget["read_allowlist"]}
    expected_training_roles = [
        f"training-world-{block}" for block in projection["training_blocks"]
    ]
    if list(reads) != ["projection-bundle", "later-source", *expected_training_roles]:
        _fail("fold budget read capability differs")
    heldout_role = f"training-world-{projection['heldout_block']}"
    if heldout_role in reads:
        _fail("held-out world entered selection read capability")
    if reads["later-source"] != projection["later_source_identity"]:
        _fail("later-source authority differs")
    source_body, source_identity = _read_bound_json(
        reads["later-source"], read_exact=read_exact, label="later source",
    )
    slate_rows = [
        row for row in source_body.get("slates", [])
        if isinstance(row, Mapping) and row.get("slate_id") == projection["slate_id"]
    ]
    if len(slate_rows) != 1:
        _fail("projection slate is absent or repeated in later source")
    slate = dict(slate_rows[0])
    if "catalog" not in slate or "artifact_receipts" not in slate:
        _fail("later-source slate catalog/receipts are absent")
    package = {
        "schema_version": SELECTION_PACKAGE_SCHEMA,
        "manifest_sha256": manifest["task_manifest_sha256"],
        "header_sha256": header["header_sha256"],
        "source_ordinal": source_ordinal,
        "fold_ordinal": fold_ordinal,
        "slate_id": projection["slate_id"],
        "heldout_block_label_only": projection["heldout_block"],
        "training_blocks": list(projection["training_blocks"]),
        "projection_bundle_identity": bundle_identity,
        "topology_identity": topology_identity,
        "projection_sha256": projection["projection_sha256"],
        "process_budget_identity": budget_identity,
        "later_source_identity": source_identity,
        "candidate_count": len(projection["candidates"]),
        "candidate_lineup_order_sha256": projection["candidate_lineup_order_sha256"],
        "catalog_sha256": contract.canonical_sha256_v1(slate["catalog"]),
        "training_artifact_identities": [reads[role] for role in expected_training_roles],
        "authority_body_open_count": 4,
        "training_world_body_open_count": 0,
        "heldout_world_identity_exposed": False,
        "heldout_world_body_open_count": 0,
    }
    package["selection_package_sha256"] = contract.canonical_sha256_v1(package)
    return package


def open_training_world_bodies_v1(
    selection_package: object, *, read_exact: ReadExact,
) -> list[bytes]:
    """Materialize exactly the four identities frozen in a selection package."""
    if not isinstance(selection_package, Mapping):
        _fail("selection package must be an object")
    package = dict(selection_package)
    expected_hash = package.pop("selection_package_sha256", None)
    if expected_hash != contract.canonical_sha256_v1(package):
        _fail("selection package self hash differs")
    package["selection_package_sha256"] = expected_hash
    if package.get("schema_version") != SELECTION_PACKAGE_SCHEMA:
        _fail("selection package schema differs")
    identities = package.get("training_artifact_identities")
    if not isinstance(identities, Sequence) or len(identities) != 4:
        _fail("selection package must contain exactly four training identities")
    bodies: list[bytes] = []
    for index, raw_identity in enumerate(identities):
        identity = _identity(raw_identity, label=f"training world {index}")
        raw = read_exact(identity)
        if not isinstance(raw, bytes):
            _fail("training world reader must return bytes")
        bodies.append(raw)
    return bodies


def execute_sealed_selection_fold_v1(
    manifest_value: object, *, source_ordinal: int, fold_ordinal: int,
    read_exact: ReadExact,
) -> dict[str, object]:
    """Cross-score and select from exact sealed authorities, never a caller matrix."""
    from nfl_dfs.research import corpus_legal_feasibility as legal
    from nfl_dfs.research import corpus_r6_full_union_panel_freeze_v1 as full_union
    from nfl_dfs.research import lr8_later_period_source as later
    from nfl_dfs.research import residual_world_columns as worlds
    from nfl_dfs.research import corpus_r6_current_bank_crossed_screen_selector_v1 as selector

    manifest = tasks.validate_task_manifest_v1(manifest_value)
    request = manifest["task_bindings"][source_ordinal]["request"]
    topology, topology_identity = _read_bound_json(
        request["topology_identity"], read_exact=read_exact, label="topology",
    )
    bundle, bundle_identity = _read_bound_json(
        request["projection_bundle_identity"], read_exact=read_exact,
        label="projection bundle",
    )
    try:
        bundle = contract.validate_projection_bundle_authority_v1(
            bundle, publication_identity=bundle_identity,
            topology=topology, topology_identity=topology_identity,
        )
    except contract.CorpusR6CurrentBankCrossedScreenContractV1Error as exc:
        raise CorpusR6FairFillCurrentBankAuthorityV1Error(str(exc)) from exc
    projection = bundle["fold_projections"][fold_ordinal]
    try:
        (
            task_envelope, source_manifest, source_panel, source_members,
            _source_task_result, task_result_identity,
        ) = full_union.reopen_task_result_envelope_v1(
            projection["source_task_result_identity"], read_exact=read_exact,
        )
    except full_union.CorpusR6FullUnionPanelFreezeV1Error as exc:
        raise CorpusR6FairFillCurrentBankAuthorityV1Error(str(exc)) from exc
    if (
        task_envelope["task_result_payload_sha256"]
        != projection["task_result_payload_sha256"]
        or task_envelope["slate_id"] != projection["slate_id"]
        or task_envelope["source_ordinal"] != source_ordinal
    ):
        _fail("projection/source task-result lineage differs")
    budget, budget_identity = _read_bound_json(
        request["worker_process_budget_identities"][fold_ordinal],
        read_exact=read_exact, label="fold process budget",
    )
    try:
        budget = contract.validate_process_budget_v1(budget)
    except contract.CorpusR6CurrentBankCrossedScreenContractV1Error as exc:
        raise CorpusR6FairFillCurrentBankAuthorityV1Error(str(exc)) from exc
    reads = {str(row["role"]): row["identity"] for row in budget["read_allowlist"]}
    expected_roles = [
        "projection-bundle", "later-source",
        *[f"training-world-{block}" for block in projection["training_blocks"]],
    ]
    if list(reads) != expected_roles:
        _fail("selection process budget does not expose exact four-block law")
    source, _ = _read_bound_json(
        reads["later-source"], read_exact=read_exact, label="later source",
    )
    expected_freeze = source.get("freeze_sha256")
    if not isinstance(expected_freeze, str):
        _fail("later source lacks frozen SHA-256")
    source = later.validate_source_freeze(
        source, expected_freeze_sha256=expected_freeze
    )
    matches = [row for row in source["slates"] if row["slate_id"] == projection["slate_id"]]
    if len(matches) != 1:
        _fail("projection slate is absent or repeated in later source")
    slate = matches[0]
    players = tuple(worlds.PlayerSpec.from_mapping(row) for row in slate["catalog"])
    player_ids = tuple(player.player_id for player in players)
    receipts = {str(row["block"]): dict(row) for row in slate["artifact_receipts"]}
    aligned: list[np.ndarray] = []
    opened_training: list[dict[str, object]] = []
    for block in projection["training_blocks"]:
        role = f"training-world-{block}"
        identity = _identity(reads[role], label=role)
        expected_projection_identity = projection["world_artifact_identities"][
            f"world_artifact_{str(block).lower()}"
        ]
        receipt = receipts[str(block)]
        receipt_identity = _identity({
            key: receipt[key] for key in ("uri", "generation", "sha256", "bytes")
        }, label=f"{block} receipt")
        if identity != expected_projection_identity or identity != receipt_identity:
            _fail("budget/projection/source world identity differs")
        raw, _ = _read_bound_bytes(identity, read_exact=read_exact, label=role)
        loaded = later.load_artifact_worlds(receipt, raw)
        loaded_ids = tuple(str(value) for value in loaded.player_ids)
        draws = np.asarray(loaded.player_draws)
        if (
            loaded.block != block or len(set(loaded_ids)) != len(loaded_ids)
            or set(loaded_ids) != set(player_ids)
            or draws.dtype != np.dtype(np.float32)
            or draws.shape != (len(loaded_ids), contract.WORLDS_PER_BLOCK)
            or not np.isfinite(draws).all()
        ):
            _fail("training artifact player/matrix binding differs")
        index = {player_id: ordinal for ordinal, player_id in enumerate(loaded_ids)}
        aligned.append(draws[[index[player_id] for player_id in player_ids]])
        opened_training.append(identity)
    player_draws = np.ascontiguousarray(np.concatenate(aligned, axis=1), dtype=np.float32)
    rosters = [tuple(row["roster_player_ids"]) for row in projection["candidates"]]
    scores = np.asarray(legal.cross_score_full_union(
        players, player_draws, rosters,
        expected_worlds=4 * contract.WORLDS_PER_BLOCK,
    ))
    receipt = selector.build_selection_fold_receipt_from_matrix_v1(
        projection_bundle=bundle, projection_bundle_identity=bundle_identity,
        topology=topology, topology_identity=topology_identity,
        process_budget=budget, process_budget_identity=budget_identity,
        fold_ordinal=fold_ordinal, training_score_matrix=scores,
    )
    body = {
        "schema_version": "corpus-r6-fair-fill-sealed-selection-fold/v1",
        "manifest_sha256": manifest["task_manifest_sha256"],
        "source_ordinal": source_ordinal,
        "fold_ordinal": fold_ordinal,
        "projection_bundle_identity": bundle_identity,
        "projection_sha256": projection["projection_sha256"],
        "source_task_result_identity": task_result_identity,
        "source_task_result_payload_sha256": task_envelope[
            "task_result_payload_sha256"
        ],
        "source_execution_manifest_sha256": task_envelope[
            "execution_manifest_sha256"
        ],
        "source_manifest_identity": task_envelope["manifest_identity"],
        "source_panel_sha256": source_panel["panel_self_sha256"],
        "source_panel_member_count": len(source_members),
        "source_commit_sha": task_envelope["source_commit_sha"],
        "source_immutable_image": task_envelope["immutable_image"],
        "candidate_lineup_order_sha256": projection["candidate_lineup_order_sha256"],
        "training_score_matrix_sha256": projection["expected_training_score_matrix_sha256"],
        "training_artifact_identities": opened_training,
        "selection_fold_receipt": receipt,
        "selection_fold_receipt_sha256": receipt["selection_fold_receipt_sha256"],
        "heldout_artifact_identity_present": False,
        "heldout_artifact_body_read": False,
    }
    body["sealed_selection_fold_sha256"] = contract.canonical_sha256_v1(body)
    return body


def build_evaluation_gate_v1(
    *, selection_result_identity: object, selection_result: object,
    heldout_artifact_identity: object,
) -> dict[str, object]:
    """Bind held-out addressability to an already immutable selection result."""
    selection_identity = _identity(
        selection_result_identity, label="frozen selection result"
    )
    if not isinstance(selection_result, Mapping):
        _fail("selection result must be an object")
    try:
        contract._bind_canonical_body_to_identity_v1(
            selection_result, selection_identity, label="frozen selection result"
        )
    except contract.CorpusR6CurrentBankCrossedScreenContractV1Error as exc:
        raise CorpusR6FairFillCurrentBankAuthorityV1Error(str(exc)) from exc
    body = {
        "schema_version": EVALUATION_GATE_SCHEMA,
        "selection_result_identity": selection_identity,
        "heldout_artifact_identity": _identity(
            heldout_artifact_identity, label="heldout artifact"
        ),
        "selection_frozen_before_heldout_addressability": True,
    }
    body["evaluation_gate_sha256"] = contract.canonical_sha256_v1(body)
    return body


def derive_create_once_selection_identity_v1(selection_result: object) -> dict[str, object]:
    """Derive the sole local publication identity accepted by evaluation."""
    if not isinstance(selection_result, Mapping):
        _fail("selection result must be an object")
    body = dict(selection_result)
    required = {
        "schema_version", "manifest_sha256", "source_ordinal", "fold_ordinal",
        "projection_bundle_identity", "projection_sha256",
        "source_task_result_identity", "source_task_result_payload_sha256",
        "source_execution_manifest_sha256", "source_commit_sha",
        "source_immutable_image", "source_manifest_identity",
        "source_panel_sha256", "source_panel_member_count",
        "candidate_lineup_order_sha256", "training_score_matrix_sha256",
        "training_artifact_identities", "selection_fold_receipt",
        "selection_fold_receipt_sha256", "heldout_artifact_identity_present",
        "heldout_artifact_body_read", "sealed_selection_fold_sha256",
    }
    if (
        set(body) != required
        or body.get("schema_version")
        != "corpus-r6-fair-fill-sealed-selection-fold/v1"
        or body.get("heldout_artifact_identity_present") is not False
        or body.get("heldout_artifact_body_read") is not False
        or not isinstance(body.get("training_artifact_identities"), list)
        or len(body["training_artifact_identities"]) != 4
        or not isinstance(body.get("selection_fold_receipt"), Mapping)
        or body["selection_fold_receipt"].get("selection_fold_receipt_sha256")
        != body.get("selection_fold_receipt_sha256")
    ):
        _fail("sealed selection result fields/policy differ")
    expected = body.get("sealed_selection_fold_sha256")
    replay = contract.canonical_sha256_v1({
        key: value for key, value in body.items()
        if key != "sealed_selection_fold_sha256"
    })
    if expected != replay:
        _fail("sealed selection result self hash differs")
    raw = contract.canonical_json_bytes_v1(body)
    digest = sha256(raw).hexdigest()
    return {
        "uri": f"{LOCAL_SELECTION_PREFIX}{digest}.json",
        "generation": "1",
        "sha256": digest,
        "bytes": len(raw),
    }


def evaluate_sealed_selection_fold_v1(
    manifest_value: object, *, selection_result: object,
    selection_result_identity: object, read_exact: ReadExact,
) -> dict[str, object]:
    """Open the projection-derived fifth block only after selection freezes."""
    from nfl_dfs.research import corpus_legal_feasibility as legal
    from nfl_dfs.research import lr8_later_period_source as later
    from nfl_dfs.research import residual_world_columns as worlds

    if not isinstance(selection_result, Mapping):
        _fail("selection result must be an object")
    selection = dict(selection_result)
    expected_identity = derive_create_once_selection_identity_v1(selection)
    if _identity(selection_result_identity, label="selection result") != expected_identity:
        _fail("selection result identity is not its create-once derived authority")
    manifest = tasks.validate_task_manifest_v1(manifest_value)
    source_ordinal = int(selection["source_ordinal"])
    fold_ordinal = int(selection["fold_ordinal"])
    request = manifest["task_bindings"][source_ordinal]["request"]
    # This is the first point at which held-out addressability may be derived.
    topology, topology_identity = _read_bound_json(
        request["topology_identity"], read_exact=read_exact, label="topology",
    )
    bundle, bundle_identity = _read_bound_json(
        request["projection_bundle_identity"], read_exact=read_exact,
        label="projection bundle",
    )
    try:
        bundle = contract.validate_projection_bundle_authority_v1(
            bundle, publication_identity=bundle_identity,
            topology=topology, topology_identity=topology_identity,
        )
    except contract.CorpusR6CurrentBankCrossedScreenContractV1Error as exc:
        raise CorpusR6FairFillCurrentBankAuthorityV1Error(str(exc)) from exc
    projection = bundle["fold_projections"][fold_ordinal]
    if (
        selection["manifest_sha256"] != manifest["task_manifest_sha256"]
        or selection["projection_bundle_identity"] != bundle_identity
        or selection["projection_sha256"] != projection["projection_sha256"]
        or selection["candidate_lineup_order_sha256"]
        != projection["candidate_lineup_order_sha256"]
    ):
        _fail("frozen selection does not bind the exact evaluation projection")
    source, _ = _read_bound_json(
        projection["later_source_identity"], read_exact=read_exact,
        label="later source",
    )
    expected_freeze = source.get("freeze_sha256")
    if not isinstance(expected_freeze, str):
        _fail("later source lacks frozen SHA-256")
    source = later.validate_source_freeze(source, expected_freeze_sha256=expected_freeze)
    slate = [row for row in source["slates"] if row["slate_id"] == projection["slate_id"]]
    if len(slate) != 1:
        _fail("projection slate is absent or repeated in later source")
    slate = slate[0]
    receipts = {str(row["block"]): dict(row) for row in slate["artifact_receipts"]}
    block = str(projection["heldout_block"])
    receipt = receipts[block]
    heldout_identity = _identity({
        key: receipt[key] for key in ("uri", "generation", "sha256", "bytes")
    }, label="heldout source receipt")
    if heldout_identity != projection["world_artifact_identities"][f"world_artifact_{block.lower()}"]:
        _fail("projection/source heldout identity differs")
    raw, heldout_identity = _read_bound_bytes(
        heldout_identity, read_exact=read_exact, label="heldout world"
    )
    loaded = later.load_artifact_worlds(receipt, raw)
    players = tuple(worlds.PlayerSpec.from_mapping(row) for row in slate["catalog"])
    player_ids = tuple(player.player_id for player in players)
    loaded_ids = tuple(str(value) for value in loaded.player_ids)
    draws = np.asarray(loaded.player_draws)
    index = {player_id: ordinal for ordinal, player_id in enumerate(loaded_ids)}
    if (
        loaded.block != block or set(loaded_ids) != set(player_ids)
        or draws.dtype != np.dtype(np.float32)
        or draws.shape != (len(loaded_ids), contract.WORLDS_PER_BLOCK)
    ):
        _fail("heldout artifact player/matrix binding differs")
    aligned = np.ascontiguousarray(
        draws[[index[player_id] for player_id in player_ids]], dtype=np.float32
    )
    rosters = [tuple(row["roster_player_ids"]) for row in projection["candidates"]]
    heldout_scores = np.asarray(legal.cross_score_full_union(
        players, aligned, rosters, expected_worlds=contract.WORLDS_PER_BLOCK,
    ))
    try:
        selection_receipt = contract.validate_selection_fold_receipt_v1(
            selection["selection_fold_receipt"], projection=projection,
        )
        heldout_authority, heldout_scores = contract._heldout_fold_authority_v1(
            projection=projection, heldout_artifact_identity=heldout_identity,
            heldout_scores=heldout_scores,
        )
    except contract.CorpusR6CurrentBankCrossedScreenContractV1Error as exc:
        raise CorpusR6FairFillCurrentBankAuthorityV1Error(str(exc)) from exc
    lineup_index = {
        str(row["lineup_id"]): ordinal
        for ordinal, row in enumerate(projection["candidates"])
    }
    books: list[dict[str, object]] = []
    for cell in selection_receipt["cells"]:
        selected = [str(value) for value in cell["selected_lineup_ids"]]
        for prefix in cell["prefixes"]:
            size = int(prefix["prefix_size"])
            prefix_ids = selected[:size]
            if (
                contract.canonical_sha256_v1(prefix_ids)
                != prefix["selected_lineup_ids_sha256"]
            ):
                _fail("selection prefix lineup hash differs")
            maxima = heldout_scores[
                [lineup_index[lineup_id] for lineup_id in prefix_ids], :
            ].max(axis=0)
            book = {
                "view_id": cell["view_id"],
                "replicate": cell["replicate"],
                "strategy_id": cell["strategy_id"],
                "strategy_sha256": cell["strategy_sha256"],
                "selection_cell_sha256": cell["selection_cell_sha256"],
                "prefix_size": size,
                "prefix_payload_sha256": prefix["prefix_payload_sha256"],
                "selected_lineup_ids_sha256": prefix["selected_lineup_ids_sha256"],
                "heldout_world_count": int(maxima.size),
                "mean_portfolio_max_micro": int(round(float(maxima.mean()) * 1_000_000)),
                "world_count_ge_200": int(np.count_nonzero(maxima >= 200.0)),
                "world_count_ge_220": int(np.count_nonzero(maxima >= 220.0)),
                "world_count_ge_230": int(np.count_nonzero(maxima >= 230.0)),
            }
            book["book_evaluation_sha256"] = contract.canonical_sha256_v1(book)
            books.append(book)
    evaluation_body = {
        "schema_version": "corpus-r6-fair-fill-control-evaluation-fold/v1",
        "source_ordinal": source_ordinal,
        "fold_ordinal": fold_ordinal,
        "heldout_block": block,
        "projection_sha256": projection["projection_sha256"],
        "selection_fold_receipt_sha256": selection_receipt[
            "selection_fold_receipt_sha256"
        ],
        "heldout_fold_authority": heldout_authority,
        "book_count": len(books),
        "books": books,
        "books_sha256": contract.canonical_sha256_v1(books),
        "realized_outcomes_read": False,
    }
    evaluation_body["evaluation_fold_sha256"] = contract.canonical_sha256_v1(
        evaluation_body
    )
    return {
        "schema_version": "corpus-r6-fair-fill-sealed-evaluation-fold/v1",
        "selection_result_identity": expected_identity,
        "heldout_artifact_identity": heldout_identity,
        "heldout_opened_after_selection_freeze": True,
        "evaluation_fold": evaluation_body,
        "evaluation_fold_sha256": evaluation_body["evaluation_fold_sha256"],
    }


__all__ = [
    "CorpusR6FairFillCurrentBankAuthorityV1Error",
    "build_evaluation_gate_v1",
    "derive_create_once_selection_identity_v1",
    "evaluate_sealed_selection_fold_v1",
    "execute_sealed_selection_fold_v1",
    "open_training_world_bodies_v1",
    "prepare_selection_package_v1",
    "validate_54x5_manifest_headers_v1",
]
