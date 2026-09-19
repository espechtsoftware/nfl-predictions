#!/usr/bin/env python3
"""Run the actual v4 CLI main offline with synthetic legal books and mocked BQ.

Mock only the provider response. Classifier, legality and replacement code are
the reviewed files, imported without modification. No NFL outcomes are read.
"""
import argparse
import contextlib
import csv
import hashlib
import importlib.util
import io
import json
import math
from pathlib import Path
import sys
import tempfile
from unittest.mock import patch

import numpy as np
import pandas as pd
from google.cloud import bigquery


def fixture(root, case):
    run, vetted, out = [root / label for label in ("run", "vetted", "out")]
    run.mkdir(parents=True)
    vetted.mkdir()
    salary = [6500, 5500, 5500, 6000, 6500, 6000, 5000, 6000, 3000, 6500]
    if case == "over_salary_candidate":
        salary[-1] = 20000
    team = ["A", "C", "E", "A", "A", "B", "C", "G", "E", "A"]
    opp = ["B", "D", "F", "B", "B", "A", "D", "H", "F", "B"]
    frame = pd.DataFrame({
        "id": [f"P{i}" for i in range(1, 11)],
        "gsis_id": [f"P{i}" for i in range(1, 11)],
        "dk_player_id": range(1, 11),
        "display_name": [f"Player {i}" for i in range(1, 11)],
        "pos": ["QB", "RB", "RB", "WR", "WR", "WR", "TE", "RB", "DST", "QB"],
        "team": team, "opp": opp, "game_id": ["".join(sorted([t, o])) for t, o in zip(team, opp)],
        "salary": salary, "status": [""] * 10,
    })
    if case == "questionable_replacement_policy":
        frame.loc[3, "status"] = "Q"
    if case == "frame_out_old_clean_vet":
        frame.loc[0, "status"] = "OUT"
    frame.to_parquet(run / "frame.parquet", index=False)
    source = {"written": 2 if case == "source_count_mismatch" else 1,
              "config": {"operational_k": 2 if case == "source_count_mismatch" else 1},
              "season": 2026, "week": 2, "draft_group": 153428, "fixture": True}
    (run / "receipt.json").write_text(json.dumps(source))
    (vetted / "source_receipt.json").write_text(json.dumps(source))
    with (vetted / "book.csv").open("w", newline="") as handle:
        w = csv.writer(handle)
        w.writerow(["QB", "RB", "RB", "WR", "WR", "WR", "TE", "FLEX", "DST"])
        w.writerow(range(1, 10))
    vet = {"order_source_ranks": [1], "lineups": [{"rank": 1, "hard": False, "flags": {}}],
           "player_flags": {}}
    (vetted / "vetting.json").write_text(json.dumps(vet))
    alt = [10, 2, 3, 4, 5, 6, 7, 8, 9]
    if case == "duplicate_player_candidate":
        alt[2] = 2
    pd.DataFrame({"players": [",".join(f"P{i}" for i in alt)]}).to_parquet(run / "candidates.parquet", index=False)
    bank = np.full((10, 4), 10.0, dtype=np.float32)
    bank[-1] = 20
    if case == "nonfinite_bank":
        bank[-1, 0] = np.nan
    np.save(run / "incumbent_player_scores.npy", bank)
    np.save(run / "corrected_hsim_player_scores.npy", bank[:, :3] if case == "unequal_bank_widths" else bank)
    gate = case not in {"minimum_replacement_guard", "source_count_mismatch", "fresh_csv_out_old_clean_vet"}
    flags = pd.DataFrame([
        dict(gsis_id="P1", dk_player_id=1, qb_name="Player 1", team="A", depth_rank=2,
             dk_status="OUT" if case == "fresh_csv_out_old_clean_vet" else "",
             injury_status="", role="out" if case == "fresh_csv_out_old_clean_vet" else ("gated" if gate else "primary"), team_class="healthy"),
        dict(gsis_id="P10", dk_player_id=10, qb_name="Player 10", team="A", depth_rank=1,
             dk_status="", injury_status="", role="primary", team_class="healthy"),
    ])
    flags.to_csv(root / "flags.csv", index=False)
    return run, vetted, out, root / "flags.csv"


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def finite_json(value):
    if isinstance(value, float) and not math.isfinite(value):
        return {"non_finite_value": str(value)}
    if isinstance(value, dict):
        return {k: finite_json(v) for k, v in value.items()}
    if isinstance(value, list):
        return [finite_json(v) for v in value]
    return value


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tools", type=Path, required=True)
    ap.add_argument("--lab-src", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    sys.path.insert(0, str(a.tools))
    mod = load(a.tools / "vet_replace_v4.py", "review_v4")
    classifier = load(a.tools / "qb_classify.py", "review_classifier")
    inj = pd.DataFrame(columns=["gsis_id", "report_status", "date_modified"])
    results = []
    with tempfile.TemporaryDirectory(prefix="v4-review-") as temp:
        for case in ["legal_replacement_control", "fresh_csv_out_old_clean_vet",
                     "frame_out_old_clean_vet", "minimum_replacement_guard",
                     "source_count_mismatch", "duplicate_player_candidate",
                     "over_salary_candidate", "unequal_bank_widths", "nonfinite_bank",
                     "questionable_replacement_policy"]:
            root = Path(temp) / case
            run, vetted, out, flags = fixture(root, case)
            argv = [str(a.tools / "vet_replace_v4.py"), str(vetted), str(run), str(out),
                    "--qb-flags", str(flags), "--lab-src", str(a.lab_src)]
            if case == "minimum_replacement_guard":
                argv += ["--min-replacements", "1"]
            output, error = io.StringIO(), io.StringIO()
            code, exception = 0, None
            with patch.object(sys, "argv", argv), patch.object(bigquery, "Client") as client:
                client.return_value.query.return_value.result.return_value.to_dataframe.return_value = inj.copy()
                with contextlib.redirect_stdout(output), contextlib.redirect_stderr(error):
                    try:
                        mod.main()
                    except SystemExit as exc:
                        code = exc.code if isinstance(exc.code, int) else 1
                        exception = str(exc)
                    except Exception as exc:
                        code, exception = 99, f"{type(exc).__name__}: {exc}"
            book = []
            if (out / "book.csv").exists():
                with (out / "book.csv").open(newline="") as h:
                    book = [[int(x) for x in r] for r in list(csv.reader(h))[1:]]
            receipt = json.loads((out / "replace.json").read_text()) if (out / "replace.json").exists() else None
            results.append(dict(case=case, exit_code=code, exception=exception,
                                book=book, status=None if receipt is None else receipt["status"],
                                receipt=receipt, stdout=output.getvalue(), stderr=error.getvalue()))
    tied = pd.DataFrame([
        dict(gsis_id="A", team="CHI", depth_rank=1, injury_status="Doubtful"),
        dict(gsis_id="B", team="CHI", depth_rank=1, injury_status=""),
        dict(gsis_id="C", team="CHI", depth_rank=2, injury_status=""),
    ])
    ties = []
    for order in ([0, 1, 2], [1, 0, 2]):
        got = classifier.classify_qbs(tied.iloc[order].reset_index(drop=True))
        ties.append(dict(order=order, gated=got.loc[got.role == "gated", "gsis_id"].tolist()))
    data = dict(kind="offline_synthetic_v4_boundary_review", actual_outcomes_read=False,
                source_hashes={name: hashlib.sha256((a.tools / name).read_bytes()).hexdigest()
                               for name in ("vet_replace_v4.py", "qb_classify.py")},
                cases=results, tied_primary_order_cases=ties)
    a.out.write_text(json.dumps(finite_json(data), indent=2, allow_nan=False) + "\n")
    print(json.dumps({"cases": [{k: r[k] for k in ("case", "exit_code", "book", "status", "exception")} for r in results],
                      "ties": ties}, indent=2))


if __name__ == "__main__":
    main()
