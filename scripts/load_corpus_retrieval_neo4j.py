#!/usr/bin/env python3
"""Validate, dry-run, or load accepted corpus-retrieval evidence into Neo4j."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys
from typing import Any

from nfl_dfs.research.corpus_neo4j_extensions import (
    append_parametric_batch,
    append_retrieval_analytics,
)
from nfl_dfs.research.corpus_retrieval_neo4j import (
    CorpusRetrievalNeo4jError,
    LOAD_RESULT_SCHEMA,
    SCHEMA_STATEMENTS,
    apply_load_plan,
    build_load_plan,
    canonical_json_bytes,
    canonical_sha256,
    load_statements,
    parse_canonical_json_bytes,
    require_execute_gate,
)


URI_ENV = "CORPUS_RETRIEVAL_NEO4J_URI"
DATABASE_ENV = "CORPUS_RETRIEVAL_NEO4J_DATABASE"
USERNAME_ENV = "CORPUS_RETRIEVAL_NEO4J_USERNAME"
PASSWORD_ENV = "CORPUS_RETRIEVAL_NEO4J_PASSWORD"
DEDICATED_ENV = "CORPUS_RETRIEVAL_NEO4J_DEDICATED"


def _add_inputs(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--terminal-receipt", type=Path, required=True)
    parser.add_argument("--terminal-receipt-identity", type=Path, required=True)
    parser.add_argument("--batch-completion", type=Path, required=True)
    parser.add_argument("--task-result", type=Path, required=True)
    parser.add_argument("--graph-projection", type=Path, required=True)
    parser.add_argument(
        "--json-sidecar",
        action="append",
        default=[],
        metavar="ROLE[:STRATEGY]=PATH",
        help=(
            "optional compact retrieval JSON sidecar; NPZ/world bodies are "
            "intentionally unsupported"
        ),
    )
    parser.add_argument("--parametric-batch-completion", type=Path)
    parser.add_argument("--parametric-batch-completion-identity", type=Path)
    parser.add_argument("--parametric-task-result", type=Path)
    parser.add_argument("--parametric-task-result-identity", type=Path)
    parser.add_argument("--parametric-terminal-receipt", type=Path)
    parser.add_argument("--parametric-terminal-receipt-identity", type=Path)
    parser.add_argument("--parametric-independent-verification", type=Path)
    parser.add_argument("--parametric-independent-verification-identity", type=Path)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    validate = sub.add_parser(
        "validate", help="validate an accepted evidence chain without Neo4j"
    )
    _add_inputs(validate)
    dry_run = sub.add_parser(
        "dry-run", help="validate and describe parameterized writes without Neo4j"
    )
    _add_inputs(dry_run)
    execute = sub.add_parser(
        "execute", help="load one accepted chain into a dedicated Neo4j database"
    )
    _add_inputs(execute)
    execute.add_argument(
        "--execute",
        action="store_true",
        help="literal mutation acknowledgement (also requires the environment gate)",
    )
    execute.add_argument(
        "--receipt-output",
        type=Path,
        required=True,
        help=(
            "new local path for the canonical load-result receipt; creation "
            "is exclusive and an existing path is never overwritten"
        ),
    )
    return parser


def _load_identity(path: Path, *, label: str = "terminal receipt identity") -> dict[str, object]:
    value = parse_canonical_json_bytes(
        path.read_bytes(), label=label
    )
    if not isinstance(value, dict):
        raise CorpusRetrievalNeo4jError(
            f"{label} must be an object"
        )
    return value


def _build(args: argparse.Namespace):
    plan = build_load_plan(
        terminal_receipt_raw=args.terminal_receipt.read_bytes(),
        terminal_receipt_identity=_load_identity(args.terminal_receipt_identity),
        batch_completion_raw=args.batch_completion.read_bytes(),
        task_result_raw=args.task_result.read_bytes(),
        graph_projection_raw=args.graph_projection.read_bytes(),
    )
    sidecars: dict[tuple[str, str], bytes] = {}
    for spec in args.json_sidecar:
        key_text, marker, path_text = spec.partition("=")
        if not marker or not key_text or not path_text:
            raise CorpusRetrievalNeo4jError(
                "--json-sidecar must be ROLE[:STRATEGY]=PATH"
            )
        role, separator, strategy_id = key_text.partition(":")
        key = (role, strategy_id if separator else "")
        if key in sidecars:
            raise CorpusRetrievalNeo4jError("--json-sidecar keys repeat")
        sidecars[key] = Path(path_text).read_bytes()
    if sidecars:
        plan = append_retrieval_analytics(
            plan,
            task_result_raw=args.task_result.read_bytes(),
            json_sidecar_bodies=sidecars,
        )

    parametric_names = (
        "parametric_batch_completion",
        "parametric_batch_completion_identity",
        "parametric_task_result",
        "parametric_task_result_identity",
        "parametric_terminal_receipt",
        "parametric_terminal_receipt_identity",
        "parametric_independent_verification",
        "parametric_independent_verification_identity",
    )
    supplied = [name for name in parametric_names if getattr(args, name) is not None]
    if supplied and len(supplied) != len(parametric_names):
        missing = [name for name in parametric_names if getattr(args, name) is None]
        raise CorpusRetrievalNeo4jError(
            "parametric extension inputs must be all-or-none; missing "
            + ", ".join(missing)
        )
    if supplied:
        plan = append_parametric_batch(
            plan,
            batch_completion_raw=args.parametric_batch_completion.read_bytes(),
            batch_completion_identity=_load_identity(
                args.parametric_batch_completion_identity,
                label="parametric completion identity",
            ),
            task_result_raw=args.parametric_task_result.read_bytes(),
            task_result_identity=_load_identity(
                args.parametric_task_result_identity,
                label="parametric task-result identity",
            ),
            terminal_receipt_raw=args.parametric_terminal_receipt.read_bytes(),
            terminal_receipt_identity=_load_identity(
                args.parametric_terminal_receipt_identity,
                label="parametric terminal identity",
            ),
            independent_verification_raw=(
                args.parametric_independent_verification.read_bytes()
            ),
            independent_verification_identity=_load_identity(
                args.parametric_independent_verification_identity,
                label="parametric verification identity",
            ),
        )
    return plan


def _dry_run(plan: Any) -> dict[str, object]:
    statements = load_statements(plan)
    return {
        **plan.summary(),
        "mode": "dry-run",
        "schema_statements": [
            {
                "ordinal": index,
                "sha256": canonical_sha256(statement),
            }
            for index, statement in enumerate(SCHEMA_STATEMENTS)
        ],
        "load_statements": [
            {
                "name": statement.name,
                "parameter_names": ["rows"],
                "query_sha256": canonical_sha256(statement.query),
                "row_count": len(statement.rows),
            }
            for statement in statements
        ],
        "workstream_namespaces": sorted({
            str(row["workstream_namespace"]) for row in plan.nodes
        }),
        "node_kind_counts": {
            kind: sum(row["kind"] == kind for row in plan.nodes)
            for kind in sorted({str(row["kind"]) for row in plan.nodes})
        },
        "neo4j_contacted": False,
    }


def _write_load_result_create_exclusive(
    path: Path, receipt: dict[str, object],
) -> None:
    """Persist one canonical receipt without ever replacing an existing path."""
    if receipt.get("schema_version") != LOAD_RESULT_SCHEMA:
        raise CorpusRetrievalNeo4jError("load-result receipt schema differs")
    retained_sha = receipt.get("load_result_sha256")
    body = {
        key: value for key, value in receipt.items()
        if key != "load_result_sha256"
    }
    if (
        not isinstance(retained_sha, str)
        or retained_sha != canonical_sha256(body)
    ):
        raise CorpusRetrievalNeo4jError("load-result receipt self-hash differs")
    raw = canonical_json_bytes(receipt)
    try:
        with path.open("xb") as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
    except FileExistsError as exc:
        raise CorpusRetrievalNeo4jError(
            "load-result receipt path already exists; it was not overwritten; "
            "the graph merge is idempotent, so revalidate before retrying"
        ) from exc


def _execute(plan: Any, *, environ: dict[str, str]) -> dict[str, object]:
    uri = environ.get(URI_ENV, "")
    database = environ.get(DATABASE_ENV, "")
    username = environ.get(USERNAME_ENV, "")
    password = environ.get(PASSWORD_ENV, "")
    dedicated = environ.get(DEDICATED_ENV, "")
    missing = [
        name
        for name, value in (
            (URI_ENV, uri),
            (DATABASE_ENV, database),
            (USERNAME_ENV, username),
            (PASSWORD_ENV, password),
            (DEDICATED_ENV, dedicated if dedicated == "1" else ""),
        )
        if not value
    ]
    if missing:
        raise CorpusRetrievalNeo4jError(
            "dedicated Neo4j connection configuration is incomplete: "
            + ", ".join(missing)
        )
    try:
        from neo4j import GraphDatabase
    except ImportError as exc:  # pragma: no cover - environment dependent
        raise CorpusRetrievalNeo4jError(
            "live execution requires the optional neo4j Python driver"
        ) from exc

    driver = GraphDatabase.driver(uri, auth=(username, password))
    try:
        with driver.session(database=database) as session:
            for statement in SCHEMA_STATEMENTS:
                session.run(statement).consume()

            def write(transaction: Any) -> dict[str, object]:
                def run_statement(
                    query: str, parameters: dict[str, object]
                ) -> dict[str, object]:
                    records = list(transaction.run(query, parameters))
                    if len(records) != 1:
                        raise CorpusRetrievalNeo4jError(
                            "Neo4j merge returned an unexpected record count"
                        )
                    return dict(records[0])

                return apply_load_plan(
                    plan,
                    run_statement=run_statement,
                    database=database,
                )

            result = session.execute_write(write)
    finally:
        driver.close()
    return result


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        plan = _build(args)
        if args.command == "validate":
            result = {**plan.summary(), "mode": "validate", "neo4j_contacted": False}
        elif args.command == "dry-run":
            result = _dry_run(plan)
        elif args.command == "execute":
            require_execute_gate(execute=args.execute, environ=os.environ)
            if os.path.lexists(args.receipt_output):
                raise CorpusRetrievalNeo4jError(
                    "load-result receipt path already exists; it will not be "
                    "overwritten"
                )
            if not args.receipt_output.parent.is_dir():
                raise CorpusRetrievalNeo4jError(
                    "load-result receipt parent directory does not exist"
                )
            result = _execute(plan, environ=dict(os.environ))
            _write_load_result_create_exclusive(args.receipt_output, result)
        else:  # pragma: no cover - argparse owns this domain
            raise AssertionError(args.command)
        sys.stdout.buffer.write(canonical_json_bytes(result) + b"\n")
        return 0
    except (CorpusRetrievalNeo4jError, OSError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
