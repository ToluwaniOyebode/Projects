# Verification report — 25 October 2026

## Executed

- `python -m compileall -q rodri_studio run.py`: passed.
- `python -m pytest -q`: **11 passed**.
- YOLO11n loaded downloaded official weights and completed CPU inference on a
  blank synthetic image (zero boxes, as expected). This is an installation/
  inference smoke test, not evidence of football detection accuracy.
- OpenCV HOG processed a generated video through the real decoding/detection path.
- A generated two-shot video tested timestamps, shot boundaries and track reset.
- Overlay MP4 export was decoded and its expected frame count verified.
- FastAPI TestClient exercised video upload, range playback, metadata errors,
  identity confirmation, untrained forecast, replay suppression and JSON export.
- Synthetic classifier rows tested match holdout and binary probability output.
  Those rows are test fixtures, not Rodri observations; no football scores reported.

- End-to-end API smoke: uploaded generated MP4 → YOLO CPU analysis (5 sampled
  frames) → JSON results → rendered overlay → video download: passed.

## Not verified

- Real match detection quality, Rodri recognition or next-action prediction.
- Windows installer execution; Windows instructions are provided, but execution
  occurred on Linux with Python 3.12.14.
- Full browser interaction/layout testing: Chromium downloads returned truncated
  archives and could not be installed. API and file-level checks are not a
  substitute for visual browser QA. This remains an explicit release limitation.
- Replay/camera-cut recall or precision on broadcast footage.
- Calibrated action probabilities, ball detection or tactical understanding.

## Environment issue resolved

Initial development dependency installation brought OpenCV 5, where HOGDescriptor
was absent. The project now constrains OpenCV below 5; retesting with 4.13.0.92
passed. A deprecation warning from FastAPI's testing dependency remains nonfatal.
