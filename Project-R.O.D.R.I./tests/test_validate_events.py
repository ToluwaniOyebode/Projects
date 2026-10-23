import csv
import tempfile
import unittest
from pathlib import Path
from validate_events import validate


class ValidateEventsTests(unittest.TestCase):
    def write_csv(self, content):
        tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".csv", newline="", encoding="utf-8", delete=False)
        tmp.write(content)
        tmp.close()
        self.addCleanup(Path(tmp.name).unlink, missing_ok=True)
        return tmp.name

    def test_valid_two_matches(self):
        path = self.write_csv(
            "match_id,timestamp_seconds,action,zone,pressure,ball_state\n"
            "m1,1,receive,midfield,low,controlled\n"
            "m1,2,short_pass,midfield,low,controlled\n"
            "m2,4,long_pass,defensive,high,loose\n"
        )
        result = validate(path)
        self.assertTrue(result["ok"])
        self.assertEqual(result["rows"], 3)
        self.assertEqual(result["matches"], 2)

    def test_missing_required_column(self):
        path = self.write_csv("match_id,action\nm1,receive\n")
        self.assertFalse(validate(path)["ok"])

    def test_negative_timestamp_fails(self):
        path = self.write_csv("match_id,timestamp_seconds,action\nm1,-1,receive\n")
        self.assertFalse(validate(path)["ok"])

    def test_empty_match_fails(self):
        path = self.write_csv("match_id,timestamp_seconds,action\n,1,receive\n")
        self.assertFalse(validate(path)["ok"])

    def test_unknown_action_warns_not_fails(self):
        path = self.write_csv("match_id,timestamp_seconds,action\nm1,1,foo_action\n")
        result = validate(path)
        self.assertTrue(result["ok"])
        self.assertTrue(any("unfamiliar action" in w for w in result["warnings"]))

    def test_duplicate_timestamps_warn(self):
        path = self.write_csv("match_id,timestamp_seconds,action\nm1,1,receive\nm1,1,short_pass\n")
        result = validate(path)
        self.assertTrue(result["ok"])
        self.assertTrue(any("duplicate timestamp" in w for w in result["warnings"]))


if __name__ == "__main__":
    unittest.main()
