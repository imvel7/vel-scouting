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
}

COUNTER_FIELDS = (
    "events", "passes_attempted", "passes_completed", "crosses",
    "through_balls", "assists", "shot_assists", "carries", "shots",
    "goals", "pressures", "interceptions", "ball_recoveries",
    "clearances", "blocks", "tackles", "dribbles",
)


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

def analyse_match(match: dict[str, Any], lineups: Any,
                  events: Any) -> dict[str, Any]:
    """Build a cautious single-match player event summary."""
    if not isinstance(events, list):
        raise ImportErrorWithContext("Events dosyasının kökü JSON dizisi değil.")

    players, warnings = _lineup_players(lineups)
    minutes_result = calculate_minutes_played(events)
    counters: dict[str, Counter[str]] = defaultdict(Counter)
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
        elif event_type == "Carry":
            row["carries"] += 1
        elif event_type == "Shot":
            shot = event.get("shot") or {}
            row["shots"] += 1
            if _name(shot.get("outcome")) == "Goal":
                row["goals"] += 1
            if _finite(shot.get("statsbomb_xg")):
                xg_values[player_key].append(float(shot["statsbomb_xg"]))
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
        player_rows.append({
            **player,
            "metrics": metrics,
            "pass_length_sum": round(sum(lengths), 3),
            "pass_length_observations": len(lengths),
            "minutes_played": round(player_seconds / 60.0, 2) if player_seconds is not None else None,
            "minutes_played_seconds": round(player_seconds, 3) if player_seconds is not None else None,
            "per90_metrics": None,
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
        centre_backs.append({
            "player_id": player.get("player_id"),
            "player_name": player.get("player_name"),
            "team_names": player.get("team_names") or [],
            "positions_seen": positions,
            "matches_listed_in_squads": player.get("matches_listed_in_squads", 0),
            "matches_with_appearance_evidence": player.get("matches_with_appearance_evidence", 0),
            "minutes_played": player.get("minutes_played"),
            "metrics": {key: metrics.get(key) for key in CB_PROFILE_METRICS},
        })

    centre_backs.sort(key=lambda row: row["player_name"].casefold())
    return {
        "role_code": "CB",
        "role_name": "Centre-back",
        "metric_mode": "raw_event_counts_and_source_percentages",
        "player_count": len(centre_backs),
        "players": centre_backs,
        "interpretation_limits": [
            "No defensive rating or ranking is calculated.",
            "Raw defensive-action counts are not adjusted for minutes, team possession, defensive opportunities, match state or opponent quality.",
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
            })
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
        aggregate_rows.append({
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
            "per90_metrics": None,
            "metrics": counts,
        })
    aggregate_rows.sort(key=lambda row: row["player_name"].casefold())

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
            "event_players_missing_from_lineups": sum(
                row["quality"]["event_player_not_in_lineup_count"] for row in analysed_matches
            ),
        },
        "metric_definitions": METRIC_DEFINITIONS,
        "limitations": [
            "Minutes are calculated from Starting XI, substitutions, Player Off/On, dismissal events and period-local timestamps. If period clocks or required state transitions are incomplete, minutes remain null; per-90 metrics are still deliberately disabled pending real-match validation.",
            "Lineup/squad listings can include unused substitutes; unused substitutes receive 0.00 minutes only when the match-level event clock passes validation.",
            "Percentiles and peer rankings are not produced by this single-source ingestion proof.",
            "Event data cannot establish off-ball positioning, scanning, body orientation, communication or visual tactical behaviour.",
            "This is a selected research dataset, not complete coverage of all leagues, seasons or youth players.",
            "The report is not a definitive scout verdict, potential rating or transfer recommendation.",
        ],
        "source_files": provenance,
        "matches": analysed_matches,
        "player_sample_totals": aggregate_rows,
        "role_profiles": {
            "CB": build_cb_profile(aggregate_rows),
        },
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
            *COUNTER_FIELDS, "pass_completion_pct", "pass_length_mean", "xg",
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
                **row["metrics"],
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
