"""Dashboard v2 (2026-10-03): a read-only, server-rendered replacement for the
old app's pages. Pages read BigQuery through pure functions in ``data`` that
take a ``query(sql) -> DataFrame`` callable, so the whole package is testable
offline. ``nfl-dfs dashboard`` serves it; the old ``nfl-dfs serve`` app is
untouched."""
