"""Roll out a variable-length next-action forecast from a seed match context.

Train on all matches except --seed-match, then forecast from the final labelled
event in that held-out match. This is an experimental transition baseline, not
a learned video model. Probabilities are local transition frequencies.
"""
import argparse
import json
from pathlib import Path
from rodri_baseline import NextActionBaseline, read_events


DEFAULT_STOPS = {"shot", "tackle", "interception", "clearance", "stoppage", "goal"}


def forecast_sequence(model, seed, max_steps=12, stop_actions=None, top_k=1):
    if max_steps < 1:
        raise ValueError("max_steps must be >= 1")
    stop_actions = {x.strip().lower() for x in (stop_actions or DEFAULT_STOPS)}
    current = dict(seed)
    sequence = []
    for step in range(1, max_steps + 1):
        result = model.predict(current, k=top_k)
        choices = result["predictions"]
        if not choices:
            break
        best = choices[0]
        action = best["action"]
        sequence.append({
            "step": step,
            "action": action,
            "probability": best["probability"],
            "backoff_level": result["backoff_level"],
        })
        if action in stop_actions:
            break
        current["action"] = action
    return sequence


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("events_csv")
    p.add_argument("--seed-match", required=True, help="Match held out from training")
    p.add_argument("--max-steps", type=int, default=12)
    p.add_argument("--stop-actions", default="shot,tackle,interception,clearance,stoppage,goal")
    p.add_argument("--top-k", type=int, default=1, help="Currently chooses the top-ranked action at each step; retained for future branching support")
    p.add_argument("--out", default="forecast.json")
    args = p.parse_args()
    events = read_events(args.events_csv)
    seed_events = [e for e in events if e["match_id"] == args.seed_match]
    train = [e for e in events if e["match_id"] != args.seed_match]
    if not seed_events:
        raise SystemExit(f"No events found for seed match: {args.seed_match}")
    if not train:
        raise SystemExit("Need at least one other match to train on; seed match is held out.")
    seed = seed_events[-1]
    model = NextActionBaseline().fit(train)
    stops = {x.strip().lower() for x in args.stop_actions.split(",") if x.strip()}
    sequence = forecast_sequence(model, seed, args.max_steps, stops, top_k=1)
    report = {
        "mode": "held-out-match greedy rollout",
        "seed_match": args.seed_match,
        "seed_timestamp_seconds": seed["timestamp_seconds"],
        "seed_action": seed["action"],
        "training_matches": sorted({e["match_id"] for e in train}),
        "forecast": sequence,
        "warning": "Illustrative transition-frequency forecast only. Not a calibrated probability of an entire sequence and not a video-derived prediction."
    }
    Path(args.out).write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
