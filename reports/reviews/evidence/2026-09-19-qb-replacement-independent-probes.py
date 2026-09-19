#!/usr/bin/env python3
"""Synthetic, outcome-free review of the proposed Week-2 replacement and QB gate.

This is a counterexample reader, not a scoring experiment. It records observed
behaviour against a named operational requirement; it never reads NFL outcomes.
"""
import argparse
import csv
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

import numpy as np
import pandas as pd

SLOTS = ["QB", "RB", "RB", "WR", "WR", "WR", "TE", "FLEX", "DST"]


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def qb(gsis, depth, team="CHI", injury=None, status=None):
    return dict(gsis_id=gsis, depth_rank=depth, team_abbr=team,
                dk_position="QB", injury_status=injury, status=status)


def fixture(root, *, hard, candidate="legal", book_status="", gated=False):
    run, vetted, out = (root / n for n in ("run", "vetted", "out"))
    run.mkdir(parents=True)
    vetted.mkdir()
    positions = ["QB", "RB", "RB", "WR", "WR", "WR", "TE", "RB", "DST", "QB"]
    frame = pd.DataFrame({
        "id": [f"P{i}" for i in range(1, 11)],
        "dk_player_id": list(range(1, 11)),
        "display_name": [f"Player {i}" for i in range(1, 11)],
        "pos": positions,
        "salary": [5000] * 8 + [3000, 6500],
        "status": [book_status] + [""] * 9,
    })
    if candidate == "over_salary":
        frame.loc[9, "salary"] = 20000
    frame.to_parquet(run / "frame.parquet", index=False)
    with (vetted / "book.csv").open("w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(SLOTS)
        writer.writerow(range(1, 10))
    flags = {"Player 1": {"dk": "1", "weight": 100, "flags": ["DK:OUT"]}} if hard else {}
    vet = {"order_source_ranks": [1],
           "lineups": [{"rank": 1, "hard": hard,
                        "flags": {"Player 1": ["DK:OUT"]} if hard else {}}],
           "player_flags": flags}
    (vetted / "vetting.json").write_text(json.dumps(vet))
    (vetted / "source_receipt.json").write_text('{"fixture": true}\n')
    replacement = [10, 2, 3, 4, 5, 6, 7, 8, 9]
    if candidate == "duplicate_player":
        replacement[2] = 2
    pd.DataFrame({"players": [",".join(f"P{i}" for i in replacement)]}).to_parquet(
        run / "candidates.parquet", index=False)
    bank = np.full((10, 4), 10.0, dtype=np.float32)
    bank[9] = 20
    for name in ("incumbent_player_scores.npy", "corrected_hsim_player_scores.npy"):
        np.save(run / name, bank)
    flags_path = root / "qb-flags.csv"
    with flags_path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["qb_name", "injury_status", "verdict"])
        writer.writeheader()
        if gated:
            writer.writerow({"qb_name": "Player 1", "injury_status": "",
                             "verdict": "BEHIND-HEALTHY-STARTER"})
    return run, vetted, out, flags_path, frame


def replace_probe(root, script, name, requirement, **opts):
    minimum = opts.pop("minimum", 0)
    run, vetted, out, flags, frame = fixture(root / name, **opts)
    result = subprocess.run([sys.executable, "-X", "cpu_count=1", str(script),
                             str(vetted), str(run), str(out), "--qb-flags", str(flags),
                             "--min-replacements", str(minimum)],
                            capture_output=True, text=True, check=False)
    emitted = []
    if (out / "book.csv").exists():
        with (out / "book.csv").open(newline="") as handle:
            emitted = [[int(v) for v in row] for row in list(csv.reader(handle))[1:]]
    salary = frame.set_index("dk_player_id")["salary"].to_dict()
    return {"case": name, "requirement": requirement, "returncode": result.returncode,
            "book_emitted": bool(emitted), "book": emitted,
            "distinct_players": [len(set(row)) for row in emitted],
            "salary_totals": [sum(int(salary[v]) for v in row) for row in emitted],
            "stdout": result.stdout.strip(), "stderr": result.stderr[-3000:]}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--production", required=True, type=Path)
    ap.add_argument("--replacement", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    args = ap.parse_args()
    sys.path.insert(0, str(args.production / "src"))
    os.environ.pop("QB_BACKUP_GATE", None)
    from nfl_dfs.inference.cascade_adjust import find_backup_qbs

    cases = [
        ("healthy_primary_control", [qb("CHI1", 1), qb("CHI2", 2)], ["CHI2"],
         "Healthy unique primary gates the deeper QB."),
        ("out_primary_control", [qb("CHI1", 1, status="O"), qb("CHI2", 2), qb("CHI3", 3)], ["CHI3"],
         "Known OUT primary promotes depth 2; depth 3 is gated."),
        ("doubtful_primary_control", [qb("CHI1", 1, injury="Doubtful"), qb("CHI2", 2)], [],
         "Doubtful primary leaves team unchanged under the stated rule."),
        ("missing_depth1_two_remaining", [qb("CHI2", 2), qb("CHI3", 3)], [],
         "Handoff promises no change when no depth-1 QB is on file."),
        ("blank_team_cross_group", [qb("A1", 1, team=None), qb("B2", 2, team=None)], [],
         "Unknown teams must not be grouped as a real team; upstream live structural checks normally reject this."),
        ("tied_primary_doubtful_sorts_first", [qb("A1", 1, injury="Doubtful"), qb("B1", 1), qb("C2", 2)], [],
         "Conflicting primary evidence should not depend on lexical player ID."),
        ("tied_primary_healthy_sorts_first", [qb("B1", 1, injury="Doubtful"), qb("A1", 1), qb("C2", 2)], [],
         "Same evidence with reordered IDs must have the same ambiguous-team treatment."),
    ]
    gate_results = []
    for name, rows, expected, requirement in cases:
        got = find_backup_qbs(pd.DataFrame(rows))
        gate_results.append({"case": name, "expected": expected, "observed": got,
                             "satisfied": got == expected, "requirement": requirement})
    with tempfile.TemporaryDirectory(prefix="qb-replacement-review-") as tmp:
        root = Path(tmp)
        replacements = [
            replace_probe(root, args.replacement, "legal_replacement_control",
                          "Valid replacement should succeed.", hard=True),
            replace_probe(root, args.replacement, "new_gate_with_old_clean_vetting",
                          "Whole-slate exclusion must remove a newly gated QB from the retained book.",
                          hard=False, gated=True),
            replace_probe(root, args.replacement, "new_dk_out_with_old_clean_vetting",
                          "A frame OUT player must not survive an old clean vetting result.",
                          hard=False, book_status="OUT"),
            replace_probe(root, args.replacement, "minimum_replacement_guard",
                          "A requested minimum of one must not pass through zero replacements.",
                          hard=False, minimum=1),
            replace_probe(root, args.replacement, "duplicate_player_candidate",
                          "Nine distinct players are required before publication.",
                          hard=True, candidate="duplicate_player"),
            replace_probe(root, args.replacement, "over_salary_candidate",
                          "A lineup over $50,000 must not be published.",
                          hard=True, candidate="over_salary"),
        ]
    report = {"kind": "synthetic_outcome_free_counterexamples", "production_commit":
              subprocess.check_output(["git", "-C", str(args.production), "rev-parse", "HEAD"], text=True).strip(),
              "gate_source_sha256": digest(args.production / "src/nfl_dfs/inference/cascade_adjust.py"),
              "replacement_source_sha256": digest(args.replacement),
              "reader_sha256": digest(__file__), "gate_cases": gate_results,
              "replacement_cases": replacements}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
