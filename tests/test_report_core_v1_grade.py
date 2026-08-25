from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import importlib.util
import json
from pathlib import Path
import sys

import pytest

from nfl_dfs.research import corpus_catalog_realized_grading as grading
from nfl_dfs.research import corpus_core_v1_catalog_materializer as catalog_store
from nfl_dfs.research import corpus_core_v1_grade_publisher as publisher
from nfl_dfs.research import corpus_core_v1_outcome_snapshot as outcome
from nfl_dfs.research import corpus_core_v1_outcome_supply as supply


ROOT = Path(__file__).resolve().parents[1]


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


reporter = _load(
    ROOT / "scripts/report_core_v1_grade.py",
    "report_core_v1_grade_test",
)


def _identity(uri: str, raw: bytes, generation: int) -> dict[str, object]:
    return {
        "uri": uri,
        "generation": str(generation),
        "sha256": sha256(raw).hexdigest(),
        "bytes": len(raw),
    }


class _ReadOnlyBlob:
    def __init__(
        self,
        client: "_ReadOnlyGCSClient",
        bucket: str,
        name: str,
        generation: int | None,
    ) -> None:
        self._client = client
        self._bucket = bucket
        self.name = name
        self.generation = generation

    @property
    def _key(self) -> tuple[str, str]:
        return self._bucket, self.name

    def reload(self, *, if_generation_match: int | None = None) -> None:
        versions = self._client.objects.get(self._key, {})
        if not versions:
            raise RuntimeError("not found")
        if self.generation is None:
            self.generation = max(versions)
            self._client.current_metadata_uris.append(
                f"gs://{self._bucket}/{self.name}"
            )
        if int(self.generation) not in versions:
            raise RuntimeError("generation not found")
        if (
            if_generation_match is not None
            and int(self.generation) != if_generation_match
        ):
            raise RuntimeError("generation precondition failed")

    def download_as_bytes(
        self, *, if_generation_match: int | None = None,
    ) -> bytes:
        if self.generation is None or if_generation_match != int(self.generation):
            raise AssertionError("download was not generation-pinned")
        uri = f"gs://{self._bucket}/{self.name}"
        self._client.pinned_downloads.append((uri, int(self.generation)))
        return self._client.objects[self._key][int(self.generation)]

    def upload_from_string(self, *_args, **_kwargs) -> None:
        self._client.mutation_attempts += 1
        raise AssertionError("read-only reporter attempted an upload")

    def delete(self, *_args, **_kwargs) -> None:
        self._client.mutation_attempts += 1
        raise AssertionError("read-only reporter attempted a delete")


class _ReadOnlyBucket:
    def __init__(self, client: "_ReadOnlyGCSClient", name: str) -> None:
        self._client = client
        self._name = name

    def blob(self, name: str, generation: int | None = None) -> _ReadOnlyBlob:
        return _ReadOnlyBlob(self._client, self._name, name, generation)

    def list_blobs(self, *_args, **_kwargs):
        self._client.list_attempts += 1
        raise AssertionError("read-only reporter attempted an object listing")


class _ReadOnlyGCSClient:
    def __init__(self) -> None:
        self.objects: dict[tuple[str, str], dict[int, bytes]] = {}
        self.current_metadata_uris: list[str] = []
        self.pinned_downloads: list[tuple[str, int]] = []
        self.list_attempts = 0
        self.mutation_attempts = 0

    def bucket(self, name: str) -> _ReadOnlyBucket:
        return _ReadOnlyBucket(self, name)

    def list_blobs(self, *_args, **_kwargs):
        self.list_attempts += 1
        raise AssertionError("read-only reporter attempted an object listing")

    def seed_raw(self, identity: dict[str, object], raw: bytes) -> None:
        assert sha256(raw).hexdigest() == identity["sha256"]
        assert len(raw) == identity["bytes"]
        bucket, name = str(identity["uri"]).removeprefix("gs://").split("/", 1)
        self.objects.setdefault((bucket, name), {})[
            int(str(identity["generation"]))
        ] = raw

    def seed_json(self, identity: dict[str, object], value: object) -> None:
        self.seed_raw(identity, publisher.canonical_json_bytes(value))


@pytest.fixture(scope="module")
def completed_grade() -> dict[str, object]:
    fixture_module = _load(
        ROOT / "tests/test_corpus_core_v1_fast_scoring.py",
        "core_v1_fast_scoring_report_fixture",
    )
    sharded = fixture_module.sharded_core.__wrapped__()
    published_catalog = sharded["published"]
    catalog = published_catalog.logical_catalog
    catalog_identity = published_catalog.catalog_identity
    (
        outcome_keys,
        original_player_source,
        _,
        _,
        _,
    ) = fixture_module._outcome_artifacts(catalog, catalog_identity)

    attempt = dict(original_player_source["attempt"])
    outcome_run_id = str(attempt["run_id"])
    outcome_root = (
        f"gs://{supply.OUTPUT_BUCKET}/{supply.OUTPUT_NAMESPACE}/"
        f"{outcome_run_id}"
    )
    attempt_raw = publisher.canonical_json_bytes(attempt)
    attempt_identity = _identity(
        f"{outcome_root}/read-attempt.json", attempt_raw, 70_001
    )
    player_source_body = dict(original_player_source)
    player_source_body.pop("source_sha256")
    player_source_body["attempt_identity"] = attempt_identity
    player_source = dict(player_source_body)
    player_source["source_sha256"] = publisher.canonical_sha256(
        player_source_body
    )
    player_source_raw = publisher.canonical_json_bytes(player_source)
    player_source_identity = _identity(
        f"{outcome_root}/player-score-source.json",
        player_source_raw,
        70_002,
    )
    outcome_snapshot = outcome.build_core_outcome_snapshot(
        catalog=catalog,
        catalog_identity=catalog_identity,
        player_source=player_source,
        player_source_identity=player_source_identity,
        outcome_keys=outcome_keys,
    )
    outcome_snapshot_raw = publisher.canonical_json_bytes(outcome_snapshot)
    outcome_snapshot_identity = _identity(
        f"{outcome_root}/player-outcome-snapshot.json",
        outcome_snapshot_raw,
        70_003,
    )
    outcome_completion_body = {
        "schema_version": supply.COMPLETION_SCHEMA,
        "run_id": outcome_run_id,
        "catalog_identity": catalog_identity,
        "catalog_sha256": catalog["catalog_sha256"],
        "attempt_identity": attempt_identity,
        "player_source_identity": player_source_identity,
        "outcome_snapshot_identity": outcome_snapshot_identity,
        "outcome_key_count": len(outcome_keys),
        "one_historical_outcome_read": True,
        "independent_source_snapshot_replay_complete": True,
        "rank_available": False,
        "roi_available": False,
        "rank_roi_unavailable_reason": (
            "full_field_standings_and_payout_ladder_not_supplied"
        ),
        "historical_outcome_lease_release_required": True,
        "lease_release_owner": supply.LEASE_RELEASE_OWNER,
        "historical_retry_licensed": False,
        "historical_retune_licensed": False,
        "graph_mutation_licensed": False,
        "production_change_licensed": False,
        "decision_authority": False,
    }
    outcome_completion = dict(outcome_completion_body)
    outcome_completion["completion_sha256"] = publisher.canonical_sha256(
        outcome_completion_body
    )
    outcome_completion_raw = publisher.canonical_json_bytes(outcome_completion)
    outcome_completion_identity = _identity(
        f"{outcome_root}/completion.json", outcome_completion_raw, 70_004
    )

    run_id = "core-grade-report-fixture"
    prefix = reporter.grade_cloud.grade_output_prefix(run_id)
    publisher_fixture = _load(
        ROOT / "tests/test_corpus_core_v1_grade_publisher.py",
        "core_v1_grade_publisher_report_fixture",
    )
    grade_store = publisher_fixture._MemoryStore()
    published_grade = publisher.grade_and_publish_sharded_core_v1(
        catalog=catalog,
        catalog_identity=catalog_identity,
        outcome_snapshot=outcome_snapshot,
        outcome_snapshot_identity=outcome_snapshot_identity,
        player_source=player_source,
        player_source_identity=player_source_identity,
        outcome_keys=outcome_keys,
        output_prefix=prefix,
        max_logical_grade_bytes=100_000_000,
        read_exact=grade_store.read_exact,
        publish_create_once=grade_store.publish_create_once,
    )
    grade = publisher.reopen_sharded_core_v1_realized_grade(
        root_identity=published_grade.root_identity,
        read_exact=grade_store.read_exact,
    )
    catalog_authority = catalog_store.ReopenedShardedCoreV1Catalog(
        root=published_catalog.root,
        root_identity=published_catalog.root_identity,
        catalog_identity=published_catalog.catalog_identity,
        shard_identities=published_catalog.shard_identities,
        logical_catalog=published_catalog.logical_catalog,
    )
    completed_outcomes = reporter.grade_cloud.ReopenedCompletedOutcomes(
        completion=outcome_completion,
        completion_identity=outcome_completion_identity,
        attempt_identity=attempt_identity,
        player_source=player_source,
        player_source_identity=player_source_identity,
        outcome_snapshot=outcome_snapshot,
        outcome_snapshot_identity=outcome_snapshot_identity,
        outcome_keys=tuple(outcome_keys),
    )
    completion = reporter.grade_cloud._grade_completion_body(
        grade_run_id=run_id,
        catalog_authority=catalog_authority,
        completed=completed_outcomes,
        published=published_grade,
        reopened_grade=grade,
    )
    completion_raw = publisher.canonical_json_bytes(completion)
    completion_identity = _identity(
        prefix + reporter.grade_cloud.GRADE_COMPLETION_FILENAME,
        completion_raw,
        70_005,
    )

    client = _ReadOnlyGCSClient()
    for (uri, generation), raw in sharded["store"].raw_by_key.items():
        client.seed_raw(_identity(uri, raw, int(generation)), raw)
    client.seed_json(attempt_identity, attempt)
    client.seed_json(player_source_identity, player_source)
    client.seed_json(outcome_snapshot_identity, outcome_snapshot)
    client.seed_json(outcome_completion_identity, outcome_completion)
    for (uri, generation), raw in grade_store.values_by_key.items():
        client.seed_raw(_identity(uri, raw, int(generation)), raw)
    client.seed_json(completion_identity, completion)
    return {
        "run_id": run_id,
        "prefix": prefix,
        "grade": grade,
        "completion": completion,
        "completion_identity": completion_identity,
        "root_identity": published_grade.root_identity,
        "client": client,
        "catalog_root_identity": published_catalog.root_identity,
        "catalog_identity": published_catalog.catalog_identity,
        "catalog_shard_identities": published_catalog.shard_identities,
        "outcome_completion_identity": outcome_completion_identity,
        "outcome_attempt_identity": attempt_identity,
        "player_source_identity": player_source_identity,
        "outcome_snapshot_identity": outcome_snapshot_identity,
        "summary_identity": published_grade.summary_identity,
        "slate_grade_identities": published_grade.slate_shard_identities,
    }


def _report(fixture: dict[str, object]) -> dict[str, object]:
    return reporter.build_core_v1_grade_report(
        grade_run_id=fixture["run_id"],
        completion=fixture["completion"],
        completion_identity=fixture["completion_identity"],
        realized_grade=fixture["grade"],
    )


def _rehash(value: dict[str, object], field: str) -> None:
    value.pop(field, None)
    value[field] = publisher.canonical_sha256(value)


def _report_with_rebound_grade(
    fixture: dict[str, object], grade: dict[str, object], generation: int,
) -> dict[str, object]:
    completion = deepcopy(fixture["completion"])
    completion["realized_grade_sha256"] = grade["realized_grade_sha256"]
    _rehash(completion, "grade_completion_sha256")
    raw = publisher.canonical_json_bytes(completion)
    completion_identity = _identity(
        str(fixture["completion_identity"]["uri"]), raw, generation
    )
    return reporter.build_core_v1_grade_report(
        grade_run_id=fixture["run_id"],
        completion=completion,
        completion_identity=completion_identity,
        realized_grade=grade,
    )


def test_report_exposes_absolute_and_paired_score_surfaces(
    completed_grade: dict[str, object],
) -> None:
    report = _report(completed_grade)

    assert report["schema_version"] == reporter.REPORT_SCHEMA
    assert report["status"] == reporter.REPORT_STATUS
    assert report["baseline_strategy_id"] == "r194:incumbent"
    assert report["absolute_strategy_ids"] == list(
        reporter.ABSOLUTE_STRATEGY_IDS
    )
    assert report["source_fill_strategy_ids"] == list(
        reporter.SOURCE_STRATEGY_IDS
    )
    assert report["t230_strategy_ids"] == list(reporter.T230_STRATEGY_IDS)
    assert report["thresholds_dk"] == [180, 194, 200, 210, 220, 230, 240, 250]
    assert len(report["absolute_strategy_budget_summaries"]) == 12 * 3
    assert len(report["weekly_strategy_budget_rows"]) == 54 * 12 * 3
    assert len(report["primary_paired_summaries"]) == 5 * 3
    assert len(report["weekly_primary_contrasts"]) == 54 * 5 * 3
    assert len(report["shared_union_ceiling_rows"]) == 54
    assert {
        (row["strategy_id"], row["entry_budget"])
        for row in report["absolute_strategy_budget_summaries"]
    } == {
        (strategy_id, budget)
        for strategy_id in reporter.ABSOLUTE_STRATEGY_IDS
        for budget in reporter.catalog.EXPECTED_BOOK_BUDGETS
    }
    assert {
        (row["source_ordinal"], row["strategy_id"], row["entry_budget"])
        for row in report["weekly_strategy_budget_rows"]
    } == {
        (source_ordinal, strategy_id, budget)
        for source_ordinal in range(54)
        for strategy_id in reporter.ABSOLUTE_STRATEGY_IDS
        for budget in reporter.catalog.EXPECTED_BOOK_BUDGETS
    }

    baseline4 = next(
        row
        for row in report["absolute_strategy_budget_summaries"]
        if row["strategy_id"] == "r194:incumbent"
        and row["entry_budget"] == 4
    )
    expected_maxima: list[int] = []
    expected_200_hits = 0
    for slate in completed_grade["grade"]["slate_grades"]:
        book = next(
            row
            for row in slate["book_grades"]
            if row["strategy_id"] == "r194:incumbent"
            and row["entry_budget"] == 4
        )
        expected_maxima.append(book["maximum_micro"])
        expected_200_hits += next(
            row["at_or_above_count"]
            for row in book["thresholds"]
            if row["threshold_dk"] == 200
        )
    assert baseline4["overall_best_score"]["micro_dk"] == max(
        expected_maxima
    )
    assert baseline4["weekly_maximum_mean"] == {
        "numerator": sum(expected_maxima) // 54,
        "denominator": 1,
        "unit": "micro_dk",
        "dk_points_display": (
            f"{sum(expected_maxima) / 54 / 1_000_000:.3f}"
        ),
    }
    assert next(
        row["selected_lineup_hit_count"]
        for row in baseline4["thresholds"]
        if row["threshold_dk"] == 200
    ) == expected_200_hits

    paired = next(
        row
        for row in report["primary_paired_summaries"]
        if row["challenger_strategy_id"]
        == "t230:coverage-ge-230-v1"
        and row["entry_budget"] == 4
    )
    authoritative = next(
        row
        for row in completed_grade["grade"]["contrast_summaries"]
        if row["family"] == "primary-headline"
        and row["challenger_strategy_id"]
        == "t230:coverage-ge-230-v1"
        and row["entry_budget"] == 4
    )
    assert paired["overall"]["weekly_maximum_delta_sum"]["micro_dk"] == (
        authoritative["overall"]["weekly_maximum_delta_sum_micro"]
    )
    assert paired["overall"]["threshold_delta_sums"] == authoritative[
        "overall"
    ]["threshold_delta_sums"]
    assert report["contest_metrics"]["rank"] is None
    assert report["contest_metrics"]["roi_micro_usd"] is None
    assert "threshold_187_not_prespecified_in_core_v1" in report["limitations"]
    assert report["object_listing_used"] is False
    assert report["decision_authority"] is False

    retained_hash = report["report_sha256"]
    body = {key: value for key, value in report.items() if key != "report_sha256"}
    assert retained_hash == publisher.canonical_sha256(body)

    markdown = reporter.render_markdown(report)
    assert "Contest rank and ROI are **unavailable**" in markdown
    assert "Absolute results — 4 entries" in markdown
    assert "`t230:support-switched-policy-v1`" in markdown
    assert "all 1,944 absolute weekly book rows" in markdown


def test_report_rejects_rehashed_gap_sensitivity_and_label_drift(
    completed_grade: dict[str, object],
) -> None:
    forged_gap = deepcopy(completed_grade["grade"])
    gap_book = forged_gap["slate_grades"][0]["book_grades"][0]
    gap_book["gap_to_shared_corpus_ceiling_micro"] += 1
    _rehash(gap_book, "book_grade_sha256")
    _rehash(forged_gap["slate_grades"][0], "slate_grade_sha256")
    _rehash(forged_gap, "realized_grade_sha256")
    with pytest.raises(
        reporter.CoreV1GradeReportError, match="corpus-ceiling gap differs"
    ):
        _report_with_rebound_grade(completed_grade, forged_gap, 80_001)

    forged_sensitivity = deepcopy(completed_grade["grade"])
    primary_summary = next(
        row
        for row in forged_sensitivity["contrast_summaries"]
        if row["family"] == "primary-headline"
    )
    primary_summary["season_summaries"][0][
        "weekly_maximum_delta_sum_micro"
    ] += 1
    _rehash(primary_summary, "contrast_summary_sha256")
    _rehash(forged_sensitivity, "realized_grade_sha256")
    with pytest.raises(
        reporter.CoreV1GradeReportError,
        match="paired season .* differs from its weekly replay",
    ):
        _report_with_rebound_grade(
            completed_grade, forged_sensitivity, 80_002
        )

    forged_label = deepcopy(completed_grade["grade"])
    primary_week = next(
        row
        for row in forged_label["weekly_contrasts"]
        if row["family"] == "primary-headline"
    )
    primary_week["season"] += 1
    _rehash(primary_week, "contrast_row_sha256")
    _rehash(forged_label, "realized_grade_sha256")
    with pytest.raises(
        reporter.CoreV1GradeReportError, match="slate label differs"
    ):
        _report_with_rebound_grade(completed_grade, forged_label, 80_003)


def test_cli_is_default_off_and_exact_reopens_full_chain_without_listing(
    completed_grade: dict[str, object], capsys,
) -> None:
    argv = [
        "--grade-run-id",
        completed_grade["run_id"],
        "--grade-completion-uri",
        completed_grade["prefix"] + reporter.grade_cloud.GRADE_COMPLETION_FILENAME,
        "--grade-root-uri",
        completed_grade["prefix"] + publisher.ROOT_FILENAME,
    ]
    with pytest.raises(
        reporter.CoreV1GradeReportError, match="required explicitly"
    ):
        reporter.main(argv, environ={}, storage_client=object())
    assert capsys.readouterr().out == ""

    client = completed_grade["client"]
    assert reporter.main(
        ["--execute", *argv],
        environ={reporter.ENABLED_ENV: "1"},
        storage_client=client,
    ) == 0
    output = json.loads(capsys.readouterr().out)
    assert output["grade_root_identity"] == completed_grade["root_identity"]
    assert client.current_metadata_uris == [
        completed_grade["completion_identity"]["uri"]
    ]
    assert client.list_attempts == 0
    assert client.mutation_attempts == 0
    assert not hasattr(
        reporter.grade_cloud.ReadOnlyGenerationPinnedGCS(client),
        "publish_create_once",
    )
    downloaded_uris = {uri for uri, _ in client.pinned_downloads}
    required_uris = {
        completed_grade["completion_identity"]["uri"],
        completed_grade["catalog_root_identity"]["uri"],
        completed_grade["outcome_completion_identity"]["uri"],
        completed_grade["root_identity"]["uri"],
        completed_grade["summary_identity"]["uri"],
        *(
            identity["uri"]
            for identity in completed_grade["slate_grade_identities"]
        ),
    }
    assert required_uris <= downloaded_uris
    exact_chain_identities = [
        completed_grade["completion_identity"],
        completed_grade["catalog_root_identity"],
        completed_grade["catalog_identity"],
        *completed_grade["catalog_shard_identities"],
        completed_grade["outcome_completion_identity"],
        completed_grade["outcome_attempt_identity"],
        completed_grade["player_source_identity"],
        completed_grade["outcome_snapshot_identity"],
        completed_grade["root_identity"],
        completed_grade["summary_identity"],
        *completed_grade["slate_grade_identities"],
    ]
    assert downloaded_uris == {
        identity["uri"] for identity in exact_chain_identities
    }
    assert set(client.pinned_downloads) == {
        (identity["uri"], int(identity["generation"]))
        for identity in exact_chain_identities
    }

    source = (ROOT / "scripts/report_core_v1_grade.py").read_text()
    assert "list_blobs(" not in source
    assert "list_objects(" not in source
    assert "publish_create_once(" not in source
    assert "resolve_current_exact(" not in source


def test_cli_rejects_uri_drift_before_storage_or_reopen(
    completed_grade: dict[str, object], monkeypatch,
) -> None:
    monkeypatch.setattr(
        reporter.grade_cloud,
        "reopen_completed_core_v1_grade",
        lambda **_kwargs: pytest.fail("reopen must not run"),
    )
    with pytest.raises(
        reporter.CoreV1GradeReportError, match="root URI differs"
    ):
        reporter.main(
            [
                "--execute",
                "--grade-run-id",
                completed_grade["run_id"],
                "--grade-completion-uri",
                completed_grade["prefix"]
                + reporter.grade_cloud.GRADE_COMPLETION_FILENAME,
                "--grade-root-uri",
                "gs://fixture/wrong-root.json",
            ],
            environ={reporter.ENABLED_ENV: "1"},
            storage_client=object(),
        )
