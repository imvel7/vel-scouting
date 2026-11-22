import unittest

from diagnose_minutes_feasibility import (
    actor_side,
    classify_window,
    compare_counts,
    match_clock,
    parse_hms,
    substitution_pairs,
)

GOOD = {
    "match_start_time": "00:05:00",
    "first_half_end_time": "00:50:30",
    "second_half_start_time": "01:06:00",
    "match_end_time": "01:55:10",
}


class ParseTests(unittest.TestCase):
    def test_parse_hms(self):
        self.assertEqual(parse_hms("01:02:03"), 3723)
        self.assertEqual(parse_hms("00:00:00.500"), 0)
        for bad in ("", None, "12:61:00", "ab:cd:ef", 5, "1:2"):
            self.assertIsNone(parse_hms(bad))

    def test_match_clock_complete_and_ordered(self):
        clock = match_clock(GOOD)
        self.assertTrue(clock["complete"] and clock["ordered"])

    def test_match_clock_missing_field_is_never_filled(self):
        clock = match_clock({**GOOD, "second_half_start_time": ""})
        self.assertFalse(clock["complete"])
        self.assertFalse(clock["ordered"])
        self.assertIsNone(clock["second_half_start_time"])

    def test_match_clock_out_of_order(self):
        clock = match_clock({**GOOD, "first_half_end_time": "02:00:00"})
        self.assertTrue(clock["complete"])
        self.assertFalse(clock["ordered"])


class WindowTests(unittest.TestCase):
    def setUp(self):
        self.clock = match_clock(GOOD)

    def test_windows_and_inclusive_boundaries(self):
        c = self.clock
        self.assertEqual(classify_window(parse_hms("00:04:59"), c), "before_start")
        self.assertEqual(classify_window(parse_hms("00:05:00"), c), "first_half")
        self.assertEqual(classify_window(parse_hms("00:50:30"), c), "first_half")
        self.assertEqual(classify_window(parse_hms("00:55:00"), c), "break")
        self.assertEqual(classify_window(parse_hms("01:06:00"), c), "second_half")
        self.assertEqual(classify_window(parse_hms("01:55:10"), c), "second_half")
        self.assertEqual(classify_window(parse_hms("01:55:11"), c), "after_end")

    def test_unknown_when_clock_or_time_unusable(self):
        self.assertEqual(classify_window(None, self.clock), "unknown")
        self.assertEqual(classify_window(100, match_clock({})), "unknown")


class SubstitutionTests(unittest.TestCase):
    def test_pairs_from_home_away_and_combined_lists(self):
        match = {
            "home_substitutions": [{"in": {"player_id": "a"}, "out": {"player_id": "b"}}],
            "away_substitutions": [{"in": {"player_id": "c"}, "out": {"player_id": "d"}}, "junk"],
            "substitutions": [],
        }
        count, ins, outs = substitution_pairs(match)
        self.assertEqual((count, ins, outs), (2, {"a", "c"}, {"b", "d"}))

    def test_actor_side(self):
        ins, outs = {"a", "x"}, {"b", "x"}
        self.assertEqual(actor_side("a", ins, outs), "player_in")
        self.assertEqual(actor_side("b", ins, outs), "player_out")
        self.assertEqual(actor_side("x", ins, outs), "in_and_out")
        self.assertEqual(actor_side("z", ins, outs), "not_listed")
        self.assertEqual(actor_side(None, ins, outs), "no_actor")
        self.assertEqual(actor_side("  ", ins, outs), "no_actor")

    def test_compare_counts(self):
        self.assertEqual(compare_counts(3, 3), "equal")
        self.assertEqual(compare_counts(6, 3), "events_exactly_double")
        self.assertEqual(compare_counts(4, 3), "events_more")
        self.assertEqual(compare_counts(2, 3), "events_fewer")
        self.assertEqual(compare_counts(0, 0), "equal")
        self.assertEqual(compare_counts(2, 0), "events_more")


if __name__ == "__main__":
    unittest.main()
