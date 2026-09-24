"""Pure contracts for independent R6 selector-selection and audit banks.

This module owns no storage, warehouse, cloud, realized-score, or promotion
seam.  It freezes the eight all-block final-fit controls, bounds experimental
challengers, binds draw matrices to their ordered player catalogs and RNG
streams, and keeps selection and audit banks disjoint.  The companion
``corpus_r6_selector_audit_v1`` module consumes these receipts without
changing any of the already-pinned retrieval implementations.

The first stopping law is deliberately simple: every member in one immutable
ordered audit ledger must be consumed.  Precision fields are frozen now so a
future sequential law cannot quietly reinterpret an already-open audit bank.
"""

from __future__ import annotations

import json
import math
import re
from collections.abc import Callable, Mapping, Sequence
from hashlib import sha256
from typing import Final

import numpy as np

from nfl_dfs.research import residual_world_columns as rw
from nfl_dfs.research.corpus_r6_full_union_fast_lane_v1 import (
    frozen_full_union_strategies_v1,
)
from nfl_dfs.research.object_identity import content_identity


PLAN_SCHEMA: Final = "corpus-r6-independent-bank-plan/v2"
PRECURSOR_DESIGN_SCHEMA: Final = "corpus-r6-independent-bank-precursor-design/v1"
CANDIDATE_AUTHORITY_SCHEMA: Final = "corpus-r6-independent-bank-candidate-authority/v1"
LAW_RELEASE_SCHEMA: Final = "corpus-r6-independent-bank-law-release/v1"
CODE_RELEASE_SCHEMA: Final = "corpus-r6-independent-bank-code-release/v2"
DRAW_BANK_MEMBER_SCHEMA: Final = "corpus-r6-evaluation-draw-bank-member/v1"
DRAW_BANK_ROOT_SCHEMA: Final = "corpus-r6-evaluation-draw-bank-root/v1"
PRECISION_RULE_SCHEMA: Final = "corpus-r6-selector-precision-rule/v2"
CROSS_LAW_COUPLING_SCHEMA: Final = "corpus-r6-cross-law-coupling/v1"
MULTI_LAW_SHADOW_SCHEMA: Final = "corpus-r6-joint-multi-law-shadow/v1"
FINAL_FIT_SCOPE_ID: Final = "all-block-final-fit"
FIXED_STOPPING_LAW: Final = "fixed-all-members-v1"
ENTRY_BUDGET: Final = 80
CONTROL_COUNT: Final = 8
CHALLENGER_CAP: Final = 4
CONTRACT_MODULE_PATH: Final = (
    "src/nfl_dfs/research/corpus_r6_independent_bank_contract_v1.py"
)
SELECTOR_AUDIT_MODULE_PATH: Final = (
    "src/nfl_dfs/research/corpus_r6_selector_audit_v1.py"
)

PublishCreateOnce = Callable[[str, bytes], Mapping[str, object]]
ReadExact = Callable[[Mapping[str, object]], bytes]

EXACT_CONTROL_IDENTITIES: Final = (
    (
        0,
        "coverage-194-v1",
        "1e1e6a11149ca1c8c9babd183b85adb2ce27d0f976ca863b43768aa3dab0433f",
    ),
    (
        1,
        "strict-200-coverage-v1",
        "9689bb11de4616e4a6295ae0a5b0ec30aa174097f1965867fdc08d7b2e7d02de",
    ),
    (
        2,
        "tail-ladder-200-210-220-v1",
        "5561d663cdc2ec8f928ddf5a44889f16e3c23cdd264f4c8fef7925547aa527ea",
    ),
    (
        3,
        "mean-score-v1",
        "5c880aeca7c8ec3386a9d44b111937fada857f569cb324dd2163987b333654c6",
    ),
    (
        4,
        "expected-max-v1",
        "ad94b80a0ea61d1c58f64f825f00f0d0fea47f36158a239c29382836ff2cb780",
    ),
    (
        5,
        "block-supported-tail-ladder-v1",
        "1ae24780c211a329e8a9867e5dec39630a7efcc640deba9e05561f6a8c98668b",
    ),
    (
        6,
        "regime-robust-ladder-v1",
        "125610a3fda4c230bacd44f1778e43fe03905a504d55ec6fe4c424c0cbbd0e7b",
    ),
    (
        7,
        "strict-230-coverage-v1",
        "6b1f2b3078f6cb98f8f7d74b04e18ccf6e84477de6b4c3df4cd1912d1e0260e3",
    ),
)

THRESHOLD_METRICS: Final = {
    "worlds_ge_194": (194.0, ">="),
    "worlds_gt_200": (200.0, ">"),
    "worlds_gt_210": (210.0, ">"),
    "worlds_gt_220": (220.0, ">"),
    "worlds_gt_230": (230.0, ">"),
    "worlds_gt_240": (240.0, ">"),
}

_SUPPORTED_METHODS: Final = frozenset({
    "greedy-threshold-coverage-v1",
    "greedy-tail-ladder-v1",
    "rank-mean-score-v1",
    "greedy-expected-max-v1",
    "greedy-block-supported-ladder-v1",
    "greedy-blockmin-ladder-v1",
})

# Simulation-score fields are permitted.  Historical labels and decision
# authority are not.  Token matching catches nested spellings such as
# ``actual_score`` and ``contestWinner`` without rejecting ``score_matrix``.
_FORBIDDEN_KEY_TOKENS: Final = frozenset({
    "actual",
    "actuals",
    "realized",
    "outcome",
    "outcomes",
    "winner",
    "winning",
    "payout",
    "payouts",
    "prize",
    "roi",
    "promotion",
    "promote",
    "decision",
})
_FORBIDDEN_EXACT_KEYS: Final = frozenset({
    "rank",
    "ranking",
    "finish",
    "finish_position",
    "contest_rank",
    "field_rank",
})


class CorpusR6IndependentBankContractV1Error(ValueError):
    """An independent-bank receipt cannot preserve its scientific boundary."""


def _fail(message: str) -> None:
    raise CorpusR6IndependentBankContractV1Error(message)


def _mapping(value: object, *, label: str) -> dict[str, object]:
    if not isinstance(value, Mapping) or any(type(key) is not str for key in value):
        _fail(f"{label} must be a string-keyed object")
    return dict(value)


def _sequence(value: object, *, label: str) -> list[object]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        _fail(f"{label} must be an ordered array")
    return list(value)


def _keys(value: Mapping[str, object], expected: set[str], *, label: str) -> None:
    if set(value) != expected:
        _fail(f"{label} fields differ")


def _string(value: object, *, label: str) -> str:
    if type(value) is not str or not value:
        _fail(f"{label} must be a nonempty string")
    return value


def _integer(value: object, *, label: str, minimum: int = 0) -> int:
    if type(value) is not int or value < minimum:
        _fail(f"{label} must be an exact integer >= {minimum}")
    return value


def _finite_float(value: object, *, label: str, minimum: float | None = None) -> float:
    if type(value) not in {int, float} or type(value) is bool:
        _fail(f"{label} must be a finite number")
    retained = float(value)
    if not math.isfinite(retained) or (minimum is not None and retained < minimum):
        _fail(f"{label} is outside its allowed range")
    return retained


def _sha256(value: object, *, label: str) -> str:
    retained = _string(value, label=label)
    if len(retained) != 64 or any(character not in "0123456789abcdef" for character in retained):
        _fail(f"{label} must be lowercase SHA-256")
    return retained


def normalize_code_identity_v1(
    value: object, *, expected_module_path: str | None = None, label: str
) -> dict[str, str]:
    """Normalize one exact Git/module-byte identity.

    Git/current-byte replay belongs to the publication operator.  This pure
    contract nevertheless preserves the exact identities that operator must
    replay rather than accepting an unbound implementation label.
    """
    item = _mapping(value, label=label)
    _keys(
        item,
        {"source_commit_sha", "module_path", "module_sha256"},
        label=label,
    )
    commit = _string(item["source_commit_sha"], label=f"{label} commit")
    if len(commit) != 40 or any(character not in "0123456789abcdef" for character in commit):
        _fail(f"{label} commit must be lowercase 40-hex")
    module_path = _string(item["module_path"], label=f"{label} module path")
    if expected_module_path is not None and module_path != expected_module_path:
        _fail(f"{label} module path differs")
    return {
        "source_commit_sha": commit,
        "module_path": module_path,
        "module_sha256": _sha256(
            item["module_sha256"], label=f"{label} module sha256"
        ),
    }


def canonical_json_bytes_v1(value: object) -> bytes:
    """Return deterministic JSON bytes and reject non-finite/non-JSON values."""
    try:
        return json.dumps(
            value,
            allow_nan=False,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise CorpusR6IndependentBankContractV1Error(
            "value is not canonical JSON"
        ) from exc


def canonical_sha256_v1(value: object) -> str:
    return sha256(canonical_json_bytes_v1(value)).hexdigest()


def add_self_hash_v1(value: Mapping[str, object], *, field: str) -> dict[str, object]:
    body = dict(value)
    if field in body:
        _fail(f"self-hash field {field} already exists")
    body[field] = canonical_sha256_v1(body)
    return body


def validate_self_hash_v1(
    value: Mapping[str, object], *, field: str, label: str
) -> str:
    retained = _sha256(value.get(field), label=f"{label} {field}")
    body = {key: item for key, item in value.items() if key != field}
    if canonical_sha256_v1(body) != retained:
        _fail(f"{label} self-hash differs")
    return retained


def _key_tokens(value: str) -> tuple[str, ...]:
    snake = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", value).lower()
    return tuple(token for token in re.split(r"[^a-z0-9]+", snake) if token)


def assert_outcome_free_v1(value: object, *, label: str = "payload") -> None:
    """Recursively reject historical-label and decision-authority keys."""
    if isinstance(value, Mapping):
        for key, item in value.items():
            if type(key) is not str:
                _fail(f"{label} contains a non-string key")
            tokens = _key_tokens(key)
            normalized = "_".join(tokens)
            historical_rank = (
                {"rank", "ranking", "finish"}.intersection(tokens)
                and {"actual", "realized", "historical", "contest", "field", "winner"}
                .intersection(tokens)
            )
            if (
                normalized in _FORBIDDEN_EXACT_KEYS
                or _FORBIDDEN_KEY_TOKENS.intersection(tokens)
                or historical_rank
            ):
                _fail(f"{label} contains forbidden field {key!r}")
            assert_outcome_free_v1(item, label=f"{label}.{key}")
        return
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        for index, item in enumerate(value):
            assert_outcome_free_v1(item, label=f"{label}[{index}]")
        return
    canonical_json_bytes_v1(value)


def _normalized_content_identity(value: object, *, label: str) -> dict[str, object]:
    item = _mapping(value, label=label)
    try:
        uri, generation, digest, size = content_identity(item)
    except (KeyError, TypeError, ValueError) as exc:
        raise CorpusR6IndependentBankContractV1Error(
            f"{label} content identity differs"
        ) from exc
    if size < 0:
        _fail(f"{label} byte count differs")
    return {
        "uri": uri,
        "generation": generation,
        "sha256": digest,
        "bytes": size,
    }


def normalize_content_identity_v1(
    value: object, *, label: str
) -> dict[str, object]:
    """Public strict normalizer for an immutable object generation identity."""
    return _normalized_content_identity(value, label=label)


def reopen_body_exact_v1(
    value: Mapping[str, object],
    identity_value: object,
    *,
    read_exact: ReadExact,
    label: str,
) -> dict[str, object]:
    """Require an independent generation-pinned reopen of exact body bytes.

    A digest-shaped mapping is not publication evidence.  Every authority
    consumer must provide a separately reviewed exact-generation reader.  The
    reader receives the complete content identity and must return the bytes at
    that generation; current/live or caller-supplied bytes are insufficient.
    """
    if not callable(read_exact):
        _fail(f"{label} requires an exact-generation reader")
    body = _mapping(value, label=label)
    identity = _normalized_content_identity(identity_value, label=label)
    expected = canonical_json_bytes_v1(body)
    if (
        identity["bytes"] != len(expected)
        or identity["sha256"] != sha256(expected).hexdigest()
    ):
        _fail(f"{label} content identity differs from exact body")
    try:
        reopened = read_exact(identity)
    except Exception as exc:
        raise CorpusR6IndependentBankContractV1Error(
            f"{label} exact-generation reopen failed"
        ) from exc
    if type(reopened) is not bytes or reopened != expected:
        _fail(f"{label} exact-generation reopened bytes differ")
    return identity


def publish_body_create_once_v1(
    value: Mapping[str, object],
    *,
    uri: str,
    publish_create_once: PublishCreateOnce,
    read_exact: ReadExact,
    label: str,
) -> dict[str, object]:
    """Create once, then independently reopen the returned generation."""
    body = _mapping(value, label=label)
    target = _string(uri, label=f"{label} uri")
    if not target.startswith("gs://") or target.endswith("/"):
        _fail(f"{label} uri must be one exact gs:// object")
    if not callable(publish_create_once):
        _fail(f"{label} requires a create-once publisher")
    raw = canonical_json_bytes_v1(body)
    try:
        supplied = publish_create_once(target, raw)
    except Exception as exc:
        raise CorpusR6IndependentBankContractV1Error(
            f"{label} create-once publication failed"
        ) from exc
    identity = _normalized_content_identity(supplied, label=f"published {label}")
    if identity["uri"] != target:
        _fail(f"{label} publisher returned a different uri")
    return reopen_body_exact_v1(
        body, identity, read_exact=read_exact, label=f"published {label}"
    )


def reopen_json_identity_v1(
    identity_value: object, *, read_exact: ReadExact, label: str
) -> tuple[dict[str, object], dict[str, object]]:
    """Open canonical JSON at one exact generation and return body + identity."""
    if not callable(read_exact):
        _fail(f"{label} requires an exact-generation reader")
    identity = _normalized_content_identity(identity_value, label=label)
    try:
        raw = read_exact(identity)
    except Exception as exc:
        raise CorpusR6IndependentBankContractV1Error(
            f"{label} exact-generation reopen failed"
        ) from exc
    if (
        type(raw) is not bytes
        or len(raw) != identity["bytes"]
        or sha256(raw).hexdigest() != identity["sha256"]
    ):
        _fail(f"{label} exact-generation reopened bytes differ")
    try:
        parsed = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        raise CorpusR6IndependentBankContractV1Error(
            f"{label} must be canonical JSON"
        ) from exc
    body = _mapping(parsed, label=label)
    if canonical_json_bytes_v1(body) != raw:
        _fail(f"{label} bytes are not canonical JSON")
    return body, identity


def reopen_bytes_identity_v1(
    identity_value: object, *, read_exact: ReadExact, label: str
) -> tuple[bytes, dict[str, object]]:
    """Open arbitrary bytes at one exact immutable object generation."""
    if not callable(read_exact):
        _fail(f"{label} requires an exact-generation reader")
    identity = _normalized_content_identity(identity_value, label=label)
    try:
        raw = read_exact(identity)
    except Exception as exc:
        raise CorpusR6IndependentBankContractV1Error(
            f"{label} exact-generation reopen failed"
        ) from exc
    if (
        type(raw) is not bytes
        or len(raw) != identity["bytes"]
        or sha256(raw).hexdigest() != identity["sha256"]
    ):
        _fail(f"{label} exact-generation reopened bytes differ")
    return raw, identity


def player_ids_sha256_v1(players: Sequence[rw.PlayerSpec]) -> str:
    rows = tuple(players)
    if not rows or len({player.player_id for player in rows}) != len(rows):
        _fail("player order is empty or repeats an id")
    return canonical_sha256_v1([player.player_id for player in rows])


def player_catalog_sha256_v1(players: Sequence[rw.PlayerSpec]) -> str:
    rows = tuple(players)
    player_ids_sha256_v1(rows)
    return canonical_sha256_v1([{
        "id": player.player_id,
        "pos": player.position,
        "team": player.team,
        "opp": player.opponent,
        "game_id": player.game_id,
        "salary": player.salary,
    } for player in rows])


def float32_matrix_sha256_v1(values: np.ndarray) -> str:
    matrix = np.asarray(values)
    if (
        matrix.dtype != np.dtype(np.float32)
        or matrix.ndim != 2
        or not matrix.shape[0]
        or not matrix.shape[1]
        or not np.isfinite(matrix).all()
    ):
        _fail("player draws must be one nonempty finite float32 matrix")
    little = np.ascontiguousarray(matrix, dtype="<f4")
    header = canonical_json_bytes_v1({
        "dtype": "float32-le",
        "shape": list(little.shape),
    })
    digest = sha256()
    digest.update(header)
    digest.update(b"\0")
    digest.update(memoryview(little).cast("B"))
    return digest.hexdigest()


def draw_source_bytes_v1(
    players: Sequence[rw.PlayerSpec],
    player_draws: np.ndarray,
    *,
    precursor_design_identity: Mapping[str, object],
    precursor_design_sha256: str,
) -> bytes:
    rows = tuple(players)
    matrix = np.asarray(player_draws)
    matrix_sha = float32_matrix_sha256_v1(matrix)
    if len(rows) != matrix.shape[0]:
        _fail("draw source player rows differ from matrix")
    little = np.ascontiguousarray(matrix, dtype="<f4")
    header = canonical_json_bytes_v1({
        "schema_version": "corpus-r6-player-draw-source/v1",
        "player_ids_sha256": player_ids_sha256_v1(rows),
        "player_catalog_sha256": player_catalog_sha256_v1(rows),
        "dtype": "float32-le",
        "shape": list(little.shape),
        "matrix_sha256": matrix_sha,
        "precursor_design_identity": _normalized_content_identity(
            precursor_design_identity, label="precursor design"
        ),
        "precursor_design_sha256": _sha256(
            precursor_design_sha256, label="precursor design sha256"
        ),
    })
    return header + b"\0" + memoryview(little).cast("B").tobytes()


def reopen_draw_source_v1(
    *,
    source_identity: Mapping[str, object],
    players: Sequence[rw.PlayerSpec],
    player_draws: np.ndarray,
    precursor_design_identity: Mapping[str, object],
    precursor_design_sha256: str,
    read_exact: ReadExact,
) -> dict[str, object]:
    identity = _normalized_content_identity(source_identity, label="draw source")
    expected = draw_source_bytes_v1(
        players,
        player_draws,
        precursor_design_identity=precursor_design_identity,
        precursor_design_sha256=precursor_design_sha256,
    )
    if (
        identity["bytes"] != len(expected)
        or identity["sha256"] != sha256(expected).hexdigest()
    ):
        _fail("draw source identity differs from exact matrix bytes")
    if not callable(read_exact):
        _fail("draw source requires an exact-generation reader")
    try:
        reopened = read_exact(identity)
    except Exception as exc:
        raise CorpusR6IndependentBankContractV1Error(
            "draw source exact-generation reopen failed"
        ) from exc
    if type(reopened) is not bytes or reopened != expected:
        _fail("draw source exact-generation reopened bytes differ")
    return identity


def _candidate_rows_v1(
    lineup_ids: object, roster_by_lineup_id: object
) -> tuple[list[str], list[dict[str, object]]]:
    ids = [
        _string(value, label="candidate lineup id")
        for value in _sequence(lineup_ids, label="candidate lineup ids")
    ]
    if len(ids) < ENTRY_BUDGET or ids != sorted(set(ids)):
        _fail("candidate lineup ids must be sorted, unique, and support exact-80")
    roster_map = _mapping(roster_by_lineup_id, label="candidate roster map")
    if set(roster_map) != set(ids):
        _fail("candidate roster map does not exactly cover candidate ids")
    rows: list[dict[str, object]] = []
    seen: set[tuple[str, ...]] = set()
    for lineup_id in ids:
        roster = tuple(
            _string(value, label=f"candidate roster {lineup_id} player")
            for value in _sequence(
                roster_map[lineup_id], label=f"candidate roster {lineup_id}"
            )
        )
        if (
            len(roster) != rw.ROSTER_SIZE
            or len(set(roster)) != rw.ROSTER_SIZE
            or roster != tuple(sorted(roster))
            or roster in seen
        ):
            _fail("candidate rosters must be distinct canonical nine-player ids")
        seen.add(roster)
        rows.append({
            "lineup_id": lineup_id,
            "roster_player_ids": list(roster),
        })
    return ids, rows


def build_candidate_authority_v1(
    *,
    candidate_authority_id: str,
    candidate_lineup_ids: Sequence[str],
    roster_by_lineup_id: Mapping[str, Sequence[object]],
) -> dict[str, object]:
    """Materialize the complete candidate universe; hashes are derived only."""
    ids, rows = _candidate_rows_v1(candidate_lineup_ids, roster_by_lineup_id)
    body = {
        "schema_version": CANDIDATE_AUTHORITY_SCHEMA,
        "candidate_authority_id": _string(
            candidate_authority_id, label="candidate authority id"
        ),
        "candidate_lineup_count": len(ids),
        "candidate_lineup_ids": ids,
        "candidate_lineup_ids_sha256": canonical_sha256_v1(ids),
        "candidate_rosters": rows,
        "candidate_rosters_sha256": canonical_sha256_v1(rows),
        "evidence_tier": "outcome-free-candidate-universe-only",
    }
    assert_outcome_free_v1(body, label="candidate authority")
    return add_self_hash_v1(body, field="candidate_authority_sha256")


def validate_candidate_authority_v1(value: object) -> dict[str, object]:
    authority = _mapping(value, label="candidate authority")
    _keys(authority, {
        "schema_version",
        "candidate_authority_id",
        "candidate_lineup_count",
        "candidate_lineup_ids",
        "candidate_lineup_ids_sha256",
        "candidate_rosters",
        "candidate_rosters_sha256",
        "evidence_tier",
        "candidate_authority_sha256",
    }, label="candidate authority")
    assert_outcome_free_v1(authority, label="candidate authority")
    validate_self_hash_v1(
        authority, field="candidate_authority_sha256", label="candidate authority"
    )
    roster_rows = [
        _mapping(row, label="candidate roster row")
        for row in _sequence(
            authority["candidate_rosters"], label="candidate rosters"
        )
    ]
    roster_map: dict[str, Sequence[object]] = {}
    for row in roster_rows:
        _keys(
            row, {"lineup_id", "roster_player_ids"}, label="candidate roster row"
        )
        lineup_id = _string(row["lineup_id"], label="candidate roster lineup id")
        if lineup_id in roster_map:
            _fail("candidate roster lineup ids repeat")
        roster_map[lineup_id] = _sequence(
            row["roster_player_ids"], label="candidate roster player ids"
        )
    ids, rebuilt_rows = _candidate_rows_v1(
        authority["candidate_lineup_ids"], roster_map
    )
    if (
        authority["schema_version"] != CANDIDATE_AUTHORITY_SCHEMA
        or authority["evidence_tier"] != "outcome-free-candidate-universe-only"
        or authority["candidate_lineup_count"] != len(ids)
        or authority["candidate_lineup_ids_sha256"] != canonical_sha256_v1(ids)
        or roster_rows != rebuilt_rows
        or authority["candidate_rosters_sha256"]
        != canonical_sha256_v1(rebuilt_rows)
    ):
        _fail("candidate authority derived fields differ")
    _string(authority["candidate_authority_id"], label="candidate authority id")
    return authority


def build_law_release_v1(
    *, law_id: str, law_definition: Mapping[str, object]
) -> dict[str, object]:
    definition = _mapping(law_definition, label="law definition")
    assert_outcome_free_v1(definition, label="law definition")
    body = {
        "schema_version": LAW_RELEASE_SCHEMA,
        "law_id": _string(law_id, label="law id"),
        "law_definition": definition,
        "law_sha256": canonical_sha256_v1(definition),
        "evidence_tier": "outcome-free-simulation-law-only",
    }
    return add_self_hash_v1(body, field="law_release_sha256")


def validate_law_release_v1(value: object) -> dict[str, object]:
    release = _mapping(value, label="law release")
    _keys(release, {
        "schema_version", "law_id", "law_definition", "law_sha256",
        "evidence_tier", "law_release_sha256",
    }, label="law release")
    assert_outcome_free_v1(release, label="law release")
    validate_self_hash_v1(release, field="law_release_sha256", label="law release")
    definition = _mapping(release["law_definition"], label="law definition")
    if (
        release["schema_version"] != LAW_RELEASE_SCHEMA
        or release["law_sha256"] != canonical_sha256_v1(definition)
        or release["evidence_tier"] != "outcome-free-simulation-law-only"
    ):
        _fail("law release derived fields differ")
    _string(release["law_id"], label="law id")
    return release


def build_code_release_v1(
    *,
    source_commit_sha: str,
    module_source_identities_by_path: Mapping[str, Mapping[str, object]],
    read_exact: ReadExact,
) -> dict[str, object]:
    """Bind code identities to independently reopened immutable module bytes."""
    commit = _string(source_commit_sha, label="source commit sha")
    if len(commit) != 40 or any(value not in "0123456789abcdef" for value in commit):
        _fail("source commit sha must be lowercase 40-hex")
    if (
        not isinstance(module_source_identities_by_path, Mapping)
        or not module_source_identities_by_path
    ):
        _fail("code release module sources must be a nonempty mapping")
    modules: list[dict[str, object]] = []
    for path in sorted(module_source_identities_by_path):
        if type(path) is not str or not path:
            _fail("code release module paths must be nonempty strings")
        raw, source_identity = reopen_bytes_identity_v1(
            module_source_identities_by_path[path],
            read_exact=read_exact,
            label=f"code release module {path}",
        )
        if not raw:
            _fail("code release module bytes cannot be empty")
        modules.append({
            "code_identity": {
                "source_commit_sha": commit,
                "module_path": path,
                "module_sha256": sha256(raw).hexdigest(),
            },
            "module_source_identity": source_identity,
        })
    required = {CONTRACT_MODULE_PATH, SELECTOR_AUDIT_MODULE_PATH}
    if not required.issubset({row["code_identity"]["module_path"] for row in modules}):
        _fail("code release omits a Lane 4 contract module")
    body = {
        "schema_version": CODE_RELEASE_SCHEMA,
        "source_commit_sha": commit,
        "modules": modules,
        "module_manifest_sha256": canonical_sha256_v1(modules),
    }
    return add_self_hash_v1(body, field="code_release_sha256")


def validate_code_release_v1(
    value: object, *, read_exact: ReadExact
) -> dict[str, object]:
    release = _mapping(value, label="code release")
    _keys(release, {
        "schema_version", "source_commit_sha", "modules",
        "module_manifest_sha256", "code_release_sha256",
    }, label="code release")
    validate_self_hash_v1(release, field="code_release_sha256", label="code release")
    commit = _string(release["source_commit_sha"], label="source commit sha")
    if len(commit) != 40 or any(value not in "0123456789abcdef" for value in commit):
        _fail("source commit sha must be lowercase 40-hex")
    modules: list[dict[str, object]] = []
    for index, raw_row in enumerate(
        _sequence(release["modules"], label="code release modules")
    ):
        row = _mapping(raw_row, label=f"code release module[{index}]")
        _keys(
            row,
            {"code_identity", "module_source_identity"},
            label=f"code release module[{index}]",
        )
        code_identity = normalize_code_identity_v1(
            row["code_identity"], label=f"code release module[{index}] code"
        )
        module_bytes, source_identity = reopen_bytes_identity_v1(
            row["module_source_identity"],
            read_exact=read_exact,
            label=f"code release module[{index}] source",
        )
        if (
            not module_bytes
            or sha256(module_bytes).hexdigest() != code_identity["module_sha256"]
        ):
            _fail("code release module source differs from its code identity")
        modules.append({
            "code_identity": code_identity,
            "module_source_identity": source_identity,
        })
    paths = [row["code_identity"]["module_path"] for row in modules]
    if (
        release["schema_version"] != CODE_RELEASE_SCHEMA
        or not modules
        or paths != sorted(set(paths))
        or any(
            row["code_identity"]["source_commit_sha"] != commit
            for row in modules
        )
        or release["module_manifest_sha256"] != canonical_sha256_v1(modules)
        or not {CONTRACT_MODULE_PATH, SELECTOR_AUDIT_MODULE_PATH}.issubset(set(paths))
    ):
        _fail("code release module manifest differs")
    return release


def control_strategy_definitions_v1() -> tuple[dict[str, object], ...]:
    """Return the frozen dispatcher inputs after checking literal identities."""
    strategies = tuple(dict(value) for value in frozen_full_union_strategies_v1())
    observed = tuple(
        (
            strategy.get("ordinal"),
            strategy.get("strategy_id"),
            strategy.get("strategy_sha256"),
        )
        for strategy in strategies
    )
    if observed != EXACT_CONTROL_IDENTITIES:
        _fail("frozen exact-eight control registry differs")
    for strategy in strategies:
        if strategy.get("entry_budget") != ENTRY_BUDGET:
            _fail("frozen control entry budget differs")
        validate_self_hash_v1(
            strategy, field="strategy_sha256", label="frozen control strategy"
        )
    return strategies


def exact_control_registry_v1() -> list[dict[str, object]]:
    definitions = control_strategy_definitions_v1()
    registry = [
        {
            "ordinal": ordinal,
            "strategy_id": strategy_id,
            "strategy_sha256": strategy_sha256,
            "executable_fingerprint_sha256": strategy_executable_fingerprint_v1(
                definitions[ordinal]
            ),
            "entry_budget": ENTRY_BUDGET,
            "fit_scope_id": FINAL_FIT_SCOPE_ID,
        }
        for ordinal, strategy_id, strategy_sha256 in EXACT_CONTROL_IDENTITIES
    ]
    fingerprints = [
        str(row["executable_fingerprint_sha256"]) for row in registry
    ]
    if len(fingerprints) != len(set(fingerprints)):
        _fail("exact controls repeat an executable strategy")
    return registry


def validate_exact_control_registry_v1(value: object) -> list[dict[str, object]]:
    controls = _sequence(value, label="control registry")
    expected = exact_control_registry_v1()
    if canonical_json_bytes_v1(controls) != canonical_json_bytes_v1(expected):
        _fail("control registry is not the exact-eight all-block final-fit registry")
    return expected


def _validate_strategy_self_hash(value: object, *, label: str) -> dict[str, object]:
    strategy = _mapping(value, label=label)
    required = {
        "schema_version",
        "ordinal",
        "strategy_id",
        "method",
        "entry_budget",
        "parameters",
        "tie_law",
        "selection_inputs",
        "description",
        "strategy_sha256",
    }
    _keys(strategy, required, label=label)
    assert_outcome_free_v1(strategy, label=label)
    validate_self_hash_v1(strategy, field="strategy_sha256", label=label)
    if strategy["entry_budget"] != ENTRY_BUDGET:
        _fail(f"{label} must use exact-80")
    if strategy["selection_inputs"] != "discovery-block-simulated-scores-only":
        _fail(f"{label} selection input differs")
    if strategy["method"] not in _SUPPORTED_METHODS:
        _fail(f"{label} method is not implemented by the frozen dispatcher")
    expected_schema = control_strategy_definitions_v1()[0]["schema_version"]
    if strategy["schema_version"] != expected_schema:
        _fail(f"{label} schema differs from the frozen dispatcher")
    parameters = _mapping(strategy["parameters"], label=f"{label} parameters")
    method = str(strategy["method"])
    if method == "greedy-threshold-coverage-v1":
        _keys(parameters, {"threshold", "operator"}, label=f"{label} parameters")
        _finite_float(parameters["threshold"], label=f"{label} threshold")
        if parameters["operator"] not in {">", ">="}:
            _fail(f"{label} threshold operator differs")
    elif method in {"rank-mean-score-v1", "greedy-expected-max-v1"}:
        _keys(parameters, set(), label=f"{label} parameters")
    else:
        expected_parameter_keys = {"rungs"}
        if method == "greedy-block-supported-ladder-v1":
            expected_parameter_keys.add("support_scaling")
        _keys(parameters, expected_parameter_keys, label=f"{label} parameters")
        if (
            method == "greedy-block-supported-ladder-v1"
            and parameters["support_scaling"] != "distinct-discovery-block-count"
        ):
            _fail(f"{label} support scaling differs")
        rungs = _sequence(parameters["rungs"], label=f"{label} rungs")
        if not rungs:
            _fail(f"{label} rungs cannot be empty")
        for index, raw_rung in enumerate(rungs):
            rung = _mapping(raw_rung, label=f"{label} rung[{index}]")
            _keys(
                rung,
                {"threshold", "operator", "weight"},
                label=f"{label} rung[{index}]",
            )
            _finite_float(rung["threshold"], label=f"{label} rung threshold")
            if rung["operator"] not in {">", ">="}:
                _fail(f"{label} rung operator differs")
            if _integer(rung["weight"], label=f"{label} rung weight", minimum=1) < 1:
                _fail(f"{label} rung weight differs")
    tie_law = [
        _string(item, label=f"{label} tie law item")
        for item in _sequence(strategy["tie_law"], label=f"{label} tie law")
    ]
    if not tie_law or len(tie_law) != len(set(tie_law)):
        _fail(f"{label} tie law must be nonempty and unique")
    return strategy


def strategy_executable_fingerprint_v1(value: object) -> str:
    """Hash only dispatcher-observable strategy semantics."""
    strategy = _validate_strategy_self_hash(value, label="strategy fingerprint")
    return canonical_sha256_v1({
        "schema_version": strategy["schema_version"],
        "method": strategy["method"],
        "entry_budget": strategy["entry_budget"],
        "parameters": strategy["parameters"],
        "tie_law": strategy["tie_law"],
        "selection_inputs": strategy["selection_inputs"],
    })


def validate_challenger_registry_v1(value: object) -> list[dict[str, object]]:
    rows = _sequence(value, label="challenger registry")
    if len(rows) > CHALLENGER_CAP:
        _fail(f"challenger registry exceeds cap {CHALLENGER_CAP}")
    normalized: list[dict[str, object]] = []
    control_ids = {strategy_id for _, strategy_id, _ in EXACT_CONTROL_IDENTITIES}
    control_hashes = {digest for _, _, digest in EXACT_CONTROL_IDENTITIES}
    executable_fingerprints = {
        strategy_executable_fingerprint_v1(strategy)
        for strategy in control_strategy_definitions_v1()
    }
    for index, raw in enumerate(rows):
        row = _mapping(raw, label=f"challenger[{index}]")
        _keys(
            row,
            {
                "challenger_id",
                "fit_scope_id",
                "strategy",
                "executable_fingerprint_sha256",
            },
            label=f"challenger[{index}]",
        )
        if row["fit_scope_id"] != FINAL_FIT_SCOPE_ID:
            _fail(f"challenger[{index}] is not an all-block final-fit book")
        strategy = _validate_strategy_self_hash(
            row["strategy"], label=f"challenger[{index}] strategy"
        )
        challenger_id = _string(row["challenger_id"], label="challenger id")
        if (
            strategy["ordinal"] != CONTROL_COUNT + index
            or strategy["strategy_id"] != challenger_id
        ):
            _fail("challenger order/id differs")
        if challenger_id in control_ids or strategy["strategy_sha256"] in control_hashes:
            _fail("challenger collides with an exact control")
        fingerprint = strategy_executable_fingerprint_v1(strategy)
        if row["executable_fingerprint_sha256"] != fingerprint:
            _fail("challenger executable fingerprint differs")
        if fingerprint in executable_fingerprints:
            _fail("challenger duplicates an existing executable strategy")
        executable_fingerprints.add(fingerprint)
        normalized.append({
            "challenger_id": challenger_id,
            "fit_scope_id": FINAL_FIT_SCOPE_ID,
            "strategy": strategy,
            "executable_fingerprint_sha256": fingerprint,
        })
    ids = [str(row["challenger_id"]) for row in normalized]
    hashes = [str(row["strategy"]["strategy_sha256"]) for row in normalized]
    if len(ids) != len(set(ids)) or len(hashes) != len(set(hashes)):
        _fail("challenger identities repeat")
    return normalized


def _normalize_rng_streams_v1(
    value: object, *, role: str, world_count: int
) -> list[dict[str, object]]:
    streams: list[dict[str, object]] = []
    for index, raw_stream in enumerate(_sequence(value, label="rng streams")):
        stream = _mapping(raw_stream, label=f"rng stream[{index}]")
        _keys(
            stream,
            {
                "stream_id",
                "generator_id",
                "seed",
                "substream_start",
                "substream_stop",
                "role_domain",
            },
            label=f"rng stream[{index}]",
        )
        if stream["role_domain"] != role:
            _fail("rng stream role domain differs from bank member role")
        start = _integer(stream["substream_start"], label="rng substream start")
        stop = _integer(stream["substream_stop"], label="rng substream stop")
        if stop <= start or stop - start != world_count:
            _fail("rng substream range must exactly cover the member worlds")
        streams.append({
            "stream_id": _string(stream["stream_id"], label="rng stream id"),
            "generator_id": _string(
                stream["generator_id"], label="rng generator id"
            ),
            "seed": _integer(stream["seed"], label="rng seed"),
            "substream_start": start,
            "substream_stop": stop,
            "role_domain": role,
        })
    ids = [str(row["stream_id"]) for row in streams]
    coordinates = [
        (
            row["generator_id"],
            row["seed"],
            row["substream_start"],
            row["substream_stop"],
        )
        for row in streams
    ]
    if (
        not streams
        or len(ids) != len(set(ids))
        or len(coordinates) != len(set(coordinates))
    ):
        _fail("rng stream ledger is empty or repeats identity/coordinates")
    return streams


def _streams_overlap_v1(
    left: Mapping[str, object], right: Mapping[str, object]
) -> bool:
    return bool(
        left["generator_id"] == right["generator_id"]
        and left["seed"] == right["seed"]
        and int(left["substream_start"]) < int(right["substream_stop"])
        and int(right["substream_start"]) < int(left["substream_stop"])
    )


def bind_draw_bank_member_v1(
    *,
    member_id: str,
    slate_id: str,
    law_id: str,
    law_sha256: str,
    replicate: int,
    role: str,
    block_ordinal: int,
    rng_streams: Sequence[Mapping[str, object]],
    source_identity: Mapping[str, object],
    precursor_design_identity: Mapping[str, object],
    generation_code_identity: Mapping[str, object],
    players: Sequence[rw.PlayerSpec],
    player_draws: np.ndarray,
    read_exact: ReadExact,
) -> dict[str, object]:
    """Bind one immutable draw matrix without embedding its numerical values."""
    if role not in {"selection", "audit"}:
        _fail("draw-bank role must be selection or audit")
    rows = tuple(players)
    matrix = np.asarray(player_draws)
    if matrix.shape[0] != len(rows):
        _fail("player draw rows differ from player order")
    if matrix.ndim != 2 or matrix.shape[1] < 1:
        _fail("player draws must be a nonempty matrix")
    streams = _normalize_rng_streams_v1(
        rng_streams, role=role, world_count=int(matrix.shape[1])
    )
    design_raw, design_identity = reopen_json_identity_v1(
        precursor_design_identity,
        read_exact=read_exact,
        label="precursor design",
    )
    design = validate_precursor_design_v1(design_raw, read_exact=read_exact)
    body = {
        "schema_version": DRAW_BANK_MEMBER_SCHEMA,
        "member_id": _string(member_id, label="member id"),
        "slate_id": _string(slate_id, label="slate id"),
        "law_id": _string(law_id, label="law id"),
        "law_sha256": _sha256(law_sha256, label="law sha256"),
        "replicate": _integer(replicate, label="replicate"),
        "role": role,
        "block_ordinal": _integer(block_ordinal, label="block ordinal"),
        "rng_streams": streams,
        "precursor_design_identity": design_identity,
        "precursor_design_sha256": design["precursor_design_sha256"],
        "source_identity": reopen_draw_source_v1(
            source_identity=source_identity,
            players=rows,
            player_draws=matrix,
            precursor_design_identity=design_identity,
            precursor_design_sha256=design["precursor_design_sha256"],
            read_exact=read_exact,
        ),
        "generation_code_identity": normalize_code_identity_v1(
            generation_code_identity, label="draw generation code"
        ),
        "player_ids_sha256": player_ids_sha256_v1(rows),
        "player_catalog_sha256": player_catalog_sha256_v1(rows),
        "player_draws": {
            "dtype": "float32-le",
            "shape": [int(matrix.shape[0]), int(matrix.shape[1])],
            "sha256": float32_matrix_sha256_v1(matrix),
        },
    }
    assert_outcome_free_v1(body, label="draw bank member")
    return add_self_hash_v1(body, field="draw_bank_member_sha256")


def validate_draw_bank_member_v1(
    value: object,
    *,
    expected_role: str | None = None,
    players: Sequence[rw.PlayerSpec] | None = None,
    player_draws: np.ndarray | None = None,
) -> dict[str, object]:
    member = _mapping(value, label="draw bank member")
    _keys(member, {
        "schema_version",
        "member_id",
        "slate_id",
        "law_id",
        "law_sha256",
        "replicate",
        "role",
        "block_ordinal",
        "rng_streams",
        "precursor_design_identity",
        "precursor_design_sha256",
        "source_identity",
        "generation_code_identity",
        "player_ids_sha256",
        "player_catalog_sha256",
        "player_draws",
        "draw_bank_member_sha256",
    }, label="draw bank member")
    assert_outcome_free_v1(member, label="draw bank member")
    if member["schema_version"] != DRAW_BANK_MEMBER_SCHEMA:
        _fail("draw bank member schema differs")
    validate_self_hash_v1(
        member, field="draw_bank_member_sha256", label="draw bank member"
    )
    _string(member["member_id"], label="member id")
    _string(member["slate_id"], label="slate id")
    _string(member["law_id"], label="law id")
    _sha256(member["law_sha256"], label="law sha256")
    _integer(member["replicate"], label="replicate")
    _integer(member["block_ordinal"], label="block ordinal")
    role = member["role"]
    if role not in {"selection", "audit"}:
        _fail("draw bank member role differs")
    if expected_role is not None and role != expected_role:
        _fail(f"draw bank member is not a {expected_role} member")
    normalized_source = _normalized_content_identity(
        member["source_identity"], label="draw source"
    )
    normalized_design = _normalized_content_identity(
        member["precursor_design_identity"], label="precursor design"
    )
    if normalized_source != member["source_identity"]:
        _fail("draw source contains representation-dependent fields")
    if normalized_design != member["precursor_design_identity"]:
        _fail("precursor design contains representation-dependent fields")
    _sha256(
        member["precursor_design_sha256"], label="precursor design sha256"
    )
    _sha256(member["player_ids_sha256"], label="player ids sha256")
    _sha256(member["player_catalog_sha256"], label="player catalog sha256")
    descriptor = _mapping(member["player_draws"], label="player draws")
    _keys(descriptor, {"dtype", "shape", "sha256"}, label="player draws")
    if descriptor["dtype"] != "float32-le":
        _fail("player draws dtype differs")
    shape = _sequence(descriptor["shape"], label="player draw shape")
    if len(shape) != 2:
        _fail("player draw shape differs")
    row_count = _integer(shape[0], label="player draw rows", minimum=1)
    world_count = _integer(shape[1], label="player draw worlds", minimum=1)
    _sha256(descriptor["sha256"], label="player draws sha256")
    streams = _normalize_rng_streams_v1(
        member["rng_streams"], role=role, world_count=world_count
    )
    if streams != member["rng_streams"]:
        _fail("rng stream ledger is not canonical")
    generation_code = normalize_code_identity_v1(
        member["generation_code_identity"], label="draw generation code"
    )
    if generation_code != member["generation_code_identity"]:
        _fail("draw generation code identity is not canonical")
    if (players is None) != (player_draws is None):
        _fail("player catalog and draws must be validated together")
    if players is not None and player_draws is not None:
        rows = tuple(players)
        matrix = np.asarray(player_draws)
        if matrix.shape != (row_count, world_count) or len(rows) != row_count:
            _fail("bound player draw shape differs")
        if member["player_ids_sha256"] != player_ids_sha256_v1(rows):
            _fail("bound player order differs")
        if member["player_catalog_sha256"] != player_catalog_sha256_v1(rows):
            _fail("bound player catalog differs")
        if descriptor["sha256"] != float32_matrix_sha256_v1(matrix):
            _fail("bound player draws differ")
    return member


def _validate_law_bijection_v1(
    members: Sequence[Mapping[str, object]], *, label: str
) -> None:
    id_to_sha: dict[str, str] = {}
    sha_to_id: dict[str, str] = {}
    for member in members:
        law_id = str(member["law_id"])
        law_sha = str(member["law_sha256"])
        if (
            id_to_sha.setdefault(law_id, law_sha) != law_sha
            or sha_to_id.setdefault(law_sha, law_id) != law_id
        ):
            _fail(f"{label} law id/hash mapping is not bijective")


def _assert_member_authorities_unique_v1(
    members: Sequence[Mapping[str, object]], *, label: str
) -> None:
    member_ids = [str(member["member_id"]) for member in members]
    draw_hashes = [str(member["player_draws"]["sha256"]) for member in members]
    sources = [content_identity(member["source_identity"]) for member in members]
    if (
        len(member_ids) != len(set(member_ids))
        or len(draw_hashes) != len(set(draw_hashes))
        or len(sources) != len(set(sources))
    ):
        _fail(f"{label} repeats a member, draw matrix, or source authority")
    stream_rows = [
        (member, stream)
        for member in members
        for stream in member["rng_streams"]
    ]
    for left_index, (_left_member, left_stream) in enumerate(stream_rows):
        for _right_member, right_stream in stream_rows[left_index + 1:]:
            if _streams_overlap_v1(left_stream, right_stream):
                _fail(f"{label} reuses an overlapping RNG substream")


def build_draw_bank_root_v1(
    *, bank_id: str, role: str, members: Sequence[Mapping[str, object]]
) -> dict[str, object]:
    normalized = [
        validate_draw_bank_member_v1(member, expected_role=role)
        for member in _sequence(members, label="draw bank members")
    ]
    if not normalized:
        _fail("draw bank root cannot be empty")
    _validate_law_bijection_v1(normalized, label="draw bank root")
    _assert_member_authorities_unique_v1(normalized, label="draw bank root")
    hashes = [str(member["draw_bank_member_sha256"]) for member in normalized]
    coordinates = [
        (
            member["slate_id"],
            member["law_id"],
            member["law_sha256"],
            member["replicate"],
            member["block_ordinal"],
        )
        for member in normalized
    ]
    if len(hashes) != len(set(hashes)) or len(coordinates) != len(set(coordinates)):
        _fail("draw bank member identity or coordinate repeats")
    body = {
        "schema_version": DRAW_BANK_ROOT_SCHEMA,
        "bank_id": _string(bank_id, label="bank id"),
        "role": role,
        "member_count": len(normalized),
        "ordered_member_sha256s": hashes,
        "members": normalized,
    }
    assert_outcome_free_v1(body, label="draw bank root")
    return add_self_hash_v1(body, field="draw_bank_root_sha256")


def validate_draw_bank_root_v1(
    value: object, *, expected_role: str | None = None
) -> dict[str, object]:
    root = _mapping(value, label="draw bank root")
    _keys(root, {
        "schema_version",
        "bank_id",
        "role",
        "member_count",
        "ordered_member_sha256s",
        "members",
        "draw_bank_root_sha256",
    }, label="draw bank root")
    assert_outcome_free_v1(root, label="draw bank root")
    if root["schema_version"] != DRAW_BANK_ROOT_SCHEMA:
        _fail("draw bank root schema differs")
    validate_self_hash_v1(root, field="draw_bank_root_sha256", label="draw bank root")
    role = root["role"]
    if role not in {"selection", "audit"}:
        _fail("draw bank root role differs")
    if expected_role is not None and role != expected_role:
        _fail(f"draw bank root is not a {expected_role} root")
    members = [
        validate_draw_bank_member_v1(member, expected_role=role)
        for member in _sequence(root["members"], label="draw bank members")
    ]
    _validate_law_bijection_v1(members, label="draw bank root")
    _assert_member_authorities_unique_v1(members, label="draw bank root")
    hashes = [str(member["draw_bank_member_sha256"]) for member in members]
    if (
        root["member_count"] != len(members)
        or root["ordered_member_sha256s"] != hashes
        or not members
        or len(hashes) != len(set(hashes))
    ):
        _fail("draw bank root ledger differs")
    coordinates = [
        (
            member["slate_id"],
            member["law_id"],
            member["law_sha256"],
            member["replicate"],
            member["block_ordinal"],
        )
        for member in members
    ]
    if len(coordinates) != len(set(coordinates)):
        _fail("draw bank member coordinate repeats")
    return root


def assert_selection_audit_disjoint_members_v1(
    selection_member: object, audit_member: object
) -> None:
    selection = validate_draw_bank_member_v1(selection_member, expected_role="selection")
    audit = validate_draw_bank_member_v1(audit_member, expected_role="audit")
    if selection["slate_id"] != audit["slate_id"]:
        _fail("selection and audit members refer to different slates")
    if selection["law_id"] != audit["law_id"]:
        _fail("selection and audit members refer to different laws")
    if selection["law_sha256"] != audit["law_sha256"]:
        _fail("selection and audit members bind different law bodies")
    if selection["player_catalog_sha256"] != audit["player_catalog_sha256"]:
        _fail("selection and audit player catalogs differ")
    if selection["player_ids_sha256"] != audit["player_ids_sha256"]:
        _fail("selection and audit player order differs")
    same_source = content_identity(selection["source_identity"]) == content_identity(
        audit["source_identity"]
    )
    if (
        selection["draw_bank_member_sha256"] == audit["draw_bank_member_sha256"]
        or selection["player_draws"]["sha256"] == audit["player_draws"]["sha256"]
        or same_source
        or any(
            _streams_overlap_v1(left, right)
            for left in selection["rng_streams"]
            for right in audit["rng_streams"]
        )
    ):
        _fail("selection and audit draw authority is not disjoint")


def assert_selection_audit_disjoint_roots_v1(
    selection_root: object, audit_root: object
) -> None:
    selection = validate_draw_bank_root_v1(selection_root, expected_role="selection")
    audit = validate_draw_bank_root_v1(audit_root, expected_role="audit")
    combined_members = [*selection["members"], *audit["members"]]
    _validate_law_bijection_v1(
        combined_members, label="selection/audit bank roots"
    )
    combined_member_ids = [str(member["member_id"]) for member in combined_members]
    if len(combined_member_ids) != len(set(combined_member_ids)):
        _fail("selection and audit roots repeat a member id")
    for selection_member in selection["members"]:
        for audit_member in audit["members"]:
            if (
                selection_member["player_draws"]["sha256"]
                == audit_member["player_draws"]["sha256"]
                or content_identity(selection_member["source_identity"])
                == content_identity(audit_member["source_identity"])
                or any(
                    _streams_overlap_v1(left, right)
                    for left in selection_member["rng_streams"]
                    for right in audit_member["rng_streams"]
                )
            ):
                _fail("selection and audit roots reuse draw authority")
            if (
                selection_member["slate_id"] == audit_member["slate_id"]
                and selection_member["law_id"] == audit_member["law_id"]
                and selection_member["law_sha256"]
                == audit_member["law_sha256"]
            ):
                assert_selection_audit_disjoint_members_v1(
                    selection_member, audit_member
                )


def _normalize_member_designs_v1(
    value: object,
    *,
    role: str,
    law_release: Mapping[str, object],
    code_release: Mapping[str, object],
) -> list[dict[str, object]]:
    allowed_code = {
        canonical_json_bytes_v1(row["code_identity"])
        for row in code_release["modules"]
    }
    normalized: list[dict[str, object]] = []
    for index, raw in enumerate(_sequence(value, label=f"{role} member designs")):
        row = _mapping(raw, label=f"{role} member design[{index}]")
        input_fields = {
            "member_id", "slate_id", "replicate", "role", "block_ordinal",
            "world_count", "rng_streams", "generation_code_identity",
        }
        normalized_fields = {*input_fields, "law_id", "law_sha256"}
        if set(row) == normalized_fields:
            if (
                row["law_id"] != law_release["law_id"]
                or row["law_sha256"] != law_release["law_sha256"]
            ):
                _fail(f"{role} member design law differs from its release")
        elif set(row) != input_fields:
            _fail(f"{role} member design[{index}] fields differ")
        if row["role"] != role:
            _fail(f"{role} member design role differs")
        world_count = _integer(
            row["world_count"], label=f"{role} member world count", minimum=1
        )
        code = normalize_code_identity_v1(
            row["generation_code_identity"], label=f"{role} generation code"
        )
        if canonical_json_bytes_v1(code) not in allowed_code:
            _fail(f"{role} generation code is absent from the code release")
        normalized.append({
            "member_id": _string(row["member_id"], label=f"{role} member id"),
            "slate_id": _string(row["slate_id"], label=f"{role} slate id"),
            "law_id": law_release["law_id"],
            "law_sha256": law_release["law_sha256"],
            "replicate": _integer(row["replicate"], label=f"{role} replicate"),
            "role": role,
            "block_ordinal": _integer(
                row["block_ordinal"], label=f"{role} block ordinal"
            ),
            "world_count": world_count,
            "rng_streams": _normalize_rng_streams_v1(
                row["rng_streams"], role=role, world_count=world_count
            ),
            "generation_code_identity": code,
        })
    if not normalized:
        _fail(f"{role} member design grid cannot be empty")
    member_ids = [str(row["member_id"]) for row in normalized]
    coordinates = [
        (
            row["slate_id"], row["law_id"], row["replicate"],
            row["block_ordinal"],
        )
        for row in normalized
    ]
    if (
        len(member_ids) != len(set(member_ids))
        or len(coordinates) != len(set(coordinates))
    ):
        _fail(f"{role} member design ids or coordinates repeat")
    stream_rows = [
        stream for row in normalized for stream in row["rng_streams"]
    ]
    for left_index, left in enumerate(stream_rows):
        for right in stream_rows[left_index + 1:]:
            if _streams_overlap_v1(left, right):
                _fail(f"{role} member designs overlap an RNG substream")
    return normalized


def build_precursor_design_v1(
    *,
    design_id: str,
    candidate_authority_identity: Mapping[str, object],
    law_release_identity: Mapping[str, object],
    code_release_identity: Mapping[str, object],
    selection_member_designs: Sequence[Mapping[str, object]],
    audit_member_designs: Sequence[Mapping[str, object]],
    designated_selection_member_id: str,
    challengers: Sequence[Mapping[str, object]],
    primary_control_id: str,
    primary_strategy_id: str,
    primary_metric_id: str,
    read_exact: ReadExact,
) -> dict[str, object]:
    """Freeze the complete experiment design before any bank matrix exists."""
    candidate_raw, candidate_identity = reopen_json_identity_v1(
        candidate_authority_identity,
        read_exact=read_exact,
        label="candidate authority",
    )
    candidate = validate_candidate_authority_v1(candidate_raw)
    law_raw, law_identity = reopen_json_identity_v1(
        law_release_identity, read_exact=read_exact, label="law release"
    )
    law = validate_law_release_v1(law_raw)
    code_raw, code_identity = reopen_json_identity_v1(
        code_release_identity, read_exact=read_exact, label="code release"
    )
    code = validate_code_release_v1(code_raw, read_exact=read_exact)
    selection = _normalize_member_designs_v1(
        selection_member_designs,
        role="selection",
        law_release=law,
        code_release=code,
    )
    audit = _normalize_member_designs_v1(
        audit_member_designs,
        role="audit",
        law_release=law,
        code_release=code,
    )
    combined_streams = [
        (row["role"], stream)
        for row in [*selection, *audit]
        for stream in row["rng_streams"]
    ]
    for left_index, (_left_role, left) in enumerate(combined_streams):
        for _right_role, right in combined_streams[left_index + 1:]:
            if _streams_overlap_v1(left, right):
                _fail("selection/audit design reuses an RNG substream")
    designated = _string(
        designated_selection_member_id, label="designated selection member id"
    )
    if [row["member_id"] for row in selection].count(designated) != 1:
        _fail("designated selection member is not exact in the selection grid")
    normalized_challengers = validate_challenger_registry_v1(challengers)
    control_ids = [row[1] for row in EXACT_CONTROL_IDENTITIES]
    all_strategy_ids = [
        *control_ids,
        *[str(row["challenger_id"]) for row in normalized_challengers],
    ]
    if primary_control_id not in control_ids:
        _fail("primary control is not one of the exact eight")
    if (
        primary_strategy_id not in all_strategy_ids
        or primary_strategy_id == primary_control_id
    ):
        _fail("primary strategy must be one distinct registered strategy")
    if primary_metric_id not in THRESHOLD_METRICS:
        _fail("primary metric is not a registered threshold metric")
    modules = {
        str(row["code_identity"]["module_path"]): row["code_identity"]
        for row in code["modules"]
    }
    body = {
        "schema_version": PRECURSOR_DESIGN_SCHEMA,
        "design_id": _string(design_id, label="design id"),
        "candidate_authority_identity": candidate_identity,
        "candidate_authority_sha256": candidate["candidate_authority_sha256"],
        "candidate_lineup_count": candidate["candidate_lineup_count"],
        "candidate_lineup_ids_sha256": candidate["candidate_lineup_ids_sha256"],
        "candidate_rosters_sha256": candidate["candidate_rosters_sha256"],
        "law_release_identity": law_identity,
        "law_release_sha256": law["law_release_sha256"],
        "law_id": law["law_id"],
        "law_sha256": law["law_sha256"],
        "code_release_identity": code_identity,
        "code_release_sha256": code["code_release_sha256"],
        "contract_code_identity": modules[CONTRACT_MODULE_PATH],
        "selector_audit_code_identity": modules[SELECTOR_AUDIT_MODULE_PATH],
        "selection_member_designs": selection,
        "audit_member_designs": audit,
        "designated_selection_member_id": designated,
        "control_registry": exact_control_registry_v1(),
        "challengers": normalized_challengers,
        "challenger_registry_sha256": canonical_sha256_v1(normalized_challengers),
        "primary_control_id": primary_control_id,
        "primary_strategy_id": primary_strategy_id,
        "primary_metric_id": primary_metric_id,
        "stopping_law": FIXED_STOPPING_LAW,
        "analysis_mode": "descriptive-fixed-ledger-no-inference-v1",
        "eligibility_class": "descriptive-only-no-promotion-authority",
        "inference_claims_allowed": False,
        "multi_law_enabled": False,
        "design_frozen_before_bank_generation": True,
        "evidence_tier": "outcome-free-ex-ante-simulation-design-only",
    }
    assert_outcome_free_v1(body, label="precursor design")
    return add_self_hash_v1(body, field="precursor_design_sha256")


def validate_precursor_design_v1(
    value: object, *, read_exact: ReadExact
) -> dict[str, object]:
    design = _mapping(value, label="precursor design")
    _keys(design, {
        "schema_version", "design_id", "candidate_authority_identity",
        "candidate_authority_sha256", "candidate_lineup_count",
        "candidate_lineup_ids_sha256", "candidate_rosters_sha256",
        "law_release_identity", "law_release_sha256", "law_id", "law_sha256",
        "code_release_identity", "code_release_sha256", "contract_code_identity",
        "selector_audit_code_identity", "selection_member_designs",
        "audit_member_designs", "designated_selection_member_id",
        "control_registry", "challengers", "challenger_registry_sha256",
        "primary_control_id", "primary_strategy_id", "primary_metric_id",
        "stopping_law", "analysis_mode", "eligibility_class",
        "inference_claims_allowed", "multi_law_enabled",
        "design_frozen_before_bank_generation", "evidence_tier",
        "precursor_design_sha256",
    }, label="precursor design")
    validate_self_hash_v1(
        design, field="precursor_design_sha256", label="precursor design"
    )
    rebuilt = build_precursor_design_v1(
        design_id=_string(design["design_id"], label="design id"),
        candidate_authority_identity=_mapping(
            design["candidate_authority_identity"], label="candidate authority identity"
        ),
        law_release_identity=_mapping(
            design["law_release_identity"], label="law release identity"
        ),
        code_release_identity=_mapping(
            design["code_release_identity"], label="code release identity"
        ),
        selection_member_designs=_sequence(
            design["selection_member_designs"], label="selection member designs"
        ),
        audit_member_designs=_sequence(
            design["audit_member_designs"], label="audit member designs"
        ),
        designated_selection_member_id=_string(
            design["designated_selection_member_id"],
            label="designated selection member id",
        ),
        challengers=_sequence(design["challengers"], label="challengers"),
        primary_control_id=_string(
            design["primary_control_id"], label="primary control id"
        ),
        primary_strategy_id=_string(
            design["primary_strategy_id"], label="primary strategy id"
        ),
        primary_metric_id=_string(
            design["primary_metric_id"], label="primary metric id"
        ),
        read_exact=read_exact,
    )
    if canonical_json_bytes_v1(rebuilt) != canonical_json_bytes_v1(design):
        _fail("precursor design canonical replay differs")
    return design


def build_fixed_precision_rule_v1(
    *,
    primary_metric_id: str,
    ordered_audit_member_sha256s: Sequence[str],
) -> dict[str, object]:
    if primary_metric_id not in THRESHOLD_METRICS:
        _fail("primary metric is not a registered threshold metric")
    threshold, operator = THRESHOLD_METRICS[primary_metric_id]
    ledger = [
        _sha256(value, label="audit member sha256")
        for value in _sequence(
            ordered_audit_member_sha256s, label="audit member ledger"
        )
    ]
    if not ledger or len(ledger) != len(set(ledger)):
        _fail("audit member ledger is empty or repeats an identity")
    body = {
        "schema_version": PRECISION_RULE_SCHEMA,
        "stopping_law": FIXED_STOPPING_LAW,
        "primary_metric": {
            "metric_id": primary_metric_id,
            "threshold": threshold,
            "operator": operator,
        },
        "analysis_mode": "descriptive-fixed-ledger-no-inference-v1",
        "uncertainty_estimator": "not-implemented",
        "family_rule": "not-applied-descriptive-only",
        "eligibility_class": "descriptive-only-no-promotion-authority",
        "inference_claims_allowed": False,
        "ordered_audit_member_sha256s": ledger,
        "fixed_member_count": len(ledger),
    }
    return add_self_hash_v1(body, field="precision_rule_sha256")


def validate_fixed_precision_rule_v1(value: object) -> dict[str, object]:
    rule = _mapping(value, label="precision rule")
    _keys(rule, {
        "schema_version",
        "stopping_law",
        "primary_metric",
        "analysis_mode",
        "uncertainty_estimator",
        "family_rule",
        "eligibility_class",
        "inference_claims_allowed",
        "ordered_audit_member_sha256s",
        "fixed_member_count",
        "precision_rule_sha256",
    }, label="precision rule")
    assert_outcome_free_v1(rule, label="precision rule")
    validate_self_hash_v1(rule, field="precision_rule_sha256", label="precision rule")
    if rule["schema_version"] != PRECISION_RULE_SCHEMA:
        _fail("precision rule schema differs")
    if rule["stopping_law"] != FIXED_STOPPING_LAW:
        _fail("v1 permits only fixed-all-members stopping")
    metric = _mapping(rule["primary_metric"], label="primary metric")
    _keys(metric, {"metric_id", "threshold", "operator"}, label="primary metric")
    metric_id = _string(metric["metric_id"], label="primary metric id")
    if THRESHOLD_METRICS.get(metric_id) != (metric["threshold"], metric["operator"]):
        _fail("primary metric threshold/operator differs")
    if (
        rule["analysis_mode"] != "descriptive-fixed-ledger-no-inference-v1"
        or rule["uncertainty_estimator"] != "not-implemented"
        or rule["family_rule"] != "not-applied-descriptive-only"
        or rule["eligibility_class"]
        != "descriptive-only-no-promotion-authority"
        or rule["inference_claims_allowed"] is not False
    ):
        _fail("descriptive fixed-ledger evidence law differs")
    ledger = [
        _sha256(value, label="audit member sha256")
        for value in _sequence(
            rule["ordered_audit_member_sha256s"], label="audit member ledger"
        )
    ]
    if (
        not ledger
        or len(ledger) != len(set(ledger))
        or rule["fixed_member_count"] != len(ledger)
    ):
        _fail("fixed audit member ledger differs")
    return rule


def build_cross_law_coupling_receipt_v1(
    *,
    left_member: Mapping[str, object],
    right_member: Mapping[str, object],
    latent_map_sha256: str,
) -> dict[str, object]:
    del left_member, right_member, latent_map_sha256
    _fail(
        "cross-law CRN v1 is disabled until exact latent-coordinate bytes "
        "and deterministic derivation replay are implemented"
    )


def validate_crn_pairing_v1(
    left_member: object,
    right_member: object,
    *,
    coupling_receipt: object | None = None,
) -> str:
    """Validate exact within-law CRN or an explicit cross-law latent coupling."""
    left = validate_draw_bank_member_v1(left_member, expected_role="audit")
    right = validate_draw_bank_member_v1(right_member, expected_role="audit")
    if left["slate_id"] != right["slate_id"]:
        _fail("paired audit members refer to different slates")
    same_law_id = left["law_id"] == right["law_id"]
    same_law_sha = left["law_sha256"] == right["law_sha256"]
    if same_law_id != same_law_sha:
        _fail("paired audit members have a non-bijective law identity")
    if same_law_id and same_law_sha:
        if (
            left["draw_bank_member_sha256"] != right["draw_bank_member_sha256"]
            or left["player_draws"]["sha256"] != right["player_draws"]["sha256"]
        ):
            _fail("within-law CRN requires the exact same audit member")
        if coupling_receipt is not None:
            _fail("within-law CRN does not accept a cross-law coupling receipt")
        return "exact-same-audit-member-within-law"
    del coupling_receipt
    _fail(
        "cross-law CRN v1 is disabled until exact latent-coordinate bytes "
        "and deterministic derivation replay are implemented"
    )


def validate_calibrated_law_releases_v1(value: object) -> list[dict[str, object]]:
    releases = _sequence(value, label="calibrated law releases")
    normalized: list[dict[str, object]] = []
    for index, raw in enumerate(releases):
        row = _mapping(raw, label=f"calibrated law release[{index}]")
        _keys(
            row,
            {"law_id", "law_sha256", "calibration_release_identity"},
            label=f"calibrated law release[{index}]",
        )
        normalized.append({
            "law_id": _string(row["law_id"], label="calibrated law id"),
            "law_sha256": _sha256(row["law_sha256"], label="calibrated law sha256"),
            "calibration_release_identity": _normalized_content_identity(
                row["calibration_release_identity"],
                label="calibration release",
            ),
        })
    law_ids = [row["law_id"] for row in normalized]
    law_hashes = [row["law_sha256"] for row in normalized]
    calibration_authorities = [
        content_identity(row["calibration_release_identity"])
        for row in normalized
    ]
    if (
        len(law_ids) != len(set(law_ids))
        or len(law_hashes) != len(set(law_hashes))
        or len(calibration_authorities) != len(set(calibration_authorities))
    ):
        _fail("calibrated law release identities repeat")
    return normalized


def multi_law_weight_derivation_sha256_v1(
    *,
    law_ids: Sequence[str],
    calibration_release_sha256s: Sequence[str],
    weights: Sequence[Mapping[str, object]],
) -> str:
    del law_ids, calibration_release_sha256s, weights
    _fail(
        "multi-law weights are disabled until exact calibration bytes and "
        "a deterministic derivation implementation are available"
    )


def validate_multi_law_shadow_v1(
    value: object | None,
    *,
    calibrated_law_releases: object,
) -> dict[str, object] | None:
    validate_calibrated_law_releases_v1(calibrated_law_releases)
    if value is None:
        return None
    _fail(
        "multi-law shadows are disabled until exact calibration bytes and "
        "a deterministic joint-book implementation are available"
    )


def _generation_code_identity_manifest_v1(
    selection: Mapping[str, object], audit: Mapping[str, object]
) -> list[dict[str, str]]:
    by_path: dict[str, dict[str, str]] = {}
    for member in [*selection["members"], *audit["members"]]:
        identity = normalize_code_identity_v1(
            member["generation_code_identity"], label="generation code identity"
        )
        path = identity["module_path"]
        previous = by_path.setdefault(path, identity)
        if previous != identity:
            _fail("one generation module path binds multiple code identities")
    return [by_path[path] for path in sorted(by_path)]


def _member_matches_design_v1(
    member: Mapping[str, object], design: Mapping[str, object]
) -> bool:
    return bool(
        member["member_id"] == design["member_id"]
        and member["slate_id"] == design["slate_id"]
        and member["law_id"] == design["law_id"]
        and member["law_sha256"] == design["law_sha256"]
        and member["replicate"] == design["replicate"]
        and member["role"] == design["role"]
        and member["block_ordinal"] == design["block_ordinal"]
        and member["player_draws"]["shape"][1] == design["world_count"]
        and member["rng_streams"] == design["rng_streams"]
        and member["generation_code_identity"]
        == design["generation_code_identity"]
    )


def _assert_root_matches_design_v1(
    root: Mapping[str, object],
    designs: Sequence[Mapping[str, object]],
    *,
    role: str,
    precursor_design_identity: Mapping[str, object],
    precursor_design_sha256: str,
) -> None:
    members = root["members"]
    if len(members) != len(designs) or any(
        not _member_matches_design_v1(member, design)
        or member["precursor_design_identity"] != precursor_design_identity
        or member["precursor_design_sha256"] != precursor_design_sha256
        for member, design in zip(members, designs, strict=True)
    ):
        _fail(f"{role} bank root does not bijectively realize the ex-ante grid")


def build_independent_bank_plan_v1(
    *,
    plan_id: str,
    precursor_design: Mapping[str, object],
    precursor_design_identity: Mapping[str, object],
    selection_bank_root: Mapping[str, object],
    audit_bank_root: Mapping[str, object],
    read_exact: ReadExact,
) -> dict[str, object]:
    design = validate_precursor_design_v1(
        precursor_design, read_exact=read_exact
    )
    design_identity = reopen_body_exact_v1(
        design,
        precursor_design_identity,
        read_exact=read_exact,
        label="precursor design",
    )
    selection = validate_draw_bank_root_v1(
        selection_bank_root, expected_role="selection"
    )
    audit = validate_draw_bank_root_v1(audit_bank_root, expected_role="audit")
    assert_selection_audit_disjoint_roots_v1(selection, audit)
    _assert_root_matches_design_v1(
        selection,
        design["selection_member_designs"],
        role="selection",
        precursor_design_identity=design_identity,
        precursor_design_sha256=str(design["precursor_design_sha256"]),
    )
    _assert_root_matches_design_v1(
        audit,
        design["audit_member_designs"],
        role="audit",
        precursor_design_identity=design_identity,
        precursor_design_sha256=str(design["precursor_design_sha256"]),
    )
    designated_id = str(design["designated_selection_member_id"])
    designated = [
        member for member in selection["members"]
        if member["member_id"] == designated_id
    ]
    if len(designated) != 1:
        _fail("designated selection member does not resolve exactly once")
    rule = build_fixed_precision_rule_v1(
        primary_metric_id=str(design["primary_metric_id"]),
        ordered_audit_member_sha256s=audit["ordered_member_sha256s"],
    )
    generation_manifest = _generation_code_identity_manifest_v1(selection, audit)
    body = {
        "schema_version": PLAN_SCHEMA,
        "plan_id": _string(plan_id, label="plan id"),
        "precursor_design_identity": design_identity,
        "precursor_design_sha256": design["precursor_design_sha256"],
        "candidate_authority_identity": design["candidate_authority_identity"],
        "candidate_authority_sha256": design["candidate_authority_sha256"],
        "candidate_lineup_count": design["candidate_lineup_count"],
        "candidate_lineup_ids_sha256": design["candidate_lineup_ids_sha256"],
        "candidate_rosters_sha256": design["candidate_rosters_sha256"],
        "law_release_identity": design["law_release_identity"],
        "law_release_sha256": design["law_release_sha256"],
        "law_id": design["law_id"],
        "law_sha256": design["law_sha256"],
        "code_release_identity": design["code_release_identity"],
        "code_release_sha256": design["code_release_sha256"],
        "fit_scope_id": FINAL_FIT_SCOPE_ID,
        "control_registry": exact_control_registry_v1(),
        "control_count": CONTROL_COUNT,
        "challenger_cap": CHALLENGER_CAP,
        "challengers": design["challengers"],
        "challenger_registry_sha256": design["challenger_registry_sha256"],
        "primary_control_id": design["primary_control_id"],
        "primary_strategy_id": design["primary_strategy_id"],
        "designated_selection_member_id": designated_id,
        "designated_selection_member_sha256": designated[0][
            "draw_bank_member_sha256"
        ],
        "contract_code_identity": design["contract_code_identity"],
        "selector_audit_code_identity": design["selector_audit_code_identity"],
        "generation_code_identities": generation_manifest,
        "generation_code_identity_manifest_sha256": canonical_sha256_v1(
            generation_manifest
        ),
        "selection_bank_root": selection,
        "audit_bank_root": audit,
        "precision_rule": rule,
        "analysis_mode": "descriptive-fixed-ledger-no-inference-v1",
        "eligibility_class": "descriptive-only-no-promotion-authority",
        "inference_claims_allowed": False,
        "multi_law_enabled": False,
        "evidence_tier": "simulated-draw-analysis-only",
    }
    assert_outcome_free_v1(body, label="independent bank plan")
    return add_self_hash_v1(body, field="independent_bank_plan_sha256")


def validate_independent_bank_plan_v1(
    value: object, *, read_exact: ReadExact
) -> dict[str, object]:
    plan = _mapping(value, label="independent bank plan")
    _keys(plan, {
        "schema_version", "plan_id", "precursor_design_identity",
        "precursor_design_sha256", "candidate_authority_identity",
        "candidate_authority_sha256", "candidate_lineup_count",
        "candidate_lineup_ids_sha256", "candidate_rosters_sha256",
        "law_release_identity", "law_release_sha256", "law_id", "law_sha256",
        "code_release_identity", "code_release_sha256", "fit_scope_id",
        "control_registry", "control_count", "challenger_cap", "challengers",
        "challenger_registry_sha256", "primary_control_id",
        "primary_strategy_id", "designated_selection_member_id",
        "designated_selection_member_sha256", "contract_code_identity",
        "selector_audit_code_identity", "generation_code_identities",
        "generation_code_identity_manifest_sha256", "selection_bank_root",
        "audit_bank_root", "precision_rule", "analysis_mode",
        "eligibility_class", "inference_claims_allowed", "multi_law_enabled",
        "evidence_tier", "independent_bank_plan_sha256",
    }, label="independent bank plan")
    assert_outcome_free_v1(plan, label="independent bank plan")
    validate_self_hash_v1(
        plan, field="independent_bank_plan_sha256", label="independent bank plan"
    )
    design_raw, design_identity = reopen_json_identity_v1(
        plan["precursor_design_identity"],
        read_exact=read_exact,
        label="precursor design",
    )
    design = validate_precursor_design_v1(design_raw, read_exact=read_exact)
    if design["precursor_design_sha256"] != plan["precursor_design_sha256"]:
        _fail("independent bank plan precursor design differs")
    rebuilt = build_independent_bank_plan_v1(
        plan_id=_string(plan["plan_id"], label="plan id"),
        precursor_design=design,
        precursor_design_identity=design_identity,
        selection_bank_root=_mapping(
            plan["selection_bank_root"], label="selection bank root"
        ),
        audit_bank_root=_mapping(plan["audit_bank_root"], label="audit bank root"),
        read_exact=read_exact,
    )
    if canonical_json_bytes_v1(rebuilt) != canonical_json_bytes_v1(plan):
        _fail("independent bank plan canonical replay differs")
    return plan
