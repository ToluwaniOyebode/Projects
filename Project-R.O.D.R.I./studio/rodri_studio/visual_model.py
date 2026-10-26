"""Frozen ImageNet encoder + learned next-action head. No face recognition.

The crop locates an externally confirmed actor; this module does not identify
Rodri. Prediction uses only the frame at or before the observation timestamp.
"""
import json
from functools import lru_cache
from pathlib import Path
import threading
import cv2
import numpy as np
from .edited_video import history_start

ROOT=Path(__file__).resolve().parents[1]
ARTIFACT=ROOT/'models'/'next_action.json'
_encoder_lock=threading.Lock()


@lru_cache(maxsize=1)
def encoder():
    import torch
    from torchvision.models import resnet18, ResNet18_Weights
    torch.set_num_threads(2)
    weights=ResNet18_Weights.IMAGENET1K_V1
    local=ROOT/'models'/'resnet18-f37072fd.pth'
    if local.exists():
        network=resnet18(weights=None)
        network.load_state_dict(torch.load(local,map_location='cpu',weights_only=True))
    else:
        network=resnet18(weights=weights)
    network.fc=torch.nn.Identity()
    return network.eval(), weights.transforms()


def frame_at(path,timestamp):
    if not np.isfinite(timestamp) or timestamp<0:
        raise ValueError('Invalid observation timestamp')
    cap=cv2.VideoCapture(str(path))
    try:
        fps=cap.get(cv2.CAP_PROP_FPS)
        if fps<=0:raise ValueError('Cannot read video FPS')
        frame_index=int(np.floor(timestamp*fps+1e-6))
        cap.set(cv2.CAP_PROP_POS_FRAMES,frame_index)
        ok,image=cap.read()
        if not ok:raise ValueError('Cannot decode observation frame')
        return image,frame_index/fps
    finally:cap.release()


def visual_features(image,box):
    import torch
    from PIL import Image
    h,w=image.shape[:2]
    x1,y1,x2,y2=map(float,box)
    if not (0<=x1<x2<=w and 0<=y1<y2<=h):
        raise ValueError('Actor box is outside the frame')
    cx,cy=(x1+x2)/2,(y1+y2)/2;bw,bh=x2-x1,y2-y1
    patches=[]
    for sx,sy in [(1.3,1.2),(5.,3.)]:
        a,b=max(0,int(cx-bw*sx/2)),max(0,int(cy-bh*sy/2))
        c,d=min(w,int(cx+bw*sx/2)),min(h,int(cy+bh*sy/2))
        patches.append(Image.fromarray(cv2.cvtColor(image[b:d,a:c],cv2.COLOR_BGR2RGB)))
    with _encoder_lock:
        model,transform=encoder()
        batch=torch.stack([transform(p) for p in patches])
        with torch.inference_mode():emb=model(batch).cpu().numpy()
    emb/=np.maximum(np.linalg.norm(emb,axis=1,keepdims=True),1e-8)
    # No target time, filename, future image, score graphic or commentary feature.
    return np.concatenate([emb.ravel(),np.array([cx/w,cy/h,bw/w,bh/h],dtype=np.float32)])


def extract_observation(path,timestamp,box):
    from .motion import motion_features
    current,actual=frame_at(path,timestamp)
    previous,_=frame_at(path,max(history_start(path,actual),actual-.24))
    return np.concatenate([visual_features(current,box),motion_features(previous,current,box)])


def score_features(vector,model):
    x=np.asarray(vector,dtype=float)
    coef=np.asarray(model['coef']);intercept=np.asarray(model['intercept'])
    if x.shape!=(model['input_dimension'] if 'input_dimension' in model else model['feature_dimension'],):raise ValueError('Feature schema mismatch')
    if model.get('indices') is not None: x=x[np.asarray(model['indices'],dtype=int)]
    if 'mean' in model: x=(x-np.array(model['mean']))/np.array(model['scale'])
    logits=coef@x+intercept
    if len(logits)==1:logits=np.array([0.,logits[0]])
    probabilities=np.exp(logits-logits.max());probabilities/=probabilities.sum()
    return probabilities


def predict_image(image,box,artifact=ARTIFACT,previous=None):
    if not Path(artifact).exists():return {'status':'untrained','alternatives':[],'message':'No visual checkpoint available.'}
    model=json.loads(Path(artifact).read_text())
    needs_appearance=any(i<1028 for i in model.get('indices',range(1028)))
    vector=visual_features(image,box) if needs_appearance else np.zeros(1028)
    if model.get('input_dimension',1028)>1028:
        from .motion import motion_features
        vector=np.concatenate([vector,motion_features(previous,image,box)])
    probabilities=score_features(vector,model)
    indices=np.argsort(probabilities)[::-1]
    maximum=float(probabilities[indices[0]])
    return dict(status='experimental',quality=('below_majority_baseline_in_development_holdout' if model.get('held_out_metrics',{}).get('accuracy',0)<model.get('held_out_metrics',{}).get('majority_accuracy',0) else 'experimental_unvalidated'),deployment_refit=model.get('deployment_refit',False),abstain=maximum<.45,alternatives=[dict(action=model['classes'][i],probability=float(probabilities[i])) for i in indices[:3]],message='Small-data visual model; uncalibrated scores. Actor identity supplied separately.',training_matches=model['training_matches'],feature_kind=model['kind'])


@lru_cache(maxsize=128)
def predict_observation(path,timestamp,box,model_mtime,artifact=str(ARTIFACT)):
    image,actual=frame_at(path,timestamp)
    previous,_=frame_at(path,max(history_start(path,actual),actual-.24))
    return predict_image(image,box,artifact=artifact,previous=previous)


def fit_head(vectors,labels,training_matches,indices=None):
    from sklearn.linear_model import LogisticRegression
    if len(set(labels))<2:raise ValueError('Need at least two target actions')
    input_dimension=vectors.shape[1]
    indices=list(range(input_dimension)) if indices is None else list(indices)
    selected=vectors[:,indices]
    mean=selected.mean(axis=0);scale=selected.std(axis=0);scale[scale<1e-5]=1
    # Normalize using training data only.
    head=LogisticRegression(C=1.0,max_iter=2000,class_weight='balanced',random_state=42)
    head.fit((selected-mean)/scale,labels)
    return dict(kind=('causal_motion_linear_v2' if all(i>=1028 for i in indices) else 'resnet18_actor_context_motion_linear_v2'),input_dimension=int(input_dimension),indices=indices,mean=mean.tolist(),scale=scale.tolist(),feature_dimension=len(indices),classes=head.classes_.tolist(),coef=head.coef_.tolist(),intercept=head.intercept_.tolist(),training_matches=sorted(training_matches),encoder=('none for motion-only inference' if all(i>=1028 for i in indices) else 'ImageNet ResNet18 frozen'),forecast_scope='next reviewed coarse action in a curated possession episode; usually 0.4–1.0 s lead',identity='externally confirmed actor box required',label_quality='single-AI-reviewed visual actions with contextual identity evidence; no independent annotator audit',calibrated=False)
