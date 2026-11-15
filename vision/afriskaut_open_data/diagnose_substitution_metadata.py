#!/usr/bin/env python3
"""Check whether unmatched event actors are listed in match substitution metadata."""

from __future__ import annotations

import json
import urllib.request
import zipfile
from collections import Counter
from io import BytesIO
from pathlib import PurePosixPath

DATASET_URL = "https://github.com/Afriskaut/dynasty-scouting-league-2024-open-data/raw/refs/heads/main/Datasets.zip"
SUB_FIELDS = (
    "home_team_subs",
    "away_team_subs",
    "home_substitutions",
    "away_substitutions",
    "substitutions",
)


def walk_shapes(value, path="root"):
    """Yield structural paths and key sets without exposing field values."""
    if isinstance(value, dict):
        yield path, "object", tuple(sorted(value.keys()))
        for key, child in value.items():
            yield from walk_shapes(child, f"{path}.{key}")
    elif isinstance(value, list):
        yield path, "array", ()
        for index, child in enumerate(value[:3]):
            yield from walk_shapes(child, f"{path}[]")


def collect_named_player_ids(value) -> set[str]:
    """Collect only explicitly named player_id/playerId values."""
    found: set[str] = set()
    if isinstance(value, dict):
        for key, child in value.items():
            if key in ("player_id", "playerId") and child is not None:
                found.add(str(child).strip())
            else:
                found.update(collect_named_player_ids(child))
    elif isinstance(value, list):
        for child in value:
            found.update(collect_named_player_ids(child))
    return {item for item in found if item}


def main() -> int:
    request = urllib.request.Request(DATASET_URL, headers={"User-Agent": "VelScout-Research-Probe/0.1"})
    with urllib.request.urlopen(request, timeout=120) as response:
        archive_bytes = response.read()

    with zipfile.ZipFile(BytesIO(archive_bytes)) as archive:
        names = archive.namelist()
        match_paths: dict[str, str] = {}
        for name in sorted(names):
            if PurePosixPath(name).name != "match.json":
                continue
            match_id = PurePosixPath(name).parent.name
            current = match_paths.get(match_id)
            if current is None or ("/Datasets/" in name and "/Datasets/" not in current):
                match_paths[match_id] = name

        field_presence = Counter()
        field_types = {key: Counter() for key in SUB_FIELDS}
        field_entry_keys = {key: Counter() for key in SUB_FIELDS}
        field_candidate_player_ids = Counter()
        total_event_rows = 0
        total_event_rows_with_id = 0
        event_rows_matched_lineup = 0
        event_rows_matched_lineup_or_subs = 0
        matches_with_sub_ids = 0
        total_unique_sub_ids = 0

        for match_id, match_path in sorted(match_paths.items()):
            parent = str(PurePosixPath(match_path).parent)
            event_path = parent + "/events.jsonl"
            if event_path not in names:
                continue
            match = json.loads(archive.read(match_path))
            lineup_ids: set[str] = set()
            for lineup_key in ("home_team_line_up", "away_team_line_up"):
                for item in match.get(lineup_key) or []:
                    if isinstance(item, dict):
                        pid = item.get("player_id") or item.get("id") or item.get("_id")
                        if pid is not None and str(pid).strip():
                            lineup_ids.add(str(pid).strip())

            substitution_ids: set[str] = set()
            for field in SUB_FIELDS:
                if field not in match:
                    continue
                field_presence[field] += 1
                value = match[field]
                field_types[field][type(value).__name__] += 1
                for path, kind, keys in walk_shapes(value, field):
                    if keys:
                        field_entry_keys[field].update(keys)
                found = collect_named_player_ids(value)
                field_candidate_player_ids[field] += len(found)
                substitution_ids.update(found)

            if substitution_ids:
                matches_with_sub_ids += 1
                total_unique_sub_ids += len(substitution_ids)

            with archive.open(event_path) as stream:
                for raw_line in stream:
                    if not raw_line.strip():
                        continue
                    event = json.loads(raw_line)
                    total_event_rows += 1
                    pid = event.get("player_id")
                    if pid is None:
                        continue
                    total_event_rows_with_id += 1
                    pid = str(pid).strip()
                    if pid in lineup_ids:
                        event_rows_matched_lineup += 1
                    if pid in lineup_ids or pid in substitution_ids:
                        event_rows_matched_lineup_or_subs += 1

    summary = {
        "dataset": "Afriskaut Dynasty Scouting League 2024 Open Data",
        "matches_inspected": len(match_paths),
        "substitution_fields_present_in_matches": dict(field_presence),
        "substitution_field_types": {key: dict(value) for key, value in field_types.items()},
        "substitution_entry_key_frequency": {
            key: dict(value.most_common(25)) for key, value in field_entry_keys.items()
        },
        "explicit_player_id_values_found_in_substitution_fields": dict(field_candidate_player_ids),
        "matches_with_any_explicit_substitution_player_ids": matches_with_sub_ids,
        "sum_unique_substitution_player_ids_per_match": total_unique_sub_ids,
        "event_rows": total_event_rows,
        "event_rows_with_player_id": total_event_rows_with_id,
        "event_rows_matching_lineup_only": event_rows_matched_lineup,
        "event_rows_matching_lineup_or_explicit_substitution_ids": event_rows_matched_lineup_or_subs,
        "expanded_match_rate_percent": round(
            100 * event_rows_matched_lineup_or_subs / total_event_rows_with_id, 2
        ) if total_event_rows_with_id else None,
        "player_names_exported": False,
        "player_ids_exported": False,
        "field_values_exported": False,
    }
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
