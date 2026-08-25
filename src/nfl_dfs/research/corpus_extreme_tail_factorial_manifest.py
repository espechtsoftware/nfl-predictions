"""Pure freeze contract for the 53-slate pre-Week-1 tail factorial.

The builder in this module does not generate candidates, score matrices,
select lineups, read outcomes, access GCS, or publish anything.  It turns one
exact, generation-pinned 54-slate source catalog into an immutable execution
manifest after mechanically excluding the known four-origin 2025 Week-1
recovery slate.  The resulting contract binds the shared population/matrix
work and every outcome-blind selection cell before any experiment effect is
available.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
import re
from typing import Final

from nfl_dfs.inference import production_policy as production
from nfl_dfs.research import corpus_extreme_tail_preweek_additions as additions
from nfl_dfs.research import corpus_extreme_tail_preweek_selectors as preweek
from nfl_dfs.research import corpus_extreme_tail_retrieval_suite as suite
from nfl_dfs.research import corpus_extreme_tail_scenario_ticket as scenario
from nfl_dfs.research import corpus_extreme_tail_support_switch as support
from nfl_dfs.research import corpus_parametric_batch as batch
from nfl_dfs.research import corpus_retrieval_engine as retrieval
from nfl_dfs.research import (
    corpus_retrieval_v2_implementation_contract as retrieval_v2_implementation,
)
from nfl_dfs.research import residual_world_columns as rw


FACTORIAL_EXECUTION_MANIFEST_SCHEMA: Final = (
    "foundry-extreme-tail-factorial-execution-manifest/v1"
)
SOURCE_CATALOG_SCHEMA: Final = "foundry-factorial-source-catalog/v1"
SOURCE_MEMBERSHIP_ACCEPTANCE_SCHEMA: Final = (
    "foundry-factorial-source-membership-acceptance/v1"
)
PUBLICATION_MODE: Final = "create_once"
PROTOCOL_DOCUMENT: Final = (
    "reports/2026-08-25-pre-week1-historical-experiment-matrix.md"
)
PROTOCOL_SHA256: Final = (
    "4cd61f51617322bcafb3e2a867332ed4e35484073aa47c3d9891339fd493f338"
)

SOURCE_SLATE_COUNT: Final = 54
FACTORIAL_SLATE_COUNT: Final = 53
EXCLUDED_SOURCE_ORDINAL: Final = 36
EXCLUDED_SLATE_ID: Final = "2025-w01"
EVALUATION_BLOCKS: Final = ("R0", "R1", "R2", "R3", "R4")
RECOVERY_AVAILABLE_BLOCKS: Final = ("R0", "R1", "R2", "R4")
WORLDS_PER_BLOCK: Final = 10_000
ENTRY_BUDGETS: Final = (4, 14, 80)
RANKING_DEPTH: Final = 80
RANKING_PREFIX_LAW: Final = "exact-prefix-of-one-deterministic-rank-80"
P0_GENERATION_ENVIRONMENT_SHA256: Final = (
    "7a638d185a5cffdbbd47a336c970a5c211d4c86c08e590fc4015b8d385cd9b51"
)
PB_GENERATION_ENVIRONMENT_SHA256: Final = (
    "5af2b68289bd2cbfc3e461bd3cd5fd8a72058c9da2caa664795589424f3815a4"
)

POPULATION_IDS: Final = ("P0-incumbent-native", "PB-frozen-all-boom")
ORIGIN_MASK_IDS: Final = ("K5", "K20")
PRIMARY_RETRIEVAL_IDS: Final = (
    "coverage-194-v1",
    "frozen-census-support-switch-ge-230/v1",
)
RAW_T230_RETRIEVAL_IDS: Final = (
    "coverage-ge-230-v1",
    "bounded-tail-ladder-ge-210-250-v1",
    "block-robust-bounded-tail-ge-210-250-v1",
    "individual-ge-230-rank-v1",
)
V2_ADDITIONAL_COMPARATOR_IDS: Final = (
    "strict-200-coverage-v1",
    "tail-ladder-200-210-220-v1",
    "mean-score-v1",
    "expected-max-v1",
    "block-supported-tail-ladder-v1",
    "regime-robust-ladder-v1",
)
PREWEEK_ADDITION_IDS: Final = (
    "convex-excess-expected-max-ge-200-v1",
    "block-supported-bounded-tail-ge-210-250-v1",
    "maximum-coverage-ge-230-oracle-diagnostic-v1",
)
SECONDARY_RETRIEVAL_IDS: Final = (
    *RAW_T230_RETRIEVAL_IDS,
    "support-switched-event-component-tickets-ge-230-v1",
    "individual-training-maximum-rank-v1",
    "training-hit-ge-230-admission-v1",
    *V2_ADDITIONAL_COMPARATOR_IDS,
    *PREWEEK_ADDITION_IDS,
)
RETRIEVAL_IDS: Final = (
    PRIMARY_RETRIEVAL_IDS[0],
    *RAW_T230_RETRIEVAL_IDS,
    PRIMARY_RETRIEVAL_IDS[1],
    *SECONDARY_RETRIEVAL_IDS[len(RAW_T230_RETRIEVAL_IDS) :],
)

_RAW_SELECTOR_IMPLEMENTATION_SHA256: Final = (
    "0ede95f034186bdf382af8a9c87c311b83799c5e9609ec11d2cffb3c2114ce4b"
)
_RAW_T230_STRATEGY_SHA256_BY_ID: Final = {
    "coverage-ge-230-v1": (
        "c43598db8dc2b081158f0660f8edc1ccae4ce1c58ff6a468036c6dbc089fa965"
    ),
    "bounded-tail-ladder-ge-210-250-v1": (
        "e769cadb1a3189d736784225647d9a7342ab4ea25bd2b55f632dd0ec8de254fa"
    ),
    "block-robust-bounded-tail-ge-210-250-v1": (
        "b3c4bf6ea5e09446e0fff6b901412c7e9370a1b0e1ac0053d864eaef36f958d9"
    ),
    "individual-ge-230-rank-v1": (
        "d267f5401fd234ba962d6d350d4dac2716a8e3c9e789a2e7c8a91a79cd9a1aee"
    ),
}
_PREWEEK_SELECTOR_IMPLEMENTATION_SHA256: Final = (
    "bc54abd13c4a5ecd5966dcc5e1b78afb06028850865517bde754507ccc40e94f"
)
_V2_COMPARATOR_IMPLEMENTATION_SHA256: Final = (
    "01f62c080451f6d090da782c47474e86ae8302a1a57df698d2df16fb5dcffac7"
)
_COVERAGE_194_STRATEGY_SHA256: Final = (
    "1e1e6a11149ca1c8c9babd183b85adb2ce27d0f976ca863b43768aa3dab0433f"
)
_V2_ADDITIONAL_STRATEGY_SHA256_BY_ID: Final = {
    "strict-200-coverage-v1": (
        "9689bb11de4616e4a6295ae0a5b0ec30aa174097f1965867fdc08d7b2e7d02de"
    ),
    "tail-ladder-200-210-220-v1": (
        "5561d663cdc2ec8f928ddf5a44889f16e3c23cdd264f4c8fef7925547aa527ea"
    ),
    "mean-score-v1": (
        "5c880aeca7c8ec3386a9d44b111937fada857f569cb324dd2163987b333654c6"
    ),
    "expected-max-v1": (
        "ad94b80a0ea61d1c58f64f825f00f0d0fea47f36158a239c29382836ff2cb780"
    ),
    "block-supported-tail-ladder-v1": (
        "1ae24780c211a329e8a9867e5dec39630a7efcc640deba9e05561f6a8c98668b"
    ),
    "regime-robust-ladder-v1": (
        "125610a3fda4c230bacd44f1778e43fe03905a504d55ec6fe4c424c0cbbd0e7b"
    ),
}
_PREWEEK_STRATEGY_SHA256_BY_ID: Final = {
    "individual-training-maximum-rank-v1": (
        "7d0c3458accdd91e96aa8bb7513fd333e0804ae846216e823242d839cbc177c2"
    ),
    "training-hit-ge-230-admission-v1": (
        "4f5ffe15d0df57f245426113f48c63b0e1abee68dd4a903b94ff6e9fe0728fda"
    ),
}
_PREWEEK_ADDITION_IMPLEMENTATION_SHA256: Final = (
    "1c94e9635d6038f629c40ce81cc2b3b3ed4fcad600e4832a0f231c5c9c19403d"
)
_PREWEEK_ADDITION_STRATEGY_SHA256_BY_ID: Final = {
    "convex-excess-expected-max-ge-200-v1": (
        "189dc6986c7d70b8315f9e41cb1fe5c6fce35c54f2756729254a0e1614dd1082"
    ),
    "block-supported-bounded-tail-ge-210-250-v1": (
        "a2070561cfb0a2c2c049b27d5e5ff71682a87d3568254b09ebf987a58d775954"
    ),
    "maximum-coverage-ge-230-oracle-diagnostic-v1": (
        "b40a7ed84af58f62ba1c4d814bcaf6f360ffb09e286963d348790f9f007b6b6e"
    ),
}
_SUPPORT_SWITCH_STRATEGY_CONTRACT_SHA256: Final = (
    "e44525130cdd119d441178da9f2a003876f63d328b44f1730b48064ef61d56ab"
)
_SUPPORT_SWITCH_IMPLEMENTATION_CONTRACT_SHA256: Final = (
    "73f53f8b3e7b8d9ec6c661de16e5c171917526858bc1a358a555fcc78085bd30"
)
_SCENARIO_COMBINED_CONTRACT_SHA256: Final = (
    "026d6b94f9867fc01cd5e17acec6539b963a9914d17c894c815e96ee3106cd91"
)
_SCENARIO_STRATEGY_CONTRACT_SHA256: Final = (
    "e39218d78f697d08630363610da96d0a395bebdce770522ef476adc8eeab145b"
)

# The registered five plus the fifteen B1 prospective volume-shadow pairs.
# They are literals here so changing the production policy coherently cannot
# silently redefine the historical experiment.
_FROZEN_SEED_PAIRS: Final = (
    (0, 7331),
    (1137260708, 2690847602),
    (2875959182, 1630284992),
    (253722715, 3374646876),
    (1643280042, 3977633467),
    (2786141412, 2801677210),
    (1461353386, 1586091810),
    (137204844, 2046775861),
    (2184743543, 3320854134),
    (651833611, 3089304063),
    (1935613362, 3432329768),
    (31867868, 2977492966),
    (1988904477, 4192316077),
    (1852762881, 2368290637),
    (4006641982, 2226041783),
    (1093906274, 1859951038),
    (135109598, 3661127064),
    (3815695926, 1138144331),
    (3020163036, 3089093104),
    (186549143, 564317351),
)

_EXPECTED_CELL_ROWS: Final = (
    (
        "H01-P0-K5-R194",
        "P0-incumbent-native",
        "K5",
        "coverage-194-v1",
        "historical-factorial-baseline",
    ),
    (
        "H02-P0-K5-T230",
        "P0-incumbent-native",
        "K5",
        "frozen-census-support-switch-ge-230/v1",
        "retrieval-effect-at-incumbent-volume",
    ),
    (
        "H03-P0-K20-R194",
        "P0-incumbent-native",
        "K20",
        "coverage-194-v1",
        "volume-effect-under-incumbent-retrieval",
    ),
    (
        "H04-P0-K20-T230",
        "P0-incumbent-native",
        "K20",
        "frozen-census-support-switch-ge-230/v1",
        "incumbent-population-volume-by-retrieval",
    ),
    (
        "H05-PB-K5-R194",
        "PB-frozen-all-boom",
        "K5",
        "coverage-194-v1",
        "fill-effect-at-incumbent-volume-and-retrieval",
    ),
    (
        "H06-PB-K5-T230",
        "PB-frozen-all-boom",
        "K5",
        "frozen-census-support-switch-ge-230/v1",
        "five-origin-fill-by-retrieval-conversion",
    ),
    (
        "H07-PB-K20-R194",
        "PB-frozen-all-boom",
        "K20",
        "coverage-194-v1",
        "fill-by-volume-under-incumbent-retrieval",
    ),
    (
        "H08-PB-K20-T230",
        "PB-frozen-all-boom",
        "K20",
        "frozen-census-support-switch-ge-230/v1",
        "aggressive-joint-cell-and-three-way-interaction",
    ),
)

GLOBAL_ROSTER_FILENAME: Final = "factorial-global-rosters-v1.json"
PROVENANCE_FILENAME: Final = "factorial-occurrence-provenance-v1.json"
SCORE_MATRIX_FILENAME: Final = "factorial-ordinary-r-score-matrix-v1.npz"
LINEAGE_MASKS_FILENAME: Final = "factorial-lineage-masks-v1.json"
RESULT_FILENAME: Final = "factorial-slate-analysis-v1.json"
ACCEPTANCE_FILENAME: Final = "factorial-slate-acceptance-v1.json"

_SHA256: Final = re.compile(r"[0-9a-f]{64}")
_COMMIT: Final = re.compile(r"[0-9a-f]{40}")
_CANONICAL_ID: Final = re.compile(r"[a-z0-9][a-z0-9._:-]*")
_FALSE_AUTHORITY_FIELDS: Final = (
    "automatic_retry_licensed",
    "uses_realized_outcomes",
    "historical_scoring_licensed",
    "corpus_fill_licensed",
    "graph_mutation_licensed",
    "live_policy_access_licensed",
    "production_change_licensed",
    "realized_grade_open_authority",
    "analytical_authority",
    "r6_freeze_authority",
    "promotion_authority",
    "decision_authority",
)
_SOURCE_MEMBER_KEYS: Final = frozenset({
    "source_ordinal",
    "slate_id",
    "season",
    "week",
    "reconstruction_source_identity",
    "ordinary_r_blocks",
})
_SOURCE_BLOCK_KEYS: Final = frozenset({
    "block_id",
    "world_count",
    "world_identity",
})
_SOURCE_MEMBERSHIP_KEYS: Final = frozenset({
    "source_ordinal",
    "slate_id",
    "source_member_sha256",
    "reconstruction_source_identity",
    "ordinary_r_blocks_sha256",
})
_SOURCE_ACCEPTANCE_KEYS: Final = frozenset({
    "schema_version",
    "catalog_id",
    "source_member_count",
    "source_members_sha256",
    "source_membership_sha256",
    "exact_ordered_grid_complete",
    "all_source_objects_generation_pinned",
    "accepted",
    "uses_realized_outcomes",
})
_SOURCE_CATALOG_KEYS: Final = frozenset({
    "schema_version",
    "publication_mode",
    "catalog_id",
    "source_member_count",
    "source_members",
    "source_members_sha256",
    "source_membership",
    "source_membership_sha256",
    "membership_acceptance",
    "membership_acceptance_sha256",
    "uses_realized_outcomes",
    "source_membership_authority",
    "source_catalog_sha256",
})
_FACTORIAL_SLATE_KEYS: Final = frozenset({
    "factorial_slate_ordinal",
    "source_ordinal",
    "slate_id",
    "season",
    "week",
    "source_member_sha256",
    "reconstruction_source_identity",
    "ordinary_r_blocks",
    "shared_output_uris",
})
_OUTPUT_KEYS: Final = frozenset({
    "global_roster_table_uri",
    "occurrence_provenance_uri",
    "ordinary_r_score_matrix_uri",
    "cell_lineage_masks_uri",
    "slate_result_uri",
    "slate_acceptance_uri",
})
_MANIFEST_KEYS: Final = frozenset({
    "schema_version",
    "publication_mode",
    "manifest_id",
    "protocol_document",
    "protocol_sha256",
    "source_catalog_identity",
    "source_catalog_id",
    "source_catalog_sha256",
    "source_membership_sha256",
    "source_membership_acceptance_sha256",
    "source_catalog_contract",
    "factorial_slate_count",
    "factorial_slates",
    "factorial_slates_sha256",
    "ordinary_r_evaluation_contract",
    "candidate_origin_registry",
    "candidate_origin_registry_sha256",
    "population_registry",
    "population_registry_sha256",
    "candidate_origin_masks",
    "candidate_origin_masks_sha256",
    "candidate_origin_cross_fit_contract",
    "retrieval_contract",
    "factorial_cell_registry",
    "factorial_cell_registry_sha256",
    "shared_artifact_contract",
    "p0_generation_environment",
    "p0_generation_environment_sha256",
    "pb_generation_environment_sha256",
    "entry_budgets",
    "ranking_depth",
    "ranking_prefix_law",
    "controlled_grade_boundary",
    "source_commit_sha",
    "immutable_image",
    "output_prefix",
    *_FALSE_AUTHORITY_FIELDS,
    "execution_manifest_sha256",
})


class CorpusExtremeTailFactorialManifestError(ValueError):
    """The factorial manifest differs from its frozen outcome-blind law."""


def _fail(message: str) -> None:
    raise CorpusExtremeTailFactorialManifestError(message)


def _mapping(value: object, *, label: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping) or any(type(key) is not str for key in value):
        _fail(f"{label} must be a string-keyed object")
    return value


def _sequence(value: object, *, label: str) -> Sequence[object]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        _fail(f"{label} must be an array")
    return value


def _exact_keys(
    value: Mapping[str, object], expected: frozenset[str], *, label: str
) -> None:
    actual = frozenset(value)
    if actual != expected:
        _fail(
            f"{label} fields differ; missing={sorted(expected - actual)}, "
            f"unknown={sorted(actual - expected)}"
        )


def _exact_int(value: object, *, label: str, minimum: int = 0) -> int:
    if type(value) is not int or int(value) < minimum:
        _fail(f"{label} must be an integer >= {minimum}")
    return int(value)


def _sha256(value: object, *, label: str) -> str:
    if type(value) is not str or _SHA256.fullmatch(value) is None:
        _fail(f"{label} must be one lowercase SHA-256")
    return value


def _canonical_id(value: object, *, label: str) -> str:
    if type(value) is not str or _CANONICAL_ID.fullmatch(value) is None:
        _fail(f"{label} must be one canonical identifier")
    return value


def _identity(value: object, *, label: str) -> dict[str, object]:
    try:
        return batch.normalize_object_identity(value, label=label)
    except Exception as exc:
        raise CorpusExtremeTailFactorialManifestError(
            f"{label} is not a generation-pinned object identity"
        ) from exc


def _identity_key(value: Mapping[str, object]) -> tuple[str, str, str, int]:
    return (
        str(value["uri"]),
        str(value["generation"]),
        str(value["sha256"]),
        int(value["bytes"]),
    )


def _image(value: object) -> dict[str, str]:
    try:
        return batch.normalize_image_identity(value, label="immutable image")
    except Exception as exc:
        raise CorpusExtremeTailFactorialManifestError(
            "immutable image must be digest-pinned"
        ) from exc


def _output_prefix(value: object) -> str:
    if type(value) is not str or not value.startswith("gs://"):
        _fail("output prefix must be a GCS prefix")
    tail = value.removeprefix("gs://")
    bucket_name, separator, object_name = tail.partition("/")
    if (
        not bucket_name
        or not separator
        or not object_name
        or not value.endswith("/")
        or "//" in object_name
        or "\\" in value
        or any(character.isspace() for character in value)
        or any(character in value for character in "?#")
    ):
        _fail("output prefix is not canonical")
    segments = object_name.split("/")[:-1]
    if not segments or any(segment in {"", ".", ".."} for segment in segments):
        _fail("output prefix is not canonical")
    return value


def _false_authorities(value: Mapping[str, object], *, label: str) -> None:
    for field in _FALSE_AUTHORITY_FIELDS:
        if value.get(field) is not False:
            _fail(f"{label}.{field} must be false")


def _validate_self_hash(
    value: Mapping[str, object], *, field: str, label: str
) -> None:
    retained = _sha256(value.get(field), label=f"{label}.{field}")
    body = {key: item for key, item in value.items() if key != field}
    if batch.canonical_sha256(body) != retained:
        _fail(f"{label} self-hash differs")


def _expected_source_grid() -> tuple[tuple[int, int, str], ...]:
    return tuple(
        (season, week, f"{season}-w{week:02d}")
        for season in (2023, 2024, 2025)
        for week in range(1, 19)
    )


def _origin_registry() -> list[dict[str, object]]:
    return [
        {
            "origin_ordinal": ordinal,
            "origin_id": f"R{ordinal}",
            "projection_seed": projection_seed,
            "role_seed": role_seed,
            "origin_class": (
                "registered-incumbent-five"
                if ordinal < 5
                else "prospective-volume-shadow-extra-fifteen"
            ),
            "candidate_discovery_only": ordinal >= 5,
            "evaluation_block": f"R{ordinal}" if ordinal < 5 else None,
        }
        for ordinal, (projection_seed, role_seed) in enumerate(
            _FROZEN_SEED_PAIRS
        )
    ]


def frozen_extreme_tail_factorial_p0_environment_v1() -> dict[str, str]:
    """Return the complete explicit incumbent environment for generation."""
    environment = production.ClassicProductionPolicy().engine_environment()
    if "BOOM_UNIQUE_FILL" in environment:
        _fail("incumbent policy unexpectedly materializes BOOM_UNIQUE_FILL")
    environment["BOOM_UNIQUE_FILL"] = "0"
    if any(
        type(key) is not str or type(value) is not str
        for key, value in environment.items()
    ):
        _fail("incumbent generation environment is not string-to-string")
    return dict(sorted(environment.items()))


def _validated_p0_environment(
    value: object, *, retained_sha256: object
) -> tuple[dict[str, str], str]:
    raw = _mapping(value, label="P0 generation environment")
    if any(type(item) is not str for item in raw.values()):
        _fail("P0 generation environment values must all be strings")
    normalized = dict(sorted((str(key), str(item)) for key, item in raw.items()))
    expected = frozen_extreme_tail_factorial_p0_environment_v1()
    expected_hash = batch.canonical_sha256(expected)
    supplied_hash = _sha256(
        retained_sha256, label="P0 generation environment SHA-256"
    )
    if (
        supplied_hash != expected_hash
        or expected_hash != P0_GENERATION_ENVIRONMENT_SHA256
        or normalized != expected
    ):
        _fail("P0 generation environment differs from the complete frozen law")
    return normalized, supplied_hash


def _validate_frozen_dependency_constants() -> None:
    """Fail if code dependencies could silently redefine the protocol."""
    policy = production.ClassicProductionPolicy()
    imported_pairs = (
        tuple(policy.multiseed_seed_pairs)
        + tuple(policy.multiseed_volume_extra_seed_pairs)
    )
    raw_strategies = suite.frozen_extreme_tail_strategies_v1()
    raw_ids = tuple(str(row.get("strategy_id")) for row in raw_strategies)
    p0_environment = frozen_extreme_tail_factorial_p0_environment_v1()
    pb_environment = dict(p0_environment)
    pb_environment.update({
        "CAND_MULT": "0",
        "N_BOOM": "200",
        "BOOM_UNIQUE_FILL": "1",
    })
    pb_environment = dict(sorted(pb_environment.items()))
    if (
        SOURCE_SLATE_COUNT != 54
        or FACTORIAL_SLATE_COUNT != 53
        or EXCLUDED_SOURCE_ORDINAL != 36
        or EXCLUDED_SLATE_ID != "2025-w01"
        or EVALUATION_BLOCKS != ("R0", "R1", "R2", "R3", "R4")
        or RECOVERY_AVAILABLE_BLOCKS != ("R0", "R1", "R2", "R4")
        or WORLDS_PER_BLOCK != 10_000
        or ENTRY_BUDGETS != (4, 14, 80)
        or RANKING_DEPTH != 80
        or len(_expected_source_grid()) != SOURCE_SLATE_COUNT
        or len(_FROZEN_SEED_PAIRS) != 20
        or _FROZEN_SEED_PAIRS
        != (
            (0, 7331),
            (1137260708, 2690847602),
            (2875959182, 1630284992),
            (253722715, 3374646876),
            (1643280042, 3977633467),
            (2786141412, 2801677210),
            (1461353386, 1586091810),
            (137204844, 2046775861),
            (2184743543, 3320854134),
            (651833611, 3089304063),
            (1935613362, 3432329768),
            (31867868, 2977492966),
            (1988904477, 4192316077),
            (1852762881, 2368290637),
            (4006641982, 2226041783),
            (1093906274, 1859951038),
            (135109598, 3661127064),
            (3815695926, 1138144331),
            (3020163036, 3089093104),
            (186549143, 564317351),
        )
        or POPULATION_IDS
        != ("P0-incumbent-native", "PB-frozen-all-boom")
        or ORIGIN_MASK_IDS != ("K5", "K20")
        or PRIMARY_RETRIEVAL_IDS
        != (
            "coverage-194-v1",
            "frozen-census-support-switch-ge-230/v1",
        )
        or RAW_T230_RETRIEVAL_IDS
        != (
            "coverage-ge-230-v1",
            "bounded-tail-ladder-ge-210-250-v1",
            "block-robust-bounded-tail-ge-210-250-v1",
            "individual-ge-230-rank-v1",
        )
        or V2_ADDITIONAL_COMPARATOR_IDS
        != (
            "strict-200-coverage-v1",
            "tail-ladder-200-210-220-v1",
            "mean-score-v1",
            "expected-max-v1",
            "block-supported-tail-ladder-v1",
            "regime-robust-ladder-v1",
        )
        or PREWEEK_ADDITION_IDS
        != (
            "convex-excess-expected-max-ge-200-v1",
            "block-supported-bounded-tail-ge-210-250-v1",
            "maximum-coverage-ge-230-oracle-diagnostic-v1",
        )
        or len(RETRIEVAL_IDS) != 18
        or imported_pairs != _FROZEN_SEED_PAIRS
        or tuple(policy.multiseed_seed_pairs) != _FROZEN_SEED_PAIRS[:5]
        or policy.candidate_multiple != 2
        or policy.n_boom != 40
        or policy.n_role != 12
        or policy.n_ce != 0
        or batch.canonical_sha256(p0_environment)
        != P0_GENERATION_ENVIRONMENT_SHA256
        or batch.canonical_sha256(pb_environment)
        != PB_GENERATION_ENVIRONMENT_SHA256
        or tuple(rw.WORLD_BLOCKS) != EVALUATION_BLOCKS
        or rw.WORLDS_PER_BLOCK != WORLDS_PER_BLOCK
        or tuple(suite.ENTRY_BUDGETS) != ENTRY_BUDGETS
        or suite.RANKING_DEPTH != RANKING_DEPTH
        or tuple(suite.TAIL_RUNGS)
        != (
            (210.0, ">=", 1),
            (220.0, ">=", 2),
            (230.0, ">=", 4),
            (240.0, ">=", 8),
            (250.0, ">=", 16),
        )
        or raw_ids != RAW_T230_RETRIEVAL_IDS
        or support.POLICY_LAW_ID != PRIMARY_RETRIEVAL_IDS[1]
        or support.LITERAL_COVERAGE_STRATEGY_ID != RAW_T230_RETRIEVAL_IDS[0]
        or support.FALLBACK_STRATEGY_ID != RAW_T230_RETRIEVAL_IDS[2]
        or support.FOLD_MINIMUM_OPPORTUNITY_WORLDS != 100
        or support.FINAL_MINIMUM_OPPORTUNITY_WORLDS != 125
        or tuple(preweek.ENTRY_BUDGETS) != ENTRY_BUDGETS
        or preweek.RANKING_DEPTH != RANKING_DEPTH
        or tuple(additions.ENTRY_BUDGETS) != ENTRY_BUDGETS
        or additions.RANKING_DEPTH != RANKING_DEPTH
        or tuple(scenario.ENTRY_BUDGETS) != ENTRY_BUDGETS
        or scenario.RANKING_DEPTH != RANKING_DEPTH
        or scenario.STRATEGY_ID
        != "support-switched-event-component-tickets-ge-230-v1"
    ):
        _fail("frozen dependency constants drifted from the factorial protocol")


def _source_members(
    value: object,
) -> tuple[list[dict[str, object]], dict[str, object]]:
    rows = _sequence(value, label="source members")
    if len(rows) != SOURCE_SLATE_COUNT:
        _fail("source catalog must contain exactly 54 ordered slates")
    expected_grid = _expected_source_grid()
    normalized: list[dict[str, object]] = []
    object_identities: set[tuple[str, str, str, int]] = set()
    for source_ordinal, raw_row in enumerate(rows):
        row = _mapping(raw_row, label=f"source member[{source_ordinal}]")
        _exact_keys(
            row,
            _SOURCE_MEMBER_KEYS,
            label=f"source member[{source_ordinal}]",
        )
        season, week, slate_id = expected_grid[source_ordinal]
        retained_ordinal = _exact_int(
            row.get("source_ordinal"),
            label=f"source member[{source_ordinal}] source ordinal",
        )
        retained_season = _exact_int(
            row.get("season"),
            label=f"source member[{source_ordinal}] season",
        )
        retained_week = _exact_int(
            row.get("week"),
            label=f"source member[{source_ordinal}] week",
            minimum=1,
        )
        if (
            retained_ordinal != source_ordinal
            or retained_season != season
            or retained_week != week
            or row.get("slate_id") != slate_id
        ):
            _fail("source members differ from the exact 2023--2025 slate order")
        source_identity = _identity(
            row.get("reconstruction_source_identity"),
            label=f"source member[{source_ordinal}] reconstruction source",
        )
        source_key = _identity_key(source_identity)
        if source_key in object_identities:
            _fail("source object identities repeat")
        object_identities.add(source_key)
        raw_blocks = _sequence(
            row.get("ordinary_r_blocks"),
            label=f"source member[{source_ordinal}] ordinary-R blocks",
        )
        expected_blocks = (
            RECOVERY_AVAILABLE_BLOCKS
            if source_ordinal == EXCLUDED_SOURCE_ORDINAL
            else EVALUATION_BLOCKS
        )
        if len(raw_blocks) != len(expected_blocks):
            _fail("source member ordinary-R block count differs")
        blocks: list[dict[str, object]] = []
        for block_ordinal, (raw_block, block_id) in enumerate(
            zip(raw_blocks, expected_blocks, strict=True)
        ):
            block = _mapping(
                raw_block,
                label=(
                    f"source member[{source_ordinal}] "
                    f"ordinary-R block[{block_ordinal}]"
                ),
            )
            _exact_keys(
                block,
                _SOURCE_BLOCK_KEYS,
                label=f"source member[{source_ordinal}] ordinary-R block",
            )
            retained_world_count = _exact_int(
                block.get("world_count"),
                label=(
                    f"source member[{source_ordinal}] ordinary-R block "
                    f"{block_id} world count"
                ),
                minimum=1,
            )
            if (
                block.get("block_id") != block_id
                or retained_world_count != WORLDS_PER_BLOCK
            ):
                _fail("source member ordinary-R block identity or width differs")
            world_identity = _identity(
                block.get("world_identity"),
                label=(
                    f"source member[{source_ordinal}] "
                    f"ordinary-R block {block_id}"
                ),
            )
            world_key = _identity_key(world_identity)
            if world_key in object_identities:
                _fail("source object identities repeat")
            object_identities.add(world_key)
            blocks.append({
                "block_id": block_id,
                "world_count": WORLDS_PER_BLOCK,
                "world_identity": world_identity,
            })
        normalized.append({
            "source_ordinal": source_ordinal,
            "slate_id": slate_id,
            "season": season,
            "week": week,
            "reconstruction_source_identity": source_identity,
            "ordinary_r_blocks": blocks,
        })
    excluded = normalized[EXCLUDED_SOURCE_ORDINAL]
    if (
        excluded["slate_id"] != EXCLUDED_SLATE_ID
        or [row["block_id"] for row in excluded["ordinary_r_blocks"]]
        != list(RECOVERY_AVAILABLE_BLOCKS)
    ):
        _fail("the mechanical 2025 Week-1 exclusion source differs")
    return normalized, excluded


def _source_membership(
    source_members: Sequence[Mapping[str, object]],
) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for member in source_members:
        row = {
            "source_ordinal": member["source_ordinal"],
            "slate_id": member["slate_id"],
            "source_member_sha256": batch.canonical_sha256(member),
            "reconstruction_source_identity": member[
                "reconstruction_source_identity"
            ],
            "ordinary_r_blocks_sha256": batch.canonical_sha256(
                member["ordinary_r_blocks"]
            ),
        }
        _exact_keys(row, _SOURCE_MEMBERSHIP_KEYS, label="source membership")
        rows.append(row)
    return rows


def build_extreme_tail_factorial_source_catalog_v1(
    *, catalog_id: str, source_members: Sequence[Mapping[str, object]]
) -> dict[str, object]:
    """Prepare canonical source-catalog bytes for create-once publication.

    This pure helper creates no authority by itself.  The factorial manifest
    accepts the catalog only after its exact canonical bytes are supplied with
    a matching generation-pinned object identity.
    """
    retained_id = _canonical_id(catalog_id, label="source catalog id")
    normalized, _excluded = _source_members(source_members)
    members_hash = batch.canonical_sha256(normalized)
    membership = _source_membership(normalized)
    membership_hash = batch.canonical_sha256(membership)
    acceptance = {
        "schema_version": SOURCE_MEMBERSHIP_ACCEPTANCE_SCHEMA,
        "catalog_id": retained_id,
        "source_member_count": SOURCE_SLATE_COUNT,
        "source_members_sha256": members_hash,
        "source_membership_sha256": membership_hash,
        "exact_ordered_grid_complete": True,
        "all_source_objects_generation_pinned": True,
        "accepted": True,
        "uses_realized_outcomes": False,
    }
    _exact_keys(
        acceptance,
        _SOURCE_ACCEPTANCE_KEYS,
        label="source membership acceptance",
    )
    body: dict[str, object] = {
        "schema_version": SOURCE_CATALOG_SCHEMA,
        "publication_mode": PUBLICATION_MODE,
        "catalog_id": retained_id,
        "source_member_count": SOURCE_SLATE_COUNT,
        "source_members": normalized,
        "source_members_sha256": members_hash,
        "source_membership": membership,
        "source_membership_sha256": membership_hash,
        "membership_acceptance": acceptance,
        "membership_acceptance_sha256": batch.canonical_sha256(acceptance),
        "uses_realized_outcomes": False,
        "source_membership_authority": True,
    }
    body["source_catalog_sha256"] = batch.canonical_sha256(body)
    return body


def _validated_source_catalog(
    value: object, *, source_catalog_identity: Mapping[str, object]
) -> tuple[
    dict[str, object],
    dict[str, object],
    list[dict[str, object]],
    dict[str, object],
]:
    item = dict(_mapping(value, label="factorial source catalog"))
    _exact_keys(item, _SOURCE_CATALOG_KEYS, label="factorial source catalog")
    if (
        item.get("schema_version") != SOURCE_CATALOG_SCHEMA
        or item.get("publication_mode") != PUBLICATION_MODE
        or item.get("source_member_count") != SOURCE_SLATE_COUNT
        or item.get("uses_realized_outcomes") is not False
        or item.get("source_membership_authority") is not True
    ):
        _fail("factorial source catalog is not an accepted 54-slate catalog")
    catalog_id = _canonical_id(item.get("catalog_id"), label="source catalog id")
    _validate_self_hash(
        item,
        field="source_catalog_sha256",
        label="factorial source catalog",
    )
    identity = _identity(
        source_catalog_identity, label="factorial source catalog object"
    )
    try:
        batch.validate_json_identity(
            item, identity, label="factorial source catalog object"
        )
    except Exception as exc:
        raise CorpusExtremeTailFactorialManifestError(
            "factorial source catalog bytes differ from its generation-pinned identity"
        ) from exc
    normalized, excluded = _source_members(item.get("source_members"))
    members_hash = batch.canonical_sha256(normalized)
    if item.get("source_members_sha256") != members_hash:
        _fail("factorial source catalog member hash differs")
    expected_membership = _source_membership(normalized)
    raw_membership = _sequence(
        item.get("source_membership"), label="source catalog membership"
    )
    if batch.canonical_json_bytes(raw_membership) != batch.canonical_json_bytes(
        expected_membership
    ):
        _fail("factorial source catalog membership canonical replay differs")
    membership_hash = batch.canonical_sha256(expected_membership)
    if item.get("source_membership_sha256") != membership_hash:
        _fail("factorial source catalog membership hash differs")
    acceptance = _mapping(
        item.get("membership_acceptance"),
        label="source membership acceptance",
    )
    _exact_keys(
        acceptance,
        _SOURCE_ACCEPTANCE_KEYS,
        label="source membership acceptance",
    )
    expected_acceptance = {
        "schema_version": SOURCE_MEMBERSHIP_ACCEPTANCE_SCHEMA,
        "catalog_id": catalog_id,
        "source_member_count": SOURCE_SLATE_COUNT,
        "source_members_sha256": members_hash,
        "source_membership_sha256": membership_hash,
        "exact_ordered_grid_complete": True,
        "all_source_objects_generation_pinned": True,
        "accepted": True,
        "uses_realized_outcomes": False,
    }
    if batch.canonical_json_bytes(acceptance) != batch.canonical_json_bytes(
        expected_acceptance
    ):
        _fail("factorial source catalog membership acceptance differs")
    acceptance_hash = batch.canonical_sha256(expected_acceptance)
    if item.get("membership_acceptance_sha256") != acceptance_hash:
        _fail("factorial source catalog membership acceptance hash differs")
    rebuilt = build_extreme_tail_factorial_source_catalog_v1(
        catalog_id=catalog_id,
        source_members=normalized,
    )
    if batch.canonical_json_bytes(item) != batch.canonical_json_bytes(rebuilt):
        _fail("factorial source catalog canonical replay differs")
    return item, identity, normalized, excluded


def _output_uris(*, output_prefix: str, ordinal: int, slate_id: str) -> dict[str, str]:
    prefix = f"{output_prefix}slates/{ordinal:02d}-{slate_id}/"
    return {
        "global_roster_table_uri": prefix + GLOBAL_ROSTER_FILENAME,
        "occurrence_provenance_uri": prefix + PROVENANCE_FILENAME,
        "ordinary_r_score_matrix_uri": prefix + SCORE_MATRIX_FILENAME,
        "cell_lineage_masks_uri": prefix + LINEAGE_MASKS_FILENAME,
        "slate_result_uri": prefix + RESULT_FILENAME,
        "slate_acceptance_uri": prefix + ACCEPTANCE_FILENAME,
    }


def _factorial_slates(
    source_members: Sequence[Mapping[str, object]], *, output_prefix: str
) -> list[dict[str, object]]:
    retained = [
        member
        for member in source_members
        if member["source_ordinal"] != EXCLUDED_SOURCE_ORDINAL
    ]
    if len(retained) != FACTORIAL_SLATE_COUNT:
        _fail("mechanical recovery-slate exclusion did not yield 53 slates")
    rows: list[dict[str, object]] = []
    output_uris: set[str] = set()
    for factorial_ordinal, member in enumerate(retained):
        slate_id = str(member["slate_id"])
        outputs = _output_uris(
            output_prefix=output_prefix,
            ordinal=factorial_ordinal,
            slate_id=slate_id,
        )
        _exact_keys(outputs, _OUTPUT_KEYS, label="shared output URIs")
        if any(uri in output_uris for uri in outputs.values()):
            _fail("deterministic factorial output URIs repeat")
        output_uris.update(outputs.values())
        row = {
            "factorial_slate_ordinal": factorial_ordinal,
            "source_ordinal": member["source_ordinal"],
            "slate_id": slate_id,
            "season": member["season"],
            "week": member["week"],
            "source_member_sha256": batch.canonical_sha256(member),
            "reconstruction_source_identity": member[
                "reconstruction_source_identity"
            ],
            "ordinary_r_blocks": member["ordinary_r_blocks"],
            "shared_output_uris": outputs,
        }
        _exact_keys(row, _FACTORIAL_SLATE_KEYS, label="factorial slate")
        rows.append(row)
    if any(row["slate_id"] == EXCLUDED_SLATE_ID for row in rows):
        _fail("2025 Week 1 survived its mechanical exclusion")
    return rows


def _evaluation_contract() -> dict[str, object]:
    blocks = list(EVALUATION_BLOCKS)
    body = {
        "evaluation_blocks": blocks,
        "evaluation_blocks_sha256": batch.canonical_sha256(blocks),
        "worlds_per_block": WORLDS_PER_BLOCK,
        "score_world_count_per_slate": len(blocks) * WORLDS_PER_BLOCK,
        "world_order_law": "five-complete-block-major-ordinary-r-worlds",
        "ordinary_unweighted_r_worlds": True,
        "heldout_fold_ids": blocks,
        "heldout_fold_count_per_slate": len(blocks),
        "factorial_heldout_fold_count": FACTORIAL_SLATE_COUNT * len(blocks),
        "all_block_final_fit_count": FACTORIAL_SLATE_COUNT,
        "final_fit_is_distinct_from_every_fold_fit": True,
        "candidate_discovery_worlds_are_never_evaluation_worlds": True,
        "canonical_54_slate_panel_support_authority": False,
    }
    body["evaluation_contract_sha256"] = batch.canonical_sha256(body)
    return body


def _population_registry(
    p0_environment: Mapping[str, str], *, p0_environment_sha256: str
) -> list[dict[str, object]]:
    shared_role_law = {
        "registered_role_family": "epi",
        "registered_role_target_count": 12,
        "role_native_injection": "append-verbatim-after-non-role-truncation",
        "role_rosters_and_source_totals_unchanged_between_populations": True,
    }
    p0 = dict(sorted(p0_environment.items()))
    pb = dict(p0)
    pb.update({
        "CAND_MULT": "0",
        "N_BOOM": "200",
        "BOOM_UNIQUE_FILL": "1",
    })
    pb = dict(sorted(pb.items()))
    pb_hash = batch.canonical_sha256(pb)
    changed_keys = [key for key in p0 if p0[key] != pb[key]]
    if (
        changed_keys != ["BOOM_UNIQUE_FILL", "CAND_MULT", "N_BOOM"]
        or len(p0) != len(pb)
        or set(p0) != set(pb)
        or p0_environment_sha256 != P0_GENERATION_ENVIRONMENT_SHA256
        or pb_hash != PB_GENERATION_ENVIRONMENT_SHA256
    ):
        _fail("PB environment is not exactly the frozen three-lever derivation")
    parity_result_law = {
        "required_retained_shortfall_per_origin": 0,
        "p0_pb_retained_count_parity_required_per_origin": True,
        "failed_origin_if_either_population_count_differs": True,
        "optimizer_visits_calls_successes_and_unique_additions_retained": True,
    }
    return [
        {
            "population_ordinal": 0,
            "population_id": POPULATION_IDS[0],
            "candidate_family_law": "incumbent-compatible-native-generation",
            "literal_generation_levers": {
                "CAND_MULT": "2",
                "N_BOOM": "40",
                "BOOM_UNIQUE_FILL": "0",
            },
            "complete_generation_environment": p0,
            "generation_environment_sha256": p0_environment_sha256,
            "role_native_law": dict(shared_role_law),
            "retained_count_law": "registered-native-count-per-origin",
            "required_retained_shortfall_per_origin": 0,
            "result_acceptance_law": dict(parity_result_law),
            "new_reconstruction_required": True,
        },
        {
            "population_ordinal": 1,
            "population_id": POPULATION_IDS[1],
            "candidate_family_law": "frozen-all-boom-reallocation-v1",
            "literal_generation_levers": {
                "CAND_MULT": "0",
                "N_BOOM": "200",
                "BOOM_UNIQUE_FILL": "1",
            },
            "complete_generation_environment": pb,
            "generation_environment_sha256": pb_hash,
            "only_keys_changed_from_p0": changed_keys,
            "role_native_law": dict(shared_role_law),
            "retained_count_law": (
                "retain-generation-prefix-to-paired-native-non-role-count-"
                "then-append-role-natives"
            ),
            "required_retained_shortfall_per_origin": 0,
            "result_acceptance_law": dict(parity_result_law),
            "unique_fill_may_visit_more_than_200_worlds": True,
            "r5_through_r19_are_new_labeled_reconstructions": True,
            "new_reconstruction_required": True,
        },
    ]


def _origin_masks() -> list[dict[str, object]]:
    all_origins = [f"R{ordinal}" for ordinal in range(20)]
    return [
        {
            "mask_ordinal": 0,
            "mask_id": "K5",
            "origin_count": 5,
            "origin_ids": all_origins[:5],
        },
        {
            "mask_ordinal": 1,
            "mask_id": "K20",
            "origin_count": 20,
            "origin_ids": all_origins,
        },
    ]


def _cross_fit_contract() -> dict[str, object]:
    masks = {row["mask_id"]: row["origin_ids"] for row in _origin_masks()}
    folds: list[dict[str, object]] = []
    for heldout in EVALUATION_BLOCKS:
        folds.append({
            "heldout_block_id": heldout,
            "training_block_ids": [
                block for block in EVALUATION_BLOCKS if block != heldout
            ],
            "removed_candidate_origin_id": heldout,
            "eligible_origin_ids_by_mask": {
                mask_id: [origin for origin in origins if origin != heldout]
                for mask_id, origins in masks.items()
            },
        })
    body = {
        "law_id": "population-specific-candidate-origin-cross-fit/v1",
        "folds": folds,
        "fold_count_per_slate": len(folds),
        "heldout_origin_occurrence_tags_counts_and_attribution_stripped": True,
        "duplicate_roster_survives_only_with_a_training_origin_occurrence": True,
        "r5_through_r19_remain_candidate_discovery_origins_in_every_fold": True,
        "r5_through_r19_never_supply_selector_fit_or_evaluation_columns": True,
        "population_provenance_never_transfers_between_p0_and_pb": True,
        "k20_provenance_never_transfers_into_k5": True,
        "selector_fit_uses_only_four_training_evaluation_blocks": True,
        "selected_ids_freeze_before_heldout_block_metrics": True,
        "heldout_evaluation_uses_only_the_heldout_ordinary_r_block": True,
        "final_fit_uses_all_cell_origins_and_all_five_evaluation_blocks": True,
        "realized_outcomes_forbidden": True,
        "other_arm_scores_forbidden": True,
    }
    body["cross_fit_contract_sha256"] = batch.canonical_sha256(body)
    return body


def _validated_contract(
    value: object,
    *,
    hash_field: str,
    expected_hash: str,
    label: str,
) -> dict[str, object]:
    contract = dict(_mapping(value, label=label))
    retained_hash = _sha256(contract.get(hash_field), label=f"{label} hash")
    remainder = {
        key: item for key, item in contract.items() if key != hash_field
    }
    if (
        retained_hash != expected_hash
        or batch.canonical_sha256(remainder) != expected_hash
    ):
        _fail(f"{label} differs from its literal frozen hash")
    return contract


def _support_switch_contracts(
    raw_hash_by_id: Mapping[str, str],
) -> tuple[dict[str, object], dict[str, object]]:
    gate_law = support._gate_law()  # noqa: SLF001
    switch_law = support._switch_law(raw_hash_by_id)  # noqa: SLF001
    strategy_body = {
        "schema_version": "factorial-support-switch-strategy-contract/v1",
        "strategy_id": support.POLICY_LAW_ID,
        "entry_budgets": list(ENTRY_BUDGETS),
        "ranking_depth": RANKING_DEPTH,
        "gate_law": gate_law,
        "switch_law": switch_law,
        "projects_only_already_materialized_raw_rankings": True,
        "full_union_admission_law": suite.FULL_UNION_ADMISSION_LAW,
    }
    if (
        gate_law
        != {
            "threshold_id": "ge_230",
            "score": 230.0,
            "operator": ">=",
            "requires_every_training_block_nonzero": True,
            "fold_training_block_count": 4,
            "fold_minimum_opportunity_world_count": 100,
            "final_training_block_count": 5,
            "final_minimum_opportunity_world_count": 125,
        }
        or switch_law
        != {
            "passed_strategy_id": "coverage-ge-230-v1",
            "passed_strategy_sha256": _RAW_T230_STRATEGY_SHA256_BY_ID[
                "coverage-ge-230-v1"
            ],
            "failed_strategy_id": (
                "block-robust-bounded-tail-ge-210-250-v1"
            ),
            "failed_strategy_sha256": _RAW_T230_STRATEGY_SHA256_BY_ID[
                "block-robust-bounded-tail-ge-210-250-v1"
            ],
            "selection_law": (
                "support-gate-pass-selects-literal-coverage-otherwise-selects-"
                "block-robust-bounded-tail"
            ),
            "raw_strategy_registry_is_unchanged": True,
            "raw_selectors_are_not_recomputed_by_this_layer": True,
        }
    ):
        _fail("support-switch public contract differs from frozen literals")
    strategy_hash = batch.canonical_sha256(strategy_body)
    if strategy_hash != _SUPPORT_SWITCH_STRATEGY_CONTRACT_SHA256:
        _fail("support-switch strategy contract hash differs")
    strategy = {
        **strategy_body,
        "strategy_contract_sha256": strategy_hash,
    }
    implementation_body = {
        "schema_version": (
            "factorial-support-switch-implementation-contract/v1"
        ),
        "implementation_id": (
            "exact-materialized-raw-ranking-support-projection-v1"
        ),
        "policy_schema_version": support.POLICY_SCHEMA,
        "policy_law_id": support.POLICY_LAW_ID,
        "gate_law": gate_law,
        "switch_law": switch_law,
        "raw_selector_implementation_sha256": (
            _RAW_SELECTOR_IMPLEMENTATION_SHA256
        ),
        "runs_additional_selector": False,
        "preserves_selected_raw_ranking_and-prefixes": True,
    }
    implementation_hash = batch.canonical_sha256(implementation_body)
    if implementation_hash != _SUPPORT_SWITCH_IMPLEMENTATION_CONTRACT_SHA256:
        _fail("support-switch implementation contract hash differs")
    implementation = {
        **implementation_body,
        "implementation_contract_sha256": implementation_hash,
    }
    return strategy, implementation


def _scenario_contracts() -> tuple[dict[str, object], dict[str, object]]:
    combined = _validated_contract(
        scenario.frozen_scenario_ticket_contract_v1(),
        hash_field="contract_sha256",
        expected_hash=_SCENARIO_COMBINED_CONTRACT_SHA256,
        label="scenario-ticket combined implementation contract",
    )
    strategy_body = {
        "schema_version": "factorial-scenario-ticket-strategy-contract/v1",
        "strategy_id": combined["strategy_id"],
        "entry_budgets": combined["entry_budgets"],
        "ranking_depth": combined["ranking_depth"],
        "scope_law": combined["scope_law"],
        "event_law": combined["event_law"],
        "component_law": combined["component_law"],
        "allocation_law": combined["allocation_law"],
        "within_component_ties": combined["within_component_ties"],
        "support_gate": combined["support_gate"],
        "fallback": combined["fallback"],
        "selection_inputs": combined["selection_inputs"],
        "forbidden_inputs": combined["forbidden_inputs"],
    }
    strategy_hash = batch.canonical_sha256(strategy_body)
    if (
        combined.get("strategy_id")
        != "support-switched-event-component-tickets-ge-230-v1"
        or combined.get("implementation_id")
        != "packed-exact-event-components-dhondt-v1"
        or strategy_hash != _SCENARIO_STRATEGY_CONTRACT_SHA256
    ):
        _fail("scenario-ticket strategy projection differs from frozen literals")
    return (
        {
            **strategy_body,
            "strategy_contract_sha256": strategy_hash,
        },
        combined,
    )


def _retrieval_contract() -> dict[str, object]:
    canonical_comparators = retrieval.frozen_retrieval_strategies(
        RANKING_DEPTH
    )
    if not canonical_comparators:
        _fail("canonical comparator registry lacks coverage-194-v1")
    coverage_194 = _validated_contract(
        canonical_comparators[0],
        hash_field="strategy_sha256",
        expected_hash=_COVERAGE_194_STRATEGY_SHA256,
        label="canonical coverage-194 strategy",
    )
    if coverage_194.get("strategy_id") != PRIMARY_RETRIEVAL_IDS[0]:
        _fail("canonical coverage-194 strategy ID differs")

    v2_comparator_rows = retrieval.frozen_retrieval_strategies_v2(
        RANKING_DEPTH
    )
    expected_v2_ids = (
        PRIMARY_RETRIEVAL_IDS[0],
        *V2_ADDITIONAL_COMPARATOR_IDS,
    )
    if tuple(
        row.get("strategy_id") for row in v2_comparator_rows
    ) != expected_v2_ids:
        _fail("public v2 comparator strategy order differs")
    if batch.canonical_json_bytes(v2_comparator_rows[0]) != (
        batch.canonical_json_bytes(coverage_194)
    ):
        _fail("public v2 coverage-194 strategy differs from the canonical alias")
    v2_comparator_by_id: dict[str, dict[str, object]] = {}
    for retrieval_id, raw in zip(
        V2_ADDITIONAL_COMPARATOR_IDS,
        v2_comparator_rows[1:],
        strict=True,
    ):
        v2_comparator_by_id[retrieval_id] = _validated_contract(
            raw,
            hash_field="strategy_sha256",
            expected_hash=_V2_ADDITIONAL_STRATEGY_SHA256_BY_ID[retrieval_id],
            label=f"public v2 comparator strategy {retrieval_id}",
        )
    public_v2_implementation = (
        retrieval_v2_implementation.validate_retrieval_v2_implementation_contract_v1(
            retrieval_v2_implementation.frozen_retrieval_v2_implementation_contract_v1()
        )
    )
    public_v2_identity = dict(
        _mapping(
            public_v2_implementation.get("contract_identity"),
            label="public v2 comparator implementation identity",
        )
    )
    v2_implementation = _validated_contract(
        {
            **public_v2_identity,
            "implementation_contract_sha256": public_v2_implementation.get(
                "implementation_contract_sha256"
            ),
        },
        hash_field="implementation_contract_sha256",
        expected_hash=_V2_COMPARATOR_IMPLEMENTATION_SHA256,
        label="public v2 comparator implementation contract",
    )

    raw_implementation = _validated_contract(
        suite.frozen_selector_implementation_contract_v1(),
        hash_field="selector_implementation_sha256",
        expected_hash=_RAW_SELECTOR_IMPLEMENTATION_SHA256,
        label="raw T230 selector implementation contract",
    )
    raw_rows = suite.frozen_extreme_tail_strategies_v1()
    if len(raw_rows) != len(RAW_T230_RETRIEVAL_IDS):
        _fail("raw T230 strategy registry cardinality differs")
    raw_by_id: dict[str, dict[str, object]] = {}
    for retrieval_id, raw in zip(
        RAW_T230_RETRIEVAL_IDS, raw_rows, strict=True
    ):
        strategy = _validated_contract(
            raw,
            hash_field="strategy_sha256",
            expected_hash=_RAW_T230_STRATEGY_SHA256_BY_ID[retrieval_id],
            label=f"raw T230 strategy {retrieval_id}",
        )
        if strategy.get("strategy_id") != retrieval_id:
            _fail("raw T230 strategy ID differs from its literal registry")
        raw_by_id[retrieval_id] = strategy

    preweek_implementation = _validated_contract(
        preweek.frozen_preweek_selector_implementation_v1(),
        hash_field="implementation_sha256",
        expected_hash=_PREWEEK_SELECTOR_IMPLEMENTATION_SHA256,
        label="preweek selector implementation contract",
    )
    preweek_rows = preweek.frozen_preweek_selector_registry_v1()
    expected_preweek_ids = tuple(_PREWEEK_STRATEGY_SHA256_BY_ID)
    retained_preweek_rows = [
        row
        for row in preweek_rows
        if row.get("selector_id") in _PREWEEK_STRATEGY_SHA256_BY_ID
    ]
    if tuple(
        row.get("selector_id") for row in retained_preweek_rows
    ) != expected_preweek_ids:
        _fail("required preweek strategy order or identity differs")
    preweek_by_id: dict[str, dict[str, object]] = {}
    for retrieval_id, raw in zip(
        expected_preweek_ids, retained_preweek_rows, strict=True
    ):
        preweek_by_id[retrieval_id] = _validated_contract(
            raw,
            hash_field="strategy_sha256",
            expected_hash=_PREWEEK_STRATEGY_SHA256_BY_ID[retrieval_id],
            label=f"preweek strategy {retrieval_id}",
        )

    addition_implementation = _validated_contract(
        additions.frozen_preweek_additions_implementation_v1(),
        hash_field="implementation_sha256",
        expected_hash=_PREWEEK_ADDITION_IMPLEMENTATION_SHA256,
        label="preweek selector additions implementation contract",
    )
    addition_rows = additions.frozen_preweek_additions_registry_v1()
    if tuple(row.get("strategy_id") for row in addition_rows) != (
        PREWEEK_ADDITION_IDS
    ):
        _fail("preweek selector additions order or identity differs")
    addition_by_id: dict[str, dict[str, object]] = {}
    for retrieval_id, raw in zip(
        PREWEEK_ADDITION_IDS, addition_rows, strict=True
    ):
        addition_by_id[retrieval_id] = _validated_contract(
            raw,
            hash_field="strategy_sha256",
            expected_hash=_PREWEEK_ADDITION_STRATEGY_SHA256_BY_ID[
                retrieval_id
            ],
            label=f"preweek selector addition {retrieval_id}",
        )

    support_strategy, support_implementation = _support_switch_contracts({
        retrieval_id: str(strategy["strategy_sha256"])
        for retrieval_id, strategy in raw_by_id.items()
    })
    scenario_strategy, scenario_implementation = _scenario_contracts()
    substrate_ids = [
        f"{population_id.split('-', 1)[0]}-{mask_id}"
        for population_id in POPULATION_IDS
        for mask_id in ORIGIN_MASK_IDS
    ]
    substrate_body = {
        "schema_version": "factorial-selection-substrate-contract/v1",
        "substrate_ids": substrate_ids,
        "candidate_admission_law": suite.FULL_UNION_ADMISSION_LAW,
        "candidate_scope": (
            "complete-population-and-origin-mask-eligible-union"
        ),
        "cross_fit_scope": (
            "four-ordinary-r-training-blocks-after-heldout-origin-stripping"
        ),
        "final_fit_scope": "all-five-ordinary-r-blocks",
        "candidate_scope_is_not_part_of_strategy_identity": True,
        "legacy_cbwu_quota_admission_forbidden": True,
        "heldout_scores_and_realized_outcomes_forbidden": True,
    }
    substrate_hash = batch.canonical_sha256(substrate_body)
    substrate_contract = {
        **substrate_body,
        "selection_substrate_contract_sha256": substrate_hash,
    }

    def row(
        *,
        ordinal: int,
        retrieval_id: str,
        role: str,
        strategy_contract: Mapping[str, object],
        strategy_hash_field: str,
        implementation_contract: Mapping[str, object],
        implementation_hash_field: str,
        infeasible_scope_law: str,
        execution_kind: str = "selector",
    ) -> dict[str, object]:
        return {
            "retrieval_ordinal": ordinal,
            "retrieval_id": retrieval_id,
            "role": role,
            "execution_kind": execution_kind,
            "strategy_contract": dict(strategy_contract),
            "strategy_contract_sha256": strategy_contract[
                strategy_hash_field
            ],
            "implementation_contract": dict(implementation_contract),
            "implementation_contract_sha256": implementation_contract[
                implementation_hash_field
            ],
            "applicable_substrate_ids": substrate_ids,
            "selection_substrate_contract_sha256": substrate_hash,
            "infeasible_scope_law": infeasible_scope_law,
        }

    catalog = [
        row(
            ordinal=0,
            retrieval_id=PRIMARY_RETRIEVAL_IDS[0],
            role="primary-factorial-incumbent-retrieval",
            strategy_contract=coverage_194,
            strategy_hash_field="strategy_sha256",
            implementation_contract=preweek_implementation,
            implementation_hash_field="implementation_sha256",
            infeasible_scope_law="fail-if-fewer-than-80-eligible-candidates",
        ),
        *[
            row(
                ordinal=ordinal + 1,
                retrieval_id=retrieval_id,
                role="raw-t230-substrate-sensitivity",
                strategy_contract=raw_by_id[retrieval_id],
                strategy_hash_field="strategy_sha256",
                implementation_contract=raw_implementation,
                implementation_hash_field="selector_implementation_sha256",
                infeasible_scope_law=(
                    "fail-if-fewer-than-80-eligible-candidates"
                ),
            )
            for ordinal, retrieval_id in enumerate(RAW_T230_RETRIEVAL_IDS)
        ],
        row(
            ordinal=5,
            retrieval_id=PRIMARY_RETRIEVAL_IDS[1],
            role="primary-factorial-t230-retrieval",
            strategy_contract=support_strategy,
            strategy_hash_field="strategy_contract_sha256",
            implementation_contract=support_implementation,
            implementation_hash_field="implementation_contract_sha256",
            infeasible_scope_law="fail-if-fewer-than-80-eligible-candidates",
        ),
        row(
            ordinal=6,
            retrieval_id=(
                "support-switched-event-component-tickets-ge-230-v1"
            ),
            role="scenario-ticket-mechanism-comparison",
            strategy_contract=scenario_strategy,
            strategy_hash_field="strategy_contract_sha256",
            implementation_contract=scenario_implementation,
            implementation_hash_field="contract_sha256",
            infeasible_scope_law="frozen-block-robust-append-then-fail-short",
        ),
        row(
            ordinal=7,
            retrieval_id="individual-training-maximum-rank-v1",
            role="upper-end-anti-diversification-ablation",
            strategy_contract=preweek_by_id[
                "individual-training-maximum-rank-v1"
            ],
            strategy_hash_field="strategy_sha256",
            implementation_contract=preweek_implementation,
            implementation_hash_field="implementation_sha256",
            infeasible_scope_law="fail-if-fewer-than-80-eligible-candidates",
        ),
        row(
            ordinal=8,
            retrieval_id="training-hit-ge-230-admission-v1",
            role="hard-230-admission-sensitivity",
            strategy_contract=preweek_by_id[
                "training-hit-ge-230-admission-v1"
            ],
            strategy_hash_field="strategy_sha256",
            implementation_contract=preweek_implementation,
            implementation_hash_field="implementation_sha256",
            infeasible_scope_law="publish-no-book-if-fewer-than-80-survive",
        ),
        *[
            row(
                ordinal=ordinal + 9,
                retrieval_id=retrieval_id,
                role="existing-v2-comparator-substrate-sensitivity",
                strategy_contract=v2_comparator_by_id[retrieval_id],
                strategy_hash_field="strategy_sha256",
                implementation_contract=v2_implementation,
                implementation_hash_field="implementation_contract_sha256",
                infeasible_scope_law=(
                    "fail-if-fewer-than-80-eligible-candidates"
                ),
            )
            for ordinal, retrieval_id in enumerate(
                V2_ADDITIONAL_COMPARATOR_IDS
            )
        ],
        *[
            row(
                ordinal=ordinal + 15,
                retrieval_id=retrieval_id,
                role="fixed-preweek-selector-addition",
                strategy_contract=addition_by_id[retrieval_id],
                strategy_hash_field="strategy_sha256",
                implementation_contract=addition_implementation,
                implementation_hash_field="implementation_sha256",
                infeasible_scope_law=(
                    "fail-if-fewer-than-80-eligible-candidates"
                ),
            )
            for ordinal, retrieval_id in enumerate(PREWEEK_ADDITION_IDS[:2])
        ],
        row(
            ordinal=17,
            retrieval_id=PREWEEK_ADDITION_IDS[2],
            role="maximum-coverage-conversion-gap-diagnostic",
            strategy_contract=addition_by_id[PREWEEK_ADDITION_IDS[2]],
            strategy_hash_field="strategy_sha256",
            implementation_contract=addition_implementation,
            implementation_hash_field="implementation_sha256",
            infeasible_scope_law="fail-if-fewer-than-80-eligible-candidates",
            execution_kind="diagnostic",
        ),
    ]
    if tuple(item["retrieval_id"] for item in catalog) != RETRIEVAL_IDS:
        _fail("retrieval catalog order differs from the frozen registry")
    body = {
        "retrieval_ids": list(RETRIEVAL_IDS),
        "primary_factorial_retrieval_ids": list(PRIMARY_RETRIEVAL_IDS),
        "secondary_substrate_retrieval_ids": list(SECONDARY_RETRIEVAL_IDS),
        "selector_retrieval_ids": [
            retrieval_id
            for retrieval_id in RETRIEVAL_IDS
            if retrieval_id != PREWEEK_ADDITION_IDS[2]
        ],
        "diagnostic_retrieval_ids": [PREWEEK_ADDITION_IDS[2]],
        "catalog_count": len(catalog),
        "catalog": catalog,
        "catalog_sha256": batch.canonical_sha256(catalog),
        "selection_substrate_contract": substrate_contract,
        "selection_substrate_contract_sha256": substrate_hash,
        "full_union_admission_before_every_selector": True,
        "legacy_cbwu_quota_admission_forbidden": True,
        "bounded_tail_rungs": [
            {"threshold": threshold, "operator": operator, "weight": weight}
            for threshold, operator, weight in suite.TAIL_RUNGS
        ],
        "entry_budgets": list(ENTRY_BUDGETS),
        "ranking_depth": RANKING_DEPTH,
        "ranking_prefix_law": RANKING_PREFIX_LAW,
        "simulated_results_may_not_screen_the_controlled_grade_catalog": True,
    }
    body["retrieval_contract_sha256"] = batch.canonical_sha256(body)
    return body


def _cell_registry() -> list[dict[str, object]]:
    return [
        {
            "cell_ordinal": ordinal,
            "cell_id": cell_id,
            "population_id": population_id,
            "candidate_origin_mask_id": mask_id,
            "retrieval_id": retrieval_id,
            "primary_causal_role": role,
            "entry_budgets": list(ENTRY_BUDGETS),
        }
        for ordinal, (
            cell_id,
            population_id,
            mask_id,
            retrieval_id,
            role,
        ) in enumerate(_EXPECTED_CELL_ROWS)
    ]


def _shared_artifact_contract() -> dict[str, object]:
    body = {
        "law_id": "generate-once-score-once-select-many/v1",
        "global_roster_table_schema": "factorial-global-rosters/v1",
        "occurrence_provenance_schema": "factorial-occurrence-provenance/v1",
        "ordinary_r_score_matrix_schema": "factorial-ordinary-r-matrix/v1",
        "cell_lineage_masks_schema": "factorial-cell-lineage-masks/v1",
        "roster_identity_law": "sorted-nine-canonical-player-id-tuple",
        "lineup_id_law": "sha256-of-canonical-slate-and-roster-identity",
        "global_union_law": "every-unique-p0-or-pb-roster-from-r0-through-r19",
        "occurrence_dimensions": [
            "population_id",
            "origin_id",
            "generator_family_tags",
            "generation_law",
            "role_injection",
            "source_identities",
        ],
        "score_each_global_union_roster_once": True,
        "score_matrix_row_order": "ordered-global-lineup-ids",
        "score_matrix_column_order": "r0-through-r4-then-world-index",
        "score_matrix_world_count": len(EVALUATION_BLOCKS) * WORLDS_PER_BLOCK,
        "population_k_fold_and_final_sets_are_masks_over_global_rows": True,
        "separately_recomputed_cell_matrices_forbidden": True,
        "required_hashes": [
            "ordered-lineup-ids",
            "occurrence-provenance",
            "player-row-identity",
            "each-world-block",
            "full-score-matrix",
            "every-derived-mask",
        ],
        "selectors_consume_only_frozen-shared-artifacts": True,
    }
    body["shared_artifact_contract_sha256"] = batch.canonical_sha256(body)
    return body


def _controlled_grade_boundary() -> dict[str, object]:
    body = {
        "law_id": "one-controlled-realized-grade-after-complete-freeze/v1",
        "maximum_controlled_realized_grade_count": 1,
        "complete_predeclared_final_book_catalog_required": True,
        "all_final_lineup_ids_and_rosters_immutable_before_grade_manifest": True,
        "all_population_provenance_matrices_masks_and_traces_bound": True,
        "all_intended_4_14_80_books_frozen_before_outcome_access": True,
        "post_freeze_strategy_or_book_addition_forbidden": True,
        "simulated_effect_screening_before_catalog_inclusion_forbidden": True,
        "separate_grade_manifest_required": True,
        "this_execution_manifest_opens_outcome_access": False,
        "historical_results_license_production_change": False,
        "prospective_shadow_is_the_only_possible_nomination": True,
    }
    body["controlled_grade_boundary_sha256"] = batch.canonical_sha256(body)
    return body


def build_extreme_tail_factorial_execution_manifest_v1(
    *,
    source_catalog: Mapping[str, object],
    source_catalog_identity: Mapping[str, object],
    p0_generation_environment: Mapping[str, object],
    p0_generation_environment_sha256: str,
    source_commit_sha: str,
    immutable_image: Mapping[str, object],
    output_prefix: str,
) -> dict[str, object]:
    """Build the pure 53-slate factorial manifest from 54 frozen inputs."""
    _validate_frozen_dependency_constants()
    (
        retained_catalog,
        retained_catalog_identity,
        normalized_sources,
        excluded,
    ) = _validated_source_catalog(
        source_catalog,
        source_catalog_identity=source_catalog_identity,
    )
    retained_p0_environment, retained_p0_hash = _validated_p0_environment(
        p0_generation_environment,
        retained_sha256=p0_generation_environment_sha256,
    )
    if (
        type(source_commit_sha) is not str
        or _COMMIT.fullmatch(source_commit_sha) is None
    ):
        _fail("source commit must be one lowercase 40-character Git SHA")
    retained_image = _image(immutable_image)
    retained_prefix = _output_prefix(output_prefix)
    factorial_slates = _factorial_slates(
        normalized_sources, output_prefix=retained_prefix
    )
    origins = _origin_registry()
    populations = _population_registry(
        retained_p0_environment,
        p0_environment_sha256=retained_p0_hash,
    )
    masks = _origin_masks()
    retrieval_contract = _retrieval_contract()
    cells = _cell_registry()
    source_members_sha256 = batch.canonical_sha256(normalized_sources)
    factorial_slates_sha256 = batch.canonical_sha256(factorial_slates)
    source_contract = {
        "input_slate_count": SOURCE_SLATE_COUNT,
        "ordered_input_grid_law": "2023-then-2024-then-2025-week-01-through-18",
        "source_catalog_id": retained_catalog["catalog_id"],
        "source_catalog_identity": retained_catalog_identity,
        "source_catalog_sha256": retained_catalog["source_catalog_sha256"],
        "source_members_sha256": source_members_sha256,
        "source_membership_sha256": retained_catalog[
            "source_membership_sha256"
        ],
        "source_membership_acceptance_sha256": retained_catalog[
            "membership_acceptance_sha256"
        ],
        "mechanical_exclusion": {
            "source_ordinal": EXCLUDED_SOURCE_ORDINAL,
            "slate_id": EXCLUDED_SLATE_ID,
            "season": 2025,
            "week": 1,
            "available_block_ids": list(RECOVERY_AVAILABLE_BLOCKS),
            "missing_block_id": "R3",
            "reason": "four-origin-recovery-cannot-satisfy-five-fold-law",
            "excluded_source_member_sha256": batch.canonical_sha256(excluded),
            "effect_or_outcome_access_used": False,
        },
        "retained_slate_count": FACTORIAL_SLATE_COUNT,
        "retained_source_ordinals": [
            ordinal
            for ordinal in range(SOURCE_SLATE_COUNT)
            if ordinal != EXCLUDED_SOURCE_ORDINAL
        ],
        "factorial_slates_sha256": factorial_slates_sha256,
    }
    source_contract["source_catalog_contract_sha256"] = batch.canonical_sha256(
        source_contract
    )
    origin_hash = batch.canonical_sha256(origins)
    population_hash = batch.canonical_sha256(populations)
    mask_hash = batch.canonical_sha256(masks)
    cell_hash = batch.canonical_sha256(cells)
    manifest_id_seed = {
        "schema_version": FACTORIAL_EXECUTION_MANIFEST_SCHEMA,
        "source_catalog_identity": retained_catalog_identity,
        "source_catalog_sha256": retained_catalog["source_catalog_sha256"],
        "source_members_sha256": source_members_sha256,
        "factorial_slates_sha256": factorial_slates_sha256,
        "candidate_origin_registry_sha256": origin_hash,
        "population_registry_sha256": population_hash,
        "candidate_origin_masks_sha256": mask_hash,
        "retrieval_contract_sha256": retrieval_contract[
            "retrieval_contract_sha256"
        ],
        "factorial_cell_registry_sha256": cell_hash,
        "p0_generation_environment_sha256": retained_p0_hash,
        "source_commit_sha": source_commit_sha,
        "immutable_image": retained_image,
        "output_prefix": retained_prefix,
    }
    body: dict[str, object] = {
        "schema_version": FACTORIAL_EXECUTION_MANIFEST_SCHEMA,
        "publication_mode": PUBLICATION_MODE,
        "manifest_id": "foundry-factorial:" + batch.canonical_sha256(
            manifest_id_seed
        ),
        "protocol_document": PROTOCOL_DOCUMENT,
        "protocol_sha256": PROTOCOL_SHA256,
        "source_catalog_identity": retained_catalog_identity,
        "source_catalog_id": retained_catalog["catalog_id"],
        "source_catalog_sha256": retained_catalog["source_catalog_sha256"],
        "source_membership_sha256": retained_catalog[
            "source_membership_sha256"
        ],
        "source_membership_acceptance_sha256": retained_catalog[
            "membership_acceptance_sha256"
        ],
        "source_catalog_contract": source_contract,
        "factorial_slate_count": FACTORIAL_SLATE_COUNT,
        "factorial_slates": factorial_slates,
        "factorial_slates_sha256": factorial_slates_sha256,
        "ordinary_r_evaluation_contract": _evaluation_contract(),
        "candidate_origin_registry": origins,
        "candidate_origin_registry_sha256": origin_hash,
        "population_registry": populations,
        "population_registry_sha256": population_hash,
        "candidate_origin_masks": masks,
        "candidate_origin_masks_sha256": mask_hash,
        "candidate_origin_cross_fit_contract": _cross_fit_contract(),
        "retrieval_contract": retrieval_contract,
        "factorial_cell_registry": cells,
        "factorial_cell_registry_sha256": cell_hash,
        "shared_artifact_contract": _shared_artifact_contract(),
        "p0_generation_environment": retained_p0_environment,
        "p0_generation_environment_sha256": retained_p0_hash,
        "pb_generation_environment_sha256": populations[1][
            "generation_environment_sha256"
        ],
        "entry_budgets": list(ENTRY_BUDGETS),
        "ranking_depth": RANKING_DEPTH,
        "ranking_prefix_law": RANKING_PREFIX_LAW,
        "controlled_grade_boundary": _controlled_grade_boundary(),
        "source_commit_sha": source_commit_sha,
        "immutable_image": retained_image,
        "output_prefix": retained_prefix,
        **{field: False for field in _FALSE_AUTHORITY_FIELDS},
    }
    body["execution_manifest_sha256"] = batch.canonical_sha256(body)
    return body


def validate_extreme_tail_factorial_execution_manifest_v1(
    value: object,
    *,
    source_catalog: Mapping[str, object],
    source_catalog_identity: Mapping[str, object],
    p0_generation_environment: Mapping[str, object],
    p0_generation_environment_sha256: str,
    source_commit_sha: str,
    immutable_image: Mapping[str, object],
    output_prefix: str,
) -> dict[str, object]:
    """Validate exact keys/self-hash and replay all frozen preparation inputs."""
    item = dict(_mapping(value, label="extreme-tail factorial manifest"))
    _exact_keys(item, _MANIFEST_KEYS, label="extreme-tail factorial manifest")
    if (
        item.get("schema_version") != FACTORIAL_EXECUTION_MANIFEST_SCHEMA
        or item.get("publication_mode") != PUBLICATION_MODE
    ):
        _fail("factorial manifest schema or publication mode differs")
    _false_authorities(item, label="extreme-tail factorial manifest")
    _validate_self_hash(
        item,
        field="execution_manifest_sha256",
        label="extreme-tail factorial manifest",
    )
    expected = build_extreme_tail_factorial_execution_manifest_v1(
        source_catalog=source_catalog,
        source_catalog_identity=source_catalog_identity,
        p0_generation_environment=p0_generation_environment,
        p0_generation_environment_sha256=p0_generation_environment_sha256,
        source_commit_sha=source_commit_sha,
        immutable_image=immutable_image,
        output_prefix=output_prefix,
    )
    if batch.canonical_json_bytes(item) != batch.canonical_json_bytes(expected):
        _fail("factorial manifest differs from frozen-input canonical replay")
    return expected


__all__ = [
    "ACCEPTANCE_FILENAME",
    "CorpusExtremeTailFactorialManifestError",
    "FACTORIAL_EXECUTION_MANIFEST_SCHEMA",
    "GLOBAL_ROSTER_FILENAME",
    "LINEAGE_MASKS_FILENAME",
    "P0_GENERATION_ENVIRONMENT_SHA256",
    "PB_GENERATION_ENVIRONMENT_SHA256",
    "PROVENANCE_FILENAME",
    "PUBLICATION_MODE",
    "RESULT_FILENAME",
    "SCORE_MATRIX_FILENAME",
    "SOURCE_CATALOG_SCHEMA",
    "SOURCE_MEMBERSHIP_ACCEPTANCE_SCHEMA",
    "build_extreme_tail_factorial_execution_manifest_v1",
    "build_extreme_tail_factorial_source_catalog_v1",
    "frozen_extreme_tail_factorial_p0_environment_v1",
    "validate_extreme_tail_factorial_execution_manifest_v1",
]
