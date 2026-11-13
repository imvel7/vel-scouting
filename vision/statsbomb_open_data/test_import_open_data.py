import csv
import json
import sys
import tempfile
import unittest
from argparse import Namespace
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
from import_open_data import calculate_player_score_state_minutes, calculate_score_state_durations, calculate_match_score_timeline, extract_match_context, analyse_match, build_cb_profile, build_goalkeeper_profile, build_central_midfield_profile, build_fullback_profile, build_winger_profile, build_striker_profile, build_role_benchmarks, BENCHMARK_METRIC_GUIDANCE, ROLE_BENCHMARK_METRICS, build_player_evaluation_readiness, build_player_season_comparison, calculate_minutes_played, calculate_per90_metrics, calculate_player_data_quality, calculate_player_data_consistency, calculate_player_identity, find_player_name_collisions, build_parser, fetch_json, run_import, main, ImportErrorWithContext


MATCH = {
    "match_id": 123,
    "match_date": "2022-12-18",
    "competition": {"competition_name": "FIFA World Cup"},
    "season": {"season_name": "2022"},
    "home_team": {"home_team_name": "Argentina"},
    "away_team": {"away_team_name": "France"},
    "home_score": 3,
    "away_score": 3,
}

LINEUPS = [
    {
        "team_id": 1,
        "team_name": "Argentina",
        "lineup": [{
            "player_id": 10,
            "player_name": "Example Player",
            "player_nickname": "Example",
            "jersey_number": 10,
            "positions": [{"position": "Center Attacking Midfield"}],
        }],
    }
]

EVENTS = [
    {
        "id": "1", "type": {"name": "Pass"},
        "player": {"id": 10, "name": "Example Player"},
        "team": {"id": 1, "name": "Argentina"},
        "pass": {"length": 15.0},
    },
    {
        "id": "2", "type": {"name": "Pass"},
        "player": {"id": 10, "name": "Example Player"},
        "team": {"id": 1, "name": "Argentina"},
        "pass": {"length": 20.0, "outcome": {"name": "Incomplete"}},
    },
    {
        "id": "3", "type": {"name": "Carry"},
        "player": {"id": 10, "name": "Example Player"},
        "team": {"id": 1, "name": "Argentina"},
        "carry": {"end_location": [50, 40]},
    },
    {
        "id": "4", "type": {"name": "Shot"},
        "player": {"id": 10, "name": "Example Player"},
        "team": {"id": 1, "name": "Argentina"},
        "shot": {
            "statsbomb_xg": 0.42,
            "outcome": {"name": "Goal"},
        },
    },
    {
        "id": "5", "type": {"name": "Pressure"},
        "player": {"id": 10, "name": "Example Player"},
        "team": {"id": 1, "name": "Argentina"},
    },
    {
        "id": "6", "type": {"name": "Half Start"},
        "team": {"id": 1, "name": "Argentina"},
    },
]


class StatsBombImportTests(unittest.TestCase):
    @staticmethod
    def _clock_event(index, period, timestamp, event_type, **extra):
        parts = timestamp.split(":")
        local_seconds = int(parts[0]) * 3600 + int(parts[1]) * 60 + float(parts[2])
        period_base_minutes = {1: 0, 2: 45, 3: 90, 4: 105, 5: 120}
        match_seconds = period_base_minutes[period] * 60 + int(local_seconds)
        return {
            "index": index,
            "period": period,
            "timestamp": timestamp,
            "minute": match_seconds // 60,
            "second": match_seconds % 60,
            "type": {"name": event_type},
            **extra,
        }

    @classmethod
    def _starting_xi(cls, index, team_id, player_ids):
        return cls._clock_event(
            index,
            1,
            "00:00:00.000",
            "Starting XI",
            team={"id": team_id, "name": f"Team {team_id}"},
            tactics={
                "lineup": [
                    {"player": {"id": player_id, "name": f"Player {player_id}"}}
                    for player_id in player_ids
                ]
            },
        )

    def test_minutes_follow_starting_xi_substitutions_and_period_local_clocks(self):
        events = [
            self._starting_xi(1, 1, [10, 11]),
            self._starting_xi(2, 2, [20]),
            self._clock_event(3, 1, "00:00:00.000", "Half Start"),
            self._clock_event(
                4, 1, "00:30:00.000", "Substitution",
                player={"id": 10, "name": "Player 10"},
                substitution={"replacement": {"id": 12, "name": "Player 12"}},
            ),
            self._clock_event(
                5, 1, "00:45:00.000", "Half End"
            ),
            self._clock_event(6, 2, "00:00:00.000", "Half Start"),
            self._clock_event(7, 2, "00:45:00.000", "Half End"),
        ]
        result = calculate_minutes_played(events)
        self.assertTrue(result["valid"], result["errors"])
        self.assertEqual(result["periods"], [1, 2])
        self.assertEqual(result["seconds_by_player"]["10"], 30 * 60)
        self.assertEqual(result["seconds_by_player"]["12"], 60 * 60)
        self.assertEqual(result["seconds_by_player"]["11"], 90 * 60)
        self.assertEqual(result["seconds_by_player"]["20"], 90 * 60)

    def test_minutes_exclude_temporary_player_off_interval(self):
        events = [
            self._starting_xi(1, 1, [10]),
            self._clock_event(2, 1, "00:00:00.000", "Half Start"),
            self._clock_event(
                3, 1, "00:30:00.000", "Player Off",
                player={"id": 10, "name": "Player 10"},
                player_off={"permanent": False},
            ),
            self._clock_event(
                4, 1, "00:31:00.000", "Player On",
                player={"id": 10, "name": "Player 10"},
            ),
            self._clock_event(5, 1, "00:45:00.000", "Half End"),
        ]
        result = calculate_minutes_played(events)
        self.assertTrue(result["valid"], result["errors"])
        self.assertEqual(result["seconds_by_player"]["10"], 44 * 60)

    def test_minutes_stop_at_permanent_player_off_or_red_card(self):
        events = [
            self._starting_xi(1, 1, [10, 11]),
            self._clock_event(2, 1, "00:00:00.000", "Half Start"),
            self._clock_event(
                3, 1, "00:10:00.000", "Player Off",
                player={"id": 10, "name": "Player 10"},
                player_off={"permanent": True},
            ),
            self._clock_event(
                4, 1, "00:20:00.000", "Bad Behaviour",
                player={"id": 11, "name": "Player 11"},
                bad_behaviour={"card": {"name": "Second Yellow"}},
            ),
            self._clock_event(5, 1, "00:45:00.000", "Half End"),
        ]
        result = calculate_minutes_played(events)
        self.assertTrue(result["valid"], result["errors"])
        self.assertEqual(result["seconds_by_player"]["10"], 10 * 60)
        self.assertEqual(result["seconds_by_player"]["11"], 20 * 60)

    def test_minutes_include_extra_time_but_exclude_penalty_shootout(self):
        events = [
            self._starting_xi(1, 1, [10]),
            self._clock_event(2, 1, "00:00:00.000", "Half Start"),
            self._clock_event(3, 1, "00:45:00.000", "Half End"),
            self._clock_event(4, 2, "00:00:00.000", "Half Start"),
            self._clock_event(5, 2, "00:45:00.000", "Half End"),
            self._clock_event(6, 3, "00:00:00.000", "Half Start"),
            self._clock_event(7, 3, "00:15:00.000", "Half End"),
            self._clock_event(8, 4, "00:00:00.000", "Half Start"),
            self._clock_event(9, 4, "00:15:00.000", "Half End"),
            self._clock_event(10, 5, "00:00:00.000", "Half Start"),
            self._clock_event(11, 5, "00:05:00.000", "Half End"),
        ]
        result = calculate_minutes_played(events)
        self.assertTrue(result["valid"], result["errors"])
        self.assertEqual(result["periods"], [1, 2, 3, 4])
        self.assertEqual(result["seconds_by_player"]["10"], 120 * 60)

    def test_linked_ball_receipt_clock_anomaly_does_not_reset_minutes(self):
        events = [
            self._starting_xi(1, 1, [10]),
            self._clock_event(2, 1, "00:00:00.000", "Half Start"),
            self._clock_event(
                3, 1, "00:01:00.000", "Pass",
                id="pass-1",
                player={"id": 10, "name": "Player 10"},
            ),
            self._clock_event(
                4, 1, "00:00:00.275", "Ball Receipt*",
                id="receipt-1",
                related_events=["pass-1"],
                player={"id": 10, "name": "Player 10"},
            ),
            self._clock_event(5, 1, "00:45:00.000", "Half End"),
        ]
        result = calculate_minutes_played(events)
        self.assertTrue(result["valid"], result["errors"])
        self.assertEqual(result["seconds_by_player"]["10"], 45 * 60)
        self.assertTrue(any("Linked Ball Receipt*" in warning for warning in result["warnings"]))

    def test_minutes_are_unavailable_when_a_period_end_is_missing(self):
        events = [
            self._starting_xi(1, 1, [10]),
            self._clock_event(2, 1, "00:00:00.000", "Half Start"),
            self._clock_event(3, 1, "00:20:00.000", "Pass"),
        ]
        result = calculate_minutes_played(events)
        self.assertFalse(result["valid"])
        self.assertEqual(result["seconds_by_player"], {})
        self.assertTrue(any("Half End" in error for error in result["errors"]))

    def test_extract_match_context_includes_source_metadata_and_scoreline_result(self):
        match = {
            **MATCH,
            "kick_off": "17:00:00.000",
            "competition_stage": {"id": 26, "name": "Final"},
            "match_week": 7,
            "match_status": "available",
            "stadium": {"id": 1001114, "name": "Lusail Stadium"},
            "referee": {"id": 367, "name": "Szymon Marciniak"},
            "home_team": {
                **MATCH["home_team"],
                "home_team_group": None,
            },
            "away_team": {
                **MATCH["away_team"],
                "away_team_group": None,
            },
        }
        context = extract_match_context(match)
        self.assertEqual(context["kick_off"], "17:00:00.000")
        self.assertEqual(context["competition_stage"], "Final")
        self.assertEqual(context["match_week"], 7)
        self.assertEqual(context["match_status"], "available")
        self.assertEqual(context["stadium"], "Lusail Stadium")
        self.assertEqual(context["referee"], "Szymon Marciniak")
        self.assertEqual(context["scoreline_status"], "complete")
        self.assertEqual(context["listed_result"], "draw")
        self.assertEqual(context["home_goal_difference"], 0)
        self.assertTrue(context["source_field_availability"]["scoreline"])
        self.assertIn("event-time score state", context["interpretation_limit"])

        report = analyse_match(match, LINEUPS, EVENTS)
        self.assertEqual(
            report["match"]["match_context"]["listed_result"],
            "draw",
        )

    def test_extract_match_context_derives_home_and_away_results(self):
        home_win = extract_match_context({**MATCH, "home_score": 2, "away_score": 1})
        away_win = extract_match_context({**MATCH, "home_score": 0, "away_score": 3})
        self.assertEqual(home_win["listed_result"], "home_win")
        self.assertEqual(home_win["home_goal_difference"], 1)
        self.assertEqual(away_win["listed_result"], "away_win")
        self.assertEqual(away_win["home_goal_difference"], -3)

    def test_extract_match_context_does_not_guess_incomplete_or_invalid_scores(self):
        partial = extract_match_context({**MATCH, "home_score": 1, "away_score": None})
        invalid = extract_match_context({**MATCH, "home_score": True, "away_score": -1})
        fractional = extract_match_context({**MATCH, "home_score": 1.5, "away_score": 0})
        missing_metadata = extract_match_context({"match_id": 456})

        self.assertEqual(partial["scoreline_status"], "partial")
        self.assertIsNone(partial["listed_result"])
        self.assertIsNone(partial["home_goal_difference"])
        self.assertEqual(invalid["scoreline_status"], "unavailable")
        self.assertIsNone(invalid["listed_result"])
        self.assertEqual(fractional["scoreline_status"], "partial")
        self.assertEqual(missing_metadata["scoreline_status"], "unavailable")
        self.assertIsNone(missing_metadata["competition_stage"])
        self.assertFalse(missing_metadata["source_field_availability"]["stadium"])
        self.assertFalse(missing_metadata["source_field_availability"]["scoreline"])

    def test_score_timeline_reconstructs_goals_and_excludes_penalty_shootout(self):
        match = {
            **MATCH,
            "home_team": {
                **MATCH["home_team"],
                "home_team_id": 1,
            },
            "away_team": {
                **MATCH["away_team"],
                "away_team_id": 2,
            },
            "home_score": 2,
            "away_score": 1,
        }
        events = [
            {
                "period": 1, "index": 2, "timestamp": "00:12:00.000",
                "type": {"name": "Shot"},
                "shot": {"outcome": {"name": "Goal"}},
                "team": {"id": 1, "name": "Argentina"},
            },
            {
                "period": 1, "index": 3, "timestamp": "00:12:01.000",
                "type": {"name": "Own Goal Against"},
                "team": {"id": 2, "name": "France"},
            },
            {
                "period": 1, "index": 4, "timestamp": "00:12:01.000",
                "type": {"name": "Own Goal For"},
                "team": {"id": 1, "name": "Argentina"},
            },
            {
                "period": 2, "index": 1, "timestamp": "00:05:00.000",
                "type": {"name": "Shot"},
                "shot": {"outcome": {"name": "Goal"}},
                "team": {"id": 2, "name": "France"},
            },
            {
                "period": 5, "index": 1, "timestamp": "00:01:00.000",
                "type": {"name": "Shot"},
                "shot": {"outcome": {"name": "Goal"}},
                "team": {"id": 2, "name": "France"},
            },
        ]

        result = calculate_match_score_timeline(match, events)

        self.assertEqual(result["status"], "validated")
        self.assertTrue(result["score_reconciled"])
        self.assertEqual(result["goal_count"], 3)
        self.assertEqual(result["reconstructed_score"], {"home": 2, "away": 1})
        self.assertEqual(
            [goal["goal_type"] for goal in result["goals"]],
            ["shot_goal", "own_goal_for", "shot_goal"],
        )
        self.assertEqual(
            [(goal["period"], goal["event_index"]) for goal in result["goals"]],
            [(1, 2), (1, 4), (2, 1)],
        )
        self.assertEqual(
            [(goal["home_state_after"], goal["away_state_after"]) for goal in result["goals"]],
            [("leading", "trailing"), ("leading", "trailing"), ("leading", "trailing")],
        )

    def test_score_timeline_marks_final_score_reconciliation_mismatch(self):
        match = {
            **MATCH,
            "home_team": {**MATCH["home_team"], "home_team_id": 1},
            "away_team": {**MATCH["away_team"], "away_team_id": 2},
            "home_score": 0,
            "away_score": 0,
        }
        events = [{
            "period": 1, "index": 1, "timestamp": "00:10:00.000",
            "type": {"name": "Shot"},
            "shot": {"outcome": {"name": "Goal"}},
            "team": {"id": 1, "name": "Argentina"},
        }]
        result = calculate_match_score_timeline(match, events)
        self.assertEqual(result["status"], "reconciliation_mismatch")
        self.assertFalse(result["score_reconciled"])
        self.assertEqual(
            result["reason_codes"],
            ["reconstructed_score_does_not_match_listed_final_score"],
        )
        self.assertEqual(result["reconstructed_score"], {"home": 1, "away": 0})

    def test_score_timeline_fails_closed_on_missing_or_duplicate_event_order(self):
        match = {
            **MATCH,
            "home_team": {**MATCH["home_team"], "home_team_id": 1},
            "away_team": {**MATCH["away_team"], "away_team_id": 2},
        }
        missing = calculate_match_score_timeline(
            match,
            [{"period": 1, "timestamp": "00:10:00.000"}],
        )
        duplicate = calculate_match_score_timeline(
            match,
            [
                {"period": 1, "index": 1, "timestamp": "00:10:00.000"},
                {"period": 1, "index": 1, "timestamp": "00:11:00.000"},
            ],
        )
        unknown_team = calculate_match_score_timeline(
            match,
            [{
                "period": 1, "index": 1, "timestamp": "00:10:00.000",
                "type": {"name": "Shot"},
                "shot": {"outcome": {"name": "Goal"}},
                "team": {"id": 99, "name": "Unknown"},
            }],
        )
        self.assertEqual(missing["status"], "unavailable")
        self.assertIn("event_order_fields_unavailable_or_invalid", missing["reason_codes"])
        self.assertEqual(duplicate["status"], "unavailable")
        self.assertIn("duplicate_period_event_index", duplicate["reason_codes"])
        self.assertEqual(unknown_team["status"], "unavailable")
        self.assertIn("goal_team_id_unavailable_or_unknown", unknown_team["reason_codes"])

    def test_score_timeline_is_not_claimed_when_final_score_is_missing(self):
        match = {
            **MATCH,
            "home_team": {**MATCH["home_team"], "home_team_id": 1},
            "away_team": {**MATCH["away_team"], "away_team_id": 2},
            "home_score": None,
        }
        result = calculate_match_score_timeline(match, [])
        self.assertEqual(result["status"], "unavailable")
        self.assertIn("listed_final_score_unavailable_or_invalid", result["reason_codes"])

    def test_analyse_match_exposes_unavailable_timeline_when_event_order_is_missing(self):
        report = analyse_match(MATCH, LINEUPS, EVENTS)
        timeline = report["match"]["match_context"]["score_state_timeline"]
        self.assertEqual(timeline["status"], "unavailable")
        self.assertIn("match_team_ids_unavailable_or_ambiguous", timeline["reason_codes"])

    def test_player_score_state_minutes_follow_substitution_temporary_off_and_red_card(self):
        match = {
            **MATCH,
            "home_team": {"home_team_id": 1, "home_team_name": "Home"},
            "away_team": {"away_team_id": 2, "away_team_name": "Away"},
            "home_score": 1,
            "away_score": 1,
        }
        events = [
            self._starting_xi(1, 1, [10, 11]),
            self._starting_xi(2, 2, [20]),
            self._clock_event(3, 1, "00:00:00.000", "Half Start"),
            self._clock_event(
                4, 1, "00:10:00.000", "Shot",
                player={"id": 10, "name": "Player 10"},
                team={"id": 1, "name": "Home"},
                shot={"outcome": {"name": "Goal"}},
                timestamp="00:10:00.000",
            ),
            self._clock_event(
                5, 1, "00:30:00.000", "Substitution",
                player={"id": 10, "name": "Player 10"},
                team={"id": 1, "name": "Home"},
                substitution={"replacement": {"id": 12, "name": "Player 12"}},
            ),
            self._clock_event(
                6, 1, "00:35:00.000", "Player Off",
                player={"id": 11, "name": "Player 11"},
                team={"id": 1, "name": "Home"},
                player_off={"permanent": False},
            ),
            self._clock_event(
                7, 1, "00:36:00.000", "Player On",
                player={"id": 11, "name": "Player 11"},
                team={"id": 1, "name": "Home"},
            ),
            self._clock_event(
                8, 1, "00:40:00.000", "Bad Behaviour",
                player={"id": 12, "name": "Player 12"},
                team={"id": 1, "name": "Home"},
                bad_behaviour={"card": {"name": "Second Yellow"}},
            ),
            self._clock_event(9, 1, "00:45:00.000", "Half End"),
            self._clock_event(10, 2, "00:00:00.000", "Half Start"),
            self._clock_event(
                11, 2, "00:20:00.000", "Shot",
                player={"id": 20, "name": "Player 20"},
                team={"id": 2, "name": "Away"},
                shot={"outcome": {"name": "Goal"}},
                timestamp="00:20:00.000",
            ),
            self._clock_event(12, 2, "00:45:00.000", "Half End"),
        ]

        timeline = calculate_match_score_timeline(match, events)
        timeline["durations"] = calculate_score_state_durations(match, events, timeline)
        minutes = calculate_minutes_played(events)
        result = calculate_player_score_state_minutes(match, events, timeline, minutes)

        self.assertEqual(timeline["status"], "validated")
        self.assertEqual(timeline["durations"]["status"], "validated")
        self.assertTrue(minutes["valid"], minutes["errors"])
        self.assertEqual(result["status"], "validated", result["reason_codes"])
        self.assertEqual(
            result["seconds_by_player"]["10"],
            {"leading": 20 * 60, "drawing": 10 * 60, "trailing": 0.0},
        )
        self.assertEqual(
            result["seconds_by_player"]["12"],
            {"leading": 10 * 60, "drawing": 0.0, "trailing": 0.0},
        )
        self.assertEqual(
            result["seconds_by_player"]["11"],
            {"leading": 54 * 60, "drawing": 35 * 60, "trailing": 0.0},
        )
        self.assertEqual(
            result["seconds_by_player"]["20"],
            {"leading": 0.0, "drawing": 35 * 60, "trailing": 55 * 60},
        )
        for player_id, expected in minutes["seconds_by_player"].items():
            self.assertEqual(
                sum(result["seconds_by_player"][player_id].values()),
                expected,
            )

    def test_player_score_state_minutes_include_extra_time_but_exclude_shootout(self):
        match = {
            **MATCH,
            "home_team": {"home_team_id": 1, "home_team_name": "Home"},
            "away_team": {"away_team_id": 2, "away_team_name": "Away"},
            "home_score": 0,
            "away_score": 0,
        }
        events = [
            self._starting_xi(1, 1, [10]),
            self._starting_xi(2, 2, [20]),
            self._clock_event(3, 1, "00:00:00.000", "Half Start"),
            self._clock_event(4, 1, "00:45:00.000", "Half End"),
            self._clock_event(5, 2, "00:00:00.000", "Half Start"),
            self._clock_event(6, 2, "00:45:00.000", "Half End"),
            self._clock_event(7, 3, "00:00:00.000", "Half Start"),
            self._clock_event(8, 3, "00:15:00.000", "Half End"),
            self._clock_event(9, 4, "00:00:00.000", "Half Start"),
            self._clock_event(10, 4, "00:15:00.000", "Half End"),
            self._clock_event(11, 5, "00:00:00.000", "Half Start"),
            self._clock_event(12, 5, "00:05:00.000", "Half End"),
        ]
        timeline = calculate_match_score_timeline(match, events)
        timeline["durations"] = calculate_score_state_durations(match, events, timeline)
        minutes = calculate_minutes_played(events)
        result = calculate_player_score_state_minutes(match, events, timeline, minutes)

        self.assertTrue(minutes["valid"], minutes["errors"])
        self.assertEqual(timeline["durations"]["status"], "validated")
        self.assertEqual(result["status"], "validated", result["reason_codes"])
        self.assertEqual(
            result["seconds_by_player"]["10"],
            {"leading": 0.0, "drawing": 120 * 60, "trailing": 0.0},
        )
        self.assertEqual(
            result["seconds_by_player"]["20"],
            {"leading": 0.0, "drawing": 120 * 60, "trailing": 0.0},
        )

    def test_player_score_state_minutes_fail_closed_when_totals_do_not_reconcile(self):
        match = {
            **MATCH,
            "home_team": {"home_team_id": 1, "home_team_name": "Home"},
            "away_team": {"away_team_id": 2, "away_team_name": "Away"},
            "home_score": 0,
            "away_score": 0,
        }
        events = [
            self._starting_xi(1, 1, [10]),
            self._starting_xi(2, 2, [20]),
            self._clock_event(3, 1, "00:00:00.000", "Half Start"),
            self._clock_event(4, 1, "00:45:00.000", "Half End"),
        ]
        timeline = calculate_match_score_timeline(match, events)
        timeline["durations"] = calculate_score_state_durations(match, events, timeline)
        inconsistent_minutes = {
            "valid": True,
            "seconds_by_player": {"10": 44 * 60, "20": 45 * 60},
        }
        result = calculate_player_score_state_minutes(
            match, events, timeline, inconsistent_minutes
        )
        self.assertEqual(result["status"], "unavailable")
        self.assertEqual(
            result["reason_codes"],
            ["player_score_state_minutes_do_not_reconcile_with_total_minutes"],
        )

    def test_score_state_durations_partition_match_time_across_all_three_states(self):
        match = {
            **MATCH,
            "home_team": {
                **MATCH["home_team"],
                "home_team_id": 1,
            },
            "away_team": {
                **MATCH["away_team"],
                "away_team_id": 2,
            },
            "home_score": 2,
            "away_score": 2,
        }
        events = [
            self._starting_xi(1, 1, [10]),
            self._starting_xi(2, 2, [20]),
            self._clock_event(3, 1, "00:00:00.000", "Half Start"),
            self._clock_event(
                4, 1, "00:10:00.000", "Shot",
                player={"id": 10, "name": "Home Player"},
                team={"id": 1, "name": "Argentina"},
                shot={"outcome": {"name": "Goal"}},
            ),
            self._clock_event(
                5, 1, "00:20:00.000", "Shot",
                player={"id": 20, "name": "Away Player"},
                team={"id": 2, "name": "France"},
                shot={"outcome": {"name": "Goal"}},
            ),
            self._clock_event(
                6, 1, "00:30:00.000", "Shot",
                player={"id": 20, "name": "Away Player"},
                team={"id": 2, "name": "France"},
                shot={"outcome": {"name": "Goal"}},
            ),
            self._clock_event(7, 1, "00:45:00.000", "Half End"),
            self._clock_event(8, 2, "00:00:00.000", "Half Start"),
            self._clock_event(
                9, 2, "00:15:00.000", "Shot",
                player={"id": 10, "name": "Home Player"},
                team={"id": 1, "name": "Argentina"},
                shot={"outcome": {"name": "Goal"}},
            ),
            self._clock_event(10, 2, "00:45:00.000", "Half End"),
        ]

        timeline = calculate_match_score_timeline(match, events)
        durations = calculate_score_state_durations(match, events, timeline)

        self.assertEqual(timeline["status"], "validated")
        self.assertEqual(durations["status"], "validated")
        self.assertEqual(durations["total_seconds"], 90 * 60)
        self.assertEqual(durations["periods_included"], [1, 2])
        self.assertEqual(
            durations["home_team_seconds_by_state"],
            {"leading": 10 * 60, "drawing": 50 * 60, "trailing": 30 * 60},
        )
        self.assertEqual(
            durations["away_team_seconds_by_state"],
            {"leading": 30 * 60, "drawing": 50 * 60, "trailing": 10 * 60},
        )
        self.assertEqual(
            sum(durations["home_team_seconds_by_state"].values()),
            durations["total_seconds"],
        )
        self.assertEqual(
            sum(durations["away_team_seconds_by_state"].values()),
            durations["total_seconds"],
        )

    def test_score_state_durations_accept_paired_team_period_boundaries(self):
        match = {
            **MATCH,
            "home_team": {**MATCH["home_team"], "home_team_id": 1},
            "away_team": {**MATCH["away_team"], "away_team_id": 2},
            "home_score": 0,
            "away_score": 0,
        }
        events = [
            self._starting_xi(1, 1, [10]),
            self._starting_xi(2, 2, [20]),
            self._clock_event(3, 1, "00:00:00.000", "Half Start"),
            self._clock_event(4, 1, "00:00:00.000", "Half Start"),
            self._clock_event(5, 1, "00:45:00.000", "Half End"),
            self._clock_event(6, 1, "00:45:00.000", "Half End"),
            self._clock_event(7, 2, "00:00:00.000", "Half Start"),
            self._clock_event(8, 2, "00:00:00.000", "Half Start"),
            self._clock_event(9, 2, "00:45:00.000", "Half End"),
            self._clock_event(10, 2, "00:45:00.000", "Half End"),
        ]
        timeline = calculate_match_score_timeline(match, events)
        result = calculate_score_state_durations(match, events, timeline)
        self.assertEqual(result["status"], "validated")
        self.assertEqual(result["total_seconds"], 90 * 60)
        self.assertEqual(result["home_team_seconds_by_state"]["drawing"], 90 * 60)
        self.assertEqual(result["away_team_seconds_by_state"]["drawing"], 90 * 60)

    def test_score_state_durations_fail_closed_without_period_boundaries(self):
        match = {
            **MATCH,
            "home_team": {**MATCH["home_team"], "home_team_id": 1},
            "away_team": {**MATCH["away_team"], "away_team_id": 2},
            "home_score": 0,
            "away_score": 0,
        }
        events = [
            self._starting_xi(1, 1, [10]),
            self._starting_xi(2, 2, [20]),
            self._clock_event(3, 1, "00:00:00.000", "Half Start"),
            self._clock_event(4, 1, "00:45:00.000", "Half End"),
        ]
        timeline = calculate_match_score_timeline(match, events)
        missing_start = calculate_score_state_durations(
            match, [event for event in events if event["type"]["name"] != "Half Start"], timeline
        )
        self.assertEqual(missing_start["status"], "unavailable")
        self.assertIn(
            "period_start_or_end_boundary_ambiguous",
            missing_start["reason_codes"],
        )

    def test_score_state_durations_reject_unvalidated_score_timeline(self):
        match = {
            **MATCH,
            "home_team": {**MATCH["home_team"], "home_team_id": 1},
            "away_team": {**MATCH["away_team"], "away_team_id": 2},
            "home_score": 1,
            "away_score": 0,
        }
        events = [
            self._starting_xi(1, 1, [10]),
            self._starting_xi(2, 2, [20]),
            self._clock_event(3, 1, "00:00:00.000", "Half Start"),
            self._clock_event(
                4, 1, "00:10:00.000", "Shot",
                player={"id": 10, "name": "Home Player"},
                team={"id": 1, "name": "Argentina"},
                shot={"outcome": {"name": "Goal"}},
            ),
            self._clock_event(5, 1, "00:45:00.000", "Half End"),
        ]
        invalid_timeline = {
            "status": "reconciliation_mismatch",
            "goals": [],
        }
        result = calculate_score_state_durations(match, events, invalid_timeline)
        self.assertEqual(result["status"], "unavailable")
        self.assertEqual(
            result["reason_codes"],
            ["score_timeline_not_validated"],
        )

    def test_player_actions_are_classified_by_score_state_before_each_goal(self):
        match = {
            **MATCH,
            "home_team": {
                **MATCH["home_team"],
                "home_team_id": 1,
            },
            "away_team": {
                **MATCH["away_team"],
                "away_team_id": 2,
            },
            "home_score": 1,
            "away_score": 0,
        }
        lineups = [
            {
                "team_id": 1,
                "team_name": "Argentina",
                "lineup": [{
                    "player_id": 10,
                    "player_name": "Home Player",
                    "positions": [{"position": "Center Midfield"}],
                }],
            },
            {
                "team_id": 2,
                "team_name": "France",
                "lineup": [{
                    "player_id": 20,
                    "player_name": "Away Player",
                    "positions": [{"position": "Center Midfield"}],
                }],
            },
        ]
        events = [
            {
                "period": 1, "index": 1, "timestamp": "00:01:00.000",
                "type": {"name": "Pass"},
                "player": {"id": 10, "name": "Home Player"},
                "team": {"id": 1, "name": "Argentina"},
                "pass": {},
            },
            {
                "period": 1, "index": 2, "timestamp": "00:02:00.000",
                "type": {"name": "Pressure"},
                "player": {"id": 20, "name": "Away Player"},
                "team": {"id": 2, "name": "France"},
            },
            {
                "period": 1, "index": 3, "timestamp": "00:03:00.000",
                "type": {"name": "Shot"},
                "player": {"id": 10, "name": "Home Player"},
                "team": {"id": 1, "name": "Argentina"},
                "shot": {
                    "outcome": {"name": "Goal"},
                    "statsbomb_xg": 0.25,
                },
            },
            {
                "period": 1, "index": 4, "timestamp": "00:04:00.000",
                "type": {"name": "Carry"},
                "player": {"id": 10, "name": "Home Player"},
                "team": {"id": 1, "name": "Argentina"},
            },
            {
                "period": 1, "index": 5, "timestamp": "00:05:00.000",
                "type": {"name": "Pass"},
                "player": {"id": 10, "name": "Home Player"},
                "team": {"id": 1, "name": "Argentina"},
                "pass": {"outcome": {"name": "Incomplete"}},
            },
            {
                "period": 1, "index": 6, "timestamp": "00:06:00.000",
                "type": {"name": "Pressure"},
                "player": {"id": 20, "name": "Away Player"},
                "team": {"id": 2, "name": "France"},
            },
        ]

        report = analyse_match(match, lineups, events)
        home = next(row for row in report["player_metrics"] if row["player_id"] == 10)
        away = next(row for row in report["player_metrics"] if row["player_id"] == 20)
        home_state = home["score_state_analysis"]
        away_state = away["score_state_analysis"]

        self.assertEqual(report["match"]["match_context"]["score_state_timeline"]["status"], "validated")
        self.assertEqual(home_state["status"], "validated")
        self.assertEqual(home_state["classified_player_events"], 4)
        self.assertEqual(home_state["unclassified_player_events"], 0)
        self.assertEqual(home_state["metrics_by_state"]["drawing"]["events"], 2)
        self.assertEqual(home_state["metrics_by_state"]["drawing"]["passes_attempted"], 1)
        self.assertEqual(home_state["metrics_by_state"]["drawing"]["shots"], 1)
        self.assertEqual(home_state["metrics_by_state"]["drawing"]["goals"], 1)
        self.assertEqual(home_state["metrics_by_state"]["drawing"]["xg"], 0.25)
        self.assertEqual(home_state["metrics_by_state"]["leading"]["events"], 2)
        self.assertEqual(home_state["metrics_by_state"]["leading"]["carries"], 1)
        self.assertEqual(home_state["metrics_by_state"]["leading"]["passes_attempted"], 1)
        self.assertEqual(home_state["metrics_by_state"]["trailing"]["events"], 0)

        self.assertEqual(away_state["status"], "validated")
        self.assertEqual(away_state["metrics_by_state"]["drawing"]["pressures"], 1)
        self.assertEqual(away_state["metrics_by_state"]["trailing"]["pressures"], 1)
        self.assertEqual(away_state["metrics_by_state"]["drawing"]["events"], 1)
        self.assertEqual(away_state["metrics_by_state"]["trailing"]["events"], 1)

    def test_player_score_state_is_partial_when_event_team_cannot_be_mapped(self):
        match = {
            **MATCH,
            "home_team": {**MATCH["home_team"], "home_team_id": 1},
            "away_team": {**MATCH["away_team"], "away_team_id": 2},
            "home_score": 1,
            "away_score": 0,
        }
        lineups = [
            {
                "team_id": 1,
                "team_name": "Argentina",
                "lineup": [{
                    "player_id": 10,
                    "player_name": "Home Player",
                    "positions": [{"position": "Center Midfield"}],
                }],
            },
        ]
        events = [
            {
                "period": 1, "index": 1, "timestamp": "00:01:00.000",
                "type": {"name": "Pass"},
                "player": {"id": 10, "name": "Home Player"},
                "team": {"id": 1, "name": "Argentina"},
                "pass": {},
            },
            {
                "period": 1, "index": 2, "timestamp": "00:02:00.000",
                "type": {"name": "Pressure"},
                "player": {"id": 20, "name": "Unmapped Player"},
                "team": {"id": 99, "name": "Unknown Team"},
            },
            {
                "period": 1, "index": 3, "timestamp": "00:03:00.000",
                "type": {"name": "Shot"},
                "player": {"id": 10, "name": "Home Player"},
                "team": {"id": 1, "name": "Argentina"},
                "shot": {"outcome": {"name": "Goal"}},
            },
        ]
        report = analyse_match(match, lineups, events)
        unmapped = next(row for row in report["player_metrics"] if row["player_id"] == 20)
        analysis = unmapped["score_state_analysis"]
        self.assertEqual(report["match"]["match_context"]["score_state_timeline"]["status"], "validated")
        self.assertEqual(analysis["status"], "partial")
        self.assertEqual(analysis["classified_player_events"], 0)
        self.assertEqual(analysis["unclassified_player_events"], 1)
        self.assertEqual(analysis["metrics_by_state"]["drawing"]["events"], 0)

    def test_player_score_state_metrics_are_unavailable_when_timeline_is_not_validated(self):
        match = {
            **MATCH,
            "home_team": {**MATCH["home_team"], "home_team_id": 1},
            "away_team": {**MATCH["away_team"], "away_team_id": 2},
            "home_score": 1,
            "away_score": 0,
        }
        lineups = [{
            "team_id": 1,
            "team_name": "Argentina",
            "lineup": [{
                "player_id": 10,
                "player_name": "Home Player",
                "positions": [{"position": "Center Midfield"}],
            }],
        }]
        events = [{
            "period": 1, "index": 1, "timestamp": "00:01:00.000",
            "type": {"name": "Pass"},
            "player": {"id": 10, "name": "Home Player"},
            "team": {"id": 1, "name": "Argentina"},
            "pass": {},
        }]
        report = analyse_match(match, lineups, events)
        player = report["player_metrics"][0]
        self.assertEqual(
            report["match"]["match_context"]["score_state_timeline"]["status"],
            "reconciliation_mismatch",
        )
        self.assertEqual(player["score_state_analysis"]["status"], "unavailable")
        self.assertIsNone(player["score_state_analysis"]["metrics_by_state"])
        self.assertEqual(player["score_state_analysis"]["unclassified_player_events"], 1)

    def test_counts_events_and_pass_success_using_statsbomb_rule(self):
        report = analyse_match(MATCH, LINEUPS, EVENTS)
        player = report["player_metrics"][0]
        self.assertEqual(player["metrics"]["passes_attempted"], 2)
        self.assertEqual(player["metrics"]["passes_completed"], 1)
        self.assertEqual(player["metrics"]["pass_completion_pct"], 50.0)
        self.assertEqual(player["metrics"]["pass_length_mean"], 17.5)

    def test_counts_carry_shot_goal_xg_and_pressure(self):
        report = analyse_match(MATCH, LINEUPS, EVENTS)
        metrics = report["player_metrics"][0]["metrics"]
        self.assertEqual(metrics["carries"], 1)
        self.assertEqual(metrics["shots"], 1)
        self.assertEqual(metrics["goals"], 1)
        self.assertEqual(metrics["xg"], 0.42)
        self.assertEqual(metrics["pressures"], 1)

    def test_counts_goalkeeper_actions_and_goal_kicks_from_source_types(self):
        goalkeeper_events = [
            ("Shot Saved", None),
            ("Shot Faced", None),
            ("Goal Conceded", None),
            ("Collected", None),
            ("Punch", None),
            ("Keeper Sweeper", None),
            ("Smother", None),
            ("Penalty Saved to Post", None),
            ("Shot Saved Off Target", None),
            ("Penalty Conceded", None),
            ("New Source Type", None),
        ]
        events = list(EVENTS)
        for index, (action_type, _) in enumerate(goalkeeper_events, start=7):
            events.append({
                "id": str(index),
                "type": {"name": "Goal Keeper"},
                "player": {"id": 10, "name": "Example Player"},
                "team": {"id": 1, "name": "Argentina"},
                "goalkeeper": {"type": {"name": action_type}},
            })
        events.append({
            "id": "18",
            "type": {"name": "Pass"},
            "player": {"id": 10, "name": "Example Player"},
            "team": {"id": 1, "name": "Argentina"},
            "pass": {"type": {"name": "Goal Kick"}, "length": 55.0},
        })

        report = analyse_match(MATCH, LINEUPS, events)
        player = next(row for row in report["player_metrics"] if row["player_id"] == 10)
        metrics = player["metrics"]
        self.assertEqual(metrics["goalkeeper_actions"], 11)
        self.assertEqual(metrics["goalkeeper_saves"], 3)
        self.assertEqual(metrics["goalkeeper_shots_faced"], 1)
        self.assertEqual(metrics["goalkeeper_goals_conceded"], 1)
        self.assertEqual(metrics["goalkeeper_collections"], 1)
        self.assertEqual(metrics["goalkeeper_punches"], 1)
        self.assertEqual(metrics["goalkeeper_sweeps"], 1)
        self.assertEqual(metrics["goalkeeper_smotherings"], 1)
        self.assertEqual(metrics["goalkeeper_penalty_saves"], 1)
        self.assertEqual(metrics["goalkeeper_penalties_conceded"], 1)
        self.assertEqual(metrics["goalkeeper_unclassified_actions"], 1)
        self.assertEqual(metrics["goal_kicks"], 1)

    def test_player_data_quality_is_complete_when_core_checks_pass(self):
        quality = calculate_player_data_quality({
            "matches_with_appearance_evidence": 2,
            "minutes_calculation_complete": True,
            "minutes_played": 155.0,
            "per90_metrics": {"events": 90.0},
            "metrics": {"events": 155},
        })
        self.assertEqual(quality["status"], "complete")
        self.assertEqual(quality["reasons"], [])
        self.assertTrue(quality["checks"]["per90_available"])

    def test_player_data_quality_is_partial_when_minutes_are_incomplete(self):
        quality = calculate_player_data_quality({
            "matches_with_appearance_evidence": 2,
            "minutes_calculation_complete": False,
            "minutes_played": None,
            "per90_metrics": None,
            "metrics": {"events": 70},
        })
        self.assertEqual(quality["status"], "partial")
        self.assertIn("minutes_calculation_incomplete", quality["reasons"])
        self.assertFalse(quality["checks"]["per90_available"])

    def test_player_data_quality_is_insufficient_without_appearance_or_events(self):
        quality = calculate_player_data_quality({
            "matches_with_appearance_evidence": 0,
            "minutes_calculation_complete": True,
            "minutes_played": 0.0,
            "per90_metrics": None,
            "metrics": {"events": 0},
        })
        self.assertEqual(quality["status"], "insufficient")
        self.assertIn("no_appearance_evidence", quality["reasons"])
        self.assertIn("no_attributed_events", quality["reasons"])

    def test_player_identity_uses_source_id_when_names_match_across_matches(self):
        player = {"player_id": 10, "player_name": "Example Player"}
        match_rows = [
            {"player_id": 10, "player_name": "Example Player"},
            {"player_id": 10, "player_name": "Example Player"},
        ]
        identity = calculate_player_identity(player, match_rows)
        self.assertEqual(identity["key"], "statsbomb:10")
        self.assertEqual(identity["status"], "consistent")
        self.assertTrue(identity["checks"]["player_id_matches"])
        self.assertEqual(identity["name_variants"], ["Example Player"])

    def test_player_identity_flags_name_variants_without_merging_by_name(self):
        player = {"player_id": 10, "player_name": "Example Player"}
        match_rows = [
            {"player_id": 10, "player_name": "Example Player"},
            {"player_id": 10, "player_name": "Example P."},
        ]
        identity = calculate_player_identity(player, match_rows)
        self.assertEqual(identity["key"], "statsbomb:10")
        self.assertEqual(identity["status"], "review")
        self.assertIn("player_name_varies_for_same_id", identity["reasons"])
        self.assertEqual(len(identity["name_variants"]), 2)

    def test_player_identity_flags_mismatched_source_ids(self):
        player = {"player_id": 10, "player_name": "Example Player"}
        match_rows = [
            {"player_id": 10, "player_name": "Example Player"},
            {"player_id": 11, "player_name": "Example Player"},
        ]
        identity = calculate_player_identity(player, match_rows)
        self.assertEqual(identity["status"], "review")
        self.assertFalse(identity["checks"]["player_id_matches"])
        self.assertIn("player_id_mismatch_across_records", identity["reasons"])

    def test_name_collision_report_flags_same_name_with_different_ids(self):
        collisions = find_player_name_collisions([
            {
                "player_id": 10,
                "player_name": "Alex Smith",
                "team_names": ["Team A"],
                "matches_listed_in_squads": 2,
            },
            {
                "player_id": 22,
                "player_name": "Alex Smith",
                "team_names": ["Team B"],
                "matches_listed_in_squads": 1,
            },
        ])
        self.assertEqual(len(collisions), 1)
        self.assertEqual(collisions[0]["normalized_name"], "alex smith")
        self.assertEqual(collisions[0]["player_ids"], [10, 22])
        self.assertEqual(
            [row["identity_key"] for row in collisions[0]["players"]],
            ["statsbomb:10", "statsbomb:22"],
        )

    def test_name_collision_detection_normalizes_case_and_whitespace(self):
        collisions = find_player_name_collisions([
            {"player_id": 10, "player_name": "Alex   Smith"},
            {"player_id": 22, "player_name": " alex smith "},
        ])
        self.assertEqual(len(collisions), 1)
        self.assertEqual(collisions[0]["normalized_name"], "alex smith")

    def test_name_collision_detection_does_not_flag_one_id_or_unknown_names(self):
        collisions = find_player_name_collisions([
            {"player_id": 10, "player_name": "Alex Smith"},
            {"player_id": 10, "player_name": "Alex Smith"},
            {"player_id": 22, "player_name": "Unknown player 22"},
        ])
        self.assertEqual(collisions, [])

    def test_season_comparison_matches_same_source_player_across_seasons(self):
        reports = [
            {
                "competition_season": {
                    "competition_id": 43,
                    "competition_name": "FIFA World Cup",
                    "season_id": 106,
                    "season_name": "2022",
                },
                "sample": {"selected_match_count": 3},
                "player_sample_totals": [{
                    "player_id": 10,
                    "player_name": "Example Player",
                    "positions_seen": ["Center Back"],
                    "matches_listed_in_squads": 3,
                    "matches_with_appearance_evidence": 3,
                    "minutes_played": 270.0,
                    "per90_metrics": {"events": 80.0, "passes_attempted": 40.0, "xg": 0.2},
                    "data_quality": {"status": "complete"},
                    "data_consistency": {"status": "consistent"},
                    "identity": {"status": "consistent"},
                }],
            },
            {
                "competition_season": {
                    "competition_id": 43,
                    "competition_name": "FIFA World Cup",
                    "season_id": 107,
                    "season_name": "2023",
                },
                "sample": {"selected_match_count": 4},
                "player_sample_totals": [{
                    "player_id": 10,
                    "player_name": "Example Player",
                    "positions_seen": ["Defensive Midfield"],
                    "matches_listed_in_squads": 4,
                    "matches_with_appearance_evidence": 4,
                    "minutes_played": 360.0,
                    "per90_metrics": {"events": 90.0, "passes_attempted": 45.0, "xg": 0.3},
                    "data_quality": {"status": "complete"},
                    "data_consistency": {"status": "consistent"},
                    "identity": {"status": "consistent"},
                }],
            },
        ]
        comparison = build_player_season_comparison(reports)
        self.assertEqual(comparison["season_count"], 2)
        self.assertEqual(comparison["player_count"], 1)
        player = comparison["players"][0]
        self.assertEqual(player["identity_key"], "statsbomb:10")
        self.assertEqual(player["seasons"][0]["player_name"], "Example Player")
        self.assertEqual(player["seasons"][1]["player_name"], "Example Player")
        self.assertEqual(player["seasons"][1]["previous_season"], "2022")
        self.assertEqual(
            player["seasons"][1]["position_comparison_from_previous"]["status"],
            "changed",
        )
        self.assertEqual(
            player["seasons"][1]["position_comparison_from_previous"]["shared_positions"],
            [],
        )
        self.assertEqual(player["seasons"][1]["per90_change_from_previous"]["events"], 10.0)
        self.assertEqual(player["seasons"][1]["per90_change_from_previous"]["xg"], 0.1)

    def test_season_comparison_marks_same_positions_when_labels_match(self):
        reports = [
            {
                "competition_season": {"competition_id": 43, "season_id": 106, "season_name": "2022"},
                "sample": {"selected_match_count": 1},
                "player_sample_totals": [{"player_id": 10, "player_name": "Player", "positions_seen": ["Center Back"]}],
            },
            {
                "competition_season": {"competition_id": 43, "season_id": 107, "season_name": "2023"},
                "sample": {"selected_match_count": 1},
                "player_sample_totals": [{"player_id": 10, "player_name": "Player", "positions_seen": ["Center Back"]}],
            },
        ]
        comparison = build_player_season_comparison(reports)
        role = comparison["players"][0]["seasons"][1]["position_comparison_from_previous"]
        self.assertEqual(role["status"], "same")
        self.assertEqual(role["shared_positions"], ["center back"])

    def test_season_comparison_preserves_shared_position_label_and_summary(self):
        reports = [
            {
                "competition_season": {"competition_id": 43, "season_id": 106, "season_name": "2022"},
                "sample": {"selected_match_count": 1},
                "player_sample_totals": [{
                    "player_id": 10,
                    "player_name": "Player",
                    "positions_seen": ["Center Back", "Defensive Midfield"],
                }],
            },
            {
                "competition_season": {"competition_id": 43, "season_id": 107, "season_name": "2023"},
                "sample": {"selected_match_count": 1},
                "player_sample_totals": [{
                    "player_id": 10,
                    "player_name": "Player",
                    "positions_seen": ["Center Back"],
                }],
            },
        ]
        comparison = build_player_season_comparison(reports)
        player = comparison["players"][0]
        relation = player["seasons"][1]["position_comparison_from_previous"]
        self.assertEqual(relation["status"], "changed")
        self.assertEqual(relation["shared_positions"], ["center back"])
        self.assertEqual(relation["previous_positions"], ["Center Back", "Defensive Midfield"])
        self.assertEqual(player["position_comparison_status"], "changed")
        self.assertEqual(player["position_change_count"], 1)

    def test_season_comparison_position_labels_compare_case_insensitively(self):
        reports = [
            {
                "competition_season": {"competition_id": 43, "season_id": 106, "season_name": "2022"},
                "sample": {"selected_match_count": 1},
                "player_sample_totals": [{"player_id": 10, "player_name": "Player", "positions_seen": ["Center Back"]}],
            },
            {
                "competition_season": {"competition_id": 43, "season_id": 107, "season_name": "2023"},
                "sample": {"selected_match_count": 1},
                "player_sample_totals": [{"player_id": 10, "player_name": "Player", "positions_seen": [" center   back "]}],
            },
        ]
        comparison = build_player_season_comparison(reports)
        player = comparison["players"][0]
        self.assertEqual(player["seasons"][1]["position_comparison_from_previous"]["status"], "same")
        self.assertEqual(player["seasons"][1]["position_comparison_from_previous"]["shared_positions"], ["center back"])

    def test_season_comparison_marks_position_as_unavailable_when_missing(self):
        reports = [
            {
                "competition_season": {"competition_id": 43, "season_id": 106, "season_name": "2022"},
                "sample": {"selected_match_count": 1},
                "player_sample_totals": [{"player_id": 10, "player_name": "Player", "positions_seen": []}],
            },
            {
                "competition_season": {"competition_id": 43, "season_id": 107, "season_name": "2023"},
                "sample": {"selected_match_count": 1},
                "player_sample_totals": [{"player_id": 10, "player_name": "Player", "positions_seen": ["Center Back"]}],
            },
        ]
        comparison = build_player_season_comparison(reports)
        role = comparison["players"][0]["seasons"][1]["position_comparison_from_previous"]
        self.assertEqual(role["status"], "unavailable")
        self.assertEqual(role["shared_positions"], [])

    def test_season_comparison_omits_players_not_found_in_both_seasons(self):
        reports = [
            {
                "competition_season": {"competition_id": 43, "season_id": 106, "season_name": "2022"},
                "sample": {"selected_match_count": 1},
                "player_sample_totals": [{"player_id": 10, "player_name": "Returning Player", "per90_metrics": {"events": 80}}],
            },
            {
                "competition_season": {"competition_id": 43, "season_id": 107, "season_name": "2023"},
                "sample": {"selected_match_count": 1},
                "player_sample_totals": [{"player_id": 20, "player_name": "New Player", "per90_metrics": {"events": 90}}],
            },
        ]
        comparison = build_player_season_comparison(reports)
        self.assertEqual(comparison["player_count"], 0)
        self.assertEqual(comparison["players"], [])

    def test_season_comparison_rejects_mixed_competitions_and_duplicate_seasons(self):
        base = {
            "competition_season": {"competition_id": 43, "season_id": 106, "season_name": "2022"},
            "sample": {"selected_match_count": 1},
            "player_sample_totals": [],
        }
        mixed = {
            "competition_season": {"competition_id": 44, "season_id": 107, "season_name": "2023"},
            "sample": {"selected_match_count": 1},
            "player_sample_totals": [],
        }
        duplicate = {
            "competition_season": {"competition_id": 43, "season_id": 106, "season_name": "2022"},
            "sample": {"selected_match_count": 1},
            "player_sample_totals": [],
        }
        with self.assertRaisesRegex(ValueError, "nesnesi"):
            build_player_season_comparison([None, base])
        with self.assertRaisesRegex(ValueError, "tek bir turnuva"):
            build_player_season_comparison([base, mixed])
        with self.assertRaisesRegex(ValueError, "birden fazla"):
            build_player_season_comparison([base, duplicate])

    def test_season_comparison_leaves_per90_changes_unavailable_when_minutes_missing(self):
        reports = [
            {
                "competition_season": {"competition_id": 43, "season_id": 106, "season_name": "2022"},
                "sample": {"selected_match_count": 1},
                "player_sample_totals": [{"player_id": 10, "player_name": "Player", "per90_metrics": None}],
            },
            {
                "competition_season": {"competition_id": 43, "season_id": 107, "season_name": "2023"},
                "sample": {"selected_match_count": 1},
                "player_sample_totals": [{"player_id": 10, "player_name": "Player", "per90_metrics": {"events": 75.0}}],
            },
        ]
        comparison = build_player_season_comparison(reports)
        latest = comparison["players"][0]["seasons"][1]
        self.assertIsNone(latest["per90_change_from_previous"])

    def test_main_writes_season_comparison_into_current_report(self):
        previous_report = {
            "competition_season": {
                "competition_id": 43, "competition_name": "FIFA World Cup",
                "season_id": 106, "season_name": "2022",
            },
            "sample": {"selected_match_count": 1},
            "player_sample_totals": [{
                "player_id": 10, "player_name": "Example Player",
                "per90_metrics": {"events": 80.0},
            }],
        }
        current_report = {
            "competition_season": {
                "competition_id": 43, "competition_name": "FIFA World Cup",
                "season_id": 107, "season_name": "2023",
            },
            "sample": {"selected_match_count": 1, "event_count": 10, "unique_players_listed_or_seen": 1},
            "player_sample_totals": [{
                "player_id": 10, "player_name": "Example Player",
                "per90_metrics": {"events": 90.0},
            }],
            "output_files": {},
        }
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            previous_path = root / "2022.json"
            output_path = root / "2023.json"
            previous_path.write_text(json.dumps(previous_report), encoding="utf-8")
            current_report["output_files"]["json"] = str(output_path)
            current_report["output_files"]["players_csv"] = str(root / "2023.csv")
            output_path.write_text(json.dumps(current_report), encoding="utf-8")

            with patch("sys.argv", [
                "import_open_data.py", "--report", str(output_path),
                "--compare-report", str(previous_path),
            ]), patch("import_open_data.run_import", return_value=current_report):
                from contextlib import redirect_stdout
                from io import StringIO
                with redirect_stdout(StringIO()):
                    result = main()

            saved = json.loads(output_path.read_text(encoding="utf-8"))
            self.assertEqual(result, 0)
            self.assertEqual(saved["season_comparison"]["player_count"], 1)
            self.assertEqual(
                saved["season_comparison"]["players"][0]["seasons"][1][
                    "per90_change_from_previous"
                ]["events"],
                10.0,
            )

    def test_cli_accepts_multiple_comparison_report_paths(self):
        args = build_parser().parse_args([
            "--compare-report", "season-2022.json",
            "--compare-report", "season-2023.json",
        ])
        self.assertEqual(args.compare_report, ["season-2022.json", "season-2023.json"])

    def test_player_data_consistency_accepts_matching_match_totals(self):
        metrics = {
            "events": 8,
            "passes_attempted": 4,
            "passes_completed": 3,
            "xg": 0.5,
        }
        for field in (
            "crosses", "through_balls", "assists", "shot_assists", "carries",
            "shots", "goals", "pressures", "interceptions", "ball_recoveries",
            "clearances", "blocks", "tackles", "dribbles",
        ):
            metrics.setdefault(field, 0)
        player = {
            "matches_listed_in_squads": 2,
            "matches_with_appearance_evidence": 2,
            "minutes_calculation_complete": True,
            "minutes_matches_valid": 2,
            "minutes_played": 90.0,
            "per90_metrics": calculate_per90_metrics(metrics, 90 * 60),
            "metrics": metrics,
        }
        match_rows = [
            {
                "appearance_evidence": True,
                "minutes_played_seconds": 45 * 60,
                "metrics": {"events": 3, "passes_attempted": 1, "passes_completed": 1, "xg": 0.2},
            },
            {
                "appearance_evidence": True,
                "minutes_played_seconds": 45 * 60,
                "metrics": {"events": 5, "passes_attempted": 3, "passes_completed": 2, "xg": 0.3},
            },
        ]
        result = calculate_player_data_consistency(player, match_rows)
        self.assertEqual(result["status"], "consistent")
        self.assertEqual(result["reasons"], [])
        self.assertTrue(result["checks"]["event_metric_totals_match"])
        self.assertTrue(result["checks"]["minutes_total_matches"])
        self.assertTrue(result["checks"]["per90_recalculated"])

    def test_player_data_consistency_reconciles_score_state_totals(self):
        states = {
            "leading": {"events": 2, "passes_attempted": 1, "xg": 0.0},
            "drawing": {"events": 1, "passes_attempted": 0, "xg": 0.2},
            "trailing": {"events": 0, "passes_attempted": 0, "xg": 0.0},
        }
        aggregate_states = {
            state: dict(values) for state, values in states.items()
        }
        player = {
            "matches_listed_in_squads": 1,
            "matches_with_appearance_evidence": 1,
            "minutes_calculation_complete": False,
            "minutes_matches_valid": 0,
            "minutes_played": None,
            "per90_metrics": None,
            "metrics": {"events": 3, "passes_attempted": 1, "xg": 0.2},
            "score_state_analysis": {
                "match_status_counts": {
                    "validated": 1,
                    "partial": 0,
                    "unavailable": 0,
                },
                "metrics_by_state": aggregate_states,
            },
        }
        match_rows = [{
            "appearance_evidence": True,
            "minutes_played_seconds": None,
            "metrics": {"events": 3, "passes_attempted": 1, "xg": 0.2},
            "score_state_analysis": {
                "status": "validated",
                "metrics_by_state": states,
            },
        }]
        result = calculate_player_data_consistency(player, match_rows)
        self.assertEqual(result["status"], "consistent")
        self.assertTrue(result["checks"]["score_state_match_status_counts_match"])
        self.assertTrue(result["checks"]["score_state_metric_totals_match"])

        player["score_state_analysis"]["metrics_by_state"]["leading"]["passes_attempted"] = 2
        mismatched = calculate_player_data_consistency(player, match_rows)
        self.assertEqual(mismatched["status"], "review")
        self.assertFalse(mismatched["checks"]["score_state_metric_totals_match"])
        self.assertIn(
            "score_state_metric_total_mismatch:leading:passes_attempted",
            mismatched["reasons"],
        )

    def test_player_data_consistency_flags_mismatched_event_totals(self):
        player = {
            "matches_listed_in_squads": 1,
            "matches_with_appearance_evidence": 1,
            "minutes_calculation_complete": False,
            "minutes_matches_valid": 0,
            "minutes_played": None,
            "per90_metrics": None,
            "metrics": {"events": 8},
        }
        match_rows = [{
            "appearance_evidence": True,
            "minutes_played_seconds": None,
            "metrics": {"events": 7},
        }]
        result = calculate_player_data_consistency(player, match_rows)
        self.assertEqual(result["status"], "review")
        self.assertIn("metric_total_mismatch:events", result["reasons"])

    def test_per90_normalizes_counts_and_xg_but_not_percentages_or_means(self):
        metrics = {
            "events": 15,
            "passes_attempted": 10,
            "xg": 1.25,
            "pass_completion_pct": 80.0,
            "pass_length_mean": 20.0,
        }
        result = calculate_per90_metrics(metrics, 45 * 60)
        self.assertEqual(result["events"], 30.0)
        self.assertEqual(result["passes_attempted"], 20.0)
        self.assertEqual(result["xg"], 2.5)
        self.assertNotIn("pass_completion_pct", result)
        self.assertNotIn("pass_length_mean", result)

    def test_per90_is_unavailable_without_positive_verified_minutes(self):
        self.assertIsNone(calculate_per90_metrics({"events": 5}, None))
        self.assertIsNone(calculate_per90_metrics({"events": 5}, 0))

    def test_match_report_includes_per90_when_match_minutes_are_valid(self):
        events = [
            self._starting_xi(1, 1, [10]),
            self._clock_event(2, 1, "00:00:00.000", "Half Start"),
            self._clock_event(
                3, 1, "00:10:00.000", "Pass",
                player={"id": 10, "name": "Player 10"},
                team={"id": 1, "name": "Team 1"},
                pass_data={"length": 20.0},
            ),
            self._clock_event(4, 1, "00:45:00.000", "Half End"),
        ]
        events[2]["pass"] = events[2].pop("pass_data")
        report = analyse_match(MATCH, LINEUPS, events)
        player = next(row for row in report["player_metrics"] if row["player_id"] == 10)
        self.assertEqual(player["minutes_played"], 45.0)
        self.assertEqual(player["per90_metrics"]["events"], 2.0)
        self.assertEqual(player["per90_metrics"]["passes_attempted"], 2.0)

    def test_does_not_fabricate_per90_without_minutes(self):
        report = analyse_match(MATCH, LINEUPS, EVENTS)
        player = report["player_metrics"][0]
        self.assertIsNone(player["minutes_played"])
        self.assertIsNone(player["per90_metrics"])


    def test_unused_squad_member_is_not_assumed_to_have_appeared(self):
        lineups = [{
            "team_id": 1,
            "team_name": "Argentina",
            "lineup": [
                {
                    "player_id": 10,
                    "player_name": "Example Player",
                    "positions": [{"position": "Center Attacking Midfield"}],
                },
                {
                    "player_id": 11,
                    "player_name": "Unused Substitute",
                    "positions": [],
                },
            ],
        }]
        report = analyse_match(MATCH, lineups, EVENTS)
        player = next(row for row in report["player_metrics"] if row["player_id"] == 11)
        self.assertFalse(player["appearance_evidence"])
        self.assertIsNone(player["minutes_played"])

    def test_structural_events_without_player_are_not_counted_as_unattributed(self):
        report = analyse_match(MATCH, LINEUPS, EVENTS)
        self.assertEqual(report["quality"]["unattributed_non_structural_events"], 0)

    def test_unknown_player_in_events_is_preserved_and_flagged(self):
        events = EVENTS + [{
            "id": "7", "type": {"name": "Interception"},
            "player": {"id": 77, "name": "Unexpected Player"},
            "team": {"id": 1, "name": "Argentina"},
        }]
        report = analyse_match(MATCH, LINEUPS, events)
        ids = {str(row["player_id"]) for row in report["player_metrics"]}
        self.assertIn("77", ids)
        self.assertTrue(any("lineup dosyasında yok" in warning
                            for warning in report["quality"]["warnings"]))

    def test_invalid_events_root_is_rejected(self):
        with self.assertRaises(ImportErrorWithContext):
            analyse_match(MATCH, LINEUPS, {"not": "a list"})


    def test_run_import_writes_json_report_and_player_csv(self):
        def fake_fetch_json(relative_path, cache_root, force=False):
            metadata = {
                "path": relative_path,
                "cache": "fixture",
                "bytes": 100,
                "sha256": "a" * 64,
                "url": "https://example.invalid/" + relative_path,
            }
            if relative_path == "competitions.json":
                return [{
                    "competition_id": 43,
                    "season_id": 106,
                    "competition_name": "FIFA World Cup",
                    "season_name": "2022",
                    "competition_gender": "male",
                    "competition_youth": False,
                }], metadata
            if relative_path == "matches/43/106.json":
                return [MATCH], metadata
            if relative_path == "lineups/123.json":
                return LINEUPS, metadata
            if relative_path == "events/123.json":
                timed_events = [
                    self._starting_xi(0, 1, [10]),
                    self._clock_event(1, 1, "00:00:00.000", "Half Start"),
                ]
                for index, event in enumerate(EVENTS, start=2):
                    extra = {
                        key: value for key, value in event.items()
                        if key not in {"index", "period", "minute", "second", "timestamp", "type"}
                    }
                    timed_events.append(self._clock_event(
                        index, 1, f"00:{index * 5:02d}:00.000",
                        event["type"]["name"], **extra
                    ))
                timed_events.append(self._clock_event(
                    len(EVENTS) + 2, 1, "00:45:00.000", "Half End"
                ))
                return timed_events, metadata
            raise AssertionError("Unexpected source path: " + relative_path)

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            args = Namespace(
                competition_id=43,
                season_id=106,
                match_id=None,
                limit=1,
                data_root=str(root / "raw"),
                report=str(root / "reports" / "report.json"),
                force=False,
            )
            with patch("import_open_data.fetch_json", side_effect=fake_fetch_json):
                report = run_import(args)

            json_path = Path(report["output_files"]["json"])
            csv_path = Path(report["output_files"]["players_csv"])
            self.assertTrue(json_path.exists())
            self.assertTrue(csv_path.exists())
            self.assertEqual(report["competition_season"]["competition_name"], "FIFA World Cup")
            self.assertEqual(report["competition_season"]["season_name"], "2022")
            self.assertEqual(report["sample"]["event_count"], len(EVENTS) + 3)
            self.assertEqual(report["sample"]["selected_match_count"], 1)
            self.assertEqual(report["sample"]["possible_same_name_collision_groups"], 0)
            self.assertEqual(report["player_identity_review"]["same_name_different_ids"], [])

            with csv_path.open(encoding="utf-8-sig", newline="") as stream:
                rows = list(csv.DictReader(stream))
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["player_name"], "Example Player")
            self.assertEqual(rows[0]["passes_attempted"], "2")
            self.assertEqual(rows[0]["pass_completion_pct"], "50.0")
            self.assertEqual(rows[0]["minutes_played"], "45.0")
            self.assertEqual(rows[0]["per90_events"], "10.0")
            self.assertEqual(rows[0]["per90_passes_attempted"], "4.0")
            self.assertEqual(rows[0]["per90_xg"], "0.84")
            self.assertEqual(rows[0]["data_quality_status"], "complete")
            self.assertEqual(rows[0]["data_quality_reasons"], "")
            self.assertEqual(rows[0]["data_quality_appearance_evidence"], "True")
            self.assertEqual(rows[0]["data_quality_minutes_complete"], "True")
            self.assertEqual(rows[0]["data_quality_has_attributed_events"], "True")
            self.assertEqual(rows[0]["possible_same_name_collision"], "False")
            self.assertEqual(rows[0]["other_same_name_player_ids"], "")
            self.assertEqual(rows[0]["data_consistency_status"], "consistent")
            self.assertEqual(rows[0]["data_consistency_reasons"], "")
            self.assertEqual(rows[0]["data_consistency_match_records"], "1")
            self.assertEqual(rows[0]["player_identity_key"], "statsbomb:10")
            self.assertEqual(rows[0]["player_identity_status"], "consistent")
            self.assertEqual(rows[0]["player_identity_reasons"], "")
            self.assertEqual(rows[0]["player_identity_name_variants"], "Example Player")
            self.assertEqual(rows[0]["score_state_analysis_status"], "unavailable")
            self.assertEqual(rows[0]["score_state_matches_unavailable"], "1")
            self.assertEqual(rows[0]["score_state_classified_player_events"], "0")
            self.assertEqual(rows[0]["score_state_unclassified_player_events"], "5")
            self.assertEqual(rows[0]["score_state_leading_metrics_json"], "")
            self.assertEqual(
                report["player_sample_totals"][0]["score_state_analysis"]["status"],
                "unavailable",
            )
            self.assertTrue(
                report["player_sample_totals"][0]["data_consistency"]["checks"][
                    "score_state_metric_totals_match"
                ]
            )
            self.assertNotIn("per90_pass_completion_pct", rows[0])
            self.assertNotIn("per90_pass_length_mean", rows[0])


    def test_cb_profile_selects_centre_backs_without_creating_a_rating(self):
        players = [
            {
                "player_id": 20572,
                "player_name": "Example Centre Back",
                "team_names": ["Argentina"],
                "positions_seen": ["Right Center Back"],
                "matches_listed_in_squads": 3,
                "matches_with_appearance_evidence": 3,
                "metrics": {
                    "events": 40,
                    "passes_attempted": 30,
                    "passes_completed": 27,
                    "crosses": 3,
                    "through_balls": 2,
                    "shot_assists": 1,
                    "pass_completion_pct": 90.0,
                    "pass_length_mean": 22.4,
                    "carries": 6,
                    "pressures": 9,
                    "interceptions": 4,
                    "ball_recoveries": 5,
                    "clearances": 7,
                    "blocks": 2,
                    "tackles": 3,
                },
                "per90_metrics": {
                    "passes_attempted": 20.0,
                    "passes_completed": 18.0,
                    "crosses": 2.0,
                    "through_balls": 1.3,
                    "shot_assists": 0.7,
                    "carries": 4.0,
                    "pressures": 6.0,
                    "interceptions": 2.7,
                    "ball_recoveries": 3.3,
                    "clearances": 4.7,
                    "blocks": 1.3,
                    "tackles": 2.0,
                },
            },
            {
                "player_id": 5503,
                "player_name": "Example Forward",
                "team_names": ["Argentina"],
                "positions_seen": ["Right Center Forward"],
                "matches_listed_in_squads": 3,
                "matches_with_appearance_evidence": 3,
                "metrics": {"passes_attempted": 20},
            },
        ]
        profile = build_cb_profile(players)
        self.assertEqual(profile["role_code"], "CB")
        self.assertEqual(profile["player_count"], 1)
        selected = profile["players"][0]
        self.assertEqual(selected["player_id"], 20572)
        self.assertEqual(selected["matches_with_appearance_evidence"], 3)
        self.assertEqual(selected["metrics"]["events"], 40)
        self.assertIsNone(selected["minutes_played"])
        self.assertEqual(
            [group["code"] for group in profile["metric_groups"]],
            ["distribution_progression", "defensive_activity", "box_protection"],
        )
        distribution = selected["grouped_metrics"]["distribution_progression"]
        self.assertEqual(distribution["raw_counts"]["passes_attempted"], 30)
        self.assertEqual(distribution["per90_counts"]["passes_attempted"], 20.0)
        self.assertEqual(distribution["context_metrics"]["pass_completion_pct"], 90.0)
        defence = selected["grouped_metrics"]["defensive_activity"]
        self.assertEqual(defence["raw_counts"]["interceptions"], 4)
        self.assertEqual(defence["per90_counts"]["ball_recoveries"], 3.3)
        box = selected["grouped_metrics"]["box_protection"]
        self.assertEqual(box["raw_counts"]["clearances"], 7)
        self.assertNotIn("aerial_duels", selected["grouped_metrics"])
        self.assertEqual(
            profile["not_yet_available"][0]["metric"], "aerial_duel_success"
        )
        self.assertNotIn("rating", selected)
        self.assertIn("defensive rating or ranking", profile["interpretation_limits"][0])

    def test_fullback_profile_groups_wingback_and_fullback_metrics(self):
        players = [
            {
                "player_id": 1,
                "player_name": "Right Back",
                "team_names": ["Example FC"],
                "positions_seen": ["Right Back"],
                "matches_listed_in_squads": 4,
                "matches_with_appearance_evidence": 4,
                "minutes_played": 300.0,
                "per90_metrics": {
                    "crosses": 3.0,
                    "assists": 0.3,
                    "xg": 0.1,
                    "passes_attempted": 45.0,
                    "carries": 5.0,
                    "pressures": 8.0,
                    "tackles": 2.0,
                    "interceptions": 1.0,
                    "clearances": 2.0,
                },
                "metrics": {
                    "crosses": 10,
                    "through_balls": 2,
                    "shot_assists": 1,
                    "assists": 1,
                    "shots": 3,
                    "goals": 1,
                    "xg": 0.2,
                    "passes_attempted": 150,
                    "passes_completed": 120,
                    "pass_completion_pct": 80.0,
                    "pass_length_mean": 23.5,
                    "carries": 17,
                    "dribbles": 4,
                    "pressures": 27,
                    "tackles": 7,
                    "interceptions": 3,
                    "ball_recoveries": 5,
                    "clearances": 8,
                    "blocks": 2,
                },
            },
            {
                "player_id": 2,
                "player_name": "Wing Back",
                "positions_seen": ["Left Wing Back", "Left Midfield"],
                "metrics": {"crosses": 4},
            },
            {
                "player_id": 3,
                "player_name": "Centre Back",
                "positions_seen": ["Right Center Back"],
                "metrics": {"clearances": 5},
            },
            {
                "player_id": 4,
                "player_name": "Winger",
                "positions_seen": ["Right Wing"],
                "metrics": {"crosses": 8},
            },
        ]

        profile = build_fullback_profile(players)
        self.assertEqual(profile["role_code"], "FB")
        self.assertEqual(profile["player_count"], 2)
        self.assertEqual(
            [row["player_id"] for row in profile["players"]],
            [1, 2],
        )

        selected = profile["players"][0]
        self.assertEqual(selected["fullback_position_labels"], ["Right Back"])
        self.assertEqual(
            [group["code"] for group in profile["metric_groups"]],
            ["attacking_output", "distribution_progression", "defensive_activity"],
        )
        attacking = selected["grouped_metrics"]["attacking_output"]
        self.assertEqual(attacking["raw_counts"]["crosses"], 10)
        self.assertEqual(attacking["per90_counts"]["crosses"], 3.0)
        self.assertEqual(attacking["raw_rate_totals"]["xg"], 0.2)
        self.assertEqual(attacking["per90_rate_metrics"]["xg"], 0.1)

        progression = selected["grouped_metrics"]["distribution_progression"]
        self.assertEqual(progression["raw_counts"]["passes_attempted"], 150)
        self.assertEqual(progression["context_metrics"]["pass_completion_pct"], 80.0)
        defence = selected["grouped_metrics"]["defensive_activity"]
        self.assertEqual(defence["raw_counts"]["tackles"], 7)
        self.assertEqual(defence["per90_counts"]["pressures"], 8.0)

        wingback = profile["players"][1]
        self.assertEqual(wingback["fullback_position_labels"], ["Left Wing Back"])
        self.assertNotIn("rating", selected)
        self.assertEqual(profile["interpretation_limits"][0], "No full-back rating or ranking is calculated.")

    def test_fullback_profile_does_not_fabricate_per90_without_verified_metrics(self):
        profile = build_fullback_profile([{
            "player_id": 8,
            "player_name": "Unverified Fullback",
            "positions_seen": ["Left Back"],
            "metrics": {"crosses": 5, "pressures": 10},
            "per90_metrics": None,
        }])
        player = profile["players"][0]
        self.assertEqual(
            player["grouped_metrics"]["attacking_output"]["raw_counts"]["crosses"],
            5,
        )
        self.assertEqual(
            player["grouped_metrics"]["attacking_output"]["per90_counts"],
            {},
        )
        self.assertEqual(
            player["grouped_metrics"]["defensive_activity"]["per90_counts"],
            {},
        )

    def test_fullback_position_filter_excludes_centre_back_and_attacking_winger(self):
        profile = build_fullback_profile([
            {"player_id": 1, "player_name": "CB", "positions_seen": ["Left Centre Back"]},
            {"player_id": 2, "player_name": "Winger", "positions_seen": ["Left Wing"]},
            {"player_id": 3, "player_name": "Fullback", "positions_seen": ["Right Fullback"]},
        ])
        self.assertEqual(profile["player_count"], 1)
        self.assertEqual(profile["players"][0]["player_id"], 3)

    def test_central_midfield_profile_groups_metrics_and_selects_central_roles(self):
        players = [
            {
                "player_id": 10,
                "player_name": "Central Midfielder",
                "team_names": ["Example FC"],
                "positions_seen": ["Left Center Midfield", "Center Defensive Midfield"],
                "matches_listed_in_squads": 5,
                "matches_with_appearance_evidence": 5,
                "minutes_played": 420.0,
                "per90_metrics": {
                    "passes_attempted": 55.0,
                    "through_balls": 1.4,
                    "carries": 6.0,
                    "dribbles": 2.0,
                    "shot_assists": 0.8,
                    "shots": 1.2,
                    "xg": 0.15,
                    "pressures": 12.0,
                    "tackles": 2.1,
                    "interceptions": 1.7,
                    "ball_recoveries": 3.5,
                },
                "metrics": {
                    "passes_attempted": 256,
                    "passes_completed": 220,
                    "pass_completion_pct": 85.94,
                    "pass_length_mean": 18.7,
                    "through_balls": 7,
                    "carries": 28,
                    "dribbles": 9,
                    "shot_assists": 4,
                    "assists": 2,
                    "crosses": 3,
                    "shots": 6,
                    "goals": 1,
                    "xg": 0.7,
                    "pressures": 56,
                    "tackles": 10,
                    "interceptions": 8,
                    "ball_recoveries": 16,
                    "clearances": 3,
                    "blocks": 1,
                },
            },
            {
                "player_id": 11,
                "player_name": "Defensive Midfielder",
                "positions_seen": ["Defensive Midfield"],
                "metrics": {"interceptions": 7},
            },
            {
                "player_id": 12,
                "player_name": "Attacking Midfielder",
                "positions_seen": ["Center Attacking Midfield"],
                "metrics": {"shot_assists": 4},
            },
            {
                "player_id": 13,
                "player_name": "Wide Midfielder",
                "positions_seen": ["Left Midfield"],
                "metrics": {"crosses": 9},
            },
            {
                "player_id": 14,
                "player_name": "Centre Back",
                "positions_seen": ["Right Center Back"],
                "metrics": {"clearances": 12},
            },
            {
                "player_id": 15,
                "player_name": "Winger",
                "positions_seen": ["Left Wing"],
                "metrics": {"dribbles": 8},
            },
        ]

        profile = build_central_midfield_profile(players)
        self.assertEqual(profile["role_code"], "CM")
        self.assertEqual(profile["player_count"], 3)
        self.assertEqual(
            [row["player_id"] for row in profile["players"]],
            [12, 10, 11],
        )

        selected = next(row for row in profile["players"] if row["player_id"] == 10)
        self.assertEqual(
            selected["central_midfield_position_labels"],
            ["Center Defensive Midfield", "Left Center Midfield"],
        )
        self.assertEqual(
            [group["code"] for group in profile["metric_groups"]],
            ["distribution_progression", "chance_creation", "defensive_activity"],
        )
        passing = selected["grouped_metrics"]["distribution_progression"]
        self.assertEqual(passing["raw_counts"]["passes_attempted"], 256)
        self.assertEqual(passing["per90_counts"]["passes_attempted"], 55.0)
        self.assertEqual(passing["context_metrics"]["pass_completion_pct"], 85.94)

        chance = selected["grouped_metrics"]["chance_creation"]
        self.assertEqual(chance["raw_counts"]["shot_assists"], 4)
        self.assertEqual(chance["per90_counts"]["shots"], 1.2)
        self.assertEqual(chance["raw_rate_totals"]["xg"], 0.7)
        self.assertEqual(chance["per90_rate_metrics"]["xg"], 0.15)

        defence = selected["grouped_metrics"]["defensive_activity"]
        self.assertEqual(defence["raw_counts"]["interceptions"], 8)
        self.assertEqual(defence["per90_counts"]["ball_recoveries"], 3.5)
        self.assertNotIn("rating", selected)
        self.assertIn("No central-midfielder rating or ranking", profile["interpretation_limits"][0])

    def test_central_midfield_profile_does_not_fabricate_rates(self):
        profile = build_central_midfield_profile([{
            "player_id": 20,
            "player_name": "Unverified Midfielder",
            "positions_seen": ["Center Midfield"],
            "metrics": {"passes_attempted": 40, "shots": 3, "pressures": 12, "xg": 0.2},
            "per90_metrics": None,
        }])
        player = profile["players"][0]
        self.assertEqual(
            player["grouped_metrics"]["distribution_progression"]["raw_counts"]["passes_attempted"],
            40,
        )
        self.assertEqual(
            player["grouped_metrics"]["distribution_progression"]["per90_counts"],
            {},
        )
        self.assertEqual(
            player["grouped_metrics"]["chance_creation"]["per90_rate_metrics"],
            {},
        )

    def test_central_midfield_position_filter_handles_labels_without_wide_midfield(self):
        profile = build_central_midfield_profile([
            {"player_id": 1, "player_name": "Center", "positions_seen": ["Center Midfield"]},
            {"player_id": 2, "player_name": "Right Center", "positions_seen": ["Right Center Midfield"]},
            {"player_id": 3, "player_name": "Left Midfield", "positions_seen": ["Left Midfield"]},
            {"player_id": 4, "player_name": "Wide Midfield", "positions_seen": ["Wide Midfield"]},
            {"player_id": 5, "player_name": "Center Back", "positions_seen": ["Center Back"]},
            {"player_id": 6, "player_name": "Central", "positions_seen": ["Central Midfield"]},
        ])
        self.assertEqual(profile["player_count"], 3)
        self.assertEqual(
            {row["player_id"] for row in profile["players"]},
            {1, 2, 6},
        )

    def test_winger_profile_groups_attacking_and_progression_metrics(self):
        players = [
            {
                "player_id": 30,
                "player_name": "Right Winger",
                "team_names": ["Example FC"],
                "positions_seen": ["Right Wing"],
                "matches_listed_in_squads": 5,
                "matches_with_appearance_evidence": 5,
                "minutes_played": 410.0,
                "per90_metrics": {
                    "shot_assists": 0.9,
                    "assists": 0.4,
                    "shots": 2.1,
                    "goals": 0.5,
                    "xg": 0.28,
                    "crosses": 2.7,
                    "through_balls": 0.8,
                    "passes_attempted": 28.0,
                    "passes_completed": 21.0,
                    "dribbles": 4.2,
                    "carries": 5.1,
                    "pressures": 9.8,
                    "tackles": 1.2,
                    "interceptions": 0.6,
                    "ball_recoveries": 1.9,
                },
                "metrics": {
                    "shot_assists": 4,
                    "assists": 2,
                    "shots": 10,
                    "goals": 2,
                    "xg": 1.3,
                    "crosses": 13,
                    "through_balls": 3,
                    "passes_attempted": 130,
                    "passes_completed": 96,
                    "pass_completion_pct": 73.85,
                    "pass_length_mean": 16.2,
                    "dribbles": 19,
                    "carries": 23,
                    "pressures": 45,
                    "tackles": 6,
                    "interceptions": 3,
                    "ball_recoveries": 9,
                },
            },
            {
                "player_id": 31,
                "player_name": "Left Winger",
                "positions_seen": ["Left Wing"],
                "metrics": {"dribbles": 8},
            },
            {
                "player_id": 32,
                "player_name": "Wing Back",
                "positions_seen": ["Left Wing Back"],
                "metrics": {"crosses": 10},
            },
            {
                "player_id": 33,
                "player_name": "Centre Forward",
                "positions_seen": ["Right Center Forward"],
                "metrics": {"shots": 5},
            },
            {
                "player_id": 34,
                "player_name": "Wide Midfielder",
                "positions_seen": ["Left Midfield"],
                "metrics": {"crosses": 7},
            },
        ]

        profile = build_winger_profile(players)
        self.assertEqual(profile["role_code"], "W")
        self.assertEqual(profile["player_count"], 2)
        self.assertEqual(
            [row["player_id"] for row in profile["players"]],
            [31, 30],
        )
        selected = profile["players"][1]
        self.assertEqual(selected["winger_position_labels"], ["Right Wing"])
        self.assertEqual(
            [group["code"] for group in profile["metric_groups"]],
            [
                "chance_creation_finishing",
                "wide_delivery",
                "one_v_one_progression",
                "defensive_contribution",
            ],
        )

        attacking = selected["grouped_metrics"]["chance_creation_finishing"]
        self.assertEqual(attacking["raw_counts"]["shots"], 10)
        self.assertEqual(attacking["per90_counts"]["shots"], 2.1)
        self.assertEqual(attacking["raw_rate_totals"]["xg"], 1.3)
        self.assertEqual(attacking["per90_rate_metrics"]["xg"], 0.28)

        delivery = selected["grouped_metrics"]["wide_delivery"]
        self.assertEqual(delivery["raw_counts"]["crosses"], 13)
        self.assertEqual(delivery["per90_counts"]["crosses"], 2.7)
        self.assertEqual(delivery["context_metrics"]["pass_completion_pct"], 73.85)

        progression = selected["grouped_metrics"]["one_v_one_progression"]
        self.assertEqual(progression["raw_counts"]["dribbles"], 19)
        self.assertEqual(progression["per90_counts"]["carries"], 5.1)

        defence = selected["grouped_metrics"]["defensive_contribution"]
        self.assertEqual(defence["raw_counts"]["pressures"], 45)
        self.assertEqual(defence["per90_counts"]["ball_recoveries"], 1.9)
        self.assertNotIn("rating", selected)
        self.assertIn("No winger rating or ranking", profile["interpretation_limits"][0])

    def test_winger_profile_does_not_fabricate_per90_rates(self):
        profile = build_winger_profile([{
            "player_id": 40,
            "player_name": "Unverified Winger",
            "positions_seen": ["Left Wing"],
            "metrics": {"shots": 4, "xg": 0.4, "crosses": 6, "dribbles": 8, "pressures": 10},
            "per90_metrics": None,
        }])
        player = profile["players"][0]
        self.assertEqual(
            player["grouped_metrics"]["chance_creation_finishing"]["raw_counts"]["shots"],
            4,
        )
        self.assertEqual(
            player["grouped_metrics"]["chance_creation_finishing"]["per90_counts"],
            {},
        )
        self.assertEqual(
            player["grouped_metrics"]["chance_creation_finishing"]["per90_rate_metrics"],
            {},
        )
        self.assertEqual(
            player["grouped_metrics"]["one_v_one_progression"]["per90_counts"],
            {},
        )

    def test_winger_position_filter_excludes_wingbacks_forwards_and_wide_midfielders(self):
        profile = build_winger_profile([
            {"player_id": 1, "player_name": "Left Wing", "positions_seen": ["Left Wing"]},
            {"player_id": 2, "player_name": "Right Wing", "positions_seen": ["Right Wing"]},
            {"player_id": 3, "player_name": "Wing Back", "positions_seen": ["Right Wing Back"]},
            {"player_id": 4, "player_name": "Forward", "positions_seen": ["Left Center Forward"]},
            {"player_id": 5, "player_name": "Wide Midfielder", "positions_seen": ["Right Midfield"]},
            {"player_id": 6, "player_name": "Mixed Role", "positions_seen": ["Left Wing", "Left Wing Back"]},
        ])
        self.assertEqual(profile["player_count"], 3)
        self.assertEqual(
            {row["player_id"] for row in profile["players"]},
            {1, 2, 6},
        )
        mixed = next(row for row in profile["players"] if row["player_id"] == 6)
        self.assertEqual(mixed["winger_position_labels"], ["Left Wing"])
        self.assertEqual(mixed["positions_seen"], ["Left Wing", "Left Wing Back"])

    def test_striker_profile_groups_finishing_chance_creation_and_link_play(self):
        players = [
            {
                "player_id": 50,
                "player_name": "Centre Forward",
                "team_names": ["Example FC"],
                "positions_seen": ["Center Forward", "Left Center Forward"],
                "matches_listed_in_squads": 5,
                "matches_with_appearance_evidence": 5,
                "minutes_played": 405.0,
                "per90_metrics": {
                    "shots": 3.1,
                    "goals": 0.8,
                    "xg": 0.62,
                    "shot_assists": 0.7,
                    "assists": 0.2,
                    "through_balls": 0.4,
                    "passes_attempted": 22.0,
                    "passes_completed": 15.0,
                    "carries": 3.5,
                    "dribbles": 1.1,
                    "pressures": 8.5,
                    "tackles": 0.7,
                    "interceptions": 0.3,
                    "ball_recoveries": 1.4,
                },
                "metrics": {
                    "shots": 14,
                    "goals": 4,
                    "xg": 2.8,
                    "shot_assists": 3,
                    "assists": 1,
                    "through_balls": 2,
                    "passes_attempted": 99,
                    "passes_completed": 68,
                    "pass_completion_pct": 68.69,
                    "pass_length_mean": 14.1,
                    "carries": 16,
                    "dribbles": 5,
                    "pressures": 38,
                    "tackles": 3,
                    "interceptions": 1,
                    "ball_recoveries": 6,
                },
            },
            {
                "player_id": 51,
                "player_name": "Striker",
                "positions_seen": ["Striker"],
                "metrics": {"goals": 3},
            },
            {
                "player_id": 52,
                "player_name": "Secondary Striker",
                "positions_seen": ["Secondary Striker"],
                "metrics": {"shots": 2},
            },
            {
                "player_id": 53,
                "player_name": "Left Winger",
                "positions_seen": ["Left Wing"],
                "metrics": {"shots": 9},
            },
            {
                "player_id": 54,
                "player_name": "Right Wing",
                "positions_seen": ["Right Wing"],
                "metrics": {"crosses": 4},
            },
            {
                "player_id": 55,
                "player_name": "Centre Midfielder",
                "positions_seen": ["Center Midfield"],
                "metrics": {"passes_attempted": 20},
            },
        ]

        profile = build_striker_profile(players)
        self.assertEqual(profile["role_code"], "ST")
        self.assertEqual(profile["player_count"], 3)
        selected = next(row for row in profile["players"] if row["player_id"] == 50)
        self.assertEqual(
            selected["striker_position_labels"],
            ["Center Forward", "Left Center Forward"],
        )
        self.assertEqual(
            [group["code"] for group in profile["metric_groups"]],
            [
                "finishing_output",
                "chance_creation",
                "link_play",
                "pressing_contribution",
            ],
        )

        finishing = selected["grouped_metrics"]["finishing_output"]
        self.assertEqual(finishing["raw_counts"]["shots"], 14)
        self.assertEqual(finishing["per90_counts"]["goals"], 0.8)
        self.assertEqual(finishing["raw_rate_totals"]["xg"], 2.8)
        self.assertEqual(finishing["per90_rate_metrics"]["xg"], 0.62)

        creation = selected["grouped_metrics"]["chance_creation"]
        self.assertEqual(creation["raw_counts"]["shot_assists"], 3)
        self.assertEqual(creation["per90_counts"]["through_balls"], 0.4)

        link_play = selected["grouped_metrics"]["link_play"]
        self.assertEqual(link_play["raw_counts"]["passes_attempted"], 99)
        self.assertEqual(link_play["context_metrics"]["pass_completion_pct"], 68.69)

        pressing = selected["grouped_metrics"]["pressing_contribution"]
        self.assertEqual(pressing["raw_counts"]["pressures"], 38)
        self.assertEqual(pressing["per90_counts"]["ball_recoveries"], 1.4)

        self.assertEqual(
            {item["metric"] for item in profile["not_yet_available"]},
            {"touches_in_box", "aerial_duel_success", "finishing_efficiency"},
        )
        self.assertNotIn("rating", selected)
        self.assertIn("No striker rating or ranking", profile["interpretation_limits"][0])

    def test_striker_profile_does_not_fabricate_per90_or_finishing_metrics(self):
        profile = build_striker_profile([{
            "player_id": 60,
            "player_name": "Unverified Striker",
            "positions_seen": ["Right Center Forward"],
            "metrics": {"shots": 5, "goals": 1, "xg": 0.8, "pressures": 12},
            "per90_metrics": None,
        }])
        player = profile["players"][0]
        self.assertEqual(
            player["grouped_metrics"]["finishing_output"]["raw_counts"]["shots"],
            5,
        )
        self.assertEqual(
            player["grouped_metrics"]["finishing_output"]["per90_counts"],
            {},
        )
        self.assertEqual(
            player["grouped_metrics"]["finishing_output"]["per90_rate_metrics"],
            {},
        )
        self.assertEqual(
            {item["metric"] for item in profile["not_yet_available"]},
            {"touches_in_box", "aerial_duel_success", "finishing_efficiency"},
        )

    def test_striker_position_filter_excludes_wingers_and_midfielders(self):
        profile = build_striker_profile([
            {"player_id": 1, "player_name": "Center Forward", "positions_seen": ["Center Forward"]},
            {"player_id": 2, "player_name": "Left Center Forward", "positions_seen": ["Left Center Forward"]},
            {"player_id": 3, "player_name": "Right Center Forward", "positions_seen": ["Right Center Forward"]},
            {"player_id": 4, "player_name": "Striker", "positions_seen": ["Striker"]},
            {"player_id": 5, "player_name": "Left Winger", "positions_seen": ["Left Wing"]},
            {"player_id": 6, "player_name": "Attacking Midfielder", "positions_seen": ["Center Attacking Midfield"]},
            {"player_id": 7, "player_name": "Mixed Role", "positions_seen": ["Center Forward", "Right Wing"]},
            {"player_id": 8, "player_name": "Wide Forward", "positions_seen": ["Left Forward"]},
        ])
        self.assertEqual(profile["player_count"], 5)
        self.assertEqual(
            {row["player_id"] for row in profile["players"]},
            {1, 2, 3, 4, 7},
        )
        mixed = next(row for row in profile["players"] if row["player_id"] == 7)
        self.assertEqual(mixed["striker_position_labels"], ["Center Forward"])
        self.assertEqual(mixed["positions_seen"], ["Center Forward", "Right Wing"])

    def test_goalkeeper_profile_groups_shot_stopping_area_control_and_distribution(self):
        players = [
            {
                "player_id": 90,
                "player_name": "Example Goalkeeper",
                "team_names": ["Example FC"],
                "positions_seen": ["Goalkeeper"],
                "matches_listed_in_squads": 4,
                "matches_with_appearance_evidence": 4,
                "minutes_played": 360.0,
                "per90_metrics": {
                    "goalkeeper_saves": 3.5,
                    "goalkeeper_shots_faced": 5.0,
                    "goalkeeper_goals_conceded": 1.0,
                    "goalkeeper_penalty_saves": 0.25,
                    "goalkeeper_collections": 1.5,
                    "goalkeeper_punches": 0.25,
                    "goalkeeper_sweeps": 0.5,
                    "goalkeeper_smotherings": 0.25,
                    "passes_attempted": 24.0,
                    "passes_completed": 17.0,
                    "goal_kicks": 4.0,
                },
                "metrics": {
                    "goalkeeper_actions": 30,
                    "goalkeeper_saves": 14,
                    "goalkeeper_shots_faced": 20,
                    "goalkeeper_goals_conceded": 4,
                    "goalkeeper_collections": 6,
                    "goalkeeper_punches": 1,
                    "goalkeeper_sweeps": 2,
                    "goalkeeper_smotherings": 1,
                    "goalkeeper_penalty_saves": 1,
                    "goalkeeper_penalties_conceded": 1,
                    "goalkeeper_unclassified_actions": 0,
                    "passes_attempted": 96,
                    "passes_completed": 68,
                    "pass_completion_pct": 70.83,
                    "pass_length_mean": 35.4,
                    "goal_kicks": 16,
                },
            },
            {
                "player_id": 91,
                "player_name": "Outfield Player",
                "positions_seen": ["Center Back"],
                "metrics": {"goalkeeper_saves": 4},
            },
        ]

        profile = build_goalkeeper_profile(players)
        self.assertEqual(profile["role_code"], "GK")
        self.assertEqual(profile["player_count"], 1)
        selected = profile["players"][0]
        self.assertEqual(selected["goalkeeper_position_labels"], ["Goalkeeper"])
        self.assertEqual(
            [group["code"] for group in profile["metric_groups"]],
            ["shot_stopping", "area_control", "distribution"],
        )

        stopping = selected["grouped_metrics"]["shot_stopping"]
        self.assertEqual(stopping["raw_counts"]["goalkeeper_saves"], 14)
        self.assertEqual(stopping["per90_counts"]["goalkeeper_saves"], 3.5)
        self.assertEqual(stopping["raw_counts"]["goalkeeper_goals_conceded"], 4)

        area = selected["grouped_metrics"]["area_control"]
        self.assertEqual(area["raw_counts"]["goalkeeper_collections"], 6)
        self.assertEqual(area["per90_counts"]["goalkeeper_sweeps"], 0.5)

        distribution = selected["grouped_metrics"]["distribution"]
        self.assertEqual(distribution["raw_counts"]["passes_attempted"], 96)
        self.assertEqual(distribution["per90_counts"]["goal_kicks"], 4.0)
        self.assertEqual(distribution["context_metrics"]["pass_completion_pct"], 70.83)

        self.assertEqual(
            {item["metric"] for item in profile["not_yet_available"]},
            {
                "save_percentage",
                "post_shot_xg_or_goals_prevented",
                "cross_claim_rate",
                "distribution_long_ball_accuracy",
            },
        )
        self.assertNotIn("rating", selected)
        self.assertIn("No goalkeeper rating or ranking", profile["interpretation_limits"][0])

    def test_goalkeeper_profile_does_not_fabricate_per90_metrics(self):
        profile = build_goalkeeper_profile([{
            "player_id": 92,
            "player_name": "Unverified Goalkeeper",
            "positions_seen": ["Goalkeeper"],
            "metrics": {"goalkeeper_saves": 7, "passes_attempted": 25},
            "per90_metrics": None,
        }])
        selected = profile["players"][0]
        self.assertEqual(
            selected["grouped_metrics"]["shot_stopping"]["raw_counts"]["goalkeeper_saves"],
            7,
        )
        self.assertEqual(
            selected["grouped_metrics"]["shot_stopping"]["per90_counts"],
            {},
        )
        self.assertEqual(
            selected["grouped_metrics"]["distribution"]["per90_counts"],
            {},
        )

    def test_goalkeeper_profile_selects_only_explicit_goalkeeper_positions(self):
        profile = build_goalkeeper_profile([
            {"player_id": 1, "player_name": "GK", "positions_seen": ["Goalkeeper"]},
            {"player_id": 2, "player_name": "Goal Keeper", "positions_seen": ["Goal Keeper"]},
            {"player_id": 3, "player_name": "CB", "positions_seen": ["Center Back"]},
            {"player_id": 4, "player_name": "Sweeper", "positions_seen": ["Keeper Sweeper"]},
            {"player_id": 5, "player_name": "Midfielder", "positions_seen": ["Center Midfield"]},
        ])
        self.assertEqual(profile["player_count"], 2)
        self.assertEqual(
            {row["player_id"] for row in profile["players"]},
            {1, 2},
        )

    def test_role_benchmarks_use_same_role_verified_cohort_and_tie_aware_percentiles(self):
        def player(player_id, value, minutes=600.0):
            return {
                "player_id": player_id,
                "player_name": f"Player {player_id}",
                "minutes_played": minutes,
                "per90_metrics": {"passes_attempted": value, "pressures": value / 2},
                "data_quality": {"status": "complete"},
                "data_consistency": {"status": "consistent"},
                "identity": {"status": "consistent"},
            }

        role_profiles = {
            "CB": {
                "role_name": "Centre-back",
                "players": [
                    player(1, 1.0),
                    player(2, 2.0),
                    player(3, 2.0),
                    player(4, 3.0),
                    player(5, 99.0, minutes=300.0),
                ],
            },
            "W": {
                "role_name": "Winger",
                "players": [player(6, 100.0)],
            },
        }
        result = build_role_benchmarks(
            role_profiles,
            minimum_verified_minutes=450,
            minimum_cohort_size=4,
        )
        cb = result["roles"]["CB"]
        self.assertEqual(cb["eligible_player_count"], 4)
        self.assertEqual(cb["cohort_status"], "ready")
        target = next(row for row in cb["players"] if row["player_id"] == 2)
        self.assertTrue(target["eligible_for_peer_comparison"])
        self.assertEqual(target["metrics"]["passes_attempted"]["percentile"], 50.0)
        self.assertEqual(target["metrics"]["passes_attempted"]["cohort_size"], 4)
        self.assertEqual(target["metrics"]["passes_attempted"]["status"], "ready")
        self.assertEqual(
            cb["metric_summaries"]["passes_attempted"]["distribution"],
            {
                "minimum": 1.0,
                "p25": 1.75,
                "median": 2.0,
                "p75": 2.25,
                "maximum": 3.0,
                "quartile_method": "linear interpolation over sorted observations",
            },
        )
        self.assertEqual(
            target["metrics"]["passes_attempted"]["difference_from_median_per90"],
            0.0,
        )
        self.assertTrue(
            target["metrics"]["passes_attempted"]["within_cohort_middle_50_percent"]
        )
        lowest = next(row for row in cb["players"] if row["player_id"] == 1)
        self.assertEqual(
            lowest["metrics"]["passes_attempted"]["difference_from_median_per90"],
            -1.0,
        )
        self.assertFalse(
            lowest["metrics"]["passes_attempted"]["within_cohort_middle_50_percent"]
        )

        excluded = next(row for row in cb["players"] if row["player_id"] == 5)
        self.assertFalse(excluded["eligible_for_peer_comparison"])
        self.assertIn("below_minimum_verified_minutes", excluded["eligibility_reasons"])
        self.assertEqual(
            excluded["metrics"]["passes_attempted"]["status"],
            "player_not_eligible",
        )
        self.assertEqual(
            result["roles"]["W"]["eligible_player_count"],
            1,
        )
        self.assertEqual(
            result["roles"]["W"]["metric_summaries"]["shots"]["status"],
            "insufficient_sample",
        )
        self.assertNotIn("ranking", target)
        self.assertEqual(result["comparison_scope"], "same competition and season report; same role profile")

    def test_role_benchmarks_leave_percentiles_unavailable_for_small_metric_cohorts(self):
        players = []
        for player_id, passes in [(1, 30.0), (2, 40.0), (3, None)]:
            per90 = {"pressures": 5.0}
            if passes is not None:
                per90["passes_attempted"] = passes
            players.append({
                "player_id": player_id,
                "player_name": f"Player {player_id}",
                "minutes_played": 700.0,
                "per90_metrics": per90,
                "data_quality": {"status": "complete"},
                "data_consistency": {"status": "consistent"},
                "identity": {"status": "consistent"},
            })
        result = build_role_benchmarks(
            {"CM": {"role_name": "Central Midfielder", "players": players}},
            minimum_verified_minutes=450,
            minimum_cohort_size=3,
        )
        cm = result["roles"]["CM"]
        self.assertEqual(cm["eligible_player_count"], 3)
        self.assertEqual(
            cm["metric_summaries"]["passes_attempted"]["status"],
            "insufficient_sample",
        )
        self.assertIsNone(cm["metric_summaries"]["passes_attempted"]["distribution"])
        for player in cm["players"]:
            metric = player["metrics"]["passes_attempted"]
            self.assertIsNone(metric["percentile"])
            self.assertIsNone(metric["difference_from_median_per90"])
            self.assertIsNone(metric["within_cohort_middle_50_percent"])
            self.assertEqual(metric["cohort_size"], 2)
            if player["player_id"] == 3:
                self.assertEqual(metric["status"], "metric_unavailable")
            else:
                self.assertEqual(metric["status"], "insufficient_sample")

    def test_linear_quantile_uses_interpolation_and_rejects_invalid_probability(self):
        from import_open_data import _linear_quantile

        self.assertEqual(_linear_quantile([1.0, 2.0, 2.0, 3.0], 0.25), 1.75)
        self.assertEqual(_linear_quantile([1.0, 2.0, 2.0, 3.0], 0.50), 2.0)
        self.assertEqual(_linear_quantile([1.0, 2.0, 2.0, 3.0], 0.75), 2.25)
        self.assertIsNone(_linear_quantile([], 0.5))
        with self.assertRaisesRegex(ValueError, "0 ile 1"):
            _linear_quantile([1.0, 2.0], 1.5)

    def test_role_benchmarks_reject_players_with_unreliable_data_statuses(self):
        players = [
            {
                "player_id": 1,
                "player_name": "Partial",
                "minutes_played": 700.0,
                "per90_metrics": {"passes_attempted": 30.0},
                "data_quality": {"status": "partial"},
                "data_consistency": {"status": "consistent"},
                "identity": {"status": "consistent"},
            },
            {
                "player_id": 2,
                "player_name": "Review",
                "minutes_played": 700.0,
                "per90_metrics": {"passes_attempted": 30.0},
                "data_quality": {"status": "complete"},
                "data_consistency": {"status": "review"},
                "identity": {"status": "consistent"},
            },
            {
                "player_id": 3,
                "player_name": "Identity Review",
                "minutes_played": 700.0,
                "per90_metrics": {"passes_attempted": 30.0},
                "data_quality": {"status": "complete"},
                "data_consistency": {"status": "consistent"},
                "identity": {"status": "review"},
            },
        ]
        result = build_role_benchmarks(
            {"CB": {"role_name": "Centre-back", "players": players}},
            minimum_verified_minutes=450,
            minimum_cohort_size=2,
        )
        cb = result["roles"]["CB"]
        self.assertEqual(cb["eligible_player_count"], 0)
        self.assertEqual(cb["cohort_status"], "insufficient_sample")
        reasons = {
            row["player_id"]: row["eligibility_reasons"] for row in cb["players"]
        }
        self.assertIn("data_quality_not_complete", reasons[1])
        self.assertIn("data_consistency_not_consistent", reasons[2])
        self.assertIn("identity_not_consistent", reasons[3])

    def test_role_benchmark_configuration_is_validated(self):
        with self.assertRaisesRegex(ValueError, "negatif veya geçersiz"):
            build_role_benchmarks({}, minimum_verified_minutes=-1)
        with self.assertRaisesRegex(ValueError, "en az 2"):
            build_role_benchmarks({}, minimum_cohort_size=1)

    def test_benchmark_metric_guidance_covers_all_metrics_without_assuming_higher_is_better(self):
        expected_metrics = {
            metric
            for metrics in ROLE_BENCHMARK_METRICS.values()
            for metric in metrics
        }
        self.assertEqual(set(BENCHMARK_METRIC_GUIDANCE), expected_metrics)

        required_fields = {
            "display_name", "unit", "directionality", "what_it_measures",
            "interpretation_note", "does_not_measure",
        }
        for metric, guidance in BENCHMARK_METRIC_GUIDANCE.items():
            with self.subTest(metric=metric):
                self.assertEqual(set(guidance), required_fields)
                self.assertTrue(all(
                    isinstance(value, str) and value.strip()
                    for value in guidance.values()
                ))
                self.assertIn(
                    guidance["directionality"],
                    {"context_dependent", "adverse_outcome_context_dependent"},
                )

        self.assertEqual(
            BENCHMARK_METRIC_GUIDANCE["goalkeeper_goals_conceded"]["directionality"],
            "adverse_outcome_context_dependent",
        )
        self.assertEqual(
            BENCHMARK_METRIC_GUIDANCE["goalkeeper_saves"]["directionality"],
            "context_dependent",
        )
        report = build_role_benchmarks({
            role: {"players": []} for role in ROLE_BENCHMARK_METRICS
        })
        self.assertEqual(report["metric_guidance"], BENCHMARK_METRIC_GUIDANCE)

    def test_player_evaluation_readiness_requires_core_evidence_and_reports_peer_context(self):
        role_profiles = {
            "CB": {
                "role_name": "Centre-back",
                "players": [
                    {
                        "player_id": 1,
                        "player_name": "Ready Player",
                        "minutes_played": 540.0,
                        "matches_with_appearance_evidence": 6,
                        "metrics": {"passes_attempted": 150},
                        "per90_metrics": {"passes_attempted": 25.0},
                        "data_quality": {
                            "status": "complete",
                            "checks": {"attributed_events": True},
                        },
                        "data_consistency": {"status": "consistent"},
                        "identity": {
                            "status": "consistent",
                            "possible_same_name_collision": False,
                        },
                    },
                    {
                        "player_id": 2,
                        "player_name": "Limited Player",
                        "minutes_played": 300.0,
                        "matches_with_appearance_evidence": 3,
                        "metrics": {"passes_attempted": 70},
                        "per90_metrics": {"passes_attempted": 21.0},
                        "data_quality": {
                            "status": "partial",
                            "checks": {"attributed_events": True},
                        },
                        "data_consistency": {"status": "review"},
                        "identity": {
                            "status": "consistent",
                            "possible_same_name_collision": True,
                        },
                    },
                    {
                        "player_id": 3,
                        "player_name": "No Event Evidence",
                        "minutes_played": None,
                        "matches_with_appearance_evidence": 0,
                        "metrics": {},
                        "per90_metrics": None,
                        "data_quality": {
                            "status": "insufficient",
                            "checks": {"attributed_events": False},
                        },
                        "data_consistency": {"status": "review"},
                        "identity": {"status": "review"},
                    },
                ],
            },
        }
        role_benchmarks = {
            "roles": {
                "CB": {
                    "players": [
                        {
                            "player_id": 1,
                            "eligible_for_peer_comparison": True,
                            "metrics": {
                                "passes_attempted": {
                                    "value_per90": 25.0,
                                    "cohort_size": 12,
                                    "percentile": 70.0,
                                    "status": "ready",
                                },
                                "clearances": {
                                    "value_per90": 3.0,
                                    "cohort_size": 4,
                                    "percentile": None,
                                    "status": "insufficient_sample",
                                },
                            },
                        },
                        {
                            "player_id": 2,
                            "eligible_for_peer_comparison": False,
                            "metrics": {},
                        },
                        {
                            "player_id": 3,
                            "eligible_for_peer_comparison": False,
                            "metrics": {},
                        },
                    ]
                }
            }
        }

        readiness = build_player_evaluation_readiness(
            role_profiles, role_benchmarks
        )
        cb = readiness["roles"]["CB"]
        ready = next(row for row in cb["players"] if row["player_id"] == 1)
        limited = next(row for row in cb["players"] if row["player_id"] == 2)
        insufficient = next(row for row in cb["players"] if row["player_id"] == 3)

        self.assertEqual(ready["readiness_status"], "ready_for_scout_review")
        self.assertEqual(ready["peer_context_status"], "available")
        self.assertEqual(ready["peer_percentiles_available"], ["passes_attempted"])
        self.assertEqual(ready["peer_metrics_available"], ["clearances", "passes_attempted"])

        self.assertEqual(limited["readiness_status"], "limited")
        self.assertIn("below_minimum_verified_minutes", limited["reason_codes"])
        self.assertIn("insufficient_appearance_sample", limited["reason_codes"])
        self.assertIn("data_quality_not_complete", limited["reason_codes"])
        self.assertIn("data_consistency_not_consistent", limited["reason_codes"])
        self.assertIn("possible_same_name_collision", limited["reason_codes"])
        self.assertEqual(limited["peer_context_status"], "not_eligible")

        self.assertEqual(insufficient["readiness_status"], "insufficient_data")
        self.assertIn("insufficient_event_evidence", insufficient["reason_codes"])
        self.assertIn("verified_minutes_unavailable", insufficient["reason_codes"])

        self.assertEqual(readiness["summary"]["player_role_records"], 3)
        self.assertEqual(readiness["summary"]["ready_for_scout_review"], 1)
        self.assertEqual(readiness["summary"]["limited"], 1)
        self.assertEqual(readiness["summary"]["insufficient_data"], 1)

    def test_readiness_distinguishes_missing_appearance_from_missing_events(self):
        role_profiles = {
            "CB": {
                "role_name": "Centre-back",
                "players": [{
                    "player_id": 20,
                    "player_name": "Event Without Appearance Evidence",
                    "minutes_played": 500.0,
                    "matches_with_appearance_evidence": 0,
                    "metrics": {"events": 4},
                    "per90_metrics": {"events": 0.72},
                    "data_quality": {
                        "status": "insufficient",
                        "checks": {
                            "appearance_evidence": False,
                            "attributed_events": True,
                        },
                    },
                    "data_consistency": {"status": "consistent"},
                    "identity": {
                        "status": "consistent",
                        "possible_same_name_collision": False,
                    },
                }],
            }
        }
        readiness = build_player_evaluation_readiness(role_profiles, {"roles": {}})
        player = readiness["roles"]["CB"]["players"][0]

        self.assertEqual(player["readiness_status"], "limited")
        self.assertIn("no_appearance_evidence", player["reason_codes"])
        self.assertNotIn("insufficient_event_evidence", player["reason_codes"])

    def test_player_can_be_ready_for_human_review_without_peer_percentiles(self):
        role_profiles = {
            "ST": {
                "role_name": "Striker",
                "players": [{
                    "player_id": 10,
                    "player_name": "Small Cohort Player",
                    "minutes_played": 600.0,
                    "matches_with_appearance_evidence": 7,
                    "metrics": {"shots": 15},
                    "per90_metrics": {"shots": 2.25},
                    "data_quality": {
                        "status": "complete",
                        "checks": {"attributed_events": True},
                    },
                    "data_consistency": {"status": "consistent"},
                    "identity": {
                        "status": "consistent",
                        "possible_same_name_collision": False,
                    },
                }],
            }
        }
        benchmarks = {
            "roles": {
                "ST": {
                    "players": [{
                        "player_id": 10,
                        "eligible_for_peer_comparison": True,
                        "metrics": {
                            "shots": {
                                "value_per90": 2.25,
                                "cohort_size": 4,
                                "percentile": None,
                                "status": "insufficient_sample",
                            }
                        },
                    }]
                }
            }
        }
        readiness = build_player_evaluation_readiness(role_profiles, benchmarks)
        player = readiness["roles"]["ST"]["players"][0]
        self.assertEqual(player["readiness_status"], "ready_for_scout_review")
        self.assertEqual(player["peer_context_status"], "insufficient_sample")
        self.assertEqual(player["peer_metrics_available"], ["shots"])
        self.assertEqual(player["peer_percentiles_available"], [])

    def test_player_evaluation_readiness_validates_sample_thresholds(self):
        with self.assertRaisesRegex(ValueError, "negatif veya geçersiz"):
            build_player_evaluation_readiness({}, {}, minimum_verified_minutes=-1)
        with self.assertRaisesRegex(ValueError, "en az 1"):
            build_player_evaluation_readiness({}, {}, minimum_appearances=0)

    def test_cache_json_records_content_hash(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            relative = "sample.json"
            file_path = root / relative
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_text(json.dumps([{"ok": True}]), encoding="utf-8")
            data, metadata = fetch_json(relative, root)
            self.assertEqual(data, [{"ok": True}])
            self.assertEqual(metadata["cache"], "hit")
            self.assertEqual(len(metadata["sha256"]), 64)


if __name__ == "__main__":
    unittest.main()
