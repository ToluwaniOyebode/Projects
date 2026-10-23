"""CPU-conscious person detection and multi-object tracking for short football clips.

Install: python -m pip install opencv-python ultralytics
Example: python detect_track.py input.mp4 --out runs/pilot --start 120 --duration 45 --every 3
Exports detections.csv and an optional annotated preview. Track IDs are NOT player identities.
"""
import argparse
import csv
import os
from pathlib import Path


FIELDS = ["timestamp_seconds", "frame_index", "track_id", "class_id",
          "class_name", "confidence", "x1", "y1", "x2", "y2"]


def parse_args():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("video", help="Local video path")
    p.add_argument("--out", default="runs/track_pilot")
    p.add_argument("--start", type=float, default=0.0, help="Start offset in seconds")
    p.add_argument("--duration", type=float, default=30.0, help="Clip duration; default 30 seconds")
    p.add_argument("--every", type=int, default=3, help="Process every Nth frame (default 3)")
    p.add_argument("--imgsz", type=int, default=640)
    p.add_argument("--conf", type=float, default=0.25)
    p.add_argument("--tracker", choices=("bytetrack.yaml", "botsort.yaml"), default="bytetrack.yaml")
    p.add_argument("--model", default="yolo11n.pt", help="Ultralytics model weights; downloads on first use")
    p.add_argument("--preview", action="store_true", help="Write annotated MP4 preview")
    return p.parse_args()


def main():
    args = parse_args()
    if args.start < 0 or args.duration <= 0 or args.every < 1:
        raise SystemExit("--start must be >= 0, --duration > 0, and --every >= 1")
    video = Path(args.video)
    if not video.is_file():
        raise SystemExit(f"Video not found: {video}")
    try:
        import cv2
        from ultralytics import YOLO
    except ImportError as exc:
        raise SystemExit("Install dependencies: python -m pip install opencv-python ultralytics") from exc

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    cap = cv2.VideoCapture(str(video))
    if not cap.isOpened():
        raise SystemExit(f"OpenCV could not open video: {video}")
    fps = cap.get(cv2.CAP_PROP_FPS) or 0.0
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    if fps <= 0:
        cap.release()
        raise SystemExit("Video reports invalid FPS; convert/remux it or inspect with ffprobe.")
    start_frame = int(args.start * fps)
    end_frame = min(total_frames, int((args.start + args.duration) * fps)) if total_frames else int((args.start + args.duration) * fps)
    if start_frame >= end_frame:
        cap.release()
        raise SystemExit("Requested clip starts after video end.")
    cap.set(cv2.CAP_PROP_POS_FRAMES, start_frame)
    model = YOLO(args.model)
    csv_path = out / "detections.csv"
    preview_path = out / "preview.mp4"
    writer = None
    processed = 0
    saved = 0
    names = model.names

    try:
        with csv_path.open("w", newline="", encoding="utf-8") as f:
            rows = csv.DictWriter(f, fieldnames=FIELDS)
            rows.writeheader()
            frame_index = start_frame
            while frame_index < end_frame:
                ok, frame = cap.read()
                if not ok:
                    break
                if (frame_index - start_frame) % args.every == 0:
                    result = model.track(frame, persist=True, tracker=args.tracker,
                                         classes=[0], conf=args.conf, imgsz=args.imgsz,
                                         verbose=False)[0]
                    processed += 1
                    if args.preview:
                        if writer is None:
                            h, w = frame.shape[:2]
                            writer = cv2.VideoWriter(str(preview_path),
                                cv2.VideoWriter_fourcc(*"mp4v"), max(1.0, fps / args.every), (w, h))
                        writer.write(result.plot())
                    boxes = result.boxes
                    if boxes is not None and len(boxes):
                        xyxy = boxes.xyxy.cpu().tolist()
                        confs = boxes.conf.cpu().tolist()
                        classes = boxes.cls.cpu().tolist()
                        ids = boxes.id.int().cpu().tolist() if boxes.id is not None else [None] * len(xyxy)
                        for box, confidence, cls, track_id in zip(xyxy, confs, classes, ids):
                            class_id = int(cls)
                            rows.writerow({
                                "timestamp_seconds": round(frame_index / fps, 3),
                                "frame_index": frame_index,
                                "track_id": "" if track_id is None else int(track_id),
                                "class_id": class_id,
                                "class_name": names.get(class_id, str(class_id)) if isinstance(names, dict) else names[class_id],
                                "confidence": round(float(confidence), 5),
                                "x1": round(box[0], 2), "y1": round(box[1], 2),
                                "x2": round(box[2], 2), "y2": round(box[3], 2),
                            })
                            saved += 1
                frame_index += 1
    finally:
        cap.release()
        if writer is not None:
            writer.release()

    report = {
        "input_video": str(video.resolve()),
        "clip_start_seconds": args.start,
        "requested_duration_seconds": args.duration,
        "processed_frames": processed,
        "detection_rows": saved,
        "csv": str(csv_path),
        "preview": str(preview_path) if args.preview else None,
        "warning": "Track IDs are temporary tracker IDs, not verified footballer identities. Manually verify Rodri before using any track as his data."
    }
    (out / "run_summary.json").write_text(__import__("json").dumps(report, indent=2), encoding="utf-8")
    print(__import__("json").dumps(report, indent=2))


if __name__ == "__main__":
    main()
