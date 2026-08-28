#!/usr/bin/env python3
"""Object-store-free grouped selector successor matrix child."""

from __future__ import annotations

import json
import sys
from typing import Final

from nfl_dfs.research import (
    corpus_r6_current_bank_crossed_screen_contract_v1 as contract,
)
from nfl_dfs.research import (
    corpus_r6_current_bank_crossed_screen_selection_fold_worker_v1 as worker,
)
from nfl_dfs.research import (
    corpus_r6_current_bank_selector_successor_authority_v1 as authority,
)
from nfl_dfs.research import (
    corpus_r6_current_bank_selector_successor_process_adapter_v1 as adapter,
)
from nfl_dfs.research import (
    corpus_r6_current_bank_selector_successor_cloud_v1 as cloud,
)
from nfl_dfs.research import (
    corpus_r6_current_bank_selector_successor_runtime_v1 as runtime,
)


MAXIMUM_STDIN_BYTES: Final = 112_000_000


class RunCorpusR6CurrentBankSelectorSuccessorV1Error(ValueError):
    """The grouped selector matrix child failed closed."""


def _fail(message: str) -> None:
    raise RunCorpusR6CurrentBankSelectorSuccessorV1Error(message)


def execute_child_request_v1(
    value: object, *, fd_number: int | None = None,
) -> dict[str, object]:
    request = cloud.validate_matrix_child_request_v1(value)
    capability = request["matrix_capability"]
    process_ordinal = int(capability["process_ordinal"])
    observed_runtime = runtime.derive_current_process_runtime_evidence_v1(
        process_ordinal=process_ordinal
    )
    scores, region = worker._map_inherited_matrix_readonly_v1(
        capability["matrix_descriptor"], fd_number=fd_number
    )
    try:
        response = authority.run_authority_bound_broad_selectors_v1(
            matrix_capability=capability,
            training_score_matrix=scores,
            runtime_evidence=observed_runtime,
        )
        return adapter.build_successor_broad_fold_receipt_v1(
            successor_process_budget=request["successor_process_budget"],
            successor_process_budget_identity=request[
                "successor_process_budget_identity"
            ],
            source_process_budget=request["source_process_budget"],
            source_process_budget_identity=request[
                "source_process_budget_identity"
            ],
            matrix_capability=capability,
            training_score_matrix=scores,
            runtime_evidence=observed_runtime,
            authority_response=response,
            launch_intent_identity=request["launch_intent_identity"],
        )
    finally:
        del scores
        region.close()


def _read_stdin_bounded_v1() -> bytes:
    raw = sys.stdin.buffer.read(MAXIMUM_STDIN_BYTES + 1)
    if not raw or len(raw) > MAXIMUM_STDIN_BYTES:
        _fail("grouped selector child stdin byte count differs")
    return raw


def _strict_json_v1(raw: bytes) -> dict[str, object]:
    try:
        value = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RunCorpusR6CurrentBankSelectorSuccessorV1Error(
            "grouped selector child stdin is not JSON"
        ) from exc
    if not isinstance(value, dict) or any(type(key) is not str for key in value):
        _fail("grouped selector child stdin must be a string-keyed object")
    item = dict(value)
    if contract.canonical_json_bytes_v1(item) != raw:
        _fail("grouped selector child stdin is not canonical JSON")
    return item


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if args != ["matrix-selector"]:
        raise SystemExit("usage: ...selector_successor_v1.py matrix-selector")
    request = _strict_json_v1(_read_stdin_bounded_v1())
    result = execute_child_request_v1(request)
    raw = contract.canonical_json_bytes_v1(result)
    if len(raw) > adapter.FOLD_RECEIPT_BYTE_CEILING:
        _fail("grouped selector child stdout exceeds exact fold ceiling")
    sys.stdout.buffer.write(raw)
    sys.stdout.buffer.flush()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
