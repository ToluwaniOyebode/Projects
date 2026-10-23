"""CPU-friendly video sampler for the R.O.D.R.I. annotation workflow.

Requires: pip install opencv-python
Extracts one frame every N seconds plus a CSV index. It does NOT detect or identify Rodri.
"""
from __future__ import annotations
import argparse
import csv
from pathlib import Path


def sample_times(duration_seconds: float, interval_seconds: float, start_seconds: float = 0.0):
    if duration_seconds < 0:
        raise ValueError("duration_seconds must be non-negative")
    if interval_seconds <= 0:
        raise ValueError("interval_seconds must be positive")
    if start_seconds < 0:
        raise ValueError("start_seconds must be non-negative")
    t = start_seconds
    while t < duration_seconds:
        yield round(t, 3)
        t += interval_seconds


def extract(video_path: Path, output_dir: Path, interval: float, start: float, end: float | None):
    try:
        import cv2
    except ImportError as exc:
        raise SystemExit("OpenCV missing. Install with: python -m pip install opencv-python") from exc

    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise SystemExit(f"Could not open video: {video_path}")
    fps = cap.get(cv2.CAP_PROP_FPS)
    frame_count = cap.get(cv2.CAP_PROP_FRAME_COUNT)
    duration = frame_count / fps if fps and fps > 0 else 0.0
    if duration <= 0:
        cap.release()
        raise SystemExit("Could not read video duration/FPS; verify the video file is valid.")
    stop = min(end, duration) if end is not None else duration
    if start >= stop:
        cap.release()
        raise SystemExit(f"Invalid time range: start={start}, end={stop}, duration={duration:.1f}s")

    output_dir.mkdir(parents=True, exist_ok=True)
    index_path = output_dir / "frames.csv"
    saved = 0
    with index_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["frame_file", "timestamp_seconds", "source_video"])
        writer.writeheader()
        for timestamp in sample_times(stop, interval, start):
            cap.set(cv2.CAP_PROP_POS_MSEC, timestamp * 1000)
            ok, frame = cap.read()
            if not ok:
                print(f"Warning: could not decode frame at {timestamp:.1f}s; skipping")
                continue
            name = f"frame_{timestamp:010.3f}s.jpg".replace(":", "_")
            target = output_dir / name
            if not cv2.imwrite(str(target), frame):
                print(f"Warning: failed to write {target}; skipping")
                continue
            writer.writerow({"frame_file": name, "timestamp_seconds": timestamp,
                             "source_video": video_path.name})
            saved += 1
    cap.release()
    print(f"Video: {video_path.name}")
    print(f"Duration: {duration/60:.2f} minutes | FPS: {fps:.3f} | frame count: {int(frame_count)}")
    print(f"Saved {saved} frames and index: {index_path}")
    print("These frames are for manual inspection/annotation; no player identity or action is inferred.")
    return saved


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("video", type=Path, help="Path to a local match video")
    parser.add_argument("--out", type=Path, default=Path("data/sample_frames"))
    parser.add_argument("--interval", type=float, default=10.0, help="Seconds between frames (default: 10)")
    parser.add_argument("--start", type=float, default=0.0, help="Start time in seconds")
    parser.add_argument("--end", type=float, help="Optional end time in seconds")
    args = parser.parse_args()
    if not args.video.is_file():
        raise SystemExit(f"Video not found: {args.video}")
    extract(args.video, args.out, args.interval, args.start, args.end)


if __name__ == "__main__":
    main()
