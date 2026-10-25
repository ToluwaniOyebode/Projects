import json
from pathlib import Path
import cv2
import numpy as np
import pytest
from rodri_studio.motion import motion_features
from rodri_studio.visual_model import frame_at,fit_head,score_features,predict_image
from test_core import make_video


def test_motion_feature_schema_and_missing_history():
    image=np.full((128,160,3),(30,100,30),np.uint8)
    box=[30,20,50,80]
    no_history=motion_features(None,image,box)
    with_history=motion_features(image,image,box)
    assert no_history.shape==with_history.shape==(26,)
    assert np.isfinite(with_history).all()


def test_timestamp_floor_is_causal(tmp_path):
    path=tmp_path/'source.mp4';make_video(path)
    _,actual=frame_at(path,.219)
    assert actual==pytest.approx(.2)
    assert actual<=.219


def test_serialized_head_reproduces_probabilities():
    x=np.zeros((12,1054))
    x[:,1028:]=np.array([[0]*26,[1]*26]*6)
    y=np.array(['pass','receive']*6)
    head=fit_head(x,y,{'training_match'},indices=range(1028,1054))
    scores=score_features(x[0],json.loads(json.dumps(head)))
    assert scores.sum()==pytest.approx(1)
    assert head['classes'][scores.argmax()]=='pass'
    assert head['training_matches']==['training_match']
    with pytest.raises(ValueError):score_features(np.zeros(3),head)


def test_motion_checkpoint_does_not_need_appearance_encoder(tmp_path,monkeypatch):
    from rodri_studio import visual_model
    x=np.zeros((12,1054));x[1::2,1028:]=1
    head=fit_head(x,np.array(['pass','receive']*6),{'fixture'},range(1028,1054))
    p=tmp_path/'head.json';p.write_text(json.dumps(head))
    def fail(*args):raise AssertionError('Appearance encoder should not run')
    monkeypatch.setattr(visual_model,'visual_features',fail)
    image=np.full((128,160,3),(30,100,30),np.uint8)
    prediction=predict_image(image,[30,20,50,80],p,previous=image)
    assert prediction['status']=='experimental'
    assert len(prediction['alternatives'])==2
