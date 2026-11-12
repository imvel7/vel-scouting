import unittest

from validate_dataset import compare_video_gsr_metadata, validate_bas_payload


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


    def test_detects_video_dimension_mismatch(self):
        video = {"width": 4096, "height": 1504, "fps": 25.0}
        gsr = {
            "image_dimensions": {"3840x1504": 67650},
            "declared_frame_rate": 25,
        }
        result = compare_video_gsr_metadata(video, gsr)
        self.assertFalse(result["metadata_matches"])
        self.assertEqual(result["declared_geometry"], "3840x1504")
        self.assertEqual(result["actual_geometry"], "4096x1504")

    def test_accepts_matching_video_metadata(self):
        video = {"width": 3840, "height": 1504, "fps": 25.0}
        gsr = {
            "image_dimensions": {"3840x1504": 67650},
            "declared_frame_rate": 25,
        }
        result = compare_video_gsr_metadata(video, gsr)
        self.assertTrue(result["metadata_matches"])
        self.assertEqual(result["warnings"], [])


if __name__ == "__main__":
    unittest.main()
