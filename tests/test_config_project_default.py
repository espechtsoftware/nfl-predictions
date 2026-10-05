"""O-31: with GCP_PROJECT unset, config targets the real project, never the nonexistent nfl-dfs-prod."""
import importlib
import os


def test_default_project_and_bucket_are_the_real_ones(monkeypatch):
    monkeypatch.delenv("GCP_PROJECT", raising=False)
    monkeypatch.delenv("GCS_BUCKET", raising=False)
    import nfl_dfs.config as C
    s = C.Settings()
    assert s.project == "nfl-predictions-503414" == C.DEFAULT_PROJECT
    assert s.gcs_bucket == "nfl-predictions-503414-raw"
    assert not [line for line in open(C.__file__) if "os.environ.get" in line and "nfl-dfs-prod" in line]


def test_env_still_wins(monkeypatch):
    monkeypatch.setenv("GCP_PROJECT", "some-other-project")
    import nfl_dfs.config as C
    assert C.Settings().project == "some-other-project"
