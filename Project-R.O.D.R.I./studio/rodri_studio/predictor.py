"""Learn the next annotated action from causal image-motion features."""
import json
from pathlib import Path
import numpy as np

ACTIONS = ['receive','short_pass','long_pass','carry','shot','press','tackle','support_run','lose_possession','unknown']
FEATURES = ['x','y','vx','vy','speed','box_width','box_height']


def features(det, width, height):
    x,y = det['center']
    vx,vy = det['velocity']
    b = det['box']
    return [x,y,vx,vy,float(np.hypot(vx,vy)),(b[2]-b[0])/width,(b[3]-b[1])/height]


def predict(vector, model_path):
    if not Path(model_path).exists():
        return {'status':'untrained','alternatives':[], 'message':'No trained next-action model. Add verified labels from multiple matches and train.'}
    model = json.loads(Path(model_path).read_text())
    x = (np.array(vector)-np.array(model['mean']))/np.array(model['scale'])
    logits = np.array(model['coef']) @ x + np.array(model['intercept'])
    if len(logits)==1:
        logits = np.array([0.,float(logits[0])])
    probs = np.exp(logits-logits.max()); probs /= probs.sum()
    choices = sorted(zip(model['classes'],probs.tolist()), key=lambda v:-v[1])
    return {'status':'experimental','alternatives':[{'action':a,'probability':p} for a,p in choices[:3]], 'message':'Learned classifier scores; uncalibrated. Not a validated tactical forecast.', 'metrics':model['metrics']}


def train(rows, destination):
    from sklearn.linear_model import LogisticRegression
    from sklearn.metrics import accuracy_score, f1_score, log_loss
    valid = [r for r in rows if r.get('verified') and r.get('target_action') in ACTIONS and r['target_action'] != 'unknown' and not r.get('replay')]
    sources = {}
    for row in valid:
        source=row.get('source_video')
        if source and source in sources and sources[source]!=row['match_id']:
            raise ValueError('One source video was assigned to multiple match IDs; correct the labels before training.')
        if source: sources[source]=row['match_id']
    matches = sorted({r['match_id'] for r in valid})
    if len(matches)<3 or len(valid)<30:
        raise ValueError('Need at least 30 verified examples across 3 matches; one entire match is held out.')
    heldout = matches[-1]
    training = [r for r in valid if r['match_id'] != heldout]
    testing = [r for r in valid if r['match_id'] == heldout]
    labels = [r['target_action'] for r in training]
    if len(set(labels))<2:
        raise ValueError('Training matches need at least two action classes.')
    if not set(r['target_action'] for r in testing).issubset(labels):
        raise ValueError('Held-out match contains classes absent from training.')
    x = np.array([r['features'] for r in training], dtype=float)
    mean, scale = x.mean(axis=0), x.std(axis=0); scale[scale<1e-8]=1
    classifier = LogisticRegression(max_iter=1000, random_state=42).fit((x-mean)/scale,labels)
    xt = (np.array([r['features'] for r in testing])-mean)/scale
    truth = [r['target_action'] for r in testing]
    predicted = classifier.predict(xt)
    majority = max(set(labels),key=labels.count)
    metrics = dict(held_out_match=heldout, test_examples=len(testing), training_examples=len(training), accuracy=float(accuracy_score(truth,predicted)), macro_f1=float(f1_score(truth,predicted,average='macro',zero_division=0)), majority_accuracy=float(accuracy_score(truth,[majority]*len(testing))), log_loss=float(log_loss(truth,classifier.predict_proba(xt),labels=classifier.classes_)))
    model = dict(classes=classifier.classes_.tolist(),coef=classifier.coef_.tolist(),intercept=classifier.intercept_.tolist(),mean=mean.tolist(),scale=scale.tolist(),metrics=metrics,features=FEATURES,training_matches=matches[:-1])
    path=Path(destination); temporary=path.with_suffix('.tmp')
    temporary.write_text(json.dumps(model,indent=2)); temporary.replace(path)
    return metrics
