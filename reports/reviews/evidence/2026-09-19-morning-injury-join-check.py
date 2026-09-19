"""Read-only, whole-capture injury join check for the authorized morning refresh."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path

from google.cloud import bigquery

SQL = """
WITH capture AS (
  SELECT * FROM `nfl-predictions-503414.nfl_raw.injury_snapshots`
  WHERE season=2026 AND week=2
    AND pulled_at=(SELECT MAX(pulled_at)
      FROM `nfl-predictions-503414.nfl_raw.injury_snapshots`
      WHERE season=2026 AND week=2)
), matched AS (
  SELECT s.gsis_id, s.report_status, s.pulled_at,
    i.gsis_id AS injury_id, i.injury_status AS injury_status,
    i.injury_snapshot_pulled_at,
    p.gsis_id AS inference_id, p.injury_status AS inference_status
  FROM capture s
  LEFT JOIN `nfl-predictions-503414.nfl_features.player_week_injury` i
    ON s.gsis_id=i.gsis_id AND i.season=2026 AND i.week=2
  LEFT JOIN `nfl-predictions-503414.nfl_features.player_week_inference` p
    ON s.gsis_id=p.gsis_id AND p.season=2026 AND p.week=2
)
SELECT COUNT(*) source_rows, COUNT(DISTINCT gsis_id) source_players,
  COUNTIF(report_status IS NOT NULL) source_designated,
  MAX(pulled_at) source_captured_at,
  COUNTIF(injury_id IS NULL) missing_injury_feature_rows,
  COUNTIF(report_status IS DISTINCT FROM injury_status) injury_status_mismatches,
  COUNTIF(injury_snapshot_pulled_at IS DISTINCT FROM pulled_at) injury_capture_mismatches,
  COUNTIF(inference_id IS NOT NULL) matching_inference_rows,
  COUNTIF(inference_id IS NOT NULL AND report_status IS NOT NULL) expected_inference_designated,
  COUNTIF(inference_id IS NOT NULL AND report_status IS DISTINCT FROM inference_status) inference_status_mismatches,
  (SELECT COUNTIF(injury_status IS NOT NULL)
   FROM `nfl-predictions-503414.nfl_features.player_week_inference`
   WHERE season=2026 AND week=2) actual_inference_designated
FROM matched
"""


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--expect-current', action='store_true')
    args = p.parse_args()
    assert not args.output.exists()
    client = bigquery.Client(project='nfl-predictions-503414')
    job = client.query(SQL, job_config=bigquery.QueryJobConfig(maximum_bytes_billed=2_000_000_000))
    rows = [dict(r) for r in job.result(timeout=120)]
    record = dict(at=datetime.now(timezone.utc), read_only=True, query=SQL,
                  job_id=job.job_id, bytes_processed=job.total_bytes_processed, rows=rows)
    with args.output.open('x') as f:
        json.dump(record, f, indent=2, default=str, allow_nan=False)
    print(json.dumps(record, default=str), flush=True)
    if args.expect_current:
        r = rows[0]
        assert r['source_rows'] == r['source_players'] and r['source_designated'] > 0
        for key in ('missing_injury_feature_rows', 'injury_status_mismatches',
                    'injury_capture_mismatches', 'inference_status_mismatches'):
            assert r[key] == 0, (key, r[key])
        assert r['actual_inference_designated'] >= r['expected_inference_designated'] > 0
        print('CURRENT_CAPTURE_INJURY_JOINS_PASS', flush=True)


if __name__ == '__main__':
    main()
