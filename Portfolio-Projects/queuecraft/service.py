"""Persistent at-least-once queue with expiring leases and fencing tokens."""
import json
import re
import time
import uuid

from webcore import Problem, connect, integer, text


def validate_payload(kind,payload):
    if not isinstance(payload,dict):raise Problem('payload must be an object')
    if kind=='sum':
        numbers=payload.get('numbers')
        if not isinstance(numbers,list) or not 1<=len(numbers)<=1000:raise Problem('numbers must be a list with 1–1,000 integers')
        for value in numbers:integer(value,'numbers[]',-1000000000,1000000000)
    elif kind=='word_count':text(payload.get('text'),'text',10000)
    elif kind=='flaky':
        integer(payload.get('fail_until',1),'fail_until',0,5)
        text(payload.get('message','Finished after retry'),'message',500)
    else:raise Problem('kind must be sum, word_count or flaky')
    if len(json.dumps(payload))>20000:raise Problem('Payload exceeds 20 KB')


def perform(job):
    payload=job['payload']
    if job['kind']=='sum':return {'sum':sum(payload['numbers']),'items':len(payload['numbers'])}
    if job['kind']=='word_count':
        words=re.findall(r'[^\W_]+',payload['text'].casefold())
        return {'words':len(words),'unique_words':len(set(words)),'characters':len(payload['text'])}
    if job['attempts']<=payload.get('fail_until',1):raise RuntimeError('Demonstration transient failure')
    return {'message':payload.get('message','Finished after retry')}


class App:
    name='QueueCraft'
    def __init__(self,path,demo=True,clock=None,auto_worker=False):
        self.path=path;self.clock=clock or time.time;self.worker=None
        with connect(path) as db:
            db.execute('PRAGMA journal_mode=WAL')
            db.executescript('''CREATE TABLE IF NOT EXISTS jobs(
              id INTEGER PRIMARY KEY,kind TEXT NOT NULL,payload TEXT NOT NULL,
              status TEXT NOT NULL CHECK(status IN ('queued','running','succeeded','dead')),
              attempts INTEGER NOT NULL DEFAULT 0,max_attempts INTEGER NOT NULL,
              priority INTEGER NOT NULL,available_at REAL NOT NULL,lease_until REAL,
              token TEXT,result TEXT,error TEXT,request_key TEXT NOT NULL UNIQUE,signature TEXT NOT NULL,
              created_at REAL NOT NULL,updated_at REAL NOT NULL);
              CREATE INDEX IF NOT EXISTS job_claim ON jobs(status,available_at,priority);
              CREATE TABLE IF NOT EXISTS history(id INTEGER PRIMARY KEY,job_id INTEGER NOT NULL REFERENCES jobs(id),event TEXT NOT NULL,detail TEXT NOT NULL,at REAL NOT NULL);
              CREATE TABLE IF NOT EXISTS metadata(key TEXT PRIMARY KEY);''')
        if demo:
            with connect(path) as db:seeded=db.execute("SELECT 1 FROM metadata WHERE key='seeded'").fetchone()
            if not seeded:
                self.enqueue({'kind':'sum','payload':{'numbers':[12,18,24,30]},'request_key':'demo-sum'})
                self.enqueue({'kind':'word_count','payload':{'text':'Reliable background work deserves visible progress.'},'request_key':'demo-words'})
                self.enqueue({'kind':'flaky','payload':{'fail_until':2},'request_key':'demo-retry'})
                with connect(path) as db:db.execute("INSERT OR IGNORE INTO metadata VALUES('seeded')")
        if auto_worker:
            from worker import Worker
            self.worker=Worker(self);self.worker.start()

    def close(self):
        if self.worker:self.worker.stop()

    def _job(self,row):
        result=dict(row);result['payload']=json.loads(result['payload']);result['result']=json.loads(result['result']) if result['result'] else None
        result.pop('token',None);result.pop('signature',None)
        return result

    def _event(self,db,job_id,event,detail=''):
        db.execute('INSERT INTO history(job_id,event,detail,at) VALUES(?,?,?,?)',(job_id,event,detail,self.clock()))

    def enqueue(self,data):
        kind=data.get('kind');payload=data.get('payload');validate_payload(kind,payload)
        max_attempts=integer(data.get('max_attempts',3),'max_attempts',1,8)
        priority=integer(data.get('priority',5),'priority',0,9)
        key=text(data.get('request_key',str(uuid.uuid4())),'request_key',100)
        raw=json.dumps(payload,sort_keys=True,allow_nan=False)
        signature=json.dumps([kind,payload,max_attempts,priority],sort_keys=True)
        now=self.clock()
        with connect(self.path) as db:
            db.execute('BEGIN IMMEDIATE')
            old=db.execute('SELECT * FROM jobs WHERE request_key=?',(key,)).fetchone()
            if old:
                if old['signature']!=signature:raise Problem('Request key already used for a different job',409)
                return self._job(old)
            cursor=db.execute("INSERT INTO jobs(kind,payload,status,max_attempts,priority,available_at,request_key,signature,created_at,updated_at) VALUES(?,?,'queued',?,?,?,?,?,?,?)",(kind,raw,max_attempts,priority,now,key,signature,now,now))
            self._event(db,cursor.lastrowid,'enqueued',f'Priority {priority}; max {max_attempts} attempts')
            return self._job(db.execute('SELECT * FROM jobs WHERE id=?',(cursor.lastrowid,)).fetchone())

    def claim(self,lease_seconds=15):
        now=self.clock()
        with connect(self.path) as db:
            db.execute('BEGIN IMMEDIATE')
            expired=db.execute("SELECT * FROM jobs WHERE status='running' AND lease_until<=?",(now,)).fetchall()
            for row in expired:
                status='dead' if row['attempts']>=row['max_attempts'] else 'queued'
                db.execute('UPDATE jobs SET status=?,available_at=?,lease_until=NULL,token=NULL,error=?,updated_at=? WHERE id=?',(status,now,'Worker lease expired',now,row['id']))
                self._event(db,row['id'],'lease_expired',status)
            row=db.execute("SELECT * FROM jobs WHERE status='queued' AND available_at<=? ORDER BY priority DESC,created_at,id LIMIT 1",(now,)).fetchone()
            if not row:return None
            token=str(uuid.uuid4())
            db.execute("UPDATE jobs SET status='running',attempts=attempts+1,lease_until=?,token=?,updated_at=? WHERE id=?",(now+lease_seconds,token,now,row['id']))
            self._event(db,row['id'],'claimed',f"Attempt {row['attempts']+1}")
            result=self._job(db.execute('SELECT * FROM jobs WHERE id=?',(row['id'],)).fetchone());result['token']=token
            return result

    def finish(self,job_id,token,result=None,error=None):
        now=self.clock()
        with connect(self.path) as db:
            db.execute('BEGIN IMMEDIATE')
            row=db.execute("SELECT * FROM jobs WHERE id=? AND token=? AND status='running' AND lease_until>?",(job_id,token,now)).fetchone()
            if not row:raise Problem('Lease expired or owned by another worker',409)
            if error is None:
                status='succeeded';available=now;raw=json.dumps(result,allow_nan=False)
                self._event(db,job_id,'succeeded')
            else:
                status='dead' if row['attempts']>=row['max_attempts'] else 'queued'
                available=now+min(60,2**(row['attempts']-1));raw=None
                self._event(db,job_id,'dead' if status=='dead' else 'retry_scheduled',str(error)[:500])
            db.execute('UPDATE jobs SET status=?,available_at=?,result=?,error=?,lease_until=NULL,token=NULL,updated_at=? WHERE id=?',(status,available,raw,None if error is None else str(error)[:500],now,job_id))
            return self._job(db.execute('SELECT * FROM jobs WHERE id=?',(job_id,)).fetchone())

    def retry(self,job_id):
        now=self.clock()
        with connect(self.path) as db:
            db.execute('BEGIN IMMEDIATE')
            row=db.execute('SELECT * FROM jobs WHERE id=?',(job_id,)).fetchone()
            if not row:raise Problem('Job not found',404)
            if row['status']!='dead':raise Problem('Only dead-letter jobs can be retried',409)
            db.execute("UPDATE jobs SET status='queued',attempts=0,available_at=?,error=NULL,result=NULL,updated_at=? WHERE id=?",(now,now,job_id))
            self._event(db,job_id,'manually_retried','Attempt counter reset; history retained')
            return self._job(db.execute('SELECT * FROM jobs WHERE id=?',(job_id,)).fetchone())

    def handle(self,method,path,query,body):
        if path=='/api/jobs' and method=='POST':return self.enqueue(body)
        if path=='/api/jobs' and method=='GET':
            status=query.get('status','')
            if status and status not in ('queued','running','succeeded','dead'):raise Problem('Unknown status')
            with connect(self.path) as db:return [self._job(r) for r in db.execute("SELECT * FROM jobs WHERE (?='' OR status=?) ORDER BY id DESC LIMIT 100",(status,status))]
        if path=='/api/stats' and method=='GET':
            with connect(self.path) as db:
                counts={r['status']:r['n'] for r in db.execute('SELECT status,count(*) n FROM jobs GROUP BY status')}
                attempts=db.execute('SELECT coalesce(sum(attempts),0) FROM jobs').fetchone()[0]
            return {'counts':{s:counts.get(s,0) for s in ('queued','running','succeeded','dead')},'attempts':attempts,'worker':'embedded' if self.worker else 'external or stopped'}
        match=re.fullmatch(r'/api/jobs/(\d+)(/retry)?',path)
        if match:
            job_id=int(match[1])
            if match[2] and method=='POST':return self.retry(job_id)
            if method=='GET' and not match[2]:
                with connect(self.path) as db:
                    row=db.execute('SELECT * FROM jobs WHERE id=?',(job_id,)).fetchone()
                    if not row:raise Problem('Job not found',404)
                    return {'job':self._job(row),'history':[dict(r) for r in db.execute('SELECT * FROM history WHERE job_id=? ORDER BY id',(job_id,))]}
        raise Problem('Not found',404)
