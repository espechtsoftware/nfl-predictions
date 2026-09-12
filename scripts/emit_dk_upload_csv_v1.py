#!/usr/bin/env python3
"""Emit a DraftKings classic upload CSV with slate-specific draftable IDs.

Two sources, both fail-closed (see ``nfl_dfs.inference.dk_upload_csv_v1``):

* ``--source run-dir``: a lab ``live_week.py`` run directory.  Its
  ``book.csv`` carries stable ``dk_player_id`` values, which DraftKings'
  import does not match on; they are mapped to draftable IDs through the
  run's own ``frame.parquet`` and every slot is checked for position
  eligibility.
* ``--source published``: a Week-1 A5 publish.  The terminal is read live,
  the requested book is exact-reopened by its pinned identity, and the
  salary catalog (also exact-reopened) supplies positions for the slot check.

The output path is create-only.  A JSON receipt with the file's SHA-256 and
the source identities is printed so the upload can be tied to the book.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from nfl_dfs.inference import dk_upload_csv_v1 as up
from nfl_dfs.inference.prospective_generation_shadow_operator import (
    GCSImmutableObjectStore,
)
from nfl_dfs.research.object_identity import live_object_receipt


def _published(terminal_uri: str, book_id: str) -> tuple[list[list[int]], dict]:
    from google.cloud import storage

    client = storage.Client()
    store = GCSImmutableObjectStore(client)
    terminal_receipt, raw = live_object_receipt(client, terminal_uri)
    terminal = json.loads(raw)
    books = terminal.get("books") or {}
    if book_id not in books:
        raise SystemExit(f"terminal has no book {book_id!r}; it has {sorted(books)}")
    book_identity = dict(books[book_id]["artifact_identity"])
    book = json.loads(store.read_exact(identity=book_identity)["raw"])
    if book.get("policy") != book_id:
        raise SystemExit(f"book {book_id} policy label differs: {book.get('policy')!r}")
    catalog_identity = dict(terminal["salary_catalog"]["artifact_identity"])
    catalog = json.loads(store.read_exact(identity=catalog_identity)["raw"])
    if str(catalog.get("draft_group_id")) != str(book.get("draft_group_id")):
        raise SystemExit("salary catalog and book name different draft groups")
    positions = up.positions_from_salary_catalog(catalog)
    rows = up.rows_from_book_entries(
        book["entries"], position_by_draftable_id=positions
    )
    receipt = {
        "source": "published-a5-book",
        "book_id": book_id,
        "draft_group_id": str(book.get("draft_group_id")),
        "slate_id": book.get("slate_id"),
        "terminal_identity": {
            k: terminal_receipt[k] for k in ("uri", "generation", "sha256", "bytes")
        },
        "book_identity": book_identity,
        "book_semantic_sha256": book.get("semantic_sha256"),
        "salary_catalog_identity": catalog_identity,
        "id_form": "slot_dk_draftable_ids from the published book",
    }
    return rows, receipt


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--source", choices=("run-dir", "published"), required=True)
    parser.add_argument("--run-dir", type=Path)
    parser.add_argument("--terminal-uri")
    parser.add_argument("--book-id")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--ranks",
        help="inclusive 1-based lineup-rank range to write, e.g. 1-57 for the "
             "Millionaire prefix; default writes every lineup",
    )
    args = parser.parse_args()

    if args.source == "run-dir":
        if args.run_dir is None:
            raise SystemExit("--run-dir is required with --source run-dir")
        rows, receipt = up.rows_from_live_week_run(args.run_dir.resolve(strict=True))
    else:
        if not args.terminal_uri or not args.book_id:
            raise SystemExit("--terminal-uri and --book-id are required")
        rows, receipt = _published(args.terminal_uri, args.book_id)
    if args.ranks:
        try:
            first, last = (int(part) for part in args.ranks.split("-", 1))
        except ValueError:
            raise SystemExit("--ranks must look like 1-57") from None
        rows = up.slice_ranks(rows, first, last)
        receipt["ranks"] = {"first": first, "last": last}
    written = up.write_upload_csv(rows, args.output)
    print(json.dumps({"upload": written, "source": receipt}, sort_keys=True, indent=1))


if __name__ == "__main__":
    sys.exit(main())
