import argparse, csv, json
from collections import Counter, defaultdict

REQUIRED = {"match_id", "timestamp_seconds", "action"}
CONTEXT = ("zone", "pressure", "ball_state")

def read_events(path):
    with open(path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        missing = REQUIRED - set(reader.fieldnames or [])
        if missing:
            raise ValueError("Missing CSV columns: " + ", ".join(sorted(missing)))
        events = []
        for line, row in enumerate(reader, 2):
            match = (row.get("match_id") or "").strip()
            action = (row.get("action") or "").strip().lower()
            if not match or not action:
                raise ValueError(f"Line {line}: match_id/action cannot be empty")
            try:
                t = float(row["timestamp_seconds"])
            except (TypeError, ValueError):
                raise ValueError(f"Line {line}: timestamp_seconds must be numeric")
            if t < 0:
                raise ValueError(f"Line {line}: timestamp_seconds cannot be negative")
            e = {"match_id": match, "timestamp_seconds": t, "action": action, "_line": line}
            for c in CONTEXT:
                e[c] = (row.get(c) or "unknown").strip().lower() or "unknown"
            events.append(e)
    return sorted(events, key=lambda e: (e["match_id"], e["timestamp_seconds"], e["_line"]))

def key(e):
    return (e["action"], e["zone"], e["pressure"], e["ball_state"])

class NextActionBaseline:
    def fit(self, events):
        self.global_counts, self.by_action, self.by_context = Counter(), defaultdict(Counter), defaultdict(Counter)
        self.labels = {e["action"] for e in events}
        groups = defaultdict(list)
        for e in events:
            groups[e["match_id"]].append(e)
        for group in groups.values():
            group.sort(key=lambda e: (e["timestamp_seconds"], e.get("_line", 0)))
            for cur, nxt in zip(group, group[1:]):
                self.global_counts[nxt["action"]] += 1
                self.by_action[cur["action"]][nxt["action"]] += 1
                self.by_context[key(cur)][nxt["action"]] += 1
        if not self.global_counts:
            raise ValueError("Need at least two events in training data")
        return self

    @staticmethod
    def ranked(counts, k):
        total = sum(counts.values())
        return [{"action": a, "probability": n / total, "count": n}
                for a, n in counts.most_common(k)] if total else []

    def predict(self, current, k=3):
        if k < 1:
            raise ValueError("k must be >= 1")
        counts = self.by_context.get(key(current), Counter())
        level = "action+context"
        if not counts:
            counts = self.by_action.get(current["action"], Counter())
            level = "action"
        if not counts:
            counts, level = self.global_counts, "global"
        return {"backoff_level": level, "predictions": self.ranked(counts, k)}

    def evaluate_leave_one_match_out(self, events, k=1):
        ids = sorted({e["match_id"] for e in events})
        if len(ids) < 2:
            raise ValueError("Need at least 2 matches for held-out-match evaluation")
        hit = total = 0
        majority_hit = majority_total = 0
        per_match = {}
        for held in ids:
            train = [e for e in events if e["match_id"] != held]
            test = [e for e in events if e["match_id"] == held]
            model = NextActionBaseline().fit(train)
            majority_action = model.global_counts.most_common(1)[0][0]
            mh = mt = bh = bt = 0
            for cur, nxt in zip(test, test[1:]):
                pred = model.predict(cur, k)["predictions"]
                if pred:
                    mt += 1
                    mh += int(nxt["action"] in {p["action"] for p in pred})
                bt += 1
                bh += int(nxt["action"] == majority_action)
            hit += mh
            total += mt
            majority_hit += bh
            majority_total += bt
            per_match[held] = {
                "correct": mh, "evaluated": mt,
                "top_k_accuracy": mh / mt if mt else None,
                "majority_action": majority_action,
                "majority_correct": bh, "majority_evaluated": bt,
                "majority_top1_accuracy": bh / bt if bt else None,
            }
        model_accuracy = hit / total if total else None
        majority_accuracy = majority_hit / majority_total if majority_total else None
        return {
            "split": "leave-one-match-out", "k": k,
            "correct": hit, "evaluated": total,
            "top_k_accuracy": model_accuracy,
            "majority_baseline": {
                "correct": majority_hit, "evaluated": majority_total,
                "top1_accuracy": majority_accuracy,
            },
            "accuracy_lift_vs_majority": (
                model_accuracy - majority_accuracy
                if model_accuracy is not None and majority_accuracy is not None else None
            ),
            "per_match": per_match,
        }

def main():
    p = argparse.ArgumentParser(description="CPU-only transition baseline for Rodri action labels")
    p.add_argument("csv")
    p.add_argument("--evaluate", action="store_true")
    p.add_argument("--match")
    p.add_argument("--index", type=int, default=-1)
    p.add_argument("--top-k", type=int, default=3)
    a = p.parse_args()
    events = read_events(a.csv)
    if a.evaluate:
        print(json.dumps(NextActionBaseline().evaluate_leave_one_match_out(events, a.top_k), indent=2))
    elif a.match:
        chosen = [e for e in events if e["match_id"] == a.match]
        if not chosen:
            raise SystemExit("Unknown match_id: " + a.match)
        training = [e for e in events if e["match_id"] != a.match]
        model = NextActionBaseline().fit(training if training else events)
        current = chosen[a.index]
        print(json.dumps({"current_event": {k:v for k,v in current.items() if not k.startswith("_")},
                          "forecast": model.predict(current, a.top_k)}, indent=2))
    else:
        model = NextActionBaseline().fit(events)
        print(json.dumps({"events": len(events), "matches": len({e["match_id"] for e in events}),
                          "action_classes": sorted(model.labels),
                          "next_action_distribution": model.ranked(model.global_counts, a.top_k)}, indent=2))

if __name__ == "__main__":
    main()
