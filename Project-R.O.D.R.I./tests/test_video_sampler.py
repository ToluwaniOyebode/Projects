import unittest
from video_sampler import sample_times

class SampleTimesTests(unittest.TestCase):
    def test_default_interval(self):
        self.assertEqual(list(sample_times(25, 10)), [0.0, 10.0, 20.0])
    def test_start_offset(self):
        self.assertEqual(list(sample_times(26, 10, 5)), [5.0, 15.0, 25.0])
    def test_empty_when_start_at_end(self):
        self.assertEqual(list(sample_times(10, 5, 10)), [])
    def test_rejects_bad_interval(self):
        with self.assertRaises(ValueError):
            list(sample_times(10, 0))
    def test_rejects_negative_start(self):
        with self.assertRaises(ValueError):
            list(sample_times(10, 5, -1))

if __name__ == "__main__":
    unittest.main()
