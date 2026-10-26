import json
from pathlib import Path
import cv2
import numpy as np
import pytest
from rodri_studio.vision import Tracker, signature, boundary, Detector
from rodri_studio.pipeline import analyze, inspect
from rodri_studio.predictor import train, predict
from rodri_studio.app import context


def make_video(path):
    writer=cv2.VideoWriter(str(path),cv2.VideoWriter_fourcc(*'mp4v'),10,(160,128))
    assert writer.isOpened()
    for i in range(30):
        image=np.zeros((128,160,3),np.uint8)
        image[:]=(0,90,0) if i<15 else (110,20,20)
        writer.write(image)
    writer.release()


class FakeDetector:
    def detect(self,frame):
        return [dict(box=[20.,20.,40.,100.],confidence=.8)]


def test_camera_cut_resets_tracker_and_video_smoke(tmp_path):
    path=tmp_path/'fixture.mp4';make_video(path)
    result=analyze(path,0,3,'test',detector=FakeDetector())
    assert len(result['cuts'])==2
    assert len(result['frames'])==15
    assert result['frames'][0]['time']==0
    assert result['frames'][-1]['time']==2.8
    assert result['identities']=={}
    for f in result['frames']:
        assert f['detections'][0]['track']==1
    assert inspect(path)['duration']==3


def test_hog_real_video_smoke(tmp_path):
    path=tmp_path/'fixture.mp4';make_video(path)
    result=analyze(path,0,1,'hog')
    assert len(result['frames'])==5
    assert not result['frames'][0]['detections']


def test_bad_video_and_bounds(tmp_path):
    path=tmp_path/'bad.mp4';path.write_bytes(b'not a video')
    with pytest.raises(ValueError):inspect(path)
    path=tmp_path/'ok.mp4';make_video(path)
    for start,duration in [(0,0),(3,1),(-1,1),(0,float('nan'))]:
        with pytest.raises(ValueError):analyze(path,start,duration,'hog')


def test_identity_never_crosses_cuts_expiry_or_replay():
    d=dict(track=1)
    r=dict(frames=[dict(time=0,shot=1,replay_suspected=False,detections=[d]),dict(time=6,shot=1,replay_suspected=False,detections=[d]),dict(time=7,shot=2,replay_suspected=False,detections=[d])],identities={'1':dict(track=1,time=0,expires=5)},replays=[])
    assert context(r,0)[1] is d
    assert context(r,6)[1] is None
    assert context(r,7)[1] is None
    r['replays']=[dict(start=0,end=1)]
    assert context(r,0)[1] is None
    r['replays']=[];r['frames'][0]['replay_suspected']=True
    assert context(r,0)[1] is None


def test_no_model_no_fake_probabilities(tmp_path):
    result=predict([0]*7,tmp_path/'missing.json')
    assert result['status']=='untrained'
    assert result['alternatives']==[]


def test_training_requires_match_holdout(tmp_path):
    with pytest.raises(ValueError):train([],tmp_path/'model.json')
    # Artificial feature/label fixture tests mechanics, not football accuracy.
    rows=[dict(match_id=str(m),verified=True,replay=False,features=[i%2]*7,target_action='carry' if i%2 else 'short_pass') for m in range(3) for i in range(12)]
    path=tmp_path/'model.json';metrics=train(rows,path)
    model=json.loads(path.read_text())
    assert metrics['held_out_match'] not in model['training_matches']
    assert metrics['test_examples']==12
    result=predict([0]*7,path)
    assert result['status']=='experimental'
    assert sum(x['probability'] for x in result['alternatives'])==pytest.approx(1)


def test_tracker_assignment_one_to_one_and_occlusion():
    f=np.full((200,200,3),100,np.uint8);tracker=Tracker()
    a=tracker.update([dict(box=[20,20,40,80],confidence=.9)],f,0)
    b=tracker.update([dict(box=[21,20,41,80],confidence=.9),dict(box=[22,20,42,80],confidence=.9)],f,.2)
    assert len({x['track'] for x in b})==2
    assert b[0]['track']==a[0]['track']
    c=tracker.update([dict(box=[21,20,41,80],confidence=.9)],f,2)
    assert c[0]['track'] not in {x['track'] for x in b}


def test_overlay_export_is_decodable(tmp_path):
    from rodri_studio.render import render_video
    path=tmp_path/'source.mp4';make_video(path)
    r=analyze(path,0,1,'hog')
    output=tmp_path/'overlay.mp4'
    stats=render_video(path,r,output,tmp_path/'missing.json')
    assert stats['frames']==10
    assert inspect(output)['frames']==10



def test_batched_detection_preserves_frame_order_and_cut_resets(tmp_path):
    path=tmp_path/'fixture.mp4';make_video(path)
    class BatchDetector(FakeDetector):
        batches=[]
        def detect_many(self,images):
            self.batches.append(len(images))
            return [self.detect(image) for image in images]
    detector=BatchDetector()
    result=analyze(path,0,3,'test',detector=detector)
    reference=analyze(path,0,3,'test',detector=FakeDetector())
    assert result==reference
    assert detector.batches==[4,4,4,3]
    assert result['actor_scope']=='general_football'
