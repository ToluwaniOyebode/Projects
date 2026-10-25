import csv
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "import_wyscout_events.py"


class WyscoutImporterTests(unittest.TestCase):
    def test_filters_rodri_and_exports_event_fields(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            source = root / "events.json"
            output = root / "out.csv"
            source.write_text(json.dumps([
                {
                    "matchId": 123, "matchPeriod": "1H", "minute": 12, "second": 34,
                    "player": {"name": "Rodri"}, "team": {"name": "Manchester City"},
                    "type": {"name": "Pass"}, "outcome": {"name": "Successful"},
                    "positions": [{"x": 40, "y": 50}, {"x": 70, "y": 35}],
                    "tags": [{"id": 1801}]
                },
                {
                    "matchId": 123, "matchPeriod": "1H", "minute": 13, "second": 0,
                    "player": {"name": "Opponent"}, "team": {"name": "Chelsea"},
                    "type": {"name": "Duel"}
                }
            ]), encoding="utf-8")
            result = subprocess.run(
                [sys.executable, str(SCRIPT), str(source), "--out", str(output)],
                capture_output=True, text=True, check=True
            )
            with output.open(encoding="utf-8", newline="") as f:
                rows = list(csv.DictReader(f))
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["player"], "Rodri")
            self.assertEqual(rows[0]["action"], "Pass")
            self.assertEqual(rows[0]["timestamp_seconds"], "754.000")
            self.assertEqual(rows[0]["start_x"], "40")
            self.assertIn("needs_video_match_and_action_verification", rows[0]["verification_status"])
            self.assertIn("Wrote 1 candidate events", result.stdout)

    def test_include_all_players_option(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            source = root / "events.json"
            output = root / "out.csv"
            source.write_text(json.dumps([
                {"matchPeriod": "2H", "minute": 52, "second": 0,
                 "player": {"name": "Opponent"}, "team": {"name": "Chelsea"},
                 "type": {"name": "Duel"}}
            ]), encoding="utf-8")
            subprocess.run(
                [sys.executable, str(SCRIPT), str(source), "--out", str(output),
                 "--include-all-players"],
                capture_output=True, text=True, check=True
            )
            with output.open(encoding="utf-8", newline="") as f:
                rows = list(csv.DictReader(f))
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["match_period"], "2")
            self.assertEqual(rows[0]["timestamp_seconds"], "3120.000")


if __name__ == "__main__":
    unittest.main()
