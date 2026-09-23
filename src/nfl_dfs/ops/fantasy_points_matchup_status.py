"""Read-only status of every Fantasy Points live matchup capture on disk.

Answers, per run and per report, how far an export actually got:
``downloaded`` (bytes on disk), ``gate_passed`` (schedule gate in the run's
own record), ``validated`` (schema-2 ``validated_reports`` or a ledger entry),
``staged`` and ``consumed`` (ledger entries written by the loader and the
shadow join).  A failed run is never counted as a capture; a schema-1 run's
``captured`` record counts as ``gate_passed`` only, since those runs predate the
retention contract and were sealed by hand.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Sequence

from .fantasy_points_matchups import CAPTURE_ID, MATCHUPS, LEDGER_ORDER, ledger_path, read_ledger


REPORT_KEYS = tuple(definition.key for definition in MATCHUPS)
STAGES = ("downloaded", "gate_passed", "validated", "staged", "consumed")


def _report_status(run_dir: Path, manifest: dict[str, Any], key: str, ledger: dict | None) -> dict[str, Any]:
    records = [r for r in manifest.get("reports", []) if r.get("key") == key]
    files = [r.get("path") for r in records if r.get("path") and (run_dir / str(r["path"])).is_file()]
    schema = manifest.get("schema_version")
    gate_passed = any(
        (r.get("schedule_gate") or {}).get("passes") is True for r in records
    )
    if schema == 2:
        validated = key in (manifest.get("validated_reports") or {})
    else:
        validated = False
    entry = (ledger or {}).get("reports", {}).get(key, {}) if ledger else {}
    validated = validated or entry.get("validated") is not None
    staged = entry.get("staged") is not None
    consumed = entry.get("consumed") is not None
    reached = "none"
    for stage, flag in (
        ("downloaded", bool(files)), ("gate_passed", gate_passed),
        ("validated", validated), ("staged", staged), ("consumed", consumed),
    ):
        if flag:
            reached = stage
    return {
        "attempts": len(records),
        "files_on_disk": len(files),
        "downloaded": bool(files),
        "gate_passed": gate_passed,
        "validated": validated,
        "staged": staged,
        "consumed": consumed,
        "reached": reached,
        "rejections": [
            (r.get("rejection") or {}).get("failure_class")
            for r in records if r.get("status") == "rejected"
        ],
    }


def run_status(run_dir: str | Path) -> dict[str, Any]:
    run_dir = Path(run_dir)
    manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
    if manifest.get("capture_id") != CAPTURE_ID:
        raise ValueError(f"{run_dir.name}: not a live matchup capture")
    ledger = read_ledger(run_dir) if ledger_path(run_dir).is_file() else None
    return {
        "run_id": manifest.get("run_id", run_dir.name),
        "schema_version": manifest.get("schema_version"),
        "target_week": manifest.get("target_week"),
        "run_status": manifest.get("status"),
        "failure_class": manifest.get("failure_class"),
        "error": manifest.get("error"),
        "ledger": ledger is not None,
        "reports": {key: _report_status(run_dir, manifest, key, ledger) for key in REPORT_KEYS},
    }


def scan(output_root: str | Path, *, week: int | None = None) -> list[dict[str, Any]]:
    root = Path(output_root)
    runs = []
    for run_dir in sorted(root.glob(f"*__{CAPTURE_ID}__week-*")):
        if not (run_dir / "manifest.json").is_file():
            continue
        status = run_status(run_dir)
        if week is not None and status["target_week"] != int(week):
            continue
        runs.append(status)
    return runs


def summarize(runs: Sequence[dict[str, Any]]) -> dict[str, Any]:
    """Counts per week and report of the furthest stage reached by any run."""
    summary: dict[str, Any] = {"runs": len(runs), "weeks": {}}
    for status in runs:
        week = str(status["target_week"])
        bucket = summary["weeks"].setdefault(week, {
            "runs": 0, "complete_runs": 0, "failed_runs": 0,
            "reports": {key: {stage: 0 for stage in STAGES} for key in REPORT_KEYS},
        })
        bucket["runs"] += 1
        if status["run_status"] == "complete":
            bucket["complete_runs"] += 1
        elif status["run_status"] == "failed":
            bucket["failed_runs"] += 1
        for key, report in status["reports"].items():
            for stage in STAGES:
                if report[stage]:
                    bucket["reports"][key][stage] += 1
    return summary


def _render(runs: Sequence[dict[str, Any]]) -> str:
    lines = []
    for status in runs:
        head = (
            f"{status['run_id']}  schema={status['schema_version']}  week={status['target_week']}  "
            f"run={status['run_status']}"
        )
        if status.get("failure_class"):
            head += f"  failure_class={status['failure_class']}"
        lines.append(head)
        for key, report in status["reports"].items():
            rej = f" rejected={report['rejections']}" if report["rejections"] else ""
            lines.append(
                f"    {key:<22} attempts={report['attempts']} files={report['files_on_disk']} "
                f"reached={report['reached']}{rej}"
            )
    return "\n".join(lines)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="fantasy-points-matchup-status",
        description="Per-run, per-report retention status of live matchup captures (read-only)",
    )
    parser.add_argument("--output-root", type=Path, default=Path.cwd() / "fantasy-points" / "automated")
    parser.add_argument("--week", type=int, default=None)
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    runs = scan(args.output_root, week=args.week)
    if args.json:
        print(json.dumps({"runs": runs, "summary": summarize(runs)}, indent=2, sort_keys=True))
    else:
        print(_render(runs))
        print(json.dumps(summarize(runs), sort_keys=True))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
