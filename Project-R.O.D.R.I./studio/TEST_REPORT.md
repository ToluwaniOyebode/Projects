# Source verification

28 automated checks passed on Linux CPU. They cover track crossing, camera-pan compensation, uncertain identity handling, causal sequence extraction and missing masks, ball association, temporal embargo, portable scoring, API validation, cut/identity/replay handling and evaluation accounting.

The prepared package also passed actual-video API and browser smoke tests, including identity selection, V4 outcome and conditional forecasts, evidence status, replay suppression and mobile layout. Software checks do not establish predictive accuracy or automatic player identification. Windows was not available for execution.

Dataset-specific metrics, labels and rendered review evidence remain in the separately prepared private package.

## 2026-10-26 edited-match integration

38 automated tests pass. New checks cover identical-image edit gaps, causal history masking, source-time mapping, labels spanning removals, original-match grouping, hash-registered uploads, no Rodri anchors on the generic match, and preserving V4 as the default while exposing V5 separately. JavaScript passes `node --check`.

A real clip was uploaded through the API, recognized by hash, analyzed with YOLO, and tested before/after actor confirmation. Both V4 and optional V5 produced finite normalized scores with edit provenance; the generic match appeared only in V5's training matches. No automatic player-name recognition was tested or claimed. The exported 96-second review is H.264, 1280×540, and shows all 32 added training examples; it is not a held-out accuracy video.

Training produced a mixed-player candidate and an explicit regression report: 5/12 correct versus 4/12 for V4, with worse macro-F1 and pass/receive recall. These are reused observations, not independent-match evidence. V4 stays the default.
