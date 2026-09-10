#!/usr/bin/env python3
"""Build the row-free R6 final-book prefix and ranking audit."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Sequence

from nfl_dfs.research import corpus_r6_full_union_attribution_v1 as attribution
from nfl_dfs.research import corpus_r6_prefix_ranking_audit_v1 as audit


class PrefixRankingAuditCliV1Error(ValueError):
    pass


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--attribution-shard-dir", type=Path, required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if not args.execute:
        raise PrefixRankingAuditCliV1Error("--execute is required")
    paths = sorted(args.attribution_shard_dir.glob("*.json"))
    if len(paths) != 54:
        raise PrefixRankingAuditCliV1Error("exactly 54 attribution shards are required")
    shards = []
    identities = []
    for path in paths:
        raw = path.read_bytes()
        try:
            value = json.loads(raw)
            retained = attribution.validate_slate_attribution_structure_v1(value)
        except (json.JSONDecodeError, attribution.CorpusR6FullUnionAttributionV1Error) as exc:
            raise PrefixRankingAuditCliV1Error(
                f"invalid attribution shard {path.name}: {exc}"
            ) from exc
        shards.append(retained)
        identities.append(
            {
                "file_name": path.name,
                "bytes": len(raw),
                "sha256": hashlib.sha256(raw).hexdigest(),
                "source_ordinal": retained["source_ordinal"],
                "slate_id": retained["slate_id"],
                "slate_attribution_sha256": retained["slate_attribution_sha256"],
                "slate_grade_identity": retained["slate_grade_identity"],
            }
        )
    result = audit.build_prefix_ranking_audit_v1(
        shards,
        source_binding={
            "attribution_shard_count": len(identities),
            "attribution_shards": identities,
            "source_law": "persisted-r6-attribution-shards-only",
        },
    )
    print(json.dumps(result, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (PrefixRankingAuditCliV1Error, audit.CorpusR6PrefixRankingAuditV1Error) as exc:
        raise SystemExit(f"ERROR: {exc}") from exc
