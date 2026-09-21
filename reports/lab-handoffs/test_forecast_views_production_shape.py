"""SUPERSEDED 2026-09-21 by nfl2 `1c25e2a2` — do not adopt as originally written.

The original first test here asserted that `served70_mean25_30` must differ from
`served` on a production-shaped frame, where `proj == mean_projection`. That was
the right defect and the wrong remedy: the lab's fix refuses outright when
`mean25` is absent, rather than making the view differ, which is stronger. With
that fix in place the original test FAILS — correctly — because the function
now raises instead of returning a degraded view.

Adopting it unchanged would put a red test in front of whoever next touches this
file, for a defect that is already closed. It is retired here.

What survives is the fail-closed test below, which agrees with the lab's own
`test_missing_historical_mean_fails_closed`. Both are kept because they assert
the same rule from opposite directions: theirs supplies no `mean25` at all,
this one supplies the `mean_projection` column specifically, pinning that the
alias substitution never comes back.
"""

import pandas as pd
import pytest

from nfl2.forecast_views import build_forecast_views


def test_mean_projection_is_not_accepted_as_a_mean25_alias():
    """`mean_projection` is the current 0.45 model + 0.55 market blend, and per
    pipeline.py:162 `proj` equals it except in the punt band. Accepting it as a
    stand-in made view 3 a byte-copy of the control above $4,000. A frame that
    carries `mean_projection` but not `mean25` must still fail closed.
    """
    frame = pd.DataFrame({
        "id": ["a", "b"],
        "proj": [10.0, 20.0],
        "model_points_pre": [8.0, 18.0],
        "mean_projection": [10.0, 20.0],   # present, and equal to proj as production has it
        "proj_p90": [15.0, 25.0],
    })
    with pytest.raises(ValueError, match="mean25"):
        build_forecast_views(frame)
