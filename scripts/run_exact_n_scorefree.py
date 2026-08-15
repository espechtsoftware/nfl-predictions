#!/usr/bin/env python3
"""Run the frozen outcome-free exact-N contest-book diagnostic."""

from __future__ import annotations

import argparse
from collections import Counter
import json
import os
from pathlib import Path
from typing import Any

import numpy as np
from google.cloud import bigquery, storage

from nfl_dfs.analysis.exact_n_portfolio import (
    ENTRY_TARGET_LINES,
    book_scorefree_metrics,
    exact_n_scorefree_diagnostic,
    summarize_exact_n_panel,
)
from nfl_dfs.inference.multiseed_portfolio import (
    combine_cbwu_books,
    combine_cbwu_order_invariant_books,
)
from nfl_dfs.optimizer.lineup import Lineup, select_tail_entries
from nfl_dfs.research.source_preflight import (
    resolve_panel_artifacts,
    validate_execution_identity,
    verify_local_sha256,
)

from run_cbwu_seed_order_audit import (
    FORENSIC_MANIFEST_SHA256,
    PLAYER_SQL,
    PROJECT,
    SOURCE_PANEL_IDS,
    SOURCE_SQL,
    _candidate_batch,
    _download_artifact,
    _query,
    _upload_create_only,
    validate_scorefree_queries,
)


VERSION = "exact-n-scorefree-v1"
PARENT_PROTOCOL_PATH = Path(
    "reports/2026-08-15-exact-n-scorefree-protocol.md"
)
PARENT_PROTOCOL_SHA256 = (
    "4918cdf96675a2b7608c5688e80fb826b61c443e9beb6bbb210f34a5b6319c11"
)
SOURCE_AMENDMENT_PATH = Path(
    "reports/2026-08-15-exact-n-order-invariant-source-amendment.md"
)
SOURCE_AMENDMENT_SHA256 = (
    "934af9c612fe5399bbe2c6aa0061d258c2fd4691785ac678cb8f5d6d633203ce"
)
CBWU_REPORT_PATH = Path(
    "reports/cbwu-order-invariant-runs/"
    "20260815-cbwu-order-invariant-repair-v1/report.json"
)
CBWU_REPORT_SHA256 = (
    "556adeca6e0bf2855ad82296b1e708041a20446dc27e2c988c1d11e8c5bd4d33"
)
OUTPUT_URI = (
    "gs://nfl-predictions-503414-raw/research/final-forensic-runs/"
    "20260814-final-preseason-forensic-v1/post-forensic-addenda/"
    "20260815-exact-n-scorefree-v1/result.json"
)
WORLDS_PER_BLOCK = 10_000
ENTRY_COUNT = 80
TAIL_LINE = 194.0


def _identities(batch) -> list[list[str]]:
    result = [sorted(str(value) for value in lineup.ids)
              for lineup in batch.candidates]
    if len(result) != len({tuple(value) for value in result}):
        raise RuntimeError("exact-N candidate identities repeat")
    return result


def _selected_identities(batch, selected: list[int]) -> list[list[str]]:
    identities = _identities(batch)
    return [identities[index] for index in selected]


def _is_production_legal(lineup: Lineup) -> bool:
    players = list(lineup.players)
    if len(players) != 9 or len(lineup.ids) != 9:
        return False
    salary = sum(int(player["salary"]) for player in players)
    if not 49_000 <= salary <= 50_000:
        return False
    positions = Counter(str(player["pos"]).upper() for player in players)
    if not (
        positions["QB"] == 1 and positions["DST"] == 1
        and 2 <= positions["RB"] <= 3
        and 3 <= positions["WR"] <= 4
        and 1 <= positions["TE"] <= 2
    ):
        return False
    teams = Counter(str(player["team"]) for player in players)
    if max(teams.values(), default=0) > 8:
        return False
    games = {str(player.get("game_id", "")) for player in players
             if str(player.get("game_id", ""))}
    if len(games) < 2:
        return False
    qb = next(player for player in players if str(player["pos"]).upper() == "QB")
    qb_team = str(qb["team"])
    qb_opp = str(qb["opp"])
    catchers = sum(
        str(player["team"]) == qb_team
        and str(player["pos"]).upper() in {"WR", "TE"}
        for player in players
    )
    bring_backs = sum(
        str(player["team"]) == qb_opp
        and str(player["pos"]).upper() in {"RB", "WR", "TE"}
        for player in players
    )
    if catchers < 2 or bring_backs < 1:
        return False
    rbs = [player for player in players if str(player["pos"]).upper() == "RB"]
    if any(count > 1 for count in Counter(
        str(player["team"]) for player in rbs
    ).values()):
        return False
    dst = next(player for player in players if str(player["pos"]).upper() == "DST")
    if any(str(player["team"]) == str(dst["opp"]) for player in rbs):
        return False
    return True


def _production_context(
    canonical,
    canonical_selected: list[int],
    treatment,
    treatment_selected: list[int],
    n_entries: int,
) -> dict[str, Any]:
    control = canonical_selected[:n_entries]
    return {
        "label": "composite-construction-plus-selector-non-gating",
        "control": book_scorefree_metrics(
            np.asarray(canonical.candidate_totals), control,
        ),
        "treatment": book_scorefree_metrics(
            np.asarray(treatment.candidate_totals), treatment_selected,
        ),
        "identity_overlap": len(
            {tuple(value) for value in _selected_identities(canonical, control)}
            & {tuple(value) for value in _selected_identities(
                treatment, treatment_selected,
            )}
        ),
        "gating": False,
    }


def run(output_uri: str) -> dict[str, Any]:
    if output_uri != OUTPUT_URI:
        raise RuntimeError("exact-N output identity differs")
    code_sha = os.environ.get("CODE_SHA", "").strip()
    image = os.environ.get("ANALYSIS_IMAGE", "").strip()
    validate_execution_identity(code_sha, image)
    local_receipts = verify_local_sha256({
        "parent_protocol": (PARENT_PROTOCOL_PATH, PARENT_PROTOCOL_SHA256),
        "source_amendment": (
            SOURCE_AMENDMENT_PATH, SOURCE_AMENDMENT_SHA256,
        ),
        "cbwu_oi_report": (CBWU_REPORT_PATH, CBWU_REPORT_SHA256),
    })
    validate_scorefree_queries()

    source_report = json.loads(CBWU_REPORT_PATH.read_text(encoding="utf-8"))
    if (
        source_report.get("uses_realized_outcomes") is not False
        or source_report.get("aggregate", {}).get(
            "passes_scorefree_gate"
        ) is not True
        or len(source_report.get("slates", [])) != 54
    ):
        raise RuntimeError("exact-N CBWU-OI source did not pass")
    expected_by_slate = {
        (int(row["season"]), int(row["week"])): row
        for row in source_report["slates"]
    }
    if len(expected_by_slate) != 54:
        raise RuntimeError("exact-N CBWU-OI slate keys repeat")

    bq = bigquery.Client(project=PROJECT)
    gcs = storage.Client(project=PROJECT)
    sources = _query(bq, SOURCE_SQL, [bigquery.ArrayQueryParameter(
        "panel_ids", "STRING", list(SOURCE_PANEL_IDS),
    )])
    players = _query(bq, PLAYER_SQL)
    preflight = resolve_panel_artifacts(
        sources.to_dict("records"), panel_ids=SOURCE_PANEL_IDS,
        expected_slates=54,
    )
    if set(players.manifest_sha256.astype(str)) != {FORENSIC_MANIFEST_SHA256}:
        raise RuntimeError("exact-N forensic manifest differs")
    slates = [tuple(int(value) for value in key)
              for key in preflight["slates"]]
    if set(slates) != set(expected_by_slate):
        raise RuntimeError("exact-N source slate population differs")
    source_map = {
        (str(row["panel_run_id"]), int(row["season"]), int(row["week"])): row
        for row in preflight["artifacts"]
    }

    records = []
    artifact_receipts = []
    for season, week in slates:
        catalog = players[
            players.season.astype(int).eq(season)
            & players.week.astype(int).eq(week)
        ].copy()
        books = {}
        for seed, panel_id in enumerate(SOURCE_PANEL_IDS):
            group = sources[
                sources.panel_run_id.astype(str).eq(panel_id)
                & sources.season.astype(int).eq(season)
                & sources.week.astype(int).eq(week)
            ].copy()
            source = source_map[(panel_id, season, week)]
            artifact, receipt = _download_artifact(
                gcs, str(source["uri"]), str(source["sha256"]),
            )
            books[f"R{seed}"] = _candidate_batch(group, artifact, catalog)
            artifact_receipts.append({
                "seed": seed, "panel_run_id": panel_id,
                "season": season, "week": week,
                "candidate_rows": int(source["source_rows"]),
                **receipt,
            })

        order = tuple(books)
        canonical = combine_cbwu_books(
            books, order, expected_worlds_per_book=WORLDS_PER_BLOCK,
        )
        rotations = tuple(order[offset:] + order[:offset] for offset in range(5))
        treatments = [
            combine_cbwu_order_invariant_books(
                books, rotation, tail_line=TAIL_LINE,
                expected_worlds_per_book=WORLDS_PER_BLOCK,
            )
            for rotation in rotations
        ]
        treatment = treatments[0]
        treatment_ids = _identities(treatment)
        if any(
            _identities(batch) != treatment_ids
            or not np.array_equal(
                np.asarray(batch.candidate_totals),
                np.asarray(treatment.candidate_totals),
            )
            for batch in treatments[1:]
        ):
            raise RuntimeError("exact-N OI reconstruction is order-sensitive")
        if len(canonical.candidates) != len(treatment.candidates):
            raise RuntimeError("exact-N candidate budget differs")

        canonical_selected = select_tail_entries(
            np.asarray(canonical.candidate_totals), ENTRY_COUNT, TAIL_LINE,
            env={"SELECT_LSE": "0"},
        )
        treatment_selected = select_tail_entries(
            np.asarray(treatment.candidate_totals), ENTRY_COUNT, TAIL_LINE,
            env={"SELECT_LSE": "0"},
        )
        expected = expected_by_slate[(season, week)]
        if (
            expected.get("order_invariant") is not True
            or _selected_identities(canonical, canonical_selected)
            != expected["control"]["identities"]
            or _selected_identities(treatment, treatment_selected)
            != expected["treatment"]["identities"]
        ):
            raise RuntimeError("exact-N full-book source reproduction differs")
        n80_legal = all(
            _is_production_legal(treatment.candidates[index])
            for index in treatment_selected
        )
        if not n80_legal:
            raise RuntimeError("exact-N source exact-80 book is illegal")

        book_rows = {}
        for n_entries in ENTRY_TARGET_LINES:
            diagnostic = exact_n_scorefree_diagnostic(
                np.asarray(treatment.candidate_totals),
                treatment_selected,
                n_entries,
            )
            selected = diagnostic["treatment"]["selected"]
            diagnostic["control_identities"] = _selected_identities(
                treatment, diagnostic["control"]["selected"],
            )
            diagnostic["treatment_identities"] = _selected_identities(
                treatment, selected,
            )
            diagnostic["treatment_legal"] = all(
                _is_production_legal(treatment.candidates[index])
                for index in selected
            )
            diagnostic["production_context"] = _production_context(
                canonical, canonical_selected, treatment, selected, n_entries,
            )
            book_rows[str(n_entries)] = diagnostic
        records.append({
            "season": season,
            "week": week,
            "uses_realized_outcomes": False,
            "candidate_budget": len(treatment.candidates),
            "n80_parity": True,
            "n80_legal": n80_legal,
            "n80_identities": _selected_identities(
                treatment, treatment_selected,
            ),
            "books": book_rows,
        })

    aggregate = summarize_exact_n_panel(records)
    report = {
        "version": VERSION,
        "code_sha": code_sha,
        "image": image,
        "protocol_sha256": PARENT_PROTOCOL_SHA256,
        "source_amendment_sha256": SOURCE_AMENDMENT_SHA256,
        "cbwu_oi_scorefree_report_sha256": CBWU_REPORT_SHA256,
        "local_source_receipts": local_receipts,
        "forensic_manifest_sha256": FORENSIC_MANIFEST_SHA256,
        "source_panels": list(SOURCE_PANEL_IDS),
        "source_preflight": {
            key: preflight[key]
            for key in ("panel_ids", "slates", "slate_count", "artifact_count")
        },
        "source_artifacts": artifact_receipts,
        "uses_realized_outcomes": False,
        "candidate_or_lineup_scores_read": False,
        "selector_tuned": False,
        "historical_arm_licensed": False,
        "production_change_licensed": False,
        "result": aggregate,
        "slates": records,
        "consequence": (
            "score-free cardinality-specific pre-lock shadow license only; "
            "cannot score historical lineups or change production"
        ),
    }
    payload = (json.dumps(
        report, sort_keys=True, separators=(",", ":"), allow_nan=False,
    ) + "\n").encode("utf-8")
    report["output"] = _upload_create_only(gcs, output_uri, payload)
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-uri", required=True)
    args = parser.parse_args()
    report = run(args.output_uri)
    print(json.dumps({
        "version": report["version"],
        "result": report["result"],
        "output": report["output"],
    }, sort_keys=True))


if __name__ == "__main__":
    main()
