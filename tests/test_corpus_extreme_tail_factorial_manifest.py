from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
from types import SimpleNamespace
from typing import Callable

import pytest

from nfl_dfs.research import corpus_extreme_tail_factorial_manifest as manifest
from nfl_dfs.research import corpus_parametric_batch as batch


COMMIT = "a" * 40
DIGEST = "sha256:" + "b" * 64
IMAGE = {
    "uri": f"us-central1-docker.pkg.dev/example/research/factorial@{DIGEST}",
    "digest": DIGEST,
}
OUTPUT_PREFIX = "gs://fixture-bucket/research/factorial/run-001/"
CATALOG_ID = "fixture-factorial-source-catalog-v1"
CATALOG_URI = "gs://fixture-bucket/research/factorial/source-catalog-v1.json"


def _identity(label: str, ordinal: int) -> dict[str, object]:
    payload = f"{label}:{ordinal}".encode()
    return {
        "uri": f"gs://fixture-bucket/objects/{label}-{ordinal:05d}.json",
        "generation": str(10_000 + ordinal),
        "sha256": sha256(payload).hexdigest(),
        "bytes": len(payload),
    }


def _source_members() -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    source_ordinal = 0
    world_ordinal = 10_000
    for season in (2023, 2024, 2025):
        for week in range(1, 19):
            blocks = (
                ("R0", "R1", "R2", "R4")
                if (season, week) == (2025, 1)
                else ("R0", "R1", "R2", "R3", "R4")
            )
            rows.append({
                "source_ordinal": source_ordinal,
                "slate_id": f"{season}-w{week:02d}",
                "season": season,
                "week": week,
                "reconstruction_source_identity": _identity(
                    "reconstruction", source_ordinal
                ),
                "ordinary_r_blocks": [
                    {
                        "block_id": block_id,
                        "world_count": 10_000,
                        "world_identity": _identity("world", world_ordinal + index),
                    }
                    for index, block_id in enumerate(blocks)
                ],
            })
            world_ordinal += 5
            source_ordinal += 1
    return rows


def _build(
    sources: list[dict[str, object]] | None = None,
    *,
    source_catalog: dict[str, object] | None = None,
    source_catalog_identity: dict[str, object] | None = None,
    p0_environment: dict[str, object] | None = None,
    p0_environment_sha256: str | None = None,
    source_commit_sha: str = COMMIT,
    immutable_image: dict[str, object] | None = None,
    output_prefix: str = OUTPUT_PREFIX,
) -> dict[str, object]:
    if source_catalog is None:
        source_catalog, source_catalog_identity = _source_catalog(
            _source_members() if sources is None else sources
        )
    assert source_catalog_identity is not None
    if p0_environment is None:
        p0_environment = (
            manifest.frozen_extreme_tail_factorial_p0_environment_v1()
        )
    if p0_environment_sha256 is None:
        p0_environment_sha256 = batch.canonical_sha256(p0_environment)
    if immutable_image is None:
        immutable_image = IMAGE
    return manifest.build_extreme_tail_factorial_execution_manifest_v1(
        source_catalog=source_catalog,
        source_catalog_identity=source_catalog_identity,
        p0_generation_environment=p0_environment,
        p0_generation_environment_sha256=p0_environment_sha256,
        source_commit_sha=source_commit_sha,
        immutable_image=immutable_image,
        output_prefix=output_prefix,
    )


def _source_catalog(
    sources: list[dict[str, object]] | None = None,
) -> tuple[dict[str, object], dict[str, object]]:
    catalog = manifest.build_extreme_tail_factorial_source_catalog_v1(
        catalog_id=CATALOG_ID,
        source_members=_source_members() if sources is None else sources,
    )
    identity = batch.object_identity_for_json(
        catalog,
        uri=CATALOG_URI,
        generation="9001",
    )
    return catalog, identity


def _validate(
    value: object,
    *,
    sources: list[dict[str, object]] | None = None,
    source_catalog: dict[str, object] | None = None,
    source_catalog_identity: dict[str, object] | None = None,
    p0_environment: dict[str, object] | None = None,
    p0_environment_sha256: str | None = None,
) -> dict[str, object]:
    if source_catalog is None:
        source_catalog, source_catalog_identity = _source_catalog(
            _source_members() if sources is None else sources
        )
    assert source_catalog_identity is not None
    if p0_environment is None:
        p0_environment = (
            manifest.frozen_extreme_tail_factorial_p0_environment_v1()
        )
    if p0_environment_sha256 is None:
        p0_environment_sha256 = batch.canonical_sha256(p0_environment)
    return manifest.validate_extreme_tail_factorial_execution_manifest_v1(
        value,
        source_catalog=source_catalog,
        source_catalog_identity=source_catalog_identity,
        p0_generation_environment=p0_environment,
        p0_generation_environment_sha256=p0_environment_sha256,
        source_commit_sha=COMMIT,
        immutable_image=IMAGE,
        output_prefix=OUTPUT_PREFIX,
    )


def _rehash(value: dict[str, object]) -> dict[str, object]:
    retained = deepcopy(value)
    retained.pop("execution_manifest_sha256", None)
    retained["execution_manifest_sha256"] = batch.canonical_sha256(retained)
    return retained


def _catalog_identity_for(
    catalog: dict[str, object], *, generation: str = "9002"
) -> dict[str, object]:
    return batch.object_identity_for_json(
        catalog,
        uri=CATALOG_URI,
        generation=generation,
    )


def _rehash_catalog(value: dict[str, object]) -> dict[str, object]:
    retained = deepcopy(value)
    retained.pop("source_catalog_sha256", None)
    retained["source_catalog_sha256"] = batch.canonical_sha256(retained)
    return retained


def test_manifest_freezes_exact_53_slate_exclusion_and_evaluation_surface() -> None:
    value = _build()
    catalog, catalog_identity = _source_catalog()

    assert value["schema_version"] == (
        "foundry-extreme-tail-factorial-execution-manifest/v1"
    )
    assert value["publication_mode"] == "create_once"
    assert value["protocol_document"] == (
        "reports/2026-08-25-pre-week1-historical-experiment-matrix.md"
    )
    assert value["protocol_sha256"] == (
        "4cd61f51617322bcafb3e2a867332ed4e35484073aa47c3d9891339fd493f338"
    )
    assert value["factorial_slate_count"] == 53
    assert value["source_catalog_identity"] == catalog_identity
    assert value["source_catalog_id"] == CATALOG_ID
    assert value["source_catalog_sha256"] == catalog["source_catalog_sha256"]
    assert value["source_membership_sha256"] == catalog[
        "source_membership_sha256"
    ]
    assert value["source_membership_acceptance_sha256"] == catalog[
        "membership_acceptance_sha256"
    ]
    slates = value["factorial_slates"]
    assert isinstance(slates, list)
    assert len(slates) == 53
    assert [row["factorial_slate_ordinal"] for row in slates] == list(range(53))
    assert [row["source_ordinal"] for row in slates] == [
        ordinal for ordinal in range(54) if ordinal != 36
    ]
    assert slates[35]["slate_id"] == "2024-w18"
    assert slates[36]["slate_id"] == "2025-w02"
    assert "2025-w01" not in {row["slate_id"] for row in slates}

    source = value["source_catalog_contract"]
    assert source["input_slate_count"] == 54
    assert source["retained_slate_count"] == 53
    assert source["mechanical_exclusion"] == {
        "source_ordinal": 36,
        "slate_id": "2025-w01",
        "season": 2025,
        "week": 1,
        "available_block_ids": ["R0", "R1", "R2", "R4"],
        "missing_block_id": "R3",
        "reason": "four-origin-recovery-cannot-satisfy-five-fold-law",
        "excluded_source_member_sha256": batch.canonical_sha256(
            _source_members()[36]
        ),
        "effect_or_outcome_access_used": False,
    }

    evaluation = value["ordinary_r_evaluation_contract"]
    assert evaluation["evaluation_blocks"] == ["R0", "R1", "R2", "R3", "R4"]
    assert evaluation["worlds_per_block"] == 10_000
    assert evaluation["score_world_count_per_slate"] == 50_000
    assert evaluation["factorial_heldout_fold_count"] == 265
    assert evaluation["all_block_final_fit_count"] == 53
    assert evaluation["canonical_54_slate_panel_support_authority"] is False


def test_source_catalog_is_canonical_self_hashed_and_membership_accepted() -> None:
    catalog, identity = _source_catalog()
    assert catalog["schema_version"] == "foundry-factorial-source-catalog/v1"
    assert catalog["publication_mode"] == "create_once"
    assert catalog["catalog_id"] == CATALOG_ID
    assert catalog["source_member_count"] == 54
    assert catalog["source_membership_authority"] is True
    assert catalog["uses_realized_outcomes"] is False
    assert catalog["source_members_sha256"] == batch.canonical_sha256(
        catalog["source_members"]
    )
    assert catalog["source_membership_sha256"] == batch.canonical_sha256(
        catalog["source_membership"]
    )
    assert catalog["membership_acceptance_sha256"] == batch.canonical_sha256(
        catalog["membership_acceptance"]
    )
    assert catalog["source_catalog_sha256"] == batch.canonical_sha256({
        key: item
        for key, item in catalog.items()
        if key != "source_catalog_sha256"
    })
    batch.validate_json_identity(catalog, identity, label="fixture source catalog")
    acceptance = catalog["membership_acceptance"]
    assert acceptance == {
        "schema_version": "foundry-factorial-source-membership-acceptance/v1",
        "catalog_id": CATALOG_ID,
        "source_member_count": 54,
        "source_members_sha256": catalog["source_members_sha256"],
        "source_membership_sha256": catalog["source_membership_sha256"],
        "exact_ordered_grid_complete": True,
        "all_source_objects_generation_pinned": True,
        "accepted": True,
        "uses_realized_outcomes": False,
    }


def test_coherent_source_catalog_change_cannot_reuse_authoritative_identity() -> None:
    sources = _source_members()
    original, original_identity = _source_catalog(sources)
    sources[10]["ordinary_r_blocks"][2]["world_identity"] = _identity(
        "replacement-world", 99_999
    )
    changed, _changed_identity = _source_catalog(sources)
    assert changed["source_catalog_sha256"] != original["source_catalog_sha256"]
    with pytest.raises(
        manifest.CorpusExtremeTailFactorialManifestError,
        match="generation-pinned identity",
    ):
        _build(
            source_catalog=changed,
            source_catalog_identity=original_identity,
        )


def test_coherent_membership_and_acceptance_splices_fail_catalog_replay() -> None:
    original, _identity_value = _source_catalog()

    membership = deepcopy(original)
    membership["source_membership"][0]["slate_id"] = "2023-w02"
    membership["source_membership_sha256"] = batch.canonical_sha256(
        membership["source_membership"]
    )
    membership["membership_acceptance"]["source_membership_sha256"] = (
        membership["source_membership_sha256"]
    )
    membership["membership_acceptance_sha256"] = batch.canonical_sha256(
        membership["membership_acceptance"]
    )
    membership = _rehash_catalog(membership)

    acceptance = deepcopy(original)
    acceptance["membership_acceptance"]["accepted"] = False
    acceptance["membership_acceptance_sha256"] = batch.canonical_sha256(
        acceptance["membership_acceptance"]
    )
    acceptance = _rehash_catalog(acceptance)

    for ordinal, changed in enumerate((membership, acceptance), start=2):
        changed_identity = _catalog_identity_for(
            changed, generation=str(9_000 + ordinal)
        )
        with pytest.raises(
            manifest.CorpusExtremeTailFactorialManifestError,
            match="membership",
        ):
            _build(
                source_catalog=changed,
                source_catalog_identity=changed_identity,
            )


def test_source_catalog_self_hash_and_unknown_field_fail_closed() -> None:
    catalog, identity = _source_catalog()
    damaged = deepcopy(catalog)
    damaged["source_member_count"] = 53
    with pytest.raises(
        manifest.CorpusExtremeTailFactorialManifestError,
        match="accepted 54-slate catalog",
    ):
        _build(source_catalog=damaged, source_catalog_identity=identity)

    unknown = deepcopy(catalog)
    unknown["latest_alias"] = True
    unknown = _rehash_catalog(unknown)
    unknown_identity = _catalog_identity_for(unknown)
    with pytest.raises(
        manifest.CorpusExtremeTailFactorialManifestError,
        match="fields differ",
    ):
        _build(
            source_catalog=unknown,
            source_catalog_identity=unknown_identity,
        )


def test_complete_p0_environment_and_exact_three_key_pb_derivation_are_bound() -> None:
    value = _build()
    p0 = manifest.frozen_extreme_tail_factorial_p0_environment_v1()
    assert len(p0) == 66
    assert value["p0_generation_environment"] == p0
    assert value["p0_generation_environment_sha256"] == (
        "7a638d185a5cffdbbd47a336c970a5c211d4c86c08e590fc4015b8d385cd9b51"
    )
    assert value["pb_generation_environment_sha256"] == (
        "5af2b68289bd2cbfc3e461bd3cd5fd8a72058c9da2caa664795589424f3815a4"
    )
    populations = value["population_registry"]
    assert populations[0]["complete_generation_environment"] == p0
    pb = populations[1]["complete_generation_environment"]
    assert set(pb) == set(p0)
    assert {
        key: (p0[key], pb[key])
        for key in p0
        if p0[key] != pb[key]
    } == {
        "BOOM_UNIQUE_FILL": ("0", "1"),
        "CAND_MULT": ("2", "0"),
        "N_BOOM": ("40", "200"),
    }
    assert populations[0]["generation_environment_sha256"] == batch.canonical_sha256(
        p0
    )
    assert populations[1]["generation_environment_sha256"] == batch.canonical_sha256(
        pb
    )


@pytest.mark.parametrize(
    "mutate",
    [
        lambda environment: environment.__setitem__("N_BOOM", "41"),
        lambda environment: environment.__setitem__("BOOM_UNIQUE_FILL", ""),
        lambda environment: environment.pop("N_DARKGAME"),
        lambda environment: environment.__setitem__("UNREGISTERED_FILL", "1"),
    ],
)
def test_coherent_p0_environment_drift_fails_closed(
    mutate: Callable[[dict[str, object]], object],
) -> None:
    environment: dict[str, object] = dict(
        manifest.frozen_extreme_tail_factorial_p0_environment_v1()
    )
    mutate(environment)
    with pytest.raises(
        manifest.CorpusExtremeTailFactorialManifestError,
        match="complete frozen law",
    ):
        _build(
            p0_environment=environment,
            p0_environment_sha256=batch.canonical_sha256(environment),
        )


def test_p0_environment_hash_mismatch_fails_closed() -> None:
    environment = manifest.frozen_extreme_tail_factorial_p0_environment_v1()
    with pytest.raises(
        manifest.CorpusExtremeTailFactorialManifestError,
        match="complete frozen law",
    ):
        _build(
            p0_environment=dict(environment),
            p0_environment_sha256="f" * 64,
        )


def test_exact_twenty_volume_origins_and_k_masks_are_literal() -> None:
    value = _build()
    origins = value["candidate_origin_registry"]
    assert len(origins) == 20
    assert [row["origin_id"] for row in origins] == [
        f"R{ordinal}" for ordinal in range(20)
    ]
    assert [(row["projection_seed"], row["role_seed"]) for row in origins] == [
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
    ]
    assert {row["origin_class"] for row in origins[:5]} == {
        "registered-incumbent-five"
    }
    assert {row["origin_class"] for row in origins[5:]} == {
        "prospective-volume-shadow-extra-fifteen"
    }
    assert all(row["candidate_discovery_only"] is False for row in origins[:5])
    assert all(row["candidate_discovery_only"] is True for row in origins[5:])
    assert [row["evaluation_block"] for row in origins[:5]] == [
        "R0",
        "R1",
        "R2",
        "R3",
        "R4",
    ]
    assert all(row["evaluation_block"] is None for row in origins[5:])

    masks = value["candidate_origin_masks"]
    assert masks == [
        {
            "mask_ordinal": 0,
            "mask_id": "K5",
            "origin_count": 5,
            "origin_ids": ["R0", "R1", "R2", "R3", "R4"],
        },
        {
            "mask_ordinal": 1,
            "mask_id": "K20",
            "origin_count": 20,
            "origin_ids": [f"R{ordinal}" for ordinal in range(20)],
        },
    ]


def test_population_contract_freezes_incumbent_and_all_boom_laws() -> None:
    populations = _build()["population_registry"]
    assert [row["population_id"] for row in populations] == [
        "P0-incumbent-native",
        "PB-frozen-all-boom",
    ]
    assert populations[0]["literal_generation_levers"] == {
        "CAND_MULT": "2",
        "N_BOOM": "40",
        "BOOM_UNIQUE_FILL": "0",
    }
    assert populations[1]["literal_generation_levers"] == {
        "CAND_MULT": "0",
        "N_BOOM": "200",
        "BOOM_UNIQUE_FILL": "1",
    }
    assert populations[0]["role_native_law"] == populations[1]["role_native_law"]
    assert populations[0]["required_retained_shortfall_per_origin"] == 0
    assert populations[1]["required_retained_shortfall_per_origin"] == 0
    assert populations[1]["only_keys_changed_from_p0"] == [
        "BOOM_UNIQUE_FILL",
        "CAND_MULT",
        "N_BOOM",
    ]
    assert populations[0]["result_acceptance_law"] == populations[1][
        "result_acceptance_law"
    ]
    assert populations[0]["result_acceptance_law"] == {
        "required_retained_shortfall_per_origin": 0,
        "p0_pb_retained_count_parity_required_per_origin": True,
        "failed_origin_if_either_population_count_differs": True,
        "optimizer_visits_calls_successes_and_unique_additions_retained": True,
    }
    assert populations[1]["unique_fill_may_visit_more_than_200_worlds"] is True
    assert populations[1]["r5_through_r19_are_new_labeled_reconstructions"]


def test_cross_fit_law_strips_only_heldout_candidate_origin_provenance() -> None:
    cross_fit = _build()["candidate_origin_cross_fit_contract"]
    folds = cross_fit["folds"]
    assert len(folds) == 5
    for heldout_ordinal, fold in enumerate(folds):
        heldout = f"R{heldout_ordinal}"
        assert fold["heldout_block_id"] == heldout
        assert fold["removed_candidate_origin_id"] == heldout
        assert heldout not in fold["training_block_ids"]
        assert heldout not in fold["eligible_origin_ids_by_mask"]["K5"]
        assert heldout not in fold["eligible_origin_ids_by_mask"]["K20"]
        assert fold["eligible_origin_ids_by_mask"]["K20"][4:] == [
            f"R{ordinal}" for ordinal in range(5, 20)
        ]
    assert cross_fit[
        "heldout_origin_occurrence_tags_counts_and_attribution_stripped"
    ]
    assert cross_fit[
        "duplicate_roster_survives_only_with_a_training_origin_occurrence"
    ]
    assert cross_fit["population_provenance_never_transfers_between_p0_and_pb"]
    assert cross_fit["k20_provenance_never_transfers_into_k5"]
    assert cross_fit["selected_ids_freeze_before_heldout_block_metrics"]
    assert cross_fit["realized_outcomes_forbidden"]


def test_eight_cells_and_exact_retrieval_catalog_are_frozen() -> None:
    value = _build()
    cells = value["factorial_cell_registry"]
    assert [row["cell_id"] for row in cells] == [
        "H01-P0-K5-R194",
        "H02-P0-K5-T230",
        "H03-P0-K20-R194",
        "H04-P0-K20-T230",
        "H05-PB-K5-R194",
        "H06-PB-K5-T230",
        "H07-PB-K20-R194",
        "H08-PB-K20-T230",
    ]
    assert [row["entry_budgets"] for row in cells] == [[4, 14, 80]] * 8
    assert {
        (row["population_id"], row["candidate_origin_mask_id"])
        for row in cells
    } == {
        ("P0-incumbent-native", "K5"),
        ("P0-incumbent-native", "K20"),
        ("PB-frozen-all-boom", "K5"),
        ("PB-frozen-all-boom", "K20"),
    }

    contract = value["retrieval_contract"]
    expected_ids = [
        "coverage-194-v1",
        "coverage-ge-230-v1",
        "bounded-tail-ladder-ge-210-250-v1",
        "block-robust-bounded-tail-ge-210-250-v1",
        "individual-ge-230-rank-v1",
        "frozen-census-support-switch-ge-230/v1",
        "support-switched-event-component-tickets-ge-230-v1",
        "individual-training-maximum-rank-v1",
        "training-hit-ge-230-admission-v1",
        "strict-200-coverage-v1",
        "tail-ladder-200-210-220-v1",
        "mean-score-v1",
        "expected-max-v1",
        "block-supported-tail-ladder-v1",
        "regime-robust-ladder-v1",
        "convex-excess-expected-max-ge-200-v1",
        "block-supported-bounded-tail-ge-210-250-v1",
        "maximum-coverage-ge-230-oracle-diagnostic-v1",
    ]
    assert contract["retrieval_ids"] == expected_ids
    assert [row["retrieval_id"] for row in contract["catalog"]] == expected_ids
    assert contract["primary_factorial_retrieval_ids"] == [
        "coverage-194-v1",
        "frozen-census-support-switch-ge-230/v1",
    ]
    assert contract["secondary_substrate_retrieval_ids"] == expected_ids[1:5] + (
        expected_ids[6:]
    )
    assert contract["catalog_count"] == 18
    assert contract["selector_retrieval_ids"] == expected_ids[:-1]
    assert contract["diagnostic_retrieval_ids"] == expected_ids[-1:]
    assert [row["execution_kind"] for row in contract["catalog"]] == (
        ["selector"] * 17 + ["diagnostic"]
    )
    assert contract["entry_budgets"] == [4, 14, 80]
    assert contract["ranking_depth"] == 80
    assert contract["bounded_tail_rungs"] == [
        {"threshold": 210.0, "operator": ">=", "weight": 1},
        {"threshold": 220.0, "operator": ">=", "weight": 2},
        {"threshold": 230.0, "operator": ">=", "weight": 4},
        {"threshold": 240.0, "operator": ">=", "weight": 8},
        {"threshold": 250.0, "operator": ">=", "weight": 16},
    ]
    expected_strategy_hashes = [
        "1e1e6a11149ca1c8c9babd183b85adb2ce27d0f976ca863b43768aa3dab0433f",
        "c43598db8dc2b081158f0660f8edc1ccae4ce1c58ff6a468036c6dbc089fa965",
        "e769cadb1a3189d736784225647d9a7342ab4ea25bd2b55f632dd0ec8de254fa",
        "b3c4bf6ea5e09446e0fff6b901412c7e9370a1b0e1ac0053d864eaef36f958d9",
        "d267f5401fd234ba962d6d350d4dac2716a8e3c9e789a2e7c8a91a79cd9a1aee",
        "e44525130cdd119d441178da9f2a003876f63d328b44f1730b48064ef61d56ab",
        "e39218d78f697d08630363610da96d0a395bebdce770522ef476adc8eeab145b",
        "7d0c3458accdd91e96aa8bb7513fd333e0804ae846216e823242d839cbc177c2",
        "4f5ffe15d0df57f245426113f48c63b0e1abee68dd4a903b94ff6e9fe0728fda",
        "9689bb11de4616e4a6295ae0a5b0ec30aa174097f1965867fdc08d7b2e7d02de",
        "5561d663cdc2ec8f928ddf5a44889f16e3c23cdd264f4c8fef7925547aa527ea",
        "5c880aeca7c8ec3386a9d44b111937fada857f569cb324dd2163987b333654c6",
        "ad94b80a0ea61d1c58f64f825f00f0d0fea47f36158a239c29382836ff2cb780",
        "1ae24780c211a329e8a9867e5dec39630a7efcc640deba9e05561f6a8c98668b",
        "125610a3fda4c230bacd44f1778e43fe03905a504d55ec6fe4c424c0cbbd0e7b",
        "189dc6986c7d70b8315f9e41cb1fe5c6fce35c54f2756729254a0e1614dd1082",
        "a2070561cfb0a2c2c049b27d5e5ff71682a87d3568254b09ebf987a58d775954",
        "b40a7ed84af58f62ba1c4d814bcaf6f360ffb09e286963d348790f9f007b6b6e",
    ]
    expected_implementation_hashes = [
        "bc54abd13c4a5ecd5966dcc5e1b78afb06028850865517bde754507ccc40e94f",
        *[
            "0ede95f034186bdf382af8a9c87c311b83799c5e9609ec11d2cffb3c2114ce4b"
        ]
        * 4,
        "73f53f8b3e7b8d9ec6c661de16e5c171917526858bc1a358a555fcc78085bd30",
        "026d6b94f9867fc01cd5e17acec6539b963a9914d17c894c815e96ee3106cd91",
        "bc54abd13c4a5ecd5966dcc5e1b78afb06028850865517bde754507ccc40e94f",
        "bc54abd13c4a5ecd5966dcc5e1b78afb06028850865517bde754507ccc40e94f",
        *[
            "01f62c080451f6d090da782c47474e86ae8302a1a57df698d2df16fb5dcffac7"
        ]
        * 6,
        *[
            "1c94e9635d6038f629c40ce81cc2b3b3ed4fcad600e4832a0f231c5c9c19403d"
        ]
        * 3,
    ]
    assert [
        row["strategy_contract_sha256"] for row in contract["catalog"]
    ] == expected_strategy_hashes
    assert [
        row["implementation_contract_sha256"]
        for row in contract["catalog"]
    ] == expected_implementation_hashes
    for row in contract["catalog"]:
        assert isinstance(row["strategy_contract"], dict)
        assert isinstance(row["implementation_contract"], dict)
        assert row["strategy_contract_sha256"] in row["strategy_contract"].values()
        assert row["implementation_contract_sha256"] in row[
            "implementation_contract"
        ].values()
    assert contract["catalog_sha256"] == batch.canonical_sha256(
        contract["catalog"]
    )
    substrate = contract["selection_substrate_contract"]
    assert substrate["substrate_ids"] == ["P0-K5", "P0-K20", "PB-K5", "PB-K20"]
    assert substrate["candidate_admission_law"] == (
        "fold-eligible-full-union-only/v1"
    )
    assert substrate["candidate_scope"] == (
        "complete-population-and-origin-mask-eligible-union"
    )
    assert substrate["cross_fit_scope"] == (
        "four-ordinary-r-training-blocks-after-heldout-origin-stripping"
    )
    assert substrate["final_fit_scope"] == "all-five-ordinary-r-blocks"
    assert substrate["candidate_scope_is_not_part_of_strategy_identity"]
    assert contract["selection_substrate_contract_sha256"] == (
        batch.canonical_sha256({
            key: item
            for key, item in substrate.items()
            if key != "selection_substrate_contract_sha256"
        })
    )
    assert {
        row["selection_substrate_contract_sha256"]
        for row in contract["catalog"]
    } == {contract["selection_substrate_contract_sha256"]}

    support_row = contract["catalog"][5]
    assert support_row["strategy_contract"]["gate_law"] == {
        "threshold_id": "ge_230",
        "score": 230.0,
        "operator": ">=",
        "requires_every_training_block_nonzero": True,
        "fold_training_block_count": 4,
        "fold_minimum_opportunity_world_count": 100,
        "final_training_block_count": 5,
        "final_minimum_opportunity_world_count": 125,
    }
    assert support_row["strategy_contract"]["switch_law"][
        "passed_strategy_id"
    ] == "coverage-ge-230-v1"
    assert support_row["strategy_contract"]["switch_law"][
        "failed_strategy_id"
    ] == "block-robust-bounded-tail-ge-210-250-v1"


def test_shared_global_artifacts_are_once_per_slate_and_deterministic() -> None:
    value = _build()
    shared = value["shared_artifact_contract"]
    assert shared["law_id"] == "generate-once-score-once-select-many/v1"
    assert shared["roster_identity_law"] == (
        "sorted-nine-canonical-player-id-tuple"
    )
    assert shared["global_union_law"] == (
        "every-unique-p0-or-pb-roster-from-r0-through-r19"
    )
    assert shared["score_each_global_union_roster_once"] is True
    assert shared["score_matrix_world_count"] == 50_000
    assert shared[
        "population_k_fold_and_final_sets_are_masks_over_global_rows"
    ]
    assert shared["separately_recomputed_cell_matrices_forbidden"]

    all_uris: list[str] = []
    for ordinal, slate in enumerate(value["factorial_slates"]):
        prefix = f"{OUTPUT_PREFIX}slates/{ordinal:02d}-{slate['slate_id']}/"
        outputs = slate["shared_output_uris"]
        assert outputs == {
            "global_roster_table_uri": prefix
            + "factorial-global-rosters-v1.json",
            "occurrence_provenance_uri": prefix
            + "factorial-occurrence-provenance-v1.json",
            "ordinary_r_score_matrix_uri": prefix
            + "factorial-ordinary-r-score-matrix-v1.npz",
            "cell_lineage_masks_uri": prefix
            + "factorial-lineage-masks-v1.json",
            "slate_result_uri": prefix + "factorial-slate-analysis-v1.json",
            "slate_acceptance_uri": prefix
            + "factorial-slate-acceptance-v1.json",
        }
        all_uris.extend(outputs.values())
    assert len(all_uris) == 53 * 6
    assert len(set(all_uris)) == len(all_uris)


def test_one_controlled_grade_boundary_and_all_authorities_are_false() -> None:
    value = _build()
    boundary = value["controlled_grade_boundary"]
    assert boundary["maximum_controlled_realized_grade_count"] == 1
    assert boundary["complete_predeclared_final_book_catalog_required"]
    assert boundary["all_intended_4_14_80_books_frozen_before_outcome_access"]
    assert boundary["post_freeze_strategy_or_book_addition_forbidden"]
    assert boundary[
        "simulated_effect_screening_before_catalog_inclusion_forbidden"
    ]
    assert boundary["separate_grade_manifest_required"]
    assert boundary["this_execution_manifest_opens_outcome_access"] is False
    assert boundary["historical_results_license_production_change"] is False
    for field in manifest._FALSE_AUTHORITY_FIELDS:  # noqa: SLF001
        assert value[field] is False


def test_build_is_deterministic_and_validator_replays_all_inputs() -> None:
    sources = _source_members()
    first = _build(sources)
    second = _build(deepcopy(sources))
    assert batch.canonical_json_bytes(first) == batch.canonical_json_bytes(second)
    assert first["execution_manifest_sha256"] == batch.canonical_sha256({
        key: item
        for key, item in first.items()
        if key != "execution_manifest_sha256"
    })
    assert _validate(deepcopy(first), sources=sources) == first


def test_self_hash_unknown_field_and_coherent_rehash_fail_closed() -> None:
    sources = _source_members()
    value = _build(sources)

    damaged = deepcopy(value)
    damaged["entry_budgets"] = [4, 15, 80]
    with pytest.raises(
        manifest.CorpusExtremeTailFactorialManifestError,
        match="self-hash differs",
    ):
        _validate(damaged, sources=sources)

    coherent = _rehash(damaged)
    with pytest.raises(
        manifest.CorpusExtremeTailFactorialManifestError,
        match="canonical replay",
    ):
        _validate(coherent, sources=sources)

    unknown = deepcopy(value)
    unknown["unregistered_selector"] = "helpful"
    unknown = _rehash(unknown)
    with pytest.raises(
        manifest.CorpusExtremeTailFactorialManifestError,
        match="fields differ",
    ):
        _validate(unknown, sources=sources)


@pytest.mark.parametrize(
    "mutate,match",
    [
        (
            lambda rows: rows.pop(),
            "exactly 54",
        ),
        (
            lambda rows: rows[0].__setitem__("source_ordinal", 1),
            "exact 2023--2025 slate order",
        ),
        (
            lambda rows: rows[36].__setitem__("slate_id", "2025-w02"),
            "exact 2023--2025 slate order",
        ),
        (
            lambda rows: rows[36]["ordinary_r_blocks"].append({
                "block_id": "R3",
                "world_count": 10_000,
                "world_identity": _identity("extra", 999),
            }),
            "block count differs",
        ),
        (
            lambda rows: rows[1]["ordinary_r_blocks"][3].__setitem__(
                "block_id", "R4"
            ),
            "block identity or width differs",
        ),
        (
            lambda rows: rows[1]["ordinary_r_blocks"][0].__setitem__(
                "world_count", 9_999
            ),
            "block identity or width differs",
        ),
        (
            lambda rows: rows[1].__setitem__(
                "reconstruction_source_identity",
                rows[0]["reconstruction_source_identity"],
            ),
            "object identities repeat",
        ),
        (
            lambda rows: rows[2]["ordinary_r_blocks"][0].__setitem__(
                "world_identity", rows[1]["ordinary_r_blocks"][0]["world_identity"]
            ),
            "object identities repeat",
        ),
    ],
)
def test_source_catalog_drift_fails_before_manifest_build(
    mutate: Callable[[list[dict[str, object]]], object],
    match: str,
) -> None:
    sources = _source_members()
    mutate(sources)
    with pytest.raises(manifest.CorpusExtremeTailFactorialManifestError, match=match):
        _build(sources)


@pytest.mark.parametrize(
    "commit,image,prefix,match",
    [
        ("A" * 40, IMAGE, OUTPUT_PREFIX, "source commit"),
        (
            COMMIT,
            {"uri": IMAGE["uri"], "digest": "sha256:" + "c" * 64},
            OUTPUT_PREFIX,
            "digest-pinned",
        ),
        (COMMIT, IMAGE, "https://fixture/factorial/", "GCS prefix"),
        (COMMIT, IMAGE, "gs://fixture/factorial", "canonical"),
        (COMMIT, IMAGE, "gs://fixture/a/../b/", "canonical"),
    ],
)
def test_commit_image_and_output_prefix_must_be_immutable_and_canonical(
    commit: str,
    image: dict[str, object],
    prefix: str,
    match: str,
) -> None:
    with pytest.raises(manifest.CorpusExtremeTailFactorialManifestError, match=match):
        _build(
            source_commit_sha=commit,
            immutable_image=image,
            output_prefix=prefix,
        )


def test_false_authority_tamper_fails_even_after_coherent_rehash() -> None:
    sources = _source_members()
    value = _build(sources)
    value["realized_grade_open_authority"] = True
    value = _rehash(value)
    with pytest.raises(
        manifest.CorpusExtremeTailFactorialManifestError,
        match="realized_grade_open_authority must be false",
    ):
        _validate(value, sources=sources)


def test_nested_cell_population_retrieval_and_output_splices_fail_replay() -> None:
    sources = _source_members()
    original = _build(sources)
    mutations = []

    cell = deepcopy(original)
    cell["factorial_cell_registry"][7]["retrieval_id"] = (
        "complete-union-inclusive-r194-rank-v1"
    )
    cell["factorial_cell_registry_sha256"] = batch.canonical_sha256(
        cell["factorial_cell_registry"]
    )
    mutations.append(cell)

    population = deepcopy(original)
    population["population_registry"][1]["literal_generation_levers"][
        "N_BOOM"
    ] = "201"
    population["population_registry_sha256"] = batch.canonical_sha256(
        population["population_registry"]
    )
    mutations.append(population)

    retrieval_value = deepcopy(original)
    inner = retrieval_value["retrieval_contract"]
    support_row = inner["catalog"][5]
    support_strategy = support_row["strategy_contract"]
    support_strategy["gate_law"][
        "fold_minimum_opportunity_world_count"
    ] = 99
    support_strategy.pop("strategy_contract_sha256")
    support_strategy["strategy_contract_sha256"] = batch.canonical_sha256(
        support_strategy
    )
    support_row["strategy_contract_sha256"] = support_strategy[
        "strategy_contract_sha256"
    ]
    inner["catalog_sha256"] = batch.canonical_sha256(inner["catalog"])
    inner.pop("retrieval_contract_sha256")
    inner["retrieval_contract_sha256"] = batch.canonical_sha256(inner)
    mutations.append(retrieval_value)

    output = deepcopy(original)
    output["factorial_slates"][0]["shared_output_uris"][
        "slate_result_uri"
    ] = output["factorial_slates"][1]["shared_output_uris"]["slate_result_uri"]
    output["factorial_slates_sha256"] = batch.canonical_sha256(
        output["factorial_slates"]
    )
    mutations.append(output)

    for changed in mutations:
        changed = _rehash(changed)
        with pytest.raises(
            manifest.CorpusExtremeTailFactorialManifestError,
            match="canonical replay",
        ):
            _validate(changed, sources=sources)


def test_source_input_change_cannot_replay_an_existing_manifest() -> None:
    sources = _source_members()
    value = _build(sources)
    replacement = _identity("replacement-world", 99_999)
    sources[10]["ordinary_r_blocks"][2]["world_identity"] = replacement
    with pytest.raises(
        manifest.CorpusExtremeTailFactorialManifestError,
        match="canonical replay",
    ):
        _validate(value, sources=sources)


def test_seed_pair_dependency_drift_is_rejected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    policy = manifest.production.ClassicProductionPolicy()
    changed_extras = list(policy.multiseed_volume_extra_seed_pairs)
    changed_extras[-1] = (changed_extras[-1][0] + 1, changed_extras[-1][1])
    replacement = SimpleNamespace(
        multiseed_seed_pairs=policy.multiseed_seed_pairs,
        multiseed_volume_extra_seed_pairs=tuple(changed_extras),
        candidate_multiple=policy.candidate_multiple,
        n_boom=policy.n_boom,
        n_role=policy.n_role,
        n_ce=policy.n_ce,
        engine_environment=policy.engine_environment,
    )
    monkeypatch.setattr(
        manifest.production, "ClassicProductionPolicy", lambda: replacement
    )
    with pytest.raises(
        manifest.CorpusExtremeTailFactorialManifestError,
        match="dependency constants drifted",
    ):
        _build()


@pytest.mark.parametrize(
    "dependency,field,replacement",
    [
        (manifest.rw, "WORLDS_PER_BLOCK", 9_999),
        (manifest.suite, "ENTRY_BUDGETS", (5, 14, 80)),
        (manifest.support, "POLICY_LAW_ID", "changed-support-switch/v1"),
        (manifest.support, "FOLD_MINIMUM_OPPORTUNITY_WORLDS", 99),
    ],
)
def test_world_budget_and_support_dependency_drift_is_rejected(
    monkeypatch: pytest.MonkeyPatch,
    dependency: object,
    field: str,
    replacement: object,
) -> None:
    monkeypatch.setattr(dependency, field, replacement)
    with pytest.raises(
        manifest.CorpusExtremeTailFactorialManifestError,
        match="dependency constants drifted",
    ):
        _build()


@pytest.mark.parametrize("row_index", range(4))
def test_coherent_raw_strategy_same_id_drift_is_rejected(
    monkeypatch: pytest.MonkeyPatch,
    row_index: int,
) -> None:
    original = manifest.suite.frozen_extreme_tail_strategies_v1

    def changed_registry() -> list[dict[str, object]]:
        rows = deepcopy(original())
        rows[row_index]["role"] = "same-id-coherent-drift"
        rows[row_index].pop("strategy_sha256")
        rows[row_index]["strategy_sha256"] = batch.canonical_sha256(
            rows[row_index]
        )
        return rows

    monkeypatch.setattr(
        manifest.suite, "frozen_extreme_tail_strategies_v1", changed_registry
    )
    with pytest.raises(
        manifest.CorpusExtremeTailFactorialManifestError,
        match="literal frozen hash",
    ):
        _build()


def test_coherent_raw_implementation_same_id_drift_is_rejected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original = manifest.suite.frozen_selector_implementation_contract_v1

    def changed_contract() -> dict[str, object]:
        contract = deepcopy(original())
        contract["candidate_chunk_rows"] = 257
        contract.pop("selector_implementation_sha256")
        contract["selector_implementation_sha256"] = batch.canonical_sha256(
            contract
        )
        return contract

    monkeypatch.setattr(
        manifest.suite,
        "frozen_selector_implementation_contract_v1",
        changed_contract,
    )
    with pytest.raises(
        manifest.CorpusExtremeTailFactorialManifestError,
        match="literal frozen hash",
    ):
        _build()


@pytest.mark.parametrize("row_index", (1, 2))
def test_coherent_preweek_strategy_same_id_drift_is_rejected(
    monkeypatch: pytest.MonkeyPatch,
    row_index: int,
) -> None:
    original = manifest.preweek.frozen_preweek_selector_registry_v1

    def changed_registry() -> list[dict[str, object]]:
        rows = deepcopy(original())
        rows[row_index]["role"] = "same-id-coherent-drift"
        rows[row_index].pop("strategy_sha256")
        rows[row_index]["strategy_sha256"] = batch.canonical_sha256(
            rows[row_index]
        )
        return rows

    monkeypatch.setattr(
        manifest.preweek,
        "frozen_preweek_selector_registry_v1",
        changed_registry,
    )
    with pytest.raises(
        manifest.CorpusExtremeTailFactorialManifestError,
        match="literal frozen hash",
    ):
        _build()


def test_coherent_canonical_coverage_194_same_id_drift_is_rejected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original = manifest.retrieval.frozen_retrieval_strategies

    def changed_registry(entry_budget: int) -> list[dict[str, object]]:
        rows = deepcopy(original(entry_budget))
        rows[0]["description"] = "same-id-coherent-drift"
        rows[0].pop("strategy_sha256")
        rows[0]["strategy_sha256"] = batch.canonical_sha256(rows[0])
        return rows

    monkeypatch.setattr(
        manifest.retrieval,
        "frozen_retrieval_strategies",
        changed_registry,
    )
    with pytest.raises(
        manifest.CorpusExtremeTailFactorialManifestError,
        match="literal frozen hash",
    ):
        _build()


def test_coherent_preweek_implementation_same_id_drift_is_rejected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original = manifest.preweek.frozen_preweek_selector_implementation_v1

    def changed_contract() -> dict[str, object]:
        contract = deepcopy(original())
        contract["candidate_chunk_rows"] = 257
        contract.pop("implementation_sha256")
        contract["implementation_sha256"] = batch.canonical_sha256(contract)
        return contract

    monkeypatch.setattr(
        manifest.preweek,
        "frozen_preweek_selector_implementation_v1",
        changed_contract,
    )
    with pytest.raises(
        manifest.CorpusExtremeTailFactorialManifestError,
        match="literal frozen hash",
    ):
        _build()


def test_coherent_scenario_combined_contract_same_id_drift_is_rejected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original = manifest.scenario.frozen_scenario_ticket_contract_v1

    def changed_contract() -> dict[str, object]:
        contract = deepcopy(original())
        contract["allocation_law"]["breadth_visits"] = (
            "same-id-coherent-drift"
        )
        contract.pop("contract_sha256")
        contract["contract_sha256"] = batch.canonical_sha256(contract)
        return contract

    monkeypatch.setattr(
        manifest.scenario,
        "frozen_scenario_ticket_contract_v1",
        changed_contract,
    )
    with pytest.raises(
        manifest.CorpusExtremeTailFactorialManifestError,
        match="literal frozen hash",
    ):
        _build()


@pytest.mark.parametrize("contract_kind", ("strategy", "implementation"))
def test_support_switch_same_id_contract_drift_is_rejected(
    monkeypatch: pytest.MonkeyPatch,
    contract_kind: str,
) -> None:
    if contract_kind == "strategy":
        original = manifest.support._switch_law  # noqa: SLF001

        def changed_switch(
            strategy_hash_by_id: dict[str, str],
        ) -> dict[str, object]:
            law = deepcopy(original(strategy_hash_by_id))
            law["selection_law"] = "same-id-coherent-drift"
            return law

        monkeypatch.setattr(manifest.support, "_switch_law", changed_switch)
        expected = "public contract differs"
    else:
        monkeypatch.setattr(
            manifest.support,
            "POLICY_SCHEMA",
            "same-id-coherent-implementation-drift/v1",
        )
        expected = "implementation contract hash differs"

    with pytest.raises(
        manifest.CorpusExtremeTailFactorialManifestError,
        match=expected,
    ):
        _build()


@pytest.mark.parametrize("row_index", (1, 6))
def test_coherent_v2_comparator_strategy_same_id_drift_is_rejected(
    monkeypatch: pytest.MonkeyPatch,
    row_index: int,
) -> None:
    original_registry = manifest.retrieval.frozen_retrieval_strategies_v2
    implementation_module = manifest.retrieval_v2_implementation
    stable_implementation = (
        implementation_module.frozen_retrieval_v2_implementation_contract_v1()
    )

    def changed_registry(entry_budget: int) -> list[dict[str, object]]:
        rows = deepcopy(original_registry(entry_budget))
        rows[row_index]["description"] = "same-id-coherent-drift"
        rows[row_index].pop("strategy_sha256")
        rows[row_index]["strategy_sha256"] = batch.canonical_sha256(
            rows[row_index]
        )
        return rows

    monkeypatch.setattr(
        manifest.retrieval,
        "frozen_retrieval_strategies_v2",
        changed_registry,
    )
    monkeypatch.setattr(
        implementation_module,
        "frozen_retrieval_v2_implementation_contract_v1",
        lambda: stable_implementation,
    )
    monkeypatch.setattr(
        implementation_module,
        "validate_retrieval_v2_implementation_contract_v1",
        lambda value: value,
    )
    with pytest.raises(
        manifest.CorpusExtremeTailFactorialManifestError,
        match="literal frozen hash",
    ):
        _build()


def test_coherent_v2_comparator_implementation_same_id_drift_is_rejected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    implementation_module = manifest.retrieval_v2_implementation
    original = (
        implementation_module.frozen_retrieval_v2_implementation_contract_v1
    )

    def changed_contract() -> dict[str, object]:
        contract = deepcopy(original())
        identity = contract["contract_identity"]
        identity["execution_laws"]["entry_budget"] = 79
        contract["implementation_contract_sha256"] = batch.canonical_sha256(
            identity
        )
        return contract

    monkeypatch.setattr(
        implementation_module,
        "frozen_retrieval_v2_implementation_contract_v1",
        changed_contract,
    )
    monkeypatch.setattr(
        implementation_module,
        "validate_retrieval_v2_implementation_contract_v1",
        lambda value: value,
    )
    with pytest.raises(
        manifest.CorpusExtremeTailFactorialManifestError,
        match="literal frozen hash",
    ):
        _build()


def test_v2_comparator_diagnostic_paths_do_not_affect_manifest_identity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    baseline = _build()
    implementation_module = manifest.retrieval_v2_implementation
    original = (
        implementation_module.frozen_retrieval_v2_implementation_contract_v1
    )

    def relocated_contract() -> dict[str, object]:
        contract = deepcopy(original())
        contract["diagnostics"]["absolute_source_path"] = (
            "/different/image/corpus_retrieval_engine.py"
        )
        contract["diagnostics"]["absolute_python_executable_path"] = (
            "/different/image/python"
        )
        contract["diagnostics"]["absolute_numpy_core_binary_path"] = (
            "/different/image/numpy-core.so"
        )
        return contract

    monkeypatch.setattr(
        implementation_module,
        "frozen_retrieval_v2_implementation_contract_v1",
        relocated_contract,
    )
    assert _build() == baseline


@pytest.mark.parametrize("row_index", (0, 1, 2))
def test_coherent_preweek_addition_strategy_same_id_drift_is_rejected(
    monkeypatch: pytest.MonkeyPatch,
    row_index: int,
) -> None:
    original = manifest.additions.frozen_preweek_additions_registry_v1

    def changed_registry() -> list[dict[str, object]]:
        rows = deepcopy(original())
        rows[row_index]["role"] = "same-id-coherent-drift"
        rows[row_index].pop("strategy_sha256")
        rows[row_index]["strategy_sha256"] = batch.canonical_sha256(
            rows[row_index]
        )
        return rows

    monkeypatch.setattr(
        manifest.additions,
        "frozen_preweek_additions_registry_v1",
        changed_registry,
    )
    with pytest.raises(
        manifest.CorpusExtremeTailFactorialManifestError,
        match="literal frozen hash",
    ):
        _build()


def test_coherent_preweek_addition_implementation_same_id_drift_is_rejected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original = manifest.additions.frozen_preweek_additions_implementation_v1

    def changed_contract() -> dict[str, object]:
        contract = deepcopy(original())
        contract["candidate_chunk_rows"] = 65
        contract.pop("implementation_sha256")
        contract["implementation_sha256"] = batch.canonical_sha256(contract)
        return contract

    monkeypatch.setattr(
        manifest.additions,
        "frozen_preweek_additions_implementation_v1",
        changed_contract,
    )
    with pytest.raises(
        manifest.CorpusExtremeTailFactorialManifestError,
        match="literal frozen hash",
    ):
        _build()
