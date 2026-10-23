# Project R.O.D.R.I. — next-action baseline

This folder is a CPU-first, standard-library-only baseline for predicting Rodri's next labelled action from manually verified action sequences. It does not yet identify Rodri or infer actions directly from video.

## Run

```bash
python -m unittest discover -s tests -v
python rodri_baseline.py data/events_template.csv
python rodri_baseline.py data/events_template.csv --evaluate --top-k 3
```

Replace illustrative template rows with verified labels before interpreting evaluation. Keep separate match IDs and evaluate by held-out match, never random frames. Begin with 100–300 accurately labelled Rodri actions across at least two matches; verify player identity before adding tracking features.