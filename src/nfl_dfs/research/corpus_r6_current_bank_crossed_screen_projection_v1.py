"""Direct sealed-task projection for the R6 current-bank crossed screen.

This executable layer has one deliberately narrow job: exact-reopen the
already-sealed 54-slate full-union panel and publish one five-fold selection
input bundle per slate.  It never reconstructs the seven Foundry arms, opens a
world artifact, runs a selector, or copies an existing selected book.

The input boundary is an exact 111-object allowlist:

``panel root + execution manifest + fixed panel + 54 leaves + 54 task results``.

The root is read first by its contract-pinned identity.  Because those bytes
are already content-addressed by the frozen contract, their embedded object
identities can safely define the closed allowlist before the structural replay
follows a child.  Repeated validator reads are served from the cache; a URI
cannot be addressed at two generations and no listing/current-generation API
exists in this module.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from copy import deepcopy
from hashlib import sha256
from typing import Final

from nfl_dfs.research import corpus_parametric_batch as batch
from nfl_dfs.research import corpus_r6_current_bank_crossed_screen_contract_v1 as contract
from nfl_dfs.research import corpus_r6_full_union_panel_freeze_v1 as freeze


PROJECTION_EXECUTION_SUMMARY_SCHEMA: Final = (
    "corpus-r6-current-bank-projection-execution-summary/v1"
)
STRUCTURAL_OBJECT_COUNT: Final = contract.EXACT_STRUCTURAL_OBJECT_COUNT
FOLD_SCOPE_IDS: Final = tuple(
    f"holdout-{block}" for block in contract.WORLD_BLOCKS
)
ALL_BLOCK_SCOPE_ID: Final = "all-block-final-fit"

# These are fields of the sealed historical books, not inputs to the crossed
# screen.  Prefix matching prevents a future selected/marginal variant from
# silently entering the projection even if the upstream schema grows.
_FORBIDDEN_EXACT_OUTPUT_FIELDS: Final = frozenset({
    "admission",
    "admission_id",
    "admission_sha256",
    "books",
    "book_id",
    "book_sha256",
    "heldout_metrics_descriptive",
    "training_metrics",
})
_FORBIDDEN_OUTPUT_PREFIXES: Final = (
    "marginal_",
    "selected_",
)


class CorpusR6CurrentBankCrossedScreenProjectionV1Error(ValueError):
    """The direct current-bank projection cannot be proven exact."""


ReadExact = Callable[[Mapping[str, object]], bytes]
PublishCreateOnce = Callable[[str, bytes], object]
IdentityKey = tuple[str, str, str, int]


def _fail(message: str) -> None:
    raise CorpusR6CurrentBankCrossedScreenProjectionV1Error(message)


def _mapping(value: object, *, label: str) -> dict[str, object]:
    if not isinstance(value, Mapping) or any(type(key) is not str for key in value):
        _fail(f"{label} must be a string-keyed object")
    return dict(value)


def _sequence(value: object, *, label: str) -> list[object]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        _fail(f"{label} must be an ordered array")
    return list(value)


def _identity(value: object, *, label: str) -> dict[str, object]:
    if hasattr(value, "as_dict") and callable(value.as_dict):
        value = value.as_dict()
    try:
        return batch.normalize_object_identity(value, label=label)
    except batch.CorpusParametricBatchError as exc:
        raise CorpusR6CurrentBankCrossedScreenProjectionV1Error(str(exc)) from exc


def _identity_key(value: object, *, label: str) -> IdentityKey:
    item = _identity(value, label=label)
    return (
        str(item["uri"]),
        str(item["generation"]),
        str(item["sha256"]),
        int(item["bytes"]),
    )


def _read_exact_bytes(
    identity_value: object,
    *,
    read_exact: ReadExact,
    label: str,
) -> tuple[bytes, dict[str, object]]:
    identity = _identity(identity_value, label=f"{label} identity")
    raw = read_exact(identity)
    if (
        type(raw) is not bytes
        or len(raw) != identity["bytes"]
        or sha256(raw).hexdigest() != identity["sha256"]
    ):
        _fail(f"{label} exact-read content identity differs")
    return raw, identity


def _parse_canonical_json(raw: bytes, *, label: str) -> dict[str, object]:
    try:
        value = batch.parse_canonical_json_bytes(raw, label=label)
    except batch.CorpusParametricBatchError as exc:
        raise CorpusR6CurrentBankCrossedScreenProjectionV1Error(str(exc)) from exc
    return _mapping(value, label=label)


class StructuralObjectCacheV1:
    """Exact finite cache with no URI listing or current-generation seam."""

    def __init__(
        self,
        *,
        read_exact: ReadExact,
        allowed_identities: Sequence[Mapping[str, object]],
        preloaded: Mapping[IdentityKey, bytes] | None = None,
    ) -> None:
        normalized = [
            _identity(value, label=f"structural identity[{index}]")
            for index, value in enumerate(allowed_identities)
        ]
        keys = [
            _identity_key(value, label=f"structural identity[{index}]")
            for index, value in enumerate(normalized)
        ]
        uris = [str(value["uri"]) for value in normalized]
        if (
            len(normalized) != STRUCTURAL_OBJECT_COUNT
            or len(set(keys)) != STRUCTURAL_OBJECT_COUNT
            or len(set(uris)) != STRUCTURAL_OBJECT_COUNT
        ):
            _fail("structural allowlist is not exactly 111 unique objects")
        self._read = read_exact
        self._allowed = dict(zip(keys, normalized, strict=True))
        self._uri_to_key = dict(zip(uris, keys, strict=True))
        self._values: dict[IdentityKey, bytes] = {}
        self._underlying_reads: list[IdentityKey] = []
        for key, raw in dict(preloaded or {}).items():
            if key not in self._allowed:
                _fail("preloaded structural object is outside the allowlist")
            identity = self._allowed[key]
            if (
                type(raw) is not bytes
                or len(raw) != identity["bytes"]
                or sha256(raw).hexdigest() != identity["sha256"]
            ):
                _fail("preloaded structural object identity differs")
            self._values[key] = bytes(raw)
            self._underlying_reads.append(key)

    def read_exact(self, identity_value: Mapping[str, object]) -> bytes:
        identity = _identity(identity_value, label="structural read identity")
        key = _identity_key(identity, label="structural read identity")
        uri = str(identity["uri"])
        if uri not in self._uri_to_key or self._uri_to_key[uri] != key:
            _fail("structural read is outside the exact 111-object allowlist")
        cached = self._values.get(key)
        if cached is not None:
            return cached
        raw = self._read(identity)
        if (
            type(raw) is not bytes
            or len(raw) != identity["bytes"]
            or sha256(raw).hexdigest() != identity["sha256"]
        ):
            _fail("structural exact-read content identity differs")
        self._values[key] = bytes(raw)
        self._underlying_reads.append(key)
        return raw

    def require_complete(self) -> dict[str, object]:
        observed = set(self._values)
        expected = set(self._allowed)
        if observed != expected or len(self._underlying_reads) != STRUCTURAL_OBJECT_COUNT:
            _fail("structural replay did not read each of the 111 objects exactly once")
        ordered = [self._allowed[key] for key in self._allowed]
        return {
            "structural_object_count": STRUCTURAL_OBJECT_COUNT,
            "underlying_exact_read_count": len(self._underlying_reads),
            "structural_identities_sha256": contract.canonical_sha256_v1(ordered),
            "no_listing_api": True,
            "no_current_generation_input_read": True,
        }


def projection_structural_identity_inventory_v1(
    root_value: object, *, panel_identity: object,
) -> list[dict[str, object]]:
    """Bind the frozen panel root and derive A's exact 111-object inventory."""
    root = _mapping(root_value, label="sealed panel root hint")
    retained_panel_identity = _identity(
        panel_identity, label="sealed panel root"
    )
    root_raw = contract.canonical_json_bytes_v1(root)
    if (
        retained_panel_identity != contract.PANEL_IDENTITY
        or len(root_raw) != retained_panel_identity["bytes"]
        or sha256(root_raw).hexdigest() != retained_panel_identity["sha256"]
        or root.get("panel_freeze_sha256") != contract.PANEL_SELF_SHA256
    ):
        _fail("sealed panel root self-hash differs from the frozen contract")
    rows = [
        _mapping(value, label=f"panel slate descriptor[{index}]")
        for index, value in enumerate(
            _sequence(root.get("slate_freezes"), label="panel slate descriptors")
        )
    ]
    if (
        len(rows) != contract.PANEL_SLATE_COUNT
        or [row.get("source_ordinal") for row in rows]
        != list(range(contract.PANEL_SLATE_COUNT))
    ):
        _fail("sealed panel root source-ordinal inventory differs")
    inventory = [
        retained_panel_identity,
        _identity(root.get("manifest_identity"), label="execution manifest"),
        _identity(root.get("panel_index_identity"), label="fixed panel index"),
    ]
    for index, row in enumerate(rows):
        inventory.extend((
            _identity(
                row.get("slate_freeze_identity"),
                label=f"slate freeze[{index}]",
            ),
            _identity(
                row.get("task_result_identity"),
                label=f"task result[{index}]",
            ),
        ))
    identity_keys = [_identity_key(value, label="structural identity") for value in inventory]
    if (
        len(inventory) != STRUCTURAL_OBJECT_COUNT
        or len(set(identity_keys)) != STRUCTURAL_OBJECT_COUNT
        or len({str(value["uri"]) for value in inventory})
        != STRUCTURAL_OBJECT_COUNT
    ):
        _fail("sealed panel structural inventory count differs")
    return inventory


def _reopen_structural_panel_v1(
    *, read_exact: ReadExact,
) -> tuple[
    dict[str, object],
    dict[str, object],
    StructuralObjectCacheV1,
    dict[str, object],
]:
    # The sole pre-allowlist read is the fixed root identity itself.  Its exact
    # bytes then define every child that the structural validator may follow.
    root_raw, root_identity = _read_exact_bytes(
        contract.PANEL_IDENTITY,
        read_exact=read_exact,
        label="sealed panel root",
    )
    root_hint = _parse_canonical_json(root_raw, label="sealed panel root")
    inventory = projection_structural_identity_inventory_v1(
        root_hint, panel_identity=root_identity
    )
    root_key = _identity_key(root_identity, label="sealed panel root")
    cache = StructuralObjectCacheV1(
        read_exact=read_exact,
        allowed_identities=inventory,
        preloaded={root_key: root_raw},
    )
    try:
        panel, reopened_identity = freeze.reopen_panel_freeze_v1(
            contract.PANEL_IDENTITY,
            read_exact=cache.read_exact,
        )
    except Exception as exc:
        raise CorpusR6CurrentBankCrossedScreenProjectionV1Error(
            "sealed panel exact structural replay failed"
        ) from exc
    if (
        reopened_identity != root_identity
        or panel.get("panel_freeze_sha256") != contract.PANEL_SELF_SHA256
        or panel.get("source_slate_count") != contract.PANEL_SLATE_COUNT
        or panel.get("rank_80_book_count") != contract.PANEL_RANK_80_BOOK_COUNT
        or panel.get("prefix_count") != contract.PANEL_PREFIX_COUNT
    ):
        _fail("sealed panel replay differs from the frozen contract")
    cache_summary = cache.require_complete()
    return panel, root_identity, cache, cache_summary


def _forbid_old_book_output_fields(value: object, *, path: str = "projection") -> None:
    if isinstance(value, Mapping):
        for raw_key, item in value.items():
            key = str(raw_key)
            if (
                key in _FORBIDDEN_EXACT_OUTPUT_FIELDS
                or key.startswith(_FORBIDDEN_OUTPUT_PREFIXES)
            ):
                _fail(f"{path}.{key} copies an old book/heldout/marginal field")
            _forbid_old_book_output_fields(item, path=f"{path}.{key}")
    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        for index, item in enumerate(value):
            _forbid_old_book_output_fields(item, path=f"{path}[{index}]")


def _common_book_training_authority_v1(
    *,
    scope_value: object,
    candidate_lineup_ids: Sequence[str],
    fold_ordinal: int,
) -> tuple[str, list[int]]:
    scope = _mapping(scope_value, label=f"fold scope[{fold_ordinal}]")
    books = [
        _mapping(value, label=f"fold[{fold_ordinal}] book[{index}]")
        for index, value in enumerate(
            _sequence(scope.get("books"), label=f"fold[{fold_ordinal}] books")
        )
    ]
    strategies = contract.frozen_strategies_v1()
    expected_blocks = [
        block
        for block in contract.WORLD_BLOCKS
        if block != contract.WORLD_BLOCKS[fold_ordinal]
    ]
    expected_shape = [
        len(candidate_lineup_ids),
        len(expected_blocks) * contract.WORLDS_PER_BLOCK,
    ]
    input_ids_sha256 = contract.canonical_sha256_v1(list(candidate_lineup_ids))
    if len(books) != len(strategies):
        _fail("fold scope does not contain the exact eight sealed books")
    matrix_hashes: set[str] = set()
    for index, (book, strategy) in enumerate(zip(books, strategies, strict=True)):
        if (
            book.get("strategy_id") != strategy["strategy_id"]
            or book.get("strategy_sha256") != strategy["strategy_sha256"]
            or book.get("fit_scope_id") != FOLD_SCOPE_IDS[fold_ordinal]
            or book.get("heldout_block") != contract.WORLD_BLOCKS[fold_ordinal]
            or book.get("training_blocks") != expected_blocks
            or book.get("input_lineup_ids_sha256") != input_ids_sha256
            or book.get("training_score_shape") != expected_shape
        ):
            _fail(
                f"fold[{fold_ordinal}] book[{index}] candidate order/input/shape "
                "differs"
            )
        digest = book.get("training_score_matrix_sha256")
        if (
            type(digest) is not str
            or len(digest) != 64
            or any(character not in "0123456789abcdef" for character in digest)
        ):
            _fail(f"fold[{fold_ordinal}] book[{index}] training matrix hash differs")
        matrix_hashes.add(digest)
    if len(matrix_hashes) != 1:
        _fail("the eight sealed books do not share one training matrix hash")
    return next(iter(matrix_hashes)), expected_shape


def _build_projection_bundle_from_task_surface_v1(
    *,
    source_ordinal: int,
    slate_id: str,
    source_task_result_identity: object,
    task_result_payload_sha256: str,
    task_result: object,
) -> dict[str, object]:
    result = _mapping(task_result, label="direct task result surface")
    if result.get("slate_id") != slate_id:
        _fail("direct task result slate differs from panel source ordinal")
    surface = _mapping(result.get("full_union_surface"), label="full-union surface")
    scopes = [
        _mapping(value, label=f"full-union scope[{index}]")
        for index, value in enumerate(
            _sequence(surface.get("scopes"), label="full-union scopes")
        )
    ]
    if (
        len(scopes) != len(contract.WORLD_BLOCKS) + 1
        or [scope.get("fit_scope_id") for scope in scopes[:5]] != list(FOLD_SCOPE_IDS)
        or scopes[5].get("fit_scope_id") != ALL_BLOCK_SCOPE_ID
        or surface.get("rotated_simulated_fold_count") != len(contract.WORLD_BLOCKS)
        or surface.get("final_fit_is_distinct_all_block_refit") is not True
    ):
        _fail("direct task result does not expose five folds plus one distinct final fit")
    expected_payload_sha = batch.canonical_sha256(result)
    if task_result_payload_sha256 != expected_payload_sha:
        _fail("task-result payload hash differs from the exact direct surface")

    fold_projections: list[dict[str, object]] = []
    for fold_ordinal, (heldout, scope) in enumerate(
        zip(contract.WORLD_BLOCKS, scopes[:5], strict=True)
    ):
        view = _mapping(
            scope.get("candidate_view"),
            label=f"fold[{fold_ordinal}] candidate view",
        )
        raw_candidates = [
            _mapping(value, label=f"fold[{fold_ordinal}] candidate[{index}]")
            for index, value in enumerate(
                _sequence(
                    view.get("eligible_candidates"),
                    label=f"fold[{fold_ordinal}] eligible candidates",
                )
            )
        ]
        # Explicitly project the seven allowed fields.  This is the schema
        # firewall that prevents selected books or descriptive metrics from
        # hitchhiking out of the sealed task body.
        candidates = [
            {
                "lineup_id": candidate.get("lineup_id"),
                "roster_player_ids": deepcopy(candidate.get("roster_player_ids")),
                "training_origin_blocks": deepcopy(
                    candidate.get("training_origin_blocks")
                ),
                "training_source_arms": deepcopy(
                    candidate.get("training_source_arms")
                ),
                "training_occurrence_counts_by_block": deepcopy(
                    candidate.get("training_occurrence_counts_by_block")
                ),
                "training_source_arms_by_block": deepcopy(
                    candidate.get("training_source_arms_by_block")
                ),
                "training_occurrence_count": candidate.get(
                    "training_occurrence_count"
                ),
            }
            for candidate in raw_candidates
        ]
        lineup_ids = [str(candidate["lineup_id"]) for candidate in candidates]
        rosters = [candidate["roster_player_ids"] for candidate in candidates]
        matrix_sha256, matrix_shape = _common_book_training_authority_v1(
            scope_value=scope,
            candidate_lineup_ids=lineup_ids,
            fold_ordinal=fold_ordinal,
        )
        training_blocks = [
            block for block in contract.WORLD_BLOCKS if block != heldout
        ]
        body: dict[str, object] = {
            "schema_version": contract.PROJECTION_SCHEMA,
            "contract_id": contract.CONTRACT_ID,
            "slate_id": slate_id,
            "fit_scope_id": FOLD_SCOPE_IDS[fold_ordinal],
            "source_task_result_identity": _identity(
                source_task_result_identity,
                label="source task-result identity",
            ),
            "task_result_payload_sha256": task_result_payload_sha256,
            "later_source_identity": deepcopy(
                result.get("later_source_freeze_identity")
            ),
            "world_artifact_identities": deepcopy(
                result.get("world_artifact_identities")
            ),
            "fit_candidate_view_sha256": view.get(
                "fit_candidate_view_sha256"
            ),
            "selection_provenance_sha256": view.get(
                "selection_provenance_sha256"
            ),
            "training_blocks": training_blocks,
            "heldout_block": heldout,
            "training_world_columns_sha256": (
                contract.canonical_world_columns_sha256_v1(training_blocks)
            ),
            "candidates": candidates,
            "candidate_lineup_order_sha256": contract.canonical_sha256_v1(
                lineup_ids
            ),
            "candidate_rosters_sha256": contract.canonical_sha256_v1(rosters),
            "candidate_rows_sha256": contract.canonical_sha256_v1(candidates),
            "expected_training_score_matrix_sha256": matrix_sha256,
            "expected_training_score_shape": matrix_shape,
            "policy": dict(contract.POLICY_CLAIMS),
        }
        body["projection_sha256"] = contract.canonical_sha256_v1(body)
        fold_projections.append(contract.validate_narrow_projection_v1(body))

    bundle = contract.build_projection_bundle_v1(
        source_ordinal=source_ordinal,
        fold_projections=fold_projections,
    )
    _forbid_old_book_output_fields(bundle)
    return contract.validate_projection_bundle_v1(bundle)


def _task_result_payload_sha256_v1(
    *,
    task_result_identity: object,
    task_result: Mapping[str, object],
    cache: StructuralObjectCacheV1,
) -> str:
    raw = cache.read_exact(
        _identity(task_result_identity, label="task-result envelope identity")
    )
    envelope = _parse_canonical_json(raw, label="task-result envelope")
    digest = envelope.get("task_result_payload_sha256")
    expected = batch.canonical_sha256(dict(task_result))
    if digest != expected:
        _fail("task-result envelope payload hash differs from reopened task surface")
    return expected


def _reopen_design_and_topology_v1(
    *,
    design_identity: object,
    topology_identity: object,
    read_exact: ReadExact,
) -> tuple[
    dict[str, object],
    dict[str, object],
    dict[str, object],
    dict[str, object],
]:
    design_raw, retained_design_identity = _read_exact_bytes(
        design_identity,
        read_exact=read_exact,
        label="crossed-screen design",
    )
    design = _parse_canonical_json(design_raw, label="crossed-screen design")
    topology_raw, retained_topology_identity = _read_exact_bytes(
        topology_identity,
        read_exact=read_exact,
        label="crossed-screen topology",
    )
    topology = _parse_canonical_json(
        topology_raw,
        label="crossed-screen topology",
    )
    try:
        retained_design = contract.validate_design_authority_v1(
            design,
            publication_identity=retained_design_identity,
        )
        retained_topology = contract.validate_result_topology_v1(topology)
    except contract.CorpusR6CurrentBankCrossedScreenContractV1Error as exc:
        raise CorpusR6CurrentBankCrossedScreenProjectionV1Error(str(exc)) from exc
    if (
        retained_design["topology"] != retained_topology
        or retained_design["topology_sha256"] != retained_topology["topology_sha256"]
        or len(topology_raw) != retained_topology_identity["bytes"]
        or sha256(topology_raw).hexdigest() != retained_topology_identity["sha256"]
    ):
        _fail("design and exact topology authority differ")
    return (
        retained_design,
        retained_design_identity,
        retained_topology,
        retained_topology_identity,
    )


def _publication_identity_v1(
    *,
    uri: str,
    raw: bytes,
    returned_identity: object,
    read_exact: ReadExact,
) -> dict[str, object]:
    identity = _identity(returned_identity, label="projection publication identity")
    if (
        identity["uri"] != uri
        or identity["bytes"] != len(raw)
        or identity["sha256"] != sha256(raw).hexdigest()
    ):
        _fail("create-once projection publication identity differs")
    reopened = read_exact(identity)
    if type(reopened) is not bytes or reopened != raw:
        _fail("create-once projection exact reopen differs")
    return identity


def publish_projection_layer_v1(
    *,
    design_identity: object,
    topology_identity: object,
    read_exact: ReadExact,
    publish_create_once: PublishCreateOnce,
) -> dict[str, object]:
    """Publish all 54 direct five-fold bundles in source-ordinal order.

    All bundle bytes and their topology budgets are computed before the first
    output write.  The publisher has one operation, create-once; the returned
    generation is exact-reopened and byte-compared before the next ordinal.
    """
    (
        design,
        retained_design_identity,
        topology,
        retained_topology_identity,
    ) = _reopen_design_and_topology_v1(
        design_identity=design_identity,
        topology_identity=topology_identity,
        read_exact=read_exact,
    )
    panel, panel_identity, cache, cache_summary = _reopen_structural_panel_v1(
        read_exact=read_exact
    )
    rows = [
        _mapping(value, label=f"panel slate descriptor[{index}]")
        for index, value in enumerate(panel["slate_freezes"])
    ]
    bundles: list[dict[str, object]] = []
    for source_ordinal, row in enumerate(rows):
        leaf_identity = _identity(
            row.get("slate_freeze_identity"),
            label=f"slate-freeze identity[{source_ordinal}]",
        )
        try:
            (
                leaf,
                _manifest,
                _fixed_panel,
                _members,
                task_result,
                reopened_leaf_identity,
            ) = freeze.reopen_slate_freeze_v1(
                leaf_identity,
                read_exact=cache.read_exact,
            )
        except Exception as exc:
            raise CorpusR6CurrentBankCrossedScreenProjectionV1Error(
                f"slate[{source_ordinal}] exact structural replay failed"
            ) from exc
        task_result_identity = _identity(
            row.get("task_result_identity"),
            label=f"task-result identity[{source_ordinal}]",
        )
        if (
            reopened_leaf_identity != leaf_identity
            or leaf.get("source_ordinal") != source_ordinal
            or leaf.get("slate_id") != row.get("slate_id")
            or leaf.get("task_result_identity") != task_result_identity
        ):
            _fail(f"slate[{source_ordinal}] leaf/task-result binding differs")
        payload_sha256 = _task_result_payload_sha256_v1(
            task_result_identity=task_result_identity,
            task_result=task_result,
            cache=cache,
        )
        bundles.append(_build_projection_bundle_from_task_surface_v1(
            source_ordinal=source_ordinal,
            slate_id=str(row["slate_id"]),
            source_task_result_identity=task_result_identity,
            task_result_payload_sha256=payload_sha256,
            task_result=task_result,
        ))
    # The second slate replay and envelope access must be pure cache hits.
    if cache.require_complete() != cache_summary:
        _fail("structural cache identity changed during direct projection")

    topology_projection_rows = [
        _mapping(row, label="projection topology row")
        for row in topology["objects"]
        if row["role"] == "projection"
    ]
    budget_by_uri = {
        str(row["uri"]): _mapping(row, label="design publication budget")
        for row in design["publication_budgets"]
    }
    planned: list[tuple[str, bytes, dict[str, object]]] = []
    for source_ordinal, (topology_row, bundle) in enumerate(
        zip(topology_projection_rows, bundles, strict=True)
    ):
        uri = str(topology_row["uri"])
        raw = contract.canonical_json_bytes_v1(bundle)
        budget = budget_by_uri.get(uri)
        if (
            topology_row.get("ordinal") != source_ordinal + 1
            or budget is None
            or budget.get("role") != "projection"
            or budget.get("create_once") is not True
            or type(budget.get("max_bytes")) is not int
            or not 0 < len(raw) <= int(budget["max_bytes"])
        ):
            _fail("projection output URI/order/byte precharge differs")
        planned.append((uri, raw, bundle))
    if len(planned) != contract.PANEL_SLATE_COUNT:
        _fail("projection publication plan does not contain exactly 54 slates")

    layer_entries: list[dict[str, object]] = []
    identities: list[dict[str, object]] = []
    for source_ordinal, (uri, raw, bundle) in enumerate(planned):
        returned = publish_create_once(uri, raw)
        identity = _publication_identity_v1(
            uri=uri,
            raw=raw,
            returned_identity=returned,
            read_exact=read_exact,
        )
        try:
            contract.validate_projection_bundle_authority_v1(
                bundle,
                publication_identity=identity,
                topology=topology,
                topology_identity=retained_topology_identity,
            )
        except contract.CorpusR6CurrentBankCrossedScreenContractV1Error as exc:
            raise CorpusR6CurrentBankCrossedScreenProjectionV1Error(str(exc)) from exc
        identities.append(identity)
        layer_entries.append({
            "source_ordinal": source_ordinal,
            "slate_id": bundle["slate_id"],
            "identity": identity,
        })
    layer = contract.build_layer_binding_v1(
        role="projection",
        entries=layer_entries,
    )
    body: dict[str, object] = {
        "schema_version": PROJECTION_EXECUTION_SUMMARY_SCHEMA,
        "contract_id": contract.CONTRACT_ID,
        "design_identity": retained_design_identity,
        "topology_identity": retained_topology_identity,
        "topology_sha256": topology["topology_sha256"],
        "panel_identity": panel_identity,
        "panel_self_sha256": panel["panel_freeze_sha256"],
        "structural_replay": cache_summary,
        "projection_count": len(identities),
        "projection_identities": identities,
        "projection_identities_sha256": contract.canonical_sha256_v1(identities),
        "projection_layer": layer,
        "planned_write_bytes": sum(len(raw) for _uri, raw, _body in planned),
        "planned_write_ceiling_bytes": sum(
            int(budget_by_uri[uri]["max_bytes"]) for uri, _raw, _body in planned
        ),
        "source_ordinal_order": list(range(contract.PANEL_SLATE_COUNT)),
        "fold_order": list(contract.WORLD_BLOCKS),
        "selector_executed": False,
        "world_artifact_read": False,
        "old_seven_arm_reconstruction_executed": False,
        "old_book_fields_copied": False,
        "input_listing_performed": False,
        "input_current_generation_resolution_performed": False,
        "policy": dict(contract.POLICY_CLAIMS),
    }
    body["projection_execution_summary_sha256"] = contract.canonical_sha256_v1(body)
    return body


__all__ = [
    "CorpusR6CurrentBankCrossedScreenProjectionV1Error",
    "PROJECTION_EXECUTION_SUMMARY_SCHEMA",
    "STRUCTURAL_OBJECT_COUNT",
    "StructuralObjectCacheV1",
    "projection_structural_identity_inventory_v1",
    "publish_projection_layer_v1",
]
