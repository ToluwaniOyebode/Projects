import tempfile
import unittest
from pathlib import Path
from analytics import analyze, parse_csv, shot_score
from service import App
from webcore import Problem

HEADER = "event_id,minute,team,player,action,outcome,x,y,end_x,end_y,receiver\n"
ROWS = "1,2,A,Ada,pass,complete,50,30,70,40,Bola\n2,3,A,Bola,shot,goal,88,50,100,50,\n3,4,B,Chi,pass,incomplete,30,50,40,60,Dele\n"


class FootballTests(unittest.TestCase):
    def test_counts_progression_and_pass_network(self):
        a = analyze(parse_csv(HEADER + ROWS))
        self.assertEqual(
            (
                a["passes"],
                a["pass_completion"],
                a["progressive_passes"],
                a["final_third_entries"],
                a["goals"],
            ),
            (2, 50.0, 1, 1, 1),
        )
        self.assertEqual(
            a["edges"], [{"team": "A", "source": "Ada", "target": "Bola", "count": 1}]
        )

    def test_location_heuristic_prefers_close_central_shots(self):
        self.assertGreater(shot_score(90, 50), shot_score(65, 50))
        self.assertGreater(shot_score(90, 50), shot_score(90, 5))
        for x in range(0, 101, 10):
            for y in range(0, 101, 10):
                self.assertTrue(0 <= shot_score(x, y) <= 1)

    def test_invalid_coordinates_outcomes_and_duplicate_ids(self):
        for source in [
            ROWS.replace("50,30", "NaN,30"),
            ROWS.replace("50,30", "101,30"),
            ROWS.replace("shot,goal", "pass,goal"),
            ROWS + ROWS,
        ]:
            with self.subTest(source=source), self.assertRaises(Problem):
                parse_csv(HEADER + source)

    def test_empty_analysis_has_no_division_by_zero(self):
        a = analyze([])
        self.assertEqual(a["pass_completion"], 0)
        self.assertEqual(a["players"], [])

    def test_bad_import_does_not_replace_match_and_filters_are_correct(self):
        with tempfile.TemporaryDirectory() as tmp:
            app = App(str(Path(tmp) / "match.db"), False)
            app.handle(
                "POST", "/api/import", {}, {"csv": HEADER + ROWS, "label": "Fixture"}
            )
            with self.assertRaises(Problem):
                app.handle(
                    "POST",
                    "/api/import",
                    {},
                    {"csv": HEADER + ROWS.replace("50,30", "200,30")},
                )
            self.assertEqual(len(app.events({})), 3)
            self.assertEqual(
                len(app.events({"team": "A", "from": "2.5", "to": "4"})), 1
            )
            self.assertEqual(app.events({"player": "Ada"})[0]["event_id"], "1")

    def test_same_player_name_on_two_teams_is_not_merged(self):
        a = analyze(parse_csv(HEADER + ROWS.replace("Chi", "Ada")))
        self.assertEqual(len([p for p in a["players"] if p["player"] == "Ada"]), 2)


if __name__ == "__main__":
    unittest.main()
