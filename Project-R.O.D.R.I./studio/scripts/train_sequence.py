"""Select on grouped development folds, freeze, then evaluate reserved episodes once.

Real video and reviewer-provided actor/action labels are required. A held-out
passage from a previously used match is never described as an unseen-match test.
"""
import argparse,hashlib,json,sys
from collections import Counter
from pathlib import Path
import numpy as np
from sklearn.ensemble import ExtraTreesClassifier,RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score,f1_score,classification_report
from sklearn.model_selection import GroupKFold
from sklearn.preprocessing import StandardScaler
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from rodri_studio.sequence_model import FEATURE_VERSION
from rodri_studio.temporal_model import serialize_classifier,probabilities

CLASSES=['carry','off_ball','pass','receive','shot']


def temporal_partition(rows,spec):
    """Cluster entire episodes by temporal proximity before assigning folds.

    The interval includes three seconds of input and the reviewed future target.
    Neighboring episodes in a reserved cluster are embargoed, never trained.
    """
    episodes={}
    for r in rows:
        key=(r['match_id'],r['episode']);a,b=r['observation_seconds']-3,r['target_seconds']
        if key not in episodes:episodes[key]=[a,b]
        else:episodes[key]=[min(a,episodes[key][0]),max(b,episodes[key][1])]
    mapping={};reserved=set(spec['held_out_episodes']);excluded=set()
    for match in sorted({k[0] for k in episodes}):
        clusters=[]
        for key in sorted((k for k in episodes if k[0]==match),key=lambda k:episodes[k][0]):
            a,b=episodes[key]
            if not clusters or a-clusters[-1]['end']>spec['minimum_embargo_seconds']:clusters.append(dict(end=b,keys=[key]))
            else:clusters[-1]['end']=max(b,clusters[-1]['end']);clusters[-1]['keys'].append(key)
        for i,cluster in enumerate(clusters):
            has_test=any(k[1] in reserved for k in cluster['keys'])
            for key in cluster['keys']:
                mapping[key]=f'{match}:cluster_{i}'
                if has_test and key[1] not in reserved:excluded.add(key)
    test=np.array([r['episode'] in reserved for r in rows]);train=np.array([not t and (r['match_id'],r['episode']) not in excluded for r,t in zip(rows,test)])
    groups=np.array([mapping[(r['match_id'],r['episode'])] for r in rows])
    if not test.any() or not train.any() or set(groups[train])&set(groups[test]):raise ValueError('Invalid or leaking split')
    return train,test,groups


def estimator(name):
    family,c=name.split(':');weighted='balanced' if family.endswith('_balanced') else None
    if family.startswith('logistic'):return LogisticRegression(C=float(c),max_iter=3000,class_weight=weighted,random_state=42)
    cls=ExtraTreesClassifier if family.startswith('extra') else RandomForestClassifier
    return cls(n_estimators=120,max_depth=int(c),class_weight=weighted,min_samples_leaf=2,random_state=42,n_jobs=2)


def fit(x,y,indices,name):
    s=StandardScaler().fit(x[:,indices]);h=estimator(name).fit(s.transform(x[:,indices]),y)
    packed=serialize_classifier(h,indices,s.mean_,s.scale_)
    if not np.allclose(h.predict_proba(s.transform(x[:,indices])),np.stack([probabilities(v,packed) for v in x]),atol=1e-7):raise ValueError('Portable scorer mismatch')
    return packed


def predict(x,h):
    ps=np.stack([probabilities(v,h) for v in x]);return np.array(h['classes'])[ps.argmax(axis=1)],ps


def metrics(y,q):
    return dict(examples=len(y),correct=int(np.sum(y==q)),accuracy=float(accuracy_score(y,q)),macro_f1=float(f1_score(y,q,labels=CLASSES,average='macro',zero_division=0)),classification_report=classification_report(y,q,labels=CLASSES,output_dict=True,zero_division=0))


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--videos',type=Path,required=True);p.add_argument('--data',type=Path,default=Path('data/v4'));p.add_argument('--out',type=Path,default=Path('models/next_action_v4.json'));args=p.parse_args()
    rows=json.loads((args.data/'reviewed_events.json').read_text());digest=hashlib.sha256((args.data/'reviewed_events.json').read_bytes()).hexdigest();spec=json.loads((args.data/'frozen_episode_split.json').read_text())
    if any(r.get('replay') or r.get('source_type','real')!='real' or r['target_seconds']<=r['observation_seconds'] for r in rows) or len(set(r['id'] for r in rows))!=len(rows):raise ValueError('Invalid/replay/synthetic/duplicate labels')
    cache=np.load(args.data/'features_v4.npz',allow_pickle=False)
    if str(cache['events_sha256'])!=digest or str(cache['feature_version'])!=FEATURE_VERSION:raise ValueError('Stale cache')
    x=cache['features'];y=np.array([r['target_action'] for r in rows]);train,test,groups=temporal_partition(rows,spec)
    families=dict(current=list(range(11))+list(range(101,105)),sequence=list(range(105)),hybrid=list(range(131)),legacy=list(range(105,131)))
    names=['logistic_balanced:0.01','logistic_balanced:0.1','logistic:0.1','logistic:1','extra_balanced:4','extra:8','forest_balanced:4','forest:8']
    records=[];folds=list(GroupKFold(n_splits=min(4,len(set(groups[train])))).split(x[train],y[train],groups[train]))
    for family,indices in families.items():
        for name in names:
            pred=np.empty(train.sum(),dtype=object)
            for tr,va in folds:
                h=fit(x[train][tr],y[train][tr],indices,name);pred[va]=predict(x[train][va],h)[0]
            record=dict(family=family,config=name,cv_macro_f1=float(f1_score(y[train],pred,labels=CLASSES,average='macro',zero_division=0)),cv_accuracy=float(accuracy_score(y[train],pred)))
            records.append(record);print(json.dumps(record),flush=True)
    best=max(records,key=lambda r:(r['cv_macro_f1'],r['cv_accuracy']));indices=families[best['family']]
    common=dict(kind='causal_sequence_v4',feature_version=FEATURE_VERSION,horizon_seconds=.6,classes=CLASSES,events_sha256=digest,calibrated=False,synthetic_training=False,label_quality='Single-AI contextual identity/action review; no independent human audit',training_matches=sorted({r['match_id'] for r,m in zip(rows,train) if m}),deployment_refit=False,selection=best,forecast_target='Observed coarse state/event about 0.6 seconds ahead; conditional receiving requires delivery')
    h=fit(x[train],y[train],indices,best['config']);event=train&(y!='off_ball');conditional=fit(x[event],y[event],indices,'logistic_balanced:0.1')
    frozen=dict(**common,classifier=h,conditional_head=conditional)
    args.out.parent.mkdir(parents=True,exist_ok=True);frozen_path=args.out.with_name(args.out.stem+'_frozen.json');frozen_path.write_text(json.dumps(frozen))
    freeze=dict(checkpoint_sha256=hashlib.sha256(frozen_path.read_bytes()).hexdigest(),selection_source='Development temporal-cluster GroupKFold only; no reserved labels used for selection',selection=best,train_ids=[r['id'] for r,m in zip(rows,train) if m],test_ids=[r['id'] for r,m in zip(rows,test) if m],embargoed_ids=[r['id'] for r,a,b in zip(rows,train,test) if not a and not b],candidates=records)
    (args.data/'selection_freeze.json').write_text(json.dumps(freeze,indent=2))
    # No candidate fitting/selection below this point. Frozen test evaluated once.
    q,ps=predict(x[test],h);majority=Counter(y[train]).most_common(1)[0][0];baseline=np.repeat(majority,test.sum());old=json.loads((args.out.parent/'next_action_v3.json').read_text())
    from rodri_studio.temporal_model import extract as extract_v3
    oldx=np.stack([extract_v3(args.videos/r['source_filename'],r['observation_seconds'],r['box'],legacy_only=True) for r,m in zip(rows,test) if m]);oq,op=predict(oldx,old['classifier'])
    result=dict(evaluation_status='Frozen new episodes from previously used matches; not unseen-match accuracy',selection_source=freeze['selection_source'],training_examples=int(train.sum()),test_examples=int(test.sum()),embargoed_examples=len(freeze['embargoed_ids']),training_clusters=len(set(groups[train])),test_episodes=len(set(r['episode'] for r,m in zip(rows,test) if m)),training_distribution=dict(Counter(y[train])),test_distribution=dict(Counter(y[test])),selection=best,**metrics(y[test],q),majority_action=majority,majority_accuracy=float(np.mean(y[test]==baseline)),majority_metrics=metrics(y[test],baseline),v3_identical_cases=metrics(y[test],oq),frozen_sha256=freeze['checkpoint_sha256'],independent_match_accuracy=None,independent_human_review=False)
    on=y[test]!='off_ball';cq,_=predict(x[test][on],conditional);result['conditional_event_metrics']=metrics(y[test][on],cq);result['conditional_event_metrics']['scope']='Actual on-ball events only; not validation of unrealized alternatives'
    predictions=[dict(id=r['id'],truth=r['target_action'],prediction=str(label),v3_prediction=str(oldlabel),probabilities=dict(zip(h['classes'],p.tolist()))) for r,label,oldlabel,p in zip([r for r,m in zip(rows,test) if m],q,oq,ps)]
    (args.data/'evaluation.json').write_text(json.dumps(dict(metrics=result,predictions=predictions),indent=2));frozen['held_out_metrics']=result;args.out.write_text(json.dumps(frozen))
    (args.data/'test_events.json').write_text(json.dumps([r for r,m in zip(rows,test) if m],indent=2));print('FINAL',json.dumps(result),flush=True)

if __name__=='__main__':main()
