"""Causal optical flow and tentative white-ball cues; no scripted action labels."""
import cv2
import numpy as np


def ball_candidates(image,box):
    x1,y1,x2,y2=box;bh=y2-y1;cx=(x1+x2)/2
    h,w=image.shape[:2]
    a,b=max(0,int(cx-3*bh)),max(0,int(y2-1.6*bh))
    c,d=min(w,int(cx+3*bh)),min(h,int(y2+1.2*bh))
    patch=image[b:d,a:c]
    if not patch.size:return []
    hsv=cv2.cvtColor(patch,cv2.COLOR_BGR2HSV)
    white=((hsv[:,:,1]<80)&(hsv[:,:,2]>150)).astype(np.uint8)
    # Exclude the actor's shirt/shorts, retaining foot-level pixels.
    ya,yb=max(0,int(y1-b)),max(0,int(y2-b-.2*bh))
    xa,xb=max(0,int(x1-a-2)),min(white.shape[1],int(x2-a+2))
    white[ya:yb,xa:xb]=0
    count,labels,stats,centers=cv2.connectedComponentsWithStats(white)
    candidates=[]
    for i in range(1,count):
        x,y,bw,hh,area=stats[i]
        if 1<=area<=max(24,.04*bh*bh) and bw<=max(8,.4*bh) and hh<=max(8,.4*bh):
            px,py=centers[i]+[a,b]
            candidates.append((float(px),float(py)))
    return candidates


def motion_features(previous,current,box):
    x1,y1,x2,y2=map(float,box);bh=max(8,y2-y1);bw=x2-x1
    h,w=current.shape[:2];cx=(x1+x2)/2;cy=(y1+y2)/2
    cur=ball_candidates(current,box)
    ball=min(cur,key=lambda p:(p[0]-cx)**2+(p[1]-y2)**2) if cur else (cx,y2)
    dx,dy=(ball[0]-cx)/bh,(ball[1]-y2)/bh
    base=[dx,dy,float(np.hypot(dx,dy)),float(bool(cur)),min(len(cur),20)/20,bw/bh,bh/h,cx/w,cy/h]
    if previous is None:return np.array(base+[0.]*17,dtype=np.float32)
    prev_gray=cv2.cvtColor(previous,cv2.COLOR_BGR2GRAY);gray=cv2.cvtColor(current,cv2.COLOR_BGR2GRAY)
    flow=cv2.calcOpticalFlowFarneback(prev_gray,gray,None,.5,3,15,3,5,1.2,0)
    hsv=cv2.cvtColor(current,cv2.COLOR_BGR2HSV)
    grass=(hsv[:,:,0]>30)&(hsv[:,:,0]<90)&(hsv[:,:,1]>55)
    grass[max(0,int(y1)):min(h,int(y2)),max(0,int(x1)):min(w,int(x2))]=False
    camera=np.median(flow[grass],axis=0) if grass.any() else np.zeros(2)
    local=flow[max(0,int(y1)):min(h,int(y2)),max(0,int(x1)):min(w,int(x2))]-camera
    if not local.size:local=np.zeros((1,1,2))
    lo=local.reshape(-1,2)/bh
    lower=lo[len(lo)//2:]
    back_box=[x1-camera[0],y1-camera[1],x2-camera[0],y2-camera[1]]
    old=ball_candidates(previous,back_box)
    old_ball=min(old,key=lambda p:(p[0]+camera[0]-ball[0])**2+(p[1]+camera[1]-ball[1])**2) if old else ball
    ball_motion=(np.array(ball)-old_ball-camera)/bh if old else np.zeros(2)
    extras=[*ball_motion.tolist(),*lo.mean(axis=0).tolist(),*lo.std(axis=0).tolist(),*lower.mean(axis=0).tolist(),float(np.percentile(np.linalg.norm(lo,axis=1),90)),float(np.percentile(np.linalg.norm(lo,axis=1),50)),float(np.mean(gray[max(0,int(y1)):min(h,int(y2)),max(0,int(x1)):min(w,int(x2))]))/255,*camera.tolist(),float(bool(old)),float(np.linalg.norm(ball_motion)),float(np.mean(np.abs(gray.astype(float)-prev_gray.astype(float))))/255,1.]
    return np.nan_to_num(np.clip(np.array(base+extras,dtype=np.float32),-10,10))
