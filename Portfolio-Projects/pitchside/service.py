import csv
import io
import json
from pathlib import Path
from analytics import FIELDS,analyze,number,parse_csv
from webcore import Problem,Raw,connect,csv_cell,text


class App:
    name='Pitchside'
    def __init__(self,path,demo=True):
        self.path=path
        with connect(path) as db:
            db.execute('PRAGMA journal_mode=WAL')
            db.executescript('CREATE TABLE IF NOT EXISTS events(event_id TEXT PRIMARY KEY,minute REAL NOT NULL,team TEXT NOT NULL,player TEXT NOT NULL,body TEXT NOT NULL);CREATE TABLE IF NOT EXISTS metadata(key TEXT PRIMARY KEY,value TEXT);')
            if demo and not db.execute("SELECT 1 FROM metadata WHERE key='initialized'").fetchone():
                source=(Path(__file__).parent/'static'/'demo_match.csv').read_text()
                for event in parse_csv(source):
                    db.execute('INSERT INTO events VALUES(?,?,?,?,?)',(event['event_id'],event['minute'],event['team'],event['player'],json.dumps(event)))
                db.execute("INSERT INTO metadata VALUES('initialized','1')")
                db.execute("INSERT INTO metadata VALUES('label','Synthetic demonstration match')")

    def events(self,query):
        minimum=number(query.get('from',0),'from',0,130);maximum=number(query.get('to',130),'to',0,130)
        if minimum>maximum:raise Problem('from must be no greater than to')
        team=text(query.get('team',''),'team',100,True);player=text(query.get('player',''),'player',100,True)
        with connect(self.path) as db:
            rows=db.execute("SELECT body FROM events WHERE minute>=? AND minute<=? AND (?='' OR team=?) AND (?='' OR player=?) ORDER BY minute,event_id",(minimum,maximum,team,team,player,player))
            return [json.loads(row['body']) for row in rows]

    def handle(self,method,path,query,body):
        if path=='/api/analysis' and method=='GET':return analyze(self.events(query))
        if path=='/api/events' and method=='GET':return self.events(query)
        if path=='/api/match' and method=='GET':
            with connect(self.path) as db:
                label=db.execute("SELECT value FROM metadata WHERE key='label'").fetchone()
            events=self.events({})
            return {'label':label['value'] if label else 'No match imported','teams':sorted({e['team'] for e in events}),'players':[{'team':team,'player':player} for team,player in sorted({(e['team'],e['player']) for e in events})],'count':len(events)}
        if path=='/api/import' and method=='POST':
            events=parse_csv(body.get('csv'))
            label=text(body.get('label','Imported match'),'label',120)
            with connect(self.path) as db:
                db.execute('DELETE FROM events')
                for event in events:db.execute('INSERT INTO events VALUES(?,?,?,?,?)',(event['event_id'],event['minute'],event['team'],event['player'],json.dumps(event)))
                db.execute("INSERT OR REPLACE INTO metadata VALUES('label',?)",(label,))
                db.execute("INSERT OR REPLACE INTO metadata VALUES('initialized','1')")
            return {'imported':len(events),'label':label}
        if path=='/api/export.csv' and method=='GET':
            output=io.StringIO();writer=csv.writer(output);writer.writerow(FIELDS)
            for event in self.events(query):writer.writerow([csv_cell(event[k]) if isinstance(event[k],str) else event[k] for k in FIELDS])
            return Raw(output.getvalue(),'text/csv; charset=utf-8','match-events.csv')
        raise Problem('Not found',404)
