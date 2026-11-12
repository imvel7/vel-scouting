#!/usr/bin/env python3
"""Classify event actors not linked to the same match's lineup or substitution metadata."""

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


def collect_player_ids(value) -> set[str]:
    found: set[str] = set()
    if isinstance(value, dict):
        for key, child in value.items():
            if key in ("player_id", "playerId") and child is not None:
                found.add(str(child).strip())
            else:
                found.update(collect_player_ids(child))
    elif isinstance(value, list):
        for child in value:
            found.update(collect_player_ids(child))
    return {value for value in found if value}


def actor_id(event) -> str | None:
    value = event.get("player_id")
    if value is None or not str(value).strip():
        return None
    return str(value).strip()


def add_value(counter: Counter, value) -> None:
    if value is None:
        counter["<missing>"] += 1
    elif isinstance(value, (str, int, float, bool)):
        counter[str(value)] += 1
    else:
        counter[f"<{type(value).__name__}>"] += 1


def main() -> int:
    request = urllib.request.Request(DATASET_URL, headers={"User-Agent": "VelScout-Research-Probe/0.1"})
    with urllib.request.urlopen(request, timeout=120) as response:
        archive_bytes = response.read()

    with zipfile.ZipFile(BytesIO(archive_bytes)) as archive:
        names = archive.namelist()
        match_paths = {}
        for name in sorted(names):
            if PurePosixPath(name).name != "match.json":
                continue
            mid = PurePosixPath(name).parent.name
            old = match_paths.get(mid)
            if old is None or ("/Datasets/" in name and "/Datasets/" not in old):
                match_paths[mid] = name

        per_match = []
        for mid, match_path in sorted(match_paths.items()):
            parent = str(PurePosixPath(match_path).parent)
            event_path = parent + "/events.jsonl"
            if event_path not in names:
                continue
            match = json.loads(archive.read(match_path))
            lineup_ids: set[str] = set()
            for key in ("home_team_line_up", "away_team_line_up"):
                for item in match.get(key) or []:
                    if isinstance(item, dict):
                        for id_key in ("player_id", "id", "_id"):
                            value = item.get(id_key)
                            if value is not None and str(value).strip():
                                lineup_ids.add(str(value).strip())
                                break
            substitution_ids: set[str] = set()
            for key in SUB_FIELDS:
                substitution_ids.update(collect_player_ids(match.get(key)))
            per_match.append((mid, match, event_path, lineup_ids, substitution_ids))

        global_known_ids = {
            pid for _, _, _, lineup, subs in per_match for pid in (lineup | subs)
        }
        global_events_ids: set[str] = set()
        for _, _, event_path, _, _ in per_match:
            with archive.open(event_path) as stream:
                for raw in stream:
                    if raw.strip():
                        pid = actor_id(json.loads(raw))
                        if pid:
                            global_events_ids.add(pid)

        residual_event_rows = 0
        residual_ids: set[str] = set()
        residual_by_event_name = Counter()
        residual_by_event_type = Counter()
        residual_by_role = Counter()
        residual_by_side = Counter()
        residual_by_team_relation = Counter()
        residual_by_match = Counter()
        residual_with_id_found_elsewhere_in_lineup_or_subs = 0
        total_rows = 0

        for mid, match, event_path, lineup_ids, sub_ids in per_match:
            home_team = str(match.get("home_team")) if match.get("home_team") is not None else None
            away_team = str(match.get("away_team")) if match.get("away_team") is not None else None
            with archive.open(event_path) as stream:
                for raw in stream:
                    if not raw.strip():
                        continue
                    event = json.loads(raw)
                    total_rows += 1
                    pid = actor_id(event)
                    if not pid or pid in lineup_ids or pid in sub_ids:
                        continue

                    residual_event_rows += 1
                    residual_ids.add(pid)
                    residual_by_match[mid] += 1
                    add_value(residual_by_event_name, event.get("event_name"))
                    add_value(residual_by_event_type, event.get("event_type"))
                    add_value(residual_by_role, event.get("player_role") or event.get("player_position"))
                    add_value(residual_by_side, event.get("isHome"))
                    event_team = str(event.get("team_id")) if event.get("team_id") is not None else None
                    relation = (
                        "home_team" if event_team is not None and event_team == home_team else
                        "away_team" if event_team is not None and event_team == away_team else
                        "missing_team_id" if event_team is None else
                        "team_id_not_equal_to_match_teams"
                    )
                    residual_by_team_relation[relation] += 1
                    if pid in global_known_ids:
                        residual_with_id_found_elsewhere_in_lineup_or_subs += 1

    print(json.dumps({
        "dataset": "Afriskaut Dynasty Scouting League 2024 Open Data",
        "substitution_fields_checked": list(SUB_FIELDS),
        "events_examined": total_rows,
        "residual_event_rows": residual_event_rows,
        "residual_unique_player_ids": len(residual_ids),
        "residual_rows_with_id_found_in_another_match_lineup_or_subs": residual_with_id_found_elsewhere_in_lineup_or_subs,
        "residual_rows_by_event_name": dict(residual_by_event_name.most_common()),
        "residual_rows_by_event_type": dict(residual_by_event_type.most_common()),
        "residual_rows_by_position_role": dict(residual_by_role.most_common()),
        "residual_rows_by_isHome": dict(residual_by_side.most_common()),
        "residual_rows_by_team_relation": dict(residual_by_team_relation.most_common()),
        "matches_with_residual_rows": len(residual_by_match),
        "max_residual_rows_in_one_match": max(residual_by_match.values(), default=0),
        "player_names_exported": False,
        "player_ids_exported": False,
        "raw_event_context_exported": False,
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
