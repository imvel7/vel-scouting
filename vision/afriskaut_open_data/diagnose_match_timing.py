#!/usr/bin/env python3
"""Describe the structure of Afriskaut match/event timing data without exporting personal data.

Prints aggregate structure only: field paths, value types, numeric ranges, a small set of
categorical event-type counts and character-class shapes for timing-like string fields.
It never prints player names, player IDs, team names or any free-text value, writes nothing
to disk and does not touch Supabase.
"""

from __future__ import annotations

import json
import re
import statistics
import urllib.request
import zipfile
from collections import Counter, defaultdict
from io import BytesIO
from pathlib import PurePosixPath

DATASET_URL = "https://github.com/Afriskaut/dynasty-scouting-league-2024-open-data/raw/refs/heads/main/Datasets.zip"
TIMING_KEY_RE = re.compile(
    r"(period|time|minute|second|clock|start|end|duration|half|stoppage|extra|kick|sub|status|phase|position|formation)",
    re.IGNORECASE,
)
BLOCKED_KEY_RE = re.compile(r"(name|player|team|club|coach|referee|venue|url|email|id)$", re.IGNORECASE)


def string_shape(value: str) -> str:
    """Replace letters and digits by character classes so no real text is exported."""
    return re.sub(r"[A-Za-z]", "a", re.sub(r"\d", "9", value))[:40]


class SchemaStats:
    def __init__(self) -> None:
        self.type_counts: dict[str, Counter] = defaultdict(Counter)
        self.numbers: dict[str, list[float]] = defaultdict(list)
        self.shapes: dict[str, Counter] = defaultdict(Counter)

    def add(self, value, path: str = "root") -> None:
        if isinstance(value, dict):
            self.type_counts[path]["object"] += 1
            for key, child in value.items():
                self.add(child, f"{path}.{key}")
        elif isinstance(value, list):
            self.type_counts[path]["array"] += 1
            for child in value:
                self.add(child, f"{path}[]")
        else:
            kind = "null" if value is None else type(value).__name__
            self.type_counts[path][kind] += 1
            key = path.rsplit(".", 1)[-1]
            if isinstance(value, bool):
                return
            if isinstance(value, (int, float)):
                if len(self.numbers[path]) < 5000:
                    self.numbers[path].append(float(value))
            elif isinstance(value, str) and TIMING_KEY_RE.search(key) and not BLOCKED_KEY_RE.search(key):
                self.shapes[path][string_shape(value)] += 1

    def summary(self) -> dict:
        out = {}
        for path in sorted(self.type_counts):
            entry: dict = {"types": dict(self.type_counts[path])}
            numbers = self.numbers.get(path)
            if numbers:
                entry["numeric"] = {
                    "min": min(numbers),
                    "max": max(numbers),
                    "median": statistics.median(numbers),
                    "sampled": len(numbers),
                }
            shapes = self.shapes.get(path)
            if shapes:
                entry["string_shapes_top5"] = dict(shapes.most_common(5))
            out[path] = entry
        return out


def main() -> int:
    request = urllib.request.Request(DATASET_URL, headers={"User-Agent": "VelScout-Research-Probe/0.1"})
    with urllib.request.urlopen(request, timeout=180) as response:
        archive_bytes = response.read()

    match_stats = SchemaStats()
    event_stats = SchemaStats()
    event_type_counts: Counter = Counter()
    periods_per_match: Counter = Counter()
    matches = 0

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

        for _match_id, match_path in sorted(match_paths.items()):
            event_path = str(PurePosixPath(match_path).parent) + "/events.jsonl"
            if event_path not in names:
                continue
            matches += 1
            match_stats.add(json.loads(archive.read(match_path)))
            seen_periods: set = set()
            with archive.open(event_path) as stream:
                for raw_line in stream:
                    if not raw_line.strip():
                        continue
                    event = json.loads(raw_line)
                    event_stats.add(event)
                    event_type_counts[str(event.get("event_type") or "").strip().upper()] += 1
                    if "period" in event:
                        seen_periods.add(str(event.get("period")))
            periods_per_match[",".join(sorted(seen_periods))] += 1

    print(json.dumps({
        "dataset": "Afriskaut Dynasty Scouting League 2024 Open Data",
        "matches_inspected": matches,
        "match_json_structure": match_stats.summary(),
        "event_structure": event_stats.summary(),
        "event_type_counts_top60": dict(event_type_counts.most_common(60)),
        "distinct_period_sets_per_match": dict(periods_per_match.most_common(10)),
        "player_names_exported": False,
        "player_ids_exported": False,
        "free_text_values_exported": False,
    }, indent=1, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
