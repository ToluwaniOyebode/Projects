import json
import math
import os
from pathlib import Path
import threading
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

import cv2
from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from .pipeline import inspect, analyze
from .predictor import features, predict, train, ACTIONS

ROOT=Path(__file__).resolve().parent
DATA=Path(os.environ.get('RODRI_DATA','workspace')).resolve(); DATA.mkdir(exist_ok=True,parents=True)
MODEL=DATA/'action_model.json'
app=FastAPI(title='Rodri Studio',version='0.1.0')
app.mount('/static',StaticFiles(directory=ROOT/'static'),name='static')
executor=ThreadPoolExecutor(max_workers=1)
lock=threading.RLock()
jobs={}


def folder(uid):
    if len(uid)!=32 or any(c not in '0123456789abcdef' for c in uid):
        raise HTTPException(404,'Unknown video')
    p=DATA/uid
    if not (p/'video.json').exists():
        raise HTTPException(404,'Unknown video')
    return p


def read_result(uid):
    p=folder(uid)/'analysis.json'
    if not p.exists():
        raise HTTPException(409,'Analyze this clip first')
    return json.loads(p.read_text())


def write_result(uid,result):
    p=folder(uid)/'analysis.json'; temp=p.with_suffix('.tmp')
    temp.write_text(json.dumps(result)); temp.replace(p)


@app.get('/')
def home():
    return FileResponse(ROOT/'static'/'index.html')


@app.post('/api/videos')
async def upload(video: UploadFile=File(...)):
    suffix=Path(video.filename or '').suffix.lower()
    if suffix not in {'.mp4','.mkv','.mov','.avi','.webm','.m4v'}:
        raise HTTPException(400,'Choose a video file')
    uid=uuid4().hex; dest=DATA/uid; dest.mkdir()
    path=dest/('source'+suffix)
    try:
        with path.open('wb') as f:
            while chunk:=await video.read(1024*1024):
                f.write(chunk)
        meta=inspect(path)
    except (ValueError,OSError) as exc:
        path.unlink(missing_ok=True)
        raise HTTPException(400,str(exc))
    info=dict(id=uid,name=video.filename,path=str(path),metadata=meta)
    (dest/'video.json').write_text(json.dumps(info))
    return {k:v for k,v in info.items() if k!='path'}


@app.get('/api/videos/{uid}/source')
def source(uid:str):
    info=json.loads((folder(uid)/'video.json').read_text())
    return FileResponse(info['path'])


class Clip(BaseModel):
    start:float=Field(default=0,ge=0,allow_inf_nan=False)
    duration:float=Field(default=30,gt=0,le=120,allow_inf_nan=False)
    backend:str='yolo'


@app.post('/api/videos/{uid}/analyze')
def start_analysis(uid:str,clip:Clip):
    p=folder(uid)
    if clip.backend not in {'yolo','hog'}:
        raise HTTPException(400,'Unknown detector')
    with lock:
        if jobs.get(uid,{}).get('status') in {'queued','running'}:
            raise HTTPException(409,'Analysis already running')
        if (p/'analysis.json').exists():
            raise HTTPException(409,'Upload the video again for a new pilot; existing labels are preserved')
        info=json.loads((p/'video.json').read_text())
        if clip.start>=info['metadata']['duration']:
            raise HTTPException(400,'Start is outside the video')
        jobs[uid]={'status':'queued','progress':0}
    def work():
        try:
            jobs[uid]={'status':'running','progress':0}
            result=analyze(info['path'],clip.start,clip.duration,clip.backend,lambda v:jobs[uid].update(progress=v))
            with lock:
                write_result(uid,result)
            jobs[uid]={'status':'complete','progress':1}
        except Exception as exc:
            import traceback
            traceback.print_exc()
            jobs[uid]={'status':'failed','progress':0,'error':f'{type(exc).__name__}: {exc}'}
    executor.submit(work)
    return jobs[uid]


@app.get('/api/videos/{uid}/status')
def status(uid:str):
    p=folder(uid)
    return jobs.get(uid,{'status':'complete' if (p/'analysis.json').exists() else 'idle','progress':0})


@app.get('/api/videos/{uid}/analysis')
def result(uid:str):
    with lock:
        return read_result(uid)


class Identity(BaseModel):
    time:float=Field(ge=0,allow_inf_nan=False)
    track:int


@app.post('/api/videos/{uid}/identity')
def identity(uid:str,seed:Identity):
    with lock:
        r=read_result(uid)
        frame=min(r['frames'],key=lambda f:abs(f['time']-seed.time))
        if abs(frame['time']-seed.time)>.3 or not any(d['track']==seed.track for d in frame['detections']):
            raise HTTPException(400,'Select a detected person at an analyzed timestamp')
        # Confirmation lasts at most five seconds; no transfer to other shots.
        key=str(frame['shot'])
        confirmations=r['identities'].get(key,[])
        if isinstance(confirmations,dict): confirmations=[confirmations]
        confirmations=[v for v in confirmations if v['time']!=frame['time']]
        confirmations.append(dict(track=seed.track,time=frame['time'],expires=frame['time']+5))
        r['identities'][key]=sorted(confirmations,key=lambda v:v['time'])
        write_result(uid,r)
    return r['identities']


class Replay(BaseModel):
    start:float=Field(ge=0,allow_inf_nan=False)
    end:float=Field(gt=0,allow_inf_nan=False)


@app.post('/api/videos/{uid}/replay')
def replay(uid:str,segment:Replay):
    with lock:
        r=read_result(uid)
        if segment.end<=segment.start or segment.end>r['metadata']['duration']:
            raise HTTPException(400,'Invalid replay interval')
        r['replays'].append(segment.model_dump()); write_result(uid,r)
    return r['replays']


def context(r,t):
    past=[f for f in r['frames'] if f['time']<=t+1e-8]
    frame=past[-1] if past else r['frames'][0]
    if not past or t-frame['time']>.3:
        return frame,None,'Outside analyzed clip'
    if frame['replay_suspected'] or any(v['start']<=t<=v['end'] for v in r['replays']):
        return frame,None,'Replay / repeat suspected: forecast suppressed'
    confirmations=r['identities'].get(str(frame['shot']),[])
    if isinstance(confirmations,dict): confirmations=[confirmations]
    applicable=[v for v in confirmations if v['time']<=t]
    seed=applicable[-1] if applicable else None
    if not seed or not seed['time']<=t<=seed['expires']:
        return frame,None,'Confirm Rodri in this shot (identity expires after 5 seconds)'
    det=next((d for d in frame['detections'] if d['track']==seed['track']),None)
    return frame,det,('Identity lost / occluded' if det is None else 'Human-confirmed track; ID switches remain possible')


@app.get('/api/videos/{uid}/forecast')
def forecast(uid:str,time:float):
    if not math.isfinite(time):
        raise HTTPException(400,'Invalid timestamp')
    r=read_result(uid); frame,det,message=context(r,time)
    prediction=predict(features(det,r['metadata']['width'],r['metadata']['height']),MODEL) if det else {'status':'suppressed','alternatives':[]}
    return dict(time=frame['time'],shot=frame['shot'],person=det,message=message,prediction=prediction)


class Annotation(BaseModel):
    time:float=Field(ge=0,allow_inf_nan=False)
    target_action:str
    match_id:str=Field(min_length=1,max_length=120)
    target_time:float=Field(gt=0,allow_inf_nan=False)


@app.post('/api/videos/{uid}/labels')
def annotate(uid:str,label:Annotation):
    with lock:
        r=read_result(uid); frame,det,message=context(r,label.time)
        if det is None:
            raise HTTPException(400,message)
        if label.target_action not in ACTIONS or label.target_time<=label.time or label.target_time>r['metadata']['duration']:
            raise HTTPException(400,'Choose the actual next action and its later timestamp')
        if any(s['start']<=label.target_time and s['end']>=label.time for s in r['replays']):
            raise HTTPException(400,'The label interval overlaps a replay')
        if label.target_time>r['frames'][-1]['time'] or any(label.time<c<=label.target_time for c in r['cuts']):
            raise HTTPException(400,'Target must be within this analyzed shot; do not bridge a camera cut')
        row=dict(**label.model_dump(),features=features(det,r['metadata']['width'],r['metadata']['height']),verified=True,replay=False,source_video=uid,shot=frame['shot'])
        r['annotations']=[v for v in r['annotations'] if v['time']!=label.time]+[row]
        write_result(uid,r)
    return {'saved':len(r['annotations'])}


@app.post('/api/train')
def train_model():
    with lock:
        rows=[]
        for p in DATA.glob('*/analysis.json'):
            analysis=json.loads(p.read_text())
            for row in analysis.get('annotations',[]):
                if not any(v['start']<=row['target_time'] and v['end']>=row['time'] for v in analysis['replays']):
                    rows.append(row)
        try:
            metrics=train(rows,MODEL)
        except ValueError as exc:
            raise HTTPException(400,str(exc))
    return metrics


@app.get('/api/videos/{uid}/export')
def export(uid:str):
    p=folder(uid)/'analysis.json'
    read_result(uid)
    return FileResponse(p,filename='rodri-analysis.json',media_type='application/json')

@app.post('/api/videos/{uid}/render')
def render(uid:str):
    from .render import render_video
    with lock:
        r=read_result(uid)
        p=folder(uid)
        if jobs.get(uid,{}).get('status')=='rendering':
            raise HTTPException(409,'Render already running')
        source_path=json.loads((p/'video.json').read_text())['path']
        jobs[uid]={'status':'rendering','progress':0}
    def work():
        try:
            stats=render_video(source_path,r,p/'overlay.mp4',MODEL)
            jobs[uid]={'status':'rendered','progress':1,'render':stats}
        except Exception as exc:
            import traceback
            traceback.print_exc()
            jobs[uid]={'status':'failed','error':str(exc),'progress':0}
    executor.submit(work)
    return {'status':'rendering'}


@app.get('/api/videos/{uid}/overlay')
def overlay(uid:str):
    p=folder(uid)/'overlay.mp4'
    if not p.exists() or jobs.get(uid,{}).get('status')=='rendering':
        raise HTTPException(409,'Render the overlay first')
    return FileResponse(p,filename='rodri-overlay.mp4',media_type='video/mp4')
