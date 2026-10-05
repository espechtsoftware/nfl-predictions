#!/usr/bin/env python3
"""Fail-closed check: every call our money-path scripts make into the PINNED lab clone matches that clone's signatures.

Why (2026-10-05): union_reselect's game cap called optimize(set_constraints=...); its unit test mocked optimize with the
same keyword and passed, while the pinned lab (32cdb61) had no such parameter (it has member_bounds). A mock cannot
catch an API mismatch. This reads BOTH sources with `ast` (the lab is never imported):
  * our side: every call to the listed lab functions, its explicit keywords, the string keys of dicts expanded with
    `**` (including names bound to dict literals), and its count of positional arguments;
  * the clone's side: each function's parameter names, whether it takes **kwargs, and its positional capacity.
A keyword the pinned function does not accept, or more positional arguments than it takes, is a FAIL.

    python scripts/check_lab_api.py --clone "$CLONE"        # the arm preflight (run_week_build.sh) runs this
Exit 0 = every call matches; 2 = a mismatch or a missing clone (named). Tests: tests/test_check_lab_api.py.
"""
from __future__ import annotations

import argparse
import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
# money-path script -> the lab functions it calls (by the name it imports them under)
TOOLS = {
    "union_reselect.py": ("optimize", "select_top_mean", "tail_probability", "validate_roster", "dk_csv"),
    "apply_swaps.py": ("validate_roster",),
    "sat_late_swap_live.py": ("late_world_quantiles", "swap_entry"),
    "vet_replace_v4.py": ("validate_roster",),
}


def lab_params(src: Path, names: set[str]) -> dict[str, tuple[set, bool, int]]:
    """name -> (parameter names, has **kwargs, positional capacity) for module-level defs in the clone's nfl2 package."""
    out = {}
    for f in sorted((src / "nfl2").rglob("*.py")):
        for node in ast.parse(f.read_text(), filename=str(f)).body:
            if isinstance(node, ast.FunctionDef) and node.name in names:
                a = node.args
                cap = 10 ** 6 if a.vararg is not None else len(a.posonlyargs) + len(a.args)
                out[node.name] = ({x.arg for x in a.posonlyargs + a.args + a.kwonlyargs}, a.kwarg is not None, cap)
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


def tool_calls(path: Path, funcs: tuple[str, ...]) -> list[tuple[str, int, set[str], int]]:
    """(function, line, keywords incl. ** dict keys, positional count) for every call to `funcs` in `path`."""
    tree = ast.parse(path.read_text(), filename=str(path))
    assigned: dict[str, list[ast.Dict]] = {}
    for n in ast.walk(tree):
        if isinstance(n, ast.Assign) and isinstance(n.value, ast.Dict):
            for t in n.targets:
                if isinstance(t, ast.Name):
                    assigned.setdefault(t.id, []).append(n.value)
    calls = []
    for n in ast.walk(tree):
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id in funcs:
            kws = {k.arg for k in n.keywords if k.arg}
            for k in n.keywords:
                if k.arg is None:
                    kws |= _dict_keys(k.value, assigned)
            calls.append((n.func.id, n.lineno, kws, sum(1 for x in n.args if not isinstance(x, ast.Starred))))
    return calls


def check(src: Path, scripts_dir: Path = ROOT / "scripts", tools: dict = TOOLS) -> list[str]:
    """All problems, named; empty = every call matches the pinned clone."""
    if not (src / "nfl2").is_dir():
        return [f"pinned lab clone source not found at {src} (expected {src}/nfl2)"]
    problems = []
    for tool, funcs in tools.items():
        params = lab_params(src, set(funcs))
        calls = tool_calls(scripts_dir / tool, funcs)
        seen = {c[0] for c in calls}
        for f in funcs:
            if f not in seen:
                problems.append(f"{tool}: expected a call to {f}, found none (update TOOLS)")
            if f not in params:
                problems.append(f"{tool}: {f} is not defined in the pinned clone {src}")
        for name, line, kws, npos in calls:
            if name not in params:
                continue
            names, has_kwargs, cap = params[name]
            if not has_kwargs and kws - names:
                problems.append(f"{tool} line {line}: {name}({sorted(kws - names)}) not in the pinned signature")
            if npos > cap:
                problems.append(f"{tool} line {line}: {name} given {npos} positional arguments; the pinned signature takes {cap}")
    return problems


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--clone", type=Path, required=True, help="the armed lab clone (its src/ holds nfl2)")
    a = ap.parse_args(argv)
    problems = check(a.clone / "src")
    if problems:
        print("LAB API CHECK FAILED -- a money-path call does not match the pinned lab clone:", file=sys.stderr)
        for p in problems:
            print(f"  {p}", file=sys.stderr)
        return 2
    n = sum(len(tool_calls(ROOT / "scripts" / t, f)) for t, f in TOOLS.items())
    print(f"lab API check: {n} calls in {len(TOOLS)} money-path scripts match the pinned clone {a.clone}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
