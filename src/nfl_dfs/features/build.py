"""Feature build runner: executes sql/features/*.sql in numeric order, then
runs the leakage assertions. Fails loudly — a broken feature build must never
silently feed stale projections.

Schedule: daily 07:00 CT and after each DK pull.
"""

from __future__ import annotations

import logging
import sys

from ..bq import SQL_DIR, run_sql_file
from .leakage import (
    SMOOTHING_PRIOR_K,
    run_leakage_checks,
    run_team_qb_quality_checks,
)

log = logging.getLogger(__name__)

# Empirical-Bayes prior weight, in games, for red zone smoothing (guide §5.2;
# tune on validation — typical optimum 3-5).
PRIOR_K = SMOOTHING_PRIOR_K


def run(check_leakage: bool = True) -> None:
    feature_sql = sorted((SQL_DIR / "features").glob("*.sql"))
    if not feature_sql:
        raise FileNotFoundError(f"No feature SQL found under {SQL_DIR / 'features'}")
    for path in feature_sql:
        run_sql_file(path, prior_k=PRIOR_K)
    if check_leakage:
        run_leakage_checks()


def run_team_qb_quality() -> None:
    """Build and independently validate only the research side table."""
    path = SQL_DIR / "features" / "017l_team_qb_quality.sql"
    run_sql_file(path, prior_k=PRIOR_K)
    run_team_qb_quality_checks()
    print("TEAM_QB_QUALITY_SIDE_TABLE_VALIDATED")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run(check_leakage="--skip-leakage" not in sys.argv)
