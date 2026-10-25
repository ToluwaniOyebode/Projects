import json
import hashlib
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
VISUAL_MODELS=ROOT.parent/'models'
app=FastAPI(title='Rodri Studio',version='0.1.0')
app.mount('/static',StaticFiles(directory=ROOT/'static'),name='static')
executor=ThreadPoolExecutor(max_workers=1)
lock=threading.RLock()
jobs={}


def reviewed_events_path():
    for version in ['v4','v3']:
        current=ROOT.parent/'data'/version/'reviewed_events.json'
        if current.exists():return current
    return ROOT.parent/'data'/'reviewed_events.json'


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
    digest=hashlib.sha256()
    try:
        with path.open('wb') as f:
            while chunk:=await video.read(1024*1024):
                f.write(chunk);digest.update(chunk)
        meta=inspect(path)
    except (ValueError,OSError) as exc:
        path.unlink(missing_ok=True)
        raise HTTPException(400,str(exc))
    manifest_path=ROOT.parent/'data'/'video_manifest.json'
    sources=json.loads(manifest_path.read_text()) if manifest_path.exists() else []
    source=next((s for s in sources if s['sha256']==digest.hexdigest()),None)
    event_path=reviewed_events_path()
    anchors=[r for r in json.loads(event_path.read_text()) if source and r['match_id']==source['match_id']] if event_path.exists() else []
    info=dict(id=uid,name=video.filename,path=str(path),metadata=meta,sha256=digest.hexdigest(),known_match=source['match_id'] if source else None,suggested_start=max(0,anchors[0]['observation_seconds']-.2) if anchors else 0)
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
            result['known_match']=info.get('known_match')
            apply_reviewed_anchors(result,info)
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


def apply_reviewed_anchors(result,info):
    """Use recorded actor localizations only for the exact hashed source video."""
    path=reviewed_events_path()
    if not info.get('known_match') or not path.exists(): return
    rows=[r for r in json.loads(path.read_text()) if r['match_id']==info['known_match']]
    for row in rows:
        candidates=[f for f in result['frames'] if f['time']<=row['observation_seconds'] and row['observation_seconds']-f['time']<.21]
        if not candidates:continue
        frame=candidates[-1];box=row['box'];cx=(box[0]+box[2])/2;cy=(box[1]+box[3])/2
        detections=frame['detections']
        if not detections:continue
        det=min(detections,key=lambda d:((d['box'][0]+d['box'][2])/2-cx)**2+((d['box'][1]+d['box'][3])/2-cy)**2)
        distance=((det['box'][0]+det['box'][2])/2-cx)**2+((det['box'][1]+det['box'][3])/2-cy)**2
        if distance>max(12,box[3]-box[1])**2:continue
        key=str(frame['shot'])
        result['identities'].setdefault(key,[]).append(dict(track=det['track'],time=row['observation_seconds'],expires=row['observation_seconds']+2,source='exact-video reviewed actor anchor; not automatic name recognition'))
    for key,seeds in result['identities'].items():result['identities'][key]=sorted(seeds,key=lambda v:v['time'])


def action_prediction(source_path,time,det,metadata,checkpoint='deployment'):
    sequence=VISUAL_MODELS/'next_action_v4.json'
    if checkpoint=='deployment' and sequence.exists():
        from .sequence_model import predict_observation as sequence_predict
        return sequence_predict(str(source_path),float(time),tuple(det['box']),sequence.stat().st_mtime_ns,str(sequence))
    from .temporal_model import predict_observation as temporal_predict
    temporal=VISUAL_MODELS/('next_action_v3_holdout.json' if checkpoint=='holdout' else 'next_action_v3.json')
    if temporal.exists():return temporal_predict(str(source_path),float(time),tuple(det['box']),temporal.stat().st_mtime_ns,str(temporal))
    from .visual_model import predict_observation
    artifact=VISUAL_MODELS/('next_action_holdout.json' if checkpoint=='holdout' else 'next_action.json')
    if artifact.exists():
        return predict_observation(str(source_path),float(time),tuple(det['box']),artifact.stat().st_mtime_ns,str(artifact))
    return predict(features(det,metadata['width'],metadata['height']),MODEL)


@app.get('/api/model')
def model_info():
    sequence=VISUAL_MODELS/'next_action_v4.json'
    if sequence.exists():
        model=json.loads(sequence.read_text());metrics=model['held_out_metrics']
        return dict(status='trained_pilot',version=4,classes=model['classes'],training_matches=model['training_matches'],metrics=metrics,
            warning=f"V4 frozen-episode accuracy: {metrics['accuracy']:.1%} on {metrics['test_examples']} observations; majority baseline: {metrics['majority_accuracy']:.1%}. Selected using separate development folds. Previously used matches, single-AI labels; unseen-match accuracy remains unknown. New videos need Rodri confirmation.")
    current=VISUAL_MODELS/'next_action_v3.json'
    if current.exists():
        model=json.loads(current.read_text());metrics=model['held_out_metrics']
        return dict(status='trained_pilot',version=3,classes=model['classes'],training_matches=model['training_matches'],metrics=metrics,
            warning=f"V3 supports off-ball movement and conditional receiving context. Development accuracy (Inter used for selection): {metrics['accuracy']:.1%}; majority baseline: {metrics['majority_accuracy']:.1%}. Small selected sample, single-AI labels; not independent final accuracy. Deployment uses both real matches; holdout uses Chelsea only.")
    p=VISUAL_MODELS/'next_action.json'
    if not p.exists():return {'status':'untrained'}
    model=json.loads(p.read_text())
    return dict(status='trained_pilot',training_matches=model['training_matches'],metrics=model['held_out_metrics'],warning=f"Development holdout accuracy: {model['held_out_metrics']['accuracy']:.1%}; majority baseline: {model['held_out_metrics']['majority_accuracy']:.1%}. Not a reliable tactical predictor. Deployment refit uses both matches; holdout checkpoint uses Chelsea only.")


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
    if det and det.get('identity_uncertain') and frame['time']>seed['time']+.01:
        return frame,None,'Ambiguous player association: confirm Rodri again'
    confirmed='AI-reviewed source anchor; verify identity (not a name recognizer)' if seed.get('source') else 'Human-confirmed track; ID switches remain possible'
    return frame,det,('Identity lost / occluded' if det is None else confirmed)


@app.get('/api/videos/{uid}/forecast')
def forecast(uid:str,time:float,checkpoint:str='deployment'):
    if not math.isfinite(time):
        raise HTTPException(400,'Invalid timestamp')
    if checkpoint not in {'deployment','holdout'}:raise HTTPException(400,'Unknown checkpoint')
    r=read_result(uid); frame,det,message=context(r,time)
    info=json.loads((folder(uid)/'video.json').read_text())
    prediction=action_prediction(info.get('path',''),frame['time'],det,r['metadata'],checkpoint) if det else {'status':'suppressed','alternatives':[]}
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
def render(uid:str,checkpoint:str='deployment'):
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
            stats=render_video(source_path,r,p/'overlay.mp4',MODEL,checkpoint=checkpoint)
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
