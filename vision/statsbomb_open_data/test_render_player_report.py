import json
import sys
import tempfile
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from render_player_report import ReportError, load_report, render_player_report, write_report

class RendererTests(unittest.TestCase):
    def setUp(self):
        player = {"player_id": 7, "player_name": "Sample Player", "team_names": ["Example FC"], "positions_seen": ["Center Back"], "matches_listed_in_squads": 3, "matches_with_appearance_evidence": 3, "minutes_played": 270, "grouped_metrics": {"distribution": {"raw_counts": {"passes_attempted": 90, "passes_completed": 81}, "per90_counts": {"passes_attempted": 30.0, "passes_completed": 27.0}, "context_metrics": {"pass_completion_pct": 90.0}, "per90_by_score_state": {"leading": {"passes_attempted": 28.0}, "drawing": {"passes_attempted": 31.0}, "trailing": {"passes_attempted": 32.0}}}}, "score_state_context": {"per90_status": "validated", "minutes_status": "validated"}, "data_quality": {"status": "complete", "reasons": []}, "data_consistency": {"status": "consistent", "reasons": []}, "identity": {"status": "consistent", "possible_same_name_collision": False, "reasons": []}}
        self.report = {
            "report_type": "statsbomb_import_quality_and_event_profile",
            "generated_at": "2026-11-19",
            "source": {"name": "StatsBomb Open Data", "repository": "https://github.com/hudl/open-data", "attribution_required_for_shared_analysis": True, "usage_note": "Research prototype; no commercial licence."},
            "competition_season": {"competition_name": "Example Cup", "season_name": "2022"},
            "sample": {"available_matches_in_season_file": 64, "selected_match_count": 3, "selected_match_ids": [101, 102, 103], "event_count": 12000, "unique_players_listed_or_seen": 40, "event_players_missing_from_lineups": 0},
            "source_files": [{"path": "events/101.json", "sha256": "abc123", "bytes": 321}],
            "limitations": ["Selected sample only."],
            "role_profiles": {"CB": {"role_name": "Centre-back", "metric_groups": [{"code": "distribution", "label": "Distribution and progression", "description": "Recorded passing.", "count_metrics": ["passes_attempted"]}], "players": [player]}},
            "role_benchmarks": {
                "metric_guidance": {"passes_attempted": {"display_name": "Pass attempts"}},
                "roles": {"CB": {
                    "eligible_player_count": 12, "profile_player_count": 20,
                    "minimum_verified_minutes": 450, "minimum_cohort_size": 10,
                    "metric_summaries": {"passes_attempted": {"status": "ready", "eligible_values": 12, "minimum_required": 10}},
                    "players": [{"player_id": 7, "eligible_for_peer_comparison": True, "eligibility_reasons": [], "metrics": {
                        "passes_attempted": {"value_per90": 30.0, "cohort_size": 12, "percentile": 66.7, "difference_from_median_per90": 2.5, "within_cohort_middle_50_percent": True, "status": "ready"},
                        "passes_completed": {"value_per90": 27.0, "cohort_size": 8, "percentile": None, "status": "insufficient_sample"}
                    }}]
                }}
            },
            "player_evaluation_readiness": {"roles": {"CB": {"players": [{"player_id": 7, "readiness_status": "limited", "reason_codes": ["below-minimum-verified-minutes"], "peer_context_status": "available"}]}}}
        }

    def test_profile_includes_provenance_metrics_and_peer_data(self):
        result = render_player_report(self.report, "7", "CB")
        for text in ("Sample Player", "Pass attempts", "66.7", "insufficient_sample", "Selected sample only", "not a player rating"):
            self.assertIn(text.lower(), result.lower())

    def test_missing_values_stay_missing(self):
        player = self.report["role_profiles"]["CB"]["players"][0]
        player["minutes_played"] = None
        player["grouped_metrics"]["distribution"]["per90_counts"]["passes_attempted"] = None
        result = render_player_report(self.report, "7", "CB")
        self.assertIn("Verified minutes: —", result)
        self.assertIn("| Pass attempts | 90 | — |", result)

    def test_missing_peer_percentile_is_not_zero(self):
        result = render_player_report(self.report, "7", "CB")
        row = next(x for x in result.splitlines() if "| Passes completed | 27 | Not available |" in x)
        self.assertNotIn("0.0", row)

    def test_source_id_and_role_are_required(self):
        with self.assertRaises(ReportError): render_player_report(self.report, "Sample Player", "CB")
        with self.assertRaises(ReportError): render_player_report(self.report, "7", "GK")
        with self.assertRaises(ReportError): render_player_report(self.report, "7", "bad")

    def test_duplicate_player_id_fails_closed(self):
        rows = self.report["role_profiles"]["CB"]["players"]
        rows.append(dict(rows[0]))
        with self.assertRaises(ReportError): render_player_report(self.report, "7", "CB")

    def test_wrong_report_type_and_bad_json_rejected(self):
        with self.assertRaises(ReportError): render_player_report({"report_type": "other"}, "7", "CB")
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "bad.json"
            path.write_text("{bad", encoding="utf-8")
            with self.assertRaises(ReportError): load_report(path)

    def test_safe_write_overwrite_gate(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "player.md"
            write_report("first", path)
            with self.assertRaises(ReportError): write_report("second", path)
            write_report("second", path, True)
            self.assertEqual(path.read_text(encoding="utf-8"), "second\n")

if __name__ == "__main__":
    unittest.main()
