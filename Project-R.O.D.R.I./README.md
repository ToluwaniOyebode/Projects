# Project R.O.D.R.I. — Rodri Studio

The current local video application and training/test tools are in **[studio](studio/README.md)**.

```powershell
cd Project-R.O.D.R.I./studio
py -3 -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe run.py
```

Open http://127.0.0.1:8000. A source-only checkout has no trained next-action checkpoint; the prepared model package is provided separately. Private video-derived annotations and checkpoints are not published here.

The code includes tracking, identity review, camera/replay safeguards, causal motion and visual features, training/evaluation, and exports. Fifteen automated tests pass locally. Real-world predictive reliability and automatic player-name recognition are not established.

Earlier starter scripts remain for reference. The Studio implementation is independent of them.
