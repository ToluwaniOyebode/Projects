# Rodri Studio source

Local football-video analysis with person tracks, identity confirmation, camera/replay review and next-action visualization. V4 supports off-ball movement, receiving, carrying, passing and shooting, plus a separate conditional on-ball distribution.

This GitHub folder contains source code. Trained checkpoints, reviewed examples, feature caches and private review videos are distributed separately in the prepared model package. A source-only checkout reports an untrained state until a compatible checkpoint is supplied.

Use Python 3.12 or 3.11. With the complete prepared package, run `start_windows.bat` on Windows, or install `requirements.txt` and run `python run.py`. Open http://127.0.0.1:8000. Load a local video, analyze a passage, pause and confirm the target person. No action labeling is required to use a prepared checkpoint. CPU processing may be slower than playback.

Tracking uses Hungarian assignment, camera compensation, velocity and jersey appearance. Confirmation expires and does not transfer across cuts. Ambiguous associations require confirmation again. This is not a general automatic Rodri name recognizer; tracks and uncertainty heuristics can fail.

V4 extracts up to three seconds of causal actor/ball/nearby-player context, stopping at cuts or lost/ambiguous identity. Missing evidence is masked. The viewer exposes usable history and learned-ball candidates. The hybrid representation also retains older motion/proximity cues; ball candidates are uncertain. Team context is a jersey-color heuristic.

The observed-outcome model and conditional on-ball head are distinct. Receiving depends on pass delivery; conditional scores do not reveal a passer's unobserved intention. Scores are uncalibrated. Trails display observed image motion. No validated future-trajectory claim is made.

`scripts/extract_sequence.py` encodes reviewed observations. `scripts/train_sequence.py` groups temporal neighbors, embargoes reserved clusters, selects using development-only GroupKFold and freezes parameters before scoring reserved episodes. An episode holdout from a previously used match must not be presented as unseen-match accuracy. `scripts/evaluate_reviewed.py` renders all supplied review cases, including errors. See the prepared package's model card for measured limitations; useful generalization is not established.

Run software checks with `python -m pytest -q`. See THIRD_PARTY_MODELS.md for pretrained perception-model provenance. Private data, learned checkpoints and video exports are excluded from source commits.

## Edited-match training support

Eight prepared Real Madrid–Barcelona clips are treated as **one original match**, with Rodri explicitly absent. They contain 75m53.2s of edited footage. The prepared V5 model update supplies their hash registry, source-time maps, 32 sparse single-AI-reviewed examples and an optional mixed-player checkpoint. The complete match is not densely action-labelled. These examples must not be represented as Rodri observations.

Install the separately supplied model update into this `studio` directory after updating the source. Run Studio normally, load one of the existing edited MP4s, analyze a passage, select the player, and choose **V5 · experimental mixed-player candidate** to try the added model. No action labelling is required for inference. V4 remains the default Rodri checkpoint. A source-only checkout has neither checkpoint.

To register validated edited clips for a local training run:

```powershell
python scripts/register_edited_match.py --clips "C:\matches\edited" --metadata "C:\matches\match_edit_metadata.zip"
python scripts/extract_sequence.py --videos "C:\matches\edited" --data data/general_2017
python scripts/train_mixed.py
```

Registration verifies the video hashes before updating the registry and creates `.mp4.edits.json` sidecars. Keep these beside videos used by the CLI. Studio restores the timeline when an exact registered video is uploaded, even if renamed. Tracking, causal history and annotation windows respect explicit edit boundaries as well as detected camera cuts. Registered clips cannot be relabelled with different match IDs to manufacture independent folds.

V5 uses whole-original-match development folds, excluding the older reserved/embargoed observations from fitting. Its 5/12 result versus V4's 4/12 is on **reused regression cases**, not new independent test accuracy. Macro-F1 fell from 0.229 to 0.214, and pass/receive performance regressed. Useful improvement is not established. See [MODEL_CARD_V5.md](MODEL_CARD_V5.md).

`scripts/render_mixed_review.py --videos "C:\matches\edited" --out demo/mixed-review.mp4` renders every added training case, including errors. Its video is a training illustration, not a held-out performance demonstration.
