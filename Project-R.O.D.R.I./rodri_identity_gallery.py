"""Build a human-review gallery for identifying Rodri in tracked football footage.

This is the practical first step toward a Rodri-specific appearance model: review detected
player crops, mark confirmed Rodri examples, and keep uncertain examples out of training.
It does NOT automatically identify Rodri or train a model.

Usage:
  python rodri_identity_gallery.py match.mp4 --detections runs/pilot/detections.csv --out runs/rodri_gallery
  Then open runs/rodri_gallery/index.html in a browser and mark candidates in labels.csv.
"""
import argparse
import csv
import html
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("video", help="Original video used by detect_track.py")
    parser.add_argument("--detections", required=True, help="detections.csv from detect_track.py")
    parser.add_argument("--out", default="runs/rodri_gallery")
    parser.add_argument("--max-crops-per-track", type=int, default=12)
    parser.add_argument("--min-confidence", type=float, default=0.25)
    args = parser.parse_args()

    try:
        import cv2
    except ImportError as exc:
        raise SystemExit("Install OpenCV first: python -m pip install opencv-python") from exc

    video = Path(args.video)
    detections_path = Path(args.detections)
    out = Path(args.out)
    crops_dir = out / "crops"
    if not video.is_file():
        raise SystemExit(f"Video not found: {video}")
    if not detections_path.is_file():
        raise SystemExit(f"Detections CSV not found: {detections_path}")
    if args.max_crops_per_track < 1:
        raise SystemExit("--max-crops-per-track must be >= 1")
    out.mkdir(parents=True, exist_ok=True)
    crops_dir.mkdir(parents=True, exist_ok=True)

    with detections_path.open(newline="", encoding="utf-8-sig") as f:
        detections = list(csv.DictReader(f))
    required = {"timestamp_seconds", "frame_index", "track_id", "confidence", "x1", "y1", "x2", "y2"}
    if not detections or not required.issubset(detections[0]):
        raise SystemExit("CSV is empty or missing required columns from detect_track.py.")

    # Choose evenly spaced examples per track, rather than many nearly identical adjacent frames.
    by_track = {}
    for row in detections:
        if not row.get("track_id", "").strip():
            continue
        try:
            if float(row["confidence"]) < args.min_confidence:
                continue
            tid = row["track_id"]
            by_track.setdefault(tid, []).append(row)
        except (ValueError, KeyError):
            continue

    selected = []
    for tid, rows in sorted(by_track.items(), key=lambda pair: int(pair[0]) if pair[0].isdigit() else pair[0]):
        rows.sort(key=lambda r: int(r["frame_index"]))
        if len(rows) > args.max_crops_per_track:
            indices = [round(i * (len(rows) - 1) / (args.max_crops_per_track - 1)) for i in range(args.max_crops_per_track)] if args.max_crops_per_track > 1 else [len(rows) // 2]
            rows = [rows[i] for i in sorted(set(indices))]
        selected.extend(rows)

    cap = cv2.VideoCapture(str(video))
    if not cap.isOpened():
        raise SystemExit(f"OpenCV could not open video: {video}")
    fps = cap.get(cv2.CAP_PROP_FPS) or 0.0
    if fps <= 0:
        cap.release()
        raise SystemExit("Video reports invalid FPS.")
    labels_path = out / "labels.csv"
    metadata = []
    try:
        for i, row in enumerate(selected, start=1):
            frame_no = int(row["frame_index"])
            cap.set(cv2.CAP_PROP_POS_FRAMES, frame_no)
            ok, frame = cap.read()
            if not ok:
                continue
            h, w = frame.shape[:2]
            x1, y1, x2, y2 = [float(row[k]) for k in ("x1", "y1", "x2", "y2")]
            # Small padding preserves body outline and some kit context.
            pw, ph = (x2 - x1) * 0.12, (y2 - y1) * 0.08
            x1, y1 = max(0, int(x1 - pw)), max(0, int(y1 - ph))
            x2, y2 = min(w, int(x2 + pw)), min(h, int(y2 + ph))
            if x2 <= x1 or y2 <= y1:
                continue
            crop_name = f"track_{row['track_id']}_t{float(row['timestamp_seconds']):09.3f}.jpg".replace(":", "_")
            crop_path = crops_dir / crop_name
            if not cv2.imwrite(str(crop_path), frame[y1:y2, x1:x2]):
                continue
            metadata.append({
                "crop_file": f"crops/{crop_name}",
                "track_id": row["track_id"],
                "timestamp_seconds": row["timestamp_seconds"],
                "frame_index": row["frame_index"],
                "confidence": row["confidence"],
                "is_rodri": "unknown",
                "notes": ""
            })
    finally:
        cap.release()

    with labels_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["crop_file", "track_id", "timestamp_seconds", "frame_index", "confidence", "is_rodri", "notes"])
        writer.writeheader()
        writer.writerows(metadata)

    cards = []
    for row in metadata:
        cards.append(
            '<article><img loading="lazy" src="' + html.escape(row["crop_file"], quote=True) + '" alt="Player crop">'
            + '<div><b>Track ' + html.escape(row["track_id"]) + '</b> · ' + html.escape(row["timestamp_seconds"]) + ' s'
            + '<br><small>Detection confidence: ' + html.escape(row["confidence"]) + '</small></div></article>'
        )
    page = """<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width">
<title>Rodri identity review gallery</title><style>
body{font:16px system-ui;margin:20px;background:#111;color:#eee}p{max-width:900px;line-height:1.5}
main{display:grid;grid-template-columns:repeat(auto-fill,minmax(180px,1fr));gap:12px}
article{background:#222;padding:8px;border-radius:8px;overflow:hidden}img{width:100%;height:180px;object-fit:contain;background:#080808}
small{color:#bbb}code{background:#333;padding:2px 5px}
</style></head><body><h1>Rodri identity review</h1>
<p>Review crops and edit <code>labels.csv</code>. Change <code>is_rodri</code> to <code>yes</code> only when certain, <code>no</code> when clearly another player, and leave <code>unknown</code> otherwise. Several crops share a tracker ID; IDs can switch or merge, so verify the full sequence rather than assuming an ID is Rodri. This gallery does not train a model.</p>
<p>Generated crops: """ + str(len(metadata)) + """ · tracks: """ + str(len(by_track)) + """</p><main>""" + "\n".join(cards) + """</main></body></html>"""
    (out / "index.html").write_text(page, encoding="utf-8")
    print(f"Created {len(metadata)} crops from {len(by_track)} tracked IDs.")
    print(f"Review gallery: {out / 'index.html'}")
    print(f"Edit labels: {labels_path}")


if __name__ == "__main__":
    main()
