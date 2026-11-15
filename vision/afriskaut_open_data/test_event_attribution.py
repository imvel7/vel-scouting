import unittest

from event_attribution import classify_event_attribution


class EventAttributionTests(unittest.TestCase):
    def test_lineup_linked_actor_is_player_attributed(self):
        result = classify_event_attribution(
            {"player_id": "p-1", "event_type": "PASS"},
            {"p-1", "p-2"},
            set(),
        )
        self.assertEqual(result.scope, "player")
        self.assertTrue(result.player_metrics_eligible)
        self.assertEqual(result.reason, "matched_same_match_lineup_or_substitution")

    def test_substitute_is_player_attributed(self):
        result = classify_event_attribution(
            {"player_id": "p-sub", "event_type": "PASS"},
            set(),
            {"p-sub"},
        )
        self.assertEqual(result.scope, "player")
        self.assertTrue(result.player_metrics_eligible)

    def test_team_own_goal_is_never_player_metric_evidence(self):
        result = classify_event_attribution(
            {"player_id": "p-1", "event_type": "TEAM_OWN_GOAL"},
            {"p-1"},
            set(),
        )
        self.assertEqual(result.scope, "team")
        self.assertFalse(result.player_metrics_eligible)
        self.assertEqual(result.reason, "team_level_event_type")

    def test_unmatched_actor_is_unverified(self):
        result = classify_event_attribution(
            {"player_id": "p-unknown", "event_type": "PASS"},
            {"p-1"},
            {"p-2"},
        )
        self.assertEqual(result.scope, "unverified")
        self.assertFalse(result.player_metrics_eligible)
        self.assertEqual(result.reason, "player_id_not_linked_to_same_match")

    def test_missing_player_id_is_unattributed(self):
        result = classify_event_attribution(
            {"event_type": "SHOT"},
            {"p-1"},
            {"p-2"},
        )
        self.assertEqual(result.scope, "unattributed")
        self.assertFalse(result.player_metrics_eligible)
        self.assertEqual(result.reason, "missing_player_id")

    def test_whitespace_and_id_type_are_normalized(self):
        result = classify_event_attribution(
            {"player_id": 123, "event_type": "pass"},
            {" 123 "},
            set(),
        )
        self.assertEqual(result.scope, "player")
        self.assertTrue(result.player_metrics_eligible)

    def test_team_own_goal_rule_is_case_insensitive(self):
        result = classify_event_attribution(
            {"player_id": "p-1", "event_type": "team_own_goal"},
            set(),
            {"p-1"},
        )
        self.assertEqual(result.scope, "team")
        self.assertFalse(result.player_metrics_eligible)


if __name__ == "__main__":
    unittest.main()
