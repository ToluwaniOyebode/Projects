import json
import numpy as np
import pytest
from rodri_studio.edited_video import EditTimeline, FORMAT, validate_observation
from rodri_studio import sequence_model as sequence
from rodri_studio.pipeline import analyze
from rodri_studio.app import context, apply_reviewed_anchors
from test_core import make_video, FakeDetector


def metadata():
    return dict(format=FORMAT,match_id='same_match',rodri_present=False,actor_scope='general_football',segments=[dict(clip_start_seconds=0.,clip_end_seconds_exclusive=1.,source_start_seconds=20.,source_end_seconds_exclusive=21.,continuous_sequence_id='a'),dict(clip_start_seconds=1.,clip_end_seconds_exclusive=3.,source_start_seconds=40.,source_end_seconds_exclusive=42.,continuous_sequence_id='b')])


def sidecar(path):
    from pathlib import Path
    Path(str(path)+'.edits.json').write_text(json.dumps(metadata()))


def test_edit_times_are_half_open_and_preserve_source_time():
    t=EditTimeline(metadata())
    assert t.source_time(.6)==pytest.approx(20.6)
    assert t.source_time(1.)==40.
    assert t.crosses(.9,1.)
    assert not t.crosses(1.,1.6)
    with pytest.raises(ValueError):t.segment(3.)
    with pytest.raises(ValueError):t.segment(float('nan'))


def test_reject_incomplete_or_overlapping_timeline():
    m=metadata();m['segments'][1]['clip_start_seconds']=1.1
    with pytest.raises(ValueError):EditTimeline(m)
    m=metadata();m['segments'][1]['source_end_seconds_exclusive']=45.
    with pytest.raises(ValueError):EditTimeline(m)


def test_feature_history_never_reads_through_explicit_edit(tmp_path,monkeypatch):
    p=tmp_path/'clip.mp4';sidecar(p)
    image=np.full((360,640,3),100,np.uint8);requests=[];legacy=[]
    monkeypatch.setattr(sequence,'video_fps',lambda _:25.)
    monkeypatch.setattr(sequence,'frame_width',lambda _:640.)
    def sample(path,index,fps):
        requests.append(index/fps)
        return image,index/fps,[dict(box=[200,100,220,160],confidence=.9)],[]
    def previous(path,time):legacy.append(time);return image,time
    monkeypatch.setattr(sequence,'sample',sample);monkeypatch.setattr(sequence,'frame_at',previous)
    x,e=sequence.extract(p,1.12,[200,100,220,160])
    assert min(requests)>=1. and min(legacy)>=1.
    assert e['history_cut'] and e['history_samples']==1
    assert e['edit_sequence']=='b' and e['original_source_seconds']==pytest.approx(40.12)
    assert x.shape==(131,) and np.isfinite(x).all()


def test_identical_images_still_reset_tracker_at_edit(tmp_path):
    p=tmp_path/'clip.mp4';make_video(p);sidecar(p)
    r=analyze(p,0,1.4,'test',detector=FakeDetector())
    before=next(f for f in r['frames'] if f['time']==.8)
    after=next(f for f in r['frames'] if f['time']==1.)
    assert before['shot']!=after['shot']
    assert 1. in r['cuts'] and r['edit_cuts']==[1.]
    assert after['original_source_seconds']==40.
    r['identities']={str(before['shot']):[dict(track=1,time=.8,expires=5.)]}
    assert context(r,1.)[1] is None
    assert r['actor_scope']=='general_football' and r['rodri_present'] is False


def test_labels_cannot_bridge_edit_or_change_match_id(tmp_path):
    p=tmp_path/'clip.mp4';sidecar(p)
    row=dict(match_id='same_match',observation_seconds=.9,target_seconds=1.5)
    with pytest.raises(ValueError,match='removed section'):validate_observation(p,row)
    row.update(observation_seconds=1.1,target_seconds=1.7,match_id='fake_clip_match')
    with pytest.raises(ValueError,match='same source match ID|share the source match ID'):validate_observation(p,row)


def test_no_rodri_anchor_applied_to_general_match(monkeypatch):
    def forbidden():raise AssertionError('Rodri anchors must not be read')
    from rodri_studio import app as module
    monkeypatch.setattr(module,'reviewed_events_path',forbidden)
    apply_reviewed_anchors({},dict(rodri_present=False,known_match='same_match'))


def test_general_confirmation_does_not_name_rodri():
    r=dict(actor_scope='general_football',frames=[dict(time=0,shot=1,replay_suspected=False,detections=[])],identities={},replays=[])
    assert 'selected player' in context(r,0)[2]
    assert 'Rodri' not in context(r,0)[2]


def test_uploaded_known_generic_clip_keeps_its_edit_timeline(tmp_path,monkeypatch):
    import hashlib
    from fastapi.testclient import TestClient
    from rodri_studio import app as module
    from rodri_studio.edited_video import timeline_for
    bundle=tmp_path/'bundle';(bundle/'data').mkdir(parents=True)
    video=tmp_path/'generic.mp4';make_video(video)
    digest=hashlib.sha256(video.read_bytes()).hexdigest()
    row=dict(match_id='same_match',sha256=digest,rodri_present=False,edit_metadata=metadata())
    (bundle/'data/video_manifest.json').write_text(json.dumps([row]))
    uploads=tmp_path/'uploads';uploads.mkdir()
    monkeypatch.setattr(module,'ROOT',bundle/'rodri_studio')
    monkeypatch.setattr(module,'DATA',uploads)
    client=TestClient(module.app)
    with video.open('rb') as f:
        response=client.post('/api/videos',files={'video':('renamed.mp4',f,'video/mp4')})
    assert response.status_code==200
    info=response.json()
    assert info['actor_scope']=='general_football' and info['rodri_present'] is False
    assert timeline_for(uploads/info['id']/'source.mp4').source_time(1.)==40.


def test_mixed_checkpoint_never_replaces_rodri_default(tmp_path,monkeypatch):
    from rodri_studio import app as module
    for name in ['next_action_v4.json','next_action_v5.json']:
        (tmp_path/name).write_text('{}')
    monkeypatch.setattr(module,'VISUAL_MODELS',tmp_path)
    monkeypatch.setattr(sequence,'predict_observation',lambda *args:args[-1])
    assert module.action_prediction('x',0,{'box':[0,0,1,1]},{}).endswith('next_action_v4.json')
    assert module.action_prediction('x',0,{'box':[0,0,1,1]},{},'mixed').endswith('next_action_v5.json')


def test_registered_match_id_cannot_be_changed_per_clip(tmp_path,monkeypatch):
    from fastapi.testclient import TestClient
    from rodri_studio import app as module
    monkeypatch.setattr(module,'DATA',tmp_path)
    uid='c'*32;folder=tmp_path/uid;folder.mkdir();(folder/'video.json').write_text('{}')
    r=dict(known_match='same_match',actor_scope='general_football',metadata={'duration':3,'width':100,'height':100},frames=[dict(time=0,shot=1,replay_suspected=False,detections=[dict(track=1,box=[10,10,20,40],confidence=.8,center=[.2,.3],velocity=[0,0])]),dict(time=1,shot=1,replay_suspected=False,detections=[])],identities={'1':[dict(time=0,expires=2,track=1)]},replays=[],cuts=[0],annotations=[])
    (folder/'analysis.json').write_text(json.dumps(r))
    client=TestClient(module.app)
    response=client.post(f'/api/videos/{uid}/labels',json=dict(time=0,target_time=.6,target_action='carry',match_id='one_clip_is_not_a_match'))
    assert response.status_code==400 and 'original match ID' in response.json()['detail']
