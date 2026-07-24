import json
from datetime import datetime, timedelta, timezone

import pandas as pd

from nfl_dfs.graph import news


def raw_llm_output():
    return json.dumps([
        {"player": "Beta Receiver Jr.", "claim_type": "role_change",
         "direction": 1, "confidence": 0.8,
         "quote": "coach wants him more involved in the red zone"},
        {"player": "Alpha Receiver", "claim_type": "injury_status",
         "direction": -1, "confidence": 0.9, "quote": "did not practice"},
        # Invalid rows the parser must drop:
        {"player": "Bad Type", "claim_type": "vibes", "direction": 1,
         "confidence": 0.5, "quote": "x"},
        {"player": "Bad Direction", "claim_type": "role_change",
         "direction": 2, "confidence": 0.5, "quote": "x"},
        {"player": "", "claim_type": "role_change", "direction": 1,
         "confidence": 0.5, "quote": "x"},
    ])


def id_map():
    return pd.DataFrame({
        "display_name": ["Beta Receiver", "Alpha Receiver"],
        "gsis_id": ["WR2", "WR1"],
    })


def test_parse_claims_enforces_schema():
    claims = news.parse_claims(raw_llm_output(), "beat-writer",
                               "2025-09-16T12:00:00Z", 0.7)
    assert len(claims) == 2
    assert {c.claim_type for c in claims} == {"role_change", "injury_status"}


def test_parse_claims_garbage_returns_empty():
    assert news.parse_claims("no json here", "s", "2025-01-01T00:00:00Z", 0.5) == []
    assert news.parse_claims("[{broken", "s", "2025-01-01T00:00:00Z", 0.5) == []


def test_entity_resolution_strips_suffixes():
    claims = news.parse_claims(raw_llm_output(), "beat-writer",
                               "2025-09-16T12:00:00Z", 0.7)
    resolved = news.resolve_entities(claims, id_map())
    by_player = {c.player: c.gsis_id for c in resolved}
    assert by_player["Beta Receiver Jr."] == "WR2"   # suffix stripped
    assert by_player["Alpha Receiver"] == "WR1"


def test_signal_features_decay_and_direction():
    now = datetime(2025, 9, 18, tzinfo=timezone.utc)
    fresh = (now - timedelta(days=1)).isoformat()
    stale = (now - timedelta(days=12)).isoformat()
    claims = news.parse_claims(raw_llm_output(), "beat", fresh, 0.8)
    claims += news.parse_claims(raw_llm_output(), "beat", stale, 0.8)
    resolved = news.resolve_entities(claims, id_map())
    feats = news.signal_features(news.to_frame(resolved), as_of=now)
    feats = feats.set_index("gsis_id")

    # WR2 has a fresh positive role signal; WR1 a fresh injury concern
    assert feats.loc["WR2", "positive_role_signals_l7d"] > 0.3
    assert feats.loc["WR1", "injury_concern_signals_l7d"] > 0.3
    # 12-day-old claims fell outside the 7d window entirely: totals equal
    # what the fresh claims alone produce
    only_fresh = news.signal_features(
        news.to_frame(news.resolve_entities(
            news.parse_claims(raw_llm_output(), "beat", fresh, 0.8), id_map()
        )), as_of=now,
    ).set_index("gsis_id")
    assert feats.loc["WR2", "positive_role_signals_l7d"] == (
        only_fresh.loc["WR2", "positive_role_signals_l7d"]
    )


def test_unresolved_claims_excluded_from_features():
    claims = news.parse_claims(json.dumps([
        {"player": "Unknown Guy", "claim_type": "role_change", "direction": 1,
         "confidence": 0.9, "quote": "x"},
    ]), "beat", "2025-09-16T12:00:00Z", 0.9)
    resolved = news.resolve_entities(claims, id_map())
    feats = news.signal_features(news.to_frame(resolved),
                                 as_of=datetime(2025, 9, 17, tzinfo=timezone.utc))
    assert feats.empty
