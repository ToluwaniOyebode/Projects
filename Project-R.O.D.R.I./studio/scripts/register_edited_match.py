"""Register validated edited clips without copying their bytes or inventing labels."""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import sys
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from rodri_studio.edited_video import EditTimeline, FORMAT


def register(clips, metadata, data, match_id):
    with zipfile.ZipFile(metadata) as z:
        mapping = list(csv.DictReader(z.read('source_timestamp_map.csv').decode().splitlines()))
        verification = json.loads(z.read('verification.json'))
    if verification.get('status') != 'passed':
        raise ValueError('Clip export verification did not pass')
    checks = {r['clip']:r for r in verification['checks']}
    sources = []
    # Validate every input before changing any registry or sidecar.
    for name in sorted({r['clip'] for r in mapping}):
        if Path(name).name != name:
            raise ValueError('Clip name must be a basename')
        path = clips/name
        with path.open('rb') as f:
            digest = hashlib.file_digest(f,'sha256').hexdigest()
        check = checks[name]
        if digest != check['sha256'] or path.stat().st_size != check['size_bytes']:
            raise ValueError('Clip bytes differ from validated export: '+name)
        segments=[]
        for row in mapping:
            if row['clip'] != name:
                continue
            segments.append({k:float(row[k]) for k in ['source_start_seconds','source_end_seconds_exclusive','clip_start_seconds','clip_end_seconds_exclusive']} | {'continuous_sequence_id':row['continuous_sequence_id']})
        timeline = dict(format=FORMAT,match_id=match_id,rodri_present=False,actor_scope='general_football',sha256=digest,segments=segments)
        parsed = EditTimeline(timeline)
        if abs(parsed.segments[-1]['clip_end_seconds_exclusive']-check['duration_seconds'])>1e-6:
            raise ValueError('Timeline does not cover the complete clip')
        sources.append(dict(filename=name,match_id=match_id,sha256=digest,bytes=check['size_bytes'],fps=25.,width=1280,height=720,duration_seconds=check['duration_seconds'],rodri_present=False,actor_scope='general_football',edit_metadata=timeline,label_status='Sparse reviewed examples are stored separately; full-match actions are not densely annotated.'))
    data.mkdir(parents=True,exist_ok=True)
    registry = data/'video_manifest.json'
    old = json.loads(registry.read_text()) if registry.exists() else []
    hashes = {r['sha256'] for r in sources}
    combined = [r for r in old if r['sha256'] not in hashes]+sources
    for row in sources:
        Path(str(clips/row['filename'])+'.edits.json').write_text(json.dumps(row['edit_metadata'],indent=2))
    temp = registry.with_suffix('.tmp')
    temp.write_text(json.dumps(combined,indent=2));temp.replace(registry)
    return sources


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--clips',type=Path,required=True)
    p.add_argument('--metadata',type=Path,required=True)
    p.add_argument('--data',type=Path,default=Path('data'))
    p.add_argument('--match-id',default='real_madrid_barcelona_2017')
    args=p.parse_args()
    rows=register(args.clips,args.metadata,args.data,args.match_id)
    print(json.dumps(dict(clips=len(rows),seconds=sum(r['duration_seconds'] for r in rows),rodri_present=False,match_id=args.match_id)))


if __name__=='__main__':
    main()
