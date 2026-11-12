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

from position_normalizer import normalize_position_labels

DATASET_URL = "https://github.com/Afriskaut/dynasty-scouting-league-2024-open-data/raw/refs/heads/main/Datasets.zip"


def extract_player_id(item: dict) -> str | None:
    """Read the first populated player identifier field without exposing it."""
    for key in ("player_id", "id", "_id"):
        value = item.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    return None


def compare_match_player_ids(event_ids: set[str], lineup_ids: set[str]) -> dict[str, int]:
    """Compare unique event actors with that same match's lineup identifiers."""
    return {
        "event_actor_ids": len(event_ids),
        "matched_actor_ids": len(event_ids & lineup_ids),
        "unmatched_actor_ids": len(event_ids - lineup_ids),
    }


def main() -> int:
    request = urllib.request.Request(DATASET_URL, headers={"User-Agent": "VelScout-Research-Probe/0.1"})
    with urllib.request.urlopen(request, timeout=120) as response:
        archive_bytes = response.read()

    match_count = 0
    event_count = 0
    event_player_ids: set[str] = set()
    lineup_player_ids: set[str] = set()
    team_ids: set[str] = set()
    event_types: Counter[str] = Counter()
    raw_positions: Counter[str] = Counter()
    normalized_positions: Counter[str] = Counter()
    unknown_positions: Counter[str] = Counter()
    match_schema: set[str] = set()
    event_schema: set[str] = set()
    lineup_count = 0
    lineup_rows_without_player_id = 0
    missing_player_id_events = 0
    event_rows_with_player_id = 0
    event_rows_matched_to_lineup = 0
    event_rows_not_matched_to_lineup = 0
    unique_match_actor_ids = 0
    unique_match_actor_ids_matched = 0
    unique_match_actor_ids_unmatched = 0
    matches_with_all_actor_ids_matched = 0
    matches_with_unmatched_actor_ids = 0
    matches_without_actor_ids = 0
    sample_matches = []

    def record_position(value: object) -> None:
        raw_positions[str(value)] += 1
        recognized, unknown = normalize_position_labels(value)
        normalized_positions.update(recognized)
        unknown_positions.update(unknown)

    with zipfile.ZipFile(BytesIO(archive_bytes)) as archive:
        names = archive.namelist()
        match_paths_by_id: dict[str, str] = {}
        for name in sorted(names):
            if PurePosixPath(name).name != "match.json":
                continue
            match_id = PurePosixPath(name).parent.name
            current = match_paths_by_id.get(match_id)
            # Prefer the canonical Datasets/ copy if the ZIP contains a mirror.
            if current is None or ("/Datasets/" in name and "/Datasets/" not in current):
                match_paths_by_id[match_id] = name

        for match_id, match_path in sorted(match_paths_by_id.items()):
            parent = str(PurePosixPath(match_path).parent)
            event_path = parent + "/events.jsonl"
            if event_path not in names:
                continue

            match = json.loads(archive.read(match_path))
            match_count += 1
            match_schema.update(match.keys())
            match_lineup_ids: set[str] = set()
            match_event_ids: set[str] = set()

            for key in ("home_team", "away_team"):
                if match.get(key) is not None:
                    team_ids.add(str(match[key]))

            for key in ("home_team_line_up", "away_team_line_up"):
                value = match.get(key)
                if isinstance(value, list):
                    for item in value:
                        if not isinstance(item, dict):
                            continue
                        lineup_count += 1
                        pid = extract_player_id(item)
                        if pid is not None:
                            lineup_player_ids.add(pid)
                            match_lineup_ids.add(pid)
                        else:
                            lineup_rows_without_player_id += 1
                        for pkey in ("player_position", "position", "player_role", "role"):
                            role = item.get(pkey)
                            if role:
                                record_position(role)

            match_events = 0
            with archive.open(event_path) as stream:
                for raw_line in stream:
                    if not raw_line.strip():
                        continue
                    event = json.loads(raw_line)
                    match_events += 1
                    event_count += 1
                    event_schema.update(event.keys())
                    pid = extract_player_id(event)
                    if pid is None:
                        missing_player_id_events += 1
                    else:
                        event_rows_with_player_id += 1
                        event_player_ids.add(pid)
                        match_event_ids.add(pid)
                        if pid in match_lineup_ids:
                            event_rows_matched_to_lineup += 1
                        else:
                            event_rows_not_matched_to_lineup += 1
                    for key in ("event_name", "event_type"):
                        if event.get(key):
                            event_types[str(event[key])] += 1
                    role = event.get("player_role") or event.get("player_position")
                    if role:
                        record_position(role)

            comparison = compare_match_player_ids(match_event_ids, match_lineup_ids)
            unique_match_actor_ids += comparison["event_actor_ids"]
            unique_match_actor_ids_matched += comparison["matched_actor_ids"]
            unique_match_actor_ids_unmatched += comparison["unmatched_actor_ids"]
            if comparison["event_actor_ids"] == 0:
                matches_without_actor_ids += 1
            elif comparison["unmatched_actor_ids"] == 0:
                matches_with_all_actor_ids_matched += 1
            else:
                matches_with_unmatched_actor_ids += 1

            if len(sample_matches) < 3:
                sample_matches.append({
                    "match_id": match_id,
                    "date": match.get("date"),
                    "events": match_events,
                    "lineup_rows": sum(
                        len(match.get(key) or []) if isinstance(match.get(key), list) else 0
                        for key in ("home_team_line_up", "away_team_line_up")
                    ),
                    "unique_event_actor_ids": comparison["event_actor_ids"],
                    "actor_ids_matched_to_same_match_lineup": comparison["matched_actor_ids"],
                    "actor_ids_unmatched_in_same_match": comparison["unmatched_actor_ids"],
                })

    result = {
        "dataset": "Afriskaut Dynasty Scouting League 2024 Open Data",
        "archive_bytes": len(archive_bytes),
        "matches_with_event_files": match_count,
        "events": event_count,
        "unique_event_player_ids": len(event_player_ids),
        "unique_lineup_player_ids": len(lineup_player_ids),
        "unique_player_ids_seen_union": len(event_player_ids | lineup_player_ids),
        "event_player_ids_also_seen_in_any_lineup": len(event_player_ids & lineup_player_ids),
        "team_ids_seen": len(team_ids),
        "lineup_rows_detected": lineup_count,
        "lineup_rows_without_player_id": lineup_rows_without_player_id,
        "events_without_player_id": missing_player_id_events,
        "event_rows_with_player_id": event_rows_with_player_id,
        "event_rows_matched_to_same_match_lineup": event_rows_matched_to_lineup,
        "event_rows_not_matched_to_same_match_lineup": event_rows_not_matched_to_lineup,
        "event_row_lineup_match_rate_percent": round(
            100 * event_rows_matched_to_lineup / event_rows_with_player_id, 2
        ) if event_rows_with_player_id else None,
        "unique_match_actor_ids_total": unique_match_actor_ids,
        "unique_match_actor_ids_matched": unique_match_actor_ids_matched,
        "unique_match_actor_ids_unmatched": unique_match_actor_ids_unmatched,
        "matches_with_all_actor_ids_matched": matches_with_all_actor_ids_matched,
        "matches_with_unmatched_actor_ids": matches_with_unmatched_actor_ids,
        "matches_without_actor_ids": matches_without_actor_ids,
        "match_json_fields": sorted(match_schema),
        "event_jsonl_fields": sorted(event_schema),
        "event_name_counts": dict(event_types.most_common(20)),
        "position_role_counts_raw": dict(raw_positions.most_common(30)),
        "position_role_counts_normalized": dict(normalized_positions.most_common(30)),
        "unrecognized_position_labels": dict(unknown_positions.most_common(30)),
        "sample_matches": sample_matches,
        "player_names_exported": False,
        "player_ids_exported": False,
        "duplicate_archive_copies_deduplicated": True,
    }
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
