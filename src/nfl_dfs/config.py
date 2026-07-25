"""Central configuration, driven by environment variables.

Everything that differs between local dev and Cloud Run lives here so the
rest of the codebase never reads os.environ directly.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path


def _load_dotenv(path: str = ".env") -> None:
    """Minimal .env support: KEY=VALUE lines from the working directory,
    never overriding variables already set in the real environment. The
    file is gitignored; it's where local secrets and API keys live."""
    p = Path(path)
    if not p.is_file():
        return
    for line in p.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip("'\""))


_load_dotenv()


@dataclass(frozen=True)
class Settings:
    project: str = field(default_factory=lambda: os.environ.get("GCP_PROJECT", "nfl-dfs-prod"))
    location: str = field(default_factory=lambda: os.environ.get("BQ_LOCATION", "US"))
    raw_dataset: str = field(default_factory=lambda: os.environ.get("BQ_RAW_DATASET", "nfl_raw"))
    features_dataset: str = field(
        default_factory=lambda: os.environ.get("BQ_FEATURES_DATASET", "nfl_features")
    )
    predictions_dataset: str = field(
        default_factory=lambda: os.environ.get("BQ_PREDICTIONS_DATASET", "nfl_predictions")
    )
    # Default follows deploy/setup_gcp.sh's convention: ${PROJECT}-raw.
    gcs_bucket: str = field(
        default_factory=lambda: os.environ.get(
            "GCS_BUCKET",
            f"{os.environ.get('GCP_PROJECT', 'nfl-dfs-prod')}-raw",
        )
    )
    model_registry_prefix: str = field(
        default_factory=lambda: os.environ.get("MODEL_REGISTRY_PREFIX", "models")
    )
    # Backfill start. PBP exists back to 1999, but training only uses 2015+
    # (below), so default to one season of feature run-up before that; set
    # FIRST_SEASON=1999 if you want deep history for exploration.
    first_season: int = field(default_factory=lambda: int(os.environ.get("FIRST_SEASON", "2014")))
    # Seasons used for model training; PBP exists to 1999 but DK salaries only to 2014.
    train_first_season: int = field(
        default_factory=lambda: int(os.environ.get("TRAIN_FIRST_SEASON", "2015"))
    )

    @property
    def raw(self) -> str:
        return f"{self.project}.{self.raw_dataset}"

    @property
    def features(self) -> str:
        return f"{self.project}.{self.features_dataset}"

    @property
    def predictions(self) -> str:
        return f"{self.project}.{self.predictions_dataset}"


def current_season(today: date | None = None) -> int:
    """NFL season year; rolls over in March."""
    t = today or date.today()
    return t.year if t.month >= 3 else t.year - 1


settings = Settings()
