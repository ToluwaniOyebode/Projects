# Rebuild progress

Fresh implementation completed: local app, CPU person detector, per-shot temporary
tracks, human identity confirmation, camera/repeat heuristics, replay intervals,
image-motion visualization, next-action annotation, trainable linear classifier,
match-level holdout metrics, JSON export and annotated video rendering.

11 automated tests pass; YOLO CPU inference smoke test completed.

Incomplete: automatic Rodri identification, validated replay recognition, ball/
team/context extraction, trained Rodri forecasting, temporal sequence models,
calibration, real-footage evaluation and full browser/Windows testing.

Blocker: Drive folder now lists City–Chelsea and City–Inter videos. Both exceed the
connected downloader's 256 MiB limit; public links redirect to sign-in. No usable match video or
verified identity/action labels available. No claim of predictive accuracy.

Next: obtain accessible footage and validate a 30-second shot/replay/identity pilot.
