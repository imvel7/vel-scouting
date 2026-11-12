#!/usr/bin/env python3
"""Inspect the public Afriskaut Dynasty Scouting League dataset without exporting player identities."""

from __future__ import annotations

import json
import sys
import urllib.request
import zipfile
from collections import Counter
from io import BytesIO
from pathlib import PurePosixPath

DATASET_URL = "https://github.com/Afriskaut/dynasty-scouting-league-2024-open-data/raw/refs/heads/main/Datasets.zip"


def main() -> int:
    request = urllib.request.Request(DATASET_URL, headers={"User-Agent": "VelScout-Research-Probe/0.1"})
    with urllib.request.urlopen(request, timeout=120) as response:
        archive_bytes = response.read()

    match_count = 0
    event_count = 0
    player_ids: set[str] = set()
    team_ids: set[str] = set()
    event_types: Counter[str] = Counter()
    positions: Counter[str] = Counter()
    match_schema: set[str] = set()
    event_schema: set[str] = set()
    lineup_count = 0
    missing_player_id_events = 0
    sample_matches = []

    with zipfile.ZipFile(BytesIO(archive_bytes)) as archive:
        names = archive.namelist()
        match_json_paths = sorted(
            name for name in names
            if PurePosixPath(name).name == "match.json"
        )
        for match_path in match_json_paths:
            parent = str(PurePosixPath(match_path).parent)
            event_path = parent + "/events.jsonl"
            if event_path not in names:
                continue

            match = json.loads(archive.read(match_path))
            match_count += 1
            match_schema.update(match.keys())
            for key in ("home_team", "away_team"):
                if match.get(key) is not None:
                    team_ids.add(str(match[key]))

            for key in ("lineups", "home_lineup", "away_lineup", "players"):
                value = match.get(key)
                if isinstance(value, list):
                    for item in value:
                        if not isinstance(item, dict):
                            continue
                        lineup_count += 1
                        pid = item.get("player_id") or item.get("id") or item.get("_id")
                        if pid is not None:
                            player_ids.add(str(pid))
                        for pkey in ("player_position", "position", "player_role", "role"):
                            role = item.get(pkey)
                            if role:
                                positions.update(
                                    part.strip() for part in str(role).split(",") if part.strip()
                                )

            match_events = 0
            with archive.open(event_path) as stream:
                for raw_line in stream:
                    if not raw_line.strip():
                        continue
                    event = json.loads(raw_line)
                    match_events += 1
                    event_count += 1
                    event_schema.update(event.keys())
                    pid = event.get("player_id")
                    if pid is None:
                        missing_player_id_events += 1
                    else:
                        player_ids.add(str(pid))
                    for key in ("event_name", "event_type"):
                        if event.get(key):
                            event_types[str(event[key])] += 1
                    role = event.get("player_role") or event.get("player_position")
                    if role:
                        positions.update(
                            part.strip() for part in str(role).split(",") if part.strip()
                        )

            if len(sample_matches) < 3:
                sample_matches.append({
                    "match_id": PurePosixPath(parent).name,
                    "date": match.get("date"),
                    "events": match_events,
                    "has_lineup_fields": any(
                        key in match for key in ("lineups", "home_lineup", "away_lineup", "players")
                    ),
                })

    result = {
        "dataset": "Afriskaut Dynasty Scouting League 2024 Open Data",
        "archive_bytes": len(archive_bytes),
        "matches_with_event_files": match_count,
        "events": event_count,
        "unique_player_ids_seen": len(player_ids),
        "team_ids_seen": len(team_ids),
        "lineup_rows_detected": lineup_count,
        "events_without_player_id": missing_player_id_events,
        "match_json_fields": sorted(match_schema),
        "event_jsonl_fields": sorted(event_schema),
        "event_name_counts": dict(event_types.most_common(20)),
        "position_role_counts": dict(positions.most_common(30)),
        "sample_matches": sample_matches,
        "player_names_exported": False,
        "player_ids_exported": False,
    }
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
