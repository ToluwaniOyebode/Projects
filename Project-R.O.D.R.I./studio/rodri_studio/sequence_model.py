"""Three-second causal actor/ball context, with explicit missing-evidence masks."""
from functools import lru_cache
from pathlib import Path
import json
import cv2
import numpy as np
from .tracking import Tracker,jersey_descriptor,iou
from .temporal_model import canonical,ball_detector,BALL_LOCK,probabilities
from .visual_model import frame_at
from .vision import Detector,boundary,signature
from .motion import motion_features
from .edited_video import timeline_for

ROOT=Path(__file__).resolve().parents[1]
FEATURE_VERSION='actor_ball_sequence_3s_v4'
LAGS=[0.,.5,1.,1.5,2.,2.5,3.]
ARTIFACT=ROOT/'models/next_action_v4.json'


@lru_cache(maxsize=1)
def person_detector():return Detector()


@lru_cache(maxsize=16)
def video_fps(path):
    cap=cv2.VideoCapture(str(path))
    try:return cap.get(cv2.CAP_PROP_FPS)
    finally:cap.release()


@lru_cache(maxsize=384)
def sample(path,index,fps):
    image,actual=frame_at(path,index/fps);image,_=canonical(image,[0,0,1,1])
    people=person_detector().detect(image)
    with BALL_LOCK:result=ball_detector().predict(image,conf=.12,imgsz=960,device='cpu',verbose=False)[0]
    balls=[]
    for q in result.boxes.data.cpu().numpy():
        cx,cy=(q[0]+q[2])/2,(q[1]+q[3])/2
        if cy>image.shape[0]*.15 and (q[2]-q[0])*(q[3]-q[1])<400:
            balls.append(dict(box=q[:4].tolist(),center=[float(cx),float(cy)],confidence=float(q[4])))
    return image,actual,people,balls


class BallAssociation:
    """Association of learned detections only: no boot/white-blob fallback."""
    def __init__(self):self.last=None;self.time=None;self.velocity=np.zeros(2)

    def update(self,candidates,time):
        if not candidates:return None
        if self.last is None or time-self.time>1.:
            best=max(candidates,key=lambda q:q['confidence']);confirmed=best['confidence']>=.65
        else:
            dt=time-self.time;expected=np.asarray(self.last['center'])+self.velocity*dt
            best=max(candidates,key=lambda q:q['confidence']-.7*min(np.linalg.norm(np.asarray(q['center'])-expected)/640,1))
            distance=np.linalg.norm(np.asarray(best['center'])-expected)/640
            if distance>.35 and best['confidence']<.65:return None
            confirmed=best['confidence']>=.65 or distance<.18
            self.velocity=.5*self.velocity+.5*(np.asarray(best['center'])-self.last['center'])/max(dt,1e-6)
        result=dict(best,confirmed=bool(confirmed));self.last=result;self.time=time
        return result


def extract(path,timestamp,box):
    fps=video_fps(str(path))
    if fps<=0 or not np.isfinite(timestamp) or timestamp<0:raise ValueError('Invalid video/timestamp')
    current_index=int(np.floor(timestamp*fps+1e-6));first=sample(str(path),current_index,fps);image,actual,people,balls=first
    scale=640/frame_width(str(path));b=np.asarray(box,float)*scale
    if not (0<=b[0]<b[2]<=image.shape[1] and 0<=b[1]<b[3]<=image.shape[0]):raise ValueError('Invalid actor box')
    start_people=[q for q in people if iou(np.asarray(q['box']),b)<.4]+[dict(box=b.tolist(),confidence=1.)]
    tracker=Tracker();initial=tracker.update(start_people,image,0);tid=initial[-1]['track'];matrix=np.eye(3)
    timeline=timeline_for(path)
    segment=timeline.segment(actual) if timeline else None
    history=[dict(image=image,time=actual,people=people,box=b,balls=balls,to_current=np.eye(3),lag=0.)]
    previous=image;uncertain=False;cut=False
    for k,lag in enumerate(LAGS[1:],1):
        if actual<lag:break
        index=int(np.floor((actual-lag)*fps+1e-6))
        if segment and index/fps < segment['clip_start_seconds']-1e-8:
            cut=True;break
        past,t,ds,bs=sample(str(path),index,fps)
        if boundary(signature(previous),signature(past)):cut=True;break
        tracked=tracker.update(ds,past,lag);actor=next((d for d in tracked if d['track']==tid),None)
        if actor is None or actor.get('identity_uncertain'):uncertain=True;break
        transform=np.eye(3);transform[:2]=tracker.last_camera;matrix=transform@matrix
        history.append(dict(image=past,time=t,people=ds,box=np.asarray(actor['box']),balls=bs,to_current=np.linalg.inv(matrix),lag=lag));previous=past
    association=BallAssociation()
    for h in reversed(history):h['ball']=association.update(h['balls'],h['time'])
    feet=np.array([(b[0]+b[2])/2,b[3]]);bh=max(8,b[3]-b[1]);states=[]
    for k in range(len(LAGS)):
        if k>=len(history):states.extend([0.]*11);continue
        h=history[k];q=h['box'];foot=np.array([(q[0]+q[2])/2,q[3]]);height=max(8,q[3]-q[1]);ball=h['ball'];own=jersey_descriptor(h['image'],q)
        ally=[];opponent=[];owners=[]
        for person in h['people']:
            p=np.asarray(person['box']);pfoot=np.array([(p[0]+p[2])/2,p[3]])
            if iou(p,q)>.4:continue
            color=float(np.abs(jersey_descriptor(h['image'],p)-own).sum()/2);distance=np.linalg.norm(pfoot-foot)/height
            (ally if color<.25 else opponent).append(distance)
            if ball:owners.append((np.linalg.norm(pfoot-ball['center'])/height,float(color<.25)))
        gap=np.asarray(ball['center'])-foot if ball else np.zeros(2);dx,dy=gap/height
        owner=min(owners,key=lambda v:v[0]) if owners else (20.,0.)
        states.extend([1.,float(ball is not None),ball['confidence'] if ball else 0.,float(ball.get('confirmed',False)) if ball else 0.,dx,dy,float(np.hypot(dx,dy)),min(ally,default=20.),min(opponent,default=20.),owner[0],owner[1]])
    movement=[];ball_movement=[];current_ball=history[0]['ball']
    for k,lag in enumerate(LAGS[1:],1):
        if k>=len(history):movement.extend([0.,0.]);ball_movement.extend([0.,0.]);continue
        h=history[k];q=h['box'];old=np.array([(q[0]+q[2])/2,q[3],1.]);projected=(h['to_current']@old)[:2]
        movement.extend(((feet-projected)/bh/lag).tolist())
        if current_ball and h['ball']:
            oldball=(h['to_current']@np.r_[h['ball']['center'],1.])[:2];ball_movement.extend(((np.asarray(current_ball['center'])-oldball)/bh/lag).tolist())
        else:ball_movement.extend([0.,0.])
    previous,_=frame_at(path,max(segment['clip_start_seconds'] if segment else 0,actual-.24));previous,_=canonical(previous,box)
    if boundary(signature(previous),signature(image)):previous=image
    legacy=motion_features(previous,image,b)
    geometry=[(b[2]-b[0])/bh,bh/image.shape[0],feet[0]/640,feet[1]/image.shape[0]]
    vector=np.nan_to_num(np.clip(np.r_[states,movement,ball_movement,geometry,legacy],-20,20)).astype(float)
    ball_info=None
    if current_ball:ball_info=dict(box_normalized=(np.asarray(current_ball['box'])/[640,image.shape[0],640,image.shape[0]]).tolist(),confidence=current_ball['confidence'],confirmed=current_ball['confirmed'])
    evidence=dict(history_seconds=history[-1]['lag'],history_samples=len(history),history_uncertain=uncertain,history_cut=cut,ball=ball_info,ball_method='learned football detector with temporal association; no white-blob fallback',edit_sequence=segment['continuous_sequence_id'] if segment else None,original_source_seconds=timeline.source_time(actual) if timeline else actual)
    return vector,evidence


@lru_cache(maxsize=16)
def frame_width(path):
    cap=cv2.VideoCapture(str(path))
    try:return cap.get(cv2.CAP_PROP_FRAME_WIDTH)
    finally:cap.release()


@lru_cache(maxsize=4)
def load(path,mtime):return json.loads(Path(path).read_text())


@lru_cache(maxsize=96)
def predict_observation(path,timestamp,box,model_mtime,artifact=str(ARTIFACT)):
    model=load(artifact,model_mtime)
    if model['feature_version']!=FEATURE_VERSION:raise ValueError('V4 checkpoint feature mismatch')
    vector,evidence=extract(path,timestamp,box);p=probabilities(vector,model['classifier']);order=np.argsort(p)[::-1];conditional=[]
    if model.get('conditional_head'):
        h=model['conditional_head'];cp=probabilities(vector,h);conditional=[dict(action=h['classes'][i],probability=float(cp[i])) for i in np.argsort(cp)[::-1]]
    return dict(status='experimental',feature_kind=FEATURE_VERSION,alternatives=[dict(action=model['classes'][i],probability=float(p[i])) for i in order],conditional_options=conditional,conditional_context='If an on-ball event occurs. Receiving still depends on delivery; these separate uncalibrated models do not infer passer intention.',message='Three-second actor/ball context. Missing ball/history evidence is explicitly masked; scores are uncalibrated.',evidence=evidence,off_ball_motion=None,calibrated=False,abstain=bool(p.max()<.45),training_matches=model['training_matches'],deployment_refit=model.get('deployment_refit',False))
