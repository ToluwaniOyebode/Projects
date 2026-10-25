"""Reproduce frozen-encoder extraction and a predeclared match holdout."""
import argparse,json,sys,hashlib
from collections import Counter
from pathlib import Path
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from rodri_studio.visual_model import visual_features,frame_at,fit_head,score_features,extract_observation


def validate_events(rows):
    ids=set()
    for r in rows:
        if r['id'] in ids:raise ValueError('Duplicate observation ID')
        ids.add(r['id'])
        if not r['observation_seconds']<r['target_seconds']:raise ValueError('Target is not in the future')
        if r.get('replay') or r.get('exclude'):raise ValueError('Excluded/replay rows cannot enter training')
        if r['target_action'] not in {'receive','carry','pass','shot'}:raise ValueError('Unknown action')
        if len(r['box'])!=4:raise ValueError('Missing actor localization')


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--videos',type=Path,required=True)
    p.add_argument('--events',type=Path,default=Path('data/reviewed_events.json'))
    p.add_argument('--held-out',default='inter_2023_final')
    p.add_argument('--out',type=Path,default=Path('models/next_action.json'))
    p.add_argument('--cache',type=Path,default=Path('data/visual_motion_features.npz'))
    p.add_argument('--refit-all',action='store_true',help='Explicit deployment refit; does not produce new held-out metrics')
    a=p.parse_args();rows=json.loads(a.events.read_text());validate_events(rows)
    digest=hashlib.sha256(a.events.read_bytes()).hexdigest()
    if a.cache.exists():
        cached=np.load(a.cache,allow_pickle=False)
        if str(cached['events_sha256'])!=digest:raise ValueError('Feature cache does not match annotations; choose a new --cache')
        x=cached['features']
    else:
        vectors=[]
        for i,row in enumerate(rows):
            image,actual=frame_at(a.videos/row['source_filename'],row['observation_seconds'])
            assert actual<=row['observation_seconds']+1e-6
            vectors.append(extract_observation(a.videos/row['source_filename'],row['observation_seconds'],row['box']))
            print(f'Encoded {i+1}/{len(rows)}: {row["id"]}',flush=True)
        x=np.stack(vectors)
        a.cache.parent.mkdir(exist_ok=True,parents=True)
        np.savez_compressed(a.cache,features=x,events_sha256=np.array(digest))
    labels=np.array([r['target_action'] for r in rows]);matches=np.array([r['match_id'] for r in rows])
    train=(matches!=a.held_out);test=~train
    if not train.any() or not test.any():raise ValueError('Training and held-out matches are both required')
    # Choose feature family by leave-one-possession-out CV on training match only.
    groups=np.array([r['episode'] for r in rows])[train]
    candidates={'appearance':list(range(1028)),'motion':list(range(1028,x.shape[1])),'combined':list(range(x.shape[1]))}
    cv_scores={}
    from sklearn.metrics import f1_score
    for name,indices in candidates.items():
        truth=[];pred=[]
        for group in sorted(set(groups)):
            a_train=groups!=group;a_test=~a_train
            h=fit_head(x[train][a_train],labels[train][a_train],set(matches[train]),indices)
            ps=np.stack([score_features(v,h) for v in x[train][a_test]])
            truth.extend(labels[train][a_test]);pred.extend(np.array(h['classes'])[ps.argmax(axis=1)])
        cv_scores[name]=float(f1_score(truth,pred,average='macro',zero_division=0))
    selected=max(cv_scores,key=cv_scores.get)
    print('Training-only episode CV:',cv_scores,'selected:',selected,flush=True)
    head=fit_head(x[train],labels[train],set(matches[train]),candidates[selected])
    head['training_episode_cv']=cv_scores;head['selected_features']=selected
    from sklearn.metrics import accuracy_score,f1_score,classification_report,confusion_matrix
    probabilities=np.stack([score_features(v,head) for v in x[test]])
    predictions=np.array(head['classes'])[probabilities.argmax(axis=1)]
    majority=Counter(labels[train]).most_common(1)[0][0]
    metrics=dict(training_episode_cv=cv_scores,selected_features=selected,evaluation_status='development match holdout; not an untouched final test after iterative development',held_out_match=a.held_out,training_matches=head['training_matches'],training_examples=int(train.sum()),test_examples=int(test.sum()),training_distribution=dict(Counter(labels[train])),test_distribution=dict(Counter(labels[test])),accuracy=float(accuracy_score(labels[test],predictions)),macro_f1=float(f1_score(labels[test],predictions,average='macro',zero_division=0)),majority_action=str(majority),majority_accuracy=float(np.mean(labels[test]==majority)),classes=head['classes'],confusion_matrix=confusion_matrix(labels[test],predictions,labels=head['classes']).tolist(),classification_report=classification_report(labels[test],predictions,zero_division=0,output_dict=True),identity_condition='reviewer-supplied actor localization; not end-to-end automatic Rodri identification',sampling='curated possession moments, not all frames of a full match',label_review='single AI reviewer; identity often supported by commentary + continuity, not legible jersey in every wide frame',events_sha256=digest)
    output_rows=[]
    for r,ps,pred in zip([r for r,m in zip(rows,test) if m],probabilities,predictions):
        output_rows.append(dict(id=r['id'],truth=r['target_action'],prediction=str(pred),probabilities=dict(zip(head['classes'],ps.tolist()))))
    report=a.out.with_name('evaluation.json');report.parent.mkdir(exist_ok=True,parents=True)
    report.write_text(json.dumps(dict(metrics=metrics,predictions=output_rows),indent=2))
    if a.refit_all:
        head=fit_head(x,labels,set(matches),candidates[selected]);head['selected_features']=selected;head['deployment_refit']=True
    else:head['deployment_refit']=False
    head['held_out_metrics']=metrics;head['events_sha256']=digest
    a.out.write_text(json.dumps(head,indent=2))
    print(json.dumps(metrics,indent=2))

if __name__=='__main__':main()
