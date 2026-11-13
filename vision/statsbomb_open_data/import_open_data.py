#!/usr/bin/env python3
"""Import a small, reproducible StatsBomb Open Data sample and report its quality.

The tool downloads only public JSON files from the official hudl/open-data
repository. It does not download match video, bypass access controls, or write
to Supabase. Raw files and reports default to .cache/, which is git-ignored.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

BASE_URL = "https://raw.githubusercontent.com/hudl/open-data/master/data"
SOURCE_NAME = "StatsBomb Open Data"
SOURCE_REPOSITORY = "https://github.com/hudl/open-data"

METRIC_DEFINITIONS = {
    "events": "Count of attributed StatsBomb events for the player in selected matches.",
    "passes_attempted": "Count of Pass events attributed to the player.",
    "passes_completed": "Pass events with no pass.outcome object; StatsBomb encodes a completed pass by omitting outcome.",
    "pass_completion_pct": "passes_completed / passes_attempted * 100; null when there are no attempts.",
    "pass_length_mean": "Arithmetic mean of pass.length for passes where length is present; source unit is retained.",
    "crosses": "Pass events with pass.cross = true.",
    "through_balls": "Pass events with pass.through_ball = true.",
    "assists": "Pass events with pass.goal_assist = true.",
    "shot_assists": "Pass events with pass.shot_assist = true.",
    "carries": "Count of Carry events attributed to the player.",
    "shots": "Count of Shot events attributed to the player.",
    "goals": "Shot events whose shot.outcome.name is Goal.",
    "xg": "Sum of shot.statsbomb_xg where present; null if no shot carries an xG value.",
    "pressures": "Count of Pressure events attributed to the player.",
    "interceptions": "Count of Interception events attributed to the player.",
    "ball_recoveries": "Count of Ball Recovery events attributed to the player.",
    "clearances": "Count of Clearance events attributed to the player.",
    "blocks": "Count of Block events attributed to the player.",
    "tackles": "Duel events whose duel.type.name is Tackle.",
    "dribbles": "Count of Dribble events attributed to the player.",
    "goalkeeper_actions": "Count of Goal Keeper events; StatsBomb records attempts, not only successful actions.",
    "goalkeeper_saves": "Goal Keeper events with type Penalty Saved, Penalty Saved to Post, Shot Saved, Shot Saved Off Target or Shot Saved to Post.",
    "goalkeeper_shots_faced": "Goal Keeper events with type Shot Faced.",
    "goalkeeper_goals_conceded": "Goal Keeper events with type Goal Conceded.",
    "goalkeeper_collections": "Goal Keeper events with type Collected.",
    "goalkeeper_punches": "Goal Keeper events with type Punch.",
    "goalkeeper_sweeps": "Goal Keeper events with type Keeper Sweeper or Keeper Sweep.",
    "goalkeeper_smotherings": "Goal Keeper events with type Smother.",
    "goalkeeper_penalty_saves": "Goal Keeper events with type Penalty Saved or Penalty Saved to Post.",
    "goalkeeper_penalties_conceded": "Goal Keeper events with type Penalty Conceded.",
    "goalkeeper_unclassified_actions": "Goal Keeper events with a missing or unrecognized goalkeeper type.",
    "goal_kicks": "Pass events whose pass.type.name is Goal Kick.",
    "per90_metrics": "Count metrics and total xG per 90 verified on-pitch minutes; null when minutes are unavailable or zero. Percentages and means are excluded.",
    "data_quality": "Selected-sample availability checks for appearance evidence, attributed events and verified positive minutes; not a player rating.",
    "data_consistency": "Reconciliation of selected-match records against aggregate counts, xG, minutes, per-90 calculations and score-state totals.",
    "score_state_analysis": "Raw player event counts and summed source xG split by leading/drawing/trailing state, only where the match score timeline is validated; no score-state minutes or per-90 rates.",
}

COUNTER_FIELDS = (
    "events", "passes_attempted", "passes_completed", "crosses",
    "through_balls", "assists", "shot_assists", "carries", "shots",
    "goals", "pressures", "interceptions", "ball_recoveries",
    "clearances", "blocks", "tackles", "dribbles",
    "goalkeeper_actions", "goalkeeper_saves", "goalkeeper_shots_faced",
    "goalkeeper_goals_conceded", "goalkeeper_collections",
    "goalkeeper_punches", "goalkeeper_sweeps", "goalkeeper_smotherings",
    "goalkeeper_penalty_saves", "goalkeeper_penalties_conceded",
    "goalkeeper_unclassified_actions", "goal_kicks",
)


def calculate_per90_metrics(metrics: dict[str, Any], minutes_played_seconds: Any) -> dict[str, float] | None:
    """Normalize count metrics and total xG to 90 verified on-pitch minutes."""
    if not _finite(minutes_played_seconds) or float(minutes_played_seconds) <= 0:
        return None

    scale = 5400.0 / float(minutes_played_seconds)
    per90 = {
        field: round(float(metrics[field]) * scale, 2)
        for field in COUNTER_FIELDS
        if _finite(metrics.get(field))
    }
    if _finite(metrics.get("xg")):
        per90["xg"] = round(float(metrics["xg"]) * scale, 3)
    return per90


def calculate_player_data_quality(player: dict[str, Any]) -> dict[str, Any]:
    """Describe data availability for a player's selected-match aggregate."""
    metrics = player.get("metrics") or {}
    appearance_matches = int(player.get("matches_with_appearance_evidence") or 0)
    has_appearance_evidence = appearance_matches > 0
    has_attributed_events = int(metrics.get("events") or 0) > 0
    minutes_complete = player.get("minutes_calculation_complete") is True
    minutes_played = player.get("minutes_played")
    has_positive_minutes = _finite(minutes_played) and float(minutes_played) > 0

    reasons = []
    if not has_appearance_evidence:
        reasons.append("no_appearance_evidence")
    if not has_attributed_events:
        reasons.append("no_attributed_events")
    if not minutes_complete:
        reasons.append("minutes_calculation_incomplete")
    if not has_positive_minutes:
        reasons.append("no_positive_verified_minutes")

    if not has_appearance_evidence or not has_attributed_events:
        status = "insufficient"
    elif not minutes_complete or not has_positive_minutes:
        status = "partial"
    else:
        status = "complete"

    return {
        "status": status,
        "reasons": reasons,
        "checks": {
            "appearance_evidence": has_appearance_evidence,
            "appearance_matches": appearance_matches,
            "attributed_events": has_attributed_events,
            "minutes_calculation_complete": minutes_complete,
            "positive_verified_minutes": has_positive_minutes,
            "per90_available": isinstance(player.get("per90_metrics"), dict),
        },
    }


def _normalise_player_name(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    normalised = " ".join(value.casefold().split())
    if not normalised or normalised.startswith("unknown player "):
        return None
    return normalised


def find_player_name_collisions(
    players: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Find exact normalized names associated with multiple source player IDs."""
    grouped: dict[str, dict[str, dict[str, Any]]] = defaultdict(dict)
    for player in players:
        normalised = _normalise_player_name(player.get("player_name"))
        player_id = player.get("player_id")
        if normalised is None or player_id is None:
            continue
        grouped[normalised].setdefault(str(player_id), player)

    collisions = []
    for normalised, by_id in grouped.items():
        if len(by_id) < 2:
            continue
        entries = []
        for player_id in sorted(by_id):
            player = by_id[player_id]
            entries.append({
                "player_id": player.get("player_id"),
                "identity_key": f"statsbomb:{player_id}",
                "player_name": player.get("player_name"),
                "team_names": player.get("team_names") or [],
                "matches_listed_in_squads": player.get("matches_listed_in_squads", 0),
            })
        collisions.append({
            "normalized_name": normalised,
            "display_name": entries[0]["player_name"],
            "player_ids": [entry["player_id"] for entry in entries],
            "players": entries,
        })

    return sorted(collisions, key=lambda item: item["normalized_name"])


def build_player_season_comparison(
    reports: list[dict[str, Any]],
) -> dict[str, Any]:
    """Compare the same source-identified players across reports for one competition."""
    if not isinstance(reports, list) or len(reports) < 2:
        raise ValueError("Sezon karşılaştırması için en az iki sezon raporu gerekli.")

    competitions: dict[str, str] = {}
    seasons: dict[str, dict[str, str]] = {}
    player_rows: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)

    for report in reports:
        if not isinstance(report, dict):
            raise ValueError("Sezon raporunun kökü JSON nesnesi olmalı.")
        competition = report.get("competition_season") or {}
        competition_id = competition.get("competition_id")
        season_id = competition.get("season_id")
        if competition_id is None or season_id is None:
            raise ValueError("Karşılaştırma raporunda turnuva veya sezon kimliği eksik.")
        competition_key = str(competition_id)
        season_key = str(season_id)
        competitions.setdefault(
            competition_key, str(competition.get("competition_name") or competition_key)
        )
        if season_key in seasons:
            raise ValueError(f"Aynı sezon raporu birden fazla verildi: {season_key}")
        seasons[season_key] = {
            "season_id": season_key,
            "season_name": str(competition.get("season_name") or season_key),
        }

        sample = report.get("sample") or {}
        selected_matches = int(sample.get("selected_match_count") or 0)
        player_totals = report.get("player_sample_totals")
        if not isinstance(player_totals, list):
            raise ValueError("Sezon raporunda player_sample_totals listesi bulunamadı.")

        for player in player_totals:
            if not isinstance(player, dict) or player.get("player_id") is None:
                continue
            player_id = str(player["player_id"])
            player_rows[(competition_key, player_id)].append({
                "player_id": player["player_id"],
                "player_name": player.get("player_name") or f"Unknown player {player_id}",
                "positions_seen": sorted({
                    " ".join(position.split())
                    for position in (
                        player.get("positions_seen")
                        if isinstance(player.get("positions_seen"), list) else []
                    )
                    if isinstance(position, str) and position.strip()
                }, key=str.casefold),
                "season_id": season_key,
                "season_name": seasons[season_key]["season_name"],
                "selected_match_count": selected_matches,
                "matches_listed_in_squads": player.get("matches_listed_in_squads", 0),
                "matches_with_appearance_evidence": player.get(
                    "matches_with_appearance_evidence", 0
                ),
                "minutes_played": player.get("minutes_played"),
                "per90_metrics": player.get("per90_metrics"),
                "data_quality_status": (player.get("data_quality") or {}).get("status"),
                "data_consistency_status": (player.get("data_consistency") or {}).get("status"),
                "identity_status": (player.get("identity") or {}).get("status"),
            })

    if len(competitions) != 1:
        raise ValueError(
            "Aynı karşılaştırmada yalnızca tek bir turnuva kullanılabilir; "
            "farklı turnuvaları ayrı karşılaştırın."
        )

    comparison_players = []
    for (competition_id, player_id), records in player_rows.items():
        if len(records) < 2:
            continue
        records.sort(key=lambda row: (row["season_name"].casefold(), row["season_id"]))
        season_results = []
        previous = None
        for record in records:
            per90 = record.get("per90_metrics")
            per90_values = per90 if isinstance(per90, dict) else None
            changes = None
            previous_season = None
            if previous is not None:
                previous_values = previous.get("per90_metrics")
                if isinstance(previous_values, dict) and isinstance(per90_values, dict):
                    changes = {}
                    for metric in sorted(set(previous_values) & set(per90_values)):
                        before = previous_values[metric]
                        after = per90_values[metric]
                        if _finite(before) and _finite(after):
                            decimals = 3 if metric == "xg" else 2
                            changes[metric] = round(float(after) - float(before), decimals)
                previous_season = previous["season_name"]

            current_positions = record["positions_seen"]
            previous_positions = previous.get("positions_seen", []) if previous else []
            position_comparison = None
            if previous is not None:
                if not current_positions or not previous_positions:
                    position_status = "unavailable"
                    shared_positions = []
                else:
                    previous_by_key = {
                        value.casefold(): value for value in previous_positions
                    }
                    current_by_key = {
                        value.casefold(): value for value in current_positions
                    }
                    position_status = (
                        "same"
                        if set(previous_by_key) == set(current_by_key)
                        else "changed"
                    )
                    shared_positions = sorted(
                        set(previous_by_key) & set(current_by_key)
                    )
                position_comparison = {
                    "status": position_status,
                    "shared_positions": shared_positions,
                    "previous_positions": previous_positions,
                    "current_positions": current_positions,
                }
            season_results.append({
                "player_name": record["player_name"],
                "season_id": record["season_id"],
                "season_name": record["season_name"],
                "selected_match_count": record["selected_match_count"],
                "matches_listed_in_squads": record["matches_listed_in_squads"],
                "matches_with_appearance_evidence": record[
                    "matches_with_appearance_evidence"
                ],
                "minutes_played": record["minutes_played"],
                "positions_seen": current_positions,
                "position_comparison_from_previous": position_comparison,
                "per90_metrics": per90_values,
                "previous_season": previous_season,
                "per90_change_from_previous": changes,
                "data_quality_status": record["data_quality_status"],
                "data_consistency_status": record["data_consistency_status"],
                "identity_status": record["identity_status"],
            })
            previous = record

        latest_name = records[-1]["player_name"]
        position_states = [
            row["position_comparison_from_previous"]["status"]
            for row in season_results
            if row["position_comparison_from_previous"] is not None
        ]
        if "changed" in position_states:
            position_status = "changed"
        elif "unavailable" in position_states and "same" in position_states:
            position_status = "partially_comparable"
        elif "same" in position_states:
            position_status = "same"
        else:
            position_status = "unavailable"
        all_positions = sorted({
            position
            for row in records
            for position in row["positions_seen"]
        }, key=str.casefold)
        comparison_players.append({
            "player_id": records[-1]["player_id"],
            "identity_key": f"statsbomb:{player_id}",
            "player_name": latest_name,
            "competition_id": competition_id,
            "seasons_present": len(records),
            "positions_seen_across_seasons": all_positions,
            "position_comparison_status": position_status,
            "position_change_count": position_states.count("changed"),
            "position_data_gaps": position_states.count("unavailable"),
            "seasons": season_results,
        })

    comparison_players.sort(key=lambda row: row["player_name"].casefold())
    return {
        "comparison_basis": "verified_per90_metrics",
        "competition_id": next(iter(competitions)),
        "competition_name": next(iter(competitions.values())),
        "season_count": len(seasons),
        "player_count": len(comparison_players),
        "players": comparison_players,
        "interpretation_limits": [
            "Only the same source player_id is matched across seasons; names are not matching keys.",
            "Only players found in at least two supplied season reports are included.",
            "Per-90 values are compared only when verified minutes produced values in both seasons.",
            "A positive or negative per-90 change is a statistical difference, not a conclusion that the player improved or declined.",
            "Selected match counts, competition strength, role changes, team context and source coverage can affect comparisons.",
            "Position comparisons use exact normalized source labels only; label differences do not independently prove a tactical role change.",
        ],
    }


def calculate_player_identity(
    player: dict[str, Any],
    match_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    """Validate a player's source ID across match rows; never merge by name."""
    player_id = player.get("player_id")
    expected_id = str(player_id) if player_id is not None else None
    record_ids = {
        str(row.get("player_id"))
        for row in match_rows
        if row.get("player_id") is not None
    }
    player_id_matches = (
        expected_id is not None
        and record_ids == {expected_id}
        and len(record_ids) == 1
    )

    names: dict[str, str] = {}
    for row in match_rows:
        label = row.get("player_name")
        normalised = _normalise_player_name(label)
        if normalised:
            names.setdefault(normalised, str(label).strip())

    aggregate_name = player.get("player_name")
    aggregate_normalised = _normalise_player_name(aggregate_name)
    if aggregate_normalised:
        names.setdefault(aggregate_normalised, str(aggregate_name).strip())

    reasons = []
    if not player_id_matches:
        reasons.append("player_id_mismatch_across_records")
    if len(names) > 1:
        reasons.append("player_name_varies_for_same_id")

    return {
        "key": f"statsbomb:{expected_id}" if expected_id is not None else None,
        "source": "StatsBomb player_id",
        "status": "consistent" if not reasons else "review",
        "reasons": reasons,
        "name_variants": sorted(names.values(), key=str.casefold),
        "checked_match_records": len(match_rows),
        "checks": {
            "player_id_matches": player_id_matches,
            "single_source_id": len(record_ids) == 1 and expected_id is not None,
            "name_consistent": len(names) <= 1,
        },
    }


def calculate_player_data_consistency(
    player: dict[str, Any],
    match_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    """Reconcile an aggregate player row against its selected-match records."""
    metrics = player.get("metrics") or {}
    reasons: list[str] = []
    expected_records = int(player.get("matches_listed_in_squads") or 0)
    record_count_matches = len(match_rows) == expected_records
    if not record_count_matches:
        reasons.append("match_record_count_mismatch")

    appearance_count = sum(1 for row in match_rows if row.get("appearance_evidence"))
    appearance_count_matches = (
        appearance_count == int(player.get("matches_with_appearance_evidence") or 0)
    )
    if not appearance_count_matches:
        reasons.append("appearance_match_count_mismatch")

    metric_totals_match = True
    for field in COUNTER_FIELDS:
        actual_total = int(metrics.get(field) or 0)
        match_total = sum(
            int((row.get("metrics") or {}).get(field) or 0)
            for row in match_rows
        )
        if actual_total != match_total:
            metric_totals_match = False
            reasons.append(f"metric_total_mismatch:{field}")

    xg_values = [
        float((row.get("metrics") or {})["xg"])
        for row in match_rows
        if _finite((row.get("metrics") or {}).get("xg"))
    ]
    expected_xg = metrics.get("xg")
    if _finite(expected_xg):
        xg_total_matches = math.isclose(
            float(expected_xg), sum(xg_values), rel_tol=0.0, abs_tol=0.001
        )
    else:
        xg_total_matches = not xg_values
    if not xg_total_matches:
        reasons.append("xg_total_mismatch")

    matched_minute_records = sum(
        1 for row in match_rows if _finite(row.get("minutes_played_seconds"))
    )
    minutes_record_count_matches = (
        matched_minute_records == int(player.get("minutes_matches_valid") or 0)
    )
    if not minutes_record_count_matches:
        reasons.append("minutes_record_count_mismatch")

    minutes_complete = player.get("minutes_calculation_complete") is True
    minutes_total_matches: bool | None = None
    per90_recalculated: bool | None = None
    per90_matches: bool | None = None
    if minutes_complete:
        all_minutes_present = all(
            _finite(row.get("minutes_played_seconds")) for row in match_rows
        )
        total_seconds = sum(
            float(row["minutes_played_seconds"])
            for row in match_rows
            if _finite(row.get("minutes_played_seconds"))
        )
        minutes_total_matches = (
            all_minutes_present
            and round(total_seconds / 60.0, 2) == player.get("minutes_played")
        )
        if not minutes_total_matches:
            reasons.append("minutes_total_mismatch")

        expected_per90 = calculate_per90_metrics(metrics, total_seconds)
        actual_per90 = player.get("per90_metrics")
        if expected_per90 is None:
            per90_matches = actual_per90 is None
        elif not isinstance(actual_per90, dict):
            per90_matches = False
        else:
            per90_matches = set(actual_per90) == set(expected_per90) and all(
                math.isclose(
                    float(actual_per90[key]), float(value),
                    rel_tol=0.0, abs_tol=0.001
                )
                for key, value in expected_per90.items()
            )
        per90_recalculated = per90_matches
        if not per90_matches:
            reasons.append("per90_recalculation_mismatch")

    aggregate_score_state = player.get("score_state_analysis") or {}
    aggregate_by_state = aggregate_score_state.get("metrics_by_state")
    match_score_state_rows = [
        row.get("score_state_analysis") or {} for row in match_rows
    ]
    has_score_state_metadata = (
        "score_state_analysis" in player
        or any("score_state_analysis" in row for row in match_rows)
    )
    score_state_status_counts = Counter(
        row.get("status") or "unavailable" for row in match_score_state_rows
    )
    status_counts_match: bool | None = None
    if has_score_state_metadata:
        status_counts_match = (
            score_state_status_counts
            == Counter(aggregate_score_state.get("match_status_counts") or {})
        )
        if not status_counts_match:
            reasons.append("score_state_match_status_count_mismatch")

    match_rows_with_score_state = [
        row for row in match_score_state_rows
        if isinstance(row.get("metrics_by_state"), dict)
    ]
    score_state_metric_totals_match: bool | None = None
    if isinstance(aggregate_by_state, dict):
        score_state_metric_totals_match = True
        for state in SCORE_STATES:
            aggregate_metrics = aggregate_by_state.get(state) or {}
            for field in SCORE_STATE_METRIC_FIELDS:
                expected_value = sum(
                    float((row["metrics_by_state"].get(state) or {}).get(field) or 0)
                    for row in match_rows_with_score_state
                )
                actual_value = float(aggregate_metrics.get(field) or 0)
                if not math.isclose(
                    actual_value, expected_value, rel_tol=0.0, abs_tol=0.001
                ):
                    score_state_metric_totals_match = False
                    reasons.append(f"score_state_metric_total_mismatch:{state}:{field}")
    elif not match_rows_with_score_state:
        score_state_metric_totals_match = True if has_score_state_metadata else None
    else:
        score_state_metric_totals_match = False
        reasons.append("score_state_aggregate_missing")

    checks = {
        "match_record_count_matches": record_count_matches,
        "appearance_match_count_matches": appearance_count_matches,
        "event_metric_totals_match": metric_totals_match,
        "xg_total_matches": xg_total_matches,
        "minutes_record_count_matches": minutes_record_count_matches,
        "minutes_total_matches": minutes_total_matches,
        "per90_recalculated": per90_recalculated,
        "score_state_match_status_counts_match": status_counts_match,
        "score_state_metric_totals_match": score_state_metric_totals_match,
    }
    return {
        "status": "consistent" if not reasons else "review",
        "reasons": reasons,
        "checked_match_records": len(match_rows),
        "expected_match_records": expected_records,
        "checks": checks,
    }


class ImportErrorWithContext(RuntimeError):
    """A source download or data-validation error with a useful user message."""


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _read_json(path: Path) -> tuple[Any, bytes]:
    try:
        payload = path.read_bytes()
        return json.loads(payload.decode("utf-8")), payload
    except FileNotFoundError as exc:
        raise ImportErrorWithContext(f"Dosya bulunamadı: {path}") from exc
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ImportErrorWithContext(f"Geçerli UTF-8 JSON değil: {path}") from exc


def fetch_json(relative_path: str, cache_root: Path, force: bool = False,
               timeout: int = 45) -> tuple[Any, dict[str, Any]]:
    """Read a cached source JSON or fetch it from the official raw repository."""
    safe_parts = Path(relative_path).parts
    if relative_path.startswith("/") or ".." in safe_parts:
        raise ValueError("Kaynak yolu güvenli değil.")

    destination = cache_root / relative_path
    if destination.exists() and not force:
        obj, payload = _read_json(destination)
        return obj, {
            "path": relative_path,
            "cache": "hit",
            "bytes": len(payload),
            "sha256": sha256_bytes(payload),
            "url": f"{BASE_URL}/{relative_path}",
        }

    url = f"{BASE_URL}/{relative_path}"
    request = Request(url, headers={"User-Agent": "VelScout-DataPrototype/1.0"})
    try:
        with urlopen(request, timeout=timeout) as response:
            payload = response.read()
    except HTTPError as exc:
        if exc.code == 404:
            raise ImportErrorWithContext(
                f"Kaynak dosya bulunamadı (404): {url}"
            ) from exc
        raise ImportErrorWithContext(
            f"Kaynak indirme hatası HTTP {exc.code}: {url}"
        ) from exc
    except (URLError, TimeoutError) as exc:
        raise ImportErrorWithContext(
            f"Kaynağa erişilemedi: {url} ({exc})"
        ) from exc

    try:
        obj = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ImportErrorWithContext(
            f"Kaynak geçerli UTF-8 JSON değil: {url}"
        ) from exc

    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(destination.suffix + ".tmp")
    temporary.write_bytes(payload)
    temporary.replace(destination)
    return obj, {
        "path": relative_path,
        "cache": "downloaded",
        "bytes": len(payload),
        "sha256": sha256_bytes(payload),
        "url": url,
    }


def _name(value: Any) -> str | None:
    if not isinstance(value, dict):
        return None
    for key in ("name", "competition_name", "season_name", "team_name", "player_name"):
        if value.get(key):
            return str(value[key])
    return None


def _id(value: Any) -> Any:
    return value.get("id") if isinstance(value, dict) else None


def _finite(value: Any) -> bool:
    try:
        return math.isfinite(float(value))
    except (TypeError, ValueError):
        return False


def _player_from_event(event: dict[str, Any]) -> dict[str, Any] | None:
    player = event.get("player")
    player_id = _id(player)
    if player_id is None:
        return None
    return {
        "player_id": player_id,
        "player_name": _name(player) or f"Unknown player {player_id}",
        "team_id": _id(event.get("team")),
        "team_name": _name(event.get("team")),
        "event_position": _name(event.get("position")),
    }


def _lineup_players(lineups: Any) -> tuple[dict[str, dict[str, Any]], list[str]]:
    players: dict[str, dict[str, Any]] = {}
    warnings: list[str] = []
    if not isinstance(lineups, list):
        raise ImportErrorWithContext("Lineup dosyasının kökü JSON dizisi değil.")

    for team in lineups:
        if not isinstance(team, dict):
            warnings.append("Lineup içinde nesne olmayan takım kaydı var.")
            continue
        team_id = team.get("team_id")
        team_name = team.get("team_name")
        squad = team.get("lineup")
        if not isinstance(squad, list):
            warnings.append(f"{team_name or team_id}: lineup listesi eksik.")
            continue
        for player in squad:
            if not isinstance(player, dict) or player.get("player_id") is None:
                warnings.append(f"{team_name or team_id}: player_id eksik.")
                continue
            player_id = str(player["player_id"])
            positions = player.get("positions") or []
            position_names = []
            for segment in positions:
                if isinstance(segment, dict) and segment.get("position"):
                    position_names.append(str(segment["position"]))
            players[player_id] = {
                "player_id": player["player_id"],
                "player_name": player.get("player_name") or f"Unknown player {player_id}",
                "nickname": player.get("player_nickname"),
                "jersey_number": player.get("jersey_number"),
                "team_id": team_id,
                "team_name": team_name,
                "positions": sorted(set(position_names)),
                "appearance_evidence": bool(position_names),
                "minutes_played": None,
            }
    return players, warnings



def _match_clock_seconds(event: dict[str, Any]) -> int | None:
    """Read the StatsBomb match clock from its integer minute/second fields."""
    try:
        minute = int(event.get("minute"))
        second = int(event.get("second"))
    except (TypeError, ValueError):
        return None
    if minute < 0 or second < 0 or second >= 60:
        return None
    return minute * 60 + second


def calculate_minutes_played(events: Any) -> dict[str, Any]:
    """Calculate on-pitch time from ordered StatsBomb event match-clock fields.

    StatsBomb's minute/second clock is used because the video timestamp can
    have different offsets across regulation and extra-time periods. Each
    period starts from its first recorded clock value, so breaks are excluded.
    Period 5 (penalty shootout) is excluded. Missing or contradictory
    clock/state evidence makes the whole match result unavailable rather than
    guessed.
    """
    result = {
        "valid": False,
        "seconds_by_player": {},
        "player_names": {},
        "periods": [],
        "warnings": [],
        "errors": [],
    }
    if not isinstance(events, list):
        result["errors"] = ["Events kökü liste değil."]
        return result

    indexed_events = [(index, event) for index, event in enumerate(events) if isinstance(event, dict)]
    if indexed_events and all(isinstance(event.get("index"), int) for _, event in indexed_events):
        indexed_events.sort(key=lambda item: item[1]["index"])

    active: set[str] = set()
    permanently_off: set[str] = set()
    temporarily_off: set[str] = set()
    seconds_by_player: defaultdict[str, float] = defaultdict(float)
    player_names: dict[str, str] = {}
    warnings: list[str] = []
    errors: list[str] = []
    periods_seen: set[int] = set()
    periods_closed: set[int] = set()
    current_period: int | None = None
    last_time = 0.0
    last_event_index: Any = None
    last_event_type: str | None = None
    last_event_id: str | None = None
    starting_xi_count = 0

    def remember_player(player: Any) -> str | None:
        player_id = _id(player)
        if player_id is None:
            return None
        key = str(player_id)
        name = _name(player)
        if name:
            player_names[key] = name
        seconds_by_player.setdefault(key, 0.0)
        return key

    for _, event in indexed_events:
        try:
            period = int(event.get("period"))
        except (TypeError, ValueError):
            errors.append("Bir event için geçerli period alanı yok.")
            continue
        if period == 5:
            continue
        if period not in (1, 2, 3, 4):
            errors.append(f"Desteklenmeyen maç periodu: {period}.")
            continue

        event_type = _name(event.get("type")) or "Unknown"
        event_time = _match_clock_seconds(event)
        if event_time is None:
            errors.append(
                f"Geçersiz minute/second maç saati: period {period}, index {event.get('index')}."
            )
            continue

        periods_seen.add(period)
        if current_period is None:
            if period != 1:
                errors.append("Maç period 1 ile başlamıyor.")
            current_period = period
            last_time = event_time
        elif period != current_period:
            if period != current_period + 1:
                errors.append(
                    f"Period sırası kesintili: {current_period} sonrasında {period} geldi."
                )
            if current_period not in periods_closed:
                errors.append(f"Period {current_period} için Half End olayı eksik.")
            current_period = period
            # Anchor to the first clock value in the new period; do not count
            # half-time or the interval between extra-time periods.
            last_time = event_time

        if period in periods_closed and event_type != "Half End":
            errors.append(f"Period {period}, Half End sonrasında yeni event içeriyor.")
        linked_receipt_clock_anomaly = (
            event_time < last_time
            and event_type == "Ball Receipt*"
            and last_event_type == "Pass"
            and last_event_id in (event.get("related_events") or [])
        )
        if event_time < last_time and linked_receipt_clock_anomaly:
            warnings.append(
                f"Linked Ball Receipt* timestamp ignored for clock continuity "
                f"(event index {event.get('index')}, related pass {last_event_id})."
            )
            event_time = last_time
        elif event_time < last_time:
            errors.append(
                f"Period {period} maç saati geriye gidiyor: "
                f"event index={event.get('index')} type={event_type} "
                f"clock={event_time}; previous index={last_event_index} "
                f"type={last_event_type} clock={last_time}."
            )
            continue

        delta = event_time - last_time
        if delta:
            for player_id in active:
                seconds_by_player[player_id] += delta
        last_time = event_time
        last_event_index = event.get("index")
        last_event_type = event_type
        last_event_id = str(event.get("id")) if event.get("id") is not None else None

        if event_type == "Starting XI":
            tactics = event.get("tactics") or {}
            lineup = tactics.get("lineup")
            if not isinstance(lineup, list) or not lineup:
                errors.append(f"Period {period} Starting XI lineup verisi eksik.")
                continue
            starting_xi_count += 1
            for member in lineup:
                member = member or {}
                player_id = remember_player(member.get("player"))
                if player_id is None:
                    errors.append("Starting XI içinde player_id eksik.")
                    continue
                active.add(player_id)
                permanently_off.discard(player_id)
                temporarily_off.discard(player_id)

        elif event_type == "Substitution":
            outgoing_id = remember_player(event.get("player"))
            substitution = event.get("substitution") or {}
            incoming_id = remember_player(substitution.get("replacement"))
            if outgoing_id is None or incoming_id is None:
                errors.append(f"Period {period} substitution oyuncu bilgisi eksik.")
                continue
            if outgoing_id not in active:
                warnings.append(
                    f"Substitution sırasında çıkan oyuncu aktif görünmüyor: {player_names.get(outgoing_id, outgoing_id)}."
                )
                errors.append("Substitution state uyuşmazlığı.")
            active.discard(outgoing_id)
            temporarily_off.discard(outgoing_id)
            if incoming_id in permanently_off or incoming_id in active:
                errors.append(
                    f"Substitution ile giren oyuncu zaten aktif veya kalıcı olarak çıkmış: {player_names.get(incoming_id, incoming_id)}."
                )
            active.add(incoming_id)
            temporarily_off.discard(incoming_id)

        elif event_type == "Player Off":
            player_id = remember_player(event.get("player"))
            if player_id is None:
                errors.append("Player Off event içinde player_id eksik.")
                continue
            if player_id not in active:
                errors.append(
                    f"Player Off sırasında oyuncu aktif görünmüyor: {player_names.get(player_id, player_id)}."
                )
            active.discard(player_id)
            off_data = event.get("player_off") or {}
            if off_data.get("permanent") is True:
                permanently_off.add(player_id)
                temporarily_off.discard(player_id)
            else:
                temporarily_off.add(player_id)

        elif event_type == "Player On":
            player_id = remember_player(event.get("player"))
            if player_id is None:
                errors.append("Player On event içinde player_id eksik.")
                continue
            if player_id in permanently_off:
                errors.append(
                    f"Kalıcı olarak çıkmış oyuncu tekrar döndü olarak işaretlenmiş: {player_names.get(player_id, player_id)}."
                )
            elif player_id not in temporarily_off:
                errors.append(
                    f"Karşılık gelen Player Off olmadan Player On geldi: {player_names.get(player_id, player_id)}."
                )
            else:
                active.add(player_id)
                temporarily_off.discard(player_id)

        elif event_type in ("Bad Behaviour", "Foul Committed"):
            payload_key = "bad_behaviour" if event_type == "Bad Behaviour" else "foul_committed"
            card = _name((event.get(payload_key) or {}).get("card"))
            if card in ("Red Card", "Second Yellow"):
                player_id = remember_player(event.get("player"))
                if player_id is None:
                    errors.append(f"{card} event içinde player_id eksik.")
                else:
                    if player_id not in active:
                        errors.append(
                            f"{card} sırasında oyuncu aktif görünmüyor: {player_names.get(player_id, player_id)}."
                        )
                    active.discard(player_id)
                    temporarily_off.discard(player_id)
                    permanently_off.add(player_id)

        elif event_type == "Half End":
            if event.get("early_video_end") is True or event.get("match_suspended") is True:
                errors.append(
                    f"Period {period} Half End kaydı erken video bitişi veya maçın askıya alınmasını işaretliyor."
                )
            periods_closed.add(period)

    if starting_xi_count == 0:
        errors.append("Starting XI eventleri bulunamadı.")
    if not periods_seen:
        errors.append("Süre hesaplamak için geçerli maç periodu bulunamadı.")
    if periods_seen and sorted(periods_seen) != list(range(1, max(periods_seen) + 1)):
        errors.append("Maç periodları kesintisiz değil.")
    for period in sorted(periods_seen):
        if period not in periods_closed:
            errors.append(f"Period {period} için Half End olayı eksik.")

    result["periods"] = sorted(periods_seen)
    result["warnings"] = sorted(set(warnings))
    result["errors"] = sorted(set(errors))
    if errors:
        return result

    result["valid"] = True
    result["seconds_by_player"] = dict(seconds_by_player)
    result["player_names"] = player_names
    return result

def _non_negative_score(value: Any) -> int | None:
    """Accept only finite, non-negative integer score values."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    if not math.isfinite(float(value)) or float(value) < 0:
        return None
    if not float(value).is_integer():
        return None
    return int(value)


def extract_match_context(match: dict[str, Any]) -> dict[str, Any]:
    """Expose source-provided match context without inferring player performance."""
    home = match.get("home_team") if isinstance(match.get("home_team"), dict) else {}
    away = match.get("away_team") if isinstance(match.get("away_team"), dict) else {}
    stadium = match.get("stadium") if isinstance(match.get("stadium"), dict) else {}
    referee = match.get("referee") if isinstance(match.get("referee"), dict) else {}
    home_score = _non_negative_score(match.get("home_score"))
    away_score = _non_negative_score(match.get("away_score"))
    if home_score is not None and away_score is not None:
        scoreline_status = "complete"
        if home_score > away_score:
            result = "home_win"
        elif away_score > home_score:
            result = "away_win"
        else:
            result = "draw"
        goal_difference = home_score - away_score
    else:
        scoreline_status = (
            "partial" if home_score is not None or away_score is not None
            else "unavailable"
        )
        result = None
        goal_difference = None

    competition_stage = _name(match.get("competition_stage"))
    match_week = match.get("match_week")
    kick_off = match.get("kick_off")
    match_status = match.get("match_status")
    stadium_name = _name(stadium)
    referee_name = _name(referee)
    home_group = home.get("home_team_group")
    away_group = away.get("away_team_group")

    return {
        "kick_off": kick_off,
        "competition_stage": competition_stage,
        "match_week": match_week,
        "match_status": match_status,
        "stadium": stadium_name,
        "referee": referee_name,
        "home_team_group": home_group,
        "away_team_group": away_group,
        "scoreline_status": scoreline_status,
        "listed_result": result,
        "home_goal_difference": goal_difference,
        "source_field_availability": {
            "kick_off": kick_off is not None,
            "competition_stage": competition_stage is not None,
            "match_week": match_week is not None,
            "match_status": match_status is not None,
            "stadium": stadium_name is not None,
            "referee": referee_name is not None,
            "home_team_group": home_group is not None,
            "away_team_group": away_group is not None,
            "scoreline": scoreline_status == "complete",
        },
        "interpretation_limit": (
            "Listed final score and match metadata only; no event-time score state, "
            "possession adjustment or player-performance correction is calculated."
        ),
    }


def _score_state(score_for: int, score_against: int) -> str:
    """Describe a team's state relative to its opponent."""
    if score_for > score_against:
        return "leading"
    if score_for < score_against:
        return "trailing"
    return "drawing"


def calculate_match_score_timeline(
    match: dict[str, Any],
    events: Any,
) -> dict[str, Any]:
    """Reconstruct goal-by-goal score state and reconcile it to the listed score.

    Only Shot events with outcome Goal and Own Goal For events add to a score.
    Own Goal Against is the conceding-side counterpart and is not counted as
    a second goal. Period 5 penalty-shootout kicks are excluded.
    """
    result: dict[str, Any] = {
        "status": "unavailable",
        "reason_codes": [],
        "goals": [],
        "goal_count": 0,
        "reconstructed_score": None,
        "listed_score": None,
        "score_reconciled": False,
        "event_order": "period_then_index",
        "penalty_shootout_excluded": True,
        "interpretation_limit": (
            "Goal-by-goal score state only. Player event states are not yet "
            "classified, and no performance adjustment is calculated."
        ),
    }

    if not isinstance(events, list):
        result["reason_codes"] = ["events_not_a_list"]
        return result

    home = match.get("home_team") if isinstance(match, dict) else None
    away = match.get("away_team") if isinstance(match, dict) else None
    home = home if isinstance(home, dict) else {}
    away = away if isinstance(away, dict) else {}
    home_id = home.get("home_team_id")
    away_id = away.get("away_team_id")
    if home_id is None or away_id is None or str(home_id) == str(away_id):
        result["reason_codes"] = ["match_team_ids_unavailable_or_ambiguous"]
        return result

    home_score = _non_negative_score(match.get("home_score"))
    away_score = _non_negative_score(match.get("away_score"))
    if home_score is None or away_score is None:
        result["reason_codes"] = ["listed_final_score_unavailable_or_invalid"]
        return result
    result["listed_score"] = {"home": home_score, "away": away_score}

    ordered_events = []
    seen_indices: set[tuple[int, int]] = set()
    for event in events:
        if not isinstance(event, dict):
            result["reason_codes"] = ["invalid_event_record"]
            return result
        period = event.get("period")
        index = event.get("index")
        if (
            isinstance(period, bool) or not isinstance(period, int)
            or period < 1 or period > 5
            or isinstance(index, bool) or not isinstance(index, int)
            or index < 1
        ):
            result["reason_codes"] = ["event_order_fields_unavailable_or_invalid"]
            return result
        key = (period, index)
        if key in seen_indices:
            result["reason_codes"] = ["duplicate_period_event_index"]
            return result
        seen_indices.add(key)
        ordered_events.append((period, index, event))

    ordered_events.sort(key=lambda row: (row[0], row[1]))
    score = {str(home_id): 0, str(away_id): 0}
    team_names = {
        str(home_id): home.get("home_team_name"),
        str(away_id): away.get("away_team_name"),
    }

    for period, index, event in ordered_events:
        if period == 5:
            continue
        event_type = _name(event.get("type"))
        scoring_team_id = None
        if event_type == "Shot" and _name((event.get("shot") or {}).get("outcome")) == "Goal":
            scoring_team_id = _id(event.get("team"))
            goal_type = "shot_goal"
        elif event_type == "Own Goal For":
            scoring_team_id = _id(event.get("team"))
            goal_type = "own_goal_for"
        else:
            # Own Goal Against describes the conceding-side record; the
            # corresponding Own Goal For event credits the scoring team.
            continue

        if scoring_team_id is None or str(scoring_team_id) not in score:
            result["reason_codes"] = ["goal_team_id_unavailable_or_unknown"]
            result["goals"] = []
            result["goal_count"] = 0
            return result
        timestamp = event.get("timestamp")
        if not isinstance(timestamp, str) or not timestamp.strip():
            result["reason_codes"] = ["goal_event_timestamp_unavailable"]
            result["goals"] = []
            result["goal_count"] = 0
            return result

        score[str(scoring_team_id)] += 1
        home_after = score[str(home_id)]
        away_after = score[str(away_id)]
        result["goals"].append({
            "period": period,
            "event_index": index,
            "timestamp": timestamp,
            "goal_type": goal_type,
            "scoring_team_id": scoring_team_id,
            "scoring_team_name": team_names[str(scoring_team_id)],
            "home_score_after": home_after,
            "away_score_after": away_after,
            "home_state_after": _score_state(home_after, away_after),
            "away_state_after": _score_state(away_after, home_after),
        })

    result["goal_count"] = len(result["goals"])
    result["reconstructed_score"] = {
        "home": score[str(home_id)],
        "away": score[str(away_id)],
    }
    if result["reconstructed_score"] != result["listed_score"]:
        result["status"] = "reconciliation_mismatch"
        result["reason_codes"] = ["reconstructed_score_does_not_match_listed_final_score"]
        return result

    result["status"] = "validated"
    result["reason_codes"] = []
    result["score_reconciled"] = True
    return result


SCORE_STATES = ("leading", "drawing", "trailing")
SCORE_STATE_METRIC_FIELDS = (*COUNTER_FIELDS, "xg")


def _build_event_score_state_lookup(
    match: dict[str, Any],
    events: Any,
    score_timeline: dict[str, Any],
) -> dict[tuple[int, int], dict[str, str]]:
    """Map each ordered event to the state before it for home and away teams."""
    if not isinstance(events, list) or score_timeline.get("status") != "validated":
        return {}

    home = match.get("home_team") if isinstance(match, dict) else None
    away = match.get("away_team") if isinstance(match, dict) else None
    home = home if isinstance(home, dict) else {}
    away = away if isinstance(away, dict) else {}
    home_id = home.get("home_team_id")
    away_id = away.get("away_team_id")
    if home_id is None or away_id is None:
        return {}

    home_key, away_key = str(home_id), str(away_id)
    score = {home_key: 0, away_key: 0}
    goal_by_event = {
        (int(goal["period"]), int(goal["event_index"])): str(goal["scoring_team_id"])
        for goal in score_timeline.get("goals", [])
    }
    lookup: dict[tuple[int, int], dict[str, str]] = {}

    for period, index, event in sorted(
        (int(event["period"]), int(event["index"]), event)
        for event in events
    ):
        if period == 5:
            continue
        lookup[(period, index)] = {
            home_key: _score_state(score[home_key], score[away_key]),
            away_key: _score_state(score[away_key], score[home_key]),
        }
        scoring_team = goal_by_event.get((period, index))
        if scoring_team == home_key:
            score[home_key] += 1
        elif scoring_team == away_key:
            score[away_key] += 1
    return lookup


def _score_state_metric_contributions(event: dict[str, Any]) -> Counter[str]:
    """Mirror supported player event counters for a single event."""
    contributions: Counter[str] = Counter({"events": 1})
    event_type = _name(event.get("type")) or "Unknown"

    if event_type == "Pass":
        pass_data = event.get("pass") or {}
        contributions["passes_attempted"] += 1
        if not pass_data.get("outcome"):
            contributions["passes_completed"] += 1
        if pass_data.get("cross") is True:
            contributions["crosses"] += 1
        if pass_data.get("through_ball") is True:
            contributions["through_balls"] += 1
        if pass_data.get("goal_assist") is True:
            contributions["assists"] += 1
        if pass_data.get("shot_assist") is True:
            contributions["shot_assists"] += 1
        if _name(pass_data.get("type")) == "Goal Kick":
            contributions["goal_kicks"] += 1
    elif event_type == "Carry":
        contributions["carries"] += 1
    elif event_type == "Shot":
        shot = event.get("shot") or {}
        contributions["shots"] += 1
        if _name(shot.get("outcome")) == "Goal":
            contributions["goals"] += 1
        if _finite(shot.get("statsbomb_xg")):
            contributions["xg"] += float(shot["statsbomb_xg"])
    elif event_type == "Goal Keeper":
        goalkeeper = event.get("goalkeeper") or {}
        goalkeeper_type = _name(goalkeeper.get("type"))
        normalized_type = goalkeeper_type.casefold() if goalkeeper_type else ""
        contributions["goalkeeper_actions"] += 1
        save_types = {
            "penalty saved", "penalty saved to post", "shot saved",
            "shot saved off target", "shot saved to post",
        }
        if normalized_type in save_types:
            contributions["goalkeeper_saves"] += 1
        if normalized_type in {"penalty saved", "penalty saved to post"}:
            contributions["goalkeeper_penalty_saves"] += 1
        if normalized_type == "shot faced":
            contributions["goalkeeper_shots_faced"] += 1
        elif normalized_type == "goal conceded":
            contributions["goalkeeper_goals_conceded"] += 1
        elif normalized_type == "collected":
            contributions["goalkeeper_collections"] += 1
        elif normalized_type == "punch":
            contributions["goalkeeper_punches"] += 1
        elif normalized_type in {
            "keeper sweeper", "keeper sweep", "keeper pick-up", "keeper pick up"
        }:
            contributions["goalkeeper_sweeps"] += 1
        elif normalized_type == "smother":
            contributions["goalkeeper_smotherings"] += 1
        elif normalized_type == "penalty conceded":
            contributions["goalkeeper_penalties_conceded"] += 1
        elif normalized_type not in save_types:
            contributions["goalkeeper_unclassified_actions"] += 1
    elif event_type == "Pressure":
        contributions["pressures"] += 1
    elif event_type == "Interception":
        contributions["interceptions"] += 1
    elif event_type == "Ball Recovery":
        contributions["ball_recoveries"] += 1
    elif event_type == "Clearance":
        contributions["clearances"] += 1
    elif event_type == "Block":
        contributions["blocks"] += 1
    elif event_type == "Duel":
        if _name((event.get("duel") or {}).get("type")) == "Tackle":
            contributions["tackles"] += 1
    elif event_type == "Dribble":
        contributions["dribbles"] += 1

    return contributions


def _serialise_score_state_metrics(
    metrics_by_state: dict[str, Counter[str]],
) -> dict[str, dict[str, int | float]]:
    """Return explicit zero-filled raw-count maps for all score states."""
    output = {}
    for state in SCORE_STATES:
        values = metrics_by_state.get(state, Counter())
        output[state] = {
            field: (
                round(float(values.get(field, 0.0)), 3)
                if field == "xg" else int(values.get(field, 0))
            )
            for field in SCORE_STATE_METRIC_FIELDS
        }
    return output


def calculate_score_state_durations(
    match: dict[str, Any],
    events: Any,
    score_timeline: dict[str, Any],
) -> dict[str, Any]:
    """Calculate team seconds in each score state using validated period clocks."""
    result: dict[str, Any] = {
        "status": "unavailable",
        "reason_codes": [],
        "total_seconds": None,
        "home_team_seconds_by_state": None,
        "away_team_seconds_by_state": None,
        "clock_precision": "whole_seconds",
        "periods_included": [],
        "penalty_shootout_excluded": True,
    }
    if score_timeline.get("status") != "validated":
        result["reason_codes"] = ["score_timeline_not_validated"]
        return result
    if not isinstance(events, list):
        result["reason_codes"] = ["events_not_a_list"]
        return result

    minute_validation = calculate_minutes_played(events)
    if not minute_validation["valid"]:
        result["reason_codes"] = ["match_clock_validation_failed"]
        result["clock_errors"] = minute_validation["errors"]
        return result

    home = match.get("home_team") if isinstance(match, dict) else None
    away = match.get("away_team") if isinstance(match, dict) else None
    home = home if isinstance(home, dict) else {}
    away = away if isinstance(away, dict) else {}
    home_id, away_id = home.get("home_team_id"), away.get("away_team_id")
    if home_id is None or away_id is None or str(home_id) == str(away_id):
        result["reason_codes"] = ["match_team_ids_unavailable_or_ambiguous"]
        return result

    ordered_by_period: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for event in events:
        if not isinstance(event, dict):
            result["reason_codes"] = ["invalid_event_record"]
            return result
        period = event.get("period")
        index = event.get("index")
        if (
            isinstance(period, bool) or not isinstance(period, int)
            or period < 1 or period > 5
            or isinstance(index, bool) or not isinstance(index, int)
            or index < 1
        ):
            result["reason_codes"] = ["event_order_fields_unavailable_or_invalid"]
            return result
        if period == 5:
            continue
        ordered_by_period[period].append(event)

    goal_keys = {
        (int(goal["period"]), int(goal["event_index"]))
        for goal in score_timeline.get("goals", [])
    }
    home_seconds = Counter({state: 0 for state in SCORE_STATES})
    away_seconds = Counter({state: 0 for state in SCORE_STATES})
    score = {str(home_id): 0, str(away_id): 0}
    total_seconds = 0
    included_periods = []

    for period in sorted(ordered_by_period):
        period_events = sorted(ordered_by_period[period], key=lambda event: event["index"])
        starts = [i for i, event in enumerate(period_events)
                  if _name(event.get("type")) == "Half Start"]
        ends = [i for i, event in enumerate(period_events)
                if _name(event.get("type")) == "Half End"]
        if len(starts) != 1 or len(ends) != 1 or ends[0] <= starts[0]:
            result["reason_codes"] = ["period_start_or_end_boundary_ambiguous"]
            return result
        start_index, end_index = starts[0], ends[0]
        pre_start_events = period_events[:start_index]
        if any(_name(event.get("type")) != "Starting XI" for event in pre_start_events):
            result["reason_codes"] = ["unexpected_events_before_period_start"]
            return result

        start_time = _match_clock_seconds(period_events[start_index])
        if start_time is None:
            result["reason_codes"] = ["period_start_clock_unavailable"]
            return result
        last_time = start_time
        last_event_type = _name(period_events[start_index].get("type"))
        last_event_id = (
            str(period_events[start_index].get("id"))
            if period_events[start_index].get("id") is not None else None
        )

        for event in period_events[start_index + 1:end_index + 1]:
            event_time = _match_clock_seconds(event)
            if event_time is None:
                result["reason_codes"] = ["event_clock_unavailable"]
                return result
            event_type = _name(event.get("type")) or "Unknown"
            linked_receipt_clock_anomaly = (
                event_time < last_time
                and event_type == "Ball Receipt*"
                and last_event_type == "Pass"
                and last_event_id in (event.get("related_events") or [])
            )
            if event_time < last_time and linked_receipt_clock_anomaly:
                event_time = last_time
            elif event_time < last_time:
                result["reason_codes"] = ["event_clock_regression"]
                return result

            delta = event_time - last_time
            if delta:
                home_state = _score_state(score[str(home_id)], score[str(away_id)])
                away_state = _score_state(score[str(away_id)], score[str(home_id)])
                home_seconds[home_state] += delta
                away_seconds[away_state] += delta
                total_seconds += delta
            last_time = event_time

            key = (period, int(event["index"]))
            if key in goal_keys:
                scoring_team_id = next(
                    str(goal["scoring_team_id"])
                    for goal in score_timeline["goals"]
                    if int(goal["period"]) == period
                    and int(goal["event_index"]) == key[1]
                )
                score[scoring_team_id] += 1

            last_event_type = event_type
            last_event_id = str(event.get("id")) if event.get("id") is not None else None

        included_periods.append(period)

    home_total = sum(home_seconds.values())
    away_total = sum(away_seconds.values())
    if total_seconds <= 0 or home_total != total_seconds or away_total != total_seconds:
        result["reason_codes"] = ["score_state_duration_total_mismatch"]
        return result

    result.update({
        "status": "validated",
        "reason_codes": [],
        "total_seconds": total_seconds,
        "home_team_seconds_by_state": dict(home_seconds),
        "away_team_seconds_by_state": dict(away_seconds),
        "periods_included": included_periods,
    })
    return result


def analyse_match(match: dict[str, Any], lineups: Any,
                  events: Any) -> dict[str, Any]:
    """Build a cautious single-match player event summary."""
    if not isinstance(events, list):
        raise ImportErrorWithContext("Events dosyasının kökü JSON dizisi değil.")

    players, warnings = _lineup_players(lineups)
    minutes_result = calculate_minutes_played(events)
    score_state_timeline = calculate_match_score_timeline(match, events)
    score_state_timeline["durations"] = calculate_score_state_durations(
        match, events, score_state_timeline
    )
    score_state_lookup = _build_event_score_state_lookup(
        match, events, score_state_timeline
    )
    counters: dict[str, Counter[str]] = defaultdict(Counter)
    score_state_counters: dict[str, dict[str, Counter[str]]] = defaultdict(
        lambda: {state: Counter() for state in SCORE_STATES}
    )
    score_state_unclassified_events: Counter[str] = Counter()
    pass_lengths: dict[str, list[float]] = defaultdict(list)
    xg_values: dict[str, list[float]] = defaultdict(list)
    event_types: Counter[str] = Counter()
    unattributed_events = 0
    unknown_team_events = 0
    event_players_missing_from_lineup: set[str] = set()

    for event in events:
        if not isinstance(event, dict):
            warnings.append("Event dizisinde nesne olmayan kayıt var.")
            continue
        event_type = _name(event.get("type")) or "Unknown"
        event_types[event_type] += 1
        player = _player_from_event(event)
        if player is None:
            if event_type not in {"Starting XI", "Half Start", "Half End",
                                  "Tactical Shift", "Substitution"}:
                unattributed_events += 1
            continue

        player_key = str(player["player_id"])
        if player_key not in players:
            players[player_key] = {
                **player,
                "nickname": None,
                "jersey_number": None,
                "positions": [],
                "appearance_evidence": True,
                "minutes_played": None,
            }
            event_players_missing_from_lineup.add(player_key)
            warnings.append(
                f"Event oyuncusu lineup dosyasında yok: {player['player_name']} ({player_key})"
            )
        else:
            players[player_key]["appearance_evidence"] = True
            if not players[player_key].get("team_name") and player.get("team_name"):
                players[player_key]["team_name"] = player["team_name"]
            event_position = player.get("event_position")
            if event_position and event_position not in players[player_key]["positions"]:
                players[player_key]["positions"].append(event_position)
                players[player_key]["positions"].sort()

        if not player.get("team_id"):
            unknown_team_events += 1

        row = counters[player_key]
        row["events"] += 1

        if score_state_timeline["status"] == "validated":
            period = event.get("period")
            index = event.get("index")
            event_team_id = _id(event.get("team"))
            event_state = None
            if (
                isinstance(period, int) and not isinstance(period, bool)
                and isinstance(index, int) and not isinstance(index, bool)
                and event_team_id is not None
            ):
                event_state = score_state_lookup.get(
                    (period, index), {}
                ).get(str(event_team_id))
            if event_state in SCORE_STATES:
                score_state_counters[player_key][event_state].update(
                    _score_state_metric_contributions(event)
                )
            else:
                score_state_unclassified_events[player_key] += 1
        else:
            score_state_unclassified_events[player_key] += 1

        if event_type == "Pass":
            pass_data = event.get("pass") or {}
            row["passes_attempted"] += 1
            # StatsBomb represents a completed pass by omitting pass.outcome.
            if not pass_data.get("outcome"):
                row["passes_completed"] += 1
            if _finite(pass_data.get("length")):
                pass_lengths[player_key].append(float(pass_data["length"]))
            if pass_data.get("cross") is True:
                row["crosses"] += 1
            if pass_data.get("through_ball") is True:
                row["through_balls"] += 1
            if pass_data.get("goal_assist") is True:
                row["assists"] += 1
            if pass_data.get("shot_assist") is True:
                row["shot_assists"] += 1
            if _name(pass_data.get("type")) == "Goal Kick":
                row["goal_kicks"] += 1
        elif event_type == "Carry":
            row["carries"] += 1
        elif event_type == "Shot":
            shot = event.get("shot") or {}
            row["shots"] += 1
            if _name(shot.get("outcome")) == "Goal":
                row["goals"] += 1
            if _finite(shot.get("statsbomb_xg")):
                xg_values[player_key].append(float(shot["statsbomb_xg"]))
        elif event_type == "Goal Keeper":
            goalkeeper = event.get("goalkeeper") or {}
            goalkeeper_type = _name(goalkeeper.get("type"))
            normalized_type = goalkeeper_type.casefold() if goalkeeper_type else ""
            row["goalkeeper_actions"] += 1
            if normalized_type in {
                "penalty saved", "penalty saved to post", "shot saved",
                "shot saved off target", "shot saved to post",
            }:
                row["goalkeeper_saves"] += 1
            if normalized_type in {"penalty saved", "penalty saved to post"}:
                row["goalkeeper_penalty_saves"] += 1
            if normalized_type == "shot faced":
                row["goalkeeper_shots_faced"] += 1
            elif normalized_type == "goal conceded":
                row["goalkeeper_goals_conceded"] += 1
            elif normalized_type == "collected":
                row["goalkeeper_collections"] += 1
            elif normalized_type == "punch":
                row["goalkeeper_punches"] += 1
            elif normalized_type in {"keeper sweeper", "keeper sweep", "keeper pick-up", "keeper pick up"}:
                row["goalkeeper_sweeps"] += 1
            elif normalized_type == "smother":
                row["goalkeeper_smotherings"] += 1
            elif normalized_type == "penalty conceded":
                row["goalkeeper_penalties_conceded"] += 1
            elif normalized_type not in {
                "penalty saved", "penalty saved to post", "shot saved",
                "shot saved off target", "shot saved to post",
            }:
                row["goalkeeper_unclassified_actions"] += 1
        elif event_type == "Pressure":
            row["pressures"] += 1
        elif event_type == "Interception":
            row["interceptions"] += 1
        elif event_type == "Ball Recovery":
            row["ball_recoveries"] += 1
        elif event_type == "Clearance":
            row["clearances"] += 1
        elif event_type == "Block":
            row["blocks"] += 1
        elif event_type == "Duel":
            duel_type = _name((event.get("duel") or {}).get("type"))
            if duel_type == "Tackle":
                row["tackles"] += 1
        elif event_type == "Dribble":
            row["dribbles"] += 1

    player_rows = []
    lineup_only_count = 0
    for player_key, player in players.items():
        values = counters[player_key]
        if not values:
            lineup_only_count += 1
        attempted = int(values.get("passes_attempted", 0))
        completed = int(values.get("passes_completed", 0))
        lengths = pass_lengths.get(player_key, [])
        xg = xg_values.get(player_key, [])
        metrics = {field: int(values.get(field, 0)) for field in COUNTER_FIELDS}
        player_seconds = None
        if minutes_result["valid"]:
            if player_key in minutes_result["seconds_by_player"]:
                player_seconds = minutes_result["seconds_by_player"][player_key]
            elif not player.get("appearance_evidence"):
                # A listed squad member with no on-pitch event is an unused substitute.
                player_seconds = 0.0
        if player_seconds is not None and player_seconds > 0:
            player["appearance_evidence"] = True
        metrics.update({
            "pass_completion_pct": round(completed / attempted * 100, 2) if attempted else None,
            "pass_length_mean": round(sum(lengths) / len(lengths), 2) if lengths else None,
            "pass_length_sum": round(sum(lengths), 3),
            "pass_length_observations": len(lengths),
            "xg": round(sum(xg), 3) if xg else None,
            "xg_shots_with_value": len(xg),
        })
        if (
            minutes_result["valid"]
            and player.get("appearance_evidence")
            and player_seconds is None
        ):
            warnings.append(
                f"Minutes hesaplanamadı; oyuncu appearance kanıtı var: {player.get('player_name', player_key)}"
            )
        classified_score_state_events = sum(
            int(score_state_counters[player_key][state].get("events", 0))
            for state in SCORE_STATES
        )
        unclassified_score_state_events = int(
            score_state_unclassified_events[player_key]
        )
        if score_state_timeline["status"] == "validated":
            score_state_status = (
                "validated" if unclassified_score_state_events == 0 else "partial"
            )
            score_state_metrics_by_state = _serialise_score_state_metrics(
                score_state_counters[player_key]
            )
        else:
            score_state_status = "unavailable"
            score_state_metrics_by_state = None

        player_rows.append({
            **player,
            "metrics": metrics,
            "score_state_analysis": {
                "status": score_state_status,
                "timeline_status": score_state_timeline["status"],
                "classified_player_events": classified_score_state_events,
                "unclassified_player_events": unclassified_score_state_events,
                "metrics_by_state": score_state_metrics_by_state,
                "unit": "raw event counts; xG is summed source xG",
                "interpretation_limit": (
                    "No score-state minutes or per-90 rates are calculated. "
                    "Events without a validated state/team mapping remain unclassified."
                ),
            },
            "pass_length_sum": round(sum(lengths), 3),
            "pass_length_observations": len(lengths),
            "minutes_played": round(player_seconds / 60.0, 2) if player_seconds is not None else None,
            "minutes_played_seconds": round(player_seconds, 3) if player_seconds is not None else None,
            "per90_metrics": calculate_per90_metrics(metrics, player_seconds),
        })

    player_rows.sort(key=lambda item: (
        (item.get("team_name") or ""),
        (item.get("player_name") or "").casefold(),
    ))
    home = match.get("home_team") or {}
    away = match.get("away_team") or {}
    return {
        "match": {
            "match_id": match.get("match_id"),
            "match_date": match.get("match_date"),
            "competition": _name(match.get("competition")),
            "season": _name(match.get("season")),
            "home_team": home.get("home_team_name"),
            "away_team": away.get("away_team_name"),
            "home_score": match.get("home_score"),
            "away_score": match.get("away_score"),
            "match_context": {
                **extract_match_context(match),
                "score_state_timeline": score_state_timeline,
            },
        },
        "quality": {
            "event_count": len(events),
            "players_listed_or_seen_count": len(players),
            "players_with_attributed_events": sum(1 for key in players if counters[key]),
            "lineup_only_player_count": lineup_only_count,
            "event_player_not_in_lineup_count": len(event_players_missing_from_lineup),
            "unattributed_non_structural_events": unattributed_events,
            "events_without_team_id": unknown_team_events,
            "event_types": dict(sorted(event_types.items())),
            "warnings": sorted(set(warnings)),
            "minutes_calculation": {
                "status": "valid" if minutes_result["valid"] else "unavailable",
                "periods": minutes_result["periods"],
                "players_with_minutes": sum(
                    1 for value in minutes_result["seconds_by_player"].values() if value > 0
                ),
                "warnings": minutes_result["warnings"],
                "errors": minutes_result["errors"],
            },
        },
        "player_metrics": player_rows,
    }


CB_PROFILE_METRICS = (
    "events",
    "passes_attempted",
    "passes_completed",
    "pass_completion_pct",
    "pass_length_mean",
    "carries",
    "pressures",
    "interceptions",
    "ball_recoveries",
    "clearances",
    "blocks",
    "tackles",
)



CB_METRIC_GROUPS = (
    {
        "code": "distribution_progression",
        "label": "Distribution and progression",
        "count_metrics": (
            "passes_attempted", "passes_completed", "crosses",
            "through_balls", "shot_assists", "carries",
        ),
        "context_metrics": ("pass_completion_pct", "pass_length_mean"),
        "description": "Recorded passing volume, selected pass types and carries.",
    },
    {
        "code": "defensive_activity",
        "label": "Defensive activity",
        "count_metrics": (
            "pressures", "tackles", "interceptions", "ball_recoveries",
        ),
        "context_metrics": (),
        "description": "Recorded pressure, tackle-type duels, interceptions and recoveries.",
    },
    {
        "code": "box_protection",
        "label": "Box protection",
        "count_metrics": ("clearances", "blocks"),
        "context_metrics": (),
        "description": "Recorded clearances and blocks.",
    },
)



FB_METRIC_GROUPS = (
    {
        "code": "attacking_output",
        "label": "Chance creation and attacking output",
        "count_metrics": (
            "crosses", "through_balls", "shot_assists", "assists",
            "shots", "goals",
        ),
        "rate_metrics": ("xg",),
        "context_metrics": (),
        "description": "Recorded delivery, chance creation and shot contribution.",
    },
    {
        "code": "distribution_progression",
        "label": "Distribution and progression",
        "count_metrics": (
            "passes_attempted", "passes_completed", "carries", "dribbles",
        ),
        "rate_metrics": (),
        "context_metrics": ("pass_completion_pct", "pass_length_mean"),
        "description": "Recorded passing volume, completion, carries and dribbles.",
    },
    {
        "code": "defensive_activity",
        "label": "Defensive activity",
        "count_metrics": (
            "pressures", "tackles", "interceptions", "ball_recoveries",
            "clearances", "blocks",
        ),
        "rate_metrics": (),
        "context_metrics": (),
        "description": "Recorded pressure, tackle-type duels, recoveries and defensive actions.",
    },
)


def _is_fullback_position(position: Any) -> bool:
    """Match full-back and wing-back labels without including centre-backs."""
    if not isinstance(position, str):
        return False
    normalized = " ".join(position.casefold().split())
    if not normalized or "center back" in normalized or "centre back" in normalized:
        return False
    return normalized.endswith("back") or normalized.endswith("fullback")


def build_fullback_profile(player_rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Group observed full-back/wing-back events; this is not a player rating."""
    fullbacks = []
    for player in player_rows:
        positions = player.get("positions_seen") or []
        fullback_positions = sorted({
            " ".join(position.split())
            for position in positions
            if _is_fullback_position(position)
        }, key=str.casefold)
        if not fullback_positions:
            continue

        metrics = player.get("metrics") or {}
        per90 = player.get("per90_metrics") or {}
        grouped_metrics = {}
        for group in FB_METRIC_GROUPS:
            count_fields = group["count_metrics"]
            rate_fields = group["rate_metrics"]
            context_fields = group["context_metrics"]
            grouped_metrics[group["code"]] = {
                "raw_counts": {key: metrics.get(key) for key in count_fields},
                "per90_counts": {
                    key: per90.get(key) for key in count_fields if key in per90
                },
                "raw_rate_totals": {key: metrics.get(key) for key in rate_fields},
                "per90_rate_metrics": {
                    key: per90.get(key) for key in rate_fields if key in per90
                },
                "context_metrics": {
                    key: metrics.get(key) for key in context_fields
                },
            }

        fullbacks.append({
            "player_id": player.get("player_id"),
            "player_name": player.get("player_name"),
            "team_names": player.get("team_names") or [],
            "positions_seen": positions,
            "fullback_position_labels": fullback_positions,
            "matches_listed_in_squads": player.get("matches_listed_in_squads", 0),
            "matches_with_appearance_evidence": player.get(
                "matches_with_appearance_evidence", 0
            ),
            "minutes_played": player.get("minutes_played"),
            "per90_metrics": player.get("per90_metrics"),
            "grouped_metrics": grouped_metrics,
            "data_quality": player.get("data_quality"),
            "data_consistency": player.get("data_consistency"),
            "identity": player.get("identity"),
            "metrics": {
                key: metrics.get(key)
                for key in (
                    "crosses", "through_balls", "shot_assists", "assists",
                    "shots", "goals", "xg", "passes_attempted",
                    "passes_completed", "pass_completion_pct",
                    "pass_length_mean", "carries", "dribbles",
                    "pressures", "tackles", "interceptions",
                    "ball_recoveries", "clearances", "blocks",
                )
            },
        })

    fullbacks.sort(key=lambda row: str(row.get("player_name") or "").casefold())
    return {
        "role_code": "FB",
        "role_name": "Full-back / Wing-back",
        "position_labels_included": [
            "Left Back", "Right Back", "Left Wing Back", "Right Wing Back",
        ],
        "metric_mode": "grouped_raw_event_counts_with_verified_per90_rates",
        "metric_groups": [
            {
                "code": group["code"],
                "label": group["label"],
                "count_metrics": list(group["count_metrics"]),
                "rate_metrics": list(group["rate_metrics"]),
                "context_metrics": list(group["context_metrics"]),
                "description": group["description"],
            }
            for group in FB_METRIC_GROUPS
        ],
        "player_count": len(fullbacks),
        "players": fullbacks,
        "interpretation_limits": [
            "No full-back rating or ranking is calculated.",
            "Raw event counts depend on selected minutes, team possession, role, match state and opponent context.",
            "Per-90 values are included only when derived from complete, positive verified minutes.",
            "The profile groups recorded actions; it does not measure overlapping runs, defensive positioning, crossing quality or tactical responsibility.",
            "Players with more than one observed position retain all source position labels; the profile does not infer a single primary role.",
        ],
    }




WINGER_METRIC_GROUPS = (
    {
        "code": "chance_creation_finishing",
        "label": "Chance creation and finishing",
        "count_metrics": ("shot_assists", "assists", "shots", "goals"),
        "rate_metrics": ("xg",),
        "context_metrics": (),
        "description": "Recorded shot creation, assists and shooting output.",
    },
    {
        "code": "wide_delivery",
        "label": "Wide delivery and passing",
        "count_metrics": (
            "crosses", "through_balls", "passes_attempted", "passes_completed",
        ),
        "rate_metrics": (),
        "context_metrics": ("pass_completion_pct", "pass_length_mean"),
        "description": "Recorded crosses, through balls and passing volume.",
    },
    {
        "code": "one_v_one_progression",
        "label": "One-v-one and ball progression",
        "count_metrics": ("dribbles", "carries"),
        "rate_metrics": (),
        "context_metrics": (),
        "description": "Recorded dribble actions and ball carries.",
    },
    {
        "code": "defensive_contribution",
        "label": "Pressing and defensive contribution",
        "count_metrics": (
            "pressures", "tackles", "interceptions", "ball_recoveries",
        ),
        "rate_metrics": (),
        "context_metrics": (),
        "description": "Recorded pressures, tackle-type duels, interceptions and recoveries.",
    },
)


def _is_winger_position(position: Any) -> bool:
    """Recognize explicit wing labels while excluding wing-back positions."""
    if not isinstance(position, str):
        return False
    tokens = set(" ".join(position.casefold().split()).split())
    return "wing" in tokens and not {"back", "fullback"}.intersection(tokens)


def build_winger_profile(player_rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Group explicit winger position labels; this is not a player rating."""
    wingers = []
    for player in player_rows:
        positions = player.get("positions_seen") or []
        winger_positions = sorted({
            " ".join(position.split())
            for position in positions
            if _is_winger_position(position)
        }, key=str.casefold)
        if not winger_positions:
            continue

        metrics = player.get("metrics") or {}
        per90 = player.get("per90_metrics") or {}
        grouped_metrics = {}
        for group in WINGER_METRIC_GROUPS:
            count_fields = group["count_metrics"]
            rate_fields = group["rate_metrics"]
            context_fields = group["context_metrics"]
            grouped_metrics[group["code"]] = {
                "raw_counts": {key: metrics.get(key) for key in count_fields},
                "per90_counts": {
                    key: per90.get(key) for key in count_fields if key in per90
                },
                "raw_rate_totals": {key: metrics.get(key) for key in rate_fields},
                "per90_rate_metrics": {
                    key: per90.get(key) for key in rate_fields if key in per90
                },
                "context_metrics": {
                    key: metrics.get(key) for key in context_fields
                },
            }

        wingers.append({
            "player_id": player.get("player_id"),
            "player_name": player.get("player_name"),
            "team_names": player.get("team_names") or [],
            "positions_seen": positions,
            "winger_position_labels": winger_positions,
            "matches_listed_in_squads": player.get("matches_listed_in_squads", 0),
            "matches_with_appearance_evidence": player.get(
                "matches_with_appearance_evidence", 0
            ),
            "minutes_played": player.get("minutes_played"),
            "per90_metrics": player.get("per90_metrics"),
            "grouped_metrics": grouped_metrics,
            "data_quality": player.get("data_quality"),
            "data_consistency": player.get("data_consistency"),
            "identity": player.get("identity"),
            "metrics": {
                key: metrics.get(key)
                for key in (
                    "shot_assists", "assists", "shots", "goals", "xg",
                    "crosses", "through_balls", "passes_attempted",
                    "passes_completed", "pass_completion_pct",
                    "pass_length_mean", "dribbles", "carries",
                    "pressures", "tackles", "interceptions", "ball_recoveries",
                )
            },
        })

    wingers.sort(key=lambda row: str(row.get("player_name") or "").casefold())
    return {
        "role_code": "W",
        "role_name": "Winger",
        "position_labels_included": ["Left Wing", "Right Wing"],
        "metric_mode": "grouped_raw_event_counts_with_verified_per90_rates",
        "metric_groups": [
            {
                "code": group["code"],
                "label": group["label"],
                "count_metrics": list(group["count_metrics"]),
                "rate_metrics": list(group["rate_metrics"]),
                "context_metrics": list(group["context_metrics"]),
                "description": group["description"],
            }
            for group in WINGER_METRIC_GROUPS
        ],
        "player_count": len(wingers),
        "players": wingers,
        "interpretation_limits": [
            "No winger rating or ranking is calculated.",
            "Raw event counts depend on selected minutes, team possession, role, match state and opponent context.",
            "Per-90 values are included only when derived from complete, positive verified minutes.",
            "The profile groups recorded actions; it does not measure successful take-on rate, crossing quality, off-ball runs, pressing triggers or tactical decision quality.",
            "Players with more than one observed position retain all source position labels; the profile does not infer one primary wing.",
            "Wing-back labels are deliberately excluded from this profile.",
        ],
    }




STRIKER_METRIC_GROUPS = (
    {
        "code": "finishing_output",
        "label": "Finishing and shot output",
        "count_metrics": ("shots", "goals"),
        "rate_metrics": ("xg",),
        "context_metrics": (),
        "description": "Recorded shots, goals and expected-goals total.",
    },
    {
        "code": "chance_creation",
        "label": "Chance creation and combination",
        "count_metrics": ("shot_assists", "assists", "through_balls"),
        "rate_metrics": (),
        "context_metrics": (),
        "description": "Recorded shot assists, assists and through balls.",
    },
    {
        "code": "link_play",
        "label": "Link play and ball retention",
        "count_metrics": (
            "passes_attempted", "passes_completed", "carries", "dribbles",
        ),
        "rate_metrics": (),
        "context_metrics": ("pass_completion_pct", "pass_length_mean"),
        "description": "Recorded passing, carries and dribbles.",
    },
    {
        "code": "pressing_contribution",
        "label": "Pressing and defensive contribution",
        "count_metrics": (
            "pressures", "tackles", "interceptions", "ball_recoveries",
        ),
        "rate_metrics": (),
        "context_metrics": (),
        "description": "Recorded pressures, tackle-type duels, interceptions and recoveries.",
    },
)


def _is_centre_forward_position(position: Any) -> bool:
    """Recognize central-forward and striker labels, excluding wide forwards."""
    if not isinstance(position, str):
        return False
    normalized = " ".join(position.casefold().split())
    if not normalized or "wing" in normalized:
        return False
    tokens = set(normalized.split())
    if "striker" in tokens:
        return True
    return "forward" in tokens and bool({"center", "centre"} & tokens)


def build_striker_profile(player_rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Group central-forward event metrics; this is not a finishing rating."""
    strikers = []
    for player in player_rows:
        positions = player.get("positions_seen") or []
        striker_positions = sorted({
            " ".join(position.split())
            for position in positions
            if _is_centre_forward_position(position)
        }, key=str.casefold)
        if not striker_positions:
            continue

        metrics = player.get("metrics") or {}
        per90 = player.get("per90_metrics") or {}
        grouped_metrics = {}
        for group in STRIKER_METRIC_GROUPS:
            count_fields = group["count_metrics"]
            rate_fields = group["rate_metrics"]
            context_fields = group["context_metrics"]
            grouped_metrics[group["code"]] = {
                "raw_counts": {key: metrics.get(key) for key in count_fields},
                "per90_counts": {
                    key: per90.get(key) for key in count_fields if key in per90
                },
                "raw_rate_totals": {key: metrics.get(key) for key in rate_fields},
                "per90_rate_metrics": {
                    key: per90.get(key) for key in rate_fields if key in per90
                },
                "context_metrics": {
                    key: metrics.get(key) for key in context_fields
                },
            }

        strikers.append({
            "player_id": player.get("player_id"),
            "player_name": player.get("player_name"),
            "team_names": player.get("team_names") or [],
            "positions_seen": positions,
            "striker_position_labels": striker_positions,
            "matches_listed_in_squads": player.get("matches_listed_in_squads", 0),
            "matches_with_appearance_evidence": player.get(
                "matches_with_appearance_evidence", 0
            ),
            "minutes_played": player.get("minutes_played"),
            "per90_metrics": player.get("per90_metrics"),
            "grouped_metrics": grouped_metrics,
            "data_quality": player.get("data_quality"),
            "data_consistency": player.get("data_consistency"),
            "identity": player.get("identity"),
            "metrics": {
                key: metrics.get(key)
                for key in (
                    "shots", "goals", "xg", "shot_assists", "assists",
                    "through_balls", "passes_attempted", "passes_completed",
                    "pass_completion_pct", "pass_length_mean", "carries",
                    "dribbles", "pressures", "tackles", "interceptions",
                    "ball_recoveries",
                )
            },
        })

    strikers.sort(key=lambda row: str(row.get("player_name") or "").casefold())
    return {
        "role_code": "ST",
        "role_name": "Striker / Centre-forward",
        "position_labels_included": [
            "Center Forward", "Left Center Forward", "Right Center Forward",
            "Striker", "Second Striker", "Secondary Striker",
        ],
        "metric_mode": "grouped_raw_event_counts_with_verified_per90_rates",
        "metric_groups": [
            {
                "code": group["code"],
                "label": group["label"],
                "count_metrics": list(group["count_metrics"]),
                "rate_metrics": list(group["rate_metrics"]),
                "context_metrics": list(group["context_metrics"]),
                "description": group["description"],
            }
            for group in STRIKER_METRIC_GROUPS
        ],
        "player_count": len(strikers),
        "players": strikers,
        "not_yet_available": [
            {
                "metric": "touches_in_box",
                "reason": "The current importer does not calculate a validated penalty-area touch metric.",
            },
            {
                "metric": "aerial_duel_success",
                "reason": "Aerial-duel classification and outcomes have not been separately validated.",
            },
            {
                "metric": "finishing_efficiency",
                "reason": "Shots and xG are descriptive event totals; no calibrated finishing model is implemented.",
            },
        ],
        "interpretation_limits": [
            "No striker rating or ranking is calculated.",
            "Raw event counts depend on selected minutes, team possession, role, match state and opponent context.",
            "Per-90 values are included only when derived from complete, positive verified minutes.",
            "Shots, goals and xG describe recorded output; they do not independently measure shot selection or finishing skill.",
            "The groups do not measure off-ball movement, pressing triggers, hold-up quality, aerial timing or tactical decision quality.",
            "Players with more than one observed position retain all source position labels; the profile does not infer one primary striker role.",
        ],
    }




GOALKEEPER_METRIC_GROUPS = (
    {
        "code": "shot_stopping",
        "label": "Shot stopping",
        "count_metrics": (
            "goalkeeper_saves", "goalkeeper_shots_faced",
            "goalkeeper_goals_conceded", "goalkeeper_penalty_saves",
            "goalkeeper_penalties_conceded",
        ),
        "context_metrics": (),
        "description": "Recorded goalkeeper save, shot-faced and concession event types.",
    },
    {
        "code": "area_control",
        "label": "Area control",
        "count_metrics": (
            "goalkeeper_collections", "goalkeeper_punches",
            "goalkeeper_sweeps", "goalkeeper_smotherings",
        ),
        "context_metrics": (),
        "description": "Recorded collections, punches, sweeps and smother actions.",
    },
    {
        "code": "distribution",
        "label": "Distribution and restarts",
        "count_metrics": (
            "passes_attempted", "passes_completed", "goal_kicks",
        ),
        "context_metrics": ("pass_completion_pct", "pass_length_mean"),
        "description": "Recorded passing volume, goal kicks and pass-length/completion context.",
    },
)


def _is_goalkeeper_position(position: Any) -> bool:
    """Match only explicit goalkeeper position labels."""
    if not isinstance(position, str):
        return False
    normalized = " ".join(position.casefold().split())
    return normalized in {"goalkeeper", "goal keeper", "keeper"}


def build_goalkeeper_profile(player_rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Group recorded goalkeeper events and distribution; this is not a rating."""
    goalkeepers = []
    for player in player_rows:
        positions = player.get("positions_seen") or []
        goalkeeper_positions = sorted({
            " ".join(position.split())
            for position in positions
            if _is_goalkeeper_position(position)
        }, key=str.casefold)
        if not goalkeeper_positions:
            continue

        metrics = player.get("metrics") or {}
        per90 = player.get("per90_metrics") or {}
        grouped_metrics = {}
        for group in GOALKEEPER_METRIC_GROUPS:
            count_fields = group["count_metrics"]
            context_fields = group["context_metrics"]
            grouped_metrics[group["code"]] = {
                "raw_counts": {key: metrics.get(key) for key in count_fields},
                "per90_counts": {
                    key: per90.get(key) for key in count_fields if key in per90
                },
                "context_metrics": {
                    key: metrics.get(key) for key in context_fields
                },
            }

        goalkeepers.append({
            "player_id": player.get("player_id"),
            "player_name": player.get("player_name"),
            "team_names": player.get("team_names") or [],
            "positions_seen": positions,
            "goalkeeper_position_labels": goalkeeper_positions,
            "matches_listed_in_squads": player.get("matches_listed_in_squads", 0),
            "matches_with_appearance_evidence": player.get(
                "matches_with_appearance_evidence", 0
            ),
            "minutes_played": player.get("minutes_played"),
            "per90_metrics": player.get("per90_metrics"),
            "grouped_metrics": grouped_metrics,
            "data_quality": player.get("data_quality"),
            "data_consistency": player.get("data_consistency"),
            "identity": player.get("identity"),
            "metrics": {
                key: metrics.get(key)
                for key in (
                    "goalkeeper_actions", "goalkeeper_saves",
                    "goalkeeper_shots_faced", "goalkeeper_goals_conceded",
                    "goalkeeper_collections", "goalkeeper_punches",
                    "goalkeeper_sweeps", "goalkeeper_smotherings",
                    "goalkeeper_penalty_saves", "goalkeeper_penalties_conceded",
                    "goalkeeper_unclassified_actions", "passes_attempted",
                    "passes_completed", "pass_completion_pct",
                    "pass_length_mean", "goal_kicks",
                )
            },
        })

    goalkeepers.sort(key=lambda row: str(row.get("player_name") or "").casefold())
    return {
        "role_code": "GK",
        "role_name": "Goalkeeper",
        "position_labels_included": ["Goalkeeper"],
        "metric_mode": "grouped_raw_event_counts_with_verified_per90_rates",
        "metric_groups": [
            {
                "code": group["code"],
                "label": group["label"],
                "count_metrics": list(group["count_metrics"]),
                "context_metrics": list(group["context_metrics"]),
                "description": group["description"],
            }
            for group in GOALKEEPER_METRIC_GROUPS
        ],
        "player_count": len(goalkeepers),
        "players": goalkeepers,
        "not_yet_available": [
            {
                "metric": "save_percentage",
                "reason": "A complete and validated shots-faced denominator has not been established for the current Open Data sample.",
            },
            {
                "metric": "post_shot_xg_or_goals_prevented",
                "reason": "The current importer does not calculate a validated post-shot expected-goals or goals-prevented model.",
            },
            {
                "metric": "cross_claim_rate",
                "reason": "Cross-claim opportunities and outcomes are not yet modelled as a validated denominator and numerator.",
            },
            {
                "metric": "distribution_long_ball_accuracy",
                "reason": "Pass length and completion are available, but a validated long-ball classification and accuracy metric is not yet implemented.",
            },
        ],
        "interpretation_limits": [
            "No goalkeeper rating or ranking is calculated.",
            "StatsBomb Goal Keeper events are action records and can represent attempts; a recorded event does not always prove the action succeeded.",
            "Per-90 event counts are included only when derived from complete, positive verified minutes.",
            "Pass completion and average pass length describe recorded distribution only; they do not independently measure decision quality.",
            "The profile does not measure positioning, reaction quality, starting position, communication or command of the penalty area.",
        ],
    }



CM_METRIC_GROUPS = (
    {
        "code": "distribution_progression",
        "label": "Passing and progression",
        "count_metrics": (
            "passes_attempted", "passes_completed", "through_balls",
            "carries", "dribbles",
        ),
        "rate_metrics": (),
        "context_metrics": ("pass_completion_pct", "pass_length_mean"),
        "description": "Recorded passing volume, through balls, ball carries and dribbles.",
    },
    {
        "code": "chance_creation",
        "label": "Chance creation and attacking contribution",
        "count_metrics": ("shot_assists", "assists", "crosses", "shots", "goals"),
        "rate_metrics": ("xg",),
        "context_metrics": (),
        "description": "Recorded shot assists, assists, deliveries and shooting output.",
    },
    {
        "code": "defensive_activity",
        "label": "Defensive work",
        "count_metrics": (
            "pressures", "tackles", "interceptions", "ball_recoveries",
            "clearances", "blocks",
        ),
        "rate_metrics": (),
        "context_metrics": (),
        "description": "Recorded pressure, tackle-type duels, recoveries and defensive actions.",
    },
)


def _is_central_midfield_position(position: Any) -> bool:
    """Recognize central midfield labels; leave wide midfield and wings out."""
    if not isinstance(position, str):
        return False
    normalized = " ".join(position.casefold().split())
    if not normalized or "midfield" not in normalized or "wide" in normalized:
        return False
    if normalized in {"defensive midfield", "attacking midfield", "central midfield"}:
        return True
    tokens = set(normalized.split())
    return "center" in tokens or "centre" in tokens


def build_central_midfield_profile(player_rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Group observed central-midfield actions; this is not a player rating."""
    midfielders = []
    for player in player_rows:
        positions = player.get("positions_seen") or []
        central_positions = sorted({
            " ".join(position.split())
            for position in positions
            if _is_central_midfield_position(position)
        }, key=str.casefold)
        if not central_positions:
            continue

        metrics = player.get("metrics") or {}
        per90 = player.get("per90_metrics") or {}
        grouped_metrics = {}
        for group in CM_METRIC_GROUPS:
            count_fields = group["count_metrics"]
            rate_fields = group["rate_metrics"]
            context_fields = group["context_metrics"]
            grouped_metrics[group["code"]] = {
                "raw_counts": {key: metrics.get(key) for key in count_fields},
                "per90_counts": {
                    key: per90.get(key) for key in count_fields if key in per90
                },
                "raw_rate_totals": {key: metrics.get(key) for key in rate_fields},
                "per90_rate_metrics": {
                    key: per90.get(key) for key in rate_fields if key in per90
                },
                "context_metrics": {
                    key: metrics.get(key) for key in context_fields
                },
            }

        midfielders.append({
            "player_id": player.get("player_id"),
            "player_name": player.get("player_name"),
            "team_names": player.get("team_names") or [],
            "positions_seen": positions,
            "central_midfield_position_labels": central_positions,
            "matches_listed_in_squads": player.get("matches_listed_in_squads", 0),
            "matches_with_appearance_evidence": player.get(
                "matches_with_appearance_evidence", 0
            ),
            "minutes_played": player.get("minutes_played"),
            "per90_metrics": player.get("per90_metrics"),
            "grouped_metrics": grouped_metrics,
            "data_quality": player.get("data_quality"),
            "data_consistency": player.get("data_consistency"),
            "identity": player.get("identity"),
            "metrics": {
                key: metrics.get(key)
                for key in (
                    "passes_attempted", "passes_completed", "pass_completion_pct",
                    "pass_length_mean", "through_balls", "carries", "dribbles",
                    "shot_assists", "assists", "crosses", "shots", "goals", "xg",
                    "pressures", "tackles", "interceptions", "ball_recoveries",
                    "clearances", "blocks",
                )
            },
        })

    midfielders.sort(key=lambda row: str(row.get("player_name") or "").casefold())
    return {
        "role_code": "CM",
        "role_name": "Central Midfielder",
        "position_labels_included": [
            "Center Midfield", "Left Center Midfield", "Right Center Midfield",
            "Center Defensive Midfield", "Center Attacking Midfield",
            "Defensive Midfield", "Attacking Midfield",
        ],
        "metric_mode": "grouped_raw_event_counts_with_verified_per90_rates",
        "metric_groups": [
            {
                "code": group["code"],
                "label": group["label"],
                "count_metrics": list(group["count_metrics"]),
                "rate_metrics": list(group["rate_metrics"]),
                "context_metrics": list(group["context_metrics"]),
                "description": group["description"],
            }
            for group in CM_METRIC_GROUPS
        ],
        "player_count": len(midfielders),
        "players": midfielders,
        "interpretation_limits": [
            "No central-midfielder rating or ranking is calculated.",
            "Raw event counts depend on selected minutes, team possession, role, match state and opponent context.",
            "Per-90 values are included only when derived from complete, positive verified minutes.",
            "The groups organize recorded actions; they do not measure scanning, pressure resistance, positional discipline or tactical decision quality.",
            "Players with more than one observed position retain all source position labels; the profile does not infer one primary midfield role.",
        ],
    }



def build_cb_profile(player_rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Select event profiles with an explicit centre-back position label.

    This is a metric summary, not a defensive rating. Raw counts are retained
    because minutes, team possession, defensive opportunities and opponent
    context have not yet been validated for normalization.
    """
    centre_backs = []
    for player in player_rows:
        positions = player.get("positions_seen") or []
        if not any("center back" in str(position).casefold() for position in positions):
            continue
        metrics = player.get("metrics") or {}
        per90 = player.get("per90_metrics") or {}
        grouped_metrics = {}
        for group in CB_METRIC_GROUPS:
            count_fields = group["count_metrics"]
            context_fields = group["context_metrics"]
            grouped_metrics[group["code"]] = {
                "raw_counts": {key: metrics.get(key) for key in count_fields},
                "per90_counts": {
                    key: per90.get(key)
                    for key in count_fields
                    if key in per90
                },
                "context_metrics": {
                    key: metrics.get(key) for key in context_fields
                },
            }
        centre_backs.append({
            "player_id": player.get("player_id"),
            "player_name": player.get("player_name"),
            "team_names": player.get("team_names") or [],
            "positions_seen": positions,
            "matches_listed_in_squads": player.get("matches_listed_in_squads", 0),
            "matches_with_appearance_evidence": player.get("matches_with_appearance_evidence", 0),
            "minutes_played": player.get("minutes_played"),
            "per90_metrics": player.get("per90_metrics"),
            "grouped_metrics": grouped_metrics,
            "data_quality": player.get("data_quality"),
            "data_consistency": player.get("data_consistency"),
            "identity": player.get("identity"),
            "metrics": {key: metrics.get(key) for key in CB_PROFILE_METRICS},
        })

    centre_backs.sort(key=lambda row: row["player_name"].casefold())
    return {
        "role_code": "CB",
        "role_name": "Centre-back",
        "metric_mode": "grouped_raw_event_counts_with_verified_per90_rates",
        "metric_groups": [
            {
                "code": group["code"],
                "label": group["label"],
                "count_metrics": list(group["count_metrics"]),
                "context_metrics": list(group["context_metrics"]),
                "description": group["description"],
            }
            for group in CB_METRIC_GROUPS
        ],
        "player_count": len(centre_backs),
        "players": centre_backs,
        "not_yet_available": [
            {
                "metric": "aerial_duel_success",
                "reason": "Aerial-duel event classification and outcomes have not yet been separately validated against source records.",
            }
        ],
        "interpretation_limits": [
            "No defensive rating or ranking is calculated.",
            "Raw defensive-action counts are not adjusted for minutes, team possession, defensive opportunities, match state or opponent quality.",
            "Per-90 counts are included only when verified positive minutes are available.",
            "The groups organize recorded actions; they are not tactical evaluations or proof of action quality.",
            "Event data does not establish defensive line height, spacing, scanning, body orientation, aerial timing or communication.",
            "Pass completion and pass length describe recorded distribution only; they do not independently measure decision quality.",
        ],
    }


def run_import(args: argparse.Namespace) -> dict[str, Any]:
    cache_root = Path(args.data_root).expanduser().resolve()
    report_path = Path(args.report).expanduser().resolve()
    provenance: list[dict[str, Any]] = []

    competitions, meta = fetch_json("competitions.json", cache_root, args.force)
    provenance.append(meta)
    comp_id, season_id = int(args.competition_id), int(args.season_id)
    competition = next((row for row in competitions
                        if int(row.get("competition_id", -1)) == comp_id
                        and int(row.get("season_id", -1)) == season_id), None)
    if competition is None:
        raise ImportErrorWithContext(
            f"{comp_id}/{season_id} competitions.json içinde bulunamadı."
        )

    matches_path = f"matches/{comp_id}/{season_id}.json"
    matches, meta = fetch_json(matches_path, cache_root, args.force)
    provenance.append(meta)
    if not isinstance(matches, list):
        raise ImportErrorWithContext("Matches dosyasının kökü JSON dizisi değil.")

    available_ids = {str(row.get("match_id")) for row in matches}
    if args.match_id:
        requested = [str(value) for value in args.match_id]
        missing = [value for value in requested if value not in available_ids]
        if missing:
            raise ImportErrorWithContext(
                "İstenen maç(lar) bu yarışma/sezonda yok: " + ", ".join(missing)
            )
        selected = [row for row in matches if str(row.get("match_id")) in requested]
        selected.sort(key=lambda row: (row.get("match_date") or "", row.get("match_id") or 0))
        # Preserve the explicit order requested by the caller.
        by_id = {str(row["match_id"]): row for row in selected}
        selected = [by_id[value] for value in requested]
    else:
        selected = sorted(
            matches,
            key=lambda row: (row.get("match_date") or "", row.get("match_id") or 0),
        )[:max(1, args.limit)]

    if not selected:
        raise ImportErrorWithContext("İşlenecek maç seçilemedi.")

    analysed_matches = []
    for match in selected:
        match_id = int(match["match_id"])
        lineups, lineup_meta = fetch_json(
            f"lineups/{match_id}.json", cache_root, args.force
        )
        events, events_meta = fetch_json(
            f"events/{match_id}.json", cache_root, args.force
        )
        provenance.extend([lineup_meta, events_meta])
        analysed_matches.append(analyse_match(match, lineups, events))

    all_players: dict[str, dict[str, Any]] = {}
    for match_report in analysed_matches:
        for player in match_report["player_metrics"]:
            key = str(player["player_id"])
            aggregate = all_players.setdefault(key, {
                "player_id": player["player_id"],
                "player_name": player["player_name"],
                "team_names": set(),
                "positions": set(),
                "squad_listings": 0,
                "matches_with_appearance_evidence": 0,
                "minutes_played_seconds": 0.0,
                "minutes_calculation_complete": True,
                "minutes_matches_valid": 0,
                "metrics": Counter(),
                "pass_length_sum": 0.0,
                "pass_length_observations": 0,
                "xg_values": [],
                "score_state_metrics": {
                    state: Counter() for state in SCORE_STATES
                },
                "score_state_match_statuses": Counter(),
                "score_state_classified_events": 0,
                "score_state_unclassified_events": 0,
                "match_rows": [],
            })
            aggregate["match_rows"].append(player)
            score_state_analysis = player.get("score_state_analysis") or {}
            score_state_status = score_state_analysis.get("status") or "unavailable"
            aggregate["score_state_match_statuses"][score_state_status] += 1
            aggregate["score_state_classified_events"] += int(
                score_state_analysis.get("classified_player_events") or 0
            )
            aggregate["score_state_unclassified_events"] += int(
                score_state_analysis.get("unclassified_player_events") or 0
            )
            metrics_by_state = score_state_analysis.get("metrics_by_state")
            if isinstance(metrics_by_state, dict):
                for state in SCORE_STATES:
                    for field in SCORE_STATE_METRIC_FIELDS:
                        value = (metrics_by_state.get(state) or {}).get(field, 0)
                        aggregate["score_state_metrics"][state][field] += value
            aggregate["squad_listings"] += 1
            if player.get("appearance_evidence"):
                aggregate["matches_with_appearance_evidence"] += 1
            if (
                match_report["quality"]["minutes_calculation"]["status"] == "valid"
                and player.get("minutes_played_seconds") is not None
            ):
                aggregate["minutes_played_seconds"] += player["minutes_played_seconds"]
                aggregate["minutes_matches_valid"] += 1
            else:
                aggregate["minutes_calculation_complete"] = False
            if player.get("team_name"):
                aggregate["team_names"].add(player["team_name"])
            aggregate["positions"].update(player.get("positions") or [])
            for field in COUNTER_FIELDS:
                aggregate["metrics"][field] += player["metrics"].get(field, 0)
            aggregate["pass_length_sum"] += player.get("pass_length_sum", 0.0)
            aggregate["pass_length_observations"] += player.get("pass_length_observations", 0)
            if player["metrics"].get("xg") is not None:
                aggregate["xg_values"].append(player["metrics"]["xg"])

    aggregate_rows = []
    for player in all_players.values():
        counts = {field: int(player["metrics"].get(field, 0)) for field in COUNTER_FIELDS}
        attempts = counts["passes_attempted"]
        counts.update({
            "pass_completion_pct": (
                round(counts["passes_completed"] / attempts * 100, 2)
                if attempts else None
            ),
            "pass_length_mean": (
                round(player["pass_length_sum"] / player["pass_length_observations"], 2)
                if player["pass_length_observations"] else None
            ),
            "xg": round(sum(player["xg_values"]), 3) if player["xg_values"] else None,
        })
        match_status_counts = {
            status: int(player["score_state_match_statuses"].get(status, 0))
            for status in ("validated", "partial", "unavailable")
        }
        if match_status_counts["validated"] == len(player["match_rows"]):
            score_state_status = "validated"
        elif match_status_counts["validated"] + match_status_counts["partial"] > 0:
            score_state_status = "partial"
        else:
            score_state_status = "unavailable"
        has_score_state_metrics = (
            match_status_counts["validated"] + match_status_counts["partial"] > 0
        )
        aggregate_score_state_analysis = {
            "status": score_state_status,
            "match_records": len(player["match_rows"]),
            "match_status_counts": match_status_counts,
            "classified_player_events": int(player["score_state_classified_events"]),
            "unclassified_player_events": int(player["score_state_unclassified_events"]),
            "metrics_by_state": (
                _serialise_score_state_metrics(player["score_state_metrics"])
                if has_score_state_metrics else None
            ),
            "unit": "raw event counts across selected match records; xG is summed source xG",
            "interpretation_limit": (
                "No score-state minutes or per-90 rates are calculated. "
                "Only match records with a validated score timeline contribute to state totals."
            ),
        }
        aggregate_row = {
            "player_id": player["player_id"],
            "player_name": player["player_name"],
            "team_names": sorted(player["team_names"]),
            "positions_seen": sorted(player["positions"]),
            "matches_listed_in_squads": player["squad_listings"],
            "matches_with_appearance_evidence": player["matches_with_appearance_evidence"],
            "minutes_played": (
                round(player["minutes_played_seconds"] / 60.0, 2)
                if player["minutes_calculation_complete"] else None
            ),
            "minutes_calculation_complete": player["minutes_calculation_complete"],
            "minutes_matches_valid": player["minutes_matches_valid"],
            "per90_metrics": calculate_per90_metrics(
                counts,
                player["minutes_played_seconds"] if player["minutes_calculation_complete"] else None,
            ),
            "metrics": counts,
            "score_state_analysis": aggregate_score_state_analysis,
        }
        aggregate_row["data_quality"] = calculate_player_data_quality(aggregate_row)
        aggregate_row["data_consistency"] = calculate_player_data_consistency(
            aggregate_row, player["match_rows"]
        )
        aggregate_row["identity"] = calculate_player_identity(
            aggregate_row, player["match_rows"]
        )
        aggregate_rows.append(aggregate_row)
    aggregate_rows.sort(key=lambda row: row["player_name"].casefold())

    name_collisions = find_player_name_collisions(aggregate_rows)
    collision_ids_by_player: dict[str, set[str]] = defaultdict(set)
    for collision in name_collisions:
        collision_ids = {str(value) for value in collision["player_ids"]}
        for player_id in collision_ids:
            collision_ids_by_player[player_id].update(collision_ids - {player_id})
    for player in aggregate_rows:
        other_ids = sorted(collision_ids_by_player.get(str(player["player_id"]), set()))
        player["identity"]["possible_same_name_collision"] = bool(other_ids)
        player["identity"]["other_same_name_player_ids"] = other_ids

    role_profiles = {
        "CB": build_cb_profile(aggregate_rows),
        "FB": build_fullback_profile(aggregate_rows),
        "CM": build_central_midfield_profile(aggregate_rows),
        "W": build_winger_profile(aggregate_rows),
        "ST": build_striker_profile(aggregate_rows),
        "GK": build_goalkeeper_profile(aggregate_rows),
    }
    role_benchmarks = build_role_benchmarks(role_profiles)
    player_evaluation_readiness = build_player_evaluation_readiness(
        role_profiles, role_benchmarks
    )

    report = {
        "report_type": "statsbomb_import_quality_and_event_profile",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": {
            "name": SOURCE_NAME,
            "repository": SOURCE_REPOSITORY,
            "repository_ref": "master",
            "attribution_required_for_shared_analysis": True,
            "usage_note": (
                "Public release described by StatsBomb as intended for research "
                "and genuine football analytics interest. This prototype does "
                "not establish a commercial Vel Scout licence."
            ),
        },
        "competition_season": {
            "competition_id": comp_id,
            "season_id": season_id,
            "competition_name": competition.get("competition_name"),
            "season_name": competition.get("season_name"),
            "gender": competition.get("competition_gender"),
            "is_youth_competition": competition.get("competition_youth"),
        },
        "sample": {
            "available_matches_in_season_file": len(matches),
            "selected_match_count": len(analysed_matches),
            "selected_match_ids": [row["match"]["match_id"] for row in analysed_matches],
            "event_count": sum(row["quality"]["event_count"] for row in analysed_matches),
            "unique_players_listed_or_seen": len(all_players),
            "possible_same_name_collision_groups": len(name_collisions),
            "players_in_possible_name_collisions": sum(
                len(item["player_ids"]) for item in name_collisions
            ),
            "event_players_missing_from_lineups": sum(
                row["quality"]["event_player_not_in_lineup_count"] for row in analysed_matches
            ),
        },
        "metric_definitions": METRIC_DEFINITIONS,
        "limitations": [
            "Minutes are calculated from Starting XI, substitutions, Player Off/On, dismissal events and period-local timestamps. If period clocks or required state transitions are incomplete, minutes remain null; per-90 values are emitted only for complete, positive minute totals.",
            "Lineup/squad listings can include unused substitutes; unused substitutes receive 0.00 minutes only when the match-level event clock passes validation.",
            "Peer percentiles are emitted only when same-role, same-report cohorts meet the minimum verified-minute and peer-count requirements; they describe event frequency, not player quality.",
            "Event data cannot establish off-ball positioning, scanning, body orientation, communication or visual tactical behaviour.",
            "This is a selected research dataset, not complete coverage of all leagues, seasons or youth players.",
            "Players are grouped only by the StatsBomb player_id; names are never used as a merge key. Name variants for one ID are exposed for review.",
            "The report is not a definitive scout verdict, potential rating or transfer recommendation.",
            "Score-state player counts are raw event totals, not rates. They are available only when the match score timeline reconciles to the listed final score and the event team maps to the match home/away team.",
            "No minutes by score state or score-state per-90 metrics are calculated; raw counts across different state durations must not be compared as performance rates.",
        ],
        "source_files": provenance,
        "matches": analysed_matches,
        "player_sample_totals": aggregate_rows,
        "player_identity_review": {
            "matching_rule": "case-insensitive exact name after whitespace normalization; source IDs remain separate",
            "same_name_different_ids": name_collisions,
        },
        "role_profiles": role_profiles,
        "role_benchmarks": role_benchmarks,
        "player_evaluation_readiness": player_evaluation_readiness,
    }

    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    csv_path = report_path.with_suffix(".players.csv")
    with csv_path.open("w", encoding="utf-8-sig", newline="") as stream:
        fields = [
            "player_id", "player_name", "team_names", "positions_seen",
            "matches_listed_in_squads", "matches_with_appearance_evidence",
            "minutes_played", "minutes_calculation_complete", "minutes_matches_valid",
            "data_quality_status", "data_quality_reasons",
            "data_quality_appearance_evidence", "data_quality_minutes_complete",
            "data_quality_has_attributed_events",
            "data_consistency_status", "data_consistency_reasons",
            "data_consistency_match_records",
            "player_identity_key", "player_identity_status",
            "player_identity_reasons", "player_identity_name_variants",
            "possible_same_name_collision", "other_same_name_player_ids",
            "score_state_analysis_status",
            "score_state_matches_validated", "score_state_matches_partial",
            "score_state_matches_unavailable",
            "score_state_classified_player_events",
            "score_state_unclassified_player_events",
            "score_state_leading_metrics_json",
            "score_state_drawing_metrics_json",
            "score_state_trailing_metrics_json",
            *COUNTER_FIELDS, "pass_completion_pct", "pass_length_mean", "xg",
            *[f"per90_{field}" for field in (*COUNTER_FIELDS, "xg")],
        ]
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for row in aggregate_rows:
            output = {
                "player_id": row["player_id"],
                "player_name": row["player_name"],
                "team_names": " | ".join(row["team_names"]),
                "positions_seen": " | ".join(row["positions_seen"]),
                "matches_listed_in_squads": row["matches_listed_in_squads"],
                "matches_with_appearance_evidence": row["matches_with_appearance_evidence"],
                "minutes_played": row["minutes_played"],
                "minutes_calculation_complete": row["minutes_calculation_complete"],
                "minutes_matches_valid": row["minutes_matches_valid"],
                "data_quality_status": row["data_quality"]["status"],
                "data_quality_reasons": " | ".join(row["data_quality"]["reasons"]),
                "data_quality_appearance_evidence": row["data_quality"]["checks"]["appearance_evidence"],
                "data_quality_minutes_complete": row["data_quality"]["checks"]["minutes_calculation_complete"],
                "data_quality_has_attributed_events": row["data_quality"]["checks"]["attributed_events"],
                "data_consistency_status": row["data_consistency"]["status"],
                "data_consistency_reasons": " | ".join(row["data_consistency"]["reasons"]),
                "data_consistency_match_records": row["data_consistency"]["checked_match_records"],
                "player_identity_key": row["identity"]["key"],
                "player_identity_status": row["identity"]["status"],
                "player_identity_reasons": " | ".join(row["identity"]["reasons"]),
                "player_identity_name_variants": " | ".join(row["identity"]["name_variants"]),
                "possible_same_name_collision": row["identity"]["possible_same_name_collision"],
                "other_same_name_player_ids": " | ".join(row["identity"]["other_same_name_player_ids"]),
                "score_state_analysis_status": row["score_state_analysis"]["status"],
                "score_state_matches_validated": row["score_state_analysis"]["match_status_counts"]["validated"],
                "score_state_matches_partial": row["score_state_analysis"]["match_status_counts"]["partial"],
                "score_state_matches_unavailable": row["score_state_analysis"]["match_status_counts"]["unavailable"],
                "score_state_classified_player_events": row["score_state_analysis"]["classified_player_events"],
                "score_state_unclassified_player_events": row["score_state_analysis"]["unclassified_player_events"],
                "score_state_leading_metrics_json": (
                    json.dumps(row["score_state_analysis"]["metrics_by_state"]["leading"], ensure_ascii=False, sort_keys=True)
                    if row["score_state_analysis"]["metrics_by_state"] is not None else ""
                ),
                "score_state_drawing_metrics_json": (
                    json.dumps(row["score_state_analysis"]["metrics_by_state"]["drawing"], ensure_ascii=False, sort_keys=True)
                    if row["score_state_analysis"]["metrics_by_state"] is not None else ""
                ),
                "score_state_trailing_metrics_json": (
                    json.dumps(row["score_state_analysis"]["metrics_by_state"]["trailing"], ensure_ascii=False, sort_keys=True)
                    if row["score_state_analysis"]["metrics_by_state"] is not None else ""
                ),
                **row["metrics"],
                **{
                    f"per90_{field}": (row.get("per90_metrics") or {}).get(field)
                    for field in (*COUNTER_FIELDS, "xg")
                },
            }
            writer.writerow(output)

    report["output_files"] = {
        "json": str(report_path),
        "players_csv": str(csv_path),
    }
    # Rewrite once with output paths included.
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return report



BENCHMARK_METRIC_GUIDANCE = {
    "passes_attempted": {
        "display_name": "Passes attempted",
        "unit": "events per 90 verified minutes",
        "directionality": "context_dependent",
        "what_it_measures": "Volume of recorded pass attempts.",
        "interpretation_note": "Higher volume can reflect possession, team build-up patterns or the player's role rather than better passing.",
        "does_not_measure": "Pass accuracy, difficulty, progression value or decision quality.",
    },
    "passes_completed": {
        "display_name": "Passes completed",
        "unit": "events per 90 verified minutes",
        "directionality": "context_dependent",
        "what_it_measures": "Volume of recorded completed passes.",
        "interpretation_note": "Read alongside attempts, pass difficulty, direction and team possession; a high count alone is not passing quality.",
        "does_not_measure": "Completion percentage, progressive value or execution difficulty.",
    },
    "pressures": {
        "display_name": "Pressures",
        "unit": "events per 90 verified minutes",
        "directionality": "context_dependent",
        "what_it_measures": "Volume of recorded pressure actions.",
        "interpretation_note": "High volume may reflect pressing role, opponent possession or team pressing strategy.",
        "does_not_measure": "Pressure success, coordination, intensity or whether possession was regained.",
    },
    "tackles": {
        "display_name": "Tackles",
        "unit": "events per 90 verified minutes",
        "directionality": "context_dependent",
        "what_it_measures": "Volume of recorded tackle-type duel events.",
        "interpretation_note": "Interpret with defensive opportunities, duel outcomes and team context.",
        "does_not_measure": "Tackle success rate, foul risk or overall defensive quality.",
    },
    "interceptions": {
        "display_name": "Interceptions",
        "unit": "events per 90 verified minutes",
        "directionality": "context_dependent",
        "what_it_measures": "Volume of recorded interception events.",
        "interpretation_note": "Affected by opponent passing volume, team block and the player's defensive role.",
        "does_not_measure": "All passing lanes denied, anticipation quality or total defensive contribution.",
    },
    "ball_recoveries": {
        "display_name": "Ball recoveries",
        "unit": "events per 90 verified minutes",
        "directionality": "context_dependent",
        "what_it_measures": "Volume of recorded ball-recovery events.",
        "interpretation_note": "Affected by loose-ball opportunities, possession patterns and team pressure.",
        "does_not_measure": "Recovery difficulty, territorial value or whether the recovery created an advantage.",
    },
    "clearances": {
        "display_name": "Clearances",
        "unit": "events per 90 verified minutes",
        "directionality": "context_dependent",
        "what_it_measures": "Volume of recorded clearances.",
        "interpretation_note": "High volume can reflect defensive workload or sustained pressure rather than superior defending.",
        "does_not_measure": "Clearance quality, danger removed or ability to prevent the preceding attack.",
    },
    "blocks": {
        "display_name": "Blocks",
        "unit": "events per 90 verified minutes",
        "directionality": "context_dependent",
        "what_it_measures": "Volume of recorded blocks.",
        "interpretation_note": "Depends on shots and passing lanes faced, defensive positioning and team shape.",
        "does_not_measure": "Block success beyond the recorded event, shot danger prevented or positioning quality.",
    },
    "crosses": {
        "display_name": "Crosses",
        "unit": "events per 90 verified minutes",
        "directionality": "context_dependent",
        "what_it_measures": "Volume of recorded cross attempts.",
        "interpretation_note": "Interpret with crossing opportunities, target movement and team attacking structure.",
        "does_not_measure": "Cross accuracy, delivery quality or chance created.",
    },
    "shot_assists": {
        "display_name": "Shot assists",
        "unit": "events per 90 verified minutes",
        "directionality": "context_dependent",
        "what_it_measures": "Volume of recorded actions credited as leading to a teammate's shot.",
        "interpretation_note": "The resulting shot's quality and the teammate's execution matter; volume alone is incomplete.",
        "does_not_measure": "Chance quality, expected assists or creation value independent of the shot outcome.",
    },
    "carries": {
        "display_name": "Carries",
        "unit": "events per 90 verified minutes",
        "directionality": "context_dependent",
        "what_it_measures": "Volume of recorded ball-carry events.",
        "interpretation_note": "Affected by role, possession and available space; pair with progression and outcome measures when validated.",
        "does_not_measure": "Progressive distance, pressure resistance or value gained by the carry.",
    },
    "dribbles": {
        "display_name": "Dribbles",
        "unit": "events per 90 verified minutes",
        "directionality": "context_dependent",
        "what_it_measures": "Volume of recorded dribble events.",
        "interpretation_note": "Treat as activity volume until outcome and success handling are separately validated.",
        "does_not_measure": "Dribble success rate, opponent beaten or possession retained.",
    },
    "through_balls": {
        "display_name": "Through balls",
        "unit": "events per 90 verified minutes",
        "directionality": "context_dependent",
        "what_it_measures": "Volume of recorded through-ball pass events.",
        "interpretation_note": "Interpret with completion, receiver movement, defensive line and resulting chance.",
        "does_not_measure": "Pass accuracy, defensive-line break value or chance quality.",
    },
    "assists": {
        "display_name": "Assists",
        "unit": "events per 90 verified minutes",
        "directionality": "context_dependent",
        "what_it_measures": "Volume of goals with a recorded assist attribution to the player.",
        "interpretation_note": "Sensitive to teammate finishing and small samples; use alongside chance-creation context.",
        "does_not_measure": "All creative contribution, expected assists or repeatable chance quality.",
    },
    "shots": {
        "display_name": "Shots",
        "unit": "events per 90 verified minutes",
        "directionality": "context_dependent",
        "what_it_measures": "Volume of recorded shot attempts.",
        "interpretation_note": "High volume can reflect role and team chance supply; assess locations and shot quality separately.",
        "does_not_measure": "Finishing skill, shot quality or conversion rate.",
    },
    "goals": {
        "display_name": "Goals",
        "unit": "events per 90 verified minutes",
        "directionality": "context_dependent",
        "what_it_measures": "Volume of recorded goals credited to the player.",
        "interpretation_note": "A useful outcome count, but strongly affected by opportunity, teammates and sample size.",
        "does_not_measure": "Finishing sustainability, conversion above expectation or overall attacking value.",
    },
    "xg": {
        "display_name": "Expected goals (xG)",
        "unit": "xG per 90 verified minutes",
        "directionality": "context_dependent",
        "what_it_measures": "Sum of source-provided expected-goal values for the player's shots, normalized per 90.",
        "interpretation_note": "Combines chance volume and shot-level probability; interpret with role, shot locations and the source model.",
        "does_not_measure": "Goals scored, finishing above expectation or a model-independent measure of chance quality.",
    },
    "goalkeeper_saves": {
        "display_name": "Goalkeeper saves",
        "unit": "events per 90 verified minutes",
        "directionality": "context_dependent",
        "what_it_measures": "Volume of recorded goalkeeper save events.",
        "interpretation_note": "More saves can mean more shots faced; compare with shot quality and a validated denominator.",
        "does_not_measure": "Save percentage, goals prevented or shot-stopping quality.",
    },
    "goalkeeper_shots_faced": {
        "display_name": "Shots faced",
        "unit": "events per 90 verified minutes",
        "directionality": "context_dependent",
        "what_it_measures": "Volume of recorded shots faced by the goalkeeper.",
        "interpretation_note": "Primarily describes defensive workload and opponent shot volume.",
        "does_not_measure": "Shot danger, goalkeeper responsibility or defensive quality.",
    },
    "goalkeeper_goals_conceded": {
        "display_name": "Goals conceded",
        "unit": "events per 90 verified minutes",
        "directionality": "adverse_outcome_context_dependent",
        "what_it_measures": "Volume of recorded goals conceded in the goalkeeper event data.",
        "interpretation_note": "A higher count is an adverse team outcome, but attribution requires shot quality, defensive errors, minutes and context.",
        "does_not_measure": "Goals caused by the goalkeeper, goals prevented or goalkeeper quality.",
    },
    "goalkeeper_collections": {
        "display_name": "Goalkeeper collections",
        "unit": "events per 90 verified minutes",
        "directionality": "context_dependent",
        "what_it_measures": "Volume of recorded goalkeeper collection events.",
        "interpretation_note": "Depends on delivery volume, defensive structure and the goalkeeper's role.",
        "does_not_measure": "Collection success rate, claim difficulty or command of the area.",
    },
    "goalkeeper_punches": {
        "display_name": "Goalkeeper punches",
        "unit": "events per 90 verified minutes",
        "directionality": "context_dependent",
        "what_it_measures": "Volume of recorded goalkeeper punch events.",
        "interpretation_note": "Interpret with cross and set-piece exposure, traffic and alternative handling choices.",
        "does_not_measure": "Punch accuracy, decision quality or overall aerial command.",
    },
    "goalkeeper_sweeps": {
        "display_name": "Goalkeeper sweeps",
        "unit": "events per 90 verified minutes",
        "directionality": "context_dependent",
        "what_it_measures": "Volume of recorded goalkeeper sweeping actions.",
        "interpretation_note": "Affected by defensive line height, through-ball exposure and team tactics.",
        "does_not_measure": "Sweeping success, starting position quality or space controlled.",
    },
    "goalkeeper_smotherings": {
        "display_name": "Goalkeeper smotherings",
        "unit": "events per 90 verified minutes",
        "directionality": "context_dependent",
        "what_it_measures": "Volume of recorded goalkeeper smothering events.",
        "interpretation_note": "Depends on one-on-one and loose-ball opportunities; sample size is often small.",
        "does_not_measure": "Smothering success rate or all close-range threat management.",
    },
    "goalkeeper_penalty_saves": {
        "display_name": "Penalty saves",
        "unit": "events per 90 verified minutes",
        "directionality": "context_dependent",
        "what_it_measures": "Volume of recorded penalty-save events.",
        "interpretation_note": "Penalty samples are usually sparse; do not infer a stable skill level from a few events.",
        "does_not_measure": "Penalty-save percentage or repeatable penalty-stopping ability.",
    },
    "goal_kicks": {
        "display_name": "Goal kicks",
        "unit": "events per 90 verified minutes",
        "directionality": "context_dependent",
        "what_it_measures": "Volume of recorded goal-kick restarts.",
        "interpretation_note": "Influenced by match state, opposition pressure and team restart strategy.",
        "does_not_measure": "Goal-kick accuracy, distance, possession retained or distribution quality.",
    },
}


ROLE_BENCHMARK_METRICS = {
    "CB": (
        "passes_attempted", "passes_completed", "pressures", "tackles",
        "interceptions", "ball_recoveries", "clearances", "blocks",
    ),
    "FB": (
        "crosses", "shot_assists", "carries", "dribbles", "pressures",
        "tackles", "interceptions", "ball_recoveries",
    ),
    "CM": (
        "passes_attempted", "passes_completed", "through_balls", "carries",
        "dribbles", "shot_assists", "assists", "pressures", "tackles",
        "interceptions", "ball_recoveries",
    ),
    "W": (
        "shots", "goals", "xg", "shot_assists", "crosses", "dribbles",
        "carries", "pressures",
    ),
    "ST": (
        "shots", "goals", "xg", "shot_assists", "assists", "through_balls",
        "carries", "dribbles", "pressures",
    ),
    "GK": (
        "goalkeeper_saves", "goalkeeper_shots_faced",
        "goalkeeper_goals_conceded", "goalkeeper_collections",
        "goalkeeper_punches", "goalkeeper_sweeps",
        "goalkeeper_smotherings", "goalkeeper_penalty_saves",
        "goal_kicks", "passes_attempted",
    ),
}


def _peer_percentile(value: float, cohort: list[float]) -> float:
    """Return a tie-aware midrank percentile within the supplied cohort."""
    less = sum(item < value for item in cohort)
    equal = sum(item == value for item in cohort)
    return round(((less + 0.5 * equal) / len(cohort)) * 100.0, 1)


def _linear_quantile(sorted_values: list[float], quantile: float) -> float | None:
    """Calculate a linearly interpolated quantile from sorted observations."""
    if not _finite(quantile) or not 0.0 <= float(quantile) <= 1.0:
        raise ValueError("quantile 0 ile 1 arasında olmalı.")
    if not sorted_values:
        return None
    position = (len(sorted_values) - 1) * float(quantile)
    lower_index = math.floor(position)
    upper_index = math.ceil(position)
    if lower_index == upper_index:
        return float(sorted_values[lower_index])
    fraction = position - lower_index
    lower = float(sorted_values[lower_index])
    upper = float(sorted_values[upper_index])
    return lower + ((upper - lower) * fraction)


def _cohort_distribution(sorted_values: list[float]) -> dict[str, Any] | None:
    """Describe a peer cohort with min, quartiles, median and max."""
    if not sorted_values:
        return None
    p25 = _linear_quantile(sorted_values, 0.25)
    median = _linear_quantile(sorted_values, 0.50)
    p75 = _linear_quantile(sorted_values, 0.75)
    return {
        "minimum": round(float(sorted_values[0]), 3),
        "p25": round(float(p25), 3),
        "median": round(float(median), 3),
        "p75": round(float(p75), 3),
        "maximum": round(float(sorted_values[-1]), 3),
        "quartile_method": "linear interpolation over sorted observations",
    }


def build_role_benchmarks(
    role_profiles: dict[str, dict[str, Any]],
    minimum_verified_minutes: float = 450.0,
    minimum_cohort_size: int = 10,
) -> dict[str, Any]:
    """Build cautious same-report, same-role percentiles from verified per-90 data."""
    if not _finite(minimum_verified_minutes) or float(minimum_verified_minutes) < 0:
        raise ValueError("minimum_verified_minutes negatif veya geçersiz olamaz.")
    if minimum_cohort_size < 2:
        raise ValueError("minimum_cohort_size en az 2 olmalı.")

    benchmarks: dict[str, Any] = {}
    for role_code, metric_names in ROLE_BENCHMARK_METRICS.items():
        profile = role_profiles.get(role_code) or {}
        players = profile.get("players") or []
        prepared = []
        for player in players:
            reasons = []
            minutes = player.get("minutes_played")
            if not _finite(minutes) or float(minutes) <= 0:
                reasons.append("verified_minutes_unavailable")
            elif float(minutes) < minimum_verified_minutes:
                reasons.append("below_minimum_verified_minutes")
            if (player.get("data_quality") or {}).get("status") != "complete":
                reasons.append("data_quality_not_complete")
            if (player.get("data_consistency") or {}).get("status") != "consistent":
                reasons.append("data_consistency_not_consistent")
            if (player.get("identity") or {}).get("status") != "consistent":
                reasons.append("identity_not_consistent")
            per90 = player.get("per90_metrics")
            if not isinstance(per90, dict) or not per90:
                reasons.append("per90_metrics_unavailable")
            prepared.append({
                "player": player,
                "reasons": sorted(set(reasons)),
                "eligible": not reasons,
            })

        eligible = [item for item in prepared if item["eligible"]]
        metric_cohorts: dict[str, list[float]] = {}
        metric_summaries = {}
        for metric in metric_names:
            values = sorted(
                float(item["player"]["per90_metrics"][metric])
                for item in eligible
                if _finite((item["player"].get("per90_metrics") or {}).get(metric))
            )
            metric_cohorts[metric] = values
            ready = len(values) >= minimum_cohort_size
            metric_summaries[metric] = {
                "status": "ready" if ready else "insufficient_sample",
                "eligible_values": len(values),
                "minimum_required": minimum_cohort_size,
                "distribution": _cohort_distribution(values) if ready else None,
            }

        player_results = []
        for item in prepared:
            player = item["player"]
            per90 = player.get("per90_metrics") or {}
            player_metrics = {}
            for metric in metric_names:
                value = per90.get(metric) if isinstance(per90, dict) else None
                cohort = metric_cohorts[metric]
                if item["eligible"] and _finite(value) and len(cohort) >= minimum_cohort_size:
                    distribution = metric_summaries[metric]["distribution"]
                    cohort_median = _linear_quantile(cohort, 0.50)
                    cohort_p25 = _linear_quantile(cohort, 0.25)
                    cohort_p75 = _linear_quantile(cohort, 0.75)
                    player_metrics[metric] = {
                        "value_per90": round(float(value), 3),
                        "cohort_size": len(cohort),
                        "percentile": _peer_percentile(float(value), cohort),
                        "difference_from_median_per90": round(
                            float(value) - float(cohort_median), 3
                        ),
                        "within_cohort_middle_50_percent": (
                            float(cohort_p25) <= float(value) <= float(cohort_p75)
                        ),
                        "status": "ready",
                    }
                else:
                    if not item["eligible"]:
                        status = "player_not_eligible"
                    elif not _finite(value):
                        status = "metric_unavailable"
                    else:
                        status = "insufficient_sample"
                    player_metrics[metric] = {
                        "value_per90": round(float(value), 3) if _finite(value) else None,
                        "cohort_size": len(cohort),
                        "percentile": None,
                        "difference_from_median_per90": None,
                        "within_cohort_middle_50_percent": None,
                        "status": status,
                    }
            player_results.append({
                "player_id": player.get("player_id"),
                "player_name": player.get("player_name"),
                "minutes_played": player.get("minutes_played"),
                "eligible_for_peer_comparison": item["eligible"],
                "eligibility_reasons": item["reasons"],
                "metrics": player_metrics,
            })

        benchmarks[role_code] = {
            "role_name": profile.get("role_name"),
            "comparison_scope": "same competition, season report and role profile",
            "minimum_verified_minutes": minimum_verified_minutes,
            "minimum_cohort_size": minimum_cohort_size,
            "profile_player_count": len(players),
            "eligible_player_count": len(eligible),
            "cohort_status": (
                "ready"
                if any(item["status"] == "ready" for item in metric_summaries.values())
                else "insufficient_sample"
            ),
            "percentile_method": "midrank; ties share the middle rank",
            "metric_summaries": metric_summaries,
            "players": player_results,
            "interpretation_limits": [
                "Percentiles describe relative per-90 event frequency within this report's same-role cohort; they are not quality scores or player rankings.",
                "A higher percentile is not always better; interpretation depends on the metric and tactical context.",
                "Only players with complete data quality, consistent match reconciliation, consistent source identity and at least the minimum verified minutes enter a cohort.",
                "Each metric requires its own minimum number of available peer values; otherwise its percentile remains unavailable.",
                "The cohort is limited to this competition/season report and does not adjust for team style, possession, age, opposition strength or tactical role.",
            ],
        }

    return {
        "benchmark_version": "peer-percentiles-v1",
        "minimum_verified_minutes": minimum_verified_minutes,
        "minimum_cohort_size": minimum_cohort_size,
        "comparison_scope": "same competition and season report; same role profile",
        "metric_guidance": {
            metric: BENCHMARK_METRIC_GUIDANCE[metric]
            for metric in sorted({
                name for names in ROLE_BENCHMARK_METRICS.values() for name in names
            })
        },
        "roles": benchmarks,
    }




def build_player_evaluation_readiness(
    role_profiles: dict[str, dict[str, Any]],
    role_benchmarks: dict[str, Any],
    minimum_verified_minutes: float = 450.0,
    minimum_appearances: int = 5,
) -> dict[str, Any]:
    """Describe whether a player record is ready for human scouting review."""
    if not _finite(minimum_verified_minutes) or float(minimum_verified_minutes) < 0:
        raise ValueError("minimum_verified_minutes negatif veya geçersiz olamaz.")
    if minimum_appearances < 1:
        raise ValueError("minimum_appearances en az 1 olmalı.")

    role_results = {}
    all_results = []
    for role_code in ROLE_BENCHMARK_METRICS:
        profile = role_profiles.get(role_code) or {}
        benchmark = (role_benchmarks.get("roles") or {}).get(role_code) or {}
        benchmark_players = {
            str(row.get("player_id")): row
            for row in benchmark.get("players", [])
        }
        results = []
        for player in profile.get("players") or []:
            player_id = str(player.get("player_id"))
            data_quality = (player.get("data_quality") or {}).get("status")
            consistency = (player.get("data_consistency") or {}).get("status")
            identity = player.get("identity") or {}
            identity_status = identity.get("status")
            metrics = player.get("metrics") or {}
            quality_checks = (player.get("data_quality") or {}).get("checks") or {}
            minutes = player.get("minutes_played")
            appearances = int(player.get("matches_with_appearance_evidence") or 0)
            has_attributed_events = (
                quality_checks.get("attributed_events") is True
                or int(metrics.get("events") or 0) > 0
            )
            reasons = []

            if not has_attributed_events:
                reasons.append("insufficient_event_evidence")
            elif data_quality != "complete":
                reasons.append("data_quality_not_complete")
            if appearances == 0:
                reasons.append("no_appearance_evidence")
            if consistency != "consistent":
                reasons.append("data_consistency_not_consistent")
            if identity_status != "consistent":
                reasons.append("identity_not_consistent")
            if identity.get("possible_same_name_collision") is True:
                reasons.append("possible_same_name_collision")
            if not _finite(minutes) or float(minutes) <= 0:
                reasons.append("verified_minutes_unavailable")
            elif float(minutes) < minimum_verified_minutes:
                reasons.append("below_minimum_verified_minutes")
            if appearances < minimum_appearances:
                reasons.append("insufficient_appearance_sample")

            benchmark_player = benchmark_players.get(player_id) or {}
            benchmark_metrics = benchmark_player.get("metrics") or {}
            ready_metrics = sorted(
                metric for metric, result in benchmark_metrics.items()
                if result.get("status") == "ready"
                and _finite(result.get("percentile"))
            )
            available_metrics = sorted(
                metric for metric, result in benchmark_metrics.items()
                if _finite(result.get("value_per90"))
            )

            if reasons:
                status = (
                    "insufficient_data"
                    if "insufficient_event_evidence" in reasons
                    and not has_attributed_events
                    else "limited"
                )
            else:
                status = "ready_for_scout_review"

            if not benchmark_player.get("eligible_for_peer_comparison", False):
                peer_context_status = "not_eligible"
            elif ready_metrics:
                peer_context_status = "available"
            else:
                peer_context_status = "insufficient_sample"

            result = {
                "player_id": player.get("player_id"),
                "player_name": player.get("player_name"),
                "role_code": role_code,
                "readiness_status": status,
                "reason_codes": sorted(set(reasons)),
                "checks": {
                    "data_quality_status": data_quality,
                    "data_consistency_status": consistency,
                    "identity_status": identity_status,
                    "possible_same_name_collision": bool(
                        identity.get("possible_same_name_collision")
                    ),
                    "verified_minutes": (
                        round(float(minutes), 2) if _finite(minutes) else None
                    ),
                    "minimum_verified_minutes": minimum_verified_minutes,
                    "appearance_matches": appearances,
                    "minimum_appearances": minimum_appearances,
                    "attributed_events_available": has_attributed_events,
                },
                "peer_context_status": peer_context_status,
                "peer_metrics_available": available_metrics,
                "peer_percentiles_available": ready_metrics,
            }
            results.append(result)
            all_results.append(result)

        role_results[role_code] = {
            "role_name": profile.get("role_name"),
            "player_count": len(results),
            "readiness_counts": {
                status: sum(row["readiness_status"] == status for row in results)
                for status in ("ready_for_scout_review", "limited", "insufficient_data")
            },
            "players": results,
        }

    return {
        "readiness_version": "scout-review-readiness-v1",
        "purpose": "Data sufficiency and reliability gate before human scouting review; not a player rating.",
        "minimum_verified_minutes": minimum_verified_minutes,
        "minimum_appearances": minimum_appearances,
        "roles": role_results,
        "summary": {
            "player_role_records": len(all_results),
            "ready_for_scout_review": sum(
                row["readiness_status"] == "ready_for_scout_review" for row in all_results
            ),
            "limited": sum(row["readiness_status"] == "limited" for row in all_results),
            "insufficient_data": sum(
                row["readiness_status"] == "insufficient_data" for row in all_results
            ),
        },
        "interpretation_limits": [
            "Ready means the selected data passes technical sample and quality gates; it does not mean that the player is good or recommended.",
            "This first version uses minimum verified minutes and appearance count as simple sample gates; it does not yet adjust for age, competition strength, position-specific opportunity or match context.",
            "Peer percentiles are contextual only and remain unavailable when metric cohorts are too small.",
            "Video review and human scouting judgement are still required for tactical, technical and behavioural evaluation.",
        ],
    }



def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="StatsBomb Open Data için küçük Vel Scout import/kalite prototipi."
    )
    parser.add_argument("--competition-id", type=int, default=43)
    parser.add_argument("--season-id", type=int, default=106)
    parser.add_argument(
        "--match-id", type=int, action="append",
        help="Belirli maç ID'si; tekrarlanabilir. Verilmezse --limit kadar maç seçilir.",
    )
    parser.add_argument("--limit", type=int, default=1)
    parser.add_argument(
        "--compare-report", action="append", default=[],
        help="Aynı turnuvanın önceki sezon rapor yolu; birden fazla kez verilebilir.",
    )
    parser.add_argument(
        "--data-root", default=".cache/statsbomb-open-data/raw",
        help="Ham JSON cache dizini (varsayılan .cache altında).",
    )
    parser.add_argument(
        "--report", default=".cache/statsbomb-open-data/reports/import-report.json",
        help="JSON kalite/oyuncu raporu çıktı yolu.",
    )
    parser.add_argument("--force", action="store_true", help="Cache yerine kaynağı yeniden indir.")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        report = run_import(args)
        comparison_paths = getattr(args, "compare_report", []) or []
        if comparison_paths:
            comparison_reports = []
            current_report_path = Path(report["output_files"]["json"]).resolve()
            for comparison_path in comparison_paths:
                path = Path(comparison_path)
                if path.resolve() == current_report_path:
                    raise ValueError(
                        "--compare-report mevcut raporun çıktı yoluyla aynı olamaz."
                    )
                try:
                    comparison_reports.append(
                        json.loads(path.read_text(encoding="utf-8"))
                    )
                except (OSError, json.JSONDecodeError) as exc:
                    raise ValueError(
                        f"Karşılaştırma raporu okunamadı: {path}: {exc}"
                    ) from exc
            comparison_reports.append(report)
            report["season_comparison"] = build_player_season_comparison(
                comparison_reports
            )
            current_report_path.write_text(
                json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
            )
    except (ImportErrorWithContext, ValueError) as exc:
        print(f"HATA: {exc}")
        return 2
    print("StatsBomb import tamamlandı.")
    print(f"Turnuva: {report['competition_season']['competition_name']} "
          f"{report['competition_season']['season_name']}")
    print(f"Maç: {report['sample']['selected_match_count']}")
    print(f"Olay: {report['sample']['event_count']}")
    print(f"Oyuncu: {report['sample']['unique_players_listed_or_seen']}")
    print(f"Rapor: {report['output_files']['json']}")
    print(f"Oyuncu CSV: {report['output_files']['players_csv']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
