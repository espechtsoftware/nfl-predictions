"""LLM-assisted news extraction (guide §8.7).

The one place an LLM belongs in this system: turning beat-writer prose
("coach wants to get him more involved in the red zone") into structured
claims, BEFORE the usage change shows up in the changepoint detector.

The LLM stays strictly in the extraction role. It never generates
projections — it would produce confident, fluent, uncalibrated numbers,
the worst failure mode in a system where calibration is the whole game.

Pipeline: fetch items -> extract claims (strict schema, entity-resolved)
-> write as decaying graph edges -> aggregate into two model features:
positive_role_signals_l7d, injury_concern_signals_l7d.
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone

import pandas as pd

log = logging.getLogger(__name__)

CLAIM_TYPES = {"role_change", "snap_count", "injury_status", "scheme_change",
               "depth_chart"}
SIGNAL_HALF_LIFE_DAYS = 5.0

EXTRACTION_SYSTEM_PROMPT = """\
You extract structured claims about NFL player usage from news snippets.
Return ONLY a JSON array; each element:
{
  "player": "<name as written>",
  "claim_type": "role_change" | "snap_count" | "injury_status" | "scheme_change" | "depth_chart",
  "direction": 1 | -1,          // 1 = more opportunity/health, -1 = less
  "confidence": 0.0-1.0,        // how directly the text supports the claim
  "quote": "<shortest supporting span>"
}
Rules: no forecasts, no fantasy advice, no numbers not in the text.
If the snippet contains no usage-relevant claim, return [].
"""


@dataclass
class Claim:
    player: str
    gsis_id: str | None
    claim_type: str
    direction: int
    confidence: float
    quote: str
    source: str
    source_credibility: float
    published_at: str


def extract_claims_llm(
    text: str, source: str, published_at: str, source_credibility: float = 0.5,
    model: str = "claude-sonnet-5",
) -> list[Claim]:
    """Extraction via the Anthropic API. Requires ANTHROPIC_API_KEY."""
    import anthropic

    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    resp = client.messages.create(
        model=model,
        max_tokens=1024,
        system=EXTRACTION_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": text[:8000]}],
    )
    raw = resp.content[0].text
    return parse_claims(raw, source, published_at, source_credibility)


def parse_claims(
    raw: str, source: str, published_at: str, source_credibility: float
) -> list[Claim]:
    """Validate model output against the strict schema; drop anything that
    doesn't conform rather than guessing."""
    try:
        start, end = raw.find("["), raw.rfind("]")
        items = json.loads(raw[start : end + 1]) if start >= 0 else []
    except (json.JSONDecodeError, ValueError):
        log.warning("Unparseable extraction output from %s", source)
        return []

    claims = []
    for it in items:
        if not isinstance(it, dict):
            continue
        if it.get("claim_type") not in CLAIM_TYPES:
            continue
        if it.get("direction") not in (1, -1):
            continue
        try:
            conf = float(it.get("confidence", 0))
        except (TypeError, ValueError):
            continue
        if not 0 <= conf <= 1 or not it.get("player"):
            continue
        claims.append(
            Claim(
                player=str(it["player"]),
                gsis_id=None,
                claim_type=it["claim_type"],
                direction=int(it["direction"]),
                confidence=conf,
                quote=str(it.get("quote", ""))[:300],
                source=source,
                source_credibility=source_credibility,
                published_at=published_at,
            )
        )
    return claims


def resolve_entities(claims: list[Claim], id_map: pd.DataFrame) -> list[Claim]:
    """Attach gsis_ids via the crosswalk (display_name -> gsis_id). Claims
    that don't resolve keep gsis_id=None and are excluded from features —
    a misattributed claim is worse than a dropped one."""
    lookup = {
        _norm(name): gid
        for name, gid in zip(id_map["display_name"], id_map["gsis_id"])
    }
    for c in claims:
        c.gsis_id = lookup.get(_norm(c.player))
    unresolved = sum(1 for c in claims if c.gsis_id is None)
    if unresolved:
        log.info("%d/%d claims unresolved to gsis_id", unresolved, len(claims))
    return claims


def _norm(name: str) -> str:
    import re

    name = re.sub(r"\s+(jr|sr|ii|iii|iv|v)\.?$", "", name.strip().lower())
    return re.sub(r"[^a-z ]", "", name)


def to_frame(claims: list[Claim]) -> pd.DataFrame:
    return pd.DataFrame([asdict(c) for c in claims])


def signal_features(
    claims_df: pd.DataFrame, as_of: datetime | None = None
) -> pd.DataFrame:
    """Aggregate resolved claims into the two model features, exponentially
    decayed by age (half-life SIGNAL_HALF_LIFE_DAYS), weighted by claim
    confidence x source credibility."""
    if claims_df.empty:
        return pd.DataFrame(columns=[
            "gsis_id", "positive_role_signals_l7d", "injury_concern_signals_l7d"
        ])
    as_of = as_of or datetime.now(timezone.utc)
    df = claims_df.dropna(subset=["gsis_id"]).copy()
    ts = pd.to_datetime(df["published_at"], utc=True)
    age_days = (as_of - ts).dt.total_seconds() / 86400.0
    df = df[(age_days >= 0) & (age_days <= 7)]
    age_days = age_days[df.index]
    df["weight"] = (
        df["confidence"] * df["source_credibility"]
        * 0.5 ** (age_days / SIGNAL_HALF_LIFE_DAYS)
    )
    role = df[df.claim_type.isin(["role_change", "snap_count", "depth_chart",
                                  "scheme_change"])]
    injury = df[df.claim_type == "injury_status"]
    pos = (role.weight * role.direction).groupby(role.gsis_id).sum().clip(lower=0)
    concern = (-injury.weight * injury.direction).groupby(injury.gsis_id).sum().clip(lower=0)
    out = pd.DataFrame({
        "positive_role_signals_l7d": pos,
        "injury_concern_signals_l7d": concern,
    }).fillna(0.0)
    return out.rename_axis("gsis_id").reset_index()


def to_graph_edges(claims_df: pd.DataFrame, team_lookup: dict[str, str]) -> pd.DataFrame:
    """Claims as graph edges (player -> team) for the reasoning layer."""
    df = claims_df.dropna(subset=["gsis_id"]).copy()
    df["team"] = df["gsis_id"].map(team_lookup)
    return df.dropna(subset=["team"])[
        ["gsis_id", "team", "claim_type", "direction", "confidence", "published_at"]
    ]
