from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

import pytest

from nfl_dfs.research.winner_registry_v2 import (
    ADJUDICATION_SCHEMA,
    WinnerRegistryV2Error,
    WinnerSourceSpec,
    accepted_observations,
    adjudication_receipt_template,
    build_candidate_ledger,
    seal_adjudication_receipt,
    seal_target_contest_policy,
    target_contest_policy_template,
    validate_adjudication_receipt,
    validate_candidate_ledger,
    validate_target_contest_policy,
    verify_source_files,
)


REPO_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def ledger():
    return build_candidate_ledger(REPO_ROOT)


def _observations(ledger, *, season, week, source_suffix=None):
    artifacts = {
        row["source_artifact_id"]: row for row in ledger["source_artifacts"]
    }
    rows = [
        row
        for row in ledger["observations"]
        if row["season"] == season and row["week"] == week
    ]
    if source_suffix is not None:
        rows = [
            row
            for row in rows
            if artifacts[row["source_artifact_id"]]["repo_relative_path"].endswith(
                source_suffix
            )
        ]
    return rows


def _frozen_policy():
    policy = target_contest_policy_template()
    policy["target_definition"].update(
        {
            "contest_family": "operator-chosen flagship-millionaire-family",
            "selection_rule": (
                "match exact contest ID to the frozen family; never choose by score"
            ),
            "multiple_contest_rule": (
                "retain all candidates and accept only the exact frozen-family ID"
            ),
        }
    )
    policy["effective_scope"] = {"first_season": 2023, "last_season": 2025}
    policy["policy_owner"] = "test adjudicator"
    policy["approved_at_utc"] = "2026-09-01T00:00:00Z"
    return seal_target_contest_policy(policy)


def _accepted_receipt(
    ledger,
    observation,
    policy,
    *,
    official_evidence,
    contest_id="123456",
    official_score="224.4",
    slate_date="2023-09-17",
):
    artifact = next(
        row
        for row in ledger["source_artifacts"]
        if row["source_artifact_id"] == observation["source_artifact_id"]
    )
    source_evidence = [
        {
            "evidence_id": "candidate-source-1",
            "source_uri": artifact["repo_relative_path"],
            "source_artifact_id": artifact["source_artifact_id"],
            "authority_class": artifact["source_role"],
            "content_sha256": artifact["sha256"],
            "bytes": artifact["bytes"],
            "captured_at_utc": "2026-09-01T00:00:00Z",
            "physical_rows": dict(observation["physical_rows"]),
            "supports": ["candidate_observation"],
        }
    ]
    if official_evidence:
        source_evidence.append(
            {
                "evidence_id": "official-export-1",
                "source_uri": f"gs://immutable/contest-{contest_id}.csv",
                "authority_class": "draftkings_official_contest_export",
                "content_sha256": "a" * 64,
                "bytes": 1234,
                "captured_at_utc": "2023-09-20T00:00:00Z",
                "physical_rows": {"start": 2, "end": 2},
                "supports": [
                    "official_target_winning_score",
                    "target_contest_identity",
                ],
                "extracted_fields": {
                    "draftkings_contest_id": contest_id,
                    "official_target_winning_score": official_score,
                },
            }
        )
    receipt = {
        "schema_version": ADJUDICATION_SCHEMA,
        "template_status": "operational_receipt",
        "receipt_id": None,
        "receipt_sha256": None,
        "observation_id": observation["observation_id"],
        "decision": "accepted",
        "target_policy_id": policy["policy_id"],
        "target_policy_sha256": policy["policy_sha256"],
        "target_contest_identity": {
            "season": observation["season"],
            "week": observation["week"],
            "draftkings_contest_id": contest_id,
            "contest_name": "NFL Millionaire test fixture",
            "contest_family": "operator-chosen flagship-millionaire-family",
            "slate_date": slate_date,
            "lock_time_utc": f"{slate_date}T17:00:00Z",
            "roster_format": "Classic",
            "entry_fee_usd": "20",
            "top_prize_usd": "1000000",
        },
        "scores": {
            "official_target_winning_score": official_score,
            "captured_roster_points_sum": observation["scores"][
                "captured_roster_points_sum"
            ],
            "article_or_summary_reported_score": observation["scores"][
                "article_or_summary_reported_score"
            ],
        },
        "source_evidence": source_evidence,
        "adjudicator": {"name": "Registry Test", "role": "data steward"},
        "adjudicated_at_utc": "2026-09-01T00:00:00Z",
        "reason": "Exact contest-ID and score fixture match.",
    }
    return seal_adjudication_receipt(receipt)


def test_real_ledger_is_lossless_unadjudicated_and_source_bound(ledger):
    validate_candidate_ledger(ledger)
    verify_source_files(ledger, REPO_ROOT)
    assert ledger["source_artifact_count"] == 4
    assert ledger["observation_count"] == 117
    assert ledger["distinct_season_week_label_count"] == 70
    assert ledger["official_target_score_count"] == 0
    assert sum(
        row["physical_layout"]["data_row_count"]
        for row in ledger["source_artifacts"]
    ) == 917
    assert all(
        row["scores"]["official_target_winning_score"] is None
        for row in ledger["observations"]
    )
    # V2 preserves all observations; it has no forced 17-week season shape.
    canonical_2024 = _observations(
        ledger,
        season=2024,
        week=1,
        source_suffix="milly-winners-2019-2023-2024.csv",
    )[0]["source_artifact_id"]
    assert sum(
        row["season"] == 2024 and row["source_artifact_id"] == canonical_2024
        for row in ledger["observations"]
    ) == 18


def test_2023_week2_conflicting_contests_are_not_conflated(ledger):
    rows = _observations(ledger, season=2023, week=2)
    assert len(rows) == 2
    scores = {
        (
            row["scores"]["captured_roster_points_sum"],
            row["scores"]["article_or_summary_reported_score"],
        )
        for row in rows
    }
    assert scores == {("193.94", None), ("224.4", "224.4")}
    assert len({row["observation_id"] for row in rows}) == 2
    assert len({row["roster_content_sha256_excluding_season_week"] for row in rows}) == 2


def test_2024_week14_preserves_reported_scalar_and_roster_sum(ledger):
    row = _observations(
        ledger,
        season=2024,
        week=14,
        source_suffix="milly_rosters_2023_2024.csv",
    )[0]
    assert row["physical_rows"] == {"start": 254, "end": 262, "count": 9}
    assert row["scores"] == {
        "official_target_winning_score": None,
        "captured_roster_points_sum": "281.68",
        "article_or_summary_reported_score": "281.6",
    }
    assert {raw["winning_score"] for raw in row["raw_records"]} == {"281.6"}


def test_2024_week9_duplicate_roster_is_preserved_not_deduplicated(ledger):
    week7 = _observations(
        ledger,
        season=2024,
        week=7,
        source_suffix="milly-winners-2019-2023-2024.csv",
    )[0]
    week9 = _observations(
        ledger,
        season=2024,
        week=9,
        source_suffix="milly-winners-2019-2023-2024.csv",
    )[0]
    assert week7["observation_id"] != week9["observation_id"]
    assert (
        week7["roster_content_sha256_excluding_season_week"]
        == week9["roster_content_sha256_excluding_season_week"]
    )
    assert week7["raw_records"][0]["week"] == "7"
    assert week9["raw_records"][0]["week"] == "9"


def test_raw_strings_and_physical_ranges_survive_exactly(ledger):
    row = _observations(
        ledger,
        season=2023,
        week=2,
        source_suffix="milly_rosters_2023_2024.csv",
    )[0]
    assert row["physical_rows"] == {"start": 11, "end": 19, "count": 9}
    assert row["raw_records"][0] == {
        "season": "2023",
        "week": "2",
        "player": "Daniel Jones",
        "position": "QB",
        "salary": "6000",
        "own_pct": "3.28",
        "pts": "34.74",
        "winning_score": "224.4",
    }


def test_build_and_hashes_are_deterministic_across_json_round_trip(ledger):
    again = build_candidate_ledger(REPO_ROOT)
    assert again == ledger
    round_tripped = json.loads(json.dumps(ledger, sort_keys=True))
    validate_candidate_ledger(round_tripped)
    assert round_tripped["ledger_sha256"] == ledger["ledger_sha256"]

    mutated = deepcopy(round_tripped)
    mutated["observations"][0]["raw_records"][0]["player"] = "mutated"
    with pytest.raises(WinnerRegistryV2Error, match="content hash mismatch"):
        validate_candidate_ledger(mutated)


def test_same_week_multiple_rosters_in_one_source_split_instead_of_collapsing(
    tmp_path,
):
    reports = tmp_path / "reports"
    reports.mkdir()
    rows = ["season,week,player,pts"]
    for contest in range(2):
        for player in range(9):
            rows.append(f"2024,4,p{contest}-{player},{contest + player / 10}")
    (reports / "two.csv").write_text("\n".join(rows) + "\n", encoding="utf-8")
    spec = WinnerSourceSpec(
        relative_path="reports/two.csv",
        source_role="test_roster_capture",
        season_field="season",
        default_season=None,
        week_field="week",
        rows_per_observation=9,
        roster_points_field="pts",
        reported_score_field=None,
    )
    built = build_candidate_ledger(tmp_path, source_specs=(spec,))
    assert built["observation_count"] == 2
    assert built["distinct_season_week_label_count"] == 1
    assert [row["same_source_slate_ordinal"] for row in built["observations"]] == [
        1,
        2,
    ]
    assert [row["physical_rows"] for row in built["observations"]] == [
        {"start": 2, "end": 10, "count": 9},
        {"start": 11, "end": 19, "count": 9},
    ]


def test_policy_template_is_explicitly_unresolved_and_cannot_accept(ledger):
    policy = target_contest_policy_template()
    receipt = adjudication_receipt_template()
    validate_target_contest_policy(policy, require_frozen=False)
    with pytest.raises(WinnerRegistryV2Error, match="not frozen"):
        validate_target_contest_policy(policy, require_frozen=True)
    receipt["decision"] = "accepted"
    with pytest.raises(WinnerRegistryV2Error, match="not frozen"):
        validate_adjudication_receipt(receipt, ledger=ledger, target_policy=policy)


def test_frozen_policy_requires_scope_owner_approval_and_full_contract():
    base = target_contest_policy_template()
    base["target_definition"].update(
        {
            "contest_family": "family",
            "selection_rule": "exact contest ID",
            "multiple_contest_rule": "one exact target per slate",
        }
    )
    base["policy_owner"] = "owner"
    base["approved_at_utc"] = "2026-09-01T00:00:00Z"

    missing_scope = deepcopy(base)
    with pytest.raises(WinnerRegistryV2Error, match="effective scope"):
        seal_target_contest_policy(missing_scope)

    base["effective_scope"] = {"first_season": 2023, "last_season": 2025}
    missing_owner = deepcopy(base)
    missing_owner["policy_owner"] = None
    with pytest.raises(WinnerRegistryV2Error, match="missing policy_owner"):
        seal_target_contest_policy(missing_owner)

    weakened = deepcopy(base)
    weakened["required_contest_identity_fields"].remove("draftkings_contest_id")
    with pytest.raises(WinnerRegistryV2Error, match="weakens contest identity"):
        seal_target_contest_policy(weakened)


def test_accepted_receipt_rejects_unsupported_official_score(ledger):
    policy = _frozen_policy()
    observation = _observations(
        ledger,
        season=2023,
        week=2,
        source_suffix="milly_rosters_2023_2024.csv",
    )[0]
    unsupported = _accepted_receipt(
        ledger, observation, policy, official_evidence=False
    )
    with pytest.raises(WinnerRegistryV2Error, match="official score lacks"):
        validate_adjudication_receipt(
            unsupported, ledger=ledger, target_policy=policy
        )


def test_accepted_receipt_requires_contest_source_and_adjudicator(ledger):
    policy = _frozen_policy()
    observation = _observations(
        ledger,
        season=2023,
        week=2,
        source_suffix="milly_rosters_2023_2024.csv",
    )[0]
    valid = _accepted_receipt(ledger, observation, policy, official_evidence=True)
    validate_adjudication_receipt(valid, ledger=ledger, target_policy=policy)
    assert accepted_observations(ledger, [valid], policy)[0]["observation"] == observation
    assert seal_adjudication_receipt(valid) == valid

    no_contest_id = deepcopy(valid)
    no_contest_id["target_contest_identity"]["draftkings_contest_id"] = None
    no_contest_id = seal_adjudication_receipt(no_contest_id)
    with pytest.raises(WinnerRegistryV2Error, match="missing draftkings_contest_id"):
        validate_adjudication_receipt(
            no_contest_id, ledger=ledger, target_policy=policy
        )

    no_adjudicator = deepcopy(valid)
    no_adjudicator["adjudicator"]["name"] = None
    no_adjudicator = seal_adjudication_receipt(no_adjudicator)
    with pytest.raises(WinnerRegistryV2Error, match="no adjudicator"):
        validate_adjudication_receipt(
            no_adjudicator, ledger=ledger, target_policy=policy
        )

    no_candidate_source = deepcopy(valid)
    no_candidate_source["source_evidence"] = no_candidate_source[
        "source_evidence"
    ][1:]
    no_candidate_source = seal_adjudication_receipt(no_candidate_source)
    with pytest.raises(WinnerRegistryV2Error, match="original candidate artifact"):
        validate_adjudication_receipt(
            no_candidate_source, ledger=ledger, target_policy=policy
        )


def test_accepted_receipt_binds_observation_policy_family_format_and_scope(ledger):
    policy = _frozen_policy()
    observation = _observations(
        ledger,
        season=2023,
        week=2,
        source_suffix="milly_rosters_2023_2024.csv",
    )[0]
    valid = _accepted_receipt(ledger, observation, policy, official_evidence=True)

    wrong_week = deepcopy(valid)
    wrong_week["target_contest_identity"]["week"] = 3
    wrong_week = seal_adjudication_receipt(wrong_week)
    with pytest.raises(WinnerRegistryV2Error, match="disagree with observation"):
        validate_adjudication_receipt(
            wrong_week, ledger=ledger, target_policy=policy
        )

    wrong_family = deepcopy(valid)
    wrong_family["target_contest_identity"]["contest_family"] = "other-family"
    wrong_family = seal_adjudication_receipt(wrong_family)
    with pytest.raises(WinnerRegistryV2Error, match="family disagrees"):
        validate_adjudication_receipt(
            wrong_family, ledger=ledger, target_policy=policy
        )

    wrong_format = deepcopy(valid)
    wrong_format["target_contest_identity"]["roster_format"] = "Showdown"
    wrong_format = seal_adjudication_receipt(wrong_format)
    with pytest.raises(WinnerRegistryV2Error, match="format disagrees"):
        validate_adjudication_receipt(
            wrong_format, ledger=ledger, target_policy=policy
        )

    old_observation = _observations(
        ledger,
        season=2019,
        week=1,
        source_suffix="milly-winners-2019-2023-2024.csv",
    )[0]
    outside_scope = _accepted_receipt(
        ledger,
        old_observation,
        policy,
        official_evidence=True,
        contest_id="old-1",
        official_score="281.36",
        slate_date="2019-09-08",
    )
    with pytest.raises(WinnerRegistryV2Error, match="outside frozen policy"):
        validate_adjudication_receipt(
            outside_scope, ledger=ledger, target_policy=policy
        )


def test_accepted_cohort_has_one_contest_id_and_one_target_per_policy_slate(ledger):
    policy = _frozen_policy()
    article_w2 = _observations(
        ledger,
        season=2023,
        week=2,
        source_suffix="milly_rosters_2023_2024.csv",
    )[0]
    canonical_w2 = _observations(
        ledger,
        season=2023,
        week=2,
        source_suffix="milly-winners-2019-2023-2024.csv",
    )[0]
    article_w3 = _observations(
        ledger,
        season=2023,
        week=3,
        source_suffix="milly_rosters_2023_2024.csv",
    )[0]

    first = _accepted_receipt(
        ledger, article_w2, policy, official_evidence=True, contest_id="c-w2-a"
    )
    second_same_slate = _accepted_receipt(
        ledger,
        canonical_w2,
        policy,
        official_evidence=True,
        contest_id="c-w2-b",
        official_score="201.24",
    )
    with pytest.raises(WinnerRegistryV2Error, match="policy slate"):
        accepted_observations(ledger, [first, second_same_slate], policy)

    second_same_contest_id = _accepted_receipt(
        ledger,
        article_w3,
        policy,
        official_evidence=True,
        contest_id="c-w2-a",
        official_score="294.38",
        slate_date="2023-09-24",
    )
    with pytest.raises(WinnerRegistryV2Error, match="duplicate accepted target"):
        accepted_observations(ledger, [first, second_same_contest_id], policy)
