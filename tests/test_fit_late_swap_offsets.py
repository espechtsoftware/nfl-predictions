import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from fit_late_swap_offsets import fit_offsets  # noqa: E402


def _ladder(entries, *tiers):
    return {"entries": entries, "payoutSummary": [{"minPosition": a, "maxPosition": b, "payoutDescriptions": [{"value": v}]}
                                                  for a, b, v in tiers]}


def test_offsets_per_type_flat_only():
    milly = np.arange(1, 1001, dtype=float)                                # quantile q -> about 1 + 999 q
    layout = [{"cid": "s1", "name": "sat20"}, {"cid": "s2", "name": "sat20"}, {"cid": "s1", "name": "sat20"},
              {"cid": "m", "name": "milly"}]
    details = {"s1": _ladder(10, (1, 1, 20.0)), "s2": _ladder(10, (1, 1, 20.0)),
               "m": _ladder(1000, (1, 1, 1e6), (2, 100, 30.0))}          # top-heavy: never fitted
    pts = {"s1": np.array([950.0, 10.0, 5.0]), "s2": np.array([3.0, 931.0]), "m": milly}
    fit = fit_offsets(layout, details, pts, milly)
    q = float(np.quantile(milly, 0.9))
    assert set(fit) == {10, "pooled"} and fit[10]["n"] == 2                 # keyed by field size; s1 once; no Millionaire
    assert abs(fit[10]["offset"] - round(((950 - q) + (931 - q)) / 2, 2)) < 1e-9 and fit["pooled"]["n"] == 2
