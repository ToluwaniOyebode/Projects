"""Application pipeline with optimistic concurrency and an append-only activity log."""
import csv
import io
import re
from datetime import date, timedelta
from urllib.parse import urlsplit

from webcore import Problem, Raw, connect, csv_cell, integer, iso_date, text

STAGES = ('saved', 'applied', 'interview', 'offer', 'closed')
FIELDS = ('company', 'role', 'stage', 'applied_on', 'followup_on', 'url', 'notes')


class App:
    name = 'Applyboard'

    def __init__(self, path, demo=True):
        self.path = path
        with connect(path) as db:
            db.execute('PRAGMA journal_mode=WAL')
            db.executescript('''
                CREATE TABLE IF NOT EXISTS applications(
                  id INTEGER PRIMARY KEY, company TEXT NOT NULL, role TEXT NOT NULL,
                  stage TEXT NOT NULL CHECK(stage IN ('saved','applied','interview','offer','closed')),
                  applied_on TEXT NOT NULL, followup_on TEXT NOT NULL, url TEXT NOT NULL,
                  notes TEXT NOT NULL, version INTEGER NOT NULL DEFAULT 1);
                CREATE TABLE IF NOT EXISTS activity(
                  id INTEGER PRIMARY KEY, application_id INTEGER, company TEXT NOT NULL,
                  message TEXT NOT NULL, created_at TEXT DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')));
                CREATE TABLE IF NOT EXISTS metadata(key TEXT PRIMARY KEY, value TEXT);
            ''')
            seeded = db.execute("SELECT 1 FROM metadata WHERE key='demo_seeded'").fetchone()
            if demo and not seeded:
                today = date.today()
                examples = [
                    ('Northstar Labs', 'Backend Engineer', 'interview', -14, 2, 'Prepare a walkthrough of an API transaction and its tests.'),
                    ('Acacia Systems', 'Software Engineer', 'applied', -6, -1, 'Follow up with a short note and the inventory project.'),
                    ('Orbit Studio', 'Full Stack Developer', 'saved', 0, 4, 'Tailor the application to the product team.'),
                    ('Harbor Data', 'Junior Data Engineer', 'applied', -3, 3, 'Share the CSV validation and analytics work.'),
                    ('Fieldwork', 'Python Developer', 'interview', -10, 1, 'Review SQLite transactions and HTTP error handling.'),
                    ('Copperworks', 'Platform Intern', 'offer', -20, 5, 'Compare responsibilities and mentoring opportunities.'),
                    ('Juniper Apps', 'Frontend Developer', 'closed', -25, 0, 'Keep a record of lessons from the process.'),
                ]
                for company, role, stage, ago, followup, notes in examples:
                    db.execute('INSERT INTO applications(company,role,stage,applied_on,followup_on,url,notes) VALUES(?,?,?,?,?,?,?)',
                               (company, role, stage, (today+timedelta(days=ago)).isoformat(), (today+timedelta(days=followup)).isoformat(), '', notes))
                db.execute("INSERT INTO metadata VALUES('demo_seeded','1')")

    def validate(self, data):
        result = {k: text(data.get(k, ''), k, 4000 if k == 'notes' else 500,
                          k in ('applied_on', 'followup_on', 'url', 'notes')) for k in FIELDS}
        if result['stage'] not in STAGES:
            raise Problem('Unknown application stage')
        for key in ('applied_on', 'followup_on'):
            result[key] = iso_date(result[key], key, True)
        if result['url']:
            parts = urlsplit(result['url'])
            if parts.scheme not in ('https', 'http') or not parts.netloc or parts.username:
                raise Problem('Job URL must be an http(s) URL without credentials')
        return result

    def applications(self, query):
        stage = query.get('stage', '')
        if stage and stage not in STAGES:
            raise Problem('Unknown stage filter')
        needle = text(query.get('q', ''), 'q', 200, True).lower()
        with connect(self.path) as db:
            rows = db.execute('''SELECT * FROM applications WHERE (?='' OR stage=?)
                AND instr(lower(company || ' ' || role || ' ' || notes),?)>0 ORDER BY id DESC''', (stage, stage, needle))
            return [dict(row) for row in rows]

    def create(self, data):
        values = self.validate(data)
        with connect(self.path) as db:
            cursor = db.execute('INSERT INTO applications(company,role,stage,applied_on,followup_on,url,notes) VALUES(?,?,?,?,?,?,?)', tuple(values[k] for k in FIELDS))
            item_id = cursor.lastrowid
            db.execute('INSERT INTO activity(application_id,company,message) VALUES(?,?,?)', (item_id, values['company'], f"Added to {values['stage']}"))
            return dict(db.execute('SELECT * FROM applications WHERE id=?', (item_id,)).fetchone())

    def update(self, item_id, data):
        version = integer(data.get('version'), 'version', 1)
        with connect(self.path) as db:
            db.execute('BEGIN IMMEDIATE')
            old = db.execute('SELECT * FROM applications WHERE id=?', (item_id,)).fetchone()
            if old is None:
                raise Problem('Application not found', 404)
            values = self.validate({**dict(old), **data})
            changed = db.execute('UPDATE applications SET company=?,role=?,stage=?,applied_on=?,followup_on=?,url=?,notes=?,version=version+1 WHERE id=? AND version=?',
                                 (*[values[k] for k in FIELDS], item_id, version))
            if changed.rowcount == 0:
                raise Problem('This application changed. Refresh before editing again.', 409)
            message = f"{old['stage']} → {values['stage']}" if old['stage'] != values['stage'] else 'Updated details'
            db.execute('INSERT INTO activity(application_id,company,message) VALUES(?,?,?)', (item_id, values['company'], message))
            return dict(db.execute('SELECT * FROM applications WHERE id=?', (item_id,)).fetchone())

    def stats(self):
        items = self.applications({})
        counts = {stage: sum(row['stage'] == stage for row in items) for stage in STAGES}
        due = sorted((r for r in items if r['followup_on'] and r['followup_on'] <= date.today().isoformat() and r['stage'] not in ('closed', 'offer')), key=lambda r: r['followup_on'])
        submitted = sum(counts[k] for k in ('applied', 'interview', 'offer', 'closed'))
        return {'total': len(items), 'counts': counts, 'active': sum(counts[k] for k in ('saved', 'applied', 'interview')),
                'interview_or_offer_rate': round(100*(counts['interview']+counts['offer']) / submitted, 1) if submitted else 0,
                'followups_due': due}

    def handle(self, method, path, query, body):
        if path == '/api/applications' and method == 'GET':
            return self.applications(query)
        if path == '/api/applications' and method == 'POST':
            return self.create(body)
        if path == '/api/stats' and method == 'GET':
            return self.stats()
        if path == '/api/activity' and method == 'GET':
            with connect(self.path) as db:
                return [dict(r) for r in db.execute('SELECT * FROM activity ORDER BY id DESC LIMIT 20')]
        if path == '/api/export.csv' and method == 'GET':
            output = io.StringIO()
            writer = csv.writer(output)
            writer.writerow(FIELDS)
            for row in self.applications(query):
                writer.writerow([csv_cell(row[k]) for k in FIELDS])
            return Raw(output.getvalue(), 'text/csv; charset=utf-8', 'applications.csv')
        match = re.fullmatch(r'/api/applications/(\d+)', path)
        if match and method == 'PATCH':
            return self.update(int(match[1]), body)
        if match and method == 'DELETE':
            with connect(self.path) as db:
                old = db.execute('SELECT * FROM applications WHERE id=?', (int(match[1]),)).fetchone()
                if old is None:
                    raise Problem('Application not found', 404)
                db.execute('DELETE FROM applications WHERE id=?', (old['id'],))
                db.execute('INSERT INTO activity(application_id,company,message) VALUES(?,?,?)', (old['id'], old['company'], 'Deleted application'))
            return {'deleted': True}
        raise Problem('Not found', 404)
