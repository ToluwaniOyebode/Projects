"""Validate manually annotated R.O.D.R.I. event CSVs before training/evaluation.

This checks data integrity, not whether the labels are factually correct.
Standard library only.
"""
from __future__ import annotations
import argparse
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path

REQUIRED = {"match_id", "timestamp_seconds", "action"}
OPTIONAL = {"zone", "pressure", "ball_state"}
KNOWN_ACTIONS = {
    "receive", "short_pass", "long_pass", "carry", "shield", "shot", "press",
    "tackle", "interception", "clearance", "support_run", "track_opponent",
    "stoppage", "unknown",
}


def validate(path: str | Path) -> dict:
    errors, warnings = [], []
    per_match = defaultdict(list)
    actions = Counter()
    total = 0
    with open(path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        fields = set(reader.fieldnames or [])
        missing = REQUIRED - fields
        if missing:
            return {"ok": False, "rows": 0, "matches": 0, "actions": {},
                    "errors": ["Missing required columns: " + ", ".join(sorted(missing))],
                    "warnings": []}
        for line, row in enumerate(reader, start=2):
            total += 1
            match = (row.get("match_id") or "").strip()
            action = (row.get("action") or "").strip().lower()
            if not match:
                errors.append(f"Line {line}: match_id is empty")
            if not action:
                errors.append(f"Line {line}: action is empty")
            elif action not in KNOWN_ACTIONS:
                warnings.append(f"Line {line}: unfamiliar action label {action!r}; check spelling/taxonomy")
            try:
                timestamp = float(row.get("timestamp_seconds", ""))
                if timestamp < 0:
                    raise ValueError
            except (TypeError, ValueError):
                errors.append(f"Line {line}: timestamp_seconds must be a non-negative number")
                continue
            if match:
                per_match[match].append((timestamp, line))
            if action:
                actions[action] += 1
            for field in OPTIONAL & fields:
                if not (row.get(field) or "").strip():
                    warnings.append(f"Line {line}: {field} is blank; use 'unknown' if unavailable")
    for match, items in per_match.items():
        items.sort()
        for (t1, line1), (t2, line2) in zip(items, items[1:]):
            if t2 < t1:
                errors.append(f"Match {match!r}: timestamps go backwards at lines {line1}/{line2}")
            if t2 == t1:
                warnings.append(f"Match {match!r}: duplicate timestamp {t2:g}s at lines {line1}/{line2}")
    if total == 0:
        warnings.append("CSV contains a header but no event rows")
    return {"ok": not errors, "rows": total, "matches": len(per_match),
            "actions": dict(sorted(actions.items())), "errors": errors, "warnings": warnings}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("csv", type=Path)
    args = parser.parse_args()
    if not args.csv.is_file():
        raise SystemExit(f"CSV not found: {args.csv}")
    result = validate(args.csv)
    print(json.dumps(result, indent=2))
    raise SystemExit(0 if result["ok"] else 1)


if __name__ == "__main__":
    main()
