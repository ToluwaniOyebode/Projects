"""Train an experimental mixed-player V5 head; preserve the V4 benchmark split.

All clips of the added match share one CV group. The old reserved cases are a
reused regression benchmark, not a new independent test or model-selection set.
"""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import sys
import numpy as np
from sklearn.metrics import accuracy_score, f1_score
from sklearn.model_selection import LeaveOneGroupOut

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from train_sequence import temporal_partition, fit, predict, metrics, CLASSES
from rodri_studio.sequence_model import FEATURE_VERSION


def read_features(data):
    source=data/'reviewed_events.json'
    rows=json.loads(source.read_text())
    cache=np.load(data/'features_v4.npz',allow_pickle=False)
    if str(cache['events_sha256'])!=hashlib.sha256(source.read_bytes()).hexdigest() or str(cache['feature_version'])!=FEATURE_VERSION:
        raise ValueError('Feature cache does not match reviewed labels')
    x=cache['features']
    if x.shape!=(len(rows),131) or not np.isfinite(x).all():
        raise ValueError('Invalid feature rows')
    if len({r['id'] for r in rows})!=len(rows) or any(r.get('replay') or r.get('source_type')!='real' or r['target_action'] not in CLASSES or r['target_seconds']<=r['observation_seconds'] for r in rows):
        raise ValueError('Invalid reviewed rows')
    return rows,x


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--original',type=Path,default=Path('data/v4'))
    p.add_argument('--general',type=Path,default=Path('data/general_2017'))
    p.add_argument('--out',type=Path,default=Path('models/next_action_v5.json'))
    args=p.parse_args()
    old,oldx=read_features(args.original);new,newx=read_features(args.general)
    if not new or any(r.get('actor_scope')!='general_football' or r.get('rodri_present') is not False for r in new):
        raise ValueError('Generic actors must never be labelled Rodri')
    if len({r['match_id'] for r in new})!=1:
        raise ValueError('The edited clips must share one original match ID')
    eligible,test,clusters=temporal_partition(old,json.loads((args.original/'frozen_episode_split.json').read_text()))
    train_rows=[r for r,m in zip(old,eligible) if m]+new
    x=np.vstack([oldx[eligible],newx]);y=np.array([r['target_action'] for r in train_rows]);groups=np.array([r['match_id'] for r in train_rows])
    if len(set(groups))<3:raise ValueError('Need three original-match groups')
    families={'current':list(range(11))+list(range(101,105)),'sequence':list(range(105)),'hybrid':list(range(131))}
    names=['logistic_balanced:0.01','logistic_balanced:0.1','extra_balanced:4','forest_balanced:4']
    candidates=[];folds=list(LeaveOneGroupOut().split(x,y,groups))
    for family,indices in families.items():
        for name in names:
            q=np.empty(len(y),dtype=object);fold_reports=[]
            for tr,va in folds:
                head=fit(x[tr],y[tr],indices,name);q[va]=predict(x[va],head)[0]
                majority=Counter(y[tr]).most_common(1)[0][0]
                fold_reports.append(dict(held_out_match=str(groups[va][0]),examples=int(va.size),accuracy=float(accuracy_score(y[va],q[va])),majority_accuracy=float(np.mean(y[va]==majority))))
            score=dict(family=family,config=name,cv_macro_f1=float(f1_score(y,q,labels=CLASSES,average='macro',zero_division=0)),cv_accuracy=float(accuracy_score(y,q)),folds=fold_reports)
            candidates.append(score);print(json.dumps(score),flush=True)
    best=max(candidates,key=lambda r:(r['cv_macro_f1'],r['cv_accuracy']))
    indices=families[best['family']]
    head=fit(x,y,indices,best['config']);event=y!='off_ball'
    conditional=fit(x[event],y[event],indices,'logistic_balanced:0.1')
    out=dict(kind='causal_sequence_v4',version=5,feature_version=FEATURE_VERSION,horizon_seconds=.6,classes=CLASSES,classifier=head,conditional_head=conditional,training_matches=sorted(set(groups)),deployment_refit=False,calibrated=False,synthetic_training=False,label_quality='Sparse single-AI visual/context review; no independent human audit',training_examples=len(y),generic_training_examples=len(new),selection=best,selection_scope='Leave-one-original-match-out development CV; used for selection, not an untouched final test',frozen_before_regression_evaluation=True)
    args.out.parent.mkdir(parents=True,exist_ok=True)
    frozen=args.out.with_name(args.out.stem+'_frozen.json');frozen.write_text(json.dumps(out))
    frozen_sha=hashlib.sha256(frozen.read_bytes()).hexdigest()
    truth=np.array([r['target_action'] for r,m in zip(old,test) if m]);q,ps=predict(oldx[test],head)
    previous=json.loads((args.out.parent/'next_action_v4.json').read_text());before=predict(oldx[test],previous['classifier'])[0]
    majority=Counter(y).most_common(1)[0][0]
    report=dict(**metrics(truth,q),scope='Previously scored V4 reserved episodes, reused only as a regression benchmark; not new independent accuracy',v4_identical_cases=metrics(truth,before),majority_accuracy=float(np.mean(truth==majority)),independent_match_accuracy=None,independent_human_review=False,frozen_sha256=frozen_sha,training_examples=len(y),generic_training_examples=len(new),training_distribution=dict(Counter(y)),generic_distribution=dict(Counter(r['target_action'] for r in new)))
    warning=f"V5 experimental mixed-player model: {len(new)} added generic-player observations. Reused Rodri regression cases: {report['correct']}/{report['examples']}; V4: {report['v4_identical_cases']['correct']}/{report['examples']}. This is not a new independent test. Match-grouped development CV was used for selection. Unseen-match and Rodri-specific improvement are not established; scores are uncalibrated."
    warning+=' V4 remains the default Rodri checkpoint: V5 has not demonstrated an improvement across action classes.'
    out.update(held_out_metrics=report,evaluation_warning=warning,recommended_default=False,deployment_status='optional_experimental_candidate')
    args.out.write_text(json.dumps(out))
    result=dict(metrics=report,selection=best,candidates=candidates,train_ids=[r['id'] for r in train_rows],regression_ids=[r['id'] for r,m in zip(old,test) if m],cases=[dict(id=r['id'],truth=r['target_action'],prediction=str(label),v4_prediction=str(prior)) for r,label,prior in zip([r for r,m in zip(old,test) if m],q,before)],labels_sha256=dict(original=hashlib.sha256((args.original/'reviewed_events.json').read_bytes()).hexdigest(),general=hashlib.sha256((args.general/'reviewed_events.json').read_bytes()).hexdigest()))
    (args.general/'training_report.json').write_text(json.dumps(result,indent=2));print('FINAL',json.dumps(report),flush=True)


if __name__=='__main__':main()
