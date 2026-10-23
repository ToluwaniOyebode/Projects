import unittest
from rodri_baseline import NextActionBaseline


def event(match, timestamp, action, zone="midfield", pressure="low", ball_state="controlled"):
    return {
        "match_id": match,
        "timestamp_seconds": timestamp,
        "action": action,
        "zone": zone,
        "pressure": pressure,
        "ball_state": ball_state,
    }


class NextActionBaselineTests(unittest.TestCase):
    def setUp(self):
        self.events = [
            event("match_a", 1, "receive"),
            event("match_a", 2, "short_pass"),
            event("match_a", 3, "receive"),
            event("match_a", 4, "short_pass"),
            event("match_b", 1, "receive"),
            event("match_b", 2, "long_pass", zone="defensive"),
            event("match_b", 3, "receive"),
            event("match_b", 4, "short_pass"),
        ]

    def test_fit_and_predict(self):
        model = NextActionBaseline().fit(self.events)
        result = model.predict(event("new_match", 1, "receive"), k=2)
        self.assertTrue(result["predictions"])
        self.assertLessEqual(len(result["predictions"]), 2)
        self.assertIn(result["backoff_level"], {"action+context", "action", "global"})

    def test_leave_one_match_out_reports_majority_comparison(self):
        result = NextActionBaseline().evaluate_leave_one_match_out(self.events, k=1)
        self.assertEqual(result["split"], "leave-one-match-out")
        self.assertIn("majority_baseline", result)
        self.assertIn("accuracy_lift_vs_majority", result)
        self.assertEqual(set(result["per_match"]), {"match_a", "match_b"})
        self.assertGreater(result["evaluated"], 0)
        self.assertGreater(result["majority_baseline"]["evaluated"], 0)

    def test_requires_two_matches_for_evaluation(self):
        with self.assertRaises(ValueError):
            NextActionBaseline().evaluate_leave_one_match_out(self.events[:4])


if __name__ == "__main__":
    unittest.main()
