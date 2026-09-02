from __future__ import annotations

import os
from hashlib import sha256
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from nfl_dfs.app import historical_corpus_research as api
from nfl_dfs.research import corpus_r6_historical_realized_summary_v1 as contract


def _ratio(numerator: int, denominator: int) -> dict[str, int]:
    return {"numerator": numerator, "denominator": denominator}


def _generation_rows(
    coordinates: list[tuple[str, str]],
) -> list[dict[str, object]]:
    binding = contract._PRODUCTION_BINDING
    total_visits = int(binding.expected_reconciliation["visit_occurrence_count"])
    high_visits = 574
    rows: list[dict[str, object]] = []
    for ordinal, (arm, block) in enumerate(coordinates):
        visits = total_visits - len(coordinates) + 1 if ordinal == 0 else 1
        row: dict[str, object] = {
            "source_slate_count": binding.slate_count,
            "full_population_candidate_count": binding.expected_reconciliation[
                "candidate_count"
            ],
            "candidate_membership_count": (
                binding.expected_reconciliation["candidate_count"]
                if ordinal == 0
                else 1
            ),
            "visit_count": visits,
            "high_score_candidate_membership_count": 279 if ordinal == 0 else 0,
            "high_score_visit_count": high_visits if ordinal == 0 else 0,
            "high_score_visit_rate": _ratio(high_visits if ordinal == 0 else 0, visits),
        }
        if arm:
            row["fill_arm_id"] = arm
        if block:
            row["world_block_id"] = block
        rows.append(row)
    return rows


def _valid_summary() -> dict[str, object]:
    binding = contract._PRODUCTION_BINDING
    selected_sums = (
        9_551_620_000,
        9_523_400_000,
        9_635_500_000,
        9_504_140_000,
        9_533_020_000,
        9_635_500_000,
        9_563_560_000,
        9_582_960_000,
    )
    positive = (50, 51, 49, 50, 51, 49, 49, 49)
    below = (23, 23, 23, 23, 23, 23, 22, 22)
    selected_slates = (6, 6, 6, 6, 6, 6, 7, 7)
    selected_slots = (9, 10, 13, 22, 13, 13, 12, 13)
    eligible_sum = 10_943_760_000
    strategies: list[dict[str, object]] = []
    for ordinal, strategy_id in enumerate(binding.strategy_ids):
        selected_sum = selected_sums[ordinal]
        rescue_sum = eligible_sum - selected_sum
        strategies.append(
            {
                "strategy_id": strategy_id,
                "strategy_sha256": sha256(strategy_id.encode()).hexdigest(),
                "cohort": "one-final-fit-book-per-source-slate",
                "threshold_operator": "greater-than-or-equal",
                "score_unit": "micro_dk",
                "mean_denominator_slate_count": binding.slate_count,
                "source_slate_count": binding.slate_count,
                "entry_count_k": 80,
                "eligible_maximum_score_sum_micro": eligible_sum,
                "eligible_maximum_score_mean_micro": _ratio(
                    eligible_sum, binding.slate_count
                ),
                "selected_maximum_score_sum_micro": selected_sum,
                "selected_maximum_score_mean_micro": _ratio(
                    selected_sum, binding.slate_count
                ),
                "sum_individual_rescue_deltas_micro": rescue_sum,
                "mean_individual_rescue_delta_micro": _ratio(
                    rescue_sum, binding.slate_count
                ),
                "positive_rescue_slate_count": positive[ordinal],
                "eligible_high_selected_below_threshold_slate_count": below[ordinal],
                "selected_high_slate_count": selected_slates[ordinal],
                "selected_high_score_lineup_slot_count": selected_slots[ordinal],
                "rescue_sum_is_jointly_achievable": False,
            }
        )
    source = {
        "accepted_e0_receipt_file_sha256": binding.receipt_file_sha256,
        "accepted_e0_receipt_sha256": binding.receipt_sha256,
        "e0_plan_sha256": binding.plan_sha256,
        "e0_manifest_sha256": binding.manifest_sha256,
        "no_rescore_funnel_identity": dict(binding.funnel_identity),
        "no_rescore_funnel_internal_sha256": binding.funnel_internal_sha256,
        "source_object_count": binding.source_object_count,
        "source_object_manifest_sha256": binding.source_object_manifest_sha256,
        "source_row_digest_manifest_sha256": (
            binding.source_row_digest_manifest_sha256
        ),
        "node_rows_sha256": binding.node_rows_sha256,
        "relationship_rows_sha256": binding.relationship_rows_sha256,
    }
    total_candidates = int(binding.expected_reconciliation["candidate_count"])
    total_visits = int(binding.expected_reconciliation["visit_occurrence_count"])
    body: dict[str, object] = {
        "schema_version": contract.SUMMARY_SCHEMA,
        "evidence_class": contract.EVIDENCE_CLASS,
        "threshold_dk": binding.threshold_dk,
        "threshold_micro": binding.threshold_dk * 1_000_000,
        "source_binding": source,
        "outcome_funnel_summary": {
            "cohort": "persisted-eligible-lineups-at-or-above-threshold",
            "threshold_operator": "greater-than-or-equal",
            "score_unit": "micro_dk",
            "source_slate_count": binding.slate_count,
            "final_fit_strategy_count": len(binding.strategy_ids),
            "eligible_high_score_lineup_count": 279,
            "observed_in_any_final_fit_book_count": 38,
            "first_observed_absence_count": 241,
            "opportunity_slate_count": 29,
            "converted_slate_count": 10,
            "unconverted_opportunity_slate_count": 19,
            "selected_high_scorer_book_edge_count": 105,
            "absent_high_scorer_book_edge_count": 2_127,
            "book_classification_edge_count": 2_232,
            "first_observed_absence_class": contract.FIRST_OBSERVED_ABSENCE_CLASS,
            "absence_derivation": (
                "synthesized-set-difference-across-observed-final-fit-books"
            ),
            "source_emitted_selector_rejection": False,
            "causal_first_loss_claim": False,
        },
        "strategy_rescue_summary": strategies,
        "generation_yield_summary": {
            "cohort": "full-fixed-g0-candidate-population",
            "threshold_operator": "greater-than-or-equal",
            "score_unit": "micro_dk",
            "rate_denominator_unit": "generation_visit",
            "total_candidate_count": total_candidates,
            "total_visit_count": total_visits,
            "total_high_score_visit_count": 574,
            "candidate_membership_semantics": (
                "overlapping-within-dimension-not-additive-across-rows"
            ),
            "visit_semantics": "partitioned-generation-occurrences",
            "by_fill_arm": _generation_rows([(arm, "") for arm in binding.arm_ids]),
            "by_world_block": _generation_rows(
                [("", block) for block in binding.block_ids]
            ),
            "by_fill_arm_world_block": _generation_rows(
                [(arm, block) for arm in binding.arm_ids for block in binding.block_ids]
            ),
        },
        "uses_realized_outcomes": True,
        "persisted_realized_labels_only": True,
        "separate_from_corpus_graph_vnext_v2": True,
        "raw_outcome_query_performed": False,
        "lineup_rescore_performed": False,
        "individual_rows_included": False,
        "neo4j_mutation_performed": False,
        "promotion_authority": False,
        "decision_authority": False,
        "policy_feedback_authority": False,
        "complete": True,
    }
    body["summary_sha256"] = contract.canonical_sha256(body)
    return contract.validate_historical_realized_summary_v1(body)


def _client(reader: object | None = None) -> TestClient:
    app = FastAPI()
    app.include_router(api.router)
    if reader is not None:
        app.dependency_overrides[api.get_historical_realized_summary_reader] = lambda: (
            reader
        )
    return TestClient(app)


class _Reader:
    def __init__(self, value: object = None, error: Exception | None = None) -> None:
        self.value = value
        self.error = error

    def read(self) -> object:
        if self.error is not None:
            raise self.error
        return self.value


def test_file_reader_and_route_revalidate_on_every_request(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    value = _valid_summary()
    path = tmp_path / "summary.json"
    path.write_bytes(contract.canonical_json_bytes(value) + b"\n")
    reader = api.FileHistoricalRealizedSummaryReader(path)
    real_validate = contract.validate_historical_realized_summary_v1
    calls: list[object] = []

    def tracked(candidate: object) -> dict[str, object]:
        calls.append(candidate)
        return real_validate(candidate)

    monkeypatch.setattr(api.summary, "validate_historical_realized_summary_v1", tracked)
    client = _client(reader)
    response = client.get("/api/corpus-research/historical-realized-summary")
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert response.json()["summary_sha256"] == value["summary_sha256"]
    assert len(calls) == 2

    path.write_bytes(b"{}\n")
    second = client.get("/api/corpus-research/historical-realized-summary")
    assert second.status_code == 503
    assert second.headers["cache-control"] == "no-store"


def test_unconfigured_and_injected_errors_are_generic_503(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv(api.SUMMARY_PATH_ENV, raising=False)
    unconfigured = _client().get("/api/corpus-research/historical-realized-summary")
    assert unconfigured.status_code == 503
    assert unconfigured.headers["cache-control"] == "no-store"
    assert api.SUMMARY_PATH_ENV not in unconfigured.text

    secret = "/private/secret/outcome-summary.json"
    failed = _client(_Reader(error=RuntimeError(secret))).get(
        "/api/corpus-research/historical-realized-summary"
    )
    assert failed.status_code == 503
    assert failed.headers["cache-control"] == "no-store"
    assert secret not in failed.text


def test_injected_reader_is_revalidated_at_route_boundary() -> None:
    value = _valid_summary()
    value["summary_sha256"] = "0" * 64
    response = _client(_Reader(value=value)).get(
        "/api/corpus-research/historical-realized-summary"
    )
    assert response.status_code == 503
    assert response.headers["cache-control"] == "no-store"


@pytest.mark.parametrize("mutation", ["missing-lf", "extra-lf", "pretty"])
def test_file_reader_requires_exact_canonical_json_plus_one_lf(
    tmp_path: Path, mutation: str
) -> None:
    value = _valid_summary()
    canonical = contract.canonical_json_bytes(value)
    raw = {
        "missing-lf": canonical,
        "extra-lf": canonical + b"\n\n",
        "pretty": (str(value) + "\n").encode(),
    }[mutation]
    path = tmp_path / "summary.json"
    path.write_bytes(raw)
    with pytest.raises(ValueError):
        api.FileHistoricalRealizedSummaryReader(path).read()


@pytest.mark.parametrize("kind", ["relative", "symlink", "hardlink", "oversize"])
def test_file_reader_rejects_unsafe_file_envelopes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, kind: str
) -> None:
    value = _valid_summary()
    source = tmp_path / "summary.json"
    source.write_bytes(contract.canonical_json_bytes(value) + b"\n")
    path = source
    if kind == "relative":
        monkeypatch.chdir(tmp_path)
        path = Path("summary.json")
    elif kind == "symlink":
        path = tmp_path / "summary-link.json"
        path.symlink_to(source)
    elif kind == "hardlink":
        path = tmp_path / "summary-hardlink.json"
        os.link(source, path)
    else:
        path.write_bytes(b"x" * (api.MAX_SUMMARY_BYTES + 1))
    with pytest.raises(ValueError):
        api.FileHistoricalRealizedSummaryReader(path).read()


def test_main_registers_only_the_new_router_import_and_include() -> None:
    main = (Path(api.__file__).parent / "main.py").read_text()
    assert (
        "from .historical_corpus_research import router as historical_research_router"
    ) in main
    assert main.count("app.include_router(historical_research_router)") == 1


def test_first_observed_absence_query_is_aggregate_and_noncausal() -> None:
    value = _valid_summary()

    result = api.first_observed_absence_query(value)

    assert result["schema_version"] == api.FIRST_OBSERVED_ABSENCE_QUERY_SCHEMA
    assert result["source_summary"] == {
        "schema_version": contract.SUMMARY_SCHEMA,
        "summary_sha256": value["summary_sha256"],
    }
    assert result["outcome_funnel_summary"] == value["outcome_funnel_summary"]
    assert result["outcome_funnel_summary"] is not value["outcome_funnel_summary"]
    assert result["interpretation_boundary"] == {
        "localization": "observed-final-fit-book-membership-only",
        "causal_first_loss_claim": False,
        "source_emitted_selector_rejection": False,
        "failed_solver_request_has_roster_identity": False,
        "ordinary_solver_requests_define_finite_roster_universe": False,
        "roster_level_not_produced_claim_available": False,
    }
    assert result["individual_rows_included"] is False
    assert result["neo4j_mutation_performed"] is False
    assert result["separate_from_corpus_graph_vnext_v2"] is True
    assert result["decision_authority"] is False
    assert result["policy_feedback_authority"] is False
    assert result["query_response_complete"] is True
    assert result["complete_prelock_candidate_lineage_available"] is False
    assert "complete" not in result
    assert "strategy_rescue_summary" not in result
    assert "generation_yield_summary" not in result


def test_strategy_rescue_query_supports_all_or_one_exact_aggregate() -> None:
    value = _valid_summary()

    all_rows = api.strategy_rescue_query(value)
    exact = api.strategy_rescue_query(value, strategy_id="expected-max-v1")

    assert all_rows["schema_version"] == api.STRATEGY_RESCUE_QUERY_SCHEMA
    assert all_rows["strategy_filter"] == {"mode": "all", "strategy_id": None}
    assert all_rows["row_count"] == 8
    assert exact["strategy_filter"] == {
        "mode": "exact",
        "strategy_id": "expected-max-v1",
    }
    assert exact["row_count"] == 1
    assert exact["strategy_rescue_summary"][0]["strategy_id"] == "expected-max-v1"
    assert exact["interpretation_boundary"] == {
        "rescue_basis": (
            "per-slate-hindsight-eligible-maximum-minus-observed-selected-book-maximum"
        ),
        "counterfactual_selector_rerun_performed": False,
        "forecast_or_promised_gain_claim": False,
        "rescue_sum_is_jointly_achievable": False,
    }
    assert exact["individual_rows_included"] is False
    assert exact["neo4j_mutation_performed"] is False
    assert exact["promotion_authority"] is False
    exact["strategy_rescue_summary"][0]["strategy_id"] = "mutated"
    assert value["strategy_rescue_summary"][4]["strategy_id"] == "expected-max-v1"


def test_strategy_rescue_query_rejects_an_unknown_strategy() -> None:
    with pytest.raises(api.HistoricalRealizedStrategyNotFoundError):
        api.strategy_rescue_query(_valid_summary(), strategy_id="unknown-strategy")


def test_bounded_query_routes_are_no_store_and_fail_closed() -> None:
    value = _valid_summary()
    client = _client(_Reader(value=value))

    absence = client.get(
        "/api/corpus-research/historical-realized-summary/first-observed-absence"
    )
    rescue = client.get(
        "/api/corpus-research/historical-realized-summary/rescue",
        params={"strategy_id": "expected-max-v1"},
    )
    unknown = client.get(
        "/api/corpus-research/historical-realized-summary/rescue",
        params={"strategy_id": "unknown-strategy"},
    )

    assert absence.status_code == 200
    assert absence.headers["cache-control"] == "no-store"
    assert absence.json()["query_name"] == "first-observed-absence-at-final-book"
    assert rescue.status_code == 200
    assert rescue.headers["cache-control"] == "no-store"
    assert rescue.json()["row_count"] == 1
    assert unknown.status_code == 404
    assert unknown.headers["cache-control"] == "no-store"
    assert unknown.json() == {
        "detail": "Historical realized corpus strategy unavailable."
    }

    broken = _client(_Reader(value={})).get(
        "/api/corpus-research/historical-realized-summary/first-observed-absence"
    )
    assert broken.status_code == 503
    assert broken.headers["cache-control"] == "no-store"
