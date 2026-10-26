# All-player development and repository review

Reviewed 2026-10-26. Priority: visible-person tracking, player action recognition, causal anticipation, then optional Rodri specialization. Tracking IDs do not imply names, teams, or full-match identity.

| Repository | Useful contribution | Integration decision |
| --- | --- | --- |
| [abdullahtarek/football_analysis](https://github.com/abdullahtarek/football_analysis) | Batched YOLO, ByteTrack, kit-colour clustering, ball proximity, optical flow | Added an independent bounded-batch detector interface to our existing pipeline. Existing camera-compensated tracker stays in place. No source copied; no license file was present in the inspected tree. |
| [SoccerNet/sn-spotting](https://github.com/SoccerNet/sn-spotting) | Broadcast event-spotting baselines and pretrained models | Candidate event recognition branch. Event labels alone do not identify the actor. Check temporal lookahead and feature preprocessing before reuse. Not installed as a trained component. |
| [deltatrelabs/deltatre-microsoft-ai-soccer-action-recognition](https://github.com/deltatrelabs/deltatre-microsoft-ai-soccer-action-recognition) | Released shot-recognition prototypes | Older dependency stack and narrow shot task; no immediate replacement for player action forecasting. Not installed. |
| [lRomul/ball-action-spotting](https://github.com/lRomul/ball-action-spotting) | Pretrained PASS/DRIVE spotter and shared visual encoding | Promising recognition baseline. Centered temporal windows can use future frames; cannot count as causal anticipation. Not installed. |
| [SoccerNet/sn-gamestate](https://github.com/SoccerNet/sn-gamestate) | Roles, team/jersey inference, tracking, pitch calibration | Stronger all-player target architecture; isolate its older environment before integration. Not installed. |
| [JeremieOchin/FOOTPASS](https://github.com/JeremieOchin/FOOTPASS) | Player-centric action labels and shared video backbone with per-track ROI features | Closest match for who-did-what recognition. Dataset access requires agreement; no ready football checkpoint was identified in the reviewed tree. Not installed. |
| [MohamadDalal/FAANTRA](https://github.com/MohamadDalal/FAANTRA) | Future football event anticipation baseline | Relevant future-stage benchmark, with match events rather than named player targets. No ready arbitrary-video checkpoint was identified. Not installed. |

## Changes implemented

- New uploads and analyses default to general football, without automatically seeding a particular player's identity.
- All person boxes are visible by default. Optional manual selection supports detailed review.
- YOLO runs bounded four-frame batches; tracking, cut resets, replay checks and source-time mapping remain chronological.
- `/api/videos/{uid}/players?time=...` exports all visible anonymous person candidates with shot-scoped keys.
- Optional `actions=true` evaluates the existing V5 mixed-player pilot for each candidate, shares existing perception caches, and suppresses uncertain associations and replay frames. It never silently substitutes the Rodri checkpoint if V5 is absent.
- The interface exposes these scores on demand at a paused timestamp. CPU throughput is not claimed to be real time.

## What must not transfer from the tutorial unchanged

Its pitch transform uses fixed sample-video coordinates, team assignment includes a particular track-ID override, and missing-ball interpolation uses later frames. These do not provide general calibration, general identities, or causal evidence. Current source tree: `e4799632cdf271cf57f4eb0c4d872cf1b7ab0f17`. No code or weights from this repository were bundled.

## Completion assessment

The project is a working research prototype, not a completed predictive model. Prepared video import, edit provenance, anonymous tracking, review UI and evaluation tooling work. General action recognition is an early pilot; reliable anticipation and independent-match validation are incomplete. Rodri specialization is deferred. Automated software tests do not establish football accuracy. V5's earlier whole-match development result was 40.5% accuracy, macro-F1 0.279; on the added match's held-out fold, 34.4% accuracy was below the 59.4% majority baseline. No accuracy improvement is claimed for this engineering update.

## Validation of this update

40 automated tests pass, including batch-versus-sequential tracking equivalence across a camera cut and all-player API abstention. Browser JavaScript passes `node --check`. A narrow warmed CPU detector check on four frames of the supplied match measured 0.271/0.193 seconds for sequential calls versus 0.222/0.156 seconds for four-frame calls. Counts matched (9,16,11,10). These two short repetitions suggest about 19% lower detector-call time here; they do not establish full-pipeline speed, detection accuracy, or real-time performance.

A real edited-match API smoke test analyzed eight sampled frames, returned nine anonymous tracks at the first timestamp, and produced nine experimental V5 outputs without manual identity selection. Edited time 10.0 seconds mapped to original source time 292.0 seconds. The combined short analysis and scoring check took 6.42 seconds on this CPU.
