"""Command-line entry points: `nfl-dfs <command>`.

Thin wrappers over the job modules so everything Cloud Scheduler runs can
also be run by hand.
"""

from __future__ import annotations

import argparse
import logging


def main(argv: list[str] | None = None) -> None:
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(name)s %(levelname)s %(message)s")
    parser = argparse.ArgumentParser(prog="nfl-dfs")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("ingest-nflverse", help="Load nflverse data into nfl_raw")
    p.add_argument("--full", action="store_true", help="Backfill 1999-present")

    sub.add_parser("ingest-dk", help="Snapshot current DK slates/salaries")
    sub.add_parser("ingest-odds", help="Snapshot DK sportsbook game lines")
    sub.add_parser("ingest-weather", help="Fetch Open-Meteo forecasts for upcoming games")

    p = sub.add_parser("backfill-rotoguru", help="One-time historical DK salary backfill")
    p.add_argument("--first-season", type=int, default=2014)

    p = sub.add_parser("build-features", help="Run feature SQL + leakage checks")
    p.add_argument("--skip-leakage", action="store_true")

    sub.add_parser("train", help="Weekly retrain + registry write")
    sub.add_parser("project", help="Project the upcoming slate")

    p = sub.add_parser("trends", help="Changepoint detection + salary-lag watchlist")
    p.add_argument("--season", type=int, default=None)

    p = sub.add_parser("serve", help="Run the FastAPI app")
    p.add_argument("--port", type=int, default=8080)

    args = parser.parse_args(argv)

    if args.command == "ingest-nflverse":
        from .ingest import nflverse_job

        nflverse_job.run(full_refresh=args.full)
    elif args.command == "ingest-dk":
        from .ingest import dk_job

        dk_job.run()
    elif args.command == "ingest-odds":
        from .ingest import odds_job

        odds_job.run()
    elif args.command == "ingest-weather":
        from .ingest import weather_job

        weather_job.run()
    elif args.command == "backfill-rotoguru":
        from .ingest import rotoguru_backfill

        rotoguru_backfill.run(first_season=args.first_season)
    elif args.command == "build-features":
        from .features import build

        build.run(check_leakage=not args.skip_leakage)
    elif args.command == "train":
        from .models import train_job

        train_job.train_and_register()
    elif args.command == "project":
        from .inference import run_projections

        run_projections.run()
    elif args.command == "trends":
        from .config import current_season
        from .trends import alerts

        alerts.run(args.season or current_season())
    elif args.command == "serve":
        import uvicorn

        uvicorn.run("nfl_dfs.app.main:app", host="0.0.0.0", port=args.port)


if __name__ == "__main__":
    main()
