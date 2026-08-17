from __future__ import annotations

from hashlib import sha256
from pathlib import Path
import subprocess


ROOT = Path(__file__).resolve().parents[1]
WRAPPER = ROOT / "scripts/atlas_repair5_validator_bin/awk"


def test_wrapper_corrects_only_frozen_malformed_program(tmp_path: Path) -> None:
    manifest = tmp_path / "manifest.txt"
    manifest.write_text("run_id=x\noutput_prefix=gs://expected/path\n", encoding="utf-8")
    result = subprocess.run(
        [
            str(WRAPPER),
            "-F=",
            r'$1==\"output_prefix\" {print $2}',
            str(manifest),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    assert result.stdout == "gs://expected/path\n"


def test_wrapper_passes_other_programs_through(tmp_path: Path) -> None:
    value = tmp_path / "value.txt"
    value.write_text("a=b\n", encoding="utf-8")
    result = subprocess.run(
        [str(WRAPPER), "-F=", '$1=="a" {print $2}', str(value)],
        check=True,
        capture_output=True,
        text=True,
    )
    assert result.stdout == "b\n"


def test_repair_preserves_frozen_validator_and_canary_identity() -> None:
    validator = ROOT / "scripts/cloud_wait_atlas_repair5_canary.sh"
    resume = (
        ROOT
        / "scripts/resume_atlas_repair5_after_canary_validator_quoting.sh"
    ).read_text(encoding="utf-8")
    protocol = (
        ROOT
        / "reports/2026-08-17-atlas-repair5-canary-validator-quoting-repair.md"
    ).read_text(encoding="utf-8")

    assert sha256(validator.read_bytes()).hexdigest() == (
        "e1c82612f231976563f0df12ffbe9f5e2db1aebfae636f61b723ad8699ae1411"
    )
    assert "atlas-md-s2023-w1-r5-45nvf" in resume
    assert "canary_rerun=false" in resume
    assert 'PATH="$WRAPPER_DIR:$PATH" bash "$VALIDATOR"' in resume
    assert "released_after_canary=53" in resume
    assert "object_content_inspected=false" in resume
    assert "effect_fields_inspected=false" in resume
    assert "Do not rerun the canary" in protocol
    assert "Every other argv vector" in protocol


def test_historical_v3_binding_was_frozen_before_results() -> None:
    amendment = (
        ROOT
        / "reports/2026-08-17-atlas-historical-score-canary-validator-repair-binding-amendment.md"
    )
    assert sha256(amendment.read_bytes()).hexdigest() == (
        "f986238a0919879944d4bddbb76855676fd5b96b5e20064f9797476cc20e5477"
    )
    text = amendment.read_text(encoding="utf-8")
    assert "before the canary shard body" in text
    assert "canary_rerun=false" in text
    assert "invalidates the v3 source lock" in text
