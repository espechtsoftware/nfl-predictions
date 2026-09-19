#!/usr/bin/env python3
"""The same independent v4 boundaries with v4.1's second provider query mocked."""
import argparse
import contextlib
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
from unittest.mock import patch

import pandas as pd
from google.cloud import bigquery


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tools", type=Path, required=True)
    ap.add_argument("--lab-src", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    basepath = Path(__file__).with_name("2026-09-19-v4-independent-boundaries.py")
    spec = importlib.util.spec_from_file_location("v4_fixture", basepath)
    base = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(base)
    sys.path.insert(0, str(a.tools))
    mod = base.load(a.tools / "vet_replace_v4.py", "review_v41")
    classify = base.load(a.tools / "qb_classify.py", "review_classifier_v41")
    results = []
    cases = ["legal_replacement_control", "fresh_csv_out_old_clean_vet", "frame_out_old_clean_vet",
             "minimum_replacement_guard", "source_count_mismatch", "duplicate_player_candidate",
             "over_salary_candidate", "unequal_bank_widths", "nonfinite_bank",
             "questionable_replacement_policy", "questionable_with_admit_risky",
             "fresh_blank_clears_old_questionable"]
    with tempfile.TemporaryDirectory(prefix="v41-review-") as temp:
        for case in cases:
            fixture_case = "questionable_replacement_policy" if case in {
                "questionable_with_admit_risky", "fresh_blank_clears_old_questionable"} else case
            run, vet, out, flags = base.fixture(Path(temp) / case, fixture_case)
            frame = pd.read_parquet(run / "frame.parquet")
            fresh = frame[["dk_player_id", "status"]].copy()
            fresh["pulled_at"] = pd.Timestamp.now(tz="UTC")
            if case == "fresh_blank_clears_old_questionable":
                fresh["status"] = ""
            inj = pd.DataFrame(columns=["gsis_id", "report_status", "date_modified"])
            def provider(sql, **kwargs):
                data = fresh if "dk_salaries" in sql else inj
                return SimpleNamespace(result=lambda: SimpleNamespace(to_dataframe=lambda: data.copy()))
            argv = [str(a.tools / "vet_replace_v4.py"), str(vet), str(run), str(out),
                    "--qb-flags", str(flags), "--lab-src", str(a.lab_src)]
            if case == "minimum_replacement_guard":
                argv += ["--min-replacements", "1"]
            if case == "questionable_with_admit_risky":
                argv += ["--admit-risky"]
            output, error, code, exception = io.StringIO(), io.StringIO(), 0, None
            with patch.object(sys, "argv", argv), patch.object(bigquery, "Client") as client:
                client.return_value.query.side_effect = provider
                with contextlib.redirect_stdout(output), contextlib.redirect_stderr(error):
                    try:
                        mod.main()
                    except SystemExit as exc:
                        code = exc.code if isinstance(exc.code, int) else 1
                        exception = str(exc)
                    except Exception as exc:
                        code, exception = 99, f"{type(exc).__name__}: {exc}"
            receipt = json.loads((out / "replace.json").read_text()) if (out / "replace.json").exists() else None
            book = (out / "book.csv").read_text() if (out / "book.csv").exists() else None
            results.append(dict(case=case, exit_code=code, exception=exception, book=book,
                                receipt=receipt, stdout=output.getvalue(), stderr=error.getvalue()))
    q = pd.DataFrame([dict(gsis_id="A", team="CHI", depth_rank=1, injury_status="Doubtful"),
                      dict(gsis_id="B", team="CHI", depth_rank=1, injury_status=""),
                      dict(gsis_id="C", team="CHI", depth_rank=2, injury_status="")])
    ties = [classify.gated_ids(q.iloc[order].reset_index(drop=True), "gsis_id") for order in ([0, 1, 2], [1, 0, 2])]
    data = dict(kind="offline_synthetic_v41_boundary_review", source_hashes={
        name: hashlib.sha256((a.tools / name).read_bytes()).hexdigest()
        for name in ("vet_replace_v4.py", "qb_classify.py")},
        reader_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        fixture_sha256=hashlib.sha256(basepath.read_bytes()).hexdigest(), cases=results, tied_primary_results=ties)
    a.out.write_text(json.dumps(base.finite_json(data), indent=2, allow_nan=False) + "\n")
    print(json.dumps({"cases": [{k: row[k] for k in ("case", "exit_code", "exception")} for row in results],
                      "ties": ties}, indent=2))


if __name__ == "__main__":
    main()
