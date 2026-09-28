"""Cash shadow arm B (reports/lab-handoffs/cash_shadow_paper.py): the conversion shift touches only live-priced rows."""
import importlib.util
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

_P = Path(__file__).resolve().parents[1] / "reports" / "lab-handoffs" / "cash_shadow_paper.py"
_spec = importlib.util.spec_from_file_location("cash_shadow_paper", _P)
csp = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(csp)


def test_shift_is_market_weight_times_the_conversion_difference_on_live_priced_rows_only():
    fr = pd.DataFrame({"gsis_id": ["a", "b", "c", "d"], "market_points": [10.0, np.nan, 8.0, 5.0],
                       "proj": [12.0, 9.0, 7.0, 4.0]})
    plain, conv = {"a": 10.0, "b": 6.0, "c": 8.0}, {"a": 11.0, "b": 9.0, "c": 7.0}   # d has no offline price
    delta, rec = csp.conversion_shift(fr, plain, conv)
    assert delta.tolist() == pytest.approx([0.55, 0.0, -0.55, 0.0])       # b was not priced live; d not offline
    assert rec == {"rows_priced_live": 3, "rows_shifted": 2, "rows_priced_live_without_offline_price": 1,
                   "mean_shift_on_shifted": 0.0}
