import unittest

from diagnose_match_timing import SchemaStats, string_shape


class SchemaStatsTests(unittest.TestCase):
    def test_string_shape_hides_real_text(self):
        self.assertEqual(string_shape("45:00+2 Half"), "99:99+9 aaaa")
        self.assertNotIn("Half", string_shape("45:00+2 Half"))

    def test_collects_paths_types_and_numeric_range(self):
        stats = SchemaStats()
        stats.add({"minute": 10, "lineup": [{"player_id": "p1", "start_minute": 0}]})
        stats.add({"minute": 90, "lineup": [{"player_id": "p2", "start_minute": 46}]})
        summary = stats.summary()
        self.assertEqual(summary["root.minute"]["numeric"]["min"], 10.0)
        self.assertEqual(summary["root.minute"]["numeric"]["max"], 90.0)
        self.assertEqual(summary["root.lineup[].start_minute"]["numeric"]["max"], 46.0)
        self.assertEqual(summary["root.lineup"]["types"], {"array": 2})

    def test_never_exports_values_of_blocked_or_non_timing_string_fields(self):
        stats = SchemaStats()
        stats.add({"player_id": "SECRET-ID-1", "team_name": "Secret FC", "kickoff_time": "15:30", "notes": "free text"})
        text = repr(stats.summary())
        for secret in ("SECRET-ID-1", "Secret FC", "free text"):
            self.assertNotIn(secret, text)
        self.assertIn("99:99", text)

    def test_booleans_are_not_treated_as_numbers(self):
        stats = SchemaStats()
        stats.add({"is_starter": True})
        self.assertNotIn("numeric", stats.summary()["root.is_starter"])


if __name__ == "__main__":
    unittest.main()
