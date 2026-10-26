"""Train a person-detector candidate; these samples do not label next actions.

All splits are within one clip, so results do not establish unseen-match accuracy.
The candidate never replaces the default detector automatically.
"""
import argparse,csv,hashlib,json,shutil,time
from pathlib import Path
import cv2
import numpy as np
from scipy.optimize import linear_sum_assignment
import torch
from ultralytics import YOLO
import yaml

VIDEO_SHA='26c3b4016b943219855f2006d4083744a00f2e5f4770bc63a595ae378c444eda'
SPLITS={'train':list(range(1,451,15)),'val':list(range(601,721,15)),'test':list(range(781,901,15))}


def load_boxes(path):
    with path.open() as f:rows=list(csv.reader(f))
    if len(rows)!=904 or any(len(row)!=93 for row in rows):raise ValueError('Unexpected annotation shape')
    teams,_,attributes=rows[:3];result={}
    for row in rows[4:]:
        boxes=[]
        for offset in range(1,len(row),4):
            if teams[offset]=='BALL':continue
            fields={attributes[offset+i]:float(row[offset+i]) for i in range(4)}
            x,y,w,h=[fields[k] for k in ['bb_left','bb_top','bb_width','bb_height']]
            if not np.isfinite([x,y,w,h]).all() or w<=0 or h<=0:raise ValueError('Invalid box')
            boxes.append([x,y,x+w,y+h])
        if len(boxes)!=22:raise ValueError('Expected 22 players')
        result[int(row[0])]=boxes
    if set(result)!=set(range(1,901)):raise ValueError('Invalid frame IDs')
    return result


def prepare(samples,out,names):
    source=samples/'soccertrack_top_view_0000_0030.mp4'
    if hashlib.sha256(source.read_bytes()).hexdigest()!=VIDEO_SHA:raise ValueError('Unexpected source hash')
    labels=load_boxes(samples/'atomscott_D_20220220_1_0000_0030.csv')
    cap=cv2.VideoCapture(str(source));width,height=cap.get(3),cap.get(4)
    lookup={frame:split for split,frames in SPLITS.items() for frame in frames}
    try:
        for frame in range(1,max(lookup)+1):
            ok,image=cap.read()
            if not ok:raise ValueError('Video ended early')
            if frame not in lookup:continue
            split=lookup[frame];images=out/'images'/split;annotations=out/'labels'/split
            images.mkdir(parents=True,exist_ok=True);annotations.mkdir(parents=True,exist_ok=True)
            if not cv2.imwrite(str(images/f'{frame:06d}.jpg'),image):raise OSError('Frame write failed')
            lines=[]
            for x1,y1,x2,y2 in labels[frame]:
                x1,x2=np.clip([x1,x2],0,width);y1,y2=np.clip([y1,y2],0,height)
                if x2<=x1 or y2<=y1:raise ValueError('Box outside video')
                lines.append(f'0 {(x1+x2)/(2*width):.9f} {(y1+y2)/(2*height):.9f} {(x2-x1)/width:.9f} {(y2-y1)/height:.9f}')
            (annotations/f'{frame:06d}.txt').write_text('\n'.join(lines)+'\n')
    finally:cap.release()
    # Preserve the pretrained 80-class head; class zero is person.
    config=dict(path=str(out.resolve()),train='images/train',val='images/val',test='images/test',names=names)
    (out/'dataset.yaml').write_text(yaml.safe_dump(config))
    (out/'split_manifest.json').write_text(json.dumps(dict(source_sha256=VIDEO_SHA,source='https://www.kaggle.com/datasets/atomscott/soccertrack',original_match_group='soccertrack_D_20220220_1',splits=SPLITS,label_type='22 person boxes per frame; ball excluded',scope='Temporally separated frames of SAME clip, not independent-match evaluation'),indent=2))
    return labels


def add_broadcast_rehearsal(directory,reviewed_path,out,teacher,imgsz):
    """Automatic teacher labels preserve existing behaviour; these are not truth."""
    reviewed=json.loads(reviewed_path.read_text())
    records=[]
    for source in sorted(directory.glob('match_H*.mp4')):
        cap=cv2.VideoCapture(str(source))
        for timestamp in [10.,30.,50.,70.]:
            # Keep exact and nearby actor-regression observations out of rehearsal.
            if any(r['source_filename']==source.name and abs(r['observation_seconds']-timestamp)<5 for r in reviewed):continue
            cap.set(cv2.CAP_PROP_POS_MSEC,timestamp*1000);ok,image=cap.read()
            if not ok:raise ValueError('Cannot decode broadcast rehearsal frame')
            prediction=teacher.predict(image,classes=[0],device='cpu',conf=.3,imgsz=imgsz,verbose=False)[0]
            boxes=prediction.boxes.xyxy.cpu().numpy();height,width=image.shape[:2]
            stem=f"rehearsal_{source.stem}_{int(timestamp):04d}"
            if not cv2.imwrite(str(out/'images/train'/f'{stem}.jpg'),image):raise OSError('Frame write failed')
            lines=[f'0 {(x1+x2)/(2*width):.9f} {(y1+y2)/(2*height):.9f} {(x2-x1)/width:.9f} {(y2-y1)/height:.9f}' for x1,y1,x2,y2 in boxes]
            (out/'labels/train'/f'{stem}.txt').write_text('\n'.join(lines)+'\n')
            records.append(dict(source_filename=source.name,time=timestamp,person_boxes=len(boxes),label_type='automatic original-detector pseudo-label; not verified ground truth'))
        cap.release()
    if not records:raise ValueError('No broadcast rehearsal frames found')
    manifest=out/'split_manifest.json';metadata=json.loads(manifest.read_text());metadata['broadcast_rehearsal']=records;metadata['broadcast_rehearsal_warning']='Original edited match used for development. Rehearsal labels are teacher predictions, not new human annotations.';manifest.write_text(json.dumps(metadata,indent=2))
    return records


def pairwise_iou(a,b):
    a=np.asarray(a,float).reshape(-1,4);b=np.asarray(b,float).reshape(-1,4)
    lo=np.maximum(a[:,None,:2],b[None,:,:2]);hi=np.minimum(a[:,None,2:],b[None,:,2:])
    inter=np.maximum(hi-lo,0).prod(axis=2)
    aa=np.maximum(a[:,2:]-a[:,:2],0).prod(axis=1);ab=np.maximum(b[:,2:]-b[:,:2],0).prod(axis=1)
    return inter/np.maximum(aa[:,None]+ab[None,:]-inter,1e-9)


def evaluate(weights,dataset,labels,split,imgsz):
    model=YOLO(str(weights));totals=dict(tp=0,fp=0,fn=0);rows=[]
    for frame in SPLITS[split]:
        prediction=model.predict(str(dataset/'images'/split/f'{frame:06d}.jpg'),classes=[0],device='cpu',imgsz=imgsz,conf=.3,verbose=False)[0]
        boxes=prediction.boxes.xyxy.cpu().numpy();overlap=pairwise_iou(boxes,labels[frame])
        if overlap.size:
            ri,ci=linear_sum_assignment(-((overlap>=.5).astype(float)+overlap*.001));tp=int((overlap[ri,ci]>=.5).sum())
        else:tp=0
        fp=len(boxes)-tp;fn=len(labels[frame])-tp
        for key,value in dict(tp=tp,fp=fp,fn=fn).items():totals[key]+=value
        rows.append(dict(frame=frame,detected=len(boxes),tp=tp,fp=fp,fn=fn))
    precision=totals['tp']/max(totals['tp']+totals['fp'],1);recall=totals['tp']/max(totals['tp']+totals['fn'],1)
    return dict(**totals,precision=precision,recall=recall,f1=2*precision*recall/max(precision+recall,1e-9),confidence_threshold=.3,iou_threshold=.5,frames=rows)


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--samples',type=Path,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--weights',type=Path,default=Path('models/yolo11n.pt'));p.add_argument('--broadcast-directory',type=Path);p.add_argument('--broadcast-reviewed',type=Path,default=Path('data/general_2017/reviewed_events.json'));p.add_argument('--epochs',type=int,default=8);p.add_argument('--imgsz',type=int,default=1024);args=p.parse_args()
    if args.epochs<1:raise ValueError('Need at least one epoch')
    args.out.mkdir(parents=True,exist_ok=True)
    if (args.out/'training_report.json').exists():raise ValueError('Preserve existing run; use new output')
    torch.set_num_threads(4);torch.set_num_interop_threads(2)
    model=YOLO(str(args.weights));dataset=args.out/'dataset';labels=prepare(args.samples,dataset,model.names);rehearsal=add_broadcast_rehearsal(args.broadcast_directory,args.broadcast_reviewed,dataset,model,args.imgsz) if args.broadcast_directory else [];started=time.perf_counter()
    model.train(data=str(dataset/'dataset.yaml'),epochs=args.epochs,imgsz=args.imgsz,batch=2,device='cpu',workers=0,optimizer='AdamW',lr0=.0005,lrf=.1,freeze=10,seed=42,deterministic=True,amp=False,cache=False,plots=False,patience=0,mosaic=0,mixup=0,fliplr=.5,flipud=0,translate=.03,scale=.1,degrees=0,project=str(args.out/'runs'),name='soccertrack_person',exist_ok=False)
    candidate=args.out/'runs'/'soccertrack_person'/'weights'/'best.pt';frozen=args.out/'soccertrack_person_candidate.pt'
    if not candidate.exists():raise ValueError('No trained weights produced')
    frozen_sha=hashlib.sha256(candidate.read_bytes()).hexdigest();shutil.copyfile(candidate,frozen)
    baseline=evaluate(args.weights,dataset,labels,'test',args.imgsz);after=evaluate(frozen,dataset,labels,'test',args.imgsz)
    report=dict(task='person_detection',candidate=frozen.name,candidate_sha256=frozen_sha,pretrained_sha256=hashlib.sha256(args.weights.read_bytes()).hexdigest(),epochs=args.epochs,imgsz=args.imgsz,training_frames=len(SPLITS['train'])+len(rehearsal),verified_training_frames=len(SPLITS['train']),pseudo_labelled_rehearsal_frames=len(rehearsal),pseudo_labelled_boxes=sum(r['person_boxes'] for r in rehearsal),development_frames=len(SPLITS['val']),regression_frames=len(SPLITS['test']),training_boxes=22*len(SPLITS['train']),elapsed_seconds=time.perf_counter()-started,baseline=baseline,candidate_metrics=after,installed_as_default=False,independent_match_accuracy=None,next_action_model_retrained=False,warning='Same-clip temporal regression only. Drone-view adaptation may degrade broadcast detection. No action-anticipation improvement established.')
    (args.out/'training_report.json').write_text(json.dumps(report,indent=2));print('FINAL_REPORT',json.dumps(report),flush=True)


if __name__=='__main__':main()
