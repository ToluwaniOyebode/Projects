import csv
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import video_inventory


class VideoInventoryTests(unittest.TestCase):
    def test_inventory_lists_supported_video_files_recursively(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "videos"
            (root / "nested").mkdir(parents=True)
            (root / "a.mp4").write_bytes(b"video")
            (root / "nested" / "b.MKV").write_bytes(b"video2")
            (root / "notes.txt").write_text("not a video", encoding="utf-8")
            output = Path(temp) / "out" / "manifest.csv"
            metadata = {
                "duration_seconds": 60.0, "width": 640, "height": 360,
                "fps": 25.0, "codec": "h264", "probe_status": "ok", "notes": "",
            }
            with patch.object(video_inventory, "probe_video", return_value=metadata):
                rows = video_inventory.inventory(root, output)
            self.assertEqual(len(rows), 2)
            self.assertEqual([row["video_id"] for row in rows], ["match_video_001", "match_video_002"])
            with output.open(newline="", encoding="utf-8") as handle:
                saved = list(csv.DictReader(handle))
            self.assertEqual(len(saved), 2)
            self.assertEqual(saved[0]["duration_seconds"], "60.0")
            self.assertIn("nested/b.MKV", [row["relative_path"] for row in saved])

    def test_missing_ffprobe_is_reported_without_crashing(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "videos"
            root.mkdir()
            (root / "match.mp4").write_bytes(b"fake")
            output = Path(temp) / "manifest.csv"
            with patch.object(video_inventory.shutil, "which", return_value=None):
                rows = video_inventory.inventory(root, output)
            self.assertEqual(rows[0]["probe_status"], "ffprobe_missing")
            self.assertIn("Install FFmpeg", rows[0]["notes"])

    def test_nonexistent_folder_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaises(NotADirectoryError):
                video_inventory.inventory(Path(temp) / "missing", Path(temp) / "out.csv")

    def test_probe_parses_fractional_frame_rate(self):
        class Completed:
            stdout = '{"streams":[{"codec_type":"video","codec_name":"h264","width":640,"height":360,"avg_frame_rate":"30000/1001"}],"format":{"duration":"12.5"}}'
        with patch.object(video_inventory.shutil, "which", return_value="ffprobe"):
            with patch.object(video_inventory.subprocess, "run", return_value=Completed()):
                result = video_inventory.probe_video(Path("match.mp4"))
        self.assertEqual(result["probe_status"], "ok")
        self.assertAlmostEqual(result["fps"], 29.9700, places=3)
        self.assertEqual(result["duration_seconds"], 12.5)


if __name__ == "__main__":
    unittest.main()
