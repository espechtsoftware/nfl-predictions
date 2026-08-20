from __future__ import annotations

from hashlib import sha256
import importlib.util
import json
from pathlib import Path
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
SPEC = importlib.util.spec_from_file_location(
    "run_b1_corpus_tail_model", ROOT / "scripts/run_b1_corpus_tail_model.py",
)
assert SPEC and SPEC.loader
runner = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(runner)


def _pinned_json(path: Path, value: object) -> dict[str, str]:
    raw = (
        json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)
        + "\n"
    ).encode()
    path.write_bytes(raw)
    return {"path": str(path), "sha256": sha256(raw).hexdigest()}


def test_outcome_blind_sql_has_no_realized_or_winner_column():
    sql = runner._candidate_sql(outcomes=False, one_slate=True).lower()
    assert "actual_score" not in sql
    assert "winner" not in sql
    assert "@season" in sql and "@week" in sql


def test_historical_sql_adds_only_the_registered_score_label():
    sql = runner._candidate_sql(outcomes=True, one_slate=False).lower()
    assert "actual_score" in sql
    assert "winner" not in sql
    assert "payout" not in sql and "winnings" not in sql


def test_label_state_requires_exact_boolean_dtype():
    pandas = __import__("pandas")
    runner._require_exact_boolean_series(
        pandas.Series([True, False]), field="labels_complete",
    )
    for values in ([1, 0], ["true", "false"], [True, None]):
        with pytest.raises(Exception, match="exact boolean"):
            runner._require_exact_boolean_series(
                pandas.Series(values), field="labels_complete",
            )


def test_historical_runner_validates_live_lease_before_source_query(monkeypatch, tmp_path):
    events = []
    monkeypatch.setattr(runner, "_require_b1_pins", lambda: None)
    monkeypatch.setattr(runner, "_validate_protocol", lambda value: "a" * 64)
    monkeypatch.setattr(
        runner, "_validate_live_lease",
        lambda path: events.append("lease") or {"object": {}},
    )
    monkeypatch.setattr(
        runner, "_create_historical_attempt",
        lambda **kwargs: events.append("attempt") or {"object": {}},
    )

    def source(*args, **kwargs):
        events.append("query")
        raise RuntimeError("stop after ordering check")

    monkeypatch.setattr(runner, "_source_frames", source)
    with pytest.raises(RuntimeError, match="ordering check"):
        runner._historical(
            object(), report_path=tmp_path / "report.json",
            model_path=tmp_path / "model.json", protocol_sha="a" * 64,
            lease_path=tmp_path / "lease.json",
            attempt_path=tmp_path / "attempt.json",
        )
    assert events == ["lease", "attempt", "query"]


def test_historical_lease_must_be_the_current_live_generation(monkeypatch, tmp_path):
    lease = {"version": "historical-outcome-active-v1", "run_id": runner.RUN_ID}
    raw = (json.dumps(lease, sort_keys=True, separators=(",", ":")) + "\n").encode()
    receipt = {
        "lease": lease,
        "object": {
            "uri": runner.LEASE_URI, "generation": "7",
            "sha256": sha256(raw).hexdigest(), "create_only": True,
        },
    }
    receipt_path = tmp_path / "lease.json"
    receipt_path.write_text(json.dumps(receipt), encoding="utf-8")

    class Blob:
        generation = "7"

        def reload(self):
            return None

        def download_as_bytes(self, *, if_generation_match):
            assert if_generation_match == 7
            return raw

    class Bucket:
        def blob(self, name):
            return Blob()

    class Client:
        def bucket(self, name):
            return Bucket()

    monkeypatch.setattr(runner.storage, "Client", lambda **kwargs: Client())
    assert runner._validate_live_lease(receipt_path)["lease"] == lease

    Blob.generation = "8"
    with pytest.raises(Exception, match="current live generation"):
        runner._validate_live_lease(receipt_path)


def test_shadow_interface_is_2026_only():
    with pytest.raises(Exception, match="invalid"):
        runner._shadow(
            object(), slate=(2025, 1), panels=["p"], canonical_panel="p",
            model_path=Path("model.json"), output=Path("out.json"),
            snapshot_id="late", lock_at="2025-09-01T17:00:00Z",
        )


def test_shadow_rejects_nonboolean_label_state_before_build(monkeypatch, tmp_path):
    candidates = __import__("pandas").DataFrame({
        "panel_run_id": ["p"], "labels_complete": ["false"],
    })
    players = __import__("pandas").DataFrame({"id": ["p"]})
    monkeypatch.setattr(
        runner, "_source_frames", lambda *args, **kwargs: (candidates, players, {}),
    )
    with pytest.raises(Exception, match="exact boolean"):
        runner._shadow(
            object(), slate=(2026, 1), panels=["p"], canonical_panel="p",
            model_path=tmp_path / "model.json", output=tmp_path / "out.json",
            snapshot_id="late", lock_at="2026-09-01T17:00:00Z",
        )


def test_adoption_grades_are_derived_from_pinned_books_and_scores(tmp_path):
    weeks = []
    for week in range(1, 7):
        control = [
            {"rank": rank, "roster_key": ",".join(f"c{week}-{rank}-{slot}" for slot in range(9))}
            for rank in range(80)
        ]
        challenger = [
            {
                "rank": rank,
                "roster_key": ",".join(f"t{week}-{rank}-{slot}" for slot in range(9)),
                "prelock_tail_score": 0.5,
            }
            for rank in range(80)
        ]
        receipt = {
            "version": "b1-corpus-tail-shadow-receipt-v1",
            "policy_version": "b1-corpus-tail-exact80-shadow-v1",
            "season": 2026, "week": week,
            "model_artifact_sha256": "a" * 64,
            "source_identity": {
                "snapshot_id": f"2026-{week}",
                "snapshot_at": f"2026-09-{week:02d}T15:00:00+00:00",
                "lock_at": f"2026-09-{week:02d}T17:00:00+00:00",
                "panels": ["canonical"], "canonical_panel": "canonical",
                "candidate_query": {
                    "ended": f"2026-09-{week:02d}T14:59:00+00:00",
                },
                "player_query": {
                    "ended": f"2026-09-{week:02d}T15:00:00+00:00",
                },
                "realized_outcome_columns_read": [],
            },
            "candidate_budget_control": 255,
            "candidate_budget_challenger": 255,
            "entry_budget": 80,
            "redundancy": {},
            "control_entries": control,
            "challenger_entries": challenger,
            "uses_realized_outcomes": False,
            "uses_winner_target_or_feature": False,
            "production_licensed": False,
            "prospective_adoption_gate_required": True,
        }
        scores = [
            {"roster_key": row["roster_key"], "actual_score": 190.0 + week}
            for row in control
        ] + [
            {"roster_key": row["roster_key"], "actual_score": 200.0 + week}
            for row in challenger
        ]
        settled = {
            "version": "b1-corpus-tail-settled-scores-v1",
            "season": 2026, "week": week,
            "labels_complete": True,
            "source_identity": {
                "source": "replay_candidates_staging.actual_score",
                "job_id": f"settled-{week}",
                "query_sha256": "b" * 64,
                "captured_at": f"2026-09-{week:02d}T22:00:00+00:00",
            },
            "scores": scores,
        }
        weeks.append({
            "week": week,
            "shadow_receipt": _pinned_json(tmp_path / f"receipt-{week}.json", receipt),
            "settled_scores": _pinned_json(tmp_path / f"scores-{week}.json", settled),
        })
    manifest_path = tmp_path / "manifest.json"
    _pinned_json(manifest_path, {
        "version": "b1-corpus-tail-adoption-grade-manifest-v1",
        "season": 2026,
        "weeks": weeks,
    })
    grades = runner._materialize_adoption_grades(manifest_path)
    assert grades.week.tolist() == list(range(1, 7))
    assert grades.control_max.tolist() == [191, 192, 193, 194, 195, 196]
    assert grades.challenger_max.tolist() == [201, 202, 203, 204, 205, 206]

    receipt_path = Path(weeks[0]["shadow_receipt"]["path"])
    receipt_path.write_bytes(receipt_path.read_bytes().replace(b"255", b"256", 1))
    with pytest.raises(Exception, match="SHA-256"):
        runner._materialize_adoption_grades(manifest_path)
