"""Deterministic no-rescore funnel over the terminal R6 attribution release.

The public builder accepts exactly two retained authorities: the terminal
attribution-release root identity and a higher-level-prepinned immutable
Millionaire-winner registry identity.  It exact-reads the root, follows only
the 54 attribution shard identities named by that root, exact-reads the
pre-pinned registry, and derives all corpus and selection scores from the
persisted ``realized_score_micro`` labels in those shards.  It has no score
implementation, raw-outcome reader, object-store client, publisher, or
caller-supplied row seam.

The output deliberately separates the eight legal exact-80 books from their
diagnostic union.  Every exact-80 random reference uses ``K=80``; the union's
reference uses its actual slate-specific cardinality ``K_s``.  Fill-arm,
block, and selector summaries are descriptive ancestry only.  They are not
causal allocation evidence or promotion authority.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable, Mapping, Sequence
from decimal import Decimal, ROUND_HALF_EVEN, localcontext
from fractions import Fraction
from hashlib import sha256
import json
import math
import re
from typing import Final

from nfl_dfs.research import corpus_parametric_batch as batch
from nfl_dfs.research import corpus_r6_full_union_attribution_release_v1 as release
from nfl_dfs.research import corpus_r6_full_union_attribution_v1 as attribution
from nfl_dfs.research import corpus_r6_full_union_realized_grading_v1 as grading
from nfl_dfs.research import residual_world_columns as rw


FUNNEL_RELEASE_SCHEMA: Final = "corpus-r6-no-rescore-funnel-release/v1"
DERIVATION_MODE: Final = "terminal-attribution-exact-read-pure-derivation"
WINNER_REGISTRY_SCHEMA: Final = "milly-winner-registry/v1"
WINNER_REGISTRY_AUTHORITY_SCHEMA: Final = (
    "corpus-r6-winner-registry-prepinned-authority/v1"
)
WINNER_REGISTRY_AUTHORITY_ID: Final = "adopted-milly-winner-registry-v1"
ADOPTED_WINNER_REGISTRY_SHA256: Final = (
    "b8fc84eeeab18f64bdf1b4bef0888301c5c1434227d6b8066baef4fe7597e302"
)
ADOPTED_WINNER_REGISTRY_AUTHORITY_SHA256: Final = (
    "91087f3b8d6328d8254d2c97f91c193b913730b87e31756be81c494b14a8689e"
)
ADOPTED_WINNER_REGISTRY_IDENTITY: Final = {
    "uri": (
        "gs://nfl-predictions-503414-corpus-retrieval/research/"
        "corpus-r6-winner-registry/"
        "20260827-adopted-milly-winner-registry-v1/"
        "winner-registry-v1.json"
    ),
    "generation": "1787857632161809",
    "sha256": "13286cd428cecfcdb27544d4f590a970f526a2474f04b83b8a4328859866bdab",
    "bytes": 74_045,
}
ADOPTED_WINNER_CANONICAL_SOURCES: Final = (
    {
        "bytes": 17_609,
        "file": "milly-winners-2019-2023-2024.csv",
        "rows": 468,
        "sha256": "86359e22fdfbe87e9d1f899dd864038979881db5abbafbf26b40b1ff31985885",
    },
    {
        "bytes": 5_310,
        "file": "2025-milly-rosters.csv",
        "rows": 153,
        "sha256": "685db4eb916fb32f64af3138b1893a1b14dfeacd0e55d7ea8b968a2aaa103e3d",
    },
)
ADOPTED_WINNER_CROSSCHECK_SOURCES: Final = (
    {
        "bytes": 12_349,
        "file": "milly_rosters_2023_2024.csv",
        "rows": 279,
        "sha256": "b56d0a72db347be0a92a1cde23cf5fd680d9f5a4ff1ba701d1cfb809d9c3599d",
    },
    {
        "bytes": 1_725,
        "file": "2025-milly-winners.csv",
        "rows": 17,
        "sha256": "adeef608421736c13c2ff6b18c84e8df41c8880f1b6576e34d35d85f7e38fbc9",
    },
)
ADOPTED_WINNER_EXCLUSIONS: Final = ({
    "reason": "2024 week 9 duplicates week 7 in the canonical file",
    "rows_excluded": 9,
    "season": 2024,
    "week": 9,
},)
FINAL_SCOPE_ORDINAL: Final = grading.SCOPES_PER_SLATE - 1
FINAL_FIT_SCOPE_ID: Final = "all-block-final-fit"
EXACT_ENTRY_COUNT: Final = 80
MICRO_DK_PER_POINT: Final = grading.MICRO_DK_PER_POINT
DECIMAL_PLACES: Final = 18
DEEP_REVIEW_DOCUMENT_SHA256: Final = (
    "aa299baf4276a54b6727b5fc611059cfaf060c9055172b4dcd46fee7144e3e14"
)

STRATEGY_IDS: Final = (
    "coverage-194-v1",
    "strict-200-coverage-v1",
    "tail-ladder-200-210-220-v1",
    "mean-score-v1",
    "expected-max-v1",
    "block-supported-tail-ladder-v1",
    "regime-robust-ladder-v1",
    "strict-230-coverage-v1",
)

EXPECTED_REVIEW_HEADLINES: Final = {
    "source_slate_count": 54,
    "lineup_count": 199_244,
    "nominal_generation_occurrence_count": 378_000,
    "diagnostic_union_lineup_count": 11_062,
    "thresholds": {
        "187": {
            "population_lineup_count": 887,
            "population_opportunity_slates": 44,
            "diagnostic_union_hit_slates": 24,
        },
        "194": {
            "population_lineup_count": 483,
            "population_opportunity_slates": 36,
            "diagnostic_union_hit_slates": 16,
        },
        "200": {
            "population_lineup_count": 279,
            "population_opportunity_slates": 29,
            "diagnostic_union_hit_slates": 10,
        },
        "210": {
            "population_lineup_count": 105,
            "population_opportunity_slates": 18,
            "diagnostic_union_hit_slates": 6,
        },
        "220": {
            "population_lineup_count": 34,
            "population_opportunity_slates": 10,
            "diagnostic_union_hit_slates": 4,
        },
        "230": {
            "population_lineup_count": 7,
            "population_opportunity_slates": 3,
            "diagnostic_union_hit_slates": 2,
        },
        "240": {
            "population_lineup_count": 2,
            "population_opportunity_slates": 2,
            "diagnostic_union_hit_slates": 2,
        },
    },
    "diagnostic_union_exact_oracle_capture_slates": 9,
    "winner_target_included_slates": 51,
    "corpus_reaches_winner_slates": 1,
    "corpus_within_10_winner_slates": 2,
    "corpus_within_25_winner_slates": 20,
}

_SHA256: Final = re.compile(r"^[0-9a-f]{64}$")
_SLATE_ID: Final = re.compile(r"^(?P<season>[0-9]{4})-w(?P<week>[0-9]{2})$")
ReadExact = Callable[[Mapping[str, object]], bytes]

_FALSE_AUTHORITY_FIELDS: Final = (
    "raw_outcome_source_read",
    "outcome_snapshot_read",
    "outcome_query_executed",
    "lineup_rescore_performed",
    "historical_retry_licensed",
    "historical_retune_licensed",
    "corpus_fill_licensed",
    "graph_mutation_licensed",
    "production_change_licensed",
    "promotion_authority",
    "decision_authority",
    "live_money_policy_authority",
    "causal_claims_licensed",
    "structure_only_validation_authority",
)

_ROOT_FIELDS: Final = frozenset({
    "schema_version",
    "derivation_mode",
    "predecessors",
    "laws",
    "source_slate_count",
    "strategy_registry",
    "slate_rows",
    "slate_rows_sha256",
    "population_result",
    "exact_80_strategy_results",
    "diagnostic_union_result",
    "winner_target_census",
    "descriptive_attribution",
    "headline_reproduction",
    "uses_realized_outcomes",
    "no_rescore",
    "realized_lineup_scores_from_terminal_attribution_only",
    "winner_registry_prepinned_identity_required",
    "winner_registry_generation_exact_read",
    "winner_registry_internal_self_hash_verified",
    "authoritative_reopen_required",
    "complete",
    *_FALSE_AUTHORITY_FIELDS,
    "funnel_release_sha256",
})
_PREDECESSOR_FIELDS: Final = frozenset({
    "attribution_release_root_identity",
    "attribution_release_sha256",
    "grade_completion_identity",
    "persisted_grade_root_identity",
    "panel_freeze_identity",
    "panel_freeze_sha256",
    "attribution_shard_identities",
    "attribution_shard_identities_sha256",
    "winner_registry_identity",
    "winner_registry_sha256",
    "winner_registry_authority",
    "winner_registry_source_manifest",
})
_LAW_FIELDS: Final = frozenset({
    "final_fit_filter",
    "thresholds_dk",
    "threshold_operator",
    "random_book_reference_formula",
    "exact_80_random_draw_count_k",
    "diagnostic_union_random_draw_count",
    "inference_unit",
    "winner_target_interpretation",
    "descriptive_only",
})
_WINNER_AUTHORITY_FIELDS: Final = frozenset({
    "schema_version",
    "authority_id",
    "winner_registry_identity",
    "winner_registry_sha256",
    "expected_contest_count",
    "expected_governed_cohort_count",
    "expected_governed_seasons",
    "expected_per_season_contest_counts",
    "expected_provenance_gaps",
    "higher_level_operator_prepin_required",
    "terminal",
    "automatic_promotion",
    "production_policy_authority",
    "winner_registry_authority_sha256",
})
_SCORE_THRESHOLD_FIELDS: Final = frozenset({
    "threshold_dk",
    "threshold_micro",
    "population_lineup_count",
    "population_available",
    "selected_lineup_count",
    "selected_hit",
    "draw_count_k",
    "descriptive_random_hit_probability_rational",
    "descriptive_random_hit_probability_decimal",
    "high_score_density_per_1000_decimal",
})


class CorpusR6NoRescoreFunnelV1Error(ValueError):
    """The terminal-attribution funnel failed closed."""


def _fail(message: str) -> None:
    raise CorpusR6NoRescoreFunnelV1Error(message)


def canonical_json_bytes(value: object) -> bytes:
    try:
        return batch.canonical_json_bytes(value)
    except batch.CorpusParametricBatchError as exc:
        raise CorpusR6NoRescoreFunnelV1Error(str(exc)) from exc


def canonical_sha256(value: object) -> str:
    return sha256(canonical_json_bytes(value)).hexdigest()


def _mapping(value: object, *, label: str) -> dict[str, object]:
    if not isinstance(value, Mapping) or any(type(key) is not str for key in value):
        _fail(f"{label} must be a string-keyed object")
    return dict(value)


def _sequence(value: object, *, label: str) -> list[object]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        _fail(f"{label} must be an ordered array")
    return list(value)


def _identity(value: object, *, label: str) -> dict[str, object]:
    try:
        return batch.normalize_object_identity(value, label=label)
    except batch.CorpusParametricBatchError as exc:
        raise CorpusR6NoRescoreFunnelV1Error(str(exc)) from exc


def _identity_key(value: object, *, label: str) -> tuple[str, str, str, int]:
    row = _identity(value, label=label)
    return (
        str(row["uri"]),
        str(row["generation"]),
        str(row["sha256"]),
        int(row["bytes"]),
    )


def _digest(value: object, *, label: str) -> str:
    if type(value) is not str or _SHA256.fullmatch(value) is None:
        _fail(f"{label} must be one lowercase SHA-256")
    return value


def _exact_keys(
    value: Mapping[str, object], expected: frozenset[str], *, label: str,
) -> None:
    if frozenset(value) != expected:
        _fail(f"{label} fields differ")


def _exact_json(
    identity_value: object,
    *,
    read_exact: ReadExact,
    label: str,
    require_canonical_bytes: bool,
) -> tuple[dict[str, object], dict[str, object]]:
    identity = _identity(identity_value, label=f"{label} identity")
    try:
        raw = read_exact(identity)
    except CorpusR6NoRescoreFunnelV1Error:
        raise
    except Exception as exc:
        raise CorpusR6NoRescoreFunnelV1Error(
            f"{label} exact read failed"
        ) from exc
    if (
        type(raw) is not bytes
        or len(raw) != identity["bytes"]
        or sha256(raw).hexdigest() != identity["sha256"]
    ):
        _fail(f"{label} content identity differs")
    try:
        body = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CorpusR6NoRescoreFunnelV1Error(
            f"{label} is not JSON"
        ) from exc
    if not isinstance(body, dict):
        _fail(f"{label} must be a JSON object")
    if require_canonical_bytes and canonical_json_bytes(body) != raw:
        _fail(f"{label} canonical bytes differ")
    return body, identity


def _allowlisted_reader(
    *, read_exact: ReadExact, allowed_identities: Sequence[Mapping[str, object]],
) -> ReadExact:
    allowed = {
        _identity_key(value, label="allowed funnel predecessor identity")
        for value in allowed_identities
    }
    if len(allowed) != grading.SOURCE_SLATE_COUNT + 1:
        _fail("funnel predecessor exact-read allowlist census differs")

    def read_scoped(identity_value: Mapping[str, object]) -> bytes:
        retained = _identity(
            identity_value, label="requested funnel predecessor identity"
        )
        key = _identity_key(retained, label="requested funnel predecessor")
        if key not in allowed:
            _fail("funnel read identity is outside the exact allowlist")
        return read_exact(retained)

    return read_scoped


def _decimal(value: Decimal, *, places: int = DECIMAL_PLACES) -> str:
    quantum = Decimal(1).scaleb(-places)
    return format(value.quantize(quantum, rounding=ROUND_HALF_EVEN), "f")


def _ratio(numerator: int, denominator: int) -> str:
    if denominator <= 0:
        _fail("ratio denominator must be positive")
    with localcontext() as context:
        context.prec = 60
        return _decimal(Decimal(numerator) / Decimal(denominator))


def _random_hit_probability_fraction(
    *, population: int, qualifying: int, draw: int,
) -> Fraction:
    """Return the exact rational ``1-C(N-M,K)/C(N,K)``."""
    if (
        type(population) is not int
        or type(qualifying) is not int
        or type(draw) is not int
        or population < 1
        or not 0 <= qualifying <= population
        or not 0 <= draw <= population
    ):
        _fail("descriptive-random-null arguments differ")
    if qualifying == 0 or draw == 0:
        return Fraction(0, 1)
    if draw > population - qualifying:
        return Fraction(1, 1)
    misses = math.comb(population - qualifying, draw)
    total = math.comb(population, draw)
    return Fraction(total - misses, total)


def _fraction_decimal(value: Fraction) -> str:
    with localcontext() as context:
        context.prec = 60
        return _decimal(Decimal(value.numerator) / Decimal(value.denominator))


def _integer_minus_fraction_decimal(integer: int, value: Fraction) -> str:
    """Subtract exactly and round only the final retained decimal."""
    with localcontext() as context:
        context.prec = 80
        result = Decimal(integer) - (
            Decimal(value.numerator) / Decimal(value.denominator)
        )
        return _decimal(result)


def _random_hit_probability(*, population: int, qualifying: int, draw: int) -> str:
    """Return the exact null rounded once for display at the slate surface."""
    return _fraction_decimal(_random_hit_probability_fraction(
        population=population, qualifying=qualifying, draw=draw
    ))


def _fraction_from_row(value: object, *, label: str) -> Fraction:
    row = _mapping(value, label=label)
    if frozenset(row) != {"numerator", "denominator"}:
        _fail(f"{label} fields differ")
    numerator = row.get("numerator")
    denominator = row.get("denominator")
    if (
        type(numerator) is not str
        or type(denominator) is not str
        or not numerator.isdigit()
        or not denominator.isdigit()
        or int(denominator) < 1
    ):
        _fail(f"{label} differs")
    retained = Fraction(int(numerator), int(denominator))
    if (
        str(retained.numerator) != numerator
        or str(retained.denominator) != denominator
    ):
        _fail(f"{label} is not reduced")
    return retained


def _micro_from_winner_score(value: object, *, label: str) -> int:
    if type(value) not in {int, float} or isinstance(value, bool):
        _fail(f"{label} differs")
    text = str(value)
    try:
        micro = Decimal(text) * Decimal(MICRO_DK_PER_POINT)
    except Exception as exc:  # pragma: no cover - Decimal has narrow failures
        raise CorpusR6NoRescoreFunnelV1Error(f"{label} differs") from exc
    if not micro.is_finite() or micro != micro.to_integral_value():
        _fail(f"{label} is not exact in micro-DK")
    return int(micro)


def validate_winner_registry_authority_v1(value: object) -> dict[str, object]:
    """Validate an explicit higher-level pin for the adopted winner registry.

    The authority self-hash and exact immutable registry identity are fixed in
    this contract, independently of the caller.  The fixed internal registry
    hash and cohort laws additionally prevent a replacement from selecting a
    different target population.
    """
    item = _mapping(value, label="winner registry authority")
    _exact_keys(item, _WINNER_AUTHORITY_FIELDS, label="winner registry authority")
    retained_hash = _digest(
        item.get("winner_registry_authority_sha256"),
        label="winner registry authority SHA",
    )
    if canonical_sha256({
        key: nested for key, nested in item.items()
        if key != "winner_registry_authority_sha256"
    }) != retained_hash:
        _fail("winner registry authority self-hash differs")
    registry_identity = _identity(
        item.get("winner_registry_identity"), label="winner registry identity"
    )
    if (
        retained_hash != ADOPTED_WINNER_REGISTRY_AUTHORITY_SHA256
        or registry_identity != ADOPTED_WINNER_REGISTRY_IDENTITY
        or item.get("schema_version") != WINNER_REGISTRY_AUTHORITY_SCHEMA
        or item.get("authority_id") != WINNER_REGISTRY_AUTHORITY_ID
        or item.get("winner_registry_sha256")
        != ADOPTED_WINNER_REGISTRY_SHA256
        or item.get("expected_contest_count") != 68
        or item.get("expected_governed_cohort_count") != 51
        or item.get("expected_governed_seasons") != [2023, 2024, 2025]
        or item.get("expected_per_season_contest_counts")
        != {"2019": 17, "2023": 17, "2024": 17, "2025": 17}
        or item.get("expected_provenance_gaps")
        != ["contest-id-absent", "source-url-absent", "capture-time-absent"]
        or item.get("higher_level_operator_prepin_required") is not True
        or item.get("terminal") is not True
        or item.get("automatic_promotion") is not False
        or item.get("production_policy_authority") is not False
    ):
        _fail("winner registry authority law differs")
    item["winner_registry_identity"] = registry_identity
    return item


def _winner_targets_from_registry_v1(
    value: object,
) -> tuple[dict[str, int], dict[str, object]]:
    registry = _mapping(value, label="winner registry")
    required = frozenset({
        "canonical_sources",
        "contest_count",
        "contests",
        "crosscheck_sources",
        "excluded_duplicates",
        "governed_cohort_count",
        "governed_cohort_seasons",
        "outcome_scope",
        "per_season_contest_counts",
        "promotion_authority",
        "provenance_gaps",
        "schema_version",
        "uses_realized_outcomes",
        "winner_registry_sha256",
    })
    _exact_keys(registry, required, label="winner registry")
    retained_hash = _digest(
        registry.get("winner_registry_sha256"), label="winner registry SHA"
    )
    if canonical_sha256({
        key: nested for key, nested in registry.items()
        if key != "winner_registry_sha256"
    }) != retained_hash:
        _fail("winner registry self-hash differs")
    if (
        registry.get("schema_version") != WINNER_REGISTRY_SCHEMA
        or registry.get("contest_count") != 68
        or registry.get("governed_cohort_count") != 51
        or registry.get("governed_cohort_seasons") != [2023, 2024, 2025]
        or registry.get("per_season_contest_counts")
        != {"2019": 17, "2023": 17, "2024": 17, "2025": 17}
        or registry.get("canonical_sources")
        != list(ADOPTED_WINNER_CANONICAL_SOURCES)
        or registry.get("crosscheck_sources")
        != list(ADOPTED_WINNER_CROSSCHECK_SOURCES)
        or registry.get("excluded_duplicates")
        != list(ADOPTED_WINNER_EXCLUSIONS)
        or registry.get("provenance_gaps")
        != ["contest-id-absent", "source-url-absent", "capture-time-absent"]
        or registry.get("uses_realized_outcomes") is not True
        or registry.get("promotion_authority") is not False
    ):
        _fail("winner registry cohort or authority law differs")
    contests = [
        _mapping(raw, label=f"winner contest[{ordinal}]")
        for ordinal, raw in enumerate(
            _sequence(registry.get("contests"), label="winner contests")
        )
    ]
    if len(contests) != 68:
        _fail("winner registry contest census differs")
    targets: dict[str, int] = {}
    seen: set[str] = set()
    governed_count = 0
    observed_coordinates: list[tuple[int, int]] = []
    observed_per_season: Counter[int] = Counter()
    for ordinal, contest in enumerate(contests):
        expected_fields = frozenset({
            "season", "week", "slate_key", "governed_cohort", "players",
            "salary_total", "roster_points_total", "integrity_flags",
            "crosscheck",
        })
        _exact_keys(contest, expected_fields, label=f"winner contest[{ordinal}]")
        season = contest.get("season")
        week = contest.get("week")
        slate_id = contest.get("slate_key")
        players = _sequence(
            contest.get("players"), label=f"winner contest[{ordinal}] players"
        )
        if (
            type(season) is not int
            or type(week) is not int
            or type(slate_id) is not str
            or slate_id != f"{season}-w{week:02d}"
            or slate_id in seen
            or len(players) != 9
            or type(contest.get("governed_cohort")) is not bool
        ):
            _fail(f"winner contest[{ordinal}] coordinate differs")
        seen.add(slate_id)
        observed_coordinates.append((season, week))
        observed_per_season[season] += 1
        score_micro = _micro_from_winner_score(
            contest.get("roster_points_total"),
            label=f"winner contest[{ordinal}] score",
        )
        listed_total_micro = 0
        salary_values: list[int] = []
        salary_missing = False
        for player_ordinal, raw_player in enumerate(players):
            player = _mapping(
                raw_player,
                label=f"winner contest[{ordinal}] player[{player_ordinal}]",
            )
            _exact_keys(
                player,
                frozenset({
                    "name", "position", "salary", "ownership_pct",
                    "listed_points",
                }),
                label=f"winner contest[{ordinal}] player",
            )
            if (
                type(player.get("name")) is not str
                or not player["name"]
                or type(player.get("position")) is not str
                or not player["position"]
                or player.get("position")
                not in {"QB", "RB", "WR", "TE", "FLEX", "DST"}
            ):
                _fail(f"winner contest[{ordinal}] player identity differs")
            listed_total_micro += _micro_from_winner_score(
                player.get("listed_points"),
                label=f"winner contest[{ordinal}] persisted listed score",
            )
            salary = player.get("salary")
            if salary is None:
                salary_missing = True
            elif type(salary) is int and salary >= 0:
                salary_values.append(salary)
            else:
                _fail(f"winner contest[{ordinal}] salary differs")
        if listed_total_micro != score_micro:
            _fail(f"winner contest[{ordinal}] persisted score arithmetic differs")
        expected_salary_total = None if salary_missing else sum(salary_values)
        if contest.get("salary_total") != expected_salary_total:
            _fail(f"winner contest[{ordinal}] salary arithmetic differs")
        governed = bool(contest["governed_cohort"])
        if governed is not (season in {2023, 2024, 2025}):
            _fail(f"winner contest[{ordinal}] governed-cohort flag differs")
        if governed:
            targets[slate_id] = score_micro
            governed_count += 1
    if governed_count != 51 or len(targets) != 51:
        _fail("winner target governed census differs")
    if (
        observed_coordinates != sorted(observed_coordinates)
        or observed_per_season != Counter({2019: 17, 2023: 17, 2024: 17, 2025: 17})
    ):
        _fail("winner registry season/slate order or census differs")
    source_manifest = {
        "canonical_sources": registry["canonical_sources"],
        "crosscheck_sources": registry["crosscheck_sources"],
        "excluded_duplicates": registry["excluded_duplicates"],
        "provenance_gaps": registry["provenance_gaps"],
        "winner_registry_sha256": retained_hash,
    }
    return targets, source_manifest


def _score_threshold_rows(
    *, population_scores: Sequence[int], selected_scores: Sequence[int], draw: int,
) -> list[dict[str, object]]:
    population = len(population_scores)
    if population < 1 or len(selected_scores) != draw:
        _fail("threshold population/draw census differs")
    rows: list[dict[str, object]] = []
    for threshold in grading.THRESHOLDS_DK:
        threshold_micro = int(threshold) * MICRO_DK_PER_POINT
        qualifying = sum(score >= threshold_micro for score in population_scores)
        selected_count = sum(score >= threshold_micro for score in selected_scores)
        random_probability = _random_hit_probability_fraction(
            population=population, qualifying=qualifying, draw=draw
        )
        rows.append({
            "threshold_dk": int(threshold),
            "threshold_micro": threshold_micro,
            "population_lineup_count": qualifying,
            "population_available": qualifying > 0,
            "selected_lineup_count": selected_count,
            "selected_hit": selected_count > 0,
            "draw_count_k": draw,
            "descriptive_random_hit_probability_rational": {
                "numerator": str(random_probability.numerator),
                "denominator": str(random_probability.denominator),
            },
            "descriptive_random_hit_probability_decimal": _fraction_decimal(
                random_probability
            ),
            "high_score_density_per_1000_decimal": _decimal(
                Decimal(qualifying) * Decimal(1000) / Decimal(population)
            ),
        })
    return rows


def _validate_score_threshold_rows_v1(
    value: object,
    *,
    population: int,
    draw: int,
    label: str,
) -> list[dict[str, object]]:
    rows = [
        _mapping(raw, label=f"{label}[{ordinal}]")
        for ordinal, raw in enumerate(_sequence(value, label=label))
    ]
    if len(rows) != len(grading.THRESHOLDS_DK):
        _fail(f"{label} census differs")
    for expected_threshold, row in zip(
        grading.THRESHOLDS_DK, rows, strict=True
    ):
        _exact_keys(row, _SCORE_THRESHOLD_FIELDS, label=label)
        qualifying = row.get("population_lineup_count")
        selected = row.get("selected_lineup_count")
        probability = _fraction_from_row(
            row.get("descriptive_random_hit_probability_rational"),
            label=f"{label} exact random probability",
        )
        if (
            row.get("threshold_dk") != expected_threshold
            or row.get("threshold_micro")
            != int(expected_threshold) * MICRO_DK_PER_POINT
            or type(qualifying) is not int
            or not 0 <= qualifying <= population
            or row.get("population_available") is not (qualifying > 0)
            or type(selected) is not int
            or not 0 <= selected <= draw
            or row.get("selected_hit") is not (selected > 0)
            or row.get("draw_count_k") != draw
            or probability
            != _random_hit_probability_fraction(
                population=population, qualifying=qualifying, draw=draw
            )
            or row.get("descriptive_random_hit_probability_decimal")
            != _fraction_decimal(probability)
            or row.get("high_score_density_per_1000_decimal")
            != _decimal(
                Decimal(qualifying) * Decimal(1000) / Decimal(population)
            )
        ):
            _fail(f"{label} row differs")
    return rows


def _descriptive_lineage_v1(
    lineup_rows: Sequence[Mapping[str, object]],
) -> dict[str, object]:
    arm_rows = {
        arm: {
            "lineup_membership_count": 0,
            "exclusive_lineup_count": 0,
            "threshold_membership_counts": {
                str(threshold): 0 for threshold in grading.THRESHOLDS_DK
            },
            "threshold_exclusive_counts": {
                str(threshold): 0 for threshold in grading.THRESHOLDS_DK
            },
        }
        for arm in batch.PARAMETER_SET_ORDER
    }
    block_rows = {
        block: {
            "lineup_membership_count": 0,
            "exclusive_lineup_count": 0,
            "threshold_membership_counts": {
                str(threshold): 0 for threshold in grading.THRESHOLDS_DK
            },
            "threshold_exclusive_counts": {
                str(threshold): 0 for threshold in grading.THRESHOLDS_DK
            },
        }
        for block in rw.WORLD_BLOCKS
    }
    recurrence = Counter()
    nominal_occurrences = 0
    for row in lineup_rows:
        score = row.get("realized_score_micro")
        arms = _sequence(row.get("training_source_arms"), label="lineup arms")
        blocks = _sequence(
            row.get("training_origin_blocks"), label="lineup origin blocks"
        )
        occurrence_count = row.get("training_occurrence_count")
        if (
            type(score) is not int
            or type(occurrence_count) is not int
            or occurrence_count < 1
            or arms != sorted(set(arms))
            or blocks != [block for block in rw.WORLD_BLOCKS if block in blocks]
            or any(arm not in arm_rows for arm in arms)
            or any(block not in block_rows for block in blocks)
        ):
            _fail("lineup descriptive lineage differs")
        nominal_occurrences += occurrence_count
        recurrence[occurrence_count] += 1
        for arm in arms:
            target = arm_rows[str(arm)]
            target["lineup_membership_count"] += 1
            if len(arms) == 1:
                target["exclusive_lineup_count"] += 1
            for threshold in grading.THRESHOLDS_DK:
                if score >= int(threshold) * MICRO_DK_PER_POINT:
                    target["threshold_membership_counts"][str(threshold)] += 1
                    if len(arms) == 1:
                        target["threshold_exclusive_counts"][str(threshold)] += 1
        for block in blocks:
            target = block_rows[str(block)]
            target["lineup_membership_count"] += 1
            if len(blocks) == 1:
                target["exclusive_lineup_count"] += 1
            for threshold in grading.THRESHOLDS_DK:
                if score >= int(threshold) * MICRO_DK_PER_POINT:
                    target["threshold_membership_counts"][str(threshold)] += 1
                    if len(blocks) == 1:
                        target["threshold_exclusive_counts"][str(threshold)] += 1
    return {
        "interpretation": "descriptive-only-pooled-multi-arm-not-causal",
        "candidate_provenance_resolution": (
            attribution.CANDIDATE_PROVENANCE_RESOLUTION
        ),
        "exact_generation_occurrence_rows_available": False,
        "raw_recurrence_interpretation": (
            "conditional-stability-descriptor-not-probability-mass"
        ),
        "nominal_generation_occurrence_count": nominal_occurrences,
        "occurrence_count_histogram": [
            {"occurrence_count": count, "lineup_count": recurrence[count]}
            for count in sorted(recurrence)
        ],
        "fill_arms": [
            {"fill_arm_id": arm, **arm_rows[arm]}
            for arm in batch.PARAMETER_SET_ORDER
        ],
        "world_blocks": [
            {"world_block_id": block, **block_rows[block]}
            for block in rw.WORLD_BLOCKS
        ],
    }


def _slate_funnel_v1(
    *,
    shard: Mapping[str, object],
    descriptor: Mapping[str, object],
    shard_identity: Mapping[str, object],
    winner_target_micro: int | None,
) -> tuple[
    dict[str, object], dict[str, dict[str, object]], list[int],
]:
    ordinal = int(shard["source_ordinal"])
    slate_id = str(shard["slate_id"])
    if (
        descriptor.get("source_ordinal") != ordinal
        or descriptor.get("slate_id") != slate_id
        or descriptor.get("slate_attribution_identity") != shard_identity
        or descriptor.get("slate_attribution_sha256")
        != shard.get("slate_attribution_sha256")
        or descriptor.get("slate_freeze_identity")
        != shard.get("slate_freeze_identity")
        or descriptor.get("task_result_identity")
        != shard.get("task_result_identity")
        or descriptor.get("task_result_sha256")
        != shard.get("task_result_sha256")
        or descriptor.get("slate_grade_identity")
        != shard.get("slate_grade_identity")
        or descriptor.get("slate_grade_sha256")
        != shard.get("slate_grade_sha256")
    ):
        _fail(f"attribution descriptor/shard binding[{ordinal}] differs")
    lineup_rows = [
        _mapping(raw, label=f"lineup[{ordinal}]")
        for raw in _sequence(shard.get("lineup_rows"), label="lineup rows")
    ]
    score_by_id = {
        str(row["lineup_id"]): int(row["realized_score_micro"])
        for row in lineup_rows
    }
    if len(score_by_id) != len(lineup_rows) or len(score_by_id) < EXACT_ENTRY_COUNT:
        _fail(f"lineup score lookup[{ordinal}] differs")
    population_scores = list(score_by_id.values())
    corpus_maximum = max(population_scores)
    corpus_maximum_ids = sorted(
        lineup_id for lineup_id, score in score_by_id.items()
        if score == corpus_maximum
    )

    final_books = [
        _mapping(raw, label=f"final book[{ordinal}]")
        for raw in _sequence(shard.get("book_rows"), label="book rows")
        if isinstance(raw, Mapping)
        and raw.get("scope_ordinal") == FINAL_SCOPE_ORDINAL
        and raw.get("fit_scope_id") == FINAL_FIT_SCOPE_ID
    ]
    final_selections = [
        _mapping(raw, label=f"final selection[{ordinal}]")
        for raw in _sequence(shard.get("selection_rows"), label="selection rows")
        if isinstance(raw, Mapping)
        and raw.get("scope_ordinal") == FINAL_SCOPE_ORDINAL
        and raw.get("fit_scope_id") == FINAL_FIT_SCOPE_ID
    ]
    if (
        len(final_books) != len(STRATEGY_IDS)
        or len(final_selections) != len(STRATEGY_IDS) * EXACT_ENTRY_COUNT
    ):
        _fail(f"final-fit book/selection census[{ordinal}] differs")

    strategy_rows: list[dict[str, object]] = []
    registry: dict[str, dict[str, object]] = {}
    selected_sets: dict[str, set[str]] = {}
    for strategy_ordinal, strategy_id in enumerate(STRATEGY_IDS):
        book = final_books[strategy_ordinal]
        selections = sorted(
            (
                row for row in final_selections
                if row.get("strategy_ordinal") == strategy_ordinal
                and row.get("strategy_id") == strategy_id
            ),
            key=lambda row: int(row["selection_rank"]),
        )
        selected_ids = [str(row["lineup_id"]) for row in selections]
        if (
            book.get("strategy_ordinal") != strategy_ordinal
            or book.get("strategy_id") != strategy_id
            or book.get("selected_lineup_count") != EXACT_ENTRY_COUNT
            or book.get("eligible_lineup_count") != len(population_scores)
            or len(selections) != EXACT_ENTRY_COUNT
            or [row.get("selection_rank") for row in selections]
            != list(range(EXACT_ENTRY_COUNT))
            or len(set(selected_ids)) != EXACT_ENTRY_COUNT
            or any(lineup_id not in score_by_id for lineup_id in selected_ids)
        ):
            _fail(f"exact-80 strategy[{ordinal},{strategy_ordinal}] differs")
        selected_scores = [score_by_id[lineup_id] for lineup_id in selected_ids]
        selected_maximum = max(selected_scores)
        if (
            book.get("eligible_maximum_score_micro") != corpus_maximum
            or book.get("eligible_maximum_lineup_ids") != corpus_maximum_ids
            or book.get("selected_maximum_score_micro") != selected_maximum
            or book.get("selected_maximum_lineup_ids") != sorted(
                lineup_id for lineup_id in selected_ids
                if score_by_id[lineup_id] == selected_maximum
            )
            or book.get("selector_regret_micro")
            != corpus_maximum - selected_maximum
        ):
            _fail(f"exact-80 strategy maximum[{ordinal},{strategy_ordinal}] differs")
        computed_thresholds = _score_threshold_rows(
            population_scores=population_scores,
            selected_scores=selected_scores,
            draw=EXACT_ENTRY_COUNT,
        )
        retained_captures = _sequence(
            book.get("threshold_capture"), label="retained threshold captures"
        )
        for computed, raw_capture in zip(
            computed_thresholds, retained_captures, strict=True
        ):
            capture = _mapping(raw_capture, label="retained threshold capture")
            if (
                capture.get("threshold_dk") != computed["threshold_dk"]
                or capture.get("threshold_micro") != computed["threshold_micro"]
                or capture.get("eligible_lineup_count")
                != computed["population_lineup_count"]
                or capture.get("selected_lineup_count")
                != computed["selected_lineup_count"]
                or capture.get("eligible_hit")
                is not computed["population_available"]
                or capture.get("selected_hit") is not computed["selected_hit"]
            ):
                _fail(
                    f"retained threshold capture[{ordinal},{strategy_ordinal}] "
                    "differs from persisted lineup labels"
                )
        strategy_sha = _digest(
            book.get("strategy_sha256"), label="strategy SHA"
        )
        registry[strategy_id] = {
            "strategy_ordinal": strategy_ordinal,
            "strategy_id": strategy_id,
            "strategy_sha256": strategy_sha,
        }
        selected_sets[strategy_id] = set(selected_ids)
        top_order = sorted(score_by_id, key=lambda key: (-score_by_id[key], key))
        strategy_rows.append({
            "strategy_ordinal": strategy_ordinal,
            "strategy_id": strategy_id,
            "strategy_sha256": strategy_sha,
            "book_id": book["book_id"],
            "book_sha256": book["book_sha256"],
            "entry_count_k": EXACT_ENTRY_COUNT,
            "selected_maximum_score_micro": selected_maximum,
            "selector_regret_micro": corpus_maximum - selected_maximum,
            "exact_oracle_captured": bool(
                selected_sets[strategy_id].intersection(corpus_maximum_ids)
            ),
            "top_corpus_recall": [
                {
                    "q": q,
                    "captured_count": len(
                        selected_sets[strategy_id].intersection(top_order[:q])
                    ),
                    "recall_decimal": _ratio(
                        len(selected_sets[strategy_id].intersection(top_order[:q])),
                        q,
                    ),
                }
                for q in (1, 10, 80)
            ],
            "thresholds": computed_thresholds,
        })

    union_ids = sorted(set().union(*selected_sets.values()))
    union_scores = [score_by_id[lineup_id] for lineup_id in union_ids]
    union_maximum = max(union_scores)
    top_order = sorted(score_by_id, key=lambda key: (-score_by_id[key], key))
    union_thresholds = _score_threshold_rows(
        population_scores=population_scores,
        selected_scores=union_scores,
        draw=len(union_ids),
    )
    pairwise_overlap = []
    for left_ordinal, left in enumerate(STRATEGY_IDS):
        for right in STRATEGY_IDS[left_ordinal + 1:]:
            pairwise_overlap.append({
                "left_strategy_id": left,
                "right_strategy_id": right,
                "shared_lineup_count": len(
                    selected_sets[left].intersection(selected_sets[right])
                ),
            })
    lineage = _descriptive_lineage_v1(lineup_rows)
    winner = {
        "included": winner_target_micro is not None,
        "inclusion_reason_code": (
            "governed-winner-target-available"
            if winner_target_micro is not None else None
        ),
        "exclusion_reason_code": (
            None
            if winner_target_micro is not None
            else "winner-target-unavailable-for-panel-slate"
        ),
        "contest_id": None,
        "contest_identity_reason_code": "contest-id-absent",
        "target_score_micro": winner_target_micro,
        "corpus_maximum_score_micro": (
            corpus_maximum if winner_target_micro is not None else None
        ),
        "corpus_minus_target_micro": (
            corpus_maximum - winner_target_micro
            if winner_target_micro is not None else None
        ),
        "corpus_reaches_target": (
            corpus_maximum >= winner_target_micro
            if winner_target_micro is not None else None
        ),
        "diagnostic_union_maximum_score_micro": (
            union_maximum if winner_target_micro is not None else None
        ),
        "diagnostic_union_minus_target_micro": (
            union_maximum - winner_target_micro
            if winner_target_micro is not None else None
        ),
    }
    slate_row = {
        "source_ordinal": ordinal,
        "slate_id": slate_id,
        "attribution_shard_identity": dict(shard_identity),
        "attribution_shard_sha256": shard["slate_attribution_sha256"],
        "slate_freeze_identity": shard["slate_freeze_identity"],
        "task_result_identity": shard["task_result_identity"],
        "task_result_sha256": shard["task_result_sha256"],
        "slate_grade_identity": shard["slate_grade_identity"],
        "slate_grade_sha256": shard["slate_grade_sha256"],
        "candidate_provenance_sha256": shard["candidate_provenance_sha256"],
        "corpus": {
            "lineup_count": len(population_scores),
            "realized_score_sum_micro": sum(population_scores),
            "corpus_maximum_score_micro": corpus_maximum,
            "corpus_maximum_lineup_ids": corpus_maximum_ids,
            "thresholds": _score_threshold_rows(
                population_scores=population_scores,
                selected_scores=population_scores,
                draw=len(population_scores),
            ),
        },
        "exact_80_books": strategy_rows,
        "diagnostic_union": {
            "deployable_book": False,
            "actual_entry_count_k_s": len(union_ids),
            "selected_maximum_score_micro": union_maximum,
            "selector_regret_micro": corpus_maximum - union_maximum,
            "exact_oracle_captured": bool(set(union_ids).intersection(
                corpus_maximum_ids
            )),
            "top_corpus_recall": [
                {
                    "q": q,
                    "captured_count": len(set(union_ids).intersection(top_order[:q])),
                    "recall_decimal": _ratio(
                        len(set(union_ids).intersection(top_order[:q])), q
                    ),
                }
                for q in (1, 10, 80)
            ],
            "thresholds": union_thresholds,
            "pairwise_strategy_overlap": pairwise_overlap,
        },
        "winner_target": winner,
        "descriptive_lineage": lineage,
    }
    return slate_row, registry, population_scores


def _median_x2(values: Sequence[int]) -> int:
    if not values:
        _fail("median population is empty")
    ordered = sorted(values)
    middle = len(ordered) // 2
    if len(ordered) % 2:
        return 2 * ordered[middle]
    return ordered[middle - 1] + ordered[middle]


def _aggregate_panel_v1(
    *,
    slate_rows: Sequence[Mapping[str, object]],
    strategy_registry: Sequence[Mapping[str, object]],
    all_population_scores: Sequence[int],
) -> tuple[
    dict[str, object],
    list[dict[str, object]],
    dict[str, object],
    dict[str, object],
    dict[str, object],
]:
    oracle_scores: list[int] = []
    nominal_occurrences = 0
    union_entry_counts: list[int] = []
    arm_totals = {
        arm: {
            "lineup_membership_count": 0,
            "exclusive_lineup_count": 0,
            "threshold_membership_counts": {
                str(t): 0 for t in grading.THRESHOLDS_DK
            },
            "threshold_exclusive_counts": {
                str(t): 0 for t in grading.THRESHOLDS_DK
            },
        }
        for arm in batch.PARAMETER_SET_ORDER
    }
    block_totals = {
        block: {
            "lineup_membership_count": 0,
            "exclusive_lineup_count": 0,
            "threshold_membership_counts": {
                str(t): 0 for t in grading.THRESHOLDS_DK
            },
            "threshold_exclusive_counts": {
                str(t): 0 for t in grading.THRESHOLDS_DK
            },
        }
        for block in rw.WORLD_BLOCKS
    }
    strategy_panels = {
        strategy_id: {
            "maximum_scores": [],
            "regrets": [],
            "oracle_captures": 0,
            "thresholds": {
                str(t): {"hits": 0, "selected": 0, "random": []}
                for t in grading.THRESHOLDS_DK
            },
        }
        for strategy_id in STRATEGY_IDS
    }
    union_panel = {
        "maximum_scores": [],
        "regrets": [],
        "oracle_captures": 0,
        "thresholds": {
            str(t): {"hits": 0, "selected": 0, "random": []}
            for t in grading.THRESHOLDS_DK
        },
    }
    winner_rows: list[dict[str, object]] = []
    for expected_ordinal, raw_slate in enumerate(slate_rows):
        slate = _mapping(raw_slate, label=f"slate row[{expected_ordinal}]")
        if slate.get("source_ordinal") != expected_ordinal:
            _fail("slate row ordinal differs")
        corpus = _mapping(slate["corpus"], label="slate corpus")
        oracle_scores.append(int(corpus["corpus_maximum_score_micro"]))
        lineage = _mapping(slate["descriptive_lineage"], label="lineage")
        nominal_occurrences += int(lineage["nominal_generation_occurrence_count"])
        for row in _sequence(lineage["fill_arms"], label="fill arms"):
            item = _mapping(row, label="fill arm")
            target = arm_totals[str(item["fill_arm_id"])]
            for field in ("lineup_membership_count", "exclusive_lineup_count"):
                target[field] += int(item[field])
            for field in ("threshold_membership_counts", "threshold_exclusive_counts"):
                for threshold, count in _mapping(item[field], label=field).items():
                    target[field][threshold] += int(count)
        for row in _sequence(lineage["world_blocks"], label="world blocks"):
            item = _mapping(row, label="world block")
            target = block_totals[str(item["world_block_id"])]
            for field in ("lineup_membership_count", "exclusive_lineup_count"):
                target[field] += int(item[field])
            for field in ("threshold_membership_counts", "threshold_exclusive_counts"):
                for threshold, count in _mapping(item[field], label=field).items():
                    target[field][threshold] += int(count)
        for book in _sequence(slate["exact_80_books"], label="exact-80 books"):
            item = _mapping(book, label="exact-80 book")
            strategy_id = str(item["strategy_id"])
            panel = strategy_panels[strategy_id]
            panel["maximum_scores"].append(int(item["selected_maximum_score_micro"]))
            panel["regrets"].append(int(item["selector_regret_micro"]))
            panel["oracle_captures"] += int(bool(item["exact_oracle_captured"]))
            for threshold in _sequence(item["thresholds"], label="book thresholds"):
                threshold_row = _mapping(threshold, label="book threshold")
                cell = panel["thresholds"][str(threshold_row["threshold_dk"])]
                cell["hits"] += int(bool(threshold_row["selected_hit"]))
                cell["selected"] += int(threshold_row["selected_lineup_count"])
                cell["random"].append(
                    _fraction_from_row(
                        threshold_row[
                            "descriptive_random_hit_probability_rational"
                        ],
                        label="exact-80 random probability",
                    )
                )
        union = _mapping(slate["diagnostic_union"], label="diagnostic union")
        union_entry_counts.append(int(union["actual_entry_count_k_s"]))
        union_panel["maximum_scores"].append(int(union["selected_maximum_score_micro"]))
        union_panel["regrets"].append(int(union["selector_regret_micro"]))
        union_panel["oracle_captures"] += int(bool(union["exact_oracle_captured"]))
        for threshold in _sequence(union["thresholds"], label="union thresholds"):
            threshold_row = _mapping(threshold, label="union threshold")
            cell = union_panel["thresholds"][str(threshold_row["threshold_dk"])]
            cell["hits"] += int(bool(threshold_row["selected_hit"]))
            cell["selected"] += int(threshold_row["selected_lineup_count"])
            cell["random"].append(
                _fraction_from_row(
                    threshold_row["descriptive_random_hit_probability_rational"],
                    label="diagnostic-union random probability",
                )
            )
        winner_rows.append(dict(_mapping(slate["winner_target"], label="winner")))

    # Aggregate corpus scores from retained exact sums/counts rather than
    # reintroducing lineup rows into the result object.
    total_lineups = sum(int(_mapping(row["corpus"], label="corpus")["lineup_count"])
                        for row in slate_rows)
    total_score_micro = sum(
        int(_mapping(row["corpus"], label="corpus")["realized_score_sum_micro"])
        for row in slate_rows
    )
    if (
        len(all_population_scores) != total_lineups
        or sum(all_population_scores) != total_score_micro
    ):
        _fail("ephemeral population-score census/sum differs")
    population_thresholds = []
    for threshold in grading.THRESHOLDS_DK:
        cells = [
            _mapping(next(
                raw for raw in _sequence(
                    _mapping(row["corpus"], label="corpus")["thresholds"],
                    label="corpus thresholds",
                )
                if _mapping(raw, label="threshold")["threshold_dk"] == threshold
            ), label="population threshold")
            for row in slate_rows
        ]
        population_count = sum(int(cell["population_lineup_count"]) for cell in cells)
        opportunity_slates = sum(bool(cell["population_available"]) for cell in cells)
        population_thresholds.append({
            "threshold_dk": int(threshold),
            "population_lineup_count": population_count,
            "population_opportunity_slates": opportunity_slates,
            "high_score_density_per_1000_decimal": _decimal(
                Decimal(population_count) * Decimal(1000) / Decimal(total_lineups)
            ),
        })
    population_result = {
        "lineup_count": total_lineups,
        "nominal_generation_occurrence_count": nominal_occurrences,
        "unique_yield_decimal": _ratio(total_lineups, nominal_occurrences),
        "realized_score_sum_micro": total_score_micro,
        "realized_score_mean_micro_decimal": _decimal(
            Decimal(total_score_micro) / Decimal(total_lineups)
        ),
        "realized_score_median_micro_x2": _median_x2(all_population_scores),
        "realized_score_minimum_micro": min(all_population_scores),
        "realized_score_maximum_micro": max(all_population_scores),
        "corpus_oracle_score_mean_micro_decimal": _decimal(
            Decimal(sum(oracle_scores)) / Decimal(len(oracle_scores))
        ),
        "corpus_oracle_score_median_micro_x2": _median_x2(oracle_scores),
        "corpus_oracle_score_minimum_micro": min(oracle_scores),
        "corpus_oracle_score_maximum_micro": max(oracle_scores),
        "thresholds": population_thresholds,
    }

    exact_results = []
    population_opportunities = {
        str(row["threshold_dk"]): int(row["population_opportunity_slates"])
        for row in population_thresholds
    }
    for registry_row in strategy_registry:
        strategy_id = str(registry_row["strategy_id"])
        panel = strategy_panels[strategy_id]
        threshold_results = []
        for threshold in grading.THRESHOLDS_DK:
            cell = panel["thresholds"][str(threshold)]
            expected_random_fraction = sum(cell["random"], Fraction(0, 1))
            expected_random = _fraction_decimal(expected_random_fraction)
            threshold_results.append({
                "threshold_dk": int(threshold),
                "observed_hit_slates": int(cell["hits"]),
                "population_opportunity_slates": population_opportunities[str(threshold)],
                "conditional_conversion_decimal": _ratio(
                    int(cell["hits"]),
                    max(1, population_opportunities[str(threshold)]),
                ),
                "selected_qualifying_lineup_count": int(cell["selected"]),
                "descriptive_random_draw_count_k": EXACT_ENTRY_COUNT,
                "descriptive_random_expected_hit_slates_rational": {
                    "numerator": str(expected_random_fraction.numerator),
                    "denominator": str(expected_random_fraction.denominator),
                },
                "descriptive_random_expected_hit_slates_decimal": expected_random,
                "additive_lift_over_random_expected_hits_decimal": (
                    _integer_minus_fraction_decimal(
                        int(cell["hits"]), expected_random_fraction
                    )
                ),
            })
        maximum_scores = panel["maximum_scores"]
        regrets = panel["regrets"]
        exact_results.append({
            **dict(registry_row),
            "book_semantics": "one-deployable-exact-80-book-per-slate",
            "entry_count_k": EXACT_ENTRY_COUNT,
            "source_slate_count": len(slate_rows),
            "selected_maximum_score_mean_micro_decimal": _decimal(
                Decimal(sum(maximum_scores)) / Decimal(len(maximum_scores))
            ),
            "selector_regret_mean_micro_decimal": _decimal(
                Decimal(sum(regrets)) / Decimal(len(regrets))
            ),
            "exact_oracle_capture_slates": int(panel["oracle_captures"]),
            "thresholds": threshold_results,
        })

    union_threshold_results = []
    for threshold in grading.THRESHOLDS_DK:
        cell = union_panel["thresholds"][str(threshold)]
        expected_random_fraction = sum(cell["random"], Fraction(0, 1))
        expected_random = _fraction_decimal(expected_random_fraction)
        union_threshold_results.append({
            "threshold_dk": int(threshold),
            "observed_hit_slates": int(cell["hits"]),
            "population_opportunity_slates": population_opportunities[str(threshold)],
            "conditional_conversion_decimal": _ratio(
                int(cell["hits"]), max(1, population_opportunities[str(threshold)])
            ),
            "selected_qualifying_lineup_count": int(cell["selected"]),
            "descriptive_random_draw_law": "actual-slate-specific-k-s",
            "descriptive_random_expected_hit_slates_rational": {
                "numerator": str(expected_random_fraction.numerator),
                "denominator": str(expected_random_fraction.denominator),
            },
            "descriptive_random_expected_hit_slates_decimal": expected_random,
            "additive_lift_over_random_expected_hits_decimal": (
                _integer_minus_fraction_decimal(
                    int(cell["hits"]), expected_random_fraction
                )
            ),
        })
    diagnostic_union_result = {
        "deployable_book": False,
        "interpretation": "diagnostic-union-of-eight-alternative-exact-80-books",
        "source_slate_count": len(slate_rows),
        "total_distinct_lineup_occurrences": sum(union_entry_counts),
        "actual_k_s_minimum": min(union_entry_counts),
        "actual_k_s_maximum": max(union_entry_counts),
        "actual_k_s_mean_decimal": _decimal(
            Decimal(sum(union_entry_counts)) / Decimal(len(union_entry_counts))
        ),
        "selected_maximum_score_mean_micro_decimal": _decimal(
            Decimal(sum(union_panel["maximum_scores"]))
            / Decimal(len(union_panel["maximum_scores"]))
        ),
        "selector_regret_mean_micro_decimal": _decimal(
            Decimal(sum(union_panel["regrets"]))
            / Decimal(len(union_panel["regrets"]))
        ),
        "exact_oracle_capture_slates": int(union_panel["oracle_captures"]),
        "thresholds": union_threshold_results,
    }

    included = [row for row in winner_rows if row["included"] is True]
    gaps = [int(row["corpus_minus_target_micro"]) for row in included]
    winner_target_census = {
        "panel_slate_count": len(winner_rows),
        "included_slate_count": len(included),
        "excluded_slate_count": len(winner_rows) - len(included),
        "contest_identity_gap": "contest-id-absent",
        "corpus_reaches_target_slates": sum(gap >= 0 for gap in gaps),
        "corpus_within_10_target_slates": sum(
            gap >= -10 * MICRO_DK_PER_POINT for gap in gaps
        ),
        "corpus_within_25_target_slates": sum(
            gap >= -25 * MICRO_DK_PER_POINT for gap in gaps
        ),
        "corpus_minus_target_mean_micro_decimal": _decimal(
            Decimal(sum(gaps)) / Decimal(len(gaps))
        ),
        "corpus_minus_target_median_micro_x2": _median_x2(gaps),
        "corpus_minus_target_minimum_micro": min(gaps),
        "corpus_minus_target_maximum_micro": max(gaps),
        "rows": [
            {
                "source_ordinal": int(slate_rows[index]["source_ordinal"]),
                "slate_id": str(slate_rows[index]["slate_id"]),
                **winner_rows[index],
            }
            for index in range(len(slate_rows))
        ],
    }
    descriptive_attribution = {
        "interpretation": "descriptive-only-not-causal-allocation-evidence",
        "candidate_provenance_resolution": attribution.CANDIDATE_PROVENANCE_RESOLUTION,
        "exact_generation_occurrence_rows_available": False,
        "raw_recurrence_interpretation": (
            "conditional-stability-descriptor-not-probability-mass"
        ),
        "fill_arms": [
            {"fill_arm_id": arm, **arm_totals[arm]}
            for arm in batch.PARAMETER_SET_ORDER
        ],
        "world_blocks": [
            {"world_block_id": block, **block_totals[block]}
            for block in rw.WORLD_BLOCKS
        ],
        "selector_interpretation": (
            "descriptive-final-fit-membership-not-causal-strategy-effect"
        ),
    }
    return (
        population_result,
        exact_results,
        diagnostic_union_result,
        winner_target_census,
        descriptive_attribution,
    )


def _observed_review_headlines_v1(
    *,
    population_result: Mapping[str, object],
    diagnostic_union_result: Mapping[str, object],
    winner_target_census: Mapping[str, object],
) -> dict[str, object]:
    population_thresholds = {
        str(row["threshold_dk"]): row
        for row in population_result["thresholds"]  # type: ignore[index]
    }
    union_thresholds = {
        str(row["threshold_dk"]): row
        for row in diagnostic_union_result["thresholds"]  # type: ignore[index]
    }
    return {
        "source_slate_count": int(diagnostic_union_result["source_slate_count"]),
        "lineup_count": int(population_result["lineup_count"]),
        "nominal_generation_occurrence_count": int(
            population_result["nominal_generation_occurrence_count"]
        ),
        "diagnostic_union_lineup_count": int(
            diagnostic_union_result["total_distinct_lineup_occurrences"]
        ),
        "thresholds": {
            str(threshold): {
                "population_lineup_count": int(
                    population_thresholds[str(threshold)]["population_lineup_count"]
                ),
                "population_opportunity_slates": int(
                    population_thresholds[str(threshold)][
                        "population_opportunity_slates"
                    ]
                ),
                "diagnostic_union_hit_slates": int(
                    union_thresholds[str(threshold)]["observed_hit_slates"]
                ),
            }
            for threshold in grading.THRESHOLDS_DK
        },
        "diagnostic_union_exact_oracle_capture_slates": int(
            diagnostic_union_result["exact_oracle_capture_slates"]
        ),
        "winner_target_included_slates": int(
            winner_target_census["included_slate_count"]
        ),
        "corpus_reaches_winner_slates": int(
            winner_target_census["corpus_reaches_target_slates"]
        ),
        "corpus_within_10_winner_slates": int(
            winner_target_census["corpus_within_10_target_slates"]
        ),
        "corpus_within_25_winner_slates": int(
            winner_target_census["corpus_within_25_target_slates"]
        ),
    }


def _enforce_review_headlines_v1(observed: Mapping[str, object]) -> None:
    if canonical_json_bytes(observed) != canonical_json_bytes(
        EXPECTED_REVIEW_HEADLINES
    ):
        _fail("computed funnel does not reproduce the adopted deep-review headlines")


def _validate_panel_aggregate_cross_fields_v1(
    *,
    slate_rows: Sequence[Mapping[str, object]],
    population_result: Mapping[str, object],
    exact_results: Sequence[Mapping[str, object]],
    diagnostic_union_result: Mapping[str, object],
    winner_target_census: Mapping[str, object],
    descriptive_attribution: Mapping[str, object],
) -> None:
    """Recompute every aggregate that is recoverable from compact slate rows."""
    corpus_rows = [
        _mapping(row["corpus"], label="cross-field slate corpus")
        for row in slate_rows
    ]
    lineup_count = sum(int(row["lineup_count"]) for row in corpus_rows)
    score_sum = sum(int(row["realized_score_sum_micro"]) for row in corpus_rows)
    oracle_scores = [int(row["corpus_maximum_score_micro"]) for row in corpus_rows]
    nominal_occurrences = sum(
        int(_mapping(row["descriptive_lineage"], label="lineage")[
            "nominal_generation_occurrence_count"
        ])
        for row in slate_rows
    )
    if (
        population_result.get("lineup_count") != lineup_count
        or population_result.get("nominal_generation_occurrence_count")
        != nominal_occurrences
        or population_result.get("unique_yield_decimal")
        != _ratio(lineup_count, nominal_occurrences)
        or population_result.get("realized_score_sum_micro") != score_sum
        or population_result.get("realized_score_mean_micro_decimal")
        != _decimal(Decimal(score_sum) / Decimal(lineup_count))
        or population_result.get("corpus_oracle_score_mean_micro_decimal")
        != _decimal(Decimal(sum(oracle_scores)) / Decimal(len(oracle_scores)))
        or population_result.get("corpus_oracle_score_median_micro_x2")
        != _median_x2(oracle_scores)
        or population_result.get("corpus_oracle_score_minimum_micro")
        != min(oracle_scores)
        or population_result.get("corpus_oracle_score_maximum_micro")
        != max(oracle_scores)
    ):
        _fail("population aggregate differs from compact slate rows")
    population_thresholds = [
        _mapping(raw, label="population panel threshold")
        for raw in _sequence(
            population_result.get("thresholds"), label="population thresholds"
        )
    ]
    if len(population_thresholds) != len(grading.THRESHOLDS_DK):
        _fail("population panel threshold census differs")
    opportunities: dict[int, int] = {}
    for threshold_ordinal, threshold in enumerate(grading.THRESHOLDS_DK):
        slate_cells = [
            _mapping(
                _sequence(row["thresholds"], label="slate corpus thresholds")[
                    threshold_ordinal
                ],
                label="slate corpus threshold",
            )
            for row in corpus_rows
        ]
        count = sum(int(row["population_lineup_count"]) for row in slate_cells)
        opportunity = sum(bool(row["population_available"]) for row in slate_cells)
        opportunities[int(threshold)] = opportunity
        retained = population_thresholds[threshold_ordinal]
        if retained != {
            "threshold_dk": int(threshold),
            "population_lineup_count": count,
            "population_opportunity_slates": opportunity,
            "high_score_density_per_1000_decimal": _decimal(
                Decimal(count) * Decimal(1000) / Decimal(lineup_count)
            ),
        }:
            _fail("population panel threshold differs from compact slate rows")

    for strategy_ordinal, (strategy_id, raw_result) in enumerate(
        zip(STRATEGY_IDS, exact_results, strict=True)
    ):
        result = _mapping(raw_result, label="exact-80 aggregate")
        books = [
            _mapping(
                _sequence(row["exact_80_books"], label="slate books")[
                    strategy_ordinal
                ],
                label="slate exact-80 book",
            )
            for row in slate_rows
        ]
        maxima = [int(row["selected_maximum_score_micro"]) for row in books]
        regrets = [int(row["selector_regret_micro"]) for row in books]
        if (
            result.get("strategy_id") != strategy_id
            or result.get("selected_maximum_score_mean_micro_decimal")
            != _decimal(Decimal(sum(maxima)) / Decimal(len(maxima)))
            or result.get("selector_regret_mean_micro_decimal")
            != _decimal(Decimal(sum(regrets)) / Decimal(len(regrets)))
            or result.get("exact_oracle_capture_slates")
            != sum(bool(row["exact_oracle_captured"]) for row in books)
        ):
            _fail("exact-80 aggregate differs from compact slate books")
        retained_thresholds = _sequence(
            result.get("thresholds"), label="exact-80 aggregate thresholds"
        )
        for threshold_ordinal, threshold in enumerate(grading.THRESHOLDS_DK):
            cells = [
                _mapping(
                    _sequence(book["thresholds"], label="book thresholds")[
                        threshold_ordinal
                    ],
                    label="book threshold",
                )
                for book in books
            ]
            hits = sum(bool(row["selected_hit"]) for row in cells)
            selected = sum(int(row["selected_lineup_count"]) for row in cells)
            probability = sum((
                _fraction_from_row(
                    row["descriptive_random_hit_probability_rational"],
                    label="book random probability",
                )
                for row in cells
            ), Fraction(0, 1))
            retained = _mapping(
                retained_thresholds[threshold_ordinal],
                label="exact-80 aggregate threshold",
            )
            if retained != {
                "threshold_dk": int(threshold),
                "observed_hit_slates": hits,
                "population_opportunity_slates": opportunities[int(threshold)],
                "conditional_conversion_decimal": _ratio(
                    hits, max(1, opportunities[int(threshold)])
                ),
                "selected_qualifying_lineup_count": selected,
                "descriptive_random_draw_count_k": EXACT_ENTRY_COUNT,
                "descriptive_random_expected_hit_slates_rational": {
                    "numerator": str(probability.numerator),
                    "denominator": str(probability.denominator),
                },
                "descriptive_random_expected_hit_slates_decimal": (
                    _fraction_decimal(probability)
                ),
                "additive_lift_over_random_expected_hits_decimal": (
                    _integer_minus_fraction_decimal(hits, probability)
                ),
            }:
                _fail("exact-80 threshold aggregate differs from slate books")

    unions = [
        _mapping(row["diagnostic_union"], label="slate diagnostic union")
        for row in slate_rows
    ]
    union_counts = [int(row["actual_entry_count_k_s"]) for row in unions]
    union_maxima = [int(row["selected_maximum_score_micro"]) for row in unions]
    union_regrets = [int(row["selector_regret_micro"]) for row in unions]
    if (
        diagnostic_union_result.get("total_distinct_lineup_occurrences")
        != sum(union_counts)
        or diagnostic_union_result.get("actual_k_s_minimum") != min(union_counts)
        or diagnostic_union_result.get("actual_k_s_maximum") != max(union_counts)
        or diagnostic_union_result.get("actual_k_s_mean_decimal")
        != _decimal(Decimal(sum(union_counts)) / Decimal(len(union_counts)))
        or diagnostic_union_result.get("selected_maximum_score_mean_micro_decimal")
        != _decimal(Decimal(sum(union_maxima)) / Decimal(len(union_maxima)))
        or diagnostic_union_result.get("selector_regret_mean_micro_decimal")
        != _decimal(Decimal(sum(union_regrets)) / Decimal(len(union_regrets)))
        or diagnostic_union_result.get("exact_oracle_capture_slates")
        != sum(bool(row["exact_oracle_captured"]) for row in unions)
    ):
        _fail("diagnostic-union aggregate differs from compact slate rows")
    retained_union_thresholds = _sequence(
        diagnostic_union_result.get("thresholds"),
        label="diagnostic-union aggregate thresholds",
    )
    for threshold_ordinal, threshold in enumerate(grading.THRESHOLDS_DK):
        cells = [
            _mapping(
                _sequence(union["thresholds"], label="union thresholds")[
                    threshold_ordinal
                ],
                label="union threshold",
            )
            for union in unions
        ]
        hits = sum(bool(row["selected_hit"]) for row in cells)
        selected = sum(int(row["selected_lineup_count"]) for row in cells)
        probability = sum((
            _fraction_from_row(
                row["descriptive_random_hit_probability_rational"],
                label="union random probability",
            )
            for row in cells
        ), Fraction(0, 1))
        retained = _mapping(
            retained_union_thresholds[threshold_ordinal],
            label="diagnostic-union aggregate threshold",
        )
        if retained != {
            "threshold_dk": int(threshold),
            "observed_hit_slates": hits,
            "population_opportunity_slates": opportunities[int(threshold)],
            "conditional_conversion_decimal": _ratio(
                hits, max(1, opportunities[int(threshold)])
            ),
            "selected_qualifying_lineup_count": selected,
            "descriptive_random_draw_law": "actual-slate-specific-k-s",
            "descriptive_random_expected_hit_slates_rational": {
                "numerator": str(probability.numerator),
                "denominator": str(probability.denominator),
            },
            "descriptive_random_expected_hit_slates_decimal": (
                _fraction_decimal(probability)
            ),
            "additive_lift_over_random_expected_hits_decimal": (
                _integer_minus_fraction_decimal(hits, probability)
            ),
        }:
            _fail("diagnostic-union threshold aggregate differs from slate rows")

    winner_rows = [
        _mapping(row["winner_target"], label="slate winner target")
        for row in slate_rows
    ]
    included = [row for row in winner_rows if row["included"] is True]
    gaps = [int(row["corpus_minus_target_micro"]) for row in included]
    expected_winner_summary = {
        "panel_slate_count": len(winner_rows),
        "included_slate_count": len(included),
        "excluded_slate_count": len(winner_rows) - len(included),
        "contest_identity_gap": "contest-id-absent",
        "corpus_reaches_target_slates": sum(gap >= 0 for gap in gaps),
        "corpus_within_10_target_slates": sum(
            gap >= -10 * MICRO_DK_PER_POINT for gap in gaps
        ),
        "corpus_within_25_target_slates": sum(
            gap >= -25 * MICRO_DK_PER_POINT for gap in gaps
        ),
        "corpus_minus_target_mean_micro_decimal": _decimal(
            Decimal(sum(gaps)) / Decimal(len(gaps))
        ),
        "corpus_minus_target_median_micro_x2": _median_x2(gaps),
        "corpus_minus_target_minimum_micro": min(gaps),
        "corpus_minus_target_maximum_micro": max(gaps),
    }
    if any(
        winner_target_census.get(field) != expected
        for field, expected in expected_winner_summary.items()
    ):
        _fail("winner-target aggregate differs from compact slate rows")
    retained_winner_rows = _sequence(
        winner_target_census.get("rows"), label="winner-target census rows"
    )
    expected_winner_rows = [
        {
            "source_ordinal": int(slate_rows[index]["source_ordinal"]),
            "slate_id": str(slate_rows[index]["slate_id"]),
            **winner_rows[index],
        }
        for index in range(len(slate_rows))
    ]
    if canonical_json_bytes(retained_winner_rows) != canonical_json_bytes(
        expected_winner_rows
    ):
        _fail("winner-target census rows differ from compact slate rows")

    for family_field, id_field in (
        ("fill_arms", "fill_arm_id"), ("world_blocks", "world_block_id")
    ):
        retained_rows = [
            _mapping(raw, label=f"aggregate {family_field}")
            for raw in _sequence(
                descriptive_attribution.get(family_field), label=family_field
            )
        ]
        expected_ids = (
            list(batch.PARAMETER_SET_ORDER)
            if family_field == "fill_arms" else list(rw.WORLD_BLOCKS)
        )
        if [str(row[id_field]) for row in retained_rows] != expected_ids:
            _fail(f"descriptive aggregate {family_field} order differs")
        for index, member_id in enumerate(expected_ids):
            source_rows = [
                _mapping(
                    next(
                        raw for raw in _sequence(
                            _mapping(slate["descriptive_lineage"], label="lineage")[
                                family_field
                            ],
                            label=family_field,
                        )
                        if _mapping(raw, label=family_field).get(id_field)
                        == member_id
                    ),
                    label=f"slate {family_field}",
                )
                for slate in slate_rows
            ]
            expected = {id_field: member_id}
            for field in ("lineup_membership_count", "exclusive_lineup_count"):
                expected[field] = sum(int(row[field]) for row in source_rows)
            for field in (
                "threshold_membership_counts", "threshold_exclusive_counts"
            ):
                expected[field] = {
                    str(threshold): sum(
                        int(_mapping(row[field], label=field)[str(threshold)])
                        for row in source_rows
                    )
                    for threshold in grading.THRESHOLDS_DK
                }
            if retained_rows[index] != expected:
                _fail(f"descriptive aggregate {family_field} differs")


def build_no_rescore_funnel_release_v1(
    *,
    attribution_release_root_identity: object,
    winner_registry_authority: object,
    read_exact: ReadExact,
) -> dict[str, object]:
    """Build the compact funnel from terminal retained artifacts only."""
    if not callable(read_exact):
        _fail("funnel exact reader differs")
    root, root_identity = _exact_json(
        attribution_release_root_identity,
        read_exact=read_exact,
        label="terminal attribution release root",
        require_canonical_bytes=True,
    )
    try:
        retained_root = release.validate_attribution_release_structure_v1(root)
    except release.CorpusR6FullUnionAttributionReleaseV1Error as exc:
        raise CorpusR6NoRescoreFunnelV1Error(str(exc)) from exc
    if (
        retained_root.get("target_uri") != root_identity["uri"]
        or retained_root.get("complete") is not True
        or retained_root.get("no_rescore") is not True
        or retained_root.get("every_shard_exact_reopened_and_predecessor_replayed")
        is not True
    ):
        _fail("attribution root is not terminal authority for the funnel")
    descriptors = [
        _mapping(raw, label=f"attribution descriptor[{ordinal}]")
        for ordinal, raw in enumerate(
            _sequence(
                retained_root.get("slate_attribution_objects"),
                label="attribution descriptors",
            )
        )
    ]
    retained_winner_authority = validate_winner_registry_authority_v1(
        winner_registry_authority
    )
    winner_identity = _identity(
        retained_winner_authority["winner_registry_identity"],
        label="winner registry identity",
    )
    allowed_reader = _allowlisted_reader(
        read_exact=read_exact,
        allowed_identities=[
            winner_identity,
            *[
                _identity(
                    row["slate_attribution_identity"],
                    label=f"attribution shard identity[{ordinal}]",
                )
                for ordinal, row in enumerate(descriptors)
            ],
        ],
    )
    winner_registry, reopened_winner_identity = _exact_json(
        winner_identity,
        read_exact=allowed_reader,
        label="winner registry",
        require_canonical_bytes=False,
    )
    winner_targets, winner_source_manifest = _winner_targets_from_registry_v1(
        winner_registry
    )
    if (
        winner_registry.get("winner_registry_sha256")
        != retained_winner_authority["winner_registry_sha256"]
    ):
        _fail("winner registry differs from the higher-level pre-pinned authority")

    slate_rows: list[dict[str, object]] = []
    all_population_scores: list[int] = []
    retained_strategy_registry: list[dict[str, object]] | None = None
    shard_identities: list[dict[str, object]] = []
    for source_ordinal, descriptor in enumerate(descriptors):
        shard, shard_identity = _exact_json(
            descriptor["slate_attribution_identity"],
            read_exact=allowed_reader,
            label=f"attribution shard[{source_ordinal}]",
            require_canonical_bytes=True,
        )
        try:
            retained_shard = attribution.validate_slate_attribution_structure_v1(
                shard
            )
        except attribution.CorpusR6FullUnionAttributionV1Error as exc:
            raise CorpusR6NoRescoreFunnelV1Error(str(exc)) from exc
        slate_id = str(retained_shard["slate_id"])
        row, registry, population_scores = _slate_funnel_v1(
            shard=retained_shard,
            descriptor=descriptor,
            shard_identity=shard_identity,
            winner_target_micro=winner_targets.get(slate_id),
        )
        ordered_registry = [registry[strategy_id] for strategy_id in STRATEGY_IDS]
        if retained_strategy_registry is None:
            retained_strategy_registry = ordered_registry
        elif canonical_json_bytes(retained_strategy_registry) != canonical_json_bytes(
            ordered_registry
        ):
            _fail("final-fit strategy registry differs across slates")
        slate_rows.append(row)
        all_population_scores.extend(population_scores)
        shard_identities.append(shard_identity)
    if (
        retained_strategy_registry is None
        or len(slate_rows) != grading.SOURCE_SLATE_COUNT
        or {str(row["slate_id"]) for row in slate_rows}.intersection(winner_targets)
        != set(winner_targets)
    ):
        _fail("funnel panel or winner-target coverage differs")
    if (
        sum(int(row["corpus"]["lineup_count"]) for row in slate_rows)  # type: ignore[index]
        != retained_root["lineup_count"]
    ):
        _fail("funnel lineup census differs from terminal attribution root")

    (
        population_result,
        exact_results,
        diagnostic_union_result,
        winner_target_census,
        descriptive_attribution,
    ) = _aggregate_panel_v1(
        slate_rows=slate_rows,
        strategy_registry=retained_strategy_registry,
        all_population_scores=all_population_scores,
    )
    observed_headlines = _observed_review_headlines_v1(
        population_result=population_result,
        diagnostic_union_result=diagnostic_union_result,
        winner_target_census=winner_target_census,
    )
    _enforce_review_headlines_v1(observed_headlines)

    body: dict[str, object] = {
        "schema_version": FUNNEL_RELEASE_SCHEMA,
        "derivation_mode": DERIVATION_MODE,
        "predecessors": {
            "attribution_release_root_identity": root_identity,
            "attribution_release_sha256": retained_root[
                "attribution_release_sha256"
            ],
            "grade_completion_identity": retained_root[
                "grade_completion_identity"
            ],
            "persisted_grade_root_identity": retained_root[
                "persisted_grade_root_identity"
            ],
            "panel_freeze_identity": retained_root["panel_freeze_identity"],
            "panel_freeze_sha256": retained_root["panel_freeze_sha256"],
            "attribution_shard_identities": shard_identities,
            "attribution_shard_identities_sha256": canonical_sha256(
                shard_identities
            ),
            "winner_registry_identity": reopened_winner_identity,
            "winner_registry_sha256": winner_registry["winner_registry_sha256"],
            "winner_registry_authority": retained_winner_authority,
            "winner_registry_source_manifest": winner_source_manifest,
        },
        "laws": {
            "final_fit_filter": {
                "scope_ordinal": FINAL_SCOPE_ORDINAL,
                "fit_scope_id": FINAL_FIT_SCOPE_ID,
            },
            "thresholds_dk": list(grading.THRESHOLDS_DK),
            "threshold_operator": ">=",
            "random_book_reference_formula": "1-C(N_s-M_s(t),K)/C(N_s,K)",
            "exact_80_random_draw_count_k": EXACT_ENTRY_COUNT,
            "diagnostic_union_random_draw_count": "actual-slate-specific-k-s",
            "inference_unit": "slate-not-lineup",
            "winner_target_interpretation": (
                "recorded-winner-score-target-not-literal-contest-rank"
            ),
            "descriptive_only": True,
        },
        "source_slate_count": len(slate_rows),
        "strategy_registry": retained_strategy_registry,
        "slate_rows": slate_rows,
        "slate_rows_sha256": canonical_sha256(slate_rows),
        "population_result": population_result,
        "exact_80_strategy_results": exact_results,
        "diagnostic_union_result": diagnostic_union_result,
        "winner_target_census": winner_target_census,
        "descriptive_attribution": descriptive_attribution,
        "headline_reproduction": {
            "deep_review_document_sha256": DEEP_REVIEW_DOCUMENT_SHA256,
            "verified": True,
            "expected": EXPECTED_REVIEW_HEADLINES,
            "observed": observed_headlines,
            "observed_sha256": canonical_sha256(observed_headlines),
        },
        "uses_realized_outcomes": True,
        "no_rescore": True,
        "realized_lineup_scores_from_terminal_attribution_only": True,
        "winner_registry_prepinned_identity_required": True,
        "winner_registry_generation_exact_read": True,
        "winner_registry_internal_self_hash_verified": True,
        "authoritative_reopen_required": True,
        "complete": True,
        **{field: False for field in _FALSE_AUTHORITY_FIELDS},
    }
    body["funnel_release_sha256"] = canonical_sha256(body)
    return validate_no_rescore_funnel_release_v1(body)


def validate_no_rescore_funnel_release_v1(value: object) -> dict[str, object]:
    """Validate structure only; this grants no predecessor/reopen authority."""
    item = _mapping(value, label="no-rescore funnel release")
    _exact_keys(item, _ROOT_FIELDS, label="no-rescore funnel release")
    retained_hash = _digest(
        item.get("funnel_release_sha256"), label="funnel release SHA"
    )
    if canonical_sha256({
        key: nested for key, nested in item.items()
        if key != "funnel_release_sha256"
    }) != retained_hash:
        _fail("funnel release self-hash differs")
    if (
        item.get("schema_version") != FUNNEL_RELEASE_SCHEMA
        or item.get("derivation_mode") != DERIVATION_MODE
        or item.get("source_slate_count") != grading.SOURCE_SLATE_COUNT
        or item.get("uses_realized_outcomes") is not True
        or item.get("no_rescore") is not True
        or item.get("realized_lineup_scores_from_terminal_attribution_only")
        is not True
        or item.get("winner_registry_prepinned_identity_required") is not True
        or item.get("winner_registry_generation_exact_read") is not True
        or item.get("winner_registry_internal_self_hash_verified") is not True
        or item.get("authoritative_reopen_required") is not True
        or item.get("complete") is not True
        or any(item.get(field) is not False for field in _FALSE_AUTHORITY_FIELDS)
    ):
        _fail("funnel release authority law differs")
    predecessors = _mapping(item.get("predecessors"), label="predecessors")
    _exact_keys(predecessors, _PREDECESSOR_FIELDS, label="predecessors")
    for field in (
        "attribution_release_root_identity",
        "grade_completion_identity",
        "persisted_grade_root_identity",
        "panel_freeze_identity",
        "winner_registry_identity",
    ):
        _identity(predecessors.get(field), label=field)
    retained_winner_authority = validate_winner_registry_authority_v1(
        predecessors.get("winner_registry_authority")
    )
    if (
        retained_winner_authority.get("winner_registry_identity")
        != predecessors.get("winner_registry_identity")
        or retained_winner_authority.get("winner_registry_sha256")
        != predecessors.get("winner_registry_sha256")
    ):
        _fail("winner registry predecessor/authority binding differs")
    if predecessors.get("winner_registry_source_manifest") != {
        "canonical_sources": list(ADOPTED_WINNER_CANONICAL_SOURCES),
        "crosscheck_sources": list(ADOPTED_WINNER_CROSSCHECK_SOURCES),
        "excluded_duplicates": list(ADOPTED_WINNER_EXCLUSIONS),
        "provenance_gaps": [
            "contest-id-absent",
            "source-url-absent",
            "capture-time-absent",
        ],
        "winner_registry_sha256": ADOPTED_WINNER_REGISTRY_SHA256,
    }:
        _fail("winner registry predecessor source manifest differs")
    for field in (
        "attribution_release_sha256",
        "panel_freeze_sha256",
        "attribution_shard_identities_sha256",
        "winner_registry_sha256",
    ):
        _digest(predecessors.get(field), label=field)
    shard_identities = _sequence(
        predecessors.get("attribution_shard_identities"),
        label="attribution shard identities",
    )
    if (
        len(shard_identities) != grading.SOURCE_SLATE_COUNT
        or predecessors.get("attribution_shard_identities_sha256")
        != canonical_sha256(shard_identities)
    ):
        _fail("funnel predecessor shard census/hash differs")
    for ordinal, identity in enumerate(shard_identities):
        _identity(identity, label=f"attribution shard identity[{ordinal}]")
    laws = _mapping(item.get("laws"), label="funnel laws")
    _exact_keys(laws, _LAW_FIELDS, label="funnel laws")
    if laws != {
        "final_fit_filter": {
            "scope_ordinal": FINAL_SCOPE_ORDINAL,
            "fit_scope_id": FINAL_FIT_SCOPE_ID,
        },
        "thresholds_dk": list(grading.THRESHOLDS_DK),
        "threshold_operator": ">=",
        "random_book_reference_formula": "1-C(N_s-M_s(t),K)/C(N_s,K)",
        "exact_80_random_draw_count_k": EXACT_ENTRY_COUNT,
        "diagnostic_union_random_draw_count": "actual-slate-specific-k-s",
        "inference_unit": "slate-not-lineup",
        "winner_target_interpretation": (
            "recorded-winner-score-target-not-literal-contest-rank"
        ),
        "descriptive_only": True,
    }:
        _fail("funnel laws differ")
    slate_rows = _sequence(item.get("slate_rows"), label="slate rows")
    if (
        len(slate_rows) != grading.SOURCE_SLATE_COUNT
        or item.get("slate_rows_sha256") != canonical_sha256(slate_rows)
        or [
            _mapping(row, label="slate row").get("source_ordinal")
            for row in slate_rows
        ] != list(range(grading.SOURCE_SLATE_COUNT))
    ):
        _fail("funnel slate-row census/hash/order differs")
    for ordinal, (raw_slate, shard_identity) in enumerate(
        zip(slate_rows, shard_identities, strict=True)
    ):
        slate = _mapping(raw_slate, label=f"slate row[{ordinal}]")
        corpus = _mapping(slate.get("corpus"), label=f"slate corpus[{ordinal}]")
        books = _sequence(
            slate.get("exact_80_books"), label=f"exact-80 books[{ordinal}]"
        )
        union = _mapping(
            slate.get("diagnostic_union"), label=f"diagnostic union[{ordinal}]"
        )
        winner = _mapping(
            slate.get("winner_target"), label=f"winner target[{ordinal}]"
        )
        if (
            slate.get("source_ordinal") != ordinal
            or slate.get("attribution_shard_identity") != shard_identity
            or type(slate.get("slate_id")) is not str
            or _SLATE_ID.fullmatch(str(slate["slate_id"])) is None
            or type(corpus.get("lineup_count")) is not int
            or int(corpus["lineup_count"]) < EXACT_ENTRY_COUNT
            or len(books) != len(STRATEGY_IDS)
            or [
                _mapping(book, label="exact-80 book").get("strategy_id")
                for book in books
            ] != list(STRATEGY_IDS)
            or any(
                _mapping(book, label="exact-80 book").get("entry_count_k")
                != EXACT_ENTRY_COUNT
                for book in books
            )
            or union.get("deployable_book") is not False
            or type(union.get("actual_entry_count_k_s")) is not int
            or not EXACT_ENTRY_COUNT
            <= int(union["actual_entry_count_k_s"])
            <= len(STRATEGY_IDS) * EXACT_ENTRY_COUNT
            or type(winner.get("included")) is not bool
            or winner.get("contest_id") is not None
            or winner.get("contest_identity_reason_code") != "contest-id-absent"
        ):
            _fail(f"funnel slate row[{ordinal}] differs")
        population = int(corpus["lineup_count"])
        corpus_thresholds = _validate_score_threshold_rows_v1(
            corpus.get("thresholds"),
            population=population,
            draw=population,
            label=f"slate corpus thresholds[{ordinal}]",
        )
        if any(
            row["selected_lineup_count"] != row["population_lineup_count"]
            for row in corpus_thresholds
        ):
            _fail(f"slate corpus threshold self-selection[{ordinal}] differs")
        for strategy_ordinal, raw_book in enumerate(books):
            book = _mapping(
                raw_book,
                label=f"slate exact-80 book[{ordinal},{strategy_ordinal}]",
            )
            _validate_score_threshold_rows_v1(
                book.get("thresholds"),
                population=population,
                draw=EXACT_ENTRY_COUNT,
                label=f"slate exact-80 thresholds[{ordinal},{strategy_ordinal}]",
            )
        _validate_score_threshold_rows_v1(
            union.get("thresholds"),
            population=population,
            draw=int(union["actual_entry_count_k_s"]),
            label=f"slate diagnostic-union thresholds[{ordinal}]",
        )
    registry = _sequence(item.get("strategy_registry"), label="strategy registry")
    if (
        len(registry) != len(STRATEGY_IDS)
        or [
            _mapping(row, label="strategy registry row").get("strategy_id")
            for row in registry
        ] != list(STRATEGY_IDS)
    ):
        _fail("funnel strategy registry differs")
    for ordinal, raw_registry in enumerate(registry):
        row = _mapping(raw_registry, label=f"strategy registry[{ordinal}]")
        if (
            frozenset(row)
            != {"strategy_ordinal", "strategy_id", "strategy_sha256"}
            or row.get("strategy_ordinal") != ordinal
            or row.get("strategy_id") != STRATEGY_IDS[ordinal]
        ):
            _fail(f"funnel strategy registry[{ordinal}] differs")
        _digest(row.get("strategy_sha256"), label="strategy SHA")
    exact_results = _sequence(
        item.get("exact_80_strategy_results"), label="exact-80 strategy results"
    )
    if len(exact_results) != len(STRATEGY_IDS):
        _fail("exact-80 strategy result census differs")
    for ordinal, raw_result in enumerate(exact_results):
        result = _mapping(raw_result, label=f"exact-80 strategy result[{ordinal}]")
        thresholds = _sequence(
            result.get("thresholds"), label="exact-80 panel thresholds"
        )
        if (
            result.get("strategy_ordinal") != ordinal
            or result.get("strategy_id") != STRATEGY_IDS[ordinal]
            or result.get("entry_count_k") != EXACT_ENTRY_COUNT
            or result.get("book_semantics")
            != "one-deployable-exact-80-book-per-slate"
            or result.get("source_slate_count") != grading.SOURCE_SLATE_COUNT
            or len(thresholds) != len(grading.THRESHOLDS_DK)
            or [
                _mapping(row, label="exact-80 threshold").get("threshold_dk")
                for row in thresholds
            ] != list(grading.THRESHOLDS_DK)
            or any(
                _mapping(row, label="exact-80 threshold").get(
                    "descriptive_random_draw_count_k"
                ) != EXACT_ENTRY_COUNT
                for row in thresholds
            )
        ):
            _fail(f"exact-80 strategy result[{ordinal}] differs")
    population_result = _mapping(
        item.get("population_result"), label="population result"
    )
    diagnostic_union_result = _mapping(
        item.get("diagnostic_union_result"), label="diagnostic union result"
    )
    winner_target_census = _mapping(
        item.get("winner_target_census"), label="winner target census"
    )
    descriptive_attribution = _mapping(
        item.get("descriptive_attribution"), label="descriptive attribution"
    )
    if (
        diagnostic_union_result.get("deployable_book") is not False
        or diagnostic_union_result.get("interpretation")
        != "diagnostic-union-of-eight-alternative-exact-80-books"
        or descriptive_attribution.get("interpretation")
        != "descriptive-only-not-causal-allocation-evidence"
        or descriptive_attribution.get("exact_generation_occurrence_rows_available")
        is not False
        or winner_target_census.get("included_slate_count") != 51
        or winner_target_census.get("excluded_slate_count") != 3
        or len(_sequence(winner_target_census.get("rows"), label="winner rows"))
        != grading.SOURCE_SLATE_COUNT
    ):
        _fail("funnel aggregate interpretation/census differs")
    _validate_panel_aggregate_cross_fields_v1(
        slate_rows=slate_rows,
        population_result=population_result,
        exact_results=exact_results,
        diagnostic_union_result=diagnostic_union_result,
        winner_target_census=winner_target_census,
        descriptive_attribution=descriptive_attribution,
    )
    recomputed_headlines = _observed_review_headlines_v1(
        population_result=population_result,
        diagnostic_union_result=diagnostic_union_result,
        winner_target_census=winner_target_census,
    )
    headline = _mapping(
        item.get("headline_reproduction"), label="headline reproduction"
    )
    if (
        headline.get("deep_review_document_sha256")
        != DEEP_REVIEW_DOCUMENT_SHA256
        or headline.get("verified") is not True
        or headline.get("expected") != EXPECTED_REVIEW_HEADLINES
        or headline.get("observed") != recomputed_headlines
        or recomputed_headlines != EXPECTED_REVIEW_HEADLINES
        or headline.get("observed_sha256")
        != canonical_sha256(recomputed_headlines)
    ):
        _fail("funnel headline reproduction differs")
    return item


def reopen_no_rescore_funnel_release_v1(
    funnel_release_identity: object,
    *,
    attribution_release_root_identity: object,
    winner_registry_authority: object,
    read_exact: ReadExact,
) -> tuple[dict[str, object], dict[str, object]]:
    """Authoritatively exact-open and byte-replay the complete derivation."""
    observed, reopened_identity = _exact_json(
        funnel_release_identity,
        read_exact=read_exact,
        label="no-rescore funnel release",
        require_canonical_bytes=True,
    )
    retained = validate_no_rescore_funnel_release_v1(observed)
    expected = build_no_rescore_funnel_release_v1(
        attribution_release_root_identity=attribution_release_root_identity,
        winner_registry_authority=winner_registry_authority,
        read_exact=read_exact,
    )
    if canonical_json_bytes(retained) != canonical_json_bytes(expected):
        _fail("funnel release canonical predecessor replay differs")
    return expected, reopened_identity


__all__ = [
    "ADOPTED_WINNER_REGISTRY_AUTHORITY_SHA256",
    "ADOPTED_WINNER_REGISTRY_IDENTITY",
    "ADOPTED_WINNER_REGISTRY_SHA256",
    "CorpusR6NoRescoreFunnelV1Error",
    "DERIVATION_MODE",
    "EXPECTED_REVIEW_HEADLINES",
    "FUNNEL_RELEASE_SCHEMA",
    "STRATEGY_IDS",
    "build_no_rescore_funnel_release_v1",
    "canonical_json_bytes",
    "canonical_sha256",
    "reopen_no_rescore_funnel_release_v1",
    "validate_no_rescore_funnel_release_v1",
    "validate_winner_registry_authority_v1",
]
