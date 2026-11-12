import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from import_open_data import analyse_match, fetch_json, ImportErrorWithContext


MATCH = {
    "match_id": 123,
    "match_date": "2022-12-18",
    "competition": {"competition_name": "FIFA World Cup"},
    "season": {"season_name": "2022"},
    "home_team": {"home_team_name": "Argentina"},
    "away_team": {"away_team_name": "France"},
    "home_score": 3,
    "away_score": 3,
}

LINEUPS = [
    {
        "team_id": 1,
        "team_name": "Argentina",
        "lineup": [{
            "player_id": 10,
            "player_name": "Example Player",
            "player_nickname": "Example",
            "jersey_number": 10,
            "positions": [{"position": "Center Attacking Midfield"}],
        }],
    }
]

EVENTS = [
    {
        "id": "1", "type": {"name": "Pass"},
        "player": {"id": 10, "name": "Example Player"},
        "team": {"id": 1, "name": "Argentina"},
        "pass": {"length": 15.0},
    },
    {
        "id": "2", "type": {"name": "Pass"},
        "player": {"id": 10, "name": "Example Player"},
        "team": {"id": 1, "name": "Argentina"},
        "pass": {"length": 20.0, "outcome": {"name": "Incomplete"}},
    },
    {
        "id": "3", "type": {"name": "Carry"},
        "player": {"id": 10, "name": "Example Player"},
        "team": {"id": 1, "name": "Argentina"},
        "carry": {"end_location": [50, 40]},
    },
    {
        "id": "4", "type": {"name": "Shot"},
        "player": {"id": 10, "name": "Example Player"},
        "team": {"id": 1, "name": "Argentina"},
        "shot": {
            "statsbomb_xg": 0.42,
            "outcome": {"name": "Goal"},
        },
    },
    {
        "id": "5", "type": {"name": "Pressure"},
        "player": {"id": 10, "name": "Example Player"},
        "team": {"id": 1, "name": "Argentina"},
    },
    {
        "id": "6", "type": {"name": "Half Start"},
        "team": {"id": 1, "name": "Argentina"},
    },
]


class StatsBombImportTests(unittest.TestCase):
    def test_counts_events_and_pass_success_using_statsbomb_rule(self):
        report = analyse_match(MATCH, LINEUPS, EVENTS)
        player = report["player_metrics"][0]
        self.assertEqual(player["metrics"]["passes_attempted"], 2)
        self.assertEqual(player["metrics"]["passes_completed"], 1)
        self.assertEqual(player["metrics"]["pass_completion_pct"], 50.0)
        self.assertEqual(player["metrics"]["pass_length_mean"], 17.5)

    def test_counts_carry_shot_goal_xg_and_pressure(self):
        report = analyse_match(MATCH, LINEUPS, EVENTS)
        metrics = report["player_metrics"][0]["metrics"]
        self.assertEqual(metrics["carries"], 1)
        self.assertEqual(metrics["shots"], 1)
        self.assertEqual(metrics["goals"], 1)
        self.assertEqual(metrics["xg"], 0.42)
        self.assertEqual(metrics["pressures"], 1)

    def test_does_not_fabricate_per90_without_minutes(self):
        report = analyse_match(MATCH, LINEUPS, EVENTS)
        player = report["player_metrics"][0]
        self.assertIsNone(player["minutes_played"])
        self.assertIsNone(player["per90_metrics"])

    def test_structural_events_without_player_are_not_counted_as_unattributed(self):
        report = analyse_match(MATCH, LINEUPS, EVENTS)
        self.assertEqual(report["quality"]["unattributed_non_structural_events"], 0)

    def test_unknown_player_in_events_is_preserved_and_flagged(self):
        events = EVENTS + [{
            "id": "7", "type": {"name": "Interception"},
            "player": {"id": 77, "name": "Unexpected Player"},
            "team": {"id": 1, "name": "Argentina"},
        }]
        report = analyse_match(MATCH, LINEUPS, events)
        ids = {str(row["player_id"]) for row in report["player_metrics"]}
        self.assertIn("77", ids)
        self.assertTrue(any("lineup dosyasında yok" in warning
                            for warning in report["quality"]["warnings"]))

    def test_invalid_events_root_is_rejected(self):
        with self.assertRaises(ImportErrorWithContext):
            analyse_match(MATCH, LINEUPS, {"not": "a list"})

    def test_cache_json_records_content_hash(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            relative = "sample.json"
            file_path = root / relative
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_text(json.dumps([{"ok": True}]), encoding="utf-8")
            data, metadata = fetch_json(relative, root)
            self.assertEqual(data, [{"ok": True}])
            self.assertEqual(metadata["cache"], "hit")
            self.assertEqual(len(metadata["sha256"]), 64)


if __name__ == "__main__":
    unittest.main()
