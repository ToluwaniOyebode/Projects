"""Causal five-class model with an explicit off-ball gate and optional motion head.

JSON checkpoints contain parameters only. Player identity is supplied upstream.
"""
from functools import lru_cache
import json
from pathlib import Path
import threading
import cv2
import numpy as np
from .edited_video import history_start

ROOT=Path(__file__).resolve().parents[1]
ARTIFACT=ROOT/'models/next_action_v3.json'
FEATURE_VERSION='canonical_ball_actor_temporal_v3.2'
BALL_LOCK=threading.Lock()


def canonical(image,box):
    scale=640/image.shape[1]
    return cv2.resize(image,(640,round(image.shape[0]*scale))),np.asarray(box,dtype=float)*scale


@lru_cache(maxsize=1)
def ball_detector():
    from ultralytics import YOLO
    p=ROOT/'models/football-ball.pt'
    if not p.exists():raise ValueError('Use the complete V3 package including football-ball.pt')
    return YOLO(str(p))


def locate_ball(image):
    with BALL_LOCK:
        results=ball_detector().predict(image,conf=.08,imgsz=960,device='cpu',verbose=False)[0]
    choices=[]
    for q in results.boxes.data.cpu().numpy():
        x,y=(q[0]+q[2])/2,(q[1]+q[3])/2
        if y>image.shape[0]*.15 and (q[2]-q[0])*(q[3]-q[1])<400:
            choices.append((float(q[4]),np.array([x,y])))
    return max(choices,key=lambda z:z[0]) if choices else (0.,None)


def camera_affine(previous,current):
    old=cv2.cvtColor(previous,cv2.COLOR_BGR2GRAY);new=cv2.cvtColor(current,cv2.COLOR_BGR2GRAY)
    # Keep stadium texture as well as field lines; score graphics are excluded.
    mask=np.full(old.shape,255,np.uint8);mask[:int(old.shape[0]*.12),:]=0;mask[int(old.shape[0]*.9):,:]=0
    points=cv2.goodFeaturesToTrack(old,600,.005,4,mask=mask)
    identity=np.array([[1.,0.,0.],[0.,1.,0.]])
    if points is None or len(points)<10:return identity
    nxt,status,_=cv2.calcOpticalFlowPyrLK(old,new,points,None,winSize=(31,31),maxLevel=4)
    back,back_status,_=cv2.calcOpticalFlowPyrLK(new,old,nxt,None,winSize=(31,31),maxLevel=4)
    selected=(status.ravel()==1)&(back_status.ravel()==1)&(np.linalg.norm((back-points).reshape(-1,2),axis=1)<1.5)
    if selected.sum()<10:return identity
    matrix,inliers=cv2.estimateAffinePartial2D(points[selected],nxt[selected],method=cv2.RANSAC,ransacReprojThreshold=2)
    if matrix is None or inliers.sum()<10:return identity
    return matrix if .8<np.hypot(matrix[0,0],matrix[1,0])<1.2 else identity


def actor_motion(previous,current,box,matrix):
    old=cv2.cvtColor(previous,cv2.COLOR_BGR2GRAY);now=cv2.cvtColor(current,cv2.COLOR_BGR2GRAY)
    a,b,c,d=map(int,box);mask=np.zeros(now.shape,np.uint8);mask[max(0,b):d,max(0,a):c]=255
    hsv=cv2.cvtColor(current,cv2.COLOR_BGR2HSV);mask[(hsv[:,:,0]>30)&(hsv[:,:,0]<90)&(hsv[:,:,1]>60)]=0
    points=cv2.goodFeaturesToTrack(now,50,.01,2,mask=mask)
    if points is None:return np.zeros(2)
    prev,status,_=cv2.calcOpticalFlowPyrLK(now,old,points,None,winSize=(21,21),maxLevel=3)
    if prev is None or status.sum()<3:return np.zeros(2)
    valid=status.ravel()==1;p=prev.reshape(-1,2)[valid];q=points.reshape(-1,2)[valid]
    return np.median(q-(p@matrix[:,:2].T+matrix[:,2]),axis=0)


def extract(path,timestamp,box,legacy_only=False):
    from .visual_model import frame_at
    from .motion import motion_features
    from .vision import boundary,signature
    current,actual=frame_at(path,timestamp);current,b=canonical(current,box)
    earliest=history_start(path,actual)
    if legacy_only:
        previous,_=frame_at(path,max(earliest,actual-.24));previous,_=canonical(previous,box)
        if boundary(signature(previous),signature(current)):previous=current
        return np.concatenate([np.zeros(78),motion_features(previous,current,b)]).astype(float)
    confidence,ball=locate_ball(current);center=(b[:2]+b[2:])/2;bh=max(8,b[3]-b[1]);vectors=[];legacy=None
    for lag in [.24,.48,.72]:
        previous,_=frame_at(path,max(earliest,actual-lag));previous,_=canonical(previous,box)
        if boundary(signature(previous),signature(current)):previous=current
        v=motion_features(previous,current,b)
        if legacy is None:legacy=v.copy()
        affine=camera_affine(previous,current)
        v[11:13]=actor_motion(previous,current,b,affine)/bh;v[15:17]=v[11:13]
        v[20:22]=(affine[:,:2]@center+affine[:,2]-center)/[640,current.shape[0]]
        v[3:5]=[float(ball is not None),confidence]
        if ball is not None:
            dx,dy=(ball-np.array([center[0],b[3]]))/bh;v[:3]=[dx,dy,np.hypot(dx,dy)]
        else:v[:3]=0
        old_conf,old_ball=locate_ball(previous)
        if ball is not None and old_ball is not None:
            velocity=(ball-(affine[:,:2]@old_ball+affine[:,2]))/bh;v[9:11]=velocity;v[23]=np.linalg.norm(velocity)
        else:v[9:11]=0;v[23]=0
        v[22]=float(old_ball is not None);vectors.append(np.clip(v,-10,10))
    return np.concatenate(vectors+[legacy]).astype(float)


def camera_relative_target(path,observation,target,box,target_box):
    from .visual_model import frame_at
    a,_=frame_at(path,observation);z,_=frame_at(path,target);a,b=canonical(a,box);z,q=canonical(z,target_box)
    matrix=camera_affine(a,z);foot=np.array([(b[0]+b[2])/2,b[3]]);end=np.array([(q[0]+q[2])/2,q[3]])
    return (end-(matrix[:,:2]@foot+matrix[:,2]))/max(8,b[3]-b[1])


def serialize_classifier(estimator,indices,mean,scale):
    result=dict(indices=list(map(int,indices)),mean=np.asarray(mean).tolist(),scale=np.asarray(scale).tolist(),classes=estimator.classes_.tolist())
    if hasattr(estimator,'estimators_'):
        trees=[]
        for model in estimator.estimators_:
            t=model.tree_;values=t.value[:,0,:];values=values/np.maximum(values.sum(axis=1,keepdims=True),1e-12)
            trees.append(dict(left=t.children_left.tolist(),right=t.children_right.tolist(),feature=t.feature.tolist(),threshold=t.threshold.tolist(),value=values.tolist()))
        result.update(format='forest_v1',trees=trees)
    else:result.update(format='linear_v1',coef=estimator.coef_.tolist(),intercept=estimator.intercept_.tolist())
    return result


def probabilities(vector,model):
    if model['format']=='hierarchical_v1':
        gate=probabilities(vector,model['gate']);event=probabilities(vector,model['event'])
        off=float(gate[model['gate']['classes'].index('off_ball')]);values=dict(zip(model['event']['classes'],(1-off)*event));values['off_ball']=off
        return np.array([values.get(c,0.) for c in model['classes']])
    x=(np.asarray(vector)[model['indices']]-model['mean'])/model['scale']
    if model['format']=='linear_v1':
        logits=np.asarray(model['coef'])@x+model['intercept']
        if len(logits)==1:logits=np.array([0.,logits[0]])
        p=np.exp(logits-logits.max());return p/p.sum()
    x=x.astype(np.float32);values=[]
    for t in model['trees']:
        node=0
        while t['left'][node]>=0:
            node=t['left'][node] if float(x[t['feature'][node]])<=t['threshold'][node] else t['right'][node]
        values.append(t['value'][node])
    return np.mean(values,axis=0)


@lru_cache(maxsize=4)
def load_model(path,mtime):return json.loads(Path(path).read_text())


@lru_cache(maxsize=128)
def predict_observation(path,timestamp,box,model_mtime,artifact=str(ARTIFACT)):
    m=load_model(artifact,model_mtime)
    if m['feature_version']!=FEATURE_VERSION:raise ValueError('Incompatible model feature version')
    def needed(head):
        return set(head['indices']) if head['format']!='hierarchical_v1' else needed(head['gate'])|needed(head['event'])
    required=needed(m['classifier'])
    if m.get('conditional_head'):required|=needed(m['conditional_head'])
    if m.get('movement_head',{}).get('enabled'):required|=set(m['movement_head']['indices'])
    v=extract(path,timestamp,box,legacy_only=all(i>=78 for i in required));p=probabilities(v,m['classifier']);order=np.argsort(p)[::-1];motion=None
    h=m.get('movement_head')
    if h and h.get('enabled') and m['classes'][order[0]]=='off_ball':
        x=(v[h['indices']]-h['mean'])/h['scale'];units=np.asarray(h['coef'])@x+h['intercept']
        cap=cv2.VideoCapture(str(path))
        try:width,height=cap.get(cv2.CAP_PROP_FRAME_WIDTH),cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
        finally:cap.release()
        delta=units*(box[3]-box[1])/np.array([width,height])
        motion=dict(horizon_seconds=.6,camera_relative_displacement=delta.tolist(),method='learned camera-relative off-ball motion',validation=h['validation'])
    options=[]
    if m.get('conditional_head'):
        ch=m['conditional_head'];cp=probabilities(v,ch);options=[dict(action=ch['classes'][i],probability=float(cp[i])) for i in np.argsort(cp)[::-1]]
    return dict(status='experimental',feature_kind=FEATURE_VERSION,alternatives=[dict(action=m['classes'][i],probability=float(p[i])) for i in order],conditional_options=options,conditional_scope='Conditioned on an on-ball event in the forecast window; trained from selected on-ball examples, not a causal counterfactual estimate',calibrated=False,abstain=bool(p.max()<.45),message='Learned observed state/event forecast, about 0.6 seconds ahead. Off-ball movement is supported; scores are uncalibrated.',conditional_context='Receiving depends on a teammate delivering the ball. An unrealized receiving option may remain plausible; this model does not infer the passer\'s intention.',off_ball_motion=motion,training_matches=m['training_matches'],deployment_refit=m['deployment_refit'])
