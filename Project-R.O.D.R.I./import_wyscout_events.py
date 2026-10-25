"""Convert Wyscout-style event JSON into R.O.D.R.I. candidate action CSV.

This supports the public Wyscout event schema (events with player, team, type,
matchPeriod, minute, second, positions, and outcome). It does not download data.
Rows are candidate labels, not verified observations of Rodri or video timestamps.
"""
import argparse
import csv
import json
from pathlib import Path

PERIODS = {"1H": 1, "2H": 2, "E1": 3, "E2": 4, "P": 5}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("json_file")
    parser.add_argument("--out", default="data/wyscout_candidates.csv")
    parser.add_argument("--player", default="Rodri")
    parser.add_argument("--team", default="Manchester City")
    parser.add_argument("--include-all-players", action="store_true")
    args = parser.parse_args()

    raw = json.loads(Path(args.json_file).read_text(encoding="utf-8"))
    events = raw.get("events", raw) if isinstance(raw, dict) else raw
    if not isinstance(events, list):
        raise SystemExit("Expected a JSON list of events or an object containing an 'events' list.")

    out = []
    for e in events:
        if not isinstance(e, dict):
            continue
        player = e.get("player") or {}
        team = e.get("team") or {}
        player_name = player.get("name", "") if isinstance(player, dict) else str(player)
        team_name = team.get("name", "") if isinstance(team, dict) else str(team)
        if not args.include_all_players and args.player.casefold() not in player_name.casefold():
            continue
        if args.team and team_name and args.team.casefold() not in team_name.casefold():
            continue
        period = str(e.get("matchPeriod", ""))
        minute = int(e.get("minute") or 0)
        second = float(e.get("second") or 0)
        positions = e.get("positions") or []
        start = positions[0] if positions else {}
        end = positions[1] if len(positions) > 1 else {}
        typ = e.get("type") or {}
        outcome = e.get("outcome") or {}
        tags = e.get("tags") or []
        out.append({
            "match_id": e.get("matchId", ""),
            "timestamp_seconds": f"{minute * 60 + second:.3f}",
            "match_period": PERIODS.get(period, period),
            "match_clock_minute": minute,
            "match_clock_second": second,
            "player": player_name,
            "team": team_name,
            "action": typ.get("name", "") if isinstance(typ, dict) else str(typ),
            "outcome": outcome.get("name", "") if isinstance(outcome, dict) else str(outcome),
            "start_x": start.get("x", ""),
            "start_y": start.get("y", ""),
            "end_x": end.get("x", ""),
            "end_y": end.get("y", ""),
            "tags_json": json.dumps(tags, ensure_ascii=False),
            "annotation_source": "wyscout_event_candidate",
            "verification_status": "needs_video_match_and_action_verification",
        })

    dest = Path(args.out)
    dest.parent.mkdir(parents=True, exist_ok=True)
    fields = ["match_id", "timestamp_seconds", "match_period", "match_clock_minute",
              "match_clock_second", "player", "team", "action", "outcome",
              "start_x", "start_y", "end_x", "end_y", "tags_json",
              "annotation_source", "verification_status"]
    with dest.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(out)
    print(f"Wrote {len(out)} candidate events to {dest}")
    print("Wyscout timestamps are match-clock candidates, not video offsets.")
    print("Match period offsets, stoppages, broadcast edits, and event accuracy still need checking.")


if __name__ == "__main__":
    main()
