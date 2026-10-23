# Project R.O.D.R.I. — early implementation

This folder contains a deliberately staged video-to-prediction prototype:
1. A CPU-only next-action transition baseline trained on manually verified event labels.
2. A video sampler that extracts timestamped frames for manual inspection and annotation.
3. A local video inventory tool that records file size and, when FFmpeg's `ffprobe` is installed, duration/resolution/frame-rate/codec metadata.
4. A dataset validator that catches common CSV/data-integrity problems before evaluation.
5. A browser-based annotation tool for creating timestamped action labels.

## Important limitations

The sampler does **not** detect players or identify Rodri. The baseline does **not** infer actions from pixels. The inventory records technical metadata only. The validator checks structure and consistency, **not** whether a human label is correct. Do not interpret example CSV rows as real observations; replace placeholders with labels verified against footage before evaluating predictive performance.

## 1. Install and test

Python 3.10+ is required. Baseline, validator, inventory tool, and tests use only the standard library. OpenCV is needed only for frame sampling.

```bash
cd Project-R.O.D.R.I.
python -m unittest discover -s tests -v
python validate_events.py data/events_template.csv
python rodri_baseline.py data/events_template.csv
python rodri_baseline.py data/events_template.csv --evaluate --top-k 3
```

The template is illustrative and must **not** be treated as training evidence.

## 2. Inventory your local match videos

This creates a CSV manifest for all supported video files in a folder (including subfolders). It does not upload or alter the videos.

```bash
# Optional but recommended: install FFmpeg so ffprobe can read metadata.
python video_inventory.py "C:/path/to/your/match-videos" --out data/video_manifest.csv
```

Supported extensions: MP4, MKV, AVI, MOV, WEBM, M4V. The manifest records a stable row ID, relative filename, file size, duration, dimensions, frame rate, codec and probe status. If FFmpeg/ffprobe is absent, it still inventories the files but leaves technical metadata blank. Keep the original video filenames and manifest together so timestamps can be traced to the right source.

## 3. Sample video frames

Install OpenCV only for video sampling:

```bash
python -m pip install opencv-python
python video_sampler.py "path/to/match.mp4" --out data/sample_frames --interval 10
```

For a shorter pilot, sample a five-minute section:

```bash
python video_sampler.py "path/to/match.mp4" --start 1200 --end 1500 --interval 5 --out data/pilot_frames
```

The script saves JPEG frames and `frames.csv` with source timestamps. Ten-second sampling is for browsing only; it can miss brief actions and is not a substitute for continuous tracking.

## 4. Annotate events

Use one row per verified Rodri action, seconds from the start of that exact video, and a unique `match_id` for every match. Recommended columns:
- Required: `match_id,timestamp_seconds,action`
- Context: `zone,pressure,ball_state`

Suggested labels: `receive`, `short_pass`, `long_pass`, `carry`, `shield`, `shot`, `press`, `tackle`, `interception`, `clearance`, `support_run`, `track_opponent`, `stoppage`, `unknown`.

Open [annotator.html](annotator.html) in a desktop browser, select a local video, pause at a confirmed Rodri action, and add the action/context labels. Export a CSV or save a JSON backup. The video remains local in your browser. The tool does not automatically identify Rodri; use `unknown` if identity or action is uncertain.

Validate labels before modelling:

```bash
python validate_events.py data/rodri_events.csv
```

## 5. Evaluation discipline

`--evaluate` uses leave-one-match-out evaluation: all events from the held-out match are excluded from training. Never randomly split frames/events from the same match into train and test. Compare top-1/top-3 accuracy with the most-common-action baseline. Template/example rows are not evidence of model performance.

## Next milestones

1. Inventory and sample the available videos on the local computer.
2. Verify Rodri identity and annotate 100–300 actions across at least two matches.
3. Validate the real labels and measure baseline performance on held-out matches.
4. Build and test player detection/tracking with identity consistency checks.
5. Connect tracked visual evidence to action classification and variable-length forecasting; define stopping events such as shot, turnover, foul or stoppage and report uncertainty.

## New: short-clip person detection and tracking

`detect_track.py` is the first pixel-to-detection component. It runs an Ultralytics pretrained person detector with persistent ByteTrack IDs and exports bounding boxes to CSV. It is deliberately limited to a short clip by default so it is more practical on a CPU-only laptop.

Install the optional dependencies (in a virtual environment):
```bash
python -m pip install opencv-python ultralytics
```

Run a 30-second pilot (model weights may download on first run):
```bash
python detect_track.py "path/to/match.mp4" --out runs/pilot
```

Choose a 45-second segment starting at 20 minutes, process every third frame, and save an annotated preview:
```bash
python detect_track.py "path/to/match.mp4" --start 1200 --duration 45 --every 3 --preview --out runs/pilot_20m
```

Outputs: `detections.csv`, `run_summary.json`, and (if requested) `preview.mp4`. The CSV records timestamps, frame numbers, detector class/confidence, bounding boxes, and tracker IDs. Use `--tracker botsort.yaml` to compare the alternative tracker.

**Critical limitation:** this does not recognize Rodri. COCO person detection treats players as generic people, and tracking IDs can switch after occlusion or camera cuts. Inspect the preview and verify identity manually before linking a track to Rodri or generating action labels. Small distant players in 640×360 broadcast footage may be missed. This component is not yet validated on the project's match videos; do not claim detection quality or prediction accuracy until a real clip is run and audited.

## Variable-length sequence rollout

`sequence_forecast.py` rolls the transition baseline forward one action at a time and stops at a configured major event (default: shot, tackle, interception, clearance, stoppage, or goal) or a maximum step count. It trains on every match except the specified seed match, then starts from the final labelled event in that held-out match:

```bash
python sequence_forecast.py data/events.csv --seed-match match_held_out --max-steps 12 --out forecast.json
```

This is a greedy chain of local transition-frequency choices. It is not a trained video model, a calibrated whole-sequence probability, or evidence of accuracy on real Rodri footage. Meaningful evaluation requires correctly labelled events from multiple matches.


## New: build a Rodri identity review gallery

Rather than training a new vision model from scratch, first collect verified positive examples from real footage. Run the detector/tracker, then crop a small set of views for each tracked player so a human can identify Rodri and flag tracker ID switches.

```bash
python rodri_identity_gallery.py "path/to/match.mp4" --detections runs/pilot/detections.csv --out runs/rodri_gallery
```

Open `runs/rodri_gallery/index.html` locally and inspect the crops. In `labels.csv`, set `is_rodri` to `yes` only for confidently identified Rodri crops, `no` for other players, and leave uncertain examples as `unknown`. Keep several views across time and verify the entire track; an ID is not automatically a player identity.

This gallery is a data-curation tool, **not an automatic recognizer or trained model**. Once we have verified positive and negative crops across multiple matches, the next step is to benchmark a pretrained person re-identification embedding model against a simple visual baseline. We should only fine-tune if the verified data and evaluation justify it. Split evaluation by match to avoid near-duplicate frames leaking across train and test.
