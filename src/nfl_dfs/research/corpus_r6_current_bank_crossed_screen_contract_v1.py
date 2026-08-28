"""Pure pre-output contract for the sealed R6 current-bank crossed screen.

This module contains no object store, cloud client, outcome source, scorer,
publisher, graph writer, deployment seam, or policy authority.  It freezes the
existing seven construction profiles and eight selectors, derives fold-safe
profile views, produces deterministic equal-count subsamples, measures
effective independent simulated tail shots, and applies the predeclared
finalist function without accepting a human finalist list.

The execution/reopen layer is intentionally separate.  It must bind this code
and the companion tracked report to a clean commit before any sealed-bank
metric is emitted.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping, Sequence
from fractions import Fraction
from functools import lru_cache
from hashlib import sha256
import json
import math
import re
from typing import Final

import numpy as np

CONTRACT_SCHEMA: Final = "corpus-r6-current-bank-crossed-screen-contract/v1"
VIEW_REGISTRY_SCHEMA: Final = "corpus-r6-current-bank-view-registry/v1"
SUBSAMPLE_SCHEMA: Final = "corpus-r6-current-bank-equal-count-subsample/v1"
TAIL_SHOTS_SCHEMA: Final = "corpus-r6-effective-independent-tail-shots/v1"
NOMINATION_SCHEMA: Final = "corpus-r6-current-bank-nomination-function/v1"
NOMINATION_PUBLICATION_SCHEMA: Final = (
    "corpus-r6-current-bank-nomination-publication/v1"
)
FINALIST_SCHEMA: Final = "corpus-r6-current-bank-finalist-function/v1"
PROJECTION_SCHEMA: Final = "corpus-r6-current-bank-selection-input-projection/v1"
PROJECTION_BUNDLE_SCHEMA: Final = (
    "corpus-r6-current-bank-slate-projection-bundle/v1"
)
PHASE_GRID_SCHEMA: Final = "corpus-r6-current-bank-phase-grid/v1"
BROAD_PHASE_AUTHORITY_SCHEMA: Final = (
    "corpus-r6-current-bank-broad-phase-authority/v1"
)
SELECTION_FOLD_RECEIPT_SCHEMA: Final = (
    "corpus-r6-current-bank-four-block-selection-fold-receipt/v1"
)
SELECTION_RECEIPT_SCHEMA: Final = (
    "corpus-r6-current-bank-slate-selection-receipt/v1"
)
HELDOUT_EVALUATION_AUTHORITY_SCHEMA: Final = (
    "corpus-r6-current-bank-heldout-evaluation-authority/v1"
)
EVALUATION_RESULT_SCHEMA: Final = (
    "corpus-r6-current-bank-slate-evaluation-result/v1"
)
HELDOUT_FOLD_AUTHORITY_SCHEMA: Final = (
    "corpus-r6-current-bank-heldout-fold-score-authority/v1"
)
POPULATION_METRIC_ROW_SCHEMA: Final = (
    "corpus-r6-current-bank-population-metric-row/v1"
)
BOOK_METRIC_ROW_SCHEMA: Final = (
    "corpus-r6-current-bank-book-metric-row/v1"
)
COMPARISON_LEDGER_SCHEMA: Final = (
    "corpus-r6-current-bank-paired-comparison-ledger/v1"
)
AGGREGATE_MECHANICS_SCHEMA: Final = (
    "corpus-r6-current-bank-aggregate-mechanics/v1"
)
BOOTSTRAP_INPUT_SCHEMA: Final = (
    "corpus-r6-current-bank-bootstrap-input-binding/v1"
)
PROCESS_BUDGET_SCHEMA: Final = "corpus-r6-current-bank-process-budget/v1"
EVALUATOR_PROCESS_BUDGET_SCHEMA: Final = (
    "corpus-r6-current-bank-evaluator-process-budget/v1"
)
PUBLISHER_PROCESS_BUDGET_SCHEMA: Final = (
    "corpus-r6-current-bank-publisher-process-budget/v1"
)
BOOTSTRAP_MANIFEST_SCHEMA: Final = (
    "corpus-r6-current-bank-bootstrap-manifest/v1"
)
RUNTIME_OBSERVATION_SCHEMA: Final = (
    "corpus-r6-current-bank-runtime-observation/v1"
)
BOOTSTRAP_SCHEMA: Final = "corpus-r6-current-bank-slate-cluster-bootstrap/v1"
TOPOLOGY_SCHEMA: Final = "corpus-r6-current-bank-result-topology/v1"
DESIGN_SCHEMA: Final = "corpus-r6-current-bank-design/v1"
FINALIST_PUBLICATION_SCHEMA: Final = "corpus-r6-current-bank-finalist-publication/v1"
ROOT_SCHEMA: Final = "corpus-r6-current-bank-terminal-root/v1"
CONTRACT_ID: Final = "20260827-r6-current-bank-crossed-screen-v1"
CONTRACT_REPORT_PATH: Final = (
    "reports/2026-08-27-r6-current-bank-crossed-screen-preoutput-contract.md"
)
MODULE_PATH: Final = (
    "src/nfl_dfs/research/"
    "corpus_r6_current_bank_crossed_screen_contract_v1.py"
)

PANEL_IDENTITY: Final = {
    "uri": (
        "gs://nfl-predictions-503414-corpus-retrieval/research/"
        "corpus-r6-full-union-freezes/"
        "20260826-foundry-v12-r6-full-union-freeze-v1/panel-freeze.json"
    ),
    "generation": "1787756181440564",
    "sha256": "57844386a3da86ddf05f8b3e6b19ae19c7327afcfc1057647b210e58caec2467",
    "bytes": 89_879,
}
PANEL_SELF_SHA256: Final = (
    "26d27abf5074ed20cbd401e1a93332b34449eb3ec9b3c7175330c1de10736f2d"
)
PANEL_SLATE_COUNT: Final = 54
PANEL_RANK_80_BOOK_COUNT: Final = 2_592
PANEL_PREFIX_COUNT: Final = 7_776
EXACT_STRUCTURAL_OBJECT_COUNT: Final = 111

WORLD_BLOCKS: Final = ("R0", "R1", "R2", "R3", "R4")
WORLDS_PER_BLOCK: Final = 10_000
PREFIX_SIZES: Final = (4, 14, 80)
ENTRY_BUDGET: Final = 80
ROSTER_SIZE: Final = 9
MAX_SELECTION_CANDIDATES_PER_FOLD: Final = 250
MAX_EQUAL_COUNT_SAMPLE: Final = MAX_SELECTION_CANDIDATES_PER_FOLD
MAX_LINEUP_ID_UTF8_BYTES: Final = 71
MAX_PLAYER_ID_UTF8_BYTES: Final = 32
MAX_GCS_URI_UTF8_BYTES: Final = 512
MAX_GENERATION_DIGITS: Final = 32
MAX_IDENTITY_BYTES: Final = 1_000_000_000
MAX_OCCURRENCE_COUNT: Final = 2_147_483_647
BROAD_SELECTION_RECEIPT_MAX_BYTES: Final = 32_000_000
CONFIRMATION_SELECTION_RECEIPT_MAX_BYTES: Final = 96_000_000
SUBSAMPLE_REPLICATES: Final = 32
BROAD_SCREEN_REPLICATES: Final = 1
BROAD_SCREEN_PHASE: Final = "broad-screen"
CONFIRMATION_PHASE: Final = "confirmation-sensitivity"
BOOTSTRAP_RESAMPLES: Final = 10_000
BOOTSTRAP_CLUSTER_COUNT: Final = 54
BOOTSTRAP_BLOCKS_PER_CLUSTER: Final = 5
BOOTSTRAP_LOWER_QUANTILE: Final = (1, 40)
BOOTSTRAP_UPPER_QUANTILE: Final = (39, 40)
OUTPUT_OBJECT_COUNT: Final = 275
OUTPUT_NAMESPACE: Final = (
    "gs://nfl-predictions-503414-corpus-retrieval/research/"
    "corpus-r6-current-bank-crossed-screens/"
)
MAXIMUM_BROAD_SELECTOR_FITS: Final = 17_280
MAXIMUM_CONFIRMATION_SELECTOR_FITS: Final = 51_840
MAXIMUM_SELECTOR_FITS: Final = 69_120
LOGICAL_FOLD_SELECTION_COUNT_PER_PHASE: Final = (
    PANEL_SLATE_COUNT * len(WORLD_BLOCKS)
)
SELECTOR_OS_PROCESS_COUNT_PER_PHASE: Final = (
    2 * LOGICAL_FOLD_SELECTION_COUNT_PER_PHASE
)
# Compatibility name retained for callers that use the statistical fold count.
# It is not an OS-process count: every logical fold selection is an ordered
# artifact-broker -> matrix-selector pair.
FOLD_SELECTOR_SUBPROCESS_COUNT: Final = LOGICAL_FOLD_SELECTION_COUNT_PER_PHASE
FOLDS_PER_SLATE: Final = len(WORLD_BLOCKS)
INFERENTIAL_VIEW_COUNT: Final = 8
STRATEGY_COUNT: Final = 8
BROAD_FITS_PER_FOLD: Final = INFERENTIAL_VIEW_COUNT * STRATEGY_COUNT
MAXIMUM_CONFIRMATION_NOMINEES: Final = 6
MINIMUM_CONFIRMATION_NOMINEES: Final = 3

POLICY_CLAIMS: Final = {
    "uses_realized_outcomes": False,
    "historical_scoring_performed": False,
    "historical_scoring_licensed": False,
    "corpus_regeneration_performed": False,
    "matchup_source_read": False,
    "graph_mutation_performed": False,
    "production_change_performed": False,
    "promotion_authority": False,
    "decision_authority": False,
}

PROCESS_ROLES: Final = (
    "projection-publisher",
    "broad-fold-selector",
    "broad-slate-assembler",
    "broad-evaluator",
    "confirmation-fold-selector",
    "confirmation-slate-assembler",
    "confirmation-evaluator",
    "broad-nomination-publisher",
    "aggregate-finalist-publisher",
    "terminal-root-publisher",
)
LAYER_ROLES: Final = (
    "projection",
    "broad-selection-receipt",
    "broad-evaluation-result",
    "confirmation-selection-receipt",
    "confirmation-evaluation-result",
)
_ROLE_OUTPUT_BYTE_CEILINGS: Final = {
    "projection-publisher": PANEL_SLATE_COUNT * 256_000_000,
    "broad-fold-selector": 64 * 2_000_000,
    "broad-slate-assembler": BROAD_SELECTION_RECEIPT_MAX_BYTES,
    "broad-evaluator": 256_000_000,
    "confirmation-fold-selector": 192 * 2_000_000,
    "confirmation-slate-assembler": CONFIRMATION_SELECTION_RECEIPT_MAX_BYTES,
    "confirmation-evaluator": 768_000_000,
    "broad-nomination-publisher": 16_000_000,
    "aggregate-finalist-publisher": 272_000_000,
    "terminal-root-publisher": 16_000_000,
}
_PUBLICATION_BYTE_CEILINGS: Final = {
    "design": 4_000_000,
    "projection": 256_000_000,
    "broad-selection-receipt": BROAD_SELECTION_RECEIPT_MAX_BYTES,
    "broad-evaluation-result": 256_000_000,
    "nomination": 16_000_000,
    "confirmation-selection-receipt": CONFIRMATION_SELECTION_RECEIPT_MAX_BYTES,
    "confirmation-evaluation-result": 768_000_000,
    "aggregate": 256_000_000,
    "confirmed-finalists": 16_000_000,
    "root": 16_000_000,
}
_FORBIDDEN_URI_FRAGMENTS: Final = (
    "/actual",
    "/attribution",
    "/contest-result",
    "/funnel",
    "/grade",
    "/graph",
    "/historical-lease",
    "/no-rescore",
    "/outcome",
    "/query-evidence",
    "/realized",
    "/historical-score",
    "/roi",
    "/winner",
)

PROFILE_REGISTRY_SHA256: Final = (
    "5de89cacdf6f836f7161b79ac889d80dafbc8a5040cbf18e06ba5cc14d9464fa"
)
PROFILE_IDENTITIES: Final = (
    (
        0,
        "incumbent",
        "9083a369a9a82a462b02cba8da508654c2ecb2b36712fba0c19166e8f514dc3e",
    ),
    (
        1,
        "remove-salary-floor",
        "a29865440e6f524578c4038075a4c9fe82ec8409d34ec91abc6ca2a10bbd5229",
    ),
    (
        2,
        "remove-qb-stack",
        "146e53ad0352eb3f491149a623da9803decf3bcad758ac83b4ff42d91a151fcb",
    ),
    (
        3,
        "remove-bring-back",
        "fe5d196e362a097f21ec1875e749ec06d992b75b1f39785e1ec82beedcaabbd5",
    ),
    (
        4,
        "allow-rb-vs-dst",
        "494378dd052610f4f4259c457368b3391599d9bf08d1f36cc60a724e00f73788",
    ),
    (
        5,
        "allow-two-rb",
        "286873ae9139d449e43d9212805f41fc520d645d8f3ec20adcb86201e808ed46",
    ),
    (
        6,
        "remove-all-five-shared-constraints",
        "c68042831f7fe21cc0bd61c1ef59d56c84c6632fb016891766d1f131d5de8840",
    ),
)

STRATEGY_REGISTRY_SHA256: Final = (
    "15bafff2d7b973118565191846474e479fe76ee50053e492b66e7bcb0c7c25ba"
)
STRATEGY_IDENTITIES: Final = (
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

# These canonical JSON literals are part of this contract, not aliases to a live
# selector registry.  Keeping them here makes the schema/evaluation import
# closure incapable of importing or invoking selection code.  The sibling
# selector executor separately verifies the live registries byte-for-byte.
_FROZEN_PROFILES_JSON: Final = '[{"ordinal":0,"parameter_schema_sha256":"d4fb644fa56d0234adc6777d18496620647a1eb77d8c31d2d37158b576e3caff","parameter_set_id":"incumbent","parameter_set_sha256":"9083a369a9a82a462b02cba8da508654c2ecb2b36712fba0c19166e8f514dc3e","schema_version":"corpus-parametric-parameter-set-v1","values":{"bring_back_min":1,"forbid_rb_vs_dst":true,"forbid_two_rb_same_team":true,"min_lineup_salary":49000,"qb_stack_min":2}},{"ordinal":1,"parameter_schema_sha256":"d4fb644fa56d0234adc6777d18496620647a1eb77d8c31d2d37158b576e3caff","parameter_set_id":"remove-salary-floor","parameter_set_sha256":"a29865440e6f524578c4038075a4c9fe82ec8409d34ec91abc6ca2a10bbd5229","schema_version":"corpus-parametric-parameter-set-v1","values":{"bring_back_min":1,"forbid_rb_vs_dst":true,"forbid_two_rb_same_team":true,"min_lineup_salary":0,"qb_stack_min":2}},{"ordinal":2,"parameter_schema_sha256":"d4fb644fa56d0234adc6777d18496620647a1eb77d8c31d2d37158b576e3caff","parameter_set_id":"remove-qb-stack","parameter_set_sha256":"146e53ad0352eb3f491149a623da9803decf3bcad758ac83b4ff42d91a151fcb","schema_version":"corpus-parametric-parameter-set-v1","values":{"bring_back_min":1,"forbid_rb_vs_dst":true,"forbid_two_rb_same_team":true,"min_lineup_salary":49000,"qb_stack_min":0}},{"ordinal":3,"parameter_schema_sha256":"d4fb644fa56d0234adc6777d18496620647a1eb77d8c31d2d37158b576e3caff","parameter_set_id":"remove-bring-back","parameter_set_sha256":"fe5d196e362a097f21ec1875e749ec06d992b75b1f39785e1ec82beedcaabbd5","schema_version":"corpus-parametric-parameter-set-v1","values":{"bring_back_min":0,"forbid_rb_vs_dst":true,"forbid_two_rb_same_team":true,"min_lineup_salary":49000,"qb_stack_min":2}},{"ordinal":4,"parameter_schema_sha256":"d4fb644fa56d0234adc6777d18496620647a1eb77d8c31d2d37158b576e3caff","parameter_set_id":"allow-rb-vs-dst","parameter_set_sha256":"494378dd052610f4f4259c457368b3391599d9bf08d1f36cc60a724e00f73788","schema_version":"corpus-parametric-parameter-set-v1","values":{"bring_back_min":1,"forbid_rb_vs_dst":false,"forbid_two_rb_same_team":true,"min_lineup_salary":49000,"qb_stack_min":2}},{"ordinal":5,"parameter_schema_sha256":"d4fb644fa56d0234adc6777d18496620647a1eb77d8c31d2d37158b576e3caff","parameter_set_id":"allow-two-rb","parameter_set_sha256":"286873ae9139d449e43d9212805f41fc520d645d8f3ec20adcb86201e808ed46","schema_version":"corpus-parametric-parameter-set-v1","values":{"bring_back_min":1,"forbid_rb_vs_dst":true,"forbid_two_rb_same_team":false,"min_lineup_salary":49000,"qb_stack_min":2}},{"ordinal":6,"parameter_schema_sha256":"d4fb644fa56d0234adc6777d18496620647a1eb77d8c31d2d37158b576e3caff","parameter_set_id":"remove-all-five-shared-constraints","parameter_set_sha256":"c68042831f7fe21cc0bd61c1ef59d56c84c6632fb016891766d1f131d5de8840","schema_version":"corpus-parametric-parameter-set-v1","values":{"bring_back_min":0,"forbid_rb_vs_dst":false,"forbid_two_rb_same_team":false,"min_lineup_salary":0,"qb_stack_min":0}}]'
_FROZEN_STRATEGIES_JSON: Final = '[{"description":"Incumbent binary world coverage at 194 DK points.","entry_budget":80,"method":"greedy-threshold-coverage-v1","ordinal":0,"parameters":{"operator":">=","threshold":194.0},"schema_version":"corpus-retrieval-strategy/v1","selection_inputs":"discovery-block-simulated-scores-only","strategy_id":"coverage-194-v1","strategy_sha256":"1e1e6a11149ca1c8c9babd183b85adb2ce27d0f976ca863b43768aa3dab0433f","tie_law":["largest-marginal-new-world-count","largest-individual-threshold-count","largest-discovery-mean-score","ascending-lineup-id"]},{"description":"Strict primary-event world coverage above 200.","entry_budget":80,"method":"greedy-threshold-coverage-v1","ordinal":1,"parameters":{"operator":">","threshold":200.0},"schema_version":"corpus-retrieval-strategy/v1","selection_inputs":"discovery-block-simulated-scores-only","strategy_id":"strict-200-coverage-v1","strategy_sha256":"9689bb11de4616e4a6295ae0a5b0ec30aa174097f1965867fdc08d7b2e7d02de","tie_law":["largest-marginal-new-world-count","largest-individual-threshold-count","largest-discovery-mean-score","ascending-lineup-id"]},{"description":"Tail-focused marginal utility above 200/210/220.","entry_budget":80,"method":"greedy-tail-ladder-v1","ordinal":2,"parameters":{"rungs":[{"operator":">","threshold":200.0,"weight":1},{"operator":">","threshold":210.0,"weight":4},{"operator":">","threshold":220.0,"weight":12}]},"schema_version":"corpus-retrieval-strategy/v1","selection_inputs":"discovery-block-simulated-scores-only","strategy_id":"tail-ladder-200-210-220-v1","strategy_sha256":"5561d663cdc2ec8f928ddf5a44889f16e3c23cdd264f4c8fef7925547aa527ea","tie_law":["largest-weighted-marginal-rung-utility","largest-individual-strict-gt-200-count","largest-discovery-mean-score","ascending-lineup-id"]},{"description":"Highest discovery-world mean score with stable ties.","entry_budget":80,"method":"rank-mean-score-v1","ordinal":3,"parameters":{},"schema_version":"corpus-retrieval-strategy/v1","selection_inputs":"discovery-block-simulated-scores-only","strategy_id":"mean-score-v1","strategy_sha256":"5c880aeca7c8ec3386a9d44b111937fada857f569cb324dd2163987b333654c6","tie_law":["largest-discovery-mean-score","largest-individual-strict-gt-200-count","ascending-lineup-id"]},{"description":"Greedy marginal gain in the expected discovery-world book maximum (submodular expected-max objective).","entry_budget":80,"method":"greedy-expected-max-v1","ordinal":4,"parameters":{},"schema_version":"corpus-retrieval-strategy/v1","selection_inputs":"discovery-block-simulated-scores-only","strategy_id":"expected-max-v1","strategy_sha256":"ad94b80a0ea61d1c58f64f825f00f0d0fea47f36158a239c29382836ff2cb780","tie_law":["largest-marginal-expected-max-gain","largest-individual-strict-gt-200-count","largest-discovery-mean-score","ascending-lineup-id"]},{"description":"Tail ladder above 200/210/220 with each lineup\'s marginal coverage scaled by its distinct-discovery-block event support, discounting one-block tail accidents.","entry_budget":80,"method":"greedy-block-supported-ladder-v1","ordinal":5,"parameters":{"rungs":[{"operator":">","threshold":200.0,"weight":1},{"operator":">","threshold":210.0,"weight":4},{"operator":">","threshold":220.0,"weight":12}],"support_scaling":"distinct-discovery-block-count"},"schema_version":"corpus-retrieval-strategy/v1","selection_inputs":"discovery-block-simulated-scores-only","strategy_id":"block-supported-tail-ladder-v1","strategy_sha256":"1ae24780c211a329e8a9867e5dec39630a7efcc640deba9e05561f6a8c98668b","tie_law":["largest-block-supported-marginal-rung-utility","largest-individual-strict-gt-200-count","largest-discovery-mean-score","ascending-lineup-id"]},{"description":"Regime-robust ladder that leximin-maximizes the ascending-sorted per-block weighted rung coverage profile so no single world family dominates the book.","entry_budget":80,"method":"greedy-blockmin-ladder-v1","ordinal":6,"parameters":{"rungs":[{"operator":">","threshold":200.0,"weight":1},{"operator":">","threshold":210.0,"weight":4},{"operator":">","threshold":220.0,"weight":12}]},"schema_version":"corpus-retrieval-strategy/v1","selection_inputs":"discovery-block-simulated-scores-only","strategy_id":"regime-robust-ladder-v1","strategy_sha256":"125610a3fda4c230bacd44f1778e43fe03905a504d55ec6fe4c424c0cbbd0e7b","tie_law":["greatest-post-addition-leximin-block-utility-profile","largest-individual-strict-gt-200-count","largest-discovery-mean-score","ascending-lineup-id"]},{"description":"Strict simulated-world coverage above 230 DK points; an outcome-blind T230 retrieval arm over the accepted full union.","entry_budget":80,"method":"greedy-threshold-coverage-v1","ordinal":7,"parameters":{"operator":">","threshold":230.0},"schema_version":"corpus-retrieval-strategy/v1","selection_inputs":"discovery-block-simulated-scores-only","strategy_id":"strict-230-coverage-v1","strategy_sha256":"6b1f2b3078f6cb98f8f7d74b04e18ccf6e84477de6b4c3df4cd1912d1e0260e3","tie_law":["largest-marginal-new-world-count","largest-individual-threshold-count","largest-discovery-mean-score","ascending-lineup-id"]}]'

TAIL_THRESHOLDS: Final = (
    ("ge_194", 194.0, ">="),
    ("gt_200", 200.0, ">"),
    ("gt_210", 210.0, ">"),
    ("gt_220", 220.0, ">"),
    ("gt_230", 230.0, ">"),
    ("gt_240", 240.0, ">"),
)
EFFECTIVE_SHOT_THRESHOLDS: Final = (200.0, 210.0, 220.0, 230.0)
PRIMARY_BASELINE_VIEW_ID: Final = "U"
PRIMARY_BASELINE_STRATEGY_ID: Final = "coverage-194-v1"
TAIL_CONTROL_STRATEGY_ID: Final = "tail-ladder-200-210-220-v1"
STRUCTURAL_CONTRAST_PROFILES: Final = frozenset({
    "remove-qb-stack",
    "remove-bring-back",
    "remove-all-five-shared-constraints",
})
EXPECTED_MAX_DIVERSITY_WINDOW: Final = 0.50
P200_ABSOLUTE_NONINFERIORITY_MARGIN: Final = 0.001
P200_RELATIVE_NONINFERIORITY_MARGIN: Final = 0.02
NUMERICAL_EIGENVALUE_FLOOR: Final = -1e-12
MICRO_SCALE: Final = 1_000_000
EXPECTED_MAX_DIVERSITY_WINDOW_MICRO: Final = 500_000
P200_ABSOLUTE_NONINFERIORITY_MARGIN_MICRO: Final = 1_000
P200_RELATIVE_MARGIN_NUMERATOR: Final = 2
P200_RELATIVE_MARGIN_DENOMINATOR: Final = 100

_SHA256_HEX: Final = frozenset("0123456789abcdef")
_BOUNDED_ID_RE: Final = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]*\Z")
_GCS_URI_RE: Final = re.compile(r"gs://[A-Za-z0-9][A-Za-z0-9._:/-]*\Z")
_PROJECTION_CANDIDATE_FIELDS: Final = frozenset({
    "lineup_id",
    "roster_player_ids",
    "training_origin_blocks",
    "training_source_arms",
    "training_occurrence_counts_by_block",
    "training_source_arms_by_block",
    "training_occurrence_count",
})


class CorpusR6CurrentBankCrossedScreenContractV1Error(ValueError):
    """The frozen current-bank screen contract cannot be preserved."""


def _fail(message: str) -> None:
    raise CorpusR6CurrentBankCrossedScreenContractV1Error(message)


def canonical_json_bytes_v1(value: object) -> bytes:
    try:
        return json.dumps(
            value,
            allow_nan=False,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise CorpusR6CurrentBankCrossedScreenContractV1Error(
            "value is not canonical JSON"
        ) from exc


def canonical_sha256_v1(value: object) -> str:
    return sha256(canonical_json_bytes_v1(value)).hexdigest()


def _with_hash(value: Mapping[str, object], *, field: str) -> dict[str, object]:
    body = dict(value)
    if field in body:
        _fail(f"self-hash field {field} already exists")
    body[field] = canonical_sha256_v1(body)
    return body


def _mapping(value: object, *, label: str) -> dict[str, object]:
    if not isinstance(value, Mapping) or any(type(key) is not str for key in value):
        _fail(f"{label} must be a string-keyed object")
    return dict(value)


def _sequence(value: object, *, label: str) -> list[object]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        _fail(f"{label} must be an ordered array")
    return list(value)


def _string(value: object, *, label: str) -> str:
    if type(value) is not str or not value:
        _fail(f"{label} must be a nonempty string")
    return value


def _bounded_identifier(
    value: object, *, label: str, maximum_utf8_bytes: int,
) -> str:
    retained = _string(value, label=label)
    if (
        len(retained.encode("utf-8")) > maximum_utf8_bytes
        or _BOUNDED_ID_RE.fullmatch(retained) is None
    ):
        _fail(f"{label} differs from its bounded ASCII identifier law")
    return retained


def _integer(
    value: object, *, label: str, minimum: int = 0,
    maximum: int | None = None,
) -> int:
    if (
        type(value) is not int
        or value < minimum
        or (maximum is not None and value > maximum)
    ):
        suffix = "" if maximum is None else f" and <= {maximum}"
        _fail(f"{label} must be an exact integer >= {minimum}{suffix}")
    return value


def _finite_float(value: object, *, label: str) -> float:
    if type(value) not in {int, float} or type(value) is bool:
        _fail(f"{label} must be a finite number")
    retained = float(value)
    if not math.isfinite(retained):
        _fail(f"{label} must be finite")
    return retained


def _probability(value: object, *, label: str) -> float:
    retained = _finite_float(value, label=label)
    if not 0.0 <= retained <= 1.0:
        _fail(f"{label} must be within [0,1]")
    return retained


def _sha256_hex(value: object, *, label: str) -> str:
    if (
        type(value) is not str
        or len(value) != 64
        or any(character not in _SHA256_HEX for character in value)
    ):
        _fail(f"{label} must be one lowercase SHA-256")
    return value


def _object_identity(value: object, *, label: str) -> dict[str, object]:
    item = _mapping(value, label=label)
    if set(item) != {"uri", "generation", "sha256", "bytes"}:
        _fail(f"{label} fields differ")
    uri = _string(item["uri"], label=f"{label} uri")
    generation = _string(item["generation"], label=f"{label} generation")
    size = _integer(
        item["bytes"], label=f"{label} bytes", minimum=1,
        maximum=MAX_IDENTITY_BYTES,
    )
    if (
        len(uri.encode("utf-8")) > MAX_GCS_URI_UTF8_BYTES
        or _GCS_URI_RE.fullmatch(uri) is None
        or not generation.isdigit()
        or generation.startswith("0")
        or len(generation) > MAX_GENERATION_DIGITS
    ):
        _fail(f"{label} transport identity differs")
    return {
        "uri": uri,
        "generation": generation,
        "sha256": _sha256_hex(item["sha256"], label=f"{label} sha256"),
        "bytes": size,
    }


def _validate_uri_policy(uri: str, *, label: str) -> str:
    retained = _string(uri, label=label)
    lowered = retained.lower()
    if any(fragment in lowered for fragment in _FORBIDDEN_URI_FRAGMENTS):
        _fail(f"{label} belongs to a forbidden URI family")
    if any(part in {"", ".", ".."} for part in retained.removeprefix("gs://").split("/")):
        _fail(f"{label} contains an empty or relative path component")
    return retained


def _safe_object_identity(value: object, *, label: str) -> dict[str, object]:
    identity = _object_identity(value, label=label)
    _validate_uri_policy(str(identity["uri"]), label=f"{label} uri")
    return identity


def _validate_one_generation_per_uri_v1(
    identities_value: object, *, label: str,
) -> list[dict[str, object]]:
    identities = [
        _safe_object_identity(value, label=f"{label}[{index}]")
        for index, value in enumerate(_sequence(identities_value, label=label))
    ]
    generation_by_uri: dict[str, str] = {}
    exact_by_uri: dict[str, dict[str, object]] = {}
    for identity in identities:
        uri = str(identity["uri"])
        generation = str(identity["generation"])
        if uri in generation_by_uri and generation_by_uri[uri] != generation:
            _fail(f"{label} addresses more than one generation for one URI")
        if uri in exact_by_uri and exact_by_uri[uri] != identity:
            _fail(f"{label} repeats one URI with inconsistent content identity")
        generation_by_uri[uri] = generation
        exact_by_uri[uri] = identity
    return identities


def _policy_block() -> dict[str, bool]:
    return dict(POLICY_CLAIMS)


def validate_policy_block_v1(value: object, *, label: str) -> dict[str, bool]:
    item = _mapping(value, label=f"{label} policy")
    if item != POLICY_CLAIMS:
        _fail(f"{label} policy claims differ")
    return dict(POLICY_CLAIMS)


def _bind_canonical_body_to_identity_v1(
    body: Mapping[str, object], identity_value: object, *, label: str,
) -> dict[str, object]:
    identity = _safe_object_identity(identity_value, label=f"{label} identity")
    raw = canonical_json_bytes_v1(dict(body))
    if len(raw) != identity["bytes"] or sha256(raw).hexdigest() != identity["sha256"]:
        _fail(f"{label} differs from its exact publication identity")
    return identity


def _float64_matrix_sha256_v1(matrix_value: object, *, label: str) -> str:
    matrix = np.asarray(matrix_value)
    if (
        matrix.dtype != np.dtype(np.float64)
        or matrix.ndim != 2
        or not matrix.shape[0]
        or not matrix.shape[1]
        or not np.isfinite(matrix).all()
    ):
        _fail(f"{label} must be one nonempty finite float64 matrix")
    array = np.ascontiguousarray(matrix, dtype="<f8")
    header = canonical_json_bytes_v1({
        "dtype": "float64-le",
        "shape": [int(array.shape[0]), int(array.shape[1])],
    })
    digest = sha256()
    digest.update(header)
    digest.update(b"\0")
    digest.update(memoryview(array).cast("B"))
    return digest.hexdigest()


def _score_row_sha256_fixture_v1(row_value: object) -> str:
    """Private fixture helper implementing the frozen score-row byte law."""
    row = np.asarray(row_value)
    if (
        row.dtype != np.dtype(np.float64)
        or row.ndim != 1
        or not row.size
        or not np.isfinite(row).all()
    ):
        _fail("fixture score row must be one nonempty finite float64 vector")
    array = np.ascontiguousarray(row, dtype="<f8")
    header = canonical_json_bytes_v1({
        "dtype": "float64-le",
        "shape": [int(array.shape[0])],
    })
    digest = sha256()
    digest.update(header)
    digest.update(b"\0")
    digest.update(memoryview(array).cast("B"))
    return digest.hexdigest()


def _ordered_score_row_ledger_fixture_v1(
    lineup_ids_value: object, scores_value: object,
) -> dict[str, object]:
    """Private synthetic helper; authoritative seams build this after reopen."""
    lineup_ids = [
        _string(value, label="score-row lineup id")
        for value in _sequence(lineup_ids_value, label="score-row lineup ids")
    ]
    scores = np.asarray(scores_value)
    if (
        lineup_ids != sorted(set(lineup_ids))
        or scores.dtype != np.dtype(np.float64)
        or scores.ndim != 2
        or scores.shape[0] != len(lineup_ids)
        or scores.shape[1] != 4 * WORLDS_PER_BLOCK
        or not np.isfinite(scores).all()
    ):
        _fail("fixture ordered score-row ledger inputs differ")
    rows = [
        {
            "lineup_id": lineup_id,
            "score_row_sha256": _score_row_sha256_fixture_v1(scores[index]),
        }
        for index, lineup_id in enumerate(lineup_ids)
    ]
    return {
        "dtype": "float64-le",
        "world_count": int(scores.shape[1]),
        "row_count": len(rows),
        "lineup_ids_sha256": canonical_sha256_v1(lineup_ids),
        "rows": rows,
        "rows_sha256": canonical_sha256_v1(rows),
        "score_matrix_shape": [int(scores.shape[0]), int(scores.shape[1])],
        "score_matrix_sha256": _float64_matrix_sha256_v1(
            scores, label="fixture score-row matrix"
        ),
    }


def _validate_score_row_ledger_v1(
    value: object, *, expected_lineup_ids: Sequence[str], expected_world_count: int,
) -> dict[str, object]:
    ledger = _mapping(value, label="ordered score-row ledger")
    if set(ledger) != {
        "dtype", "world_count", "row_count", "lineup_ids_sha256", "rows",
        "rows_sha256", "score_matrix_shape", "score_matrix_sha256",
    }:
        _fail("ordered score-row ledger fields differ")
    ids = [str(value) for value in expected_lineup_ids]
    rows = [
        _mapping(row, label=f"score-row ledger[{index}]")
        for index, row in enumerate(_sequence(ledger["rows"], label="score-row rows"))
    ]
    if any(set(row) != {"lineup_id", "score_row_sha256"} for row in rows):
        _fail("score-row ledger row fields differ")
    row_ids = [
        _string(row["lineup_id"], label="score-row ledger lineup id") for row in rows
    ]
    for row in rows:
        _sha256_hex(row["score_row_sha256"], label="score-row sha256")
    if (
        ledger["dtype"] != "float64-le"
        or ledger["world_count"] != expected_world_count
        or ledger["row_count"] != len(ids)
        or row_ids != ids
        or ids != sorted(set(ids))
        or ledger["lineup_ids_sha256"] != canonical_sha256_v1(ids)
        or ledger["rows_sha256"] != canonical_sha256_v1(rows)
        or ledger["score_matrix_shape"] != [len(ids), expected_world_count]
    ):
        _fail("ordered score-row ledger binding differs")
    _sha256_hex(ledger["score_matrix_sha256"], label="score matrix sha256")
    return ledger


def _sampled_score_row_ledger_from_full_v1(
    full_ledger_value: object, sampled_lineup_ids_value: object,
) -> dict[str, object]:
    """Derive, rather than attest, one exact ordered subset row ledger."""
    full = _mapping(full_ledger_value, label="full score-row ledger")
    full_rows = [
        _mapping(row, label=f"full score-row[{index}]")
        for index, row in enumerate(_sequence(full.get("rows"), label="full rows"))
    ]
    full_ids = [str(row.get("lineup_id")) for row in full_rows]
    retained_full = _validate_score_row_ledger_v1(
        full,
        expected_lineup_ids=full_ids,
        expected_world_count=4 * WORLDS_PER_BLOCK,
    )
    sampled_ids = [
        _string(value, label="sampled score-row lineup id")
        for value in _sequence(
            sampled_lineup_ids_value, label="sampled score-row lineup ids"
        )
    ]
    if sampled_ids != sorted(set(sampled_ids)) or not set(sampled_ids) <= set(full_ids):
        _fail("sampled score-row IDs differ from full ledger")
    by_id = {str(row["lineup_id"]): row for row in retained_full["rows"]}
    rows = [by_id[lineup_id] for lineup_id in sampled_ids]
    return {
        "dtype": "float64-le",
        "world_count": 4 * WORLDS_PER_BLOCK,
        "row_count": len(rows),
        "lineup_ids_sha256": canonical_sha256_v1(sampled_ids),
        "rows": rows,
        "rows_sha256": canonical_sha256_v1(rows),
        "source_full_rows_sha256": retained_full["rows_sha256"],
        "source_full_score_matrix_sha256": retained_full["score_matrix_sha256"],
    }


def _self_hash(value: Mapping[str, object], *, field: str, label: str) -> str:
    retained = _sha256_hex(value.get(field), label=f"{label} {field}")
    body = {key: item for key, item in value.items() if key != field}
    if canonical_sha256_v1(body) != retained:
        _fail(f"{label} self-hash differs")
    return retained


def canonical_world_columns_v1(training_blocks_value: object) -> list[dict[str, object]]:
    blocks = [
        _string(value, label="training block")
        for value in _sequence(training_blocks_value, label="training blocks")
    ]
    if (
        len(blocks) != 4
        or len(set(blocks)) != 4
        or blocks != [block for block in WORLD_BLOCKS if block in set(blocks)]
    ):
        _fail("training blocks must be four canonical ordered R6 blocks")
    return [
        {"block": block, "index": index}
        for block in blocks
        for index in range(WORLDS_PER_BLOCK)
    ]


def canonical_world_columns_sha256_v1(training_blocks_value: object) -> str:
    return canonical_sha256_v1(canonical_world_columns_v1(training_blocks_value))


def _fraction(
    numerator: object, denominator: object, *, label: str, allow_negative: bool = False,
) -> Fraction:
    minimum = -(2**63) if allow_negative else 0
    retained_numerator = _integer(numerator, label=f"{label} numerator", minimum=minimum)
    retained_denominator = _integer(
        denominator, label=f"{label} denominator", minimum=1
    )
    return Fraction(retained_numerator, retained_denominator)


def _round_fraction_ties_even(value: Fraction) -> int:
    floor = value.numerator // value.denominator
    remainder = value.numerator - floor * value.denominator
    doubled = remainder * 2
    if doubled < value.denominator:
        return floor
    if doubled > value.denominator:
        return floor + 1
    return floor if floor % 2 == 0 else floor + 1


def to_micro_v1(value: object, *, label: str) -> int:
    """Serialize one finite float64 scalar with ties-to-even micro rounding."""
    retained = _finite_float(value, label=label)
    scaled = np.rint(np.float64(retained) * np.float64(MICRO_SCALE))
    limits = np.iinfo(np.int64)
    if not np.isfinite(scaled) or scaled < limits.min or scaled > limits.max:
        _fail(f"{label} micro value exceeds int64")
    return int(np.int64(scaled))


def _profile_id(ordinal: int) -> str:
    try:
        expected_ordinal, profile_id, _ = PROFILE_IDENTITIES[ordinal]
    except IndexError as exc:
        raise CorpusR6CurrentBankCrossedScreenContractV1Error(
            "profile ordinal is outside the frozen registry"
        ) from exc
    if expected_ordinal != ordinal:
        _fail("profile registry ordinal differs")
    return profile_id


def isolated_view_id_v1(profile_ordinal: int) -> str:
    profile_id = _profile_id(profile_ordinal)
    return f"I:{profile_ordinal:02d}:{profile_id}"


def leave_one_out_view_id_v1(profile_ordinal: int) -> str:
    profile_id = _profile_id(profile_ordinal)
    return f"L:{profile_ordinal:02d}:{profile_id}"


def pair_union_view_id_v1(profile_ordinal: int) -> str:
    if profile_ordinal == 0:
        _fail("pair-union view requires one relaxed profile")
    profile_id = _profile_id(profile_ordinal)
    return f"P:{profile_ordinal:02d}:{profile_id}"


def exclusive_view_id_v1(profile_ordinal: int) -> str:
    profile_id = _profile_id(profile_ordinal)
    return f"E:{profile_ordinal:02d}:{profile_id}"


def frozen_profiles_v1() -> list[dict[str, object]]:
    """Return a detached copy of the contract-owned profile registry."""
    profiles = json.loads(_FROZEN_PROFILES_JSON)
    profile_tuples = tuple(
        (
            int(value["ordinal"]),
            str(value["parameter_set_id"]),
            str(value["parameter_set_sha256"]),
        )
        for value in profiles
    )
    if (
        profile_tuples != PROFILE_IDENTITIES
        or canonical_sha256_v1(profiles) != PROFILE_REGISTRY_SHA256
    ):
        _fail("contract-owned seven-profile registry differs")
    return profiles


def frozen_strategies_v1() -> list[dict[str, object]]:
    """Return a detached copy of the contract-owned selector registry."""
    strategies = json.loads(_FROZEN_STRATEGIES_JSON)
    strategy_tuples = tuple(
        (
            int(value["ordinal"]),
            str(value["strategy_id"]),
            str(value["strategy_sha256"]),
        )
        for value in strategies
    )
    if (
        strategy_tuples != STRATEGY_IDENTITIES
        or canonical_sha256_v1(strategies) != STRATEGY_REGISTRY_SHA256
    ):
        _fail("contract-owned eight-selector registry differs")
    return strategies


def _exact_contract_registries_v1() -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    return frozen_profiles_v1(), frozen_strategies_v1()


def frozen_contract_v1() -> dict[str, object]:
    """Return the executable constants that must match the tracked report."""
    profiles, strategies = _exact_contract_registries_v1()
    body = {
        "schema_version": CONTRACT_SCHEMA,
        "contract_id": CONTRACT_ID,
        "contract_report_path": CONTRACT_REPORT_PATH,
        "module_path": MODULE_PATH,
        "panel_identity": dict(PANEL_IDENTITY),
        "panel_self_sha256": PANEL_SELF_SHA256,
        "panel_slate_count": PANEL_SLATE_COUNT,
        "panel_rank_80_book_count": PANEL_RANK_80_BOOK_COUNT,
        "panel_prefix_count": PANEL_PREFIX_COUNT,
        "exact_structural_object_count": EXACT_STRUCTURAL_OBJECT_COUNT,
        "world_blocks": list(WORLD_BLOCKS),
        "worlds_per_block": WORLDS_PER_BLOCK,
        "prefix_sizes": list(PREFIX_SIZES),
        "entry_budget": ENTRY_BUDGET,
        "subsample_replicates": SUBSAMPLE_REPLICATES,
        "broad_screen_replicates": BROAD_SCREEN_REPLICATES,
        "phase_domains": [BROAD_SCREEN_PHASE, CONFIRMATION_PHASE],
        "maximum_broad_selector_fits": MAXIMUM_BROAD_SELECTOR_FITS,
        "maximum_confirmation_selector_fits": MAXIMUM_CONFIRMATION_SELECTOR_FITS,
        "maximum_selector_fits": MAXIMUM_SELECTOR_FITS,
        "all_block_final_fit_count": 0,
        "logical_fold_selection_count_per_phase": (
            LOGICAL_FOLD_SELECTION_COUNT_PER_PHASE
        ),
        "selector_os_process_count_per_phase": (
            SELECTOR_OS_PROCESS_COUNT_PER_PHASE
        ),
        "folds_per_slate_projection_bundle": FOLDS_PER_SLATE,
        "selector_subprocess_artifact_read_count": 4,
        "slate_assembler_artifact_body_read_count": 0,
        "selector_process_isolation_law": (
            "one-logical-slate-fold-broker-matrix-chain-four-training-artifacts-only"
        ),
        "selection_receipt_assembly_law": (
            "five-fold-receipts-to-one-no-artifact-slate-assembler"
        ),
        "output_object_count": OUTPUT_OBJECT_COUNT,
        "bootstrap_resamples": BOOTSTRAP_RESAMPLES,
        "profiles": profiles,
        "profile_registry_sha256": PROFILE_REGISTRY_SHA256,
        "strategies": strategies,
        "strategy_registry_sha256": STRATEGY_REGISTRY_SHA256,
        "tail_thresholds": [
            {"metric_id": metric_id, "threshold": threshold, "operator": operator}
            for metric_id, threshold, operator in TAIL_THRESHOLDS
        ],
        "effective_shot_thresholds": list(EFFECTIVE_SHOT_THRESHOLDS),
        "primary_baseline": {
            "view_id": PRIMARY_BASELINE_VIEW_ID,
            "strategy_id": PRIMARY_BASELINE_STRATEGY_ID,
            "prefix_size": ENTRY_BUDGET,
        },
        "mandatory_controls": [
            {
                "view_id": "U",
                "strategy_id": PRIMARY_BASELINE_STRATEGY_ID,
                "prefix_size": ENTRY_BUDGET,
            },
            {
                "view_id": "U",
                "strategy_id": TAIL_CONTROL_STRATEGY_ID,
                "prefix_size": ENTRY_BUDGET,
            },
            {
                "view_id": isolated_view_id_v1(0),
                "strategy_id": PRIMARY_BASELINE_STRATEGY_ID,
                "prefix_size": ENTRY_BUDGET,
            },
        ],
        "p200_noninferiority": {
            "absolute_margin_micro": P200_ABSOLUTE_NONINFERIORITY_MARGIN_MICRO,
            "relative_margin_numerator": P200_RELATIVE_MARGIN_NUMERATOR,
            "relative_margin_denominator": P200_RELATIVE_MARGIN_DENOMINATOR,
        },
        "expected_max_diversity_window_micro": (
            EXPECTED_MAX_DIVERSITY_WINDOW_MICRO
        ),
        "structural_contrast_profiles": sorted(STRUCTURAL_CONTRAST_PROFILES),
        "uses_realized_outcomes": False,
        "historical_scoring_licensed": False,
        "corpus_regeneration_licensed": False,
        "matchup_source_licensed": False,
        "graph_mutation_licensed": False,
        "production_change_licensed": False,
        "promotion_authority": False,
        "decision_authority": False,
        "policy": _policy_block(),
    }
    return _with_hash(body, field="contract_sha256")


def validate_panel_identity_v1(
    identity_value: object, *, panel_self_sha256: object
) -> dict[str, object]:
    identity = _mapping(identity_value, label="panel identity")
    if identity != PANEL_IDENTITY or panel_self_sha256 != PANEL_SELF_SHA256:
        _fail("sealed panel identity differs from the frozen contract")
    return dict(PANEL_IDENTITY)


def validate_narrow_projection_v1(value: object) -> dict[str, object]:
    """Validate the only authoritative selection input exposed by preflight."""
    item = _mapping(value, label="narrow selection-input projection")
    expected_fields = {
        "schema_version", "contract_id", "slate_id", "fit_scope_id",
        "source_task_result_identity", "task_result_payload_sha256",
        "later_source_identity", "world_artifact_identities",
        "fit_candidate_view_sha256", "selection_provenance_sha256",
        "training_blocks", "heldout_block", "training_world_columns_sha256",
        "candidates", "candidate_lineup_order_sha256", "candidate_rosters_sha256",
        "candidate_rows_sha256", "expected_training_score_matrix_sha256",
        "expected_training_score_shape", "policy", "projection_sha256",
    }
    if set(item) != expected_fields:
        _fail("narrow selection-input projection fields differ")
    _self_hash(item, field="projection_sha256", label="narrow projection")
    if (
        item.get("schema_version") != PROJECTION_SCHEMA
        or item.get("contract_id") != CONTRACT_ID
    ):
        _fail("narrow selection-input projection policy differs")
    validate_policy_block_v1(item.get("policy"), label="narrow projection")
    slate_id = _string(item.get("slate_id"), label="projection slate id")
    fit_scope_id = _string(item.get("fit_scope_id"), label="projection fit scope")
    heldout = _string(item.get("heldout_block"), label="projection heldout block")
    if heldout not in WORLD_BLOCKS or fit_scope_id != f"holdout-{heldout}":
        _fail("projection heldout scope differs")
    training_blocks = [
        _string(value, label="projection training block")
        for value in _sequence(item.get("training_blocks"), label="training blocks")
    ]
    expected_training_blocks = [block for block in WORLD_BLOCKS if block != heldout]
    if training_blocks != expected_training_blocks:
        _fail("projection training block order differs")
    expected_column_sha = canonical_world_columns_sha256_v1(training_blocks)
    if item.get("training_world_columns_sha256") != expected_column_sha:
        _fail("projection training world-column hash differs")

    source_identity = _safe_object_identity(
        item.get("source_task_result_identity"), label="source task result"
    )
    later_source = _safe_object_identity(
        item.get("later_source_identity"), label="later source"
    )
    worlds_raw = _mapping(
        item.get("world_artifact_identities"), label="world artifact identities"
    )
    expected_world_roles = {f"world_artifact_{block.lower()}" for block in WORLD_BLOCKS}
    if set(worlds_raw) != expected_world_roles:
        _fail("projection world artifact roles differ")
    worlds = {
        role: _safe_object_identity(identity, label=f"projection {role}")
        for role, identity in worlds_raw.items()
    }
    if len({identity["uri"] for identity in worlds.values()}) != len(WORLD_BLOCKS):
        _fail("projection world artifact URI repeats")
    _validate_one_generation_per_uri_v1(
        [source_identity, later_source, *worlds.values()],
        label="projection authorities",
    )
    for field in (
        "task_result_payload_sha256", "fit_candidate_view_sha256",
        "selection_provenance_sha256", "candidate_lineup_order_sha256",
        "candidate_rosters_sha256", "candidate_rows_sha256",
        "expected_training_score_matrix_sha256",
    ):
        _sha256_hex(item.get(field), label=f"projection {field}")

    raw_candidates = _sequence(item.get("candidates"), label="projection candidates")
    if not ENTRY_BUDGET <= len(raw_candidates) <= MAX_SELECTION_CANDIDATES_PER_FOLD:
        _fail("projection candidate count differs from its fixed-panel bounds")
    candidates: list[dict[str, object]] = []
    known_profiles = {profile_id for _, profile_id, _ in PROFILE_IDENTITIES}
    prior_id = ""
    for offset, raw_candidate in enumerate(raw_candidates):
        candidate = _mapping(raw_candidate, label=f"projection candidate[{offset}]")
        if set(candidate) != _PROJECTION_CANDIDATE_FIELDS:
            _fail("projection candidate fields differ")
        lineup_id = _bounded_identifier(
            candidate["lineup_id"], label="candidate lineup id",
            maximum_utf8_bytes=MAX_LINEUP_ID_UTF8_BYTES,
        )
        roster = [
            _bounded_identifier(
                player_id, label="candidate roster player",
                maximum_utf8_bytes=MAX_PLAYER_ID_UTF8_BYTES,
            )
            for player_id in _sequence(
                candidate["roster_player_ids"], label="candidate roster"
            )
        ]
        origin_blocks = [
            _string(block, label="candidate origin block")
            for block in _sequence(
                candidate["training_origin_blocks"], label="candidate origin blocks"
            )
        ]
        source_arms = [
            _string(arm, label="candidate source arm")
            for arm in _sequence(
                candidate["training_source_arms"], label="candidate source arms"
            )
        ]
        counts = _mapping(
            candidate["training_occurrence_counts_by_block"],
            label="candidate occurrence counts",
        )
        arms_by_block_raw = _mapping(
            candidate["training_source_arms_by_block"],
            label="candidate arms by block",
        )
        if (
            lineup_id <= prior_id
            or len(roster) != ROSTER_SIZE
            or roster != sorted(set(roster))
            or source_arms != sorted(set(source_arms))
            or not source_arms
            or not set(source_arms) <= known_profiles
            or set(counts) != set(training_blocks)
            or set(arms_by_block_raw) != set(training_blocks)
        ):
            _fail("projection candidate identity/provenance differs")
        prior_id = lineup_id
        normalized_counts: dict[str, int] = {}
        normalized_arms_by_block: dict[str, list[str]] = {}
        for block in training_blocks:
            count = _integer(
                counts[block], label=f"candidate {block} occurrence count",
                maximum=MAX_OCCURRENCE_COUNT,
            )
            arms = [
                _string(arm, label=f"candidate {block} source arm")
                for arm in _sequence(
                    arms_by_block_raw[block], label=f"candidate {block} source arms"
                )
            ]
            if (
                arms != sorted(set(arms))
                or not set(arms) <= known_profiles
                or (count == 0) != (arms == [])
            ):
                _fail("projection candidate block provenance differs")
            normalized_counts[block] = count
            normalized_arms_by_block[block] = arms
        total_occurrence_count = _integer(
            candidate["training_occurrence_count"],
            label="candidate training occurrence count",
            maximum=MAX_OCCURRENCE_COUNT,
        )
        if (
            origin_blocks
            != [block for block in training_blocks if normalized_counts[block] > 0]
            or source_arms
            != sorted({arm for arms in normalized_arms_by_block.values() for arm in arms})
            or total_occurrence_count != sum(normalized_counts.values())
        ):
            _fail("projection candidate provenance summary differs")
        candidates.append({
            "lineup_id": lineup_id,
            "roster_player_ids": roster,
            "training_origin_blocks": origin_blocks,
            "training_source_arms": source_arms,
            "training_occurrence_counts_by_block": normalized_counts,
            "training_source_arms_by_block": normalized_arms_by_block,
            "training_occurrence_count": total_occurrence_count,
        })
    lineup_ids = [candidate["lineup_id"] for candidate in candidates]
    rosters = [candidate["roster_player_ids"] for candidate in candidates]
    shape = item.get("expected_training_score_shape")
    if (
        item.get("candidate_lineup_order_sha256") != canonical_sha256_v1(lineup_ids)
        or item.get("candidate_rosters_sha256") != canonical_sha256_v1(rosters)
        or item.get("candidate_rows_sha256") != canonical_sha256_v1(candidates)
        or shape != [len(candidates), len(training_blocks) * WORLDS_PER_BLOCK]
    ):
        _fail("projection candidate/matrix binding differs")
    normalized = dict(item)
    normalized["source_task_result_identity"] = source_identity
    normalized["later_source_identity"] = later_source
    normalized["world_artifact_identities"] = worlds
    normalized["candidates"] = candidates
    if canonical_json_bytes_v1(normalized) != canonical_json_bytes_v1(item):
        _fail("projection canonical normalization differs")
    _string(slate_id, label="projection slate id")
    return normalized


def build_projection_bundle_v1(
    *, source_ordinal: int, fold_projections: object,
) -> dict[str, object]:
    """Build one durable slate bundle from exactly five direct projections."""
    ordinal = _integer(
        source_ordinal, label="projection bundle source ordinal"
    )
    if ordinal >= PANEL_SLATE_COUNT:
        _fail("projection bundle source ordinal is outside 0..53")
    projections = [
        validate_narrow_projection_v1(value)
        for value in _sequence(fold_projections, label="fold projections")
    ]
    if len(projections) != FOLDS_PER_SLATE:
        _fail("projection bundle requires exactly five fold projections")
    slate_id = str(projections[0]["slate_id"])
    if (
        [projection["heldout_block"] for projection in projections]
        != list(WORLD_BLOCKS)
        or [projection["fit_scope_id"] for projection in projections]
        != [f"holdout-{block}" for block in WORLD_BLOCKS]
        or any(projection["slate_id"] != slate_id for projection in projections)
    ):
        _fail("projection bundle fold order or slate binding differs")
    common_fields = (
        "source_task_result_identity",
        "task_result_payload_sha256",
        "later_source_identity",
        "world_artifact_identities",
    )
    for field in common_fields:
        if any(projection[field] != projections[0][field] for projection in projections):
            _fail(f"projection bundle common {field} differs across folds")
    body = {
        "schema_version": PROJECTION_BUNDLE_SCHEMA,
        "contract_id": CONTRACT_ID,
        "source_ordinal": ordinal,
        "slate_id": slate_id,
        "panel_identity": dict(PANEL_IDENTITY),
        "panel_self_sha256": PANEL_SELF_SHA256,
        "structural_object_count": EXACT_STRUCTURAL_OBJECT_COUNT,
        "fold_count": FOLDS_PER_SLATE,
        "fold_order": list(WORLD_BLOCKS),
        "fold_projections": projections,
        "fold_projection_sha256s": [
            projection["projection_sha256"] for projection in projections
        ],
        "fold_projections_sha256": canonical_sha256_v1(projections),
        "selector_executed": False,
        "old_book_fields_copied": False,
        "policy": _policy_block(),
    }
    return _with_hash(body, field="projection_bundle_sha256")


def validate_projection_bundle_v1(value: object) -> dict[str, object]:
    item = _mapping(value, label="slate projection bundle")
    if set(item) != {
        "schema_version", "contract_id", "source_ordinal", "slate_id",
        "panel_identity", "panel_self_sha256", "structural_object_count",
        "fold_count", "fold_order", "fold_projections",
        "fold_projection_sha256s", "fold_projections_sha256",
        "selector_executed", "old_book_fields_copied", "policy",
        "projection_bundle_sha256",
    }:
        _fail("slate projection bundle fields differ")
    _self_hash(item, field="projection_bundle_sha256", label="projection bundle")
    if (
        item["schema_version"] != PROJECTION_BUNDLE_SCHEMA
        or item["contract_id"] != CONTRACT_ID
        or item["panel_identity"] != PANEL_IDENTITY
        or item["panel_self_sha256"] != PANEL_SELF_SHA256
        or item["structural_object_count"] != EXACT_STRUCTURAL_OBJECT_COUNT
        or item["selector_executed"] is not False
        or item["old_book_fields_copied"] is not False
    ):
        _fail("slate projection bundle authority differs")
    validate_policy_block_v1(item["policy"], label="projection bundle")
    expected = build_projection_bundle_v1(
        source_ordinal=_integer(
            item["source_ordinal"], label="projection bundle source ordinal"
        ),
        fold_projections=item["fold_projections"],
    )
    if canonical_json_bytes_v1(item) != canonical_json_bytes_v1(expected):
        _fail("slate projection bundle canonical replay differs")
    return expected


def validate_projection_bundle_authority_v1(
    value: object,
    *,
    publication_identity: object,
    topology: object,
    topology_identity: object,
) -> dict[str, object]:
    """Validate a bundle only when bound to exact reopened publication bytes."""
    bundle = validate_projection_bundle_v1(value)
    retained_topology = validate_result_topology_v1(topology)
    _bind_canonical_body_to_identity_v1(
        retained_topology, topology_identity, label="result topology"
    )
    identity = _bind_canonical_body_to_identity_v1(
        bundle, publication_identity, label="projection bundle"
    )
    if identity["uri"] != _topology_uri_v1(
        retained_topology,
        role="projection",
        source_ordinal=int(bundle["source_ordinal"]),
    ):
        _fail("projection bundle URI differs from result topology")
    return bundle


def candidate_dedup_diagnostics_from_projection_v1(
    value: object,
) -> dict[str, object]:
    """Separate occurrence collapse from surviving roster aliases."""
    projection = validate_narrow_projection_v1(value)
    candidates = list(projection["candidates"])
    occurrence_count = sum(
        int(candidate["training_occurrence_count"]) for candidate in candidates
    )
    rosters = [tuple(candidate["roster_player_ids"]) for candidate in candidates]
    if occurrence_count < len(candidates):
        _fail("projection occurrence total is below unique candidate count")
    return {
        "candidate_row_count": len(candidates),
        "training_occurrence_count": occurrence_count,
        "occurrence_dedup_loss_count": occurrence_count - len(candidates),
        "unique_canonical_roster_count": len(set(rosters)),
        "surviving_roster_alias_count": len(candidates) - len(set(rosters)),
        "candidate_rows_sha256": projection["candidate_rows_sha256"],
    }


def derive_view_registry_from_projection_v1(value: object) -> dict[str, object]:
    projection = validate_narrow_projection_v1(value)
    return _derive_view_registry_fixture_v1(projection["candidates"])


def _derive_view_registry_fixture_v1(
    eligible_candidates_value: object,
) -> dict[str, object]:
    """Derive profile views only from fold-stripped training provenance."""
    raw_candidates = _sequence(
        eligible_candidates_value, label="eligible candidates"
    )
    candidates: list[tuple[str, frozenset[str]]] = []
    known_profiles = {profile_id for _, profile_id, _ in PROFILE_IDENTITIES}
    for offset, raw_candidate in enumerate(raw_candidates):
        candidate = _mapping(raw_candidate, label=f"eligible candidate[{offset}]")
        lineup_id = _string(
            candidate.get("lineup_id"), label=f"eligible candidate[{offset}] lineup id"
        )
        raw_arms = _sequence(
            candidate.get("training_source_arms"),
            label=f"eligible candidate[{offset}] training source arms",
        )
        arms = [
            _string(value, label=f"eligible candidate[{offset}] source arm")
            for value in raw_arms
        ]
        if not arms or arms != sorted(set(arms)) or not set(arms) <= known_profiles:
            _fail("eligible candidate training source arms differ")
        candidates.append((lineup_id, frozenset(arms)))
    ids = [lineup_id for lineup_id, _ in candidates]
    if ids != sorted(set(ids)) or len(ids) < ENTRY_BUDGET:
        _fail("eligible lineup ids must be sorted, unique, and support exact-80")

    by_view: dict[str, list[str]] = {"U": ids}
    incumbent = _profile_id(0)
    for ordinal, profile_id, _ in PROFILE_IDENTITIES:
        by_view[isolated_view_id_v1(ordinal)] = [
            lineup_id for lineup_id, arms in candidates if profile_id in arms
        ]
        by_view[leave_one_out_view_id_v1(ordinal)] = [
            lineup_id
            for lineup_id, arms in candidates
            if any(arm != profile_id for arm in arms)
        ]
        by_view[exclusive_view_id_v1(ordinal)] = [
            lineup_id for lineup_id, arms in candidates if arms == {profile_id}
        ]
        if ordinal > 0:
            by_view[pair_union_view_id_v1(ordinal)] = [
                lineup_id
                for lineup_id, arms in candidates
                if incumbent in arms or profile_id in arms
            ]

    ordered_views = []
    for view_id in [
        "U",
        *(isolated_view_id_v1(index) for index in range(len(PROFILE_IDENTITIES))),
        *(leave_one_out_view_id_v1(index) for index in range(len(PROFILE_IDENTITIES))),
        *(pair_union_view_id_v1(index) for index in range(1, len(PROFILE_IDENTITIES))),
        *(exclusive_view_id_v1(index) for index in range(len(PROFILE_IDENTITIES))),
    ]:
        lineup_ids = by_view[view_id]
        if lineup_ids != sorted(set(lineup_ids)):
            _fail("derived view lineup ids differ from canonical order")
        ordered_views.append({
            "view_id": view_id,
            "lineup_count": len(lineup_ids),
            "exact_80_feasible": len(lineup_ids) >= ENTRY_BUDGET,
            "lineup_ids": lineup_ids,
            "lineup_ids_sha256": canonical_sha256_v1(lineup_ids),
        })
    body = {
        "schema_version": VIEW_REGISTRY_SCHEMA,
        "candidate_count": len(ids),
        "candidate_lineup_ids_sha256": canonical_sha256_v1(ids),
        "views": ordered_views,
        "uses_training_source_arms_only": True,
        "uses_realized_outcomes": False,
    }
    return _with_hash(body, field="view_registry_sha256")


def _view_ids_by_id(view_registry_value: object) -> dict[str, list[str]]:
    registry = _mapping(view_registry_value, label="view registry")
    if set(registry) != {
        "schema_version", "candidate_count", "candidate_lineup_ids_sha256",
        "views", "uses_training_source_arms_only", "uses_realized_outcomes",
        "view_registry_sha256",
    }:
        _fail("view registry fields differ")
    _self_hash(registry, field="view_registry_sha256", label="view registry")
    if (
        registry["schema_version"] != VIEW_REGISTRY_SCHEMA
        or registry["uses_training_source_arms_only"] is not True
        or registry["uses_realized_outcomes"] is not False
    ):
        _fail("view registry policy differs")
    raw_views = _sequence(registry.get("views"), label="view registry views")
    result: dict[str, list[str]] = {}
    for offset, raw_view in enumerate(raw_views):
        view = _mapping(raw_view, label=f"view[{offset}]")
        if set(view) != {
            "view_id", "lineup_count", "exact_80_feasible", "lineup_ids",
            "lineup_ids_sha256",
        }:
            _fail("view registry row fields differ")
        view_id = _string(view.get("view_id"), label=f"view[{offset}] id")
        ids = [
            _string(value, label=f"view[{offset}] lineup id")
            for value in _sequence(view.get("lineup_ids"), label=f"view[{offset}] ids")
        ]
        if (
            view_id in result
            or ids != sorted(set(ids))
            or view.get("lineup_count") != len(ids)
            or view.get("exact_80_feasible") is not (len(ids) >= ENTRY_BUDGET)
            or view.get("lineup_ids_sha256") != canonical_sha256_v1(ids)
        ):
            _fail("view registry contents differ")
        result[view_id] = ids
    expected_order = [
        "U",
        *(isolated_view_id_v1(index) for index in range(len(PROFILE_IDENTITIES))),
        *(leave_one_out_view_id_v1(index) for index in range(len(PROFILE_IDENTITIES))),
        *(pair_union_view_id_v1(index) for index in range(1, len(PROFILE_IDENTITIES))),
        *(exclusive_view_id_v1(index) for index in range(len(PROFILE_IDENTITIES))),
    ]
    if list(result) != expected_order or len(result) != 28:
        _fail("view registry order/lattice differs")
    union_ids = result["U"]
    if (
        registry["candidate_count"] != len(union_ids)
        or registry["candidate_lineup_ids_sha256"] != canonical_sha256_v1(union_ids)
        or any(not set(ids) <= set(union_ids) for ids in result.values())
    ):
        _fail("view registry union binding differs")
    return result


def _deterministic_equal_count_samples_fixture_v1(
    *,
    view_registry: Mapping[str, object],
    slate_id: str,
    fit_scope_id: str,
    phase: str,
) -> dict[str, object]:
    """Freeze one broad or 32 confirmation common-count samples."""
    slate = _string(slate_id, label="slate id")
    fit_scope = _string(fit_scope_id, label="fit scope id")
    if fit_scope not in {f"holdout-{block}" for block in WORLD_BLOCKS}:
        _fail("equal-count sampling requires one registered held-out fit scope")
    retained_phase = _string(phase, label="sampling phase")
    if retained_phase not in {BROAD_SCREEN_PHASE, CONFIRMATION_PHASE}:
        _fail("sampling phase differs")
    replicate_count = (
        BROAD_SCREEN_REPLICATES
        if retained_phase == BROAD_SCREEN_PHASE
        else SUBSAMPLE_REPLICATES
    )
    ids_by_view = _view_ids_by_id(view_registry)
    inferential_view_ids = [
        "U",
        *(isolated_view_id_v1(index) for index in range(len(PROFILE_IDENTITIES))),
    ]
    if any(view_id not in ids_by_view for view_id in inferential_view_ids):
        _fail("view registry omits an inferential profile view")
    target = min(len(ids_by_view[view_id]) for view_id in inferential_view_ids)
    if target < ENTRY_BUDGET:
        _fail("common equal-count target cannot support exact-80")

    replicates: list[dict[str, object]] = []
    for replicate in range(replicate_count):
        sampled_views: list[dict[str, object]] = []
        seed_material = {
            "contract_id": CONTRACT_ID,
            "panel_object_sha256": PANEL_IDENTITY["sha256"],
            "panel_self_sha256": PANEL_SELF_SHA256,
            "slate_id": slate,
            "fit_scope_id": fit_scope,
            "phase": retained_phase,
            "replicate": replicate,
        }
        seed_bytes = canonical_json_bytes_v1(seed_material)
        for view_id in inferential_view_ids:
            source_ids = ids_by_view[view_id]
            retained = (
                list(source_ids)
                if len(source_ids) == target
                else sorted(
                    source_ids,
                    key=lambda lineup_id: (
                        sha256(seed_bytes + b"\x00" + lineup_id.encode("utf-8")).digest(),
                        lineup_id,
                    ),
                )[:target]
            )
            retained = sorted(retained)
            if len(retained) != target or len(set(retained)) != target:
                _fail("deterministic equal-count sample differs")
            sampled_views.append({
                "view_id": view_id,
                "source_count": len(source_ids),
                "target_count": target,
                "seed_material_sha256": sha256(seed_bytes).hexdigest(),
                "sampled_lineup_ids": retained,
                "sampled_lineup_ids_sha256": canonical_sha256_v1(retained),
            })
        replicates.append({
            "replicate": replicate,
            "seed_material": seed_material,
            "seed_material_sha256": sha256(seed_bytes).hexdigest(),
            "views": sampled_views,
        })
    body = {
        "schema_version": SUBSAMPLE_SCHEMA,
        "slate_id": slate,
        "fit_scope_id": fit_scope,
        "phase": retained_phase,
        "target_count": target,
        "replicate_count": replicate_count,
        "replicates": replicates,
        "uses_realized_outcomes": False,
    }
    return _with_hash(body, field="subsample_sha256")


def deterministic_equal_count_samples_from_projection_v1(
    value: object, *, phase: str,
) -> dict[str, object]:
    """Authoritative sampling entry point bound to a validated projection."""
    projection = validate_narrow_projection_v1(value)
    registry = derive_view_registry_from_projection_v1(projection)
    return _deterministic_equal_count_samples_fixture_v1(
        view_registry=registry,
        slate_id=str(projection["slate_id"]),
        fit_scope_id=str(projection["fit_scope_id"]),
        phase=phase,
    )


def strategy_executable_fingerprint_v1(value: object) -> str:
    """Hash exactly the dispatcher-observable selector semantics."""
    strategy = _mapping(value, label="strategy fingerprint")
    required = {
        "schema_version", "ordinal", "strategy_id", "method", "entry_budget",
        "parameters", "tie_law", "selection_inputs", "description",
        "strategy_sha256",
    }
    if set(strategy) != required:
        _fail("strategy fingerprint fields differ")
    _self_hash(strategy, field="strategy_sha256", label="strategy fingerprint")
    if strategy["entry_budget"] != ENTRY_BUDGET:
        _fail("strategy fingerprint entry budget differs")
    return canonical_sha256_v1({
        "schema_version": strategy["schema_version"],
        "method": strategy["method"],
        "entry_budget": strategy["entry_budget"],
        "parameters": strategy["parameters"],
        "tie_law": strategy["tie_law"],
        "selection_inputs": strategy["selection_inputs"],
    })


def _selection_prefixes_v1(
    selected_lineup_ids: Sequence[str], roster_by_id: Mapping[str, Sequence[str]],
) -> list[dict[str, object]]:
    ids = [str(value) for value in selected_lineup_ids]
    rosters = [list(roster_by_id[lineup_id]) for lineup_id in ids]
    rows = []
    for prefix_size in PREFIX_SIZES:
        prefix_ids = ids[:prefix_size]
        prefix_rosters = rosters[:prefix_size]
        rows.append({
            "prefix_size": prefix_size,
            "selected_lineup_ids_sha256": canonical_sha256_v1(prefix_ids),
            "selected_rosters_sha256": canonical_sha256_v1(prefix_rosters),
            "prefix_payload_sha256": canonical_sha256_v1({
                "selected_lineup_ids": prefix_ids,
                "selected_rosters": prefix_rosters,
            }),
        })
    return rows


def _selection_trace_binding_v1(
    *,
    selected_lineup_ids: Sequence[str],
    sampled_lineup_ids: Sequence[str],
    sampled_score_row_ledger: Mapping[str, object],
) -> list[dict[str, object]]:
    """Derive the exact selected order/row-hash trace; no free trace hash."""
    selected = [str(value) for value in selected_lineup_ids]
    sampled = [str(value) for value in sampled_lineup_ids]
    row_hash_by_id = {
        str(row["lineup_id"]): str(row["score_row_sha256"])
        for row in sampled_score_row_ledger["rows"]
    }
    ordinal_by_id = {lineup_id: index for index, lineup_id in enumerate(sampled)}
    if (
        len(selected) != ENTRY_BUDGET
        or len(set(selected)) != ENTRY_BUDGET
        or not set(selected) <= set(sampled)
        or set(row_hash_by_id) != set(sampled)
    ):
        _fail("selection trace inputs differ")
    return [
        {
            "selection_ordinal": ordinal,
            "lineup_id": lineup_id,
            "sampled_lineup_ordinal": ordinal_by_id[lineup_id],
            "score_row_sha256": row_hash_by_id[lineup_id],
        }
        for ordinal, lineup_id in enumerate(selected)
    ]


def _validate_selection_cell_v1(
    value: object,
    *,
    projection: Mapping[str, object],
    expected_sample: Mapping[str, object],
    strategy: Mapping[str, object],
    replicate: int,
    full_candidate_score_row_ledger: Mapping[str, object],
) -> dict[str, object]:
    cell = _mapping(value, label="selection cell")
    if set(cell) != {
        "replicate", "view_id", "sampled_lineup_ids",
        "sampled_lineup_ids_sha256", "rank_seed_sha256",
        "strategy_ordinal", "strategy_id", "strategy_sha256",
        "executable_fingerprint_sha256", "training_score_row_ledger",
        "selected_lineup_ids", "selected_lineup_ids_sha256",
        "selected_rosters_sha256", "prefixes", "selection_trace",
        "selection_trace_sha256",
        "selection_cell_sha256",
    }:
        _fail("selection cell fields differ")
    _self_hash(cell, field="selection_cell_sha256", label="selection cell")
    sample = _mapping(expected_sample, label="expected sample")
    sampled_ids = [
        _string(item, label="sampled lineup id")
        for item in _sequence(cell["sampled_lineup_ids"], label="sampled IDs")
    ]
    if (
        cell["replicate"] != replicate
        or cell["view_id"] != sample["view_id"]
        or sampled_ids != sample["sampled_lineup_ids"]
        or cell["sampled_lineup_ids_sha256"]
        != sample["sampled_lineup_ids_sha256"]
        or cell["rank_seed_sha256"] != sample["seed_material_sha256"]
        or cell["strategy_ordinal"] != strategy["ordinal"]
        or cell["strategy_id"] != strategy["strategy_id"]
        or cell["strategy_sha256"] != strategy["strategy_sha256"]
        or cell["executable_fingerprint_sha256"]
        != strategy_executable_fingerprint_v1(strategy)
    ):
        _fail("selection cell sample or selector binding differs")
    ledger = _mapping(
        cell["training_score_row_ledger"], label="sampled score-row ledger"
    )
    expected_ledger = _sampled_score_row_ledger_from_full_v1(
        full_candidate_score_row_ledger, sampled_ids
    )
    if canonical_json_bytes_v1(ledger) != canonical_json_bytes_v1(expected_ledger):
        _fail("selection cell score-row ledger differs from exact full subset")
    selected_ids = [
        _string(item, label="selected lineup id")
        for item in _sequence(cell["selected_lineup_ids"], label="selected IDs")
    ]
    candidate_by_id = {
        str(candidate["lineup_id"]): candidate
        for candidate in projection["candidates"]
    }
    if (
        len(selected_ids) != ENTRY_BUDGET
        or len(set(selected_ids)) != ENTRY_BUDGET
        or not set(selected_ids) <= set(sampled_ids)
        or cell["selected_lineup_ids_sha256"] != canonical_sha256_v1(selected_ids)
    ):
        _fail("selection cell exact-80 order differs")
    roster_by_id = {
        lineup_id: list(candidate_by_id[lineup_id]["roster_player_ids"])
        for lineup_id in selected_ids
    }
    expected_prefixes = _selection_prefixes_v1(selected_ids, roster_by_id)
    expected_trace = _selection_trace_binding_v1(
        selected_lineup_ids=selected_ids,
        sampled_lineup_ids=sampled_ids,
        sampled_score_row_ledger=ledger,
    )
    if (
        cell["selected_rosters_sha256"]
        != canonical_sha256_v1([roster_by_id[lineup_id] for lineup_id in selected_ids])
        or cell["prefixes"] != expected_prefixes
        or ledger["lineup_ids_sha256"] != cell["sampled_lineup_ids_sha256"]
        or cell["selection_trace"] != expected_trace
        or cell["selection_trace_sha256"]
        != canonical_sha256_v1(expected_trace)
    ):
        _fail("selection cell roster, matrix, prefix, or trace binding differs")
    return cell


def _nominee_keys_v1(value: object) -> list[tuple[str, str]]:
    nomination = _mapping(value, label="nomination authority")
    nominees = [
        _mapping(item, label=f"nominee[{index}]")
        for index, item in enumerate(
            _sequence(nomination.get("nominees"), label="nominees")
        )
    ]
    keys = [
        (
            _string(item.get("view_id"), label="nominee view id"),
            _string(item.get("strategy_id"), label="nominee strategy id"),
        )
        for item in nominees
    ]
    if (
        not MINIMUM_CONFIRMATION_NOMINEES <= len(keys) <= MAXIMUM_CONFIRMATION_NOMINEES
        or len(keys) != len(set(keys))
    ):
        _fail("nomination authority cell lattice differs")
    return keys


def _validate_confirmation_nomination_authority_v1(
    *,
    nomination_publication: object,
    nomination_publication_identity: object,
    topology: object,
    topology_identity: object,
) -> tuple[dict[str, object], dict[str, object], dict[str, object]]:
    """Reopen ordinal 163, which alone carries broad authority to confirmation."""
    retained_topology = validate_result_topology_v1(topology)
    retained_topology_identity = _bind_canonical_body_to_identity_v1(
        retained_topology, topology_identity, label="result topology"
    )
    publication = validate_nomination_publication_authority_v1(
        nomination_publication,
        publication_identity=nomination_publication_identity,
    )
    broad = publication["broad_phase_authority"]
    if broad["topology_identity"] != retained_topology_identity:
        _fail("confirmation broad authority topology differs")
    retained_nomination = publication["nomination"]
    retained_identity = _safe_object_identity(
        nomination_publication_identity, label="nomination publication"
    )
    if retained_identity["uri"] != _topology_uri_v1(
        retained_topology, role="nomination"
    ):
        _fail("confirmation nomination URI differs from result topology")
    return retained_nomination, retained_identity, broad


def _build_selection_fold_receipt_structural_v1(
    *,
    source_ordinal: int,
    fold_ordinal: int,
    projection: object,
    phase: str,
    full_candidate_score_row_ledger: object,
    cells: object,
    nomination: object | None = None,
    broad_phase_authority: object | None = None,
) -> dict[str, object]:
    """Build one ephemeral four-block child receipt; no fifth block is addressable."""
    source = _integer(source_ordinal, label="selection source ordinal")
    fold = _integer(fold_ordinal, label="selection fold ordinal")
    if source >= PANEL_SLATE_COUNT or fold >= FOLDS_PER_SLATE:
        _fail("selection source/fold ordinal differs")
    retained_projection = validate_narrow_projection_v1(projection)
    heldout = WORLD_BLOCKS[fold]
    if retained_projection["heldout_block"] != heldout:
        _fail("selection fold projection differs")
    retained_phase = _string(phase, label="selection phase")
    if retained_phase not in {BROAD_SCREEN_PHASE, CONFIRMATION_PHASE}:
        _fail("selection phase differs")
    candidate_ids = [
        str(candidate["lineup_id"]) for candidate in retained_projection["candidates"]
    ]
    full_ledger = _validate_score_row_ledger_v1(
        full_candidate_score_row_ledger,
        expected_lineup_ids=candidate_ids,
        expected_world_count=4 * WORLDS_PER_BLOCK,
    )
    if full_ledger["score_matrix_sha256"] != retained_projection[
        "expected_training_score_matrix_sha256"
    ]:
        _fail("recomputed full training matrix differs from sealed expected hash")
    sample_receipt = deterministic_equal_count_samples_from_projection_v1(
        retained_projection, phase=retained_phase
    )
    view_registry = derive_view_registry_from_projection_v1(retained_projection)
    sample_by_key = {
        (int(replicate["replicate"]), str(view["view_id"])): view
        for replicate in sample_receipt["replicates"]
        for view in replicate["views"]
    }
    strategies = frozen_strategies_v1()
    strategy_by_id = {str(strategy["strategy_id"]): strategy for strategy in strategies}
    if retained_phase == BROAD_SCREEN_PHASE:
        expected_keys = [
            (0, view_id, str(strategy["strategy_id"]))
            for view_id in [
                "U", *(isolated_view_id_v1(index) for index in range(len(PROFILE_IDENTITIES)))
            ]
            for strategy in strategies
        ]
        nomination_sha256 = None
    else:
        if nomination is None or broad_phase_authority is None:
            _fail("confirmation selection requires broad nomination authority")
        broad_authority = validate_broad_phase_authority_v1(
            broad_phase_authority
        )
        nomination_item = validate_nomination_v1(
            nomination, broad_phase_authority=broad_authority
        )
        nomination_sha256 = _sha256_hex(
            nomination_item.get("nomination_sha256"), label="nomination sha256"
        )
        expected_keys = [
            (replicate, view_id, strategy_id)
            for replicate in range(SUBSAMPLE_REPLICATES)
            for view_id, strategy_id in _nominee_keys_v1(nomination_item)
        ]
    raw_cells = [
        _mapping(item, label=f"selection cell[{index}]")
        for index, item in enumerate(_sequence(cells, label="selection cells"))
    ]
    observed_keys = [
        (int(item.get("replicate", -1)), str(item.get("view_id", "")), str(item.get("strategy_id", "")))
        for item in raw_cells
    ]
    if observed_keys != expected_keys:
        _fail("selection fold cell order/lattice differs")
    normalized_cells = [
        _validate_selection_cell_v1(
            item,
            projection=retained_projection,
            expected_sample=sample_by_key[(replicate, view_id)],
            strategy=strategy_by_id[strategy_id],
            replicate=replicate,
            full_candidate_score_row_ledger=full_ledger,
        )
        for item, (replicate, view_id, strategy_id) in zip(
            raw_cells, expected_keys, strict=True
        )
    ]
    training_roles = [
        f"world_artifact_{block.lower()}"
        for block in retained_projection["training_blocks"]
    ]
    training_identities = [
        retained_projection["world_artifact_identities"][role]
        for role in training_roles
    ]
    body = {
        "schema_version": SELECTION_FOLD_RECEIPT_SCHEMA,
        "contract_id": CONTRACT_ID,
        "source_ordinal": source,
        "fold_ordinal": fold,
        "selector_process_ordinal": source * FOLDS_PER_SLATE + fold,
        "selector_process_count": FOLD_SELECTOR_SUBPROCESS_COUNT,
        "slate_id": retained_projection["slate_id"],
        "fit_scope_id": retained_projection["fit_scope_id"],
        "heldout_block": heldout,
        "phase": retained_phase,
        "projection_sha256": retained_projection["projection_sha256"],
        "training_blocks": list(retained_projection["training_blocks"]),
        "training_artifact_roles": training_roles,
        "training_artifact_identities": training_identities,
        "training_artifact_count": 4,
        "heldout_artifact_addressable": False,
        "heldout_artifact_read": False,
        "full_candidate_score_row_ledger": full_ledger,
        "subsample_sha256": sample_receipt["subsample_sha256"],
        "full_view_registry_sha256": view_registry["view_registry_sha256"],
        "nomination_sha256": nomination_sha256,
        "broad_phase_authority_sha256": (
            None
            if retained_phase == BROAD_SCREEN_PHASE
            else broad_authority["broad_phase_authority_sha256"]
        ),
        "cell_count": len(normalized_cells),
        "cells": normalized_cells,
        "cells_sha256": canonical_sha256_v1(normalized_cells),
        "policy": _policy_block(),
    }
    return _with_hash(body, field="selection_fold_receipt_sha256")


def validate_selection_fold_receipt_v1(
    value: object,
    *,
    projection: object,
    nomination: object | None = None,
    broad_phase_authority: object | None = None,
) -> dict[str, object]:
    item = _mapping(value, label="selection fold receipt")
    _self_hash(
        item, field="selection_fold_receipt_sha256", label="selection fold receipt"
    )
    validate_policy_block_v1(item.get("policy"), label="selection fold receipt")
    expected = _build_selection_fold_receipt_structural_v1(
        source_ordinal=_integer(item.get("source_ordinal"), label="selection source ordinal"),
        fold_ordinal=_integer(item.get("fold_ordinal"), label="selection fold ordinal"),
        projection=projection,
        phase=_string(item.get("phase"), label="selection phase"),
        full_candidate_score_row_ledger=item.get("full_candidate_score_row_ledger"),
        cells=item.get("cells"),
        nomination=nomination,
        broad_phase_authority=broad_phase_authority,
    )
    if canonical_json_bytes_v1(item) != canonical_json_bytes_v1(expected):
        _fail("selection fold receipt canonical replay differs")
    return expected


def _validate_child_execution_evidence_v1(
    value: object, *, phase: str, source_ordinal: int, fold_ordinal: int,
    fold_receipt: Mapping[str, object], bootstrap_manifest: Mapping[str, object],
    bootstrap_manifest_identity: object, launch_intent_identity: object,
) -> dict[str, object]:
    evidence = _mapping(value, label="child execution evidence")
    _self_hash(
        evidence,
        field="child_execution_evidence_sha256",
        label="child execution evidence",
    )
    role = (
        "broad-fold-selector"
        if phase == BROAD_SCREEN_PHASE
        else "confirmation-fold-selector"
    )
    process_chain = bootstrap_process_spec_v1(
        bootstrap_manifest, process_role=role
    )["process_chain"]
    training_reads = [
        _mapping(row, label="child training-artifact read")
        for row in _sequence(
            evidence.get("training_artifact_read_ledger"),
            label="child training-artifact reads",
        )
    ]
    expected_training_roles = [
        f"training-world-{block}"
        for block in WORLD_BLOCKS
        if block != WORLD_BLOCKS[fold_ordinal]
    ]
    expected_training_identities = list(
        fold_receipt["training_artifact_identities"]
    )
    for row in training_reads:
        if set(row) != {"ordinal", "channel", "role", "identity"}:
            _fail("child training-artifact read fields differ")
        _safe_object_identity(row["identity"], label="child training artifact")
    runtimes = []
    for runtime_name in ("broker_runtime_evidence", "matrix_runtime_evidence"):
        runtime = _mapping(evidence.get(runtime_name), label=runtime_name)
        _self_hash(runtime, field="runtime_evidence_sha256", label=runtime_name)
        runtimes.append(runtime)
    child_bytes = _integer(
        evidence.get("child_output_bytes"), label="child output bytes", minimum=1
    )
    child_ceiling = _integer(
        evidence.get("child_output_byte_ceiling"),
        label="child output byte ceiling",
        minimum=1,
    )
    if (
        evidence.get("schema_version")
        != "corpus-r6-current-bank-child-execution-evidence/v1"
        or evidence.get("phase") != phase
        or evidence.get("source_ordinal") != source_ordinal
        or evidence.get("fold_ordinal") != fold_ordinal
        or evidence.get("heldout_block") != WORLD_BLOCKS[fold_ordinal]
        or evidence.get("process_ordinal")
        != source_ordinal * FOLDS_PER_SLATE + fold_ordinal
        or evidence.get("logical_fold_process_count") != 1
        or evidence.get("os_process_count") != 2
        or evidence.get("ordered_process_chain") != process_chain
        or evidence.get("ordered_process_chain_sha256")
        != canonical_sha256_v1(process_chain)
        or evidence.get("broker_command") != process_chain[0]["command"]
        or evidence.get("broker_entrypoint_sha256")
        != process_chain[0]["entrypoint_sha256"]
        or evidence.get("matrix_command") != process_chain[1]["command"]
        or evidence.get("matrix_entrypoint_sha256")
        != process_chain[1]["entrypoint_sha256"]
        or [row.get("role") for row in training_reads] != expected_training_roles
        or [row.get("ordinal") for row in training_reads]
        != sorted({
            _integer(row.get("ordinal"), label="child training read ordinal")
            for row in training_reads
        })
        or any(row.get("channel") != "process-budget" for row in training_reads)
        or [row.get("identity") for row in training_reads]
        != expected_training_identities
        or evidence.get("training_artifact_read_count") != 4
        or evidence.get("training_artifact_read_ledger_sha256")
        != canonical_sha256_v1(training_reads)
        or evidence.get("bootstrap_manifest_identity")
        != _safe_object_identity(
            bootstrap_manifest_identity, label="child bootstrap manifest"
        )
        or evidence.get("bootstrap_manifest_sha256")
        != bootstrap_manifest["bootstrap_manifest_sha256"]
        or evidence.get("process_budget_identity") is None
        or evidence.get("launch_intent_identity")
        != _safe_object_identity(
            launch_intent_identity, label="child launch intent"
        )
        or evidence.get("fit_count") != fold_receipt["cell_count"]
        or evidence.get("broker_runtime_evidence_sha256")
        != runtimes[0]["runtime_evidence_sha256"]
        or evidence.get("matrix_runtime_evidence_sha256")
        != runtimes[1]["runtime_evidence_sha256"]
        or any(
            runtime.get("command") != process_chain[index]["command"]
            or runtime.get("entrypoint_sha256")
            != process_chain[index]["entrypoint_sha256"]
            or runtime.get("code_commit") != bootstrap_manifest["code_commit"]
            or runtime.get("image_digest") != bootstrap_manifest["image_digest"]
            for index, runtime in enumerate(runtimes)
        )
        or child_bytes > child_ceiling
        or evidence.get("selection_fold_receipt_sha256")
        != fold_receipt["selection_fold_receipt_sha256"]
        or evidence.get("runtime_evidence_strength")
        != "process-environment-observation-only"
        or evidence.get("outer_launch_authority_binding_required") is not True
        or evidence.get("outer_launch_authority_identity")
        != _safe_object_identity(
            launch_intent_identity, label="child outer launch authority"
        )
        or evidence.get("transport_capability_reached_matrix_process") is not False
        or evidence.get("heldout_identity_reached_matrix_process") is not False
    ):
        _fail("child execution evidence authority/lattice differs")
    expected_fields = {
        "schema_version", "phase", "source_ordinal", "fold_ordinal",
        "heldout_block", "process_ordinal", "logical_fold_process_count",
        "os_process_count", "ordered_process_chain",
        "ordered_process_chain_sha256", "broker_command",
        "broker_entrypoint_sha256", "matrix_command",
        "matrix_entrypoint_sha256", "broker_runtime_evidence",
        "broker_runtime_evidence_sha256", "matrix_runtime_evidence",
        "matrix_runtime_evidence_sha256", "training_artifact_read_ledger",
        "training_artifact_read_ledger_sha256",
        "training_artifact_read_count", "bootstrap_manifest_identity",
        "bootstrap_manifest_sha256", "process_budget_identity",
        "launch_intent_identity", "fit_count", "matrix_capability_sha256",
        "matrix_response_sha256", "matrix_response_bytes",
        "child_output_bytes", "child_output_byte_ceiling",
        "selection_fold_receipt_sha256", "runtime_evidence_strength",
        "outer_launch_authority_binding_required",
        "outer_launch_authority_identity",
        "transport_capability_reached_matrix_process",
        "heldout_identity_reached_matrix_process",
        "child_execution_evidence_sha256",
    }
    if set(evidence) != expected_fields:
        _fail("child execution evidence fields differ")
    for field in (
        "matrix_capability_sha256", "matrix_response_sha256",
        "broker_runtime_evidence_sha256", "matrix_runtime_evidence_sha256",
    ):
        _sha256_hex(evidence[field], label=f"child {field}")
    response_bytes = _integer(
        evidence["matrix_response_bytes"], label="matrix response bytes", minimum=1
    )
    if response_bytes > child_ceiling:
        _fail("matrix response exceeds child byte ceiling")
    _safe_object_identity(
        evidence["process_budget_identity"], label="child process budget"
    )
    return evidence


def build_selection_receipt_v1(
    *,
    projection_bundle: object,
    projection_bundle_identity: object,
    topology: object,
    topology_identity: object,
    phase: str,
    fold_receipts: object,
    bootstrap_manifest: object,
    bootstrap_manifest_identity: object,
    launch_intent_identity: object,
    child_execution_evidence: object,
    nomination_publication: object | None = None,
    nomination_publication_identity: object | None = None,
) -> dict[str, object]:
    """No-artifact assembler for five isolated selector subprocess receipts."""
    bundle = validate_projection_bundle_authority_v1(
        projection_bundle,
        publication_identity=projection_bundle_identity,
        topology=topology,
        topology_identity=topology_identity,
    )
    retained_topology = validate_result_topology_v1(topology)
    retained_topology_identity = _bind_canonical_body_to_identity_v1(
        retained_topology, topology_identity, label="result topology"
    )
    retained_phase = _string(phase, label="selection receipt phase")
    raw_folds = _sequence(fold_receipts, label="selection fold receipts")
    if len(raw_folds) != FOLDS_PER_SLATE:
        _fail("selection receipt assembler requires exactly five fold receipts")
    if retained_phase == CONFIRMATION_PHASE:
        if (
            nomination_publication is None
            or nomination_publication_identity is None
        ):
            _fail("confirmation receipt requires ordinal-163 publication")
        (
            retained_nomination,
            retained_nomination_identity,
            retained_broad_authority,
        ) = _validate_confirmation_nomination_authority_v1(
            nomination_publication=nomination_publication,
            nomination_publication_identity=nomination_publication_identity,
            topology=retained_topology,
            topology_identity=retained_topology_identity,
        )
    elif retained_phase == BROAD_SCREEN_PHASE:
        if any(value is not None for value in (
            nomination_publication, nomination_publication_identity,
        )):
            _fail("broad receipt cannot accept nomination authority")
        retained_nomination = None
        retained_nomination_identity = None
        retained_broad_authority = None
    else:
        _fail("selection receipt phase differs")
    folds = [
        validate_selection_fold_receipt_v1(
            raw_folds[index],
            projection=bundle["fold_projections"][index],
            nomination=retained_nomination,
            broad_phase_authority=retained_broad_authority,
        )
        for index in range(FOLDS_PER_SLATE)
    ]
    manifest = validate_bootstrap_manifest_authority_v1(
        bootstrap_manifest,
        publication_identity=bootstrap_manifest_identity,
        topology=retained_topology,
        topology_identity=retained_topology_identity,
    )
    launch_authority = _launch_authority_from_bootstrap_v1(
        manifest, launch_intent_identity
    )
    raw_evidence = _sequence(
        child_execution_evidence, label="selection child execution evidence"
    )
    if len(raw_evidence) != FOLDS_PER_SLATE:
        _fail("selection receipt requires five child execution authorities")
    evidence = [
        _validate_child_execution_evidence_v1(
            raw_evidence[fold],
            phase=retained_phase,
            source_ordinal=int(bundle["source_ordinal"]),
            fold_ordinal=fold,
            fold_receipt=folds[fold],
            bootstrap_manifest=manifest,
            bootstrap_manifest_identity=bootstrap_manifest_identity,
            launch_intent_identity=launch_authority,
        )
        for fold in range(FOLDS_PER_SLATE)
    ]
    if [fold["fold_ordinal"] for fold in folds] != list(range(FOLDS_PER_SLATE)):
        _fail("selection receipt fold order differs")
    if (
        len({row["child_execution_evidence_sha256"] for row in evidence})
        != FOLDS_PER_SLATE
        or len({
            canonical_sha256_v1(row["process_budget_identity"])
            for row in evidence
        }) != FOLDS_PER_SLATE
    ):
        _fail("selection child evidence/budget authorities repeat")
    expected_cells_per_fold = (
        BROAD_FITS_PER_FOLD
        if retained_phase == BROAD_SCREEN_PHASE
        else SUBSAMPLE_REPLICATES * len(_nominee_keys_v1(retained_nomination))
    )
    if (
        any(fold["phase"] != retained_phase for fold in folds)
        or any(fold["source_ordinal"] != bundle["source_ordinal"] for fold in folds)
        or any(fold["cell_count"] != expected_cells_per_fold for fold in folds)
        or [fold["selector_process_ordinal"] for fold in folds]
        != [
            int(bundle["source_ordinal"]) * FOLDS_PER_SLATE + fold
            for fold in range(FOLDS_PER_SLATE)
        ]
    ):
        _fail("selection receipt phase/source/process/cell lattice differs")
    fit_count = sum(int(fold["cell_count"]) for fold in folds)
    maximum = (
        BROAD_FITS_PER_FOLD * FOLDS_PER_SLATE
        if retained_phase == BROAD_SCREEN_PHASE
        else SUBSAMPLE_REPLICATES * MAXIMUM_CONFIRMATION_NOMINEES * FOLDS_PER_SLATE
    )
    if fit_count > maximum:
        _fail("selection receipt fit count exceeds phase ceiling")
    body = {
        "schema_version": SELECTION_RECEIPT_SCHEMA,
        "contract_id": CONTRACT_ID,
        "phase": retained_phase,
        "source_ordinal": bundle["source_ordinal"],
        "slate_id": bundle["slate_id"],
        "projection_bundle_identity": _safe_object_identity(
            projection_bundle_identity, label="projection bundle identity"
        ),
        "projection_bundle_sha256": bundle["projection_bundle_sha256"],
        "logical_fold_selection_count": FOLDS_PER_SLATE,
        "logical_fold_selection_ordinals": [
            int(fold["selector_process_ordinal"]) for fold in folds
        ],
        "selector_os_process_count": 2 * FOLDS_PER_SLATE,
        "child_execution_evidence": evidence,
        "child_execution_evidence_sha256s": [
            row["child_execution_evidence_sha256"] for row in evidence
        ],
        "child_execution_evidence_set_sha256": canonical_sha256_v1(evidence),
        "bootstrap_manifest_identity": _safe_object_identity(
            bootstrap_manifest_identity, label="selection bootstrap manifest"
        ),
        "bootstrap_manifest_sha256": manifest["bootstrap_manifest_sha256"],
        "launch_intent_identity": launch_authority,
        "fold_receipts": folds,
        "fold_receipt_sha256s": [
            fold["selection_fold_receipt_sha256"] for fold in folds
        ],
        "fold_receipts_sha256": canonical_sha256_v1(folds),
        "full_view_registry_sha256s": [
            fold["full_view_registry_sha256"] for fold in folds
        ],
        "fit_count": fit_count,
        "nomination_publication_identity": retained_nomination_identity,
        "nomination_publication_sha256": (
            None
            if nomination_publication is None
            else validate_nomination_publication_v1(
                nomination_publication
            )["nomination_publication_sha256"]
        ),
        "nomination_sha256": (
            None
            if retained_nomination is None
            else retained_nomination["nomination_sha256"]
        ),
        "broad_phase_authority_sha256": (
            None
            if retained_broad_authority is None
            else retained_broad_authority["broad_phase_authority_sha256"]
        ),
        "topology_identity": retained_topology_identity,
        "assembler_artifact_body_read_count": 0,
        "assembler_selector_execution_count": 0,
        "immutable_before_heldout_read": True,
        "policy": _policy_block(),
    }
    return _with_hash(body, field="selection_receipt_sha256")


def validate_selection_receipt_v1(
    value: object,
    *,
    projection_bundle: object,
    projection_bundle_identity: object,
    topology: object,
    topology_identity: object,
    bootstrap_manifest: object,
    bootstrap_manifest_identity: object,
    launch_intent_identity: object,
    nomination_publication: object | None = None,
    nomination_publication_identity: object | None = None,
) -> dict[str, object]:
    item = _mapping(value, label="selection receipt")
    _self_hash(item, field="selection_receipt_sha256", label="selection receipt")
    validate_policy_block_v1(item.get("policy"), label="selection receipt")
    expected = build_selection_receipt_v1(
        projection_bundle=projection_bundle,
        projection_bundle_identity=projection_bundle_identity,
        topology=topology,
        topology_identity=topology_identity,
        phase=_string(item.get("phase"), label="selection receipt phase"),
        fold_receipts=item.get("fold_receipts"),
        bootstrap_manifest=bootstrap_manifest,
        bootstrap_manifest_identity=bootstrap_manifest_identity,
        launch_intent_identity=launch_intent_identity,
        child_execution_evidence=item.get("child_execution_evidence"),
        nomination_publication=nomination_publication,
        nomination_publication_identity=nomination_publication_identity,
    )
    if canonical_json_bytes_v1(item) != canonical_json_bytes_v1(expected):
        _fail("selection receipt canonical replay differs")
    return expected


def validate_selection_receipt_authority_v1(
    value: object,
    *,
    publication_identity: object,
    projection_bundle: object,
    projection_bundle_identity: object,
    topology: object,
    topology_identity: object,
    bootstrap_manifest: object,
    bootstrap_manifest_identity: object,
    launch_intent_identity: object,
    nomination_publication: object | None = None,
    nomination_publication_identity: object | None = None,
) -> dict[str, object]:
    receipt = validate_selection_receipt_v1(
        value,
        projection_bundle=projection_bundle,
        projection_bundle_identity=projection_bundle_identity,
        topology=topology,
        topology_identity=topology_identity,
        bootstrap_manifest=bootstrap_manifest,
        bootstrap_manifest_identity=bootstrap_manifest_identity,
        launch_intent_identity=launch_intent_identity,
        nomination_publication=nomination_publication,
        nomination_publication_identity=nomination_publication_identity,
    )
    publication = _bind_canonical_body_to_identity_v1(
        receipt, publication_identity, label="selection receipt"
    )
    retained_topology = validate_result_topology_v1(topology)
    expected_role = (
        "broad-selection-receipt"
        if receipt["phase"] == BROAD_SCREEN_PHASE
        else "confirmation-selection-receipt"
    )
    if publication["uri"] != _topology_uri_v1(
        retained_topology,
        role=expected_role,
        source_ordinal=int(receipt["source_ordinal"]),
    ):
        _fail("selection receipt URI differs from result topology")
    return receipt


def _build_evaluation_result_fixture_v1(
    *,
    selection_receipt: object,
    selection_receipt_identity: object,
    projection_bundle: object,
    projection_bundle_identity: object,
    topology: object,
    topology_identity: object,
    fold_summaries: object,
    nomination: object | None = None,
    nomination_identity: object | None = None,
    broad_phase_authority: object | None = None,
) -> dict[str, object]:
    """Bind one slate's five held-out evaluation summaries to its receipt."""
    receipt = validate_selection_receipt_authority_v1(
        selection_receipt,
        publication_identity=selection_receipt_identity,
        projection_bundle=projection_bundle,
        projection_bundle_identity=projection_bundle_identity,
        topology=topology,
        topology_identity=topology_identity,
        nomination=nomination,
        nomination_identity=nomination_identity,
        broad_phase_authority=broad_phase_authority,
    )
    bundle = validate_projection_bundle_authority_v1(
        projection_bundle,
        publication_identity=projection_bundle_identity,
        topology=topology,
        topology_identity=topology_identity,
    )
    raw_summaries = _sequence(fold_summaries, label="evaluation fold summaries")
    if len(raw_summaries) != FOLDS_PER_SLATE:
        _fail("evaluation result requires exactly five fold summaries")
    normalized = []
    for fold, raw in enumerate(raw_summaries):
        row = _mapping(raw, label=f"evaluation fold summary[{fold}]")
        if set(row) != {
            "fold_ordinal", "heldout_block", "heldout_world_count",
            "selection_fold_receipt_sha256", "heldout_artifact_identity",
            "evaluated_selection_cell_count", "evaluated_prefix_count",
            "metric_rows_sha256",
        }:
            _fail("evaluation fold summary fields differ")
        projection = bundle["fold_projections"][fold]
        fold_receipt = receipt["fold_receipts"][fold]
        artifact = _safe_object_identity(
            row["heldout_artifact_identity"],
            label=f"evaluation heldout artifact[{fold}]",
        )
        expected_artifact = projection["world_artifact_identities"][
            f"world_artifact_{WORLD_BLOCKS[fold].lower()}"
        ]
        cell_count = int(fold_receipt["cell_count"])
        if (
            row["fold_ordinal"] != fold
            or row["heldout_block"] != WORLD_BLOCKS[fold]
            or row["heldout_world_count"] != WORLDS_PER_BLOCK
            or row["selection_fold_receipt_sha256"]
            != fold_receipt["selection_fold_receipt_sha256"]
            or artifact != expected_artifact
            or row["evaluated_selection_cell_count"] != cell_count
            or row["evaluated_prefix_count"] != cell_count * len(PREFIX_SIZES)
        ):
            _fail("evaluation fold summary authority/count differs")
        normalized.append({
            "fold_ordinal": fold,
            "heldout_block": WORLD_BLOCKS[fold],
            "heldout_world_count": WORLDS_PER_BLOCK,
            "selection_fold_receipt_sha256": fold_receipt[
                "selection_fold_receipt_sha256"
            ],
            "heldout_artifact_identity": artifact,
            "evaluated_selection_cell_count": cell_count,
            "evaluated_prefix_count": cell_count * len(PREFIX_SIZES),
            "metric_rows_sha256": _sha256_hex(
                row["metric_rows_sha256"],
                label=f"evaluation metric rows[{fold}]",
            ),
        })
    body = {
        "schema_version": EVALUATION_RESULT_SCHEMA,
        "contract_id": CONTRACT_ID,
        "phase": receipt["phase"],
        "source_ordinal": receipt["source_ordinal"],
        "slate_id": receipt["slate_id"],
        "selection_receipt_identity": _safe_object_identity(
            selection_receipt_identity, label="selection receipt identity"
        ),
        "selection_receipt_sha256": receipt["selection_receipt_sha256"],
        "projection_bundle_identity": _safe_object_identity(
            projection_bundle_identity, label="projection bundle identity"
        ),
        "projection_bundle_sha256": bundle["projection_bundle_sha256"],
        "topology_identity": _safe_object_identity(
            topology_identity, label="result topology identity"
        ),
        "fold_count": FOLDS_PER_SLATE,
        "fold_summaries": normalized,
        "fold_summaries_sha256": canonical_sha256_v1(normalized),
        "heldout_world_count_per_fold": WORLDS_PER_BLOCK,
        "selection_code_callable": False,
        "policy": _policy_block(),
    }
    return _with_hash(body, field="evaluation_result_sha256")


def _validate_evaluation_result_fixture_v1(
    value: object,
    *,
    selection_receipt: object,
    selection_receipt_identity: object,
    projection_bundle: object,
    projection_bundle_identity: object,
    topology: object,
    topology_identity: object,
    nomination: object | None = None,
    nomination_identity: object | None = None,
    broad_phase_authority: object | None = None,
) -> dict[str, object]:
    item = _mapping(value, label="evaluation result")
    _self_hash(item, field="evaluation_result_sha256", label="evaluation result")
    validate_policy_block_v1(item.get("policy"), label="evaluation result")
    expected = _build_evaluation_result_fixture_v1(
        selection_receipt=selection_receipt,
        selection_receipt_identity=selection_receipt_identity,
        projection_bundle=projection_bundle,
        projection_bundle_identity=projection_bundle_identity,
        topology=topology,
        topology_identity=topology_identity,
        fold_summaries=item.get("fold_summaries"),
        nomination=nomination,
        nomination_identity=nomination_identity,
        broad_phase_authority=broad_phase_authority,
    )
    if canonical_json_bytes_v1(item) != canonical_json_bytes_v1(expected):
        _fail("evaluation result canonical replay differs")
    return expected


def _validate_evaluation_result_fixture_authority_v1(
    value: object,
    *,
    publication_identity: object,
    selection_receipt: object,
    selection_receipt_identity: object,
    projection_bundle: object,
    projection_bundle_identity: object,
    topology: object,
    topology_identity: object,
    nomination: object | None = None,
    nomination_identity: object | None = None,
    broad_phase_authority: object | None = None,
) -> dict[str, object]:
    result = _validate_evaluation_result_fixture_v1(
        value,
        selection_receipt=selection_receipt,
        selection_receipt_identity=selection_receipt_identity,
        projection_bundle=projection_bundle,
        projection_bundle_identity=projection_bundle_identity,
        topology=topology,
        topology_identity=topology_identity,
        nomination=nomination,
        nomination_identity=nomination_identity,
        broad_phase_authority=broad_phase_authority,
    )
    publication = _bind_canonical_body_to_identity_v1(
        result, publication_identity, label="evaluation result"
    )
    retained_topology = validate_result_topology_v1(topology)
    role = (
        "broad-evaluation-result"
        if result["phase"] == BROAD_SCREEN_PHASE
        else "confirmation-evaluation-result"
    )
    if publication["uri"] != _topology_uri_v1(
        retained_topology,
        role=role,
        source_ordinal=int(result["source_ordinal"]),
    ):
        _fail("evaluation result URI differs from result topology")
    return result


def _effective_independent_tail_shots_fixture_v1(
    selected_scores_value: object,
    *,
    threshold: float,
    operator: str = ">",
) -> dict[str, object]:
    """Private synthetic-array helper for the registered tail-rank metric."""
    if operator != ">":
        _fail("effective-shot metric is authoritative only for strict thresholds")
    retained_threshold = _finite_float(threshold, label="tail threshold")
    if retained_threshold not in EFFECTIVE_SHOT_THRESHOLDS:
        _fail("effective-shot threshold is not registered")
    scores = np.asarray(selected_scores_value)
    if (
        scores.dtype != np.dtype(np.float64)
        or scores.ndim != 2
        or not 1 <= scores.shape[0] <= ENTRY_BUDGET
        or scores.shape[1] < 2
        or not np.isfinite(scores).all()
    ):
        _fail("selected held-out score matrix shape/dtype/content differs")
    events = scores > retained_threshold if operator == ">" else scores >= retained_threshold
    counts = np.count_nonzero(events, axis=1)
    zero_count = int(np.count_nonzero(counts == 0))
    all_count = int(np.count_nonzero(counts == scores.shape[1]))
    active_mask = (counts > 0) & (counts < scores.shape[1])
    active = np.asarray(events[active_mask], dtype=np.float64)
    active_count = int(active.shape[0])

    pairwise_mean: float | None = None
    pairwise_minimum: float | None = None
    pairwise_maximum: float | None = None
    active_pair_count = 0
    if active_count == 0:
        participation_ratio = 0.0
        entropy_effective_rank = 0.0
    elif active_count == 1:
        participation_ratio = 1.0
        entropy_effective_rank = 1.0
    else:
        centered = active - np.mean(active, axis=1, keepdims=True, dtype=np.float64)
        norms = np.sqrt(np.sum(centered * centered, axis=1, dtype=np.float64))
        if not np.isfinite(norms).all() or np.any(norms <= 0.0):
            _fail("active tail rows have invalid variance")
        correlations = (centered @ centered.T) / np.outer(norms, norms)
        correlations = (correlations + correlations.T) / 2.0
        np.fill_diagonal(correlations, 1.0)
        triangle = correlations[np.triu_indices(active_count, k=1)]
        active_pair_count = int(triangle.size)
        pairwise_mean = float(np.mean(triangle, dtype=np.float64))
        pairwise_minimum = float(np.min(triangle))
        pairwise_maximum = float(np.max(triangle))
        raw_eigenvalues = np.linalg.eigvalsh(correlations)
        minimum = float(np.min(raw_eigenvalues))
        if minimum < NUMERICAL_EIGENVALUE_FLOOR:
            _fail("tail-event correlation matrix is not positive semidefinite")
        clipped = np.maximum(raw_eigenvalues, 0.0)
        eigen_sum = float(np.sum(clipped, dtype=np.float64))
        squared_sum = float(np.sum(clipped * clipped, dtype=np.float64))
        if eigen_sum <= 0.0 or squared_sum <= 0.0:
            _fail("tail-event eigenvalue mass differs")
        participation_ratio = (eigen_sum * eigen_sum) / squared_sum
        probabilities = clipped / eigen_sum
        positive = probabilities[probabilities > 0.0]
        entropy_effective_rank = float(
            np.exp(-np.sum(positive * np.log(positive), dtype=np.float64))
        )

    body = {
        "schema_version": TAIL_SHOTS_SCHEMA,
        "threshold": retained_threshold,
        "operator": operator,
        "selected_lineup_count": int(scores.shape[0]),
        "heldout_world_count": int(scores.shape[1]),
        "active_tail_lineup_count": active_count,
        "zero_event_lineup_count": zero_count,
        "all_event_lineup_count": all_count,
        "active_pair_count": active_pair_count,
        "pairwise_active_correlation_mean_micro": (
            None
            if pairwise_mean is None
            else to_micro_v1(pairwise_mean, label="pairwise correlation mean")
        ),
        "pairwise_active_correlation_minimum_micro": (
            None
            if pairwise_minimum is None
            else to_micro_v1(
                pairwise_minimum, label="pairwise correlation minimum"
            )
        ),
        "pairwise_active_correlation_maximum_micro": (
            None
            if pairwise_maximum is None
            else to_micro_v1(
                pairwise_maximum, label="pairwise correlation maximum"
            )
        ),
        "participation_ratio_micro": to_micro_v1(
            participation_ratio, label="participation ratio"
        ),
        "entropy_effective_rank_micro": to_micro_v1(
            entropy_effective_rank, label="entropy effective rank"
        ),
        "uses_realized_outcomes": False,
    }
    return _with_hash(body, field="tail_shots_sha256")


def _build_heldout_evaluation_authority_fixture_v1(
    *,
    selection_receipt: object,
    selection_receipt_identity: object,
    projection_bundle: object,
    projection_bundle_identity: object,
    topology: object,
    topology_identity: object,
    fold_ordinal: int,
    selection_cell_sha256: str,
    prefix_size: int,
    heldout_artifact_identity: object,
    heldout_scores: object,
    nomination: object | None = None,
    nomination_identity: object | None = None,
    broad_phase_authority: object | None = None,
) -> dict[str, object]:
    """Bind one held-out matrix to an exact immutable selection prefix."""
    receipt = validate_selection_receipt_authority_v1(
        selection_receipt,
        publication_identity=selection_receipt_identity,
        projection_bundle=projection_bundle,
        projection_bundle_identity=projection_bundle_identity,
        nomination=nomination,
        nomination_identity=nomination_identity,
        broad_phase_authority=broad_phase_authority,
        topology=topology,
        topology_identity=topology_identity,
    )
    bundle = validate_projection_bundle_authority_v1(
        projection_bundle,
        publication_identity=projection_bundle_identity,
        topology=topology,
        topology_identity=topology_identity,
    )
    fold = _integer(fold_ordinal, label="evaluation fold ordinal")
    if fold >= FOLDS_PER_SLATE:
        _fail("evaluation fold ordinal differs")
    prefix = _integer(prefix_size, label="evaluation prefix size", minimum=1)
    if prefix not in PREFIX_SIZES:
        _fail("evaluation prefix is not one frozen nested prefix")
    cell_sha = _sha256_hex(selection_cell_sha256, label="selection cell sha256")
    fold_receipt = receipt["fold_receipts"][fold]
    cells = [
        cell for cell in fold_receipt["cells"]
        if cell["selection_cell_sha256"] == cell_sha
    ]
    if len(cells) != 1:
        _fail("evaluation selection cell is absent or repeated")
    cell = cells[0]
    selected_ids = list(cell["selected_lineup_ids"][:prefix])
    projection = bundle["fold_projections"][fold]
    candidate_by_id = {
        str(candidate["lineup_id"]): candidate for candidate in projection["candidates"]
    }
    selected_rosters = [
        list(candidate_by_id[lineup_id]["roster_player_ids"])
        for lineup_id in selected_ids
    ]
    expected_artifact = projection["world_artifact_identities"][
        f"world_artifact_{WORLD_BLOCKS[fold].lower()}"
    ]
    artifact = _safe_object_identity(
        heldout_artifact_identity, label="heldout artifact identity"
    )
    scores = np.asarray(heldout_scores)
    if (
        artifact != expected_artifact
        or scores.dtype != np.dtype(np.float64)
        or scores.shape != (prefix, WORLDS_PER_BLOCK)
        or not np.isfinite(scores).all()
    ):
        _fail("heldout authority artifact or exact prefix matrix differs")
    body = {
        "schema_version": HELDOUT_EVALUATION_AUTHORITY_SCHEMA,
        "contract_id": CONTRACT_ID,
        "phase": receipt["phase"],
        "source_ordinal": receipt["source_ordinal"],
        "slate_id": receipt["slate_id"],
        "fold_ordinal": fold,
        "fit_scope_id": projection["fit_scope_id"],
        "heldout_block": WORLD_BLOCKS[fold],
        "selection_receipt_identity": _safe_object_identity(
            selection_receipt_identity, label="selection receipt identity"
        ),
        "selection_receipt_sha256": receipt["selection_receipt_sha256"],
        "projection_bundle_identity": _safe_object_identity(
            projection_bundle_identity, label="projection bundle identity"
        ),
        "projection_bundle_sha256": bundle["projection_bundle_sha256"],
        "selection_cell_sha256": cell_sha,
        "prefix_size": prefix,
        "selected_lineup_ids_sha256": canonical_sha256_v1(selected_ids),
        "selected_rosters_sha256": canonical_sha256_v1(selected_rosters),
        "heldout_artifact_identity": artifact,
        "heldout_world_count": WORLDS_PER_BLOCK,
        "heldout_score_shape": [prefix, WORLDS_PER_BLOCK],
        "heldout_score_matrix_sha256": _float64_matrix_sha256_v1(
            scores, label="heldout score matrix"
        ),
        "selection_code_callable": False,
        "policy": _policy_block(),
    }
    return _with_hash(body, field="heldout_evaluation_authority_sha256")


def _validate_heldout_evaluation_authority_fixture_v1(
    value: object, *, heldout_scores: object,
) -> dict[str, object]:
    item = _mapping(value, label="heldout evaluation authority")
    if set(item) != {
        "schema_version", "contract_id", "phase", "source_ordinal", "slate_id",
        "fold_ordinal", "fit_scope_id", "heldout_block",
        "selection_receipt_identity", "selection_receipt_sha256",
        "projection_bundle_identity", "projection_bundle_sha256",
        "selection_cell_sha256", "prefix_size", "selected_lineup_ids_sha256",
        "selected_rosters_sha256", "heldout_artifact_identity",
        "heldout_world_count", "heldout_score_shape",
        "heldout_score_matrix_sha256", "selection_code_callable", "policy",
        "heldout_evaluation_authority_sha256",
    }:
        _fail("heldout evaluation authority fields differ")
    _self_hash(
        item,
        field="heldout_evaluation_authority_sha256",
        label="heldout evaluation authority",
    )
    validate_policy_block_v1(item["policy"], label="heldout evaluation authority")
    prefix = _integer(item["prefix_size"], label="heldout prefix", minimum=1)
    scores = np.asarray(heldout_scores)
    if (
        item["schema_version"] != HELDOUT_EVALUATION_AUTHORITY_SCHEMA
        or item["contract_id"] != CONTRACT_ID
        or prefix not in PREFIX_SIZES
        or item["heldout_world_count"] != WORLDS_PER_BLOCK
        or item["heldout_score_shape"] != [prefix, WORLDS_PER_BLOCK]
        or scores.dtype != np.dtype(np.float64)
        or scores.shape != (prefix, WORLDS_PER_BLOCK)
        or not np.isfinite(scores).all()
        or item["heldout_score_matrix_sha256"]
        != _float64_matrix_sha256_v1(scores, label="heldout score matrix")
        or item["selection_code_callable"] is not False
    ):
        _fail("heldout evaluation authority exact matrix/prefix binding differs")
    _safe_object_identity(item["selection_receipt_identity"], label="selection receipt")
    _safe_object_identity(item["projection_bundle_identity"], label="projection bundle")
    _safe_object_identity(item["heldout_artifact_identity"], label="heldout artifact")
    for field in (
        "selection_receipt_sha256", "projection_bundle_sha256",
        "selection_cell_sha256", "selected_lineup_ids_sha256",
        "selected_rosters_sha256",
    ):
        _sha256_hex(item[field], label=field)
    return item


def _effective_independent_tail_shots_from_authority_fixture_v1(
    authority: object,
    heldout_scores: object,
    *,
    threshold: float,
    operator: str = ">",
) -> dict[str, object]:
    """Authoritative metric entry: exact 10k heldout worlds and frozen prefix."""
    retained = _validate_heldout_evaluation_authority_fixture_v1(
        authority, heldout_scores=heldout_scores
    )
    result = _effective_independent_tail_shots_fixture_v1(
        heldout_scores, threshold=threshold, operator=operator
    )
    body = {
        "schema_version": result["schema_version"],
        "heldout_evaluation_authority_sha256": retained[
            "heldout_evaluation_authority_sha256"
        ],
        "selection_receipt_sha256": retained["selection_receipt_sha256"],
        "selection_cell_sha256": retained["selection_cell_sha256"],
        "prefix_size": retained["prefix_size"],
        "heldout_world_count": WORLDS_PER_BLOCK,
        "metric": result,
        "policy": _policy_block(),
    }
    return _with_hash(body, field="authoritative_tail_shots_sha256")


def _heldout_score_row_ledger_v1(
    lineup_ids_value: object, scores_value: object,
) -> dict[str, object]:
    """Derive the exact little-endian row ledger for one fifth block."""
    lineup_ids = [
        _string(value, label="heldout score-row lineup id")
        for value in _sequence(
            lineup_ids_value, label="heldout score-row lineup ids"
        )
    ]
    scores = np.asarray(scores_value)
    if (
        lineup_ids != sorted(set(lineup_ids))
        or scores.dtype != np.dtype(np.float64)
        or scores.ndim != 2
        or scores.shape != (len(lineup_ids), WORLDS_PER_BLOCK)
        or not np.isfinite(scores).all()
    ):
        _fail("heldout score-row ledger inputs differ")
    rows = [
        {
            "lineup_id": lineup_id,
            "score_row_sha256": _score_row_sha256_fixture_v1(scores[index]),
        }
        for index, lineup_id in enumerate(lineup_ids)
    ]
    return {
        "dtype": "float64-le",
        "world_count": WORLDS_PER_BLOCK,
        "row_count": len(rows),
        "lineup_ids_sha256": canonical_sha256_v1(lineup_ids),
        "rows": rows,
        "rows_sha256": canonical_sha256_v1(rows),
        "score_matrix_shape": [len(rows), WORLDS_PER_BLOCK],
        "score_matrix_sha256": _float64_matrix_sha256_v1(
            scores, label="heldout score-row matrix"
        ),
    }


def _validate_heldout_score_row_ledger_v1(
    value: object, *, expected_lineup_ids: Sequence[str],
) -> dict[str, object]:
    return _validate_score_row_ledger_v1(
        value,
        expected_lineup_ids=expected_lineup_ids,
        expected_world_count=WORLDS_PER_BLOCK,
    )


def _later_source_player_game_map_v1(
    *, later_source_body: object, later_source_identity: object,
    slate_id: str, required_player_ids: Sequence[str],
) -> tuple[dict[str, str], str]:
    """Read only player/game identity from exact generation-pinned source bytes."""
    body = _mapping(later_source_body, label="later-source body")
    authority = _bind_canonical_body_to_identity_v1(
        body, later_source_identity, label="later-source body"
    )
    raw_slates = _sequence(body.get("slates"), label="later-source slates")
    matching = [
        _mapping(raw, label="later-source slate")
        for raw in raw_slates
        if isinstance(raw, Mapping) and raw.get("slate_id") == slate_id
    ]
    if len(matching) != 1:
        _fail("later-source body does not contain one exact slate catalog")
    slate = matching[0]
    raw_catalog = _sequence(slate.get("catalog"), label="later-source catalog")
    if "catalog_sha256" in slate and slate["catalog_sha256"] != canonical_sha256_v1(
        raw_catalog
    ):
        _fail("later-source catalog hash differs")
    player_game: dict[str, str] = {}
    prior = ""
    for offset, raw in enumerate(raw_catalog):
        row = _mapping(raw, label=f"later-source catalog[{offset}]")
        player_id = _string(row.get("id"), label="later-source player id")
        game_id = _string(row.get("game_id"), label="later-source game id")
        if player_id <= prior:
            _fail("later-source player catalog is not unique ascending order")
        prior = player_id
        player_game[player_id] = game_id
    required = [_string(value, label="required player id") for value in required_player_ids]
    if not set(required) <= set(player_game):
        _fail("later-source catalog omits a candidate roster player")
    retained = {player_id: player_game[player_id] for player_id in sorted(set(required))}
    return retained, str(authority["sha256"])


def _quantile_micro_v1(values: np.ndarray, probability: float, *, label: str) -> int:
    result = float(np.quantile(values, probability, method="linear"))
    return to_micro_v1(result, label=label)


def _score_summary_v1(scores_value: object, *, label: str) -> dict[str, object]:
    scores = np.asarray(scores_value)
    if (
        scores.dtype != np.dtype(np.float64)
        or scores.ndim != 2
        or scores.shape[0] < 1
        or scores.shape[1] != WORLDS_PER_BLOCK
        or not np.isfinite(scores).all()
    ):
        _fail(f"{label} score matrix differs")
    world_max = np.max(scores, axis=0)
    return {
        "mean_micro": to_micro_v1(
            float(np.mean(world_max, dtype=np.float64)), label=f"{label} mean"
        ),
        "maximum_micro": to_micro_v1(
            float(np.max(world_max)), label=f"{label} maximum"
        ),
        "q50_micro": _quantile_micro_v1(world_max, 0.50, label=f"{label} q50"),
        "q90_micro": _quantile_micro_v1(world_max, 0.90, label=f"{label} q90"),
        "q95_micro": _quantile_micro_v1(world_max, 0.95, label=f"{label} q95"),
        "q99_micro": _quantile_micro_v1(world_max, 0.99, label=f"{label} q99"),
    }


def _threshold_events_v1(
    scores_value: object, *, include_book_max: bool,
) -> list[dict[str, object]]:
    scores = np.asarray(scores_value)
    if (
        scores.dtype != np.dtype(np.float64)
        or scores.ndim != 2
        or scores.shape[0] < 1
        or scores.shape[1] != WORLDS_PER_BLOCK
        or not np.isfinite(scores).all()
    ):
        _fail("tail-event score matrix differs")
    book_max = np.max(scores, axis=0) if include_book_max else None
    rows = []
    for metric_id, threshold, operator in TAIL_THRESHOLDS:
        events = scores >= threshold if operator == ">=" else scores > threshold
        event_count = int(np.count_nonzero(events))
        lineup_count = int(np.count_nonzero(np.any(events, axis=1)))
        denominator = int(scores.shape[0]) * WORLDS_PER_BLOCK
        row: dict[str, object] = {
            "metric_id": metric_id,
            "threshold_micro": to_micro_v1(threshold, label="tail threshold"),
            "operator": operator,
            "tail_lineup_count": lineup_count,
            "tail_event_count": event_count,
            "tail_lineups_per_1000_micro": _round_fraction_ties_even(
                Fraction(1_000 * MICRO_SCALE * lineup_count, scores.shape[0])
            ),
            "tail_event_probability_numerator": event_count,
            "tail_event_probability_denominator": denominator,
            "tail_event_probability_micro": _round_fraction_ties_even(
                Fraction(event_count * MICRO_SCALE, denominator)
            ),
        }
        if include_book_max:
            assert book_max is not None
            book_events = (
                book_max >= threshold if operator == ">=" else book_max > threshold
            )
            book_count = int(np.count_nonzero(book_events))
            row.update({
                "book_max_event_count": book_count,
                "book_max_event_denominator": WORLDS_PER_BLOCK,
                "book_max_event_probability_micro": book_count * 100,
            })
        rows.append(row)
    return rows


def _provenance_exposure_v1(
    candidates: Sequence[Mapping[str, object]],
) -> dict[str, object]:
    profile_rows = []
    for ordinal, profile_id, _ in PROFILE_IDENTITIES:
        members = [
            candidate for candidate in candidates
            if profile_id in candidate["training_source_arms"]
        ]
        profile_rows.append({
            "profile_ordinal": ordinal,
            "profile_id": profile_id,
            "lineup_membership_count": len(members),
            "supported_training_occurrence_count": sum(
                int(candidate["training_occurrence_count"])
                for candidate in members
            ),
        })
    block_rows = []
    profile_block_rows = []
    for block in WORLD_BLOCKS:
        if any(block not in candidate["training_occurrence_counts_by_block"] for candidate in candidates):
            continue
        block_rows.append({
            "training_block": block,
            "lineup_membership_count": sum(
                int(candidate["training_occurrence_counts_by_block"][block]) > 0
                for candidate in candidates
            ),
            "training_occurrence_count": sum(
                int(candidate["training_occurrence_counts_by_block"][block])
                for candidate in candidates
            ),
        })
        for ordinal, profile_id, _ in PROFILE_IDENTITIES:
            members = [
                candidate for candidate in candidates
                if profile_id in candidate["training_source_arms_by_block"][block]
            ]
            profile_block_rows.append({
                "training_block": block,
                "profile_ordinal": ordinal,
                "profile_id": profile_id,
                "lineup_membership_count": len(members),
                "profile_supported_occurrence_count": sum(
                    int(candidate["training_occurrence_counts_by_block"][block])
                    for candidate in members
                ),
            })
    return {
        "by_profile": profile_rows,
        "by_training_block": block_rows,
        "by_profile_and_training_block": profile_block_rows,
        "exclusive_profile_lineup_count": sum(
            len(candidate["training_source_arms"]) == 1 for candidate in candidates
        ),
        "shared_profile_lineup_count": sum(
            len(candidate["training_source_arms"]) > 1 for candidate in candidates
        ),
    }


def _overlap_metrics_v1(
    rosters: Sequence[Sequence[str]], *, player_game: Mapping[str, str],
) -> dict[str, object]:
    retained = [tuple(roster) for roster in rosters]
    if not retained or any(len(roster) != 9 for roster in retained):
        _fail("book overlap rosters differ")
    pair_count = len(retained) * (len(retained) - 1) // 2
    shared_counts = [
        len(set(retained[left]) & set(retained[right]))
        for left in range(len(retained))
        for right in range(left + 1, len(retained))
    ]
    shared_sum = sum(shared_counts)
    unique_players = sorted({player for roster in retained for player in roster})
    if not set(unique_players) <= set(player_game):
        _fail("book overlap game map omits a selected player")
    return {
        "unordered_lineup_pair_count": pair_count,
        "shared_player_count_numerator": shared_sum,
        "shared_player_count_denominator": pair_count,
        "mean_shared_player_count_micro": _round_fraction_ties_even(
            Fraction(shared_sum * MICRO_SCALE, pair_count)
        ),
        "maximum_shared_player_count": max(shared_counts),
        "unique_player_count": len(unique_players),
        "unique_game_id_count": len({player_game[player] for player in unique_players}),
    }


def _view_profile_fields_v1(view_id: str) -> tuple[str, int, str]:
    if view_id == "U":
        return "union", -1, "all-profiles"
    for kind, builder in (
        ("isolated-origin-membership", isolated_view_id_v1),
        ("leave-one-profile-out", leave_one_out_view_id_v1),
        ("exclusive-origin", exclusive_view_id_v1),
    ):
        for ordinal, profile_id, _ in PROFILE_IDENTITIES:
            if view_id == builder(ordinal):
                return kind, ordinal, profile_id
    for ordinal, profile_id, _ in PROFILE_IDENTITIES[1:]:
        if view_id == pair_union_view_id_v1(ordinal):
            return "incumbent-relaxed-pair-union", ordinal, profile_id
    _fail("population metric view differs from frozen registry")


def _empty_population_tail_rows_v1() -> list[dict[str, object]]:
    return [
        {
            "metric_id": metric_id,
            "threshold_micro": to_micro_v1(threshold, label="tail threshold"),
            "operator": operator,
            "tail_lineup_count": 0,
            "tail_event_count": 0,
            "tail_lineups_per_1000_micro": None,
            "tail_event_probability_numerator": 0,
            "tail_event_probability_denominator": 0,
            "tail_event_probability_micro": None,
        }
        for metric_id, threshold, operator in TAIL_THRESHOLDS
    ]


def _population_metric_rows_v1(
    *, projection: Mapping[str, object], heldout_scores: np.ndarray,
) -> list[dict[str, object]]:
    registry = derive_view_registry_from_projection_v1(projection)
    ids_by_view = _view_ids_by_id(registry)
    candidates = list(projection["candidates"])
    candidate_by_id = {str(row["lineup_id"]): row for row in candidates}
    index_by_id = {
        str(row["lineup_id"]): index for index, row in enumerate(candidates)
    }
    inferential = {
        "U", *(isolated_view_id_v1(index) for index in range(len(PROFILE_IDENTITIES)))
    }
    equal_target = min(len(ids_by_view[view_id]) for view_id in inferential)
    score_cache: dict[str, tuple[dict[str, object] | None, list[dict[str, object]]]] = {}
    rows: list[dict[str, object]] = []
    for view_ordinal, (view_id, lineup_ids) in enumerate(ids_by_view.items()):
        view_kind, profile_ordinal, profile_id = _view_profile_fields_v1(view_id)
        view_candidates = [candidate_by_id[lineup_id] for lineup_id in lineup_ids]
        rosters = [tuple(candidate["roster_player_ids"]) for candidate in view_candidates]
        lineup_hash = canonical_sha256_v1(lineup_ids)
        cached = score_cache.get(lineup_hash)
        if cached is None:
            if lineup_ids:
                view_scores = heldout_scores[
                    [index_by_id[lineup_id] for lineup_id in lineup_ids], :
                ]
                cached = (
                    _score_summary_v1(view_scores, label="population oracle"),
                    _threshold_events_v1(view_scores, include_book_max=False),
                )
            else:
                cached = (None, _empty_population_tail_rows_v1())
            score_cache[lineup_hash] = cached
        oracle, tail_rows = cached
        occurrence_count = sum(
            int(candidate["training_occurrence_count"])
            for candidate in view_candidates
        )
        row = {
            "schema_version": POPULATION_METRIC_ROW_SCHEMA,
            "fold_ordinal": int(WORLD_BLOCKS.index(str(projection["heldout_block"]))),
            "heldout_block": projection["heldout_block"],
            "view_ordinal": view_ordinal,
            "view_id": view_id,
            "view_kind": view_kind,
            "profile_ordinal": profile_ordinal,
            "profile_id": profile_id,
            "full_candidate_count": len(lineup_ids),
            "equal_count_target": equal_target,
            "equal_count_selection_applicable": view_id in inferential,
            "equal_count_candidate_count": equal_target if view_id in inferential else 0,
            "exact_80_feasible": len(lineup_ids) >= ENTRY_BUDGET,
            "candidate_lineup_ids_sha256": lineup_hash,
            "training_occurrence_count": occurrence_count,
            "occurrence_dedup_loss_count": occurrence_count - len(lineup_ids),
            "unique_canonical_roster_count": len(set(rosters)),
            "surviving_roster_alias_count": len(lineup_ids) - len(set(rosters)),
            "provenance_exposure": _provenance_exposure_v1(view_candidates),
            "simulated_corpus_oracle": oracle,
            "tail_availability": tail_rows,
            "leave_one_out_delta_from_union": None,
            "policy": _policy_block(),
        }
        rows.append(row)
    union = rows[0]
    union_tails = {
        str(row["metric_id"]): row for row in union["tail_availability"]
    }
    union_oracle = union["simulated_corpus_oracle"]
    for row in rows:
        if row["view_kind"] != "leave-one-profile-out":
            continue
        tails = {str(item["metric_id"]): item for item in row["tail_availability"]}
        row["leave_one_out_delta_from_union"] = {
            "profile_ordinal": row["profile_ordinal"],
            "profile_id": row["profile_id"],
            "candidate_count_loss": int(union["full_candidate_count"])
            - int(row["full_candidate_count"]),
            "mean_simulated_corpus_oracle_loss_micro": (
                None
                if union_oracle is None or row["simulated_corpus_oracle"] is None
                else int(union_oracle["mean_micro"])
                - int(row["simulated_corpus_oracle"]["mean_micro"])
            ),
            "tail_lineup_availability_loss": [
                {
                    "metric_id": metric_id,
                    "tail_lineup_count_loss": int(union_tails[metric_id]["tail_lineup_count"])
                    - int(tails[metric_id]["tail_lineup_count"]),
                }
                for metric_id, _, _ in TAIL_THRESHOLDS
            ],
        }
    return [
        _with_hash(row, field="population_metric_row_sha256") for row in rows
    ]


def _effective_tail_rows_v1(scores: np.ndarray) -> list[dict[str, object]]:
    return [
        _effective_independent_tail_shots_fixture_v1(
            scores, threshold=threshold, operator=">"
        )
        for threshold in EFFECTIVE_SHOT_THRESHOLDS
    ]


def _aggregate_scalars_from_book_v1(
    *, summary: Mapping[str, object], tail_rows: Sequence[Mapping[str, object]],
    effective_rows: Sequence[Mapping[str, object]],
) -> dict[str, object]:
    tails = {str(row["metric_id"]): row for row in tail_rows}
    effective = {int(row["threshold"]): row for row in effective_rows}
    return {
        "mean_heldout_expected_book_max_micro": {
            "numerator": int(summary["mean_micro"]), "denominator": 1,
        },
        "mean_heldout_p_max_gt_200": {
            "numerator": int(tails["gt_200"]["book_max_event_count"]),
            "denominator": int(tails["gt_200"]["book_max_event_denominator"]),
        },
        "mean_heldout_p_max_gt_220": {
            "numerator": int(tails["gt_220"]["book_max_event_count"]),
            "denominator": int(tails["gt_220"]["book_max_event_denominator"]),
        },
        "mean_heldout_p_max_gt_230": {
            "numerator": int(tails["gt_230"]["book_max_event_count"]),
            "denominator": int(tails["gt_230"]["book_max_event_denominator"]),
        },
        "mean_heldout_participation_ratio_gt_220_micro": {
            "numerator": int(effective[220]["participation_ratio_micro"]),
            "denominator": 1,
        },
    }


def _book_metric_rows_v1(
    *, projection: Mapping[str, object], fold_receipt: Mapping[str, object],
    heldout_scores: np.ndarray, player_game: Mapping[str, str],
    population_rows: Sequence[Mapping[str, object]],
) -> list[dict[str, object]]:
    candidates = list(projection["candidates"])
    candidate_by_id = {str(row["lineup_id"]): row for row in candidates}
    index_by_id = {
        str(row["lineup_id"]): index for index, row in enumerate(candidates)
    }
    population_by_view = {str(row["view_id"]): row for row in population_rows}
    derived_cache: dict[str, dict[str, object]] = {}
    rows: list[dict[str, object]] = []
    for cell_ordinal, cell in enumerate(fold_receipt["cells"]):
        selected_ids = [str(value) for value in cell["selected_lineup_ids"]]
        for prefix_ordinal, prefix_size in enumerate(PREFIX_SIZES):
            prefix_ids = selected_ids[:prefix_size]
            prefix_binding = cell["prefixes"][prefix_ordinal]
            prefix_hash = str(prefix_binding["prefix_payload_sha256"])
            cached = derived_cache.get(prefix_hash)
            if cached is None:
                selected_candidates = [candidate_by_id[lineup_id] for lineup_id in prefix_ids]
                selected_scores = heldout_scores[
                    [index_by_id[lineup_id] for lineup_id in prefix_ids], :
                ]
                rosters = [
                    list(candidate["roster_player_ids"])
                    for candidate in selected_candidates
                ]
                score_summary = _score_summary_v1(
                    selected_scores, label="heldout book maximum"
                )
                tail_rows = _threshold_events_v1(
                    selected_scores, include_book_max=True
                )
                effective_rows = _effective_tail_rows_v1(selected_scores)
                cached = {
                    "book_score_summary": score_summary,
                    "tail_metrics": tail_rows,
                    "effective_tail_shots": effective_rows,
                    "overlap_metrics": _overlap_metrics_v1(
                        rosters, player_game=player_game
                    ),
                    "selected_provenance_exposure": _provenance_exposure_v1(
                        selected_candidates
                    ),
                    "aggregate_scalars": _aggregate_scalars_from_book_v1(
                        summary=score_summary,
                        tail_rows=tail_rows,
                        effective_rows=effective_rows,
                    ),
                }
                derived_cache[prefix_hash] = cached
            population = population_by_view[str(cell["view_id"])]
            population_oracle = population["simulated_corpus_oracle"]
            if population_oracle is None:
                _fail("selected view has no heldout population oracle")
            view_kind, profile_ordinal, profile_id = _view_profile_fields_v1(
                str(cell["view_id"])
            )
            row = {
                "schema_version": BOOK_METRIC_ROW_SCHEMA,
                "fold_ordinal": int(fold_receipt["fold_ordinal"]),
                "heldout_block": fold_receipt["heldout_block"],
                "cell_ordinal": cell_ordinal,
                "prefix_ordinal": prefix_ordinal,
                "replicate": int(cell["replicate"]),
                "view_id": cell["view_id"],
                "view_kind": view_kind,
                "profile_ordinal": profile_ordinal,
                "profile_id": profile_id,
                "strategy_ordinal": int(cell["strategy_ordinal"]),
                "strategy_id": cell["strategy_id"],
                "selection_cell_sha256": cell["selection_cell_sha256"],
                "prefix_size": prefix_size,
                "prefix_payload_sha256": prefix_hash,
                "selected_lineup_ids_sha256": prefix_binding[
                    "selected_lineup_ids_sha256"
                ],
                "selected_rosters_sha256": prefix_binding["selected_rosters_sha256"],
                "retrieval_metrics": {
                    "full_view_candidate_count": population["full_candidate_count"],
                    "equal_size_candidate_count": len(cell["sampled_lineup_ids"]),
                    "selected_lineup_count": prefix_size,
                    "simulated_corpus_oracle_gap_micro": int(
                        population_oracle["mean_micro"]
                    ) - int(cached["book_score_summary"]["mean_micro"]),
                    "population_tail_lineup_counts": [
                        {
                            "metric_id": value["metric_id"],
                            "tail_lineup_count": value["tail_lineup_count"],
                        }
                        for value in population["tail_availability"]
                    ],
                    "selected_tail_lineup_counts": [
                        {
                            "metric_id": value["metric_id"],
                            "tail_lineup_count": value["tail_lineup_count"],
                        }
                        for value in cached["tail_metrics"]
                    ],
                },
                **cached,
                "policy": _policy_block(),
            }
            rows.append(_with_hash(row, field="book_metric_row_sha256"))
    return rows


def _heldout_fold_authority_v1(
    *, projection: Mapping[str, object], heldout_artifact_identity: object,
    heldout_scores: object,
) -> tuple[dict[str, object], np.ndarray]:
    retained_projection = validate_narrow_projection_v1(projection)
    artifact = _safe_object_identity(
        heldout_artifact_identity, label="heldout fold artifact"
    )
    expected_artifact = retained_projection["world_artifact_identities"][
        f"world_artifact_{str(retained_projection['heldout_block']).lower()}"
    ]
    lineup_ids = [
        str(candidate["lineup_id"])
        for candidate in retained_projection["candidates"]
    ]
    scores = np.asarray(heldout_scores)
    if (
        artifact != expected_artifact
        or scores.dtype != np.dtype(np.float64)
        or scores.shape != (len(lineup_ids), WORLDS_PER_BLOCK)
        or not np.isfinite(scores).all()
    ):
        _fail("heldout fold artifact or full candidate matrix differs")
    ledger = _heldout_score_row_ledger_v1(lineup_ids, scores)
    body = {
        "schema_version": HELDOUT_FOLD_AUTHORITY_SCHEMA,
        "fit_scope_id": retained_projection["fit_scope_id"],
        "heldout_block": retained_projection["heldout_block"],
        "projection_sha256": retained_projection["projection_sha256"],
        "candidate_lineup_order_sha256": retained_projection[
            "candidate_lineup_order_sha256"
        ],
        "heldout_artifact_identity": artifact,
        "score_row_ledger": ledger,
        "score_row_ledger_sha256": canonical_sha256_v1(ledger),
        "policy": _policy_block(),
    }
    return _with_hash(body, field="heldout_fold_authority_sha256"), scores


def build_evaluation_fold_v1(
    *, fold_ordinal: int, projection: object, selection_fold_receipt: object,
    heldout_artifact_identity: object, heldout_score_matrix: object,
    later_source_body: object,
) -> dict[str, object]:
    """Derive one fold while its sole held-out matrix is resident in memory."""
    fold = _integer(fold_ordinal, label="evaluation fold ordinal")
    if fold >= FOLDS_PER_SLATE:
        _fail("evaluation fold ordinal differs")
    retained_projection = validate_narrow_projection_v1(projection)
    fold_receipt = _mapping(
        selection_fold_receipt, label="evaluation selection fold receipt"
    )
    _self_hash(
        fold_receipt,
        field="selection_fold_receipt_sha256",
        label="evaluation selection fold receipt",
    )
    if (
        retained_projection["heldout_block"] != WORLD_BLOCKS[fold]
        or fold_receipt.get("fold_ordinal") != fold
        or fold_receipt.get("heldout_block") != WORLD_BLOCKS[fold]
        or fold_receipt.get("projection_sha256")
        != retained_projection["projection_sha256"]
    ):
        _fail("evaluation fold projection/receipt binding differs")
    required_players = sorted({
        str(player_id)
        for candidate in retained_projection["candidates"]
        for player_id in candidate["roster_player_ids"]
    })
    player_game, later_source_body_sha256 = _later_source_player_game_map_v1(
        later_source_body=later_source_body,
        later_source_identity=retained_projection["later_source_identity"],
        slate_id=str(retained_projection["slate_id"]),
        required_player_ids=required_players,
    )
    heldout_authority, scores = _heldout_fold_authority_v1(
        projection=retained_projection,
        heldout_artifact_identity=heldout_artifact_identity,
        heldout_scores=heldout_score_matrix,
    )
    population_rows = _population_metric_rows_v1(
        projection=retained_projection, heldout_scores=scores
    )
    book_rows = _book_metric_rows_v1(
        projection=retained_projection,
        fold_receipt=fold_receipt,
        heldout_scores=scores,
        player_game=player_game,
        population_rows=population_rows,
    )
    expected_book_count = int(fold_receipt["cell_count"]) * len(PREFIX_SIZES)
    if len(population_rows) != 28 or len(book_rows) != expected_book_count:
        _fail("internally derived evaluation row lattice differs")
    body = {
        "fold_ordinal": fold,
        "heldout_block": WORLD_BLOCKS[fold],
        "selection_fold_receipt_sha256": fold_receipt[
            "selection_fold_receipt_sha256"
        ],
        "heldout_fold_authority": heldout_authority,
        "heldout_fold_authority_sha256": heldout_authority[
            "heldout_fold_authority_sha256"
        ],
        "later_source_body_sha256": later_source_body_sha256,
        "player_game_map_sha256": canonical_sha256_v1(player_game),
        "population_metric_row_count": len(population_rows),
        "population_metric_rows": population_rows,
        "population_metric_rows_sha256": canonical_sha256_v1(population_rows),
        "selection_cell_count": int(fold_receipt["cell_count"]),
        "book_metric_row_count": len(book_rows),
        "book_metric_rows": book_rows,
        "book_metric_rows_sha256": canonical_sha256_v1(book_rows),
    }
    return _with_hash(body, field="evaluation_fold_sha256")


def build_evaluation_result_v1(
    *,
    design: object,
    design_publication_identity: object,
    topology_identity: object,
    selection_receipt: object,
    selection_receipt_identity: object,
    projection_bundle: object,
    projection_bundle_identity: object,
    heldout_fold_input_stream: Iterable[object],
    later_source_body: object,
    evaluator_process_budget: object,
    evaluator_process_budget_identity: object,
    bootstrap_manifest: object,
    bootstrap_manifest_identity: object,
    runtime_observation: object,
    launch_intent_identity: object,
    nomination_publication: object | None = None,
    nomination_publication_identity: object | None = None,
) -> dict[str, object]:
    """Consume five matrices once and derive every persisted metric row."""
    retained_design = validate_design_authority_v1(
        design, publication_identity=design_publication_identity
    )
    topology = retained_design["topology"]
    retained_topology_identity = _bind_canonical_body_to_identity_v1(
        topology, topology_identity, label="result topology"
    )
    receipt = validate_selection_receipt_authority_v1(
        selection_receipt,
        publication_identity=selection_receipt_identity,
        projection_bundle=projection_bundle,
        projection_bundle_identity=projection_bundle_identity,
        topology=topology,
        topology_identity=retained_topology_identity,
        bootstrap_manifest=bootstrap_manifest,
        bootstrap_manifest_identity=bootstrap_manifest_identity,
        launch_intent_identity=launch_intent_identity,
        nomination_publication=nomination_publication,
        nomination_publication_identity=nomination_publication_identity,
    )
    bundle = validate_projection_bundle_authority_v1(
        projection_bundle,
        publication_identity=projection_bundle_identity,
        topology=topology,
        topology_identity=retained_topology_identity,
    )
    if receipt["projection_bundle_sha256"] != bundle["projection_bundle_sha256"]:
        _fail("evaluation receipt/projection authority differs")
    manifest = validate_bootstrap_manifest_authority_v1(
        bootstrap_manifest,
        publication_identity=bootstrap_manifest_identity,
        topology=topology,
        topology_identity=retained_topology_identity,
    )
    if (
        retained_design["bootstrap_manifest_identity"]
        != _safe_object_identity(
            bootstrap_manifest_identity, label="evaluation bootstrap manifest"
        )
        or retained_design["bootstrap_manifest_sha256"]
        != manifest["bootstrap_manifest_sha256"]
    ):
        _fail("evaluation bootstrap manifest differs from design")
    process_budget = validate_evaluator_process_budget_v1(
        evaluator_process_budget,
        design=retained_design,
        design_publication_identity=design_publication_identity,
        bootstrap_manifest=manifest,
        bootstrap_manifest_identity=bootstrap_manifest_identity,
        launch_intent_identity=launch_intent_identity,
    )
    process_budget_identity = _bind_canonical_body_to_identity_v1(
        process_budget,
        evaluator_process_budget_identity,
        label="evaluator process budget",
    )
    expected_role = (
        "broad-evaluator"
        if receipt["phase"] == BROAD_SCREEN_PHASE
        else "confirmation-evaluator"
    )
    if (
        process_budget["process_role"] != expected_role
        or process_budget["source_ordinal"] != receipt["source_ordinal"]
        or process_budget["projection_bundle_identity"]
        != _safe_object_identity(
            projection_bundle_identity, label="evaluation projection identity"
        )
    ):
        _fail("evaluator process budget differs from evaluation authority")
    runtime = validate_runtime_observation_v1(
        runtime_observation,
        bootstrap_manifest=manifest,
        bootstrap_manifest_identity=bootstrap_manifest_identity,
        process_budget=process_budget,
        process_budget_identity=process_budget_identity,
        launch_intent_identity=launch_intent_identity,
    )
    try:
        stream = iter(heldout_fold_input_stream)
    except TypeError as exc:
        raise CorpusR6CurrentBankCrossedScreenContractV1Error(
            "heldout fold inputs must be a single-pass iterable"
        ) from exc
    folds = []
    for fold_ordinal in range(FOLDS_PER_SLATE):
        try:
            raw_input = next(stream)
        except StopIteration as exc:
            raise CorpusR6CurrentBankCrossedScreenContractV1Error(
                "evaluation fold stream ended before R4"
            ) from exc
        fold_input = _mapping(
            raw_input, label=f"evaluation fold input[{fold_ordinal}]"
        )
        if set(fold_input) != {
            "fold_ordinal", "heldout_artifact_identity", "heldout_score_matrix",
        } or fold_input["fold_ordinal"] != fold_ordinal:
            _fail("evaluation fold stream order/fields differ")
        projection = bundle["fold_projections"][fold_ordinal]
        fold_receipt = receipt["fold_receipts"][fold_ordinal]
        fold_body = build_evaluation_fold_v1(
            fold_ordinal=fold_ordinal,
            projection=projection,
            selection_fold_receipt=fold_receipt,
            heldout_artifact_identity=fold_input["heldout_artifact_identity"],
            heldout_score_matrix=fold_input["heldout_score_matrix"],
            later_source_body=later_source_body,
        )
        folds.append(fold_body)
        del fold_input, raw_input
    try:
        next(stream)
    except StopIteration:
        pass
    else:
        _fail("evaluation fold stream contains more than five folds")
    later_source_hashes = {fold["later_source_body_sha256"] for fold in folds}
    player_game_hashes = {fold["player_game_map_sha256"] for fold in folds}
    if len(later_source_hashes) != 1 or len(player_game_hashes) != 1:
        _fail("evaluation fold later-source derivation differs")
    phase_role = (
        "broad-evaluation-result"
        if receipt["phase"] == BROAD_SCREEN_PHASE
        else "confirmation-evaluation-result"
    )
    body = {
        "schema_version": EVALUATION_RESULT_SCHEMA,
        "contract_id": CONTRACT_ID,
        "phase": receipt["phase"],
        "source_ordinal": receipt["source_ordinal"],
        "slate_id": receipt["slate_id"],
        "design_publication_identity": _safe_object_identity(
            design_publication_identity, label="evaluation design publication"
        ),
        "design_sha256": retained_design["design_sha256"],
        "topology_identity": retained_topology_identity,
        "bootstrap_manifest_identity": _safe_object_identity(
            bootstrap_manifest_identity, label="evaluation bootstrap manifest"
        ),
        "bootstrap_manifest_sha256": manifest["bootstrap_manifest_sha256"],
        "evaluator_process_budget_identity": process_budget_identity,
        "evaluator_process_budget_sha256": process_budget[
            "evaluator_process_budget_sha256"
        ],
        "launch_intent_identity": _safe_object_identity(
            launch_intent_identity, label="evaluation launch intent"
        ),
        "runtime_observation": runtime,
        "runtime_observation_sha256": runtime["runtime_observation_sha256"],
        "selection_receipt_identity": _safe_object_identity(
            selection_receipt_identity, label="selection receipt identity"
        ),
        "selection_receipt_sha256": receipt["selection_receipt_sha256"],
        "logical_fold_selection_count": receipt[
            "logical_fold_selection_count"
        ],
        "selector_os_process_count": receipt["selector_os_process_count"],
        "child_execution_evidence_sha256s": receipt[
            "child_execution_evidence_sha256s"
        ],
        "child_execution_evidence_set_sha256": receipt[
            "child_execution_evidence_set_sha256"
        ],
        "projection_bundle_identity": _safe_object_identity(
            projection_bundle_identity, label="projection bundle identity"
        ),
        "projection_bundle_sha256": bundle["projection_bundle_sha256"],
        "later_source_identity": bundle["fold_projections"][0][
            "later_source_identity"
        ],
        "later_source_body_sha256": next(iter(later_source_hashes)),
        "player_game_map_sha256": next(iter(player_game_hashes)),
        "fold_count": FOLDS_PER_SLATE,
        "folds": folds,
        "folds_sha256": canonical_sha256_v1(folds),
        "population_metric_row_count": sum(
            int(fold["population_metric_row_count"]) for fold in folds
        ),
        "book_metric_row_count": sum(
            int(fold["book_metric_row_count"]) for fold in folds
        ),
        "metric_derivation_law": (
            "sequential-R0-through-R4-full-matrix-to-ordered-metric-rows"
        ),
        "caller_metric_rows_accepted": False,
        "selection_code_callable": False,
        "publication_role": phase_role,
        "policy": _policy_block(),
    }
    return _with_hash(body, field="evaluation_result_sha256")


def _validate_effective_tail_row_v1(value: object) -> dict[str, object]:
    row = _mapping(value, label="effective-tail row")
    expected_fields = {
        "schema_version", "threshold", "operator", "selected_lineup_count",
        "heldout_world_count", "active_tail_lineup_count",
        "zero_event_lineup_count", "all_event_lineup_count",
        "active_pair_count", "pairwise_active_correlation_mean_micro",
        "pairwise_active_correlation_minimum_micro",
        "pairwise_active_correlation_maximum_micro",
        "participation_ratio_micro", "entropy_effective_rank_micro",
        "uses_realized_outcomes", "tail_shots_sha256",
    }
    if set(row) != expected_fields:
        _fail("effective-tail row fields differ")
    _self_hash(row, field="tail_shots_sha256", label="effective-tail row")
    selected = _integer(
        row["selected_lineup_count"], label="effective-tail selected count", minimum=1
    )
    active = _integer(
        row["active_tail_lineup_count"], label="effective-tail active count"
    )
    zero = _integer(row["zero_event_lineup_count"], label="effective-tail zero count")
    all_count = _integer(
        row["all_event_lineup_count"], label="effective-tail all count"
    )
    expected_pairs = active * (active - 1) // 2
    if (
        row["schema_version"] != TAIL_SHOTS_SCHEMA
        or row["threshold"] not in EFFECTIVE_SHOT_THRESHOLDS
        or row["operator"] != ">"
        or row["heldout_world_count"] != WORLDS_PER_BLOCK
        or active + zero + all_count != selected
        or row["active_pair_count"] != expected_pairs
        or row["uses_realized_outcomes"] is not False
        or not 0 <= int(row["participation_ratio_micro"]) <= selected * MICRO_SCALE
        or not 0 <= int(row["entropy_effective_rank_micro"]) <= selected * MICRO_SCALE
    ):
        _fail("effective-tail row invariants differ")
    correlation_fields = (
        "pairwise_active_correlation_mean_micro",
        "pairwise_active_correlation_minimum_micro",
        "pairwise_active_correlation_maximum_micro",
    )
    if expected_pairs == 0:
        if any(row[field] is not None for field in correlation_fields):
            _fail("effective-tail degenerate correlation fields differ")
    else:
        if any(type(row[field]) is not int for field in correlation_fields):
            _fail("effective-tail correlation fields differ")
    return row


def _validate_tail_rows_v1(
    value: object, *, selected_count: int, include_book_max: bool,
) -> list[dict[str, object]]:
    rows = [
        _mapping(row, label=f"tail row[{index}]")
        for index, row in enumerate(_sequence(value, label="tail rows"))
    ]
    if len(rows) != len(TAIL_THRESHOLDS):
        _fail("tail row threshold lattice differs")
    for row, (metric_id, threshold, operator) in zip(
        rows, TAIL_THRESHOLDS, strict=True
    ):
        expected_fields = {
            "metric_id", "threshold_micro", "operator", "tail_lineup_count",
            "tail_event_count", "tail_lineups_per_1000_micro",
            "tail_event_probability_numerator",
            "tail_event_probability_denominator",
            "tail_event_probability_micro",
        }
        if include_book_max:
            expected_fields |= {
                "book_max_event_count", "book_max_event_denominator",
                "book_max_event_probability_micro",
            }
        if set(row) != expected_fields:
            _fail("tail row fields differ")
        lineup_count = _integer(row["tail_lineup_count"], label="tail lineup count")
        event_count = _integer(row["tail_event_count"], label="tail event count")
        denominator = selected_count * WORLDS_PER_BLOCK
        if (
            row["metric_id"] != metric_id
            or row["threshold_micro"] != to_micro_v1(threshold, label="tail threshold")
            or row["operator"] != operator
            or lineup_count > selected_count
            or event_count > denominator
            or row["tail_event_probability_numerator"] != event_count
            or row["tail_event_probability_denominator"] != denominator
            or row["tail_lineups_per_1000_micro"]
            != _round_fraction_ties_even(
                Fraction(1_000 * MICRO_SCALE * lineup_count, selected_count)
            )
            or row["tail_event_probability_micro"]
            != _round_fraction_ties_even(
                Fraction(event_count * MICRO_SCALE, denominator)
            )
        ):
            _fail("tail row count/probability invariants differ")
        if include_book_max:
            book_count = _integer(
                row["book_max_event_count"], label="book max event count"
            )
            if (
                book_count > WORLDS_PER_BLOCK
                or book_count > event_count
                or row["book_max_event_denominator"] != WORLDS_PER_BLOCK
                or row["book_max_event_probability_micro"] != book_count * 100
            ):
                _fail("book max tail row invariants differ")
    return rows


def _validate_population_metric_row_v1(
    value: object, *, expected_view_ordinal: int, expected_fold: int,
) -> dict[str, object]:
    row = _mapping(value, label="population metric row")
    expected_fields = {
        "schema_version", "fold_ordinal", "heldout_block", "view_ordinal",
        "view_id", "view_kind", "profile_ordinal", "profile_id",
        "full_candidate_count", "equal_count_target",
        "equal_count_selection_applicable", "equal_count_candidate_count",
        "exact_80_feasible", "candidate_lineup_ids_sha256",
        "training_occurrence_count", "occurrence_dedup_loss_count",
        "unique_canonical_roster_count", "surviving_roster_alias_count",
        "provenance_exposure", "simulated_corpus_oracle", "tail_availability",
        "leave_one_out_delta_from_union", "policy",
        "population_metric_row_sha256",
    }
    if set(row) != expected_fields:
        _fail("population metric row fields differ")
    _self_hash(
        row, field="population_metric_row_sha256", label="population metric row"
    )
    validate_policy_block_v1(row["policy"], label="population metric row")
    kind, profile_ordinal, profile_id = _view_profile_fields_v1(str(row["view_id"]))
    count = _integer(row["full_candidate_count"], label="population candidate count")
    occurrence = _integer(
        row["training_occurrence_count"], label="population occurrence count"
    )
    unique_rosters = _integer(
        row["unique_canonical_roster_count"], label="population unique rosters"
    )
    if (
        row["schema_version"] != POPULATION_METRIC_ROW_SCHEMA
        or row["fold_ordinal"] != expected_fold
        or row["heldout_block"] != WORLD_BLOCKS[expected_fold]
        or row["view_ordinal"] != expected_view_ordinal
        or (row["view_kind"], row["profile_ordinal"], row["profile_id"])
        != (kind, profile_ordinal, profile_id)
        or occurrence < count
        or row["occurrence_dedup_loss_count"] != occurrence - count
        or unique_rosters > count
        or row["surviving_roster_alias_count"] != count - unique_rosters
        or row["exact_80_feasible"] is not (count >= ENTRY_BUDGET)
    ):
        _fail("population metric row identity/count invariants differ")
    _sha256_hex(
        row["candidate_lineup_ids_sha256"], label="population lineup IDs"
    )
    if count == 0:
        if row["simulated_corpus_oracle"] is not None:
            _fail("empty population view has an oracle")
    else:
        summary = _mapping(
            row["simulated_corpus_oracle"], label="population oracle"
        )
        if set(summary) != {
            "mean_micro", "maximum_micro", "q50_micro", "q90_micro",
            "q95_micro", "q99_micro",
        } or any(type(value) is not int for value in summary.values()):
            _fail("population oracle fields differ")
        _validate_tail_rows_v1(
            row["tail_availability"], selected_count=count, include_book_max=False
        )
    return row


def _validate_book_metric_row_v1(
    value: object, *, expected_fold: int, expected_cell: int,
    expected_prefix_ordinal: int,
) -> dict[str, object]:
    row = _mapping(value, label="book metric row")
    expected_fields = {
        "schema_version", "fold_ordinal", "heldout_block", "cell_ordinal",
        "prefix_ordinal", "replicate", "view_id", "view_kind",
        "profile_ordinal", "profile_id", "strategy_ordinal", "strategy_id",
        "selection_cell_sha256", "prefix_size", "prefix_payload_sha256",
        "selected_lineup_ids_sha256", "selected_rosters_sha256",
        "retrieval_metrics", "book_score_summary", "tail_metrics",
        "effective_tail_shots", "overlap_metrics",
        "selected_provenance_exposure", "aggregate_scalars", "policy",
        "book_metric_row_sha256",
    }
    if set(row) != expected_fields:
        _fail("book metric row fields differ")
    _self_hash(row, field="book_metric_row_sha256", label="book metric row")
    validate_policy_block_v1(row["policy"], label="book metric row")
    prefix = PREFIX_SIZES[expected_prefix_ordinal]
    kind, profile_ordinal, profile_id = _view_profile_fields_v1(str(row["view_id"]))
    strategy_ordinal = _integer(
        row["strategy_ordinal"], label="book strategy ordinal"
    )
    if (
        row["schema_version"] != BOOK_METRIC_ROW_SCHEMA
        or row["fold_ordinal"] != expected_fold
        or row["heldout_block"] != WORLD_BLOCKS[expected_fold]
        or row["cell_ordinal"] != expected_cell
        or row["prefix_ordinal"] != expected_prefix_ordinal
        or row["prefix_size"] != prefix
        or (row["view_kind"], row["profile_ordinal"], row["profile_id"])
        != (kind, profile_ordinal, profile_id)
        or strategy_ordinal >= len(STRATEGY_IDENTITIES)
        or row["strategy_id"] != STRATEGY_IDENTITIES[strategy_ordinal][1]
    ):
        _fail("book metric row identity/lattice differs")
    for field in (
        "selection_cell_sha256", "prefix_payload_sha256",
        "selected_lineup_ids_sha256", "selected_rosters_sha256",
    ):
        _sha256_hex(row[field], label=f"book {field}")
    summary = _mapping(row["book_score_summary"], label="book score summary")
    if set(summary) != {
        "mean_micro", "maximum_micro", "q50_micro", "q90_micro",
        "q95_micro", "q99_micro",
    } or any(type(value) is not int for value in summary.values()):
        _fail("book score summary fields differ")
    tails = _validate_tail_rows_v1(
        row["tail_metrics"], selected_count=prefix, include_book_max=True
    )
    effective = [
        _validate_effective_tail_row_v1(item)
        for item in _sequence(
            row["effective_tail_shots"], label="effective-tail rows"
        )
    ]
    if [item["threshold"] for item in effective] != list(
        EFFECTIVE_SHOT_THRESHOLDS
    ) or any(item["selected_lineup_count"] != prefix for item in effective):
        _fail("effective-tail threshold/prefix lattice differs")
    expected_scalars = _aggregate_scalars_from_book_v1(
        summary=summary, tail_rows=tails, effective_rows=effective
    )
    if row["aggregate_scalars"] != expected_scalars:
        _fail("book aggregate scalars differ from derived metrics")
    overlap = _mapping(row["overlap_metrics"], label="book overlap metrics")
    pair_count = prefix * (prefix - 1) // 2
    if (
        overlap.get("unordered_lineup_pair_count") != pair_count
        or overlap.get("shared_player_count_denominator") != pair_count
        or not 0 <= int(overlap.get("maximum_shared_player_count", -1)) <= 9
    ):
        _fail("book overlap metric invariants differ")
    return row


def validate_evaluation_result_v1(value: object) -> dict[str, object]:
    """Validate the durable derivation transcript without accepting new rows."""
    item = _mapping(value, label="evaluation result")
    expected_fields = {
        "schema_version", "contract_id", "phase", "source_ordinal", "slate_id",
        "design_publication_identity", "design_sha256", "topology_identity",
        "bootstrap_manifest_identity", "bootstrap_manifest_sha256",
        "evaluator_process_budget_identity", "evaluator_process_budget_sha256",
        "launch_intent_identity", "runtime_observation",
        "runtime_observation_sha256",
        "selection_receipt_identity", "selection_receipt_sha256",
        "logical_fold_selection_count", "selector_os_process_count",
        "child_execution_evidence_sha256s",
        "child_execution_evidence_set_sha256",
        "projection_bundle_identity", "projection_bundle_sha256",
        "later_source_identity", "later_source_body_sha256",
        "player_game_map_sha256", "fold_count", "folds", "folds_sha256",
        "population_metric_row_count", "book_metric_row_count",
        "metric_derivation_law", "caller_metric_rows_accepted",
        "selection_code_callable", "publication_role", "policy",
        "evaluation_result_sha256",
    }
    if set(item) != expected_fields:
        _fail("evaluation result fields differ")
    _self_hash(item, field="evaluation_result_sha256", label="evaluation result")
    validate_policy_block_v1(item["policy"], label="evaluation result")
    phase = _string(item["phase"], label="evaluation phase")
    role = (
        "broad-evaluation-result"
        if phase == BROAD_SCREEN_PHASE
        else "confirmation-evaluation-result"
        if phase == CONFIRMATION_PHASE
        else ""
    )
    source = _integer(item["source_ordinal"], label="evaluation source ordinal")
    if (
        item["schema_version"] != EVALUATION_RESULT_SCHEMA
        or item["contract_id"] != CONTRACT_ID
        or not role
        or source >= PANEL_SLATE_COUNT
        or item["fold_count"] != FOLDS_PER_SLATE
        or item["publication_role"] != role
        or item["logical_fold_selection_count"] != FOLDS_PER_SLATE
        or item["selector_os_process_count"] != 2 * FOLDS_PER_SLATE
        or item["metric_derivation_law"]
        != "sequential-R0-through-R4-full-matrix-to-ordered-metric-rows"
        or item["caller_metric_rows_accepted"] is not False
        or item["selection_code_callable"] is not False
    ):
        _fail("evaluation result authority/law differs")
    _string(item["slate_id"], label="evaluation slate id")
    for field in (
        "design_sha256", "bootstrap_manifest_sha256",
        "evaluator_process_budget_sha256", "runtime_observation_sha256",
        "selection_receipt_sha256", "projection_bundle_sha256",
        "later_source_body_sha256", "player_game_map_sha256",
    ):
        _sha256_hex(item[field], label=f"evaluation {field}")
    evidence_hashes = [
        _sha256_hex(value, label=f"evaluation child evidence[{index}]")
        for index, value in enumerate(
            _sequence(
                item["child_execution_evidence_sha256s"],
                label="evaluation child evidence hashes",
            )
        )
    ]
    if (
        len(evidence_hashes) != FOLDS_PER_SLATE
        or len(set(evidence_hashes)) != FOLDS_PER_SLATE
    ):
        _fail("evaluation child execution evidence ledger differs")
    _sha256_hex(
        item["child_execution_evidence_set_sha256"],
        label="evaluation child evidence set",
    )
    for field in (
        "design_publication_identity", "topology_identity",
        "bootstrap_manifest_identity", "evaluator_process_budget_identity",
        "launch_intent_identity",
        "selection_receipt_identity", "projection_bundle_identity",
        "later_source_identity",
    ):
        _safe_object_identity(item[field], label=f"evaluation {field}")
    runtime = _mapping(item["runtime_observation"], label="runtime observation")
    _self_hash(
        runtime, field="runtime_observation_sha256", label="runtime observation"
    )
    validate_policy_block_v1(runtime.get("policy"), label="runtime observation")
    if (
        runtime.get("schema_version") != RUNTIME_OBSERVATION_SCHEMA
        or runtime.get("runtime_observation_sha256")
        != item["runtime_observation_sha256"]
        or runtime.get("bootstrap_manifest_identity")
        != item["bootstrap_manifest_identity"]
        or runtime.get("process_budget_identity")
        != item["evaluator_process_budget_identity"]
        or runtime.get("launch_intent_identity") != item["launch_intent_identity"]
        or runtime.get("cloud_values_are_unattested_observations") is not True
        or runtime.get("terminal_execution_attestation_required") is not True
    ):
        _fail("evaluation runtime observation binding differs")
    folds = [
        _mapping(fold, label=f"evaluation fold[{index}]")
        for index, fold in enumerate(_sequence(item["folds"], label="evaluation folds"))
    ]
    if len(folds) != FOLDS_PER_SLATE:
        _fail("evaluation result requires exactly five folds")
    population_total = 0
    book_total = 0
    expected_view_ids = list(_view_ids_by_id(
        _derive_view_registry_fixture_v1([
            {
                "lineup_id": f"placeholder-{index:03d}",
                "training_source_arms": sorted(
                    profile_id for _, profile_id, _ in PROFILE_IDENTITIES
                ),
            }
            for index in range(ENTRY_BUDGET)
        ])
    ))
    for fold_ordinal, fold in enumerate(folds):
        if set(fold) != {
            "fold_ordinal", "heldout_block", "selection_fold_receipt_sha256",
            "heldout_fold_authority", "heldout_fold_authority_sha256",
            "later_source_body_sha256", "player_game_map_sha256",
            "population_metric_row_count", "population_metric_rows",
            "population_metric_rows_sha256", "selection_cell_count",
            "book_metric_row_count", "book_metric_rows",
            "book_metric_rows_sha256", "evaluation_fold_sha256",
        }:
            _fail("evaluation fold fields differ")
        _self_hash(fold, field="evaluation_fold_sha256", label="evaluation fold")
        if (
            fold["fold_ordinal"] != fold_ordinal
            or fold["heldout_block"] != WORLD_BLOCKS[fold_ordinal]
        ):
            _fail("evaluation fold order differs")
        if (
            fold["later_source_body_sha256"] != item["later_source_body_sha256"]
            or fold["player_game_map_sha256"] != item["player_game_map_sha256"]
        ):
            _fail("evaluation fold later-source binding differs")
        _sha256_hex(
            fold["selection_fold_receipt_sha256"],
            label="evaluation selection fold receipt",
        )
        heldout = _mapping(
            fold["heldout_fold_authority"], label="heldout fold authority"
        )
        _self_hash(
            heldout,
            field="heldout_fold_authority_sha256",
            label="heldout fold authority",
        )
        if (
            heldout.get("schema_version") != HELDOUT_FOLD_AUTHORITY_SCHEMA
            or heldout.get("heldout_block") != WORLD_BLOCKS[fold_ordinal]
            or heldout.get("heldout_fold_authority_sha256")
            != fold["heldout_fold_authority_sha256"]
        ):
            _fail("heldout fold authority binding differs")
        ledger = _mapping(heldout.get("score_row_ledger"), label="heldout ledger")
        ledger_ids = [str(row.get("lineup_id")) for row in ledger.get("rows", [])]
        _validate_heldout_score_row_ledger_v1(
            ledger, expected_lineup_ids=ledger_ids
        )
        if heldout.get("score_row_ledger_sha256") != canonical_sha256_v1(ledger):
            _fail("heldout score-row ledger hash differs")
        population_rows = [
            _validate_population_metric_row_v1(
                row, expected_view_ordinal=index, expected_fold=fold_ordinal
            )
            for index, row in enumerate(
                _sequence(
                    fold["population_metric_rows"], label="population metric rows"
                )
            )
        ]
        if (
            len(population_rows) != len(expected_view_ids)
            or [row["view_id"] for row in population_rows] != expected_view_ids
            or fold["population_metric_row_count"] != len(population_rows)
            or fold["population_metric_rows_sha256"]
            != canonical_sha256_v1(population_rows)
        ):
            _fail("evaluation population metric lattice/hash differs")
        book_rows_raw = _sequence(
            fold["book_metric_rows"], label="book metric rows"
        )
        cell_count = _integer(
            fold["selection_cell_count"], label="evaluation selection cell count"
        )
        if (
            len(book_rows_raw) != cell_count * len(PREFIX_SIZES)
            or fold["book_metric_row_count"] != len(book_rows_raw)
        ):
            _fail("evaluation book metric row count differs")
        book_rows = [
            _validate_book_metric_row_v1(
                row,
                expected_fold=fold_ordinal,
                expected_cell=index // len(PREFIX_SIZES),
                expected_prefix_ordinal=index % len(PREFIX_SIZES),
            )
            for index, row in enumerate(book_rows_raw)
        ]
        if fold["book_metric_rows_sha256"] != canonical_sha256_v1(book_rows):
            _fail("evaluation book metric row hash differs")
        cell_keys = [
            (
                int(book_rows[index * len(PREFIX_SIZES)]["replicate"]),
                str(book_rows[index * len(PREFIX_SIZES)]["view_id"]),
                str(book_rows[index * len(PREFIX_SIZES)]["strategy_id"]),
            )
            for index in range(cell_count)
        ]
        if phase == BROAD_SCREEN_PHASE:
            expected_keys = [
                (0, view_id, strategy_id)
                for view_id in [
                    "U",
                    *(isolated_view_id_v1(index) for index in range(len(PROFILE_IDENTITIES))),
                ]
                for _, strategy_id, _ in STRATEGY_IDENTITIES
            ]
            if cell_keys != expected_keys:
                _fail("broad evaluation cell lattice/order differs")
        else:
            if cell_count % SUBSAMPLE_REPLICATES != 0:
                _fail("confirmation evaluation cell count differs")
            nominee_count = cell_count // SUBSAMPLE_REPLICATES
            if not MINIMUM_CONFIRMATION_NOMINEES <= nominee_count <= MAXIMUM_CONFIRMATION_NOMINEES:
                _fail("confirmation evaluation nominee count differs")
            base_keys = [(view_id, strategy_id) for _, view_id, strategy_id in cell_keys[:nominee_count]]
            expected_keys = [
                (replicate, view_id, strategy_id)
                for replicate in range(SUBSAMPLE_REPLICATES)
                for view_id, strategy_id in base_keys
            ]
            if cell_keys != expected_keys or len(set(base_keys)) != nominee_count:
                _fail("confirmation evaluation cell lattice/order differs")
        population_total += len(population_rows)
        book_total += len(book_rows)
    if (
        item["folds_sha256"] != canonical_sha256_v1(folds)
        or item["population_metric_row_count"] != population_total
        or item["book_metric_row_count"] != book_total
    ):
        _fail("evaluation result row totals/hash differ")
    return item


def validate_evaluation_result_authority_v1(
    value: object,
    *,
    publication_identity: object,
    design: object,
    design_publication_identity: object,
    topology_identity: object,
    selection_receipt: object,
    selection_receipt_identity: object,
    projection_bundle: object,
    projection_bundle_identity: object,
    heldout_fold_input_stream: Iterable[object],
    later_source_body: object,
    evaluator_process_budget: object,
    evaluator_process_budget_identity: object,
    bootstrap_manifest: object,
    bootstrap_manifest_identity: object,
    runtime_observation: object,
    launch_intent_identity: object,
    nomination_publication: object | None = None,
    nomination_publication_identity: object | None = None,
) -> dict[str, object]:
    expected = build_evaluation_result_v1(
        design=design,
        design_publication_identity=design_publication_identity,
        topology_identity=topology_identity,
        selection_receipt=selection_receipt,
        selection_receipt_identity=selection_receipt_identity,
        projection_bundle=projection_bundle,
        projection_bundle_identity=projection_bundle_identity,
        heldout_fold_input_stream=heldout_fold_input_stream,
        later_source_body=later_source_body,
        evaluator_process_budget=evaluator_process_budget,
        evaluator_process_budget_identity=evaluator_process_budget_identity,
        bootstrap_manifest=bootstrap_manifest,
        bootstrap_manifest_identity=bootstrap_manifest_identity,
        runtime_observation=runtime_observation,
        launch_intent_identity=launch_intent_identity,
        nomination_publication=nomination_publication,
        nomination_publication_identity=nomination_publication_identity,
    )
    retained = validate_evaluation_result_v1(value)
    if canonical_json_bytes_v1(retained) != canonical_json_bytes_v1(expected):
        _fail("evaluation result differs from exact internally derived metrics")
    identity = _bind_canonical_body_to_identity_v1(
        retained, publication_identity, label="evaluation result"
    )
    design_value = validate_design_authority_v1(
        design, publication_identity=design_publication_identity
    )
    if identity["uri"] != _topology_uri_v1(
        design_value["topology"],
        role=str(retained["publication_role"]),
        source_ordinal=int(retained["source_ordinal"]),
    ):
        _fail("evaluation result URI differs from design topology")
    return retained


def _metric_row(value: object, *, offset: int, expected_replicates: int) -> dict[str, object]:
    row = _mapping(value, label=f"aggregate metric row[{offset}]")
    metric_stems = (
        "mean_heldout_expected_book_max_micro", "mean_heldout_p_max_gt_200",
        "mean_heldout_p_max_gt_220", "mean_heldout_p_max_gt_230",
        "mean_heldout_participation_ratio_gt_220_micro",
    )
    metric_fields = {f"{stem}_{part}" for stem in metric_stems for part in ("numerator", "denominator")}
    expected_fields = {
        "view_id",
        "profile_id",
        "profile_ordinal",
        "strategy_id",
        "strategy_ordinal",
        "prefix_size",
        *metric_fields,
        "complete_cell_count",
        "subsample_replicate_count",
    }
    if set(row) != expected_fields:
        _fail(f"aggregate metric row[{offset}] fields differ")
    view_id = _string(row["view_id"], label=f"row[{offset}] view id")
    profile_id = _string(row["profile_id"], label=f"row[{offset}] profile id")
    profile_ordinal = _integer(
        row["profile_ordinal"],
        label=f"row[{offset}] profile ordinal",
        minimum=-1,
    )
    strategy_id = _string(row["strategy_id"], label=f"row[{offset}] strategy id")
    strategy_ordinal = _integer(
        row["strategy_ordinal"], label=f"row[{offset}] strategy ordinal"
    )
    if (
        strategy_ordinal >= len(STRATEGY_IDENTITIES)
        or strategy_id != STRATEGY_IDENTITIES[strategy_ordinal][1]
    ):
        _fail(f"aggregate metric row[{offset}] strategy differs")
    if view_id == "U":
        if profile_id != "all-profiles" or profile_ordinal != -1:
            _fail(f"aggregate metric row[{offset}] union profile differs")
    elif (
        not 0 <= profile_ordinal < len(PROFILE_IDENTITIES)
        or profile_id != _profile_id(profile_ordinal)
        or view_id != isolated_view_id_v1(profile_ordinal)
    ):
        _fail(f"aggregate metric row[{offset}] is not an exploratory view")
    if row["prefix_size"] != ENTRY_BUDGET:
        _fail(f"aggregate metric row[{offset}] must be the exact-80 prefix")
    normalized = {
        "view_id": view_id,
        "profile_id": profile_id,
        "profile_ordinal": profile_ordinal,
        "strategy_id": strategy_id,
        "strategy_ordinal": strategy_ordinal,
        "prefix_size": ENTRY_BUDGET,
        **{
            field: _integer(
                row[field],
                label=f"row[{offset}] {field}",
                minimum=1 if field.endswith("_denominator") else 0,
            )
            for field in metric_fields
        },
        "complete_cell_count": _integer(
            row["complete_cell_count"], label=f"row[{offset}] complete cells"
        ),
        "subsample_replicate_count": _integer(
            row["subsample_replicate_count"],
            label=f"row[{offset}] subsample replicates",
        ),
    }
    values = {stem: Fraction(normalized[f"{stem}_numerator"], normalized[f"{stem}_denominator"]) for stem in metric_stems}
    if (
        normalized["complete_cell_count"] != PANEL_SLATE_COUNT * len(WORLD_BLOCKS)
        or normalized["subsample_replicate_count"] != expected_replicates
        or any(values[stem] > 1 for stem in metric_stems[1:4])
        or values[metric_stems[4]] > ENTRY_BUDGET * MICRO_SCALE
    ):
        _fail(f"aggregate metric row[{offset}] completeness or range differs")
    return normalized


def _metric_fraction(row: Mapping[str, object], stem: str) -> Fraction:
    return Fraction(int(row[f"{stem}_numerator"]), int(row[f"{stem}_denominator"]))


def _cell_key(row: Mapping[str, object]) -> tuple[str, str]:
    return str(row["view_id"]), str(row["strategy_id"])


def _performance_order(row: Mapping[str, object]) -> tuple[Fraction, Fraction, Fraction, int, int]:
    return (
        -_metric_fraction(row, "mean_heldout_expected_book_max_micro"),
        -_metric_fraction(row, "mean_heldout_p_max_gt_220"),
        -_metric_fraction(row, "mean_heldout_participation_ratio_gt_220_micro"),
        int(row["profile_ordinal"]),
        int(row["strategy_ordinal"]),
    )


def _diversity_order(row: Mapping[str, object]) -> tuple[Fraction, Fraction, int, int]:
    return (
        -_metric_fraction(row, "mean_heldout_participation_ratio_gt_220_micro"),
        -_metric_fraction(row, "mean_heldout_p_max_gt_230"),
        int(row["profile_ordinal"]),
        int(row["strategy_ordinal"]),
    )


def _p200_guard_v1(baseline: Fraction) -> tuple[Fraction, Fraction]:
    relative = baseline * Fraction(P200_RELATIVE_MARGIN_NUMERATOR, P200_RELATIVE_MARGIN_DENOMINATOR)
    margin = max(Fraction(P200_ABSOLUTE_NONINFERIORITY_MARGIN_MICRO, MICRO_SCALE), relative)
    return margin, baseline - margin


def _fraction_json(value: Fraction) -> dict[str, int]:
    return {"numerator": value.numerator, "denominator": value.denominator}


def _broad_metric_grid_v1(value: object) -> dict[tuple[str, str], dict[str, object]]:
    rows = [
        _metric_row(value, offset=offset, expected_replicates=BROAD_SCREEN_REPLICATES)
        for offset, value in enumerate(
            _sequence(value, label="broad-screen aggregate metric rows")
        )
    ]
    by_key = {_cell_key(row): row for row in rows}
    if len(by_key) != len(rows):
        _fail("broad-screen metric cells must be unique")
    required_keys = {
        ("U", strategy_id)
        for _, strategy_id, _ in STRATEGY_IDENTITIES
    } | {
        (isolated_view_id_v1(profile_ordinal), strategy_id)
        for profile_ordinal, _, _ in PROFILE_IDENTITIES
        for _, strategy_id, _ in STRATEGY_IDENTITIES
    }
    if set(by_key) != required_keys:
        _fail("broad-screen grid is not the exact U plus seven-profile lattice")
    for stem in (
        "mean_heldout_expected_book_max_micro", "mean_heldout_p_max_gt_200",
        "mean_heldout_p_max_gt_220", "mean_heldout_p_max_gt_230",
        "mean_heldout_participation_ratio_gt_220_micro",
    ):
        if len({row[f"{stem}_denominator"] for row in rows}) != 1:
            _fail("aggregate grid metric denominators must be common")
    return by_key


def _nomination_v1(
    broad_rows_value: object,
) -> tuple[
    dict[tuple[str, str], dict[str, object]],
    dict[tuple[str, str], list[str]],
    Fraction,
    Fraction,
    Fraction,
]:
    by_key = _broad_metric_grid_v1(broad_rows_value)
    baseline = by_key[(PRIMARY_BASELINE_VIEW_ID, PRIMARY_BASELINE_STRATEGY_ID)]
    baseline_p200 = _metric_fraction(baseline, "mean_heldout_p_max_gt_200")
    margin, guard_floor = _p200_guard_v1(baseline_p200)
    passing = [
        row
        for row in by_key.values()
        if int(row["profile_ordinal"]) > 0
        and row["view_id"] == isolated_view_id_v1(int(row["profile_ordinal"]))
        and _metric_fraction(row, "mean_heldout_p_max_gt_200") >= guard_floor
    ]
    selected_roles: dict[tuple[str, str], list[str]] = {}

    def add(row: Mapping[str, object], role: str) -> None:
        selected_roles.setdefault(_cell_key(row), []).append(role)

    add(baseline, "mandatory-current-union-control")
    add(
        by_key[("U", TAIL_CONTROL_STRATEGY_ID)],
        "mandatory-current-union-tail-control",
    )
    add(
        by_key[(isolated_view_id_v1(0), PRIMARY_BASELINE_STRATEGY_ID)],
        "mandatory-legacy-profile-sentinel",
    )
    performance = min(passing, key=_performance_order) if passing else None
    if performance is not None:
        add(performance, "performance-nominee")
    chosen = set(selected_roles)
    diversity_pool = []
    if performance is not None:
        top_expected = _metric_fraction(performance, "mean_heldout_expected_book_max_micro")
        diversity_pool = [
            row
            for row in passing
            if _cell_key(row) not in chosen
            and _metric_fraction(row, "mean_heldout_expected_book_max_micro")
            >= top_expected - EXPECTED_MAX_DIVERSITY_WINDOW_MICRO
        ]
    diversity = min(diversity_pool, key=_diversity_order) if diversity_pool else None
    if diversity is not None:
        add(diversity, "diversity-nominee")
    chosen = set(selected_roles)
    structural_pool = [
        row
        for row in passing
        if _cell_key(row) not in chosen
        and str(row["profile_id"]) in STRUCTURAL_CONTRAST_PROFILES
    ]
    structural = min(structural_pool, key=_performance_order) if structural_pool else None
    if structural is not None:
        add(structural, "structural-contrast-nominee")
    return by_key, selected_roles, baseline_p200, margin, guard_floor


def _ordered_cells_v1(
    *,
    by_key: Mapping[tuple[str, str], Mapping[str, object]],
    roles_by_key: Mapping[tuple[str, str], Sequence[str]],
    guard_floor: Fraction,
) -> list[dict[str, object]]:
    role_order = {
        "mandatory-current-union-control": 0,
        "mandatory-current-union-tail-control": 1,
        "mandatory-legacy-profile-sentinel": 2,
        "performance-nominee": 3,
        "diversity-nominee": 4,
        "structural-contrast-nominee": 5,
    }
    cells = []
    for key, roles_value in roles_by_key.items():
        row = by_key[key]
        roles = list(roles_value)
        cells.append({
            "view_id": row["view_id"],
            "profile_id": row["profile_id"],
            "profile_ordinal": row["profile_ordinal"],
            "strategy_id": row["strategy_id"],
            "strategy_ordinal": row["strategy_ordinal"],
            "prefix_size": ENTRY_BUDGET,
            "roles": roles,
            "passes_simulated_p200_noninferiority": (
                _metric_fraction(row, "mean_heldout_p_max_gt_200") >= guard_floor
                if int(row["profile_ordinal"]) > 0
                else None
            ),
        })
    cells.sort(key=lambda row: (
        min(role_order[role] for role in row["roles"]),
        int(row["profile_ordinal"]),
        int(row["strategy_ordinal"]),
    ))
    return cells


def _deterministic_nominees_fixture_v1(broad_rows_value: object) -> dict[str, object]:
    """Nominate a bounded confirmation lattice from one broad-screen sample."""
    by_key, roles, baseline_p200, margin, guard_floor = _nomination_v1(
        broad_rows_value
    )
    nominees = _ordered_cells_v1(
        by_key=by_key, roles_by_key=roles, guard_floor=guard_floor
    )
    if not 3 <= len(nominees) <= 6:
        _fail("deterministic nominee count differs")
    body = {
        "schema_version": NOMINATION_SCHEMA,
        "contract_id": CONTRACT_ID,
        "baseline_p200": _fraction_json(baseline_p200),
        "p200_noninferiority_margin": _fraction_json(margin),
        "p200_noninferiority_floor": _fraction_json(guard_floor),
        "nominee_count": len(nominees),
        "nominees": nominees,
        "human_nominee_input_accepted": False,
        "uses_realized_outcomes": False,
        "promotion_authority": False,
        "decision_authority": False,
    }
    return _with_hash(body, field="nomination_sha256")


def _deterministic_finalists_fixture_v1(
    broad_rows_value: object, confirmation_rows_value: object
) -> dict[str, object]:
    """Confirm broad nominees on 32 new samples; never add or backfill a cell."""
    nomination = _deterministic_nominees_fixture_v1(broad_rows_value)
    raw_confirmation = _sequence(
        confirmation_rows_value, label="confirmation aggregate metric rows"
    )
    confirmation_rows = [
        _metric_row(value, offset=offset, expected_replicates=SUBSAMPLE_REPLICATES)
        for offset, value in enumerate(raw_confirmation)
    ]
    by_key = {_cell_key(row): row for row in confirmation_rows}
    if len(by_key) != len(confirmation_rows):
        _fail("confirmation metric cells must be unique")
    roles_by_key = {
        (str(row["view_id"]), str(row["strategy_id"])): list(row["roles"])
        for row in nomination["nominees"]
    }
    if set(by_key) != set(roles_by_key):
        _fail("confirmation grid differs from deterministic nominees")
    baseline = by_key[(PRIMARY_BASELINE_VIEW_ID, PRIMARY_BASELINE_STRATEGY_ID)]
    baseline_p200 = _metric_fraction(baseline, "mean_heldout_p_max_gt_200")
    margin, guard_floor = _p200_guard_v1(baseline_p200)
    retained_roles = {
        key: roles
        for key, roles in roles_by_key.items()
        if any(role.startswith("mandatory-") for role in roles)
        or _metric_fraction(by_key[key], "mean_heldout_p_max_gt_200") >= guard_floor
    }
    finalists = _ordered_cells_v1(
        by_key=by_key, roles_by_key=retained_roles, guard_floor=guard_floor
    )
    if not 3 <= len(finalists) <= len(roles_by_key):
        _fail("deterministic finalist count differs")
    body = {
        "schema_version": FINALIST_SCHEMA,
        "contract_id": CONTRACT_ID,
        "nomination_sha256": nomination["nomination_sha256"],
        "baseline_p200": _fraction_json(baseline_p200),
        "p200_noninferiority_margin": _fraction_json(margin),
        "p200_noninferiority_floor": _fraction_json(guard_floor),
        "nominee_count": len(roles_by_key),
        "finalist_count": len(finalists),
        "removed_challenger_count": len(roles_by_key) - len(finalists),
        "finalists": finalists,
        "human_finalist_input_accepted": False,
        "uses_realized_outcomes": False,
        "historical_scoring_licensed": False,
        "promotion_authority": False,
        "decision_authority": False,
    }
    return _with_hash(body, field="finalist_function_sha256")


def _build_phase_grid_fixture_v1(*, phase: str, rows: object) -> dict[str, object]:
    retained_phase = _string(phase, label="phase grid phase")
    if retained_phase not in {BROAD_SCREEN_PHASE, CONFIRMATION_PHASE}:
        _fail("phase grid phase differs")
    expected_replicates = (
        BROAD_SCREEN_REPLICATES
        if retained_phase == BROAD_SCREEN_PHASE
        else SUBSAMPLE_REPLICATES
    )
    normalized_rows = [
        _metric_row(row, offset=index, expected_replicates=expected_replicates)
        for index, row in enumerate(_sequence(rows, label="phase grid rows"))
    ]
    if not normalized_rows:
        _fail("phase grid cannot be empty")
    metric_stems = (
        "mean_heldout_expected_book_max_micro", "mean_heldout_p_max_gt_200",
        "mean_heldout_p_max_gt_220", "mean_heldout_p_max_gt_230",
        "mean_heldout_participation_ratio_gt_220_micro",
    )
    for stem in metric_stems:
        denominators = {
            int(row[f"{stem}_denominator"]) for row in normalized_rows
        }
        if len(denominators) != 1 or next(iter(denominators)) < 1:
            _fail(f"{retained_phase} phase grid {stem} denominator differs")
    if retained_phase == BROAD_SCREEN_PHASE:
        _broad_metric_grid_v1(normalized_rows)
    body = {
        "schema_version": PHASE_GRID_SCHEMA,
        "contract_id": CONTRACT_ID,
        "phase": retained_phase,
        "row_count": len(normalized_rows),
        "rows": normalized_rows,
        "rows_sha256": canonical_sha256_v1(normalized_rows),
        "policy": _policy_block(),
    }
    return _with_hash(body, field="phase_grid_sha256")


def validate_phase_grid_v1(value: object, *, phase: str) -> dict[str, object]:
    item = _mapping(value, label="phase grid")
    if set(item) != {
        "schema_version", "contract_id", "phase", "row_count", "rows",
        "rows_sha256", "policy", "phase_grid_sha256",
    }:
        _fail("phase grid fields differ")
    _self_hash(item, field="phase_grid_sha256", label="phase grid")
    validate_policy_block_v1(item["policy"], label="phase grid")
    expected = _build_phase_grid_fixture_v1(phase=phase, rows=item["rows"])
    if canonical_json_bytes_v1(item) != canonical_json_bytes_v1(expected):
        _fail("phase grid canonical replay differs")
    return expected


def build_layer_binding_v1(*, role: str, entries: object) -> dict[str, object]:
    retained_role = _string(role, label="layer role")
    if retained_role not in LAYER_ROLES:
        _fail("layer role differs from the exact result topology")
    raw_entries = _sequence(entries, label=f"{retained_role} layer entries")
    if len(raw_entries) != PANEL_SLATE_COUNT:
        _fail(f"{retained_role} layer requires exactly 54 identities")
    normalized = []
    slate_ids: list[str] = []
    identities = []
    for ordinal, raw in enumerate(raw_entries):
        row = _mapping(raw, label=f"{retained_role} layer[{ordinal}]")
        if set(row) != {"source_ordinal", "slate_id", "identity"}:
            _fail(f"{retained_role} layer row fields differ")
        if row["source_ordinal"] != ordinal:
            _fail(f"{retained_role} layer must use explicit ordinal order")
        slate_id = _string(row["slate_id"], label=f"{retained_role} slate id")
        identity = _safe_object_identity(
            row["identity"], label=f"{retained_role} identity[{ordinal}]"
        )
        normalized.append({
            "source_ordinal": ordinal,
            "slate_id": slate_id,
            "identity": identity,
        })
        slate_ids.append(slate_id)
        identities.append(identity)
    _validate_one_generation_per_uri_v1(identities, label=f"{retained_role} identities")
    if len(set(slate_ids)) != PANEL_SLATE_COUNT:
        _fail(f"{retained_role} layer slate ids repeat")
    body = {
        "role": retained_role,
        "entry_count": PANEL_SLATE_COUNT,
        "ordinal_order_law": "source-ordinal-0-through-53-not-uri-lexical-order",
        "entries": normalized,
        "entries_sha256": canonical_sha256_v1(normalized),
    }
    return _with_hash(body, field="layer_binding_sha256")


def validate_layer_binding_v1(value: object, *, role: str) -> dict[str, object]:
    item = _mapping(value, label=f"{role} layer binding")
    _self_hash(item, field="layer_binding_sha256", label=f"{role} layer binding")
    expected = build_layer_binding_v1(role=role, entries=item.get("entries"))
    if canonical_json_bytes_v1(item) != canonical_json_bytes_v1(expected):
        _fail(f"{role} layer binding canonical replay differs")
    return expected


def _build_broad_phase_authority_fixture_v1(
    *,
    design_identity: object,
    topology: object,
    topology_identity: object,
    run_identity: object,
    projection_layer: object,
    selection_layer: object,
    evaluation_layer: object,
    broad_phase_grid: object,
) -> dict[str, object]:
    retained_topology = validate_result_topology_v1(topology)
    retained_topology_identity = _bind_canonical_body_to_identity_v1(
        retained_topology, topology_identity, label="result topology"
    )
    grid = validate_phase_grid_v1(
        broad_phase_grid, phase=BROAD_SCREEN_PHASE
    )
    projections = validate_layer_binding_v1(projection_layer, role="projection")
    selections = validate_layer_binding_v1(
        selection_layer, role="broad-selection-receipt"
    )
    evaluations = validate_layer_binding_v1(
        evaluation_layer, role="broad-evaluation-result"
    )
    slate_orders = [
        [row["slate_id"] for row in layer["entries"]]
        for layer in (projections, selections, evaluations)
    ]
    if slate_orders[1:] != slate_orders[:1] * 2:
        _fail("broad phase authority layer slate order differs")
    for layer, role in (
        (projections, "projection"),
        (selections, "broad-selection-receipt"),
        (evaluations, "broad-evaluation-result"),
    ):
        if [str(entry["identity"]["uri"]) for entry in layer["entries"]] != [
            _topology_uri_v1(
                retained_topology, role=role, source_ordinal=source_ordinal
            )
            for source_ordinal in range(PANEL_SLATE_COUNT)
        ]:
            _fail(f"broad phase authority {role} URIs differ from topology")
    body = {
        "schema_version": BROAD_PHASE_AUTHORITY_SCHEMA,
        "contract_id": CONTRACT_ID,
        "design_identity": _safe_object_identity(design_identity, label="design"),
        "topology": retained_topology,
        "topology_identity": retained_topology_identity,
        "run_identity": _safe_object_identity(run_identity, label="run"),
        "projection_layer": projections,
        "broad_selection_layer": selections,
        "broad_evaluation_layer": evaluations,
        "broad_phase_grid": grid,
        "policy": _policy_block(),
    }
    return _with_hash(body, field="broad_phase_authority_sha256")


def _validate_broad_phase_authority_fixture_v1(value: object) -> dict[str, object]:
    item = _mapping(value, label="broad phase authority")
    _self_hash(
        item, field="broad_phase_authority_sha256", label="broad phase authority"
    )
    validate_policy_block_v1(item.get("policy"), label="broad phase authority")
    expected = _build_broad_phase_authority_fixture_v1(
        design_identity=item.get("design_identity"),
        topology=item.get("topology"),
        topology_identity=item.get("topology_identity"),
        run_identity=item.get("run_identity"),
        projection_layer=item.get("projection_layer"),
        selection_layer=item.get("broad_selection_layer"),
        evaluation_layer=item.get("broad_evaluation_layer"),
        broad_phase_grid=item.get("broad_phase_grid"),
    )
    if canonical_json_bytes_v1(item) != canonical_json_bytes_v1(expected):
        _fail("broad phase authority canonical replay differs")
    return expected


def deterministic_nominees_from_broad_authority_v1(value: object) -> dict[str, object]:
    authority = validate_broad_phase_authority_v1(value)
    fixture = _deterministic_nominees_fixture_v1(
        authority["broad_phase_grid"]["rows"]
    )
    body = {
        key: item for key, item in fixture.items() if key != "nomination_sha256"
    }
    body.update({
        "broad_phase_authority_sha256": authority[
            "broad_phase_authority_sha256"
        ],
        "broad_phase_grid_sha256": authority["broad_phase_grid"][
            "phase_grid_sha256"
        ],
        "policy": _policy_block(),
    })
    return _with_hash(body, field="nomination_sha256")


def validate_nomination_v1(value: object, *, broad_phase_authority: object) -> dict[str, object]:
    item = _mapping(value, label="nomination")
    _self_hash(item, field="nomination_sha256", label="nomination")
    validate_policy_block_v1(item.get("policy"), label="nomination")
    expected = deterministic_nominees_from_broad_authority_v1(
        broad_phase_authority
    )
    if canonical_json_bytes_v1(item) != canonical_json_bytes_v1(expected):
        _fail("nomination differs from exact broad phase authority")
    return expected


def _bootstrap_index(seed: bytes, replicate: int, draw: int) -> int:
    limit = 2**256 - (2**256 % BOOTSTRAP_CLUSTER_COUNT)
    nonce = 0
    while True:
        digest = sha256(seed + replicate.to_bytes(4, "big") + draw.to_bytes(2, "big") + nonce.to_bytes(4, "big")).digest()
        number = int.from_bytes(digest, "big")
        if number < limit:
            return number % BOOTSTRAP_CLUSTER_COUNT
        nonce += 1


@lru_cache(maxsize=8)
def _bootstrap_draw_matrix(seed_hex: str) -> tuple[tuple[int, ...], ...]:
    seed = bytes.fromhex(seed_hex)
    return tuple(
        tuple(
            _bootstrap_index(seed, replicate, draw)
            for draw in range(BOOTSTRAP_CLUSTER_COUNT)
        )
        for replicate in range(BOOTSTRAP_RESAMPLES)
    )


def _linear_quantile_micro(values: Sequence[int], numerator: int, denominator: int) -> int:
    ordered = sorted(values)
    position = Fraction((len(ordered) - 1) * numerator, denominator)
    lower = position.numerator // position.denominator
    upper = min(lower + 1, len(ordered) - 1)
    weight = position - lower
    return _round_fraction_ties_even(Fraction(ordered[lower]) * (1 - weight) + Fraction(ordered[upper]) * weight)


def _deterministic_slate_cluster_bootstrap_fixture_v1(
    rows_value: object, *, contract_sha256: str, code_sha256: str,
    slate_identities_value: object,
) -> dict[str, object]:
    """Canonical 10k resamples of 54 whole five-fold slate clusters."""
    contract_hash = _sha256_hex(contract_sha256, label="tracked contract sha256")
    code_hash = _sha256_hex(code_sha256, label="code sha256")
    identities = [_mapping(value, label="slate identity") for value in _sequence(slate_identities_value, label="slate identities")]
    if len(identities) != PANEL_SLATE_COUNT:
        _fail("bootstrap requires exactly 54 slate identities")
    slate_ids: list[str] = []
    normalized_identities = []
    for item in identities:
        if set(item) != {"slate_id", "sha256"}:
            _fail("bootstrap slate identity fields differ")
        slate_id = _string(item["slate_id"], label="bootstrap slate id")
        normalized_identities.append({"slate_id": slate_id, "sha256": _sha256_hex(item["sha256"], label="bootstrap slate sha256")})
        slate_ids.append(slate_id)
    if len(set(slate_ids)) != PANEL_SLATE_COUNT:
        _fail("bootstrap slate identities must be unique in source-ordinal order")
    rows = [_mapping(value, label="bootstrap row") for value in _sequence(rows_value, label="bootstrap rows")]
    by_slate: dict[str, list[Fraction]] = {slate_id: [] for slate_id in slate_ids}
    for row in rows:
        if set(row) != {"slate_id", "heldout_block", "delta_numerator_micro", "delta_denominator"}:
            _fail("bootstrap row fields differ")
        slate_id = _string(row["slate_id"], label="bootstrap row slate")
        block = _string(row["heldout_block"], label="bootstrap heldout block")
        if slate_id not in by_slate or block != WORLD_BLOCKS[len(by_slate[slate_id])]:
            _fail("bootstrap rows must be ordered by slate then canonical heldout block")
        by_slate[slate_id].append(_fraction(row["delta_numerator_micro"], row["delta_denominator"], label="bootstrap delta", allow_negative=True))
    if any(len(values) != BOOTSTRAP_BLOCKS_PER_CLUSTER for values in by_slate.values()):
        _fail("bootstrap requires all five folds per slate")
    seed_material = {
        "contract_sha256": contract_hash, "code_sha256": code_hash,
        "panel_identity": dict(PANEL_IDENTITY), "panel_self_sha256": PANEL_SELF_SHA256,
        "slate_identities": normalized_identities,
    }
    seed = bytes.fromhex(canonical_sha256_v1(seed_material))
    values = []
    draws_by_replicate = _bootstrap_draw_matrix(seed.hex())
    for replicate in range(BOOTSTRAP_RESAMPLES):
        total = Fraction(0)
        for source in draws_by_replicate[replicate]:
            total += sum(by_slate[slate_ids[source]], Fraction(0))
        values.append(_round_fraction_ties_even(total / (BOOTSTRAP_CLUSTER_COUNT * BOOTSTRAP_BLOCKS_PER_CLUSTER)))
    body = {
        "schema_version": BOOTSTRAP_SCHEMA, "contract_id": CONTRACT_ID,
        "seed_material": seed_material, "seed_sha256": seed.hex(),
        "resample_count": BOOTSTRAP_RESAMPLES, "cluster_count": BOOTSTRAP_CLUSTER_COUNT,
        "folds_per_cluster": BOOTSTRAP_BLOCKS_PER_CLUSTER,
        "lower_quantile": {"numerator": 1, "denominator": 40},
        "upper_quantile": {"numerator": 39, "denominator": 40},
        "lower_endpoint_micro": _linear_quantile_micro(values, 1, 40),
        "upper_endpoint_micro": _linear_quantile_micro(values, 39, 40),
        "resample_values_sha256": canonical_sha256_v1(values),
        "policy": _policy_block(),
    }
    return _with_hash(body, field="bootstrap_sha256")


def _build_bootstrap_input_binding_fixture_v1(
    *,
    contract_sha256: str,
    code_sha256: str,
    evaluation_layer: object,
    rows: object,
) -> dict[str, object]:
    """Bind the exact 54-by-five paired-delta ledger before resampling."""
    layer = validate_layer_binding_v1(
        evaluation_layer, role="confirmation-evaluation-result"
    )
    normalized_rows = [
        _mapping(row, label=f"bootstrap input row[{index}]")
        for index, row in enumerate(
            _sequence(rows, label="bootstrap input rows")
        )
    ]
    expected_pairs = [
        (str(entry["slate_id"]), block)
        for entry in layer["entries"]
        for block in WORLD_BLOCKS
    ]
    observed_pairs: list[tuple[str, str]] = []
    for index, row in enumerate(normalized_rows):
        if set(row) != {
            "slate_id", "heldout_block", "delta_numerator_micro",
            "delta_denominator",
        }:
            _fail(f"bootstrap input row[{index}] fields differ")
        observed_pairs.append((
            _string(row["slate_id"], label=f"bootstrap row[{index}] slate"),
            _string(row["heldout_block"], label=f"bootstrap row[{index}] block"),
        ))
        numerator = row["delta_numerator_micro"]
        if type(numerator) is not int:
            _fail(f"bootstrap row[{index}] delta numerator must be an integer")
        _integer(
            row["delta_denominator"],
            label=f"bootstrap row[{index}] delta denominator",
            minimum=1,
        )
    if observed_pairs != expected_pairs:
        _fail("bootstrap input rows differ from source-ordinal/fold order")
    slate_identities = [
        {
            "slate_id": str(entry["slate_id"]),
            "sha256": str(entry["identity"]["sha256"]),
        }
        for entry in layer["entries"]
    ]
    body = {
        "schema_version": BOOTSTRAP_INPUT_SCHEMA,
        "contract_id": CONTRACT_ID,
        "contract_sha256": _sha256_hex(
            contract_sha256, label="bootstrap contract sha256"
        ),
        "code_sha256": _sha256_hex(code_sha256, label="bootstrap code sha256"),
        "evaluation_layer": layer,
        "evaluation_layer_sha256": layer["layer_binding_sha256"],
        "slate_identities": slate_identities,
        "slate_identities_sha256": canonical_sha256_v1(slate_identities),
        "row_count": len(normalized_rows),
        "rows": normalized_rows,
        "rows_sha256": canonical_sha256_v1(normalized_rows),
        "source_order_law": "source-ordinal-0-through-53-then-R0-through-R4",
        "policy": _policy_block(),
    }
    return _with_hash(body, field="bootstrap_input_sha256")


def validate_bootstrap_input_binding_v1(value: object) -> dict[str, object]:
    item = _mapping(value, label="bootstrap input binding")
    _self_hash(item, field="bootstrap_input_sha256", label="bootstrap input")
    validate_policy_block_v1(item.get("policy"), label="bootstrap input")
    expected = _build_bootstrap_input_binding_fixture_v1(
        contract_sha256=item.get("contract_sha256"),
        code_sha256=item.get("code_sha256"),
        evaluation_layer=item.get("evaluation_layer"),
        rows=item.get("rows"),
    )
    if canonical_json_bytes_v1(item) != canonical_json_bytes_v1(expected):
        _fail("bootstrap input canonical replay differs")
    return expected


def _deterministic_slate_cluster_bootstrap_from_binding_v1(
    value: object,
) -> dict[str, object]:
    """Authoritative bootstrap entry point; raw ledgers are not accepted."""
    binding = validate_bootstrap_input_binding_v1(value)
    result = _deterministic_slate_cluster_bootstrap_fixture_v1(
        binding["rows"],
        contract_sha256=str(binding["contract_sha256"]),
        code_sha256=str(binding["code_sha256"]),
        slate_identities_value=binding["slate_identities"],
    )
    body = {
        key: retained
        for key, retained in result.items()
        if key not in {"bootstrap_sha256", "policy"}
    }
    body.update({
        "bootstrap_input_sha256": binding["bootstrap_input_sha256"],
        "evaluation_layer_sha256": binding["evaluation_layer_sha256"],
        "rows_sha256": binding["rows_sha256"],
        "policy": _policy_block(),
    })
    return _with_hash(body, field="bootstrap_sha256")


def build_result_topology_v1(output_prefix: str) -> dict[str, object]:
    prefix = _string(output_prefix, label="output prefix")
    child = prefix[len(OUTPUT_NAMESPACE):] if prefix.startswith(OUTPUT_NAMESPACE) else ""
    if (
        not prefix.startswith(OUTPUT_NAMESPACE)
        or not prefix.endswith("/")
        or not child
        or child == "/"
        or any(part in {"", ".", ".."} for part in child[:-1].split("/"))
        or "//" in prefix[5:]
    ):
        _fail("output prefix is outside the fixed research namespace")
    objects: list[dict[str, object]] = [{"ordinal": 0, "role": "design", "uri": prefix + "design.json"}]
    ordinal = 1
    layers = (
        ("projection", "projections"),
        ("broad-selection-receipt", "broad/selection-receipts"),
        ("broad-evaluation-result", "broad/evaluation-results"),
    )
    for role, directory in layers:
        for index in range(PANEL_SLATE_COUNT):
            objects.append({"ordinal": ordinal, "role": role, "uri": f"{prefix}{directory}/slate-{index:02d}.json"}); ordinal += 1
    objects.append({"ordinal": ordinal, "role": "nomination", "uri": prefix + "nomination.json"}); ordinal += 1
    for role, directory in (
        ("confirmation-selection-receipt", "confirmation/selection-receipts"),
        ("confirmation-evaluation-result", "confirmation/evaluation-results"),
    ):
        for index in range(PANEL_SLATE_COUNT):
            objects.append({"ordinal": ordinal, "role": role, "uri": f"{prefix}{directory}/slate-{index:02d}.json"}); ordinal += 1
    for role, leaf in (("aggregate", "aggregate.json"), ("confirmed-finalists", "confirmed-finalists.json"), ("root", "root.json")):
        objects.append({"ordinal": ordinal, "role": role, "uri": prefix + leaf}); ordinal += 1
    if (
        len(objects) != OUTPUT_OBJECT_COUNT
        or len({row["uri"] for row in objects}) != OUTPUT_OBJECT_COUNT
        or objects[-1]["role"] != "root"
        or objects[-1]["ordinal"] != OUTPUT_OBJECT_COUNT - 1
    ):
        _fail("result topology count differs")
    return _with_hash({
        "schema_version": TOPOLOGY_SCHEMA,
        "contract_id": CONTRACT_ID,
        "output_prefix": prefix,
        "child_run_prefix": child[:-1],
        "object_count": len(objects),
        "publication_order_law": "strict-ordinal-create-once-root-last",
        "objects": objects,
        "policy": _policy_block(),
    }, field="topology_sha256")


def validate_result_topology_v1(value: object) -> dict[str, object]:
    item = _mapping(value, label="result topology")
    _self_hash(item, field="topology_sha256", label="result topology")
    validate_policy_block_v1(item.get("policy"), label="result topology")
    expected = build_result_topology_v1(
        _string(item.get("output_prefix"), label="topology output prefix")
    )
    if canonical_json_bytes_v1(item) != canonical_json_bytes_v1(expected):
        _fail("result topology canonical replay differs")
    return expected


def _topology_uri_v1(
    topology: Mapping[str, object], *, role: str, source_ordinal: int | None = None,
) -> str:
    rows = [row for row in topology["objects"] if row["role"] == role]
    if source_ordinal is None:
        if len(rows) != 1:
            _fail(f"topology role {role} is not singular")
        return str(rows[0]["uri"])
    ordinal = _integer(source_ordinal, label=f"{role} source ordinal")
    if ordinal >= PANEL_SLATE_COUNT or len(rows) != PANEL_SLATE_COUNT:
        _fail(f"topology role {role} cardinality differs")
    return str(rows[ordinal]["uri"])


def _process_budget_inventory_v1() -> list[dict[str, object]]:
    invocation_counts = {
        "projection-publisher": 1,
        "broad-fold-selector": PANEL_SLATE_COUNT * FOLDS_PER_SLATE,
        "broad-slate-assembler": PANEL_SLATE_COUNT,
        "broad-evaluator": PANEL_SLATE_COUNT,
        "confirmation-fold-selector": PANEL_SLATE_COUNT * FOLDS_PER_SLATE,
        "confirmation-slate-assembler": PANEL_SLATE_COUNT,
        "confirmation-evaluator": PANEL_SLATE_COUNT,
        "broad-nomination-publisher": 1,
        "aggregate-finalist-publisher": 1,
        "terminal-root-publisher": 1,
    }
    return [
        {
            "process_role": role,
            "maximum_logical_invocation_count": invocation_counts[role],
            "maximum_os_process_count": invocation_counts[role] * (
                2 if role.endswith("fold-selector") else 1
            ),
            "maximum_output_bytes_per_invocation": _ROLE_OUTPUT_BYTE_CEILINGS[role],
        }
        for role in PROCESS_ROLES
    ]


def build_bootstrap_manifest_v1(
    *, topology: object, topology_identity: object, run_identity: object,
    code_commit: str, image_digest: str, process_specs: object,
) -> dict[str, object]:
    """Freeze the expected execution image, commands, and process inventory."""
    retained_topology = validate_result_topology_v1(topology)
    retained_topology_identity = _bind_canonical_body_to_identity_v1(
        retained_topology, topology_identity, label="bootstrap topology"
    )
    commit = _string(code_commit, label="bootstrap code commit")
    if (
        len(commit) != 40
        or any(character not in _SHA256_HEX for character in commit)
    ):
        _fail("bootstrap code commit must be one lowercase 40-hex commit")
    digest = _string(image_digest, label="bootstrap image digest")
    if not digest.startswith("sha256:"):
        _fail("bootstrap image digest differs")
    _sha256_hex(digest[7:], label="bootstrap image digest")
    raw_specs = _sequence(process_specs, label="bootstrap process specs")
    if len(raw_specs) != len(PROCESS_ROLES):
        _fail("bootstrap process spec count differs")
    specs = []
    for expected_role, raw in zip(PROCESS_ROLES, raw_specs, strict=True):
        row = _mapping(raw, label=f"bootstrap process spec {expected_role}")
        if set(row) != {"process_role", "process_chain"}:
            _fail("bootstrap process spec fields differ")
        raw_chain = _sequence(
            row["process_chain"], label=f"{expected_role} process chain"
        )
        expected_components = (
            ["artifact-broker", "matrix-selector"]
            if expected_role.endswith("fold-selector")
            else ["main"]
        )
        if (
            row["process_role"] != expected_role
            or len(raw_chain) != len(expected_components)
        ):
            _fail("bootstrap process spec role/chain differs")
        chain = []
        for component_role, raw_component in zip(
            expected_components, raw_chain, strict=True
        ):
            component = _mapping(
                raw_component,
                label=f"{expected_role} {component_role} process spec",
            )
            if set(component) != {
                "component_role", "command", "entrypoint_path",
                "entrypoint_sha256",
            } or component["component_role"] != component_role:
                _fail("bootstrap process-chain component differs")
            command = [
                _string(token, label=f"{expected_role} command token")
                for token in _sequence(
                    component["command"], label=f"{expected_role} command"
                )
            ]
            if not command:
                _fail("bootstrap process-chain command is empty")
            chain.append({
                "component_role": component_role,
                "command": command,
                "entrypoint_path": _string(
                    component["entrypoint_path"],
                    label=f"{expected_role} entrypoint",
                ),
                "entrypoint_sha256": _sha256_hex(
                    component["entrypoint_sha256"],
                    label=f"{expected_role} entrypoint sha256",
                ),
            })
        specs.append({
            "process_role": expected_role,
            "process_chain": chain,
        })
    inventory = _process_budget_inventory_v1()
    body = {
        "schema_version": BOOTSTRAP_MANIFEST_SCHEMA,
        "contract_id": CONTRACT_ID,
        "run_identity": _safe_object_identity(run_identity, label="bootstrap run"),
        "run_identity_semantics": (
            "pre-design-run-authorization-and-launch-intent-token"
        ),
        "launch_intent_identity_must_equal_run_identity": True,
        "run_identity_is_cloud_execution_attestation": False,
        "code_commit": commit,
        "image_digest": digest,
        "topology": retained_topology,
        "topology_identity": retained_topology_identity,
        "topology_sha256": retained_topology["topology_sha256"],
        "process_specs": specs,
        "process_specs_sha256": canonical_sha256_v1(specs),
        "process_budget_inventory": inventory,
        "process_budget_inventory_sha256": canonical_sha256_v1(inventory),
        "environment_values_are_observations_only": True,
        "cloud_attestation_required_at_terminal_execution": True,
        "policy": _policy_block(),
    }
    return _with_hash(body, field="bootstrap_manifest_sha256")


def validate_bootstrap_manifest_v1(value: object) -> dict[str, object]:
    item = _mapping(value, label="bootstrap manifest")
    _self_hash(item, field="bootstrap_manifest_sha256", label="bootstrap manifest")
    validate_policy_block_v1(item.get("policy"), label="bootstrap manifest")
    expected = build_bootstrap_manifest_v1(
        topology=item.get("topology"),
        topology_identity=item.get("topology_identity"),
        run_identity=item.get("run_identity"),
        code_commit=str(item.get("code_commit", "")),
        image_digest=str(item.get("image_digest", "")),
        process_specs=item.get("process_specs"),
    )
    return expected


def validate_bootstrap_manifest_authority_v1(
    value: object, *, publication_identity: object, topology: object,
    topology_identity: object,
) -> dict[str, object]:
    item = _mapping(value, label="bootstrap manifest")
    expected_fields = {
        "schema_version", "contract_id", "run_identity", "code_commit",
        "run_identity_semantics",
        "launch_intent_identity_must_equal_run_identity",
        "run_identity_is_cloud_execution_attestation",
        "image_digest", "topology", "topology_identity", "topology_sha256",
        "process_specs", "process_specs_sha256", "process_budget_inventory",
        "process_budget_inventory_sha256",
        "environment_values_are_observations_only",
        "cloud_attestation_required_at_terminal_execution", "policy",
        "bootstrap_manifest_sha256",
    }
    if set(item) != expected_fields:
        _fail("bootstrap manifest fields differ")
    retained_topology = validate_result_topology_v1(topology)
    retained_topology_identity = _bind_canonical_body_to_identity_v1(
        retained_topology, topology_identity, label="bootstrap topology"
    )
    expected = build_bootstrap_manifest_v1(
        topology=retained_topology,
        topology_identity=retained_topology_identity,
        run_identity=item["run_identity"],
        code_commit=str(item["code_commit"]),
        image_digest=str(item["image_digest"]),
        process_specs=item["process_specs"],
    )
    if canonical_json_bytes_v1(item) != canonical_json_bytes_v1(expected):
        _fail("bootstrap manifest canonical replay differs")
    _bind_canonical_body_to_identity_v1(
        expected, publication_identity, label="bootstrap manifest"
    )
    return expected


def _launch_authority_from_bootstrap_v1(
    bootstrap_manifest: Mapping[str, object], launch_intent_identity: object,
) -> dict[str, object]:
    """Bind launch authority without creating a design/bootstrap cycle.

    The bootstrap run identity is the immutable, pre-design authorization
    token.  It is not evidence that a cloud job ran; terminal execution
    receipts provide that later attestation.
    """
    launch = _safe_object_identity(
        launch_intent_identity, label="pre-design launch authorization"
    )
    if (
        bootstrap_manifest.get("run_identity_semantics")
        != "pre-design-run-authorization-and-launch-intent-token"
        or bootstrap_manifest.get(
            "launch_intent_identity_must_equal_run_identity"
        ) is not True
        or bootstrap_manifest.get(
            "run_identity_is_cloud_execution_attestation"
        ) is not False
        or launch != bootstrap_manifest.get("run_identity")
    ):
        _fail("launch authority differs from bootstrap run authorization")
    return launch


def build_design_v1(
    *, output_prefix: str, code_identity: object, report_identity: object,
    topology_identity: object, bootstrap_manifest: object,
    bootstrap_manifest_identity: object,
) -> dict[str, object]:
    """Freeze topology and an exact precharge for every one of 275 objects."""
    topology = build_result_topology_v1(output_prefix)
    retained_topology_identity = _bind_canonical_body_to_identity_v1(
        topology, topology_identity, label="design topology"
    )
    retained_bootstrap = validate_bootstrap_manifest_authority_v1(
        bootstrap_manifest,
        publication_identity=bootstrap_manifest_identity,
        topology=topology,
        topology_identity=retained_topology_identity,
    )
    publication_budgets = [
        {
            "ordinal": row["ordinal"],
            "role": row["role"],
            "uri": row["uri"],
            "max_bytes": _PUBLICATION_BYTE_CEILINGS[str(row["role"])],
            "create_once": True,
        }
        for row in topology["objects"]
    ]
    body = {
        "schema_version": DESIGN_SCHEMA,
        "contract_id": CONTRACT_ID,
        "code_identity": _safe_object_identity(code_identity, label="design code"),
        "report_identity": _safe_object_identity(report_identity, label="design report"),
        "topology": topology,
        "topology_identity": retained_topology_identity,
        "topology_sha256": topology["topology_sha256"],
        "bootstrap_manifest_identity": _safe_object_identity(
            bootstrap_manifest_identity, label="design bootstrap manifest"
        ),
        "bootstrap_manifest": retained_bootstrap,
        "bootstrap_manifest_sha256": retained_bootstrap[
            "bootstrap_manifest_sha256"
        ],
        "publication_object_count": OUTPUT_OBJECT_COUNT,
        "publication_budgets": publication_budgets,
        "publication_budgets_sha256": canonical_sha256_v1(publication_budgets),
        "selector_fit_ceiling": MAXIMUM_SELECTOR_FITS,
        "all_block_fit_count": 0,
        "policy": _policy_block(),
    }
    return _with_hash(body, field="design_sha256")


def validate_design_v1(value: object) -> dict[str, object]:
    item = _mapping(value, label="design")
    _self_hash(item, field="design_sha256", label="design")
    validate_policy_block_v1(item.get("policy"), label="design")
    topology = validate_result_topology_v1(item.get("topology"))
    expected = build_design_v1(
        output_prefix=str(topology["output_prefix"]),
        code_identity=item.get("code_identity"),
        report_identity=item.get("report_identity"),
        topology_identity=item.get("topology_identity"),
        bootstrap_manifest=item.get("bootstrap_manifest"),
        bootstrap_manifest_identity=item.get("bootstrap_manifest_identity"),
    )
    if canonical_json_bytes_v1(item) != canonical_json_bytes_v1(expected):
        _fail("design canonical replay differs")
    return expected


def validate_design_authority_v1(value: object, *, publication_identity: object) -> dict[str, object]:
    design = validate_design_v1(value)
    identity = _bind_canonical_body_to_identity_v1(design, publication_identity, label="design")
    if identity["uri"] != _topology_uri_v1(design["topology"], role="design"):
        _fail("design URI differs from embedded topology")
    return design


def build_finalist_publication_v1(
    *, finalists: object, aggregate: object, aggregate_publication_identity: object,
) -> dict[str, object]:
    retained = validate_finalists_v1(
        finalists,
        aggregate=aggregate,
        aggregate_publication_identity=aggregate_publication_identity,
    )
    body = {
        "schema_version": FINALIST_PUBLICATION_SCHEMA,
        "contract_id": CONTRACT_ID,
        "aggregate_publication_identity": _safe_object_identity(
            aggregate_publication_identity, label="aggregate publication"
        ),
        "finalists": retained,
        "finalist_function_sha256": retained["finalist_function_sha256"],
        "policy": _policy_block(),
    }
    return _with_hash(body, field="finalist_publication_sha256")


def validate_finalist_publication_authority_v1(
    value: object, *, publication_identity: object, aggregate: object,
    aggregate_publication_identity: object,
) -> dict[str, object]:
    item = _mapping(value, label="finalist publication")
    _self_hash(item, field="finalist_publication_sha256", label="finalist publication")
    expected = build_finalist_publication_v1(
        finalists=item.get("finalists"), aggregate=aggregate,
        aggregate_publication_identity=aggregate_publication_identity,
    )
    if canonical_json_bytes_v1(item) != canonical_json_bytes_v1(expected):
        _fail("finalist publication canonical replay differs")
    aggregate_value = validate_aggregate_mechanics_authority_v1(
        aggregate, publication_identity=aggregate_publication_identity
    )
    identity = _bind_canonical_body_to_identity_v1(item, publication_identity, label="finalist publication")
    if identity["uri"] != _topology_uri_v1(aggregate_value["topology"], role="confirmed-finalists"):
        _fail("finalist publication URI differs from topology")
    return item


def _build_terminal_root_fixture_v1(
    *, design: object, design_publication_identity: object,
    predecessor_bodies: object, predecessor_identities: object,
) -> dict[str, object]:
    retained_design = validate_design_authority_v1(
        design, publication_identity=design_publication_identity
    )
    topology = retained_design["topology"]
    expected_rows = list(topology["objects"][:-1])
    bodies = list(_sequence(predecessor_bodies, label="root predecessor bodies"))
    identities = list(_sequence(predecessor_identities, label="root predecessor identities"))
    if len(bodies) != OUTPUT_OBJECT_COUNT - 1 or len(identities) != len(bodies):
        _fail("terminal root requires exactly 274 predecessors")
    rows = []
    for expected_row, body_value, identity_value in zip(expected_rows, bodies, identities, strict=True):
        body = _mapping(body_value, label="root predecessor body")
        identity = _bind_canonical_body_to_identity_v1(body, identity_value, label="root predecessor")
        if identity["uri"] != expected_row["uri"]:
            _fail("terminal root predecessor URI/order differs")
        rows.append({"ordinal": expected_row["ordinal"], "role": expected_row["role"], "identity": identity})
    if rows[0]["identity"] != _safe_object_identity(design_publication_identity, label="design publication"):
        _fail("terminal root first predecessor is not the exact design")
    body = {
        "schema_version": ROOT_SCHEMA,
        "contract_id": CONTRACT_ID,
        "design_publication_identity": rows[0]["identity"],
        "topology_sha256": topology["topology_sha256"],
        "predecessor_count": len(rows),
        "predecessors": rows,
        "predecessors_sha256": canonical_sha256_v1(rows),
        "publication_order_law": "strict-ordinal-create-once-root-last",
        "policy": _policy_block(),
    }
    return _with_hash(body, field="root_sha256")


def _validate_terminal_root_fixture_authority_v1(
    value: object, *, publication_identity: object, design: object,
    design_publication_identity: object, predecessor_bodies: object,
    predecessor_identities: object,
) -> dict[str, object]:
    item = _mapping(value, label="terminal root")
    _self_hash(item, field="root_sha256", label="terminal root")
    validate_policy_block_v1(item.get("policy"), label="terminal root")
    expected = _build_terminal_root_fixture_v1(
        design=design,
        design_publication_identity=design_publication_identity,
        predecessor_bodies=predecessor_bodies,
        predecessor_identities=predecessor_identities,
    )
    if canonical_json_bytes_v1(item) != canonical_json_bytes_v1(expected):
        _fail("terminal root canonical replay differs")
    retained_design = validate_design_authority_v1(
        design, publication_identity=design_publication_identity
    )
    identity = _bind_canonical_body_to_identity_v1(item, publication_identity, label="terminal root")
    if identity["uri"] != _topology_uri_v1(retained_design["topology"], role="root"):
        _fail("terminal root URI differs from topology")
    return expected


def _build_aggregate_mechanics_fixture_v1(
    *,
    design_identity: object,
    topology: object,
    topology_identity: object,
    run_identity: object,
    broad_phase_authority: object,
    nomination: object,
    nomination_identity: object,
    projection_layer: object,
    broad_selection_layer: object,
    broad_evaluation_layer: object,
    confirmation_selection_layer: object,
    confirmation_evaluation_layer: object,
    broad_phase_grid: object,
    confirmation_phase_grid: object,
    bootstrap_input: object,
) -> dict[str, object]:
    """Bind both experiment phases without inventing unmaterialized roots."""
    retained_topology = validate_result_topology_v1(topology)
    retained_topology_identity = _bind_canonical_body_to_identity_v1(
        retained_topology, topology_identity, label="result topology"
    )
    design = _safe_object_identity(design_identity, label="design")
    run = _safe_object_identity(run_identity, label="run")
    broad_authority = validate_broad_phase_authority_v1(broad_phase_authority)
    if (
        broad_authority["design_identity"] != design
        or broad_authority["topology_identity"] != retained_topology_identity
        or broad_authority["run_identity"] != run
    ):
        _fail("broad authority design/topology/run binding differs")
    retained_nomination = validate_nomination_v1(
        nomination, broad_phase_authority=broad_authority
    )
    retained_nomination_identity = _bind_canonical_body_to_identity_v1(
        retained_nomination, nomination_identity, label="nomination"
    )
    layers = {
        "projection_layer": validate_layer_binding_v1(
            projection_layer, role="projection"
        ),
        "broad_selection_layer": validate_layer_binding_v1(
            broad_selection_layer, role="broad-selection-receipt"
        ),
        "broad_evaluation_layer": validate_layer_binding_v1(
            broad_evaluation_layer, role="broad-evaluation-result"
        ),
        "confirmation_selection_layer": validate_layer_binding_v1(
            confirmation_selection_layer,
            role="confirmation-selection-receipt",
        ),
        "confirmation_evaluation_layer": validate_layer_binding_v1(
            confirmation_evaluation_layer,
            role="confirmation-evaluation-result",
        ),
    }
    if (
        layers["projection_layer"] != broad_authority["projection_layer"]
        or layers["broad_selection_layer"]
        != broad_authority["broad_selection_layer"]
        or layers["broad_evaluation_layer"]
        != broad_authority["broad_evaluation_layer"]
    ):
        _fail("aggregate broad layers differ from nomination authority")
    slate_orders = [
        [entry["slate_id"] for entry in layer["entries"]]
        for layer in layers.values()
    ]
    if any(order != slate_orders[0] for order in slate_orders[1:]):
        _fail("aggregate layer source-ordinal slate order differs")
    topology_roles = {
        "projection_layer": "projection",
        "broad_selection_layer": "broad-selection-receipt",
        "broad_evaluation_layer": "broad-evaluation-result",
        "confirmation_selection_layer": "confirmation-selection-receipt",
        "confirmation_evaluation_layer": "confirmation-evaluation-result",
    }
    for layer_name, role in topology_roles.items():
        expected_uris = [
            _topology_uri_v1(retained_topology, role=role, source_ordinal=index)
            for index in range(PANEL_SLATE_COUNT)
        ]
        observed_uris = [
            str(entry["identity"]["uri"])
            for entry in layers[layer_name]["entries"]
        ]
        if observed_uris != expected_uris:
            _fail(f"aggregate {layer_name} differs from topology role URIs")
    broad_grid = validate_phase_grid_v1(
        broad_phase_grid, phase=BROAD_SCREEN_PHASE
    )
    confirmation_grid = validate_phase_grid_v1(
        confirmation_phase_grid, phase=CONFIRMATION_PHASE
    )
    if broad_grid != broad_authority["broad_phase_grid"]:
        _fail("aggregate broad grid differs from nomination authority")
    if {_cell_key(row) for row in confirmation_grid["rows"]} != set(
        _nominee_keys_v1(retained_nomination)
    ):
        _fail("confirmation grid differs from exact nomination lattice")
    bootstrap = validate_bootstrap_input_binding_v1(bootstrap_input)
    if bootstrap["evaluation_layer"] != layers["confirmation_evaluation_layer"]:
        _fail("bootstrap input differs from confirmation evaluation layer")
    body = {
        "schema_version": AGGREGATE_MECHANICS_SCHEMA,
        "contract_id": CONTRACT_ID,
        "design_identity": design,
        "topology": retained_topology,
        "topology_identity": retained_topology_identity,
        "run_identity": run,
        "broad_phase_authority": broad_authority,
        "broad_phase_authority_sha256": broad_authority[
            "broad_phase_authority_sha256"
        ],
        "nomination": retained_nomination,
        "nomination_identity": retained_nomination_identity,
        "nomination_sha256": retained_nomination["nomination_sha256"],
        **layers,
        "broad_phase_grid": broad_grid,
        "confirmation_phase_grid": confirmation_grid,
        "bootstrap_input": bootstrap,
        "bootstrap_input_sha256": bootstrap["bootstrap_input_sha256"],
        "output_object_count": OUTPUT_OBJECT_COUNT,
        "all_block_final_fit_count": 0,
        "policy": _policy_block(),
    }
    return _with_hash(body, field="aggregate_mechanics_sha256")


def _validate_aggregate_mechanics_fixture_v1(value: object) -> dict[str, object]:
    item = _mapping(value, label="aggregate mechanics")
    _self_hash(
        item, field="aggregate_mechanics_sha256", label="aggregate mechanics"
    )
    validate_policy_block_v1(item.get("policy"), label="aggregate mechanics")
    expected = _build_aggregate_mechanics_fixture_v1(
        design_identity=item.get("design_identity"),
        topology=item.get("topology"),
        topology_identity=item.get("topology_identity"),
        run_identity=item.get("run_identity"),
        broad_phase_authority=item.get("broad_phase_authority"),
        nomination=item.get("nomination"),
        nomination_identity=item.get("nomination_identity"),
        projection_layer=item.get("projection_layer"),
        broad_selection_layer=item.get("broad_selection_layer"),
        broad_evaluation_layer=item.get("broad_evaluation_layer"),
        confirmation_selection_layer=item.get("confirmation_selection_layer"),
        confirmation_evaluation_layer=item.get("confirmation_evaluation_layer"),
        broad_phase_grid=item.get("broad_phase_grid"),
        confirmation_phase_grid=item.get("confirmation_phase_grid"),
        bootstrap_input=item.get("bootstrap_input"),
    )
    if canonical_json_bytes_v1(item) != canonical_json_bytes_v1(expected):
        _fail("aggregate mechanics canonical replay differs")
    return expected


def _validate_aggregate_mechanics_fixture_authority_v1(
    value: object, *, publication_identity: object,
) -> dict[str, object]:
    aggregate = _validate_aggregate_mechanics_fixture_v1(value)
    publication = _bind_canonical_body_to_identity_v1(
        aggregate, publication_identity, label="aggregate mechanics"
    )
    if publication["uri"] != _topology_uri_v1(
        aggregate["topology"], role="aggregate"
    ):
        _fail("aggregate mechanics URI differs from result topology")
    return aggregate


def _evaluation_publications_v1(
    value: object, *, phase: str, design: Mapping[str, object],
    design_publication_identity: Mapping[str, object],
) -> list[dict[str, object]]:
    topology = design["topology"]
    role = (
        "broad-evaluation-result"
        if phase == BROAD_SCREEN_PHASE
        else "confirmation-evaluation-result"
        if phase == CONFIRMATION_PHASE
        else ""
    )
    if not role:
        _fail("evaluation publication phase differs")
    raw_records = _sequence(value, label=f"{phase} evaluation publications")
    if len(raw_records) != PANEL_SLATE_COUNT:
        _fail(f"{phase} requires exactly 54 evaluation publications")
    records: list[dict[str, object]] = []
    shared_fold_exemplars: dict[str, dict[str, object]] = {}
    for source_ordinal, raw in enumerate(raw_records):
        record = _mapping(
            raw, label=f"{phase} evaluation publication[{source_ordinal}]"
        )
        if set(record) != {"source_ordinal", "body", "identity"}:
            _fail("evaluation publication record fields differ")
        raw_body = _mapping(record["body"], label="evaluation publication body")
        folds_hash = str(raw_body.get("folds_sha256", ""))
        exemplar = shared_fold_exemplars.get(folds_hash)
        if (
            exemplar is not None
            and raw_body.get("folds") is exemplar.get("folds")
        ):
            body = _validate_evaluation_result_shared_folds_v1(
                raw_body, exemplar=exemplar
            )
        else:
            body = validate_evaluation_result_v1(raw_body)
            shared_fold_exemplars[folds_hash] = body
        identity = _bind_canonical_body_to_identity_v1(
            body, record["identity"], label=f"{phase} evaluation publication"
        )
        if (
            record["source_ordinal"] != source_ordinal
            or body["source_ordinal"] != source_ordinal
            or body["phase"] != phase
            or body["publication_role"] != role
            or body["design_publication_identity"] != design_publication_identity
            or body["design_sha256"] != design["design_sha256"]
            or identity["uri"] != _topology_uri_v1(
                topology, role=role, source_ordinal=source_ordinal
            )
        ):
            _fail("evaluation publication source/phase/design/topology differs")
        records.append({
            "source_ordinal": source_ordinal,
            "slate_id": body["slate_id"],
            "phase": phase,
            "body": body,
            "identity": identity,
        })
    if len({str(record["slate_id"]) for record in records}) != PANEL_SLATE_COUNT:
        _fail("evaluation publication slate IDs repeat")
    _validate_one_generation_per_uri_v1(
        [record["identity"] for record in records],
        label=f"{phase} evaluation identities",
    )
    return records


def _validate_evaluation_result_shared_folds_v1(
    value: object, *, exemplar: Mapping[str, object],
) -> dict[str, object]:
    """Fast path only for an identical in-memory fold object already validated."""
    item = _mapping(value, label="shared-fold evaluation result")
    if item.get("folds") is not exemplar.get("folds"):
        _fail("shared-fold validation requires the exact validated fold object")
    _self_hash(item, field="evaluation_result_sha256", label="evaluation result")
    validate_policy_block_v1(item.get("policy"), label="evaluation result")
    phase = _string(item.get("phase"), label="evaluation phase")
    role = (
        "broad-evaluation-result"
        if phase == BROAD_SCREEN_PHASE
        else "confirmation-evaluation-result"
        if phase == CONFIRMATION_PHASE
        else ""
    )
    source = _integer(item.get("source_ordinal"), label="evaluation source ordinal")
    immutable_fold_fields = (
        "fold_count", "folds", "folds_sha256", "population_metric_row_count",
        "book_metric_row_count", "later_source_identity",
        "later_source_body_sha256", "player_game_map_sha256",
        "logical_fold_selection_count", "selector_os_process_count",
    )
    if (
        set(item) != set(exemplar)
        or not role
        or source >= PANEL_SLATE_COUNT
        or item.get("schema_version") != EVALUATION_RESULT_SCHEMA
        or item.get("contract_id") != CONTRACT_ID
        or item.get("publication_role") != role
        or item.get("metric_derivation_law")
        != "sequential-R0-through-R4-full-matrix-to-ordered-metric-rows"
        or item.get("caller_metric_rows_accepted") is not False
        or item.get("selection_code_callable") is not False
        or any(item.get(field) != exemplar.get(field) for field in immutable_fold_fields)
    ):
        _fail("shared-fold evaluation header/law differs")
    _string(item.get("slate_id"), label="evaluation slate id")
    for field in (
        "design_sha256", "bootstrap_manifest_sha256",
        "evaluator_process_budget_sha256", "runtime_observation_sha256",
        "selection_receipt_sha256", "projection_bundle_sha256",
        "later_source_body_sha256", "player_game_map_sha256",
    ):
        _sha256_hex(item.get(field), label=f"evaluation {field}")
    for field in (
        "design_publication_identity", "topology_identity",
        "bootstrap_manifest_identity", "evaluator_process_budget_identity",
        "launch_intent_identity",
        "selection_receipt_identity", "projection_bundle_identity",
        "later_source_identity",
    ):
        _safe_object_identity(item.get(field), label=f"evaluation {field}")
    return item


def _compact_evaluation_record_v1(
    record: Mapping[str, object],
) -> dict[str, object]:
    """Retain only aggregate inputs after an evaluation body was validated."""
    body = _mapping(record["body"], label="evaluation body to compact")
    compact_folds = [
        {
            "fold_ordinal": fold["fold_ordinal"],
            "heldout_block": fold["heldout_block"],
            "book_metric_rows": [
                row
                for row in fold["book_metric_rows"]
                if row["prefix_size"] == ENTRY_BUDGET
            ],
        }
        for fold in body["folds"]
    ]
    compact_body = {
        field: body[field]
        for field in (
            "evaluation_result_sha256", "selection_receipt_identity",
            "selection_receipt_sha256", "projection_bundle_identity",
            "projection_bundle_sha256", "topology_identity", "design_sha256",
            "bootstrap_manifest_identity", "bootstrap_manifest_sha256",
            "evaluator_process_budget_identity",
            "evaluator_process_budget_sha256", "launch_intent_identity",
            "runtime_observation_sha256", "folds_sha256",
            "logical_fold_selection_count", "selector_os_process_count",
            "child_execution_evidence_sha256s",
            "child_execution_evidence_set_sha256",
        )
    }
    compact_body["folds"] = compact_folds
    return {
        "source_ordinal": int(record["source_ordinal"]),
        "slate_id": record["slate_id"],
        "phase": record["phase"],
        "body": compact_body,
        "identity": record["identity"],
    }


def _minimal_aggregate_evaluation_record_v1(
    compact_record: Mapping[str, object],
) -> dict[str, object]:
    """Retain only the exact-80 aggregate scalars used by frozen reducers."""
    compact = _mapping(compact_record, label="compact evaluation record")
    body = _mapping(compact["body"], label="compact evaluation body")
    folds: list[dict[str, object]] = []
    for fold_index, fold_value in enumerate(body["folds"]):
        fold = _mapping(fold_value, label=f"compact fold[{fold_index}]")
        rows: list[dict[str, object]] = []
        for row_index, row_value in enumerate(fold["book_metric_rows"]):
            row = _mapping(
                row_value, label=f"compact fold[{fold_index}] row[{row_index}]"
            )
            scalars = _mapping(
                row["aggregate_scalars"], label="compact aggregate scalars"
            )
            rows.append({
                "prefix_size": row["prefix_size"],
                "replicate": row["replicate"],
                "view_id": row["view_id"],
                "strategy_id": row["strategy_id"],
                "aggregate_scalars": {
                    str(stem): dict(_mapping(value, label=f"compact {stem}"))
                    for stem, value in scalars.items()
                },
            })
        folds.append({
            "fold_ordinal": fold["fold_ordinal"],
            "heldout_block": fold["heldout_block"],
            "book_metric_rows": rows,
        })
    minimal_body = {key: value for key, value in body.items() if key != "folds"}
    minimal_body["folds"] = folds
    return {
        "source_ordinal": compact["source_ordinal"],
        "slate_id": compact["slate_id"],
        "phase": compact["phase"],
        "body": minimal_body,
        "identity": compact["identity"],
    }


def _evaluation_publication_summaries_v1(
    records: Sequence[Mapping[str, object]],
) -> list[dict[str, object]]:
    return [
        {
            "source_ordinal": int(record["source_ordinal"]),
            "slate_id": record["slate_id"],
            "phase": record["phase"],
            "evaluation_identity": record["identity"],
            "evaluation_result_sha256": record["body"][
                "evaluation_result_sha256"
            ],
            "selection_receipt_identity": record["body"][
                "selection_receipt_identity"
            ],
            "selection_receipt_sha256": record["body"][
                "selection_receipt_sha256"
            ],
            "projection_bundle_identity": record["body"][
                "projection_bundle_identity"
            ],
            "projection_bundle_sha256": record["body"][
                "projection_bundle_sha256"
            ],
            "bootstrap_manifest_identity": record["body"][
                "bootstrap_manifest_identity"
            ],
            "bootstrap_manifest_sha256": record["body"][
                "bootstrap_manifest_sha256"
            ],
            "evaluator_process_budget_identity": record["body"][
                "evaluator_process_budget_identity"
            ],
            "evaluator_process_budget_sha256": record["body"][
                "evaluator_process_budget_sha256"
            ],
            "launch_intent_identity": record["body"]["launch_intent_identity"],
            "runtime_observation_sha256": record["body"][
                "runtime_observation_sha256"
            ],
            "logical_fold_selection_count": record["body"][
                "logical_fold_selection_count"
            ],
            "selector_os_process_count": record["body"][
                "selector_os_process_count"
            ],
            "child_execution_evidence_sha256s": record["body"][
                "child_execution_evidence_sha256s"
            ],
            "child_execution_evidence_set_sha256": record["body"][
                "child_execution_evidence_set_sha256"
            ],
            "folds_sha256": record["body"]["folds_sha256"],
        }
        for record in records
    ]


def _phase_execution_lattice_v1(
    summaries: Sequence[Mapping[str, object]], *, phase: str,
) -> dict[str, object]:
    """Reduce 54 five-fold transcripts to one ordered phase authority."""
    retained_phase = _string(phase, label="phase execution lattice")
    if len(summaries) != PANEL_SLATE_COUNT:
        _fail("phase execution lattice requires 54 evaluation summaries")
    evidence_hashes: list[str] = []
    evidence_set_hashes: list[str] = []
    logical_count = 0
    os_count = 0
    expected_summary_fields = {
        "source_ordinal", "slate_id", "phase", "evaluation_identity",
        "evaluation_result_sha256", "selection_receipt_identity",
        "selection_receipt_sha256", "projection_bundle_identity",
        "projection_bundle_sha256", "bootstrap_manifest_identity",
        "bootstrap_manifest_sha256", "evaluator_process_budget_identity",
        "evaluator_process_budget_sha256", "launch_intent_identity",
        "runtime_observation_sha256", "logical_fold_selection_count",
        "selector_os_process_count", "child_execution_evidence_sha256s",
        "child_execution_evidence_set_sha256", "folds_sha256",
    }
    for source, summary in enumerate(summaries):
        if (
            set(summary) != expected_summary_fields
            or summary.get("phase") != retained_phase
            or summary.get("source_ordinal") != source
            or summary.get("logical_fold_selection_count") != FOLDS_PER_SLATE
            or summary.get("selector_os_process_count")
            != 2 * FOLDS_PER_SLATE
        ):
            _fail("phase execution summary count/order differs")
        hashes = [
            _sha256_hex(value, label="phase child execution evidence")
            for value in _sequence(
                summary.get("child_execution_evidence_sha256s"),
                label="phase child execution evidence hashes",
            )
        ]
        if len(hashes) != FOLDS_PER_SLATE or len(set(hashes)) != FOLDS_PER_SLATE:
            _fail("phase child execution evidence fold lattice differs")
        evidence_hashes.extend(hashes)
        evidence_set_hashes.append(_sha256_hex(
            summary.get("child_execution_evidence_set_sha256"),
            label="phase child execution evidence set",
        ))
        logical_count += int(summary["logical_fold_selection_count"])
        os_count += int(summary["selector_os_process_count"])
    if (
        logical_count != LOGICAL_FOLD_SELECTION_COUNT_PER_PHASE
        or os_count != SELECTOR_OS_PROCESS_COUNT_PER_PHASE
        or len(evidence_hashes) != LOGICAL_FOLD_SELECTION_COUNT_PER_PHASE
        or len(set(evidence_hashes)) != LOGICAL_FOLD_SELECTION_COUNT_PER_PHASE
        or len(set(evidence_set_hashes)) != PANEL_SLATE_COUNT
    ):
        _fail("phase execution authority count/distinctness differs")
    return {
        "phase": retained_phase,
        "logical_fold_selection_count": logical_count,
        "selector_os_process_count": os_count,
        "child_execution_evidence_sha256s": evidence_hashes,
        "child_execution_evidence_sha256s_sha256": canonical_sha256_v1(
            evidence_hashes
        ),
        "slate_child_execution_evidence_set_sha256s": evidence_set_hashes,
        "slate_child_execution_evidence_set_sha256s_sha256": canonical_sha256_v1(
            evidence_set_hashes
        ),
        "source_fold_order_law": (
            "source-ordinal-0-through-53-then-R0-through-R4"
        ),
    }


_AGGREGATE_METRIC_STEMS: Final = (
    "mean_heldout_expected_book_max_micro",
    "mean_heldout_p_max_gt_200",
    "mean_heldout_p_max_gt_220",
    "mean_heldout_p_max_gt_230",
    "mean_heldout_participation_ratio_gt_220_micro",
)


def _phase_book_rows_v1(
    records: Sequence[Mapping[str, object]],
) -> list[dict[str, object]]:
    rows = []
    for record in records:
        for fold in record["body"]["folds"]:
            for row in fold["book_metric_rows"]:
                if row["prefix_size"] != ENTRY_BUDGET:
                    continue
                rows.append({
                    "source_ordinal": record["source_ordinal"],
                    "slate_id": record["slate_id"],
                    "fold_ordinal": fold["fold_ordinal"],
                    "heldout_block": fold["heldout_block"],
                    **row,
                })
    return rows


def _phase_grid_from_evaluations_v1(
    records: Sequence[Mapping[str, object]], *, phase: str,
    expected_keys: Sequence[tuple[str, str]] | None = None,
) -> dict[str, object]:
    rows = _phase_book_rows_v1(records)
    if not rows:
        _fail("phase evaluation publications contain no exact-80 book rows")
    if phase == BROAD_SCREEN_PHASE:
        ordered_keys = [
            (view_id, strategy_id)
            for view_id in [
                "U",
                *(isolated_view_id_v1(index) for index in range(len(PROFILE_IDENTITIES))),
            ]
            for _, strategy_id, _ in STRATEGY_IDENTITIES
        ]
        replicate_count = BROAD_SCREEN_REPLICATES
    elif phase == CONFIRMATION_PHASE:
        if expected_keys is None:
            _fail("confirmation phase grid requires exact nominated keys")
        ordered_keys = list(expected_keys)
        replicate_count = SUBSAMPLE_REPLICATES
    else:
        _fail("phase grid derivation phase differs")
    by_key: dict[tuple[str, str], list[Mapping[str, object]]] = {
        key: [] for key in ordered_keys
    }
    for row in rows:
        key = (str(row["view_id"]), str(row["strategy_id"]))
        if key not in by_key:
            _fail("evaluation publication contains a non-phase cell")
        by_key[key].append(row)
    expected_per_key = PANEL_SLATE_COUNT * FOLDS_PER_SLATE * replicate_count
    if any(len(values) != expected_per_key for values in by_key.values()):
        _fail("phase evaluation cell coverage is incomplete")
    grid_rows = []
    for view_id, strategy_id in ordered_keys:
        values = by_key[(view_id, strategy_id)]
        view_kind, profile_ordinal, profile_id = _view_profile_fields_v1(view_id)
        del view_kind
        strategy_ordinal = next(
            ordinal
            for ordinal, registered_id, _ in STRATEGY_IDENTITIES
            if registered_id == strategy_id
        )
        aggregate_fields: dict[str, int] = {}
        for stem in _AGGREGATE_METRIC_STEMS:
            numerators: list[int] = []
            denominators: set[int] = set()
            for row in values:
                scalar = row["aggregate_scalars"][stem]
                numerator = _integer(
                    scalar["numerator"], label=f"{phase} {stem} numerator",
                )
                denominator = _integer(
                    scalar["denominator"],
                    label=f"{phase} {stem} denominator",
                    minimum=1,
                )
                numerators.append(numerator)
                denominators.add(denominator)
            if len(denominators) != 1:
                _fail(f"{phase} evaluation {stem} denominator differs")
            # Preserve one canonical denominator across every phase-grid row.
            # Reducing each rational mean independently would make equivalent
            # cells acquire different denominators and violate the exact-grid
            # authority even though their values are well-defined.
            source_denominator = next(iter(denominators))
            aggregate_fields[f"{stem}_numerator"] = sum(numerators)
            aggregate_fields[f"{stem}_denominator"] = (
                source_denominator * len(numerators)
            )
        grid_rows.append({
            "view_id": view_id,
            "profile_id": profile_id,
            "profile_ordinal": profile_ordinal,
            "strategy_id": strategy_id,
            "strategy_ordinal": strategy_ordinal,
            "prefix_size": ENTRY_BUDGET,
            **aggregate_fields,
            "complete_cell_count": PANEL_SLATE_COUNT * FOLDS_PER_SLATE,
            "subsample_replicate_count": replicate_count,
        })
    return _build_phase_grid_fixture_v1(phase=phase, rows=grid_rows)


def _layers_from_evaluations_v1(
    records: Sequence[Mapping[str, object]], *, phase: str,
) -> tuple[dict[str, object], dict[str, object], dict[str, object]]:
    selection_role = (
        "broad-selection-receipt"
        if phase == BROAD_SCREEN_PHASE
        else "confirmation-selection-receipt"
    )
    evaluation_role = (
        "broad-evaluation-result"
        if phase == BROAD_SCREEN_PHASE
        else "confirmation-evaluation-result"
    )
    projection = build_layer_binding_v1(
        role="projection",
        entries=[
            {
                "source_ordinal": record["source_ordinal"],
                "slate_id": record["slate_id"],
                "identity": record["body"]["projection_bundle_identity"],
            }
            for record in records
        ],
    )
    selection = build_layer_binding_v1(
        role=selection_role,
        entries=[
            {
                "source_ordinal": record["source_ordinal"],
                "slate_id": record["slate_id"],
                "identity": record["body"]["selection_receipt_identity"],
            }
            for record in records
        ],
    )
    evaluation = build_layer_binding_v1(
        role=evaluation_role,
        entries=[
            {
                "source_ordinal": record["source_ordinal"],
                "slate_id": record["slate_id"],
                "identity": record["identity"],
            }
            for record in records
        ],
    )
    return projection, selection, evaluation


def _build_broad_phase_authority_from_records_v1(
    *, retained_design: Mapping[str, object],
    retained_design_identity: Mapping[str, object], run_identity: object,
    records: Sequence[Mapping[str, object]],
) -> dict[str, object]:
    if len(records) != PANEL_SLATE_COUNT:
        _fail("broad compact evaluation record count differs")
    run_authority = _launch_authority_from_bootstrap_v1(
        retained_design["bootstrap_manifest"], run_identity
    )
    topology_identity = records[0]["body"]["topology_identity"]
    if any(record["body"]["topology_identity"] != topology_identity for record in records):
        _fail("broad evaluation topology identities differ")
    _bind_canonical_body_to_identity_v1(
        retained_design["topology"], topology_identity, label="broad topology"
    )
    projection, selection, evaluation = _layers_from_evaluations_v1(
        records, phase=BROAD_SCREEN_PHASE
    )
    summaries = _evaluation_publication_summaries_v1(records)
    if any(summary["launch_intent_identity"] != run_authority for summary in summaries):
        _fail("broad evaluation launch authorities differ from run authorization")
    execution_lattice = _phase_execution_lattice_v1(
        summaries, phase=BROAD_SCREEN_PHASE
    )
    grid = _phase_grid_from_evaluations_v1(records, phase=BROAD_SCREEN_PHASE)
    body = {
        "schema_version": BROAD_PHASE_AUTHORITY_SCHEMA,
        "contract_id": CONTRACT_ID,
        "design_publication_identity": dict(retained_design_identity),
        "design_sha256": retained_design["design_sha256"],
        "contract_report_sha256": retained_design["report_identity"]["sha256"],
        "code_sha256": retained_design["code_identity"]["sha256"],
        "topology": retained_design["topology"],
        "topology_identity": topology_identity,
        "run_identity": run_authority,
        "evaluation_publication_count": len(summaries),
        "evaluation_publication_summaries": summaries,
        "evaluation_publication_summaries_sha256": canonical_sha256_v1(summaries),
        "phase_execution_authority": execution_lattice,
        "phase_execution_authority_sha256": canonical_sha256_v1(
            execution_lattice
        ),
        "projection_layer": projection,
        "broad_selection_layer": selection,
        "broad_evaluation_layer": evaluation,
        "broad_phase_grid": grid,
        "grid_derivation_law": "exact-54-publication-source-ordinal-reduction",
        "caller_phase_grid_accepted": False,
        "policy": _policy_block(),
    }
    return _with_hash(body, field="broad_phase_authority_sha256")


def build_broad_phase_authority_v1(
    *, design: object, design_publication_identity: object,
    run_identity: object, evaluation_publications: object,
) -> dict[str, object]:
    """Exact-reopen 54 broad publications and derive the only broad grid."""
    retained_design = validate_design_authority_v1(
        design, publication_identity=design_publication_identity
    )
    retained_design_identity = _safe_object_identity(
        design_publication_identity, label="broad design publication"
    )
    records = [
        _compact_evaluation_record_v1(record)
        for record in _evaluation_publications_v1(
            evaluation_publications,
            phase=BROAD_SCREEN_PHASE,
            design=retained_design,
            design_publication_identity=retained_design_identity,
        )
    ]
    return _build_broad_phase_authority_from_records_v1(
        retained_design=retained_design,
        retained_design_identity=retained_design_identity,
        run_identity=run_identity,
        records=records,
    )


def validate_broad_phase_authority_v1(value: object) -> dict[str, object]:
    item = _mapping(value, label="broad phase authority")
    expected_fields = {
        "schema_version", "contract_id", "design_publication_identity",
        "design_sha256", "contract_report_sha256", "code_sha256", "topology",
        "topology_identity", "run_identity",
        "evaluation_publication_count", "evaluation_publication_summaries",
        "evaluation_publication_summaries_sha256", "projection_layer",
        "phase_execution_authority", "phase_execution_authority_sha256",
        "broad_selection_layer", "broad_evaluation_layer", "broad_phase_grid",
        "grid_derivation_law", "caller_phase_grid_accepted", "policy",
        "broad_phase_authority_sha256",
    }
    if set(item) != expected_fields:
        _fail("broad phase authority fields differ")
    _self_hash(
        item, field="broad_phase_authority_sha256", label="broad phase authority"
    )
    validate_policy_block_v1(item["policy"], label="broad phase authority")
    topology = validate_result_topology_v1(item["topology"])
    topology_identity = _bind_canonical_body_to_identity_v1(
        topology, item["topology_identity"], label="broad topology"
    )
    summaries = [
        _mapping(row, label=f"broad evaluation summary[{index}]")
        for index, row in enumerate(
            _sequence(
                item["evaluation_publication_summaries"],
                label="broad evaluation summaries",
            )
        )
    ]
    if (
        item["schema_version"] != BROAD_PHASE_AUTHORITY_SCHEMA
        or item["contract_id"] != CONTRACT_ID
        or item["evaluation_publication_count"] != PANEL_SLATE_COUNT
        or len(summaries) != PANEL_SLATE_COUNT
        or [row.get("source_ordinal") for row in summaries]
        != list(range(PANEL_SLATE_COUNT))
        or len({str(row.get("slate_id")) for row in summaries}) != PANEL_SLATE_COUNT
        or item["evaluation_publication_summaries_sha256"]
        != canonical_sha256_v1(summaries)
        or item["phase_execution_authority"]
        != _phase_execution_lattice_v1(summaries, phase=BROAD_SCREEN_PHASE)
        or item["phase_execution_authority_sha256"]
        != canonical_sha256_v1(item["phase_execution_authority"])
        or item["grid_derivation_law"]
        != "exact-54-publication-source-ordinal-reduction"
        or item["caller_phase_grid_accepted"] is not False
    ):
        _fail("broad phase authority summary/law differs")
    design_identity = _safe_object_identity(
        item["design_publication_identity"], label="broad design"
    )
    _sha256_hex(item["design_sha256"], label="broad design sha256")
    _sha256_hex(item["contract_report_sha256"], label="broad contract report")
    _sha256_hex(item["code_sha256"], label="broad code")
    _safe_object_identity(item["run_identity"], label="broad run")
    if any(
        summary["launch_intent_identity"] != item["run_identity"]
        for summary in summaries
    ):
        _fail("broad summary launch authority differs from run authorization")
    projection = validate_layer_binding_v1(item["projection_layer"], role="projection")
    selection = validate_layer_binding_v1(
        item["broad_selection_layer"], role="broad-selection-receipt"
    )
    evaluation = validate_layer_binding_v1(
        item["broad_evaluation_layer"], role="broad-evaluation-result"
    )
    grid = validate_phase_grid_v1(
        item["broad_phase_grid"], phase=BROAD_SCREEN_PHASE
    )
    slate_orders = [
        [entry["slate_id"] for entry in layer["entries"]]
        for layer in (projection, selection, evaluation)
    ]
    if slate_orders[1:] != slate_orders[:1] * 2:
        _fail("broad phase layer slate order differs")
    for source, summary in enumerate(summaries):
        if set(summary) != {
            "source_ordinal", "slate_id", "phase", "evaluation_identity",
            "evaluation_result_sha256", "selection_receipt_identity",
            "selection_receipt_sha256", "projection_bundle_identity",
            "projection_bundle_sha256", "bootstrap_manifest_identity",
            "bootstrap_manifest_sha256", "evaluator_process_budget_identity",
            "evaluator_process_budget_sha256", "launch_intent_identity",
            "runtime_observation_sha256", "logical_fold_selection_count",
            "selector_os_process_count",
            "child_execution_evidence_sha256s",
            "child_execution_evidence_set_sha256", "folds_sha256",
        }:
            _fail("broad evaluation summary fields differ")
        if (
            summary["phase"] != BROAD_SCREEN_PHASE
            or summary["slate_id"] != slate_orders[0][source]
            or summary["projection_bundle_identity"]
            != projection["entries"][source]["identity"]
            or summary["selection_receipt_identity"]
            != selection["entries"][source]["identity"]
            or summary["evaluation_identity"]
            != evaluation["entries"][source]["identity"]
            or str(summary["evaluation_identity"]["uri"])
            != _topology_uri_v1(
                topology, role="broad-evaluation-result", source_ordinal=source
            )
        ):
            _fail("broad evaluation summary/layer binding differs")
        for field in (
            "evaluation_result_sha256", "selection_receipt_sha256",
            "projection_bundle_sha256", "bootstrap_manifest_sha256",
            "evaluator_process_budget_sha256", "runtime_observation_sha256",
            "folds_sha256",
        ):
            _sha256_hex(summary[field], label=f"broad summary {field}")
    del topology_identity, design_identity, grid
    return item


def build_nomination_publication_v1(
    *, design: object, design_publication_identity: object,
    run_identity: object, broad_evaluation_publications: object,
) -> dict[str, object]:
    """Derive the sole ordinal-163 broad-authority/nomination publication."""
    broad = build_broad_phase_authority_v1(
        design=design,
        design_publication_identity=design_publication_identity,
        run_identity=run_identity,
        evaluation_publications=broad_evaluation_publications,
    )
    nomination = deterministic_nominees_from_broad_authority_v1(broad)
    body = {
        "schema_version": NOMINATION_PUBLICATION_SCHEMA,
        "contract_id": CONTRACT_ID,
        "design_publication_identity": _safe_object_identity(
            design_publication_identity, label="nomination design publication"
        ),
        "run_identity": _safe_object_identity(
            run_identity, label="nomination run"
        ),
        "broad_phase_authority": broad,
        "broad_phase_authority_sha256": broad[
            "broad_phase_authority_sha256"
        ],
        "nomination": nomination,
        "nomination_sha256": nomination["nomination_sha256"],
        "derivation_law": (
            "exact-54-broad-evaluations-to-broad-authority-and-nomination"
        ),
        "caller_broad_authority_or_nominees_accepted": False,
        "policy": _policy_block(),
    }
    return _with_hash(body, field="nomination_publication_sha256")


def validate_nomination_publication_v1(value: object) -> dict[str, object]:
    item = _mapping(value, label="nomination publication")
    expected_fields = {
        "schema_version", "contract_id", "design_publication_identity",
        "run_identity", "broad_phase_authority",
        "broad_phase_authority_sha256", "nomination", "nomination_sha256",
        "derivation_law", "caller_broad_authority_or_nominees_accepted",
        "policy", "nomination_publication_sha256",
    }
    if set(item) != expected_fields:
        _fail("nomination publication fields differ")
    _self_hash(
        item,
        field="nomination_publication_sha256",
        label="nomination publication",
    )
    validate_policy_block_v1(item["policy"], label="nomination publication")
    broad = validate_broad_phase_authority_v1(item["broad_phase_authority"])
    nomination = validate_nomination_v1(
        item["nomination"], broad_phase_authority=broad
    )
    if (
        item["schema_version"] != NOMINATION_PUBLICATION_SCHEMA
        or item["contract_id"] != CONTRACT_ID
        or item["design_publication_identity"]
        != broad["design_publication_identity"]
        or item["run_identity"] != broad["run_identity"]
        or item["broad_phase_authority_sha256"]
        != broad["broad_phase_authority_sha256"]
        or item["nomination_sha256"] != nomination["nomination_sha256"]
        or item["derivation_law"]
        != "exact-54-broad-evaluations-to-broad-authority-and-nomination"
        or item["caller_broad_authority_or_nominees_accepted"] is not False
    ):
        _fail("nomination publication authority/law differs")
    return item


def validate_nomination_publication_authority_v1(
    value: object, *, publication_identity: object,
) -> dict[str, object]:
    publication = validate_nomination_publication_v1(value)
    identity = _bind_canonical_body_to_identity_v1(
        publication, publication_identity, label="nomination publication"
    )
    if identity["uri"] != _topology_uri_v1(
        publication["broad_phase_authority"]["topology"], role="nomination"
    ):
        _fail("nomination publication URI differs from topology")
    return publication


def validate_nomination_publication_from_evaluations_authority_v1(
    value: object, *, publication_identity: object, design: object,
    design_publication_identity: object, run_identity: object,
    broad_evaluation_publications: object,
) -> dict[str, object]:
    expected = build_nomination_publication_v1(
        design=design,
        design_publication_identity=design_publication_identity,
        run_identity=run_identity,
        broad_evaluation_publications=broad_evaluation_publications,
    )
    retained = validate_nomination_publication_authority_v1(
        value, publication_identity=publication_identity
    )
    if canonical_json_bytes_v1(retained) != canonical_json_bytes_v1(expected):
        _fail("nomination publication differs from exact broad evaluations")
    return retained


def _book_scalar_micro_fraction_v1(
    row: Mapping[str, object], stem: str,
) -> Fraction:
    scalar = _mapping(row["aggregate_scalars"][stem], label=f"book scalar {stem}")
    value = _fraction(
        scalar["numerator"], scalar["denominator"],
        label=f"book scalar {stem}", allow_negative=False,
    )
    if stem in {
        "mean_heldout_p_max_gt_200",
        "mean_heldout_p_max_gt_220",
        "mean_heldout_p_max_gt_230",
    }:
        value *= MICRO_SCALE
    return value


def _fraction_median_v1(values: Sequence[Fraction]) -> Fraction:
    if not values:
        _fail("paired comparison median requires at least one value")
    ordered = sorted(values)
    midpoint = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[midpoint]
    return (ordered[midpoint - 1] + ordered[midpoint]) / 2


def _comparison_summary_v1(rows: Sequence[Mapping[str, object]]) -> dict[str, object]:
    deltas = [
        _fraction(
            row["delta_numerator_micro"], row["delta_denominator"],
            label="paired comparison delta", allow_negative=True,
        )
        for row in rows
    ]
    mean = sum(deltas, Fraction(0)) / len(deltas)
    median = _fraction_median_v1(deltas)
    block_means = []
    for block in WORLD_BLOCKS:
        values = [
            delta
            for row, delta in zip(rows, deltas, strict=True)
            if row["heldout_block"] == block
        ]
        if len(values) != PANEL_SLATE_COUNT:
            _fail("paired comparison block family is incomplete")
        block_means.append({
            "heldout_block": block,
            "mean_delta_micro": _fraction_json(sum(values, Fraction(0)) / len(values)),
        })
    by_season: dict[str, list[Fraction]] = {}
    for row, delta in zip(rows, deltas, strict=True):
        slate_id = str(row["slate_id"])
        season_id = slate_id.split("-w", 1)[0]
        by_season.setdefault(season_id, []).append(delta)
    season_means = [
        {
            "season_id": season_id,
            "cell_count": len(values),
            "mean_delta_micro": _fraction_json(
                sum(values, Fraction(0)) / len(values)
            ),
        }
        for season_id, values in sorted(by_season.items())
    ]
    return {
        "paired_cell_count": len(rows),
        "mean_delta_micro": _fraction_json(mean),
        "median_delta_micro": _fraction_json(median),
        "heldout_block_family_means": block_means,
        "season_means_diagnostic_only": season_means,
        "distinct_delta_count": len(set(deltas)),
        "nonzero_delta_count": sum(delta != 0 for delta in deltas),
        "missing_or_failed_cell_count": 0,
    }


def _comparison_ledgers_v1(
    *, records: Sequence[Mapping[str, object]],
    nominee_keys: Sequence[tuple[str, str]], contract_sha256: str,
    code_sha256: str, evaluation_layer: Mapping[str, object],
) -> list[dict[str, object]]:
    baseline_key = (PRIMARY_BASELINE_VIEW_ID, PRIMARY_BASELINE_STRATEGY_ID)
    if baseline_key not in nominee_keys:
        _fail("confirmation comparison lattice omits primary baseline")
    per_cluster: dict[
        tuple[int, int], dict[tuple[str, str], dict[int, Mapping[str, object]]]
    ] = {}
    for record in records:
        source = int(record["source_ordinal"])
        for fold in record["body"]["folds"]:
            fold_ordinal = int(fold["fold_ordinal"])
            by_key: dict[tuple[str, str], dict[int, Mapping[str, object]]] = {
                key: {} for key in nominee_keys
            }
            for row in fold["book_metric_rows"]:
                if row["prefix_size"] != ENTRY_BUDGET:
                    continue
                key = (str(row["view_id"]), str(row["strategy_id"]))
                if key not in by_key:
                    _fail("confirmation evaluation contains an unnominated key")
                replicate = int(row["replicate"])
                if replicate in by_key[key]:
                    _fail("confirmation evaluation repeats a replicate/key")
                by_key[key][replicate] = row
            if any(set(values) != set(range(SUBSAMPLE_REPLICATES)) for values in by_key.values()):
                _fail("confirmation comparison replicate lattice is incomplete")
            per_cluster[(source, fold_ordinal)] = by_key
    if len(per_cluster) != PANEL_SLATE_COUNT * FOLDS_PER_SLATE:
        _fail("confirmation comparison cluster lattice is incomplete")
    slate_identities = [
        {
            "slate_id": entry["slate_id"],
            "sha256": entry["identity"]["sha256"],
        }
        for entry in evaluation_layer["entries"]
    ]
    comparisons = []
    comparison_ordinal = 0
    for challenger_key in nominee_keys:
        if challenger_key == baseline_key:
            continue
        for stem in _AGGREGATE_METRIC_STEMS:
            ledger_rows = []
            for record in records:
                source = int(record["source_ordinal"])
                slate_id = str(record["slate_id"])
                for fold_ordinal, block in enumerate(WORLD_BLOCKS):
                    cluster = per_cluster[(source, fold_ordinal)]
                    challenger_values = [
                        _book_scalar_micro_fraction_v1(
                            cluster[challenger_key][replicate], stem
                        )
                        for replicate in range(SUBSAMPLE_REPLICATES)
                    ]
                    baseline_values = [
                        _book_scalar_micro_fraction_v1(
                            cluster[baseline_key][replicate], stem
                        )
                        for replicate in range(SUBSAMPLE_REPLICATES)
                    ]
                    challenger_mean = sum(challenger_values, Fraction(0)) / SUBSAMPLE_REPLICATES
                    baseline_mean = sum(baseline_values, Fraction(0)) / SUBSAMPLE_REPLICATES
                    delta = challenger_mean - baseline_mean
                    ledger_rows.append({
                        "source_ordinal": source,
                        "slate_id": slate_id,
                        "fold_ordinal": fold_ordinal,
                        "heldout_block": block,
                        "challenger_numerator_micro": challenger_mean.numerator,
                        "challenger_denominator": challenger_mean.denominator,
                        "baseline_numerator_micro": baseline_mean.numerator,
                        "baseline_denominator": baseline_mean.denominator,
                        "delta_numerator_micro": delta.numerator,
                        "delta_denominator": delta.denominator,
                    })
            comparison_key = {
                "challenger_view_id": challenger_key[0],
                "challenger_strategy_id": challenger_key[1],
                "baseline_view_id": baseline_key[0],
                "baseline_strategy_id": baseline_key[1],
                "prefix_size": ENTRY_BUDGET,
                "metric_id": stem,
            }
            ledger = _with_hash({
                "schema_version": COMPARISON_LEDGER_SCHEMA,
                "comparison_ordinal": comparison_ordinal,
                "comparison_key": comparison_key,
                "row_count": len(ledger_rows),
                "rows": ledger_rows,
                "rows_sha256": canonical_sha256_v1(ledger_rows),
                "source_order_law": "source-ordinal-0-through-53-then-R0-through-R4",
                "replicate_reduction_law": "mean-32-within-slate-fold-before-delta",
                "summary": _comparison_summary_v1(ledger_rows),
                "policy": _policy_block(),
            }, field="comparison_ledger_sha256")
            bootstrap_rows = [
                {
                    "slate_id": row["slate_id"],
                    "heldout_block": row["heldout_block"],
                    "delta_numerator_micro": row["delta_numerator_micro"],
                    "delta_denominator": row["delta_denominator"],
                }
                for row in ledger_rows
            ]
            bootstrap = _deterministic_slate_cluster_bootstrap_fixture_v1(
                bootstrap_rows,
                contract_sha256=contract_sha256,
                code_sha256=code_sha256,
                slate_identities_value=slate_identities,
            )
            comparisons.append({
                "comparison_ordinal": comparison_ordinal,
                "comparison_key": comparison_key,
                "ledger": ledger,
                "comparison_ledger_sha256": ledger["comparison_ledger_sha256"],
                "bootstrap": bootstrap,
                "bootstrap_sha256": bootstrap["bootstrap_sha256"],
            })
            comparison_ordinal += 1
    return comparisons


def _build_aggregate_mechanics_from_records_v1(
    *, retained_design: Mapping[str, object],
    retained_design_identity: Mapping[str, object], run_identity: object,
    nomination_publication: object, nomination_publication_identity: object,
    broad_records: Sequence[Mapping[str, object]],
    confirmation_records: Sequence[Mapping[str, object]],
) -> dict[str, object]:
    run = _launch_authority_from_bootstrap_v1(
        retained_design["bootstrap_manifest"], run_identity
    )
    rebuilt_broad = _build_broad_phase_authority_from_records_v1(
        retained_design=retained_design,
        retained_design_identity=retained_design_identity,
        run_identity=run,
        records=broad_records,
    )
    retained_publication = validate_nomination_publication_authority_v1(
        nomination_publication,
        publication_identity=nomination_publication_identity,
    )
    retained_broad = retained_publication["broad_phase_authority"]
    if canonical_json_bytes_v1(retained_broad) != canonical_json_bytes_v1(rebuilt_broad):
        _fail("aggregate broad authority differs from exact reopened publications")
    retained_nomination = retained_publication["nomination"]
    retained_nomination_identity = _safe_object_identity(
        nomination_publication_identity, label="aggregate nomination publication"
    )
    if retained_nomination_identity["uri"] != _topology_uri_v1(
        retained_design["topology"], role="nomination"
    ):
        _fail("aggregate nomination URI differs from design topology")
    if len(broad_records) != PANEL_SLATE_COUNT or len(confirmation_records) != PANEL_SLATE_COUNT:
        _fail("aggregate compact phase record count differs")
    if [record["slate_id"] for record in confirmation_records] != [
        record["slate_id"] for record in broad_records
    ]:
        _fail("aggregate broad/confirmation slate order differs")
    if [record["body"]["projection_bundle_identity"] for record in confirmation_records] != [
        record["body"]["projection_bundle_identity"] for record in broad_records
    ]:
        _fail("aggregate broad/confirmation projection authorities differ")
    broad_projection, broad_selection, broad_evaluation = _layers_from_evaluations_v1(
        broad_records, phase=BROAD_SCREEN_PHASE
    )
    confirmation_projection, confirmation_selection, confirmation_evaluation = (
        _layers_from_evaluations_v1(
            confirmation_records, phase=CONFIRMATION_PHASE
        )
    )
    if confirmation_projection != broad_projection:
        _fail("aggregate confirmation projection layer differs")
    nominee_keys = _nominee_keys_v1(retained_nomination)
    confirmation_grid = _phase_grid_from_evaluations_v1(
        confirmation_records,
        phase=CONFIRMATION_PHASE,
        expected_keys=nominee_keys,
    )
    comparisons = _comparison_ledgers_v1(
        records=confirmation_records,
        nominee_keys=nominee_keys,
        contract_sha256=str(retained_design["report_identity"]["sha256"]),
        code_sha256=str(retained_design["code_identity"]["sha256"]),
        evaluation_layer=confirmation_evaluation,
    )
    broad_summaries = _evaluation_publication_summaries_v1(broad_records)
    confirmation_summaries = _evaluation_publication_summaries_v1(
        confirmation_records
    )
    if any(
        summary["launch_intent_identity"] != run
        for summary in (*broad_summaries, *confirmation_summaries)
    ):
        _fail("aggregate evaluation launch authorities differ from run authorization")
    confirmation_execution_lattice = _phase_execution_lattice_v1(
        confirmation_summaries, phase=CONFIRMATION_PHASE
    )
    body = {
        "schema_version": AGGREGATE_MECHANICS_SCHEMA,
        "contract_id": CONTRACT_ID,
        "design_publication_identity": dict(retained_design_identity),
        "design_sha256": retained_design["design_sha256"],
        "contract_report_sha256": retained_design["report_identity"]["sha256"],
        "code_sha256": retained_design["code_identity"]["sha256"],
        "topology": retained_design["topology"],
        "topology_identity": retained_broad["topology_identity"],
        "run_identity": run,
        "nomination_publication": retained_publication,
        "nomination_publication_identity": retained_nomination_identity,
        "nomination_publication_sha256": retained_publication[
            "nomination_publication_sha256"
        ],
        "broad_phase_authority": retained_broad,
        "broad_phase_authority_sha256": retained_broad[
            "broad_phase_authority_sha256"
        ],
        "nomination": retained_nomination,
        "nomination_identity": retained_nomination_identity,
        "nomination_sha256": retained_nomination["nomination_sha256"],
        "broad_evaluation_publication_summaries": broad_summaries,
        "broad_evaluation_publication_summaries_sha256": canonical_sha256_v1(
            broad_summaries
        ),
        "confirmation_evaluation_publication_summaries": confirmation_summaries,
        "confirmation_evaluation_publication_summaries_sha256": canonical_sha256_v1(
            confirmation_summaries
        ),
        "broad_phase_execution_authority": retained_broad[
            "phase_execution_authority"
        ],
        "broad_phase_execution_authority_sha256": retained_broad[
            "phase_execution_authority_sha256"
        ],
        "confirmation_phase_execution_authority": (
            confirmation_execution_lattice
        ),
        "confirmation_phase_execution_authority_sha256": canonical_sha256_v1(
            confirmation_execution_lattice
        ),
        "projection_layer": broad_projection,
        "broad_selection_layer": broad_selection,
        "broad_evaluation_layer": broad_evaluation,
        "confirmation_selection_layer": confirmation_selection,
        "confirmation_evaluation_layer": confirmation_evaluation,
        "broad_phase_grid": retained_broad["broad_phase_grid"],
        "confirmation_phase_grid": confirmation_grid,
        "paired_comparison_count": len(comparisons),
        "paired_comparisons": comparisons,
        "paired_comparisons_sha256": canonical_sha256_v1(comparisons),
        "aggregate_derivation_law": (
            "exact-reopen-54-plus-54-evaluations-derive-grids-ledgers-bootstraps"
        ),
        "caller_phase_grid_or_bootstrap_rows_accepted": False,
        "output_object_count": OUTPUT_OBJECT_COUNT,
        "all_block_final_fit_count": 0,
        "policy": _policy_block(),
    }
    return _with_hash(body, field="aggregate_mechanics_sha256")


def build_aggregate_mechanics_v1(
    *, design: object, design_publication_identity: object,
    run_identity: object, nomination_publication: object,
    nomination_publication_identity: object,
    broad_evaluation_publications: object,
    confirmation_evaluation_publications: object,
) -> dict[str, object]:
    """Reopen both 54-body phases and derive grids, deltas, and bootstraps."""
    retained_design = validate_design_authority_v1(
        design, publication_identity=design_publication_identity
    )
    retained_design_identity = _safe_object_identity(
        design_publication_identity, label="aggregate design publication"
    )
    broad_records = [
        _compact_evaluation_record_v1(record)
        for record in _evaluation_publications_v1(
            broad_evaluation_publications,
            phase=BROAD_SCREEN_PHASE,
            design=retained_design,
            design_publication_identity=retained_design_identity,
        )
    ]
    confirmation_records = [
        _compact_evaluation_record_v1(record)
        for record in _evaluation_publications_v1(
            confirmation_evaluation_publications,
            phase=CONFIRMATION_PHASE,
            design=retained_design,
            design_publication_identity=retained_design_identity,
        )
    ]
    return _build_aggregate_mechanics_from_records_v1(
        retained_design=retained_design,
        retained_design_identity=retained_design_identity,
        run_identity=run_identity,
        nomination_publication=nomination_publication,
        nomination_publication_identity=nomination_publication_identity,
        broad_records=broad_records,
        confirmation_records=confirmation_records,
    )


def _validate_comparison_ledger_v1(
    value: object, *, expected_ordinal: int,
) -> dict[str, object]:
    ledger = _mapping(value, label="paired comparison ledger")
    if set(ledger) != {
        "schema_version", "comparison_ordinal", "comparison_key", "row_count",
        "rows", "rows_sha256", "source_order_law", "replicate_reduction_law",
        "summary", "policy", "comparison_ledger_sha256",
    }:
        _fail("paired comparison ledger fields differ")
    _self_hash(
        ledger, field="comparison_ledger_sha256", label="paired comparison ledger"
    )
    validate_policy_block_v1(ledger["policy"], label="paired comparison ledger")
    rows = [
        _mapping(row, label=f"paired comparison row[{index}]")
        for index, row in enumerate(
            _sequence(ledger["rows"], label="paired comparison rows")
        )
    ]
    expected_pairs = [
        (source, block_ordinal)
        for source in range(PANEL_SLATE_COUNT)
        for block_ordinal in range(FOLDS_PER_SLATE)
    ]
    observed_pairs = [
        (row.get("source_ordinal"), row.get("fold_ordinal")) for row in rows
    ]
    for row, (source, fold) in zip(rows, expected_pairs, strict=True):
        if set(row) != {
            "source_ordinal", "slate_id", "fold_ordinal", "heldout_block",
            "challenger_numerator_micro", "challenger_denominator",
            "baseline_numerator_micro", "baseline_denominator",
            "delta_numerator_micro", "delta_denominator",
        }:
            _fail("paired comparison row fields differ")
        challenger = _fraction(
            row["challenger_numerator_micro"], row["challenger_denominator"],
            label="paired challenger", allow_negative=False,
        )
        baseline = _fraction(
            row["baseline_numerator_micro"], row["baseline_denominator"],
            label="paired baseline", allow_negative=False,
        )
        delta = _fraction(
            row["delta_numerator_micro"], row["delta_denominator"],
            label="paired delta", allow_negative=True,
        )
        if (
            row["heldout_block"] != WORLD_BLOCKS[fold]
            or challenger - baseline != delta
        ):
            _fail("paired comparison row delta/block differs")
    if (
        ledger["schema_version"] != COMPARISON_LEDGER_SCHEMA
        or ledger["comparison_ordinal"] != expected_ordinal
        or ledger["row_count"] != PANEL_SLATE_COUNT * FOLDS_PER_SLATE
        or len(rows) != ledger["row_count"]
        or observed_pairs != expected_pairs
        or ledger["rows_sha256"] != canonical_sha256_v1(rows)
        or ledger["source_order_law"]
        != "source-ordinal-0-through-53-then-R0-through-R4"
        or ledger["replicate_reduction_law"]
        != "mean-32-within-slate-fold-before-delta"
        or ledger["summary"] != _comparison_summary_v1(rows)
    ):
        _fail("paired comparison ledger order/hash/summary differs")
    return ledger


def validate_aggregate_mechanics_v1(value: object) -> dict[str, object]:
    item = _mapping(value, label="aggregate mechanics")
    expected_fields = {
        "schema_version", "contract_id", "design_publication_identity",
        "design_sha256", "contract_report_sha256", "code_sha256", "topology",
        "topology_identity", "run_identity",
        "nomination_publication", "nomination_publication_identity",
        "nomination_publication_sha256",
        "broad_phase_authority", "broad_phase_authority_sha256", "nomination",
        "nomination_identity", "nomination_sha256",
        "broad_evaluation_publication_summaries",
        "broad_evaluation_publication_summaries_sha256",
        "confirmation_evaluation_publication_summaries",
        "confirmation_evaluation_publication_summaries_sha256",
        "broad_phase_execution_authority",
        "broad_phase_execution_authority_sha256",
        "confirmation_phase_execution_authority",
        "confirmation_phase_execution_authority_sha256",
        "projection_layer", "broad_selection_layer", "broad_evaluation_layer",
        "confirmation_selection_layer", "confirmation_evaluation_layer",
        "broad_phase_grid", "confirmation_phase_grid",
        "paired_comparison_count", "paired_comparisons",
        "paired_comparisons_sha256", "aggregate_derivation_law",
        "caller_phase_grid_or_bootstrap_rows_accepted", "output_object_count",
        "all_block_final_fit_count", "policy", "aggregate_mechanics_sha256",
    }
    if set(item) != expected_fields:
        _fail("aggregate mechanics fields differ")
    _self_hash(
        item, field="aggregate_mechanics_sha256", label="aggregate mechanics"
    )
    validate_policy_block_v1(item["policy"], label="aggregate mechanics")
    nomination_publication = validate_nomination_publication_authority_v1(
        item["nomination_publication"],
        publication_identity=item["nomination_publication_identity"],
    )
    broad = nomination_publication["broad_phase_authority"]
    nomination = nomination_publication["nomination"]
    topology = validate_result_topology_v1(item["topology"])
    _bind_canonical_body_to_identity_v1(
        topology, item["topology_identity"], label="aggregate topology"
    )
    if (
        item["schema_version"] != AGGREGATE_MECHANICS_SCHEMA
        or item["contract_id"] != CONTRACT_ID
        or item["broad_phase_authority_sha256"]
        != broad["broad_phase_authority_sha256"]
        or item["broad_phase_authority"] != broad
        or item["nomination"] != nomination
        or item["nomination_identity"]
        != item["nomination_publication_identity"]
        or item["nomination_publication_sha256"]
        != nomination_publication["nomination_publication_sha256"]
        or item["nomination_sha256"] != nomination["nomination_sha256"]
        or item["broad_phase_grid"] != broad["broad_phase_grid"]
        or item["broad_phase_execution_authority"]
        != broad["phase_execution_authority"]
        or item["broad_phase_execution_authority_sha256"]
        != broad["phase_execution_authority_sha256"]
        or item["contract_report_sha256"] != broad["contract_report_sha256"]
        or item["code_sha256"] != broad["code_sha256"]
        or item["aggregate_derivation_law"]
        != "exact-reopen-54-plus-54-evaluations-derive-grids-ledgers-bootstraps"
        or item["caller_phase_grid_or_bootstrap_rows_accepted"] is not False
        or item["output_object_count"] != OUTPUT_OBJECT_COUNT
        or item["all_block_final_fit_count"] != 0
    ):
        _fail("aggregate mechanics authority/law differs")
    _safe_object_identity(item["design_publication_identity"], label="aggregate design")
    _safe_object_identity(item["run_identity"], label="aggregate run")
    _sha256_hex(item["contract_report_sha256"], label="aggregate contract report")
    _sha256_hex(item["code_sha256"], label="aggregate code")
    _safe_object_identity(
        item["nomination_identity"], label="aggregate nomination publication"
    )
    layers = {
        "projection_layer": validate_layer_binding_v1(
            item["projection_layer"], role="projection"
        ),
        "broad_selection_layer": validate_layer_binding_v1(
            item["broad_selection_layer"], role="broad-selection-receipt"
        ),
        "broad_evaluation_layer": validate_layer_binding_v1(
            item["broad_evaluation_layer"], role="broad-evaluation-result"
        ),
        "confirmation_selection_layer": validate_layer_binding_v1(
            item["confirmation_selection_layer"],
            role="confirmation-selection-receipt",
        ),
        "confirmation_evaluation_layer": validate_layer_binding_v1(
            item["confirmation_evaluation_layer"],
            role="confirmation-evaluation-result",
        ),
    }
    slate_orders = [
        [entry["slate_id"] for entry in layer["entries"]]
        for layer in layers.values()
    ]
    if any(order != slate_orders[0] for order in slate_orders[1:]):
        _fail("aggregate layer slate order differs")
    broad_summaries = list(_sequence(
        item["broad_evaluation_publication_summaries"],
        label="aggregate broad summaries",
    ))
    confirmation_summaries = list(_sequence(
        item["confirmation_evaluation_publication_summaries"],
        label="aggregate confirmation summaries",
    ))
    if (
        broad_summaries != broad["evaluation_publication_summaries"]
        or item["broad_evaluation_publication_summaries_sha256"]
        != canonical_sha256_v1(broad_summaries)
        or len(confirmation_summaries) != PANEL_SLATE_COUNT
        or [row.get("source_ordinal") for row in confirmation_summaries]
        != list(range(PANEL_SLATE_COUNT))
        or item["confirmation_evaluation_publication_summaries_sha256"]
        != canonical_sha256_v1(confirmation_summaries)
        or item["confirmation_phase_execution_authority"]
        != _phase_execution_lattice_v1(
            confirmation_summaries, phase=CONFIRMATION_PHASE
        )
        or item["confirmation_phase_execution_authority_sha256"]
        != canonical_sha256_v1(
            item["confirmation_phase_execution_authority"]
        )
    ):
        _fail("aggregate evaluation publication summaries differ")
    confirmation_grid = validate_phase_grid_v1(
        item["confirmation_phase_grid"], phase=CONFIRMATION_PHASE
    )
    if [_cell_key(row) for row in confirmation_grid["rows"]] != _nominee_keys_v1(
        nomination
    ):
        _fail("aggregate confirmation grid differs from nomination order")
    comparisons = [
        _mapping(row, label=f"paired comparison[{index}]")
        for index, row in enumerate(
            _sequence(item["paired_comparisons"], label="paired comparisons")
        )
    ]
    expected_comparison_count = (len(_nominee_keys_v1(nomination)) - 1) * len(
        _AGGREGATE_METRIC_STEMS
    )
    expected_comparison_keys = [
        {
            "challenger_view_id": challenger[0],
            "challenger_strategy_id": challenger[1],
            "baseline_view_id": PRIMARY_BASELINE_VIEW_ID,
            "baseline_strategy_id": PRIMARY_BASELINE_STRATEGY_ID,
            "prefix_size": ENTRY_BUDGET,
            "metric_id": stem,
        }
        for challenger in _nominee_keys_v1(nomination)
        if challenger
        != (PRIMARY_BASELINE_VIEW_ID, PRIMARY_BASELINE_STRATEGY_ID)
        for stem in _AGGREGATE_METRIC_STEMS
    ]
    slate_identities = [
        {
            "slate_id": entry["slate_id"],
            "sha256": entry["identity"]["sha256"],
        }
        for entry in layers["confirmation_evaluation_layer"]["entries"]
    ]
    for index, comparison in enumerate(comparisons):
        if set(comparison) != {
            "comparison_ordinal", "comparison_key", "ledger",
            "comparison_ledger_sha256", "bootstrap", "bootstrap_sha256",
        } or (
            comparison["comparison_ordinal"] != index
            or comparison["comparison_key"] != expected_comparison_keys[index]
        ):
            _fail("paired comparison fields/order differs")
        ledger = _validate_comparison_ledger_v1(
            comparison["ledger"], expected_ordinal=index
        )
        if (
            comparison["comparison_key"] != ledger["comparison_key"]
            or comparison["comparison_ledger_sha256"]
            != ledger["comparison_ledger_sha256"]
        ):
            _fail("paired comparison key/ledger binding differs")
        bootstrap_rows = [
            {
                "slate_id": row["slate_id"],
                "heldout_block": row["heldout_block"],
                "delta_numerator_micro": row["delta_numerator_micro"],
                "delta_denominator": row["delta_denominator"],
            }
            for row in ledger["rows"]
        ]
        expected_bootstrap = _deterministic_slate_cluster_bootstrap_fixture_v1(
            bootstrap_rows,
            contract_sha256=str(item["contract_report_sha256"]),
            code_sha256=str(item["code_sha256"]),
            slate_identities_value=slate_identities,
        )
        bootstrap = _mapping(comparison["bootstrap"], label="paired bootstrap")
        if (
            canonical_json_bytes_v1(bootstrap)
            != canonical_json_bytes_v1(expected_bootstrap)
            or comparison["bootstrap_sha256"] != bootstrap["bootstrap_sha256"]
        ):
            _fail("paired bootstrap differs from derived comparison ledger")
    if (
        item["paired_comparison_count"] != expected_comparison_count
        or len(comparisons) != expected_comparison_count
        or item["paired_comparisons_sha256"] != canonical_sha256_v1(comparisons)
    ):
        _fail("paired comparison count/hash differs")
    return item


def validate_aggregate_mechanics_authority_v1(
    value: object, *, publication_identity: object,
) -> dict[str, object]:
    aggregate = validate_aggregate_mechanics_v1(value)
    identity = _bind_canonical_body_to_identity_v1(
        aggregate, publication_identity, label="aggregate mechanics"
    )
    if identity["uri"] != _topology_uri_v1(
        aggregate["topology"], role="aggregate"
    ):
        _fail("aggregate mechanics URI differs from result topology")
    return aggregate


def _root_predecessor_authorities_v1(
    *, design: object, design_publication_identity: object,
    predecessor_bodies: object, predecessor_identities: object,
) -> tuple[dict[str, object], list[dict[str, object]], list[dict[str, object]]]:
    retained_design = validate_design_authority_v1(
        design, publication_identity=design_publication_identity
    )
    topology = retained_design["topology"]
    expected_rows = list(topology["objects"][:-1])
    bodies = [
        _mapping(body, label=f"root predecessor body[{index}]")
        for index, body in enumerate(
            _sequence(predecessor_bodies, label="root predecessor bodies")
        )
    ]
    identities = list(
        _sequence(predecessor_identities, label="root predecessor identities")
    )
    if len(bodies) != OUTPUT_OBJECT_COUNT - 1 or len(identities) != len(bodies):
        _fail("terminal root requires exactly 274 predecessors")
    normalized_identities = []
    for expected, body, identity_value in zip(
        expected_rows, bodies, identities, strict=True
    ):
        identity = _bind_canonical_body_to_identity_v1(
            body, identity_value, label="root predecessor"
        )
        if identity["uri"] != expected["uri"]:
            _fail("terminal root predecessor URI/order differs")
        normalized_identities.append(identity)
    if (
        bodies[0] != retained_design
        or normalized_identities[0]
        != _safe_object_identity(
            design_publication_identity, label="design publication"
        )
    ):
        _fail("terminal root first predecessor is not the exact design")
    return retained_design, bodies, normalized_identities


def _build_terminal_root_list_fixture_v1(
    *, design: object, design_publication_identity: object,
    predecessor_bodies: object, predecessor_identities: object,
) -> dict[str, object]:
    """Rebuild aggregate/finalist from exact ordinal leaves before root-last."""
    retained_design, bodies, identities = _root_predecessor_authorities_v1(
        design=design,
        design_publication_identity=design_publication_identity,
        predecessor_bodies=predecessor_bodies,
        predecessor_identities=predecessor_identities,
    )
    topology = retained_design["topology"]
    by_role: dict[str, list[tuple[dict[str, object], dict[str, object]]]] = {}
    for descriptor, body, identity in zip(
        topology["objects"][:-1], bodies, identities, strict=True
    ):
        by_role.setdefault(str(descriptor["role"]), []).append((body, identity))
    broad_evaluations = [
        {
            "source_ordinal": source,
            "body": body,
            "identity": identity,
        }
        for source, (body, identity) in enumerate(
            by_role["broad-evaluation-result"]
        )
    ]
    confirmation_evaluations = [
        {
            "source_ordinal": source,
            "body": body,
            "identity": identity,
        }
        for source, (body, identity) in enumerate(
            by_role["confirmation-evaluation-result"]
        )
    ]
    aggregate_body, aggregate_identity = by_role["aggregate"][0]
    aggregate = validate_aggregate_mechanics_authority_v1(
        aggregate_body, publication_identity=aggregate_identity
    )
    nomination_body, nomination_identity = by_role["nomination"][0]
    rebuilt = build_aggregate_mechanics_v1(
        design=retained_design,
        design_publication_identity=identities[0],
        run_identity=aggregate["run_identity"],
        broad_phase_authority=aggregate["broad_phase_authority"],
        nomination=nomination_body,
        nomination_identity=nomination_identity,
        broad_evaluation_publications=broad_evaluations,
        confirmation_evaluation_publications=confirmation_evaluations,
    )
    if canonical_json_bytes_v1(rebuilt) != canonical_json_bytes_v1(aggregate):
        _fail("terminal root aggregate differs from exact evaluation predecessors")
    projection_identities = [identity for _, identity in by_role["projection"]]
    broad_selection_identities = [
        identity for _, identity in by_role["broad-selection-receipt"]
    ]
    confirmation_selection_identities = [
        identity for _, identity in by_role["confirmation-selection-receipt"]
    ]
    for source, record in enumerate(broad_evaluations):
        body = record["body"]
        if (
            body["projection_bundle_identity"] != projection_identities[source]
            or body["selection_receipt_identity"]
            != broad_selection_identities[source]
        ):
            _fail("terminal root broad evaluation predecessor links differ")
    for source, record in enumerate(confirmation_evaluations):
        body = record["body"]
        if (
            body["projection_bundle_identity"] != projection_identities[source]
            or body["selection_receipt_identity"]
            != confirmation_selection_identities[source]
        ):
            _fail("terminal root confirmation evaluation predecessor links differ")
    finalist_body, finalist_identity = by_role["confirmed-finalists"][0]
    finalist = validate_finalist_publication_authority_v1(
        finalist_body,
        publication_identity=finalist_identity,
        aggregate=aggregate,
        aggregate_publication_identity=aggregate_identity,
    )
    rows = [
        {
            "ordinal": descriptor["ordinal"],
            "role": descriptor["role"],
            "identity": identity,
        }
        for descriptor, identity in zip(
            topology["objects"][:-1], identities, strict=True
        )
    ]
    body = {
        "schema_version": ROOT_SCHEMA,
        "contract_id": CONTRACT_ID,
        "design_publication_identity": identities[0],
        "topology_sha256": topology["topology_sha256"],
        "aggregate_publication_identity": aggregate_identity,
        "aggregate_mechanics_sha256": aggregate["aggregate_mechanics_sha256"],
        "finalist_publication_identity": finalist_identity,
        "finalist_publication_sha256": finalist["finalist_publication_sha256"],
        "predecessor_count": len(rows),
        "predecessors": rows,
        "predecessors_sha256": canonical_sha256_v1(rows),
        "terminal_reconstruction_law": (
            "exact-ordinal-leaves-rebuild-aggregate-and-finalist-before-root"
        ),
        "publication_order_law": "strict-ordinal-create-once-root-last",
        "policy": _policy_block(),
    }
    return _with_hash(body, field="root_sha256")


def _validate_terminal_root_list_fixture_authority_v1(
    value: object, *, publication_identity: object, design: object,
    design_publication_identity: object, predecessor_bodies: object,
    predecessor_identities: object,
) -> dict[str, object]:
    expected = _build_terminal_root_list_fixture_v1(
        design=design,
        design_publication_identity=design_publication_identity,
        predecessor_bodies=predecessor_bodies,
        predecessor_identities=predecessor_identities,
    )
    item = _mapping(value, label="terminal root")
    if canonical_json_bytes_v1(item) != canonical_json_bytes_v1(expected):
        _fail("terminal root differs from exact reconstructed authorities")
    identity = _bind_canonical_body_to_identity_v1(
        item, publication_identity, label="terminal root"
    )
    retained_design = validate_design_authority_v1(
        design, publication_identity=design_publication_identity
    )
    if identity["uri"] != _topology_uri_v1(
        retained_design["topology"], role="root"
    ):
        _fail("terminal root URI differs from topology")
    return expected


def build_terminal_root_from_stream_v1(
    *, design: object, design_publication_identity: object,
    predecessor_opener: Callable[
        [Mapping[str, object]], tuple[object, object]
    ],
    maximum_compact_evaluation_state_bytes: object,
    resource_checkpoint: Callable[[str], object],
) -> dict[str, object]:
    """Open 274 predecessors once, retaining only identities and reductions."""
    if not callable(predecessor_opener):
        _fail("terminal predecessor opener must be callable")
    compact_state_limit = _integer(
        maximum_compact_evaluation_state_bytes,
        label="terminal maximum compact evaluation state bytes",
        minimum=2,
        maximum=MAX_IDENTITY_BYTES,
    )
    if not callable(resource_checkpoint):
        _fail("terminal resource checkpoint must be callable")
    retained_design = validate_design_authority_v1(
        design, publication_identity=design_publication_identity
    )
    design_identity = _safe_object_identity(
        design_publication_identity, label="terminal design publication"
    )
    topology = retained_design["topology"]
    predecessor_rows: list[dict[str, object]] = []
    projection_identities: list[dict[str, object]] = []
    broad_selection_identities: list[dict[str, object]] = []
    confirmation_selection_identities: list[dict[str, object]] = []
    broad_records: list[dict[str, object]] = []
    confirmation_records: list[dict[str, object]] = []
    nomination_publication: dict[str, object] | None = None
    nomination_publication_identity: dict[str, object] | None = None
    aggregate: dict[str, object] | None = None
    aggregate_identity: dict[str, object] | None = None
    finalist: dict[str, object] | None = None
    finalist_identity: dict[str, object] | None = None
    compact_state_bytes = 2  # Canonical JSON array brackets.
    for descriptor in topology["objects"][:-1]:
        expected = _mapping(descriptor, label="terminal topology descriptor")
        opened = predecessor_opener(dict(expected))
        if (
            isinstance(opened, (str, bytes))
            or not isinstance(opened, Sequence)
            or len(opened) != 2
        ):
            _fail("terminal predecessor opener must return (body, identity)")
        body = _mapping(opened[0], label="streamed predecessor body")
        identity = _bind_canonical_body_to_identity_v1(
            body, opened[1], label="streamed predecessor"
        )
        del opened
        if identity["uri"] != expected["uri"]:
            _fail("terminal streamed predecessor URI/order differs")
        ordinal = int(expected["ordinal"])
        role = str(expected["role"])
        predecessor_rows.append({
            "ordinal": ordinal, "role": role, "identity": identity,
        })
        if role == "design":
            if body != retained_design or identity != design_identity or ordinal != 0:
                _fail("terminal streamed design predecessor differs")
        elif role == "projection":
            projection_identities.append(identity)
        elif role in {
            "broad-selection-receipt", "confirmation-selection-receipt",
        }:
            _self_hash(
                body, field="selection_receipt_sha256",
                label="streamed selection receipt",
            )
            validate_policy_block_v1(
                body.get("policy"), label="streamed selection receipt"
            )
            target = (
                broad_selection_identities
                if role == "broad-selection-receipt"
                else confirmation_selection_identities
            )
            target.append(identity)
        elif role in {"broad-evaluation-result", "confirmation-evaluation-result"}:
            evaluation = validate_evaluation_result_v1(body)
            phase = (
                BROAD_SCREEN_PHASE
                if role == "broad-evaluation-result"
                else CONFIRMATION_PHASE
            )
            source = (
                len(broad_records)
                if phase == BROAD_SCREEN_PHASE
                else len(confirmation_records)
            )
            if (
                evaluation["phase"] != phase
                or evaluation["source_ordinal"] != source
                or evaluation["design_publication_identity"] != design_identity
                or evaluation["design_sha256"] != retained_design["design_sha256"]
                or evaluation["topology_identity"]
                != retained_design["topology_identity"]
            ):
                _fail("terminal streamed evaluation authority differs")
            compact = _compact_evaluation_record_v1({
                "source_ordinal": source,
                "slate_id": evaluation["slate_id"],
                "phase": phase,
                "body": evaluation,
                "identity": identity,
            })
            record = _minimal_aggregate_evaluation_record_v1(compact)
            raw_record = canonical_json_bytes_v1(record)
            retained_record_count = len(broad_records) + len(confirmation_records)
            next_compact_state_bytes = (
                compact_state_bytes
                + len(raw_record)
                + (1 if retained_record_count else 0)
            )
            if next_compact_state_bytes > compact_state_limit:
                _fail("terminal compact evaluation state exceeds resource precharge")
            if phase == BROAD_SCREEN_PHASE:
                broad_records.append(record)
            else:
                confirmation_records.append(record)
            compact_state_bytes = next_compact_state_bytes
            del evaluation, compact, raw_record
        elif role == "nomination":
            nomination_publication = validate_nomination_publication_authority_v1(
                body, publication_identity=identity
            )
            nomination_publication_identity = identity
        elif role == "aggregate":
            aggregate = validate_aggregate_mechanics_authority_v1(
                body, publication_identity=identity
            )
            aggregate_identity = identity
        elif role == "confirmed-finalists":
            finalist = body
            finalist_identity = identity
        else:
            _fail("terminal streamed predecessor role differs")
        del body
        resource_checkpoint(
            f"terminal predecessor[{ordinal}] {role} compacted"
        )
    if (
        len(predecessor_rows) != OUTPUT_OBJECT_COUNT - 1
        or len(projection_identities) != PANEL_SLATE_COUNT
        or len(broad_selection_identities) != PANEL_SLATE_COUNT
        or len(confirmation_selection_identities) != PANEL_SLATE_COUNT
        or len(broad_records) != PANEL_SLATE_COUNT
        or len(confirmation_records) != PANEL_SLATE_COUNT
        or nomination_publication is None
        or nomination_publication_identity is None
        or aggregate is None
        or aggregate_identity is None
        or finalist is None
        or finalist_identity is None
    ):
        _fail("terminal streamed predecessor lattice is incomplete")
    rebuilt = _build_aggregate_mechanics_from_records_v1(
        retained_design=retained_design,
        retained_design_identity=design_identity,
        run_identity=aggregate["run_identity"],
        nomination_publication=nomination_publication,
        nomination_publication_identity=nomination_publication_identity,
        broad_records=broad_records,
        confirmation_records=confirmation_records,
    )
    if canonical_json_bytes_v1(rebuilt) != canonical_json_bytes_v1(aggregate):
        _fail("terminal streamed aggregate differs from evaluation reductions")
    for source, record in enumerate(broad_records):
        if (
            record["body"]["projection_bundle_identity"]
            != projection_identities[source]
            or record["body"]["selection_receipt_identity"]
            != broad_selection_identities[source]
        ):
            _fail("terminal streamed broad predecessor links differ")
    for source, record in enumerate(confirmation_records):
        if (
            record["body"]["projection_bundle_identity"]
            != projection_identities[source]
            or record["body"]["selection_receipt_identity"]
            != confirmation_selection_identities[source]
        ):
            _fail("terminal streamed confirmation predecessor links differ")
    retained_finalist = validate_finalist_publication_authority_v1(
        finalist,
        publication_identity=finalist_identity,
        aggregate=aggregate,
        aggregate_publication_identity=aggregate_identity,
    )
    body = {
        "schema_version": ROOT_SCHEMA,
        "contract_id": CONTRACT_ID,
        "design_publication_identity": design_identity,
        "topology_sha256": topology["topology_sha256"],
        "aggregate_publication_identity": aggregate_identity,
        "aggregate_mechanics_sha256": aggregate["aggregate_mechanics_sha256"],
        "finalist_publication_identity": finalist_identity,
        "finalist_publication_sha256": retained_finalist[
            "finalist_publication_sha256"
        ],
        "broad_logical_fold_selection_count": aggregate[
            "broad_phase_execution_authority"
        ]["logical_fold_selection_count"],
        "broad_selector_os_process_count": aggregate[
            "broad_phase_execution_authority"
        ]["selector_os_process_count"],
        "confirmation_logical_fold_selection_count": aggregate[
            "confirmation_phase_execution_authority"
        ]["logical_fold_selection_count"],
        "confirmation_selector_os_process_count": aggregate[
            "confirmation_phase_execution_authority"
        ]["selector_os_process_count"],
        "broad_child_execution_evidence_ledger_sha256": aggregate[
            "broad_phase_execution_authority"
        ]["child_execution_evidence_sha256s_sha256"],
        "confirmation_child_execution_evidence_ledger_sha256": aggregate[
            "confirmation_phase_execution_authority"
        ]["child_execution_evidence_sha256s_sha256"],
        "predecessor_count": len(predecessor_rows),
        "predecessors": predecessor_rows,
        "predecessors_sha256": canonical_sha256_v1(predecessor_rows),
        "predecessor_opener_call_count": len(predecessor_rows),
        "retained_full_evaluation_body_count": 0,
        "retained_compact_evaluation_record_count": (
            len(broad_records) + len(confirmation_records)
        ),
        "retained_compact_evaluation_state_bytes": compact_state_bytes,
        "streaming_body_list_accepted": False,
        "terminal_reconstruction_law": (
            "stream-exact-ordinal-reduce-evaluations-rebuild-aggregate-finalist"
        ),
        "publication_order_law": "strict-ordinal-create-once-root-last",
        "policy": _policy_block(),
    }
    return _with_hash(body, field="root_sha256")


def validate_terminal_root_from_stream_authority_v1(
    value: object, *, publication_identity: object, design: object,
    design_publication_identity: object,
    predecessor_opener: Callable[
        [Mapping[str, object]], tuple[object, object]
    ],
    maximum_compact_evaluation_state_bytes: object,
    resource_checkpoint: Callable[[str], object],
) -> dict[str, object]:
    expected = build_terminal_root_from_stream_v1(
        design=design,
        design_publication_identity=design_publication_identity,
        predecessor_opener=predecessor_opener,
        maximum_compact_evaluation_state_bytes=(
            maximum_compact_evaluation_state_bytes
        ),
        resource_checkpoint=resource_checkpoint,
    )
    item = _mapping(value, label="terminal root")
    if canonical_json_bytes_v1(item) != canonical_json_bytes_v1(expected):
        _fail("terminal root differs from streamed exact reconstruction")
    identity = _bind_canonical_body_to_identity_v1(
        item, publication_identity, label="terminal root"
    )
    retained_design = validate_design_authority_v1(
        design, publication_identity=design_publication_identity
    )
    if identity["uri"] != _topology_uri_v1(
        retained_design["topology"], role="root"
    ):
        _fail("terminal root URI differs from topology")
    return expected


def deterministic_finalists_from_aggregate_v1(
    value: object, *, aggregate_publication_identity: object,
) -> dict[str, object]:
    """Authoritative finalist entry point bound to the combined aggregate."""
    aggregate = validate_aggregate_mechanics_authority_v1(
        value, publication_identity=aggregate_publication_identity
    )
    fixture = _deterministic_finalists_fixture_v1(
        aggregate["broad_phase_grid"]["rows"],
        aggregate["confirmation_phase_grid"]["rows"],
    )
    body = {
        key: retained
        for key, retained in fixture.items()
        if key not in {
            "finalist_function_sha256", "uses_realized_outcomes",
            "historical_scoring_licensed", "promotion_authority",
            "decision_authority",
        }
    }
    body.update({
        "aggregate_mechanics_sha256": aggregate["aggregate_mechanics_sha256"],
        "aggregate_publication_identity": _safe_object_identity(
            aggregate_publication_identity, label="aggregate publication identity"
        ),
        "nomination_sha256": aggregate["nomination_sha256"],
        "policy": _policy_block(),
    })
    return _with_hash(body, field="finalist_function_sha256")


def validate_finalists_v1(
    value: object, *, aggregate: object, aggregate_publication_identity: object,
) -> dict[str, object]:
    item = _mapping(value, label="confirmed finalists")
    _self_hash(
        item, field="finalist_function_sha256", label="confirmed finalists"
    )
    validate_policy_block_v1(item.get("policy"), label="confirmed finalists")
    expected = deterministic_finalists_from_aggregate_v1(
        aggregate,
        aggregate_publication_identity=aggregate_publication_identity,
    )
    if canonical_json_bytes_v1(item) != canonical_json_bytes_v1(expected):
        _fail("confirmed finalists differ from combined aggregate")
    return expected


def compile_process_budget_v1(
    *,
    process_role: str,
    projection_bundle: object,
    projection_bundle_identity: object,
    topology: object,
    topology_identity: object,
    source_ordinal: int,
    fold_ordinal: int | None = None,
    selection_receipt: object | None = None,
    selection_receipt_identity: object | None = None,
    bootstrap_manifest: object | None = None,
    bootstrap_manifest_identity: object | None = None,
    launch_intent_identity: object | None = None,
    nomination_publication: object | None = None,
    nomination_publication_identity: object | None = None,
) -> dict[str, object]:
    """Compile exact role-derived reads, writes, and fit precharge."""
    role = _string(process_role, label="process role")
    scientific_roles = {
        "broad-fold-selector", "broad-slate-assembler", "broad-evaluator",
        "confirmation-fold-selector", "confirmation-slate-assembler",
        "confirmation-evaluator",
    }
    if role not in scientific_roles:
        _fail("scientific process role differs; publisher budget required")
    topology_value = validate_result_topology_v1(topology)
    topology_authority = _bind_canonical_body_to_identity_v1(
        topology_value, topology_identity, label="result topology"
    )
    bundle = validate_projection_bundle_authority_v1(
        projection_bundle,
        publication_identity=projection_bundle_identity,
        topology=topology_value,
        topology_identity=topology_authority,
    )
    source = _integer(source_ordinal, label="process source ordinal")
    if source >= PANEL_SLATE_COUNT or bundle["source_ordinal"] != source:
        _fail("process source ordinal differs from projection bundle")
    phase = (
        BROAD_SCREEN_PHASE if role.startswith("broad-") else CONFIRMATION_PHASE
    )
    bundle_identity = _safe_object_identity(
        projection_bundle_identity, label="projection bundle identity"
    )
    reads: list[tuple[str, dict[str, object]]] = [
        ("projection-bundle", bundle_identity)
    ]
    writes: list[dict[str, object]] = []
    fit_count = 0
    process_ordinal: int
    if role.endswith("fold-selector"):
        if fold_ordinal is None:
            _fail("fold selector budget requires one fold ordinal")
        fold = _integer(fold_ordinal, label="budget fold ordinal")
        if fold >= FOLDS_PER_SLATE:
            _fail("budget fold ordinal differs")
        projection = bundle["fold_projections"][fold]
        reads.append(("later-source", projection["later_source_identity"]))
        for block in projection["training_blocks"]:
            reads.append((
                f"training-world-{block}",
                projection["world_artifact_identities"][
                    f"world_artifact_{str(block).lower()}"
                ],
            ))
        process_ordinal = source * FOLDS_PER_SLATE + fold
        if phase == BROAD_SCREEN_PHASE:
            if any(value is not None for value in (
                nomination_publication, nomination_publication_identity,
            )):
                _fail("broad selector budget cannot accept nomination")
            fit_count = BROAD_FITS_PER_FOLD
        else:
            if (
                nomination_publication is None
                or nomination_publication_identity is None
            ):
                _fail("confirmation selector budget requires nomination")
            (
                nomination_item,
                nomination_authority,
                _,
            ) = _validate_confirmation_nomination_authority_v1(
                nomination_publication=nomination_publication,
                nomination_publication_identity=nomination_publication_identity,
                topology=topology_value,
                topology_identity=topology_authority,
            )
            nominee_count = len(_nominee_keys_v1(nomination_item))
            reads.append(("nomination", nomination_authority))
            fit_count = SUBSAMPLE_REPLICATES * nominee_count
        if selection_receipt is not None or selection_receipt_identity is not None:
            _fail("fold selector budget cannot accept a selection receipt")
    elif role.endswith("slate-assembler"):
        if fold_ordinal is not None:
            _fail("slate assembler budget cannot accept a fold ordinal")
        process_ordinal = source
        if phase == CONFIRMATION_PHASE:
            if (
                nomination_publication is None
                or nomination_publication_identity is None
            ):
                _fail("confirmation assembler budget requires nomination")
            (
                nomination_item,
                nomination_authority,
                _,
            ) = _validate_confirmation_nomination_authority_v1(
                nomination_publication=nomination_publication,
                nomination_publication_identity=nomination_publication_identity,
                topology=topology_value,
                topology_identity=topology_authority,
            )
            _nominee_keys_v1(nomination_item)
            reads.append(("nomination", nomination_authority))
        elif any(value is not None for value in (
            nomination_publication, nomination_publication_identity,
        )):
            _fail("broad assembler budget cannot accept nomination")
        output_role = (
            "broad-selection-receipt"
            if phase == BROAD_SCREEN_PHASE
            else "confirmation-selection-receipt"
        )
        writes.append({
            "role": output_role,
            "source_ordinal": source,
            "uri": _topology_uri_v1(
                topology_value, role=output_role, source_ordinal=source
            ),
            "max_bytes": _ROLE_OUTPUT_BYTE_CEILINGS[role],
            "create_once": True,
        })
        if selection_receipt is not None or selection_receipt_identity is not None:
            _fail("assembler budget cannot accept a completed receipt")
    else:
        if fold_ordinal is not None:
            _fail("evaluator budget cannot accept a fold ordinal")
        if selection_receipt is None or selection_receipt_identity is None:
            _fail("evaluator budget requires immutable selection receipt")
        if (
            bootstrap_manifest is None
            or bootstrap_manifest_identity is None
            or launch_intent_identity is None
        ):
            _fail("evaluator budget requires bootstrap/launch authorities")
        receipt = validate_selection_receipt_authority_v1(
            selection_receipt,
            publication_identity=selection_receipt_identity,
            projection_bundle=bundle,
            projection_bundle_identity=bundle_identity,
            topology=topology_value,
            topology_identity=topology_authority,
            bootstrap_manifest=bootstrap_manifest,
            bootstrap_manifest_identity=bootstrap_manifest_identity,
            launch_intent_identity=launch_intent_identity,
            nomination_publication=nomination_publication,
            nomination_publication_identity=nomination_publication_identity,
        )
        if receipt["phase"] != phase:
            _fail("evaluator receipt phase differs")
        receipt_identity = _safe_object_identity(
            selection_receipt_identity, label="selection receipt identity"
        )
        reads.append(("selection-receipt", receipt_identity))
        projection = bundle["fold_projections"][0]
        reads.append(("later-source", projection["later_source_identity"]))
        for block in WORLD_BLOCKS:
            reads.append((
                f"heldout-world-{block}",
                projection["world_artifact_identities"][
                    f"world_artifact_{block.lower()}"
                ],
            ))
        if phase == CONFIRMATION_PHASE:
            nomination_authority = _safe_object_identity(
                nomination_publication_identity,
                label="nomination publication identity",
            )
            reads.append(("nomination", nomination_authority))
        output_role = (
            "broad-evaluation-result"
            if phase == BROAD_SCREEN_PHASE
            else "confirmation-evaluation-result"
        )
        writes.append({
            "role": output_role,
            "source_ordinal": source,
            "uri": _topology_uri_v1(
                topology_value, role=output_role, source_ordinal=source
            ),
            "max_bytes": _ROLE_OUTPUT_BYTE_CEILINGS[role],
            "create_once": True,
        })
        process_ordinal = source
    normalized_identities = _validate_one_generation_per_uri_v1(
        [identity for _, identity in reads], label="budget read identities"
    )
    read_rows = [
        {"role": read_role, "identity": identity}
        for (read_role, _), identity in zip(
            reads, normalized_identities, strict=True
        )
    ]
    for write in writes:
        _validate_uri_policy(str(write["uri"]), label="budget write URI")
    phase_ceiling = (
        MAXIMUM_BROAD_SELECTOR_FITS
        if phase == BROAD_SCREEN_PHASE
        else MAXIMUM_CONFIRMATION_SELECTOR_FITS
    )
    if fit_count > phase_ceiling or fit_count > MAXIMUM_SELECTOR_FITS:
        _fail("process fit precharge exceeds frozen ceiling")
    body = {
        "schema_version": PROCESS_BUDGET_SCHEMA,
        "contract_id": CONTRACT_ID,
        "process_role": role,
        "phase": phase,
        "source_ordinal": source,
        "process_ordinal": process_ordinal,
        "child_run_prefix": topology_value["child_run_prefix"],
        "topology_identity": topology_authority,
        "projection_bundle_identity": bundle_identity,
        "read_allowlist": read_rows,
        "read_object_count": len(read_rows),
        "read_byte_ceiling": sum(
            int(row["identity"]["bytes"]) for row in read_rows
        ),
        "write_allowlist": writes,
        "write_object_count": len(writes),
        "write_byte_ceiling": sum(int(row["max_bytes"]) for row in writes),
        "child_output_byte_ceiling": (
            _ROLE_OUTPUT_BYTE_CEILINGS[role]
            if role.endswith("fold-selector") else 0
        ),
        "compute_fit_precharge": fit_count,
        "all_block_fit_count": 0,
        "current_generation_lookup_allowed": False,
        "endpoint_override_allowed": False,
        "environment_redirect_allowed": False,
        "git_ref_redirect_allowed": False,
        "policy": _policy_block(),
    }
    return _with_hash(body, field="process_budget_sha256")


def validate_process_budget_v1(value: object) -> dict[str, object]:
    item = _mapping(value, label="process budget")
    _self_hash(item, field="process_budget_sha256", label="process budget")
    validate_policy_block_v1(item.get("policy"), label="process budget")
    if (
        item.get("schema_version") != PROCESS_BUDGET_SCHEMA
        or item.get("contract_id") != CONTRACT_ID
        or item.get("process_role") not in {
            "broad-fold-selector", "broad-slate-assembler", "broad-evaluator",
            "confirmation-fold-selector", "confirmation-slate-assembler",
            "confirmation-evaluator",
        }
        or not _string(item.get("child_run_prefix"), label="child run prefix")
        or item.get("current_generation_lookup_allowed") is not False
        or item.get("endpoint_override_allowed") is not False
        or item.get("environment_redirect_allowed") is not False
        or item.get("git_ref_redirect_allowed") is not False
        or item.get("all_block_fit_count") != 0
    ):
        _fail("process budget fixed policy differs")
    expected_child_bytes = (
        _ROLE_OUTPUT_BYTE_CEILINGS[str(item["process_role"])]
        if str(item["process_role"]).endswith("fold-selector") else 0
    )
    if item.get("child_output_byte_ceiling") != expected_child_bytes:
        _fail("process budget child output precharge differs")
    reads = [
        _mapping(row, label=f"budget read[{index}]")
        for index, row in enumerate(
            _sequence(item.get("read_allowlist"), label="budget reads")
        )
    ]
    identities = _validate_one_generation_per_uri_v1(
        [row.get("identity") for row in reads], label="budget reads"
    )
    role = str(item["process_role"])
    source = _integer(item.get("source_ordinal"), label="budget source ordinal")
    process_ordinal = _integer(
        item.get("process_ordinal"), label="budget process ordinal"
    )
    if source >= PANEL_SLATE_COUNT:
        _fail("process budget source ordinal differs")
    if role.endswith("fold-selector"):
        fold = process_ordinal - source * FOLDS_PER_SLATE
        if not 0 <= fold < FOLDS_PER_SLATE:
            _fail("process budget fold process ordinal differs")
        expected_read_roles = [
            "projection-bundle", "later-source",
            *[
                f"training-world-{block}"
                for block in WORLD_BLOCKS
                if block != WORLD_BLOCKS[fold]
            ],
        ]
        if role.startswith("confirmation-"):
            expected_read_roles.append("nomination")
        expected_write_roles: list[str] = []
    elif role.endswith("slate-assembler"):
        if process_ordinal != source:
            _fail("process budget assembler ordinal differs")
        expected_read_roles = ["projection-bundle"]
        if role.startswith("confirmation-"):
            expected_read_roles.append("nomination")
        expected_write_roles = [
            "broad-selection-receipt"
            if role.startswith("broad-")
            else "confirmation-selection-receipt"
        ]
    else:
        if process_ordinal != source:
            _fail("process budget evaluator ordinal differs")
        expected_read_roles = [
            "projection-bundle", "selection-receipt", "later-source",
            *[f"heldout-world-{block}" for block in WORLD_BLOCKS],
        ]
        if role.startswith("confirmation-"):
            expected_read_roles.append("nomination")
        expected_write_roles = [
            "broad-evaluation-result"
            if role.startswith("broad-")
            else "confirmation-evaluation-result"
        ]
    if (
        any(set(row) != {"role", "identity"} for row in reads)
        or [row.get("role") for row in reads] != expected_read_roles
        or len({identity["uri"] for identity in identities}) != len(identities)
        or item.get("read_object_count") != len(reads)
        or item.get("read_byte_ceiling")
        != sum(int(identity["bytes"]) for identity in identities)
    ):
        _fail("process budget read precharge differs")
    writes = [
        _mapping(row, label=f"budget write[{index}]")
        for index, row in enumerate(
            _sequence(item.get("write_allowlist"), label="budget writes")
        )
    ]
    for row in writes:
        if (
            set(row)
            != {"role", "source_ordinal", "uri", "max_bytes", "create_once"}
            or row["create_once"] is not True
        ):
            _fail("process budget write allowlist differs")
        _validate_uri_policy(str(row["uri"]), label="budget write URI")
        if (
            not str(row["uri"]).startswith(OUTPUT_NAMESPACE)
            or f"/{item['child_run_prefix']}/" not in str(row["uri"])
        ):
            _fail("process budget write is outside its child run prefix")
    if (
        [row.get("role") for row in writes] != expected_write_roles
        or item.get("write_object_count") != len(writes)
        or item.get("write_byte_ceiling")
        != sum(int(row["max_bytes"]) for row in writes)
    ):
        _fail("process budget write precharge differs")
    expected_phase = (
        BROAD_SCREEN_PHASE if role.startswith("broad-") else CONFIRMATION_PHASE
    )
    fits = _integer(
        item.get("compute_fit_precharge"), label="budget fit precharge"
    )
    if role.endswith("fold-selector"):
        fit_ok = (
            fits == BROAD_FITS_PER_FOLD
            if role.startswith("broad-")
            else (
                fits % SUBSAMPLE_REPLICATES == 0
                and MINIMUM_CONFIRMATION_NOMINEES
                <= fits // SUBSAMPLE_REPLICATES
                <= MAXIMUM_CONFIRMATION_NOMINEES
            )
        )
    else:
        fit_ok = fits == 0
    if (
        item.get("phase") != expected_phase
        or not fit_ok
        or any(
            int(row["max_bytes"]) != _ROLE_OUTPUT_BYTE_CEILINGS[role]
            for row in writes
        )
    ):
        _fail("process budget phase/fit/write ceiling differs")
    _safe_object_identity(item.get("topology_identity"), label="budget topology")
    _safe_object_identity(
        item.get("projection_bundle_identity"), label="budget projection bundle"
    )
    return item


def compile_evaluator_process_budget_v1(
    *, design: object, design_publication_identity: object,
    bootstrap_manifest: object, bootstrap_manifest_identity: object,
    launch_intent_identity: object, projection_bundle: object,
    projection_bundle_identity: object, topology_identity: object,
    source_ordinal: int, selection_receipt: object,
    selection_receipt_identity: object,
    nomination_publication: object | None = None,
    nomination_publication_identity: object | None = None,
) -> dict[str, object]:
    """Compile evaluator reads including every ex-ante execution authority."""
    retained_design = validate_design_authority_v1(
        design, publication_identity=design_publication_identity
    )
    manifest = validate_bootstrap_manifest_authority_v1(
        bootstrap_manifest,
        publication_identity=bootstrap_manifest_identity,
        topology=retained_design["topology"],
        topology_identity=topology_identity,
    )
    launch_authority = _launch_authority_from_bootstrap_v1(
        manifest, launch_intent_identity
    )
    receipt = _mapping(selection_receipt, label="evaluator selection receipt")
    phase = _string(receipt.get("phase"), label="evaluator selection phase")
    role = (
        "broad-evaluator"
        if phase == BROAD_SCREEN_PHASE
        else "confirmation-evaluator"
        if phase == CONFIRMATION_PHASE
        else ""
    )
    if not role:
        _fail("evaluator process budget phase differs")
    base = compile_process_budget_v1(
        process_role=role,
        projection_bundle=projection_bundle,
        projection_bundle_identity=projection_bundle_identity,
        topology=retained_design["topology"],
        topology_identity=topology_identity,
        source_ordinal=source_ordinal,
        selection_receipt=selection_receipt,
        selection_receipt_identity=selection_receipt_identity,
        bootstrap_manifest=bootstrap_manifest,
        bootstrap_manifest_identity=bootstrap_manifest_identity,
        launch_intent_identity=launch_authority,
        nomination_publication=nomination_publication,
        nomination_publication_identity=nomination_publication_identity,
    )
    common = [
        {
            "role": "design",
            "identity": _safe_object_identity(
                design_publication_identity, label="evaluator design"
            ),
        },
        {
            "role": "topology",
            "identity": _safe_object_identity(
                topology_identity, label="evaluator topology"
            ),
        },
        {
            "role": "bootstrap-manifest",
            "identity": _safe_object_identity(
                bootstrap_manifest_identity, label="evaluator bootstrap manifest"
            ),
        },
        {
            "role": "launch-intent",
            "identity": _safe_object_identity(
                launch_authority, label="evaluator launch intent"
            ),
        },
    ]
    reads = [*common, *base["read_allowlist"]]
    body = {
        "schema_version": EVALUATOR_PROCESS_BUDGET_SCHEMA,
        "contract_id": CONTRACT_ID,
        "process_role": role,
        "phase": phase,
        "source_ordinal": int(base["source_ordinal"]),
        "process_ordinal": int(base["process_ordinal"]),
        "design_publication_identity": common[0]["identity"],
        "topology_identity": common[1]["identity"],
        "bootstrap_manifest_identity": common[2]["identity"],
        "bootstrap_manifest_sha256": manifest["bootstrap_manifest_sha256"],
        "launch_intent_identity": common[3]["identity"],
        "projection_bundle_identity": base["projection_bundle_identity"],
        "base_process_budget": base,
        "base_process_budget_sha256": base["process_budget_sha256"],
        "read_allowlist": reads,
        "read_object_count_excluding_budget_authority": len(reads),
        "read_byte_ceiling_excluding_budget_authority": sum(
            int(row["identity"]["bytes"]) for row in reads
        ),
        "write_allowlist": base["write_allowlist"],
        "write_object_count": base["write_object_count"],
        "write_byte_ceiling": base["write_byte_ceiling"],
        "compute_fit_precharge": 0,
        "process_budget_authority_added_at_runtime": True,
        "current_generation_lookup_allowed": False,
        "environment_redirect_allowed": False,
        "git_ref_redirect_allowed": False,
        "policy": _policy_block(),
    }
    return _with_hash(body, field="evaluator_process_budget_sha256")


def validate_evaluator_process_budget_v1(
    value: object, *, design: object, design_publication_identity: object,
    bootstrap_manifest: object, bootstrap_manifest_identity: object,
    launch_intent_identity: object,
) -> dict[str, object]:
    item = _mapping(value, label="evaluator process budget")
    _self_hash(
        item,
        field="evaluator_process_budget_sha256",
        label="evaluator process budget",
    )
    validate_policy_block_v1(item.get("policy"), label="evaluator process budget")
    retained_design = validate_design_authority_v1(
        design, publication_identity=design_publication_identity
    )
    manifest = validate_bootstrap_manifest_authority_v1(
        bootstrap_manifest,
        publication_identity=bootstrap_manifest_identity,
        topology=retained_design["topology"],
        topology_identity=item.get("topology_identity"),
    )
    launch_authority = _launch_authority_from_bootstrap_v1(
        manifest, launch_intent_identity
    )
    base = validate_process_budget_v1(item.get("base_process_budget"))
    common = [
        ("design", design_publication_identity),
        ("topology", item.get("topology_identity")),
        ("bootstrap-manifest", bootstrap_manifest_identity),
        ("launch-intent", launch_authority),
    ]
    expected_reads = [
        {"role": role, "identity": _safe_object_identity(identity, label=role)}
        for role, identity in common
    ] + list(base["read_allowlist"])
    if (
        item.get("schema_version") != EVALUATOR_PROCESS_BUDGET_SCHEMA
        or item.get("contract_id") != CONTRACT_ID
        or item.get("process_role") not in {
            "broad-evaluator", "confirmation-evaluator",
        }
        or item.get("phase") != base["phase"]
        or item.get("source_ordinal") != base["source_ordinal"]
        or item.get("process_ordinal") != base["process_ordinal"]
        or item.get("design_publication_identity") != expected_reads[0]["identity"]
        or item.get("bootstrap_manifest_identity") != expected_reads[2]["identity"]
        or item.get("bootstrap_manifest_sha256")
        != manifest["bootstrap_manifest_sha256"]
        or item.get("launch_intent_identity") != expected_reads[3]["identity"]
        or item.get("projection_bundle_identity")
        != base["projection_bundle_identity"]
        or item.get("base_process_budget_sha256") != base["process_budget_sha256"]
        or item.get("read_allowlist") != expected_reads
        or item.get("read_object_count_excluding_budget_authority")
        != len(expected_reads)
        or item.get("read_byte_ceiling_excluding_budget_authority")
        != sum(int(row["identity"]["bytes"]) for row in expected_reads)
        or item.get("write_allowlist") != base["write_allowlist"]
        or item.get("write_object_count") != base["write_object_count"]
        or item.get("write_byte_ceiling") != base["write_byte_ceiling"]
        or item.get("compute_fit_precharge") != 0
        or item.get("process_budget_authority_added_at_runtime") is not True
        or item.get("current_generation_lookup_allowed") is not False
        or item.get("environment_redirect_allowed") is not False
        or item.get("git_ref_redirect_allowed") is not False
    ):
        _fail("evaluator process budget authority differs")
    return item


def bootstrap_process_spec_v1(
    value: object, *, process_role: str,
) -> dict[str, object]:
    manifest = validate_bootstrap_manifest_v1(value)
    role = _string(process_role, label="bootstrap process role")
    rows = [row for row in manifest["process_specs"] if row["process_role"] == role]
    if len(rows) != 1:
        _fail("bootstrap process role is absent or repeated")
    return dict(rows[0])


def compile_publisher_process_budget_v1(
    *, process_role: str, design: object, design_publication_identity: object,
    topology_identity: object, bootstrap_manifest: object,
    bootstrap_manifest_identity: object, launch_intent_identity: object,
    scientific_read_identities: object,
) -> dict[str, object]:
    """Compile exact precharge for projection and deterministic publishers."""
    role = _string(process_role, label="publisher process role")
    publisher_roles = {
        "projection-publisher", "broad-nomination-publisher",
        "aggregate-finalist-publisher", "terminal-root-publisher",
    }
    if role not in publisher_roles:
        _fail("publisher process role differs")
    retained_design = validate_design_authority_v1(
        design, publication_identity=design_publication_identity
    )
    topology = retained_design["topology"]
    topology_authority = _bind_canonical_body_to_identity_v1(
        topology, topology_identity, label="publisher topology"
    )
    manifest = validate_bootstrap_manifest_authority_v1(
        bootstrap_manifest,
        publication_identity=bootstrap_manifest_identity,
        topology=topology,
        topology_identity=topology_authority,
    )
    launch_authority = _launch_authority_from_bootstrap_v1(
        manifest, launch_intent_identity
    )
    if (
        retained_design["bootstrap_manifest_identity"]
        != _safe_object_identity(
            bootstrap_manifest_identity, label="publisher bootstrap manifest"
        )
        or retained_design["bootstrap_manifest_sha256"]
        != manifest["bootstrap_manifest_sha256"]
    ):
        _fail("publisher bootstrap manifest differs from design")
    raw_scientific = _sequence(
        scientific_read_identities, label="publisher scientific reads"
    )
    scientific = _validate_one_generation_per_uri_v1(
        raw_scientific, label="publisher scientific reads"
    )
    expected_counts = {
        "projection-publisher": EXACT_STRUCTURAL_OBJECT_COUNT,
        "broad-nomination-publisher": PANEL_SLATE_COUNT,
        "aggregate-finalist-publisher": 2 * PANEL_SLATE_COUNT + 1,
        "terminal-root-publisher": OUTPUT_OBJECT_COUNT - 1,
    }
    if len(scientific) != expected_counts[role]:
        _fail("publisher scientific read count differs")
    topology_rows = list(topology["objects"])
    if role == "broad-nomination-publisher":
        expected_uris = [
            row["uri"] for row in topology_rows
            if row["role"] == "broad-evaluation-result"
        ]
    elif role == "aggregate-finalist-publisher":
        expected_uris = [
            row["uri"] for row in topology_rows
            if row["role"] in {
                "broad-evaluation-result", "nomination",
                "confirmation-evaluation-result",
            }
        ]
    elif role == "terminal-root-publisher":
        expected_uris = [row["uri"] for row in topology_rows[:-1]]
    else:
        expected_uris = [identity["uri"] for identity in scientific]
    if [identity["uri"] for identity in scientific] != expected_uris:
        _fail("publisher scientific read URI/order differs")
    common = [
        {
            "role": "design",
            "identity": _safe_object_identity(
                design_publication_identity, label="publisher design"
            ),
        },
        {"role": "topology", "identity": topology_authority},
        {
            "role": "bootstrap-manifest",
            "identity": _safe_object_identity(
                bootstrap_manifest_identity, label="publisher bootstrap manifest"
            ),
        },
        {
            "role": "launch-intent",
            "identity": _safe_object_identity(
                launch_authority, label="publisher launch intent"
            ),
        },
    ]
    reads = [
        *common,
        *[
            {"role": f"scientific-{index:03d}", "identity": identity}
            for index, identity in enumerate(scientific)
        ],
    ]
    if role == "projection-publisher":
        write_descriptors = [
            row for row in topology_rows if row["role"] == "projection"
        ]
    elif role == "broad-nomination-publisher":
        write_descriptors = [row for row in topology_rows if row["role"] == "nomination"]
    elif role == "aggregate-finalist-publisher":
        write_descriptors = [
            row for row in topology_rows
            if row["role"] in {"aggregate", "confirmed-finalists"}
        ]
    else:
        write_descriptors = [row for row in topology_rows if row["role"] == "root"]
    writes = [
        {
            "ordinal": row["ordinal"],
            "role": row["role"],
            "uri": row["uri"],
            "max_bytes": _PUBLICATION_BYTE_CEILINGS[row["role"]],
            "create_once": True,
        }
        for row in write_descriptors
    ]
    body = {
        "schema_version": PUBLISHER_PROCESS_BUDGET_SCHEMA,
        "contract_id": CONTRACT_ID,
        "process_role": role,
        "process_ordinal": 0,
        "design_publication_identity": common[0]["identity"],
        "topology_identity": topology_authority,
        "bootstrap_manifest_identity": common[2]["identity"],
        "bootstrap_manifest_sha256": manifest["bootstrap_manifest_sha256"],
        "launch_intent_identity": common[3]["identity"],
        "scientific_read_count": len(scientific),
        "scientific_read_identities_sha256": canonical_sha256_v1(scientific),
        "read_allowlist": reads,
        "read_object_count_excluding_budget_authority": len(reads),
        "read_byte_ceiling_excluding_budget_authority": sum(
            int(row["identity"]["bytes"]) for row in reads
        ),
        "write_allowlist": writes,
        "write_object_count": len(writes),
        "write_byte_ceiling": sum(int(row["max_bytes"]) for row in writes),
        "process_budget_authority_added_at_runtime": True,
        "current_generation_lookup_allowed": False,
        "environment_redirect_allowed": False,
        "git_ref_redirect_allowed": False,
        "policy": _policy_block(),
    }
    return _with_hash(body, field="publisher_process_budget_sha256")


def validate_publisher_process_budget_v1(
    value: object, *, design: object, design_publication_identity: object,
    topology_identity: object, bootstrap_manifest: object,
    bootstrap_manifest_identity: object, launch_intent_identity: object,
) -> dict[str, object]:
    item = _mapping(value, label="publisher process budget")
    _self_hash(
        item,
        field="publisher_process_budget_sha256",
        label="publisher process budget",
    )
    scientific_rows = list(item.get("read_allowlist", []))[4:]
    expected = compile_publisher_process_budget_v1(
        process_role=str(item.get("process_role", "")),
        design=design,
        design_publication_identity=design_publication_identity,
        topology_identity=topology_identity,
        bootstrap_manifest=bootstrap_manifest,
        bootstrap_manifest_identity=bootstrap_manifest_identity,
        launch_intent_identity=launch_intent_identity,
        scientific_read_identities=[row.get("identity") for row in scientific_rows],
    )
    if canonical_json_bytes_v1(item) != canonical_json_bytes_v1(expected):
        _fail("publisher process budget canonical replay differs")
    return expected


def build_runtime_observation_v1(
    *, bootstrap_manifest: object, bootstrap_manifest_identity: object,
    process_budget: object, process_budget_identity: object,
    launch_intent_identity: object, observed_code_commit: str,
    observed_image_digest: str, observed_command: object,
    observed_entrypoint_sha256: str, cloud_job_name: str,
    cloud_execution_name: str, cloud_task_index: int,
) -> dict[str, object]:
    """Embed task observations; this is explicitly not cloud attestation."""
    manifest = validate_bootstrap_manifest_v1(bootstrap_manifest)
    manifest_identity = _bind_canonical_body_to_identity_v1(
        manifest, bootstrap_manifest_identity, label="runtime bootstrap manifest"
    )
    launch_authority = _launch_authority_from_bootstrap_v1(
        manifest, launch_intent_identity
    )
    budget = _mapping(process_budget, label="runtime process budget")
    budget_hash_field = (
        "evaluator_process_budget_sha256"
        if budget.get("schema_version") == EVALUATOR_PROCESS_BUDGET_SCHEMA
        else "publisher_process_budget_sha256"
    )
    _self_hash(budget, field=budget_hash_field, label="runtime process budget")
    role = _string(budget.get("process_role"), label="runtime process role")
    spec = next(
        (row for row in manifest["process_specs"] if row["process_role"] == role),
        None,
    )
    if spec is None or len(spec["process_chain"]) != 1:
        _fail("runtime observation requires one exact OS-process spec")
    expected = spec["process_chain"][0]
    command = [
        _string(token, label="runtime command token")
        for token in _sequence(observed_command, label="runtime command")
    ]
    commit = _string(observed_code_commit, label="runtime code commit")
    image = _string(observed_image_digest, label="runtime image digest")
    entrypoint_hash = _sha256_hex(
        observed_entrypoint_sha256, label="runtime entrypoint sha256"
    )
    if (
        commit != manifest["code_commit"]
        or image != manifest["image_digest"]
        or command != expected["command"]
        or entrypoint_hash != expected["entrypoint_sha256"]
    ):
        _fail("runtime observation differs from bootstrap manifest")
    budget_identity = _bind_canonical_body_to_identity_v1(
        budget, process_budget_identity, label="runtime process budget"
    )
    body = {
        "schema_version": RUNTIME_OBSERVATION_SCHEMA,
        "contract_id": CONTRACT_ID,
        "process_role": role,
        "bootstrap_manifest_identity": manifest_identity,
        "bootstrap_manifest_sha256": manifest["bootstrap_manifest_sha256"],
        "process_budget_identity": budget_identity,
        "process_budget_sha256": budget[budget_hash_field],
        "launch_intent_identity": launch_authority,
        "observed_code_commit": commit,
        "observed_image_digest": image,
        "observed_command": command,
        "observed_entrypoint_sha256": entrypoint_hash,
        "cloud_job_name_observed": _string(
            cloud_job_name, label="runtime cloud job"
        ),
        "cloud_execution_name_observed": _string(
            cloud_execution_name, label="runtime cloud execution"
        ),
        "cloud_task_index_observed": _integer(
            cloud_task_index, label="runtime cloud task index"
        ),
        "read_object_count_including_process_budget_authority": int(
            budget["read_object_count_excluding_budget_authority"]
        ) + 1,
        "read_byte_ceiling_including_process_budget_authority": int(
            budget["read_byte_ceiling_excluding_budget_authority"]
        ) + int(budget_identity["bytes"]),
        "cloud_values_are_unattested_observations": True,
        "terminal_execution_attestation_required": True,
        "policy": _policy_block(),
    }
    return _with_hash(body, field="runtime_observation_sha256")


def validate_runtime_observation_v1(
    value: object, *, bootstrap_manifest: object,
    bootstrap_manifest_identity: object, process_budget: object,
    process_budget_identity: object, launch_intent_identity: object,
) -> dict[str, object]:
    item = _mapping(value, label="runtime observation")
    _self_hash(
        item, field="runtime_observation_sha256", label="runtime observation"
    )
    expected = build_runtime_observation_v1(
        bootstrap_manifest=bootstrap_manifest,
        bootstrap_manifest_identity=bootstrap_manifest_identity,
        process_budget=process_budget,
        process_budget_identity=process_budget_identity,
        launch_intent_identity=launch_intent_identity,
        observed_code_commit=str(item.get("observed_code_commit", "")),
        observed_image_digest=str(item.get("observed_image_digest", "")),
        observed_command=item.get("observed_command"),
        observed_entrypoint_sha256=str(
            item.get("observed_entrypoint_sha256", "")
        ),
        cloud_job_name=str(item.get("cloud_job_name_observed", "")),
        cloud_execution_name=str(
            item.get("cloud_execution_name_observed", "")
        ),
        cloud_task_index=item.get("cloud_task_index_observed"),
    )
    if canonical_json_bytes_v1(item) != canonical_json_bytes_v1(expected):
        _fail("runtime observation canonical replay differs")
    return expected


__all__ = [
    "AGGREGATE_MECHANICS_SCHEMA",
    "BOOTSTRAP_MANIFEST_SCHEMA",
    "BOOTSTRAP_INPUT_SCHEMA",
    "BROAD_PHASE_AUTHORITY_SCHEMA",
    "BROAD_SELECTION_RECEIPT_MAX_BYTES",
    "CONTRACT_ID",
    "CONTRACT_REPORT_PATH",
    "BROAD_SCREEN_PHASE",
    "CONFIRMATION_PHASE",
    "CONFIRMATION_SELECTION_RECEIPT_MAX_BYTES",
    "DESIGN_SCHEMA",
    "EVALUATION_RESULT_SCHEMA",
    "EVALUATOR_PROCESS_BUDGET_SCHEMA",
    "BOOK_METRIC_ROW_SCHEMA",
    "COMPARISON_LEDGER_SCHEMA",
    "FOLD_SELECTOR_SUBPROCESS_COUNT",
    "LOGICAL_FOLD_SELECTION_COUNT_PER_PHASE",
    "MAX_EQUAL_COUNT_SAMPLE",
    "MAX_GENERATION_DIGITS",
    "MAX_GCS_URI_UTF8_BYTES",
    "MAX_IDENTITY_BYTES",
    "MAX_LINEUP_ID_UTF8_BYTES",
    "MAX_OCCURRENCE_COUNT",
    "MAX_PLAYER_ID_UTF8_BYTES",
    "MAX_SELECTION_CANDIDATES_PER_FOLD",
    "SELECTOR_OS_PROCESS_COUNT_PER_PHASE",
    "FINALIST_PUBLICATION_SCHEMA",
    "HELDOUT_FOLD_AUTHORITY_SCHEMA",
    "LAYER_ROLES",
    "MODULE_PATH",
    "OUTPUT_NAMESPACE",
    "PANEL_IDENTITY",
    "PANEL_SELF_SHA256",
    "POLICY_CLAIMS",
    "PREFIX_SIZES",
    "POPULATION_METRIC_ROW_SCHEMA",
    "PROCESS_BUDGET_SCHEMA",
    "PUBLISHER_PROCESS_BUDGET_SCHEMA",
    "PROCESS_ROLES",
    "PROJECTION_BUNDLE_SCHEMA",
    "PROFILE_IDENTITIES",
    "SELECTION_FOLD_RECEIPT_SCHEMA",
    "SELECTION_RECEIPT_SCHEMA",
    "NOMINATION_PUBLICATION_SCHEMA",
    "RUNTIME_OBSERVATION_SCHEMA",
    "STRATEGY_IDENTITIES",
    "SUBSAMPLE_REPLICATES",
    "ROOT_SCHEMA",
    "ROSTER_SIZE",
    "WORLD_BLOCKS",
    "CorpusR6CurrentBankCrossedScreenContractV1Error",
    "build_aggregate_mechanics_v1",
    "build_broad_phase_authority_v1",
    "build_bootstrap_manifest_v1",
    "build_design_v1",
    "build_evaluation_fold_v1",
    "build_evaluation_result_v1",
    "build_layer_binding_v1",
    "build_projection_bundle_v1",
    "build_selection_receipt_v1",
    "build_finalist_publication_v1",
    "build_nomination_publication_v1",
    "build_runtime_observation_v1",
    "build_terminal_root_from_stream_v1",
    "canonical_json_bytes_v1",
    "canonical_sha256_v1",
    "canonical_world_columns_sha256_v1",
    "canonical_world_columns_v1",
    "candidate_dedup_diagnostics_from_projection_v1",
    "build_result_topology_v1",
    "bootstrap_process_spec_v1",
    "compile_evaluator_process_budget_v1",
    "compile_process_budget_v1",
    "compile_publisher_process_budget_v1",
    "derive_view_registry_from_projection_v1",
    "deterministic_equal_count_samples_from_projection_v1",
    "deterministic_finalists_from_aggregate_v1",
    "deterministic_nominees_from_broad_authority_v1",
    "exclusive_view_id_v1",
    "frozen_contract_v1",
    "frozen_profiles_v1",
    "frozen_strategies_v1",
    "isolated_view_id_v1",
    "leave_one_out_view_id_v1",
    "pair_union_view_id_v1",
    "strategy_executable_fingerprint_v1",
    "to_micro_v1",
    "validate_aggregate_mechanics_authority_v1",
    "validate_aggregate_mechanics_v1",
    "validate_broad_phase_authority_v1",
    "validate_bootstrap_manifest_authority_v1",
    "validate_bootstrap_manifest_v1",
    "validate_design_authority_v1",
    "validate_design_v1",
    "validate_evaluation_result_authority_v1",
    "validate_evaluation_result_v1",
    "validate_finalists_v1",
    "validate_finalist_publication_authority_v1",
    "validate_evaluator_process_budget_v1",
    "validate_layer_binding_v1",
    "validate_panel_identity_v1",
    "validate_narrow_projection_v1",
    "validate_nomination_v1",
    "validate_nomination_publication_authority_v1",
    "validate_nomination_publication_from_evaluations_authority_v1",
    "validate_nomination_publication_v1",
    "validate_policy_block_v1",
    "validate_process_budget_v1",
    "validate_publisher_process_budget_v1",
    "validate_projection_bundle_authority_v1",
    "validate_projection_bundle_v1",
    "validate_result_topology_v1",
    "validate_runtime_observation_v1",
    "validate_selection_fold_receipt_v1",
    "validate_selection_receipt_authority_v1",
    "validate_selection_receipt_v1",
    "validate_terminal_root_from_stream_authority_v1",
]
