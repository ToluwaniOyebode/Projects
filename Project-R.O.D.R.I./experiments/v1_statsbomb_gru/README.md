# R.O.D.R.I. V1 — StatsBomb event-sequence GRU baseline

## Purpose
First recorded event-sequence baseline for Project R.O.D.R.I. It predicts the next **event type in a general football event stream** from the previous eight event types. It does not yet predict Rodri's personal next action from video.

## Dataset and split
- Source: [StatsBomb Open Data](https://github.com/StatsBomb/open-data) (the Colab notebook cloned the Hudl mirror at https://github.com/hudl/open-data).
- Training matches: 3,396
- Held-out test matches: 839
- Training sequences: 11,891,421
- Test sequences: 2,948,870
- Context length: 8 previous events
- Split: deterministic whole-match split using SHA-256 hash modulo 5, approximately 80/20.
- Exact source repository commit/data version was not recorded in the experiment output and should be pinned for a strict rerun.

## Model and training
- Model: embedding + GRU event-type sequence classifier
- Embedding dimension: 48
- Hidden dimension: 96
- Dropout: 0.2
- Optimizer: AdamW
- Learning rate: 0.001
- Epochs: 12
- Runtime device: CUDA
- Training loss by epoch: 0.9125, 0.9012, 0.8981, 0.8965, 0.8955, 0.8949, 0.8944, 0.8941, 0.8938, 0.8936, 0.8934, 0.8932.

## Results
- GRU accuracy: 0.728648 (72.86%)
- GRU macro-F1: 0.330091
- Majority-class baseline accuracy: 0.275124 (27.51%)
- Majority-class baseline macro-F1: 0.012692

The GRU substantially exceeds the majority baseline on accuracy, but performance is uneven across event types. It performs well on common classes such as Ball Receipt, Carry and Pass, while recall is very low for some important events, including Shot, Interception and Block. See `classification_report.csv`.

## Important evaluation note
The test metrics and class-level report have already been inspected during model development. Treat this test split as a development result, not a fresh untouched final benchmark. The next experiment should introduce a separate validation split and a new held-out test set, grouped by match.

## Reproducibility and artifact status
This commit records the reported metrics and classification report. It does **not** contain the trained checkpoint, vocabulary, original notebook, or a fully pinned dataset snapshot because their saved files were not verified as available during transfer. Add those artifacts only after exporting and checking them from Colab/Drive. Do not claim the checkpoint is archived until it is uploaded.

## Next steps
1. Audit class imbalance and event taxonomy.
2. Compare weighted loss/focal loss on validation matches.
3. Add structured context (player/team, possession, location, outcome and time) where available.
4. Move from general event prediction to player-specific action prediction, then connect video/tracking.
