#!/usr/bin/env python3
"""Publish or exact-reopen the deterministic R6 no-rescore funnel.

This guarded transport can read only generation-pinned objects named by the
terminal attribution release and the tracked winner-registry authority.  It
does not query an outcome source, rescore a lineup, mutate the graph, or alter
any served strategy.  Publication is create-once and an existing object is
accepted only when its bytes are identical to the deterministic rebuild.
"""

from __future__ import annotations

import argparse
from hashlib import sha256
import json
import os
from pathlib import Path
import re
from typing import Mapping

from nfl_dfs.research import corpus_r6_no_rescore_funnel_v1 as funnel


PROJECT = "nfl-predictions-503414"
OUTPUT_BUCKET = "nfl-predictions-503414-corpus-retrieval"
OUTPUT_NAMESPACE = "research/corpus-r6-no-rescore-funnels"
ROOT_FILENAME = "no-rescore-funnel-release.json"
ENABLED_ENV = "R6_NO_RESCORE_FUNNEL_ENABLED"
CREATE_ONCE_ATTEMPTS = 3
ATTRIBUTION_ROOT_IDENTITY = {
    "uri": (
        "gs://nfl-predictions-503414-corpus-retrieval/research/"
        "corpus-r6-full-union-attributions/"
        "20260827-foundry-v12-r6-full-union-attribution-v1/"
        "attribution-release.json"
    ),
    "generation": "1787852572673874",
    "sha256": "caaddba5ef709b1e4df8c60480e2a50a37063917ef9b8d3c788f5e107133722b",
    "bytes": 114_551,
}
WINNER_REGISTRY_AUTHORITY_FILE_SHA256 = (
    "e761be802242a4b6a28ba61abaf386871a9e0e88136d50b199f4f8b04150cb10"
)
REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_AUTHORITY_PATH = REPO_ROOT / Path(
    "reports/r6-no-rescore-funnel-runs/"
    "20260827-r6-no-rescore-funnel-v1/winner-registry-authority.json"
)
_RUN_ID = re.compile(r"^[a-z0-9][a-z0-9-]{7,80}$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")


class RunCorpusR6NoRescoreFunnelV1Error(ValueError):
    """The guarded no-rescore funnel transport failed closed."""


def _fail(message: str) -> None:
    raise RunCorpusR6NoRescoreFunnelV1Error(message)


def _identity(
    *, uri: str, generation: str, sha256_value: str, bytes_value: int,
) -> dict[str, object]:
    if (
        not uri.startswith("gs://")
        or "//" in uri[5:]
        or not generation.isdigit()
        or generation.startswith("0")
        or int(generation) <= 0
        or _SHA256.fullmatch(sha256_value) is None
        or type(bytes_value) is not int
        or bytes_value < 1
    ):
        _fail("object identity differs")
    return {
        "uri": uri,
        "generation": generation,
        "sha256": sha256_value,
        "bytes": bytes_value,
    }


def _gcs_parts(uri: str) -> tuple[str, str]:
    if not uri.startswith("gs://") or "/" not in uri[5:] or "//" in uri[5:]:
        _fail("object URI must be canonical GCS")
    bucket, name = uri[5:].split("/", 1)
    if not bucket or not name:
        _fail("object URI must be canonical GCS")
    return bucket, name


def _not_found(exc: Exception) -> bool:
    code = getattr(exc, "code", None)
    return (
        code == 404
        or callable(code) and code() == 404
        or type(exc).__name__ == "NotFound"
    )


class GenerationPinnedGCSV1:
    """Minimal generation-pinned reader and create-once publisher."""

    def __init__(self, client: object) -> None:
        self.client = client

    def read_exact(self, identity_value: Mapping[str, object]) -> bytes:
        identity = _identity(
            uri=str(identity_value.get("uri")),
            generation=str(identity_value.get("generation")),
            sha256_value=str(identity_value.get("sha256")),
            bytes_value=identity_value.get("bytes"),
        )
        bucket_name, object_name = _gcs_parts(str(identity["uri"]))
        generation = int(str(identity["generation"]))
        try:
            blob = self.client.bucket(bucket_name).blob(
                object_name, generation=generation
            )
            blob.reload(if_generation_match=generation)
            raw = blob.download_as_bytes(if_generation_match=generation)
        except Exception as exc:
            raise RunCorpusR6NoRescoreFunnelV1Error(
                "generation-pinned object read failed"
            ) from exc
        if (
            type(raw) is not bytes
            or str(blob.generation) != identity["generation"]
            or len(raw) != identity["bytes"]
            or sha256(raw).hexdigest() != identity["sha256"]
        ):
            _fail("generation-pinned object content differs")
        return raw

    def _resolve_current(
        self, uri: str, *, absent_ok: bool,
    ) -> tuple[dict[str, object], bytes] | None:
        bucket_name, object_name = _gcs_parts(uri)
        try:
            current = self.client.bucket(bucket_name).blob(object_name)
            current.reload()
        except Exception as exc:
            if absent_ok and _not_found(exc):
                return None
            raise RunCorpusR6NoRescoreFunnelV1Error(
                "current object resolution failed"
            ) from exc
        generation = str(current.generation)
        if not generation.isdigit() or int(generation) <= 0:
            _fail("current object generation differs")
        try:
            pinned = self.client.bucket(bucket_name).blob(
                object_name, generation=int(generation)
            )
            pinned.reload(if_generation_match=int(generation))
            raw = pinned.download_as_bytes(if_generation_match=int(generation))
        except Exception as exc:
            raise RunCorpusR6NoRescoreFunnelV1Error(
                "current generation reopen failed"
            ) from exc
        if type(raw) is not bytes or not raw:
            _fail("current object is empty")
        identity = _identity(
            uri=uri,
            generation=generation,
            sha256_value=sha256(raw).hexdigest(),
            bytes_value=len(raw),
        )
        return identity, raw

    def publish_create_once(self, uri: str, raw: bytes) -> dict[str, object]:
        if type(raw) is not bytes or not raw:
            _fail("publication bytes differ")
        bucket_name, object_name = _gcs_parts(uri)
        for _attempt in range(CREATE_ONCE_ATTEMPTS):
            try:
                blob = self.client.bucket(bucket_name).blob(object_name)
                blob.upload_from_string(
                    raw,
                    content_type="application/json",
                    if_generation_match=0,
                )
            except Exception:
                # A collision or ambiguous transport result is resolved solely
                # by generation-pinned byte equality; no overwrite is allowed.
                pass
            reopened = self._resolve_current(uri, absent_ok=True)
            if reopened is None:
                continue
            identity, existing = reopened
            if existing != raw:
                _fail("existing create-once object differs")
            return identity
        _fail("create-once object remains absent after bounded attempts")


def _authority(path: Path) -> dict[str, object]:
    try:
        raw = path.read_bytes()
        value = json.loads(raw)
    except (OSError, json.JSONDecodeError) as exc:
        raise RunCorpusR6NoRescoreFunnelV1Error(
            "winner-registry authority read failed"
        ) from exc
    if (
        sha256(raw).hexdigest() != WINNER_REGISTRY_AUTHORITY_FILE_SHA256
        or not isinstance(value, dict)
        or funnel.canonical_json_bytes(value) + b"\n" != raw
    ):
        _fail("winner-registry authority must be canonical JSON plus one newline")
    return funnel.validate_winner_registry_authority_v1(value)


def _root_uri(run_id: str) -> str:
    if _RUN_ID.fullmatch(run_id) is None:
        _fail("output run ID differs")
    return f"gs://{OUTPUT_BUCKET}/{OUTPUT_NAMESPACE}/{run_id}/{ROOT_FILENAME}"


def _validate_root_uri(uri: str) -> str:
    prefix = f"gs://{OUTPUT_BUCKET}/{OUTPUT_NAMESPACE}/"
    suffix = f"/{ROOT_FILENAME}"
    if not uri.startswith(prefix) or not uri.endswith(suffix):
        _fail("funnel root URI differs from the governed namespace")
    run_id = uri[len(prefix):-len(suffix)]
    if uri != _root_uri(run_id):
        _fail("funnel root URI differs from the governed namespace")
    return uri


def _attribution_identity(args: argparse.Namespace) -> dict[str, object]:
    retained = _identity(
        uri=args.attribution_root_uri,
        generation=args.attribution_root_generation,
        sha256_value=args.attribution_root_sha256,
        bytes_value=args.attribution_root_bytes,
    )
    if retained != ATTRIBUTION_ROOT_IDENTITY:
        _fail("attribution root differs from the adopted terminal release")
    return retained


def _summary(
    *, command: str, release_value: Mapping[str, object], identity: Mapping[str, object],
) -> dict[str, object]:
    predecessors = dict(release_value["predecessors"])  # type: ignore[arg-type]
    authority = dict(predecessors["winner_registry_authority"])  # type: ignore[arg-type]
    return {
        "schema_version": "corpus-r6-no-rescore-funnel-cli-summary/v1",
        "command": command,
        "funnel_release_identity": dict(identity),
        "funnel_release_sha256": release_value["funnel_release_sha256"],
        "attribution_release_root_identity": predecessors[
            "attribution_release_root_identity"
        ],
        "winner_registry_identity": predecessors["winner_registry_identity"],
        "winner_registry_authority_sha256": authority[
            "winner_registry_authority_sha256"
        ],
        "source_slate_count": release_value["source_slate_count"],
        "lineup_count": release_value["population_result"]["lineup_count"],
        "winner_target_included_slates": release_value["winner_target_census"][
            "included_slate_count"
        ],
        "uses_realized_outcomes": True,
        "lineup_rescore_performed": False,
        "outcome_source_read": False,
        "graph_mutation_performed": False,
        "production_change_performed": False,
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--execute", action="store_true")
    common.add_argument("--project", default=PROJECT)
    common.add_argument(
        "--winner-registry-authority",
        type=Path,
        default=DEFAULT_AUTHORITY_PATH,
    )
    common.add_argument("--attribution-root-uri", required=True)
    common.add_argument("--attribution-root-generation", required=True)
    common.add_argument("--attribution-root-sha256", required=True)
    common.add_argument("--attribution-root-bytes", type=int, required=True)
    subparsers = parser.add_subparsers(dest="command", required=True)
    publish = subparsers.add_parser("publish", parents=[common])
    publish.add_argument("--output-run-id", required=True)
    reopen = subparsers.add_parser("reopen", parents=[common])
    reopen.add_argument("--funnel-root-uri", required=True)
    reopen.add_argument("--funnel-root-generation", required=True)
    reopen.add_argument("--funnel-root-sha256", required=True)
    reopen.add_argument("--funnel-root-bytes", type=int, required=True)
    return parser


def main() -> None:
    args = _parser().parse_args()
    if args.execute is not True or os.environ.get(ENABLED_ENV) != "1":
        _fail(f"execution requires --execute and {ENABLED_ENV}=1")
    if args.project != PROJECT:
        _fail("cloud project differs")
    try:
        from google.cloud import storage
    except ImportError as exc:  # pragma: no cover - environment integration
        raise RunCorpusR6NoRescoreFunnelV1Error(
            "google-cloud-storage is required"
        ) from exc
    store = GenerationPinnedGCSV1(storage.Client(project=args.project))
    attribution_identity = _attribution_identity(args)
    authority = _authority(args.winner_registry_authority)
    if args.command == "publish":
        built = funnel.build_no_rescore_funnel_release_v1(
            attribution_release_root_identity=attribution_identity,
            winner_registry_authority=authority,
            read_exact=store.read_exact,
        )
        raw = funnel.canonical_json_bytes(built)
        identity = store.publish_create_once(_root_uri(args.output_run_id), raw)
    else:
        identity = _identity(
            uri=_validate_root_uri(args.funnel_root_uri),
            generation=args.funnel_root_generation,
            sha256_value=args.funnel_root_sha256,
            bytes_value=args.funnel_root_bytes,
        )
    reopened, reopened_identity = funnel.reopen_no_rescore_funnel_release_v1(
        identity,
        attribution_release_root_identity=attribution_identity,
        winner_registry_authority=authority,
        read_exact=store.read_exact,
    )
    print(json.dumps(
        _summary(
            command=args.command,
            release_value=reopened,
            identity=reopened_identity,
        ),
        sort_keys=True,
        separators=(",", ":"),
    ))


if __name__ == "__main__":
    main()
