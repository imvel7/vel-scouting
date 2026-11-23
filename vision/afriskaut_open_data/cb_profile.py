"""Event-map-aware raw metric definitions for Afriskaut centre-back profiles.

Every metric is defined by (event_name, event_type[, event_outcome]) following the publisher's
"Afriskaut Event Map - 2024". Matching on event_type alone would be wrong: FOUL appears both as a defensive
action and as a CARD row, and SHORT/LONG appear for open-play passes as well as throw-ins and corners.

Rules kept on purpose:
* Raw counts and per-90 rates only; no rating, ranking or composite score.
* Outcome labels are reported as labelled ("labelled_successful"), never converted into completion
  percentages, because the event map does not say whether KEY_PASS / ASSIST outcomes also completed.
* Per-90 needs minutes the caller has verified; without them the rate is None, never zero.
* Distributions are only produced for cohorts of at least MIN_COHORT player-matches and contain quartiles
  only (no per-player value, minimum or maximum).
"""

from __future__ import annotations

import statistics
from collections import Counter
from typing import Iterable

MIN_COHORT = 10
SECONDS_PER_90 = 5400
OPEN_PLAY_PASS_TYPES = frozenset({"SHORT", "LONG", "LINE_BREAK"})

# (metric id, event_name set, event_type set, event_outcome set or None for any outcome)
METRIC_DEFINITIONS: tuple[tuple[str, frozenset, frozenset, frozenset | None], ...] = (
    ("open_play_passes_attempted", frozenset({"PASS"}), OPEN_PLAY_PASS_TYPES, None),
    ("open_play_passes_labelled_successful", frozenset({"PASS"}), OPEN_PLAY_PASS_TYPES, frozenset({"SUCCESSFUL"})),
    ("open_play_long_passes_attempted", frozenset({"PASS"}), frozenset({"LONG"}), None),
    ("line_breaking_passes_attempted", frozenset({"PASS"}), frozenset({"LINE_BREAK"}), None),
    ("key_pass_or_assist_labels", frozenset({"PASS"}), OPEN_PLAY_PASS_TYPES, frozenset({"KEY_PASS", "ASSIST"})),
    ("tackles", frozenset({"DEF_ACTIONS"}), frozenset({"TACKLE"}), None),
    ("tackles_labelled_successful", frozenset({"DEF_ACTIONS"}), frozenset({"TACKLE"}), frozenset({"SUCCESSFUL"})),
    ("interceptions", frozenset({"DEF_ACTIONS"}), frozenset({"INTERCEPTION"}), None),
    ("clearances", frozenset({"DEF_ACTIONS"}), frozenset({"CLEARANCE"}), None),
    ("blocks", frozenset({"DEF_ACTIONS"}), frozenset({"BLOCK"}), None),
    ("recoveries", frozenset({"DEF_ACTIONS"}), frozenset({"RECOVERY"}), None),
    ("errors", frozenset({"DEF_ACTIONS"}), frozenset({"ERROR"}), None),
    ("dribbled_past", frozenset({"DEF_ACTIONS"}), frozenset({"DRIBBLED_PAST"}), None),
    ("fouls_committed", frozenset({"DEF_ACTIONS"}), frozenset({"FOUL"}), None),
    ("penalties_conceded", frozenset({"DEF_ACTIONS"}), frozenset({"PENALTY_CONCEDED"}), None),
    ("aerial_duels", frozenset({"DUEL"}), frozenset({"AERIAL_DUEL"}), None),
    ("aerial_duels_labelled_successful", frozenset({"DUEL"}), frozenset({"AERIAL_DUEL"}), frozenset({"SUCCESSFUL"})),
    ("ground_duels", frozenset({"DUEL"}), frozenset({"GROUND_DUEL"}), None),
    ("ground_duels_labelled_successful", frozenset({"DUEL"}), frozenset({"GROUND_DUEL"}), frozenset({"SUCCESSFUL"})),
    ("possessions_lost", frozenset({"POSSESSION"}), frozenset({"POSSESSION_LOST"}), None),
    ("ball_progressions", frozenset({"POSSESSION"}), frozenset({"BALL_PROGRESSION"}), None),
    ("dribbles_attempted", frozenset({"POSSESSION"}), frozenset({"DRIBBLE"}), None),
    ("fouls_won", frozenset({"POSSESSION"}), frozenset({"FOUL_WON"}), None),
    ("yellow_cards", frozenset({"CARD"}), frozenset({"FOUL", "DISSENT"}), frozenset({"YELLOW"})),
    ("red_cards", frozenset({"CARD"}), frozenset({"FOUL", "DISSENT"}), frozenset({"RED"})),
)
METRIC_IDS = tuple(definition[0] for definition in METRIC_DEFINITIONS)
# Labels that appear in the data but are not defined in the publisher's event map.
UNDOCUMENTED_IN_EVENT_MAP = frozenset({"dribbled_past"})


def _norm(value) -> str:
    return str(value or "").strip().upper()


def event_key(event: dict) -> tuple[str, str, str]:
    return _norm(event.get("event_name")), _norm(event.get("event_type")), _norm(event.get("event_outcome"))


def matching_metrics(event: dict) -> list[str]:
    name, event_type, outcome = event_key(event)
    return [
        metric_id
        for metric_id, names, types, outcomes in METRIC_DEFINITIONS
        if name in names and event_type in types and (outcomes is None or outcome in outcomes)
    ]


def count_metrics(events: Iterable[dict]) -> tuple[dict[str, int], Counter, int]:
    """Return (metric counts, unmapped (event_name, event_type) pairs, events considered).

    SUBSTITUTION events are bookkeeping, not performance, and are skipped.
    """
    counts = {metric_id: 0 for metric_id in METRIC_IDS}
    unmapped: Counter = Counter()
    considered = 0
    for event in events:
        name, event_type, _ = event_key(event)
        if event_type == "SUBSTITUTION" or name == "SUBSTITUTION":
            continue
        considered += 1
        matched = matching_metrics(event)
        if not matched:
            unmapped[(name or "<MISSING>", event_type or "<MISSING>")] += 1
        for metric_id in matched:
            counts[metric_id] += 1
    return counts, unmapped, considered


def per90(count: int, minutes_seconds: int | None) -> float | None:
    """Rate per 90 minutes, or None when minutes are not available (never zero-filled)."""
    if minutes_seconds is None or minutes_seconds <= 0:
        return None
    return count * SECONDS_PER_90 / minutes_seconds


def quartiles(values: list[float], min_cohort: int = MIN_COHORT) -> dict | None:
    """Quartile summary, or None for cohorts too small to describe without singling out a player."""
    if len(values) < min_cohort:
        return None
    q1, median, q3 = statistics.quantiles(values, n=4, method="inclusive")
    return {"n": len(values), "p25": round(q1, 3), "median": round(median, 3), "p75": round(q3, 3)}
