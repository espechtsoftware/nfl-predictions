"""Model registry (guide §7.8): every trained model written to
`{root}/{scope}/{label}/{iso_week}/model.txt` plus a JSON sidecar with
hyperparameters, features, training seasons, and validation metrics.
`model_version` is stamped on every prediction row — when a week goes
badly you must be able to answer "which model made this call and what
did it see."

Root can be a local path (tests, dev) or `gs://bucket/prefix` (prod).
"""

from __future__ import annotations

import json
import tempfile
from dataclasses import asdict, dataclass, field
from pathlib import Path

import lightgbm as lgb

_MODEL_FILE = "model.txt"
_META_FILE = "meta.json"


@dataclass
class ModelMeta:
    scope: str
    label: str
    iso_week: str
    params: dict = field(default_factory=dict)
    features: list[str] = field(default_factory=list)
    train_seasons: list[int] = field(default_factory=list)
    metrics: dict = field(default_factory=dict)


def _is_gcs(root: str) -> bool:
    return root.startswith("gs://")


def _bucket_and_prefix(root: str):
    from google.cloud import storage

    bucket_name, _, prefix = root.removeprefix("gs://").partition("/")
    return storage.Client().bucket(bucket_name), prefix.rstrip("/")


def model_params(model) -> dict:
    """Return auditable registry metadata for a booster or ensemble.

    A single LightGBM booster exposes a flat ``params`` mapping.  The adopted
    component ensemble is a wrapper, so its parameters live on its members.
    Keep that distinction explicit in the sidecar instead of assuming every
    prediction-compatible object is itself a LightGBM Booster.
    """
    members = getattr(model, "members", None)
    if members is None:
        return dict(model.params)
    return {
        "model_type": "ensemble",
        "ensemble_size": len(members),
        "members": [
            {
                "index": i,
                "class": type(member).__name__,
                "params": dict(getattr(member, "params", {})),
            }
            for i, member in enumerate(members)
        ],
    }


def save(model, meta: ModelMeta, root: str) -> str:
    """Write model + sidecar; returns the version string scope/label/iso_week.
    Ensembles (objects with .members, MODEL_ENSEMBLE lever) persist as
    member_<i>.txt + ensemble.json so the weekly retrain and live load
    round-trip them transparently."""
    version = f"{meta.scope}/{meta.label}/{meta.iso_week}"
    meta_json = json.dumps(asdict(meta), indent=2, default=str)

    members = getattr(model, "members", None)
    if _is_gcs(root):
        bucket, prefix = _bucket_and_prefix(root)
        base = f"{prefix}/{version}" if prefix else version
        if members is not None:
            for i, m in enumerate(members):
                with tempfile.NamedTemporaryFile(suffix=".txt") as tmp:
                    m.save_model(tmp.name)
                    bucket.blob(f"{base}/member_{i}.txt"
                                ).upload_from_filename(tmp.name)
            bucket.blob(f"{base}/ensemble.json").upload_from_string(
                json.dumps({"k": len(members)}))
        else:
            with tempfile.NamedTemporaryFile(suffix=".txt") as tmp:
                model.save_model(tmp.name)
                bucket.blob(f"{base}/{_MODEL_FILE}").upload_from_filename(tmp.name)
        bucket.blob(f"{base}/{_META_FILE}").upload_from_string(meta_json)
    else:
        d = Path(root) / version
        d.mkdir(parents=True, exist_ok=True)
        if members is not None:
            for i, m in enumerate(members):
                m.save_model(str(d / f"member_{i}.txt"))
            (d / "ensemble.json").write_text(json.dumps({"k": len(members)}))
            (d / _META_FILE).write_text(meta_json)
            return version
        model.save_model(str(d / _MODEL_FILE))
        (d / _META_FILE).write_text(meta_json)
    return version


def load(root: str, scope: str, label: str, iso_week: str) -> tuple[lgb.Booster, ModelMeta]:
    version = f"{scope}/{label}/{iso_week}"
    if _is_gcs(root):
        bucket, prefix = _bucket_and_prefix(root)
        base = f"{prefix}/{version}" if prefix else version
        ens_blob = bucket.blob(f"{base}/ensemble.json")
        if ens_blob.exists():
            k = json.loads(ens_blob.download_as_text())["k"]
            members = []
            for i in range(k):
                with tempfile.NamedTemporaryFile(suffix=".txt") as tmp:
                    bucket.blob(f"{base}/member_{i}.txt"
                                ).download_to_filename(tmp.name)
                    members.append(lgb.Booster(model_file=tmp.name))
            from .components import _EnsembleBooster

            model = _EnsembleBooster(members)
        else:
            with tempfile.NamedTemporaryFile(suffix=".txt") as tmp:
                bucket.blob(f"{base}/{_MODEL_FILE}").download_to_filename(tmp.name)
                model = lgb.Booster(model_file=tmp.name)
        meta_raw = bucket.blob(f"{base}/{_META_FILE}").download_as_text()
    else:
        d = Path(root) / version
        if (d / "ensemble.json").exists():
            k = json.loads((d / "ensemble.json").read_text())["k"]
            from .components import _EnsembleBooster

            model = _EnsembleBooster([
                lgb.Booster(model_file=str(d / f"member_{i}.txt"))
                for i in range(k)])
        else:
            model = lgb.Booster(model_file=str(d / _MODEL_FILE))
        meta_raw = (d / _META_FILE).read_text()
    return model, ModelMeta(**json.loads(meta_raw))


def latest_iso_week(root: str, scope: str, label: str) -> str:
    """Most recent registered week for scope/label. ISO week strings
    (2025-W09) sort lexicographically, so max() is latest."""
    if _is_gcs(root):
        bucket, prefix = _bucket_and_prefix(root)
        base = f"{prefix}/{scope}/{label}/" if prefix else f"{scope}/{label}/"
        weeks = {
            blob.name.removeprefix(base).split("/")[0]
            for blob in bucket.client.list_blobs(bucket, prefix=base)
        }
    else:
        d = Path(root) / scope / label
        weeks = {p.name for p in d.iterdir() if p.is_dir()} if d.is_dir() else set()
    if not weeks:
        raise FileNotFoundError(f"no registered models under {root}/{scope}/{label}")
    return max(weeks)
