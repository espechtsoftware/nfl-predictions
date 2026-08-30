#!/usr/bin/env python3
"""Compare old-binary and proved-continuous ATLAS interaction solves."""

from __future__ import annotations

import argparse
from contextlib import contextmanager
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import sys

from google.cloud import bigquery, storage
import pulp


PROJECT = "nfl-predictions-503414"
CODE_SHA = "06797314a0ed423b9f5783fc926b269c1fb24371"
RUNNER_SHA = "0548e26e26d7e81b20c6837adcc8925bc2317f9b7c8586fba084787581cac740"
OPTIMIZER_SHA = "ba5ac3a7c9eb5d436fa6b319e13104b10281fee640c64377904d56c93db65de6"
PROTOCOL_ID = "20260816-atlas-interaction-parity-v1"
PREFIX = (
    "gs://nfl-predictions-503414-raw/research/"
    "atlas-interaction-parity-runs/" + PROTOCOL_ID
)
ALLOWED_CELL = (2024, 15)
SOURCE_SEED = "R0"


def _file_sha(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def _load_books(runner, season: int, week: int):
    bq = bigquery.Client(project=PROJECT)
    gcs = storage.Client(project=PROJECT)
    sources = runner._query(bq, runner.SOURCE_SQL, runner._source_params())
    players = runner._query(bq, runner.PLAYER_SQL, runner._player_params(season))
    sources = sources[
        sources.season.astype(int).eq(season)
        & sources.week.astype(int).eq(week)
    ].copy()
    catalog = players[players.week.astype(int).eq(week)].copy()
    if sources.empty or catalog.empty:
        raise RuntimeError("ATLAS parity source/catalog is empty")
    books = {}
    for seed, expected_panel in zip(
        runner.REGISTERED_SEEDS, runner.SOURCE_PANELS, strict=True,
    ):
        group = sources[
            sources.panel_run_id.astype(str).map(runner._canonical_panel).eq(
                expected_panel
            )
        ].copy()
        uris = group.score_artifact_uri.astype(str).unique()
        digests = group.score_artifact_sha256.astype(str).unique()
        if group.empty or len(uris) != 1 or len(digests) != 1:
            raise RuntimeError("ATLAS parity native source differs")
        artifact, _ = runner._download_artifact(gcs, uris[0], digests[0])
        books[seed] = runner._candidate_batch(group, artifact, catalog)
    return books


@contextmanager
def _interaction_variable_mode(*, force_binary: bool):
    original = pulp.LpVariable
    observed = {
        "variables": 0,
        "declared_categories": set(),
        "effective_categories": set(),
    }

    def wrapped(name, *args, **kwargs):
        if str(name).startswith("interaction_"):
            observed["variables"] += 1
            observed["declared_categories"].add(str(kwargs.get("cat")))
            if force_binary:
                kwargs["cat"] = pulp.LpBinary
            observed["effective_categories"].add(str(kwargs.get("cat")))
        return original(name, *args, **kwargs)

    pulp.LpVariable = wrapped
    try:
        yield observed
    finally:
        pulp.LpVariable = original


def _rosters(additions) -> list[list[str]]:
    return [sorted(str(value) for value in lineup.ids) for lineup in additions]


def _proposal_signature(enumeration: dict) -> list[dict]:
    keys = (
        "pass", "target_cluster", "source_cluster", "world", "stage",
        "accepted", "reason", "roster", "newly_covered_interactions",
        "newly_covered_pairs", "newly_covered_triples",
    )
    return [
        {key: row.get(key) for key in keys if key in row}
        for row in enumeration.get("proposals", [])
    ]


def _digest(value) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    return sha256(raw).hexdigest()


def run(season: int, week: int, output_uri: str) -> dict:
    if (season, week) != ALLOWED_CELL or output_uri != f"{PREFIX}/parity.json":
        raise RuntimeError("ATLAS parity cell/output identity differs")
    image = os.environ.get("ANALYSIS_IMAGE", "")
    if os.environ.get("CODE_SHA") != CODE_SHA or not re.fullmatch(
        r".+@sha256:[0-9a-f]{64}", image,
    ):
        raise RuntimeError("ATLAS parity code/image identity differs")
    for name in (
        "ATLAS_INTERACTION_PARITY_PROTOCOL_SHA256",
        "ATLAS_INTERACTION_PARITY_SOURCE_SHA256",
    ):
        if not re.fullmatch(r"[0-9a-f]{64}", os.environ.get(name, "")):
            raise RuntimeError("ATLAS parity frozen source identity is required")

    scripts = str(Path.cwd() / "scripts")
    if scripts not in sys.path:
        sys.path.insert(0, scripts)
    import run_atlas_matched_diversity_mvp as runner
    import nfl_dfs.optimizer.lineup as optimizer_module

    runner_path = Path(runner.__file__)
    optimizer_path = Path(optimizer_module.__file__)
    if _file_sha(runner_path) != RUNNER_SHA or \
            _file_sha(optimizer_path) != OPTIMIZER_SHA:
        raise RuntimeError("ATLAS parity runner/optimizer source differs")
    runner.validate_local_sources()
    books = _load_books(runner, season, week)
    pricing = runner.price_native_interactions(books)
    nonboom = [
        lineup
        for seed in runner.REGISTERED_SEEDS
        for lineup in books[seed].candidates
        if str(lineup.tag) != "boom"
    ]
    native = books[SOURCE_SEED]
    positions = [str(row.get("pos", "")) for row in native.player_rows]
    bound = runner.roster_slot_upper_bound(native.row_draws, positions)
    world_order = runner.rank_worlds(bound, 40)
    stack = runner.StackRules(qb_stack_min=2, bring_back_min=1)
    env = {"MIN_LINEUP_SALARY": "49000", "MIN_GAMES": "2"}
    exact = runner.solve_exact_worlds(
        native.player_rows, native.row_draws, world_order,
        stack=stack, env=env,
    )
    clusters = runner.build_structural_clusters(world_order, exact)
    common = dict(
        player_rows=native.player_rows,
        row_draws=native.row_draws,
        clusters=clusters,
        exact_worlds=exact,
        interaction_weights=pricing["weights_by_source"][SOURCE_SEED],
        nonboom_lineups=nonboom,
        prior_atlas_rosters=set(),
        stack=stack,
        env=env,
    )
    with _interaction_variable_mode(force_binary=True) as binary_observed:
        binary_additions, binary_enumeration = (
            runner.enumerate_matched_diversity_lineups(**common)
        )
    with _interaction_variable_mode(force_binary=False) as continuous_observed:
        continuous_additions, continuous_enumeration = (
            runner.enumerate_matched_diversity_lineups(**common)
        )

    binary_rosters = _rosters(binary_additions)
    continuous_rosters = _rosters(continuous_additions)
    binary_signature = _proposal_signature(binary_enumeration)
    continuous_signature = _proposal_signature(continuous_enumeration)
    roster_parity = binary_rosters == continuous_rosters
    proposal_parity = binary_signature == continuous_signature
    category_valid = (
        binary_observed["variables"] > 0
        and continuous_observed["variables"] > 0
        and binary_observed["declared_categories"] == {"Continuous"}
        and continuous_observed["declared_categories"] == {"Continuous"}
        and binary_observed["effective_categories"] == {"Binary"}
        and continuous_observed["effective_categories"] == {"Continuous"}
    )
    payload = {
        "version": "atlas-interaction-parity-v1",
        "uses_realized_outcomes": False,
        "persists_lineups": False,
        "production_change_licensed": False,
        "protocol_id": PROTOCOL_ID,
        "protocol_sha256": os.environ[
            "ATLAS_INTERACTION_PARITY_PROTOCOL_SHA256"
        ],
        "diagnostic_source_sha256": os.environ[
            "ATLAS_INTERACTION_PARITY_SOURCE_SHA256"
        ],
        "code_sha": CODE_SHA,
        "analysis_image": image,
        "runner_sha256": RUNNER_SHA,
        "optimizer_sha256": OPTIMIZER_SHA,
        "season": season,
        "week": week,
        "source_seed": SOURCE_SEED,
        "worlds_ranked": len(world_order),
        "binary_candidate_count": len(binary_rosters),
        "continuous_candidate_count": len(continuous_rosters),
        "binary_interaction_variables_constructed": binary_observed["variables"],
        "continuous_interaction_variables_constructed": continuous_observed[
            "variables"
        ],
        "binary_roster_sha256": _digest(binary_rosters),
        "continuous_roster_sha256": _digest(continuous_rosters),
        "binary_proposal_signature_sha256": _digest(binary_signature),
        "continuous_proposal_signature_sha256": _digest(continuous_signature),
        "ordered_roster_parity": roster_parity,
        "proposal_path_parity": proposal_parity,
        "interaction_category_instrumentation_valid": category_valid,
        "passes_parity_gate": bool(roster_parity and proposal_parity and category_valid),
    }
    client = storage.Client(project=PROJECT)
    raw = (json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n").encode()
    upload = runner._upload_create_only(client, output_uri, raw)
    print("ATLAS_INTERACTION_PARITY_RESULT " + json.dumps(upload, sort_keys=True))
    return {**payload, "output": upload}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--season", type=int, required=True)
    parser.add_argument("--week", type=int, required=True)
    parser.add_argument("--output-uri", required=True)
    args = parser.parse_args()
    run(args.season, args.week, args.output_uri)


if __name__ == "__main__":
    main()
