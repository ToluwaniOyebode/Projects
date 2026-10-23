# Project R.O.D.R.I. — Vision Integration v1

This is a Windows-first integration wrapper for the open-source Roboflow Sports soccer pipeline. The immediate goal is a **working perception smoke test**: run pretrained player tracking on a short clip and inspect the output before attempting Rodri-specific action prediction.

## Why reuse models?
The upstream Roboflow Sports example already provides player, ball and pitch detection, team classification, player tracking, and radar visualization. We should reuse these pretrained components rather than train a detector from scratch.

Upstream repositories:
- https://github.com/roboflow/sports
- https://github.com/SoccerNet/sn-tracking
- https://github.com/SoccerNet/sn-spotting

## Windows setup

Requirements: Python 3.10 or 3.11, Git, FFmpeg, and PowerShell. A compatible NVIDIA GPU is optional; CPU mode is supported but slower.

From the repository root:

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\RODRI\scripts\setup_windows.ps1
```

Run a 45-second tracking test (replace the path and start time):

```powershell
.\RODRI\scripts\run_tracking.ps1 -VideoPath "C:\path\to\match.mp4" -StartSeconds 600 -DurationSeconds 45 -Device cpu
```

Outputs are written to `RODRI/outputs`. The script deliberately limits the first run to at most 180 seconds; do not start by processing a full 90-minute match on CPU.

## What this does and does not do

It runs generic player tracking. It **does not identify Rodri automatically** and does not predict his next action. Track IDs can switch after occlusion or camera cuts. We must manually verify the correct track, build timestamped event labels, and evaluate a separate sequence model on held-out matches.

## Planned model stages

1. Perception smoke test on a short clip.
2. Manually verify Rodri identity in sampled frames and record track corrections.
3. Export timestamped player positions, ball context and visibility.
4. Annotate actions: receive, short pass, long pass/switch, carry, shield, shot, press, tackle, interception, clearance, move into space, support run, track opponent, stoppage, unknown.
5. Train and compare: majority baseline → first-order transition model → GRU/temporal Transformer.
6. Evaluate on whole held-out matches using macro-F1, top-3 accuracy, log loss, calibration and event-boundary timing.

## Licensing

The upstream Roboflow Sports repository describes its sports utility code as MIT-licensed, while its YOLOv8 integration uses Ultralytics, which is AGPL-3.0. Individual weights and dependencies may have separate terms. Review the applicable licenses before redistribution or commercial use.
