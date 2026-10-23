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
    last_timestamp = {}
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
                if match in last_timestamp:
                    previous_timestamp, previous_line = last_timestamp[match]
                    if timestamp < previous_timestamp:
                        errors.append(
                            f"Match {match!r}: timestamp goes backwards from "
                            f"line {previous_line} ({previous_timestamp:g}s) "
                            f"to line {line} ({timestamp:g}s)"
                        )
                    elif timestamp == previous_timestamp:
                        warnings.append(
                            f"Match {match!r}: duplicate timestamp {timestamp:g}s "
                            f"at lines {previous_line}/{line}"
                        )
                last_timestamp[match] = (timestamp, line)
                per_match[match].append((timestamp, line))
            if action:
                actions[action] += 1
            for field in OPTIONAL & fields:
                if not (row.get(field) or "").strip():
                    warnings.append(f"Line {line}: {field} is blank; use 'unknown' if unavailable")
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
