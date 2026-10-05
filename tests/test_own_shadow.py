"""own_shadow rows name their writer (2026-10-05, O-27 follow-up).

Until then every reader took a week's latest generation of ANY writer, so the last
job to write -- a Sunday shadow, a Thursday suite -- silently became "the" pre-lock
ownership prediction. These tests pin the writer column end to end, the reader
pattern, and that the column is additive in both deploy orders.
"""
from __future__ import annotations

import pandas as pd
import pytest
from google.cloud.bigquery import SchemaField
from google.cloud.bigquery import _pandas_helpers

from nfl_dfs.inference import live_lineups, own_shadow

STAMP = pd.Timestamp("2026-10-11T14:00:00Z")
LEGACY_COLUMNS = ["generated_at", "season", "week", "gsis_id", "name", "pos", "salary",
                  "n_pool", "pred_own", "source", "booster_own"]


def _frame():
    return pd.DataFrame({"gsis_id": ["00-1", "00-2"], "name": ["A", "B"],
                         "pos": ["QB", "WR"], "salary": [6000, 5000]})


def _rows(**kw):
    args = dict(booster_own=None, writer=own_shadow.WRITER_APP, run_type=None,
                generated_at=STAMP)
    args.update(kw)
    return own_shadow.ownership_shadow_frame(_frame(), [0.2, 0.1], "naive", 2026, 5, **args)


def test_rows_carry_writer_and_run_type():
    rows = _rows(run_type="live")
    assert list(rows.columns) == LEGACY_COLUMNS + ["writer", "run_type"]
    assert rows.writer.tolist() == ["app_build_classic"] * 2
    assert rows.run_type.tolist() == ["live"] * 2
    assert str(rows.writer.dtype) == "string" and str(rows.run_type.dtype) == "string"


@pytest.mark.parametrize("writer", [None, "", "   ", 7])
def test_a_row_without_a_writer_is_refused(writer):
    with pytest.raises(ValueError, match="non-empty writer"):
        _rows(writer=writer)


def test_default_writer_names_the_build():
    assert own_shadow.default_writer("live_shadow") == "build_sim_lineups:live_shadow"
    assert own_shadow.default_writer(None) == "build_sim_lineups:unlabelled"


def test_reader_selects_one_writer_and_its_latest_generation():
    sql, params = own_shadow.latest_generation_sql("p.d.own_shadow", writer="app_build_classic")
    assert "writer = @writer" in sql and params == {"writer": "app_build_classic"}
    assert "season = @season AND week = @week" in sql
    assert "QUALIFY generated_at = MAX(generated_at) OVER ()" in sql
    legacy, params = own_shadow.latest_generation_sql("p.d.own_shadow", writer=None)
    assert "writer IS NULL" in legacy and params == {}
    with pytest.raises(ValueError):
        own_shadow.latest_generation_sql("p.d.own_shadow", writer="")


def test_logger_writes_the_writer_and_run_type(monkeypatch):
    written = []

    class Now:
        def __init__(self, target, daemon):
            self.target = target

        def start(self):
            self.target()

    monkeypatch.setattr("threading.Thread", Now)
    monkeypatch.setattr("nfl_dfs.bq.load_dataframe",
                        lambda df, table, write_disposition: written.append((df, table)))
    live_lineups._log_ownership_shadow(
        _frame(), [0.2, 0.1], "booster", 2026, 5,
        writer="app_build_classic", run_type="live")
    (df, table), = written
    assert table.endswith(".own_shadow")
    assert df.writer.tolist() == ["app_build_classic"] * 2
    assert df.run_type.tolist() == ["live"] * 2
    assert df.booster_own.tolist() == [0.2, 0.1]


def test_logger_requires_a_writer_keyword():
    with pytest.raises(TypeError):
        live_lineups._log_ownership_shadow(_frame(), [0.2, 0.1], "naive", 2026, 5)


def test_build_sim_lineups_hands_its_writer_and_run_type_to_the_slate_build(monkeypatch):
    seen = {}

    class Stop(Exception):
        pass

    def fake_slate(*args, **kwargs):
        seen.update(kwargs)
        raise Stop

    monkeypatch.setattr(live_lineups, "build_slate_with_draws", fake_slate)
    with pytest.raises(Stop):
        live_lineups.build_sim_lineups(2026, 5, n_entries=1, stack=None, tail_line=194.0,
                                       candidate_run_type="live",
                                       own_shadow_writer="app_build_classic")
    assert seen["own_shadow_writer"] == "app_build_classic"
    assert seen["own_shadow_run_type"] == "live"
    assert seen["log_ownership_shadow"] is True


def test_the_app_names_itself_on_both_build_paths():
    from pathlib import Path

    src = (Path(__file__).resolve().parents[1] / "src/nfl_dfs/app/main.py").read_text()
    assert src.count("own_shadow_writer=WRITER_APP") == 2


def test_the_generation_suite_names_itself():
    from pathlib import Path

    src = (Path(__file__).resolve().parents[1]
           / "src/nfl_dfs/inference/prospective_generation_shadow_suite.py").read_text()
    assert "own_shadow_writer=WRITER_GENERATION_SUITE" in src


# --- the ALTER is additive in both deploy orders -----------------------------------
# google-cloud-bigquery's load_table_from_dataframe (WRITE_APPEND) builds the job schema
# from the destination table's fields THAT ARE IN THE DATAFRAME, then detects the rest
# from dtypes; nfl_dfs.bq.load_dataframe adds ALLOW_FIELD_ADDITION. Reproduce both steps.

def _job_schema(df, table_fields):
    present = {name for name, _ in _pandas_helpers.list_columns_and_indexes(df)}
    selected = [SchemaField(f.name, f.field_type, mode=f.mode)
                for f in table_fields if f.name in present]
    return _pandas_helpers.dataframe_to_bq_schema(df, selected)


TABLE_BEFORE = [SchemaField("generated_at", "TIMESTAMP"), SchemaField("season", "INTEGER"),
                SchemaField("week", "INTEGER"), SchemaField("gsis_id", "STRING"),
                SchemaField("name", "STRING"), SchemaField("pos", "STRING"),
                SchemaField("salary", "INTEGER"), SchemaField("n_pool", "INTEGER"),
                SchemaField("pred_own", "FLOAT"), SchemaField("source", "STRING"),
                SchemaField("booster_own", "FLOAT")]
TABLE_AFTER = TABLE_BEFORE + [SchemaField("writer", "STRING"), SchemaField("run_type", "STRING")]


def test_old_image_against_the_altered_table_omits_the_nullable_columns():
    legacy = _rows()[LEGACY_COLUMNS]
    schema = _job_schema(legacy, TABLE_AFTER)
    assert [f.name for f in schema] == LEGACY_COLUMNS          # writer/run_type omitted
    assert all(f.mode == "NULLABLE" for f in TABLE_AFTER[-2:])  # so BigQuery fills NULL


def test_new_image_against_the_altered_table_uses_its_string_columns():
    schema = {f.name: f.field_type for f in _job_schema(_rows(), TABLE_AFTER)}
    assert schema["writer"] == "STRING" and schema["run_type"] == "STRING"


def test_new_image_against_the_unaltered_table_detects_string_columns():
    """If the ALTER were missed, ALLOW_FIELD_ADDITION adds the columns as STRING --
    including run_type when every value is missing."""
    schema = {f.name: f.field_type for f in _job_schema(_rows(run_type=None), TABLE_BEFORE)}
    assert schema["writer"] == "STRING" and schema["run_type"] == "STRING"


# --- the Wednesday rehearsal script -----------------------------------------------

def _rehearsal():
    import importlib.util
    from pathlib import Path

    path = Path(__file__).resolve().parents[1] / "scripts/own_shadow_write_rehearsal.py"
    spec = importlib.util.spec_from_file_location("own_shadow_write_rehearsal", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("name", ["own_shadow", "own_shadow_rehearsal", "x_own_shadow_rehearsal_20261007",
                                  "own_shadow_rehearsal_20261007;DROP"])
def test_rehearsal_refuses_anything_but_a_scratch_table(name):
    with pytest.raises(SystemExit, match="refusing destination"):
        _rehearsal().run(name, load=lambda *a, **k: None, query=lambda *a: None)


def test_rehearsal_writes_one_legacy_and_one_new_row_to_the_scratch_copy():
    mod = _rehearsal()
    loads, sqls = [], []

    def query(sql):
        sqls.append(sql)
        if "INFORMATION_SCHEMA" in sql:
            return pd.DataFrame({"column_name": LEGACY_COLUMNS + ["writer", "run_type"]})
        if sql.startswith("SELECT IFNULL"):
            return pd.DataFrame({"writer": ["<NULL>", "rehearsal_scratch"],
                                 "run_type": [None, "rehearsal"], "n": [1, 1]})
        return pd.DataFrame()

    out = mod.run("own_shadow_rehearsal_20261007",
                  load=lambda df, table, write_disposition: loads.append((df, table, write_disposition)),
                  query=query, now=STAMP.to_pydatetime())
    assert out["ok"] is True
    # Hermetic (2026-10-04): the project comes from config (GCP_PROJECT), which the Cloud Build lane does not set.
    from nfl_dfs.config import settings
    ds = settings.predictions
    assert (f"CREATE TABLE `{ds}.own_shadow_rehearsal_20261007` "
            f"LIKE `{ds}.own_shadow`") in sqls
    (legacy, t1, d1), (new, t2, d2) = loads
    assert t1 == t2 == f"{ds}.own_shadow_rehearsal_20261007"
    assert d1 == d2 == "WRITE_APPEND"
    assert list(legacy.columns) == LEGACY_COLUMNS
    assert new.writer.tolist() == ["rehearsal_scratch"]


def test_rehearsal_stops_before_writing_if_the_alter_is_missing():
    mod = _rehearsal()
    loads = []
    with pytest.raises(SystemExit, match="run the ALTER first"):
        mod.run("own_shadow_rehearsal_20261007", load=lambda *a, **k: loads.append(a),
                query=lambda sql: pd.DataFrame({"column_name": LEGACY_COLUMNS}))
    assert loads == []
