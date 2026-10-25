# Rodri Studio source

Local video analysis with person tracks, identity confirmation, camera/replay review and next-action visualization. The forecasting interface supports off-ball movement, receiving, carrying with possession, passing and shooting, plus a separate conditional on-ball action distribution.

This GitHub folder contains source code. The prepared trained checkpoints, reviewed examples, feature cache and private review videos are distributed separately. A source-only checkout reports an untrained state until a compatible checkpoint is provided.

Use Python 3.12 or 3.11. With the complete model package, run `start_windows.bat` on Windows or install `requirements.txt` and run `python run.py`. Open http://127.0.0.1:8000. Load a local video, analyze a passage and confirm the target player in a shot. Identity expires and does not transfer across camera cuts. No action labeling is required to use a prepared checkpoint.

The observed-outcome model and conditional on-ball head are distinct. Receiving depends on delivery of a pass; conditional scores do not infer unobserved intentions. Scores are uncalibrated. Movement trails display observed image motion; learned future arrows are shown only when enabled by checkpoint validation.

`train_temporal.py` compares causal feature/classifier configurations using episode-separated cross-validation. `--selection development` explicitly uses the development match for selection and must not be described as independent testing. Models use parameter-only JSON serialization; the scorer is tested against sklearn. `evaluate_reviewed.py` includes all supplied review cases and retains unsupported labels.

New videos require a target-player identity confirmation. This is not a general automatic Rodri name recognizer. Tracking, camera-cut detection and replay flags can fail. See the complete prepared package’s model card for dataset-specific results.

Run software checks with `python -m pytest -q`. See THIRD_PARTY_MODELS.md for pretrained perception model provenance. Video-derived labels and learned private checkpoints are not included here.
