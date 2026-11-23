#!/usr/bin/env python3
"""Run the conservative minutes calculation on the real Afriskaut dataset and print aggregate counts.

Prints only counts and distributions: no player names, player IDs, team names or per-player values, writes
nothing to disk and does not touch Supabase. The key self-consistency check is the share of players whose
own events fall outside the interval computed for them, reported at several tolerances.
"""

from __future__ import annotations

import json
import statistics
import urllib.request
import zipfile
from collections import Counter
from io import BytesIO
from pathlib import PurePosixPath

from player_minutes import STATUS_UNAVAILABLE, compute_match_minutes

DATASET_URL = "https://github.com/Afriskaut/dynasty-scouting-league-2024-open-data/raw/refs/heads/main/Datasets.zip"
TOLERANCES = (0, 10, 60)
PRIMARY_TOLERANCE = 10


def spread(values: list[float]) -> dict | None:
    if not values:
        return None
    return {"min": round(min(values), 2), "median": round(statistics.median(values), 2),
            "max": round(max(values), 2), "n": len(values)}


def main() -> int:
    request = urllib.request.Request(DATASET_URL, headers={"User-Agent": "VelScout-Research-Probe/0.1"})
    with urllib.request.urlopen(request, timeout=180) as response:
        archive_bytes = response.read()

    status_counts: Counter = Counter()
    reason_counts: Counter = Counter()
    basis_counts: Counter = Counter()
    minutes_by_basis: dict[str, list[float]] = {}
    outside_by_tolerance = {tol: Counter() for tol in TOLERANCES}
    matches_with_clock = matches_without_clock = 0
    consistent_matches = inconsistent_matches = 0
    players_with_events = players_with_events_minutes = 0
    total_played_minutes: list[float] = []
    card_events: Counter = Counter()

    with zipfile.ZipFile(BytesIO(archive_bytes)) as archive:
        names = set(archive.namelist())
        match_paths: dict[str, str] = {}
        for name in sorted(names):
            if PurePosixPath(name).name != "match.json":
                continue
            match_id = PurePosixPath(name).parent.name
            current = match_paths.get(match_id)
            if current is None or ("/Datasets/" in name and "/Datasets/" not in current):
                match_paths[match_id] = name

        for _match_id, match_path in sorted(match_paths.items()):
            event_path = str(PurePosixPath(match_path).parent) + "/events.jsonl"
            if event_path not in names:
                continue
            match = json.loads(archive.read(match_path))
            events = []
            with archive.open(event_path) as stream:
                for raw_line in stream:
                    if raw_line.strip():
                        events.append(json.loads(raw_line))
            actors_with_events = {str(e.get("player_id")).strip() for e in events if e.get("player_id")}
            for e in events:
                if str(e.get("event_name") or "").strip().upper() == "CARD":
                    card_events[f"{str(e.get('event_type') or '').strip().upper()}:{str(e.get('event_outcome') or '').strip().upper()}"] += 1

            primary = compute_match_minutes(match, events, tolerance=PRIMARY_TOLERANCE)
            if primary["total_played_seconds"] is None:
                matches_without_clock += 1
            else:
                matches_with_clock += 1
                total_played_minutes.append(primary["total_played_seconds"] / 60)
                if primary["substitution_records_consistent"]:
                    consistent_matches += 1
                else:
                    inconsistent_matches += 1
            for pid, record in primary["players"].items():
                status_counts[record["status"]] += 1
                for reason in record["reasons"]:
                    reason_counts[reason] += 1
                if record["status"] != STATUS_UNAVAILABLE:
                    basis_counts[record["basis"]] += 1
                    minutes_by_basis.setdefault(record["basis"], []).append(record["minutes_seconds"] / 60)
                if pid in actors_with_events:
                    players_with_events += 1
                    if record["minutes_seconds"] is not None:
                        players_with_events_minutes += 1

            for tol in TOLERANCES:
                result = compute_match_minutes(match, events, tolerance=tol)
                for record in result["players"].values():
                    if "events_outside_computed_interval" in record["reasons"]:
                        outside_by_tolerance[tol]["players_blocked_by_outside_events"] += 1
                        outside_by_tolerance[tol]["outside_events"] += record["events_outside_interval"]
                    elif record["minutes_seconds"] is not None:
                        outside_by_tolerance[tol]["players_with_minutes"] += 1

    print(json.dumps({
        "dataset": "Afriskaut Dynasty Scouting League 2024 Open Data",
        "primary_tolerance_seconds": PRIMARY_TOLERANCE,
        "matches_with_usable_clock": matches_with_clock,
        "matches_without_usable_clock": matches_without_clock,
        "regular_time_played_minutes": spread(total_played_minutes),
        "card_events_by_type_and_outcome": dict(card_events),
        "matches_with_consistent_substitution_records": consistent_matches,
        "matches_with_inconsistent_substitution_records": inconsistent_matches,
        "player_status_counts": dict(status_counts),
        "unavailable_reason_counts": dict(reason_counts.most_common()),
        "minutes_basis_counts": dict(basis_counts),
        "minutes_by_basis": {basis: spread(values) for basis, values in minutes_by_basis.items()},
        "players_with_events": players_with_events,
        "players_with_events_and_minutes": players_with_events_minutes,
        "share_players_with_events_that_have_minutes": (
            round(players_with_events_minutes / players_with_events, 4) if players_with_events else None),
        "self_consistency_by_tolerance_seconds": {str(t): dict(c) for t, c in outside_by_tolerance.items()},
        "player_names_exported": False,
        "player_ids_exported": False,
        "per_player_values_exported": False,
    }, indent=1, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
