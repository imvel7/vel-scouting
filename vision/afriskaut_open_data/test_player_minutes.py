import unittest

from diagnose_minutes_feasibility import match_clock
from player_minutes import (
    STATUS_DERIVED,
    STATUS_NOT_USED,
    STATUS_UNAVAILABLE,
    STATUS_VERIFIED,
    compute_match_minutes,
    played_seconds,
)

# Kick-off 00:05:00, first half to 00:50:00, second half 01:05:00 to 01:50:00 -> 45 + 45 played minutes.
CLOCK = {
    "match_start_time": "00:05:00",
    "first_half_end_time": "00:50:00",
    "second_half_start_time": "01:05:00",
    "match_end_time": "01:50:00",
}
TOTAL = 5400


def person(pid):
    return {"player_id": pid}


def make_match(**overrides):
    match = {
        **CLOCK,
        "home_team_line_up": [person("S1"), person("S2"), person("S3")],
        "home_team_subs": [person("B1"), person("B2"), person("B3")],
        "home_substitutions": [],
    }
    match.update(overrides)
    return match


def sub_event(pid, time):
    return {"player_id": pid, "event_type": "SUBSTITUTION", "event_start_time": time}


def action(pid, time):
    return {"player_id": pid, "event_type": "PASS", "event_start_time": time}


def swap(in_id, out_id):
    return {"in": person(in_id), "out": person(out_id)}


class PlayedSecondsTests(unittest.TestCase):
    def setUp(self):
        self.clock = match_clock(CLOCK)

    def test_break_is_excluded_and_boundaries_hold(self):
        self.assertEqual(played_seconds(5 * 60, self.clock), 0)
        self.assertEqual(played_seconds(50 * 60, self.clock), 2700)
        self.assertEqual(played_seconds(57 * 60, self.clock), 2700)  # half-time break
        self.assertEqual(played_seconds(65 * 60, self.clock), 2700)
        self.assertEqual(played_seconds(80 * 60, self.clock), 2700 + 900)
        self.assertEqual(played_seconds(110 * 60, self.clock), TOTAL)

    def test_outside_match_is_none(self):
        self.assertIsNone(played_seconds(4 * 60, self.clock))
        self.assertIsNone(played_seconds(111 * 60, self.clock))
        self.assertIsNone(played_seconds(None, self.clock))


class MinutesTests(unittest.TestCase):
    def test_starter_without_exit_is_derived_not_verified(self):
        result = compute_match_minutes(make_match(), [action("S1", "00:20:00")])
        record = result["players"]["S1"]
        self.assertEqual(result["total_played_seconds"], TOTAL)
        self.assertEqual(record["minutes_seconds"], TOTAL)
        self.assertEqual(record["status"], STATUS_DERIVED)
        self.assertIn("red_card_or_injury_without_substitution_not_detectable", record["reasons"])

    def test_substitution_gives_both_players_verified_minutes(self):
        match = make_match(home_substitutions=[swap("B1", "S2")])
        events = [action("S2", "00:30:00"), sub_event("S2", "01:20:00"), action("B1", "01:30:00")]
        players = compute_match_minutes(match, events)["players"]
        self.assertEqual(players["S2"]["minutes_seconds"], 3600)  # 45 min + 15 min after the break
        self.assertEqual(players["S2"]["status"], STATUS_VERIFIED)
        self.assertEqual(players["B1"]["minutes_seconds"], TOTAL - 3600)
        self.assertEqual(players["B1"]["status"], STATUS_VERIFIED)

    def test_actor_may_be_the_player_coming_on(self):
        match = make_match(home_substitutions=[swap("B1", "S2")])
        players = compute_match_minutes(match, [sub_event("B1", "01:20:00")])["players"]
        self.assertEqual(players["S2"]["minutes_seconds"], 3600)
        self.assertEqual(players["B1"]["minutes_seconds"], TOTAL - 3600)

    def test_half_time_substitution_uses_end_of_first_half(self):
        match = make_match(home_substitutions=[swap("B1", "S2")])
        players = compute_match_minutes(match, [sub_event("S2", "00:57:00")])["players"]
        self.assertEqual(players["S2"]["minutes_seconds"], 2700)
        self.assertEqual(players["B1"]["minutes_seconds"], 2700)

    def test_listed_substitution_without_event_gives_no_minutes_for_either_player(self):
        match = make_match(home_substitutions=[swap("B1", "S2")])
        players = compute_match_minutes(match, [action("S2", "00:30:00")])["players"]
        for pid in ("S2", "B1"):
            self.assertIsNone(players[pid]["minutes_seconds"])
            self.assertEqual(players[pid]["status"], STATUS_UNAVAILABLE)
            self.assertIn("no_substitution_event_for_listed_substitution", players[pid]["reasons"])

    def test_conflicting_event_times_are_not_averaged(self):
        match = make_match(home_substitutions=[swap("B1", "S2")])
        events = [sub_event("S2", "01:20:00"), sub_event("B1", "01:25:00")]
        players = compute_match_minutes(match, events)["players"]
        self.assertIsNone(players["S2"]["minutes_seconds"])
        self.assertIn("conflicting_substitution_event_times", players["S2"]["reasons"])

    def test_same_time_from_both_actors_is_accepted(self):
        match = make_match(home_substitutions=[swap("B1", "S2")])
        events = [sub_event("S2", "01:20:00"), sub_event("B1", "01:20:00")]
        players = compute_match_minutes(match, events)["players"]
        self.assertEqual(players["S2"]["minutes_seconds"], 3600)

    def test_substitution_event_for_unlisted_actor_blocks_that_player(self):
        players = compute_match_minutes(make_match(), [sub_event("S3", "01:10:00")])["players"]
        self.assertIsNone(players["S3"]["minutes_seconds"])
        self.assertIn("substitution_event_not_in_listed_substitutions", players["S3"]["reasons"])
        # An unexplained substitution event means other starters' exits cannot be excluded either.
        self.assertEqual(players["S1"]["status"], STATUS_UNAVAILABLE)
        self.assertEqual(players["S1"]["reasons"], ["starter_exit_cannot_be_excluded_match_records_incomplete"])

    def test_events_after_computed_exit_block_minutes(self):
        match = make_match(home_substitutions=[swap("B1", "S2")])
        events = [sub_event("S2", "01:20:00"), action("S2", "01:40:00")]
        record = compute_match_minutes(match, events)["players"]["S2"]
        self.assertIsNone(record["minutes_seconds"])
        self.assertEqual(record["reasons"], ["events_outside_computed_interval"])
        self.assertEqual(record["events_outside_interval"], 1)

    def test_events_within_tolerance_of_boundary_are_accepted(self):
        match = make_match(home_substitutions=[swap("B1", "S2")])
        events = [sub_event("S2", "01:20:00"), action("S2", "01:20:05")]
        self.assertEqual(compute_match_minutes(match, events)["players"]["S2"]["minutes_seconds"], 3600)
        strict = compute_match_minutes(match, events, tolerance=0)["players"]["S2"]
        self.assertIsNone(strict["minutes_seconds"])

    def test_substitute_events_before_entry_block_minutes(self):
        match = make_match(home_substitutions=[swap("B1", "S2")])
        events = [sub_event("S2", "01:20:00"), action("B1", "00:30:00")]
        self.assertIsNone(compute_match_minutes(match, events)["players"]["B1"]["minutes_seconds"])

    def test_unused_bench_is_zero_only_without_events(self):
        players = compute_match_minutes(make_match(), [])["players"]
        self.assertEqual(players["B3"]["minutes_seconds"], 0)
        self.assertEqual(players["B3"]["status"], STATUS_NOT_USED)
        players = compute_match_minutes(make_match(), [action("B3", "00:30:00")])["players"]
        self.assertIsNone(players["B3"]["minutes_seconds"])
        self.assertIn("events_without_listed_appearance", players["B3"]["reasons"])

    def test_player_in_two_substitutions_is_ambiguous(self):
        match = make_match(home_substitutions=[swap("B1", "S1"), swap("B2", "B1")])
        events = [sub_event("S1", "00:40:00"), sub_event("B2", "01:20:00")]
        players = compute_match_minutes(match, events)["players"]
        for pid in ("S1", "B1", "B2"):
            self.assertIsNone(players[pid]["minutes_seconds"], pid)

    def test_unknown_actor_not_in_squad_lists(self):
        players = compute_match_minutes(make_match(), [action("X9", "00:20:00")])["players"]
        self.assertEqual(players["X9"]["reasons"], ["not_in_squad_lists"])

    def test_clean_match_is_flagged_consistent(self):
        result = compute_match_minutes(make_match(), [action("S1", "00:20:00")])
        self.assertTrue(result["substitution_records_consistent"])

    def test_bench_player_with_events_but_no_listing_blocks_derived_starters(self):
        result = compute_match_minutes(make_match(), [action("B2", "01:00:00"), action("S1", "00:20:00")])
        self.assertFalse(result["substitution_records_consistent"])
        self.assertEqual(result["players"]["S1"]["status"], STATUS_UNAVAILABLE)
        self.assertEqual(result["players"]["B2"]["reasons"], ["events_without_listed_appearance"])

    def test_verified_players_survive_other_defects_in_the_match(self):
        match = make_match(home_substitutions=[swap("B1", "S2")])
        events = [sub_event("S2", "01:20:00"), action("B3", "01:00:00")]
        players = compute_match_minutes(match, events)["players"]
        self.assertEqual(players["S2"]["status"], STATUS_VERIFIED)
        self.assertEqual(players["B1"]["status"], STATUS_VERIFIED)
        self.assertEqual(players["S1"]["status"], STATUS_UNAVAILABLE)

    def test_unusable_match_clock_gives_no_minutes_at_all(self):
        result = compute_match_minutes(make_match(second_half_start_time=""), [action("S1", "00:20:00")])
        self.assertIsNone(result["total_played_seconds"])
        self.assertTrue(all(r["minutes_seconds"] is None for r in result["players"].values()))
        self.assertEqual(result["players"]["S1"]["reasons"], ["match_clock_unusable"])

    def test_substitution_outside_match_clock_is_rejected(self):
        match = make_match(home_substitutions=[swap("B1", "S2")])
        record = compute_match_minutes(match, [sub_event("S2", "02:30:00")])["players"]["S2"]
        self.assertEqual(record["reasons"], ["substitution_time_outside_match_clock"])

    def test_incomplete_substitution_entry_blocks_named_player(self):
        match = make_match(home_substitutions=[{"in": person("B1"), "out": {}}])
        self.assertIsNone(compute_match_minutes(match, [])["players"]["B1"]["minutes_seconds"])

    def test_starter_also_listed_as_substitute_in_is_blocked(self):
        match = make_match(home_substitutions=[swap("S1", "S2")])
        players = compute_match_minutes(match, [sub_event("S2", "01:20:00")])["players"]
        self.assertIn("starter_listed_as_substitute_in", players["S1"]["reasons"])


if __name__ == "__main__":
    unittest.main()
