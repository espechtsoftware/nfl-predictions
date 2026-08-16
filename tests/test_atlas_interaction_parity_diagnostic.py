from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path

import pulp

from scripts.run_atlas_interaction_parity_diagnostic import (
    _digest,
    _interaction_variable_mode,
    _proposal_signature,
)


ROOT = Path(__file__).resolve().parents[1]


def test_interaction_parity_protocol_and_source_are_frozen() -> None:
    protocol = (
        ROOT / "reports/2026-08-16-atlas-continuous-interaction-parity-protocol.md"
    )
    source = ROOT / "scripts/run_atlas_interaction_parity_diagnostic.py"

    assert sha256(source.read_bytes()).hexdigest() == (
        "f8b5b54ce3aab95be36d32bdb3825f2c0b34ed9552c7ebaf0085f0e5f0fb1d2d"
    )
    text = protocol.read_text(encoding="utf-8")
    assert "85aace06-7f36-4307-acfa-194c4648ef6d" in text
    assert "2024 Week 15" in text
    assert "2023 Week 8" in text
    assert "ordered list of 40 roster identities" in text
    assert "proposal-path signature" in text
    build_config = ROOT / "cloudbuild-atlas-continuous.yaml"
    assert sha256(build_config.read_bytes()).hexdigest() == (
        "950db566469aa645efda634370e1f6fe7554db6317537e3a820e9161bec8f93e"
    )
    assert "PYTHONPATH=. pytest" in (
        ROOT / "cloudbuild.yaml"
    ).read_text(encoding="utf-8")
    repair = (
        ROOT / "reports/2026-08-16-atlas-continuous-build-path-repair.md"
    ).read_text(encoding="utf-8")
    assert "85aace06-7f36-4307-acfa-194c4648ef6d" in repair
    assert "atlas-continuous-0679731-r1" in repair


def test_interaction_variable_mode_forces_only_interaction_auxiliaries() -> None:
    with _interaction_variable_mode(force_binary=True) as observed:
        roster = pulp.LpVariable("x_player", cat=pulp.LpBinary)
        interaction = pulp.LpVariable(
            "interaction_0", lowBound=0.0, upBound=1.0,
            cat=pulp.LpContinuous,
        )
    assert roster.cat == pulp.LpInteger
    assert interaction.cat == pulp.LpInteger
    assert observed == {
        "variables": 1,
        "declared_categories": {"Continuous"},
        "effective_categories": {"Binary"},
    }

    with _interaction_variable_mode(force_binary=False) as observed:
        interaction = pulp.LpVariable(
            "interaction_1", lowBound=0.0, upBound=1.0,
            cat=pulp.LpContinuous,
        )
    assert interaction.cat == pulp.LpContinuous
    assert observed["effective_categories"] == {"Continuous"}


def test_interaction_parity_launcher_is_strictly_gated_and_score_free() -> None:
    launcher = (
        ROOT / "scripts/cloud_atlas_interaction_parity_diagnostic.sh"
    ).read_text(encoding="utf-8")
    assert "PREFLIGHT_STATUS" in launcher
    assert '[ "$PREFLIGHT_STATUS" = False ]' in launcher
    assert "repair5 retains queue priority" in launcher
    assert "ATLAS_INTERACTION_PARITY_SMOKE_OK" in launcher
    assert "atlas-continuous-0679731-r1" not in launcher
    assert (
        "sha256:437641a46e1c952ec2f1628428904c89fb4f8eef3d2a2c42a52262c45817231f"
        in launcher
    )
    assert "--cpu 8 --memory 32Gi" in launcher
    assert "--max-retries 0 --task-timeout 12h" in launcher
    assert "uses_realized_outcomes=false" in launcher
    assert "persists_lineups=false" in launcher


def test_interaction_parity_finisher_enforces_exact_gate_and_firewall() -> None:
    finisher = (
        ROOT / "scripts/cloud_finish_atlas_interaction_parity_diagnostic.sh"
    ).read_text(encoding="utf-8")
    assert 'container.get("command")!="python"' not in finisher
    assert 'container.get("command")!=["python"]' in finisher
    assert 'r.get("binary_candidate_count")!=40' in finisher
    assert 'r.get("continuous_candidate_count")!=40' in finisher
    assert "ordered_roster_parity" in finisher
    assert "proposal_path_parity" in finisher
    assert "interaction_category_instrumentation_valid" in finisher
    assert "real-slate-parity-passes" in finisher
    assert "real-slate-parity-fails" in finisher
    assert '"roster_ids","player_ids"' in finisher
    assert "production_change_licensed=false" in finisher


def test_proposal_signature_is_canonical_and_excludes_numeric_receipts() -> None:
    row = {
        "pass": 1,
        "target_cluster": 2,
        "source_cluster": 3,
        "world": 4,
        "stage": "near_optimal_interaction",
        "accepted": True,
        "roster": ["a", "b"],
        "newly_covered_interactions": 2,
        "newly_covered_pairs": 1,
        "newly_covered_triples": 1,
        "interaction_optimum": 12.345,
        "score": 234.5,
    }
    expected = [{
        key: value for key, value in row.items()
        if key not in {"interaction_optimum", "score"}
    }]
    signature = _proposal_signature({"proposals": [row]})
    assert signature == expected
    assert _digest(signature) == sha256(json.dumps(
        expected, sort_keys=True, separators=(",", ":"),
    ).encode()).hexdigest()
