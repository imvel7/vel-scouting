#!/usr/bin/env python3
"""Check whether Afriskaut match clocks can support verified player minutes.

Aggregate counts only: no player names, player IDs, team names or free text are printed, nothing is
written to disk and Supabase is not touched. Player IDs are compared in memory only.

Questions answered (each reported as counts, never as values tied to a person):
1. Are the four match clock fields present, parseable and in order?
2. Do event times fall inside the window implied by their `event_half` value, and what does
   `event_half = 0` correspond to?
3. Do SUBSTITUTION events line up with the substitutions listed in match.json, and which side
   (player in / player out) does the event actor belong to?
"""

from __future__ import annotations

import json
import re
import statistics
import urllib.request
import zipfile
from collections import Counter
from io import BytesIO
from pathlib import PurePosixPath

DATASET_URL = "https://github.com/Afriskaut/dynasty-scouting-league-2024-open-data/raw/refs/heads/main/Datasets.zip"
SUB_LIST_FIELDS = ("home_substitutions", "away_substitutions", "substitutions")
HMS_RE = re.compile(r"^\s*(\d{1,3}):([0-5]\d):([0-5]\d)(?:\.\d+)?\s*$")


def parse_hms(value) -> int | None:
    """Return whole seconds for an HH:MM:SS string, or None when missing or malformed."""
    if not isinstance(value, str):
        return None
    match = HMS_RE.match(value)
    if not match:
        return None
    hours, minutes, seconds = (int(part) for part in match.groups())
    return hours * 3600 + minutes * 60 + seconds


def match_clock(match: dict) -> dict:
    """Parse the four regular-time clock fields. Missing or unparseable values stay None."""
    keys = ("match_start_time", "first_half_end_time", "second_half_start_time", "match_end_time")
    parsed = {key: parse_hms(match.get(key)) for key in keys}
    values = [parsed[key] for key in keys]
    parsed["complete"] = all(v is not None for v in values)
    parsed["ordered"] = parsed["complete"] and values == sorted(values)
    return parsed


def classify_window(seconds: int | None, clock: dict) -> str:
    """Place an event time inside the match clock. Boundaries are inclusive."""
    if seconds is None or not clock.get("ordered"):
        return "unknown"
    if seconds < clock["match_start_time"]:
        return "before_start"
    if seconds <= clock["first_half_end_time"]:
        return "first_half"
    if seconds < clock["second_half_start_time"]:
        return "break"
    if seconds <= clock["match_end_time"]:
        return "second_half"
    return "after_end"


def substitution_pairs(match: dict) -> tuple[int, set[str], set[str]]:
    """Return (listed substitution count, player-in IDs, player-out IDs) for one match."""
    count = 0
    ins: set[str] = set()
    outs: set[str] = set()
    for field in SUB_LIST_FIELDS:
        for entry in match.get(field) or []:
            if not isinstance(entry, dict):
                continue
            count += 1
            for side, bucket in (("in", ins), ("out", outs)):
                player = entry.get(side)
                pid = player.get("player_id") if isinstance(player, dict) else None
                if pid is not None and str(pid).strip():
                    bucket.add(str(pid).strip())
    return count, ins, outs


def actor_side(player_id, ins: set[str], outs: set[str]) -> str:
    pid = str(player_id).strip() if player_id is not None else ""
    if not pid:
        return "no_actor"
    if pid in ins and pid in outs:
        return "in_and_out"
    if pid in ins:
        return "player_in"
    if pid in outs:
        return "player_out"
    return "not_listed"


def compare_counts(event_count: int, listed_count: int) -> str:
    if event_count == listed_count:
        return "equal"
    if listed_count and event_count == 2 * listed_count:
        return "events_exactly_double"
    return "events_more" if event_count > listed_count else "events_fewer"


MIN_CELL_SIZE = 5  # public CI logs: no min/median/max for fewer than 5 records


def spread(values: list[float]) -> dict | None:
    if not values:
        return None
    if len(values) < MIN_CELL_SIZE:  # small cell: could describe one individual record
        return {"n": len(values), "suppressed": True}
    return {"min": min(values), "median": statistics.median(values), "max": max(values), "n": len(values)}


def main() -> int:
    request = urllib.request.Request(DATASET_URL, headers={"User-Agent": "VelScout-Research-Probe/0.1"})
    with urllib.request.urlopen(request, timeout=180) as response:
        archive_bytes = response.read()

    clock_status: Counter = Counter()
    half_lengths_min: list[float] = []
    second_half_lengths_min: list[float] = []
    break_lengths_min: list[float] = []
    window_by_half: dict[str, Counter] = {}
    stop_before_start = 0
    events_total = 0
    sub_count_compare: Counter = Counter()
    sub_actor_side: Counter = Counter()
    sub_event_window: Counter = Counter()
    sub_total_events = 0
    sub_total_listed = 0
    half_value_counts: Counter = Counter()

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
            clock = match_clock(match)
            clock_status["complete" if clock["complete"] else "incomplete"] += 1
            clock_status["ordered" if clock["ordered"] else "not_ordered"] += 1
            if clock["ordered"]:
                half_lengths_min.append((clock["first_half_end_time"] - clock["match_start_time"]) / 60)
                second_half_lengths_min.append((clock["match_end_time"] - clock["second_half_start_time"]) / 60)
                break_lengths_min.append((clock["second_half_start_time"] - clock["first_half_end_time"]) / 60)

            listed, ins, outs = substitution_pairs(match)
            sub_total_listed += listed
            match_sub_events = 0

            with archive.open(event_path) as stream:
                for raw_line in stream:
                    if not raw_line.strip():
                        continue
                    event = json.loads(raw_line)
                    events_total += 1
                    half = str(event.get("event_half"))
                    half_value_counts[half] += 1
                    start = parse_hms(event.get("event_start_time"))
                    stop = parse_hms(event.get("event_stop_time"))
                    if start is not None and stop is not None and stop < start:
                        stop_before_start += 1
                    window = classify_window(start, clock)
                    window_by_half.setdefault(half, Counter())[window] += 1
                    if str(event.get("event_type") or "").strip().upper() == "SUBSTITUTION":
                        match_sub_events += 1
                        sub_actor_side[actor_side(event.get("player_id"), ins, outs)] += 1
                        sub_event_window[window] += 1
            sub_total_events += match_sub_events
            sub_count_compare[compare_counts(match_sub_events, listed)] += 1

    print(json.dumps({
        "dataset": "Afriskaut Dynasty Scouting League 2024 Open Data",
        "events_total": events_total,
        "match_clock_status": dict(clock_status),
        "first_half_length_minutes": spread(half_lengths_min),
        "second_half_length_minutes": spread(second_half_lengths_min),
        "half_time_break_minutes": spread(break_lengths_min),
        "event_half_value_counts": dict(half_value_counts),
        "event_window_by_event_half": {half: dict(counter) for half, counter in sorted(window_by_half.items())},
        "events_with_stop_before_start": stop_before_start,
        "substitution_events_total": sub_total_events,
        "substitutions_listed_in_match_json": sub_total_listed,
        "substitution_event_count_vs_listed_per_match": dict(sub_count_compare),
        "substitution_event_actor_side": dict(sub_actor_side),
        "substitution_event_window": dict(sub_event_window),
        "player_names_exported": False,
        "player_ids_exported": False,
    }, indent=1, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
