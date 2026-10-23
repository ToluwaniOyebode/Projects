# Project R.O.D.R.I. — early implementation

This folder contains two independent starting components:
1. A CPU-only next-action transition baseline trained on manually verified event labels.
2. A video sampler that extracts timestamped frames for manual inspection and annotation.

## Important limitations

The sampler does **not** detect players or identify Rodri. The baseline does **not** infer actions from pixels. Do not interpret the example CSV rows as real observations; replace them with labels verified against the footage before evaluating predictive performance.

## 1. Install and test

Python 3.10+ is required. Baseline and unit tests use only the standard library.

```bash
cd Project-R.O.D.R.I.
python -m unittest discover -s tests -v
python rodri_baseline.py data/events_template.csv
python rodri_baseline.py data/events_template.csv --evaluate --top-k 3
```

## 2. Sample video frames

Install OpenCV only for video sampling:

```bash
python -m pip install opencv-python
python video_sampler.py "path/to/match.mp4" --out data/sample_frames --interval 10
```

For a shorter pilot, sample a 5-minute section:

```bash
python video_sampler.py "path/to/match.mp4" --start 1200 --end 1500 --interval 5 --out data/pilot_frames
```

The script saves JPEG frames and `frames.csv` with video timestamps. Use the timestamps to locate moments in the original match. Ten-second sampling is for browsing only; it can miss brief actions, so it is not a substitute for continuous tracking.

## 3. Annotate events

Copy `data/events_template.csv` to a new CSV and replace all placeholder rows with manually verified observations. Use one row per Rodri action, seconds from the start of that video, and a unique `match_id` for every match.

Suggested action labels: `receive`, `short_pass`, `long_pass`, `carry`, `shield`, `shot`, `press`, `tackle`, `interception`, `clearance`, `support_run`, `track_opponent`, `stoppage`, `unknown`.

Optional context fields are `zone`, `pressure`, and `ball_state`. If Rodri's identity or action is uncertain, mark `unknown` instead of guessing.

## 4. Evaluation discipline

`--evaluate` uses leave-one-match-out evaluation: all events from the held-out match are excluded from training. Never randomly split frames/events from the same match into train and test. Compare top-1/top-3 accuracy to a simple most-common-action baseline.

## Next milestones

1. Produce timestamped frame samples from both available matches.
2. Verify Rodri identity and annotate 100–300 actions across at least two matches.
3. Measure this baseline on held-out matches.
4. Add tracking/perception only after checking identity consistency; then compare a temporal model against this baseline.
5. For variable-length forecasts, define the stopping event explicitly (e.g. shot, turnover, foul, or stoppage) and report uncertainty.
