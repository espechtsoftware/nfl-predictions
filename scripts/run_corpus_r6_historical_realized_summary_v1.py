#!/usr/bin/env python3
"""Build one create-once aggregate companion from the accepted local E0 slice.

The runner is intentionally local and manifest-driven.  It performs no object
listing, network access, scoring, graph access, application mutation, or
threshold selection.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import stat
from collections.abc import Sequence
from pathlib import Path
from typing import Final

from nfl_dfs.research import corpus_r6_historical_neo4j_slice_v1 as historical
from nfl_dfs.research import corpus_r6_historical_realized_summary_v1 as summary

EXPECTED_SLATE_COUNT: Final = historical.EXPECTED_SLATE_COUNT
EXPECTED_EXACT_OBJECT_COUNT: Final = historical.EXPECTED_EXACT_OBJECT_COUNT

_SLATE = r"20[0-9]{2}-w(?:0[1-9]|1[0-8])"
_CANDIDATE_URIS: Final = {
    "candidate_artifact": re.compile(
        rf".*/source-task-(?P<ordinal>[0-9]{{2}})-"
        rf"(?P<slate>{_SLATE})/accepted-candidates\.json$"
    ),
    "exact_occurrence_lineage_sidecar": re.compile(
        rf".*/source-task-(?P<ordinal>[0-9]{{2}})-"
        rf"(?P<slate>{_SLATE})/exact-occurrence-lineage\.json$"
    ),
}
_CATALOG_URI: Final = re.compile(
    rf".*/tasks/(?P<ordinal>[0-9]{{4}})-"
    rf"(?P<slate>{_SLATE})/player-catalog\.json$"
)
_ATTRIBUTION_URI: Final = re.compile(
    rf".*/(?P<filename>(?P<ordinal>[0-9]{{2}})-"
    rf"(?P<slate>{_SLATE})\.json)$"
)
_ROLE_DIRECTORIES: Final = {
    "candidate_artifact": "candidate-artifacts",
    "exact_occurrence_lineage_sidecar": "lineage-sidecars",
    "player_catalog": "player-catalogs-by-slate",
    "attribution_shard": "attribution-shards",
}


class HistoricalRealizedSummaryRunnerError(RuntimeError):
    """The local aggregate runner failed closed."""


def _fail(message: str) -> None:
    raise HistoricalRealizedSummaryRunnerError(message)


def _absolute_lexical(path: Path) -> Path:
    return Path(os.path.abspath(os.fspath(path)))


def _lstat_without_symlinks(path: Path, *, label: str) -> os.stat_result:
    absolute = _absolute_lexical(path)
    current = Path(absolute.anchor)
    try:
        metadata = os.lstat(current)
        for part in absolute.parts[1:]:
            current /= part
            metadata = os.lstat(current)
            if stat.S_ISLNK(metadata.st_mode):
                _fail(f"{label} may not contain a symlink")
    except OSError as exc:
        raise HistoricalRealizedSummaryRunnerError(
            f"{label} could not be inspected"
        ) from exc
    return metadata


class _InputFileRegistry:
    def __init__(self) -> None:
        self._inodes: dict[tuple[int, int], str] = {}

    def directory(self, path: Path, *, label: str) -> Path:
        absolute = _absolute_lexical(path)
        metadata = _lstat_without_symlinks(absolute, label=label)
        if not stat.S_ISDIR(metadata.st_mode):
            _fail(f"{label} must be a regular directory")
        return absolute

    def file(self, path: Path, *, label: str) -> Path:
        absolute = _absolute_lexical(path)
        metadata = _lstat_without_symlinks(absolute, label=label)
        if not stat.S_ISREG(metadata.st_mode):
            _fail(f"{label} must be a regular file")
        if metadata.st_nlink != 1:
            _fail(f"{label} may not be hard-linked")
        inode = (metadata.st_dev, metadata.st_ino)
        previous = self._inodes.get(inode)
        if previous is not None:
            _fail(f"{label} aliases already registered input {previous}")
        self._inodes[inode] = label
        return absolute


def _json_object(path: Path, *, label: str) -> dict[str, object]:
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise HistoricalRealizedSummaryRunnerError(
            f"{label} could not be read"
        ) from exc

    def pairs(rows: list[tuple[str, object]]) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, value in rows:
            if key in result:
                _fail(f"{label} repeats key {key!r}")
            result[key] = value
        return result

    try:
        value = json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=pairs,
            parse_constant=lambda token: _fail(
                f"{label} contains non-finite value {token}"
            ),
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise HistoricalRealizedSummaryRunnerError(
            f"{label} is not valid UTF-8 JSON"
        ) from exc
    if not isinstance(value, dict) or any(type(key) is not str for key in value):
        _fail(f"{label} must be one string-keyed JSON object")
    return dict(value)


def _identity(value: object, *, label: str) -> dict[str, object]:
    if not isinstance(value, dict) or set(value) != {
        "uri",
        "generation",
        "sha256",
        "bytes",
    }:
        _fail(f"{label} identity fields differ")
    identity = dict(value)
    if (
        type(identity["uri"]) is not str
        or not identity["uri"]
        or type(identity["generation"]) is not str
        or not identity["generation"].isdigit()
        or type(identity["sha256"]) is not str
        or len(identity["sha256"]) != 64
        or any(character not in "0123456789abcdef" for character in identity["sha256"])
        or type(identity["bytes"]) is not int
        or identity["bytes"] <= 0
    ):
        _fail(f"{label} identity differs")
    return identity


def _array(value: object, *, label: str) -> list[object]:
    if not isinstance(value, list):
        _fail(f"{label} must be an ordered array")
    return list(value)


def _row(value: object, *, label: str) -> dict[str, object]:
    if not isinstance(value, dict) or any(type(key) is not str for key in value):
        _fail(f"{label} must be a string-keyed object")
    return dict(value)


def _source_ordinal(value: object, *, label: str, width: int) -> int:
    if type(value) is not int or not 0 <= value < EXPECTED_SLATE_COUNT:
        _fail(f"{label} source ordinal differs")
    if len(f"{value:0{width}d}") != width:
        _fail(f"{label} source ordinal width differs")
    return value


class _ExactBundle:
    def __init__(self) -> None:
        self._coordinates: set[tuple[str, int | None]] = set()
        self._identity_keys: set[tuple[str, str, str, int]] = set()
        self._uris: set[str] = set()
        self._entries: dict[tuple[str, int | None], tuple[dict[str, object], Path]] = {}

    def add(
        self,
        *,
        role: str,
        source_ordinal: int | None,
        identity_value: object,
        path: Path,
    ) -> None:
        coordinate = (role, source_ordinal)
        identity = _identity(identity_value, label=f"{role} identity")
        identity_key = (
            str(identity["uri"]),
            str(identity["generation"]),
            str(identity["sha256"]),
            int(identity["bytes"]),
        )
        uri = str(identity["uri"])
        if coordinate in self._coordinates:
            _fail(f"duplicate exact-object coordinate {coordinate!r}")
        if identity_key in self._identity_keys:
            _fail(f"duplicate exact-object identity at {coordinate!r}")
        if uri in self._uris:
            _fail(f"duplicate exact-object URI at {coordinate!r}")
        self._coordinates.add(coordinate)
        self._identity_keys.add(identity_key)
        self._uris.add(uri)
        self._entries[coordinate] = (identity, path)

    def path_for(self, role: str, source_ordinal: int | None) -> Path:
        try:
            return self._entries[(role, source_ordinal)][1]
        except KeyError as exc:
            raise HistoricalRealizedSummaryRunnerError(
                f"exact-object coordinate {(role, source_ordinal)!r} is missing"
            ) from exc

    def exact_objects(self) -> list[historical.ExactJsonFileV1]:
        coordinates: list[tuple[str, int | None]] = [
            ("candidate_v2_root", None),
            ("catalog_outer", None),
            ("no_rescore_funnel_root", None),
        ]
        for ordinal in range(EXPECTED_SLATE_COUNT):
            coordinates.extend(
                (
                    ("candidate_artifact", ordinal),
                    ("exact_occurrence_lineage_sidecar", ordinal),
                    ("player_catalog", ordinal),
                    ("attribution_shard", ordinal),
                )
            )
        if (
            set(coordinates) != self._coordinates
            or len(self._entries) != EXPECTED_EXACT_OBJECT_COUNT
        ):
            _fail("exact 219-object coordinate grid differs")
        return [
            historical.ExactJsonFileV1(*self._entries[coordinate])
            for coordinate in coordinates
        ]


def _manifest_descriptors(
    *,
    candidate_root: dict[str, object],
    catalog_root: dict[str, object],
    funnel_root: dict[str, object],
) -> tuple[
    dict[str, dict[int, tuple[dict[str, object], str]]],
    dict[int, str],
]:
    roles: dict[str, dict[int, tuple[dict[str, object], str]]] = {
        role: {}
        for role in (
            "candidate_artifact",
            "exact_occurrence_lineage_sidecar",
            "player_catalog",
            "attribution_shard",
        )
    }
    slate_ids: dict[int, str] = {}

    candidate_manifest = _array(
        candidate_root.get("non_root_publication_manifest"),
        label="candidate publication manifest",
    )
    for row_ordinal, raw_row in enumerate(candidate_manifest):
        row = _row(raw_row, label=f"candidate publication[{row_ordinal}]")
        role = row.get("role")
        if role not in _CANDIDATE_URIS:
            continue
        ordinal = _source_ordinal(
            row.get("source_task_ordinal"), label=f"candidate {role}", width=2
        )
        identity = _identity(row.get("identity"), label=f"candidate {role}[{ordinal}]")
        match = _CANDIDATE_URIS[str(role)].fullmatch(str(identity["uri"]))
        if match is None or int(match.group("ordinal")) != ordinal:
            _fail(f"candidate {role}[{ordinal}] URI coordinate is unsafe or differs")
        slate_id = match.group("slate")
        if ordinal in slate_ids and slate_ids[ordinal] != slate_id:
            _fail(f"source slate[{ordinal}] differs across manifests")
        slate_ids[ordinal] = slate_id
        if ordinal in roles[str(role)]:
            _fail(f"duplicate candidate {role}[{ordinal}] coordinate")
        roles[str(role)][ordinal] = (identity, f"{ordinal}.json")

    catalog_manifest = _array(
        catalog_root.get("inner_object_manifest"), label="catalog inner manifest"
    )
    for row_ordinal, raw_row in enumerate(catalog_manifest):
        row = _row(raw_row, label=f"catalog manifest[{row_ordinal}]")
        if row.get("role") != "player_catalog":
            continue
        ordinal = _source_ordinal(
            row.get("source_task_ordinal"), label="player catalog", width=4
        )
        identity = _identity(row.get("identity"), label=f"player catalog[{ordinal}]")
        match = _CATALOG_URI.fullmatch(str(identity["uri"]))
        if match is None or int(match.group("ordinal")) != ordinal:
            _fail(f"player catalog[{ordinal}] URI coordinate is unsafe or differs")
        slate_id = match.group("slate")
        if slate_ids.get(ordinal) != slate_id:
            _fail(f"player catalog[{ordinal}] slate differs")
        if ordinal in roles["player_catalog"]:
            _fail(f"duplicate player catalog[{ordinal}] coordinate")
        roles["player_catalog"][ordinal] = (identity, f"{ordinal}.json")

    predecessors = _row(funnel_root.get("predecessors"), label="funnel predecessors")
    attribution_manifest = _array(
        predecessors.get("attribution_shard_identities"),
        label="attribution shard identities",
    )
    for raw_identity in attribution_manifest:
        identity = _identity(raw_identity, label="attribution shard")
        match = _ATTRIBUTION_URI.fullmatch(str(identity["uri"]))
        if match is None:
            _fail("attribution shard URI coordinate is unsafe or differs")
        ordinal = int(match.group("ordinal"))
        _source_ordinal(ordinal, label="attribution shard", width=2)
        if slate_ids.get(ordinal) != match.group("slate"):
            _fail(f"attribution shard[{ordinal}] slate differs")
        if ordinal in roles["attribution_shard"]:
            _fail(f"duplicate attribution shard[{ordinal}] coordinate")
        roles["attribution_shard"][ordinal] = (
            identity,
            match.group("filename"),
        )

    expected = set(range(EXPECTED_SLATE_COUNT))
    if set(slate_ids) != expected or any(
        set(rows) != expected for rows in roles.values()
    ):
        _fail("manifest-derived 54-slate role grid differs")
    return roles, slate_ids


def _exact_role_directory(
    *,
    registry: _InputFileRegistry,
    staging_dir: Path,
    directory_name: str,
    expected_names: set[str],
    label: str,
) -> dict[str, Path]:
    directory = registry.directory(
        staging_dir / directory_name, label=f"{label} directory"
    )
    try:
        with os.scandir(directory) as entries:
            observed_names = {entry.name for entry in entries}
    except OSError as exc:
        raise HistoricalRealizedSummaryRunnerError(
            f"{label} directory could not be enumerated"
        ) from exc
    if observed_names != expected_names:
        missing = sorted(expected_names - observed_names)
        extra = sorted(observed_names - expected_names)
        _fail(f"{label} entries differ: missing={missing!r}, extra={extra!r}")
    return {
        name: registry.file(directory / name, label=f"{label} {name}")
        for name in sorted(expected_names)
    }


def _prepare_bundle(
    *,
    staging_dir: Path,
    candidate_root_identity_path: Path,
    funnel_reopen_summary_path: Path,
    accepted_e0_receipt_path: Path,
) -> tuple[
    list[historical.ExactJsonFileV1],
    dict[str, object],
    dict[str, object],
    dict[str, object],
    bytes,
    bytes,
    _InputFileRegistry,
]:
    registry = _InputFileRegistry()
    staging = registry.directory(staging_dir, label="staging directory")
    candidate_identity_file = registry.file(
        candidate_root_identity_path, label="candidate root identity"
    )
    funnel_reopen_file = registry.file(
        funnel_reopen_summary_path, label="funnel reopen summary"
    )
    accepted_receipt_file = registry.file(
        accepted_e0_receipt_path, label="accepted E0 receipt"
    )
    candidate_root_path = registry.file(
        staging / "candidate-authority-release-v2.json",
        label="candidate terminal root",
    )
    catalog_root_path = registry.file(
        staging / "fixed-g0-catalog-recovery-attestation-v2.json",
        label="catalog terminal root",
    )
    funnel_root_path = registry.file(
        staging / "no-rescore-funnel-release.json",
        label="no-rescore funnel terminal root",
    )

    candidate_identity = _identity(
        _json_object(candidate_identity_file, label="candidate root identity"),
        label="candidate root",
    )
    funnel_reopen = _json_object(funnel_reopen_file, label="funnel reopen summary")
    funnel_identity = _identity(
        funnel_reopen.get("funnel_release_identity"), label="funnel root"
    )
    candidate_root = _json_object(candidate_root_path, label="candidate terminal root")
    catalog_identity = _identity(
        candidate_root.get("catalog_recovery_outer_identity"),
        label="catalog outer root",
    )
    catalog_root = _json_object(catalog_root_path, label="catalog terminal root")
    funnel_root = _json_object(funnel_root_path, label="funnel terminal root")
    roles, _ = _manifest_descriptors(
        candidate_root=candidate_root,
        catalog_root=catalog_root,
        funnel_root=funnel_root,
    )

    local_paths: dict[str, dict[str, Path]] = {}
    for role, directory_name in _ROLE_DIRECTORIES.items():
        expected_names = {filename for _, filename in roles[role].values()}
        local_paths[role] = _exact_role_directory(
            registry=registry,
            staging_dir=staging,
            directory_name=directory_name,
            expected_names=expected_names,
            label=role.replace("_", " "),
        )

    bundle = _ExactBundle()
    bundle.add(
        role="candidate_v2_root",
        source_ordinal=None,
        identity_value=candidate_identity,
        path=candidate_root_path,
    )
    bundle.add(
        role="catalog_outer",
        source_ordinal=None,
        identity_value=catalog_identity,
        path=catalog_root_path,
    )
    bundle.add(
        role="no_rescore_funnel_root",
        source_ordinal=None,
        identity_value=funnel_identity,
        path=funnel_root_path,
    )
    for role, rows in roles.items():
        for ordinal in range(EXPECTED_SLATE_COUNT):
            identity, filename = rows[ordinal]
            bundle.add(
                role=role,
                source_ordinal=ordinal,
                identity_value=identity,
                path=local_paths[role][filename],
            )
    exact_objects = bundle.exact_objects()
    try:
        accepted_receipt_raw = accepted_receipt_file.read_bytes()
        funnel_raw = funnel_root_path.read_bytes()
    except OSError as exc:
        raise HistoricalRealizedSummaryRunnerError(
            "bound local source bytes could not be read"
        ) from exc
    return (
        exact_objects,
        candidate_identity,
        catalog_identity,
        funnel_identity,
        accepted_receipt_raw,
        funnel_raw,
        registry,
    )


def _output_path(path: Path, *, staging_dir: Path) -> Path:
    absolute = _absolute_lexical(path)
    parent = absolute.parent
    parent_metadata = _lstat_without_symlinks(parent, label="output parent")
    if not stat.S_ISDIR(parent_metadata.st_mode):
        _fail("output parent must be a regular directory")
    if absolute.exists() or absolute.is_symlink():
        _fail("refusing to overwrite existing output")
    staging = _absolute_lexical(staging_dir)
    if absolute == staging or absolute.is_relative_to(staging):
        _fail("output must be outside the immutable staging directory")
    return absolute


def _write_create_once(path: Path, value: object) -> None:
    raw = summary.canonical_json_bytes(value) + b"\n"
    try:
        with path.open("xb") as handle:
            handle.write(raw)
            handle.flush()
            os.fsync(handle.fileno())
    except FileExistsError as exc:
        raise HistoricalRealizedSummaryRunnerError(
            "refusing to overwrite existing output"
        ) from exc
    except OSError as exc:
        raise HistoricalRealizedSummaryRunnerError(
            "create-once output could not be written"
        ) from exc


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--staging-dir", type=Path, required=True)
    parser.add_argument("--candidate-root-identity", type=Path, required=True)
    parser.add_argument("--funnel-reopen-summary", type=Path, required=True)
    parser.add_argument("--accepted-e0-receipt", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        output = _output_path(args.output, staging_dir=args.staging_dir)
        (
            exact_objects,
            candidate_identity,
            catalog_identity,
            funnel_identity,
            accepted_receipt_raw,
            funnel_raw,
            _,
        ) = _prepare_bundle(
            staging_dir=args.staging_dir,
            candidate_root_identity_path=args.candidate_root_identity,
            funnel_reopen_summary_path=args.funnel_reopen_summary,
            accepted_e0_receipt_path=args.accepted_e0_receipt,
        )
        plan = historical.build_historical_corpus_graph_plan_v1(
            exact_objects=exact_objects,
            candidate_root_identity=candidate_identity,
            catalog_outer_identity=catalog_identity,
            attribution_root_identity=funnel_identity,
        )
        result = summary.build_historical_realized_summary_v1(
            accepted_e0_receipt_raw=accepted_receipt_raw,
            no_rescore_funnel_raw=funnel_raw,
            e0_plan=plan,
        )
        _write_create_once(output, result)
    except HistoricalRealizedSummaryRunnerError as exc:
        raise SystemExit(str(exc)) from exc
    print(
        json.dumps(
            {
                "schema_version": result["schema_version"],
                "summary_sha256": result["summary_sha256"],
                "complete": result["complete"],
            },
            sort_keys=True,
            separators=(",", ":"),
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
