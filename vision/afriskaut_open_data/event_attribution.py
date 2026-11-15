"""Conservative attribution rules for Afriskaut event data.

Raw event rows remain untouched. This module only decides whether an event may
be attributed to an individual player in player-level metrics.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Literal


AttributionScope = Literal["player", "team", "unverified", "unattributed"]


@dataclass(frozen=True)
class EventAttribution:
    scope: AttributionScope
    player_metrics_eligible: bool
    reason: str


def classify_event_attribution(
    event: dict,
    same_match_lineup_ids: Iterable[str],
    same_match_substitution_ids: Iterable[str],
) -> EventAttribution:
    """Classify an event without guessing an actor from shirt number or name.

    Priority:
    1. Explicit team-level event types are never player performance evidence.
    2. Missing event player_id cannot be attributed to a player.
    3. A player_id must be present in this match's lineup or substitution data.
    4. All other actor IDs remain unverified and excluded from player metrics.
    """
    event_type = str(event.get("event_type") or "").strip().upper()
    if event_type == "TEAM_OWN_GOAL":
        return EventAttribution(
            scope="team",
            player_metrics_eligible=False,
            reason="team_level_event_type",
        )

    raw_player_id = event.get("player_id")
    if raw_player_id is None or not str(raw_player_id).strip():
        return EventAttribution(
            scope="unattributed",
            player_metrics_eligible=False,
            reason="missing_player_id",
        )

    player_id = str(raw_player_id).strip()
    known_ids = {
        str(value).strip()
        for value in (*tuple(same_match_lineup_ids), *tuple(same_match_substitution_ids))
        if value is not None and str(value).strip()
    }
    if player_id in known_ids:
        return EventAttribution(
            scope="player",
            player_metrics_eligible=True,
            reason="matched_same_match_lineup_or_substitution",
        )

    return EventAttribution(
        scope="unverified",
        player_metrics_eligible=False,
        reason="player_id_not_linked_to_same_match",
    )
