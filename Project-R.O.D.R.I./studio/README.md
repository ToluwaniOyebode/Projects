# Rodri Studio — local video research tools

This is the source code for the local video interface, person tracking, identity review, replay/camera safeguards, causal feature extraction, model training, evaluation and exports.

## Run on Windows

```powershell
py -3 -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe run.py
```

Open http://127.0.0.1:8000. A source-only checkout does not contain a trained action checkpoint. The prepared model package is supplied separately. Private videos, annotations, source manifests, feature caches, review clips and video-derived checkpoints are not published here.

For unfamiliar footage, analyze a short passage, pause and select Rodri's detected person box. Identity confirmation is separate from action labeling. The interface does not automatically recognize Rodri by name across novel footage.

## Tests

```powershell
.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.venv\Scripts\python.exe -m pytest -q
```

Fifteen local automated tests pass. They cover API operations, camera/identity guards, replay suppression, video decoding/export, causal timestamp access, motion feature shapes and checkpoint serialization. Tests are synthetic software checks and do not establish real-world prediction quality.

## Train with local reviewed data

Place reviewed annotations at `data/reviewed_events.json` and retain source videos locally. The schema includes unique observation IDs, match/episode IDs, a source filename, causal observation time, later target time, actor box, coarse target action and review/exclusion fields. Use only labels whose identity and action evidence you have reviewed.

```powershell
.venv\Scripts\python.exe scripts/train_visual.py --videos "C:\path\to\videos" --held-out MATCH_ID --out models/next_action.json
```

This compares feature families using training-only episode folds, fits a head, and records an entire separate match as a development holdout. `--refit-all` explicitly refits after recording development results; this does not produce an independent test score. With only iterative development matches, no claim of pristine final evaluation is justified.

Runtime motion-only inference does not need the appearance encoder; first-time appearance comparisons download ImageNet ResNet18 weights. YOLO detector weights download on first use if not present locally.

## Limits

Forecasts require an externally confirmed actor location. Camera changes, occlusions, similar kits, replay edits and small distant players remain difficult. Ball-proximity blobs are heuristics, not a reliable ball detector. Scores are uncalibrated and no reliable tactical accuracy is claimed. Original recordings and checkpoints supplied privately must remain local unless their publication is explicitly authorized.
