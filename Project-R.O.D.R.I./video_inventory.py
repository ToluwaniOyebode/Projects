#!/usr/bin/env python3
"""Build a reproducible inventory of local match videos.

Uses ffprobe when available for duration/resolution/frame-rate metadata. The
script never uploads video and does not claim to detect players or actions.
Without ffprobe it still writes a useful file inventory.
"""
from __future__ import annotations

import argparse
import csv
import json
import shutil
import subprocess
from pathlib import Path

VIDEO_SUFFIXES = {".mp4", ".mkv", ".avi", ".mov", ".webm", ".m4v"}
FIELDS = [
    "video_id", "filename", "relative_path", "size_bytes",
    "duration_seconds", "width", "height", "fps", "codec",
    "probe_status", "notes",
]


def _number(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return ""


def probe_video(path: Path, ffprobe: str | None = None) -> dict:
    """Return metadata for a video, or a structured failure if probing fails."""
    executable = ffprobe or shutil.which("ffprobe")
    if not executable:
        return {"probe_status": "ffprobe_missing", "notes": "Install FFmpeg/ffprobe for duration and codec metadata."}
    command = [
        executable, "-v", "error", "-show_entries",
        "format=duration:stream=codec_type,codec_name,width,height,avg_frame_rate",
        "-of", "json", str(path),
    ]
    try:
        result = subprocess.run(command, check=True, capture_output=True, text=True, timeout=30)
        data = json.loads(result.stdout)
    except (subprocess.SubprocessError, json.JSONDecodeError, OSError) as exc:
        return {"probe_status": "probe_failed", "notes": str(exc)}

    streams = data.get("streams", [])
    video = next((s for s in streams if s.get("codec_type") == "video"), {})
    duration = _number(data.get("format", {}).get("duration"))
    rate = video.get("avg_frame_rate", "")
    fps = ""
    if isinstance(rate, str) and "/" in rate:
        numerator, denominator = rate.split("/", 1)
        n, d = _number(numerator), _number(denominator)
        if d not in ("", 0, 0.0) and n != "":
            fps = round(n / d, 4)
    elif rate:
        fps = _number(rate)
    return {
        "duration_seconds": duration,
        "width": video.get("width", ""),
        "height": video.get("height", ""),
        "fps": fps,
        "codec": video.get("codec_name", ""),
        "probe_status": "ok" if video else "no_video_stream",
        "notes": "" if video else "No video stream found.",
    }


def inventory(root: Path, output: Path, ffprobe: str | None = None) -> list[dict]:
    root = root.expanduser().resolve()
    output = output.expanduser().resolve()
    if not root.is_dir():
        raise NotADirectoryError(f"Video folder does not exist: {root}")
    rows = []
    files = sorted(
        (p for p in root.rglob("*") if p.is_file() and p.suffix.lower() in VIDEO_SUFFIXES),
        key=lambda p: str(p).lower(),
    )
    for index, path in enumerate(files, start=1):
        try:
            relative = path.relative_to(root).as_posix()
            size = path.stat().st_size
        except OSError as exc:
            relative, size = path.name, ""
            metadata = {"probe_status": "file_error", "notes": str(exc)}
        else:
            metadata = probe_video(path, ffprobe)
        rows.append({
            "video_id": f"match_video_{index:03d}",
            "filename": path.name,
            "relative_path": relative,
            "size_bytes": size,
            "duration_seconds": metadata.get("duration_seconds", ""),
            "width": metadata.get("width", ""),
            "height": metadata.get("height", ""),
            "fps": metadata.get("fps", ""),
            "codec": metadata.get("codec", ""),
            "probe_status": metadata.get("probe_status", ""),
            "notes": metadata.get("notes", ""),
        })
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("video_folder", type=Path, help="Folder containing local match videos")
    parser.add_argument("--out", type=Path, default=Path("data/video_manifest.csv"), help="Output CSV path")
    parser.add_argument("--ffprobe", help="Optional explicit path to ffprobe executable")
    args = parser.parse_args()
    try:
        rows = inventory(args.video_folder, args.out, args.ffprobe)
    except (NotADirectoryError, OSError) as exc:
        parser.error(str(exc))
    print(f"Videos inventoried: {len(rows)}")
    print(f"Manifest: {args.out}")
    if rows and all(row["probe_status"] == "ffprobe_missing" for row in rows):
        print("Note: ffprobe was unavailable; install FFmpeg for technical metadata.")
    print("This inventory does not detect Rodri or label football actions.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
