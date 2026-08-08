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
    sub.add_parser("ingest-contests",
                   help="Poll DK contest fill rates for overlay detection "
                        "(scaffold, needs INGEST_CONTESTS_ENABLED)")
    sub.add_parser("ingest-cfb",
                   help="Poll DK college football draft groups/draftables + "
                        "contest fills (collection-only scaffold, needs "
                        "INGEST_CFB_ENABLED)")
    sub.add_parser("ingest-odds",
                   help="Snapshot DK game lines via The Odds API")
    sub.add_parser("check-freshness",
                   help="Fail if any active data feed is stale (see status.py)")
    sub.add_parser("backup-tables",
                   help="Daily snapshots of irreplaceable tables (30-day "
                        "retention, ops/backup.py)")
    p = sub.add_parser("field-calibration",
                       help="Score our field sim's dupe/salary realism vs a "
                            "real imported contest (ops/field_calibration.py)")
    p.add_argument("--season", type=int, required=True)
    p.add_argument("--week", type=int, required=True)
    p.add_argument("--contest-id", required=True)
    p.add_argument("--sims", type=int, default=20_000)
    sub.add_parser("train-ownership",
                   help="Fit ownership model on imported contest standings "
                        "(in-season; see issue #11)")
    sub.add_parser("score-entries",
                   help="Score last week's entered lineups vs actuals")
    sub.add_parser("ingest-props", help="Snapshot live prop lines (in-season)")
    sub.add_parser("ingest-weather", help="Fetch Open-Meteo forecasts for upcoming games")

    p = sub.add_parser("backfill-rotoguru", help="One-time historical DK salary backfill")
    p.add_argument("--first-season", type=int, default=2014)

    p = sub.add_parser("build-features", help="Run feature SQL + leakage checks")
    p.add_argument("--skip-leakage", action="store_true")

    sub.add_parser("train", help="Weekly retrain + registry write")
    sub.add_parser("project", help="Project the upcoming slate")

    p = sub.add_parser("trends", help="Changepoint detection + salary-lag watchlist")
    p.add_argument("--season", type=int, default=None)

    p = sub.add_parser("pricing-lag",
                       help="DK salary-vs-trailing-production residual watchlist")
    p.add_argument("--season", type=int, required=True)
    p.add_argument("--week", type=int, required=True)

    p = sub.add_parser("replay",
                       help="Replay a past season: projection accuracy + contest ROI")
    p.add_argument("--season", type=int, required=True)
    p.add_argument("--sims", type=int, default=10_000)
    p.add_argument("--entries", type=int, default=40)
    p.add_argument("--contest", choices=["gpp", "double_up"], default="gpp")
    p.add_argument("--field-size", type=int, default=5_000)
    p.add_argument("--sharp", type=float, default=0.15,
                   help="Fraction of the simulated field built by optimizer")
    p.add_argument("--tail-line", type=float, default=None,
                   help="GPP entry selection maximizes P(best >= this "
                        "score); default 194 for gpp, 0 disables")
    p.add_argument("--max-weeks", type=int, default=None,
                   help="audit smoke only: stop contest replay after N weeks")

    sub.add_parser("schaake-smoke",
                   help="Run image-level Schaake mechanism invariants")

    p = sub.add_parser("import-discoverylab",
                       help="Backfill real DK salaries from DiscoveryLab (free tier: last season)")
    p.add_argument("--first-season", type=int, default=2025)
    p.add_argument("--last-season", type=int, default=2025)

    p = sub.add_parser("import-discoverylab-showdown",
                       help="Backfill Captain Mode slates (salaries + actuals) from DiscoveryLab")
    p.add_argument("--first-season", type=int, default=2025)
    p.add_argument("--last-season", type=int, default=2025)

    p = sub.add_parser("replay-showdown",
                       help="Replay Captain Mode: entries vs hindsight-optimal per slate")
    p.add_argument("--season", type=int, default=2025)
    p.add_argument("--entries", type=int, default=40)
    p.add_argument("--days", default="thu,mon")

    p = sub.add_parser("import-prop-lines",
                       help="Backfill player-prop lines from The Odds API")
    p.add_argument("--first-season", type=int, default=2023)
    p.add_argument("--last-season", type=int, default=2025)

    p = sub.add_parser("import-ownership",
                       help="Import a DK contest-standings CSV (actual ownership)")
    p.add_argument("path")
    p.add_argument("--season", type=int, required=True)
    p.add_argument("--week", type=int, required=True)
    p.add_argument("--contest-id", required=True)
    p.add_argument("--contest-name", default=None)

    p = sub.add_parser(
        "leaderboard-analysis",
        help="Analyze captured top entries and player appearances for a contest",
    )
    p.add_argument("--season", type=int, required=True)
    p.add_argument("--week", type=int, required=True)
    p.add_argument("--contest-id", required=True)
    p.add_argument("--top-n", type=int, default=20)

    p = sub.add_parser(
        "missed-player-analysis",
        help="Attribute high-scoring unselected players in an accepted replay panel",
    )
    p.add_argument("--panel", required=True)
    p.add_argument("--threshold", type=float, default=20.0)

    p = sub.add_parser(
        "archetype-panel-analysis",
        help="Run same-slate matched controls for breakout states in a panel",
    )
    p.add_argument("--panel", required=True)
    p.add_argument("--threshold", type=float, default=20.0)

    p = sub.add_parser("archetypes",
                       help="Cluster scoring-consistency archetypes into nfl_features")
    p.add_argument("--seasons", type=int, default=3, help="Trailing seasons to profile")
    p.add_argument("--min-games", type=int, default=16)

    p = sub.add_parser("serve", help="Run the FastAPI app")
    p.add_argument("--port", type=int, default=8080)

    args = parser.parse_args(argv)

    if args.command == "ingest-nflverse":
        from .ingest import nflverse_job

        nflverse_job.run(full_refresh=args.full)
    elif args.command == "ingest-dk":
        from .ingest import dk_job

        dk_job.run()
    elif args.command == "ingest-contests":
        from .ingest import contest_job

        contest_job.run()
    elif args.command == "ingest-cfb":
        from .ingest import cfb_job

        cfb_job.run()
    elif args.command == "ingest-odds":
        from .ingest import odds_job

        odds_job.run()
    elif args.command == "check-freshness":
        from . import status

        status.check_freshness()
    elif args.command == "backup-tables":
        from .ops import backup

        backup.run()
    elif args.command == "field-calibration":
        from .ops import field_calibration

        field_calibration.run(args.season, args.week, args.contest_id,
                              n_sims=args.sims)
    elif args.command == "train-ownership":
        from .models import ownership

        ownership.run_training()
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
    elif args.command == "pricing-lag":
        from .models import pricing_lag

        pricing_lag.run(args.season, args.week)
    elif args.command == "replay":
        from .backtest import payout, replay

        contest = payout.gpp() if args.contest == "gpp" else payout.double_up()
        replay.run(args.season, n_sims=args.sims, contest=contest,
                   n_entries=args.entries, field_size=args.field_size,
                   sharp_fraction=args.sharp, tail_line=args.tail_line,
                   max_weeks=args.max_weeks)
    elif args.command == "schaake-smoke":
        from .research.schaake_diag import cloud_smoke

        cloud_smoke()
    elif args.command == "import-discoverylab":
        from .ingest import discoverylab_import

        discoverylab_import.run(first_season=args.first_season,
                                last_season=args.last_season)
    elif args.command == "import-discoverylab-showdown":
        from .ingest import discoverylab_import

        discoverylab_import.run_showdown(first_season=args.first_season,
                                         last_season=args.last_season)
    elif args.command == "replay-showdown":
        from .backtest import showdown_replay

        showdown_replay.run(season=args.season, n_entries=args.entries,
                            days=args.days)
    elif args.command == "score-entries":
        from .config import current_season
        from . import notes as _n
        from .bq import query_df as _q
        from .config import settings as _s

        season = current_season()
        wk = _q(f"SELECT MAX(week) AS w FROM `{_s.features}.team_defense_week`"
                f" WHERE season={season}")
        if wk.w.iloc[0] is not None:
            print(_n.score_entries(season, int(wk.w.iloc[0])))
    elif args.command == "ingest-props":
        from .ingest import oddsapi_import

        oddsapi_import.run_live()
    elif args.command == "import-prop-lines":
        from .ingest import oddsapi_import

        oddsapi_import.run(first_season=args.first_season,
                           last_season=args.last_season)
    elif args.command == "import-ownership":
        from .ingest import ownership_import

        ownership_import.run(args.path, season=args.season, week=args.week,
                             contest_id=args.contest_id,
                             contest_name=args.contest_name)
    elif args.command == "archetypes":
        from .analysis import archetypes

        archetypes.run(trailing_seasons=args.seasons, min_games=args.min_games)
    elif args.command == "leaderboard-analysis":
        from .analysis import leaderboard

        print(leaderboard.run(args.season, args.week, args.contest_id,
                              top_n=args.top_n))
    elif args.command == "missed-player-analysis":
        from .analysis import leaderboard

        print(leaderboard.run_missed_panel(args.panel,
                                            actual_threshold=args.threshold))
    elif args.command == "archetype-panel-analysis":
        from .analysis import archetype_research

        print(archetype_research.run(args.panel, tail=args.threshold))
    elif args.command == "serve":
        import uvicorn

        uvicorn.run("nfl_dfs.app.main:app", host="0.0.0.0", port=args.port)


if __name__ == "__main__":
    main()
