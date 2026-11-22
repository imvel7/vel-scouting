import unittest
from collections import Counter

from diagnose_event_map import canonical_event_paths, cross_summary, is_doc_path, summarize_categories


class EventMapHelperTests(unittest.TestCase):
    def test_categorical_field_prints_counts(self):
        summary = summarize_categories(Counter({"PASS": 3, "SHOT": 1}), max_distinct=5)
        self.assertEqual(summary, {"distinct": 2, "counts": {"PASS": 3, "SHOT": 1}})

    def test_high_cardinality_field_prints_only_distinct_count(self):
        counter = Counter({f"value-{i}": 1 for i in range(10)})
        summary = summarize_categories(counter, max_distinct=5)
        self.assertEqual(summary, {"distinct": 10, "counts": None})
        self.assertNotIn("value-1", repr(summary))

    def test_cross_summary_hides_wide_inner_fields(self):
        pairs = {"PASS": Counter({"OK": 2, "FAIL": 1}), "FOUL": Counter({f"x{i}": 1 for i in range(30)})}
        summary = cross_summary(pairs, max_inner=25)
        self.assertEqual(summary["PASS"], {"OK": 2, "FAIL": 1})
        self.assertEqual(summary["FOUL"], {"distinct": 30})

    def test_doc_path_excludes_dataset_archive_content(self):
        self.assertTrue(is_doc_path("README.md"))
        self.assertTrue(is_doc_path("docs/event_map.csv"))
        self.assertFalse(is_doc_path("Datasets/123/match.json"))
        self.assertFalse(is_doc_path("nested/Datasets/9/events.jsonl"))
        self.assertFalse(is_doc_path("Datasets.zip"))

    def test_mirror_copy_is_not_double_counted(self):
        # Same rule as the other Afriskaut probes: the nested .../Datasets/<id>/ copy is canonical.
        names = [
            "Datasets/Datasets/m1/events.jsonl", "Datasets/Datasets/m1/match.json",
            "DSL/m1/events.jsonl",
            "Datasets/Datasets/m2/events.jsonl",
            "DSL/m3/events.jsonl",
        ]
        chosen = canonical_event_paths(names)
        self.assertEqual(chosen, ["Datasets/Datasets/m1/events.jsonl",
                                  "Datasets/Datasets/m2/events.jsonl",
                                  "DSL/m3/events.jsonl"])


if __name__ == "__main__":
    unittest.main()
