import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _runner():
    path = ROOT / "scripts/run_cbwu_seed_order_audit.py"
    spec = importlib.util.spec_from_file_location("cbwu_order_runner", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _audit(candidate_jaccard=1.0, selected_jaccard=1.0):
    rotations = []
    for index in range(5):
        rotations.append({
            "candidate_identity_jaccard_vs_canonical": (
                1.0 if index == 0 else candidate_jaccard
            ),
            "selected_identity_jaccard_vs_canonical": (
                1.0 if index == 0 else selected_jaccard
            ),
            "selected_world_coverage": 0.25,
        })
    return {
        "uses_realized_outcomes": False,
        "rotations": rotations,
    }


def test_cbwu_runner_queries_are_score_free_and_scope_is_exact():
    runner = _runner()
    runner.validate_scorefree_queries()
    combined = (runner.SOURCE_SQL + runner.PLAYER_SQL).lower()
    for field in runner.FORBIDDEN_QUERY_TOKENS:
        assert field not in combined
    assert runner.SOURCE_PANEL_IDS == tuple(
        f"20260813-sis-asoe-treatment-r{seed}-v1" for seed in range(5)
    )


def test_cbwu_aggregate_requires_exact_identity_for_invariance():
    runner = _runner()
    audits = []
    for week in range(1, 55):
        audits.append({"season": 2025, "week": week, **_audit()})
    result = runner._aggregate_audits(audits)
    assert result["order_invariant"] is True
    assert result["disposition"] == "cbwu-order-invariant"

    audits[0] = {
        "season": 2025,
        "week": 1,
        **_audit(candidate_jaccard=0.9, selected_jaccard=0.8),
    }
    result = runner._aggregate_audits(audits)
    assert result["order_invariant"] is False
    assert result["selected_changed_comparisons"] == 4
    assert result["disposition"] == "cbwu-order-sensitive-requires-repair"


def test_cbwu_cloud_contract_is_create_only_and_packaged():
    runner = _runner()
    launch = (ROOT / "scripts/cloud_cbwu_seed_order_audit.sh").read_text()
    docker = (ROOT / "Dockerfile").read_text()
    assert "20260815-cbwu-seed-order-scorefree-v1/result.json" in launch
    assert "gcloud storage objects describe" in launch
    assert "--memory 16Gi" in launch
    assert "--max-retries 0" in launch
    assert "COPY scripts/run_cbwu_seed_order_audit.py" in docker
    assert runner.FORENSIC_MANIFEST_SHA256 == (
        "51edbe124846dc936ade71c4e5a9a07e252bcf6c7d7872b979715ccd1f6bab02"
    )
    assert "manifest.txt" in launch
    assert "execution.txt" in launch
    finish = (ROOT / "scripts/cloud_finish_cbwu_seed_order_audit.sh").read_text()
    assert "len(report.get(\"source_artifacts\", [])) != 270" in finish
    assert "aggregate.get(\"cyclic_comparisons\") != 216" in finish
    assert "uses_realized_outcomes" in finish
