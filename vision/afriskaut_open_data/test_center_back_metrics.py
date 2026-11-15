import unittest

from center_back_metrics import aggregate_center_back_match


class CenterBackMetricsTests(unittest.TestCase):
    def setUp(self):
        self.match = {
            "home_team_line_up": [
                {"player_id": "cb-1", "player_position": "Center Back"},
                {"player_id": "fb-1", "player_position": "Left Back"},
            ],
            "away_team_line_up": [
                {"player_id": "cb-2", "player_position": "Center Back,Defender"},
            ],
        }

    def test_counts_only_linked_events_for_explicit_center_backs(self):
        events = [
            {"player_id": "cb-1", "event_name": "CLEARANCE", "event_type": "DEFENSIVE_ACTION"},
            {"player_id": "cb-1", "event_name": "PASS", "event_type": "PASS"},
            {"player_id": "cb-2", "event_name": "INTERCEPTION", "event_type": "INTERCEPTION"},
            {"player_id": "fb-1", "event_name": "TACKLE"},
            {"player_id": "unknown", "event_name": "CLEARANCE"},
            {"player_id": "cb-1", "event_type": "TEAM_OWN_GOAL", "event_name": "OWN_GOAL"},
        ]
        result = aggregate_center_back_match(self.match, events)
        self.assertEqual(result["center_back_lineup_players"], 2)
        self.assertEqual(result["center_back_players_with_eligible_events"], 2)
        self.assertEqual(result["center_back_eligible_event_rows"], 3)
        self.assertEqual(
            result["event_name_counts"],
            {"CLEARANCE": 1, "INTERCEPTION": 1, "PASS": 1},
        )
        self.assertEqual(
            result["event_type_counts"],
            {"DEFENSIVE_ACTION": 1, "INTERCEPTION": 1, "PASS": 1},
        )

    def test_multirole_center_back_is_included(self):
        result = aggregate_center_back_match(
            self.match,
            [{"player_id": "cb-2", "event_name": "DUEL"}],
        )
        self.assertEqual(result["event_name_counts"], {"DUEL": 1})

    def test_unrecognized_or_missing_roles_are_not_guessed(self):
        match = {
            "home_team_line_up": [
                {"player_id": "p1", "player_position": "Defender"},
                {"player_id": "p2"},
            ]
        }
        result = aggregate_center_back_match(
            match,
            [
                {"player_id": "p1", "event_name": "CLEARANCE"},
                {"player_id": "p2", "event_name": "TACKLE"},
            ],
        )
        self.assertEqual(result["center_back_lineup_players"], 0)
        self.assertEqual(result["center_back_eligible_event_rows"], 0)

    def test_substitute_without_explicit_center_back_role_is_not_included(self):
        match = {
            "home_team_line_up": [
                {"player_id": "cb-1", "player_position": "Center Back"}
            ],
            "home_team_subs": [{"player_in": {"player_id": "sub-1"}}],
        }
        result = aggregate_center_back_match(
            match,
            [{"player_id": "sub-1", "event_name": "CLEARANCE"}],
        )
        self.assertEqual(result["center_back_eligible_event_rows"], 0)


if __name__ == "__main__":
    unittest.main()
