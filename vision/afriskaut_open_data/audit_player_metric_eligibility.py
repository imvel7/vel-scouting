#!/usr/bin/env python3
"""Audit which Afriskaut events are safe to attribute to individual players."""

from __future__ import annotations

import json
import urllib.request
import zipfile
from collections import Counter
from io import BytesIO
from pathlib import PurePosixPath

from event_attribution import classify_event_attribution

DATASET_URL = "https://github.com/Afriskaut/dynasty-scouting-league-2024-open-data/raw/refs/heads/main/Datasets.zip"
LINEUP_FIELDS = ("home_team_line_up", "away_team_line_up")
SUBSTITUTION_FIELDS = (
    "home_team_subs",
    "away_team_subs",
    "home_substitutions",
    "away_substitutions",
    "substitutions",
)


def extract_lineup_ids(value) -> set[str]:
    ids: set[str] = set()
    if not isinstance(value, list):
        return ids
    for item in value:
        if not isinstance(item, dict):
            continue
        for key in ("player_id", "id", "_id"):
            player_id = item.get(key)
            if player_id is not None and str(player_id).strip():
                ids.add(str(player_id).strip())
                break
    return ids


def extract_nested_player_ids(value) -> set[str]:
    """Find explicit player_id fields in substitution metadata only."""
    ids: set[str] = set()
    if isinstance(value, dict):
        for key, child in value.items():
            if key in ("player_id", "playerId") and child is not None:
                if str(child).strip():
                    ids.add(str(child).strip())
            else:
                ids.update(extract_nested_player_ids(child))
    elif isinstance(value, list):
        for child in value:
            ids.update(extract_nested_player_ids(child))
    return ids


def main() -> int:
    request = urllib.request.Request(
        DATASET_URL,
        headers={"User-Agent": "VelScout-Research-Probe/0.1"},
    )
    with urllib.request.urlopen(request, timeout=120) as response:
        archive_bytes = response.read()

    scope_counts: Counter[str] = Counter()
    reason_counts: Counter[str] = Counter()
    event_type_scope_counts: Counter[str] = Counter()
    event_rows = 0
    matches_scanned = 0
    player_attributed_rows_with_id: Counter[str] = Counter()
    player_attributed_rows_without_id = 0

    with zipfile.ZipFile(BytesIO(archive_bytes)) as archive:
        archive_names = set(archive.namelist())
        canonical_match_paths: dict[str, str] = {}

        for path in sorted(archive_names):
            if PurePosixPath(path).name != "match.json":
                continue
            match_id = PurePosixPath(path).parent.name
            current = canonical_match_paths.get(match_id)
            if current is None or (
                "/Datasets/" in path and "/Datasets/" not in current
            ):
                canonical_match_paths[match_id] = path

        for match_path in canonical_match_paths.values():
            parent = str(PurePosixPath(match_path).parent)
            events_path = parent + "/events.jsonl"
            if events_path not in archive_names:
                continue

            match = json.loads(archive.read(match_path))
            lineup_ids: set[str] = set()
            for field in LINEUP_FIELDS:
                lineup_ids.update(extract_lineup_ids(match.get(field)))

            substitution_ids: set[str] = set()
            for field in SUBSTITUTION_FIELDS:
                substitution_ids.update(
                    extract_nested_player_ids(match.get(field))
                )

            matches_scanned += 1
            with archive.open(events_path) as stream:
                for raw_line in stream:
                    if not raw_line.strip():
                        continue
                    event = json.loads(raw_line)
                    result = classify_event_attribution(
                        event,
                        lineup_ids,
                        substitution_ids,
                    )
                    event_rows += 1
                    scope_counts[result.scope] += 1
                    reason_counts[result.reason] += 1
                    event_type = str(event.get("event_type") or "<missing>")
                    event_type_scope_counts[
                        f"{result.scope}:{event_type}"
                    ] += 1

                    if result.player_metrics_eligible:
                        if event.get("player_id") is None:
                            player_attributed_rows_without_id += 1
                        else:
                            player_attributed_rows_with_id[
                                str(event["player_id"]).strip()
                            ] += 1

    eligible_rows = scope_counts["player"]
    excluded_rows = event_rows - eligible_rows
    if event_rows != sum(scope_counts.values()):
        raise AssertionError("Attribution scope counts do not sum to event rows")
    if eligible_rows != sum(player_attributed_rows_with_id.values()):
        raise AssertionError("Player-attributed event count does not reconcile")
    if player_attributed_rows_without_id:
        raise AssertionError("Player-attributed event missing player_id")

    report = {
        "dataset": "Afriskaut Dynasty Scouting League 2024 Open Data",
        "matches_scanned": matches_scanned,
        "event_rows_scanned": event_rows,
        "player_metric_eligible_event_rows": eligible_rows,
        "excluded_from_player_metrics_event_rows": excluded_rows,
        "player_metric_eligible_percent": round(
            100 * eligible_rows / event_rows, 2
        ) if event_rows else None,
        "attribution_scope_counts": dict(sorted(scope_counts.items())),
        "attribution_reason_counts": dict(sorted(reason_counts.items())),
        "event_type_by_attribution_scope": dict(
            sorted(event_type_scope_counts.items())
        ),
        "unique_player_ids_with_eligible_events": len(
            player_attributed_rows_with_id
        ),
        "player_names_exported": False,
        "player_ids_exported": False,
        "raw_event_context_exported": False,
        "note": (
            "Eligibility is an attribution safeguard, not a player rating. "
            "Eligible event counts are not adjusted for minutes, role, match "
            "state, possession, or opponent strength."
        ),
    }
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
