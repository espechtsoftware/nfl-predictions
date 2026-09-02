from __future__ import annotations

from copy import deepcopy
from hashlib import sha256

import pytest

from nfl_dfs.inference.generation_exposure import canonical_sha256
from nfl_dfs.inference import week1_adopted_pair as adopted


def _roster_id(label: str) -> str:
    return f"lineup-v1-{sha256(label.encode('ascii')).hexdigest()}"


def _identity(label: str) -> dict[str, object]:
    return {
        "id": label,
        "sha256": sha256(label.encode("ascii")).hexdigest(),
    }


def _artifact(label: str, generation: int) -> dict[str, object]:
    return {
        "uri": f"{adopted.GOVERNED_ARTIFACT_PREFIX}{label}.json",
        "generation": str(generation),
        "sha256": sha256(label.encode("ascii")).hexdigest(),
        "bytes": 8_000 + generation,
    }


def _arm(
    *, arm_id: str, purpose: str, lev: int, boom: int, roster_labels: range
) -> dict[str, object]:
    return {
        "arm_id": arm_id,
        "purpose": purpose,
        "config": {
            "lev": lev,
            "boom": boom,
            "selector": "dual_emax",
            "entries": 80,
            "k": 1,
        },
        "slate_identity": _identity("2026-w01-dk-151307"),
        "input_identity": _identity("live-input-root/v1"),
        "player_bridge_identity": _identity("player-bridge/v1"),
        "generation_bank_identity": _identity(
            "incumbent-generation-seed-2026"
        ),
        "selection_bank_identity": _identity(
            "incumbent-selection-seed-2076"
        ),
        "audit_bank_identity": _identity("incumbent-audit-seed-2126"),
        "hsim_bank_identity": _identity(
            "corrected-hsim-selection-seed-2326"
        ),
        "construction_identity": _identity("house_qb2_bb1_floor49_v1"),
        "generator_source_identity": _identity(
            f"nfl2-live-week@{'a' * 40}"
        ),
        "selector_source_identity": _identity(
            f"nfl2-select-expected-max@{'a' * 40}"
        ),
        "hsim_source_identity": _identity(
            f"nfl2-corrected-hsim@{'a' * 40}"
        ),
        "book_artifact": _artifact(
            f"{arm_id}/book", 7 if purpose == "paid" else 8
        ),
        "candidate_artifact": _artifact(
            f"{arm_id}/candidates", 9 if purpose == "paid" else 10
        ),
        "exposure_ledger_artifact": _artifact(
            f"{arm_id}/exposure-ledger", 11 if purpose == "paid" else 12
        ),
        "run_receipt_artifact": _artifact(
            f"{arm_id}/run-receipt", 13 if purpose == "paid" else 14
        ),
        "candidate_ids": [
            _roster_id(f"roster-{index}")
            for index in range(800 if purpose == "paid" else 400)
        ],
        "roster_ids": [_roster_id(f"roster-{index}") for index in roster_labels],
    }


def _arms() -> tuple[dict[str, object], dict[str, object]]:
    paid = _arm(
        arm_id="D800_DEMAX",
        purpose="paid",
        lev=160,
        boom=640,
        roster_labels=range(80),
    )
    # Ten memberships overlap; neither exact-K80 book contains the other.
    shadow = _arm(
        arm_id="D400_DEMAX",
        purpose="shadow",
        lev=80,
        boom=320,
        roster_labels=range(70, 150),
    )
    return paid, shadow


def _pair() -> dict[str, object]:
    paid, shadow = _arms()
    return adopted.build_week1_adopted_pair_v1(
        authority=_authority(), recipe=_recipe(), paid=paid, shadow=shadow
    )


def _authority() -> dict[str, object]:
    return {
        "season": 2026,
        "week": 1,
        "draft_group_id": "151307",
        "slate_type": "sunday-main",
        "lock_utc": adopted.WEEK1_LOCK_UTC,
        "frozen_at": "2026-09-02T03:00:00+00:00",
        "outcome_blind": True,
        "outcome_fields_read": [],
    }


def _recipe() -> dict[str, object]:
    return {
        "generation_seed": 2026,
        "selection_seed": 2076,
        "audit_seed": 2126,
        "corrected_hsim_seed": 2326,
        "incumbent_worlds": 10_000,
        "corrected_hsim_worlds": 10_000,
        "decision_worlds": 20_000,
        "law_weighting": "equal-column-mass",
        "selector_recipe": "greedy-expected-weekly-max-v1",
        "tie_break": "first-in-candidate-order-v1",
        "construction_contract": "house_qb2_bb1_floor49_v1",
    }


def _rehash(pair: dict[str, object]) -> None:
    body = dict(pair)
    body.pop("contract_sha256", None)
    pair["contract_sha256"] = canonical_sha256(body)


def test_builds_and_validates_exact_d800_paid_d400_shadow_pair() -> None:
    paid, shadow = _arms()
    pair = adopted.build_week1_adopted_pair_v1(
        authority=_authority(), recipe=_recipe(), paid=paid, shadow=shadow
    )

    assert pair["schema_version"] == adopted.SCHEMA_VERSION
    assert pair["pair_id"] == adopted.PAIR_ID
    assert pair["complete"] is True
    assert pair["paid"]["config"] == {
        "lev": 160,
        "boom": 640,
        "selector": "dual_emax",
        "entries": 80,
        "k": 1,
    }
    assert pair["shadow"]["config"] == {
        "lev": 80,
        "boom": 320,
        "selector": "dual_emax",
        "entries": 80,
        "k": 1,
    }
    assert pair["roster_overlap_count"] == 10
    assert set(pair["paid"]["roster_ids"]) - set(
        pair["shadow"]["roster_ids"]
    )
    assert set(pair["shadow"]["roster_ids"]) - set(
        pair["paid"]["roster_ids"]
    )
    assert "nested" not in pair
    assert adopted.validate_week1_adopted_pair_v1(pair) == pair

    paid["config"]["lev"] = 999
    assert pair["paid"]["config"]["lev"] == 160


@pytest.mark.parametrize(
    ("role", "field", "bad_value"),
    (
        ("paid", "lev", 159),
        ("paid", "boom", 639),
        ("paid", "selector", "cov194"),
        ("paid", "entries", 79),
        ("paid", "k", 3),
        ("shadow", "lev", 81),
        ("shadow", "boom", 321),
        ("shadow", "selector", "winner_emax"),
        ("shadow", "entries", 100),
        ("shadow", "k", True),
    ),
)
def test_rejects_any_fixed_config_drift(
    role: str, field: str, bad_value: object
) -> None:
    pair = _pair()
    pair[role]["config"][field] = bad_value
    _rehash(pair)

    with pytest.raises(
        adopted.Week1AdoptedPairError, match="config differs"
    ):
        adopted.validate_week1_adopted_pair_v1(pair)


@pytest.mark.parametrize(
    "identity_field",
    (
        "slate_identity",
        "input_identity",
        "player_bridge_identity",
        "generation_bank_identity",
        "selection_bank_identity",
        "audit_bank_identity",
        "hsim_bank_identity",
        "construction_identity",
        "generator_source_identity",
        "selector_source_identity",
        "hsim_source_identity",
    ),
)
def test_rejects_paid_shadow_identity_drift(identity_field: str) -> None:
    pair = _pair()
    pair["shadow"][identity_field]["sha256"] = "f" * 64
    _rehash(pair)

    with pytest.raises(
        adopted.Week1AdoptedPairError,
        match=f"paid/shadow {identity_field} differs",
    ):
        adopted.validate_week1_adopted_pair_v1(pair)


@pytest.mark.parametrize(
    ("role", "field", "bad_id"),
    (
        ("paid", "slate_identity", "2026-w01-dk-999999"),
        ("paid", "input_identity", "untyped-input"),
        ("shadow", "construction_identity", "dk-only"),
        ("shadow", "hsim_bank_identity", "corrected-hsim-seed-2076"),
        (
            "paid",
            "generator_source_identity",
            "nfl2-live-week@not-a-commit",
        ),
        (
            "shadow",
            "hsim_source_identity",
            f"nfl2-corrected-hsim@{'b' * 40}",
        ),
    ),
)
def test_rejects_matching_or_mismatched_wrong_semantic_identity(
    role: str, field: str, bad_id: str
) -> None:
    pair = _pair()
    pair[role][field] = _identity(bad_id)
    if role == "paid" and field not in {
        "generator_source_identity", "selector_source_identity",
        "hsim_source_identity",
    }:
        pair["shadow"][field] = _identity(bad_id)
    _rehash(pair)
    with pytest.raises(adopted.Week1AdoptedPairError):
        adopted.validate_week1_adopted_pair_v1(pair)


@pytest.mark.parametrize("role", ("paid", "shadow"))
@pytest.mark.parametrize("mutation", ("short", "duplicate"))
def test_rejects_non_exact_or_duplicate_roster_books(
    role: str, mutation: str
) -> None:
    pair = _pair()
    roster_ids = pair[role]["roster_ids"]
    if mutation == "short":
        roster_ids.pop()
    else:
        roster_ids[-1] = roster_ids[0]
    _rehash(pair)

    with pytest.raises(adopted.Week1AdoptedPairError):
        adopted.validate_week1_adopted_pair_v1(pair)


def test_overlap_is_checked_but_nesting_is_not_required() -> None:
    pair = _pair()
    assert pair["roster_overlap_count"] == 10

    pair["roster_overlap_count"] = 80
    _rehash(pair)
    with pytest.raises(
        adopted.Week1AdoptedPairError, match="overlap diagnostic differs"
    ):
        adopted.validate_week1_adopted_pair_v1(pair)


def test_selected_books_need_not_nest_but_candidate_population_must() -> None:
    pair = _pair()
    assert not set(pair["shadow"]["roster_ids"]) <= set(
        pair["paid"]["roster_ids"]
    )
    assert set(pair["shadow"]["candidate_ids"]) <= set(
        pair["paid"]["candidate_ids"]
    )

    pair["shadow"]["candidate_ids"][-1] = _roster_id("not-in-d800")
    _rehash(pair)
    with pytest.raises(
        adopted.Week1AdoptedPairError,
        match="D400 candidate population is not contained in D800",
    ):
        adopted.validate_week1_adopted_pair_v1(pair)


def test_rejects_selected_lineup_outside_its_candidate_population() -> None:
    pair = _pair()
    pair["paid"]["roster_ids"][-1] = _roster_id("not-a-paid-candidate")
    _rehash(pair)
    with pytest.raises(
        adopted.Week1AdoptedPairError,
        match="selected book is not contained",
    ):
        adopted.validate_week1_adopted_pair_v1(pair)


@pytest.mark.parametrize(
    "bad_uri",
    (
        "results/live/2026-w01/D400_DEMAX/book.json",
        f"{adopted.GOVERNED_ARTIFACT_PREFIX}./D400_DEMAX/book.json",
        f"{adopted.GOVERNED_ARTIFACT_PREFIX}x/../D400_DEMAX/book.json",
        f"{adopted.GOVERNED_ARTIFACT_PREFIX}/D400_DEMAX/book.json",
        "gs://bucket/only/a/directory/",
        "gs://outcome-bucket/week1/prelock/2026-w01/book.json",
        f"{adopted.GOVERNED_ARTIFACT_PREFIX}outcomes/D400/book.json",
        f"{adopted.GOVERNED_ARTIFACT_PREFIX}D400/book.json?generation=latest",
        f"{adopted.GOVERNED_ARTIFACT_PREFIX}D400/book.json#fragment",
    ),
)
def test_rejects_noncanonical_or_postlock_artifact_uris(bad_uri: str) -> None:
    pair = _pair()
    pair["shadow"]["book_artifact"]["uri"] = bad_uri
    _rehash(pair)
    with pytest.raises(adopted.Week1AdoptedPairError):
        adopted.validate_week1_adopted_pair_v1(pair)


def test_rejects_paid_shadow_artifact_uri_alias() -> None:
    pair = _pair()
    pair["shadow"]["book_artifact"]["uri"] = pair["paid"][
        "book_artifact"
    ]["uri"]
    _rehash(pair)

    with pytest.raises(
        adopted.Week1AdoptedPairError, match="artifact URIs alias"
    ):
        adopted.validate_week1_adopted_pair_v1(pair)


@pytest.mark.parametrize("role", ("paid", "shadow"))
def test_rejects_unpinned_artifact_digest(role: str) -> None:
    pair = _pair()
    pair[role]["book_artifact"]["sha256"] = "ABC"
    _rehash(pair)
    with pytest.raises(
        adopted.Week1AdoptedPairError, match="lowercase SHA-256"
    ):
        adopted.validate_week1_adopted_pair_v1(pair)


@pytest.mark.parametrize(
    ("field", "bad_value"),
    (
        ("generation", "0"),
        ("generation", "latest"),
        ("generation", "007"),
        ("generation", 7),
        ("bytes", 0),
        ("bytes", True),
    ),
)
@pytest.mark.parametrize("role", ("paid", "shadow"))
def test_rejects_unpinned_artifact_identity(
    role: str, field: str, bad_value: object
) -> None:
    pair = _pair()
    pair[role]["book_artifact"][field] = bad_value
    _rehash(pair)
    with pytest.raises(adopted.Week1AdoptedPairError):
        adopted.validate_week1_adopted_pair_v1(pair)


@pytest.mark.parametrize(
    ("field", "bad_value"),
    (
        ("season", 2025),
        ("week", 2),
        ("draft_group_id", "999999"),
        ("slate_type", "showdown"),
        ("lock_utc", "2026-09-13T17:01:00+00:00"),
        ("frozen_at", "2026-09-13T17:00:00+00:00"),
        ("frozen_at", "2026-09-02T03:00:00-05:00"),
        ("outcome_blind", False),
        ("outcome_fields_read", ["actual_points"]),
    ),
)
def test_rejects_authority_or_prelock_boundary_drift(
    field: str, bad_value: object
) -> None:
    pair = _pair()
    pair["authority"][field] = bad_value
    _rehash(pair)
    with pytest.raises(adopted.Week1AdoptedPairError):
        adopted.validate_week1_adopted_pair_v1(pair)


@pytest.mark.parametrize(
    ("field", "bad_value"),
    (
        ("selection_seed", 2077),
        ("corrected_hsim_seed", 2076),
        ("incumbent_worlds", 2_000),
        ("corrected_hsim_worlds", 20_000),
        ("decision_worlds", 10_000),
        ("law_weighting", "row-count-weighted"),
        ("selector_recipe", "coverage-194"),
        ("tie_break", "unstable-argmax"),
        ("construction_contract", "dk-only"),
    ),
)
def test_rejects_adopted_live_recipe_drift(
    field: str, bad_value: object
) -> None:
    pair = _pair()
    pair["recipe"][field] = bad_value
    _rehash(pair)
    with pytest.raises(
        adopted.Week1AdoptedPairError, match="recipe differs"
    ):
        adopted.validate_week1_adopted_pair_v1(pair)


@pytest.mark.parametrize(
    ("location", "field"),
    (
        ((), "complete"),
        (("authority",), "outcome_blind"),
        (("recipe",), "law_weighting"),
        (("paid",), "purpose"),
        (("shadow", "config"), "selector"),
        (("paid", "input_identity"), "sha256"),
        (("shadow", "book_artifact"), "uri"),
    ),
)
def test_rejects_missing_fields_at_every_contract_level(
    location: tuple[str, ...], field: str
) -> None:
    pair = _pair()
    target = pair
    for part in location:
        target = target[part]
    target.pop(field)
    _rehash(pair)
    with pytest.raises(
        adopted.Week1AdoptedPairError, match="fields differ"
    ):
        adopted.validate_week1_adopted_pair_v1(pair)


@pytest.mark.parametrize(
    "location",
    (
        (),
        ("authority",),
        ("recipe",),
        ("paid",),
        ("shadow", "config"),
        ("paid", "generation_bank_identity"),
        ("shadow", "book_artifact"),
    ),
)
def test_rejects_unknown_fields_at_every_contract_level(
    location: tuple[str, ...]
) -> None:
    pair = _pair()
    target = pair
    for part in location:
        target = target[part]
    target["unexpected"] = "not-authorized"
    _rehash(pair)
    with pytest.raises(
        adopted.Week1AdoptedPairError, match="fields differ"
    ):
        adopted.validate_week1_adopted_pair_v1(pair)


def test_rejects_role_swap_and_contract_hash_tampering() -> None:
    pair = _pair()
    pair["paid"]["purpose"] = "shadow"
    _rehash(pair)
    with pytest.raises(
        adopted.Week1AdoptedPairError, match="identity/purpose differs"
    ):
        adopted.validate_week1_adopted_pair_v1(pair)

    pair = _pair()
    pair["contract_sha256"] = "f" * 64
    with pytest.raises(
        adopted.Week1AdoptedPairError, match="contract SHA-256 differs"
    ):
        adopted.validate_week1_adopted_pair_v1(pair)


def test_accepts_distinct_generation_pinned_gcs_artifacts() -> None:
    paid, shadow = _arms()
    paid["book_artifact"]["uri"] = (
        f"{adopted.GOVERNED_ARTIFACT_PREFIX}D800_DEMAX/book.json"
    )
    shadow["book_artifact"]["uri"] = (
        f"{adopted.GOVERNED_ARTIFACT_PREFIX}D400_DEMAX/book.json"
    )

    pair = adopted.build_week1_adopted_pair_v1(
        authority=_authority(), recipe=_recipe(), paid=paid, shadow=shadow
    )
    assert adopted.validate_week1_adopted_pair_v1(pair) == pair
