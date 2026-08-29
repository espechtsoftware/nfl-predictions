#!/usr/bin/env python3
"""Measured isolated pytest launcher for the fixed-G0 recovery review suite."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import sys


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = REPOSITORY_ROOT / "src"
# ``.venv/bin/python`` may be a symlink to the base interpreter.  ``sys.prefix``
# is the interpreter's authenticated virtual-environment boundary; resolving
# ``sys.executable`` would incorrectly move that boundary to the base install.
VENV_ROOT = Path(sys.prefix).resolve()


def _require_trusted_pytest_origin(module_file: str | None) -> Path:
    if module_file is None:
        raise RuntimeError("pytest has no import origin")
    origin = Path(module_file).resolve()
    if (
        VENV_ROOT not in origin.parents
        or "site-packages" not in origin.parts
        or origin.name != "__init__.py"
        or origin.parent.name != "pytest"
    ):
        raise RuntimeError("pytest import escaped the fixed virtual environment")
    return origin


# Import pytest while isolated mode still exposes only stdlib and venv paths.
import pytest as _pytest  # noqa: E402

_require_trusted_pytest_origin(_pytest.__file__)

# Only after pytest is authenticated expose the measured source closure.  The
# repository root is deliberately absent while nfl_dfs is imported.
for retained in (str(SOURCE_ROOT), str(REPOSITORY_ROOT)):
    while retained in sys.path:
        sys.path.remove(retained)
sys.path.insert(0, str(SOURCE_ROOT))


def _require_exact_project_origin(module_file: str | None, expected: Path) -> Path:
    if module_file is None or Path(module_file).resolve() != expected.resolve():
        raise RuntimeError("project import escaped the measured source closure")
    return expected.resolve()


import nfl_dfs as _nfl_dfs  # noqa: E402
from nfl_dfs import research as _research  # noqa: E402
from nfl_dfs.research import corpus_r6_fixed_g0_catalog_recovery_v1 as _recovery  # noqa: E402
from nfl_dfs.research import corpus_r6_player_catalog_fixed_g0_adapter_v1 as _adapter  # noqa: E402
from nfl_dfs.research import corpus_r6_player_catalog_fixed_g0_projection_successor_v1 as _successor  # noqa: E402

_require_exact_project_origin(_nfl_dfs.__file__, SOURCE_ROOT / "nfl_dfs/__init__.py")
_require_exact_project_origin(_research.__file__, SOURCE_ROOT / "nfl_dfs/research/__init__.py")
_require_exact_project_origin(_recovery.__file__, SOURCE_ROOT / "nfl_dfs/research/corpus_r6_fixed_g0_catalog_recovery_v1.py")
_require_exact_project_origin(_adapter.__file__, SOURCE_ROOT / "nfl_dfs/research/corpus_r6_player_catalog_fixed_g0_adapter_v1.py")
_require_exact_project_origin(_successor.__file__, SOURCE_ROOT / "nfl_dfs/research/corpus_r6_player_catalog_fixed_g0_projection_successor_v1.py")


def _load_exact_module(name: str, path: Path, *, package: bool = False) -> object:
    kwargs = {"submodule_search_locations": [str(path.parent)]} if package else {}
    spec = importlib.util.spec_from_file_location(name, path, **kwargs)
    if spec is None or spec.loader is None or Path(str(spec.origin)).resolve() != path.resolve():
        raise RuntimeError("exact project module spec differs")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    _require_exact_project_origin(getattr(module, "__file__", None), path)
    return module


# Remove source before loading operator authority.  Package and runner are
# loaded from exact repository-root specs, so a source-side ``scripts.py`` or
# forged package is never imported or executed.
while str(SOURCE_ROOT) in sys.path:
    sys.path.remove(str(SOURCE_ROOT))
if __name__ == "__main__":
    for module_name in tuple(sys.modules):
        if module_name == "scripts" or module_name.startswith("scripts."):
            del sys.modules[module_name]
    _scripts = _load_exact_module(
        "scripts", REPOSITORY_ROOT / "scripts/__init__.py", package=True
    )
    _runner = _load_exact_module(
        "scripts.run_corpus_r6_fixed_g0_catalog_recovery_v1",
        REPOSITORY_ROOT / "scripts/run_corpus_r6_fixed_g0_catalog_recovery_v1.py",
    )
    wrapper_name = "scripts.run_corpus_r6_fixed_g0_catalog_recovery_focused_v1"
    wrapper_path = REPOSITORY_ROOT / "scripts/run_corpus_r6_fixed_g0_catalog_recovery_focused_v1.py"
    wrapper_spec = importlib.util.spec_from_file_location(wrapper_name, wrapper_path)
    if wrapper_spec is None or Path(str(wrapper_spec.origin)).resolve() != wrapper_path.resolve():
        raise RuntimeError("focused wrapper exact module spec differs")
    _require_exact_project_origin(__file__, wrapper_path)
    _focused = sys.modules[__name__]
    sys.modules[wrapper_name] = _focused
    setattr(_scripts, "run_corpus_r6_fixed_g0_catalog_recovery_v1", _runner)
    setattr(_scripts, "run_corpus_r6_fixed_g0_catalog_recovery_focused_v1", _focused)
else:
    import scripts as _scripts  # noqa: E402
    from scripts import run_corpus_r6_fixed_g0_catalog_recovery_v1 as _runner  # noqa: E402
    _focused = sys.modules[__name__]
    _require_exact_project_origin(_scripts.__file__, REPOSITORY_ROOT / "scripts/__init__.py")
    _require_exact_project_origin(
        _runner.__file__, REPOSITORY_ROOT / "scripts/run_corpus_r6_fixed_g0_catalog_recovery_v1.py"
    )

# Final collection order is measured source first, then repository root.  The
# exact scripts modules above are already cached and cannot be shadowed.
for retained in (str(SOURCE_ROOT), str(REPOSITORY_ROOT)):
    while retained in sys.path:
        sys.path.remove(retained)
sys.path[0:0] = [str(SOURCE_ROOT), str(REPOSITORY_ROOT)]



if __name__ == "__main__":
    raise SystemExit(_pytest.main())
