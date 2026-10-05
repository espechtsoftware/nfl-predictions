"""Every keyword union_reselect.py passes into the PINNED lab clone must exist in that clone's function.

Why (2026-10-05): the game cap called optimize(set_constraints=...); the unit test mocked optimize with that same
keyword, so it passed while the pinned lab (32cdb61) had no such parameter (it has member_bounds). Mocks cannot catch
an API mismatch; this reads BOTH sources (no import of the lab) and compares. It skips, printing why, when the pinned
clone is not on this machine (CI).
"""
from __future__ import annotations

import ast
import os
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "scripts" / "union_reselect.py"
LAB_FUNCS = ("optimize", "select_top_mean", "tail_probability", "validate_roster", "dk_csv")


def _clone_src() -> Path | None:
    for c in (os.environ.get("NFL2_PINNED_SRC"), os.environ.get("CLONE") and os.path.join(os.environ["CLONE"], "src"),
              os.environ.get("NFL2_LIVE_CLONE") and os.path.join(os.environ["NFL2_LIVE_CLONE"], "src"),
              "/home/erich/projects/.nfl2-worktrees/week4-live-center/src"):
        if c and (Path(c) / "nfl2").is_dir():
            return Path(c)
    return None


def _lab_params(src: Path) -> dict[str, tuple[set, bool, int]]:
    """name -> (keyword parameter names, has **kwargs, positional capacity) from the clone's source."""
    out = {}
    for f in (src / "nfl2").rglob("*.py"):
        for node in ast.walk(ast.parse(f.read_text(), filename=str(f))):
            if isinstance(node, ast.FunctionDef) and node.name in LAB_FUNCS and node.col_offset == 0:
                a = node.args
                names = {x.arg for x in a.posonlyargs + a.args + a.kwonlyargs}
                out[node.name] = (names, a.kwarg is not None, len(a.posonlyargs) + len(a.args) if a.vararg is None else 10**6)
    return out


def _dict_keys(node: ast.AST, assigned: dict[str, list[ast.Dict]]) -> set[str]:
    keys = set()
    for n in ast.walk(node):
        if isinstance(n, ast.Dict):
            keys |= {k.value for k in n.keys if isinstance(k, ast.Constant) and isinstance(k.value, str)}
        if isinstance(n, ast.Name) and n.id in assigned:
            for d in assigned[n.id]:
                keys |= {k.value for k in d.keys if isinstance(k, ast.Constant) and isinstance(k.value, str)}
    return keys


def _tool_calls() -> list[tuple[str, int, set[str], int]]:
    tree = ast.parse(TOOL.read_text())
    assigned: dict[str, list[ast.Dict]] = {}
    for n in ast.walk(tree):
        if isinstance(n, ast.Assign) and isinstance(n.value, ast.Dict):
            for t in n.targets:
                if isinstance(t, ast.Name):
                    assigned.setdefault(t.id, []).append(n.value)
    calls = []
    for n in ast.walk(tree):
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id in LAB_FUNCS:
            kws = {k.arg for k in n.keywords if k.arg}
            for k in n.keywords:
                if k.arg is None:                                   # **expr: the string keys of the dicts it can expand
                    kws |= _dict_keys(k.value, assigned)
            calls.append((n.func.id, n.lineno, kws, len(n.args)))
    return calls


def test_union_reselect_calls_only_keywords_the_pinned_lab_accepts():
    src = _clone_src()
    if src is None:
        pytest.skip("pinned lab clone not on this machine (set NFL2_PINNED_SRC); the API check needs its source")
    params = _lab_params(src)
    calls = _tool_calls()
    assert {c[0] for c in calls} >= {"optimize", "select_top_mean", "validate_roster", "dk_csv", "tail_probability"}
    bad = []
    for name, line, kws, npos in calls:
        assert name in params, f"{name} not defined in the pinned clone {src}"
        names, has_kwargs, cap = params[name]
        if not has_kwargs and kws - names:
            bad.append(f"line {line}: {name}({sorted(kws - names)}) not in the pinned signature")
        if npos > cap:
            bad.append(f"line {line}: {name} given {npos} positional arguments, the pinned signature takes {cap}")
    assert not bad, "\n".join(bad)


def test_the_check_would_have_caught_set_constraints(tmp_path):
    """The mutation the check exists for: a keyword the pinned optimize lacks."""
    src = _clone_src()
    if src is None:
        pytest.skip("pinned lab clone not on this machine (set NFL2_PINNED_SRC)")
    names, has_kwargs, _ = _lab_params(src)["optimize"]
    assert "member_bounds" in names and "set_constraints" not in names and not has_kwargs
