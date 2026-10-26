# V5 mixed-player candidate — 2026-10-26

Status: optional experimental checkpoint; **V4 remains the default Rodri model**. No claim of useful real-world forecasting accuracy or automatic Rodri recognition.

The added match is Real Madrid–Barcelona and does not contain Rodri. Its eight clips share the original match ID `real_madrid_barcelona_2017`. The 66 retained continuous spans and their source timestamps are registered separately from broadcast camera cuts. The prepared clips are not guaranteed to be free of every unmarked replay; admitted training examples received additional visual review.

## Data and fitting

- 32 added sparse single-AI-reviewed observations: 19 off-ball, 6 carry, 3 pass and 4 shot. No added receiving examples. This is not dense annotation of 75 minutes of footage, and no independent human audit was performed.
- 53 initial proposals were visually inspected; 28 were admitted and 25 rejected for ambiguity, tracking/camera changes, unsuitable actors or unclear timing. Four corrected shot observations were then added. Detector proposals alone are not labels.
- 89 eligible older observations plus 32 new observations: 121 fitting examples across three original matches. The 12 older reserved cases and six embargoed observations remain outside fitting and model selection.
- Input: existing 131-dimensional causal V4 feature representation. Explicit edit gaps stop historical sampling even when both sides look similar. Future frames supply labels and review displays, never input features.
- Twelve candidate configurations selected using leave-one-original-match-out development folds. All eight new clips remain together. Selected representation: current-frame/geometry subset; selected head: class-balanced random forest, depth 4. Other sequence-feature candidates were considered but did not win this development criterion.
- Conditional on-ball head is separate and uncalibrated. No new claim about unobserved passing intentions or future trajectories.

## Measured limitations

| Reused Rodri regression benchmark | V4 | V5 candidate |
|---|---:|---:|
| Correct / cases | 4 / 12 | 5 / 12 |
| Accuracy | 33.3% | 41.7% |
| Macro-F1 across five classes | 0.229 | 0.214 |
| Pass recall | 1 / 3 | 0 / 3 |
| Receive recall | 1 / 3 | 0 / 3 |

Majority accuracy on those cases is 33.3%. V5's one additional correct case does not establish an improvement: class-level performance deteriorated and the benchmark is small and previously scored. It is a regression comparison, not a new independent test.

The selected configuration's development CV accuracy is 40.5%, macro-F1 0.279. In the development fold leaving the added match out, accuracy is 34.4% versus a 59.4% majority baseline. Those folds were used for selection and are not an untouched final test. No independent new-match accuracy is available after fitting.

Model parameters were frozen before the regression comparison. V5 is retained for inspection through the `mixed` checkpoint option; it does not replace V4. Video identity confirmation remains necessary. The new footage never receives Rodri identity anchors, and its confirmed actors display as selected players.

Private prepared artifacts include reviewed rows, rejected proposals, causal feature cache, detailed training report, source hash registry, frozen checkpoint and a training-review video. Source commits contain none of the private videos, labels, learned weights or feature caches.
