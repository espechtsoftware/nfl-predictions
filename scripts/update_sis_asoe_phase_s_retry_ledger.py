#!/usr/bin/env python
"""Atomically substitute one verified zero-output Phase S retry."""

from __future__ import annotations

import argparse
import os
from pathlib import Path


def _nonempty_lines(path: Path) -> list[str]:
    return [line for line in path.read_text().splitlines() if line.strip()]


def replacement_contents(
    executions_text: str, pending_text: str, retries_text: str, *,
    arm: str, replicate: int, season: int, panel: str, job: str,
    failed_execution: str, retry_execution: str, reason: str,
) -> tuple[str, str, str]:
    executions = [line for line in executions_text.splitlines() if line.strip()]
    pending = [line for line in pending_text.splitlines() if line.strip()]
    retries = [line for line in retries_text.splitlines() if line.strip()]
    if len(executions) != 30:
        raise ValueError("Phase S execution ledger must contain exactly 30 cells")
    fields = [line.split() for line in executions]
    if any(len(row) != 6 for row in fields):
        raise ValueError("Phase S execution ledger has a malformed row")
    cells = [(row[0], int(row[1]), int(row[2])) for row in fields]
    if len(set(cells)) != 30:
        raise ValueError("Phase S execution ledger repeats a factorial cell")
    if len({row[5] for row in fields}) != 30:
        raise ValueError("Phase S execution ledger repeats an execution ID")
    if retry_execution in {row[5] for row in fields}:
        raise ValueError("retry execution already occurs in the ledger")

    cell = (arm, replicate, season)
    indexes = [index for index, value in enumerate(cells) if value == cell]
    if len(indexes) != 1:
        raise ValueError("retry cell does not occur exactly once")
    index = indexes[0]
    expected = [arm, str(replicate), str(season), panel, job, failed_execution]
    if fields[index] != expected:
        raise ValueError("ledger cell does not name the classified failed execution")
    pending_prefix = [arm, str(replicate), str(season), failed_execution]
    pending_indexes = [
        i for i, line in enumerate(pending)
        if line.split()[:4] == pending_prefix
    ]
    if len(pending_indexes) != 1:
        raise ValueError("failed execution does not occur once in the pending queue")

    fields[index][5] = retry_execution
    pending.pop(pending_indexes[0])
    retries.append(" ".join([
        arm, str(replicate), str(season), failed_execution,
        retry_execution, reason,
    ]))
    return tuple(
        "\n".join(lines) + ("\n" if lines else "")
        for lines in ([" ".join(row) for row in fields], pending, retries)
    )


def _atomic_write(path: Path, contents: str) -> None:
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temporary.write_text(contents)
    os.replace(temporary, path)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--arm", choices=("control", "treatment"), required=True)
    parser.add_argument("--replicate", type=int, choices=range(5), required=True)
    parser.add_argument("--season", type=int, choices=(2023, 2024, 2025), required=True)
    parser.add_argument("--panel", required=True)
    parser.add_argument("--job", required=True)
    parser.add_argument("--failed-execution", required=True)
    parser.add_argument("--retry-execution", required=True)
    parser.add_argument("--reason", required=True)
    args = parser.parse_args()
    paths = (
        args.run_dir / "executions.txt",
        args.run_dir / "pending_infrastructure_retries.txt",
        args.run_dir / "infrastructure_retries.txt",
    )
    if not all(path.exists() for path in paths):
        raise SystemExit("ABORT: Phase S retry ledgers are incomplete")
    contents = replacement_contents(
        *(path.read_text() for path in paths), arm=args.arm,
        replicate=args.replicate, season=args.season, panel=args.panel,
        job=args.job, failed_execution=args.failed_execution,
        retry_execution=args.retry_execution, reason=args.reason,
    )
    for path, value in zip(paths, contents, strict=True):
        _atomic_write(path, value)
    print(
        "PHASE_S_RETRY_LEDGER_UPDATED "
        f"{args.arm} R{args.replicate} {args.season} {args.retry_execution}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
