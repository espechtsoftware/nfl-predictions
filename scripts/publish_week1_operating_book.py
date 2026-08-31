#!/usr/bin/env python3
"""Publish and independently reopen the canonical 2026 Week-1 book.

This is an explicit operator command, not a scheduled job.  It accepts one
generation-pinned terminal-envelope identity and one fresh output object URI,
delegates all publication checks to the Week-1 operator, independently reads
the resulting materialization again, and only then emits the four exact
environment values consumed by the application.

The command has no outcome, grading, listing, overwrite, deployment, or
contest-entry behavior.  Publication is disabled unless both ``--apply`` and
the exact confirmation phrase are supplied.
"""

from __future__ import annotations

import argparse
from collections.abc import Callable, Mapping, Sequence
import json
import re
import sys
from typing import Final

from nfl_dfs.inference.generation_exposure import canonical_sha256
from nfl_dfs.inference.prospective_generation_shadow_evaluation import (
    normalize_object_identity_v1,
)
from nfl_dfs.inference.prospective_generation_shadow_operator import (
    GCSImmutableObjectStore,
    ImmutableObjectStore,
)
from nfl_dfs.inference.week1_operating_book_operator import (
    publish_week1_operating_book_v1,
    read_week1_operating_book_v1,
)


SCHEMA_VERSION: Final = "week1-operating-book-config-emission/v1"
CONFIRMATION_PHRASE: Final = "publish-2026-week1-canonical-book"
APP_ENVIRONMENT_KEYS: Final = (
    "WEEK1_OPERATING_BOOK_URI",
    "WEEK1_OPERATING_BOOK_GENERATION",
    "WEEK1_OPERATING_BOOK_SHA256",
    "WEEK1_OPERATING_BOOK_BYTES",
)
_SHA256 = re.compile(r"[0-9a-f]{64}\Z")


class Week1OperatingBookPublicationCliError(RuntimeError):
    """The explicit Week-1 publication command failed closed."""


def _fail(message: str) -> None:
    raise Week1OperatingBookPublicationCliError(message)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Create-once publish the canonical 2026 Week-1 operating book "
            "and emit exact app configuration after an independent reopen."
        )
    )
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--confirm", required=True)
    parser.add_argument("--terminal-envelope-uri", required=True)
    parser.add_argument("--terminal-envelope-generation", required=True)
    parser.add_argument("--terminal-envelope-sha256", required=True)
    parser.add_argument("--terminal-envelope-bytes", required=True, type=int)
    parser.add_argument("--output-uri", required=True)
    parser.add_argument("--k", required=True, type=int, choices=(80, 100))
    return parser


def _terminal_identity(arguments: argparse.Namespace) -> dict[str, object]:
    try:
        return normalize_object_identity_v1(
            {
                "uri": arguments.terminal_envelope_uri,
                "generation": arguments.terminal_envelope_generation,
                "sha256": arguments.terminal_envelope_sha256,
                "bytes": arguments.terminal_envelope_bytes,
            },
            label="Week-1 terminal-envelope identity",
        )
    except Exception as exc:
        raise Week1OperatingBookPublicationCliError(
            "terminal-envelope identity is invalid"
        ) from exc


def publish_and_emit_config_v1(
    *,
    store: ImmutableObjectStore,
    terminal_envelope_identity: Mapping[str, object],
    output_uri: str,
    k: int,
) -> dict[str, object]:
    """Publish, independently reopen, and return exact app configuration."""

    try:
        source_identity = normalize_object_identity_v1(
            terminal_envelope_identity,
            label="Week-1 terminal-envelope identity",
        )
    except Exception as exc:
        raise Week1OperatingBookPublicationCliError(
            "terminal-envelope identity is invalid"
        ) from exc
    if output_uri == source_identity["uri"]:
        _fail("output URI must differ from the terminal-envelope URI")

    try:
        publication = publish_week1_operating_book_v1(
            store=store,
            terminal_prelock_envelope_identity=source_identity,
            target_uri=output_uri,
            k=k,
        )
        output_identity = normalize_object_identity_v1(
            publication.get("materialization_identity"),
            label="published Week-1 materialization identity",
        )
        reopened = read_week1_operating_book_v1(
            store=store,
            materialization_identity=output_identity,
        )
        reopened_identity = normalize_object_identity_v1(
            reopened.get("identity"),
            label="independently reopened Week-1 materialization identity",
        )
    except Exception as exc:
        raise Week1OperatingBookPublicationCliError(
            "Week-1 publication or independent reopen failed"
        ) from exc

    materialization = reopened.get("materialization")
    if not isinstance(materialization, Mapping):
        _fail("independent reopen did not return a materialization object")
    materialization_sha = materialization.get("materialization_sha256")
    publication_sha = publication.get("materialization_sha256")
    if (
        reopened_identity != output_identity
        or output_identity["uri"] != output_uri
        or type(materialization_sha) is not str
        or _SHA256.fullmatch(materialization_sha) is None
        or publication_sha != materialization_sha
        or publication.get("independent_exact_reopen") is not True
        or publication.get("create_once") is not True
        or publication.get("complete") is not True
        or publication.get("k") != k
        or materialization.get("k") != k
        or materialization.get("cap4_used") is not False
        or materialization.get("tier3_used") is not False
        or materialization.get("uses_realized_outcomes") is not False
    ):
        _fail("publication and independent reopen bindings differ")

    environment = {
        "WEEK1_OPERATING_BOOK_URI": str(output_identity["uri"]),
        "WEEK1_OPERATING_BOOK_GENERATION": str(output_identity["generation"]),
        "WEEK1_OPERATING_BOOK_SHA256": str(output_identity["sha256"]),
        "WEEK1_OPERATING_BOOK_BYTES": str(output_identity["bytes"]),
    }
    if tuple(environment) != APP_ENVIRONMENT_KEYS:
        _fail("application configuration key order differs")

    body: dict[str, object] = {
        "schema_version": SCHEMA_VERSION,
        "complete": True,
        "k": k,
        "publication_receipt_sha256": publication[
            "publication_receipt_sha256"
        ],
        "materialization_identity": output_identity,
        "materialization_storage_created_at": reopened.get(
            "storage_created_at"
        ),
        "materialization_sha256": materialization_sha,
        "selected_lineup_ids_sha256": materialization.get(
            "selected_lineup_ids_sha256"
        ),
        "independent_exact_reopen": True,
        "app_environment": environment,
        "uses_realized_outcomes": False,
        "deployment_mutation_performed": False,
    }
    body["emission_sha256"] = canonical_sha256(body)
    return body


def _canonical_output(value: Mapping[str, object]) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ) + "\n"


def main(
    argv: Sequence[str] | None = None,
    *,
    store_factory: Callable[[], ImmutableObjectStore] = GCSImmutableObjectStore,
) -> int:
    parser = _parser()
    arguments = parser.parse_args(argv)
    if not arguments.apply or arguments.confirm != CONFIRMATION_PHRASE:
        print(
            "Week-1 publication is disabled; provide --apply and the exact "
            "confirmation phrase",
            file=sys.stderr,
        )
        return 2

    try:
        identity = _terminal_identity(arguments)
        report = publish_and_emit_config_v1(
            store=store_factory(),
            terminal_envelope_identity=identity,
            output_uri=arguments.output_uri,
            k=arguments.k,
        )
    except Exception as exc:
        print(f"Week-1 publication failed closed: {exc}", file=sys.stderr)
        return 2
    sys.stdout.write(_canonical_output(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
