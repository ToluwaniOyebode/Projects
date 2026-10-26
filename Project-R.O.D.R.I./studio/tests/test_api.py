from io import BytesIO
import json
from fastapi.testclient import TestClient
import pytest
from rodri_studio import app as module
from test_core import make_video

@pytest.fixture
def client(tmp_path,monkeypatch):
    monkeypatch.setattr(module,'DATA',tmp_path)
    monkeypatch.setattr(module,'MODEL',tmp_path/'model.json')
    monkeypatch.setattr(module,'VISUAL_MODELS',tmp_path)
    return TestClient(module.app)


def test_upload_playback_export_and_bad_request(client,tmp_path):
    video=tmp_path/'sample.mp4';make_video(video)
    with video.open('rb') as f:
        r=client.post('/api/videos',files={'video':('sample.mp4',f,'video/mp4')})
    assert r.status_code==200
    uid=r.json()['id']
    assert client.get(f'/api/videos/{uid}/source',headers={'Range':'bytes=0-31'}).status_code==206
    assert client.get(f'/api/videos/{uid}/analysis').status_code==409
    assert client.post(f'/api/videos/{uid}/analyze',json={'start':10}).status_code==400
    assert client.post(f'/api/videos/{uid}/analyze',json={'backend':'fake'}).status_code==400
    assert client.post('/api/train').status_code==400
    assert client.post('/api/videos',files={'video':('x.txt',b'x')}).status_code==400
    assert client.get('/').status_code==200


def test_replay_added_after_annotation_is_excluded(client,tmp_path):
    uid='a'*32;d=tmp_path/uid;d.mkdir();(d/'video.json').write_text('{}')
    r=dict(metadata={'duration':30},frames=[{'time':0,'shot':1,'replay_suspected':False,'detections':[]}],cuts=[0],identities={},replays=[],annotations=[dict(time=1,target_time=3,features=[0]*7,target_action='carry',match_id='one',verified=True)])
    (d/'analysis.json').write_text(json.dumps(r))
    assert client.post(f'/api/videos/{uid}/replay',json={'start':1,'end':4}).status_code==200
    assert client.get(f'/api/videos/{uid}/forecast?time=1').json()['prediction']['status']=='suppressed'
    assert client.get(f'/api/videos/{uid}/export').status_code==200
    assert client.post(f'/api/videos/{uid}/identity',json={'time':0,'track':1}).status_code==400


def test_identity_label_and_cut_guard(client,tmp_path):
    uid='b'*32;d=tmp_path/uid;d.mkdir();(d/'video.json').write_text('{}')
    det=dict(track=1,box=[10,10,30,50],confidence=.8,center=[.2,.3],velocity=[0,0])
    r=dict(metadata={'duration':10,'width':100,'height':100},frames=[dict(time=0,shot=1,replay_suspected=False,detections=[det]),dict(time=1,shot=2,replay_suspected=False,detections=[det]),dict(time=2,shot=2,replay_suspected=False,detections=[det])],cuts=[0,1],identities={},replays=[],annotations=[])
    (d/'analysis.json').write_text(json.dumps(r))
    assert client.post(f'/api/videos/{uid}/identity',json={'time':0,'track':1}).status_code==200
    assert client.get(f'/api/videos/{uid}/forecast?time=0').json()['prediction']['status']=='untrained'
    assert client.get(f'/api/videos/{uid}/forecast?time=1').json()['prediction']['status']=='suppressed'
    label=dict(time=0,target_time=2,target_action='carry',match_id='one')
    assert client.post(f'/api/videos/{uid}/labels',json=label).status_code==400
    label['target_time']=.5
    assert client.post(f'/api/videos/{uid}/labels',json=label).status_code==200
    exported=client.get(f'/api/videos/{uid}/export').json()
    assert len(exported['annotations'])==1



def test_all_players_do_not_require_named_identity_and_abstain(client,tmp_path,monkeypatch):
    uid='c'*32;d=tmp_path/uid;d.mkdir();(d/'video.json').write_text('{}')
    detections=[dict(track=1,box=[10,10,30,50]),dict(track=2,box=[40,10,60,50],identity_uncertain=True)]
    result=dict(metadata={'duration':10},frames=[dict(time=1,shot=2,replay_suspected=False,detections=detections,original_source_seconds=81)],identities={},replays=[])
    (d/'analysis.json').write_text(json.dumps(result))
    calls=[]
    def score(*args):
        calls.append(args[-1]);return dict(status='experimental',alternatives=[])
    monkeypatch.setattr(module,'action_prediction',score)
    response=client.get(f'/api/videos/{uid}/players?time=1').json()
    assert len(response['players'])==2 and calls==[]
    response=client.get(f'/api/videos/{uid}/players?time=1&actions=true').json()
    assert response['original_source_seconds']==81
    assert [p['track_key'] for p in response['players']]==['2:1','2:2']
    assert response['players'][1]['prediction']['status']=='suppressed'
    assert calls==['mixed']
    assert client.get(f'/api/videos/{uid}/players?time=2').json()['players']==[]
    assert client.get(f'/api/videos/{uid}/players?time=-1').status_code==400
    result['replays']=[dict(start=0,end=2)];(d/'analysis.json').write_text(json.dumps(result))
    response=client.get(f'/api/videos/{uid}/players?time=1&actions=true').json()
    assert all(p['prediction']['status']=='suppressed' for p in response['players'])
    assert calls==['mixed']
