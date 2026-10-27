# Pitchside API

Base URL: `http://127.0.0.1:8105/api`.

Send JSON objects with `Content-Type: application/json`. Bodies over 1 MiB are rejected. Errors use `{"error":"message"}`: 400 invalid input, 403 cross-origin writes, 404 unknown resource, 409 conflict, 413 oversized request, 415 unsupported content type. Successful requests return 200, including creates. There is no authentication; this API is designed for local use.

| Method | Path after /api | Contract                                                             |
| ------ | --------------- | -------------------------------------------------------------------- |
| GET    | `/health`       | `ok` and project name.                                               |
| GET    | `/match`        | Match label, teams, players and total event count.                   |
| GET    | `/events`       | Optional team, player, from and to minute filters.                   |
| GET    | `/analysis`     | Same filters; summaries, shots, network, player counts and timeline. |
| POST   | `/import`       | csv and label; replaces the current match after all rows validate.   |
| GET    | `/export.csv`   | Same selection filters; CSV export.                                  |

## Executable Python example

Works on Windows, macOS and Linux with Python 3.12+. Start the app first, then save/run this snippet:

```python
import json
import urllib.request

payload = {'label': 'My labeled match', 'csv': 'event_id,minute,team,player,action,outcome,x,y,end_x,end_y,receiver\n1,5,Harbor,A. Bello,pass,complete,40,50,65,55,I. Okafor'}
request = urllib.request.Request(
    "http://127.0.0.1:8105/api/import",
    data=json.dumps(payload).encode("utf-8"),
    headers={"Content-Type": "application/json"},
    method="POST",
)
with urllib.request.urlopen(request) as response:
    print(json.load(response))
```

This writes demonstration data to your local database. Repeat-key behavior is documented in the README where applicable.

## Event CSV schema

All columns are required; receiver values may be empty. A match contains at most two teams and 5,000 rows. event_id must be unique. Team and player strings are exact-match filter values.

| Column             | Meaning                                                                                |
| ------------------ | -------------------------------------------------------------------------------------- |
| event_id           | Unique string, up to 80 characters                                                     |
| minute             | Finite number from 0 to 130                                                            |
| team, player       | Non-empty labels, up to 100 characters                                                 |
| action             | pass, carry, shot or turnover                                                          |
| outcome            | pass/carry: complete or incomplete; shot: goal, saved, wide or blocked; turnover: lost |
| x, y, end_x, end_y | Finite numeric coordinates from 0 to 100                                               |
| receiver           | Receiver name for pass network edges; may be empty                                     |

Coordinates must be normalized so both teams attack in increasing x. The dashboard assumes a 105×68 m pitch only for its illustrative shot-location score. With dx=(100-x)×1.05 and dy=(50-y)×0.68, distance=hypot(dx,dy), angle=atan2(7.32×dx, dx²+dy²−3.66²), and score=1/(1+exp(2.2+0.095×distance−1.2×angle)). These are hand-selected coefficients with no accuracy or calibration claim. The map uses the score only to size circles.
