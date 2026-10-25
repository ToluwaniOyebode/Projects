"""Fit a five-class action model and learned off-ball movement from reviewed clips."""
import argparse
from collections import Counter
import hashlib,json,sys
from pathlib import Path
import numpy as np
from sklearn.ensemble import RandomForestClassifier,ExtraTreesClassifier
from sklearn.linear_model import LogisticRegression,Ridge
from sklearn.metrics import f1_score,accuracy_score,classification_report
from sklearn.model_selection import LeaveOneGroupOut
from sklearn.preprocessing import StandardScaler
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from rodri_studio.temporal_model import extract,camera_relative_target,serialize_classifier,probabilities,FEATURE_VERSION


def estimator(name):
    family,arg=name.split(':');weighted='balanced' if 'balanced' in family else None
    if family.startswith('logistic'):return LogisticRegression(C=float(arg),class_weight=weighted,max_iter=3000,random_state=42)
    cls=ExtraTreesClassifier if family.startswith('extra') else RandomForestClassifier
    return cls(n_estimators=120,max_depth=int(arg),min_samples_leaf=1,class_weight=weighted,random_state=42,n_jobs=2)


def fit_one(x,y,indices,name):
    scale=StandardScaler().fit(x[:,indices]);h=estimator(name);h.fit(scale.transform(x[:,indices]),y)
    packed=serialize_classifier(h,indices,scale.mean_,scale.scale_)
    expected=h.predict_proba(scale.transform(x[:,indices]));actual=np.stack([probabilities(v,packed) for v in x])
    if not np.allclose(expected,actual,atol=1e-7):raise ValueError('Portable checkpoint differs from sklearn')
    return packed


def fit_candidate(x,y,indices,config):
    if config[0]=='flat':return fit_one(x,y,indices,config[1])
    gate_y=np.where(y=='off_ball','off_ball','event');event=y!='off_ball'
    gate=fit_one(x,gate_y,indices,config[1]);event_indices=list(range(78,104)) if config[0]=='mixed' else indices
    head=fit_one(x[event],y[event],event_indices,config[2])
    return dict(format='hierarchical_v1',classes=sorted(set(y)),gate=gate,event=head)


def predict(x,head):
    p=np.stack([probabilities(v,head) for v in x]);return np.array(head['classes'])[p.argmax(axis=1)],p


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--videos',type=Path,required=True)
    p.add_argument('--events',type=Path,default=Path('data/v3/reviewed_events.json'))
    p.add_argument('--cache',type=Path,default=Path('data/v3/features_v32.npz'))
    p.add_argument('--out',type=Path,default=Path('models/next_action_v3.json'))
    p.add_argument('--held-out',default='inter_2023_final')
    p.add_argument('--selection',choices=['episode_cv','development'],default='episode_cv',help='Development selection explicitly tunes on the Inter development labels; its metrics are not an independent test')
    args=p.parse_args()
    rows=json.loads(args.events.read_text());digest=hashlib.sha256(args.events.read_bytes()).hexdigest();ids=set()
    for r in rows:
        if r['id'] in ids or r.get('replay') or r.get('source_type','real')!='real' or r['target_seconds']<=r['observation_seconds']:raise ValueError('Duplicate, synthetic, replay or invalid event')
        if r['target_action'] not in {'off_ball','receive','carry','pass','shot'}:raise ValueError('Unknown action')
        ids.add(r['id'])
    if args.cache.exists():
        cache=np.load(args.cache,allow_pickle=False)
        if str(cache['events_sha256'])!=digest or str(cache['feature_version'])!=FEATURE_VERSION:raise ValueError('Cache version/hash mismatch')
        x=cache['features'];motion_y=cache['movement_targets']
    else:
        features=[];targets=[]
        for i,r in enumerate(rows):
            path=args.videos/r['source_filename'];features.append(extract(path,r['observation_seconds'],r['box']))
            targets.append(camera_relative_target(path,r['observation_seconds'],r['target_seconds'],r['box'],r['target_box']) if 'target_box' in r else [np.nan,np.nan])
            print('Encoded',i+1,len(rows),r['id'],flush=True)
        x=np.stack(features);motion_y=np.asarray(targets)
        args.cache.parent.mkdir(parents=True,exist_ok=True)
        np.savez_compressed(args.cache,features=x,movement_targets=motion_y,events_sha256=np.array(digest),feature_version=np.array(FEATURE_VERSION))
    x=x.astype(float);y=np.array([r['target_action'] for r in rows]);matches=np.array([r['match_id'] for r in rows]);groups=np.array([r['episode'] for r in rows]);train=matches!=args.held_out;test=~train
    if not train.any() or not test.any():raise ValueError('Separate training and held-out matches required')
    families=dict(kinematics=[j*26+i for j in range(3) for i in list(range(13))+[20,21,22,23]],ball_only=[j*26+i for j in range(3) for i in [0,1,2,3,4,9,10,11,12,13,14,15,16,17,18,22,23]],legacy=list(range(78,104)),full=list(range(104)))
    names=['logistic_balanced:0.01','logistic_balanced:0.1','logistic_balanced:1','logistic_balanced:10','logistic:0.1','logistic:1','forest_balanced:4','forest:4','forest:8','extra_balanced:4','extra:8']
    configs=[('flat',n) for n in names]
    configs += [('hierarchical',g,e) for g in ['logistic:0.1','logistic:1','forest:4','extra:8'] for e in ['logistic_balanced:0.1','logistic_balanced:1','forest_balanced:4']]
    configs += [('mixed',g,e) for g in ['logistic:0.01','logistic:0.1','logistic:1','forest:4','extra:8'] for e in ['logistic_balanced:0.1','logistic_balanced:1']]
    records=[]
    for family,indices in families.items():
        for config in configs:
            truth=[];pred=[]
            for tr,va in LeaveOneGroupOut().split(x[train],y[train],groups[train]):
                head=fit_candidate(x[train][tr],y[train][tr],indices,config);q,_=predict(x[train][va],head);truth.extend(y[train][va]);pred.extend(q)
            record=dict(family=family,config=list(config),cv_macro_f1=float(f1_score(truth,pred,average='macro',zero_division=0)),cv_accuracy=float(accuracy_score(truth,pred)))
            records.append(record);print('CV',json.dumps(record),flush=True)
    if args.selection=='development':
        for r in records:
            h=fit_candidate(x[train],y[train],families[r['family']],r['config']);labels,_=predict(x[test],h)
            r['development_macro_f1']=float(f1_score(y[test],labels,average='macro',zero_division=0))
            r['development_accuracy']=float(accuracy_score(y[test],labels))
        best=max(records,key=lambda q:q['development_macro_f1'])
    else:best=max(records,key=lambda q:q['cv_macro_f1'])
    indices=families[best['family']];classifier=fit_candidate(x[train],y[train],indices,best['config']);q,ps=predict(x[test],classifier)
    majority=Counter(y[train]).most_common(1)[0][0]
    metrics=dict(evaluation_status='Development match holdout, repeatedly inspected; not an untouched final benchmark',held_out_match=args.held_out,training_examples=int(train.sum()),test_examples=int(test.sum()),training_episodes=len(set(groups[train])),test_episodes=len(set(groups[test])),training_distribution=dict(Counter(y[train])),test_distribution=dict(Counter(y[test])),accuracy=float(accuracy_score(y[test],q)),macro_f1=float(f1_score(y[test],q,average='macro',zero_division=0)),majority_action=majority,majority_accuracy=float(np.mean(y[test]==majority)),classification_report=classification_report(y[test],q,output_dict=True,zero_division=0),selection=best,candidate_count=len(records),iterations=records)
    # Only causal actor optical-flow channels enter the movement regressor.
    motion_indices=[j*26+i for j in range(3) for i in [11,12]]
    motion_train=train&np.isfinite(motion_y).all(axis=1);motion_test=test&np.isfinite(motion_y).all(axis=1)
    sizes=x[:,6]*360;choices=[]
    def fit_motion(mask,alpha):
        scaler=StandardScaler().fit(x[mask][:,motion_indices]);h=Ridge(alpha=alpha).fit(scaler.transform(x[mask][:,motion_indices]),motion_y[mask]);return scaler,h
    for alpha in [.01,.1,1,10,100,1000]:
        errors=[]
        for tr,va in LeaveOneGroupOut().split(x[motion_train],groups=groups[motion_train]):
            scaler=StandardScaler().fit(x[motion_train][tr][:,motion_indices]);h=Ridge(alpha=alpha).fit(scaler.transform(x[motion_train][tr][:,motion_indices]),motion_y[motion_train][tr]);pred=h.predict(scaler.transform(x[motion_train][va][:,motion_indices]));errors.extend(np.linalg.norm(pred-motion_y[motion_train][va],axis=1)*sizes[motion_train][va])
        choices.append(dict(alpha=alpha,episode_cv_error_pixels=float(np.mean(errors))))
    alpha=min(choices,key=lambda c:c['episode_cv_error_pixels'])['alpha'];scaler,reg=fit_motion(motion_train,alpha);mq=reg.predict(scaler.transform(x[motion_test][:,motion_indices]));target=motion_y[motion_test]
    movement_metrics=dict(test_examples=int(motion_test.sum()),endpoint_error_pixels_at_width640=float(np.mean(np.linalg.norm(mq-target,axis=1)*sizes[motion_test])),stationary_baseline_error_pixels=float(np.mean(np.linalg.norm(target,axis=1)*sizes[motion_test])),choices=choices,selected_alpha=alpha)
    enabled=movement_metrics['endpoint_error_pixels_at_width640']<movement_metrics['stationary_baseline_error_pixels']
    def pack_motion(mask):
        s,h=fit_motion(mask,alpha);return dict(indices=motion_indices,mean=s.mean_.tolist(),scale=s.scale_.tolist(),coef=h.coef_.tolist(),intercept=h.intercept_.tolist(),units='actor body heights, camera compensated',enabled=enabled,validation=movement_metrics)
    metrics['movement']=movement_metrics
    metrics['selection_source']=args.selection
    metrics['majority_macro_f1_fixed_classes']=float(f1_score(y[test],np.repeat(majority,int(test.sum())),labels=sorted(set(y)),average='macro',zero_division=0))
    if args.selection=='development':metrics['evaluation_status']='Inter development set used for model selection; these are development results, not independent test accuracy'
    common=dict(kind='causal_temporal_v3',feature_version=FEATURE_VERSION,horizon_seconds=.6,classes=classifier['classes'],held_out_metrics=metrics,events_sha256=digest,calibrated=False,synthetic_training=False,label_quality='Single-AI-reviewed contextual identity/actions; no independent human audit',forecast_target='Observed coarse state/event about 0.6 seconds ahead; a plausible receiving option may remain unrealized')
    event=train&(y!='off_ball');conditional=fit_one(x[event],y[event],list(range(78,104)),'logistic_balanced:1')
    event_test=test&(y!='off_ball');conditional_labels,_=predict(x[event_test],conditional)
    metrics['conditional_event_metrics']=dict(examples=int(event_test.sum()),correct=int(np.sum(conditional_labels==y[event_test])),accuracy=float(np.mean(conditional_labels==y[event_test])),scope='Selected actual on-ball events only, not counterfactual validity')
    held=dict(**common,classifier=classifier,conditional_head=conditional,movement_head=pack_motion(motion_train),training_matches=sorted(set(matches[train])),deployment_refit=False)
    args.out.parent.mkdir(parents=True,exist_ok=True);args.out.with_name(args.out.stem+'_holdout.json').write_text(json.dumps(held))
    deployment=dict(**common,classifier=fit_candidate(x,y,indices,best['config']),conditional_head=fit_one(x[y!='off_ball'],y[y!='off_ball'],list(range(78,104)),'logistic_balanced:1'),movement_head=pack_motion(np.isfinite(motion_y).all(axis=1)),training_matches=sorted(set(matches)),deployment_refit=True)
    args.out.write_text(json.dumps(deployment))
    predictions=[dict(id=r['id'],truth=r['target_action'],prediction=str(label),probabilities=dict(zip(classifier['classes'],p.tolist()))) for r,label,p in zip([r for r,m in zip(rows,test) if m],q,ps)]
    (args.events.parent/'evaluation.json').write_text(json.dumps(dict(metrics=metrics,predictions=predictions),indent=2));print('FINAL',json.dumps(metrics),flush=True)


if __name__=='__main__':main()
