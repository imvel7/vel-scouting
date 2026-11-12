import csv
import json
import sys
import tempfile
import unittest
from argparse import Namespace
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
from import_open_data import analyse_match, build_cb_profile, fetch_json, run_import, ImportErrorWithContext


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


    def test_unused_squad_member_is_not_assumed_to_have_appeared(self):
        lineups = [{
            "team_id": 1,
            "team_name": "Argentina",
            "lineup": [
                {
                    "player_id": 10,
                    "player_name": "Example Player",
                    "positions": [{"position": "Center Attacking Midfield"}],
                },
                {
                    "player_id": 11,
                    "player_name": "Unused Substitute",
                    "positions": [],
                },
            ],
        }]
        report = analyse_match(MATCH, lineups, EVENTS)
        player = next(row for row in report["player_metrics"] if row["player_id"] == 11)
        self.assertFalse(player["appearance_evidence"])
        self.assertIsNone(player["minutes_played"])

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


    def test_run_import_writes_json_report_and_player_csv(self):
        def fake_fetch_json(relative_path, cache_root, force=False):
            metadata = {
                "path": relative_path,
                "cache": "fixture",
                "bytes": 100,
                "sha256": "a" * 64,
                "url": "https://example.invalid/" + relative_path,
            }
            if relative_path == "competitions.json":
                return [{
                    "competition_id": 43,
                    "season_id": 106,
                    "competition_name": "FIFA World Cup",
                    "season_name": "2022",
                    "competition_gender": "male",
                    "competition_youth": False,
                }], metadata
            if relative_path == "matches/43/106.json":
                return [MATCH], metadata
            if relative_path == "lineups/123.json":
                return LINEUPS, metadata
            if relative_path == "events/123.json":
                return EVENTS, metadata
            raise AssertionError("Unexpected source path: " + relative_path)

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            args = Namespace(
                competition_id=43,
                season_id=106,
                match_id=None,
                limit=1,
                data_root=str(root / "raw"),
                report=str(root / "reports" / "report.json"),
                force=False,
            )
            with patch("import_open_data.fetch_json", side_effect=fake_fetch_json):
                report = run_import(args)

            json_path = Path(report["output_files"]["json"])
            csv_path = Path(report["output_files"]["players_csv"])
            self.assertTrue(json_path.exists())
            self.assertTrue(csv_path.exists())
            self.assertEqual(report["competition_season"]["competition_name"], "FIFA World Cup")
            self.assertEqual(report["competition_season"]["season_name"], "2022")
            self.assertEqual(report["sample"]["event_count"], len(EVENTS))
            self.assertEqual(report["sample"]["selected_match_count"], 1)

            with csv_path.open(encoding="utf-8-sig", newline="") as stream:
                rows = list(csv.DictReader(stream))
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["player_name"], "Example Player")
            self.assertEqual(rows[0]["passes_attempted"], "2")
            self.assertEqual(rows[0]["pass_completion_pct"], "50.0")


    def test_cb_profile_selects_centre_backs_without_creating_a_rating(self):
        players = [
            {
                "player_id": 20572,
                "player_name": "Example Centre Back",
                "team_names": ["Argentina"],
                "positions_seen": ["Right Center Back"],
                "matches_listed_in_squads": 3,
                "matches_with_appearance_evidence": 3,
                "metrics": {
                    "passes_attempted": 30,
                    "passes_completed": 27,
                    "pass_completion_pct": 90.0,
                    "pass_length_mean": 22.4,
                    "carries": 6,
                    "pressures": 9,
                    "interceptions": 4,
                    "ball_recoveries": 5,
                    "clearances": 7,
                    "blocks": 2,
                    "tackles": 3,
                },
            },
            {
                "player_id": 5503,
                "player_name": "Example Forward",
                "team_names": ["Argentina"],
                "positions_seen": ["Right Center Forward"],
                "matches_listed_in_squads": 3,
                "matches_with_appearance_evidence": 3,
                "metrics": {"passes_attempted": 20},
            },
        ]
        profile = build_cb_profile(players)
        self.assertEqual(profile["role_code"], "CB")
        self.assertEqual(profile["player_count"], 1)
        selected = profile["players"][0]
        self.assertEqual(selected["player_id"], 20572)
        self.assertEqual(selected["matches_with_appearance_evidence"], 3)
        self.assertIsNone(selected["minutes_played"])
        self.assertNotIn("rating", selected)
        self.assertIn("defensive rating or ranking", profile["interpretation_limits"][0])

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
