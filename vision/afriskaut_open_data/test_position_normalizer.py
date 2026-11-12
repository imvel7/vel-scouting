import unittest

from position_normalizer import normalize_position_labels
from probe_dataset import compare_match_player_ids, extract_player_id


class PositionNormalizerTests(unittest.TestCase):
    def test_canonical_label(self):
        self.assertEqual(
            normalize_position_labels("Center Back"),
            (["Center Back"], []),
        )

    def test_python_list_string(self):
        self.assertEqual(
            normalize_position_labels("['Attacking Midfielder', 'Center Back']"),
            (["Attacking Midfielder", "Center Back"], []),
        )

    def test_truncated_list_string(self):
        self.assertEqual(
            normalize_position_labels("['Defensive Midfielder"),
            (["Defensive Midfielder"], []),
        )

    def test_goal_keeper_alias(self):
        self.assertEqual(
            normalize_position_labels("Goal Keeper"),
            (["Goalkeeper"], []),
        )

    def test_unknown_label_is_not_guessed(self):
        self.assertEqual(
            normalize_position_labels("Inverted Centre Half"),
            ([], ["Inverted Centre Half"]),
        )

    def test_list_input(self):
        self.assertEqual(
            normalize_position_labels(["Left Back", "Right Winger"]),
            (["Left Back", "Right Winger"], []),
        )


class MatchLineupLinkageTests(unittest.TestCase):
    def test_extracts_first_available_id(self):
        self.assertEqual(extract_player_id({"player_id": "p-1", "id": "p-2"}), "p-1")
        self.assertEqual(extract_player_id({"player_id": None, "id": "p-2"}), "p-2")

    def test_missing_id_returns_none(self):
        self.assertIsNone(extract_player_id({"name": "not exported"}))
        self.assertIsNone(extract_player_id({"player_id": "  "}))

    def test_compares_only_ids_from_the_same_match(self):
        self.assertEqual(
            compare_match_player_ids({"p-1", "p-2", "p-3"}, {"p-1", "p-3", "p-4"}),
            {"event_actor_ids": 3, "matched_actor_ids": 2, "unmatched_actor_ids": 1},
        )

    def test_empty_event_actor_set(self):
        self.assertEqual(
            compare_match_player_ids(set(), {"p-1"}),
            {"event_actor_ids": 0, "matched_actor_ids": 0, "unmatched_actor_ids": 0},
        )


if __name__ == "__main__":
    unittest.main()
