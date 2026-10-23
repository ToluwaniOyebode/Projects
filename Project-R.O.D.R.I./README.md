# Project R.O.D.R.I. — early implementation

This folder contains three small, deliberately separated components:
1. A CPU-only next-action transition baseline trained on manually verified event labels.
2. A video sampler that extracts timestamped frames for manual inspection and annotation.
3. A dataset validator that catches common CSV/data-integrity problems before evaluation.

## Important limitations

The sampler does **not** detect players or identify Rodri. The baseline does **not** infer actions from pixels. The validator checks structure and consistency, **not** whether a human label is correct. Do not interpret the example CSV rows as real observations; replace all placeholders with labels verified against footage before evaluating predictive performance.

## 1. Install and test

Python 3.10+ is required. Baseline, validator, and their tests use only the standard library.

```bash
cd Project-R.O.D.R.I.
python -m unittest discover -s tests -v
python validate_events.py data/events_template.csv
python rodri_baseline.py data/events_template.csv
python rodri_baseline.py data/events_template.csv --evaluate --top-k 3
```

The template is illustrative and should **not** be treated as training evidence. The validator reports structure and taxonomy warnings; it cannot establish that the events happened.

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

Use one row per verified Rodri action, seconds from the start of that exact video, and a unique `match_id` for every match. Keep the source video and match identifier stable. Recommended columns:

- Required: `match_id,timestamp_seconds,action`
- Context (recommended): `zone,pressure,ball_state`

Suggested action labels: `receive`, `short_pass`, `long_pass`, `carry`, `shield`, `shot`, `press`, `tackle`, `interception`, `clearance`, `support_run`, `track_opponent`, `stoppage`, `unknown`.

If Rodri's identity or action is uncertain, use `unknown` rather than guessing. Use consistent definitions throughout a dataset; for example, decide in advance whether a one-touch layoff counts as `short_pass` and how a `carry` starts/ends. The taxonomy can be changed, but changes must be applied consistently.

Before modelling, run:

```bash
python validate_events.py data/rodri_events.csv
```

Validation failure exits with code 1. Warnings do not prove data is wrong, but should be reviewed. Unfamiliar labels can fragment action classes. Duplicate timestamps are warnings because multiple events can sometimes be logged at one timestamp.


## 3.5. Use the browser annotation tool

Open [annotator.html](annotator.html) in a desktop browser, choose a match video from your computer, pause at a confirmed Rodri action, set the timestamp and action/context labels, then click **Add event**. Export a CSV when finished. You can save/import a JSON session as a backup. The page works locally and does not upload the selected video. It does not identify Rodri automatically; use `unknown` whenever identity/action is uncertain. Review every annotation before treating it as ground truth.

## 4. Evaluation discipline

`--evaluate` uses leave-one-match-out evaluation: all events from the held-out match are excluded from training. Never randomly split frames/events from the same match into train and test. Compare top-1/top-3 accuracy to a simple most-common-action baseline before claiming the transition model adds value. Report per-match scores as well as aggregate scores, since matches differ.

## Next milestones

1. Extract and inspect timestamped frame samples from the available footage on a machine with OpenCV available.
2. Verify Rodri identity and annotate 100–300 actions across at least two matches; do not count template/example rows.
3. Validate the real labels and measure the baseline on held-out matches.
4. Add tracking/perception only after checking identity consistency; then compare a temporal model against the baseline.
5. For variable-length forecasts, define the stopping event explicitly (e.g. shot, turnover, foul, or stoppage) and report uncertainty.
