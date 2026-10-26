# Kaggle detector retraining — 26 October 2026

This update retrains **player perception**, not the V4/V5 next-action classifier. The verified Kaggle samples do not supply adequate player-specific future-action supervision. A two-class event-clip fit on one scoring and one red-card sample would not establish a useful action model.

## What was trained

Fine-tuned YOLO11n on 30 annotated SoccerTrack drone frames (660 person boxes). Retained the pretrained 80-class head and trained person class 0. Ball labels were excluded; the separately supplied ball detector is unchanged.

The first eight-epoch candidate adapted to the drone view but regressed on broadcast actor recovery. A second eight-epoch run combined those verified drone labels with 30 additional frames from the existing edited broadcast match, containing 339 automatic person boxes from the original detector. These rehearsal labels preserve prior behaviour; they are explicitly **pseudo-labels**, not verified annotations. Exact and nearby reviewed actor observations were excluded from rehearsal sampling by a five-second window.

CPU run: 1024-pixel input, batch 2, AdamW, initial learning rate 0.0005, backbone freeze 10, seed 42. Per-epoch results and full arguments are in the separate model package.

## Measured results

Confidence threshold 0.30 and matching IoU 0.50 were fixed for these comparisons.

| Check | Original | Drone-only candidate | Mixed-data candidate |
| --- | ---: | ---: | ---: |
| Matched player boxes in 8 drone regression frames | 0/176 | 156/176 | 164/176 |
| Unmatched detections in those frames | 0 | 43 | 50 |
| Drone-frame detection F1 | 0.000 | 0.832 | 0.841 |
| Previously reviewed broadcast actors recovered | 29/32 | 13/32 | 30/32 |

The mixed candidate's drone precision is 76.6%, recall 93.2%. Extra people outside the 22 labelled players can count as unmatched detections. These figures are **not action-prediction accuracy**.

The eight drone regression frames and eight development frames are from the same 30-second video as the training frames, with temporal gaps. The regression frames were reused after the first experiment. The broadcast cases are sparse single-AI-reviewed labels from one previously used match, and were inspected during development. They cannot measure whole-frame precision. There is **no untouched independent-match result**. No overall model completion percentage is changed by these results.

## Deployment

The mixed candidate is available as the optional **YOLO · Kaggle candidate (experimental)** detector. The standard YOLO detector remains the default because general broadcast performance has not been established. No V4/V5 checkpoint or default person/ball weights were overwritten.

Install `models/kaggle_person_candidate.pt` from the separate retraining package into this `studio/models` directory, update the source, restart Studio, choose the optional detector and analyze a newly uploaded passage. Existing analyses and labels stay intact. A missing candidate file produces an installation error rather than downloading unrelated weights. Action scores remain the existing experimental V4/V5 outputs, using their original feature-extraction detector; end-to-end prediction under this optional perception change is not validated.

## Reproduce

Use the separately downloaded Kaggle starter samples and the eight original edited clips:

```powershell
python scripts/train_kaggle_detector.py --samples C:\matches\kaggle_football_starter --out C:\experiments\kaggle_detector --broadcast-directory C:\matches\edited
python scripts/evaluate_detector_retention.py --videos C:\matches\edited --candidate C:\experiments\kaggle_detector\soccertrack_person_candidate.pt --out C:\experiments\kaggle_detector\broadcast_regression.json
```

Sources: [SoccerTrack dataset](https://www.kaggle.com/datasets/atomscott/soccertrack), [Ultralytics YOLO](https://github.com/ultralytics/ultralytics). Kaggle reports SoccerTrack as LGPL-3.0; the derived detector uses the Ultralytics AGPL-3.0 terms, included with the model package. The original dataset CSV and metadata are in the starter package.

Validation: 44 automated tests, JavaScript syntax, successful CPU training and reproducible thresholded evaluation. The model package includes both runs' reports, split manifests, logs, candidate weights and a sampled side-by-side comparison.
