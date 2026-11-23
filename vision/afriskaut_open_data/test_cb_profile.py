import unittest

from cb_profile import (
    METRIC_IDS,
    count_metrics,
    matching_metrics,
    per90,
    quartiles,
)


def ev(name, event_type, outcome=""):
    return {"event_name": name, "event_type": event_type, "event_outcome": outcome}


class DefinitionTests(unittest.TestCase):
    def test_metric_ids_are_unique(self):
        self.assertEqual(len(METRIC_IDS), len(set(METRIC_IDS)))

    def test_open_play_pass_is_not_confused_with_set_piece_delivery(self):
        self.assertIn("open_play_passes_attempted", matching_metrics(ev("PASS", "SHORT", "SUCCESSFUL")))
        for name in ("THROW_IN", "CORNER"):
            self.assertEqual(matching_metrics(ev(name, "SHORT", "SUCCESSFUL")), [])
            self.assertEqual(matching_metrics(ev(name, "LONG", "UNSUCCESSFUL")), [])

    def test_foul_committed_excludes_the_card_row(self):
        self.assertEqual(matching_metrics(ev("DEF_ACTIONS", "FOUL", "OWN_HALF")), ["fouls_committed"])
        self.assertEqual(matching_metrics(ev("CARD", "FOUL", "YELLOW")), ["yellow_cards"])
        self.assertEqual(matching_metrics(ev("CARD", "DISSENT", "RED")), ["red_cards"])

    def test_labelled_successful_is_a_subset_of_attempts(self):
        matched = matching_metrics(ev("DEF_ACTIONS", "TACKLE", "SUCCESSFUL"))
        self.assertEqual(sorted(matched), ["tackles", "tackles_labelled_successful"])
        self.assertEqual(matching_metrics(ev("DEF_ACTIONS", "TACKLE", "UNSUCCESSFUL")), ["tackles"])

    def test_key_pass_and_assist_count_as_attempts_not_as_labelled_successful(self):
        matched = matching_metrics(ev("PASS", "LONG", "KEY_PASS"))
        self.assertIn("open_play_passes_attempted", matched)
        self.assertIn("open_play_long_passes_attempted", matched)
        self.assertIn("key_pass_or_assist_labels", matched)
        self.assertNotIn("open_play_passes_labelled_successful", matched)

    def test_matching_is_case_and_whitespace_insensitive(self):
        self.assertEqual(matching_metrics(ev(" def_actions ", "interception ", "own_half")), ["interceptions"])

    def test_same_event_type_under_other_event_name_does_not_match(self):
        self.assertEqual(matching_metrics(ev("GK_ACTIONS", "INTERCEPTION")), [])
        self.assertEqual(matching_metrics(ev("POSSESSION", "FOUL")), [])


class CountTests(unittest.TestCase):
    def test_counts_unmapped_and_skips_substitutions(self):
        events = [
            ev("PASS", "SHORT", "SUCCESSFUL"), ev("PASS", "LONG", "UNSUCCESSFUL"),
            ev("DEF_ACTIONS", "CLEARANCE", "UNDER_PRESSURE"),
            ev("SHOT", "INSIDE_BOX", "ON_TARGET"),
            ev("SUBSTITUTION", "SUBSTITUTION", "free text"),
            {"event_type": "BLOCK"},
        ]
        counts, unmapped, considered = count_metrics(events)
        self.assertEqual(considered, 5)
        self.assertEqual(counts["open_play_passes_attempted"], 2)
        self.assertEqual(counts["clearances"], 1)
        self.assertEqual(counts["blocks"], 0)  # missing event_name must not match a DEF_ACTIONS metric
        self.assertEqual(unmapped[("SHOT", "INSIDE_BOX")], 1)
        self.assertEqual(unmapped[("<MISSING>", "BLOCK")], 1)

    def test_no_events_gives_zero_counts_not_none(self):
        counts, unmapped, considered = count_metrics([])
        self.assertTrue(all(v == 0 for v in counts.values()))
        self.assertEqual((len(unmapped), considered), (0, 0))


class RateTests(unittest.TestCase):
    def test_per90(self):
        self.assertEqual(per90(10, 5400), 10.0)
        self.assertEqual(per90(5, 2700), 10.0)
        self.assertEqual(per90(0, 5400), 0.0)

    def test_per90_is_none_without_usable_minutes(self):
        self.assertIsNone(per90(5, None))
        self.assertIsNone(per90(5, 0))

    def test_quartiles_need_a_minimum_cohort(self):
        self.assertIsNone(quartiles([1.0] * 9))
        summary = quartiles([float(i) for i in range(1, 11)])
        self.assertEqual(summary["n"], 10)
        self.assertEqual(set(summary), {"n", "p25", "median", "p75"})
        self.assertAlmostEqual(summary["median"], 5.5)


if __name__ == "__main__":
    unittest.main()
