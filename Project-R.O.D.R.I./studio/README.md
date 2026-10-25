# Rodri Studio

A fresh local application for reviewing football videos, confirming Rodri in a shot,
tracking image-plane movement, reviewing camera cuts/replays, and researching the
next action with a trainable classifier. This is a new implementation; it does
not import the previous Project R.O.D.R.I. scripts.

## Read this first

**This release is a tested engineering prototype, not a validated Rodri predictor.**
The included YOLO model detects generic people. You identify Rodri by clicking his
box. It cannot automatically name Rodri across different camera angles. There is
no trained Rodri action model in the download. Before training, the interface
shows **untrained**, with no invented probabilities. After sufficient verified
labels are saved, it can train and display experimental next-action scores.

Football action prediction from pixels requires more than movement: ball location,
possession, teammates, opponents, camera geometry, and reliable identity all
matter. Those richer features are not implemented in this version.

## Windows / VS Code: start here

1. Install Python **3.11 or 3.12** from python.org. Enable the Python launcher.
2. Extract this ZIP to a folder, then open that folder in VS Code.
3. Double-click `start_windows.bat`, or enter the following in VS Code's terminal:

```powershell
py -3 -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe run.py
```

4. Open **http://127.0.0.1:8000** in your browser. Keep the terminal running.

Installation downloads PyTorch and other dependencies and may take several minutes.
A CPU is sufficient for a short pilot; no NVIDIA GPU or paid API is required.
The downloadable ZIP includes YOLO11n person-detector weights under `models/`.
The GitHub checkout downloads them on first use instead of storing binary weights. The source archive
is not an offline Python installer: initial dependency installation needs internet.

On Linux/macOS:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python run.py
```

## Use a video

1. Download your video from Drive onto your computer. Choose that local file under
   **Source video**, then press **Load local video**.
2. Choose a visible passage of play: start in video seconds, duration 30 seconds.
   The analysis limit is 120 seconds per upload to keep CPU pilots manageable.
3. Select YOLO and press **Analyze selected passage**. Wait for Ready.
4. Pause at a frame where Rodri is clearly visible. Click **his detected box**.
   Only confirm him when you know his identity. The mint box indicates that
   manually confirmed temporary track, rather than an automatic recognition.
5. Play or step through the clip. Reconfirm after each camera cut and at least
   every five seconds. Track IDs can switch even within this interval: inspect
   the boxes continuously and stop using an incorrect identity.
6. Enter replay start/end times and mark the interval. Gray timeline ticks mark
   detected shot starts; amber spans mark manually reviewed replays.
7. Download the analysis JSON, or render an overlay MP4 for a visual export.

The video is copied to this computer's `workspace/` folder. It is never uploaded
to a hosted prediction API by this application. Each upload receives its own ID.
Restarting the server preserves stored analysis, but this initial UI does not list
old sessions; retain the JSON export and the workspace folder.
A nonempty analysis cannot be overwritten: upload again to analyze another clip.

### Playback formats

H.264 MP4 is recommended. OpenCV may decode a file that your browser cannot play
(e.g. some MKV/HEVC files). Convert locally with FFmpeg if needed:

```powershell
ffmpeg -i "match.mkv" -c:v libx264 -crf 20 -c:a aac "match-browser.mp4"
```

Rendered overlays use OpenCV MPEG-4 Part 2 and contain **no audio**. VLC can play
them; convert to H.264 with the command above for broader browser compatibility.
The overlay is the analyzed passage only; on-screen timestamps refer to the source.

## Camera changes and replays

- Shot-boundary detection compares color histograms and low-resolution images
  at approximately 5 FPS. It is a heuristic and may miss cuts or flag rapid pans.
- Track state resets at every flagged cut. Identities never carry across shots.
- Repeated-image comparison flags possible repeats only after earlier frames are
  available. It cannot detect every replay, especially new angles or edited footage.
  Static live scenes can be falsely flagged. There is no guaranteed replay detector.
- Manually marked replay intervals and suspected repeat frames suppress forecasts.
- There is no match-clock OCR or alignment of alternate angles to one live timeline.
- Analysis samples the video; very short events can be missed.

These conservative controls reduce mistakes; they do not solve broadcast editing.

## What the arrows mean

Arrows extrapolate observed **image-plane velocity** by 0.5 seconds. They are not
pitch-coordinate trajectories or tactical predictions. Camera pans and zooms
contaminate that measurement. Player/ball and team models, field homography, and
camera-motion compensation are future work. The detector currently detects people
only; it does not track the ball or estimate possession.

## Annotation and model-development workflow

The project developer will perform action labelling once footage can be retrieved.
The controls below are reviewer tools; the project owner is not required to label
actions. No generated or guessed labels are treated as verified training data.

### Train the experimental next-action model

For each observation:

1. Confirm Rodri at the observation timestamp, **before** the action.
2. Watch what actually happens next. Enter its later video timestamp and action.
3. Set a genuine match ID. **Use the same match ID for every clip, half and camera
   angle of that match.** Filenames default into this field only as a convenience;
   correct them before labelling.
4. Save the verified example. Do not label an interval that crosses a camera cut,
   contains a replay, or has uncertain identity.

Training requires at least **30 verified examples from 3 different matches** and
at least two action classes in the training matches. This threshold checks the
pipeline, not scientific sufficiency; many more examples and matches are needed.
The lexicographically last match ID is held out entirely for evaluation. Remaining
matches train the model. Do not repeatedly tune against that held-out match.
The saved model is not refitted to the held-out data after reporting metrics.

Select **Train & evaluate**. The application reports held-out accuracy, macro-F1,
log loss, and most-frequent-action accuracy. Scores appear above the video only
when there is a confirmed visible identity outside a replay interval.

The model is logistic regression on causal normalized image position, velocity,
speed and box size. It predicts the next human-labelled action, not the action
being performed now. It is not a trained visual action recognizer. Its scores are
uncalibrated and should not be presented as reliable real-world probabilities.
No fixed future-time horizon, learned sequence decoder, tactical explanation,
jersey OCR or automatic Rodri re-identification is supplied in this release.

The first trained artifact is `workspace/action_model.json`; all data remains
local. Export and back up your workspace separately from the source archive.

## Tests and reproducibility

```powershell
.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.venv\Scripts\python.exe -m pytest -q
```

See `TEST_REPORT.md` for actual executed checks and limits. The environment used
for testing is recorded in `TESTED_ENVIRONMENT.json`. `requirements-tested.txt`
pins direct dependencies to those observed versions; platform-specific transitive
PyTorch wheels are resolved by pip, so this is not a complete cross-platform lock.

## Structure

```
rodri-studio/
  run.py                     Local server entry point
  start_windows.bat          Windows setup/start launcher
  requirements*.txt          Runtime, test and observed-version dependencies
  models/yolo11n.pt          Generic pretrained person detector
  rodri_studio/
    app.py                   Uploads, analysis jobs, identity, labels, training
    vision.py                Detector, shot heuristics, conservative association
    pipeline.py              Bounded streaming clip analysis
    predictor.py             Trainable next-action classifier / held-out metrics
    render.py                Annotated video export
    static/index.html        Local visualization and review interface
  tests/                     Synthetic fixtures and API tests
  workspace/                 Created at runtime; private videos/data/models
```

## Current blockers and next development

No real match footage was analyzed during this build. The supplied Drive folder
became listable, but both files exceeded the connected downloader's 256 MiB
limit. Public download links redirected to sign-in. No Rodri identity gallery, action
labels or football evaluation scores were available to train from.

The next useful experiment is a real 30-second passage: audit detection quality,
confirm Rodri, review edits/replays, then collect consistent action labels from
several complete matches. Benchmark identity persistence before extending it.
A stronger predictor should add ball/team/context features and a temporal model,
then be evaluated on entirely unseen matches and calibrated before wider use.

## Third-party components

The bundled YOLO weights and Ultralytics package are from
https://github.com/ultralytics/ultralytics and
https://github.com/ultralytics/assets/releases . The associated AGPL-3.0 license
is included in `THIRD_PARTY_ULTRALYTICS_LICENSE.txt`. Other dependencies retain
their respective licenses. No claim is made that the weights recognize Rodri.
