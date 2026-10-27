import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from service import App,perform
from webcore import Problem


class QueueTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.now=1000.
        self.app=App(str(Path(self.tmp.name)/'jobs.db'),False,clock=lambda:self.now)
    def tearDown(self):self.tmp.cleanup()
    def enqueue(self,**extra):return self.app.enqueue({'kind':'sum','payload':{'numbers':[1,2,3]},**extra})
    def test_enqueue_idempotency_and_payload_conflict(self):
        a=self.enqueue(request_key='k');b=self.enqueue(request_key='k');self.assertEqual(a['id'],b['id'])
        with self.assertRaises(Problem):self.enqueue(request_key='k',payload={'numbers':[4]})
    def test_competing_claims_have_one_owner(self):
        self.enqueue()
        with ThreadPoolExecutor(6) as pool:claims=list(pool.map(lambda _:self.app.claim(),range(6)))
        self.assertEqual(sum(c is not None for c in claims),1)
    def test_expired_lease_is_reclaimed_and_old_owner_is_fenced(self):
        self.enqueue();first=self.app.claim(lease_seconds=5);self.now+=6;second=self.app.claim()
        self.assertEqual(first['id'],second['id']);self.assertNotEqual(first['token'],second['token'])
        with self.assertRaises(Problem):self.app.finish(first['id'],first['token'],result={'bad':True})
        self.app.finish(second['id'],second['token'],result=perform(second))
        self.assertEqual(self.app.handle('GET',f"/api/jobs/{first['id']}",{}, {})['job']['result']['sum'],6)
    def test_late_completion_is_rejected_even_before_reclaim(self):
        self.enqueue();job=self.app.claim(lease_seconds=1);self.now+=2
        with self.assertRaises(Problem):self.app.finish(job['id'],job['token'],result={})
    def test_backoff_exhaustion_and_manual_retry_preserve_history(self):
        row=self.enqueue(max_attempts=2);job=self.app.claim();self.app.finish(job['id'],job['token'],error='Temporary')
        self.assertIsNone(self.app.claim());self.now+=1;job=self.app.claim();result=self.app.finish(job['id'],job['token'],error='Again');self.assertEqual(result['status'],'dead')
        self.assertIsNone(self.app.claim());self.app.retry(row['id']);new=self.app.claim();self.assertEqual(new['attempts'],1)
        self.assertGreater(len(self.app.handle('GET',f"/api/jobs/{row['id']}",{}, {})['history']),5)
    def test_crashes_exhaust_attempts(self):
        self.enqueue(max_attempts=1);self.app.claim(lease_seconds=1);self.now+=2;self.assertIsNone(self.app.claim())
        self.assertEqual(self.app.handle('GET','/api/stats',{}, {})['counts']['dead'],1)
    def test_priority_then_fifo(self):
        low=self.enqueue(priority=1);high=self.enqueue(priority=9);self.assertEqual(self.app.claim()['id'],high['id']);self.assertEqual(self.app.claim()['id'],low['id'])
    def test_task_validation(self):
        for patch in [{'kind':'shell'},{'payload':{'numbers':[True]}},{'payload':{'numbers':[]}},{'max_attempts':0}]:
            with self.assertRaises(Problem):self.enqueue(**patch)
    def test_word_count_and_transient_task(self):
        row=self.app.enqueue({'kind':'word_count','payload':{'text':'hello hello world'}});job=self.app.claim();self.assertEqual(perform(job)['unique_words'],2)
        with self.assertRaises(RuntimeError):perform({'kind':'flaky','payload':{'fail_until':1},'attempts':1})
        self.assertEqual(perform({'kind':'flaky','payload':{'fail_until':1},'attempts':2}),{'message':'Finished after retry'})
    def test_restart_retains_unfinished_jobs(self):
        self.enqueue();fresh=App(self.app.path,False,clock=lambda:self.now);self.assertIsNotNone(fresh.claim())

if __name__=='__main__':unittest.main()
