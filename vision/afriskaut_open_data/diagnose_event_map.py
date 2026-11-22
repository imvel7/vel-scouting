#!/usr/bin/env python3
"""Collect what is needed to compare the publisher's event documentation with the real event labels.

Prints (1) the publisher repository tree outside the dataset archive, (2) the text of small public
documentation files (README / event map), and (3) categorical value counts for event labels. Categorical
fields are summarised only when they have few distinct values; otherwise just the distinct count is
printed. No player names, IDs, team names or free text from event rows are printed, nothing is written to
disk and Supabase is not touched.
"""

from __future__ import annotations

import json
import urllib.request
import zipfile
from collections import Counter, defaultdict
from io import BytesIO
from pathlib import PurePosixPath

REPO = "Afriskaut/dynasty-scouting-league-2024-open-data"
DATASET_URL = f"https://github.com/{REPO}/raw/refs/heads/main/Datasets.zip"
TREE_URL = f"https://api.github.com/repos/{REPO}/git/trees/main?recursive=1"
RAW_URL = f"https://raw.githubusercontent.com/{REPO}/main/"
DOC_SUFFIXES = (".md", ".txt", ".csv", ".json", ".yml", ".yaml")
MAX_DOC_BYTES = 60_000
MAX_DISTINCT = 120
CATEGORICAL_FIELDS = ("event_type", "event_name", "event_outcome", "event_direction", "isHome", "player_role")


def summarize_categories(counter: Counter, max_distinct: int = MAX_DISTINCT) -> dict:
    """Return counts only when the field is clearly categorical, else just the distinct count."""
    distinct = len(counter)
    if distinct <= max_distinct:
        return {"distinct": distinct, "counts": dict(counter.most_common())}
    return {"distinct": distinct, "counts": None}


def cross_summary(pairs: dict[str, Counter], max_inner: int = 25) -> dict:
    """Per first-level key, list second-level counts only when there are few distinct values."""
    out = {}
    for key, inner in sorted(pairs.items()):
        out[key] = dict(inner.most_common()) if len(inner) <= max_inner else {"distinct": len(inner)}
    return out


def is_doc_path(path: str) -> bool:
    lowered = path.lower()
    return lowered.endswith(DOC_SUFFIXES) and not lowered.startswith("datasets/") and "/datasets/" not in lowered


def canonical_event_paths(names: list[str]) -> list[str]:
    """One events.jsonl per match id; the canonical Datasets/ copy wins over a mirror copy in the archive."""
    chosen: dict[str, str] = {}
    for name in sorted(names):
        path = PurePosixPath(name)
        if path.name != "events.jsonl":
            continue
        match_id = path.parent.name
        current = chosen.get(match_id)
        if current is None or ("/Datasets/" in name and "/Datasets/" not in current):
            chosen[match_id] = name
    return [chosen[key] for key in sorted(chosen)]


def fetch(url: str, limit: int | None = None) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": "VelScout-Research-Probe/0.1"})
    with urllib.request.urlopen(request, timeout=180) as response:
        return response.read(limit) if limit else response.read()


def main() -> int:
    tree = json.loads(fetch(TREE_URL))
    entries = [
        {"path": item["path"], "size": item.get("size")}
        for item in tree.get("tree", []) if item.get("type") == "blob"
        and not item["path"].lower().startswith("datasets/")
    ]
    print("=== REPOSITORY FILES OUTSIDE Datasets/ ===")
    print(json.dumps(entries, indent=1))

    for item in entries:
        path, size = item["path"], item.get("size") or 0
        if is_doc_path(path) and size <= MAX_DOC_BYTES:
            print(f"\n=== DOC: {path} ({size} bytes) ===")
            print(fetch(RAW_URL + path).decode("utf-8", errors="replace"))

    archive_bytes = fetch(DATASET_URL)
    field_counts = {field: Counter() for field in CATEGORICAL_FIELDS}
    outcome_by_type: dict[str, Counter] = defaultdict(Counter)
    name_by_type: dict[str, Counter] = defaultdict(Counter)
    context_values = set()
    zip_extra = []
    with zipfile.ZipFile(BytesIO(archive_bytes)) as archive:
        names = archive.namelist()
        zip_extra = sorted({PurePosixPath(n).name for n in names
                            if PurePosixPath(n).name not in ("match.json", "events.jsonl") and not n.endswith("/")})[:40]
        for name in canonical_event_paths(names):
            with archive.open(name) as stream:
                for raw_line in stream:
                    if not raw_line.strip():
                        continue
                    event = json.loads(raw_line)
                    event_type = str(event.get("event_type") or "").strip().upper()
                    for field in CATEGORICAL_FIELDS:
                        field_counts[field][str(event.get(field))] += 1
                    outcome_by_type[event_type][str(event.get("event_outcome"))] += 1
                    name_by_type[event_type][str(event.get("event_name"))] += 1
                    context_values.add(str(event.get("event_context")))

    print("\n=== OTHER FILE NAMES INSIDE Datasets.zip (excluding match.json/events.jsonl, first 40 distinct) ===")
    print(json.dumps(zip_extra))
    print("\n=== CATEGORICAL EVENT FIELDS ===")
    print(json.dumps({field: summarize_categories(counter) for field, counter in field_counts.items()}, indent=1))
    print("\n=== event_outcome BY event_type ===")
    print(json.dumps(cross_summary(outcome_by_type), indent=1))
    print("\n=== event_name BY event_type ===")
    print(json.dumps(cross_summary(name_by_type), indent=1))
    print("\n=== event_context distinct values (count only) ===")
    print(len(context_values))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
