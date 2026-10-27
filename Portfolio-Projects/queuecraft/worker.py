"""Built-in safe task runner. A separate worker can share the server's SQLite file."""
import argparse
import threading
import time
from service import App,perform
from webcore import Problem


class Worker(threading.Thread):
    def __init__(self,app):
        super().__init__(daemon=True);self.app=app;self.stopped=threading.Event()
    def stop(self):self.stopped.set();self.join(timeout=3)
    def run(self):
        while not self.stopped.is_set():
            try:
                job=self.app.claim()
                if job:
                    try:result=perform(job)
                    except Exception as error:self.app.finish(job['id'],job['token'],error=str(error))
                    else:self.app.finish(job['id'],job['token'],result=result)
            except Problem as error:print(f'Worker discarded stale result: {error}',flush=True)
            except Exception as error:print(f'Worker error: {error}',flush=True)
            self.stopped.wait(.5)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--db',default='data.sqlite3');args=parser.parse_args()
    worker=Worker(App(args.db,demo=False));worker.start()
    print('QueueCraft worker started. Press Ctrl+C to stop.',flush=True)
    try:
        while worker.is_alive():time.sleep(.5)
    except KeyboardInterrupt:worker.stop()
