"""Minimal one-shot supplier for the frozen LR8 later-period evaluation.

The caller owns the shared historical-outcome lease lifecycle.  This module
only validates the same live generation before and after one exact-key query.
It creates the attempt before that query, derives player/DST keys solely from
the generation-pinned 108-cell book freeze, sums rosters in integer micro-DK,
and independently replays ``evaluate_frozen_later_period_once`` from reopened
create-once publications.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
import json
import re
from typing import Any, Final

from nfl_dfs.research import lr8_historical_arm as lr8
from nfl_dfs.research import lr8_label_fit_adapter as fit_adapter
from nfl_dfs.research import lr8_label_score_map as shared
from nfl_dfs.research import lr8_later_period_source as later_source
from nfl_dfs.research import residual_world_columns as rw


SUPPLIER_VERSION: Final = "lr8-later-period-evaluation-supplier-v1"
BOOK_FREEZE_VERSION: Final = later_source.BOOK_FREEZE_VERSION
ATTEMPT_VERSION: Final = "lr8-later-period-score-read-attempt-v1"
SOURCE_VERSION: Final = "lr8-later-period-player-score-source-v1"
EVALUATION_VERSION: Final = "lr8-later-period-evaluation-publication-v1"
PROJECT: Final = shared.PROJECT
LOCATION: Final = shared.LOCATION
BUCKET: Final = shared.BUCKET
SKILL_TABLE: Final = shared.SKILL_TABLE
DST_TABLE: Final = shared.DST_TABLE
OUTPUT_NAMESPACE: Final = "research/lr8-later-period-evaluation"
LEASE_OWNER: Final = "external-launcher-watcher"
SCORE_READ_STAGE: Final = "lr8-2023-2025-later-period-score-read"
EXPECTED_SLATES: Final = tuple(
    (season, week)
    for season in lr8.EVALUATION_SEASONS
    for week in lr8.EVALUATION_WEEKS
)
EXPECTED_BOOKS: Final = tuple(
    (season, week, fold)
    for season, week in EXPECTED_SLATES
    for fold in ("A", "B")
)
SOURCE_ROW_FIELDS: Final = (
    "season", "week", "source_kind", "source_key", "player_id",
    "realized_score_micro",
)
SCORE_ROW_FIELDS: Final = (
    "season", "week", "roster", "realized_total_micro",
)

_RUN_ID = re.compile(r"[a-z0-9][a-z0-9-]{2,80}")
_JOB = re.compile(r"[a-z0-9][a-z0-9-]{2,62}")
_CODE = re.compile(r"[0-9a-f]{40}")
_IMAGE = re.compile(r".+@sha256:[0-9a-f]{64}")


class LR8LaterPeriodError(RuntimeError):
    """The bounded later-period evaluation failed closed."""


@dataclass(frozen=True, slots=True)
class SupplierConfig:
    run_id: str
    job: str
    code_sha: str
    image: str
    expected_book_freeze_sha256: str
    enabled: bool = False

    @property
    def output_root(self) -> str:
        return f"gs://{BUCKET}/{OUTPUT_NAMESPACE}/{self.run_id}"


@dataclass(frozen=True, slots=True)
class CatalogPlayer:
    season: int
    week: int
    player_id: str
    source_kind: str
    source_key: str


@dataclass(frozen=True, slots=True)
class FrozenBooks:
    cells: tuple[lr8.FrozenBookCell, ...]
    catalog: tuple[CatalogPlayer, ...]
    rosters: tuple[tuple[int, int, tuple[str, ...]], ...]
    freeze_sha256: str
    receipt: Mapping[str, object]


@dataclass(frozen=True, slots=True)
class QuerySpec:
    sql: str
    parameters: tuple[shared.QueryParameter, ...]
    job_id: str
    location: str
    sql_sha256: str
    parameters_sha256: str
    union_keys_sha256: str


@dataclass(frozen=True, slots=True)
class EvaluationSupply:
    attempt: Mapping[str, object]
    attempt_receipt: Mapping[str, object]
    source: Mapping[str, object]
    source_receipt: Mapping[str, object]
    evaluation: Mapping[str, object]
    evaluation_receipt: Mapping[str, object]


QueryResult = shared.QueryResult
PublishedObject = shared.PublishedObject
LeaseVerifier = Callable[[], Mapping[str, object]]
MetadataReader = Callable[[str], Mapping[str, object]]
QueryExecutor = Callable[[QuerySpec], QueryResult]
Publisher = Callable[[str, bytes], PublishedObject]
Clock = Callable[[], datetime]
canonical_json = shared.canonical_json
canonical_sha256 = shared.canonical_sha256


def _translate(call: Callable[[], Any]) -> Any:
    try:
        return call()
    except shared.LR8ScoreMapError as exc:
        raise LR8LaterPeriodError(str(exc)) from exc


def _string(value: object, label: str) -> str:
    if not isinstance(value, str) or not value or value.strip() != value:
        raise LR8LaterPeriodError(f"{label} must be a canonical string")
    return value


def _integer(value: object, label: str, minimum: int = 0) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise LR8LaterPeriodError(f"{label} must be an exact integer")
    return value


def _config(value: SupplierConfig) -> SupplierConfig:
    if not isinstance(value, SupplierConfig) or (
        _RUN_ID.fullmatch(value.run_id) is None
        or _JOB.fullmatch(value.job) is None
        or _CODE.fullmatch(value.code_sha) is None
        or _IMAGE.fullmatch(value.image) is None
    ):
        raise LR8LaterPeriodError("later-period runtime identity differs")
    _translate(lambda: shared._strict_sha256(  # noqa: SLF001
        value.expected_book_freeze_sha256, label="book freeze hash"
    ))
    return value


def _rosters(value: object, label: str) -> tuple[tuple[str, ...], ...]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise LR8LaterPeriodError(f"{label} must be a sequence")
    result = []
    for raw in value:
        try:
            roster = rw.canonical_identity(raw)  # type: ignore[arg-type]
        except (TypeError, rw.ResidualWorldError) as exc:
            raise LR8LaterPeriodError(f"{label} contains a bad roster") from exc
        if list(raw) != list(roster):  # type: ignore[arg-type]
            raise LR8LaterPeriodError(f"{label} roster order differs")
        result.append(roster)
    if len(set(result)) != len(result):
        raise LR8LaterPeriodError(f"{label} repeats a roster")
    return tuple(result)


def _cell(value: object) -> lr8.FrozenBookCell:
    fields = {
        "season", "week", "fold_name", "candidate_budget_control",
        "candidate_budget_treatment", "control_candidates",
        "treatment_candidates", "control_book", "treatment_book",
        "cell_sha256",
    }
    if not isinstance(value, Mapping) or set(value) != fields:
        raise LR8LaterPeriodError("book-cell fields differ")
    digest = _translate(lambda: shared._strict_sha256(  # noqa: SLF001
        value["cell_sha256"], label="book-cell hash"
    ))
    body = {key: item for key, item in value.items() if key != "cell_sha256"}
    if canonical_sha256(body) != digest:
        raise LR8LaterPeriodError("book-cell hash differs")
    season = _integer(value["season"], "book season")
    week = _integer(value["week"], "book week", 1)
    fold = _string(value["fold_name"], "book fold")
    control = _rosters(value["control_candidates"], "control candidates")
    treatment = _rosters(
        value["treatment_candidates"], "treatment candidates"
    )
    control_book = _rosters(value["control_book"], "control book")
    treatment_book = _rosters(value["treatment_book"], "treatment book")
    control_n = _integer(
        value["candidate_budget_control"], "control budget", lr8.ENTRIES
    )
    treatment_n = _integer(
        value["candidate_budget_treatment"], "treatment budget", lr8.ENTRIES
    )
    if (
        (season, week, fold) not in EXPECTED_BOOKS
        or control_n != treatment_n
        or len(control) != control_n
        or len(treatment) != treatment_n
        or len(control_book) != lr8.ENTRIES
        or len(treatment_book) != lr8.ENTRIES
        or not set(control_book) <= set(control)
        or not set(treatment_book) <= set(treatment)
    ):
        raise LR8LaterPeriodError("book-cell budget or identity differs")
    return lr8.FrozenBookCell(
        season, week, fold, control_n, treatment_n, control, treatment,
        control_book, treatment_book, digest,
    )


def validate_book_freeze(
    value: Mapping[str, object], *, expected_freeze_sha256: str,
    object_receipt: Mapping[str, object],
) -> FrozenBooks:
    expected = _translate(lambda: shared._strict_sha256(  # noqa: SLF001
        expected_freeze_sha256, label="book freeze hash"
    ))
    try:
        frozen = later_source.validate_book_freeze(
            value, expected_freeze_sha256=expected
        )
    except later_source.LR8LaterSourceError as exc:
        raise LR8LaterPeriodError(str(exc)) from exc
    receipt = _translate(lambda: shared._bound_content_receipt(  # noqa: SLF001
        object_receipt, frozen, label="book freeze object"
    ))
    raw_cells = frozen["book_cells"]
    if isinstance(raw_cells, (str, bytes)) or not isinstance(raw_cells, Sequence):
        raise LR8LaterPeriodError("book cells must be a sequence")
    cells = tuple(_cell(row) for row in raw_cells)
    if tuple((row.season, row.week, row.fold_name) for row in cells) != EXPECTED_BOOKS:
        raise LR8LaterPeriodError("book cells are not the exact 108-cell lattice")

    raw_catalogs = frozen["catalogs"]
    if isinstance(raw_catalogs, (str, bytes)) or not isinstance(
        raw_catalogs, Sequence
    ) or len(raw_catalogs) != len(EXPECTED_SLATES):
        raise LR8LaterPeriodError("book catalogs differ")
    catalogs: dict[tuple[int, int], dict[str, CatalogPlayer]] = {}
    for raw, key in zip(raw_catalogs, EXPECTED_SLATES, strict=True):
        if not isinstance(raw, Mapping) or set(raw) != {
            "season", "week", "players", "catalog_sha256",
        } or (raw["season"], raw["week"]) != key:
            raise LR8LaterPeriodError("book catalog identity differs")
        players_raw = raw["players"]
        if isinstance(players_raw, (str, bytes)) or not isinstance(
            players_raw, Sequence
        ) or canonical_sha256(players_raw) != raw["catalog_sha256"]:
            raise LR8LaterPeriodError("book catalog hash differs")
        rows: list[CatalogPlayer] = []
        for player in players_raw:
            if not isinstance(player, Mapping) or set(player) != {"id", "pos", "team"}:
                raise LR8LaterPeriodError("book catalog row fields differ")
            player_id = _string(player["id"], "player id")
            position = _string(player["pos"], "player position").upper()
            team = _string(player["team"], "player team").upper()
            rows.append(CatalogPlayer(
                key[0], key[1], player_id,
                "dst" if position == "DST" else "skill",
                team if position == "DST" else player_id,
            ))
        ids = [row.player_id for row in rows]
        if ids != sorted(ids) or len(ids) != len(set(ids)):
            raise LR8LaterPeriodError("book catalog order or uniqueness differs")
        catalogs[key] = {row.player_id: row for row in rows}

    per_slate = {key: set() for key in EXPECTED_SLATES}
    for cell in cells:
        per_slate[(cell.season, cell.week)].update(
            (*cell.control_candidates, *cell.treatment_candidates)
        )
    catalog: list[CatalogPlayer] = []
    rosters: list[tuple[int, int, tuple[str, ...]]] = []
    for key in EXPECTED_SLATES:
        slate_rosters = tuple(sorted(per_slate[key]))
        player_ids = sorted({item for roster in slate_rosters for item in roster})
        if not slate_rosters or not set(player_ids) <= set(catalogs[key]):
            raise LR8LaterPeriodError("candidate union lacks catalog coverage")
        slate_catalog = tuple(catalogs[key][item] for item in player_ids)
        source_keys = [(row.source_kind, row.source_key) for row in slate_catalog]
        if len(source_keys) != len(set(source_keys)):
            raise LR8LaterPeriodError("candidate-union source keys repeat")
        catalog.extend(slate_catalog)
        rosters.extend((key[0], key[1], roster) for roster in slate_rosters)
    return FrozenBooks(cells, tuple(catalog), tuple(rosters), expected, receipt)


def authoritative_score_sql() -> str:
    sql = f"""WITH skill_scores AS (
  SELECT a.season, a.week, 'skill' AS source_kind,
         CAST(a.gsis_id AS STRING) AS source_key,
         CAST(a.dk_points AS NUMERIC) AS realized_score
  FROM `{SKILL_TABLE}` FOR SYSTEM_TIME AS OF @source_snapshot_at AS a
  WHERE a.season IN UNNEST(@target_seasons)
    AND FORMAT('%d|%02d|%s', a.season, a.week, CAST(a.gsis_id AS STRING))
      IN UNNEST(@skill_keys)
), dst_scores AS (
  SELECT d.season, d.week, 'dst' AS source_kind,
         UPPER(CAST(d.team AS STRING)) AS source_key,
         CAST(d.dst_dk_points AS NUMERIC) AS realized_score
  FROM `{DST_TABLE}` FOR SYSTEM_TIME AS OF @source_snapshot_at AS d
  WHERE d.season IN UNNEST(@target_seasons)
    AND FORMAT('%d|%02d|%s', d.season, d.week, UPPER(CAST(d.team AS STRING)))
      IN UNNEST(@dst_keys)
)
SELECT season, week, source_kind, source_key, realized_score FROM skill_scores
UNION ALL
SELECT season, week, source_kind, source_key, realized_score FROM dst_scores
ORDER BY season, week, source_kind, source_key"""
    if any(token in f" {sql.lower()} " for token in (
        " actual_score", " contest", " ownership", " payout", " winner",
        " insert ", " update ", " merge ", " delete ",
    )):
        raise AssertionError("later-period SQL exceeded its exact-union boundary")
    return sql


AUTHORITATIVE_SCORE_SQL: Final = authoritative_score_sql()
AUTHORITATIVE_SCORE_SQL_SHA256: Final = sha256(
    AUTHORITATIVE_SCORE_SQL.encode()
).hexdigest()


def _union_payload(catalog: Sequence[CatalogPlayer]) -> list[dict[str, object]]:
    return [{
        "season": row.season, "week": row.week,
        "source_kind": row.source_kind, "source_key": row.source_key,
        "player_id": row.player_id,
    } for row in catalog]


def _parameter_payload(
    catalog: Sequence[CatalogPlayer], snapshot: str,
) -> list[dict[str, object]]:
    skill = sorted(
        f"{row.season}|{row.week:02d}|{row.source_key}"
        for row in catalog if row.source_kind == "skill"
    )
    dst = sorted(
        f"{row.season}|{row.week:02d}|{row.source_key}"
        for row in catalog if row.source_kind == "dst"
    )
    return [
        {"name": "source_snapshot_at", "type": "TIMESTAMP", "array": False,
         "value": snapshot},
        {"name": "target_seasons", "type": "INT64", "array": True,
         "value": list(lr8.EVALUATION_SEASONS)},
        {"name": "skill_keys", "type": "STRING", "array": True,
         "value": skill},
        {"name": "dst_keys", "type": "STRING", "array": True, "value": dst},
    ]


def build_query_spec(
    *, config: SupplierConfig, catalog: Sequence[CatalogPlayer],
    source_snapshot_at: str,
) -> QuerySpec:
    _config(config)
    snapshot, _ = _translate(lambda: shared._utc(  # noqa: SLF001
        source_snapshot_at, label="source snapshot"
    ))
    rows = tuple(catalog)
    skill = sorted(
        f"{row.season}|{row.week:02d}|{row.source_key}"
        for row in rows if row.source_kind == "skill"
    )
    dst = sorted(
        f"{row.season}|{row.week:02d}|{row.source_key}"
        for row in rows if row.source_kind == "dst"
    )
    if (
        not skill
        or not dst
        or len(skill) + len(dst) != len(rows)
        or len(set(skill)) != len(skill)
        or len(set(dst)) != len(dst)
    ):
        raise LR8LaterPeriodError("candidate-union query keys differ")
    parameters = (
        shared.QueryParameter("source_snapshot_at", "TIMESTAMP", snapshot),
        shared.QueryParameter(
            "target_seasons", "INT64", list(lr8.EVALUATION_SEASONS), True
        ),
        shared.QueryParameter("skill_keys", "STRING", skill, True),
        shared.QueryParameter("dst_keys", "STRING", dst, True),
    )
    payload = shared._parameter_payload(parameters)  # noqa: SLF001
    return QuerySpec(
        AUTHORITATIVE_SCORE_SQL,
        parameters,
        (
            f"lr8_later_eval_{config.run_id.replace('-', '_')[:44]}_"
            f"{config.expected_book_freeze_sha256[:12]}"
        ),
        LOCATION,
        AUTHORITATIVE_SCORE_SQL_SHA256,
        sha256(canonical_json(payload)).hexdigest(),
        canonical_sha256(_union_payload(rows)),
    )


def _query_rows(value: object, books: FrozenBooks) -> list[dict[str, object]]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise LR8LaterPeriodError("query rows must be a sequence")
    expected = {
        (row.season, row.week, row.source_kind, row.source_key): row
        for row in books.catalog
    }
    result = []
    for raw in value:
        if not isinstance(raw, Mapping) or set(raw) != set(shared.QUERY_ROW_FIELDS):
            raise LR8LaterPeriodError("query row fields differ")
        key = (
            _integer(raw["season"], "query season"),
            _integer(raw["week"], "query week", 1),
            _string(raw["source_kind"], "query kind"),
            _string(raw["source_key"], "query key"),
        )
        player = expected.get(key)
        if player is None:
            raise LR8LaterPeriodError("query returned a non-union key")
        score = _translate(lambda: shared._micro_score(raw["realized_score"]))  # noqa: SLF001
        result.append({
            "season": key[0], "week": key[1], "source_kind": key[2],
            "source_key": key[3], "player_id": player.player_id,
            "realized_score_micro": score,
        })
    observed = [
        (row["season"], row["week"], row["source_kind"], row["source_key"])
        for row in result
    ]
    if observed != sorted(expected):
        raise LR8LaterPeriodError("query is not the exact ordered candidate union")
    return result


def _score_rows(
    books: FrozenBooks, rows: object,
) -> tuple[list[dict[str, object]], tuple[lr8.LaterPeriodScoreRow, ...]]:
    if isinstance(rows, (str, bytes)) or not isinstance(rows, Sequence):
        raise LR8LaterPeriodError("retained source rows differ")
    expected = {
        (row.season, row.week, row.source_kind, row.source_key): row
        for row in books.catalog
    }
    scores = {}
    observed = []
    for raw in rows:
        if not isinstance(raw, Mapping) or set(raw) != set(SOURCE_ROW_FIELDS):
            raise LR8LaterPeriodError("retained source row fields differ")
        key = (
            _integer(raw["season"], "source season"),
            _integer(raw["week"], "source week", 1),
            _string(raw["source_kind"], "source kind"),
            _string(raw["source_key"], "source key"),
        )
        player = expected.get(key)
        score = raw["realized_score_micro"]
        if player is None or raw["player_id"] != player.player_id or (
            isinstance(score, bool) or not isinstance(score, int)
        ):
            raise LR8LaterPeriodError("retained source row identity differs")
        observed.append(key)
        scores[(key[0], key[1], player.player_id)] = score
    if observed != sorted(expected):
        raise LR8LaterPeriodError("retained source is not the exact union")
    serialized = []
    evaluator = []
    for season, week, roster in books.rosters:
        try:
            total = sum(scores[(season, week, player)] for player in roster)
        except KeyError as exc:
            raise LR8LaterPeriodError("roster lacks an authoritative score") from exc
        if total < 0 or total > (1 << 63) - 1:
            raise LR8LaterPeriodError("roster sum is outside the exact range")
        serialized.append({
            "season": season, "week": week, "roster": list(roster),
            "realized_total_micro": total,
        })
        evaluator.append(lr8.LaterPeriodScoreRow(season, week, roster, total))
    return serialized, tuple(evaluator)


def _publish(
    publisher: Publisher, uri: str, payload: Mapping[str, object],
    earliest: datetime, label: str,
) -> tuple[dict[str, object], datetime, dict[str, object]]:
    raw = canonical_json(payload)
    published = publisher(uri, raw)
    if not isinstance(published, PublishedObject) or published.created is not True:
        raise LR8LaterPeriodError(f"{label} was not create-once")
    receipt = _translate(lambda: shared._create_once_receipt(  # noqa: SLF001
        published.receipt, label=f"{label} receipt"
    ))
    created_text, created = _translate(lambda: shared._utc(  # noqa: SLF001
        published.created_at, label=f"{label} creation"
    ))
    if (
        receipt["uri"] != uri
        or published.reopened_raw != raw
        or receipt["sha256"] != sha256(raw).hexdigest()
        or receipt["bytes"] != len(raw)
        or created < earliest
        or created_text != published.created_at
    ):
        raise LR8LaterPeriodError(f"{label} reopen differs")
    try:
        reopened = json.loads(published.reopened_raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise LR8LaterPeriodError(f"{label} reopened JSON differs") from exc
    if not isinstance(reopened, dict):
        raise LR8LaterPeriodError(f"{label} reopened JSON differs")
    return receipt, created, reopened


def _attempt_identity(
    receipt: Mapping[str, object], lease: Mapping[str, object],
) -> dict[str, object]:
    return {
        **{key: receipt[key] for key in ("uri", "generation", "sha256", "bytes")},
        "create_once": True,
        "stage": SCORE_READ_STAGE,
        "historical_outcome_lease_generation": (
            lease["object_receipt"]["generation"]  # type: ignore[index]
        ),
    }


def _replay(
    *, books: FrozenBooks, source: Mapping[str, object],
    source_receipt: Mapping[str, object], evaluation: Mapping[str, object],
    attempt: Mapping[str, object], attempt_receipt: Mapping[str, object],
    attempt_identity: Mapping[str, object],
) -> None:
    source_fields = {
        "version", "supplier_version", "book_freeze_sha256",
        "book_freeze_object", "attempt", "attempt_object", "query_spec",
        "job_receipt", "table_receipts", "source_snapshot_at", "row_fields",
        "rows", "rows_sha256", "table_metadata_stable_during_query",
        "historical_outcome_lease_unchanged_during_query", "lease_release_owner",
        "production_change_licensed",
    }
    if set(source) != source_fields or (
        source["version"] != SOURCE_VERSION
        or source["supplier_version"] != SUPPLIER_VERSION
        or source["book_freeze_sha256"] != books.freeze_sha256
        or source["book_freeze_object"] != books.receipt
        or source["attempt"] != attempt
        or source["attempt_object"] != attempt_receipt
        or source["row_fields"] != list(SOURCE_ROW_FIELDS)
        or source["rows_sha256"] != canonical_sha256(source["rows"])
        or source["table_metadata_stable_during_query"] is not True
        or source["historical_outcome_lease_unchanged_during_query"] is not True
        or source["lease_release_owner"] != LEASE_OWNER
        or source["production_change_licensed"] is not False
    ):
        raise LR8LaterPeriodError("reopened source replay differs")
    query_spec = source["query_spec"]
    expected_parameters = _parameter_payload(
        books.catalog, str(source["source_snapshot_at"])
    )
    if not isinstance(query_spec, Mapping) or set(query_spec) != {
        "sql_sha256", "parameters", "parameters_sha256", "union_keys_sha256",
    } or (
        query_spec["sql_sha256"] != AUTHORITATIVE_SCORE_SQL_SHA256
        or query_spec["parameters"] != expected_parameters
        or query_spec["parameters_sha256"]
        != sha256(canonical_json(expected_parameters)).hexdigest()
        or query_spec["union_keys_sha256"]
        != canonical_sha256(_union_payload(books.catalog))
    ):
        raise LR8LaterPeriodError("reopened source query identity differs")
    scores, evaluator_rows = _score_rows(books, source["rows"])
    report = lr8.evaluate_frozen_later_period_once(
        books.cells, evaluator_rows, attempt_identity=attempt_identity
    )
    evaluation_fields = {
        "version", "supplier_version", "book_freeze_sha256",
        "book_freeze_object", "attempt", "attempt_object", "attempt_identity",
        "source_object", "score_row_fields", "score_rows", "score_rows_sha256",
        "evaluation_report", "evaluation_report_sha256",
        "exact_player_sum_reconciled", "independent_evaluator_replay",
        "uses_realized_outcomes", "one_later_period_score_read",
        "historical_outcome_lease_release_required", "lease_release_owner",
        "historical_refit_licensed", "production_change_licensed",
    }
    if set(evaluation) != evaluation_fields or (
        evaluation["version"] != EVALUATION_VERSION
        or evaluation["supplier_version"] != SUPPLIER_VERSION
        or evaluation["book_freeze_sha256"] != books.freeze_sha256
        or evaluation["book_freeze_object"] != books.receipt
        or evaluation["attempt"] != attempt
        or evaluation["attempt_object"] != attempt_receipt
        or evaluation["attempt_identity"] != attempt_identity
        or evaluation["source_object"] != source_receipt
        or evaluation["score_row_fields"] != list(SCORE_ROW_FIELDS)
        or evaluation["score_rows"] != scores
        or evaluation["score_rows_sha256"] != canonical_sha256(scores)
        or evaluation["evaluation_report"] != report
        or evaluation["evaluation_report_sha256"] != report["report_sha256"]
        or evaluation["exact_player_sum_reconciled"] is not True
        or evaluation["independent_evaluator_replay"] is not True
        or evaluation["uses_realized_outcomes"] is not True
        or evaluation["one_later_period_score_read"] is not True
        or evaluation["historical_outcome_lease_release_required"] is not True
        or evaluation["lease_release_owner"] != LEASE_OWNER
        or evaluation["historical_refit_licensed"] is not False
        or evaluation["production_change_licensed"] is not False
    ):
        raise LR8LaterPeriodError("reopened evaluation replay differs")


def supply_later_period_evaluation(
    *, config: SupplierConfig, book_freeze: Mapping[str, object],
    book_freeze_receipt: Mapping[str, object], verify_lease: LeaseVerifier,
    read_table_metadata: MetadataReader, execute_query: QueryExecutor,
    publish: Publisher,
    clock: Clock = lambda: datetime.now(timezone.utc),
) -> EvaluationSupply:
    if not isinstance(config, SupplierConfig) or config.enabled is not True:
        raise LR8LaterPeriodError("LR8 later-period supplier is default-off")
    config = _config(config)
    books = validate_book_freeze(
        book_freeze,
        expected_freeze_sha256=config.expected_book_freeze_sha256,
        object_receipt=book_freeze_receipt,
    )
    attempt_uri = f"{config.output_root}/later-period-read-attempt.json"
    source_uri = f"{config.output_root}/later-period-player-score-source.json"
    evaluation_uri = f"{config.output_root}/later-period-evaluation.json"
    if len({
        books.receipt["uri"], fit_adapter.HISTORICAL_OUTCOME_LEASE_URI,
        attempt_uri, source_uri, evaluation_uri,
    }) != 5:
        raise LR8LaterPeriodError("later-period object URIs alias")
    lease_config = shared.SupplierConfig(
        config.run_id, config.job, config.code_sha, config.image,
        config.expected_book_freeze_sha256, True,
    )
    lease_before = _translate(lambda: shared._validate_lease(  # noqa: SLF001
        verify_lease(), config=lease_config
    ))
    started, started_at = _translate(lambda: shared._now(  # noqa: SLF001
        clock, label="later-period attempt start"
    ))
    _, acquired = _translate(lambda: shared._utc(  # noqa: SLF001
        lease_before["body"]["acquired_at"], label="lease acquired_at"
    ))
    if started_at < acquired:
        raise LR8LaterPeriodError("attempt predates the historical lease")
    attempt = {
        "version": ATTEMPT_VERSION,
        "supplier_version": SUPPLIER_VERSION,
        "stage": SCORE_READ_STAGE,
        "book_freeze_sha256": books.freeze_sha256,
        "book_freeze_object": books.receipt,
        "book_cell_count": len(books.cells),
        "union_player_count": len(books.catalog),
        "union_roster_count": len(books.rosters),
        "union_keys_sha256": canonical_sha256(_union_payload(books.catalog)),
        "query_sql_sha256": AUTHORITATIVE_SCORE_SQL_SHA256,
        "historical_outcome_lease": lease_before,
        "started_at": started,
        "uses_realized_outcomes_at_creation": False,
        "retry_licensed": False,
        "lease_release_owner": LEASE_OWNER,
        "production_change_licensed": False,
    }
    attempt_receipt, attempt_created, reopened_attempt = _publish(
        publish, attempt_uri, attempt, started_at, "later-period attempt"
    )
    if reopened_attempt != attempt:
        raise LR8LaterPeriodError("reopened attempt differs")

    snapshot, snapshot_at = _translate(lambda: shared._now(  # noqa: SLF001
        clock, label="later-period source snapshot"
    ))
    if snapshot_at < attempt_created:
        raise LR8LaterPeriodError("source snapshot predates the attempt")
    spec = build_query_spec(
        config=config, catalog=books.catalog, source_snapshot_at=snapshot
    )
    before = [_translate(lambda table=table: shared._table_receipt(  # noqa: SLF001
        read_table_metadata(table), table=table
    )) for table in (SKILL_TABLE, DST_TABLE)]
    queried = execute_query(spec)
    if not isinstance(queried, QueryResult):
        raise LR8LaterPeriodError("query executor returned the wrong type")
    job, query_ended = _translate(lambda: shared._job_receipt(  # noqa: SLF001
        queried.job_receipt, spec=spec, not_before=snapshot_at
    ))
    if job["cache_hit"] is not False:
        raise LR8LaterPeriodError("later-period query used cache")
    rows = _query_rows(queried.rows, books)
    after = [_translate(lambda table=table: shared._table_receipt(  # noqa: SLF001
        read_table_metadata(table), table=table
    )) for table in (SKILL_TABLE, DST_TABLE)]
    if before != after:
        raise LR8LaterPeriodError("outcome table metadata changed during query")
    lease_after = _translate(lambda: shared._validate_lease(  # noqa: SLF001
        verify_lease(), config=lease_config
    ))
    if canonical_json(lease_before) != canonical_json(lease_after):
        raise LR8LaterPeriodError("historical lease changed during query")
    source = {
        "version": SOURCE_VERSION,
        "supplier_version": SUPPLIER_VERSION,
        "book_freeze_sha256": books.freeze_sha256,
        "book_freeze_object": books.receipt,
        "attempt": attempt,
        "attempt_object": attempt_receipt,
        "query_spec": {
            "sql_sha256": spec.sql_sha256,
            "parameters": shared._parameter_payload(spec.parameters),  # noqa: SLF001
            "parameters_sha256": spec.parameters_sha256,
            "union_keys_sha256": spec.union_keys_sha256,
        },
        "job_receipt": job,
        "table_receipts": before,
        "source_snapshot_at": snapshot,
        "row_fields": list(SOURCE_ROW_FIELDS),
        "rows": rows,
        "rows_sha256": canonical_sha256(rows),
        "table_metadata_stable_during_query": True,
        "historical_outcome_lease_unchanged_during_query": True,
        "lease_release_owner": LEASE_OWNER,
        "production_change_licensed": False,
    }
    source_receipt, source_created, reopened_source = _publish(
        publish, source_uri, source, query_ended,
        "later-period player-score source",
    )
    score_rows, evaluator_rows = _score_rows(books, reopened_source["rows"])
    attempt_identity = _attempt_identity(attempt_receipt, lease_before)
    report = lr8.evaluate_frozen_later_period_once(
        books.cells, evaluator_rows, attempt_identity=attempt_identity
    )
    evaluation = {
        "version": EVALUATION_VERSION,
        "supplier_version": SUPPLIER_VERSION,
        "book_freeze_sha256": books.freeze_sha256,
        "book_freeze_object": books.receipt,
        "attempt": attempt,
        "attempt_object": attempt_receipt,
        "attempt_identity": attempt_identity,
        "source_object": source_receipt,
        "score_row_fields": list(SCORE_ROW_FIELDS),
        "score_rows": score_rows,
        "score_rows_sha256": canonical_sha256(score_rows),
        "evaluation_report": report,
        "evaluation_report_sha256": report["report_sha256"],
        "exact_player_sum_reconciled": True,
        "independent_evaluator_replay": True,
        "uses_realized_outcomes": True,
        "one_later_period_score_read": True,
        "historical_outcome_lease_release_required": True,
        "lease_release_owner": LEASE_OWNER,
        "historical_refit_licensed": False,
        "production_change_licensed": False,
    }
    evaluation_receipt, _, reopened_evaluation = _publish(
        publish, evaluation_uri, evaluation, source_created,
        "later-period evaluation",
    )
    _replay(
        books=books, source=reopened_source, source_receipt=source_receipt,
        evaluation=reopened_evaluation, attempt=attempt,
        attempt_receipt=attempt_receipt, attempt_identity=attempt_identity,
    )
    return EvaluationSupply(
        attempt, attempt_receipt, source, source_receipt,
        evaluation, evaluation_receipt,
    )


__all__ = [
    "AUTHORITATIVE_SCORE_SQL", "BOOK_FREEZE_VERSION", "EvaluationSupply",
    "LEASE_OWNER", "LR8LaterPeriodError", "PublishedObject", "QueryResult",
    "QuerySpec", "SupplierConfig", "build_query_spec", "canonical_json",
    "canonical_sha256", "supply_later_period_evaluation",
    "validate_book_freeze",
]
