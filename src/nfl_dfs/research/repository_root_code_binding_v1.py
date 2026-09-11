"""Bind a declared provenance root to the code that will actually run.

Frozen-chain drivers take ``--repository-root`` to fix the tree whose commit
is recorded as a run's provenance.  That flag has no influence on module
resolution: Python imports ``nfl_dfs`` through the interpreter, so an
editable install rooted in one checkout serves its own files no matter which
root a caller declares.  Point a driver at a worktree while running a sibling
checkout's venv and the receipt carries the worktree's commit over the other
tree's code.

Where the divergence happens to be hash-gated a downstream gate refuses and
the mislabel is merely a failed run.  Where it is not, the run succeeds and
publishes a provenance-mislabelled artifact.  This module exists to make the
declared root and the executing code one tree, before any work begins.
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
import stat
from types import ModuleType
from typing import Final

__all__ = [
    "RepositoryRootCodeBindingV1Error",
    "bind_executing_code_to_repository_root_v1",
]

_SELF_LABEL: Final = "repository root code binding"


class RepositoryRootCodeBindingV1Error(RuntimeError):
    """The declared repository root does not own the executing code."""


def _fail(message: str) -> None:
    raise RepositoryRootCodeBindingV1Error(message)


def _origin_under_root(label: str, origin: object, repository_root: Path) -> Path:
    if type(origin) is not str or not origin:
        _fail(f"{label} has no resolvable file origin")
    raw = Path(str(origin))
    try:
        mode = raw.lstat().st_mode
    except OSError as exc:
        raise RepositoryRootCodeBindingV1Error(
            f"{label} file origin is absent"
        ) from exc
    if stat.S_ISLNK(mode) or not stat.S_ISREG(mode):
        _fail(f"{label} file origin must be one regular file")
    resolved = raw.resolve()
    if repository_root not in resolved.parents:
        _fail(f"{label} is loaded from outside the declared repository root")
    return resolved


def bind_executing_code_to_repository_root_v1(
    repository_root: Path, modules: Mapping[str, ModuleType | str],
) -> dict[str, str]:
    """Refuse unless every named module resolves under ``repository_root``.

    ``modules`` maps a human label to either an imported module or a file
    path (for the calling script itself, pass its ``__file__``).  This
    module's own origin is always checked as well: a binding helper served
    from the wrong tree cannot be trusted to police the others.
    """
    root = Path(repository_root)
    if not root.is_absolute() or root.resolve() != root:
        _fail("repository root must be one canonical absolute directory")
    if not modules:
        _fail("code binding requires at least one module")

    bound: dict[str, str] = {}
    checked: dict[str, object] = dict(modules)
    checked[_SELF_LABEL] = __file__
    for label in sorted(checked):
        value = checked[label]
        origin = value if isinstance(value, str) else getattr(value, "__file__", None)
        resolved = _origin_under_root(label, origin, root)
        bound[label] = str(resolved.relative_to(root))
    return bound
