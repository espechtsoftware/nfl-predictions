#!/usr/bin/env python3
"""Validate the isolated PIT-clean registry without reading outcomes."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from google.cloud import storage

from nfl_dfs.models.components import COMPONENT_NAMES


ROLE_FEATURES = {
    "target_share_last", "carry_share_last", "snap_share_last",
    "target_share_jump", "carry_share_jump", "snap_share_jump",
}
VARIANTS = {
    "canonical": ("", 3),
    "tail_k1": ("__tail_k1", 1),
    "tail_k1_role": ("__tail_k1_role", 1),
}


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", required=True)
    parser.add_argument("--prefix", default="models_pit_v2")
    parser.add_argument("--iso-week", required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    bucket = storage.Client(project=args.project).bucket(f"{args.project}-raw")
    checks: dict[str, bool] = {}
    artifacts: dict[str, dict] = {}
    feature_sets: dict[str, set[str]] = {}
    for variant, (suffix, ensemble_size) in VARIANTS.items():
        variant_artifacts: dict[str, dict] = {}
        variant_features: set[str] | None = None
        for component in COMPONENT_NAMES:
            label = f"comp_{component}{suffix}"
            base = f"{args.prefix}/pooled/{label}/{args.iso_week}"
            meta_blob = bucket.blob(f"{base}/meta.json")
            meta_exists = meta_blob.exists()
            checks[f"{variant}_{component}_meta"] = meta_exists
            if not meta_exists:
                continue
            meta = json.loads(meta_blob.download_as_text())
            features = set(meta.get("features", []))
            if variant_features is None:
                variant_features = features
            checks[f"{variant}_{component}_feature_consistency"] = (
                features == variant_features
            )
            files = [meta_blob]
            if ensemble_size == 1:
                model = bucket.blob(f"{base}/model.txt")
                checks[f"{variant}_{component}_single_model"] = model.exists()
                files.append(model)
            else:
                descriptor = bucket.blob(f"{base}/ensemble.json")
                descriptor_ok = descriptor.exists()
                if descriptor_ok:
                    descriptor_ok = json.loads(
                        descriptor.download_as_text()).get("k") == ensemble_size
                checks[f"{variant}_{component}_ensemble_descriptor"] = descriptor_ok
                files.append(descriptor)
                for index in range(ensemble_size):
                    member = bucket.blob(f"{base}/member_{index}.txt")
                    checks[f"{variant}_{component}_member_{index}"] = member.exists()
                    files.append(member)
            variant_artifacts[component] = {
                blob.name: {
                    "generation": int(blob.generation) if blob.generation else None,
                    "md5_hash": blob.md5_hash,
                    "crc32c": blob.crc32c,
                }
                for blob in files if blob.exists()
            }
        feature_sets[variant] = variant_features or set()
        artifacts[variant] = variant_artifacts

    checks["k3_k1_feature_contract_equal"] = (
        feature_sets["canonical"] == feature_sets["tail_k1"]
        and bool(feature_sets["canonical"])
    )
    checks["role_adds_exact_registered_features"] = (
        feature_sets["tail_k1_role"] - feature_sets["tail_k1"] == ROLE_FEATURES
        and feature_sets["tail_k1"] < feature_sets["tail_k1_role"]
    )
    normalized = {name: bool(value) for name, value in checks.items()}
    passes = all(normalized.values())
    report = {
        "disposition": (
            "pit-clean-registry-qualified" if passes
            else "pit-clean-registry-invalid"
        ),
        "passes": passes,
        "project": args.project,
        "prefix": args.prefix,
        "iso_week": args.iso_week,
        "checks": normalized,
        "feature_counts": {
            variant: len(features) for variant, features in feature_sets.items()
        },
        "artifacts": artifacts,
    }
    args.output.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    if not passes:
        raise SystemExit("ABORT: isolated PIT-clean registry validation failed")
    print(f"PIT_REGISTRY_QUALIFIED {args.output}")


if __name__ == "__main__":
    main()
