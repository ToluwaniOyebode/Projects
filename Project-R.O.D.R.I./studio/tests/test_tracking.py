import cv2
import numpy as np
from rodri_studio.tracking import Tracker
from rodri_studio.app import context


def test_velocity_prediction_preserves_ids_through_crossing():
    tracker=Tracker();frame=np.full((200,200,3),100,np.uint8)
    ids=[]
    for step,(a,b) in enumerate([(20,100),(40,80),(60,60),(80,40),(100,20)]):
        # Keep a vertical separation at the crossing; reverse detection order.
        detections=[dict(box=[a,30,a+12,80],confidence=.9),dict(box=[b,45,b+12,95],confidence=.9)]
        if step%2:detections=detections[::-1]
        out=tracker.update(detections,frame,step*.2)
        first=next(q for q in out if q['box'][1]==30);second=next(q for q in out if q['box'][1]==45)
        ids.append((first['track'],second['track']))
    assert all(q==ids[0] for q in ids),ids


def test_camera_pan_does_not_create_new_identity():
    rng=np.random.default_rng(2);old=rng.integers(0,255,(200,200,3),dtype=np.uint8)
    new=cv2.warpAffine(old,np.array([[1.,0.,30.],[0.,1.,0.]]),(200,200))
    tracker=Tracker();a=tracker.update([dict(box=[40,50,60,110],confidence=.9)],old,0)
    b=tracker.update([dict(box=[70,50,90,110],confidence=.9)],new,.2)
    assert a[0]['track']==b[0]['track']


def test_uncertain_association_requires_new_confirmation():
    det=dict(track=1,identity_uncertain=True)
    r=dict(frames=[dict(time=.2,shot=1,replay_suspected=False,detections=[det])],identities={'1':[dict(track=1,time=0,expires=5)]},replays=[])
    assert context(r,.2)[1] is None
    r['identities']['1'][0]['time']=.2
    assert context(r,.2)[1] is det
