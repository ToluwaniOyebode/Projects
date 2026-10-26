"""Encode reviewed real-video observations with resumable, causal V4 features."""
import argparse,hashlib,json,sys
from pathlib import Path
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from rodri_studio.sequence_model import extract,FEATURE_VERSION
from rodri_studio.edited_video import validate_observation


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--videos',type=Path,required=True);p.add_argument('--data',type=Path,default=Path('data/v4'));args=p.parse_args()
    source=args.data/'reviewed_events.json';rows=json.loads(source.read_text());cache=args.data/'feature_rows';cache.mkdir(exist_ok=True,parents=True);features=[];evidence=[]
    for i,r in enumerate(rows):
        if r.get('replay') or r.get('source_type','real')!='real' or r['target_seconds']<=r['observation_seconds']:raise ValueError('Invalid training observation')
        timeline=validate_observation(args.videos/r['source_filename'],r)
        digest=hashlib.sha256(json.dumps(dict(row=r,feature_version=FEATURE_VERSION,edit_timeline=timeline.metadata if timeline else None),sort_keys=True).encode()).hexdigest();file=cache/(digest+'.json')
        if file.exists():q=json.loads(file.read_text())
        else:
            x,e=extract(args.videos/r['source_filename'],r['observation_seconds'],r['box']);q=dict(features=x.tolist(),evidence=e,id=r['id'],feature_version=FEATURE_VERSION);file.write_text(json.dumps(q))
        features.append(q['features']);evidence.append(q['evidence']);print('Encoded',i+1,len(rows),r['id'],flush=True)
    np.savez_compressed(args.data/'features_v4.npz',features=np.array(features),events_sha256=np.array(hashlib.sha256(source.read_bytes()).hexdigest()),feature_version=np.array(FEATURE_VERSION))
    (args.data/'feature_evidence.json').write_text(json.dumps(evidence,indent=2))

if __name__=='__main__':main()
