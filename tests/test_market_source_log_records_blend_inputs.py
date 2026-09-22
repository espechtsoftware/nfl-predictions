"""The market-source log must record the blend's INPUTS, not only its output.

Before 2026-09-21 it carried `market_points` and the blended `proj_points` but
nothing of the model side, so reconstructing what the model said meant inverting
the nominal weight. On the Week-2 signals export that inversion disagreed with
the independently recorded pre-blend value on 175 of 175 rows, and for the one
player the post-mortem turns on no pre-blend value existed at all.
"""

import numpy as np
import pandas as pd

from nfl_dfs.inference.market_source import source_log_frame
from nfl_dfs.models.blend import blend


def _sources():
    return pd.DataFrame({
        "gsis_id": ["00-1", "00-2", "00-3"],
        "display_name": ["A", "B", "C"],
        "position": ["WR", "QB", "DST"],
        "source": ["props", "props", "model_only_dst"],
        "market_points": [16.595, 18.380, np.nan],
    })


def test_log_carries_the_model_side_and_the_weight():
    pre = np.array([35.919, 22.560, 7.100])
    w = 0.45
    proj = blend(pre, np.asarray(_sources().market_points, dtype=float), w)
    out = source_log_frame(_sources(), season=2026, week=3, proj_points=proj,
                           model_points_pre=pre, model_weight=w,
                           path="project-slate")
    for col in ("model_points_pre", "model_weight", "market_points", "proj_points"):
        assert col in out.columns, f"{col} missing from the market-source log"
    assert np.allclose(out.model_points_pre.to_numpy(), pre)
    assert (out.model_weight == w).all()


def test_the_row_is_checkable_without_inverting_the_weight():
    """The point of the change: verify the blend forward, from recorded inputs."""
    pre = np.array([35.919, 22.560])
    mkt = np.array([16.595, 18.380])
    w = 0.45
    proj = blend(pre, mkt, w)
    out = source_log_frame(
        _sources().iloc[:2], season=2026, week=3, proj_points=proj,
        model_points_pre=pre, model_weight=w, path="project-slate")
    recomputed = (out.model_weight.to_numpy() * out.model_points_pre.to_numpy()
                  + (1 - out.model_weight.to_numpy()) * out.market_points.to_numpy())
    assert np.allclose(recomputed, out.proj_points.to_numpy()), (
        "recorded inputs do not reproduce the recorded output")


def test_absent_model_side_is_null_not_silently_reconstructed():
    """A caller that does not supply the model side must leave it NULL.

    Filling it by inverting the weight would recreate exactly the defect this
    column exists to end: a derived number indistinguishable from an observed one.
    """
    out = source_log_frame(_sources(), season=2026, week=3,
                           proj_points=np.array([25.291, 20.0, 7.0]),
                           path="project-slate")
    assert out.model_points_pre.isna().all()
    assert out.model_weight.isna().all()


def test_the_projection_run_actually_passes_the_model_side():
    """Pin the WIRING, not just the function.

    Without this, removing `model_points_pre=_pre_blend` from the call site in
    run_projections leaves every other test in this file passing while the
    column lands NULL in production -- the column would exist and be empty,
    which is worse than not having added it. Caught by mutation M4 on
    2026-09-21.
    """
    import ast
    import pathlib

    src = pathlib.Path(
        __import__("nfl_dfs.inference.run_projections", fromlist=["x"]).__file__
    ).read_text()
    calls = [
        n for n in ast.walk(ast.parse(src))
        if isinstance(n, ast.Call)
        and getattr(n.func, "id", getattr(n.func, "attr", None)) == "source_log_frame"
    ]
    assert calls, "run_projections no longer calls source_log_frame at all"
    for call in calls:
        kw = {k.arg for k in call.keywords}
        missing = {"model_points_pre", "model_weight"} - kw
        assert not missing, (
            f"source_log_frame call omits {sorted(missing)}; the market-source "
            "log would record the blend output without its inputs")
        for k in call.keywords:
            if k.arg in ("model_points_pre", "model_weight"):
                assert not isinstance(k.value, ast.Constant) or k.value.value is not None, (
                    f"{k.arg} is passed as a constant None at the call site")
