import unittest
from track_features import summarize_tracks


def row(t, x, y, track="1", confidence=0.8):
    return {
        "timestamp_seconds": t, "frame_index": int(t * 25), "track_id": track,
        "confidence": confidence, "x1": x, "y1": y, "x2": x + 10, "y2": y + 20
    }


class TrackFeaturesTests(unittest.TestCase):
    def test_motion_summary(self):
        features = summarize_tracks([row(0, 0, 0), row(1, 3, 4), row(2, 6, 8)])
        self.assertEqual(len(features), 1)
        self.assertEqual(features[0]["observations"], 3)
        self.assertAlmostEqual(features[0]["net_displacement_px"], 10.0)
        self.assertAlmostEqual(features[0]["duration_seconds"], 2.0)

    def test_short_tracks_are_ignored(self):
        self.assertEqual(summarize_tracks([row(0, 0, 0), row(1, 2, 2)]), [])

    def test_tracks_are_kept_separate(self):
        rows = [row(0, 0, 0, "a"), row(1, 1, 1, "a"), row(2, 2, 2, "a"),
                row(0, 50, 50, "b"), row(1, 51, 51, "b"), row(2, 52, 52, "b")]
        self.assertEqual(len(summarize_tracks(rows)), 2)

    def test_invalid_minimum_is_rejected(self):
        with self.assertRaises(ValueError):
            summarize_tracks([], min_observations=1)


if __name__ == "__main__":
    unittest.main()
