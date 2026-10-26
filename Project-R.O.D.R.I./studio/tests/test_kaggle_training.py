"""Data integrity and evaluation safeguards for optional Kaggle fine-tuning."""
import importlib.util
from pathlib import Path
import numpy as np
import pytest

spec=importlib.util.spec_from_file_location('kaggle_training',Path(__file__).parents[1]/'scripts'/'train_kaggle_detector.py')
training=importlib.util.module_from_spec(spec);spec.loader.exec_module(training)


def test_temporal_split_has_gaps_and_no_overlap():
    train,val,test=[training.SPLITS[k] for k in ['train','val','test']]
    assert max(train)<min(val)<max(val)<min(test)
    assert min(val)-max(train)>100
    assert min(test)-max(val)>50
    assert len(set(train+val+test))==len(train+val+test)


def test_iou_handles_empty_inputs_and_global_assignment():
    a=[[0,0,10,10],[30,30,40,40]]
    assert training.pairwise_iou([],a).shape==(0,2)
    np.testing.assert_array_equal(training.pairwise_iou(a,a[::-1]),[[0,1],[1,0]])
    assert training.pairwise_iou([[0,0,10,10]],[[5,0,15,10]])[0,0]==pytest.approx(1/3)


def test_wrong_annotation_format_is_rejected(tmp_path):
    path=tmp_path/'wrong.csv';path.write_text('frame,left,top\n1,10,20\n')
    with pytest.raises(ValueError,match='annotation shape'):training.load_boxes(path)


def test_broadcast_rehearsal_is_marked_automatic_and_excludes_review_neighbours(tmp_path,monkeypatch):
    import json
    from types import SimpleNamespace
    import torch
    videos=tmp_path/'videos';videos.mkdir();(videos/'match_H1_part01.mp4').touch()
    events=tmp_path/'events.json';events.write_text(json.dumps([dict(source_filename='match_H1_part01.mp4',observation_seconds=10),dict(source_filename='match_H1_part01.mp4',observation_seconds=51)]))
    out=tmp_path/'dataset';(out/'images/train').mkdir(parents=True);(out/'labels/train').mkdir(parents=True)
    (out/'split_manifest.json').write_text('{}')
    class Capture:
        def __init__(self,*args):pass
        def set(self,*args):pass
        def read(self):return True,np.zeros((100,160,3),dtype=np.uint8)
        def release(self):pass
    class Teacher:
        def predict(self,*args,**kwargs):return [SimpleNamespace(boxes=SimpleNamespace(xyxy=torch.tensor([[10.,10.,30.,50.]])))]
    monkeypatch.setattr(training.cv2,'VideoCapture',Capture)
    records=training.add_broadcast_rehearsal(videos,events,out,Teacher(),1024)
    assert [r['time'] for r in records]==[30.,70.]
    assert all('not verified ground truth' in r['label_type'] for r in records)
    assert len(list((out/'labels/train').glob('*.txt')))==2
    assert not (out/'images/test').exists()
