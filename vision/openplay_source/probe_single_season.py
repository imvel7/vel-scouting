#!/usr/bin/env python3
"""Run a small, non-publishing Openplay source probe for one senior league season.

The probe intentionally prints aggregate counts only. It does not print or
persist player names or player IDs, and it does not write to Supabase.
"""

from __future__ import annotations

import json
import math

import openplay as op


COMPETITION = "eng"
SEASON = "2425"
MINIMUM_MINUTES = 450
REQUIRED_LINEUP_COLUMNS = {
    "match_id", "player_id", "played", "minutes_played", "position", "age"
}
REQUIRED_PLAYER_MATCH_COLUMNS = {
    "match_id", "player_id", "minutes_played", "goals", "shots", "passes"
}


def build_report() -> dict:
    coverage = op.coverage_report(COMPETITION, SEASON, warn=False)
    lineups = op.lineups(COMPETITION, SEASON)
    player_matches = op.player_match_stats(COMPETITION, SEASON)
    season_rates = op.player_season_stats(
        COMPETITION,
        SEASON,
        per90=True,
        min_minutes=MINIMUM_MINUTES,
    )

    if len(coverage) != 1:
        raise AssertionError("Expected exactly one competition-season coverage row")
    missing_lineup_columns = REQUIRED_LINEUP_COLUMNS - set(lineups.columns)
    missing_player_columns = REQUIRED_PLAYER_MATCH_COLUMNS - set(player_matches.columns)
    if missing_lineup_columns:
        raise AssertionError(
            f"Openplay lineups table is missing required columns: {sorted(missing_lineup_columns)}"
        )
    if missing_player_columns:
        raise AssertionError(
            "Openplay player_match_stats table is missing required columns: "
            f"{sorted(missing_player_columns)}"
        )
    if lineups.empty or player_matches.empty:
        raise AssertionError("The selected competition-season returned no player data")

    played_lineups = lineups.loc[
        lineups["played"].fillna(False).astype(bool)
    ].copy()

    lineup_duplicate_keys = int(
        played_lineups.duplicated(["match_id", "player_id"]).sum()
    )
    player_match_duplicate_keys = int(
        player_matches.duplicated(["match_id", "player_id"]).sum()
    )
    if lineup_duplicate_keys or player_match_duplicate_keys:
        raise AssertionError(
            "Duplicate match/player keys detected: "
            f"lineups={lineup_duplicate_keys}, player_match_stats={player_match_duplicate_keys}"
        )

    linkage = player_matches[
        ["match_id", "player_id", "minutes_played"]
    ].merge(
        played_lineups[["match_id", "player_id", "minutes_played"]],
        on=["match_id", "player_id"],
        how="left",
        suffixes=("_stats", "_lineup"),
        indicator=True,
        validate="one_to_one",
    )
    matched = linkage["_merge"].eq("both")
    unmatched_rows = int((~matched).sum())
    minute_mismatches = int(
        (
            linkage.loc[matched, "minutes_played_stats"]
            != linkage.loc[matched, "minutes_played_lineup"]
        ).fillna(False).sum()
    )

    age_values = played_lineups["age"]
    youth_appearances = played_lineups.loc[
        age_values.between(16, 19, inclusive="both")
    ]
    rate_columns = ["goals", "shots", "passes", "xg"]
    missing_rate_columns = set(rate_columns) - set(season_rates.columns)
    if missing_rate_columns:
        raise AssertionError(
            f"Openplay per-90 output is missing columns: {sorted(missing_rate_columns)}"
        )
    finite_rate_rows = sum(
        all(math.isfinite(float(value)) for value in row)
        for row in season_rates[rate_columns].itertuples(index=False, name=None)
    )

    coverage_row = coverage.iloc[0]
    return {
        "source": "openplay (Noah Bair)",
        "release_tag": op.DATA_TAG,
        "competition": "Premier League",
        "competition_code": COMPETITION,
        "season": "2024/25",
        "coverage": {
            "matches_played": int(coverage_row["matches_played"]),
            "matches_with_events": int(coverage_row["matches_with_events"]),
            "coverage_pct": round(float(coverage_row["coverage_pct"]), 2),
            "known_gaps": int(coverage_row["gaps"]),
            "matches_with_data_issues": int(coverage_row["matches_with_data_issues"]),
        },
        "lineups": {
            "squad_rows": int(len(lineups)),
            "player_appearances": int(len(played_lineups)),
            "unique_players_with_appearance": int(played_lineups["player_id"].nunique()),
            "unique_players_aged_16_to_19": int(youth_appearances["player_id"].nunique()),
            "appearances_by_players_aged_16_to_19": int(len(youth_appearances)),
        },
        "player_match_stats": {
            "rows": int(len(player_matches)),
            "unique_players": int(player_matches["player_id"].nunique()),
            "rows_without_played_lineup_match": unmatched_rows,
            "minutes_mismatch_rows_when_linked": minute_mismatches,
        },
        "per90": {
            "players_with_at_least_450_minutes": int(len(season_rates)),
            "rows_with_finite_goals_shots_passes_xg_rates": int(finite_rate_rows),
        },
        "privacy": {
            "player_names_printed": False,
            "player_ids_printed": False,
            "raw_rows_saved": False,
            "supabase_written": False,
        },
        "scope_note": (
            "This is one senior men's league season. It tests the data adapter; "
            "it does not establish youth-competition coverage."
        ),
    }


def main() -> int:
    report = build_report()
    print(json.dumps(report, indent=2, sort_keys=True))
    print("Openplay single-season source probe passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
