import importlib.util
from pathlib import Path
import numpy as np
from rodri_studio import sequence_model as sequence


def ball(x,confidence=.3):
    return dict(center=[x,150],box=[x-2,148,x+2,152],confidence=confidence)


def test_ball_association_masks_weak_global_jump():
    a=sequence.BallAssociation()
    assert a.update([],0) is None
    assert not a.update([ball(50)],0)['confirmed']
    assert a.update([ball(55)],.5)['confirmed']
    assert a.update([ball(500)],1) is None
    assert a.update([ball(500,.9)],1)['confirmed']


def test_sequence_reads_only_causal_frames_and_masks_unavailable_past(monkeypatch):
    rng=np.random.default_rng(4);image=rng.integers(0,255,(360,640,3),dtype=np.uint8);requests=[];earlier=[]
    monkeypatch.setattr(sequence,'video_fps',lambda _:25.)
    monkeypatch.setattr(sequence,'frame_width',lambda _:640.)
    def sample(path,index,fps):
        requests.append(index);return image,index/fps,[dict(box=[200,100,220,160],confidence=.9)],[]
    def previous(path,time):earlier.append(time);return image,time
    monkeypatch.setattr(sequence,'sample',sample);monkeypatch.setattr(sequence,'frame_at',previous)
    x,e=sequence.extract('not-opened.mp4',2.7,[200,100,220,160])
    assert x.shape==(131,) and np.isfinite(x).all()
    assert max(requests)==67 and min(requests)>=0
    assert all(t<=2.7 for t in earlier)
    assert e['history_seconds']==2.5 and e['history_samples']==6
    assert np.all(x[66:77]==0) # 3.0-second state is unavailable
    assert e['ball'] is None


def test_temporal_embargo_removes_whole_neighboring_episode():
    path=Path(__file__).resolve().parents[1]/'scripts'/'train_sequence.py'
    spec=importlib.util.spec_from_file_location('train_sequence_test',path);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    def row(ep,time):return dict(match_id='match',episode=ep,observation_seconds=time,target_seconds=time+.6)
    rows=[row('early',10),row('reserved',100),row('neighbor',130),row('later',250),row('neighbor',150)]
    train,test,groups=module.temporal_partition(rows,dict(held_out_episodes=['reserved'],minimum_embargo_seconds=45))
    assert train.tolist()==[True,False,False,True,False]
    assert test.tolist()==[False,True,False,False,False]
    assert not set(groups[train])&set(groups[test])
