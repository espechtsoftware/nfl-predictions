"""The declared provenance root must own the code a frozen-chain run executes.

``--repository-root`` fixes the tree whose commit is stamped on a run.  It has
no influence on module resolution, so an editable install rooted in a sibling
checkout serves its own files under any declared root.  Where the divergence
is hash-gated a downstream gate refuses; where it is not, the run publishes a
provenance-mislabelled artifact and nothing complains.
"""

from __future__ import annotations

from pathlib import Path
import re

import pytest

from nfl_dfs.research import repository_root_code_binding_v1 as binding


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"


def test_binds_module_living_under_the_declared_root() -> None:
    bound = binding.bind_executing_code_to_repository_root_v1(ROOT, {"self": binding})
    assert bound["self"].endswith("repository_root_code_binding_v1.py")
    # The helper always audits its own origin, not only what it is handed.
    assert "repository root code binding" in bound


def test_refuses_module_outside_the_declared_root(tmp_path: Path) -> None:
    with pytest.raises(
        binding.RepositoryRootCodeBindingV1Error,
        match=r"is loaded from outside the declared repository root",
    ):
        binding.bind_executing_code_to_repository_root_v1(
            tmp_path.resolve(), {"self": binding}
        )


def test_refuses_a_module_with_no_file_origin() -> None:
    with pytest.raises(
        binding.RepositoryRootCodeBindingV1Error,
        match=r"has no resolvable file origin",
    ):
        binding.bind_executing_code_to_repository_root_v1(ROOT, {"ghost": ""})


def test_refuses_a_non_canonical_root() -> None:
    with pytest.raises(
        binding.RepositoryRootCodeBindingV1Error,
        match=r"repository root must be one canonical absolute directory",
    ):
        binding.bind_executing_code_to_repository_root_v1(
            Path("relative/root"), {"self": binding}
        )


def test_refuses_an_empty_module_set() -> None:
    with pytest.raises(
        binding.RepositoryRootCodeBindingV1Error,
        match=r"code binding requires at least one module",
    ):
        binding.bind_executing_code_to_repository_root_v1(ROOT, {})


def _scripts_declaring_repository_root() -> list[Path]:
    found = [
        path
        for path in sorted(SCRIPTS.glob("*.py"))
        if '"--repository-root"' in path.read_text(encoding="utf-8")
    ]
    assert found, "no --repository-root scripts discovered"
    return found


@pytest.mark.parametrize(
    "path", _scripts_declaring_repository_root(), ids=lambda p: p.name
)
def test_every_repository_root_script_binds_its_executing_code(path: Path) -> None:
    """This is the test that stops the class from coming back.

    A new driver that takes ``--repository-root`` without binding its code
    fails here rather than at some later provenance audit that may never run.
    """
    text = path.read_text(encoding="utf-8")
    # Match a CALL, never a definition: a script that defines the guard and
    # never invokes it is exactly the failure this test exists to catch.
    bound = (
        re.search(r"^\s+_bind_executing_code\(", text, re.M) is not None
        or re.search(
            r"^\s+_bind_executing_code_to_repository_root\(", text, re.M
        ) is not None
        or re.search(r"^\s+\w*\s*=?\s*_verify_module_origins\(", text, re.M)
        is not None
    )
    assert bound, (
        f"{path.name} accepts --repository-root but never binds the executing "
        "code to it; a run there can stamp the declared commit on another "
        "tree's output"
    )


@pytest.mark.parametrize(
    "path", _scripts_declaring_repository_root(), ids=lambda p: p.name
)
def test_binding_is_reached_before_the_root_is_used(path: Path) -> None:
    """Binding after the work has begun would not protect anything."""
    text = path.read_text(encoding="utf-8")
    match = re.search(r"^\s+_bind_executing_code\(getattr\(args", text, re.M)
    if match is None:
        pytest.skip("uses the in-module origin verifier, checked separately")
    call = match.start()
    parse = max(
        (m.end() for m in re.finditer(r"parse_args\(", text)), default=-1
    )
    assert parse != -1, f"{path.name} has no parse_args call"
    assert call > parse, f"{path.name} binds before its arguments are parsed"
    remainder = text[call:]
    assert "args.repository_root" not in text[:call], (
        f"{path.name} uses the declared root before binding the code to it"
    )
    assert remainder
