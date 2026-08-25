"""Outcome-blind R6-v2 panel execution and source-blocked release seam.

The public R6-v2 scientific runner already reconstructs one accepted Foundry
v12 slate and materializes five held-out fit scopes plus one distinct all-block
fit.  This module supplies the missing durable panel seam around that runner:

* ``prepare`` exact-replays the published 54-slate panel and freezes an
  immutable execution manifest;
* ``run-slate`` executes one member, validates the complete 276-book lattice,
  derives exact 4/14/80 prefixes, and publishes a mechanics result;
* a separate acceptance pass exact-reopens that result and its matchup source;
* ``finish-panel`` exact-reopens all 54 ordered acceptance objects.

The only matchup object understood by the current runner is the legacy/simple
``corpus-r6-matchup-source-snapshot/v1`` object.  The project's lineage audit
classifies that path as non-PIT retrospective and expressly forbids using it to
freeze an R6-v2 analysis.  Consequently this version can finish only as
``complete-source-blocked``.  It never accepts a caller's evidence label, does
not offer a matchup-free lane, and cannot grant R6 freeze, outcome, promotion,
or decision authority.  A future accepted release requires the separately
versioned corrected two-object source/reopen contract; it cannot be smuggled
through this mechanics seam.

No function in this module imports or reads realized outcomes.  Object-store
access is exact-name only and every publication is create-once with an exact
reopen.
"""

from __future__ import annotations

import ast
from collections.abc import Mapping, Sequence
from hashlib import sha256
import os
from pathlib import Path
import platform
import re
import sys
from typing import Final

from nfl_dfs.research import corpus_batch_retrieval_runner_v2 as runner
from nfl_dfs.research import corpus_neo4j_transport as transport
from nfl_dfs.research import corpus_parametric_batch as batch
from nfl_dfs.research import corpus_r6_v2_one_slate_execution as execution
from nfl_dfs.research import corpus_retrieval_engine as retrieval
from nfl_dfs.research import corpus_retrieval_v2_implementation_contract as impl
from nfl_dfs.research import corpus_v12_import as v12_import
from nfl_dfs.research import corpus_v12_panel_index as panel_index
from nfl_dfs.research import residual_world_columns as rw
from nfl_dfs.research.corpus_neo4j_transport import (
    ExactObjectStore,
    ObjectIdentity,
)
from nfl_dfs.research.corpus_v12_import import canonical_lineup_id


RELEASE_IMPLEMENTATION_SCHEMA: Final = (
    "corpus-r6-v2-analysis-release-implementation/v1"
)
MEASURED_IMPLEMENTATION_SCHEMA: Final = (
    "corpus-r6-v2-analysis-measured-implementation/v1"
)
PROCESS_RUNTIME_SCHEMA: Final = "corpus-r6-v2-analysis-process-runtime/v1"
VERIFICATION_REPLAY_SCHEMA: Final = (
    "corpus-r6-v2-analysis-independent-verification-replay/v1"
)
RELEASE_IMPLEMENTATION_ID: Final = "outcome-blind-r6-v2-analysis-release-v1"
MANIFEST_SCHEMA: Final = "corpus-r6-v2-analysis-execution-manifest/v1"
MECHANICS_RESULT_SCHEMA: Final = "corpus-r6-v2-analysis-slate-mechanics/v1"
VERIFIER_RESULT_SCHEMA: Final = "corpus-r6-v2-analysis-verifier-result/v1"
BOOK_CATALOG_SCHEMA: Final = "corpus-r6-v2-analysis-book-catalog/v1"
BOOK_PROJECTION_SCHEMA: Final = "corpus-r6-v2-analysis-book-projection/v1"
PREFIX_SCHEMA: Final = "corpus-r6-v2-analysis-book-prefix/v1"
SLATE_ACCEPTANCE_SCHEMA: Final = "corpus-r6-v2-analysis-slate-acceptance/v1"
PANEL_COMPLETION_SCHEMA: Final = "corpus-r6-v2-analysis-panel-completion/v1"
PUBLICATION_MODE: Final = "create_once"

AUTHORITATIVE_SLATE_COUNT: Final = 54
LANE_TASK_COUNTS: Final = (28, 26)
STRATEGY_IDS: Final = (
    "coverage-194-v1",
    "strict-200-coverage-v1",
    "tail-ladder-200-210-220-v1",
    "mean-score-v1",
    "expected-max-v1",
    "block-supported-tail-ladder-v1",
    "regime-robust-ladder-v1",
)
PRIMARY_ADMISSION_IDS: Final = (
    "fold-eligible-union-v1",
    "matchup-top-200-supported-v2",
)
FIT_SCOPE_IDS: Final = (
    "holdout-R0",
    "holdout-R1",
    "holdout-R2",
    "holdout-R3",
    "holdout-R4",
    "all-block-final-fit",
)
PREFIX_SIZES: Final = (4, 14, 80)
NEUTRAL_REPLICATES: Final = 32
BOOKS_PER_SCOPE: Final = 46
CROSS_FIT_BOOK_COUNT: Final = 230
FINAL_FIT_BOOK_COUNT: Final = 46
BOOKS_PER_SLATE: Final = 276
ENTRY_BUDGET: Final = 80
ADMISSION_CAP: Final = 200
WORLDS_PER_BLOCK: Final = 10_000
NEUTRAL_SEED_ROOT: Final = "r6-v2-neutral-v1"
MINIMUM_SUPPORTED_PLAYERS: Final = 2
MINIMUM_COMPLETENESS: Final = 0.5
CURRENT_SOURCE_EVIDENCE_CLASS: Final = (
    execution.MATCHUP_EVIDENCE_RETROSPECTIVE
)
CURRENT_SOURCE_DISPOSITION: Final = "legacy-simple-snapshot-source-blocked"
SLATE_STATUS: Final = "complete-source-blocked"
WORKER_STATUS: Final = "mechanics-published-awaiting-independent-verification"
PANEL_STATUS: Final = "complete-source-blocked"
EXPECTED_UPSTREAM_IMPLEMENTATION_SHA256: Final = (
    "01f62c080451f6d090da782c47474e86ae8302a1a57df698d2df16fb5dcffac7"
)
EXPECTED_RELEASE_MODULE_NORMALIZED_SHA256: Final = (
    "5d23d08c1aea00ada61e7038bc8ebb1be793d9581e5d2fe1ae9a3476aa8c585a"
)
EXPECTED_RELEASE_CLI_SHA256: Final = (
    "b00e50d89db6d7265c9a8ae14decd94adcacc155b0d72fc5919e5aa5f6c00ab0"
)
EXPECTED_UPSTREAM_EXECUTION_MODULE_SHA256: Final = (
    "4d79079db40f12c6449844ffa56498c0686e4f0bb46c5818dcc4e0eeb0eb6ed2"
)
EXPECTED_DEPENDENCY_MODULE_SHA256: Final = {
    "batch_runner": "989b8cc848ca9607bb48777bca58ef5852cb8c5252067affd44058c573bdedba",
    "canonical_batch": "4cb7b3d613ed9dd8c35d4d9120798cf2863bb438a5cb3a7b05596fe97bc99bae",
    "exact_object_transport": "dfc751f7cf1121730d547da2ac1e430962531b5fef402b039dcc0aa72b385288",
    "implementation_contract": "66e6b4496397a656f96a47a55e84237fe30842670519ddb0ee804d5eeec6f61e",
    "random_world_order": "86d26af93c4ddf1a5b797a78de463897dc67aebf1083baf941259e767d3cdaf1",
    "retrieval_runner": "f69262c7468752ce40f0ae5ed55151046d4e9aacdad96fb1db6450188581c10a",
    "v12_import": "7420fef4acf2cd80da728417f18c54469fba9dddc30f3334b0eecf86890e1ad6",
    "v12_panel_replay": "221ff51d4d6c27e71420832a0abf452cf8ea2e5a1554caa9e32b5037e29b53b3",
}
EXPECTED_DEPENDENCY_CALLABLE_SOURCE_SHA256: Final = {
    "batch_runner": {
        "build_fit_candidate_view": "e28aa65c4d63086e2a72d8965bb57477d00e197f018e3f312b9b60e76ec756d2",
        "validate_matchup_source_snapshot": "5bff109fca58c6a8d2413785deae7f57ecb063f0f7569f9ca8a8524dac97bb4e",
        "build_matchup_lineup_summaries": "316e7651bbd872da1c5cad8559656111560d2aebd52646471c9aced955cd21ae",
        "validate_matchup_lineup_summaries": "368b5d45148a08938f5db1b7e84ee5916db2fbe3c6e34f6eb5f9dd9daf8b93e7",
        "_full_union_admission": "bfeff6a78e187cbb6b404773915c90bb290578f8eeeb870211b5043bdbd3c6c0",
        "_matchup_admission": "fa16a4e7a9e20985edfc1e7620451196c458741d95f9f64ea29d3584e7de22df",
        "build_score_blind_neutral_admission": "73cf987b65fedc6c9ace43afdb0ef8c1a7024a205f20e3584d7c111d40de8d31",
        "_select_expected_max_without_matrix_copy": "905618c34736334e75ae563fcd43bc08dfefbb431a95ff3d067a55b2c8044aa4",
        "_run_strategy_v2": "ebc998421819ae6525efe0bc0216d2f01c5e106d9a39a8bfe59124bc37b0525c",
        "_run_book": "198f16d8e6882ce5bfd36099297d70bc9564e8e7666ef9011548e2aa64bdef30",
        "_run_fit_scope_impl": "f499b1b21bc315ffd5fbfab22290aa51aad0eaef71790160fbb843b56119d317",
        "run_fit_scope": "a1fdd4eb2f2af01804ec6fef1dfaa2e80662c1661133bb81dff76b798315ac98",
        "run_retrieval_surface_v2": "076ea4a9bf8cb26495ab46854eadc27de835c67b94f51a32cd54cfdb97df0292",
        "validate_fit_scope": "9a448f3025ce584c76253280a46fabecb2d4c2d8effeb582eb93994b2ca7d3db",
        "validate_retrieval_surface_v2": "c60dd7d5fc40d00840b4b10314d03d6ab1e3e89985314b0b5339eb156823c199",
    },
    "canonical_batch": {
        "canonical_json_bytes": "9f5d79f80d87c0372c17a4318f18aceca00115d4e3b81c4d7633978ac02ddfcd",
        "canonical_sha256": "24cee15f553f4264f7cde06342f07e0e530daa6f4399703b4024badd80675270",
        "parse_canonical_json_bytes": "efbe879dd411294d8b92650939020d0387a0c42a7033433c8beebe19a4bb1584",
        "normalize_object_identity": "01d9f9bfa97e3497908fc3bed12dc2bee43090cbd037b665c450c5df0ad1776f",
    },
    "exact_object_transport": {
        "ObjectIdentity.as_dict": "a6c1cc4e83107927c6fac1754a82258999ae04d12130f78e9a2c0b3e993c5fd7",
        "ExactObjectStore.read_exact": "90c05b1bb252a06c3c9f391645a5e8ad8015e763144011f5978f4dd72300855e",
        "ExactObjectStore.resolve_optional": "fe20cc223c9714968e81aa322de6d3ca8b2c2b605b13d88f6946c76c3f4b866a",
        "ExactObjectStore.publish_create_once": "881a5998e77279ef44fd39ccb46724efe04a8b68d20bde7c4f91bc8b1d2074f2",
        "object_identity": "7d93959a4d3cc1fcdab9d2d18c904c7f707becd5829996752db291c7d0666987",
        "_bind_raw": "4fdd801bf5e7f7b03e9558a686d91f16f2b5f07cd329dfd87a3d6fc677642d7f",
        "GoogleCloudObjectStore._parts": "7efc926ec2fc65bd7ac444dbc13f5bad395c3d7b56a0b50eee0691f98d24cb94",
        "GoogleCloudObjectStore.read_exact": "ef210872536b9131792e2e152be48bd165afb570fd00be56aac85127bc5b85e0",
        "GoogleCloudObjectStore.resolve_optional": "3bff25e22492c38dc307d9c77550e9f07e7b5351687d6c25f40f47ae55cc8949",
        "GoogleCloudObjectStore.publish_create_once": "4f576f8b4303061d78b33392ce86f599d4a3d0dfaee4ed25deaa38835e8d7f89",
    },
    "implementation_contract": {
        "frozen_retrieval_v2_implementation_contract_v1": "91653e0c2fca6722c6a23373dbf5036c58477f08a5ad1213d213c013b3fa84db",
        "validate_retrieval_v2_implementation_contract_v1": "03aafb87f74ae620ec6dc10ce9d2620f326be386a4cefd9c60d9babe8117f5ac",
    },
    "random_world_order": {
        "canonical_identity": "feb516cc83b4520cc2797c0000a2c772b6a4d39f948d502008b50c05a4a3d6f7",
        "_exact_world_order": "8d97b57182f061c4701a62bf349a0c18405860aea47ac30358f7a8d3f203b264",
    },
    "retrieval_runner": {
        "frozen_retrieval_strategies_v2": "3e7916f6369197d82bd6a8517028956831d2feeab651a180c499a49811d53157",
        "validate_retrieval_strategy_v2": "a65912a717b2666118c85d60deecb0b81e389b10c93e0c53cef395b101dfecce",
        "_select_coverage": "42226767f95cc323fc1938b65d87207b7c0d4e0782b8d8f1702d523c3a69ace2",
        "_select_ladder": "0cb37297d220371c1dae384ee61379fb2881bac595b89b8fc84abb32eaec4e46",
        "_select_mean": "2caab38561cb7e74d6d12d3013cae7fc7f203bfaa79b0aab294a3ed3f1ef5371",
        "_select_expected_max": "9b966361d80d3354f62150b9ea421deb769a1d76ed3aea7733bd439c2aa41adc",
        "_select_block_supported_ladder": "6fd1be7ac32f0cb1f4e43dd74f35eb09ecb24786f16b34fb14b2690309506da3",
        "_select_blockmin_ladder": "ae7cf9763ac64e7632296028c9cad4b0e90289da02e7ff41d655dcd8a899ca98",
        "_run_strategy": "a80971d912469998a1650857c5a13d8385957b68751b747b9a8e04bec96b3378",
    },
    "v12_import": {
        "canonical_lineup_id": "71a8882adb440fd27ec72f209c8a8a46e511a9e5b36e3ed1afc7d307614333ef",
        "reopen_v12_task": "9ba90615e233df37fce73b980c77848c156f6db229e9b6f2779aa3f51b2d5567",
        "reconstruct_v12_task": "af3b6f48d66e8eb16d1a44473b4d0d3e55a66f71718291109c7f630f1632be41",
    },
    "v12_panel_replay": {
        "derive_v12_lane_input": "2dce2a24c5bca45f093d8e28784398f2a67ef4519a520bfbd1f24c75853e689b",
        "validate_v12_panel_index": "64a0e78b733c7667ef002d1029dd3a6efcd3131ad6d0475f22b770778942da06",
        "reopen_v12_panel_index": "aea947aa801c8c8faf151a1f79aa9a1b3fdf93a82fe142c3763f88fa9430bd32",
    },
}
EXPECTED_DEPENDENCY_CONSTANT_SHA256: Final = {
    "batch_runner": "93ca86b2b8e0312de2ca66f792b4fc6f2ec60d93ac2e0914488be6787a996e31",
    "canonical_batch": "d670817d2a67017c324962d08b9a5fefc8f562ca73d4bc6f7270a5231b88ef0b",
    "exact_object_transport": "79ce5784854a7f966296236971962932b91e2e14177dac1071e98bebc39ddaf1",
    "implementation_contract": "898518f3274b2aed8d624e6fc0c4aea52a5284058e3c8e082fc2ae0af940082b",
    "one_slate_execution": "9ea48ee079d6191252e6df064b308353d763d6a00cb6765e5b380eb9ae035f44",
    "random_world_order": "fe2c985f02f831b5a1ef7e68206c591ec73c13420ffd1637b0d9ea39284adf97",
    "retrieval_runner": "db953c23be8e3dcb6b328eb936f2f91b9b0f4a0335d5377083089f38198e9a08",
    "v12_import": "9dc5ce3819dc7515f9bca312e7b832bf0778253359786a27c5cb08f5e4f7d77b",
    "v12_panel_replay": "4bd303a5a878b399aefcddb4f142275621df97e125bca0305f958c612631d31d",
}
EXPECTED_CRITICAL_CALLABLE_SOURCE_SHA256: Final = {
    "release_module": {
        "release_implementation_contract_v1": (
            "a01c9f5414bb3ccc3a8eb5157d083169d68761224f40e4def82cdf9d280bcd13"
        ),
        "_measured_release_implementation_identity_v1": (
            "d22b26664f721934dadd3f3391ae92b4c4b2c4bb75961ac19d5aa9cc8f3750ad"
        ),
        "_process_runtime_identity_v1": (
            "a47b0dc17f73ac6ac6d1d22e78e90d2994380335a1d125b31304fa8f472ac642"
        ),
        "_validate_current_process_runtime_identity_v1": (
            "661a221c5d75cf33e52306cfc7a974a30a37c5e4fb2f639cf62a56b04c57bde6"
        ),
        "build_r6_v2_analysis_manifest_v1": (
            "c28139ce2d85b57f59426dd1050ba4683192b89cf5407940b4cd514cfa8cc68d"
        ),
        "validate_r6_v2_analysis_manifest_v1": (
            "8debb34f334a7274de1e863eed968939b98bc8894e0b612481a1e14603509ab4"
        ),
        "prepare_r6_v2_analysis_release_v1": (
            "8328d65002cbe072fd4c3ac60b9b7d0e658413cb10ca6e8ea29a2d336db42c38"
        ),
        "derive_r6_v2_book_catalog_v1": (
            "836c4fe50c79428201930fb40c162f6ee5465bab6db4eaee331cf49dc7f31404"
        ),
        "build_r6_v2_mechanics_result_v1": (
            "e2441f41af5caba2c407d43d5a0b6f4c0b851797081fab5ff988b6dfdc12ed23"
        ),
        "validate_r6_v2_mechanics_result_v1": (
            "5ecdd7fb8d4e055d172ffa0401f561c9eda6f193a86507b0c7b95c5517981641"
        ),
        "run_r6_v2_analysis_slate_v1": (
            "9912f6197ee6d6fdd090daba202a8f308d96aee63d1a06e440f97f1e9ca09fbd"
        ),
        "_execute_scientific_replay_v1": (
            "4cd7996e922a04e8fc78d8d79ba95495c02c474db46775ff67ea56b4385fee21"
        ),
        "verify_r6_v2_analysis_slate_v1": (
            "23e81e64e1e3b92325eecd00ad2112c51a3f619a86d3077a4cc0263743c6a1c7"
        ),
        "build_r6_v2_verifier_result_v1": (
            "b75b71d9458c338db9a4e4eba7314b649f179f5d523bc7a57a9d7af916ad9a06"
        ),
        "validate_r6_v2_verifier_result_v1": (
            "dcedb9c28fdfa16c0f3f77dc15c33183b553606a0dc7e009dbf7fec27926b553"
        ),
        "build_source_blocked_slate_acceptance_v1": (
            "6c7f3271bc6e73bbe49ee0d2ad75f20a6897e12717a08f25d83a78a96adca814"
        ),
        "validate_source_blocked_slate_acceptance_v1": (
            "8655a6f9d92a1940253a76c5273cc926aee93da7b8e1a39e38960fa5bb4c890d"
        ),
        "build_source_blocked_panel_completion_v1": (
            "bac3df7f63a4b0048833a82fb8cd23ebda3da62e30d64a2c7768bceacaa39c57"
        ),
        "_acceptance_dependencies": (
            "d8b4870135c94af6bc572fc849f17bdfba2d3f24096a530714ca013228b67092"
        ),
        "_validate_retained_acceptance_shell_v1": (
            "c2910624e6fb0d545281b9fd4eb3df7dce55427cefe04b626e1d1b165e834e39"
        ),
        "_build_source_blocked_panel_completion_body_v1": (
            "38fb6c275d4b5f62572e590e9173bfd8b35dbe3eb92d7ba40c94cd920b0864b2"
        ),
        "validate_source_blocked_panel_completion_v1": (
            "bd24ecce249e6b45828de220c9d35a8e60922301c7dc9a46b3c7eec910be4da8"
        ),
        "finish_r6_v2_analysis_panel_v1": (
            "3bbcec6ba6f16d31d80a7893304a79c838e251d38760f414b2a0b7d4144335e8"
        ),
    },
    "release_cli": {
        "_load_identity": (
            "eb499a631b1b76d0cbab8fe91425eeea4a4fe4b90e00492fc7d40968a901f5e5"
        ),
        "_parser": (
            "075f233f11fb0ade4e327a56f73a2b77b31084b71cf25c5aafeed3460412e876"
        ),
        "run": (
            "aba32918c5f084b3ab3518289a0ee39dcd5c6ac002b7cf37a227f95b961b318f"
        ),
        "main": (
            "eabef4a0275e7d8e8fcde9e1a9086510f9a8e933894449ca545f77133e929433"
        ),
    },
    "upstream_execution": {
        "execute_one_slate_r6_v2": (
            "694b05a37784756b8a91f8d9f624f4645ed14020b23538b0b70ea5cfae08a3da"
        ),
    },
}

SOURCE_BLOCKER_CODES: Final = (
    "corrected-matchup-source-export-unavailable",
    "corrected-matchup-query-receipt-unavailable",
    "corrected-matchup-reopen-validator-unavailable",
    "minimum-retrospective-prior-period-evidence-not-proven",
)

_FALSE_AUTHORITY_FIELDS: Final = (
    "automatic_retry_licensed",
    "uses_realized_outcomes",
    "historical_scoring_licensed",
    "corpus_fill_licensed",
    "graph_mutation_licensed",
    "live_policy_access_licensed",
    "production_change_licensed",
    "analytical_authority",
    "r6_freeze_authority",
    "outcome_verdict_authority",
    "promotion_authority",
    "decision_authority",
)

_SHA256 = re.compile(r"[0-9a-f]{64}")
_COMMIT = re.compile(r"[0-9a-f]{40}")
_IMAGE = re.compile(r"[^\s@]+@sha256:[0-9a-f]{64}")
_SLATE_ID = re.compile(r"[a-z0-9][a-z0-9._-]*")

# This is a declarative implementation identity.  It intentionally does not
# hash this module's own bytes (which would create a self-owning manifest).
# The source commit and immutable image are bound separately by every manifest.
_RELEASE_IMPLEMENTATION_BODY: Final = {
    "schema_version": RELEASE_IMPLEMENTATION_SCHEMA,
    "implementation_id": RELEASE_IMPLEMENTATION_ID,
    "upstream_retrieval_implementation_sha256": (
        EXPECTED_UPSTREAM_IMPLEMENTATION_SHA256
    ),
    "panel_law": {
        "source": "exact-replayed-foundry-v12-combined-panel",
        "slate_count": 54,
        "lane_task_counts": [28, 26],
        "source_ordinals": "exact-0-through-53",
        "substitution_or_splice_allowed": False,
    },
    "surface_law": {
        "strategy_ids": list(STRATEGY_IDS),
        "primary_admission_ids": list(PRIMARY_ADMISSION_IDS),
        "neutral_law_id": "score-blind-size-composition-matched-v1",
        "neutral_replicates": 32,
        "fit_scope_ids": list(FIT_SCOPE_IDS),
        "books_per_scope": 46,
        "cross_fit_book_count": 230,
        "final_fit_book_count": 46,
        "books_per_slate": 276,
        "admission_cap": 200,
        "worlds_per_block": 10_000,
        "entry_budget": 80,
        "prefix_sizes": [4, 14, 80],
        "prefix_law": "first-n-of-one-immutable-rank-80",
    },
    "publication_law": {
        "mode": "create_once",
        "read_mode": "generation-content-exact-name-no-list",
        "commands": ["prepare", "run-slate", "verify-slate", "finish-panel"],
        "worker_may_publish_acceptance": False,
        "per_slate_objects": [
            "worker-mechanics-result",
            "independent-verifier-result",
            "source-blocked-acceptance-binding-verifier-result",
        ],
        "panel_finalizer_requires_all_ordered_acceptances": True,
    },
    "source_boundary": {
        "current_understood_schema": runner.MATCHUP_SOURCE_SCHEMA,
        "current_evidence_class": CURRENT_SOURCE_EVIDENCE_CLASS,
        "current_terminal": "complete-source-blocked",
        "caller_evidence_upgrade_allowed": False,
        "matchup_free_lane_authorized": False,
        "accepted_release_requires_separate_corrected_two_object_reopener": True,
    },
    "memory_law": {
        "panel_parallelism": 1,
        "one_slate_matrix_at_a_time": True,
        "release_validation_copies_score_matrix": False,
        "admission_books_consumed_in_runner_order": True,
    },
    **{field: False for field in _FALSE_AUTHORITY_FIELDS},
}

# Frozen after the declarative body above is canonicalized.  The literal is
# filled before the module is considered static-ready.
EXPECTED_RELEASE_IMPLEMENTATION_SHA256: Final = (
    "6b301b2e9c4814a83493246e6e7eda73fc1e0a6d9d49d03fc17d9f93178f7d62"
)

_UPSTREAM_FALSE_AUTHORITY_FIELDS: Final = (
    "automatic_retry_licensed",
    "uses_realized_outcomes",
    "historical_scoring_licensed",
    "corpus_fill_licensed",
    "graph_mutation_licensed",
    "live_policy_access_licensed",
    "production_change_licensed",
    "analytical_authority",
    "r6_freeze_authority",
    "promotion_authority",
    "decision_authority",
)

_PANEL_KEYS: Final = frozenset({
    "schema_version",
    "publication_mode",
    "panel_id",
    "artifact_source_authority_completion",
    "artifact_source_authority_completion_sha256",
    "lane_count",
    "lanes",
    "accepted_slate_count",
    "accepted_slates",
    "exclusions",
    "failures",
    "missing_tasks",
    "coverage",
    "automatic_retry_licensed",
    "uses_realized_outcomes",
    "historical_scoring_licensed",
    "corpus_fill_licensed",
    "graph_mutation_licensed",
    "live_policy_access_licensed",
    "production_change_licensed",
    "analytical_authority",
    "promotion_authority",
    "decision_authority",
    "panel_index_sha256",
})
_PANEL_MEMBER_KEYS: Final = frozenset({
    "slate_id",
    "lane_ordinal",
    "lane_id",
    "task_ordinal",
    "source_task_ordinal",
    "source_task_authority_sha256",
    "task_acceptance_identity",
    "carrier_identity",
    "arms",
})
_PANEL_ARM_KEYS: Final = frozenset({
    "arm_ordinal", "parameter_set_id", "result_identity",
})
_UPSTREAM_RESULT_KEYS: Final = frozenset({
    "schema_version",
    "execution_mode",
    "slate_id",
    "panel_index_identity",
    "panel_index_sha256",
    "accepted_slate_membership",
    "accepted_slate_membership_sha256",
    "task_acceptance_identity",
    "carrier_identity",
    "later_source_freeze_identity",
    "world_artifact_identities",
    "world_artifact_identity_set_sha256",
    "matchup_source_snapshot_identity",
    "matchup_source_snapshot_sha256",
    "matchup_evidence_class",
    "matchup_mechanics_only",
    "configuration",
    "verification",
    "output_hashes",
    "reconstruction_receipt",
    "matchup_summary",
    "retrieval_surface",
    *_UPSTREAM_FALSE_AUTHORITY_FIELDS,
    "task_result_sha256",
})
_MANIFEST_KEYS: Final = frozenset({
    "schema_version",
    "publication_mode",
    "manifest_id",
    "release_implementation",
    "release_implementation_sha256",
    "measured_implementation_identity",
    "measured_implementation_sha256",
    "upstream_retrieval_implementation_contract",
    "upstream_retrieval_implementation_sha256",
    "panel_index_identity",
    "panel_index_sha256",
    "panel_accepted_slates_sha256",
    "lane_terminal_identities",
    "source_member_count",
    "source_members",
    "source_members_sha256",
    "execution_lattice",
    "source_boundary",
    "source_commit_sha",
    "immutable_image",
    "output_prefix",
    "panel_completion_uri",
    *_FALSE_AUTHORITY_FIELDS,
    "execution_manifest_sha256",
})
_SOURCE_MEMBER_KEYS: Final = frozenset({
    "source_ordinal",
    "slate_id",
    "panel_member_sha256",
    "task_acceptance_identity",
    "carrier_identity",
    "matchup_source_contract_status",
    "mechanics_result_uri",
    "verifier_result_uri",
    "acceptance_uri",
})
_MECHANICS_KEYS: Final = frozenset({
    "schema_version",
    "publication_mode",
    "manifest_identity",
    "execution_manifest_sha256",
    "source_ordinal",
    "slate_id",
    "panel_member_sha256",
    "matchup_source_snapshot_identity",
    "matchup_source_snapshot_sha256",
    "matchup_evidence_class",
    "source_disposition",
    "worker_process_runtime",
    "worker_process_runtime_sha256",
    "upstream_task_result",
    "upstream_task_result_sha256",
    "book_catalog",
    "book_catalog_sha256",
    "fit_scope_count",
    "books_per_scope",
    "book_count",
    "prefix_sizes",
    "mechanics_complete",
    "accepted_release_eligible",
    *_FALSE_AUTHORITY_FIELDS,
    "mechanics_result_sha256",
})
_ACCEPTANCE_KEYS: Final = frozenset({
    "schema_version",
    "publication_mode",
    "status",
    "accepted",
    "manifest_identity",
    "execution_manifest_sha256",
    "source_ordinal",
    "slate_id",
    "panel_member_sha256",
    "mechanics_result_identity",
    "mechanics_result_sha256",
    "verifier_result_identity",
    "verifier_result_sha256",
    "worker_process_runtime",
    "worker_process_runtime_sha256",
    "verifier_process_runtime",
    "verifier_process_runtime_sha256",
    "independent_verification_replay",
    "independent_verification_replay_sha256",
    "matchup_source_snapshot_identity",
    "matchup_source_snapshot_sha256",
    "matchup_source_schema",
    "matchup_source_content_replay_verified",
    "mechanics_content_replay_verified",
    "scientific_executor_replayed",
    "carrier_source_world_reopened",
    "verification_replayed",
    "reconstruction_replayed",
    "matchup_replayed",
    "admissions_recomputed",
    "neutral_controls_recomputed",
    "training_matrices_recomputed",
    "all_seven_rank80_books_recomputed",
    "complete_276_book_lattice_verified",
    "prefix_4_14_80_replay_verified",
    "source_blocker_codes",
    "source_blocker_codes_sha256",
    "corrected_source_contract_present",
    "matchup_free_lane_authorized",
    "mechanics_complete",
    *_FALSE_AUTHORITY_FIELDS,
    "slate_acceptance_sha256",
})
_OUTPUT_HASH_KEYS: Final = frozenset({
    "compatibility_import_sha256",
    "candidate_provenance_sha256",
    "reconstruction_sha256",
    "matchup_summary_sha256",
    "retrieval_surface_sha256",
})
_VERIFICATION_KEYS: Final = frozenset({
    "panel_content_identity_verified",
    "panel_membership_binding_verified",
    "task_acceptance_content_identity_verified",
    "task_acceptance_carrier_binding_verified",
    "carrier_source_receipts_verified",
    "matchup_snapshot_content_identity_verified",
    "canonical_authoritative_dose_verified",
})
_RECONSTRUCTION_KEYS: Final = frozenset({
    "schema_version",
    "compatibility_import_sha256",
    "candidate_provenance_sha256",
    "matrix_binding",
    "verified_arm_score_hashes",
    "uses_realized_outcomes",
    "promotion_authority",
    "reconstruction_sha256",
})
_MATRIX_BINDING_KEYS: Final = frozenset({
    "schema_version",
    "slate",
    "candidate_provenance_sha256",
    "lineup_ids_sha256",
    "world_ids_sha256",
    "shape",
    "score_matrix_sha256",
    "uses_realized_outcomes",
    "matrix_binding_sha256",
})
_VERIFIED_ARM_KEYS: Final = frozenset({
    "ordinal",
    "parameter_set_id",
    "candidate_score_sha256",
    "selected_score_sha256",
    "unique_count",
    "selected_count",
    "verified",
})
_MATCHUP_SUMMARY_KEYS: Final = frozenset({
    "schema_version",
    "slate",
    "matchup_source_snapshot_sha256",
    "player_catalog_identity",
    "annotation_query_receipt_identity",
    "eligible_families",
    "qb_gate",
    "minimum_supported_players",
    "minimum_completeness",
    "lineups",
    "uses_realized_outcomes",
    "matchup_summary_sha256",
})
_MATCHUP_LINEUP_KEYS: Final = frozenset({
    "lineup_id",
    "matchup_edge_mean",
    "eligible_player_count",
    "supported_player_count",
    "supported_families",
    "annotation_completeness",
    "qualifies_for_matchup_admission",
    "missing_semantics",
})
_PROCESS_RUNTIME_KEYS: Final = frozenset({
    "schema_version",
    "role",
    "pid",
    "process_start_ticks",
    "boot_id_sha256",
    "pid_namespace_sha256",
    "python_implementation",
    "python_version",
    "python_executable_sha256",
    "python_executable_bytes",
    "measured_implementation_sha256",
    "process_runtime_sha256",
})
_VERIFICATION_REPLAY_KEYS: Final = frozenset({
    "schema_version",
    "manifest_identity",
    "execution_manifest_sha256",
    "source_ordinal",
    "slate_id",
    "panel_member_sha256",
    "mechanics_result_identity",
    "mechanics_result_sha256",
    "verifier_result_identity",
    "verifier_result_sha256",
    "worker_process_runtime_sha256",
    "verifier_process_runtime_sha256",
    "task_acceptance_identity",
    "carrier_identity",
    "later_source_freeze_identity",
    "world_artifact_identities",
    "world_artifact_identity_set_sha256",
    "matchup_source_snapshot_identity",
    "matchup_source_snapshot_sha256",
    "verification_sha256",
    "reconstruction_sha256",
    "matrix_binding_sha256",
    "matchup_summary_sha256",
    "retrieval_surface_sha256",
    "book_catalog_sha256",
    "upstream_task_result_sha256",
    "independent_reexecution_task_result_sha256",
    "exact_upstream_result_replay_verified",
    "verification_replayed",
    "reconstruction_replayed",
    "matchup_replayed",
    "admissions_recomputed",
    "neutral_controls_recomputed",
    "training_matrices_recomputed",
    "all_seven_rank80_books_recomputed",
    "uses_realized_outcomes",
    "r6_freeze_authority",
    "promotion_authority",
    "decision_authority",
    "verification_replay_sha256",
})
_VERIFIER_RESULT_KEYS: Final = frozenset({
    "schema_version",
    "publication_mode",
    "manifest_identity",
    "execution_manifest_sha256",
    "source_ordinal",
    "slate_id",
    "panel_member_sha256",
    "mechanics_result_identity",
    "mechanics_result_sha256",
    "worker_process_runtime",
    "worker_process_runtime_sha256",
    "verifier_process_runtime",
    "verifier_process_runtime_sha256",
    "matchup_source_snapshot_identity",
    "matchup_source_snapshot_sha256",
    "independently_replayed_upstream_task_result",
    "independently_replayed_upstream_task_result_sha256",
    "independently_derived_book_catalog",
    "independently_derived_book_catalog_sha256",
    "exact_upstream_result_replay_verified",
    "verification_replayed",
    "reconstruction_replayed",
    "matchup_replayed",
    "admissions_recomputed",
    "neutral_controls_recomputed",
    "training_matrices_recomputed",
    "all_seven_rank80_books_recomputed",
    *_FALSE_AUTHORITY_FIELDS,
    "verifier_result_sha256",
})

_PANEL_COMPLETION_KEYS: Final = frozenset({
    "schema_version",
    "publication_mode",
    "status",
    "manifest_identity",
    "execution_manifest_sha256",
    "panel_index_identity",
    "panel_index_sha256",
    "source_member_count",
    "ordered_acceptance_count",
    "ordered_acceptances",
    "ordered_acceptances_sha256",
    "mechanics_complete_count",
    "source_blocked_count",
    "accepted_release_count",
    "all_mechanics_complete",
    "all_sources_blocked",
    "accepted",
    "matchup_free_lane_authorized",
    "source_blocker_codes",
    "source_blocker_codes_sha256",
    *_FALSE_AUTHORITY_FIELDS,
    "panel_completion_sha256",
})
_PANEL_COMPLETION_ROW_KEYS: Final = frozenset({
    "source_ordinal",
    "slate_id",
    "panel_member_sha256",
    "acceptance_identity",
    "slate_acceptance_sha256",
    "mechanics_result_identity",
    "mechanics_result_sha256",
    "verifier_result_identity",
    "verifier_result_sha256",
    "matchup_source_snapshot_identity",
    "matchup_source_snapshot_sha256",
    "worker_process_runtime_sha256",
    "verifier_process_runtime_sha256",
    "independent_verification_replay_sha256",
    "upstream_task_result_sha256",
    "status",
    "accepted",
})


class CorpusR6V2AnalysisReleaseError(ValueError):
    """The R6-v2 release seam cannot proceed without weakening evidence."""


def _fail(message: str) -> None:
    raise CorpusR6V2AnalysisReleaseError(message)


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


def _sha(value: object, *, label: str) -> str:
    if type(value) is not str or _SHA256.fullmatch(value) is None:
        _fail(f"{label} must be one lowercase SHA-256")
    return value


def _identity(value: object, *, label: str) -> dict[str, object]:
    try:
        return batch.normalize_object_identity(value, label=label)
    except Exception as exc:
        raise CorpusR6V2AnalysisReleaseError(
            f"{label} must be generation/content-pinned"
        ) from exc


def _object_identity(value: object, *, label: str) -> ObjectIdentity:
    row = _identity(value, label=label)
    return ObjectIdentity(
        uri=str(row["uri"]),
        generation=str(row["generation"]),
        sha256=str(row["sha256"]),
        bytes=int(row["bytes"]),
    )


def _identity_key(value: object, *, label: str) -> tuple[str, str, str, int]:
    row = _identity(value, label=label)
    return (
        str(row["uri"]), str(row["generation"]), str(row["sha256"]),
        int(row["bytes"]),
    )


def _bind_identity_to_body(
    identity: object, body: Mapping[str, object], *, label: str
) -> dict[str, object]:
    retained = _identity(identity, label=f"{label} identity")
    raw = batch.canonical_json_bytes(body)
    if (
        retained["sha256"] != sha256(raw).hexdigest()
        or retained["bytes"] != len(raw)
    ):
        _fail(f"{label} identity differs from its canonical body")
    return retained


def _self_hash(
    value: Mapping[str, object], *, field: str, label: str
) -> str:
    retained = _sha(value.get(field), label=f"{label}.{field}")
    expected = batch.canonical_sha256({
        key: item for key, item in value.items() if key != field
    })
    if retained != expected:
        _fail(f"{label} self-hash differs")
    return retained


def _with_hash(body: Mapping[str, object], *, field: str) -> dict[str, object]:
    retained = dict(body)
    retained[field] = batch.canonical_sha256(retained)
    return retained


def _false_authorities(value: Mapping[str, object], *, label: str) -> None:
    if any(value.get(field) is not False for field in _FALSE_AUTHORITY_FIELDS):
        _fail(f"{label} carries forbidden authority")


def _output_prefix(value: object) -> str:
    if type(value) is not str or not value.startswith("gs://") or not value.endswith("/"):
        _fail("output prefix must be an explicit GCS prefix ending in /")
    retained = value.removeprefix("gs://")
    bucket_name, separator, object_name = retained.partition("/")
    if (
        not separator or not bucket_name or not object_name
        or "//" in retained or object_name.endswith("//")
    ):
        _fail("output prefix differs")
    return value


def _read_json(
    storage: ExactObjectStore, identity: object, *, label: str
) -> tuple[dict[str, object], dict[str, object]]:
    normalized = _identity(identity, label=f"{label} identity")
    raw = storage.read_exact(_object_identity(normalized, label=f"{label} identity"))
    if (
        type(raw) is not bytes
        or len(raw) != normalized["bytes"]
        or sha256(raw).hexdigest() != normalized["sha256"]
    ):
        _fail(f"{label} exact content identity differs")
    try:
        parsed = batch.parse_canonical_json_bytes(raw, label=label)
    except Exception as exc:
        raise CorpusR6V2AnalysisReleaseError(
            f"{label} is not canonical JSON"
        ) from exc
    return normalized, dict(_mapping(parsed, label=label))


def _read_exact_callback(storage: ExactObjectStore):
    def read_exact(value: Mapping[str, object]) -> bytes:
        return storage.read_exact(_object_identity(value, label="exact-read input"))

    return read_exact


def _publish_json(
    storage: ExactObjectStore, *, uri: str, value: Mapping[str, object]
) -> dict[str, object]:
    raw = batch.canonical_json_bytes(value)
    identity = storage.publish_create_once(uri, raw)
    normalized = _identity(identity.as_dict(), label=f"published {uri}")
    reopened = storage.read_exact(identity)
    if reopened != raw:
        _fail(f"published object {uri!r} differs on exact reopen")
    return normalized


_RELEASE_CRITICAL_CALLABLES: Final = (
    "release_implementation_contract_v1",
    "_measured_release_implementation_identity_v1",
    "_process_runtime_identity_v1",
    "_validate_current_process_runtime_identity_v1",
    "build_r6_v2_analysis_manifest_v1",
    "validate_r6_v2_analysis_manifest_v1",
    "prepare_r6_v2_analysis_release_v1",
    "derive_r6_v2_book_catalog_v1",
    "build_r6_v2_mechanics_result_v1",
    "validate_r6_v2_mechanics_result_v1",
    "run_r6_v2_analysis_slate_v1",
    "_execute_scientific_replay_v1",
    "verify_r6_v2_analysis_slate_v1",
    "build_r6_v2_verifier_result_v1",
    "validate_r6_v2_verifier_result_v1",
    "build_source_blocked_slate_acceptance_v1",
    "validate_source_blocked_slate_acceptance_v1",
    "build_source_blocked_panel_completion_v1",
    "_acceptance_dependencies",
    "_validate_retained_acceptance_shell_v1",
    "_build_source_blocked_panel_completion_body_v1",
    "validate_source_blocked_panel_completion_v1",
    "finish_r6_v2_analysis_panel_v1",
)
_CLI_CRITICAL_CALLABLES: Final = ("_load_identity", "_parser", "run", "main")
_UPSTREAM_CRITICAL_CALLABLES: Final = ("execute_one_slate_r6_v2",)
_DEPENDENCY_MODULES: Final = {
    "batch_runner": runner,
    "canonical_batch": batch,
    "exact_object_transport": transport,
    "implementation_contract": impl,
    "random_world_order": rw,
    "retrieval_runner": retrieval,
    "v12_import": v12_import,
    "v12_panel_replay": panel_index,
}
_DEPENDENCY_CRITICAL_CALLABLES: Final = {
    "batch_runner": (
        "build_fit_candidate_view",
        "validate_matchup_source_snapshot",
        "build_matchup_lineup_summaries",
        "validate_matchup_lineup_summaries",
        "_full_union_admission",
        "_matchup_admission",
        "build_score_blind_neutral_admission",
        "_select_expected_max_without_matrix_copy",
        "_run_strategy_v2",
        "_run_book",
        "_run_fit_scope_impl",
        "run_fit_scope",
        "run_retrieval_surface_v2",
        "validate_fit_scope",
        "validate_retrieval_surface_v2",
    ),
    "canonical_batch": (
        "canonical_json_bytes",
        "canonical_sha256",
        "parse_canonical_json_bytes",
        "normalize_object_identity",
    ),
    "exact_object_transport": (
        "ObjectIdentity.as_dict",
        "ExactObjectStore.read_exact",
        "ExactObjectStore.resolve_optional",
        "ExactObjectStore.publish_create_once",
        "object_identity",
        "_bind_raw",
        "GoogleCloudObjectStore._parts",
        "GoogleCloudObjectStore.read_exact",
        "GoogleCloudObjectStore.resolve_optional",
        "GoogleCloudObjectStore.publish_create_once",
    ),
    "implementation_contract": (
        "frozen_retrieval_v2_implementation_contract_v1",
        "validate_retrieval_v2_implementation_contract_v1",
    ),
    "random_world_order": (
        "canonical_identity",
        "_exact_world_order",
    ),
    "retrieval_runner": (
        "frozen_retrieval_strategies_v2",
        "validate_retrieval_strategy_v2",
        "_select_coverage",
        "_select_ladder",
        "_select_mean",
        "_select_expected_max",
        "_select_block_supported_ladder",
        "_select_blockmin_ladder",
        "_run_strategy",
    ),
    "v12_import": (
        "canonical_lineup_id",
        "reopen_v12_task",
        "reconstruct_v12_task",
    ),
    "v12_panel_replay": (
        "derive_v12_lane_input",
        "validate_v12_panel_index",
        "reopen_v12_panel_index",
    ),
}


def _dependency_constant_values_v1() -> dict[str, dict[str, object]]:
    """Return every direct result/security-critical live constant as JSON."""
    return {
        "batch_runner": {
            "schemas": [
                runner.RUNNER_SCHEMA,
                runner.SCOPE_SCHEMA,
                runner.ADMISSION_SCHEMA,
                runner.BOOK_SCHEMA,
                runner.MATCHUP_SUMMARY_SCHEMA,
                runner.MATCHUP_SOURCE_SCHEMA,
            ],
            "admission_ids": [
                runner.FULL_UNION_ADMISSION_ID,
                runner.MATCHUP_ADMISSION_ID,
                runner.NEUTRAL_LAW_ID,
            ],
            "admission_m": runner.DEFAULT_ADMISSION_M,
            "neutral_replicates": runner.DEFAULT_NEUTRAL_REPLICATES,
            "entry_budget": runner.ENTRY_BUDGET,
            "authoritative_dose": runner.AUTHORITATIVE_DOSE,
            "thresholds": [list(row) for row in runner.THRESHOLDS],
            "eligible_matchup_families": list(runner.ELIGIBLE_MATCHUP_FAMILIES),
        },
        "canonical_batch": {
            "task_result_schema": batch.TASK_RESULT_SCHEMA,
            "publication_mode": batch.PUBLICATION_MODE,
            "parameter_set_order": list(batch.PARAMETER_SET_ORDER),
            "source_receipt_roles": list(batch.SOURCE_RECEIPT_ROLES),
            "task_world_source_roles": list(batch.TASK_WORLD_SOURCE_ROLES),
            "worlds_per_block": batch.WORLDS_PER_BLOCK,
            "selected_entry_budget": batch.SELECTED_ENTRY_BUDGET,
        },
        "exact_object_transport": {
            "object_identity_fields": ["uri", "generation", "sha256", "bytes"],
            "read_law": "exact-generation-content-bound",
            "publication_law": "create-once-if-generation-match-zero-exact-reopen",
            "list_operation_available": False,
        },
        "implementation_contract": {
            "schema": impl.CONTRACT_SCHEMA,
            "implementation_id": impl.IMPLEMENTATION_ID,
            "source_module_logical_id": impl.SOURCE_MODULE_LOGICAL_ID,
            "source_file_name": impl.SOURCE_FILE_NAME,
            "source_file_bytes": impl.SOURCE_FILE_BYTES,
            "source_file_sha256": impl.SOURCE_FILE_SHA256,
            "entry_budget": impl.ENTRY_BUDGET,
            "world_blocks": list(impl.WORLD_BLOCKS),
            "worlds_per_block": impl.WORLDS_PER_BLOCK,
            "primary_event_threshold": impl.PRIMARY_EVENT_THRESHOLD,
            "primary_event_operator": impl.PRIMARY_EVENT_OPERATOR,
        },
        "one_slate_execution": {
            "result_schema": execution.RESULT_SCHEMA,
            "matchup_evidence_classes": list(execution.MATCHUP_EVIDENCE_CLASSES),
            "retrospective_evidence": execution.MATCHUP_EVIDENCE_RETROSPECTIVE,
        },
        "random_world_order": {
            "protocol_id": rw.PROTOCOL_ID,
            "protocol_document_sha256": rw.PROTOCOL_DOCUMENT_SHA256,
            "world_blocks": list(rw.WORLD_BLOCKS),
            "worlds_per_block": rw.WORLDS_PER_BLOCK,
            "fold_specs": [
                {
                    "name": spec.name,
                    "construction_blocks": list(spec.construction_blocks),
                    "evaluation_blocks": list(spec.evaluation_blocks),
                    "reservoir_per_block": spec.reservoir_per_block,
                    "active_per_block": spec.active_per_block,
                }
                for spec in rw.FOLD_SPECS
            ],
        },
        "retrieval_runner": {
            "strategy_schema": retrieval.STRATEGY_SCHEMA,
            "world_blocks": list(retrieval.WORLD_BLOCKS),
            "worlds_per_block": retrieval.WORLDS_PER_BLOCK,
            "score_unit": retrieval.SCORE_UNIT,
            "primary_event_operator": retrieval.PRIMARY_EVENT_OPERATOR,
            "primary_event_threshold": retrieval.PRIMARY_EVENT_THRESHOLD,
            "default_entry_budget": retrieval.DEFAULT_ENTRY_BUDGET,
            "strategies": retrieval.frozen_retrieval_strategies_v2(
                retrieval.DEFAULT_ENTRY_BUDGET
            ),
        },
        "v12_import": {
            "lineup_id_schema": v12_import.LINEUP_ID_SCHEMA,
            "provenance_schema": v12_import.PROVENANCE_SCHEMA,
            "matrix_binding_schema": v12_import.MATRIX_BINDING_SCHEMA,
            "reconstruction_schema": v12_import.RECONSTRUCTION_SCHEMA,
            "task_acceptance_schema": v12_import.TASK_ACCEPTANCE_SCHEMA,
        },
        "v12_panel_replay": {
            "panel_index_schema": panel_index.PANEL_INDEX_SCHEMA,
            "publication_mode": panel_index.PUBLICATION_MODE,
            "source_task_count": panel_index.V12_SOURCE_TASK_COUNT,
            "lane_lattice": [dict(row) for row in panel_index.V12_LANE_LATTICE],
        },
    }


def _source_callable_measurements(
    path: Path, names: Sequence[str], *, label: str
) -> list[dict[str, object]]:
    try:
        raw = path.read_bytes()
        text = raw.decode("utf-8")
        tree = ast.parse(text, filename=str(path))
    except (OSError, UnicodeDecodeError, SyntaxError) as exc:
        raise CorpusR6V2AnalysisReleaseError(
            f"cannot measure {label} source"
        ) from exc
    def source_node(name: str) -> ast.FunctionDef | ast.AsyncFunctionDef:
        parts = name.split(".")
        nodes: Sequence[ast.stmt] = tree.body
        retained: ast.AST | None = None
        for ordinal, part in enumerate(parts):
            candidates = [
                node
                for node in nodes
                if isinstance(
                    node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)
                )
                and node.name == part
            ]
            if len(candidates) != 1:
                _fail(f"{label} critical callable {name!r} differs")
            retained = candidates[0]
            if ordinal < len(parts) - 1:
                if not isinstance(retained, ast.ClassDef):
                    _fail(f"{label} critical callable {name!r} differs")
                nodes = retained.body
        if not isinstance(retained, (ast.FunctionDef, ast.AsyncFunctionDef)):
            _fail(f"{label} critical callable {name!r} differs")
        return retained

    lines = text.splitlines(keepends=True)
    rows: list[dict[str, object]] = []
    for name in names:
        node = source_node(name)
        if node.end_lineno is None:
            _fail(f"{label} callable {name!r} has no bounded source span")
        start_line = min(
            [node.lineno, *(row.lineno for row in node.decorator_list)]
        )
        source = "".join(lines[start_line - 1 : node.end_lineno]).encode("utf-8")
        rows.append({
            "callable": name,
            "source_bytes": len(source),
            "source_sha256": sha256(source).hexdigest(),
        })
    return rows


def _file_measurement(path: Path, *, role: str) -> dict[str, object]:
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise CorpusR6V2AnalysisReleaseError(
            f"cannot measure {role} bytes"
        ) from exc
    if not raw:
        _fail(f"{role} source is empty")
    return {
        "role": role,
        "basename": path.name,
        "resolved_path": str(path.resolve()),
        "bytes": len(raw),
        "sha256": sha256(raw).hexdigest(),
    }


def _normalized_release_module_sha256(raw: bytes) -> str:
    literal = EXPECTED_RELEASE_MODULE_NORMALIZED_SHA256.encode("ascii")
    if raw.count(literal) != 1:
        _fail("release module normalized-hash literal occurrence differs")
    normalized = raw.replace(
        literal, b"<EXPECTED_RELEASE_MODULE_NORMALIZED_SHA256>"
    )
    return sha256(normalized).hexdigest()


def _measured_release_implementation_identity_v1() -> dict[str, object]:
    """Measure the exact executable release seam without caller assertions."""
    release_path = Path(__file__).resolve()
    repository_root = release_path.parents[3]
    cli_path = repository_root / "scripts" / "run_corpus_r6_v2_analysis_release.py"
    upstream_path = Path(execution.__file__).resolve()
    python_path = Path(sys.executable).resolve()
    try:
        python_raw = python_path.read_bytes()
    except OSError as exc:
        raise CorpusR6V2AnalysisReleaseError(
            "cannot measure Python runtime executable"
        ) from exc
    upstream_contract = impl.frozen_retrieval_v2_implementation_contract_v1()
    upstream_identity = _mapping(
        upstream_contract.get("contract_identity"), label="upstream contract identity"
    )
    upstream_runtime = dict(
        _mapping(upstream_identity.get("runtime_identity"), label="upstream runtime")
    )
    runtime_paths = dict(_mapping(
        upstream_contract.get("diagnostics"), label="upstream runtime paths"
    ))
    if (
        upstream_runtime.get("python_executable_sha256")
        != sha256(python_raw).hexdigest()
        or upstream_runtime.get("python_executable_bytes") != len(python_raw)
    ):
        _fail("release Python runtime differs from the frozen upstream runtime")
    release_module = _file_measurement(release_path, role="release-module")
    release_raw = release_path.read_bytes()
    release_module["normalized_sha256"] = _normalized_release_module_sha256(
        release_raw
    )
    release_cli = _file_measurement(cli_path, role="release-cli")
    upstream_module = _file_measurement(
        upstream_path, role="upstream-one-slate-execution-module"
    )
    dependency_modules = {
        name: _file_measurement(
            Path(module.__file__).resolve(), role=f"dependency-{name}"
        )
        for name, module in _DEPENDENCY_MODULES.items()
    }
    observed_dependency_module_hashes = {
        name: str(row["sha256"])
        for name, row in dependency_modules.items()
    }
    dependency_callable_sources = {
        name: _source_callable_measurements(
            Path(_DEPENDENCY_MODULES[name].__file__).resolve(),
            _DEPENDENCY_CRITICAL_CALLABLES[name],
            label=f"dependency {name}",
        )
        for name in _DEPENDENCY_MODULES
    }
    observed_dependency_callable_hashes = {
        group: {
            str(row["callable"]): str(row["source_sha256"])
            for row in rows
        }
        for group, rows in dependency_callable_sources.items()
    }
    dependency_constants = _dependency_constant_values_v1()
    observed_dependency_constant_hashes = {
        name: batch.canonical_sha256(value)
        for name, value in dependency_constants.items()
    }
    python_runtime_file = _file_measurement(
        Path(str(runtime_paths["absolute_python_executable_path"])).resolve(),
        role="python-runtime-executable",
    )
    numpy_runtime_file = _file_measurement(
        Path(str(runtime_paths["absolute_numpy_core_binary_path"])).resolve(),
        role="numpy-core-runtime-binary",
    )
    if (
        python_runtime_file["sha256"]
        != upstream_runtime.get("python_executable_sha256")
        or python_runtime_file["bytes"]
        != upstream_runtime.get("python_executable_bytes")
        or numpy_runtime_file["sha256"]
        != upstream_runtime.get("numpy_core_binary_sha256")
        or numpy_runtime_file["bytes"]
        != upstream_runtime.get("numpy_core_binary_bytes")
        or Path(str(runtime_paths["absolute_source_path"])).resolve()
        != Path(retrieval.__file__).resolve()
    ):
        _fail("measured runtime path/content identity differs")
    callable_sources = {
        "release_module": _source_callable_measurements(
            release_path,
            _RELEASE_CRITICAL_CALLABLES,
            label="release module",
        ),
        "release_cli": _source_callable_measurements(
            cli_path, _CLI_CRITICAL_CALLABLES, label="release CLI"
        ),
        "upstream_execution": _source_callable_measurements(
            upstream_path,
            _UPSTREAM_CRITICAL_CALLABLES,
            label="upstream execution module",
        ),
    }
    observed_callable_hashes = {
        group: {str(row["callable"]): str(row["source_sha256"]) for row in rows}
        for group, rows in callable_sources.items()
    }
    if (
        release_module["normalized_sha256"]
        != EXPECTED_RELEASE_MODULE_NORMALIZED_SHA256
        or release_cli["sha256"] != EXPECTED_RELEASE_CLI_SHA256
        or upstream_module["sha256"]
        != EXPECTED_UPSTREAM_EXECUTION_MODULE_SHA256
        or observed_callable_hashes
        != EXPECTED_CRITICAL_CALLABLE_SOURCE_SHA256
        or observed_dependency_module_hashes
        != EXPECTED_DEPENDENCY_MODULE_SHA256
        or observed_dependency_callable_hashes
        != EXPECTED_DEPENDENCY_CALLABLE_SOURCE_SHA256
        or observed_dependency_constant_hashes
        != EXPECTED_DEPENDENCY_CONSTANT_SHA256
    ):
        _fail("release/transitive dependency literal identity drifted")
    body = {
        "schema_version": MEASURED_IMPLEMENTATION_SCHEMA,
        "release_module": release_module,
        "release_cli": release_cli,
        "upstream_execution_module": upstream_module,
        "critical_callable_sources": callable_sources,
        "critical_callable_source_sha256s": observed_callable_hashes,
        "dependency_modules": dependency_modules,
        "dependency_module_sha256s": observed_dependency_module_hashes,
        "dependency_callable_sources": dependency_callable_sources,
        "dependency_callable_source_sha256s": (
            observed_dependency_callable_hashes
        ),
        "dependency_constants": dependency_constants,
        "dependency_constant_sha256s": observed_dependency_constant_hashes,
        "runtime_paths": runtime_paths,
        "runtime_files": {
            "python": python_runtime_file,
            "numpy_core": numpy_runtime_file,
        },
        "runtime_identity": upstream_runtime,
        "upstream_retrieval_implementation_sha256": (
            EXPECTED_UPSTREAM_IMPLEMENTATION_SHA256
        ),
        "caller_source_commit_or_image_can_authorize_drift": False,
        **{field: False for field in _FALSE_AUTHORITY_FIELDS},
    }
    return _with_hash(body, field="measured_implementation_sha256")


def _process_start_ticks(pid: int) -> int:
    try:
        raw = Path(f"/proc/{pid}/stat").read_text(encoding="utf-8")
        suffix = raw.rsplit(") ", 1)[1].split()
        value = int(suffix[19])
    except (OSError, ValueError, IndexError) as exc:
        raise CorpusR6V2AnalysisReleaseError(
            "cannot measure process start identity"
        ) from exc
    if value < 1:
        _fail("process start identity differs")
    return value


def _boot_id_sha256() -> str:
    try:
        value = Path("/proc/sys/kernel/random/boot_id").read_text(
            encoding="utf-8"
        ).strip()
    except OSError as exc:
        raise CorpusR6V2AnalysisReleaseError(
            "cannot measure host boot identity"
        ) from exc
    if not value:
        _fail("host boot identity is empty")
    return sha256(value.encode("utf-8")).hexdigest()


def _pid_namespace_sha256() -> str:
    try:
        value = os.readlink("/proc/self/ns/pid")
    except OSError as exc:
        raise CorpusR6V2AnalysisReleaseError(
            "cannot measure process PID namespace"
        ) from exc
    if not value:
        _fail("process PID namespace is empty")
    return sha256(value.encode("utf-8")).hexdigest()


def _process_runtime_identity_v1(*, role: str) -> dict[str, object]:
    if role not in {"run-slate-worker", "verify-slate-verifier"}:
        _fail("process runtime role differs")
    measured = _measured_release_implementation_identity_v1()
    runtime = _mapping(measured["runtime_identity"], label="measured runtime")
    pid = os.getpid()
    body = {
        "schema_version": PROCESS_RUNTIME_SCHEMA,
        "role": role,
        "pid": pid,
        "process_start_ticks": _process_start_ticks(pid),
        "boot_id_sha256": _boot_id_sha256(),
        "pid_namespace_sha256": _pid_namespace_sha256(),
        "python_implementation": platform.python_implementation(),
        "python_version": platform.python_version(),
        "python_executable_sha256": runtime["python_executable_sha256"],
        "python_executable_bytes": runtime["python_executable_bytes"],
        "measured_implementation_sha256": measured[
            "measured_implementation_sha256"
        ],
    }
    return _with_hash(body, field="process_runtime_sha256")


def _validate_process_runtime_identity_v1(
    value: object, *, role: str
) -> dict[str, object]:
    item = dict(_mapping(value, label=f"{role} process runtime"))
    _exact_keys(item, _PROCESS_RUNTIME_KEYS, label=f"{role} process runtime")
    _self_hash(
        item,
        field="process_runtime_sha256",
        label=f"{role} process runtime",
    )
    measured = _measured_release_implementation_identity_v1()
    runtime = _mapping(measured["runtime_identity"], label="measured runtime")
    if (
        item.get("schema_version") != PROCESS_RUNTIME_SCHEMA
        or item.get("role") != role
        or type(item.get("pid")) is not int
        or int(item["pid"]) < 1
        or type(item.get("process_start_ticks")) is not int
        or int(item["process_start_ticks"]) < 1
        or _SHA256.fullmatch(str(item.get("boot_id_sha256"))) is None
        or _SHA256.fullmatch(str(item.get("pid_namespace_sha256"))) is None
        or item.get("python_implementation") != platform.python_implementation()
        or item.get("python_version") != platform.python_version()
        or item.get("python_executable_sha256")
        != runtime.get("python_executable_sha256")
        or item.get("python_executable_bytes")
        != runtime.get("python_executable_bytes")
        or item.get("measured_implementation_sha256")
        != measured.get("measured_implementation_sha256")
    ):
        _fail(f"{role} process/runtime identity differs")
    return item


def _process_instance_key(
    value: Mapping[str, object]
) -> tuple[str, str, int, int]:
    return (
        str(value["boot_id_sha256"]),
        str(value["pid_namespace_sha256"]),
        int(value["pid"]),
        int(value["process_start_ticks"]),
    )


def _validate_current_process_runtime_identity_v1(
    value: object, *, role: str
) -> dict[str, object]:
    retained = _validate_process_runtime_identity_v1(value, role=role)
    current = _process_runtime_identity_v1(role=role)
    if batch.canonical_json_bytes(retained) != batch.canonical_json_bytes(current):
        _fail(f"{role} claimed process tuple differs from /proc/current runtime")
    return retained


def release_implementation_contract_v1() -> dict[str, object]:
    """Return the literal release-law identity after dependency drift guards."""
    retained = batch.canonical_sha256(_RELEASE_IMPLEMENTATION_BODY)
    if retained != EXPECTED_RELEASE_IMPLEMENTATION_SHA256:
        _fail("R6-v2 release implementation identity drifted")
    try:
        upstream = impl.validate_retrieval_v2_implementation_contract_v1(
            impl.frozen_retrieval_v2_implementation_contract_v1()
        )
    except Exception as exc:
        raise CorpusR6V2AnalysisReleaseError(
            "public R6-v2 retrieval implementation drifted"
        ) from exc
    if (
        upstream.get("implementation_contract_sha256")
        != EXPECTED_UPSTREAM_IMPLEMENTATION_SHA256
    ):
        _fail("public R6-v2 implementation hash differs from the release literal")
    measured = _measured_release_implementation_identity_v1()
    return {
        "release_implementation": dict(_RELEASE_IMPLEMENTATION_BODY),
        "release_implementation_sha256": retained,
        "measured_implementation_identity": measured,
        "measured_implementation_sha256": measured[
            "measured_implementation_sha256"
        ],
        # Absolute paths in the upstream wrapper are diagnostic-only.  The
        # portable manifest binds only its exact hashed contract identity.
        "upstream_retrieval_implementation_contract": dict(
            _mapping(upstream["contract_identity"], label="upstream identity")
        ),
        "upstream_retrieval_implementation_sha256": str(
            upstream["implementation_contract_sha256"]
        ),
    }


def _validate_panel_body(value: object) -> tuple[dict[str, object], list[dict[str, object]]]:
    item = dict(_mapping(value, label="published v12 panel index"))
    _exact_keys(item, _PANEL_KEYS, label="published v12 panel index")
    if (
        item.get("schema_version") != panel_index.PANEL_INDEX_SCHEMA
        or item.get("publication_mode") != panel_index.PUBLICATION_MODE
        or item.get("lane_count") != 2
        or item.get("accepted_slate_count") != AUTHORITATIVE_SLATE_COUNT
        or item.get("exclusions") != []
        or item.get("failures") != []
        or item.get("missing_tasks") != []
    ):
        _fail("published v12 panel is not the complete 54-slate authority")
    for field in (
        "automatic_retry_licensed", "uses_realized_outcomes",
        "historical_scoring_licensed", "corpus_fill_licensed",
        "graph_mutation_licensed", "live_policy_access_licensed",
        "production_change_licensed", "analytical_authority",
        "promotion_authority", "decision_authority",
    ):
        if item.get(field) is not False:
            _fail("published v12 panel carries forbidden authority")
    _self_hash(item, field="panel_index_sha256", label="published v12 panel")
    coverage = _mapping(item.get("coverage"), label="panel coverage")
    if coverage != {
        "expected_task_count": 54,
        "accepted_task_count": 54,
        "excluded_task_count": 0,
        "failed_task_count": 0,
        "missing_task_count": 0,
        "complete": True,
    }:
        _fail("published v12 panel coverage differs from exact 54/54")
    lanes = list(_sequence(item.get("lanes"), label="panel lanes"))
    if len(lanes) != 2:
        _fail("published v12 panel lane count differs")
    for lane_ordinal, raw_lane in enumerate(lanes):
        lane = _mapping(raw_lane, label=f"panel lane[{lane_ordinal}]")
        if (
            lane.get("lane_ordinal") != lane_ordinal
            or lane.get("lane_id") != panel_index.V12_LANE_LATTICE[lane_ordinal][
                "lane_id"
            ]
            or lane.get("expected_task_count") != LANE_TASK_COUNTS[lane_ordinal]
            or lane.get("accepted_task_count") != LANE_TASK_COUNTS[lane_ordinal]
            or lane.get("accepted_task_ordinals")
            != list(range(LANE_TASK_COUNTS[lane_ordinal]))
            or lane.get("source_task_offset")
            != panel_index.V12_LANE_LATTICE[lane_ordinal]["source_task_offset"]
            or lane.get("complete") is not True
        ):
            _fail(f"published v12 panel lane[{lane_ordinal}] lattice differs")
        _identity(
            lane.get("terminal_receipt_identity"),
            label=f"panel lane[{lane_ordinal}] terminal",
        )
    raw_members = _sequence(item.get("accepted_slates"), label="panel members")
    if len(raw_members) != AUTHORITATIVE_SLATE_COUNT:
        _fail("published v12 panel member count differs")
    members: list[dict[str, object]] = []
    seen_slates: set[str] = set()
    seen_acceptances: set[tuple[str, str, str, int]] = set()
    seen_carriers: set[tuple[str, str, str, int]] = set()
    seen_arm_results: set[tuple[str, str, str, int]] = set()
    for source_ordinal, raw_member in enumerate(raw_members):
        member = dict(_mapping(raw_member, label=f"panel member[{source_ordinal}]"))
        _exact_keys(member, _PANEL_MEMBER_KEYS, label=f"panel member[{source_ordinal}]")
        slate_id = member.get("slate_id")
        expected_lane = 0 if source_ordinal < 28 else 1
        expected_task = source_ordinal if expected_lane == 0 else source_ordinal - 28
        if (
            type(slate_id) is not str
            or _SLATE_ID.fullmatch(slate_id) is None
            or slate_id in seen_slates
            or member.get("source_task_ordinal") != source_ordinal
            or member.get("lane_ordinal") != expected_lane
            or member.get("lane_id")
            != panel_index.V12_LANE_LATTICE[expected_lane]["lane_id"]
            or member.get("task_ordinal") != expected_task
        ):
            _fail(f"panel member[{source_ordinal}] identity/order differs")
        seen_slates.add(slate_id)
        acceptance_key = _identity_key(
            member.get("task_acceptance_identity"),
            label=f"panel member[{source_ordinal}] task acceptance",
        )
        carrier_key = _identity_key(
            member.get("carrier_identity"),
            label=f"panel member[{source_ordinal}] carrier",
        )
        if acceptance_key in seen_acceptances or carrier_key in seen_carriers:
            _fail("panel task acceptance/carrier identities repeat")
        seen_acceptances.add(acceptance_key)
        seen_carriers.add(carrier_key)
        arms = list(_sequence(member.get("arms"), label=f"panel member[{source_ordinal}] arms"))
        if len(arms) != 7:
            _fail(f"panel member[{source_ordinal}] does not bind seven arms")
        for arm_ordinal, raw_arm in enumerate(arms):
            arm = _mapping(raw_arm, label=f"panel member[{source_ordinal}] arm[{arm_ordinal}]")
            _exact_keys(arm, _PANEL_ARM_KEYS, label="panel arm")
            if (
                arm.get("arm_ordinal") != arm_ordinal
                or arm.get("parameter_set_id") != batch.PARAMETER_SET_ORDER[arm_ordinal]
            ):
                _fail("panel arm order/identity differs")
            arm_key = _identity_key(
                arm.get("result_identity"), label="panel arm result"
            )
            if arm_key in seen_arm_results:
                _fail("panel arm result identity repeats")
            seen_arm_results.add(arm_key)
        members.append(member)
    return item, members


def _source_members(
    panel_members: Sequence[Mapping[str, object]], *, output_prefix: str
) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    uris: set[str] = set()
    for source_ordinal, raw_member in enumerate(panel_members):
        member = dict(raw_member)
        slate_id = str(member["slate_id"])
        member_prefix = f"{output_prefix}slates/{source_ordinal:02d}-{slate_id}/"
        result_uri = f"{member_prefix}mechanics-result.json"
        verifier_result_uri = f"{member_prefix}verifier-result.json"
        acceptance_uri = f"{member_prefix}source-blocked-acceptance.json"
        if (
            result_uri in uris
            or verifier_result_uri in uris
            or acceptance_uri in uris
        ):
            _fail("deterministic per-slate output URIs repeat")
        uris.update((result_uri, verifier_result_uri, acceptance_uri))
        rows.append({
            "source_ordinal": source_ordinal,
            "slate_id": slate_id,
            "panel_member_sha256": batch.canonical_sha256(member),
            "task_acceptance_identity": _identity(
                member["task_acceptance_identity"],
                label=f"source member[{source_ordinal}] task acceptance",
            ),
            "carrier_identity": _identity(
                member["carrier_identity"],
                label=f"source member[{source_ordinal}] carrier",
            ),
            "matchup_source_contract_status": (
                "not-bound-corrected-source-unavailable"
            ),
            "mechanics_result_uri": result_uri,
            "verifier_result_uri": verifier_result_uri,
            "acceptance_uri": acceptance_uri,
        })
    return rows


def build_r6_v2_analysis_manifest_v1(
    *,
    panel_index_identity: object,
    validated_panel_index: Mapping[str, object],
    lane_terminal_identities: Sequence[object],
    source_commit_sha: str,
    immutable_image: str,
    output_prefix: str,
) -> dict[str, object]:
    """Build the immutable R6-v2 mechanics/source-blocked panel manifest."""
    release_contract = release_implementation_contract_v1()
    panel, panel_members = _validate_panel_body(validated_panel_index)
    retained_panel_identity = _bind_identity_to_body(
        panel_index_identity, panel, label="published panel index"
    )
    if type(source_commit_sha) is not str or _COMMIT.fullmatch(source_commit_sha) is None:
        _fail("source commit must be one lowercase 40-hex commit")
    if type(immutable_image) is not str or _IMAGE.fullmatch(immutable_image) is None:
        _fail("immutable image must be digest-pinned")
    retained_prefix = _output_prefix(output_prefix)
    raw_terminals = list(_sequence(lane_terminal_identities, label="lane terminals"))
    if len(raw_terminals) != 2:
        _fail("manifest requires exactly two lane terminal identities")
    terminals = [
        _identity(value, label=f"lane terminal[{ordinal}]")
        for ordinal, value in enumerate(raw_terminals)
    ]
    panel_lanes = list(_sequence(panel["lanes"], label="panel lanes"))
    if terminals != [
        _identity(
            _mapping(panel_lanes[ordinal], label="panel lane").get(
                "terminal_receipt_identity"
            ),
            label=f"panel lane[{ordinal}] terminal",
        )
        for ordinal in range(2)
    ]:
        _fail("manifest lane terminals differ from the published panel")
    members = _source_members(panel_members, output_prefix=retained_prefix)
    execution_lattice = {
        "strategy_ids": list(STRATEGY_IDS),
        "strategy_count": 7,
        "primary_admission_ids": list(PRIMARY_ADMISSION_IDS),
        "neutral_law_id": runner.NEUTRAL_LAW_ID,
        "neutral_replicates": NEUTRAL_REPLICATES,
        "fit_scope_ids": list(FIT_SCOPE_IDS),
        "heldout_blocks": list(rw.WORLD_BLOCKS),
        "distinct_all_block_final_fit": True,
        "books_per_scope": BOOKS_PER_SCOPE,
        "cross_fit_book_count": CROSS_FIT_BOOK_COUNT,
        "final_fit_book_count": FINAL_FIT_BOOK_COUNT,
        "books_per_slate": BOOKS_PER_SLATE,
        "entry_budget": ENTRY_BUDGET,
        "prefix_sizes": list(PREFIX_SIZES),
        "prefix_law": "first-n-of-one-immutable-rank-80",
        "admission_cap": ADMISSION_CAP,
        "worlds_per_block": WORLDS_PER_BLOCK,
        "neutral_seed_root": NEUTRAL_SEED_ROOT,
        "panel_parallelism": 1,
    }
    source_boundary = {
        "current_matchup_source_schema": runner.MATCHUP_SOURCE_SCHEMA,
        "current_evidence_class": CURRENT_SOURCE_EVIDENCE_CLASS,
        "current_source_disposition": CURRENT_SOURCE_DISPOSITION,
        "corrected_two_object_source_bound": False,
        "caller_evidence_upgrade_allowed": False,
        "matchup_free_lane_authorized": False,
        "only_permitted_terminal_status": PANEL_STATUS,
        "source_blocker_codes": list(SOURCE_BLOCKER_CODES),
    }
    manifest_seed = {
        "panel_index_identity": retained_panel_identity,
        "panel_index_sha256": panel["panel_index_sha256"],
        "release_implementation_sha256": release_contract[
            "release_implementation_sha256"
        ],
        "measured_implementation_sha256": release_contract[
            "measured_implementation_sha256"
        ],
        "source_commit_sha": source_commit_sha,
        "immutable_image": immutable_image,
        "output_prefix": retained_prefix,
    }
    body = {
        "schema_version": MANIFEST_SCHEMA,
        "publication_mode": PUBLICATION_MODE,
        "manifest_id": "r6-v2:" + batch.canonical_sha256(manifest_seed),
        **release_contract,
        "panel_index_identity": retained_panel_identity,
        "panel_index_sha256": panel["panel_index_sha256"],
        "panel_accepted_slates_sha256": batch.canonical_sha256(panel_members),
        "lane_terminal_identities": terminals,
        "source_member_count": len(members),
        "source_members": members,
        "source_members_sha256": batch.canonical_sha256(members),
        "execution_lattice": execution_lattice,
        "source_boundary": source_boundary,
        "source_commit_sha": source_commit_sha,
        "immutable_image": immutable_image,
        "output_prefix": retained_prefix,
        "panel_completion_uri": f"{retained_prefix}panel-completion.json",
        **{field: False for field in _FALSE_AUTHORITY_FIELDS},
    }
    return _with_hash(body, field="execution_manifest_sha256")


def validate_r6_v2_analysis_manifest_v1(
    value: object, *, exact_panel_index: Mapping[str, object]
) -> dict[str, object]:
    item = dict(_mapping(value, label="R6-v2 analysis manifest"))
    _exact_keys(item, _MANIFEST_KEYS, label="R6-v2 analysis manifest")
    if (
        item.get("schema_version") != MANIFEST_SCHEMA
        or item.get("publication_mode") != PUBLICATION_MODE
        or item.get("source_member_count") != AUTHORITATIVE_SLATE_COUNT
        or item.get("panel_completion_uri")
        != f"{item.get('output_prefix')}panel-completion.json"
    ):
        _fail("R6-v2 analysis manifest schema/count/path differs")
    _false_authorities(item, label="R6-v2 analysis manifest")
    _self_hash(
        item, field="execution_manifest_sha256", label="R6-v2 analysis manifest"
    )
    current_release_contract = release_implementation_contract_v1()
    if item.get("release_implementation") != _RELEASE_IMPLEMENTATION_BODY:
        _fail("release implementation body differs from the frozen literal")
    if (
        item.get("release_implementation_sha256")
        != EXPECTED_RELEASE_IMPLEMENTATION_SHA256
        or item.get("upstream_retrieval_implementation_sha256")
        != EXPECTED_UPSTREAM_IMPLEMENTATION_SHA256
    ):
        _fail("release/upstream implementation identity differs")
    if (
        item.get("measured_implementation_identity")
        != current_release_contract["measured_implementation_identity"]
        or item.get("measured_implementation_sha256")
        != current_release_contract["measured_implementation_sha256"]
    ):
        _fail("measured release module/CLI/callable/runtime identity drifted")
    panel, _ = _validate_panel_body(exact_panel_index)
    retained_panel_identity = _identity(
        item.get("panel_index_identity"), label="manifest panel identity"
    )
    panel_raw = batch.canonical_json_bytes(panel)
    if (
        retained_panel_identity["sha256"] != sha256(panel_raw).hexdigest()
        or retained_panel_identity["bytes"] != len(panel_raw)
        or item.get("panel_index_sha256") != panel.get("panel_index_sha256")
    ):
        _fail("manifest panel binding differs")
    expected = build_r6_v2_analysis_manifest_v1(
        panel_index_identity=item["panel_index_identity"],
        validated_panel_index=panel,
        lane_terminal_identities=list(
            _sequence(item["lane_terminal_identities"], label="manifest lane terminals")
        ),
        source_commit_sha=str(item["source_commit_sha"]),
        immutable_image=str(item["immutable_image"]),
        output_prefix=str(item["output_prefix"]),
    )
    if batch.canonical_json_bytes(item) != batch.canonical_json_bytes(expected):
        _fail("R6-v2 analysis manifest canonical replay differs")
    return expected


def reopen_r6_v2_analysis_manifest_v1(
    *, storage: ExactObjectStore, manifest_identity: object
) -> tuple[dict[str, object], dict[str, object], dict[str, object]]:
    normalized_manifest, manifest = _read_json(
        storage, manifest_identity, label="R6-v2 analysis manifest"
    )
    panel_identity, panel = _read_json(
        storage, manifest.get("panel_index_identity"), label="published v12 panel"
    )
    if panel_identity != _identity(
        manifest.get("panel_index_identity"), label="manifest panel identity"
    ):
        _fail("manifest panel exact-read identity differs")
    validated = validate_r6_v2_analysis_manifest_v1(
        manifest, exact_panel_index=panel
    )
    return normalized_manifest, validated, panel


def prepare_r6_v2_analysis_release_v1(
    *,
    storage: ExactObjectStore,
    panel_index_identity: object,
    lane_terminal_identities: Sequence[object],
    source_commit_sha: str,
    immutable_image: str,
    output_prefix: str,
) -> dict[str, object]:
    """Replay the complete v12 authority graph and publish one manifest."""
    raw_terminals = list(_sequence(lane_terminal_identities, label="lane terminals"))
    if len(raw_terminals) != 2:
        _fail("prepare requires exactly two lane terminal identities")
    terminals = [
        _identity(value, label=f"lane terminal[{ordinal}]")
        for ordinal, value in enumerate(raw_terminals)
    ]
    read_exact = _read_exact_callback(storage)
    try:
        lane_inputs = [
            panel_index.derive_v12_lane_input(
                lane_ordinal=ordinal,
                lane_id=str(panel_index.V12_LANE_LATTICE[ordinal]["lane_id"]),
                terminal_receipt_identity=terminals[ordinal],
                read_exact=read_exact,
            )
            for ordinal in range(2)
        ]
        panel = panel_index.reopen_v12_panel_index(
            panel_index_identity=_identity(
                panel_index_identity, label="published panel index"
            ),
            lane_inputs=lane_inputs,
            read_exact=read_exact,
        )
    except Exception as exc:
        raise CorpusR6V2AnalysisReleaseError(
            "published v12 panel did not replay from both exact lane terminals"
        ) from exc
    manifest = build_r6_v2_analysis_manifest_v1(
        panel_index_identity=panel_index_identity,
        validated_panel_index=panel,
        lane_terminal_identities=terminals,
        source_commit_sha=source_commit_sha,
        immutable_image=immutable_image,
        output_prefix=output_prefix,
    )
    identity = _publish_json(
        storage,
        uri=f"{_output_prefix(output_prefix)}execution-manifest.json",
        value=manifest,
    )
    _, replayed, _ = reopen_r6_v2_analysis_manifest_v1(
        storage=storage, manifest_identity=identity
    )
    if batch.canonical_json_bytes(replayed) != batch.canonical_json_bytes(manifest):
        _fail("published R6-v2 manifest replay differs")
    return {
        "manifest_identity": identity,
        "execution_manifest_sha256": manifest["execution_manifest_sha256"],
        "source_member_count": AUTHORITATIVE_SLATE_COUNT,
        "terminal_disposition": PANEL_STATUS,
        **{field: False for field in _FALSE_AUTHORITY_FIELDS},
    }


def _strategy_registry() -> tuple[list[dict[str, object]], dict[str, str]]:
    frozen = release_implementation_contract_v1()[
        "upstream_retrieval_implementation_contract"
    ]
    identity = _mapping(frozen, label="upstream contract identity")
    registry = [
        dict(_mapping(row, label=f"upstream strategy[{ordinal}]"))
        for ordinal, row in enumerate(
            _sequence(identity.get("strategy_registry"), label="strategy registry")
        )
    ]
    ids = [str(row.get("strategy_id")) for row in registry]
    if ids != list(STRATEGY_IDS) or len(registry) != 7:
        _fail("upstream strategy registry differs from literal seven-law order")
    hashes = {
        str(row["strategy_id"]): _sha(
            row.get("strategy_sha256"), label="upstream strategy SHA"
        )
        for row in registry
    }
    return registry, hashes


def _validate_upstream_nested_evidence_v1(
    result: Mapping[str, object]
) -> dict[str, object]:
    """Validate producer-shaped exact-read/reconstruction evidence."""
    verification = dict(
        _mapping(result.get("verification"), label="task verification")
    )
    _exact_keys(verification, _VERIFICATION_KEYS, label="task verification")
    if any(verification.get(field) is not True for field in _VERIFICATION_KEYS):
        _fail("task verification is not the exact all-true producer receipt")

    later_source = _identity(
        result.get("later_source_freeze_identity"),
        label="later source freeze identity",
    )
    worlds = dict(
        _mapping(result.get("world_artifact_identities"), label="world artifacts")
    )
    if set(worlds) != set(batch.TASK_WORLD_SOURCE_ROLES):
        _fail("world artifact roles differ from the canonical five R blocks")
    normalized_worlds = {
        role: _identity(worlds[role], label=f"world artifact {role}")
        for role in batch.TASK_WORLD_SOURCE_ROLES
    }
    if (
        len({_identity_key(row, label="world artifact") for row in normalized_worlds.values()})
        != len(batch.TASK_WORLD_SOURCE_ROLES)
        or result.get("world_artifact_identity_set_sha256")
        != batch.canonical_sha256(normalized_worlds)
    ):
        _fail("world artifact identities/set hash differ")

    reconstruction = dict(
        _mapping(result.get("reconstruction_receipt"), label="reconstruction receipt")
    )
    _exact_keys(
        reconstruction, _RECONSTRUCTION_KEYS, label="reconstruction receipt"
    )
    if (
        reconstruction.get("schema_version") != runner.RECONSTRUCTION_SCHEMA
        or reconstruction.get("uses_realized_outcomes") is not False
        or reconstruction.get("promotion_authority") is not False
    ):
        _fail("reconstruction receipt schema/authority differs")
    _self_hash(
        reconstruction,
        field="reconstruction_sha256",
        label="reconstruction receipt",
    )
    matrix = dict(
        _mapping(reconstruction.get("matrix_binding"), label="matrix binding")
    )
    _exact_keys(matrix, _MATRIX_BINDING_KEYS, label="matrix binding")
    _self_hash(matrix, field="matrix_binding_sha256", label="matrix binding")
    shape = list(_sequence(matrix.get("shape"), label="matrix shape"))
    if (
        len(shape) != 2
        or any(type(value) is not int or value < 1 for value in shape)
    ):
        _fail("matrix binding shape differs")
    if (
        matrix.get("schema_version") != runner.MATRIX_BINDING_SCHEMA
        or matrix.get("uses_realized_outcomes") is not False
        or matrix.get("slate", {}).get("slate_id") != result.get("slate_id")
        or matrix.get("candidate_provenance_sha256")
        != reconstruction.get("candidate_provenance_sha256")
        or shape != [shape[0], len(rw.WORLD_BLOCKS) * WORLDS_PER_BLOCK]
        or shape[0] < ENTRY_BUDGET
        or any(
            _SHA256.fullmatch(str(matrix.get(field))) is None
            for field in (
                "lineup_ids_sha256",
                "world_ids_sha256",
                "score_matrix_sha256",
            )
        )
    ):
        _fail("matrix binding shape/provenance/slate differs")
    raw_arms = list(
        _sequence(
            reconstruction.get("verified_arm_score_hashes"),
            label="verified arm score hashes",
        )
    )
    if len(raw_arms) != len(batch.PARAMETER_SET_ORDER):
        _fail("reconstruction does not bind exactly seven arm score receipts")
    for ordinal, raw_arm in enumerate(raw_arms):
        arm = dict(_mapping(raw_arm, label=f"verified arm[{ordinal}]"))
        _exact_keys(arm, _VERIFIED_ARM_KEYS, label=f"verified arm[{ordinal}]")
        if (
            arm.get("ordinal") != ordinal
            or arm.get("parameter_set_id") != batch.PARAMETER_SET_ORDER[ordinal]
            or _SHA256.fullmatch(str(arm.get("candidate_score_sha256"))) is None
            or _SHA256.fullmatch(str(arm.get("selected_score_sha256"))) is None
            or type(arm.get("unique_count")) is not int
            or int(arm["unique_count"]) < ENTRY_BUDGET
            or arm.get("selected_count") != ENTRY_BUDGET
            or arm.get("verified") is not True
        ):
            _fail(f"verified arm[{ordinal}] identity/count/proof differs")

    matchup = dict(_mapping(result.get("matchup_summary"), label="matchup summary"))
    _exact_keys(matchup, _MATCHUP_SUMMARY_KEYS, label="matchup summary")
    _self_hash(matchup, field="matchup_summary_sha256", label="matchup summary")
    if (
        matchup.get("schema_version") != runner.MATCHUP_SUMMARY_SCHEMA
        or matchup.get("slate") != matrix.get("slate")
        or matchup.get("matchup_source_snapshot_sha256")
        != result.get("matchup_source_snapshot_sha256")
        or matchup.get("eligible_families")
        != list(runner.ELIGIBLE_MATCHUP_FAMILIES)
        or matchup.get("qb_gate")
        != "exclude-only-when-qb_depth1-is-literal-false"
        or matchup.get("minimum_supported_players")
        != MINIMUM_SUPPORTED_PLAYERS
        or matchup.get("minimum_completeness") != MINIMUM_COMPLETENESS
        or matchup.get("uses_realized_outcomes") is not False
    ):
        _fail("matchup summary source/scope/configuration differs")
    _identity(matchup.get("player_catalog_identity"), label="matchup player catalog")
    _identity(
        matchup.get("annotation_query_receipt_identity"),
        label="matchup annotation query",
    )
    raw_lineups = list(_sequence(matchup.get("lineups"), label="matchup lineups"))
    if len(raw_lineups) != shape[0] or not raw_lineups:
        _fail("matchup summary does not cover the canonical candidate matrix")
    lineup_ids: list[str] = []
    for ordinal, raw_row in enumerate(raw_lineups):
        row = dict(_mapping(raw_row, label=f"matchup lineup[{ordinal}]"))
        _exact_keys(row, _MATCHUP_LINEUP_KEYS, label=f"matchup lineup[{ordinal}]")
        lineup_id = row.get("lineup_id")
        edge = row.get("matchup_edge_mean")
        if (
            type(lineup_id) is not str
            or not lineup_id
            or type(row.get("eligible_player_count")) is not int
            or int(row["eligible_player_count"]) < 0
            or type(row.get("supported_player_count")) is not int
            or not 0 <= int(row["supported_player_count"]) <= int(
                row["eligible_player_count"]
            )
            or not isinstance(row.get("supported_families"), list)
            or type(row.get("annotation_completeness")) is not float
            or not 0.0 <= float(row["annotation_completeness"]) <= 1.0
            or type(row.get("qualifies_for_matchup_admission")) is not bool
            or row.get("missing_semantics") != "missing-not-zero"
            or (edge is not None and type(edge) is not float)
        ):
            _fail(f"matchup lineup[{ordinal}] evidence differs")
        lineup_ids.append(lineup_id)
    if lineup_ids != sorted(set(lineup_ids)):
        _fail("matchup lineup membership/order differs")

    output_hashes = _mapping(result.get("output_hashes"), label="task output hashes")
    if (
        output_hashes.get("compatibility_import_sha256")
        != reconstruction.get("compatibility_import_sha256")
        or output_hashes.get("candidate_provenance_sha256")
        != reconstruction.get("candidate_provenance_sha256")
        or output_hashes.get("reconstruction_sha256")
        != reconstruction.get("reconstruction_sha256")
        or output_hashes.get("matchup_summary_sha256")
        != matchup.get("matchup_summary_sha256")
    ):
        _fail("nested evidence differs from the task output hashes")
    return {
        "later_source_freeze_identity": later_source,
        "world_artifact_identities": normalized_worlds,
        "verification": verification,
        "reconstruction_receipt": reconstruction,
        "matrix_binding": matrix,
        "matchup_summary": matchup,
    }


def _validate_book(
    value: object,
    *,
    slate: Mapping[str, object],
    fit_scope_id: str,
    training_blocks: Sequence[str],
    heldout_block: str | None,
    admission: Mapping[str, object],
    strategy_id: str,
    strategy_sha256: str,
    reconstruction_sha256: str,
) -> dict[str, object]:
    book = dict(_mapping(value, label="retrieval book"))
    _self_hash(book, field="book_sha256", label="retrieval book")
    admission_id = str(admission["admission_id"])
    admitted_ids = list(
        _sequence(
            admission.get("admitted_lineup_ids"),
            label="book admission lineup ids",
        )
    )
    if (
        book.get("schema_version") != runner.BOOK_SCHEMA
        or book.get("book_id") != f"{fit_scope_id}:{admission_id}:{strategy_id}"
        or book.get("fit_scope_id") != fit_scope_id
        or book.get("reconstruction_sha256") != reconstruction_sha256
        or book.get("admission_id") != admission_id
        or book.get("admission_sha256") != admission.get("admission_sha256")
        or book.get("strategy_id") != strategy_id
        or book.get("strategy_sha256") != strategy_sha256
        or book.get("training_blocks") != list(training_blocks)
        or book.get("heldout_block") != heldout_block
        or book.get("strategy_application_scope")
        != (
            "explicit-rotated-training-blocks"
            if heldout_block is not None
            else "explicit-all-five-block-final-fit"
        )
        or admitted_ids != sorted(set(admitted_ids))
        or len(admitted_ids) < ENTRY_BUDGET
        or book.get("input_lineup_ids_sha256")
        != batch.canonical_sha256(admitted_ids)
        or book.get("training_score_shape")
        != [len(admitted_ids), len(training_blocks) * WORLDS_PER_BLOCK]
        or _SHA256.fullmatch(str(book.get("training_score_matrix_sha256"))) is None
        or book.get("entry_count") != ENTRY_BUDGET
        or book.get("worlds_per_block") != WORLDS_PER_BLOCK
        or book.get("dose_authority") != runner.AUTHORITATIVE_DOSE
        or book.get("uses_realized_outcomes") is not False
        or book.get("promotion_authority") is not False
    ):
        _fail("retrieval book identity/dose/authority differs")
    selected_ids = list(
        _sequence(book.get("selected_lineup_ids"), label="selected lineup ids")
    )
    selected_rosters = list(
        _sequence(book.get("selected_rosters"), label="selected rosters")
    )
    selected_local = list(
        _sequence(book.get("selected_local_indices"), label="selected local indices")
    )
    selected_global = list(
        _sequence(book.get("selected_global_indices"), label="selected global indices")
    )
    trace = list(_sequence(book.get("marginal_trace"), label="book marginal trace"))
    if (
        len(selected_ids) != ENTRY_BUDGET
        or len(set(selected_ids)) != ENTRY_BUDGET
        or any(type(value) is not str or not value for value in selected_ids)
        or len(selected_rosters) != ENTRY_BUDGET
        or len(selected_local) != ENTRY_BUDGET
        or len(set(selected_local)) != ENTRY_BUDGET
        or len(selected_global) != ENTRY_BUDGET
        or len(set(selected_global)) != ENTRY_BUDGET
        or any(type(value) is not int or value < 0 for value in selected_local)
        or any(value >= len(admitted_ids) for value in selected_local)
        or any(type(value) is not int or value < 0 for value in selected_global)
        or len(trace) != ENTRY_BUDGET
    ):
        _fail("retrieval book does not contain one exact unique rank 80")
    for rank, (lineup_id, raw_roster, raw_trace) in enumerate(
        zip(selected_ids, selected_rosters, trace, strict=True)
    ):
        roster = list(_sequence(raw_roster, label=f"selected roster[{rank}]"))
        trace_row = _mapping(raw_trace, label=f"marginal trace[{rank}]")
        if (
            len(roster) != 9
            or len(set(roster)) != 9
            or roster != sorted(roster)
            or any(type(player_id) is not str or not player_id for player_id in roster)
            or canonical_lineup_id(slate, roster) != lineup_id
            or admitted_ids[selected_local[rank]] != lineup_id
            or trace_row.get("selection_rank") != rank
            or trace_row.get("lineup_id") != lineup_id
            or trace_row.get("global_lineup_index") != selected_global[rank]
            or trace_row.get("admitted_lineup_index") != selected_local[rank]
        ):
            _fail("retrieval book roster/rank/trace alignment differs")
    return book


def _prefixes(book: Mapping[str, object]) -> list[dict[str, object]]:
    selected_ids = list(book["selected_lineup_ids"])
    selected_rosters = list(book["selected_rosters"])
    result: list[dict[str, object]] = []
    rank_80_sha = batch.canonical_sha256({
        "selected_lineup_ids": selected_ids,
        "selected_rosters": selected_rosters,
    })
    for size in PREFIX_SIZES:
        body = {
            "schema_version": PREFIX_SCHEMA,
            "entry_count": size,
            "prefix_of_rank_80": True,
            "rank_80_sha256": rank_80_sha,
            "selected_lineup_ids": selected_ids[:size],
            "selected_rosters": selected_rosters[:size],
            "selected_lineup_ids_sha256": batch.canonical_sha256(
                selected_ids[:size]
            ),
        }
        result.append(_with_hash(body, field="prefix_sha256"))
    return result


def _validate_scope(
    value: object,
    *,
    scope_ordinal: int,
    expected_slate: Mapping[str, object],
    expected_reconstruction_sha256: str,
    expected_matchup_summary_sha256: str,
    expected_matchup_source_sha256: str,
    expected_registry: Sequence[Mapping[str, object]],
    strategy_hashes: Mapping[str, str],
) -> tuple[dict[str, object], list[dict[str, object]]]:
    scope = dict(_mapping(value, label=f"fit scope[{scope_ordinal}]"))
    _self_hash(scope, field="fit_scope_sha256", label=f"fit scope[{scope_ordinal}]")
    fit_scope_id = FIT_SCOPE_IDS[scope_ordinal]
    heldout = rw.WORLD_BLOCKS[scope_ordinal] if scope_ordinal < 5 else None
    training_blocks = [block for block in rw.WORLD_BLOCKS if block != heldout]
    if (
        scope.get("schema_version") != runner.SCOPE_SCHEMA
        or scope.get("fit_scope_id") != fit_scope_id
        or scope.get("reconstruction_sha256") != expected_reconstruction_sha256
        or scope.get("heldout_block") != heldout
        or scope.get("training_blocks") != training_blocks
        or scope.get("worlds_per_block") != WORLDS_PER_BLOCK
        or scope.get("admission_cap") != ADMISSION_CAP
        or scope.get("dose_authority") != runner.AUTHORITATIVE_DOSE
        or scope.get("require_authoritative") is not True
        or scope.get("book_count") != BOOKS_PER_SCOPE
        or scope.get("neutral_controls_apply_to_strategy_id") != STRATEGY_IDS[0]
        or scope.get("uses_realized_outcomes") is not False
        or scope.get("promotion_authority") is not False
        or scope.get("matchup_summary_sha256")
        != expected_matchup_summary_sha256
        or scope.get("matchup_source_snapshot_sha256")
        != expected_matchup_source_sha256
    ):
        _fail(f"fit scope[{scope_ordinal}] lattice/dose/authority differs")
    candidate_view = _mapping(scope.get("candidate_view"), label="scope candidate view")
    _self_hash(
        candidate_view,
        field="fit_candidate_view_sha256",
        label="scope candidate view",
    )
    slate = dict(_mapping(candidate_view.get("slate"), label="scope candidate-view slate"))
    if (
        slate != dict(expected_slate)
        or candidate_view.get("fit_scope_id") != fit_scope_id
        or candidate_view.get("training_blocks") != training_blocks
        or candidate_view.get("heldout_block") != heldout
        or candidate_view.get("dose_authority") != runner.AUTHORITATIVE_DOSE
        or candidate_view.get("selection_inputs_exclude_heldout_occurrences")
        is not True
        or candidate_view.get("uses_realized_outcomes") is not False
    ):
        _fail("fit scope candidate-view scope/slate/authority differs")
    eligible_rows = list(
        _sequence(
            candidate_view.get("eligible_candidates"),
            label="scope eligible candidates",
        )
    )
    eligible_ids = [
        str(_mapping(row, label="scope eligible candidate").get("lineup_id"))
        for row in eligible_rows
    ]
    if (
        eligible_ids != sorted(set(eligible_ids))
        or len(eligible_ids) < ENTRY_BUDGET
        or candidate_view.get("eligible_count") != len(eligible_ids)
        or candidate_view.get("excluded_count")
        != len(
            _sequence(
                candidate_view.get("excluded_candidates_audit"),
                label="scope excluded candidates",
            )
        )
        or _SHA256.fullmatch(
            str(candidate_view.get("selection_provenance_sha256"))
        ) is None
    ):
        _fail("fit scope candidate-view membership/count differs")
    registry = list(_sequence(scope.get("strategy_registry"), label="scope registry"))
    if batch.canonical_json_bytes(registry) != batch.canonical_json_bytes(
        list(expected_registry)
    ):
        _fail("fit scope strategy registry differs from frozen implementation")
    admissions = [
        dict(_mapping(row, label=f"scope admission[{ordinal}]"))
        for ordinal, row in enumerate(
            _sequence(scope.get("admissions"), label="scope admissions")
        )
    ]
    if len(admissions) != 2 + NEUTRAL_REPLICATES:
        _fail("fit scope lacks the exact two-primary plus 32-neutral admissions")
    expected_admission_ids = [
        *PRIMARY_ADMISSION_IDS,
        *[
            f"neutral-{replicate:02d}-{runner.NEUTRAL_LAW_ID}"
            for replicate in range(NEUTRAL_REPLICATES)
        ],
    ]
    for ordinal, admission in enumerate(admissions):
        _self_hash(admission, field="admission_sha256", label="scope admission")
        if (
            admission.get("schema_version") != runner.ADMISSION_SCHEMA
            or admission.get("fit_scope_id") != fit_scope_id
            or admission.get("admission_id") != expected_admission_ids[ordinal]
            or admission.get("dose_authority") != runner.AUTHORITATIVE_DOSE
            or admission.get("uses_realized_outcomes") is not False
            or admission.get("selection_provenance_sha256")
            != candidate_view.get("selection_provenance_sha256")
        ):
            _fail("fit scope admission order/identity/authority differs")
        admitted_ids = list(
            _sequence(
                admission.get("admitted_lineup_ids"),
                label="scope admitted lineup ids",
            )
        )
        excluded_rows = list(
            _sequence(
                admission.get("excluded_eligible_candidates"),
                label="scope excluded eligible candidates",
            )
        )
        excluded_ids = [
            str(_mapping(row, label="scope exclusion").get("lineup_id"))
            for row in excluded_rows
        ]
        if (
            admitted_ids != sorted(set(admitted_ids))
            or not set(admitted_ids).issubset(eligible_ids)
            or admission.get("admitted_count") != len(admitted_ids)
            or len(admitted_ids) < ENTRY_BUDGET
            or len(set(excluded_ids)) != len(excluded_ids)
            or set(excluded_ids) != set(eligible_ids) - set(admitted_ids)
        ):
            _fail("fit scope admission partition/count differs")
        if ordinal == 0 and (
            admission.get("uses_matchup_values") is not False
            or admission.get("uses_simulated_scores") is not False
            or admitted_ids != eligible_ids
        ):
            _fail("full-union admission is not score/matchup blind")
        elif ordinal == 1 and (
            admission.get("uses_matchup_values") is not True
            or admission.get("uses_simulated_scores") is not False
            or admission.get("admission_cap") != ADMISSION_CAP
        ):
            _fail("matchup admission does not use the registered score-free scope")
        elif ordinal >= 2 and (
            admission.get("neutral_law_id") != runner.NEUTRAL_LAW_ID
            or admission.get("replicate_index") != ordinal - 2
            or admission.get("uses_matchup_values") is not False
            or admission.get("uses_simulated_scores") is not False
            or admission.get("target_admission_sha256")
            != admissions[1].get("admission_sha256")
            or len(admitted_ids)
            != int(admissions[1].get("admitted_count", -1))
        ):
            _fail("score-blind neutral admission law/order/binding differs")
    books = list(_sequence(scope.get("books"), label="scope books"))
    if len(books) != BOOKS_PER_SCOPE:
        _fail("fit scope book count differs from exact 46")
    expected_cells: list[tuple[Mapping[str, object], str]] = [
        *[(admissions[0], strategy_id) for strategy_id in STRATEGY_IDS],
        *[(admissions[1], strategy_id) for strategy_id in STRATEGY_IDS],
        *[(admissions[2 + replicate], STRATEGY_IDS[0]) for replicate in range(32)],
    ]
    projections: list[dict[str, object]] = []
    for book_ordinal, (raw_book, (admission, strategy_id)) in enumerate(
        zip(books, expected_cells, strict=True)
    ):
        book = _validate_book(
            raw_book,
            slate=slate,
            fit_scope_id=fit_scope_id,
            training_blocks=training_blocks,
            heldout_block=heldout,
            admission=admission,
            strategy_id=strategy_id,
            strategy_sha256=strategy_hashes[strategy_id],
            reconstruction_sha256=expected_reconstruction_sha256,
        )
        projection = {
            "schema_version": BOOK_PROJECTION_SCHEMA,
            "scope_ordinal": scope_ordinal,
            "scope_book_ordinal": book_ordinal,
            "fit_scope_id": fit_scope_id,
            "heldout_block": heldout,
            "book_id": book["book_id"],
            "book_sha256": book["book_sha256"],
            "admission_id": book["admission_id"],
            "strategy_id": book["strategy_id"],
            "rank_80_sha256": batch.canonical_sha256({
                "selected_lineup_ids": book["selected_lineup_ids"],
                "selected_rosters": book["selected_rosters"],
            }),
            "prefixes": _prefixes(book),
        }
        projections.append(_with_hash(projection, field="book_projection_sha256"))
    if len({str(row["book_id"]) for row in projections}) != BOOKS_PER_SCOPE:
        _fail("fit scope book identifiers repeat")
    return scope, projections


def derive_r6_v2_book_catalog_v1(
    upstream_task_result: Mapping[str, object]
) -> dict[str, object]:
    """Deep-validate the runner lattice and derive exact 4/14/80 prefixes."""
    result = dict(_mapping(upstream_task_result, label="upstream R6-v2 task result"))
    _exact_keys(result, _UPSTREAM_RESULT_KEYS, label="upstream R6-v2 task result")
    _self_hash(result, field="task_result_sha256", label="upstream R6-v2 task result")
    if any(
        result.get(field) is not False
        for field in _UPSTREAM_FALSE_AUTHORITY_FIELDS
    ):
        _fail("upstream R6-v2 task result carries forbidden authority")
    if (
        result.get("schema_version") != execution.RESULT_SCHEMA
        or result.get("execution_mode")
        != "authoritative-dose-one-slate-mechanics-smoke"
        or result.get("matchup_evidence_class") != CURRENT_SOURCE_EVIDENCE_CLASS
        or result.get("matchup_mechanics_only") is not True
    ):
        _fail("upstream task result is not the registered retrospective mechanics run")
    configuration = _mapping(result.get("configuration"), label="task configuration")
    if configuration != {
        "minimum_supported_players": MINIMUM_SUPPORTED_PLAYERS,
        "minimum_completeness": MINIMUM_COMPLETENESS,
        "admission_m": ADMISSION_CAP,
        "neutral_replicates": NEUTRAL_REPLICATES,
        "neutral_seed_root": NEUTRAL_SEED_ROOT,
        "worlds_per_block": WORLDS_PER_BLOCK,
        "require_authoritative": True,
    }:
        _fail("upstream task configuration differs from the frozen release dose")
    nested = _validate_upstream_nested_evidence_v1(result)
    registry, strategy_hashes = _strategy_registry()
    surface = dict(_mapping(result.get("retrieval_surface"), label="retrieval surface"))
    _self_hash(surface, field="retrieval_surface_sha256", label="retrieval surface")
    surface_slate = _mapping(surface.get("slate"), label="retrieval surface slate")
    if (
        surface.get("schema_version") != runner.RUNNER_SCHEMA
        or surface_slate.get("slate_id") != result.get("slate_id")
        or surface.get("fold_count") != 5
        or surface.get("books_per_scope") != BOOKS_PER_SCOPE
        or surface.get("cross_fit_book_count") != CROSS_FIT_BOOK_COUNT
        or surface.get("final_fit_book_count") != FINAL_FIT_BOOK_COUNT
        or surface.get("neutral_replicate_count") != NEUTRAL_REPLICATES
        or surface.get("worlds_per_block") != WORLDS_PER_BLOCK
        or surface.get("admission_cap") != ADMISSION_CAP
        or surface.get("dose_authority") != runner.AUTHORITATIVE_DOSE
        or surface.get("require_authoritative") is not True
        or surface.get("final_fit_is_distinct_all-block-refit") is not True
        or surface.get("uses_realized_outcomes") is not False
        or surface.get("promotion_authority") is not False
    ):
        _fail("retrieval surface count/dose/authority differs")
    output_hashes = _mapping(result.get("output_hashes"), label="task output hashes")
    _exact_keys(output_hashes, _OUTPUT_HASH_KEYS, label="task output hashes")
    if (
        any(
            _SHA256.fullmatch(str(output_hashes.get(field))) is None
            for field in _OUTPUT_HASH_KEYS
        )
        or output_hashes.get("retrieval_surface_sha256")
        != surface.get("retrieval_surface_sha256")
        or output_hashes.get("candidate_provenance_sha256")
        != surface.get("candidate_provenance_sha256")
        or output_hashes.get("reconstruction_sha256")
        != surface.get("reconstruction_sha256")
        or output_hashes.get("matchup_summary_sha256")
        != surface.get("matchup_summary_sha256")
        or result.get("matchup_source_snapshot_sha256")
        != surface.get("matchup_source_snapshot_sha256")
        or surface.get("candidate_provenance_sha256")
        != nested["matrix_binding"].get("candidate_provenance_sha256")
        or surface.get("reconstruction_sha256")
        != nested["reconstruction_receipt"].get("reconstruction_sha256")
        or surface.get("matchup_summary_sha256")
        != nested["matchup_summary"].get("matchup_summary_sha256")
    ):
        _fail("task output hashes do not bind the retrieval surface")
    folds = list(_sequence(surface.get("folds"), label="retrieval folds"))
    if len(folds) != 5:
        _fail("retrieval surface does not contain exactly five folds")
    raw_scopes = [*folds, surface.get("final_fit")]
    projections: list[dict[str, object]] = []
    scope_hashes: list[str] = []
    for scope_ordinal, raw_scope in enumerate(raw_scopes):
        scope, scope_projections = _validate_scope(
            raw_scope,
            scope_ordinal=scope_ordinal,
            expected_slate=surface_slate,
            expected_reconstruction_sha256=str(
                surface["reconstruction_sha256"]
            ),
            expected_matchup_summary_sha256=str(
                surface["matchup_summary_sha256"]
            ),
            expected_matchup_source_sha256=str(
                surface["matchup_source_snapshot_sha256"]
            ),
            expected_registry=registry,
            strategy_hashes=strategy_hashes,
        )
        scope_hashes.append(str(scope["fit_scope_sha256"]))
        projections.extend(scope_projections)
    if (
        len(projections) != BOOKS_PER_SLATE
        or len({str(row["book_id"]) for row in projections}) != BOOKS_PER_SLATE
    ):
        _fail("retrieval surface does not contain 276 unique books")
    body = {
        "schema_version": BOOK_CATALOG_SCHEMA,
        "slate_id": result["slate_id"],
        "upstream_task_result_sha256": result["task_result_sha256"],
        "retrieval_surface_sha256": surface["retrieval_surface_sha256"],
        "fit_scope_ids": list(FIT_SCOPE_IDS),
        "fit_scope_sha256s": scope_hashes,
        "fit_scope_count": 6,
        "books_per_scope": BOOKS_PER_SCOPE,
        "book_count": len(projections),
        "prefix_sizes": list(PREFIX_SIZES),
        "prefix_law": "first-n-of-one-immutable-rank-80",
        "books": projections,
        "uses_realized_outcomes": False,
        "r6_freeze_authority": False,
        "promotion_authority": False,
    }
    return _with_hash(body, field="book_catalog_sha256")


def build_r6_v2_mechanics_result_v1(
    *,
    manifest_identity: object,
    manifest: Mapping[str, object],
    exact_panel_index: Mapping[str, object],
    source_ordinal: int,
    matchup_source_snapshot_identity: object,
    upstream_task_result: Mapping[str, object],
    worker_process_runtime: object,
) -> dict[str, object]:
    validated_manifest = validate_r6_v2_analysis_manifest_v1(
        manifest, exact_panel_index=exact_panel_index
    )
    retained_manifest_identity = _bind_identity_to_body(
        manifest_identity, validated_manifest, label="execution manifest"
    )
    panel, panel_members = _validate_panel_body(exact_panel_index)
    if type(source_ordinal) is not int or not 0 <= source_ordinal < 54:
        _fail("source ordinal must be one exact integer in 0..53")
    source_member = dict(validated_manifest["source_members"][source_ordinal])
    panel_member = panel_members[source_ordinal]
    if source_member["panel_member_sha256"] != batch.canonical_sha256(panel_member):
        _fail("manifest source member differs from exact panel membership")
    matchup_identity = _identity(
        matchup_source_snapshot_identity, label="matchup source snapshot"
    )
    worker_runtime = _validate_process_runtime_identity_v1(
        worker_process_runtime, role="run-slate-worker"
    )
    upstream = dict(_mapping(upstream_task_result, label="upstream task result"))
    if (
        upstream.get("slate_id") != source_member["slate_id"]
        or upstream.get("panel_index_identity")
        != _identity(validated_manifest["panel_index_identity"], label="manifest panel")
        or upstream.get("panel_index_sha256") != panel["panel_index_sha256"]
        or upstream.get("accepted_slate_membership") != panel_member
        or upstream.get("accepted_slate_membership_sha256")
        != source_member["panel_member_sha256"]
        or upstream.get("task_acceptance_identity")
        != source_member["task_acceptance_identity"]
        or upstream.get("carrier_identity") != source_member["carrier_identity"]
        or upstream.get("matchup_source_snapshot_identity") != matchup_identity
        or upstream.get("matchup_evidence_class") != CURRENT_SOURCE_EVIDENCE_CLASS
        or upstream.get("matchup_mechanics_only") is not True
    ):
        _fail("upstream task result lineage differs from manifest/member/source")
    catalog = derive_r6_v2_book_catalog_v1(upstream)
    body = {
        "schema_version": MECHANICS_RESULT_SCHEMA,
        "publication_mode": PUBLICATION_MODE,
        "manifest_identity": retained_manifest_identity,
        "execution_manifest_sha256": validated_manifest[
            "execution_manifest_sha256"
        ],
        "source_ordinal": source_ordinal,
        "slate_id": source_member["slate_id"],
        "panel_member_sha256": source_member["panel_member_sha256"],
        "matchup_source_snapshot_identity": matchup_identity,
        "matchup_source_snapshot_sha256": upstream[
            "matchup_source_snapshot_sha256"
        ],
        "matchup_evidence_class": CURRENT_SOURCE_EVIDENCE_CLASS,
        "source_disposition": CURRENT_SOURCE_DISPOSITION,
        "worker_process_runtime": worker_runtime,
        "worker_process_runtime_sha256": worker_runtime[
            "process_runtime_sha256"
        ],
        "upstream_task_result": upstream,
        "upstream_task_result_sha256": upstream["task_result_sha256"],
        "book_catalog": catalog,
        "book_catalog_sha256": catalog["book_catalog_sha256"],
        "fit_scope_count": 6,
        "books_per_scope": BOOKS_PER_SCOPE,
        "book_count": BOOKS_PER_SLATE,
        "prefix_sizes": list(PREFIX_SIZES),
        "mechanics_complete": True,
        "accepted_release_eligible": False,
        **{field: False for field in _FALSE_AUTHORITY_FIELDS},
    }
    return _with_hash(body, field="mechanics_result_sha256")


def validate_r6_v2_mechanics_result_v1(
    value: object,
    *,
    manifest_identity: object,
    manifest: Mapping[str, object],
    exact_panel_index: Mapping[str, object],
) -> dict[str, object]:
    item = dict(_mapping(value, label="R6-v2 mechanics result"))
    _exact_keys(item, _MECHANICS_KEYS, label="R6-v2 mechanics result")
    if (
        item.get("schema_version") != MECHANICS_RESULT_SCHEMA
        or item.get("publication_mode") != PUBLICATION_MODE
        or item.get("matchup_evidence_class") != CURRENT_SOURCE_EVIDENCE_CLASS
        or item.get("source_disposition") != CURRENT_SOURCE_DISPOSITION
        or item.get("fit_scope_count") != 6
        or item.get("books_per_scope") != BOOKS_PER_SCOPE
        or item.get("book_count") != BOOKS_PER_SLATE
        or item.get("prefix_sizes") != list(PREFIX_SIZES)
        or item.get("mechanics_complete") is not True
        or item.get("accepted_release_eligible") is not False
        or item.get("worker_process_runtime_sha256")
        != _mapping(
            item.get("worker_process_runtime"), label="worker process runtime"
        ).get("process_runtime_sha256")
    ):
        _fail("R6-v2 mechanics result schema/count/disposition differs")
    _false_authorities(item, label="R6-v2 mechanics result")
    _self_hash(item, field="mechanics_result_sha256", label="R6-v2 mechanics result")
    expected = build_r6_v2_mechanics_result_v1(
        manifest_identity=manifest_identity,
        manifest=manifest,
        exact_panel_index=exact_panel_index,
        source_ordinal=int(item["source_ordinal"]),
        matchup_source_snapshot_identity=item["matchup_source_snapshot_identity"],
        upstream_task_result=_mapping(
            item["upstream_task_result"], label="retained upstream task result"
        ),
        worker_process_runtime=item["worker_process_runtime"],
    )
    if batch.canonical_json_bytes(item) != batch.canonical_json_bytes(expected):
        _fail("R6-v2 mechanics result canonical replay differs")
    return expected


def build_r6_v2_verifier_result_v1(
    *,
    storage: ExactObjectStore,
    manifest_identity: object,
    manifest: Mapping[str, object],
    exact_panel_index: Mapping[str, object],
    mechanics_result_identity: object,
    mechanics_result: Mapping[str, object],
    matchup_source_snapshot_identity: object,
    matchup_source_snapshot: Mapping[str, object],
) -> dict[str, object]:
    """Capture this process and internally rerun the exact scientific seam."""
    validated_manifest = validate_r6_v2_analysis_manifest_v1(
        manifest, exact_panel_index=exact_panel_index
    )
    retained_manifest_identity = _bind_identity_to_body(
        manifest_identity, validated_manifest, label="manifest"
    )
    validated_result = validate_r6_v2_mechanics_result_v1(
        mechanics_result,
        manifest_identity=retained_manifest_identity,
        manifest=validated_manifest,
        exact_panel_index=exact_panel_index,
    )
    retained_result_identity = _bind_identity_to_body(
        mechanics_result_identity, validated_result, label="mechanics result"
    )
    source_ordinal = validated_result.get("source_ordinal")
    if type(source_ordinal) is not int or not 0 <= source_ordinal < 54:
        _fail("verifier result source ordinal differs")
    source_member = dict(validated_manifest["source_members"][source_ordinal])
    _, panel_members = _validate_panel_body(exact_panel_index)
    panel_member = panel_members[source_ordinal]
    if retained_result_identity["uri"] != source_member["mechanics_result_uri"]:
        _fail("verifier mechanics URI differs from deterministic manifest path")
    worker_runtime = _validate_process_runtime_identity_v1(
        validated_result.get("worker_process_runtime"), role="run-slate-worker"
    )
    verifier_runtime = _validate_current_process_runtime_identity_v1(
        _process_runtime_identity_v1(role="verify-slate-verifier"),
        role="verify-slate-verifier",
    )
    if _process_instance_key(worker_runtime) == _process_instance_key(
        verifier_runtime
    ):
        _fail("verify-slate must run in a distinct process from run-slate")
    try:
        validated_source = runner.validate_matchup_source_snapshot(
            _mapping(matchup_source_snapshot, label="matchup source snapshot")
        )
    except Exception as exc:
        raise CorpusR6V2AnalysisReleaseError(
            "legacy/simple matchup snapshot did not replay"
        ) from exc
    retained_matchup_identity = _bind_identity_to_body(
        matchup_source_snapshot_identity,
        validated_source,
        label="matchup source snapshot",
    )
    if (
        retained_matchup_identity
        != validated_result["matchup_source_snapshot_identity"]
        or validated_source.get("matchup_source_snapshot_sha256")
        != validated_result["matchup_source_snapshot_sha256"]
        or validated_source.get("schema_version") != runner.MATCHUP_SOURCE_SCHEMA
    ):
        _fail("matchup source identity/content differs from mechanics result")
    replayed_upstream = _execute_scientific_replay_v1(
        storage=storage,
        manifest=validated_manifest,
        panel=exact_panel_index,
        panel_member=panel_member,
        source_member=source_member,
        matchup_identity=retained_matchup_identity,
        matchup_body=validated_source,
    )
    replayed_upstream = dict(_mapping(
        replayed_upstream, label="internally replayed upstream task result"
    ))
    replayed_catalog = derive_r6_v2_book_catalog_v1(replayed_upstream)
    if (
        batch.canonical_json_bytes(replayed_upstream)
        != batch.canonical_json_bytes(validated_result["upstream_task_result"])
        or batch.canonical_json_bytes(replayed_catalog)
        != batch.canonical_json_bytes(validated_result["book_catalog"])
    ):
        _fail("independent scientific executor replay differs from worker mechanics")
    body = {
        "schema_version": VERIFIER_RESULT_SCHEMA,
        "publication_mode": PUBLICATION_MODE,
        "manifest_identity": retained_manifest_identity,
        "execution_manifest_sha256": validated_manifest[
            "execution_manifest_sha256"
        ],
        "source_ordinal": validated_result["source_ordinal"],
        "slate_id": validated_result["slate_id"],
        "panel_member_sha256": validated_result["panel_member_sha256"],
        "mechanics_result_identity": retained_result_identity,
        "mechanics_result_sha256": validated_result["mechanics_result_sha256"],
        "worker_process_runtime": worker_runtime,
        "worker_process_runtime_sha256": worker_runtime[
            "process_runtime_sha256"
        ],
        "verifier_process_runtime": verifier_runtime,
        "verifier_process_runtime_sha256": verifier_runtime[
            "process_runtime_sha256"
        ],
        "matchup_source_snapshot_identity": retained_matchup_identity,
        "matchup_source_snapshot_sha256": validated_source[
            "matchup_source_snapshot_sha256"
        ],
        "independently_replayed_upstream_task_result": replayed_upstream,
        "independently_replayed_upstream_task_result_sha256": replayed_upstream[
            "task_result_sha256"
        ],
        "independently_derived_book_catalog": replayed_catalog,
        "independently_derived_book_catalog_sha256": replayed_catalog[
            "book_catalog_sha256"
        ],
        "exact_upstream_result_replay_verified": True,
        "verification_replayed": True,
        "reconstruction_replayed": True,
        "matchup_replayed": True,
        "admissions_recomputed": True,
        "neutral_controls_recomputed": True,
        "training_matrices_recomputed": True,
        "all_seven_rank80_books_recomputed": True,
        **{field: False for field in _FALSE_AUTHORITY_FIELDS},
    }
    return _with_hash(body, field="verifier_result_sha256")


def validate_r6_v2_verifier_result_v1(
    value: object,
    *,
    manifest_identity: object,
    manifest: Mapping[str, object],
    exact_panel_index: Mapping[str, object],
    mechanics_result_identity: object,
    mechanics_result: Mapping[str, object],
    matchup_source_snapshot_identity: object,
    matchup_source_snapshot: Mapping[str, object],
) -> dict[str, object]:
    item = dict(_mapping(value, label="R6-v2 verifier result"))
    _exact_keys(item, _VERIFIER_RESULT_KEYS, label="R6-v2 verifier result")
    if (
        item.get("schema_version") != VERIFIER_RESULT_SCHEMA
        or item.get("publication_mode") != PUBLICATION_MODE
        or any(
            item.get(field) is not True
            for field in (
                "exact_upstream_result_replay_verified",
                "verification_replayed",
                "reconstruction_replayed",
                "matchup_replayed",
                "admissions_recomputed",
                "neutral_controls_recomputed",
                "training_matrices_recomputed",
                "all_seven_rank80_books_recomputed",
            )
        )
    ):
        _fail("R6-v2 verifier result schema/recomputation evidence differs")
    _false_authorities(item, label="R6-v2 verifier result")
    _self_hash(item, field="verifier_result_sha256", label="R6-v2 verifier result")
    validated_manifest = validate_r6_v2_analysis_manifest_v1(
        manifest, exact_panel_index=exact_panel_index
    )
    retained_manifest_identity = _bind_identity_to_body(
        manifest_identity, validated_manifest, label="verifier manifest"
    )
    validated_mechanics = validate_r6_v2_mechanics_result_v1(
        mechanics_result,
        manifest_identity=retained_manifest_identity,
        manifest=validated_manifest,
        exact_panel_index=exact_panel_index,
    )
    retained_mechanics_identity = _bind_identity_to_body(
        mechanics_result_identity,
        validated_mechanics,
        label="verifier mechanics result",
    )
    try:
        validated_matchup = runner.validate_matchup_source_snapshot(
            _mapping(matchup_source_snapshot, label="verifier matchup source")
        )
    except Exception as exc:
        raise CorpusR6V2AnalysisReleaseError(
            "verifier retained matchup snapshot did not replay"
        ) from exc
    retained_matchup_identity = _bind_identity_to_body(
        matchup_source_snapshot_identity,
        validated_matchup,
        label="verifier matchup source",
    )
    worker_runtime = _validate_process_runtime_identity_v1(
        item.get("worker_process_runtime"), role="run-slate-worker"
    )
    verifier_runtime = _validate_process_runtime_identity_v1(
        item.get("verifier_process_runtime"), role="verify-slate-verifier"
    )
    replayed = dict(_mapping(
        item.get("independently_replayed_upstream_task_result"),
        label="retained verifier upstream result",
    ))
    catalog = derive_r6_v2_book_catalog_v1(replayed)
    retained_catalog = dict(_mapping(
        item.get("independently_derived_book_catalog"),
        label="retained verifier catalog",
    ))
    source_ordinal = validated_mechanics.get("source_ordinal")
    if type(source_ordinal) is not int or not 0 <= source_ordinal < 54:
        _fail("retained verifier source ordinal differs")
    source_member = validated_manifest["source_members"][source_ordinal]
    if (
        item.get("manifest_identity") != retained_manifest_identity
        or item.get("execution_manifest_sha256")
        != validated_manifest.get("execution_manifest_sha256")
        or item.get("source_ordinal") != source_ordinal
        or item.get("slate_id") != validated_mechanics.get("slate_id")
        or item.get("panel_member_sha256")
        != validated_mechanics.get("panel_member_sha256")
        or retained_mechanics_identity["uri"]
        != source_member.get("mechanics_result_uri")
        or item.get("mechanics_result_identity") != retained_mechanics_identity
        or item.get("mechanics_result_sha256")
        != validated_mechanics.get("mechanics_result_sha256")
        or item.get("worker_process_runtime") != worker_runtime
        or item.get("worker_process_runtime_sha256")
        != worker_runtime.get("process_runtime_sha256")
        or item.get("verifier_process_runtime") != verifier_runtime
        or item.get("verifier_process_runtime_sha256")
        != verifier_runtime.get("process_runtime_sha256")
        or _process_instance_key(worker_runtime)
        == _process_instance_key(verifier_runtime)
        or item.get("matchup_source_snapshot_identity")
        != retained_matchup_identity
        or item.get("matchup_source_snapshot_sha256")
        != validated_matchup.get("matchup_source_snapshot_sha256")
        or retained_matchup_identity
        != validated_mechanics.get("matchup_source_snapshot_identity")
        or batch.canonical_json_bytes(replayed)
        != batch.canonical_json_bytes(validated_mechanics["upstream_task_result"])
        or item.get("independently_replayed_upstream_task_result_sha256")
        != replayed.get("task_result_sha256")
        or batch.canonical_json_bytes(catalog)
        != batch.canonical_json_bytes(retained_catalog)
        or batch.canonical_json_bytes(catalog)
        != batch.canonical_json_bytes(validated_mechanics["book_catalog"])
        or item.get("independently_derived_book_catalog_sha256")
        != catalog.get("book_catalog_sha256")
    ):
        _fail("R6-v2 verifier result canonical dependency replay differs")
    return item


def build_source_blocked_slate_acceptance_v1(
    *,
    manifest_identity: object,
    manifest: Mapping[str, object],
    exact_panel_index: Mapping[str, object],
    mechanics_result_identity: object,
    mechanics_result: Mapping[str, object],
    verifier_result_identity: object,
    verifier_result: Mapping[str, object],
    matchup_source_snapshot_identity: object,
    matchup_source_snapshot: Mapping[str, object],
) -> dict[str, object]:
    """Bind an independently rerun result into the honest blocked status."""
    validated_manifest = validate_r6_v2_analysis_manifest_v1(
        manifest, exact_panel_index=exact_panel_index
    )
    retained_manifest_identity = _bind_identity_to_body(
        manifest_identity, validated_manifest, label="manifest"
    )
    validated_result = validate_r6_v2_mechanics_result_v1(
        mechanics_result,
        manifest_identity=retained_manifest_identity,
        manifest=validated_manifest,
        exact_panel_index=exact_panel_index,
    )
    retained_result_identity = _bind_identity_to_body(
        mechanics_result_identity, validated_result, label="mechanics result"
    )
    try:
        validated_source = runner.validate_matchup_source_snapshot(
            _mapping(matchup_source_snapshot, label="matchup source snapshot")
        )
    except Exception as exc:
        raise CorpusR6V2AnalysisReleaseError(
            "legacy/simple matchup snapshot did not replay"
        ) from exc
    retained_matchup_identity = _bind_identity_to_body(
        matchup_source_snapshot_identity,
        validated_source,
        label="matchup source snapshot",
    )
    if (
        retained_matchup_identity
        != validated_result["matchup_source_snapshot_identity"]
        or validated_source.get("matchup_source_snapshot_sha256")
        != validated_result["matchup_source_snapshot_sha256"]
        or validated_source.get("schema_version") != runner.MATCHUP_SOURCE_SCHEMA
    ):
        _fail("matchup source identity/content differs from mechanics result")
    validated_verifier = validate_r6_v2_verifier_result_v1(
        verifier_result,
        manifest_identity=retained_manifest_identity,
        manifest=validated_manifest,
        exact_panel_index=exact_panel_index,
        mechanics_result_identity=retained_result_identity,
        mechanics_result=validated_result,
        matchup_source_snapshot_identity=retained_matchup_identity,
        matchup_source_snapshot=validated_source,
    )
    retained_verifier_identity = _bind_identity_to_body(
        verifier_result_identity, validated_verifier, label="verifier result"
    )
    source_member = validated_manifest["source_members"][
        int(validated_result["source_ordinal"])
    ]
    if retained_verifier_identity["uri"] != source_member["verifier_result_uri"]:
        _fail("verifier result URI differs from the deterministic manifest path")
    worker_runtime = _validate_process_runtime_identity_v1(
        validated_verifier.get("worker_process_runtime"),
        role="run-slate-worker",
    )
    verifier_runtime = _validate_process_runtime_identity_v1(
        validated_verifier.get("verifier_process_runtime"),
        role="verify-slate-verifier",
    )
    replayed_upstream = dict(_mapping(
        validated_verifier["independently_replayed_upstream_task_result"],
        label="published verifier upstream result",
    ))
    replayed_catalog = dict(_mapping(
        validated_verifier["independently_derived_book_catalog"],
        label="published verifier book catalog",
    ))
    nested = _validate_upstream_nested_evidence_v1(replayed_upstream)
    reconstruction = nested["reconstruction_receipt"]
    matrix = nested["matrix_binding"]
    matchup_summary = nested["matchup_summary"]
    verification_replay = _with_hash({
        "schema_version": VERIFICATION_REPLAY_SCHEMA,
        "manifest_identity": retained_manifest_identity,
        "execution_manifest_sha256": validated_manifest[
            "execution_manifest_sha256"
        ],
        "source_ordinal": validated_result["source_ordinal"],
        "slate_id": validated_result["slate_id"],
        "panel_member_sha256": validated_result["panel_member_sha256"],
        "mechanics_result_identity": retained_result_identity,
        "mechanics_result_sha256": validated_result[
            "mechanics_result_sha256"
        ],
        "verifier_result_identity": retained_verifier_identity,
        "verifier_result_sha256": validated_verifier["verifier_result_sha256"],
        "worker_process_runtime_sha256": worker_runtime[
            "process_runtime_sha256"
        ],
        "verifier_process_runtime_sha256": verifier_runtime[
            "process_runtime_sha256"
        ],
        "task_acceptance_identity": replayed_upstream["task_acceptance_identity"],
        "carrier_identity": replayed_upstream["carrier_identity"],
        "later_source_freeze_identity": replayed_upstream[
            "later_source_freeze_identity"
        ],
        "world_artifact_identities": replayed_upstream[
            "world_artifact_identities"
        ],
        "world_artifact_identity_set_sha256": replayed_upstream[
            "world_artifact_identity_set_sha256"
        ],
        "matchup_source_snapshot_identity": retained_matchup_identity,
        "matchup_source_snapshot_sha256": validated_source[
            "matchup_source_snapshot_sha256"
        ],
        "verification_sha256": batch.canonical_sha256(nested["verification"]),
        "reconstruction_sha256": reconstruction["reconstruction_sha256"],
        "matrix_binding_sha256": matrix["matrix_binding_sha256"],
        "matchup_summary_sha256": matchup_summary["matchup_summary_sha256"],
        "retrieval_surface_sha256": replayed_upstream["retrieval_surface"][
            "retrieval_surface_sha256"
        ],
        "book_catalog_sha256": replayed_catalog["book_catalog_sha256"],
        "upstream_task_result_sha256": validated_result[
            "upstream_task_result_sha256"
        ],
        "independent_reexecution_task_result_sha256": replayed_upstream[
            "task_result_sha256"
        ],
        "exact_upstream_result_replay_verified": True,
        "verification_replayed": True,
        "reconstruction_replayed": True,
        "matchup_replayed": True,
        "admissions_recomputed": True,
        "neutral_controls_recomputed": True,
        "training_matrices_recomputed": True,
        "all_seven_rank80_books_recomputed": True,
        "uses_realized_outcomes": False,
        "r6_freeze_authority": False,
        "promotion_authority": False,
        "decision_authority": False,
    }, field="verification_replay_sha256")
    blockers = list(SOURCE_BLOCKER_CODES)
    body = {
        "schema_version": SLATE_ACCEPTANCE_SCHEMA,
        "publication_mode": PUBLICATION_MODE,
        "status": SLATE_STATUS,
        "accepted": False,
        "manifest_identity": retained_manifest_identity,
        "execution_manifest_sha256": validated_manifest[
            "execution_manifest_sha256"
        ],
        "source_ordinal": validated_result["source_ordinal"],
        "slate_id": validated_result["slate_id"],
        "panel_member_sha256": validated_result["panel_member_sha256"],
        "mechanics_result_identity": retained_result_identity,
        "mechanics_result_sha256": validated_result["mechanics_result_sha256"],
        "verifier_result_identity": retained_verifier_identity,
        "verifier_result_sha256": validated_verifier["verifier_result_sha256"],
        "worker_process_runtime": worker_runtime,
        "worker_process_runtime_sha256": worker_runtime[
            "process_runtime_sha256"
        ],
        "verifier_process_runtime": verifier_runtime,
        "verifier_process_runtime_sha256": verifier_runtime[
            "process_runtime_sha256"
        ],
        "independent_verification_replay": verification_replay,
        "independent_verification_replay_sha256": verification_replay[
            "verification_replay_sha256"
        ],
        "matchup_source_snapshot_identity": retained_matchup_identity,
        "matchup_source_snapshot_sha256": validated_source[
            "matchup_source_snapshot_sha256"
        ],
        "matchup_source_schema": runner.MATCHUP_SOURCE_SCHEMA,
        "matchup_source_content_replay_verified": True,
        "mechanics_content_replay_verified": True,
        "scientific_executor_replayed": True,
        "carrier_source_world_reopened": True,
        "verification_replayed": True,
        "reconstruction_replayed": True,
        "matchup_replayed": True,
        "admissions_recomputed": True,
        "neutral_controls_recomputed": True,
        "training_matrices_recomputed": True,
        "all_seven_rank80_books_recomputed": True,
        "complete_276_book_lattice_verified": True,
        "prefix_4_14_80_replay_verified": True,
        "source_blocker_codes": blockers,
        "source_blocker_codes_sha256": batch.canonical_sha256(blockers),
        "corrected_source_contract_present": False,
        "matchup_free_lane_authorized": False,
        "mechanics_complete": True,
        **{field: False for field in _FALSE_AUTHORITY_FIELDS},
    }
    return _with_hash(body, field="slate_acceptance_sha256")


def validate_source_blocked_slate_acceptance_v1(
    value: object,
    *,
    manifest_identity: object,
    manifest: Mapping[str, object],
    exact_panel_index: Mapping[str, object],
    mechanics_result_identity: object,
    mechanics_result: Mapping[str, object],
    verifier_result_identity: object,
    verifier_result: Mapping[str, object],
    matchup_source_snapshot_identity: object,
    matchup_source_snapshot: Mapping[str, object],
) -> dict[str, object]:
    item = dict(_mapping(value, label="R6-v2 slate acceptance"))
    _exact_keys(item, _ACCEPTANCE_KEYS, label="R6-v2 slate acceptance")
    if (
        item.get("schema_version") != SLATE_ACCEPTANCE_SCHEMA
        or item.get("publication_mode") != PUBLICATION_MODE
        or item.get("status") != SLATE_STATUS
        or item.get("accepted") is not False
        or item.get("source_blocker_codes") != list(SOURCE_BLOCKER_CODES)
        or item.get("source_blocker_codes_sha256")
        != batch.canonical_sha256(list(SOURCE_BLOCKER_CODES))
        or item.get("corrected_source_contract_present") is not False
        or item.get("matchup_free_lane_authorized") is not False
        or item.get("mechanics_complete") is not True
        or any(
            item.get(field) is not True
            for field in (
                "matchup_source_content_replay_verified",
                "mechanics_content_replay_verified",
                "scientific_executor_replayed",
                "carrier_source_world_reopened",
                "verification_replayed",
                "reconstruction_replayed",
                "matchup_replayed",
                "admissions_recomputed",
                "neutral_controls_recomputed",
                "training_matrices_recomputed",
                "all_seven_rank80_books_recomputed",
                "complete_276_book_lattice_verified",
                "prefix_4_14_80_replay_verified",
            )
        )
    ):
        _fail("R6-v2 slate acceptance status/source boundary differs")
    _false_authorities(item, label="R6-v2 slate acceptance")
    _self_hash(item, field="slate_acceptance_sha256", label="R6-v2 slate acceptance")
    expected = build_source_blocked_slate_acceptance_v1(
        manifest_identity=manifest_identity,
        manifest=manifest,
        exact_panel_index=exact_panel_index,
        mechanics_result_identity=mechanics_result_identity,
        mechanics_result=mechanics_result,
        verifier_result_identity=verifier_result_identity,
        verifier_result=verifier_result,
        matchup_source_snapshot_identity=matchup_source_snapshot_identity,
        matchup_source_snapshot=matchup_source_snapshot,
    )
    if batch.canonical_json_bytes(item) != batch.canonical_json_bytes(expected):
        _fail("R6-v2 slate acceptance canonical replay differs")
    return expected


def _execute_scientific_replay_v1(
    *,
    storage: ExactObjectStore,
    manifest: Mapping[str, object],
    panel: Mapping[str, object],
    panel_member: Mapping[str, object],
    source_member: Mapping[str, object],
    matchup_identity: Mapping[str, object],
    matchup_body: Mapping[str, object],
) -> dict[str, object]:
    try:
        return execution.execute_one_slate_r6_v2(
            validated_panel_index=panel,
            panel_index_identity=manifest["panel_index_identity"],
            accepted_slate_membership=panel_member,
            task_acceptance_identity=source_member["task_acceptance_identity"],
            carrier_identity=source_member["carrier_identity"],
            validated_matchup_source_snapshot=matchup_body,
            matchup_source_snapshot_identity=matchup_identity,
            read_exact=_read_exact_callback(storage),
            matchup_evidence_class=CURRENT_SOURCE_EVIDENCE_CLASS,
            minimum_supported_players=MINIMUM_SUPPORTED_PLAYERS,
            minimum_completeness=MINIMUM_COMPLETENESS,
            admission_m=ADMISSION_CAP,
            neutral_replicates=NEUTRAL_REPLICATES,
            neutral_seed_root=NEUTRAL_SEED_ROOT,
            worlds_per_block=None,
            require_authoritative=True,
        )
    except Exception as exc:
        raise CorpusR6V2AnalysisReleaseError(
            f"R6-v2 scientific execution failed for {source_member['slate_id']}"
        ) from exc


def run_r6_v2_analysis_slate_v1(
    *,
    storage: ExactObjectStore,
    manifest_identity: object,
    source_ordinal: int,
    matchup_source_snapshot_identity: object,
) -> dict[str, object]:
    """Worker-only execution: publish mechanics, never an acceptance."""
    normalized_manifest, manifest, panel = reopen_r6_v2_analysis_manifest_v1(
        storage=storage, manifest_identity=manifest_identity
    )
    _, panel_members = _validate_panel_body(panel)
    if type(source_ordinal) is not int or not 0 <= source_ordinal < 54:
        _fail("source ordinal must be one exact integer in 0..53")
    source_member = dict(manifest["source_members"][source_ordinal])
    panel_member = panel_members[source_ordinal]
    matchup_identity, matchup_body = _read_json(
        storage,
        matchup_source_snapshot_identity,
        label="legacy/simple matchup source snapshot",
    )
    worker_runtime = _process_runtime_identity_v1(role="run-slate-worker")
    upstream = _execute_scientific_replay_v1(
        storage=storage,
        manifest=manifest,
        panel=panel,
        panel_member=panel_member,
        source_member=source_member,
        matchup_identity=matchup_identity,
        matchup_body=matchup_body,
    )
    mechanics = build_r6_v2_mechanics_result_v1(
        manifest_identity=normalized_manifest,
        manifest=manifest,
        exact_panel_index=panel,
        source_ordinal=source_ordinal,
        matchup_source_snapshot_identity=matchup_identity,
        upstream_task_result=upstream,
        worker_process_runtime=worker_runtime,
    )
    validate_r6_v2_mechanics_result_v1(
        mechanics,
        manifest_identity=normalized_manifest,
        manifest=manifest,
        exact_panel_index=panel,
    )
    mechanics_identity = _publish_json(
        storage, uri=str(source_member["mechanics_result_uri"]), value=mechanics
    )
    _, reopened_mechanics = _read_json(
        storage, mechanics_identity, label="published mechanics result"
    )
    return {
        "source_ordinal": source_ordinal,
        "slate_id": source_member["slate_id"],
        "mechanics_result_identity": mechanics_identity,
        "worker_process_runtime_sha256": worker_runtime[
            "process_runtime_sha256"
        ],
        "status": WORKER_STATUS,
        "accepted": False,
        **{field: False for field in _FALSE_AUTHORITY_FIELDS},
    }


def verify_r6_v2_analysis_slate_v1(
    *,
    storage: ExactObjectStore,
    manifest_identity: object,
    mechanics_result_identity: object,
) -> dict[str, object]:
    """Independent process replay and source-blocked acceptance publication."""
    normalized_manifest, manifest, panel = reopen_r6_v2_analysis_manifest_v1(
        storage=storage, manifest_identity=manifest_identity
    )
    normalized_mechanics, mechanics = _read_json(
        storage, mechanics_result_identity, label="worker mechanics result"
    )
    validated_mechanics = validate_r6_v2_mechanics_result_v1(
        mechanics,
        manifest_identity=normalized_manifest,
        manifest=manifest,
        exact_panel_index=panel,
    )
    source_ordinal = validated_mechanics.get("source_ordinal")
    if type(source_ordinal) is not int or not 0 <= source_ordinal < 54:
        _fail("worker mechanics source ordinal differs")
    source_member = dict(manifest["source_members"][source_ordinal])
    _, panel_members = _validate_panel_body(panel)
    panel_member = panel_members[source_ordinal]
    if normalized_mechanics["uri"] != source_member["mechanics_result_uri"]:
        _fail("worker mechanics URI differs from the deterministic manifest path")
    matchup_identity, matchup_body = _read_json(
        storage,
        validated_mechanics["matchup_source_snapshot_identity"],
        label="verifier matchup source snapshot",
    )
    try:
        validated_matchup = runner.validate_matchup_source_snapshot(matchup_body)
    except Exception as exc:
        raise CorpusR6V2AnalysisReleaseError(
            "verifier matchup snapshot did not replay"
        ) from exc
    if matchup_identity != validated_mechanics["matchup_source_snapshot_identity"]:
        _fail("verifier matchup exact identity differs from worker mechanics")
    verifier_result = build_r6_v2_verifier_result_v1(
        storage=storage,
        manifest_identity=normalized_manifest,
        manifest=manifest,
        exact_panel_index=panel,
        mechanics_result_identity=normalized_mechanics,
        mechanics_result=validated_mechanics,
        matchup_source_snapshot_identity=matchup_identity,
        matchup_source_snapshot=validated_matchup,
    )
    verifier_result_identity = _publish_json(
        storage,
        uri=str(source_member["verifier_result_uri"]),
        value=verifier_result,
    )
    _, reopened_verifier_result = _read_json(
        storage, verifier_result_identity, label="published verifier result"
    )
    validate_r6_v2_verifier_result_v1(
        reopened_verifier_result,
        manifest_identity=normalized_manifest,
        manifest=manifest,
        exact_panel_index=panel,
        mechanics_result_identity=normalized_mechanics,
        mechanics_result=validated_mechanics,
        matchup_source_snapshot_identity=matchup_identity,
        matchup_source_snapshot=validated_matchup,
    )
    acceptance = build_source_blocked_slate_acceptance_v1(
        manifest_identity=normalized_manifest,
        manifest=manifest,
        exact_panel_index=panel,
        mechanics_result_identity=normalized_mechanics,
        mechanics_result=validated_mechanics,
        verifier_result_identity=verifier_result_identity,
        verifier_result=reopened_verifier_result,
        matchup_source_snapshot_identity=matchup_identity,
        matchup_source_snapshot=validated_matchup,
    )
    acceptance_identity = _publish_json(
        storage, uri=str(source_member["acceptance_uri"]), value=acceptance
    )
    _, reopened_acceptance = _read_json(
        storage, acceptance_identity, label="published slate acceptance"
    )
    validate_source_blocked_slate_acceptance_v1(
        reopened_acceptance,
        manifest_identity=normalized_manifest,
        manifest=manifest,
        exact_panel_index=panel,
        mechanics_result_identity=normalized_mechanics,
        mechanics_result=validated_mechanics,
        verifier_result_identity=verifier_result_identity,
        verifier_result=reopened_verifier_result,
        matchup_source_snapshot_identity=matchup_identity,
        matchup_source_snapshot=validated_matchup,
    )
    return {
        "source_ordinal": source_ordinal,
        "slate_id": source_member["slate_id"],
        "mechanics_result_identity": normalized_mechanics,
        "verifier_result_identity": verifier_result_identity,
        "slate_acceptance_identity": acceptance_identity,
        "verifier_process_runtime_sha256": verifier_result[
            "verifier_process_runtime_sha256"
        ],
        "status": SLATE_STATUS,
        "accepted": False,
        **{field: False for field in _FALSE_AUTHORITY_FIELDS},
    }


def _acceptance_dependencies(
    *,
    storage: ExactObjectStore,
    manifest_identity: Mapping[str, object],
    manifest: Mapping[str, object],
    panel: Mapping[str, object],
    acceptance_identity: object,
) -> tuple[dict[str, object], dict[str, object]]:
    normalized_acceptance, acceptance = _read_json(
        storage, acceptance_identity, label="R6-v2 slate acceptance"
    )
    source_ordinal = acceptance.get("source_ordinal")
    if type(source_ordinal) is not int or not 0 <= source_ordinal < 54:
        _fail("slate acceptance source ordinal differs")
    source_member = _mapping(
        manifest["source_members"][source_ordinal],
        label="manifest source member",
    )
    if normalized_acceptance["uri"] != source_member.get("acceptance_uri"):
        _fail("slate acceptance URI differs from deterministic manifest path")
    mechanics_identity = _identity(
        acceptance.get("mechanics_result_identity"), label="accepted mechanics result"
    )
    verifier_result_identity = _identity(
        acceptance.get("verifier_result_identity"), label="accepted verifier result"
    )
    matchup_identity = _identity(
        acceptance.get("matchup_source_snapshot_identity"),
        label="accepted matchup source",
    )
    _, mechanics = _read_json(
        storage, mechanics_identity, label="accepted mechanics result"
    )
    normalized_verifier_result, verifier_result = _read_json(
        storage, verifier_result_identity, label="accepted verifier result"
    )
    if normalized_verifier_result["uri"] != source_member.get("verifier_result_uri"):
        _fail("accepted verifier-result URI differs from deterministic manifest path")
    _, matchup = _read_json(
        storage, matchup_identity, label="accepted matchup source"
    )
    validated = validate_source_blocked_slate_acceptance_v1(
        acceptance,
        manifest_identity=manifest_identity,
        manifest=manifest,
        exact_panel_index=panel,
        mechanics_result_identity=mechanics_identity,
        mechanics_result=mechanics,
        verifier_result_identity=normalized_verifier_result,
        verifier_result=verifier_result,
        matchup_source_snapshot_identity=matchup_identity,
        matchup_source_snapshot=matchup,
    )
    return normalized_acceptance, validated


def _validate_retained_acceptance_shell_v1(
    *,
    identity: object,
    acceptance: object,
    manifest_identity: Mapping[str, object],
    manifest: Mapping[str, object],
    source_ordinal: int,
) -> tuple[dict[str, object], dict[str, object]]:
    item = dict(_mapping(acceptance, label=f"slate acceptance[{source_ordinal}]"))
    _exact_keys(
        item, _ACCEPTANCE_KEYS, label=f"slate acceptance[{source_ordinal}]"
    )
    retained_identity = _bind_identity_to_body(
        identity, item, label=f"slate acceptance[{source_ordinal}]"
    )
    _self_hash(
        item,
        field="slate_acceptance_sha256",
        label=f"slate acceptance[{source_ordinal}]",
    )
    _false_authorities(item, label=f"slate acceptance[{source_ordinal}]")
    source_member = _mapping(
        manifest["source_members"][source_ordinal],
        label=f"source member[{source_ordinal}]",
    )
    worker = _validate_process_runtime_identity_v1(
        item.get("worker_process_runtime"), role="run-slate-worker"
    )
    verifier = _validate_process_runtime_identity_v1(
        item.get("verifier_process_runtime"), role="verify-slate-verifier"
    )
    replay = dict(
        _mapping(
            item.get("independent_verification_replay"),
            label=f"verification replay[{source_ordinal}]",
        )
    )
    mechanics_identity = _identity(
        item.get("mechanics_result_identity"), label="mechanics identity"
    )
    verifier_result_identity = _identity(
        item.get("verifier_result_identity"), label="verifier-result identity"
    )
    matchup_identity = _identity(
        item.get("matchup_source_snapshot_identity"), label="matchup identity"
    )
    _exact_keys(
        replay,
        _VERIFICATION_REPLAY_KEYS,
        label=f"verification replay[{source_ordinal}]",
    )
    _self_hash(
        replay,
        field="verification_replay_sha256",
        label=f"verification replay[{source_ordinal}]",
    )
    required_replay_true = (
        "exact_upstream_result_replay_verified",
        "verification_replayed",
        "reconstruction_replayed",
        "matchup_replayed",
        "admissions_recomputed",
        "neutral_controls_recomputed",
        "training_matrices_recomputed",
        "all_seven_rank80_books_recomputed",
    )
    if (
        item.get("schema_version") != SLATE_ACCEPTANCE_SCHEMA
        or item.get("publication_mode") != PUBLICATION_MODE
        or item.get("status") != SLATE_STATUS
        or item.get("accepted") is not False
        or item.get("manifest_identity") != manifest_identity
        or item.get("execution_manifest_sha256")
        != manifest.get("execution_manifest_sha256")
        or item.get("source_ordinal") != source_ordinal
        or item.get("slate_id") != source_member.get("slate_id")
        or item.get("panel_member_sha256")
        != source_member.get("panel_member_sha256")
        or retained_identity["uri"] != source_member.get("acceptance_uri")
        or item.get("worker_process_runtime_sha256")
        != worker.get("process_runtime_sha256")
        or item.get("verifier_process_runtime_sha256")
        != verifier.get("process_runtime_sha256")
        or _process_instance_key(worker) == _process_instance_key(verifier)
        or item.get("independent_verification_replay_sha256")
        != replay.get("verification_replay_sha256")
        or replay.get("manifest_identity") != manifest_identity
        or replay.get("execution_manifest_sha256")
        != manifest.get("execution_manifest_sha256")
        or replay.get("source_ordinal") != source_ordinal
        or replay.get("slate_id") != source_member.get("slate_id")
        or replay.get("panel_member_sha256")
        != source_member.get("panel_member_sha256")
        or replay.get("mechanics_result_identity")
        != item.get("mechanics_result_identity")
        or mechanics_identity.get("uri")
        != source_member.get("mechanics_result_uri")
        or replay.get("mechanics_result_sha256")
        != item.get("mechanics_result_sha256")
        or verifier_result_identity.get("uri")
        != source_member.get("verifier_result_uri")
        or replay.get("verifier_result_identity")
        != item.get("verifier_result_identity")
        or replay.get("verifier_result_sha256")
        != item.get("verifier_result_sha256")
        or replay.get("worker_process_runtime_sha256")
        != worker.get("process_runtime_sha256")
        or replay.get("verifier_process_runtime_sha256")
        != verifier.get("process_runtime_sha256")
        or replay.get("matchup_source_snapshot_identity")
        != item.get("matchup_source_snapshot_identity")
        or replay.get("matchup_source_snapshot_sha256")
        != item.get("matchup_source_snapshot_sha256")
        or replay.get("upstream_task_result_sha256")
        != replay.get("independent_reexecution_task_result_sha256")
        or any(replay.get(field) is not True for field in required_replay_true)
        or replay.get("uses_realized_outcomes") is not False
        or replay.get("r6_freeze_authority") is not False
        or replay.get("promotion_authority") is not False
        or replay.get("decision_authority") is not False
        or item.get("source_blocker_codes") != list(SOURCE_BLOCKER_CODES)
        or item.get("source_blocker_codes_sha256")
        != batch.canonical_sha256(list(SOURCE_BLOCKER_CODES))
        or item.get("corrected_source_contract_present") is not False
        or item.get("matchup_free_lane_authorized") is not False
        or item.get("mechanics_complete") is not True
        or any(
            item.get(field) is not True
            for field in (
                "matchup_source_content_replay_verified",
                "mechanics_content_replay_verified",
                "scientific_executor_replayed",
                "carrier_source_world_reopened",
                "verification_replayed",
                "reconstruction_replayed",
                "matchup_replayed",
                "admissions_recomputed",
                "neutral_controls_recomputed",
                "training_matrices_recomputed",
                "all_seven_rank80_books_recomputed",
                "complete_276_book_lattice_verified",
                "prefix_4_14_80_replay_verified",
            )
        )
    ):
        _fail(f"slate acceptance[{source_ordinal}] full schema/binding differs")
    _sha(item.get("mechanics_result_sha256"), label="mechanics self-hash")
    _sha(item.get("verifier_result_sha256"), label="verifier-result self-hash")
    _sha(item.get("matchup_source_snapshot_sha256"), label="matchup self-hash")
    return retained_identity, item


def _build_source_blocked_panel_completion_body_v1(
    *,
    manifest_identity: object,
    manifest: Mapping[str, object],
    ordered_acceptance_identities: Sequence[object],
    ordered_acceptances: Sequence[Mapping[str, object]],
) -> dict[str, object]:
    normalized_manifest = _bind_identity_to_body(
        manifest_identity, manifest, label="manifest"
    )
    identities = [
        _identity(value, label=f"slate acceptance[{ordinal}]")
        for ordinal, value in enumerate(
            _sequence(ordered_acceptance_identities, label="acceptance identities")
        )
    ]
    acceptances = [
        dict(_mapping(value, label=f"slate acceptance[{ordinal}]"))
        for ordinal, value in enumerate(
            _sequence(ordered_acceptances, label="slate acceptances")
        )
    ]
    if len(identities) != 54 or len(acceptances) != 54:
        _fail("panel completion requires exactly 54 ordered acceptances")
    source_members = list(
        _sequence(manifest.get("source_members"), label="manifest source members")
    )
    seen_identities: set[tuple[str, str, str, int]] = set()
    rows: list[dict[str, object]] = []
    for ordinal, (identity, acceptance, source_member) in enumerate(
        zip(identities, acceptances, source_members, strict=True)
    ):
        retained_identity, validated_acceptance = (
            _validate_retained_acceptance_shell_v1(
                identity=identity,
                acceptance=acceptance,
                manifest_identity=normalized_manifest,
                manifest=manifest,
                source_ordinal=ordinal,
            )
        )
        key = _identity_key(
            retained_identity, label=f"slate acceptance[{ordinal}]"
        )
        if key in seen_identities:
            _fail("panel acceptance identity clone/splice detected")
        seen_identities.add(key)
        replay = _mapping(
            validated_acceptance["independent_verification_replay"],
            label=f"verification replay[{ordinal}]",
        )
        rows.append({
            "source_ordinal": ordinal,
            "slate_id": source_member["slate_id"],
            "panel_member_sha256": source_member["panel_member_sha256"],
            "acceptance_identity": retained_identity,
            "slate_acceptance_sha256": validated_acceptance[
                "slate_acceptance_sha256"
            ],
            "mechanics_result_identity": validated_acceptance[
                "mechanics_result_identity"
            ],
            "mechanics_result_sha256": validated_acceptance[
                "mechanics_result_sha256"
            ],
            "verifier_result_identity": validated_acceptance[
                "verifier_result_identity"
            ],
            "verifier_result_sha256": validated_acceptance[
                "verifier_result_sha256"
            ],
            "matchup_source_snapshot_identity": validated_acceptance[
                "matchup_source_snapshot_identity"
            ],
            "matchup_source_snapshot_sha256": validated_acceptance[
                "matchup_source_snapshot_sha256"
            ],
            "worker_process_runtime_sha256": validated_acceptance[
                "worker_process_runtime_sha256"
            ],
            "verifier_process_runtime_sha256": validated_acceptance[
                "verifier_process_runtime_sha256"
            ],
            "independent_verification_replay_sha256": validated_acceptance[
                "independent_verification_replay_sha256"
            ],
            "upstream_task_result_sha256": replay[
                "upstream_task_result_sha256"
            ],
            "status": SLATE_STATUS,
            "accepted": False,
        })
    body = {
        "schema_version": PANEL_COMPLETION_SCHEMA,
        "publication_mode": PUBLICATION_MODE,
        "status": PANEL_STATUS,
        "manifest_identity": normalized_manifest,
        "execution_manifest_sha256": manifest["execution_manifest_sha256"],
        "panel_index_identity": manifest["panel_index_identity"],
        "panel_index_sha256": manifest["panel_index_sha256"],
        "source_member_count": 54,
        "ordered_acceptance_count": 54,
        "ordered_acceptances": rows,
        "ordered_acceptances_sha256": batch.canonical_sha256(rows),
        "mechanics_complete_count": 54,
        "source_blocked_count": 54,
        "accepted_release_count": 0,
        "all_mechanics_complete": True,
        "all_sources_blocked": True,
        "accepted": False,
        "matchup_free_lane_authorized": False,
        "source_blocker_codes": list(SOURCE_BLOCKER_CODES),
        "source_blocker_codes_sha256": batch.canonical_sha256(
            list(SOURCE_BLOCKER_CODES)
        ),
        **{field: False for field in _FALSE_AUTHORITY_FIELDS},
    }
    return _with_hash(body, field="panel_completion_sha256")


def build_source_blocked_panel_completion_v1(
    *,
    storage: ExactObjectStore,
    manifest_identity: object,
    ordered_acceptance_identities: Sequence[object],
) -> dict[str, object]:
    """Exact-read/full-validate 54 dependencies and build one terminal body."""
    normalized_manifest, manifest, panel = reopen_r6_v2_analysis_manifest_v1(
        storage=storage, manifest_identity=manifest_identity
    )
    raw_identities = list(
        _sequence(ordered_acceptance_identities, label="ordered acceptances")
    )
    if len(raw_identities) != AUTHORITATIVE_SLATE_COUNT:
        _fail("panel completion requires exactly 54 acceptance identities")
    identities: list[dict[str, object]] = []
    acceptances: list[dict[str, object]] = []
    for ordinal, raw_identity in enumerate(raw_identities):
        identity, acceptance = _acceptance_dependencies(
            storage=storage,
            manifest_identity=normalized_manifest,
            manifest=manifest,
            panel=panel,
            acceptance_identity=raw_identity,
        )
        if acceptance.get("source_ordinal") != ordinal:
            _fail("panel completion acceptance order differs from source ordinals")
        identities.append(identity)
        acceptances.append(acceptance)
    return _build_source_blocked_panel_completion_body_v1(
        manifest_identity=normalized_manifest,
        manifest=manifest,
        ordered_acceptance_identities=identities,
        ordered_acceptances=acceptances,
    )


def validate_source_blocked_panel_completion_v1(
    *,
    storage: ExactObjectStore,
    manifest_identity: object,
    panel_completion_identity: object,
) -> dict[str, object]:
    """Post-publication replay of all 54 exact acceptance dependencies."""
    normalized_manifest, manifest, panel = reopen_r6_v2_analysis_manifest_v1(
        storage=storage, manifest_identity=manifest_identity
    )
    normalized_completion, completion = _read_json(
        storage, panel_completion_identity, label="published panel completion"
    )
    _exact_keys(completion, _PANEL_COMPLETION_KEYS, label="panel completion")
    _self_hash(
        completion, field="panel_completion_sha256", label="panel completion"
    )
    _false_authorities(completion, label="panel completion")
    if (
        normalized_completion["uri"] != manifest.get("panel_completion_uri")
        or completion.get("schema_version") != PANEL_COMPLETION_SCHEMA
        or completion.get("publication_mode") != PUBLICATION_MODE
        or completion.get("status") != PANEL_STATUS
        or completion.get("manifest_identity") != normalized_manifest
        or completion.get("execution_manifest_sha256")
        != manifest.get("execution_manifest_sha256")
        or completion.get("panel_index_identity")
        != manifest.get("panel_index_identity")
        or completion.get("panel_index_sha256") != manifest.get("panel_index_sha256")
        or completion.get("source_member_count") != 54
        or completion.get("ordered_acceptance_count") != 54
        or completion.get("mechanics_complete_count") != 54
        or completion.get("source_blocked_count") != 54
        or completion.get("accepted_release_count") != 0
        or completion.get("all_mechanics_complete") is not True
        or completion.get("all_sources_blocked") is not True
        or completion.get("accepted") is not False
        or completion.get("matchup_free_lane_authorized") is not False
        or completion.get("source_blocker_codes") != list(SOURCE_BLOCKER_CODES)
        or completion.get("source_blocker_codes_sha256")
        != batch.canonical_sha256(list(SOURCE_BLOCKER_CODES))
    ):
        _fail("panel completion schema/path/count/authority differs")
    rows = list(
        _sequence(
            completion.get("ordered_acceptances"),
            label="panel completion acceptances",
        )
    )
    if (
        len(rows) != 54
        or completion.get("ordered_acceptances_sha256")
        != batch.canonical_sha256(rows)
    ):
        _fail("panel completion ordered acceptance hash/count differs")
    identities: list[dict[str, object]] = []
    acceptances: list[dict[str, object]] = []
    seen: set[tuple[str, str, str, int]] = set()
    for ordinal, raw_row in enumerate(rows):
        row = dict(_mapping(raw_row, label=f"panel completion row[{ordinal}]"))
        _exact_keys(
            row,
            _PANEL_COMPLETION_ROW_KEYS,
            label=f"panel completion row[{ordinal}]",
        )
        identity = _identity(
            row.get("acceptance_identity"),
            label=f"panel completion acceptance[{ordinal}]",
        )
        key = _identity_key(identity, label="panel completion acceptance")
        if key in seen:
            _fail("panel completion acceptance clone/splice detected")
        seen.add(key)
        exact_identity, acceptance = _acceptance_dependencies(
            storage=storage,
            manifest_identity=normalized_manifest,
            manifest=manifest,
            panel=panel,
            acceptance_identity=identity,
        )
        if acceptance.get("source_ordinal") != ordinal:
            _fail("panel completion acceptance order differs")
        identities.append(exact_identity)
        acceptances.append(acceptance)
    expected = _build_source_blocked_panel_completion_body_v1(
        manifest_identity=normalized_manifest,
        manifest=manifest,
        ordered_acceptance_identities=identities,
        ordered_acceptances=acceptances,
    )
    if batch.canonical_json_bytes(completion) != batch.canonical_json_bytes(expected):
        _fail("panel completion canonical dependency replay differs")
    return expected


def finish_r6_v2_analysis_panel_v1(
    *,
    storage: ExactObjectStore,
    manifest_identity: object,
    ordered_acceptance_identities: Sequence[object],
) -> dict[str, object]:
    """Exact-reopen all 54 acceptances and publish the blocked terminal."""
    normalized_manifest, manifest, panel = reopen_r6_v2_analysis_manifest_v1(
        storage=storage, manifest_identity=manifest_identity
    )
    raw_identities = list(
        _sequence(ordered_acceptance_identities, label="ordered acceptances")
    )
    if len(raw_identities) != 54:
        _fail("finish-panel requires exactly 54 acceptance identities")
    identities: list[dict[str, object]] = []
    acceptances: list[dict[str, object]] = []
    for ordinal, raw_identity in enumerate(raw_identities):
        identity, acceptance = _acceptance_dependencies(
            storage=storage,
            manifest_identity=normalized_manifest,
            manifest=manifest,
            panel=panel,
            acceptance_identity=raw_identity,
        )
        if acceptance.get("source_ordinal") != ordinal:
            _fail("finish-panel acceptance order differs from source ordinals")
        identities.append(identity)
        acceptances.append(acceptance)
    completion = _build_source_blocked_panel_completion_body_v1(
        manifest_identity=normalized_manifest,
        manifest=manifest,
        ordered_acceptance_identities=identities,
        ordered_acceptances=acceptances,
    )
    completion_identity = _publish_json(
        storage, uri=str(manifest["panel_completion_uri"]), value=completion
    )
    validated_completion = validate_source_blocked_panel_completion_v1(
        storage=storage,
        manifest_identity=normalized_manifest,
        panel_completion_identity=completion_identity,
    )
    if batch.canonical_json_bytes(validated_completion) != batch.canonical_json_bytes(
        completion
    ):
        _fail("published panel completion differs after dependency replay")
    return {
        "panel_completion_identity": completion_identity,
        "panel_completion_sha256": completion["panel_completion_sha256"],
        "status": PANEL_STATUS,
        "mechanics_complete_count": 54,
        "source_blocked_count": 54,
        "accepted_release_count": 0,
        "accepted": False,
        **{field: False for field in _FALSE_AUTHORITY_FIELDS},
    }


__all__ = [
    "ADMISSION_CAP",
    "AUTHORITATIVE_SLATE_COUNT",
    "BOOKS_PER_SCOPE",
    "BOOKS_PER_SLATE",
    "CorpusR6V2AnalysisReleaseError",
    "CURRENT_SOURCE_DISPOSITION",
    "CURRENT_SOURCE_EVIDENCE_CLASS",
    "EXPECTED_RELEASE_IMPLEMENTATION_SHA256",
    "FIT_SCOPE_IDS",
    "MANIFEST_SCHEMA",
    "MECHANICS_RESULT_SCHEMA",
    "NEUTRAL_REPLICATES",
    "PANEL_COMPLETION_SCHEMA",
    "PANEL_STATUS",
    "PREFIX_SIZES",
    "PUBLICATION_MODE",
    "SLATE_ACCEPTANCE_SCHEMA",
    "SLATE_STATUS",
    "SOURCE_BLOCKER_CODES",
    "STRATEGY_IDS",
    "VERIFICATION_REPLAY_SCHEMA",
    "VERIFIER_RESULT_SCHEMA",
    "WORKER_STATUS",
    "build_r6_v2_analysis_manifest_v1",
    "build_r6_v2_mechanics_result_v1",
    "build_r6_v2_verifier_result_v1",
    "build_source_blocked_panel_completion_v1",
    "build_source_blocked_slate_acceptance_v1",
    "derive_r6_v2_book_catalog_v1",
    "finish_r6_v2_analysis_panel_v1",
    "prepare_r6_v2_analysis_release_v1",
    "release_implementation_contract_v1",
    "reopen_r6_v2_analysis_manifest_v1",
    "run_r6_v2_analysis_slate_v1",
    "validate_r6_v2_analysis_manifest_v1",
    "validate_r6_v2_mechanics_result_v1",
    "validate_r6_v2_verifier_result_v1",
    "validate_source_blocked_slate_acceptance_v1",
    "validate_source_blocked_panel_completion_v1",
    "verify_r6_v2_analysis_slate_v1",
]
