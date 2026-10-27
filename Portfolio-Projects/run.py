"""Launch any project from this directory using Python 3.12+."""
import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

PROJECTS=['applyboard','ledgerlens','stockroom','signaldesk','pitchside','queuecraft']
ROOT=Path(__file__).resolve().parent

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('project',choices=PROJECTS)
    parser.add_argument('--port',type=int)
    args=parser.parse_args()
    env=os.environ.copy()
    if args.port:env['PORT']=str(args.port)
    if args.project=='stockroom':
        if not shutil.which('node'):parser.error('Install Node.js 24.x to run Stockroom.')
        command=['node','server.js']
    else:command=[sys.executable,'server.py']
    try:raise SystemExit(subprocess.call(command,cwd=ROOT/args.project,env=env))
    except KeyboardInterrupt:pass
