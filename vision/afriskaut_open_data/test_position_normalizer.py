import unittest

from position_normalizer import normalize_position_labels


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


if __name__ == "__main__":
    unittest.main()
