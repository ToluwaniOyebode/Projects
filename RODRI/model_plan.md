# R.O.D.R.I. model plan

## Observations
For each timestamp, store match_id, timestamp_seconds, track_id, bounding box, player foot-point, team_id (if confident), ball location/confidence, visibility, and manual Rodri identity confirmation.

## Identity
A generic tracker cannot establish player identity. Use team/lineup knowledge, jersey evidence where readable, appearance crops, temporal continuity, and manual corrections. Camera cuts and occlusions must be treated as identity uncertainty.

## Action vocabulary
Start with: receive, short_pass, long_pass, carry, shield, shot, press, tackle, interception, clearance, move_into_space, support_run, track_opponent, stoppage, unknown.

Annotate action start/end times, possession status, pressure, outcome, visibility and whether a major event ends the sequence. Unknown/occluded are valid labels.

## Training progression
1. Most-frequent-next-action baseline.
2. First-order action transition model.
3. GRU or temporal Transformer over recent action/situation tokens.
4. Optional visual embedding fusion after reliable labels exist.

## Evaluation
Hold out complete matches, never random adjacent frames from the same match. Report macro-F1, top-3 accuracy, log loss, calibration and event-boundary timing. Compare every model against the majority baseline.

## Data requirements
The current two matches can validate plumbing and support initial annotation. They are not sufficient to establish generalization. Expand to more matches and independently verified event labels before making performance claims.
