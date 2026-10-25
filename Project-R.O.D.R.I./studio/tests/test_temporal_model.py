import json
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import StandardScaler
from rodri_studio import temporal_model as module


def test_saved_forest_matches_fitted_estimator():
    rng=np.random.default_rng(42);x=rng.normal(size=(45,7));y=np.array(['off_ball','receive','pass']*15)
    s=StandardScaler().fit(x);h=RandomForestClassifier(n_estimators=15,max_depth=4,random_state=42).fit(s.transform(x),y)
    saved=json.loads(json.dumps(module.serialize_classifier(h,list(range(7)),s.mean_,s.scale_)))
    np.testing.assert_allclose(np.stack([module.probabilities(v,saved) for v in x]),h.predict_proba(s.transform(x)),atol=1e-12)


def test_float32_tree_input_does_not_round_float64_threshold():
    x=float(np.float32(.48112279176712036));threshold=.48112278431653976
    tree=dict(left=[1,-1,-1],right=[2,-1,-1],feature=[0,-2,-2],threshold=[threshold,-2,-2],value=[[.5,.5],[1,0],[0,1]])
    model=dict(indices=[0],mean=[0],scale=[1],format='forest_v1',trees=[tree])
    np.testing.assert_array_equal(module.probabilities([x],model),[0,1])


def test_hierarchical_scores_are_marginal_probabilities():
    gate=dict(format='linear_v1',indices=[0],mean=[0],scale=[1],classes=['event','off_ball'],coef=[[0]],intercept=[0])
    event=dict(format='linear_v1',indices=[0],mean=[0],scale=[1],classes=['carry','pass','receive'],coef=[[0],[0],[0]],intercept=[0,0,0])
    model=dict(format='hierarchical_v1',classes=['carry','off_ball','pass','receive'],gate=gate,event=event)
    p=module.probabilities([0],model)
    np.testing.assert_allclose(p,[1/6,.5,1/6,1/6]);assert abs(p.sum()-1)<1e-12


def test_temporal_features_only_read_past_frames(monkeypatch):
    from rodri_studio import visual_model,motion
    times=[]
    def frame(path,t):times.append(t);return np.zeros((360,640,3),np.uint8),np.floor(t*25)/25
    monkeypatch.setattr(visual_model,'frame_at',frame)
    monkeypatch.setattr(motion,'motion_features',lambda a,b,c:np.zeros(26))
    monkeypatch.setattr(module,'locate_ball',lambda image:(0.,None))
    v=module.extract('unused',10.03,[20,20,40,60]);assert v.shape==(104,)
    assert len(times)==4 and all(t<=10.03 for t in times)


def test_canonical_box_matches_resolution_change():
    image,box=module.canonical(np.zeros((1080,1920,3),np.uint8),[300,300,600,900])
    assert image.shape==(360,640,3);np.testing.assert_allclose(box,[100,100,200,300])
