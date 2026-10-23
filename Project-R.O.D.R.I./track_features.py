"""Derive conservative motion features from person-tracker detections.

This module does not identify Rodri or infer football actions as ground truth. It
creates auditable track-level motion features that can later support action
classification after a track has been verified as Rodri.
"""
import argparse
import csv
import json
import math
from collections import defaultdict
from pathlib import Path

REQUIRED = {"timestamp_seconds", "frame_index", "track_id", "confidence", "x1", "y1", "x2", "y2"}


def read_detections(path):
    with Path(path).open(newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames or not REQUIRED.issubset(reader.fieldnames):
            raise ValueError("detections CSV is missing required columns")
        rows = []
        for row in reader:
            if not row.get("track_id", "").strip():
                continue
            try:
                item = {k: float(row[k]) for k in ("timestamp_seconds", "frame_index", "confidence", "x1", "y1", "x2", "y2")}
                item["track_id"] = str(row["track_id"])
                if item["x2"] <= item["x1"] or item["y2"] <= item["y1"]:
                    continue
                rows.append(item)
            except (ValueError, TypeError, KeyError):
                continue
    return rows


def summarize_tracks(rows, min_observations=3):
    if min_observations < 2:
        raise ValueError("min_observations must be >= 2")
    grouped = defaultdict(list)
    for row in rows:
        grouped[str(row["track_id"])].append(row)
    result = []
    for track_id, points in sorted(grouped.items(), key=lambda kv: kv[0]):
        points.sort(key=lambda p: (p["timestamp_seconds"], p["frame_index"]))
        if len(points) < min_observations:
            continue
        centers = [((p["x1"] + p["x2"]) / 2, (p["y1"] + p["y2"]) / 2) for p in points]
        speeds, headings = [], []
        for prev, cur, a, b in zip(points, points[1:], centers, centers[1:]):
            dt = cur["timestamp_seconds"] - prev["timestamp_seconds"]
            if dt <= 0:
                continue
            dx, dy = b[0] - a[0], b[1] - a[1]
            speeds.append(math.hypot(dx, dy) / dt)
            headings.append(math.degrees(math.atan2(-dy, dx)))
        durations = points[-1]["timestamp_seconds"] - points[0]["timestamp_seconds"]
        displacement = math.hypot(centers[-1][0] - centers[0][0], centers[-1][1] - centers[0][1])
        widths = [p["x2"] - p["x1"] for p in points]
        heights = [p["y2"] - p["y1"] for p in points]
        result.append({
            "track_id": track_id,
            "observations": len(points),
            "start_seconds": round(points[0]["timestamp_seconds"], 3),
            "end_seconds": round(points[-1]["timestamp_seconds"], 3),
            "duration_seconds": round(max(0.0, durations), 3),
            "mean_confidence": round(sum(p["confidence"] for p in points) / len(points), 4),
            "mean_center_speed_px_s": round(sum(speeds) / len(speeds), 3) if speeds else 0.0,
            "net_displacement_px": round(displacement, 3),
            "mean_box_width_px": round(sum(widths) / len(widths), 2),
            "mean_box_height_px": round(sum(heights) / len(heights), 2),
            "mean_heading_degrees": round(sum(headings) / len(headings), 2) if headings else None,
            "warning": "Image-plane motion only; camera pans, zooms, and cuts can mimic player motion."
        })
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("detections_csv")
    parser.add_argument("--out", default="track_features.json")
    parser.add_argument("--min-observations", type=int, default=3)
    args = parser.parse_args()
    features = summarize_tracks(read_detections(args.detections_csv), args.min_observations)
    report = {
        "source": str(Path(args.detections_csv)),
        "track_count": len(features),
        "tracks": features,
        "limitations": [
            "Track IDs are not player identities; confirm Rodri before using a track.",
            "Image-plane motion is not pitch-coordinate motion and is not an action label.",
            "No predictive accuracy is claimed from these features alone."
        ]
    }
    Path(args.out).write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({"track_count": len(features), "output": args.out}, indent=2))


if __name__ == "__main__":
    main()
