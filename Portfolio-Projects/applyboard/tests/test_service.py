import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from pathlib import Path
from service import App
from webcore import Problem


class PipelineTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.app = App(str(Path(self.tmp.name)/'test.db'), demo=False)
        self.payload = dict(company='Acme', role='Developer', stage='applied', applied_on='2026-10-20', followup_on='2000-01-01')

    def tearDown(self):
        self.tmp.cleanup()

    def test_create_update_search_and_activity(self):
        row = self.app.create(self.payload)
        updated = self.app.update(row['id'], {'stage': 'interview', 'version': 1})
        self.assertEqual(updated['version'], 2)
        self.assertEqual(self.app.applications({'q': 'ACME'})[0]['stage'], 'interview')
        self.assertEqual(len(self.app.handle('GET','/api/activity',{},{})), 2)

    def test_only_one_concurrent_editor_wins(self):
        row = self.app.create(self.payload)
        def attempt(stage):
            try:
                self.app.update(row['id'], {'stage': stage, 'version': 1})
                return 200
            except Problem as error:
                return error.status
        with ThreadPoolExecutor(2) as pool:
            self.assertEqual(sorted(pool.map(attempt, ['interview','closed'])), [200,409])

    def test_followups_exclude_offers_and_closed(self):
        for stage in ('applied','offer','closed'):
            self.app.create({**self.payload,'stage':stage})
        self.assertEqual(len(self.app.stats()['followups_due']), 1)
        self.assertEqual(self.app.stats()['interview_or_offer_rate'], 33.3)

    def test_invalid_dates_and_javascript_urls(self):
        for patch in [{'followup_on':'2026-02-30'},{'url':'javascript:alert(1)'},{'stage':'hired'}]:
            with self.assertRaises(Problem):
                self.app.create({**self.payload,**patch})
        self.assertEqual(self.app.applications({}), [])

    def test_csv_neutralizes_formulas(self):
        self.app.create({**self.payload,'company':'=2+3'})
        export = self.app.handle('GET','/api/export.csv',{},{}).body.decode()
        self.assertIn("'=2+3",export)

    def test_deleted_demo_rows_do_not_reappear(self):
        demo = App(str(Path(self.tmp.name)/'demo.db'))
        for row in demo.applications({}):
            demo.handle('DELETE',f"/api/applications/{row['id']}",{},{})
        self.assertEqual(App(demo.path).applications({}), [])

if __name__ == '__main__':
    unittest.main()
