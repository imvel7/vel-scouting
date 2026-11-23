#!/usr/bin/env python3
"""Aggregate-only check of why centre-backs show few events: where do PASS rows get lost?

Prints counts only (no names, IDs or per-player values). Stages for PASS rows and for all rows:
total -> has player_id -> player_id in same-match lineup/subs -> belongs to a lineup Center Back.
Also the ratio of PASS rows per lineup starter per match, to compare with football expectations.
"""

from __future__ import annotations

import json
import statistics
import urllib.request
import zipfile
from collections import Counter
from io import BytesIO
from pathlib import PurePosixPath

from center_back_metrics import LINEUP_FIELDS, SUBSTITUTION_FIELDS, _center_back_ids, _nested_player_ids, _player_id

DATASET_URL = "https://github.com/Afriskaut/dynasty-scouting-league-2024-open-data/raw/refs/heads/main/Datasets.zip"


def main() -> int:
    req = urllib.request.Request(DATASET_URL, headers={"User-Agent": "VelScout-Research-Probe/0.1"})
    with urllib.request.urlopen(req, timeout=180) as r:
        data = r.read()
    stage: Counter = Counter()
    pass_per_starter: list[float] = []
    pass_by_cb_match: list[int] = []
    cb_lineup_entries = 0
    with zipfile.ZipFile(BytesIO(data)) as z:
        names = set(z.namelist())
        paths: dict[str, str] = {}
        for n in sorted(names):
            if PurePosixPath(n).name != "match.json":
                continue
            mid = PurePosixPath(n).parent.name
            cur = paths.get(mid)
            if cur is None or ("/Datasets/" in n and "/Datasets/" not in cur):
                paths[mid] = n
        for p in paths.values():
            ep = str(PurePosixPath(p).parent) + "/events.jsonl"
            if ep not in names:
                continue
            match = json.loads(z.read(p))
            with z.open(ep) as s:
                events = [json.loads(x) for x in s if x.strip()]
            lineup = {pid for f in LINEUP_FIELDS for q in (match.get(f) if isinstance(match.get(f), list) else [])
                      if isinstance(q, dict) for pid in [_player_id(q)] if pid}
            subs = set()
            for f in SUBSTITUTION_FIELDS:
                subs.update(_nested_player_ids(match.get(f)))
            cbs = _center_back_ids(match)
            cb_lineup_entries += len(cbs)
            per_cb = Counter()
            per_starter = Counter()
            for e in events:
                is_pass = str(e.get("event_name") or "").strip().upper() == "PASS"
                keys = ["all"] + (["pass"] if is_pass else [])
                pid = str(e.get("player_id") or "").strip()
                for k in keys:
                    stage[f"{k}:1_total"] += 1
                    if pid:
                        stage[f"{k}:2_has_player_id"] += 1
                        if pid in lineup or pid in subs:
                            stage[f"{k}:3_in_match_lineup_or_subs"] += 1
                            if pid in lineup:
                                stage[f"{k}:4_in_lineup_starters"] += 1
                            if pid in cbs:
                                stage[f"{k}:5_by_lineup_centre_back"] += 1
                if is_pass and pid in lineup:
                    per_starter[pid] += 1
                if is_pass and pid in cbs:
                    per_cb[pid] += 1
            if lineup:
                pass_per_starter.append(sum(per_starter.values()) / len(lineup))
            pass_by_cb_match.extend(per_cb.get(c, 0) for c in cbs)
    out = {
        "stages": dict(sorted(stage.items())),
        "lineup_starter_pass_rows_per_starter_per_match": {
            "matches": len(pass_per_starter),
            "median": round(statistics.median(pass_per_starter), 1) if pass_per_starter else None},
        "lineup_cb_player_matches": cb_lineup_entries,
        "lineup_cb_player_matches_with_zero_pass_rows": sum(1 for v in pass_by_cb_match if v == 0),
        "lineup_cb_pass_rows_per_player_match_median": statistics.median(pass_by_cb_match) if pass_by_cb_match else None,
        "player_ids_exported": False, "player_names_exported": False,
    }
    print(json.dumps(out, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
