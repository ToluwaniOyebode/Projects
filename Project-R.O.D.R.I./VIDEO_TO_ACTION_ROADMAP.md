# Video-to-action milestone plan

This document defines the next measurable milestone for Project R.O.D.R.I.

## Current state

The repository has a transition-table baseline, a local video sampler, a browser annotation tool, a video inventory utility, a CSV validator, and automated tests. These are development foundations only. No Rodri detector or video-trained predictor has been validated yet.

## Milestone A — establish a real labelled pilot

1. Inventory the local source videos and retain a stable mapping from each source video to its match ID.
2. Sample short sections to locate clear Rodri possession sequences.
3. Create human-verified event labels from at least two distinct matches.
4. Run the validator and leave-one-match-out evaluation.
5. Record baseline metrics, event counts, unknown-label rate, and class distribution.

**Exit criteria:** at least 100 verified events across two matches; all labels traceable to source timestamps; validator clean apart from reviewed warnings; evaluation output saved with no within-match leakage.

## Milestone B — perception prototype

1. Compare an off-the-shelf person detector on sampled frames.
2. Add multi-object tracking to maintain short-term track IDs.
3. Do not equate a track ID with Rodri. Evaluate identity continuity across camera cuts and similar-looking players.
4. Keep manual identity confirmation as a fallback until player re-identification is measured.

**Exit criteria:** documented precision/recall on a manually reviewed frame sample and an explicit identity-switch audit.

## Milestone C — action recognition and forecasting

1. Start with a small, operational action taxonomy.
2. Use temporal windows around labelled events rather than single still images alone.
3. Compare visual action classification against the transition baseline.
4. Evaluate on an entire held-out match.
5. For variable-length forecasts, define stop events and report both action accuracy and sequence-level metrics.

## Reporting rule

Never report template-row metrics as real performance. Keep code completion, data readiness, and predictive quality as separate measures. The project's overall percentage should rise materially only when a milestone's exit criteria are met.
