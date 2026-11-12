import unittest

from validate_dataset import validate_bas_payload


class BasValidationTests(unittest.TestCase):
    def test_accepts_actions_and_uppercase_labels(self):
        payload = {
            "actions": [
                {"gameTime": "1 - 00:10", "position": "10000", "label": "PASS"},
                {"gameTime": "1 - 00:20", "position": "20000", "label": "HIGH PASS"},
            ]
        }
        result = validate_bas_payload(payload)
        self.assertTrue(result["ok"])
        self.assertEqual(result["events"], 2)
        self.assertEqual(result["labels"]["Pass"], 1)
        self.assertEqual(result["labels"]["High Pass"], 1)

    def test_accepts_annotations_key(self):
        payload = {
            "annotations": [
                {"gameTime": "2 - 00:10", "position": "2700000", "label": "Goal"}
            ]
        }
        result = validate_bas_payload(payload)
        self.assertTrue(result["ok"])
        self.assertEqual(result["labels"]["Goal"], 1)

    def test_flags_unknown_labels(self):
        payload = {
            "actions": [
                {"gameTime": "1 - 00:10", "position": "10000", "label": "Unknown Event"}
            ]
        }
        result = validate_bas_payload(payload)
        self.assertFalse(result["ok"])
        self.assertIn("Unknown Event", result["unknown_labels"])

    def test_flags_invalid_positions(self):
        payload = {
            "actions": [
                {"gameTime": "1 - 00:10", "position": "not-a-number", "label": "Pass"}
            ]
        }
        result = validate_bas_payload(payload)
        self.assertFalse(result["ok"])
        self.assertTrue(any("position" in error for error in result["errors"]))


if __name__ == "__main__":
    unittest.main()
