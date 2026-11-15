"""Conservative, role-specific raw event counts for center backs."""

from __future__ import annotations

import json
import urllib.request
import zipfile
from collections import Counter
from io import BytesIO
from pathlib import PurePosixPath
from typing import Iterable

from event_attribution import classify_event_attribution
from position_normalizer import normalize_position_labels

DATASET_URL = "https://github.com/Afriskaut/dynasty-scouting-league-2024-open-data/raw/refs/heads/main/Datasets.zip"
LINEUP_FIELDS = ("home_team_line_up", "away_team_line_up")
SUBSTITUTION_FIELDS = (
    "home_team_subs", "away_team_subs",
    "home_substitutions", "away_substitutions", "substitutions",
)


def _player_id(item: dict) -> str | None:
    for key in ("player_id", "id", "_id"):
        value = item.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    return None


def _nested_player_ids(value) -> set[str]:
    found: set[str] = set()
    if isinstance(value, dict):
        for key, child in value.items():
            if key in ("player_id", "playerId") and child is not None:
                if str(child).strip():
                    found.add(str(child).strip())
            else:
                found.update(_nested_player_ids(child))
    elif isinstance(value, list):
        for child in value:
            found.update(_nested_player_ids(child))
    return found


def _center_back_ids(match: dict) -> set[str]:
    result: set[str] = set()
    for field in LINEUP_FIELDS:
        players = match.get(field)
        if not isinstance(players, list):
            continue
        for player in players:
            if not isinstance(player, dict):
                continue
            pid = _player_id(player)
            if not pid:
                continue
            role_values = [
                player.get(key)
                for key in ("player_position", "position", "player_role", "role")
                if player.get(key)
            ]
            recognized: list[str] = []
            for value in role_values:
                labels, _ = normalize_position_labels(value)
                recognized.extend(labels)
            if "Center Back" in recognized:
                result.add(pid)
    return result


def aggregate_center_back_match(match: dict, events: Iterable[dict]) -> dict:
    """Aggregate eligible events for players explicitly listed as Center Back.

    Position comes from the same-match lineup. Substitutes without an explicit
    lineup role are not guessed into the center-back cohort.
    """
    lineup_ids = {
        pid
        for field in LINEUP_FIELDS
        for player in (match.get(field) if isinstance(match.get(field), list) else [])
        if isinstance(player, dict)
        for pid in [_player_id(player)]
        if pid
    }
    substitution_ids = set()
    for field in SUBSTITUTION_FIELDS:
        substitution_ids.update(_nested_player_ids(match.get(field)))

    cb_ids = _center_back_ids(match)
    name_counts: Counter[str] = Counter()
    type_counts: Counter[str] = Counter()
    eligible_rows = 0
    cb_players_with_events: set[str] = set()
    for event in events:
        attribution = classify_event_attribution(
            event, lineup_ids, substitution_ids
        )
        if not attribution.player_metrics_eligible:
            continue
        pid = str(event.get("player_id") or "").strip()
        if pid not in cb_ids:
            continue
        event_name = str(event.get("event_name") or "").strip().upper() or "<MISSING>"
        event_type = str(event.get("event_type") or "").strip().upper() or "<MISSING>"
        name_counts[event_name] += 1
        type_counts[event_type] += 1
        eligible_rows += 1
        cb_players_with_events.add(pid)

    return {
        "center_back_lineup_players": len(cb_ids),
        "center_back_players_with_eligible_events": len(cb_players_with_events),
        "center_back_eligible_event_rows": eligible_rows,
        "event_name_counts": dict(name_counts),
        "event_type_counts": dict(type_counts),
    }


def build_dataset_report() -> dict:
    request = urllib.request.Request(
        DATASET_URL, headers={"User-Agent": "VelScout-Research-Probe/0.1"}
    )
    with urllib.request.urlopen(request, timeout=120) as response:
        archive_bytes = response.read()

    matches_scanned = 0
    cb_roster_entries = 0
    cb_players_with_events = 0
    cb_event_rows = 0
    event_name_counts: Counter[str] = Counter()
    event_type_counts: Counter[str] = Counter()

    with zipfile.ZipFile(BytesIO(archive_bytes)) as archive:
        names = set(archive.namelist())
        canonical: dict[str, str] = {}
        for path in sorted(names):
            if PurePosixPath(path).name != "match.json":
                continue
            match_id = PurePosixPath(path).parent.name
            current = canonical.get(match_id)
            if current is None or (
                "/Datasets/" in path and "/Datasets/" not in current
            ):
                canonical[match_id] = path

        for match_path in canonical.values():
            event_path = str(PurePosixPath(match_path).parent) + "/events.jsonl"
            if event_path not in names:
                continue
            match = json.loads(archive.read(match_path))
            events = []
            with archive.open(event_path) as stream:
                for raw in stream:
                    if raw.strip():
                        events.append(json.loads(raw))
            result = aggregate_center_back_match(match, events)
            matches_scanned += 1
            cb_roster_entries += result["center_back_lineup_players"]
            cb_players_with_events += result["center_back_players_with_eligible_events"]
            cb_event_rows += result["center_back_eligible_event_rows"]
            event_name_counts.update(result["event_name_counts"])
            event_type_counts.update(result["event_type_counts"])

    return {
        "dataset": "Afriskaut Dynasty Scouting League 2024 Open Data",
        "matches_scanned": matches_scanned,
        "center_back_lineup_player_match_entries": cb_roster_entries,
        "center_back_player_match_entries_with_eligible_events": cb_players_with_events,
        "center_back_player_attributed_event_rows": cb_event_rows,
        "center_back_event_name_counts": dict(sorted(event_name_counts.items())),
        "center_back_event_type_counts": dict(sorted(event_type_counts.items())),
        "position_source": "same-match lineup role explicitly includes Center Back",
        "event_source": "same-match lineup/substitution-linked player events only",
        "normalization": "raw event counts; no per-90 rates or composite score",
        "limitations": [
            "No reliable minutes played denominator was available.",
            "Substitutes without an explicit same-match lineup role are excluded.",
            "Event labels are reported as supplied; their tactical meaning is not inferred.",
            "Counts are not adjusted for possession, match state, opponent, or team style.",
            "Event data does not capture all off-ball positioning or movement.",
        ],
        "player_names_exported": False,
        "player_ids_exported": False,
    }


if __name__ == "__main__":
    print(json.dumps(build_dataset_report(), indent=2, sort_keys=True))
