#!/usr/bin/env python3
"""Default-off operator for the trusted R6 matchup source-v2 batch.

No mode is implicit.  ``validate`` performs only local Git/runtime checks;
``publish`` additionally requires both an explicit CLI confirmation and the
code-owned enable environment variable; ``reopen`` accepts only one complete
generation-pinned terminal-root identity.  None of the modes accept source
bodies, final-lock bytes, candidate bodies, outcomes, scores, or selectors.
"""

from __future__ import annotations

import argparse
from collections.abc import Sequence
import json
import os
from pathlib import Path
import sys

from nfl_dfs.research import (
    corpus_r6_matchup_batch_candidate_authority_v1 as batch,
)


def _load_root_identity(path_value: str) -> dict[str, object]:
    path = Path(path_value)
    if not path.is_absolute() or path.is_symlink() or not path.is_file():
        raise ValueError("reopen identity path must be one absolute regular file")
    raw = path.read_bytes()
    if not raw or len(raw) > 64 * 1024:
        raise ValueError("reopen identity file byte bound differs")
    try:
        value = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        raise ValueError("reopen identity file must be JSON") from exc
    if not isinstance(value, dict):
        raise ValueError("reopen identity file must contain one object")
    return value


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Validate, explicitly publish, or reopen matchup source-v2"
    )
    parser.add_argument(
        "--action",
        required=True,
        choices=("validate", "publish", "reopen"),
        help="No action is the default; choose exactly one explicit operation.",
    )
    parser.add_argument("--run-id")
    parser.add_argument("--batch-root-identity")
    parser.add_argument(
        "--confirm-publish",
        action="store_true",
        help="Required in addition to the enable environment for publication.",
    )
    return parser


def run(argv: Sequence[str] | None = None) -> dict[str, object]:
    args = _parser().parse_args(argv)
    if args.action == "validate":
        if args.run_id or args.batch_root_identity or args.confirm_publish:
            raise ValueError("validate accepts no publication or reopen arguments")
        return batch.validate_matchup_source_batch_candidate_authority_v1()
    if args.action == "reopen":
        if args.run_id or args.confirm_publish or not args.batch_root_identity:
            raise ValueError("reopen requires only --batch-root-identity")
        return batch.reopen_matchup_source_batch_candidate_authority_v1(
            batch_release_identity=_load_root_identity(args.batch_root_identity)
        )
    if (
        not args.run_id
        or args.batch_root_identity
        or args.confirm_publish is not True
        or os.environ.get(batch.PUBLISH_ENABLE_ENV) != "1"
    ):
        raise ValueError(
            "publish requires --run-id, --confirm-publish, and "
            f"{batch.PUBLISH_ENABLE_ENV}=1"
        )
    return batch.publish_matchup_source_batch_candidate_authority_v1(
        run_id=args.run_id
    )


def main(argv: Sequence[str] | None = None) -> int:
    try:
        result = run(argv)
    except (ValueError, batch.CorpusR6MatchupBatchCandidateAuthorityV1Error) as exc:
        print(str(exc), file=sys.stderr)
        return 2
    print(json.dumps(result, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
