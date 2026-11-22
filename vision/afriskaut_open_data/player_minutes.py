"""Conservative player-minutes calculation for Afriskaut match data.

Minutes are produced only when the match clock, the squad lists, the listed substitutions and the
SUBSTITUTION events agree. Anything that cannot be reconciled stays ``None`` with an explicit reason;
no value is guessed, defaulted to 90 or filled with zero.

Time model: ``event_start_time`` and the four match clock fields share one HH:MM:SS timeline. Played
time excludes the half-time break, so a clock time is mapped to elapsed play seconds with
``played_seconds``. Extra time and penalties are not handled (those fields are empty in the dataset);
a match with unusable clocks yields no minutes at all.

Known limit: the event feed has no card events, so a player who left the pitch without a listed
substitution (red card, injury without replacement) cannot be detected. Starters with no recorded exit
are therefore labelled ``derived_no_exit_recorded`` and are never labelled ``verified``.
"""

from __future__ import annotations

from collections import Counter, defaultdict

from diagnose_minutes_feasibility import SUB_LIST_FIELDS, match_clock, parse_hms

TOLERANCE_SECONDS = 10
STATUS_VERIFIED = "verified"
STATUS_DERIVED = "derived_no_exit_recorded"
STATUS_NOT_USED = "not_used_listed_bench"
STATUS_UNAVAILABLE = "unavailable"


def played_seconds(seconds: int | None, clock: dict) -> int | None:
    """Map a clock time to elapsed play seconds (break excluded); None when outside the match."""
    if seconds is None or not clock.get("ordered"):
        return None
    start, first_end = clock["match_start_time"], clock["first_half_end_time"]
    second_start, end = clock["second_half_start_time"], clock["match_end_time"]
    if seconds < start or seconds > end:
        return None
    if seconds <= first_end:
        return seconds - start
    if seconds < second_start:
        return first_end - start
    return (first_end - start) + (seconds - second_start)


def _player_id(entry) -> str:
    if not isinstance(entry, dict):
        return ""
    value = entry.get("player_id")
    return str(value).strip() if value is not None else ""


def _ids(match: dict, fields: tuple[str, ...]) -> list[str]:
    found = []
    for field in fields:
        for entry in match.get(field) or []:
            pid = _player_id(entry)
            if pid:
                found.append(pid)
    return found


def _unavailable(*reasons: str) -> dict:
    return {"minutes_seconds": None, "status": STATUS_UNAVAILABLE, "basis": None,
            "reasons": list(reasons), "events_outside_interval": 0}


def compute_match_minutes(match: dict, events: list[dict], tolerance: int = TOLERANCE_SECONDS) -> dict:
    """Return ``{"total_played_seconds": int|None, "players": {player_id: record}}`` for one match."""
    clock = match_clock(match)
    sub_events: list[dict] = []
    other_events: dict[str, list[dict]] = defaultdict(list)
    for event in events:
        if str(event.get("event_type") or "").strip().upper() == "SUBSTITUTION":
            sub_events.append(event)
            continue
        pid = _player_id(event)
        if pid:
            other_events[pid].append(event)

    starters = _ids(match, ("home_team_line_up", "away_team_line_up"))
    bench = _ids(match, ("home_team_subs", "away_team_subs"))
    pairs: list[tuple[str, str]] = []
    incomplete_ids: set[str] = set()
    for field in SUB_LIST_FIELDS:
        for entry in match.get(field) or []:
            if not isinstance(entry, dict):
                continue
            in_id, out_id = _player_id(entry.get("in")), _player_id(entry.get("out"))
            if in_id and out_id:
                pairs.append((in_id, out_id))
            else:
                incomplete_ids.update(i for i in (in_id, out_id) if i)

    sub_actor_times: dict[str, set] = defaultdict(set)
    for event in sub_events:
        pid = _player_id(event)
        if pid:
            sub_actor_times[pid].add(parse_hms(event.get("event_start_time")))

    everyone = set(starters) | set(bench) | set(other_events) | set(sub_actor_times) | incomplete_ids
    for in_id, out_id in pairs:
        everyone.update((in_id, out_id))

    if not clock["ordered"]:
        return {"total_played_seconds": None,
                "players": {pid: _unavailable("match_clock_unusable") for pid in sorted(everyone)}}

    total = (clock["first_half_end_time"] - clock["match_start_time"]) + (
        clock["match_end_time"] - clock["second_half_start_time"])

    pair_count: Counter = Counter()
    for in_id, out_id in pairs:
        pair_count[in_id] += 1
        pair_count[out_id] += 1
    in_count = Counter(in_id for in_id, _ in pairs)
    out_count = Counter(out_id for _, out_id in pairs)
    duplicate_starters = {pid for pid, n in Counter(starters).items() if n > 1}
    ambiguous = (incomplete_ids | duplicate_starters | {pid for pid, n in pair_count.items() if n > 1}
                 | (set(starters) & set(bench)))
    paired_ids = set(pair_count)

    # Resolve each listed substitution to one play-second, only when a single time is evidenced.
    resolved: dict[tuple[str, str], int] = {}
    failed: dict[tuple[str, str], str] = {}
    for pair in pairs:
        in_id, out_id = pair
        if in_id in ambiguous or out_id in ambiguous:
            failed[pair] = "ambiguous_squad_or_substitution_records"
            continue
        times = sub_actor_times.get(in_id, set()) | sub_actor_times.get(out_id, set())
        if not times:
            failed[pair] = "no_substitution_event_for_listed_substitution"
        elif None in times:
            failed[pair] = "substitution_event_time_unparseable"
        elif len(times) > 1:
            failed[pair] = "conflicting_substitution_event_times"
        else:
            seconds = played_seconds(next(iter(times)), clock)
            if seconds is None:
                failed[pair] = "substitution_time_outside_match_clock"
            else:
                resolved[pair] = seconds
    pair_by_in = {p[0]: p for p in pairs}
    pair_by_out = {p[1]: p for p in pairs}
    unreconciled = {pid for pid in sub_actor_times if pid not in paired_ids}

    players: dict[str, dict] = {}
    for pid in sorted(everyone):
        record = _classify_player(pid, starters, bench, ambiguous, unreconciled, other_events,
                                  in_count, out_count, pair_by_in, pair_by_out, resolved, failed, total)
        interval = record.pop("_interval", None)
        if interval is not None:
            start, end = interval
            outside = 0
            for event in other_events.get(pid, []):
                seconds = played_seconds(parse_hms(event.get("event_start_time")), clock)
                if seconds is not None and not (start - tolerance <= seconds <= end + tolerance):
                    outside += 1
            if outside:
                record = _unavailable("events_outside_computed_interval")
                record["events_outside_interval"] = outside
        players[pid] = record
    return {"total_played_seconds": total, "players": players}


def _classify_player(pid, starters, bench, ambiguous, unreconciled, other_events,
                     in_count, out_count, pair_by_in, pair_by_out, resolved, failed, total) -> dict:
    is_starter, is_bench = pid in starters, pid in bench
    if pid in ambiguous:
        return _unavailable("ambiguous_squad_or_substitution_records")
    if pid in unreconciled:
        return _unavailable("substitution_event_not_in_listed_substitutions")
    if is_starter:
        if in_count[pid]:
            return _unavailable("starter_listed_as_substitute_in")
        if out_count[pid]:
            pair = pair_by_out[pid]
            if pair in failed:
                return _unavailable(failed[pair])
            end = resolved[pair]
            return {"minutes_seconds": end, "status": STATUS_VERIFIED, "basis": "starter_substituted_out",
                    "reasons": [], "events_outside_interval": 0, "_interval": (0, end)}
        return {"minutes_seconds": total, "status": STATUS_DERIVED, "basis": "starter_no_exit_recorded",
                "reasons": ["red_card_or_injury_without_substitution_not_detectable"],
                "events_outside_interval": 0, "_interval": (0, total)}
    if in_count[pid]:
        pair = pair_by_in[pid]
        if pair in failed:
            return _unavailable(failed[pair])
        start = resolved[pair]
        return {"minutes_seconds": total - start, "status": STATUS_VERIFIED, "basis": "substitute_entered",
                "reasons": [], "events_outside_interval": 0, "_interval": (start, total)}
    if out_count[pid]:
        return _unavailable("listed_substituted_out_without_starting")
    if is_bench:
        if other_events.get(pid):
            return _unavailable("events_without_listed_appearance")
        return {"minutes_seconds": 0, "status": STATUS_NOT_USED, "basis": "listed_bench_no_substitution",
                "reasons": [], "events_outside_interval": 0}
    return _unavailable("not_in_squad_lists")
