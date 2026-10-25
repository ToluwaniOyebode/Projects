"""Camera-compensated global assignment; uncertain associations never certify a name."""
import cv2
import numpy as np
from scipy.optimize import linear_sum_assignment


def jersey_descriptor(frame,box):
    x1,y1,x2,y2=map(float,box);w=x2-x1;h=y2-y1
    a,b=max(0,int(x1+.15*w)),max(0,int(y1+.18*h))
    c,d=min(frame.shape[1],int(x2-.15*w)),min(frame.shape[0],int(y1+.68*h))
    patch=frame[b:d,a:c]
    if not patch.size:return np.zeros(56)
    hsv=cv2.cvtColor(patch,cv2.COLOR_BGR2HSV)
    color=cv2.calcHist([hsv],[0,1],None,[12,4],[0,180,0,256]).ravel();color/=max(color.sum(),1)
    gray=cv2.calcHist([cv2.cvtColor(patch,cv2.COLOR_BGR2GRAY)],[0],None,[8],[0,256]).ravel();gray/=max(gray.sum(),1)
    return np.r_[.85*color,.15*gray]


def iou(a,b):
    lo=np.maximum(a[:2],b[:2]);hi=np.minimum(a[2:],b[2:]);inter=np.maximum(hi-lo,0).prod()
    return float(inter/max((a[2:]-a[:2]).prod()+(b[2:]-b[:2]).prod()-inter,1e-9))


class Tracker:
    def __init__(self):
        self.tracks={};self.next_id=1;self.previous=None;self.previous_time=None;self.last_camera=np.array([[1.,0.,0.],[0.,1.,0.]])

    def update(self,detections,frame,timestamp):
        from .temporal_model import camera_affine
        height,width=frame.shape[:2];units=np.array([width,height,width,height]);step=0 if self.previous_time is None else timestamp-self.previous_time
        self.tracks={k:v for k,v in self.tracks.items() if 0<timestamp-v['last_seen']<=.7}
        matrix=np.array([[1.,0.,0.],[0.,1.,0.]])
        if self.previous is not None and 0<step<=.7:
            old_gray=cv2.cvtColor(self.previous,cv2.COLOR_BGR2GRAY).astype(np.float32)
            new_gray=cv2.cvtColor(frame,cv2.COLOR_BGR2GRAY).astype(np.float32)
            a,b=int(height*.12),int(height*.9)
            window=cv2.createHanningWindow((width,b-a),cv2.CV_32F)
            shift,response=cv2.phaseCorrelate(old_gray[a:b].copy(),new_gray[a:b].copy(),window)
            if response>.35 and np.linalg.norm(shift)<max(width,height)*.25:
                matrix[:,2]=shift
            else:matrix=camera_affine(self.previous,frame)
        self.last_camera=matrix.copy()
        keys=list(self.tracks);vectors=[jersey_descriptor(frame,q['box']) for q in detections]
        boxes=[np.asarray(q['box'],float)/units for q in detections]
        for old in self.tracks.values():
            b=old['prediction']*units;corners=np.array([[b[0],b[1]],[b[2],b[3]]])@matrix[:,:2].T+matrix[:,2]
            projected=np.r_[corners[0],corners[1]]/units
            old['prediction']=projected+np.tile(old['motion']*max(step,0),2)
        costs=np.full((len(detections),len(keys)),1000.)
        for i,b in enumerate(boxes):
            center=(b[:2]+b[2:])/2
            for j,tid in enumerate(keys):
                old=self.tracks[tid];pred=old['prediction'];distance=np.linalg.norm(center-(pred[:2]+pred[2:])/2)
                gate=max(.025,min(.12,.9*(pred[3]-pred[1])+.02));color=float(np.abs(vectors[i]-old['appearance']).sum()/2)
                ratio=(b[3]-b[1])/max(pred[3]-pred[1],1e-6)
                if distance<=gate and color<.65 and .4<ratio<2.5:
                    costs[i,j]=.6*distance/gate+.25*color+.15*(1-iou(b,pred))
        assigned={}
        if costs.size:
            rows,columns=linear_sum_assignment(costs)
            for i,j in zip(rows,columns):
                if costs[i,j]<.85:assigned[int(i)]=int(j)
        output=[]
        for i,(det,b) in enumerate(zip(detections,boxes)):
            center=(b[:2]+b[2:])/2;old=None;uncertain=False;quality=1.
            if i in assigned:
                j=assigned[i];tid=keys[j];old=self.tracks[tid];dt=timestamp-old['last_seen'];error=center-(old['prediction'][:2]+old['prediction'][2:])/2
                motion=old['motion']+.7*error/max(dt,1e-6);velocity=(center-old['center'])/dt
                alternatives=np.delete(costs[i],j);competitors=np.delete(costs[:,j],i)
                margin=min(float(alternatives.min()) if len(alternatives) else 1000.,float(competitors.min()) if len(competitors) else 1000.)-costs[i,j]
                uncertain=bool(margin<.06);quality=float(max(0,1-costs[i,j]))
            else:
                tid=self.next_id;self.next_id+=1;motion=np.zeros(2);velocity=np.zeros(2)
            self.tracks[tid]=dict(prediction=b.copy(),center=center,appearance=vectors[i],motion=motion,last_seen=timestamp)
            output.append(dict(**det,track=tid,center=center.tolist(),velocity=velocity.tolist(),camera_compensated_velocity=motion.tolist(),association_quality=quality,identity_uncertain=uncertain))
        self.previous=frame.copy();self.previous_time=timestamp
        return output
