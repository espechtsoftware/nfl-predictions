#!/usr/bin/env python3
"""Keep the Milly Aura Free instance awake: one trivial read, no writes.

    python scripts/neo4j_keepalive.py

Aura Free pauses an instance after a few days without queries. Run this once
a day (see README, "Dashboard v2" -> Neo4j keep-alive). Reads the
MILLY_NEO4J_* environment variables. Exit 0 on success, 1 when the instance
does not answer (paused? resume it in the Aura console), 2 when not configured.
"""
from __future__ import annotations

import sys

from nfl_dfs.dashboard import milly_graph as mg


def main(env=None, connect=mg.connect) -> int:
    cfg = mg.GraphConfig.from_env(env)
    if cfg is None:
        print(f"not configured: set {mg.URI_ENV}, {mg.USERNAME_ENV}, {mg.PASSWORD_ENV}", file=sys.stderr)
        return 2
    try:
        driver = connect(cfg)
        try:
            records = driver.execute_query("RETURN 1 AS ok", database_=cfg.database,
                                           routing_="r")[0]
        finally:
            driver.close()
        ok = bool(records) and records[0]["ok"] == 1
    except Exception as exc:  # noqa: BLE001 -- any failure is reported the same way
        print(f"FAIL: {cfg.uri} did not answer ({type(exc).__name__}: {exc}). "
              f"Instance paused? Resume it in the Aura console.", file=sys.stderr)
        return 1
    if not ok:
        print("FAIL: unexpected answer to RETURN 1. Instance paused? Resume it in the Aura console.",
              file=sys.stderr)
        return 1
    print(f"ok: {cfg.uri} ({cfg.database}) answered")
    return 0


if __name__ == "__main__":
    sys.exit(main())
