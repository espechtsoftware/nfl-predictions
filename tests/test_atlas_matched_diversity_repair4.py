from __future__ import annotations

from hashlib import sha256
from pathlib import Path
import sys

import pytest

from scripts.render_atlas_matched_diversity_repair4_command import render


ROOT = Path(__file__).resolve().parents[1]


def _runner(path: Path, prefix: str) -> str:
    source = f"""
SHARDED_OUTPUT_PREFIX = {prefix!r}
def main():
    print('RUNNER_MAIN', SHARDED_OUTPUT_PREFIX)
if __name__ == '__main__':
    raise AssertionError('runner main executed before prefix repair')
"""
    path.write_text(source, encoding="utf-8")
    return sha256(path.read_bytes()).hexdigest()


def test_repair4_renderer_verifies_and_patches_only_prefix(
    tmp_path: Path, capsys: pytest.CaptureFixture[str],
) -> None:
    path = tmp_path / "runner.py"
    original = "gs://bucket/repair2"
    replacement = "gs://bucket/repair4"
    digest = _runner(path, original)

    verify = render(
        replacement, verify_only=True, runner_path=str(path),
        runner_sha256=digest, original_prefix=original,
    )
    exec(verify, {})
    assert capsys.readouterr().out.strip() == (
        f"ATLAS_REPAIR4_PREFIX_PATCH_VERIFIED {digest} {original} {replacement}"
    )

    command = render(
        replacement, runner_path=str(path), runner_sha256=digest,
        original_prefix=original,
    )
    prior = sys.argv
    try:
        sys.argv = ["-c"]
        exec(command, {})
    finally:
        sys.argv = prior
    assert capsys.readouterr().out.strip() == f"RUNNER_MAIN {replacement}"


def test_repair4_renderer_fails_closed_on_source_or_original_prefix(
    tmp_path: Path,
) -> None:
    path = tmp_path / "runner.py"
    original = "gs://bucket/repair2"
    digest = _runner(path, original)
    bad_hash = render(
        "gs://bucket/repair4", verify_only=True, runner_path=str(path),
        runner_sha256="0" * 64, original_prefix=original,
    )
    with pytest.raises(RuntimeError, match="runner source differs"):
        exec(bad_hash, {})
    bad_prefix = render(
        "gs://bucket/repair4", verify_only=True, runner_path=str(path),
        runner_sha256=digest, original_prefix="gs://bucket/not-repair2",
    )
    with pytest.raises(RuntimeError, match="original output prefix differs"):
        exec(bad_prefix, {})


def test_repair4_cloud_contract_is_smoke_gated_and_exact() -> None:
    launcher = (
        ROOT / "scripts/cloud_atlas_matched_diversity_repair4.sh"
    ).read_text(encoding="utf-8")
    finisher = (
        ROOT / "scripts/cloud_finish_atlas_matched_diversity_repair4.sh"
    ).read_text(encoding="utf-8")
    runner = ROOT / "scripts/run_atlas_matched_diversity_mvp.py"
    renderer = ROOT / "scripts/render_atlas_matched_diversity_repair4_command.py"
    protocol = ROOT / "reports/2026-08-16-atlas-mvp-output-prefix-repair4.md"

    assert sha256(runner.read_bytes()).hexdigest() == (
        "0548e26e26d7e81b20c6837adcc8925bc2317f9b7c8586fba084787581cac740"
    )
    assert sha256(renderer.read_bytes()).hexdigest() == (
        "69d0ed1187bf59176a857e0bc822f65bd9aea2ffd211ffc247312796bfaeb671"
    )
    assert sha256(protocol.read_bytes()).hexdigest() == (
        "5e84a6b93522fd959e798e90da307687179327b23c474fbda6b5303d0483063a"
    )
    assert "atlas-md-prefix-r4-smoke" in launcher
    assert launcher.index("ATLAS repair4 smoke marker differs") < launcher.index(
        "for SEASON in 2023 2024 2025"
    )
    assert "--args=-c,\"$GRID_COMMAND\",--season" in launcher
    assert "'cpu=4' 'memory=16Gi'" in launcher
    assert "--max-retries 0" in launcher
    assert "20260816-atlas-matched-diversity-mvp-v1-repair4" in finisher
    assert '["-c",command,"--season",season' in finisher
    assert '"repair_treatment":"output-prefix-transport-only"' in finisher
