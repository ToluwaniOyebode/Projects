import unittest
from rodri_baseline import NextActionBaseline
from sequence_forecast import forecast_sequence


class SequenceForecastTests(unittest.TestCase):
    def setUp(self):
        self.events = [
            {"match_id": "a", "timestamp_seconds": 0, "action": "receive", "zone": "mid", "pressure": "low", "ball_state": "live"},
            {"match_id": "a", "timestamp_seconds": 1, "action": "short_pass", "zone": "mid", "pressure": "low", "ball_state": "live"},
            {"match_id": "a", "timestamp_seconds": 2, "action": "carry", "zone": "mid", "pressure": "low", "ball_state": "live"},
            {"match_id": "a", "timestamp_seconds": 3, "action": "shot", "zone": "box", "pressure": "high", "ball_state": "live"},
            {"match_id": "b", "timestamp_seconds": 0, "action": "receive", "zone": "mid", "pressure": "low", "ball_state": "live"},
            {"match_id": "b", "timestamp_seconds": 1, "action": "short_pass", "zone": "mid", "pressure": "low", "ball_state": "live"},
            {"match_id": "b", "timestamp_seconds": 2, "action": "carry", "zone": "mid", "pressure": "low", "ball_state": "live"},
            {"match_id": "b", "timestamp_seconds": 3, "action": "shot", "zone": "box", "pressure": "high", "ball_state": "live"},
        ]

    def test_rollout_stops_at_major_event(self):
        model = NextActionBaseline().fit(self.events[:4])
        seed = dict(self.events[0])
        result = forecast_sequence(model, seed, max_steps=8, stop_actions={"shot"})
        self.assertEqual([x["action"] for x in result], ["short_pass", "carry", "shot"])
        self.assertLessEqual(len(result), 8)

    def test_max_steps_limits_rollout(self):
        model = NextActionBaseline().fit(self.events[:4])
        result = forecast_sequence(model, dict(self.events[0]), max_steps=1, stop_actions={"shot"})
        self.assertEqual(len(result), 1)

    def test_invalid_max_steps(self):
        with self.assertRaises(ValueError):
            forecast_sequence(NextActionBaseline().fit(self.events[:4]), dict(self.events[0]), max_steps=0)


if __name__ == "__main__":
    unittest.main()
