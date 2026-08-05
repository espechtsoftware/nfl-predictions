"""Evidence-event schema + supersede/expiry resolution (Workstream D,
plan §8.3 and §8.7).

This is the calibrated successor to manual notes (notes.py). A manual
note is a hand-entered multiplier with no provenance; an evidence event
is a fully-provenanced structured claim (source, excerpt, timestamps,
resolved entity, confidences) whose *magnitude* is supplied later by the
effect model (evidence_effect.py), never by the extractor or the LLM.
The two systems coexist: notes remain the operator's manual override,
evidence events feed a separate, audited prior path.

Everything in this module is pure and offline: the dataclass, the DDL
string (executed only when September wires the live feed), and
`resolve_active`, which turns a pile of events into the set of active
per-player component adjustments at a point in time. Point-in-time is
sacred here too: an event only counts once `retrieved_at` has passed —
what mattered is when WE knew, not when the source published.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import datetime, timedelta

__all__ = [
    "EVENT_TYPES", "DIRECTIONS", "COMPONENTS", "REVIEW_STATUSES",
    "DEFAULT_TTL_DAYS", "TTL_DAYS_BY_TYPE", "CONFLICT_VARIANCE_STEP",
    "EvidenceEvent", "ActiveAdjustment", "EVIDENCE_EVENTS_DDL",
    "event_expiry", "resolve_active",
]

# §8.3 registered event types. "other" is the catch-all for registered
# types added later; unregistered strings are rejected at validation.
EVENT_TYPES = frozenset({
    "inactive", "limited", "promotion", "demotion", "starter_change",
    "committee", "route_change", "target_emphasis", "workload_cap",
    "weather", "other",
})

DIRECTIONS = frozenset({
    "opportunity_up", "opportunity_down", "redistributed", "uncertain",
})

# §8.3 affected components. These are opportunity/efficiency components
# of the projection model — never fantasy points (§8.2 boundary).
COMPONENTS = frozenset({
    "active_probability", "snaps", "routes", "targets", "carries",
    "red_zone_share", "efficiency", "variance",
})

REVIEW_STATUSES = frozenset({"pending", "accepted", "rejected", "modified"})

# Expiry rule when the event carries no explicit expiration: days after
# effective_from. Weather is hyper-perishable; role news persists until
# actual snaps speak (mirrors notes.DECAY_FULL_WEEK thinking).
DEFAULT_TTL_DAYS = 10
TTL_DAYS_BY_TYPE = {
    "weather": 2,
    "inactive": 7,
    "limited": 7,
}

# Each conflicting report beyond the first inflates adjustment variance
# by this step (§8.7: conflicts widen, never average into false
# certainty).
CONFLICT_VARIANCE_STEP = 0.5


@dataclass(frozen=True)
class EvidenceEvent:
    """One structured claim extracted from one source article (§8.3)."""

    event_id: str
    # Provenance
    source_url: str
    publisher: str
    author: str
    published_at: datetime
    retrieved_at: datetime
    excerpt: str                       # sanitized supporting span
    # Resolved entity
    player_name: str                   # as written in the source
    gsis_id: str
    team: str
    position: str
    # Classification
    event_type: str                    # EVENT_TYPES
    direction: str                     # DIRECTIONS
    component: str                     # COMPONENTS
    # Lifecycle
    effective_from: datetime
    expires_at: datetime | None = None
    supersedes_event_id: str | None = None
    # Confidences (extractor's span support x entity-resolution certainty)
    extraction_confidence: float = 0.0
    entity_confidence: float = 0.0
    # Contradictory reports share a conflict_group id
    conflict_group: str | None = None
    # Human review (§8.8): actions become labels, kept separate from
    # model-generated labels
    review_status: str = "pending"
    review_disposition: str = ""


# Style matches sql/raw + sql/features DDL: append-only, ${features}
# substituted by bq.run_sql_file. Corrections and retractions are new
# rows that supersede old ones — history is never overwritten (§8.4).
EVIDENCE_EVENTS_DDL = """\
-- Append-only evidence-event log (plan §8.3). Never UPDATE or DELETE:
-- retractions and corrections are new rows whose supersedes_event_id
-- points at the row they replace. resolve_active() in
-- research/evidence_schema.py is the single reader that turns this log
-- into point-in-time active adjustments.
CREATE TABLE IF NOT EXISTS `${features}.evidence_events` (
  event_id STRING,                 -- deterministic hash of provenance
  source_url STRING,
  publisher STRING,
  author STRING,
  published_at TIMESTAMP,          -- source's publication time
  retrieved_at TIMESTAMP,          -- when WE fetched it (point-in-time key)
  excerpt STRING,                  -- sanitized supporting span, verbatim
  player_name STRING,              -- entity as written in the source
  gsis_id STRING,                  -- resolved id (names.py two-stage match)
  team STRING,
  position STRING,
  event_type STRING,               -- inactive | limited | promotion | ...
  direction STRING,                -- opportunity_up | opportunity_down |
                                   --   redistributed | uncertain
  component STRING,                -- active_probability | snaps | routes |
                                   --   targets | carries | red_zone_share |
                                   --   efficiency | variance
  effective_from TIMESTAMP,
  expires_at TIMESTAMP,            -- NULL -> per-type TTL default applies
  supersedes_event_id STRING,      -- retraction/correction chain
  extraction_confidence FLOAT64,   -- 0-1, span support for the claim
  entity_confidence FLOAT64,       -- 0-1, entity-resolution certainty
  conflict_group STRING,           -- contradictory reports share this id
  review_status STRING,            -- pending | accepted | rejected | modified
  review_disposition STRING        -- human reason; becomes labeled data
)
PARTITION BY DATE(retrieved_at)
CLUSTER BY gsis_id, event_type;
"""


@dataclass(frozen=True)
class ActiveAdjustment:
    """Net active evidence for one (player, component) at a timestamp.

    Carries direction + variance treatment only. The magnitude
    distribution comes from evidence_effect.py; variance_inflation
    multiplies that distribution's sd (§8.7).
    """

    gsis_id: str
    component: str
    direction: str
    event_ids: tuple[str, ...]         # ordered by published_at
    confidence: float                  # mean extraction x entity conf
    conflict: bool
    variance_inflation: float          # 1.0 unless reports conflict
    event_types: tuple[str, ...] = field(default=())


def event_expiry(event: EvidenceEvent) -> datetime:
    """Explicit expiry, else the per-type TTL from effective_from."""
    if event.expires_at is not None:
        return event.expires_at
    ttl = TTL_DAYS_BY_TYPE.get(event.event_type, DEFAULT_TTL_DAYS)
    return event.effective_from + timedelta(days=ttl)


def _is_live(event: EvidenceEvent, at: datetime) -> bool:
    return (event.retrieved_at <= at
            and event.effective_from <= at < event_expiry(event))


def resolve_active(events: list[EvidenceEvent],
                   at: datetime) -> list[ActiveAdjustment]:
    """Active per-(player, component) adjustments at `at`. Pure.

    Rules, in order:
    - rejected events never count; pending/accepted/modified do (review
      happens on the surface, rejection is the only veto);
    - an event is dropped once a live-at-`at` event supersedes it
      (retraction = superseding event with direction 'uncertain', which
      then contributes no directional signal of its own);
    - events outside [effective_from, expiry) or not yet retrieved are
      invisible — point-in-time;
    - within a group, agreeing directions reinforce (confidence is the
      mean, variance untouched); disagreeing directions CONFLICT: the
      group direction becomes 'uncertain' and variance_inflation grows
      with each contradicting report instead of averaging (§8.7).
    """
    considered = [e for e in events if e.review_status != "rejected"]
    superseded = {e.supersedes_event_id for e in considered
                  if e.supersedes_event_id and e.retrieved_at <= at}
    live = [e for e in considered
            if e.event_id not in superseded and _is_live(e, at)]

    groups: dict[tuple[str, str], list[EvidenceEvent]] = {}
    for e in live:
        groups.setdefault((e.gsis_id, e.component), []).append(e)

    out: list[ActiveAdjustment] = []
    for (gsis_id, component), evs in sorted(groups.items()):
        evs = sorted(evs, key=lambda e: (e.published_at, e.event_id))
        directional = [e for e in evs if e.direction != "uncertain"]
        stated = {e.direction for e in directional}
        conflict = len(stated) > 1
        if conflict:
            direction = "uncertain"
            inflation = 1.0 + CONFLICT_VARIANCE_STEP * (len(directional) - 1)
        elif stated:
            direction = next(iter(stated))
            inflation = 1.0
        else:                       # only 'uncertain' reports survive
            direction = "uncertain"
            inflation = 1.0
        confs = [e.extraction_confidence * e.entity_confidence for e in evs]
        out.append(ActiveAdjustment(
            gsis_id=gsis_id, component=component, direction=direction,
            event_ids=tuple(e.event_id for e in evs),
            confidence=sum(confs) / len(confs),
            conflict=conflict, variance_inflation=inflation,
            event_types=tuple(e.event_type for e in evs)))
    return out


def assign_conflict_groups(events: list[EvidenceEvent]
                           ) -> list[EvidenceEvent]:
    """Stamp a shared conflict_group id on contradictory reports: same
    (player, component), disagreeing non-'uncertain' directions. Pure —
    returns new instances; existing group ids are preserved."""
    keyed: dict[tuple[str, str], set[str]] = {}
    for e in events:
        if e.direction != "uncertain":
            keyed.setdefault((e.gsis_id, e.component),
                             set()).add(e.direction)
    conflicted = {k for k, dirs in keyed.items() if len(dirs) > 1}
    out = []
    for e in events:
        key = (e.gsis_id, e.component)
        if key in conflicted and e.conflict_group is None:
            e = replace(e, conflict_group=f"cg-{key[0]}-{key[1]}")
        out.append(e)
    return out


def supersede(event: EvidenceEvent, *, new_event_id: str,
              retrieved_at: datetime, published_at: datetime,
              excerpt: str, direction: str = "uncertain",
              source_url: str | None = None) -> EvidenceEvent:
    """Convenience constructor for a retraction/correction row: a NEW
    event pointing back at the old one. History stays append-only."""
    return replace(
        event, event_id=new_event_id, supersedes_event_id=event.event_id,
        retrieved_at=retrieved_at, published_at=published_at,
        excerpt=excerpt, direction=direction,
        source_url=source_url or event.source_url,
        review_status="pending", review_disposition="")
