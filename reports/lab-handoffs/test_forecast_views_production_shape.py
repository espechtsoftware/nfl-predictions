"""The view-3 case their fixture cannot reach.

Written by the production side 2026-09-21 against nfl2 b6acbb2c. Their
tests/test_forecast_views.py passes (verified here, 2 passed) but its fixture
sets `proj` and `mean_projection` 1.0 apart on every row. Per their own
pipeline.py:162, production has `proj` EQUAL to `mean_projection` except in the
punt band -- so that fixture describes a frame production never produces, and
the assertion `served70_mean25_30 == [9.7, 19.7]` can only hold there.

The first test below fails on b6acbb2c and should pass once view 3 fails closed
on a missing `mean25` the way view 2 already does on `model_points_pre`.
"""

import pandas as pd
import pytest

from nfl2.forecast_views import build_forecast_views


def _production_shaped():
    """Above the punt band, production `proj` IS `mean_projection`."""
    return pd.DataFrame({
        "id": ["a", "b"],
        "proj": [10.0, 20.0],
        "model_points_pre": [8.0, 18.0],
        "mean_projection": [10.0, 20.0],   # equal, as production has them
        "proj_p90": [15.0, 25.0],
    })


def test_history_blend_is_not_a_byte_copy_of_served():
    """`mean25` exists nowhere in this codebase, so the fallback always fires.

    With production-shaped inputs that makes 0.70*served + 0.30*mean_projection
    exactly served, and the arm spends a generation budget on a duplicate of its
    own control while reporting it as a treatment. Fail closed instead, as view
    2 now does.
    """
    views, _ = build_forecast_views(_production_shaped())
    assert not views["served70_mean25_30"]["proj"].equals(views["served"]["proj"]), (
        "served70_mean25_30 is identical to served: mean25 is absent and "
        "mean_projection is not a historical mean"
    )


def test_absent_history_column_fails_closed():
    """Same rule view 2 already follows: a missing required column stops the run."""
    frame = _production_shaped().drop(columns=["mean_projection"])
    with pytest.raises(ValueError, match="mean"):
        build_forecast_views(frame)
