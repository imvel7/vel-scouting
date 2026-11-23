#!/usr/bin/env python3
"""Aggregate-only validation of event-map-aware centre-back metrics on the real Afriskaut data.

Prints counts and quartiles for cohorts of at least MIN_COHORT player-matches. No names, IDs, team names or
per-player values are printed; nothing is written to disk and Supabase is not touched.
Per-90 uses only player-matches whose minutes status is verified, or derived in a fully consistent match,
and a minimum of 45 played minutes.
"""

from __future__ import annotations

import json
import urllib.request
import zipfile
from collections import Counter
from io import BytesIO
from pathlib import PurePosixPath

from center_back_metrics import LINEUP_FIELDS, SUBSTITUTION_FIELDS, _center_back_ids, _nested_player_ids, _player_id
from cb_profile import METRIC_IDS, count_metrics, per90, quartiles
from event_attribution import classify_event_attribution
from player_minutes import STATUS_DERIVED, STATUS_VERIFIED, compute_match_minutes

DATASET_URL = "https://github.com/Afriskaut/dynasty-scouting-league-2024-open-data/raw/refs/heads/main/Datasets.zip"
MIN_SECONDS = 45 * 60


def main() -> int:
    request = urllib.request.Request(DATASET_URL, headers={"User-Agent": "VelScout-Research-Probe/0.1"})
    with urllib.request.urlopen(request, timeout=180) as response:
        archive_bytes = response.read()

    rates: dict[str, list[float]] = {m: [] for m in METRIC_IDS}
    totals = Counter()
    unmapped: Counter = Counter()
    cb_entries = cb_with_minutes = cb_used = 0
    by_status: Counter = Counter()

    with zipfile.ZipFile(BytesIO(archive_bytes)) as archive:
        names = set(archive.namelist())
        paths: dict[str, str] = {}
        for name in sorted(names):
            if PurePosixPath(name).name != "match.json":
                continue
            mid = PurePosixPath(name).parent.name
            cur = paths.get(mid)
            if cur is None or ("/Datasets/" in name and "/Datasets/" not in cur):
                paths[mid] = name
        for path in paths.values():
            event_path = str(PurePosixPath(path).parent) + "/events.jsonl"
            if event_path not in names:
                continue
            match = json.loads(archive.read(path))
            with archive.open(event_path) as stream:
                events = [json.loads(raw) for raw in stream if raw.strip()]
            lineup_ids = {pid for f in LINEUP_FIELDS for p in (match.get(f) if isinstance(match.get(f), list) else [])
                          if isinstance(p, dict) for pid in [_player_id(p)] if pid}
            sub_ids = set()
            for f in SUBSTITUTION_FIELDS:
                sub_ids.update(_nested_player_ids(match.get(f)))
            cb_ids = _center_back_ids(match)
            minutes = compute_match_minutes(match, events)["players"]
            per_player: dict[str, list[dict]] = {pid: [] for pid in cb_ids}
            for event in events:
                if not classify_event_attribution(event, lineup_ids, sub_ids).player_metrics_eligible:
                    continue
                pid = str(event.get("player_id") or "").strip()
                if pid in per_player:
                    per_player[pid].append(event)
            for pid, evs in per_player.items():
                cb_entries += 1
                record = minutes.get(pid)
                if not record or record["minutes_seconds"] is None:
                    by_status[record["status"] if record else "no_record"] += 1
                    continue
                cb_with_minutes += 1
                by_status[record["status"]] += 1
                if record["status"] not in (STATUS_VERIFIED, STATUS_DERIVED) or record["minutes_seconds"] < MIN_SECONDS:
                    continue
                cb_used += 1
                counts, unm, _ = count_metrics(evs)
                unmapped.update(unm)
                for metric in METRIC_IDS:
                    rates[metric].append(per90(counts[metric], record["minutes_seconds"]))
                totals.update(counts)

    report = {
        "centre_back_lineup_player_matches": cb_entries,
        "with_minutes": cb_with_minutes,
        "used_for_per90_min_45_minutes": cb_used,
        "minutes_status_counts": dict(by_status),
        "metric_totals_in_used_player_matches": dict(totals),
        "per90_quartiles_by_metric": {m: quartiles(v) for m, v in rates.items()},
        "unmapped_event_name_event_type_top20": [
            {"event_name": n, "event_type": t, "count": c} for (n, t), c in unmapped.most_common(20)],
        "unmapped_distinct_pairs": len(unmapped),
        "player_ids_exported": False,
        "player_names_exported": False,
    }
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
