"""Contest payout curves. ROI is the only metric that pays (guide §10):
a model with worse RMSE can have better ROI if its ceilings are calibrated.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class Contest:
    name: str
    entry_fee: float
    field_size: int
    # (top_fraction_of_field, multiple_of_entry_fee) tiers, best first.
    tiers: tuple[tuple[float, float], ...]

    def payout_for_rank(self, rank: int) -> float:
        """rank is 1-based; returns dollars won."""
        frac = rank / self.field_size
        cum = 0.0
        for top_frac, mult in self.tiers:
            cum += top_frac
            if frac <= cum + 1e-12:
                return self.entry_fee * mult
        return 0.0


def double_up(entry_fee: float = 5.0, field_size: int = 10_000) -> Contest:
    """Cash game: top ~45% roughly doubles (rake-adjusted)."""
    return Contest("double-up", entry_fee, field_size, ((0.45, 2.0),))


def gpp(entry_fee: float = 5.0, field_size: int = 100_000) -> Contest:
    """Stylized winner-take-most tournament curve, ~15% of field paid,
    ~85% of the prize pool concentrated up top."""
    return Contest(
        "gpp",
        entry_fee,
        field_size,
        (
            (0.00001, 20000.0),   # 1st
            (0.00009, 2000.0),
            (0.0009, 200.0),
            (0.009, 20.0),
            (0.04, 5.0),
            (0.10, 2.0),
        ),
    )


def roi(winnings: np.ndarray, entry_fee: float) -> float:
    """Aggregate return on investment across entries."""
    w = np.asarray(winnings, dtype=float)
    staked = entry_fee * len(w)
    return float((w.sum() - staked) / staked) if staked else 0.0
