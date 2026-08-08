"""Machine-readable shipping-defaults manifest (plan §3.5, 2026-08-05).

WHY: adopted levers live as scattered `os.environ.get(KEY, default)`
literals plus a handful of module constants, and review packages have
already gone stale against them (OWN_MODEL flipped fade -> "" on
2026-08-05; PUNT_BOOM was deleted in the replay/live paths but the
legacy app MILP pool still ships 2). This module reads the LIVE code —
imported constants where they exist, the env-read default literal
parsed from module source where they don't — and emits a stable JSON
manifest plus its sha256, to be stamped into every replay and live
build (candidate_run.manifest_hash). Cross-file disagreements are not
papered over: they land in the manifest's `discrepancies` list so the
hash changes when a path drifts.

Offline by design: source files are located with importlib.find_spec
(no import of the heavy app module) and only cheap, dependency-light
modules are imported directly.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import logging
import re
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)

MANIFEST_SCHEMA_VERSION = 1


def _module_source(dotted: str) -> str:
    spec = importlib.util.find_spec(dotted)
    if spec is None or not spec.origin:
        raise ImportError(f"cannot locate module {dotted}")
    return Path(spec.origin).read_text()


def _env_defaults(source: str, key: str) -> list[str]:
    """Every `environ.get("KEY", "<literal>")` default in `source`."""
    pat = re.compile(
        r'environ\.get\(\s*"' + re.escape(key) + r'"\s*,\s*"([^"]*)"')
    return pat.findall(source)


def _env_default(source: str, key: str, module: str) -> str:
    """The single env-read default literal for `key`; raises if the
    read disappeared or the same file disagrees with itself."""
    found = _env_defaults(source, key)
    if not found:
        raise LookupError(f"{key}: no environ.get default in {module}")
    if len(set(found)) > 1:
        raise LookupError(
            f"{key}: conflicting defaults {sorted(set(found))} in {module}")
    return found[0]


def collect_defaults() -> tuple[dict[str, Any], list[dict[str, str]]]:
    """(defaults, discrepancies) measured from the live code.

    Canonical sources are the validated construction paths (replay +
    live sim-mode + optimizer + component models); other files reading
    the same key with a different literal are recorded as
    discrepancies, never silently preferred.
    """
    # Cheap, offline-safe imports — the real constants where they exist.
    from ..backtest.engine import resolve_generation_budget
    from ..inference import live_lineups
    from ..models import blend
    from ..models.components import effective_ensemble_size
    from ..optimizer import lineup

    # env={} so the manifest records CODE defaults, never the env of the
    # process that happens to run it
    _gen_budget = resolve_generation_budget(env={})

    replay_src = _module_source("nfl_dfs.backtest.replay")
    lineup_src = _module_source("nfl_dfs.optimizer.lineup")
    simulate_src = _module_source("nfl_dfs.models.simulate")
    live_src = _module_source("nfl_dfs.inference.live_lineups")
    app_src = _module_source("nfl_dfs.app.main")

    defaults: dict[str, Any] = {
        # "" = naive-fade (Addenda 77/80/84); "fade" restores the booster.
        "OWN_MODEL": _env_default(replay_src, "OWN_MODEL", "replay"),
        # Punt MANDATE deleted (Addendum 77); p90 punt valuation stays.
        "PUNT_MIN": int(lineup.PUNT_MIN),
        # Archetype boost deleted in replay+live (Addendum 77/79b).
        "PUNT_BOOM": float(
            _env_default(replay_src, "PUNT_BOOM", "replay") or 0),
        "MIN_LINEUP_SALARY": int(_env_default(
            lineup_src, "MIN_LINEUP_SALARY", "optimizer.lineup")),
        # Log-sum-exp selection alpha; 0 = binary coverage (off).
        "SELECT_LSE": float(
            _env_default(lineup_src, "SELECT_LSE", "optimizer.lineup") or 0),
        "TD_LEDGER": _env_default(
            simulate_src, "TD_LEDGER", "models.simulate") not in ("", "0"),
        # Default-on since Addendum 50; falls back to EW empirical
        # marginals with a UI warning when the cache is missing.
        "TABPFN_MARGINALS": _env_default(
            replay_src, "TABPFN_MARGINALS", "replay") not in ("", "0"),
        # ENS3 adopted Addendum 56 (+12 tails vs same-build control).
        # Resolve behaviorally from an empty environment, not from the
        # process or a fragile source-text regex.
        "MODEL_ENSEMBLE": effective_ensemble_size({}),
        "GAME_SIM_MODE": _env_default(
            simulate_src, "GAME_SIM_MODE", "models.simulate"),
        "LIVE_SIMS": int(live_lineups.LIVE_SIMS_DEFAULT),
        # ADOPTED generation budget (2026-08-06). Recorded from the CODE
        # resolver, not from deployment env: CE was previously live only
        # via Cloud Run env vars, so the manifest reported "no drift"
        # while the adopted lever sat outside the code entirely.
        "N_CE": int(_gen_budget[0]),
        "N_EPISTEMIC": int(_gen_budget[1]),
        "N_BOOM": int(_gen_budget[2]),
        "GEN_TOTAL_BUDGET": int(_gen_budget[0] + _gen_budget[1]
                                + _gen_budget[2]),
        "BLEND_WEIGHT": float(blend.BLEND_W),
    }

    # Cross-file drift detection: any other shipping file reading the
    # same key with a different literal is a reconciliation item.
    canonical_literal = {
        "PUNT_BOOM": _env_default(replay_src, "PUNT_BOOM", "replay"),
        "TABPFN_MARGINALS": _env_default(
            replay_src, "TABPFN_MARGINALS", "replay"),
        "LIVE_SIMS": str(live_lineups.LIVE_SIMS_DEFAULT),
    }
    other_files = {
        "app/main.py": app_src,
        "inference/live_lineups.py": live_src,
        "inference/run_projections.py": _module_source(
            "nfl_dfs.inference.run_projections"),
    }
    discrepancies: list[dict[str, str]] = []
    for key, canon in canonical_literal.items():
        for path, src in other_files.items():
            for lit in _env_defaults(src, key):
                if _norm(lit) != _norm(canon):
                    discrepancies.append({
                        "key": key, "path": path,
                        "default": lit, "canonical": canon,
                    })
    return defaults, discrepancies


def _norm(literal: str) -> str:
    """Compare "30000" with "30_000"-style spellings numerically."""
    try:
        return repr(float(literal.replace("_", "") or 0))
    except ValueError:
        return literal


def manifest() -> dict[str, Any]:
    defaults, discrepancies = collect_defaults()
    return {
        "schema_version": MANIFEST_SCHEMA_VERSION,
        "defaults": defaults,
        "discrepancies": sorted(
            discrepancies, key=lambda d: (d["key"], d["path"])),
    }


def manifest_json(m: dict[str, Any] | None = None) -> str:
    """Stable serialization: sorted keys, no whitespace — byte-identical
    for identical code, so the hash is a real build fingerprint."""
    return json.dumps(m if m is not None else manifest(),
                      sort_keys=True, separators=(",", ":"))


def manifest_hash(m: dict[str, Any] | None = None) -> str:
    return hashlib.sha256(manifest_json(m).encode()).hexdigest()
